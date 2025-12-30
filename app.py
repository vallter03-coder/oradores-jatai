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
LINK_MAPS = "https://maps.app.goo.gl/aFaKWzix8CeXg5m96"
NOME_PLANILHA_GOOGLE = "oradores_db" # Nome exato da sua planilha

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
    try:
        client = conectar_gsheets()
        sheet = client.open(NOME_PLANILHA_GOOGLE).sheet1
        # OBS: Se você estiver usando abas separadas, o ideal seria atualizar cada aba.
        # Este método salva um JSON na aba 1 (funciona como backup rápido ou DB simples).
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

# --- CSS (ESTILO VISUAL) ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #1c1e26;
        border: 1px solid #33353F;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stDateInput input {
        background-color: #262730; color: white; border-radius: 8px; border: 1px solid #4A4A4A;
    }
    div.stButton > button { border-radius: 8px; font-weight: 600; height: 3em; }
    .pedido-card {
        background-color: rgba(255, 255, 255, 0.03); border-left: 4px solid #4CAF50;
        padding: 12px; margin-bottom: 12px; border-radius: 6px;
    }
    .pedido-data { color: #4CAF50; font-weight: bold; font-size: 1em; margin-bottom: 2px; }
    .pedido-nome { font-weight: bold; font-size: 1.1em; color: #EEE; }
    .pedido-tema { font-style: italic; opacity: 0.8; font-size: 0.9em; color: #CCC; }
    .status-ok { background-color: #155724; color: #d4edda; padding: 10px; border-radius: 5px; font-weight: bold; border: 1px solid #0f3e1a; }
    .status-alert { background-color: #721c24; color: #f8d7da; padding: 10px; border-radius: 5px; font-weight: bold; border: 1px solid #5c161d; }
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
    st.markdown("Preencha os dados da sua congregação e selecione os oradores.")
    with st.container(border=True):
        st.caption("📍 **PASSO 1: Identificação**")
        col_cidade, col_cong, col_mes = st.columns([1.5, 2, 1])
        cidade = col_cidade.text_input("Sua Cidade:")
        nome_congregacao = col_cong.text_input("Sua Congregação:")
        opcoes_meses = ["Selecione..."] + list(MAPA_MESES.keys())
        mes_referencia = col_mes.selectbox("Mês:", opcoes_meses)

    if not cidade or not nome_congregacao or mes_referencia == "Selecione...":
        st.info("👆 Preencha os dados acima para ver os oradores disponíveis.")
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

    st.caption("🗣️ **PASSO 2: Escolha os Oradores**")
    cols = st.columns(3)
    for index, orador in enumerate(db['oradores']):
        col = cols[index % 3]
        with col:
            with st.container(border=True):
                cargo = orador.get('cargo', 'Outro')
                icone = ICONES.get(cargo, "👤")
                st.subheader(f"{icone} {orador['nome']}")
                c_info, c_data = st.columns([1, 1.4])
                with c_info:
                    st.markdown(f"<div style='margin-top: 5px;'><b>Cargo:</b> {cargo}</div>", unsafe_allow_html=True)
                with c_data:
                    cd_label, cd_input = st.columns([0.3, 0.7])
                    with cd_label: st.markdown("<div style='margin-top: 5px; font-weight: bold;'>Data:</div>", unsafe_allow_html=True)
                    with cd_input:
                        data_pref = st.date_input("Data", value=data_padrao, min_value=date.today(), format="DD/MM/YYYY", key=f"date_{index}", label_visibility="collapsed")
                
                temas_ids = orador.get('temas_ids', [])
                tema_escolhido_str = None
                if temas_ids:
                    temas_completos = [t for t in db['temas'] if t['numero'] in temas_ids]
                    temas_completos.sort(key=lambda x: x['numero'])
                    opcoes = [f"{t['numero']} - {t['titulo']}" for t in temas_completos]
                    st.markdown("---")
                    st.caption("📚 **Escolha o Tema:**")
                    with st.container(height=120):
                        tema_escolhido_str = st.radio("Temas", opcoes, key=f"radio_{index}", label_visibility="collapsed", index=None)
                else:
                    st.caption("Sem temas cadastrados.")

                st.write("")
                ja_no_carrinho = any(item['orador'] == orador['nome'] and item['data'] == data_pref.strftime("%Y-%m-%d") for item in st.session_state['carrinho'])
                if ja_no_carrinho:
                    st.success("✅ Adicionado!")
                else:
                    if st.button("➕ Adicionar", key=f"add_{index}", use_container_width=True):
                        if tema_escolhido_str:
                            item = {"orador": orador['nome'], "cargo": cargo, "tema": tema_escolhido_str, "data": data_pref.strftime("%Y-%m-%d")}
                            st.session_state['carrinho'].append(item)
                            st.rerun()
                        else:
                            st.error("Selecione um tema.")

    with st.sidebar:
        st.header("📋 Seu Pedido")
        st.caption(f"Ref: {mes_referencia}/{ano_alvo}")
        st.write(f"**{solicitante_completo}**")
        st.divider()
        if st.session_state['carrinho']:
            for i, item in enumerate(st.session_state['carrinho']):
                dt_fmt = datetime.strptime(item['data'], '%Y-%m-%d').strftime('%d/%m')
                st.markdown(f"""<div style="background-color: #262730; padding: 10px; border-radius: 5px; border-left: 3px solid #4CAF50; margin-bottom: 5px;"><b>{dt_fmt}</b> - {item['orador']}<br><small>📖 {item['tema']}</small></div>""", unsafe_allow_html=True)
                if st.button("Remover", key=f"rem_{i}", use_container_width=True):
                    st.session_state['carrinho'].pop(i)
                    st.rerun()
            st.divider()
            if st.button("🚀 ENVIAR PEDIDO", type="primary", use_container_width=True):
                nova_solicitacao = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "solicitante": solicitante_completo, "mes": f"{mes_referencia}/{ano_alvo}", "data_envio": datetime.now().strftime("%Y-%m-%d %H:%M"), "itens": st.session_state['carrinho']
                }
                if "solicitacoes" not in db: db["solicitacoes"] = []
                db['solicitacoes'].append(nova_solicitacao)
                salvar_dados(db)
                st.session_state['carrinho'] = []
                st.success("Pedido Enviado!")
                st.balloons()
        else:
            st.info("Sua lista está vazia.")

def area_admin():
    tab1, tab2, tab3 = st.tabs(["📩 Pedidos", "📖 Histórico/Busca", "👥 Oradores"])
    with tab1:
        if not db['solicitacoes']: st.info("Nenhuma solicitação.")
        else:
            for solic in reversed(db['solicitacoes']):
                with st.expander(f"📌 {solic['solicitante']} - {solic['mes']}"):
                    texto_zap = f"*Pedido: {solic['solicitante']} ({solic['mes']})*\n\n"
                    for item in solic['itens']:
                        data_fmt = datetime.strptime(item['data'], "%Y-%m-%d").strftime("%d/%m")
                        st.markdown(f"""<div class="pedido-card"><div class="pedido-data">🗓️ {data_fmt}</div><div class="pedido-nome">{item['orador']} <small>({item['cargo']})</small></div><div class="pedido-tema">📖 {item['tema']}</div></div>""", unsafe_allow_html=True)
                        texto_zap += f"✅ {data_fmt} - {item['orador']}\n📖 {item['tema']}\n\n"
                    st.divider()
                    c1, c2 = st.columns([3, 1])
                    c1.code(texto_zap, language=None)
                    if c2.button("🗑️ Excluir", key=f"del_sol_{solic['id']}", type="primary", use_container_width=True):
                        db['solicitacoes'] = [s for s in db['solicitacoes'] if s['id'] != solic['id']]
                        salvar_dados(db)
                        st.session_state['db'] = db
                        st.rerun()
    with tab2:
        st.write("### 🔍 Histórico")
        col_busca, col_res = st.columns([1, 2])
        num_busca = col_busca.number_input("Nº Tema:", min_value=1, step=1)
        with col_res:
            st.write("") 
            st.write("") 
            historico_filtrado = [h for h in db['historico_local'] if h['tema_numero'] == num_busca]
            if historico_filtrado:
                mais_recente = max(historico_filtrado, key=lambda x: x['data'])
                dt_obj = datetime.strptime(mais_recente['data'], "%Y-%m-%d").date()
                dias = (date.today() - dt_obj).days
                dt_fmt = dt_obj.strftime("%d/%m/%Y")
                
                # --- BUSCA: Traz o titulo do tema ---
                nome_tema_busca = next((t['titulo'] for t in db['temas'] if t['numero'] == num_busca), "Tema Desconhecido")
                
                msg = f"#{num_busca} - {nome_tema_busca}<br>Feito há {dias} dias ({dt_fmt})"
                
                if dias < 365: st.markdown(f"<div class='status-alert'>⚠️ {msg}</div>", unsafe_allow_html=True)
                else: st.markdown(f"<div class='status-ok'>✅ {msg}</div>", unsafe_allow_html=True)
            else: st.markdown("<div class='status-ok'>✅ Nunca registrado.</div>", unsafe_allow_html=True)
        st.divider()
        st.write("### ➕ Registrar")
        opcoes_temas = [f"{t['numero']} - {t['titulo']}" for t in db['temas']]
        tema_add = st.selectbox("Tema:", opcoes_temas)
        data_add = st.date_input("Data:", key="data_hist", format="DD/MM/YYYY")
        if st.button("Registrar", use_container_width=True):
            num_t = int(tema_add.split(' - ')[0])
            tit_t = tema_add.split(' - ')[1]
            db['historico_local'].append({"tema_numero": num_t, "tema_titulo": tit_t, "data": data_add.strftime("%Y-%m-%d")})
            salvar_dados(db)
            st.success("Salvo!")
            st.rerun()
        
        with st.expander("Ver lista completa"):
            if db.get('historico_local'):
                hist_sorted = sorted(db['historico_local'], key=lambda x: x['data'], reverse=True)
                for i, hist in enumerate(hist_sorted):
                    d_obj = datetime.strptime(hist['data'], "%Y-%m-%d").date()
                    d_fmt = d_obj.strftime("%d/%m/%Y")
                    dias_atras = (date.today() - d_obj).days
                    
                    # --- LISTA: Pega o titulo do tema pelo numero ---
                    t_titulo = next((t['titulo'] for t in db['temas'] if t['numero'] == hist['tema_numero']), "Desconhecido")
                    
                    c1, c2 = st.columns([4, 1])
                    # Mostra: Data - #Numero Titulo (ha X dias)
                    c1.markdown(f"**{d_fmt}** — #{hist['tema_numero']} **{t_titulo}** <br><span style='color: gray; font-size: 0.9em;'>(há {dias_atras} dias)</span>", unsafe_allow_html=True)
                    if c2.button("🗑️", key=f"del_hist_{i}"):
                        db['historico_local'].remove(hist)
                        salvar_dados(db)
                        st.rerun()

    with tab3:
        st.write("### Oradores")
        nomes_oradores = [o['nome'] for o in db['oradores']]
        orador_edit_nome = st.selectbox("Selecione para Editar:", ["-- Novo --"] + nomes_oradores)
        
        if orador_edit_nome == "-- Novo --":
            st.markdown("#### Cadastrar Novo")
            nn = st.text_input("Nome do Novo Orador:")
            nc = st.selectbox("Cargo:", ["Ancião", "Servo Ministerial", "Outro"])
            if st.button("Salvar Novo", use_container_width=True):
                if nn:
                    db['oradores'].append({"nome": nn, "cargo": nc, "temas_ids": []})
                    salvar_dados(db)
                    st.success("Orador Criado!")
                    st.rerun()
                else:
                    st.error("Preencha o nome.")
        else:
            st.markdown(f"#### Editando: {orador_edit_nome}")
            idx = next(i for i, o in enumerate(db['oradores']) if o['nome'] == orador_edit_nome)
            orador_atual = db['oradores'][idx]
            
            # --- EDITAR NOME E CARGO ---
            novo_nome = st.text_input("Nome:", value=orador_atual['nome'])
            n_cargo = st.selectbox("Cargo", ["Ancião", "Servo Ministerial", "Outro"], index=["Ancião", "Servo Ministerial", "Outro"].index(orador_atual.get('cargo', 'Outro')))
            
            # --- TEMAS ---
            temas_sel = st.multiselect("Temas:", options=db['temas'], format_func=lambda x: f"{x['numero']} - {x['titulo']}", default=[t for t in db['temas'] if t['numero'] in orador_atual.get('temas_ids', [])])
            
            st.write("")
            col_salvar, col_excluir = st.columns([2, 1])
            
            with col_salvar:
                if st.button("💾 Salvar Alterações", use_container_width=True):
                    db['oradores'][idx]['nome'] = novo_nome # Salva o novo nome
                    db['oradores'][idx]['cargo'] = n_cargo
                    db['oradores'][idx]['temas_ids'] = [t['numero'] for t in temas_sel]
                    salvar_dados(db)
                    st.success("Atualizado!")
                    st.rerun()
            
            with col_excluir:
                if st.button("🗑️ Excluir Orador", type="primary", use_container_width=True):
                    db['oradores'].pop(idx) # Remove da lista
                    salvar_dados(db)
                    st.warning("Orador excluído.")
                    st.rerun()

col_header_titulo, col_header_login = st.columns([6, 1])
with col_header_titulo:
    if st.session_state['modo_admin']: st.title("🔒 Coordenador")
    else: st.title("📝 Solicitação de Oradores")
with col_header_login:
    if st.session_state['modo_admin']:
        if st.button("🔓", help="Sair", use_container_width=True):
            st.session_state['modo_admin'] = False
            st.session_state['mostrar_login'] = False
            st.rerun()
    else:
        if st.button("🔑", help="Acesso Admin", use_container_width=True):
            st.session_state['mostrar_login'] = not st.session_state['mostrar_login']
if st.session_state['mostrar_login'] and not st.session_state['modo_admin']:
    with st.container(border=True):
        col_senha, col_btn_entrar = st.columns([3, 1])
        senha_input = col_senha.text_input("Senha:", type="password", key="login_pass", label_visibility="collapsed", placeholder="Senha...")
        if col_btn_entrar.button("Entrar", use_container_width=True):
            if senha_input == "1234":
                st.session_state['modo_admin'] = True
                st.session_state['mostrar_login'] = False
                st.rerun()
            else: st.error("Senha incorreta.")

if st.session_state['modo_admin']: area_admin()
else: area_publica()

st.sidebar.markdown("---")
st.sidebar.info(f"📍 **Salão do Reino:**\n\n{ENDERECO_SALAO}\n\n🕒 **Reunião:** {HORARIO_REUNIAO}")
st.sidebar.link_button("🗺️ Ver no Street View", LINK_MAPS, use_container_width=True)
