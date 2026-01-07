import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from st_copy_to_clipboard import st_copy_to_clipboard
from datetime import datetime, date

# ==========================================
# 1. CONFIGURAÇÕES E CONEXÃO
# ==========================================
LINK_PLANILHA = "https://docs.google.com/spreadsheets/d/1_xQuUAsP5klPeats3lqiSnZx54vzAZHYsoVBg4cnMpQ/edit?usp=sharing"
ENDERECO_SALAO = "Rua João Vieira Nunes, 284, Parque Jataí, Votorantim/SP - CEP 18117-220"
HORARIO_REUNIAO = "Sábado às 18:30"
LINK_MAPS = "https://maps.app.goo.gl/36kLuQvSyK1norNm6"

st.set_page_config(page_title="Oradores Parque Jataí", layout="wide", initial_sidebar_state="collapsed")

def formatar_data_br(data_iso):
    try:
        return datetime.strptime(str(data_iso).split('T')[0], "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return str(data_iso)

@st.cache_resource
def get_gc_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def carregar_dados():
    client = get_gc_client()
    sh = client.open_by_url(LINK_PLANILHA)
    temas_raw = sh.worksheet("temas").get_all_records()
    lista_temas = [f"{t.get('numero')} - {t.get('titulo')}" for t in temas_raw]
    mapa_temas = {str(t.get('numero')): t.get('titulo') for t in temas_raw}
    return {
        "oradores": sh.worksheet("oradores").get_all_records(),
        "mapa_temas": mapa_temas,
        "lista_temas": lista_temas,
        "historico": sh.worksheet("historico").get_all_records(),
        "bloqueios": sh.worksheet("bloqueios").get_all_records()
    }

if 'db' not in st.session_state: st.session_state['db'] = carregar_dados()
db = st.session_state['db']

def acao_planilha(aba, tipo, dados=None, linha=None):
    try:
        client = get_gc_client()
        sh = client.open_by_url(LINK_PLANILHA)
        ws = sh.worksheet(aba)
        if tipo == "add": ws.append_row(dados)
        elif tipo == "del": ws.delete_rows(linha)
        elif tipo == "upd": ws.update(f"A{linha}:C{linha}", [dados])
        st.cache_data.clear()
        st.session_state['db'] = carregar_dados()
        return True
    except Exception as e:
        st.error(f"Erro: {e}")
        return False

# ==========================================
# 2. CSS PARA BOTÕES GÊMEOS (RESOLVIDO)
# ==========================================
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    
    /* Força botões e Iframes a terem o mesmo visual */
    .stButton button, a[data-testid="stLinkButton"], iframe { 
        background-color: #262730 !important; 
        border: 1px solid #444 !important;
        border-radius: 8px !important; 
        height: 42px !important;
        margin: 0 !important;
    }

    /* Botão Maps */
    .stButton button, a[data-testid="stLinkButton"] {
        color: white !important;
        font-weight: bold !important;
        width: 100% !important;
        display: flex !important;
        align-items: center;
        justify-content: center;
    }

    /* Botão Copiar (Limpeza do Iframe) */
    iframe { 
        width: 100% !important;
        background-color: transparent !important;
    }

    .item-box { border: 1px solid #333; border-radius: 10px; margin-bottom: 12px; background: #1C1E26; overflow: hidden; }
    .item-header { background: #2D313E; padding: 10px 15px; color: #5D9CEC; font-weight: bold; border-bottom: 1px solid #333; }
    .item-body { padding: 8px 15px; font-size: 0.9em; color: #BBB; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. INTERFACES
# ==========================================
def mural():
    with st.container(border=True):
        st.markdown(f"🏛️ **Salão do Reino - Parque Jataí**")
        st.caption(f"📍 {ENDERECO_SALAO} | 🕒 {HORARIO_REUNIAO}")
        
        # Colunas com gap reduzido
        c1, c2 = st.columns(2, gap="small") 
        with c1:
            st.link_button("📍 MAPS", LINK_MAPS)
        with c2:
            texto_copia = f"🏛️ *Salão Jataí*\n📍 {ENDERECO_SALAO}\n🕒 {HORARIO_REUNIAO}\n🗺️ {LINK_MAPS}"
            st_copy_to_clipboard(texto_copia, "📋 COPIAR ENDEREÇO")

    st.write("### 🗣️ Oradores")
    for o in db.get('oradores', []):
        nome = str(o.get('nome','')).upper()
        if not nome or nome == "NONE": continue
        ids_raw = str(o.get('temas_ids', '')).replace('.', ',').split(',')
        temas_desc = [f"📖 {tid.strip()} - {db['mapa_temas'].get(tid.strip(), '???')}" for tid in ids_raw if tid.strip().isdigit()]
        st.markdown(f'<div class="item-box"><div class="item-header">👤 {nome}</div><div class="item-body">{"<br>".join(temas_desc)}</div></div>', unsafe_allow_html=True)

def area_admin():
    st.title("🔒 Gestão Interna")
    c1, c2 = st.columns(2)
    if c1.button("⬅️ Sair"): st.session_state['logado'] = False; st.rerun()
    if c2.button("🔄 Atualizar"): st.cache_data.clear(); st.session_state['db'] = carregar_dados(); st.rerun()

    t1, t2, t3 = st.tabs(["👥 Oradores", "🚫 Bloqueios", "📜 Histórico"])

    with t1:
        if 'edit_idx' not in st.session_state: st.session_state['edit_idx'] = None
        ex = st.session_state['edit_idx']
        with st.form("f_or"):
            n = st.text_input("Nome", value=str(db['oradores'][ex]['nome']) if ex is not None else "")
            c = st.selectbox("Cargo", ["Ancião", "Servo Ministerial"], index=0 if ex is None or db['oradores'][ex]['cargo']=="Ancião" else 1)
            def_t = [f"{i.strip()} - {db['mapa_temas'].get(i.strip(), '')}" for i in str(db['oradores'][ex]['temas_ids']).replace('.',',').split(',') if i.strip() in db['mapa_temas']] if ex is not None else []
            sel_t = st.multiselect("Temas", options=db['lista_temas'], default=def_t)
            ids_finais = ", ".join([x.split(" - ")[0] for x in sel_t])
            if st.form_submit_button("Salvar Orador"):
                if acao_planilha("oradores", "add" if ex is None else "upd", [n, c, ids_finais], linha=None if ex is None else ex+2):
                    st.session_state['edit_idx'] = None; st.rerun()

        for i, o in enumerate(db.get('oradores', [])):
            col_t, col_e, col_d = st.columns([6, 0.7, 0.7])
            col_t.write(f"👤 {o.get('nome')}")
            if col_e.button("📝", key=f"e{i}"): st.session_state['edit_idx'] = i; st.rerun()
            if col_d.button("🗑️", key=f"d{i}"): acao_planilha("oradores", "del", linha=i+2); st.rerun()

    with t2:
        with st.form("f_b"):
            sel_b = st.selectbox("Tema para Bloquear", options=db['lista_temas'])
            if st.form_submit_button("Bloquear"):
                acao_planilha("bloqueios", "add", [sel_b.split(" - ")[0], date.today().isoformat()]); st.rerun()
        for i, b in enumerate(db.get('bloqueios', [])):
            num = str(b.get('tema'))
            c_t, c_b = st.columns([6, 1])
            c_t.write(f"🚫 Tema {num} - {db['mapa_temas'].get(num)} ({formatar_data_br(b.get('data'))})")
            if c_b.button("🗑️", key=f"rb{i}"): acao_planilha("bloqueios", "del", linha=i+2); st.rerun()

    with t3:
        st.subheader("Registrar Realização")
        sel_h = st.selectbox("Selecione o Tema", options=[""] + db['lista_temas'])
        if sel_h:
            num_tema = sel_h.split(" - ")[0]
            if any(str(bl.get('tema')) == str(num_tema) for bl in db['bloqueios']):
                st.error(f"⚠️ BLOQUEADO!")
            registros = [datetime.strptime(str(list(h.values())[0]).split('T')[0], "%Y-%m-%d").date() for h in db['historico'] if str(list(h.values())[1]) == str(num_tema)]
            if registros:
                u = max(registros)
                st.warning(f"ℹ️ Feito em {formatar_data_br(u)} (há {(date.today()-u).days} dias).")
        with st.form("f_h_real"):
            dt = st.date_input("Data da Reunião", value=date.today())
            if st.form_submit_button("Confirmar Realização"):
                if sel_h: acao_planilha("historico", "add", [dt.isoformat(), sel_h.split(" - ")[0]]); st.rerun()
        for i, h in enumerate(reversed(db.get('historico', []))):
            idx = len(db['historico']) - i + 1
            val = list(h.values())
            c_t, c_b = st.columns([6, 1])
            c_t.write(f"📅 {formatar_data_br(val[0])} — Tema {val[1]} - {db['mapa_temas'].get(str(val[1]), '???')}")
            if c_b.button("🗑️", key=f"rh{i}"): acao_planilha("historico", "del", linha=idx); st.rerun()

# --- LOGIN ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
if st.session_state['logado']:
    area_admin()
else:
    mural()
    with st.form("login"):
        senha = st.text_input("Senha Admin:", type="password")
        if st.form_submit_button("Entrar"):
            if senha == "1234": st.session_state['logado'] = True; st.rerun()
            else: st.error("Incorreta")
