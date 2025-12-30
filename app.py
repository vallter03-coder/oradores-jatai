import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import time
import urllib.parse

# ==============================================================================
# 1. CONFIGURAÇÕES VISUAIS
# ==============================================================================
st.set_page_config(page_title="Gestão de Discursos", page_icon="jx", layout="wide")

NOME_PLANILHA = "oradores_db"
ENDERECO_SALAO = "Rua João Vieira Nunes, Votorantim - SP"
LINK_MAPS = "https://www.google.com/maps/search/?api=1&query=Rua+Joao+Vieira+Nunes+Votorantim"

st.markdown("""
<style>
    .stApp {background-color: #F4F6F9; color: #333;}
    
    /* CARD DO ORADOR */
    .orador-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #E0E0E0;
        margin-bottom: 20px;
    }
    .orador-nome { font-size: 18px; font-weight: bold; color: #004E8C; margin-bottom: 5px; }
    .orador-info { font-size: 14px; color: #666; margin-bottom: 15px; }
    
    /* Botões */
    .stButton button {
        width: 100%;
        border-radius: 5px;
        font-weight: 600;
        background-color: #004E8C;
        color: white;
        border: none;
    }
    .stButton button:hover { background-color: #003366; color: white; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #ddd; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONEXÃO
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

def carregar_dados():
    client = conectar()
    sh = client.open(NOME_PLANILHA)

    # Carrega abas essenciais
    try: ws_oradores = sh.worksheet("oradores")
    except: ws_oradores = sh.add_worksheet("oradores", 100, 5)
    
    try: ws_agenda = sh.worksheet("agenda")
    except: ws_agenda = sh.add_worksheet("agenda", 100, 5)

    try: ws_temas = sh.worksheet("temas")
    except: st.error("Aba 'temas' faltando."); st.stop()

    df_oradores = pd.DataFrame(ws_oradores.get_all_records())
    df_temas = pd.DataFrame(ws_temas.get_all_records())

    # Padroniza colunas para minúsculo
    df_oradores.columns = [c.lower().strip() for c in df_oradores.columns]
    df_temas.columns = [c.lower().strip() for c in df_temas.columns]

    return ws_agenda, df_oradores, df_temas

# ==============================================================================
# 3. APP
# ==============================================================================
def main():
    try:
        ws_agenda, df_oradores, df_temas = carregar_dados()
    except Exception as e:
        st.error(f"Erro ao carregar: {e}"); st.stop()

    # --- SIDEBAR (LOCAL FIXO + FILTROS) ---
    with st.sidebar:
        st.header("📍 Nosso Salão")
        st.write(f"**{ENDERECO_SALAO}**")
        st.markdown(f"""
            <a href="{LINK_MAPS}" target="_blank">
                <button style="background-color: #34A853; color: white; width: 100%; padding: 8px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; margin-bottom: 20px;">
                    🗺️ Ver no Google Street View
                </button>
            </a>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.header("🔎 Buscar Oradores")
        
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        st.selectbox("Mês Pretendido", meses) # Apenas visual por enquanto
        
        # Filtros de Localidade do Orador
        cidades_disp = df_oradores['cidade'].unique() if 'cidade' in df_oradores.columns else []
        filtro_cidade = st.selectbox("Cidade", ["Todas"] + list(cidades_disp)) if len(cidades_disp) > 0 else st.text_input("Cidade")
        
        filtro_cong = st.text_input("Congregação")
        
        st.info("Digite a congregação acima para ver os oradores disponíveis.")

    # --- ÁREA PRINCIPAL ---
    st.title("Quadro de Discursos")

    # Lógica de Filtro
    df_filtrado = df_oradores.copy()
    
    # Se tiver as colunas, filtra. Se não, avisa.
    if 'cidade' in df_filtrado.columns and filtro_cidade != "Todas" and filtro_cidade:
        df_filtrado = df_filtrado[df_filtrado['cidade'].astype(str).str.contains(filtro_cidade, case=False)]
        
    if 'congregacao' in df_filtrado.columns and filtro_cong:
        df_filtrado = df_filtrado[df_filtrado['congregacao'].astype(str).str.contains(filtro_cong, case=False)]
    
    # Só mostra os cards se filtrar ou se pedir
    if df_filtrado.empty:
        st.warning("Nenhum orador encontrado com esses filtros.")
    else:
        # Verifica se o usuário filtrou algo para não mostrar lista gigante (opcional)
        # Mostrando GRID
        cols = st.columns(3)
        
        for index, row in df_filtrado.iterrows():
            with cols[index % 3]:
                # CARD
                nome = row.get('nome', 'Sem Nome')
                cargo = row.get('cargo', 'Orador')
                cong = row.get('congregacao', '')
                
                container = st.container()
                container.markdown(f"""
                <div class="orador-card">
                    <div class="orador-nome">{nome}</div>
                    <div class="orador-info">{cargo} {f'• {cong}' if cong else ''}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # ÁREA DE AGENDAMENTO (DENTRO DO CARD)
                with container.expander(f"📅 Agendar", expanded=True):
                    with st.form(key=f"form_{index}"):
                        data_sel = st.date_input("Data", date.today())
                        
                        # Lista de Temas do Orador
                        temas_ids = str(row.get('temas_ids', '')).replace(" ", "").split(",")
                        lista_temas = []
                        
                        # Tenta casar IDs com Titulos
                        if 'numero' in df_temas.columns and 'titulo' in df_temas.columns:
                            for t_id in temas_ids:
                                match = df_temas[df_temas['numero'].astype(str) == t_id]
                                if not match.empty:
                                    lista_temas.append(f"{t_id} - {match.iloc[0]['titulo']}")
                            
                            # Se não achou específicos, carrega todos
                            if not lista_temas:
                                lista_temas = [f"{r['numero']} - {r['titulo']}" for i, r in df_temas.iterrows()]
                        else:
                             lista_temas = ["Erro: Colunas numero/titulo não achadas na aba temas"]

                        tema_sel = st.selectbox("Tema", lista_temas)
                        
                        if st.form_submit_button("Confirmar Agendamento"):
                            # Salva na agenda
                            t_num = tema_sel.split(' - ')[0]
                            t_tit = tema_sel.split(' - ')[1] if ' - ' in tema_sel else tema_sel
                            
                            # Colunas Agenda: ID, Data, Orador, Cargo, Tema_Num, Tema_Tit
                            ws_agenda.append_row([
                                "", # ID
                                data_sel.strftime("%d/%m/%Y"),
                                nome,
                                cargo,
                                t_num,
                                t_tit,
                                cong  # Opcional: Salva a cong do orador pra referencia
                            ])
                            st.toast("Registrado na Agenda!", icon="✅")
                            time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
