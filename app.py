import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import time

# ==============================================================================
# 1. CONFIGURAÇÕES VISUAIS E PAGINAÇÃO
# ==============================================================================
st.set_page_config(
    page_title="Gestão de Discursos",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Nome da planilha (MANTENHA EXATAMENTE ASSIM)
NOME_DA_SUA_PLANILHA_NO_GOOGLE = "oradores_db"

# CSS para Design Limpo e Profissional
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
    div[data-testid="stMetricValue"] {font-size: 1.2rem; color: #004E8C;}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONEXÃO COM GOOGLE SHEETS
# ==============================================================================
@st.cache_resource
def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
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

def carregar_dados():
    client = conectar_google_sheets()
    try:
        sh = client.open(NOME_DA_SUA_PLANILHA_NO_GOOGLE)
    except:
        st.error(f"❌ Planilha '{NOME_DA_SUA_PLANILHA_NO_GOOGLE}' não encontrada."); st.stop()

    # --- GARANTE COLUNAS ATUALIZADAS (COM CIDADE) ---
    try: ws_oradores = sh.worksheet("ORADORES A1")
    except: ws_oradores = sh.add_worksheet("ORADORES A1", 100, 5); ws_oradores.append_row(["Nome", "Congregacao", "Cidade", "Contato"])
    
    # Verifica se tem a coluna Cidade, se não tiver, avisa (ou poderíamos adicionar, mas vamos assumir o padrão novo)
    # Padrão esperado: Nome, Congregacao, Cidade, Contato
    
    try: ws_prog = sh.worksheet("PROGRAMACAO")
    except: ws_prog = sh.add_worksheet("PROGRAMACAO", 100, 5); ws_prog.append_row(["Data", "Orador", "Tema", "Congregacao", "Cidade"])

    try: ws_temas = sh.worksheet("TEMAS")
    except: st.warning("Crie a aba TEMAS."); st.stop()

    df_oradores = pd.DataFrame(ws_oradores.get_all_records())
    df_prog = pd.DataFrame(ws_prog.get_all_records())
    df_temas = pd.DataFrame(ws_temas.get_all_records())

    return sh, ws_oradores, ws_prog, df_oradores, df_prog, df_temas

# ==============================================================================
# 3. INTERFACE PRINCIPAL
# ==============================================================================
def main():
    try:
        sh, ws_oradores, ws_prog, df_oradores, df_prog, df_temas = carregar_dados()
    except Exception as e:
        st.error(f"Erro de conexão: {e}"); st.stop()

    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2921/2921222.png", width=50)
    st.sidebar.title("Menu")
    menu = st.sidebar.radio("Ir para:", ["📅 Quadro de Discursos (Público)", "🔒 Área do Coordenador"])

    # --------------------------------------------------------------------------
    # PÁGINA PÚBLICA (COM FILTROS RESTAURADOS)
    # --------------------------------------------------------------------------
    if menu == "📅 Quadro de Discursos (Público)":
        st.title("📅 Quadro de Discursos")
        st.markdown("Encontre onde e quando haverá discursos.")
        
        # --- FILTROS DE PESQUISA ---
        with st.container():
            st.markdown("### 🔍 Pesquisar")
            c1, c2, c3 = st.columns(3)
            
            # Filtro 1: Mês
            meses = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
                     7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}
            
            # Adiciona opção "Todos"
            opcoes_mes = ["Todos"] + list(meses.values())
            filtro_mes = c1.selectbox("Mês", options=opcoes_mes)
            
            # Filtro 2 e 3: Cidade e Congregação
            # Pega valores únicos para sugestão, se existirem
            cidades_uniques = df_prog['Cidade'].unique() if 'Cidade' in df_prog.columns else []
            filtro_cidade = c2.selectbox("Cidade", ["Todas"] + list(cidades_uniques)) if len(cidades_uniques) > 0 else c2.text_input("Cidade")
            
            filtro_cong = c3.text_input("Congregação (Digite para buscar)")

        st.markdown("---")

        # --- APLICAR FILTROS ---
        if df_prog.empty:
            st.info("Nenhuma programação cadastrada.")
        else:
            df_view = df_prog.copy()
            
            # Converter Data
            df_view['Data_Dt'] = pd.to_datetime(df_view['Data'], format='%d/%m/%Y', errors='coerce')
            
            # 1. Filtrar Mês
            if filtro_mes != "Todos":
                # Mapeia nome do mês volta para número
                num_mes = [k for k, v in meses.items() if v == filtro_mes][0]
                df_view = df_view[df_view['Data_Dt'].dt.month == num_mes]
            
            # 2. Filtrar Cidade
            if filtro_cidade != "Todas" and filtro_cidade != "":
                if 'Cidade' in df_view.columns:
                    df_view = df_view[df_view['Cidade'].astype(str).str.contains(filtro_cidade, case=False)]
            
            # 3. Filtrar Congregação
            if filtro_cong:
                df_view = df_view[df_view['Congregacao'].astype(str).str.contains(filtro_cong, case=False)]

            # Ordenar e Mostrar
            df_view = df_view.sort_values(by='Data_Dt', ascending=False)
            
            # Seleciona colunas para exibir (garante que Cidade apareça se existir)
            cols_show = ['Data', 'Orador', 'Tema', 'Congregacao']
            if 'Cidade' in df_view.columns:
                cols_show.append('Cidade')
                
            st.dataframe(df_view[cols_show], use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # ÁREA DO COORDENADOR (COM VISÃO LOCAL)
    # --------------------------------------------------------------------------
    elif menu == "🔒 Área do Coordenador":
        st.title("Painel Administrativo")
        
        # Simulação de Login
        if 'logado' not in st.session_state:
            senha = st.sidebar.text_input("Senha", type="password")
            if senha == "1234":
                st.session_state['logado'] = True
                st.rerun()
        
        if st.session_state.get('logado'):
            # --- CONFIGURAÇÃO DA CONGREGAÇÃO DO COORDENADOR ---
            st.sidebar.markdown("---")
            st.sidebar.header("🏠 Sua Congregação")
            
            # Se não tiver configurado na sessão, pede para configurar
            if 'minha_cong' not in st.session_state:
                st.session_state['minha_cong'] = "Central" # Default
            if 'minha_cidade' not in st.session_state:
                st.session_state['minha_cidade'] = "Votorantim" # Default
            
            minha_cong = st.sidebar.text_input("Congregação:", st.session_state['minha_cong'])
            minha_cidade = st.sidebar.text_input("Cidade:", st.session_state['minha_cidade'])
            
            # Atualiza sessão
            st.session_state['minha_cong'] = minha_cong
            st.session_state['minha_cidade'] = minha_cidade
            
            st.sidebar.success(f"Logado em: {minha_cong} ({minha_cidade})")

            # --- ABAS DE GERENCIAMENTO ---
            tab1, tab2, tab3, tab4 = st.tabs([
                "➕ Novo Discurso (Aqui)", 
                "📅 Nossa Programação", 
                "👥 Meus Oradores", 
                "🌎 Visão Geral (Todos)"
            ])

            # 1. REGISTRAR DISCURSO (NA MINHA CONGREGAÇÃO)
            with tab1:
                st.subheader(f"Agendar Discurso na {minha_cong}")
                
                with st.form("form_agenda"):
                    c1, c2 = st.columns(2)
                    data_sel = c1.date_input("Data do Evento", date.today())
                    # Lista de todos os oradores disponíveis (global)
                    lista_oradores = df_oradores['Nome'].unique() if not df_oradores.empty else []
                    orador_sel = c1.selectbox("Selecione o Orador", lista_oradores)
                    
                    # Lista de Temas
                    lista_temas = [f"{r['Numero']} - {r['Tema']}" for i, r in df_temas.iterrows()]
                    tema_sel = c2.selectbox("Tema", lista_temas)
                    
                    st.markdown(f"**Local:** {minha_cong} - {minha_cidade}")
                    
                    if st.form_submit_button("💾 Salvar na Agenda"):
                        # Verifica repetição
                        # Lógica simplificada de verificação
                        ja_fez = False
                        data_fez = None
                        if not df_prog.empty:
                            num_tema = tema_sel.split(' - ')[0]
                            check = df_prog[
                                (df_prog['Orador'] == orador_sel) & 
                                (df_prog['Tema'].astype(str).str.startswith(num_tema))
                            ]
                            if not check.empty:
                                ja_fez = True
                                data_fez = check['Data'].values[0]

                        # Salva (Adicionando Cidade se necessário)
                        row = [data_sel.strftime("%d/%m/%Y"), orador_sel, tema_sel, minha_cong]
                        
                        # Se a planilha tiver coluna Cidade, adiciona
                        # (Garantimos no inicio que tentamos padronizar, mas vamos ser dinâmicos)
                        if len(df_prog.columns) >= 5: 
                             row.append(minha_cidade)
                        
                        ws_prog.append_row(row)
                        st.success("Agendado com sucesso!")
                        
                        if ja_fez:
                            st.warning(f"⚠️ Nota: Este orador já fez este tema em {data_fez}")
                        st.rerun()

            # 2. NOSSA PROGRAMAÇÃO (FILTRADA)
            with tab2:
                st.subheader(f"Discursos agendados em: {minha_cong}")
                if df_prog.empty:
                    st.info("Nada agendado.")
                else:
                    # Filtra apenas a congregação atual
                    df_local = df_prog[df_prog['Congregacao'].astype(str).str.contains(minha_cong, case=False)]
                    if df_local.empty:
                        st.warning(f"Nenhum registro encontrado para '{minha_cong}'.")
                    else:
                        st.dataframe(df_local, use_container_width=True)

            # 3. MEUS ORADORES (FILTRADO)
            with tab3:
                st.subheader(f"Oradores de: {minha_cong}")
                st.caption("Aqui aparecem apenas os oradores que pertencem à sua congregação.")
                
                if df_oradores.empty:
                    st.info("Sem oradores cadastrados.")
                else:
                    # Filtra oradores da congregação atual
                    df_oradores_local = df_oradores[df_oradores['Congregacao'].astype(str).str.contains(minha_cong, case=False)]
                    
                    if df_oradores_local.empty:
                        st.warning(f"Nenhum orador cadastrado na congregação '{minha_cong}'.")
                        if st.button("Cadastrar Novo Orador Local"):
                            # Poderia abrir um form aqui
                            pass
                    else:
                        st.dataframe(df_oradores_local, use_container_width=True)
                        
                        # Opção rápida de editar local
                        sel_orador = st.selectbox("Editar Orador Local:", df_oradores_local['Nome'].unique())
                        if st.button("Excluir Orador Selecionado"):
                            cell = ws_oradores.find(sel_orador)
                            ws_oradores.delete_rows(cell.row)
                            st.success("Excluído!")
                            time.sleep(1); st.rerun()

            # 4. VISÃO GERAL (TODOS)
            with tab4:
                st.subheader("Banco de Dados Geral")
                st.dataframe(df_oradores, use_container_width=True)
                st.markdown("---")
                st.subheader("Adicionar Orador ao Banco Geral")
                with st.form("add_global"):
                    nc1, nc2, nc3 = st.columns(3)
                    new_nome = nc1.text_input("Nome")
                    new_cong = nc2.text_input("Congregação", value=minha_cong)
                    new_cid = nc3.text_input("Cidade", value=minha_cidade)
                    new_cont = st.text_input("Contato")
                    
                    if st.form_submit_button("Cadastrar Orador"):
                        ws_oradores.append_row([new_nome, new_cong, new_cid, new_cont])
                        st.success("Cadastrado!")
                        st.rerun()

if __name__ == "__main__":
    main()
