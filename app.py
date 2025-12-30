import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão de Discursos", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
def get_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Certifique-se que o arquivo credentials.json está na mesma pasta
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    # IMPORTANTE: Coloque o nome exato da sua planilha aqui
    sh = client.open("NOME_DA_SUA_PLANILHA") 
    return sh

# --- VERIFICAÇÃO E CORREÇÃO DE CABEÇALHOS ---
def garantir_cabecalhos(sh):
    # Verifica Oradores
    try:
        ws_oradores = sh.worksheet("ORADORES A1")
    except:
        ws_oradores = sh.add_worksheet(title="ORADORES A1", rows=100, cols=10)
    
    # Se A1 estiver vazia, cria o cabeçalho para evitar sobrescrever
    if not ws_oradores.acell('A1').value:
        ws_oradores.update('A1:C1', [['Nome', 'Congregacao', 'Contato']])

    # Verifica Programação
    try:
        ws_prog = sh.worksheet("PROGRAMACAO")
    except:
        ws_prog = sh.add_worksheet(title="PROGRAMACAO", rows=100, cols=10)
        
    if not ws_prog.acell('A1').value:
        ws_prog.update('A1:D1', [['Data', 'Orador', 'Tema', 'Congregacao']])

    return ws_oradores, ws_prog

# --- CARREGAR DADOS ---
def carregar_dados():
    sh = get_connection()
    ws_oradores, ws_prog = garantir_cabecalhos(sh) # Garante que A1 não será sobrescrito
    
    # Oradores
    dados_oradores = ws_oradores.get_all_records()
    df_oradores = pd.DataFrame(dados_oradores)
    
    # Temas
    ws_temas = sh.worksheet("TEMAS")
    dados_temas = ws_temas.get_all_records()
    df_temas = pd.DataFrame(dados_temas)
    
    # Programação
    dados_prog = ws_prog.get_all_records()
    df_prog = pd.DataFrame(dados_prog)
    
    return df_oradores, df_temas, df_prog, sh, ws_oradores, ws_prog

# --- VERIFICAR DATA ANTERIOR ---
def verificar_ultima_data(df_prog, orador, tema):
    if df_prog.empty:
        return None
    
    # Tenta extrair o número do tema (ex: "12 - Amor" -> "12")
    try:
        num_tema = str(tema).split(' - ')[0].strip()
        # Filtra histórico
        filtro = df_prog[
            (df_prog['Orador'] == orador) & 
            (df_prog['Tema'].astype(str).str.startswith(num_tema))
        ]
    except:
        return None
    
    if not filtro.empty:
        # Converte datas e pega a maior
        datas = pd.to_datetime(filtro['Data'], format='%d/%m/%Y', errors='coerce')
        ultima = datas.max()
        if pd.notnull(ultima):
            return ultima.strftime('%d/%m/%Y')
    return None

# --- APP PRINCIPAL ---
st.title("Sistema de Discursos")

try:
    df_oradores, df_temas, df_prog, sh, ws_oradores, ws_prog = carregar_dados()
except Exception as e:
    st.error(f"Erro ao conectar. Verifique se o nome da planilha está correto e se o credentials.json existe.\nErro: {e}")
    st.stop()

# --- MENU LATERAL ---
menu = st.sidebar.radio("Navegação", ["Visualizar Escala", "Área do Coordenador"])

# ---------------------------------------------------------
# VISUALIZAR
# ---------------------------------------------------------
if menu == "Visualizar Escala":
    st.subheader("📅 Próximos Discursos")
    if not df_prog.empty:
        # Ordenação
        df_prog['Data_Sort'] = pd.to_datetime(df_prog['Data'], format='%d/%m/%Y', errors='coerce')
        df_view = df_prog.sort_values(by='Data_Sort', ascending=False).drop(columns=['Data_Sort'])
        st.dataframe(df_view, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma programação cadastrada.")

# ---------------------------------------------------------
# COORDENADOR
# ---------------------------------------------------------
elif menu == "Área do Coordenador":
    senha = st.sidebar.text_input("Senha", type="password")
    
    if senha == "1234":
        st.success("Logado como Coordenador")
        
        # Usando abas claras
        tab_novo, tab_gerenciar = st.tabs(["📝 Nova Designação", "⚙️ Gerenciar Oradores"])
        
        # --- ABA 1: NOVA DESIGNAÇÃO ---
        with tab_novo:
            st.markdown("### Registrar Novo Discurso")
            
            if df_oradores.empty:
                st.warning("Cadastre oradores primeiro na outra aba!")
            else:
                with st.form("form_prog"):
                    col1, col2 = st.columns(2)
                    with col1:
                        data_sel = st.date_input("Data", date.today())
                        orador_sel = st.selectbox("Orador", df_oradores['Nome'].unique())
                    with col2:
                        lista_temas = [f"{row['Numero']} - {row['Tema']}" for i, row in df_temas.iterrows()]
                        tema_sel = st.selectbox("Tema", lista_temas)
                    
                    btn_salvar_prog = st.form_submit_button("Salvar Designação")
                
                # Lógica ao clicar (fora do form para permitir alerts)
                if btn_salvar_prog:
                    # 1. Verifica Última Data ANTES de salvar (Baseado no histórico carregado)
                    ultima_vez = verificar_ultima_data(df_prog, orador_sel, tema_sel)
                    
                    # 2. Salva no Sheets
                    data_fmt = data_sel.strftime("%d/%m/%Y")
                    # Pega congregação
                    cong = df_oradores.loc[df_oradores['Nome'] == orador_sel, 'Congregacao'].values[0]
                    
                    ws_prog.append_row([data_fmt, orador_sel, tema_sel, cong])
                    
                    st.toast(f"Salvo! {orador_sel} em {data_fmt}", icon="✅")
                    
                    # 3. Mostra Alerta se já fez (Usando Session State para persistir após reload ou warning imediato)
                    if ultima_vez:
                        st.error(f"⚠️ AVISO CRÍTICO: Este orador JÁ FEZ este tema em {ultima_vez}!")
                        time.sleep(4) # Pausa para você ler antes de recarregar
                    else:
                        st.success("Primeira vez registrando este tema nesta base.")
                        time.sleep(1)
                        
                    # 4. RECARREGA A PÁGINA PARA ATUALIZAR DADOS
                    st.rerun()

        # --- ABA 2: GERENCIAR ORADORES ---
        with tab_gerenciar:
            st.markdown("### Adicionar ou Editar Oradores")
            
            modo = st.radio("O que deseja fazer?", ["Adicionar Novo", "Editar/Excluir"], horizontal=True)
            
            # MODO ADICIONAR
            if modo == "Adicionar Novo":
                with st.form("add_orador"):
                    n_nome = st.text_input("Nome Completo")
                    n_cong = st.text_input("Congregação")
                    n_cont = st.text_input("Contato")
                    btn_add = st.form_submit_button("Adicionar")
                    
                    if btn_add:
                        if n_nome and n_cong:
                            # Adiciona garantindo que não sobrescreve header
                            ws_oradores.append_row([n_nome, n_cong, n_cont])
                            st.success(f"{n_nome} adicionado!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Nome e Congregação obrigatórios")

            # MODO EDITAR/EXCLUIR
            elif modo == "Editar/Excluir":
                if df_oradores.empty:
                    st.warning("Nenhum orador cadastrado.")
                else:
                    sel_edit = st.selectbox("Selecione o Orador para alterar:", df_oradores['Nome'].unique())
                    
                    # Busca dados atuais
                    dados = df_oradores[df_oradores['Nome'] == sel_edit].iloc[0]
                    
                    # Formulário de Edição
                    st.markdown("---")
                    col_e1, col_e2, col_e3 = st.columns(3)
                    new_nome = col_e1.text_input("Nome", value=dados['Nome'])
                    new_cong = col_e2.text_input("Congregação", value=dados['Congregacao'])
                    new_cont = col_e3.text_input("Contato", value=str(dados['Contato']))
                    
                    col_b1, col_b2 = st.columns(2)
                    if col_b1.button("💾 Atualizar Dados"):
                        cell = ws_oradores.find(sel_edit)
                        if cell:
                            ws_oradores.update_cell(cell.row, 1, new_nome)
                            ws_oradores.update_cell(cell.row, 2, new_cong)
                            ws_oradores.update_cell(cell.row, 3, new_cont)
                            st.success("Atualizado!")
                            time.sleep(1)
                            st.rerun()
                    
                    if col_b2.button("🗑️ EXCLUIR ORADOR", type="primary"):
                        cell = ws_oradores.find(sel_edit)
                        if cell:
                            ws_oradores.delete_rows(cell.row)
                            st.warning("Excluído!")
                            time.sleep(1)
                            st.rerun()

    else:
        st.error("Senha Incorreta")
