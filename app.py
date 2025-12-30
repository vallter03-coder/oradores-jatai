import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import time
import urllib.parse

# ==============================================================================
# 1. CONFIGURAÇÕES VISUAIS (ESTILO DE CARDS)
# ==============================================================================
st.set_page_config(page_title="Sistema de Discursos", page_icon="jx", layout="wide")

NOME_PLANILHA = "oradores_db"

st.markdown("""
<style>
    /* Fundo e Texto */
    .stApp {background-color: #F4F6F9; color: #333;}
    
    /* Estilo do CARD do Orador */
    .orador-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 1px solid #E0E0E0;
        margin-bottom: 15px;
    }
    .orador-nome {
        font-size: 18px;
        font-weight: bold;
        color: #2C3E50;
    }
    .orador-cargo {
        color: #7F8C8D;
        font-size: 14px;
        margin-bottom: 10px;
    }
    
    /* Botões */
    .stButton button {
        width: 100%;
        border-radius: 5px;
        font-weight: 600;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #ddd;
    }
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

    # Abas
    ws_oradores = sh.worksheet("oradores")
    ws_agenda = sh.worksheet("agenda")
    ws_temas = sh.worksheet("temas")
    ws_solic = sh.worksheet("solicitacoes")

    # DataFrames
    df_oradores = pd.DataFrame(ws_oradores.get_all_records())
    df_agenda = pd.DataFrame(ws_agenda.get_all_records())
    df_temas = pd.DataFrame(ws_temas.get_all_records())

    # Normalização básica de nomes de colunas (Minúsculo para garantir)
    df_oradores.columns = [c.lower() for c in df_oradores.columns]
    df_temas.columns = [c.lower() for c in df_temas.columns]
    
    # Garante colunas mínimas para não quebrar se estiver vazio
    required_oradores = ['nome', 'cargo', 'congregacao', 'cidade', 'temas_ids', 'contato']
    for col in required_oradores:
        if col not in df_oradores.columns:
            df_oradores[col] = "" # Cria vazia se não existir na planilha

    return ws_agenda, ws_solic, df_oradores, df_agenda, df_temas

# ==============================================================================
# 3. INTERFACE PRINCIPAL
# ==============================================================================
def main():
    try:
        ws_agenda, ws_solic, df_oradores, df_agenda, df_temas = carregar_dados()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()

    # --- BARRA LATERAL (FILTROS E LOCAL) ---
    st.sidebar.header("📍 Localização")
    
    # 1. Filtros de Busca
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_selecionado = st.sidebar.selectbox("Mês Pretendido", meses)
    
    cidade_digitada = st.sidebar.text_input("Cidade", placeholder="Ex: Votorantim")
    congregacao_digitada = st.sidebar.text_input("Congregação", placeholder="Ex: Parque Jataí")

    st.sidebar.markdown("---")
    
    # 2. Botão Street View (Dinâmico)
    if cidade_digitada and congregacao_digitada:
        query_map = f"Salão do Reino das Testemunhas de Jeová {congregacao_digitada} {cidade_digitada}"
        link_map = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query_map)}"
        
        st.sidebar.markdown(f"""
            <a href="{link_map}" target="_blank">
                <button style="
                    background-color: #34A853; color: white; width: 100%; 
                    padding: 10px; border: none; border-radius: 5px; font-weight: bold; cursor: pointer;">
                    🗺️ Ver Salão no Mapa
                </button>
            </a>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.info("Digite Cidade e Congregação para ver o mapa.")

    # --- ÁREA PRINCIPAL (CARDS) ---
    st.title(f"Oradores Disponíveis")
    if congregacao_digitada:
        st.caption(f"Buscando em: {congregacao_digitada} - {cidade_digitada}")
    
    # Lógica de Filtro dos Cards
    if not df_oradores.empty:
        df_filtrado = df_oradores.copy()
        
        # Filtra por Cidade (se digitado)
        if cidade_digitada:
            df_filtrado = df_filtrado[df_filtrado['cidade'].astype(str).str.contains(cidade_digitada, case=False)]
        
        # Filtra por Congregação (se digitado)
        if congregacao_digitada:
            df_filtrado = df_filtrado[df_filtrado['congregacao'].astype(str).str.contains(congregacao_digitada, case=False)]
        
        # MOSTRAR CARDS
        if df_filtrado.empty:
            if congregacao_digitada:
                st.warning("Nenhum orador encontrado nesta congregação. Verifique se a coluna 'congregacao' está preenchida na planilha.")
            else:
                st.info("Digite uma congregação ao lado para buscar oradores.")
        else:
            # Layout em Grid (3 colunas)
            cols = st.columns(3)
            
            for index, row in df_filtrado.iterrows():
                # Distribui os cards nas colunas
                with cols[index % 3]:
                    # Início do Card Visual
                    st.markdown(f"""
                    <div class="orador-card">
                        <div class="orador-nome">{row['nome']}</div>
                        <div class="orador-cargo">{row['cargo']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Botão para abrir agendamento (Expander dentro da coluna)
                    with st.expander(f"📅 Agendar com {row['nome'].split()[0]}"):
                        with st.form(key=f"form_{index}"):
                            data_escolhida = st.date_input("Data", date.today())
                            
                            # Lógica Inteligente de Temas (Cruza IDs do orador com a lista de temas)
                            temas_do_orador = []
                            ids_raw = str(row['temas_ids']).replace(" ", "").split(",")
                            
                            # Filtra df_temas para pegar apenas os IDs que o orador faz
                            # Assumindo que temas.csv tem colunas: numero, titulo
                            for t_id in ids_raw:
                                tema_match = df_temas[df_temas['numero'].astype(str) == t_id]
                                if not tema_match.empty:
                                    titulo = tema_match.iloc[0]['titulo']
                                    temas_do_orador.append(f"{t_id} - {titulo}")
                            
                            # Se não achou temas pelos IDs, mostra todos (fallback)
                            if not temas_do_orador:
                                temas_do_orador = [f"{r['numero']} - {r['titulo']}" for i, r in df_temas.iterrows()]

                            tema_selecionado = st.selectbox("Escolha o Tema", temas_do_orador)
                            
                            submitted = st.form_submit_button("Confirmar Agendamento")
                            
                            if submitted:
                                # Salva na aba AGENDA
                                # Formato: id(auto), data, orador, cargo, tema_numero, tema_titulo
                                t_num = tema_selecionado.split(' - ')[0]
                                t_tit = tema_selecionado.split(' - ')[1] if ' - ' in tema_selecionado else tema_selecionado
                                
                                ws_agenda.append_row([
                                    "", # ID (vazio ou gerar auto)
                                    data_escolhida.strftime("%d/%m/%Y"),
                                    row['nome'],
                                    row['cargo'],
                                    t_num,
                                    t_tit,
                                    congregacao_digitada # Salva onde foi o discurso
                                ])
                                st.toast(f"Agendado! {row['nome']} dia {data_escolhida.strftime('%d/%m')}", icon="✅")
                                time.sleep(1)
                                st.rerun()

                    # Botão de Enviar Solicitação (WhatsApp)
                    if row['contato']:
                        # Mensagem pré-formatada
                        msg_wpp = f"Olá {row['nome']}, gostaríamos de convidar você para fazer um discurso na congregação {congregacao_digitada}."
                        link_wpp = f"https://wa.me/55{str(row['contato']).replace(' ','').replace('-','')}?text={urllib.parse.quote(msg_wpp)}"
                        st.markdown(f"""
                            <a href="{link_wpp}" target="_blank" style="text-decoration: none;">
                                <div style="text-align: center; margin-top: 5px; color: #25D366; font-weight: bold; border: 1px solid #25D366; border-radius: 5px; padding: 5px;">
                                    💬 Enviar Solicitação
                                </div>
                            </a>
                        """, unsafe_allow_html=True)
    else:
        st.info("Carregando banco de dados...")

if __name__ == "__main__":
    main()
