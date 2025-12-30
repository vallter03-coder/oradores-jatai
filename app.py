import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Discursos", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
def get_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    # Substitua pelo ID ou Nome da sua planilha
    sh = client.open("NOME_DA_SUA_PLANILHA") 
    return sh

# --- FUNÇÕES DE CARREGAMENTO ---
def carregar_dados():
    sh = get_connection()
    
    # Carregar Oradores
    ws_oradores = sh.worksheet("ORADORES A1")
    dados_oradores = ws_oradores.get_all_records()
    df_oradores = pd.DataFrame(dados_oradores)
    
    # Carregar Temas
    ws_temas = sh.worksheet("TEMAS")
    dados_temas = ws_temas.get_all_records()
    df_temas = pd.DataFrame(dados_temas)
    
    # Carregar Programação (Histórico)
    try:
        ws_prog = sh.worksheet("PROGRAMACAO")
        dados_prog = ws_prog.get_all_records()
        df_prog = pd.DataFrame(dados_prog)
    except:
        # Se não existir, cria um DF vazio
        df_prog = pd.DataFrame(columns=["Data", "Orador", "Tema", "Congregação"])
        
    return df_oradores, df_temas, df_prog, sh

# --- FUNÇÃO AUXILIAR: BUSCAR ÚLTIMA DATA ---
def verificar_ultima_data(df_prog, orador, tema):
    if df_prog.empty:
        return None
    
    # Filtra onde o orador e o tema coincidem
    filtro = df_prog[(df_prog['Orador'] == orador) & (df_prog['Tema'].astype(str).str.contains(str(tema).split('.')[0]))]
    
    if not filtro.empty:
        # Pega a data mais recente
        datas = pd.to_datetime(filtro['Data'], format='%d/%m/%Y', errors='coerce')
        ultima_data = datas.max()
        return ultima_data.strftime('%d/%m/%Y')
    return None

# --- INTERFACE ---
st.title("Sistema de Gestão de Discursos Públicos")

# Carrega tudo no início
try:
    df_oradores, df_temas, df_prog, sh = carregar_dados()
    st.toast("Conexão com a planilha estabelecida!", icon="✅")
except Exception as e:
    st.error(f"Erro ao conectar com a planilha: {e}")
    st.stop()

# --- MENU LATERAL ---
menu = st.sidebar.selectbox("Menu", ["Visualizar Escala", "Coordenador (Área Restrita)"])

# ---------------------------------------------------------
# ABA: VISUALIZAR ESCALA
# ---------------------------------------------------------
if menu == "Visualizar Escala":
    st.header("📅 Próximos Discursos")
    
    if not df_prog.empty:
        # Converte coluna de data para ordenar
        df_prog['Data_Sort'] = pd.to_datetime(df_prog['Data'], format='%d/%m/%Y', errors='coerce')
        df_view = df_prog.sort_values(by='Data_Sort', ascending=False).drop(columns=['Data_Sort'])
        
        st.dataframe(df_view, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma programação registrada ainda.")

# ---------------------------------------------------------
# ABA: COORDENADOR
# ---------------------------------------------------------
elif menu == "Coordenador (Área Restrita)":
    senha = st.sidebar.text_input("Senha de Acesso", type="password")
    
    if senha == "1234":  # Senha simples para exemplo
        st.success("Acesso Liberado")
        
        tab1, tab2, tab3 = st.tabs(["➕ Registrar Discurso", "👥 Gerenciar Oradores", "📜 Histórico Completo"])
        
        # --- TAB 1: REGISTRAR NOVO DISCURSO ---
        with tab1:
            st.subheader("Nova Designação")
            
            with st.form("form_designacao"):
                col1, col2 = st.columns(2)
                
                with col1:
                    data_designacao = st.date_input("Data do Discurso", date.today())
                    # Lista de Oradores
                    lista_oradores = df_oradores['Nome'].tolist() if not df_oradores.empty else []
                    orador_selecionado = st.selectbox("Selecione o Orador", lista_oradores)
                
                with col2:
                    # Lista de Temas (Concatenando Numero e Titulo para facilitar)
                    lista_temas = [f"{row['Numero']} - {row['Tema']}" for index, row in df_temas.iterrows()] if not df_temas.empty else []
                    tema_selecionado = st.selectbox("Selecione o Tema", lista_temas)
                
                # --- CHECK DE ÚLTIMA DATA (VISUALIZAÇÃO ANTES DE ENVIAR) ---
                # Nota: Dentro de st.form, a interatividade é limitada, mas podemos mostrar avisos pós-clique ou usar session_state.
                # Para simplificar, faremos a verificação ao clicar no botão.
                
                submit_prog = st.form_submit_button("💾 Salvar na Programação")
            
            if submit_prog:
                if orador_selecionado and tema_selecionado:
                    # 1. Verifica Histórico
                    numero_tema = tema_selecionado.split(' - ')[0]
                    ultima_vez = verificar_ultima_data(df_prog, orador_selecionado, numero_tema)
                    
                    # 2. Salva
                    ws_prog = sh.worksheet("PROGRAMACAO")
                    data_formatada = data_designacao.strftime("%d/%m/%Y")
                    
                    # Busca congregação do orador selecionado
                    congregacao_orador = df_oradores.loc[df_oradores['Nome'] == orador_selecionado, 'Congregacao'].values[0]
                    
                    ws_prog.append_row([data_formatada, orador_selecionado, tema_selecionado, congregacao_orador])
                    
                    st.success(f"Designação salva com sucesso para {data_formatada}!")
                    
                    # 3. Exibe mensagem da última vez
                    if ultima_vez:
                        st.warning(f"⚠️ Atenção: Este orador já fez este tema em: **{ultima_vez}**")
                    else:
                        st.info("ℹ️ Este orador nunca fez este tema nesta base de dados.")
                        
                    # Recarregar cache (opcional, força atualização visual)
                    # st.rerun() 
                else:
                    st.error("Preencha todos os campos.")

        # --- TAB 2: GERENCIAR ORADORES (ADICIONAR / EDITAR / EXCLUIR) ---
        with tab2:
            st.subheader("Cadastro de Oradores")
            
            action = st.radio("Ação:", ["Adicionar Novo", "Editar/Excluir Existente"], horizontal=True)
            
            if action == "Adicionar Novo":
                with st.form("add_orador"):
                    novo_nome = st.text_input("Nome do Orador")
                    nova_cong = st.text_input("Congregação")
                    novo_contato = st.text_input("Contato/WhatsApp")
                    submit_add = st.form_submit_button("Adicionar Orador")
                    
                    if submit_add:
                        if novo_nome and nova_cong:
                            ws_oradores = sh.worksheet("ORADORES A1")
                            # CORREÇÃO DO BUG: Usando append_row simples
                            ws_oradores.append_row([novo_nome, nova_cong, novo_contato])
                            st.success(f"Orador {novo_nome} adicionado!")
                            st.rerun()
                        else:
                            st.error("Nome e Congregação são obrigatórios.")
                            
            elif action == "Editar/Excluir Existente":
                if df_oradores.empty:
                    st.warning("Sem oradores para editar.")
                else:
                    orador_edit_sel = st.selectbox("Selecione para editar/excluir", df_oradores['Nome'].unique())
                    
                    # Pegar dados atuais
                    dados_atuais = df_oradores[df_oradores['Nome'] == orador_edit_sel].iloc[0]
                    
                    with st.form("edit_orador"):
                        edit_nome = st.text_input("Nome", value=dados_atuais['Nome'])
                        edit_cong = st.text_input("Congregação", value=dados_atuais['Congregacao'])
                        edit_contato = st.text_input("Contato", value=str(dados_atuais['Contato']))
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            btn_atualizar = st.form_submit_button("🔄 Atualizar Dados")
                        with col_b:
                            btn_excluir = st.form_submit_button("🗑️ Excluir Orador", type="primary")
                        
                        if btn_atualizar:
                            ws_oradores = sh.worksheet("ORADORES A1")
                            # Encontrar a linha (gspread é base 1, header é linha 1, então +2 no index do pandas)
                            # Mas é mais seguro buscar pela célula para evitar desalinhamento se a planilha mudar
                            cell = ws_oradores.find(orador_edit_sel)
                            if cell:
                                # Atualiza as colunas (assumindo ordem: Nome, Congregacao, Contato)
                                ws_oradores.update_cell(cell.row, 1, edit_nome)
                                ws_oradores.update_cell(cell.row, 2, edit_cong)
                                ws_oradores.update_cell(cell.row, 3, edit_contato)
                                st.success("Dados atualizados!")
                                st.rerun()
                            else:
                                st.error("Erro ao encontrar linha na planilha.")

                        if btn_excluir:
                            ws_oradores = sh.worksheet("ORADORES A1")
                            cell = ws_oradores.find(orador_edit_sel)
                            if cell:
                                ws_oradores.delete_rows(cell.row)
                                st.success(f"{orador_edit_sel} excluído com sucesso.")
                                st.rerun()
                            else:
                                st.error("Erro ao encontrar linha para excluir.")

        # --- TAB 3: HISTÓRICO ---
        with tab3:
            st.dataframe(df_prog, use_container_width=True)

    else:
        st.error("Senha incorreta.")
