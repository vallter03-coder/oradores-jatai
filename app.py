import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import time

# ==============================================================================
# 1. CONFIGURAÇÕES VISUAIS
# ==============================================================================
st.set_page_config(
    page_title="Gestão de Discursos - Pq Jataí",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Nome da planilha
NOME_DA_SUA_PLANILHA_NO_GOOGLE = "oradores_db"

# Congregação FIXA
MINHA_CONGREGACAO = "PARQUE JATAÍ"
MINHA_CIDADE = "Votorantim"

st.markdown("""
<style>
    .stApp {background-color: #FFFFFF; color: #31333F;}
    [data-testid="stSidebar"] {background-color: #F8F9FA; border-right: 1px solid #E0E0E0;}
    h1, h2, h3 {color: #004E8C; font-family: 'Segoe UI', sans-serif;}
    .stButton button {
        background-color: #004E8C; color: white; border-radius: 6px; 
        font-weight: 600; border: none; padding: 0.5rem 1rem;
    }
    .stButton button:hover {background-color: #003865;}
    /* Destaque para mensagem de erro ou sucesso */
    .stToast {font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONEXÃO E TRATAMENTO DE DADOS (CORREÇÃO DE COLUNAS)
# ==============================================================================
@st.cache_resource
def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Tenta conectar via Secrets (Nuvem) ou Arquivo (Local)
    if "gcp_service_account" in st.secrets:
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        except Exception as e:
            st.error(f"Erro Secrets: {e}"); st.stop()
    else:
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            return gspread.authorize(creds)
        except:
            st.error("Configure os Secrets ou arquivo credentials.json"); st.stop()

def normalizar_colunas(df):
    """Padroniza nomes de colunas para evitar KeyError (ex: titulo -> Tema, numero -> Numero)"""
    df.columns = [c.strip() for c in df.columns] # Remove espaços extras
    mapa = {
        'titulo': 'Tema', 'tema': 'Tema', 'TITULO': 'Tema', 'TEMA': 'Tema',
        'numero': 'Numero', 'num': 'Numero', 'NUMERO': 'Numero',
        'nome': 'Nome', 'NOME': 'Nome',
        'congregacao': 'Congregacao', 'CONGREGACAO': 'Congregacao',
        'cidade': 'Cidade', 'CIDADE': 'Cidade',
        'data': 'Data', 'DATA': 'Data',
        'orador': 'Orador', 'ORADOR': 'Orador'
    }
    return df.rename(columns=mapa)

def carregar_dados():
    client = conectar_google_sheets()
    try:
        sh = client.open(NOME_DA_SUA_PLANILHA_NO_GOOGLE)
    except:
        st.error(f"❌ Planilha '{NOME_DA_SUA_PLANILHA_NO_GOOGLE}' não encontrada no Google Drive."); st.stop()

    # --- CARREGA ABAS COM PROTEÇÃO CONTRA ERROS ---
    
    # 1. ORADORES (Tenta ler a aba nova "ORADORES A1", se não achar, tenta "oradores")
    try: 
        ws_oradores = sh.worksheet("ORADORES A1")
    except: 
        try: ws_oradores = sh.worksheet("oradores") # Tenta a aba antiga
        except: 
            ws_oradores = sh.add_worksheet("ORADORES A1", 100, 5)
            ws_oradores.append_row(["Nome", "Congregacao", "Cidade", "Contato"])
    
    # 2. PROGRAMAÇÃO
    try: ws_prog = sh.worksheet("PROGRAMACAO")
    except: ws_prog = sh.add_worksheet("PROGRAMACAO", 100, 5); ws_prog.append_row(["Data", "Orador", "Tema", "Congregacao", "Cidade"])

    # 3. TEMAS (Tenta "TEMAS" ou "temas")
    try: ws_temas = sh.worksheet("TEMAS")
    except: 
        try: ws_temas = sh.worksheet("temas")
        except: st.warning("Crie a aba TEMAS na planilha."); st.stop()

    # Cria DataFrames e Normaliza
    df_oradores = pd.DataFrame(ws_oradores.get_all_records())
    df_oradores = normalizar_colunas(df_oradores)
    
    df_prog = pd.DataFrame(ws_prog.get_all_records())
    df_prog = normalizar_colunas(df_prog)
    
    df_temas = pd.DataFrame(ws_temas.get_all_records())
    df_temas = normalizar_colunas(df_temas)

    # Garante que as colunas essenciais existam no DataFrame (mesmo que vazias) para não quebrar o código
    if 'Cidade' not in df_oradores.columns: df_oradores['Cidade'] = ""
    if 'Congregacao' not in df_oradores.columns: df_oradores['Congregacao'] = ""
    if 'Cidade' not in df_prog.columns: df_prog['Cidade'] = ""
    
    return sh, ws_oradores, ws_prog, df_oradores, df_prog, df_temas

# ==============================================================================
# 3. INTERFACE PRINCIPAL
# ==============================================================================
def main():
    try:
        sh, ws_oradores, ws_prog, df_oradores, df_prog, df_temas = carregar_dados()
    except Exception as e:
        st.error(f"Erro ao processar dados: {e}"); st.stop()

    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2921/2921222.png", width=50)
    st.sidebar.title("Menu")
    menu = st.sidebar.radio("Ir para:", ["📅 Quadro de Discursos (Público)", "🔒 Área do Coordenador"])

    # --------------------------------------------------------------------------
    # PÁGINA PÚBLICA
    # --------------------------------------------------------------------------
    if menu == "📅 Quadro de Discursos (Público)":
        st.title("📅 Quadro de Discursos")
        
        # Filtros
        with st.container():
            st.markdown("### 🔍 Pesquisar")
            c1, c2, c3 = st.columns(3)
            
            meses = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
                     7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}
            filtro_mes = c1.selectbox("Mês", ["Todos"] + list(meses.values()))
            
            # Pega lista de cidades disponíveis na programação
            cidades_disp = sorted(list(set(df_prog['Cidade'].dropna().unique())))
            filtro_cidade = c2.selectbox("Cidade", ["Todas"] + cidades_disp)
            
            filtro_cong = c3.text_input("Congregação")

        st.markdown("---")

        if df_prog.empty:
            st.info("Nenhuma programação cadastrada.")
        else:
            df_view = df_prog.copy()
            df_view['Data_Dt'] = pd.to_datetime(df_view['Data'], format='%d/%m/%Y', errors='coerce')
            
            # Aplica Filtros
            if filtro_mes != "Todos":
                num_mes = [k for k, v in meses.items() if v == filtro_mes][0]
                df_view = df_view[df_view['Data_Dt'].dt.month == num_mes]
            
            if filtro_cidade != "Todas":
                df_view = df_view[df_view['Cidade'].astype(str) == filtro_cidade]
            
            if filtro_cong:
                df_view = df_view[df_view['Congregacao'].astype(str).str.contains(filtro_cong, case=False)]

            # Exibição
            df_view = df_view.sort_values(by='Data_Dt', ascending=False)
            colunas_exibir = [c for c in ['Data', 'Orador', 'Tema', 'Congregacao', 'Cidade'] if c in df_view.columns]
            st.dataframe(df_view[colunas_exibir], use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # ÁREA DO COORDENADOR (PARQUE JATAÍ)
    # --------------------------------------------------------------------------
    elif menu == "🔒 Área do Coordenador":
        st.title(f"Painel Administrativo - {MINHA_CONGREGACAO}")
        
        senha = st.sidebar.text_input("Senha", type="password")
        if senha == "1234":
            st.sidebar.success(f"Logado: {MINHA_CONGREGACAO}")
            
            tab1, tab2, tab3 = st.tabs(["➕ Novo Discurso", "📅 Nossa Agenda", "👥 Meus Oradores"])

            # 1. NOVO DISCURSO
            with tab1:
                st.subheader(f"Agendar na {MINHA_CONGREGACAO}")
                
                with st.form("form_agenda"):
                    c1, c2 = st.columns(2)
                    data_sel = c1.date_input("Data", date.today())
                    
                    # Lista de oradores (remove duplicados e vazios)
                    lista_oradores = sorted([x for x in df_oradores['Nome'].unique() if str(x) != 'nan' and str(x) != ''])
                    orador_sel = c1.selectbox("Orador", lista_oradores)
                    
                    # Lista de Temas (Tenta montar Numero - Tema)
                    if 'Numero' in df_temas.columns and 'Tema' in df_temas.columns:
                        lista_temas = [f"{r['Numero']} - {r['Tema']}" for i, r in df_temas.iterrows()]
                    else:
                        # Fallback se as colunas não existirem
                        lista_temas = df_temas.iloc[:, 0].astype(str).tolist()
                        
                    tema_sel = c2.selectbox("Tema", lista_temas)
                    
                    if st.form_submit_button("💾 Salvar"):
                        # Verifica histórico
                        ja_fez_msg = None
                        if not df_prog.empty and 'Tema' in df_prog.columns:
                            try:
                                num_tema = tema_sel.split(' - ')[0]
                                check = df_prog[
                                    (df_prog['Orador'] == orador_sel) & 
                                    (df_prog['Tema'].astype(str).str.startswith(num_tema))
                                ]
                                if not check.empty:
                                    ja_fez_msg = f"Este orador já fez este tema em {check['Data'].values[0]}"
                            except: pass

                        # Prepara linha para salvar
                        nova_linha = [
                            data_sel.strftime("%d/%m/%Y"), 
                            orador_sel, 
                            tema_sel, 
                            MINHA_CONGREGACAO, 
                            MINHA_CIDADE
                        ]
                        
                        ws_prog.append_row(nova_linha)
                        st.success("Agendado!")
                        if ja_fez_msg: st.warning(f"⚠️ {ja_fez_msg}")
                        time.sleep(1); st.rerun()

            # 2. AGENDA LOCAL
            with tab2:
                st.subheader("Discursos no Parque Jataí")
                if not df_prog.empty and 'Congregacao' in df_prog.columns:
                    # Filtra apenas Parque Jataí
                    df_local = df_prog[df_prog['Congregacao'].astype(str).str.upper() == MINHA_CONGREGACAO]
                    st.dataframe(df_local, use_container_width=True)
                else:
                    st.info("Nenhuma programação encontrada.")

            # 3. MEUS ORADORES
            with tab3:
                st.subheader("Oradores Cadastrados")
                # Filtra oradores do Parque Jataí se houver coluna congregação, senão mostra todos
                if 'Congregacao' in df_oradores.columns:
                    df_local_oradores = df_oradores[df_oradores['Congregacao'].astype(str).str.upper() == MINHA_CONGREGACAO]
                else:
                    df_local_oradores = df_oradores
                
                if df_local_oradores.empty:
                    st.warning(f"Nenhum orador encontrado para {MINHA_CONGREGACAO}.")
                    st.info("Verifique se na planilha de oradores a coluna 'Congregacao' está preenchida como 'PARQUE JATAÍ'.")
                else:
                    st.dataframe(df_local_oradores, use_container_width=True)
                
                st.markdown("---")
                with st.expander("Cadastrar Novo Orador Local"):
                    with st.form("add_orador"):
                        nn = st.text_input("Nome")
                        nc = st.text_input("Contato")
                        if st.form_submit_button("Salvar Orador"):
                            ws_oradores.append_row([nn, MINHA_CONGREGACAO, MINHA_CIDADE, nc])
                            st.success("Salvo!"); time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
