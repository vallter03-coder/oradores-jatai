import streamlit as st
import json
import locale
from datetime import datetime, date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd # Adicionado para visualizar a tabela de oradores melhor

# ==========================================
# 1. CONFIGURAÇÕES E ENDEREÇO
# ==========================================
ENDERECO_SALAO = "Rua João Vieira Nunes, 284, Parque Jataí, Votorantim/SP - CEP 18117-220"
HORARIO_REUNIAO = "Sábado às 18:30"
LINK_MAPS = "https://maps.app.goo.gl/36kLuQvSyK1norNm6"
NOME_PLANILHA_GOOGLE = "oradores_db"

# Tenta ajustar data para Português
try: locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except: pass

st.set_page_config(page_title="Solicitação de Oradores", layout="wide", page_icon="📝")

# ==========================================
# 2. CONEXÃO E DADOS
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
        
        # Carrega Oradores
        ws_oradores = sh.worksheet("oradores")
        raw_oradores = ws_oradores.get_all_records()
        oradores_fmt = []
        for row in raw_oradores:
            ids = []
            if str(row.get('temas_ids', '')).strip():
                try: ids = [int(x.strip()) for x in str(row['temas_ids']).split(',') if x.strip().isdigit()]
                except: pass
            oradores_fmt.append({"nome": row['nome'], "cargo": row['cargo'], "temas_ids": ids})

        # Carrega Temas e Solicitações
        temas = sh.worksheet("temas").get_all_records()
        
        try: solicitacoes = sh.worksheet("solicitacoes").get_all_records()
        except: solicitacoes = []

        return {"oradores": oradores_fmt, "temas": temas, "solicitacoes": solicitacoes}
    except Exception as e:
        st.error(f"Erro ao conectar: {e}")
        return {"oradores": [], "temas": [], "solicitacoes": []}

def salvar_dados(dados):
    # Salva JSON na célula A1 da primeira aba (Método Rápido de Backup)
    try:
        client = conectar_gsheets()
        sheet = client.open(NOME_PLANILHA_GOOGLE).sheet1
        sheet.update_acell('A1', json.dumps(dados, ensure_ascii=False))
    except: pass

# Inicializa Sessão
if 'db' not in st.session_state: st.session_state['db'] = carregar_dados()
db = st.session_state['db']
if 'carrinho' not in st.session_state: st.session_state['carrinho'] = []
if 'modo_admin' not in st.session_state: st.session_state['modo_admin'] = False
if 'mostrar_login' not in st.session_state: st.session_state['mostrar_login'] = False

# ==========================================
# 3. CSS (VISUAL LIMPO E CARDS)
# ==========================================
st.markdown("""
<style>
    .stApp { background-color: #F4F6F9; color: #333; }
    
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: white; border: 1px solid #E0E0E0; border-radius: 8px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTextInput input, .stSelectbox div, .stDateInput input { background-color: #FFF; border-radius: 4px; }
    div.stButton > button { background-color: #004E8C; color: white; border-radius: 6px; border: none; font-weight: 600; }
    div.stButton > button:hover { background-color: #003366; }
    [data-testid="stSidebar"] { background-color: white; border-right: 1px solid #DDD; }
    h1, h2, h3 { color: #004E8C; font-family: sans-serif; }
    
    /* Estilo do Card de Pedido no Admin */
    .admin-card {
        background-color: #F8F9FA; border-left: 4px solid #004E8C; padding: 10px; margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

ICONES = {"Ancião": "🛡️", "Servo Ministerial": "💼", "Outro": "👤"}
MAPA_MESES = {"Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12}

# ==========================================
# 4. ÁREA PÚBLICA (MANTIDA IGUAL)
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
        st.info("👆 Por favor, preencha Cidade, Congregação e Mês para ver os oradores disponíveis.")
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
                        tema_sel = st.radio("Lista de Temas", opcoes, key=f"r_{i}", label_visibility="collapsed", index=None)
                else:
                    st.warning("Sem temas habilitados.")

                st.write("")
                
                ja_adicionado = any(item['orador'] == orador['nome'] and item['data'] == d_pref.strftime("%Y-%m-%d") for item in st.session_state['carrinho'])
                
                if ja_adicionado:
                    st.success("✅ Adicionado!")
                else:
                    if st.button("Confirmar", key=f"btn_{i}", use_container_width=True):
                        if tema_sel:
                            st.session_state['carrinho'].append({
                                "orador": orador['nome'],
                                "cargo": orador['cargo'],
                                "tema": tema_sel,
                                "data": d_pref.strftime("%Y-%m-%d")
                            })
                            st.rerun()
                        else:
                            st.error("Escolha um tema!")

    with st.sidebar:
        st.header("📋 Resumo do Pedido")
        st.info(f"Mês: {mes_ref}/{ano}")
        st.write(f"🏠 **{solicitante}**")
        st.divider()
        
        if st.session_state['carrinho']:
            for idx, item in enumerate(st.session_state['carrinho']):
                d_fmt = datetime.strptime(item['data'], '%Y-%m-%d').strftime('%d/%m')
                st.markdown(f"""
                <div style="background:white; padding:8px; border-radius:5px; border-left:4px solid #004E8C; margin-bottom:5px; font-size:0.9em; box-shadow:0 1px 2px rgba(0,0,0,0.1);">
                    <b>{d_fmt}</b> - {item['orador']}<br>
                    <span style="color:#555">📖 {item['tema']}</span>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Remover", key=f"rem_{idx}", use_container_width=True):
                    st.session_state['carrinho'].pop(idx)
                    st.rerun()
            
            st.divider()
            if st.button("🚀 ENVIAR SOLICITAÇÃO", type="primary", use_container_width=True):
                novo_pedido = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "solicitante": solicitante,
                    "mes": f"{mes_ref}/{ano}",
                    "data_envio": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "itens": st.session_state['carrinho']
                }
                if "solicitacoes" not in db: db["solicitacoes"] = []
                db['solicitacoes'].append(novo_pedido)
                salvar_dados(db) 
                st.session_state['carrinho'] = []
                st.success("Solicitação enviada!")
                st.balloons()
        else:
            st.caption("Sua lista está vazia.")

# ==========================================
# 5. ÁREA ADMIN (ATUALIZADA)
# ==========================================
def area_admin():
    st.title("🔒 Painel do Coordenador")
    tab1, tab2 = st.tabs(["📩 Pedidos Recebidos", "👥 Gerenciar Oradores"])
    
    # --- ABA 1: PEDIDOS ---
    with tab1:
        if not db['solicitacoes']: 
            st.info("Nenhuma solicitação nova.")
        else:
            for solic in reversed(db['solicitacoes']):
                with st.expander(f"📌 {solic['solicitante']} - {solic['mes']}"):
                    # Cabeçalho da mensagem do WhatsApp
                    texto_zap = f"*PEDIDO DE ORADORES*\n"
                    texto_zap += f"🏛️ *{solic['solicitante']}*\n"
                    texto_zap += f"📅 Ref: {solic['mes']}\n\n"
                    
                    st.markdown(f"**Enviado em:** {solic['data_envio']}")
                    
                    for item in solic['itens']:
                        dt_obj = datetime.strptime(item['data'], "%Y-%m-%d")
                        data_fmt = dt_obj.strftime("%d/%m")
                        icone = ICONES.get(item['cargo'], "👤")
                        
                        # Mostra Card
                        st.markdown(f"""
                        <div class="admin-card">
                            <div>🗓️ <b>{data_fmt}</b> - {icone} {item['orador']}</div>
                            <div style="font-style:italic; color:#555;">📖 {item['tema']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Adiciona ao texto do Zap (Com ícone e tema completo)
                        texto_zap += f"{icone} *{data_fmt}* - {item['orador']}\n"
                        texto_zap += f"📖 {item['tema']}\n\n"
                    
                    texto_zap += "Att, Coordenação."
                    
                    st.divider()
                    c1, c2 = st.columns([3, 1])
                    c1.text_area("Copiar para WhatsApp:", texto_zap, height=200)
                    
                    with c2:
                        st.write("")
                        st.write("")
                        if st.button("🗑️ Excluir", key=f"del_{solic['id']}", type="primary", use_container_width=True):
                            db['solicitacoes'] = [s for s in db['solicitacoes'] if s['id'] != solic['id']]
                            salvar_dados(db)
                            st.rerun()

    # --- ABA 2: ORADORES (CRUD COMPLETO) ---
    with tab2:
        st.subheader("Cadastro de Oradores")
        
        # VISUALIZAÇÃO EM TABELA
        if db['oradores']:
            df_show = pd.DataFrame(db['oradores'])
            # Simplifica visualização dos temas
            df_show['temas_ids'] = df_show['temas_ids'].apply(lambda x: f"{len(x)} temas" if isinstance(x, list) else "0")
            st.dataframe(df_show, use_container_width=True, hide_index=True)
        else:
            st.info("Lista vazia.")

        st.divider()
        
        # CONTROLES DE ADICIONAR / EDITAR
        acao = st.radio("Ação:", ["➕ Adicionar Novo", "✏️ Editar Existente"], horizontal=True)
        
        if acao == "➕ Adicionar Novo":
            with st.form("add_orador_form"):
                nome_novo = st.text_input("Nome Completo")
                cargo_novo = st.selectbox("Cargo", ["Ancião", "Servo Ministerial", "Outro"])
                
                # Multiselect para Temas
                opcoes_temas = [f"{t['numero']} - {t['titulo']}" for t in db['temas']]
                temas_sel = st.multiselect("Temas Habilitados", opcoes_temas)
                
                if st.form_submit_button("Salvar Novo Orador"):
                    if nome_novo:
                        # Extrai IDs dos temas selecionados
                        ids = [int(t.split(' - ')[0]) for t in temas_sel]
                        db['oradores'].append({
                            "nome": nome_novo,
                            "cargo": cargo_novo,
                            "temas_ids": ids
                        })
                        salvar_dados(db)
                        st.success(f"{nome_novo} adicionado!")
                        st.rerun()
                    else:
                        st.error("Digite o nome.")
                        
        elif acao == "✏️ Editar Existente":
            if not db['oradores']:
                st.warning("Nenhum orador para editar.")
            else:
                lista_nomes = [o['nome'] for o in db['oradores']]
                sel_nome = st.selectbox("Selecione o Orador:", lista_nomes)
                
                # Acha o índice do orador
                idx = next(i for i, o in enumerate(db['oradores']) if o['nome'] == sel_nome)
                dados_atuais = db['oradores'][idx]
                
                with st.form("edit_orador_form"):
                    nome_edit = st.text_input("Nome", value=dados_atuais['nome'])
                    
                    idx_cargo = ["Ancião", "Servo Ministerial", "Outro"].index(dados_atuais.get('cargo', 'Outro'))
                    cargo_edit = st.selectbox("Cargo", ["Ancião", "Servo Ministerial", "Outro"], index=idx_cargo)
                    
                    # Prepara temas pré-selecionados
                    opcoes_temas = [f"{t['numero']} - {t['titulo']}" for t in db['temas']]
                    default_temas = [f"{t['numero']} - {t['titulo']}" for t in db['temas'] if t['numero'] in dados_atuais.get('temas_ids', [])]
                    
                    temas_edit = st.multiselect("Temas Habilitados", opcoes_temas, default=default_temas)
                    
                    c_save, c_del = st.columns([2, 1])
                    save_btn = c_save.form_submit_button("🔄 Atualizar")
                    del_btn = c_del.form_submit_button("🗑️ Excluir Orador", type="primary")
                    
                    if save_btn:
                        ids_novos = [int(t.split(' - ')[0]) for t in temas_edit]
                        db['oradores'][idx]['nome'] = nome_edit
                        db['oradores'][idx]['cargo'] = cargo_edit
                        db['oradores'][idx]['temas_ids'] = ids_novos
                        salvar_dados(db)
                        st.success("Atualizado!")
                        st.rerun()
                        
                    if del_btn:
                        db['oradores'].pop(idx)
                        salvar_dados(db)
                        st.warning("Orador excluído.")
                        st.rerun()

# ==========================================
# 6. CONTROLE DE TELA
# ==========================================
col_h1, col_h2 = st.columns([6, 1])
with col_h2:
    if st.session_state['modo_admin']:
        if st.button("Sair"): 
            st.session_state['modo_admin'] = False
            st.rerun()
    else:
        if st.button("Admin"): 
            st.session_state['mostrar_login'] = not st.session_state['mostrar_login']

if st.session_state['mostrar_login'] and not st.session_state['modo_admin']:
    if st.text_input("Senha", type="password") == "1234":
        st.session_state['modo_admin'] = True
        st.session_state['mostrar_login'] = False
        st.rerun()

if st.session_state['modo_admin']: area_admin()
else: area_publica()

# SIDEBAR FIXA
st.sidebar.markdown("---")
st.sidebar.info(f"📍 **Salão do Reino:**\n\n{ENDERECO_SALAO}\n\n🕒 **Reunião:** {HORARIO_REUNIAO}")
st.sidebar.markdown(f"""
    <a href="{LINK_MAPS}" target="_blank" style="text-decoration:none;">
        <div style="background:#4CAF50; color:white; padding:10px; border-radius:5px; text-align:center; font-weight:bold;">
            🗺️ Ver no Street View
        </div>
    </a>
""", unsafe_allow_html=True)
