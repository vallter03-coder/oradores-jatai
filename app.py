import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import time

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Sistema de Gestão de Discursos",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS para deixar a tabela e botões mais bonitos
st.markdown("""
<style>
    .stButton button {
        width: 100%;
        border-radius: 5px;
        font-weight: bold;
    }
    [data-testid="stSidebar"] {
        background-color: #f0f2f6;
    }
    h1, h2, h3 {
        color: #2c3e50;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONEXÃO COM O GOOGLE SHEETS (ROBUSTA)
# ==============================================================================
@st.cache_resource
def conectar_google_sheets():
    """
    Cria a conexão. Tenta ler dos Secrets (Nuvem) primeiro. 
    Se não achar, tenta ler do arquivo (Local).
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Tenta conectar usando os Segredos do Streamlit Cloud
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    
    # Se falhar, tenta procurar o arquivo (caso você esteja rodando no seu PC)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
    client = gspread.authorize(creds)
    return client

def carregar_planilha():
    """
    Carrega as abas e garante que os cabeçalhos existam.
    """
    client = conectar_google_sheets()
    # --------------------------------------------------------------------------
    # ATENÇÃO: COLOQUE O NOME DA SUA PLANILHA AQUI EMBAIXO
    # --------------------------------------------------------------------------
    NOME_PLANILHA = "oradores_db"  # <--- EDITE AQUI SE PRECISAR
    
    try:
        sh = client.open(NOME_PLANILHA)
    except gspread.SpreadsheetNotFound:
        st.error(f"❌ Não encontrei a planilha com o nome: '{NOME_PLANILHA}'. Verifique no Google Drive.")
        st.stop()
        
    return sh

# ==============================================================================
# 3. FUNÇÕES DE DADOS (CARGA E VALIDAÇÃO)
# ==============================================================================
def obter_dados():
    sh = carregar_planilha()
    
    # --- ABA ORADORES ---
    try:
        ws_oradores = sh.worksheet("ORADORES A1")
    except:
        ws_oradores = sh.add_worksheet("ORADORES A1", 100, 5)
        ws_oradores.append_row(["Nome", "Congregacao", "Contato"]) # Cria cabeçalho se for nova
    
    # --- ABA PROGRAMACAO ---
    try:
        ws_prog = sh.worksheet("PROGRAMACAO")
    except:
        ws_prog = sh.add_worksheet("PROGRAMACAO", 100, 5)
        ws_prog.append_row(["Data", "Orador", "Tema", "Congregacao"]) # Cria cabeçalho se for nova

    # --- ABA TEMAS ---
    try:
        ws_temas = sh.worksheet("TEMAS")
    except:
        st.error("Aba 'TEMAS' não encontrada. Crie uma aba TEMAS com as colunas Numero e Tema.")
        st.stop()

    # Carrega DataFrames
    df_oradores = pd.DataFrame(ws_oradores.get_all_records())
    df_prog = pd.DataFrame(ws_prog.get_all_records())
    df_temas = pd.DataFrame(ws_temas.get_all_records())
    
    return sh, ws_oradores, ws_prog, df_oradores, df_prog, df_temas

def verificar_discurso_anterior(df_prog, nome_orador, nome_tema):
    """
    Verifica se o orador já fez este tema antes e retorna a data.
    """
    if df_prog.empty:
        return None
        
    # Extrai apenas o número do tema (ex: "12" de "12 - Amor") para busca ampla
    try:
        numero_tema = str(nome_tema).split(' - ')[0].strip()
        
        # Filtra onde o orador é o mesmo E o tema começa com o mesmo número
        filtro = df_prog[
            (df_prog['Orador'] == nome_orador) & 
            (df_prog['Tema'].astype(str).str.contains(f"^{numero_tema}"))
        ]
        
        if not filtro.empty:
            # Pega a data mais recente
            datas = pd.to_datetime(filtro['Data'], format="%d/%m/%Y", errors='coerce')
            ultima_data = datas.max()
            return ultima_data.strftime("%d/%m/%Y")
            
    except Exception as e:
        print(f"Erro ao verificar data: {e}")
        
    return None

# ==============================================================================
# 4. APLICAÇÃO PRINCIPAL (MAIN)
# ==============================================================================
def main():
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2921/2921222.png", width=50)
    st.sidebar.title("Menu Principal")
    
    # Tenta carregar dados. Se falhar, avisa o usuário.
    try:
        sh, ws_oradores, ws_prog, df_oradores, df_prog, df_temas = obter_dados()
    except Exception as e:
        st.error(f"Erro crítico ao carregar dados: {e}")
        st.stop()

    menu = st.sidebar.radio("Navegue por aqui:", ["📊 Visualizar Escala", "🔒 Área do Coordenador"])

    # --------------------------------------------------------------------------
    # MÓDULO 1: VISUALIZAÇÃO (PÚBLICO)
    # --------------------------------------------------------------------------
    if menu == "📊 Visualizar Escala":
        st.title("📅 Quadro de Discursos")
        st.markdown("---")
        
        if df_prog.empty:
            st.info("Ainda não há discursos agendados.")
        else:
            # Tratamento de dados para exibição
            df_view = df_prog.copy()
            # Converte para data real para poder ordenar
            df_view['Data_Sort'] = pd.to_datetime(df_view['Data'], format='%d/%m/%Y', errors='coerce')
            df_view = df_view.sort_values(by='Data_Sort', ascending=False) # Mais recentes primeiro
            
            # Remove a coluna auxiliar e exibe
            st.dataframe(
                df_view[['Data', 'Orador', 'Tema', 'Congregacao']], 
                use_container_width=True, 
                hide_index=True,
                height=500
            )

    # --------------------------------------------------------------------------
    # MÓDULO 2: COORDENADOR (RESTRITO)
    # --------------------------------------------------------------------------
    elif menu == "🔒 Área do Coordenador":
        st.title("⚙️ Painel de Controle")
        senha = st.sidebar.text_input("🔑 Senha de Acesso", type="password")
        
        if senha == "1234":
            st.sidebar.success("Acesso Autorizado")
            
            # Abas principais
            tab_designar, tab_gerenciar = st.tabs(["📝 Nova Designação", "👥 Gerenciar Oradores"])
            
            # --- ABA 1: DESIGNAR DISCURSO ---
            with tab_designar:
                st.subheader("Registrar Discurso na Programação")
                
                if df_oradores.empty:
                    st.warning("⚠️ Cadastre oradores na aba ao lado primeiro!")
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        data_input = st.date_input("Data do Discurso", date.today())
                        orador_input = st.selectbox("Selecione o Orador", df_oradores['Nome'].unique())
                    with col2:
                        # Monta lista de temas
                        lista_temas = [f"{row['Numero']} - {row['Tema']}" for i, row in df_temas.iterrows()]
                        tema_input = st.selectbox("Selecione o Tema", lista_temas)
                    
                    # Botão de Ação
                    if st.button("💾 Salvar Designação", type="primary"):
                        # 1. Verifica histórico
                        data_anterior = verificar_discurso_anterior(df_prog, orador_input, tema_input)
                        
                        # 2. Busca congregação do orador
                        congregacao = df_oradores.loc[df_oradores['Nome'] == orador_input, 'Congregacao'].values[0]
                        data_str = data_input.strftime("%d/%m/%Y")
                        
                        # 3. Salva no Google Sheets
                        ws_prog.append_row([data_str, orador_input, tema_input, congregacao])
                        
                        # 4. Feedback ao Usuário
                        st.success(f"✅ Designação salva para {data_str}!")
                        
                        if data_anterior:
                            st.error(f"⚠️ **ATENÇÃO:** O orador {orador_input} JÁ FEZ este tema em **{data_anterior}**.")
                            time.sleep(5) # Dá tempo de ler
                        else:
                            st.info("ℹ️ É a primeira vez que registramos este tema para este orador.")
                            time.sleep(2)
                            
                        st.rerun()

            # --- ABA 2: GERENCIAR ORADORES ---
            with tab_gerenciar:
                st.subheader("Banco de Dados de Oradores")
                
                # Escolha da ação
                acao = st.radio("Ação desejada:", ["➕ Adicionar Novo", "✏️ Editar ou Excluir"], horizontal=True)
                st.markdown("---")

                if acao == "➕ Adicionar Novo":
                    c1, c2, c3 = st.columns(3)
                    novo_nome = c1.text_input("Nome Completo")
                    nova_cong = c2.text_input("Congregação")
                    novo_cont = c3.text_input("Contato (Tel)")
                    
                    if st.button("Adicionar Orador"):
                        if novo_nome and nova_cong:
                            ws_oradores.append_row([novo_nome, nova_cong, novo_cont])
                            st.success(f"✅ {novo_nome} adicionado com sucesso!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Preencha pelo menos Nome e Congregação.")

                elif acao == "✏️ Editar ou Excluir":
                    if df_oradores.empty:
                        st.info("Nenhum orador para editar.")
                    else:
                        orador_selecionado = st.selectbox("Selecione o Orador para Modificar:", df_oradores['Nome'].unique())
                        
                        # Pega os dados atuais desse orador
                        dados_atuais = df_oradores[df_oradores['Nome'] == orador_selecionado].iloc[0]
                        
                        with st.form(key="edit_form"):
                            c1, c2, c3 = st.columns(3)
                            edit_nome = c1.text_input("Nome", value=dados_atuais['Nome'])
                            edit_cong = c2.text_input("Congregação", value=dados_atuais['Congregacao'])
                            edit_cont = c3.text_input("Contato", value=str(dados_atuais['Contato']))
                            
                            c_btn1, c_btn2 = st.columns([1, 1])
                            btn_save = c_btn1.form_submit_button("🔄 Salvar Alterações")
                            btn_del = c_btn2.form_submit_button("🗑️ Excluir Definitivamente", type="primary")
                        
                        # Lógica de Atualização
                        if btn_save:
                            cell = ws_oradores.find(orador_selecionado)
                            if cell:
                                ws_oradores.update_cell(cell.row, 1, edit_nome)
                                ws_oradores.update_cell(cell.row, 2, edit_cong)
                                ws_oradores.update_cell(cell.row, 3, edit_cont)
                                st.success("Dados atualizados!")
                                time.sleep(1)
                                st.rerun()
                                
                        # Lógica de Exclusão
                        if btn_del:
                            cell = ws_oradores.find(orador_selecionado)
                            if cell:
                                ws_oradores.delete_rows(cell.row)
                                st.warning(f"Orador {orador_selecionado} removido.")
                                time.sleep(1)
                                st.rerun()

        elif senha != "":
            st.error("Senha Incorreta")

if __name__ == "__main__":
    main()


