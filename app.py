import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import time

# ==============================================================================
# 1. CONFIGURAÇÕES INICIAIS
# ==============================================================================
st.set_page_config(
    page_title="Gestão de Discursos",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DADOS DO SISTEMA ---
# IMPORTANTE: Troque pelo nome EXATO da sua planilha no Google Drive
NOME_DA_SUA_PLANILHA_NO_GOOGLE = oradores_db

# Estilo visual
st.markdown("""
<style>
    .stButton button {width: 100%; border-radius: 5px; font-weight: 600;}
    [data-testid="stSidebar"] {background-color: #f8f9fa;}
    .reportview-container {margin-top: -2em;}
    h1, h2, h3 {color: #2c3e50;}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONEXÃO INTELIGENTE (RESOLVE O ERRO DE ARQUIVO)
# ==============================================================================
@st.cache_resource
def conectar_google_sheets():
    """
    Tenta conectar usando Secrets (Nuvem) ou arquivo JSON (Local).
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 1. Tenta ler dos SECRETS do Streamlit Cloud
    if "gcp_service_account" in st.secrets:
        try:
            # Converte o objeto de secrets para um dicionário Python padrão
            creds_dict = dict(st.secrets["gcp_service_account"])
            
            # Corrige a chave privada se vier com problemas de formatação (comum no copy-paste)
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
                
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client
        except Exception as e:
            st.error(f"Erro ao ler Secrets: {e}")
            st.stop()
            
    # 2. Se não achar Secrets, tenta ler o arquivo LOCAL (credentials.json)
    else:
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            client = gspread.authorize(creds)
            return client
        except FileNotFoundError:
            st.error("❌ ERRO CRÍTICO: Não encontrei 'credentials.json' e nem a configuração de Secrets.")
            st.info("👉 No Streamlit Cloud, vá em 'Settings > Secrets' e cole seus dados lá.")
            st.stop()

def carregar_dados():
    client = conectar_google_sheets()
    
    try:
        sh = client.open(NOME_DA_SUA_PLANILHA_NO_GOOGLE)
    except gspread.SpreadsheetNotFound:
        st.error(f"❌ Não encontrei a planilha com o nome: '{NOME_DA_SUA_PLANILHA_NO_GOOGLE}'")
        st.info("Verifique se o nome no código (linha 22) é EXATAMENTE igual ao nome no Google Drive.")
        st.stop()

    # Garante que as abas existam
    try: ws_oradores = sh.worksheet("ORADORES A1")
    except: ws_oradores = sh.add_worksheet("ORADORES A1", 100, 5); ws_oradores.append_row(["Nome", "Congregacao", "Contato"])

    try: ws_prog = sh.worksheet("PROGRAMACAO")
    except: ws_prog = sh.add_worksheet("PROGRAMACAO", 100, 5); ws_prog.append_row(["Data", "Orador", "Tema", "Congregacao"])

    try: ws_temas = sh.worksheet("TEMAS")
    except: 
        st.warning("Aba 'TEMAS' não encontrada. Crie-a no Google Sheets com colunas 'Numero' e 'Tema'.")
        st.stop()

    # DataFrames
    df_oradores = pd.DataFrame(ws_oradores.get_all_records())
    df_prog = pd.DataFrame(ws_prog.get_all_records())
    df_temas = pd.DataFrame(ws_temas.get_all_records())

    return sh, ws_oradores, ws_prog, df_oradores, df_prog, df_temas

# ==============================================================================
# 3. LÓGICA DE NEGÓCIO
# ==============================================================================
def verificar_ultima_vez(df_prog, orador, tema_completo):
    if df_prog.empty: return None
    try:
        num_tema = str(tema_completo).split(' - ')[0].strip()
        filtro = df_prog[
            (df_prog['Orador'] == orador) & 
            (df_prog['Tema'].astype(str).str.contains(f"^{num_tema}"))
        ]
        if not filtro.empty:
            datas = pd.to_datetime(filtro['Data'], format="%d/%m/%Y", errors='coerce')
            return datas.max().strftime("%d/%m/%Y")
    except:
        pass
    return None

# ==============================================================================
# 4. APLICAÇÃO (INTERFACE)
# ==============================================================================
def main():
    st.sidebar.title("Menu Principal")
    
    # Carregamento seguro
    try:
        sh, ws_oradores, ws_prog, df_oradores, df_prog, df_temas = carregar_dados()
    except Exception as e:
        st.error(f"Erro desconhecido: {e}")
        st.stop()

    menu = st.sidebar.radio("Navegação:", ["👁️ Visualizar Escala", "🔒 Área do Coordenador"])

    # --- VISUALIZAÇÃO ---
    if menu == "👁️ Visualizar Escala":
        st.title("📅 Quadro de Discursos")
        if df_prog.empty:
            st.info("Nenhum discurso agendado.")
        else:
            df_view = df_prog.copy()
            df_view['Data_Sort'] = pd.to_datetime(df_view['Data'], format='%d/%m/%Y', errors='coerce')
            df_view = df_view.sort_values(by='Data_Sort', ascending=False)
            st.dataframe(df_view[['Data', 'Orador', 'Tema', 'Congregacao']], use_container_width=True, hide_index=True)

    # --- COORDENADOR ---
    elif menu == "🔒 Área do Coordenador":
        st.title("Painel Administrativo")
        senha = st.sidebar.text_input("Senha", type="password")
        
        if senha == "1234":
            st.sidebar.success("Logado!")
            tab1, tab2 = st.tabs(["📝 Nova Designação", "👥 Gerenciar Oradores"])

            # TAB 1: DESIGNAR
            with tab1:
                st.subheader("Registrar na Programação")
                if df_oradores.empty:
                    st.warning("Cadastre oradores primeiro.")
                else:
                    c1, c2 = st.columns(2)
                    data_sel = c1.date_input("Data", date.today())
                    orador_sel = c1.selectbox("Orador", df_oradores['Nome'].unique())
                    
                    lista_temas = [f"{r['Numero']} - {r['Tema']}" for i, r in df_temas.iterrows()]
                    tema_sel = c2.selectbox("Tema", lista_temas)

                    if st.button("💾 Salvar Designação", type="primary"):
                        ultimo = verificar_ultima_vez(df_prog, orador_sel, tema_sel)
                        cong = df_oradores.loc[df_oradores['Nome'] == orador_sel, 'Congregacao'].values[0]
                        
                        ws_prog.append_row([data_sel.strftime("%d/%m/%Y"), orador_sel, tema_sel, cong])
                        
                        st.toast("Salvo com sucesso!", icon="✅")
                        if ultimo:
                            st.error(f"⚠️ ATENÇÃO: {orador_sel} já fez este tema em **{ultimo}**!")
                            time.sleep(5)
                        else:
                            st.success("Primeira vez deste tema nesta base.")
                            time.sleep(2)
                        st.rerun()

            # TAB 2: GERENCIAR ORADORES
            with tab2:
                st.subheader("Cadastro de Oradores")
                opcao = st.radio("Ação:", ["Novo Orador", "Editar/Excluir"], horizontal=True)
                st.markdown("---")

                if opcao == "Novo Orador":
                    with st.form("novo_orador"):
                        c1, c2, c3 = st.columns(3)
                        n_nome = c1.text_input("Nome")
                        n_cong = c2.text_input("Congregação")
                        n_cont = c3.text_input("Contato")
                        if st.form_submit_button("Adicionar"):
                            if n_nome and n_cong:
                                ws_oradores.append_row([n_nome, n_cong, n_cont])
                                st.success("Adicionado!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.warning("Preencha Nome e Congregação")

                elif opcao == "Editar/Excluir":
                    if not df_oradores.empty:
                        sel_edit = st.selectbox("Selecione:", df_oradores['Nome'].unique())
                        dados = df_oradores[df_oradores['Nome'] == sel_edit].iloc[0]
                        
                        with st.form("edit_form"):
                            c1, c2, c3 = st.columns(3)
                            ed_nome = c1.text_input("Nome", value=dados['Nome'])
                            ed_cong = c2.text_input("Congregação", value=dados['Congregacao'])
                            ed_cont = c3.text_input("Contato", value=str(dados['Contato']))
                            
                            cb1, cb2 = st.columns(2)
                            b_save = cb1.form_submit_button("Atualizar")
                            b_del = cb2.form_submit_button("🗑️ Excluir", type="primary")

                            if b_save:
                                cell = ws_oradores.find(sel_edit)
                                ws_oradores.update_cell(cell.row, 1, ed_nome)
                                ws_oradores.update_cell(cell.row, 2, ed_cong)
                                ws_oradores.update_cell(cell.row, 3, ed_cont)
                                st.success("Atualizado!")
                                time.sleep(1); st.rerun()
                            
                            if b_del:
                                cell = ws_oradores.find(sel_edit)
                                ws_oradores.delete_rows(cell.row)
                                st.warning("Excluído!")
                                time.sleep(1); st.rerun()
                    else:
                        st.info("Lista vazia.")
        elif senha:
            st.error("Senha incorreta")

if __name__ == "__main__":
    main()


