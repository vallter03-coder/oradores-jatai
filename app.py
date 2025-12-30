import streamlit as st
import json
import locale
from datetime import datetime, date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# ==========================================
# 1. CONFIGURAÇÕES
# ==========================================
ENDERECO_SALAO = "Rua João Vieira Nunes, 284, Parque Jataí, Votorantim/SP - CEP 18117-220"
HORARIO_REUNIAO = "Sábado às 18:30"
LINK_MAPS = "https://maps.app.goo.gl/36kLuQvSyK1norNm6"
NOME_PLANILHA_GOOGLE = "oradores_db"

try: locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except: pass

st.set_page_config(page_title="Solicitação de Oradores", layout="wide", page_icon="📝")

# ==========================================
# 2. BANCO DE DADOS
# ==========================================
def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    return client

def carregar_dados():
    try:
        client = conectar_gsheets()
        sh = client.open(NOME_PLANILHA_GOOGLE)
        
        # Oradores
        ws_oradores = sh.worksheet("oradores")
        raw_oradores = ws_oradores.get_all_records()
        oradores_fmt = []
        for row in raw_oradores:
            ids = []
            if str(row.get('temas_ids', '')).strip():
                try: ids = [int(x.strip()) for x in str(row['temas_ids']).split(',') if x.strip().isdigit()]
                except: pass
            oradores_fmt.append({"nome": row['nome'], "cargo": row['cargo'], "temas_ids": ids})

        # Temas e Solicitações
        temas = sh.worksheet("temas").get_all_records()
        try: solicitacoes = sh.worksheet("solicitacoes").get_all_records()
        except: solicitacoes = []

        return {"oradores": oradores_fmt, "temas": temas, "solicitacoes": solicitacoes}
    except Exception as e:
        st.error(f"Erro Conexão: {e}")
        return {"oradores": [], "temas": [], "solicitacoes": []}

def salvar_dados(dados):
    try:
        client = conectar_gsheets()
        sheet = client.open(NOME_PLANILHA_GOOGLE).sheet1
        sheet.update_acell('A1', json.dumps(dados, ensure_ascii=False))
    except: pass

# Sessão
if 'db' not in st.session_state: st.session_state['db'] = carregar_dados()
db = st.session_state['db']
if 'carrinho' not in st.session_state: st.session_state['carrinho'] = []
if 'modo_admin' not in st.session_state: st.session_state['modo_admin'] = False
if 'mostrar_login' not in st.session_state: st.session_state['mostrar_login'] = False

# ==========================================
# 3. ESTILO (CSS)
# ==========================================
st.markdown("""
<style>
    .stApp { background-color: #F4F6F9; color: #333; }
    div[data-testid="stVerticalBlockBorderWrapper"] { background-color: white; border: 1px solid #ddd; border-radius: 8px; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .stTextInput input, .stSelectbox div, .stDateInput input { background-color: #FFF; border-radius: 4px; }
    div.stButton > button { background-color: #004E8C; color: white; border-radius: 6px; font-weight: bold; }
    [data-testid="stSidebar"] { background-color: white; border-right: 1px solid #DDD; }
    h1, h2, h3 { color: #004E8C; font-family: sans-serif; }
    
    /* Card Admin */
    .admin-card { background: #E3F2FD; padding: 10px; border-radius: 5px; border-left: 5px solid #004E8C; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

ICONES = {"Ancião": "🛡️", "Servo Ministerial": "💼", "Outro": "👤"}
MAPA_MESES = {"Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12}

# ==========================================
# 4. ÁREA PÚBLICA
# ==========================================
def area_publica():
    st.markdown("### 👋 Solicitação de Oradores")
    
    with st.container(border=True):
        st.caption("📍 **Identificação da Congregação**")
        c1, c2, c3 = st.columns([1.5, 2, 1])
        cidade = c1.text_input("Sua Cidade:")
        congregacao = c2.text_input("Sua Congregação:")
        mes_ref = c3.selectbox("Mês:", ["Selecione..."] + list(MAPA_MESES.keys()))

    if not cidade or not congregacao or mes_ref == "Selecione...":
        st.info("👆 Preencha os dados acima para ver os oradores.")
        return

    solicitante = f"{cidade} - {congregacao}"
    hoje = date.today()
    mes_num = MAPA_MESES[mes_ref]
    ano = hoje.year + 1 if mes_num < hoje.month else hoje.year
    data_padrao = date(ano, mes_num, 1)

    st.divider()
    if not db['oradores']:
        st.warning("Nenhum orador cadastrado.")
        return

    st.markdown("### 🗣️ Escolha os Oradores")
    cols = st.columns(3)
    
    for i, orador in enumerate(db['oradores']):
        with cols[i % 3]:
            with st.container(border=True):
                icone = ICONES.get(orador['cargo'], "👤")
                st.markdown(f"#### {icone} {orador['nome']}")
                st.caption(f"{orador['cargo']}")
                st.markdown("---")
                
                st.markdown("**📅 Data:**")
                d_pref = st.date_input("Data", value=data_padrao, min_value=hoje, format="DD/MM/YYYY", key=f"d_{i}", label_visibility="collapsed")
                
                temas_ids = orador.get('temas_ids', [])
                tema_sel = None
                
                if temas_ids:
                    st.markdown("**📖 Escolha o Tema:**")
                    lista_t = [t for t in db['temas'] if t['numero'] in temas_ids]
                    lista_t.sort(key=lambda x: x['numero'])
                    opcoes = [f"{t['numero']} - {t['titulo']}" for t in lista_t]
                    with st.container(height=150):
                        tema_sel = st.radio("Temas", opcoes, key=f"r_{i}", label_visibility="collapsed", index=None)
                else: st.warning("Sem temas.")

                st.write("")
                if st.button("Confirmar", key=f"btn_{i}", use_container_width=True):
                    if tema_sel:
                        st.session_state['carrinho'].append({
                            "orador": orador['nome'],
                            "cargo": orador['cargo'],
                            "tema": tema_sel,
                            "data": d_pref.strftime("%Y-%m-%d")
                        })
                        st.rerun()
                    else: st.error("Escolha um tema!")

    with st.sidebar:
        st.header("📋 Resumo")
        st.info(f"Mês: {mes_ref}/{ano}")
        st.write(f"🏠 **{solicitante}**")
        st.divider()
        if st.session_state['carrinho']:
            for idx, item in enumerate(st.session_state['carrinho']):
                d_fmt = datetime.strptime(item['data'], '%Y-%m-%d').strftime('%d/%m')
                st.markdown(f"<div style='background:white; padding:8px; border-left:4px solid #004E8C; margin-bottom:5px; font-size:0.9em;'><b>{d_fmt}</b> - {item['orador']}<br>📖 {item['tema']}</div>", unsafe_allow_html=True)
                if st.button("Remover", key=f"rem_{idx}"):
                    st.session_state['carrinho'].pop(idx); st.rerun()
            st.divider()
            if st.button("🚀 ENVIAR PEDIDO", type="primary"):
                novo = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "solicitante": solicitante,
                    "mes": f"{mes_ref}/{ano}",
                    "data_envio": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "itens": st.session_state['carrinho']
                }
                if "solicitacoes" not in db: db["solicitacoes"] = []
                db['solicitacoes'].append(novo)
                salvar_dados(db)
                st.session_state['carrinho'] = []
                st.success("Enviado!"); st.balloons()
        else: st.caption("Lista vazia.")

# ==========================================
# 5. ÁREA ADMIN (COORDINADOR)
# ==========================================
def area_admin():
    # MARCADOR DE VERSÃO PARA VOCÊ SABER QUE ATUALIZOU
    st.title("🔒 Painel do Coordenador (V 9.0)")
    
    tab1, tab2 = st.tabs(["📩 Pedidos (WhatsApp Completo)", "👥 Gerenciar Oradores"])
    
    # --- ABA PEDIDOS ---
    with tab1:
        if not db['solicitacoes']: 
            st.info("Nenhum pedido na lista.")
        else:
            for solic in reversed(db['solicitacoes']):
                with st.expander(f"📍 {solic['solicitante']} - {solic['mes']}"):
                    # GERAÇÃO DO TEXTO DO WHATSAPP
                    txt_zap = f"*CONFIRMAÇÃO DE DISCURSOS*\n"
                    txt_zap += f"🏛️ *{solic['solicitante']}*\n"
                    txt_zap += f"📅 Ref: {solic['mes']}\n"
                    txt_zap += "----------------------------------\n\n"
                    
                    for item in solic['itens']:
                        dt_fmt = datetime.strptime(item['data'], "%Y-%m-%d").strftime("%d/%m")
                        icone = ICONES.get(item['cargo'], "👤")
                        
                        # Visual no Site
                        st.markdown(f"""
                        <div class="admin-card">
                            <div style="font-size:1.1em; font-weight:bold;">{icone} {item['orador']}</div>
                            <div>🗓️ <b>{dt_fmt}</b></div>
                            <div style="color:#444;">📖 {item['tema']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Texto Zap
                        txt_zap += f"🗓️ *{dt_fmt}* - {icone} {item['orador']}\n"
                        txt_zap += f"📖 {item['tema']}\n\n"
                    
                    txt_zap += "----------------------------------\n"
                    txt_zap += "Att, Coordenação Parque Jataí."

                    st.divider()
                    c1, c2 = st.columns([3, 1])
                    c1.text_area("Copiar Mensagem:", txt_zap, height=250)
                    if c2.button("Excluir Pedido", key=f"del_{solic['id']}", type="primary"):
                        db['solicitacoes'] = [s for s in db['solicitacoes'] if s['id'] != solic['id']]
                        salvar_dados(db)
                        st.rerun()

    # --- ABA ORADORES ---
    with tab2:
        st.subheader("Cadastro de Oradores")
        
        # 1. MOSTRAR TABELA
        if db['oradores']:
            df = pd.DataFrame(db['oradores'])
            # Formata a coluna temas para não ficar gigante visualmente
            df['temas_ids'] = df['temas_ids'].apply(lambda x: str(x).replace('[','').replace(']',''))
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("Nenhum orador cadastrado.")

        st.divider()
        col_add, col_edit = st.columns(2)

        # 2. ADICIONAR NOVO
        with col_add:
            with st.container(border=True):
                st.write("#### ➕ Adicionar Novo")
                with st.form("new_orador"):
                    n_nome = st.text_input("Nome")
                    n_cargo = st.selectbox("Cargo", ["Ancião", "Servo Ministerial", "Outro"])
                    # Pega todos os temas para selecionar
                    all_temas = [f"{t['numero']} - {t['titulo']}" for t in db['temas']]
                    n_temas = st.multiselect("Temas Habilitados", all_temas)
                    
                    if st.form_submit_button("Salvar"):
                        ids = [int(t.split(' - ')[0]) for t in n_temas]
                        db['oradores'].append({"nome": n_nome, "cargo": n_cargo, "temas_ids": ids})
                        salvar_dados(db)
                        st.success("Adicionado!"); st.rerun()

        # 3. EDITAR / EXCLUIR
        with col_edit:
            with st.container(border=True):
                st.write("#### ✏️ Editar / Excluir")
                if db['oradores']:
                    sel_nome = st.selectbox("Selecione:", [o['nome'] for o in db['oradores']])
                    # Acha o índice
                    idx = next(i for i, o in enumerate(db['oradores']) if o['nome'] == sel_nome)
                    dados = db['oradores'][idx]
                    
                    with st.form("edit_orador"):
                        e_nome = st.text_input("Nome", value=dados['nome'])
                        e_cargo = st.selectbox("Cargo", ["Ancião", "Servo Ministerial", "Outro"], index=["Ancião", "Servo Ministerial", "Outro"].index(dados['cargo']))
                        
                        # Temas Atuais
                        all_temas = [f"{t['numero']} - {t['titulo']}" for t in db['temas']]
                        defaults = [f"{t['numero']} - {t['titulo']}" for t in db['temas'] if t['numero'] in dados['temas_ids']]
                        e_temas = st.multiselect("Temas", all_temas, default=defaults)
                        
                        c_up, c_del = st.columns(2)
                        if c_up.form_submit_button("Atualizar"):
                            ids = [int(t.split(' - ')[0]) for t in e_temas]
                            db['oradores'][idx] = {"nome": e_nome, "cargo": e_cargo, "temas_ids": ids}
                            salvar_dados(db)
                            st.success("Salvo!"); st.rerun()
                        
                        if c_del.form_submit_button("Excluir", type="primary"):
                            db['oradores'].pop(idx)
                            salvar_dados(db)
                            st.rerun()
                else:
                    st.info("Nada para editar.")

# ==========================================
# 6. RODAPÉ / LOGIN
# ==========================================
c1, c2 = st.columns([6,1])
with c2:
    if st.session_state['modo_admin']:
        if st.button("Sair"): st.session_state['modo_admin'] = False; st.rerun()
    else:
        if st.button("Admin"): st.session_state['mostrar_login'] = not st.session_state['mostrar_login']

if st.session_state['mostrar_login'] and not st.session_state['modo_admin']:
    if st.text_input("Senha", type="password") == "1234":
        st.session_state['modo_admin'] = True; st.session_state['mostrar_login'] = False; st.rerun()

if st.session_state['modo_admin']: area_admin()
else: area_publica()

st.sidebar.markdown("---")
st.sidebar.info(f"📍 **Salão do Reino:**\n\n{ENDERECO_SALAO}\n\n🕒 **Reunião:** {HORARIO_REUNIAO}")
st.sidebar.markdown(f"<a href='{LINK_MAPS}' target='_blank'><button style='background:#4CAF50;color:white;width:100%;border:none;padding:10px;border-radius:5px;'>🗺️ Ver no Street View</button></a>", unsafe_allow_html=True)
