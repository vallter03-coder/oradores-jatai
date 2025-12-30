import streamlit as st
import json
import os
import locale
from datetime import datetime, date
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURAÇÕES ---
ENDERECO_SALAO = "R. João Vieira Nunes, 284 - Parque Jataí, Votorantim - SP"
HORARIO_REUNIAO = "Sábado às 18:30"
LINK_MAPS = "https://maps.app.goo.gl/aFaKWzix8CeXg5m96" # Seu link correto aqui
NOME_PLANILHA_GOOGLE = "oradores_db"

# --- TENTATIVA DE FORÇAR PORTUGUÊS ---
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except:
        pass

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Solicitação de Oradores", layout="wide", page_icon="📝")

# ==========================================
# FUNÇÕES DE BANCO DE DADOS (GOOGLE SHEETS)
# ==========================================
def conectar_gsheets():
    """Conecta ao Google Sheets usando st.secrets"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def carregar_dados():
    """Lê todas as abas da planilha e formata para o app"""
    try:
        client = conectar_gsheets()
        sh = client.open(NOME_PLANILHA_GOOGLE)
        
        # --- 1. Carregar Oradores ---
        ws_oradores = sh.worksheet("oradores")
        raw_oradores = ws_oradores.get_all_records()
        oradores_formatados = []
        
        for row in raw_oradores:
            ids_str = str(row.get('temas_ids', ''))
            if ids_str and ids_str.strip():
                try:
                    ids = [int(x.strip()) for x in ids_str.split(',') if x.strip().isdigit()]
                except:
                    ids = []
            else:
                ids = []

            oradores_formatados.append({
                "nome": row['nome'],
                "cargo": row['cargo'],
                "temas_ids": ids
            })

        # --- 2. Carregar Agenda ---
        ws_agenda = sh.worksheet("agenda")
        agenda = ws_agenda.get_all_records()
        for item in agenda:
            if 'tema_numero' in item and str(item['tema_numero']).isdigit():
                item['tema_numero'] = int(item['tema_numero'])

        # --- 3. Carregar Temas ---
        ws_temas = sh.worksheet("temas")
        temas = ws_temas.get_all_records()

        # --- 4. Carregar Solicitações ---
        ws_solic = sh.worksheet("solicitacoes")
        solicitacoes = ws_solic.get_all_records()

        return {
            "oradores": oradores_formatados,
            "agenda": agenda,
            "temas": temas,
            "solicitacoes": solicitacoes,
            "historico_local": [] 
        }

    except Exception as e:
        st.error(f"Erro ao conectar na planilha: {e}")
        return {"oradores": [], "agenda": [], "temas": [], "solicitacoes": [], "historico_local": []}

def salvar_dados(dados):
    # Nota: O salvamento via JSON na célula A1 é um método de backup rápido.
    # O ideal para produção seria salvar linha a linha nas abas respectivas.
    try:
        client = conectar_gsheets()
        sheet = client.open(NOME_PLANILHA_GOOGLE).sheet1
        conteudo_texto = json.dumps(dados, ensure_ascii=False)
        sheet.update_acell('A1', conteudo_texto)
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- INICIALIZAÇÃO DE SESSÃO ---
if 'db' not in st.session_state: st.session_state['db'] = carregar_dados()
db = st.session_state['db']
if 'carrinho' not in st.session_state: st.session_state['carrinho'] = []
if 'modo_admin' not in st.session_state: st.session_state['modo_admin'] = False
if 'mostrar_login' not in st.session_state: st.session_state['mostrar_login'] = False

# ==========================================
# CSS (DESIGN ESTILO "CARD" LIMPO)
# ==========================================
st.markdown("""
<style>
    /* Fundo Geral */
    .stApp {
        background-color: #F4F6F9; /* Cinza bem claro profissional */
        color: #31333F;
    }
    
    /* Transformar containers em CARDS brancos com sombra */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); /* Sombra suave */
    }

    /* Inputs (Caixas de texto) */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stDateInput input {
        background-color: #FFFFFF;
        color: #333;
        border-radius: 6px;
        border: 1px solid #D6D6D6;
    }
    
    /* Botões */
    div.stButton > button {
        background-color: #004E8C; /* Azul Profissional */
        color: white;
        border-radius: 6px;
        font-weight: 600;
        height: 3em;
        border: none;
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        background-color: #003366; /* Azul mais escuro ao passar o mouse */
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    
    /* Botão Secundário (Ex: Sair) */
    button[kind="secondary"] {
        background-color: #E0E0E0 !important;
        color: #333 !important;
    }
    
    /* Botão Primário (Ex: Enviar) */
    button[kind="primary"] {
        background-color: #28a745 !important; /* Verde */
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E0E0E0;
    }

    /* Estilos Específicos do Admin */
    .pedido-card {
        background-color: #F8F9FA; 
        border-left: 5px solid #004E8C;
        padding: 15px; 
        margin-bottom: 10px; 
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .pedido-data { color: #004E8C; font-weight: bold; font-size: 0.9em; }
    .pedido-nome { font-weight: bold; font-size: 1.1em; color: #333; }
    .pedido-tema { font-style: italic; color: #666; font-size: 0.95em; }
    
    /* Títulos */
    h1, h2, h3 {
        color: #004E8C;
        font-family: 'Segoe UI', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# --- ÍCONES E MAPAS ---
ICONES = {"Ancião": "🛡️", "Servo Ministerial": "💼", "Outro": "👤"}
MAPA_MESES = {
    "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6,
    "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12
}

# ==========================================
# ÁREAS DO SISTEMA
# ==========================================
def area_publica():
    st.markdown("### 👋 Bem-vindo!")
    st.markdown("Preencha os dados da sua congregação abaixo para visualizar os oradores disponíveis.")
    
    with st.container(border=True):
        st.caption("📍 **PASSO 1: Identificação**")
        col_cidade, col_cong, col_mes = st.columns([1.5, 2, 1])
        cidade = col_cidade.text_input("Sua Cidade:")
        nome_congregacao = col_cong.text_input("Sua Congregação:")
        opcoes_meses = ["Selecione..."] + list(MAPA_MESES.keys())
        mes_referencia = col_mes.selectbox("Mês:", opcoes_meses)

    if not cidade or not nome_congregacao or mes_referencia == "Selecione...":
        st.info("👆 Por favor, preencha a identificação acima para continuar.")
        return

    solicitante_completo = f"{cidade} - {nome_congregacao}"
    hoje = date.today()
    mes_num = MAPA_MESES[mes_referencia]
    ano_alvo = hoje.year + 1 if mes_num < hoje.month else hoje.year
    data_padrao = date(ano_alvo, mes_num, 1)

    st.divider()
    if not db['oradores']:
        st.warning("Nenhum orador cadastrado.")
        return

    st.markdown("### 🗣️ Oradores Disponíveis")
    st.caption("Selecione o orador, a data e o tema desejado.")
    
    cols = st.columns(3)
    for index, orador in enumerate(db['oradores']):
        col = cols[index % 3]
        with col:
            # O container com border=True agora vira um "CARD" branco graças ao CSS
            with st.container(border=True):
                cargo = orador.get('cargo', 'Outro')
                icone = ICONES.get(cargo, "👤")
                
                # Cabeçalho do Card
                st.markdown(f"#### {icone} {orador['nome']}")
                st.markdown(f"<span style='color:gray; font-size:0.9em'>{cargo}</span>", unsafe_allow_html=True)
                st.markdown("---")
                
                # Seleção de Data
                st.markdown("**📅 Data Preferida:**")
                data_pref = st.date_input("Data", value=data_padrao, min_value=date.today(), format="DD/MM/YYYY", key=f"date_{index}", label_visibility="collapsed")
                
                # Seleção de Temas
                temas_ids = orador.get('temas_ids', [])
                tema_escolhido_str = None
                
                if temas_ids:
                    st.markdown("**📖 Tema:**")
                    temas_completos = [t for t in db['temas'] if t['numero'] in temas_ids]
                    temas_completos.sort(key=lambda x: x['numero'])
                    opcoes = [f"{t['numero']} - {t['titulo']}" for t in temas_completos]
                    
                    # Scrollable container para temas
                    with st.container(height=120):
                        tema_escolhido_str = st.radio("Temas", opcoes, key=f"radio_{index}", label_visibility="collapsed", index=None)
                else:
                    st.warning("Sem temas cadastrados.")

                st.write("")
                
                # Botão de Ação
                ja_no_carrinho = any(item['orador'] == orador['nome'] and item['data'] == data_pref.strftime("%Y-%m-%d") for item in st.session_state['carrinho'])
                
                if ja_no_carrinho:
                    st.success("✅ Selecionado")
                else:
                    if st.button("➕ Adicionar à Lista", key=f"add_{index}", use_container_width=True):
                        if tema_escolhido_str:
                            item = {"orador": orador['nome'], "cargo": cargo, "tema": tema_escolhido_str, "data": data_pref.strftime("%Y-%m-%d")}
                            st.session_state['carrinho'].append(item)
                            st.rerun()
                        else:
                            st.error("Selecione um tema.")

    # Carrinho na Sidebar
    with st.sidebar:
        st.header("📋 Seu Pedido")
        st.info(f"Ref: {mes_referencia}/{ano_alvo}")
        st.write(f"🏠 **{solicitante_completo}**")
        st.divider()
        
        if st.session_state['carrinho']:
            for i, item in enumerate(st.session_state['carrinho']):
                dt_fmt = datetime.strptime(item['data'], '%Y-%m-%d').strftime('%d/%m')
                # Cardzinho do carrinho
                st.markdown(f"""
                <div style="background-color: white; padding: 10px; border-radius: 5px; border-left: 4px solid #004E8C; margin-bottom: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                    <div style="font-weight:bold; color:#004E8C;">🗓️ {dt_fmt}</div>
                    <div>{item['orador']}</div>
                    <small style="color:#666;">📖 {item['tema']}</small>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("Remover", key=f"rem_{i}", use_container_width=True):
                    st.session_state['carrinho'].pop(i)
                    st.rerun()
            
            st.divider()
            if st.button("🚀 ENVIAR PEDIDO", type="primary", use_container_width=True):
                nova_solicitacao = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "solicitante": solicitante_completo, 
                    "mes": f"{mes_referencia}/{ano_alvo}", 
                    "data_envio": datetime.now().strftime("%Y-%m-%d %H:%M"), 
                    "itens": st.session_state['carrinho']
                }
                if "solicitacoes" not in db: db["solicitacoes"] = []
                db['solicitacoes'].append(nova_solicitacao)
                salvar_dados(db)
                st.session_state['carrinho'] = []
                st.success("Pedido Enviado com Sucesso!")
                st.balloons()
        else:
            st.caption("Sua lista de oradores está vazia.")

def area_admin():
    tab1, tab2, tab3 = st.tabs(["📩 Pedidos Recebidos", "📖 Histórico/Busca", "👥 Gerenciar Oradores"])
    
    with tab1:
        st.subheader("Solicitações Pendentes")
        if not db['solicitacoes']: 
            st.info("Nenhuma solicitação recebida.")
        else:
            for solic in reversed(db['solicitacoes']):
                with st.expander(f"📌 {solic['solicitante']} - {solic['mes']} (Enviado em: {solic['data_envio']})"):
                    texto_zap = f"*Pedido: {solic['solicitante']} ({solic['mes']})*\n\n"
                    
                    for item in solic['itens']:
                        data_fmt = datetime.strptime(item['data'], "%Y-%m-%d").strftime("%d/%m")
                        # Card estilo admin
                        st.markdown(f"""
                        <div class="pedido-card">
                            <div class="pedido-data">🗓️ {data_fmt}</div>
                            <div class="pedido-nome">{item['orador']} <small style="color:#666">({item['cargo']})</small></div>
                            <div class="pedido-tema">📖 {item['tema']}</div>
                        </div>""", unsafe_allow_html=True)
                        texto_zap += f"✅ {data_fmt} - {item['orador']}\n📖 {item['tema']}\n\n"
                    
                    st.divider()
                    c1, c2 = st.columns([3, 1])
                    c1.text_area("Texto para WhatsApp", texto_zap, height=150)
                    
                    with c2:
                        st.write("")
                        st.write("")
                        if st.button("🗑️ Excluir Pedido", key=f"del_sol_{solic['id']}", type="primary", use_container_width=True):
                            db['solicitacoes'] = [s for s in db['solicitacoes'] if s['id'] != solic['id']]
                            salvar_dados(db)
                            st.session_state['db'] = db
                            st.rerun()

    with tab2:
        st.subheader("🔍 Verificar Histórico")
        col_busca, col_res = st.columns([1, 2])
        num_busca = col_busca.number_input("Número do Tema:", min_value=1, step=1)
        
        with col_res:
            historico_filtrado = [h for h in db['historico_local'] if h['tema_numero'] == num_busca]
            if historico_filtrado:
                mais_recente = max(historico_filtrado, key=lambda x: x['data'])
                dt_obj = datetime.strptime(mais_recente['data'], "%Y-%m-%d").date()
                dias = (date.today() - dt_obj).days
                dt_fmt = dt_obj.strftime("%d/%m/%Y")
                
                if dias < 365: 
                    st.error(f"⚠️ Feito há {dias} dias ({dt_fmt})")
                else: 
                    st.success(f"✅ Feito há {dias} dias ({dt_fmt})")
            else: 
                st.success("✅ Nunca registrado neste local.")
        
        st.divider()
        st.subheader("➕ Registrar no Histórico")
        with st.container(border=True):
            opcoes_temas = [f"{t['numero']} - {t['titulo']}" for t in db['temas']]
            tema_add = st.selectbox("Tema Realizado:", opcoes_temas)
            data_add = st.date_input("Data da Realização:", key="data_hist", format="DD/MM/YYYY")
            
            if st.button("Salvar no Histórico", use_container_width=True):
                num_t = int(tema_add.split(' - ')[0])
                tit_t = tema_add.split(' - ')[1]
                db['historico_local'].append({"tema_numero": num_t, "tema_titulo": tit_t, "data": data_add.strftime("%Y-%m-%d")})
                salvar_dados(db)
                st.success("Salvo com sucesso!")
                st.rerun()

    with tab3:
        st.subheader("👥 Gerenciar Oradores")
        nomes_oradores = [o['nome'] for o in db['oradores']]
        orador_edit_nome = st.selectbox("Selecione para Editar ou Criar Novo:", ["-- Novo Orador --"] + nomes_oradores)
        
        with st.container(border=True):
            if orador_edit_nome == "-- Novo Orador --":
                nn = st.text_input("Nome do Orador:")
                nc = st.selectbox("Cargo:", ["Ancião", "Servo Ministerial", "Outro"])
                if st.button("Cadastrar Orador", use_container_width=True):
                    db['oradores'].append({"nome": nn, "cargo": nc, "temas_ids": []})
                    salvar_dados(db)
                    st.success("Orador Cadastrado!")
                    st.rerun()
            else:
                idx = next(i for i, o in enumerate(db['oradores']) if o['nome'] == orador_edit_nome)
                orador_atual = db['oradores'][idx]
                
                n_cargo = st.selectbox("Cargo", ["Ancião", "Servo Ministerial", "Outro"], index=["Ancião", "Servo Ministerial", "Outro"].index(orador_atual.get('cargo', 'Outro')))
                
                temas_sel = st.multiselect(
                    "Temas Habilitados:", 
                    options=db['temas'], 
                    format_func=lambda x: f"{x['numero']} - {x['titulo']}", 
                    default=[t for t in db['temas'] if t['numero'] in orador_atual.get('temas_ids', [])]
                )
                
                if st.button("Salvar Alterações", use_container_width=True):
                    db['oradores'][idx]['cargo'] = n_cargo
                    db['oradores'][idx]['temas_ids'] = [t['numero'] for t in temas_sel]
                    salvar_dados(db)
                    st.success("Alterações Salvas!")
                    st.rerun()

# --- CABEÇALHO ---
col_header_titulo, col_header_login = st.columns([6, 1])
with col_header_titulo:
    if st.session_state['modo_admin']: 
        st.title("🔒 Painel do Coordenador")
    else: 
        st.title("📝 Solicitação de Oradores")

with col_header_login:
    if st.session_state['modo_admin']:
        if st.button("Sair", key="btn_sair", help="Sair do modo admin", use_container_width=True):
            st.session_state['modo_admin'] = False
            st.session_state['mostrar_login'] = False
            st.rerun()
    else:
        if st.button("Admin", key="btn_admin", help="Acesso do Coordenador", use_container_width=True):
            st.session_state['mostrar_login'] = not st.session_state['mostrar_login']

# Login Area
if st.session_state['mostrar_login'] and not st.session_state['modo_admin']:
    with st.container(border=True):
        st.write("Acesso Restrito")
        col_senha, col_btn_entrar = st.columns([3, 1])
        senha_input = col_senha.text_input("Senha:", type="password", key="login_pass", label_visibility="collapsed", placeholder="Digite a senha...")
        if col_btn_entrar.button("Entrar", use_container_width=True):
            if senha_input == "1234":
                st.session_state['modo_admin'] = True
                st.session_state['mostrar_login'] = False
                st.rerun()
            else: st.error("Senha incorreta.")

# Renderiza a área correta
if st.session_state['modo_admin']: 
    area_admin()
else: 
    area_publica()

# Sidebar Info
st.sidebar.markdown("---")
st.sidebar.info(f"📍 **Salão do Reino:**\n\n{ENDERECO_SALAO}\n\n🕒 **Reunião:** {HORARIO_REUNIAO}")

# Botão Estilizado de Mapa
st.sidebar.markdown(f"""
    <a href="{LINK_MAPS}" target="_blank" style="text-decoration: none;">
        <div style="background-color: #4CAF50; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold;">
            🗺️ Ver no Google Maps
        </div>
    </a>
""", unsafe_allow_html=True)
