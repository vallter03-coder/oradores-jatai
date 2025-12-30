import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import time

# ==============================================================================
# 1. CONFIGURAÇÕES
# ==============================================================================
st.set_page_config(page_title="Gestão de Discursos", page_icon="🎤", layout="wide")

# NOME DA PLANILHA (Exatamente como você falou)
NOME_PLANILHA = "oradores_db"
MINHA_CONGREGACAO = "PARQUE JATAÍ"
MINHA_CIDADE = "Votorantim"

st.markdown("""
<style>
    .stApp {background-color: #FFFFFF; color: #31333F;}
    h1, h2, h3 {color: #004E8C;}
    .stButton button {background-color: #004E8C; color: white; border-radius: 6px; border: none; padding: 0.5rem 1rem;}
    .stButton button:hover {background-color: #003865;}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONEXÃO E DADOS
# ==============================================================================
@st.cache_resource
def conectar():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)

def normalizar_df(df):
    """Padroniza os nomes das colunas para facilitar o código"""
    # Remove espaços e coloca tudo em minúsculo para comparar
    mapa = {}
    for col in df.columns:
        c_clean = col.strip().lower()
        if c_clean in ['titulo', 'tema', 'tema_titulo']: mapa[col] = 'Tema'
        elif c_clean in ['numero', 'num', 'id', 'tema_numero']: mapa[col] = 'Numero'
        elif c_clean in ['nome', 'orador', 'nome_irmao']: mapa[col] = 'Nome' # Para oradores
        elif c_clean in ['data', 'data_designacao']: mapa[col] = 'Data'
        elif c_clean in ['congregacao', 'cong']: mapa[col] = 'Congregacao'
        elif c_clean in ['cidade']: mapa[col] = 'Cidade'
        elif c_clean in ['contato', 'telefone']: mapa[col] = 'Contato'
    
    # Renomeia e retorna
    return df.rename(columns=mapa)

def carregar():
    client = conectar()
    try:
        sh = client.open(NOME_PLANILHA)
    except:
        st.error(f"❌ Não encontrei a planilha '{NOME_PLANILHA}'. Verifique o nome no Google Drive."); st.stop()

    # --- CARREGA AS ABAS QUE VOCÊ PEDIU ---
    # 1. ORADORES
    try: ws_oradores = sh.worksheet("oradores")
    except: ws_oradores = sh.add_worksheet("oradores", 100, 5) # Cria se não existir
    
    # 2. AGENDA (Programação)
    try: ws_agenda = sh.worksheet("agenda")
    except: ws_agenda = sh.add_worksheet("agenda", 100, 5)

    # 3. TEMAS
    try: ws_temas = sh.worksheet("temas")
    except: st.error("Aba 'temas' não existe."); st.stop()

    # DataFrames
    df_oradores = pd.DataFrame(ws_oradores.get_all_records())
    df_agenda = pd.DataFrame(ws_agenda.get_all_records())
    df_temas = pd.DataFrame(ws_temas.get_all_records())

    # Normaliza colunas (para o código entender 'titulo' como 'Tema')
    df_oradores = normalizar_df(df_oradores)
    df_agenda = normalizar_df(df_agenda)
    df_temas = normalizar_df(df_temas)
    
    # Garante coluna Nome na agenda p/ não dar erro de visualização
    if 'Nome' in df_agenda.columns: df_agenda.rename(columns={'Nome': 'Orador'}, inplace=True)
    if 'Orador' not in df_agenda.columns: df_agenda['Orador'] = ""

    return ws_oradores, ws_agenda, df_oradores, df_agenda, df_temas

# ==============================================================================
# 3. INTERFACE
# ==============================================================================
def main():
    try:
        ws_oradores, ws_agenda, df_oradores, df_agenda, df_temas = carregar()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}"); st.stop()

    st.sidebar.title("Menu")
    menu = st.sidebar.radio("Ir para:", ["📅 Quadro de Discursos", "🔒 Área do Coordenador"])

    # --- PÚBLICO ---
    if menu == "📅 Quadro de Discursos":
        st.title("📅 Quadro de Discursos")
        
        # Filtros
        c1, c2, c3 = st.columns(3)
        meses = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}
        
        filtro_mes = c1.selectbox("Mês", ["Todos"] + list(meses.values()))
        
        # Cidades (Se existir a coluna Cidade na agenda)
        cidades = df_agenda['Cidade'].unique() if 'Cidade' in df_agenda.columns else []
        filtro_cidade = c2.selectbox("Cidade", ["Todas"] + list(cidades))
        
        filtro_cong = c3.text_input("Congregação")
        st.markdown("---")

        if df_agenda.empty:
            st.info("Nenhuma programação na aba 'agenda'.")
        else:
            df_view = df_agenda.copy()
            # Tenta converter data
            df_view['Data_Dt'] = pd.to_datetime(df_view['Data'], format='%d/%m/%Y', errors='coerce')
            
            # Filtra
            if filtro_mes != "Todos":
                num_mes = [k for k, v in meses.items() if v == filtro_mes][0]
                df_view = df_view[df_view['Data_Dt'].dt.month == num_mes]
            if filtro_cidade != "Todas":
                df_view = df_view[df_view['Cidade'] == filtro_cidade]
            if filtro_cong:
                # Verifica se existe coluna Congregacao na agenda antes de filtrar
                if 'Congregacao' in df_view.columns:
                    df_view = df_view[df_view['Congregacao'].astype(str).str.contains(filtro_cong, case=False)]

            # Exibe (Colunas dinâmicas para não quebrar)
            cols = [c for c in ['Data', 'Orador', 'Tema', 'Congregacao', 'Cidade'] if c in df_view.columns]
            st.dataframe(df_view.sort_values('Data_Dt', ascending=False)[cols], use_container_width=True, hide_index=True)

    # --- COORDENADOR ---
    elif menu == "🔒 Área do Coordenador":
        st.title(f"Painel - {MINHA_CONGREGACAO}")
        if st.sidebar.text_input("Senha", type="password") == "1234":
            
            tab1, tab2 = st.tabs(["➕ Agendar", "👥 Meus Oradores"])
            
            # 1. Agendar
            with tab1:
                with st.form("agenda"):
                    c1, c2 = st.columns(2)
                    data_sel = c1.date_input("Data", date.today())
                    orador_sel = c1.selectbox("Orador", df_oradores['Nome'].unique())
                    
                    # Monta lista de temas (Numero - Titulo)
                    lista_temas = []
                    if 'Numero' in df_temas.columns and 'Tema' in df_temas.columns:
                        lista_temas = [f"{r['Numero']} - {r['Tema']}" for i, r in df_temas.iterrows()]
                    else:
                        lista_temas = df_temas.iloc[:, 0].astype(str).tolist() # Fallback
                        
                    tema_sel = c2.selectbox("Tema", lista_temas)
                    
                    if st.form_submit_button("Salvar na Agenda"):
                        # Verifica repetição
                        msg_aviso = ""
                        if not df_agenda.empty and 'Tema' in df_agenda.columns:
                            # Pega numero do tema
                            t_num = tema_sel.split(' - ')[0]
                            check = df_agenda[
                                (df_agenda['Orador'] == orador_sel) & 
                                (df_agenda['Tema'].astype(str).str.startswith(t_num))
                            ]
                            if not check.empty:
                                msg_aviso = f"⚠️ Orador já fez esse tema em: {check['Data'].values[0]}"

                        # Salva na aba 'agenda'
                        # Colunas: Data, Orador, Tema, Congregação, Cidade
                        # (O gspread adiciona na ordem, se sua planilha tiver colunas diferentes, ele põe nas próximas livres)
                        ws_agenda.append_row([
                            data_sel.strftime("%d/%m/%Y"),
                            orador_sel,
                            tema_sel,
                            MINHA_CONGREGACAO,
                            MINHA_CIDADE
                        ])
                        
                        st.success("Agendado!")
                        if msg_aviso: st.warning(msg_aviso)
                        time.sleep(1); st.rerun()

            # 2. Oradores
            with tab2:
                # Tenta filtrar pela congregação SE existir a coluna
                if 'Congregacao' in df_oradores.columns:
                    df_local = df_oradores[df_oradores['Congregacao'].astype(str).str.upper() == MINHA_CONGREGACAO]
                else:
                    df_local = df_oradores # Se não tiver coluna, mostra todos
                    st.info("Sua aba 'oradores' não tem coluna 'Congregacao'. Mostrando todos.")

                st.dataframe(df_local, use_container_width=True)
                
                with st.expander("Cadastrar Novo Orador"):
                    with st.form("add_orador"):
                        nn = st.text_input("Nome")
                        nc = st.text_input("Contato")
                        if st.form_submit_button("Salvar"):
                            # Salva: Nome, Cargo(vazio), Temas(vazio), Congregacao, Cidade, Contato
                            # Ajuste conforme suas colunas. Vou mandar o básico que funciona.
                            ws_oradores.append_row([nn, "Publicador", "", MINHA_CONGREGACAO, MINHA_CIDADE, nc])
                            st.success("Salvo!"); time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
