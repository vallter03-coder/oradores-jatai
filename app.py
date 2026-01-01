import streamlit as st
import json
import locale
from datetime import datetime, date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import time
# BIBLIOTECA PARA O BOTÃO DE COPIAR
from st_copy_to_clipboard import st_copy_to_clipboard

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
# 2. CONEXÃO
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
    return gspread.authorize(creds)

def carregar_dados():
    try:
        client = conectar_gsheets()
        sh = client.open(NOME_PLANILHA_GOOGLE)
        
        # --- ORADORES ---
        try: ws_oradores = sh.worksheet("oradores"); dados_or = ws_oradores.get_all_records()
        except: dados_or = []
        lista_oradores = []
        for row in dados_or:
            r = {k.lower().strip(): v for k, v in row.items()}
            if 'nome' not in r or not r['nome'] or str(r['nome']).startswith('{'): continue
            ids = []
            if str(r.get('temas_ids', '')).strip():
                try: ids = [int(x.strip()) for x in str(r['temas_ids']).split(',') if x.strip().isdigit()]
                except: pass
            lista_oradores.append({"nome": r['nome'], "cargo": r.get('cargo',''), "temas_ids": ids})

        # --- OUTROS ---
        try: temas = sh.worksheet("temas").get_all_records()
        except: temas = []
        try: historico = sh.worksheet("historico").get_all_records()
        except: historico = []
        
        # --- BLOQUEIOS ---
        try: 
            bloqueios = sh.worksheet("bloqueios").get_all_records()
        except: 
            bloqueios = []

        # --- SOLICITAÇÕES ---
        lista_solicitacoes = []
        try:
            ws_sol = sh.worksheet("solicitacoes")
            rows = ws_sol.get_all_values()
            if len(rows) > 1:
                for i in range(1, len(rows)):
                    try:
                        json_str = rows[i][1]
                        lista_solicitacoes.append(json.loads(json_str))
                    except: pass
        except: pass

        return {"oradores": lista_oradores, "temas": temas, "solicitacoes": lista_solicitacoes, "historico": historico, "bloqueios": bloqueios}
    except Exception as e:
        return {"oradores": [], "temas": [], "solicitacoes": [], "historico": [], "bloqueios": []}

# ==========================================
# 3. FUNÇÕES DE ESCRITA (SEGURAS)
# ==========================================

def adicionar_orador_safe(novo_orador):
    try:
        client = conectar_gsheets()
        ws = client.open(NOME_PLANILHA_GOOGLE).worksheet("oradores")
        ids_str = str(novo_orador['temas_ids']).replace('[','').replace(']','')
        ws.append_row([novo_orador['nome'], novo_orador['cargo'], ids_str])
        return True
    except: return False

def atualizar_orador_safe(nome_antigo, dados_novos):
    try:
        client = conectar_gsheets()
        ws = client.open(NOME_PLANILHA_GOOGLE).worksheet("oradores")
        cell = ws.find(nome_antigo)
        if cell:
            ids_str = str(dados_novos['temas_ids']).replace('[','').replace(']','')
            ws.update_cell(cell.row, 1, dados_novos['nome'])
            ws.update_cell(cell.row, 2, dados_novos['cargo'])
            ws.update_cell(cell.row, 3, ids_str)
            return True
    except: return False

def excluir_orador_safe(nome):
    try:
        client = conectar_gsheets()
        ws = client.open(NOME_PLANILHA_GOOGLE).worksheet("oradores")
        cell = ws.find(nome)
        if cell and cell.row > 1: ws.delete_rows(cell.row); return True
    except: return False

def salvar_solicitacao_safe(nova_solic):
    try:
        client = conectar_gsheets()
        try: ws = client.open(NOME_PLANILHA_GOOGLE).worksheet("solicitacoes")
        except: ws = client.open(NOME_PLANILHA_GOOGLE).add_worksheet("solicitacoes", 100, 2); ws.append_row(["id", "json_data"])
        ws.append_row([nova_solic['id'], json.dumps(nova_solic, ensure_ascii=False)])
    except: pass

def salvar_historico_safe(novo_hist):
    try:
        client = conectar_gsheets()
        try: ws = client.open(NOME_PLANILHA_GOOGLE).worksheet("historico")
        except: ws = client.open(NOME_PLANILHA_GOOGLE).add_worksheet("historico", 1000, 3)
        ws.append_row([novo_hist['tema_numero'], novo_hist['tema_titulo'], novo_hist['data']])
    except: pass

def excluir_pedido_safe(id_ped):
    try:
        client = conectar_gsheets()
        ws = client.open(NOME_PLANILHA_GOOGLE).worksheet("solicitacoes")
        cell = ws.find(str(id_ped))
        if cell: ws.delete_rows(cell.row)
    except: pass

def salvar_bloqueio_safe(tema_nome):
    try:
        client = conectar_gsheets()
        try: ws = client.open(NOME_PLANILHA_GOOGLE).worksheet("bloqueios")
        except: ws = client.open(NOME_PLANILHA_GOOGLE).add_worksheet("bloqueios", 100, 2); ws.append_row(["tema", "data"])
        ws.append_row([tema_nome, datetime.now().strftime("%Y-%m-%d")])
    except: pass

def remover_bloqueio_safe(tema_nome):
    try:
        client = conectar_gsheets()
        ws = client.open(NOME_PLANILHA_GOOGLE).worksheet("bloqueios")
        cell = ws.find(tema_nome)
        if cell: ws.delete_rows(cell.row)
    except: pass

# Sessão
if 'db' not in st.session_state: st.session_state['db'] = carregar_dados()
db = st.session_state['db']
if 'carrinho' not in st.session_state: st.session_state['carrinho'] = []
if 'modo_admin' not in st.session_state: st.session_state['modo_admin'] = False
if 'mostrar_login' not in st.session_state: st.session_state['mostrar_login'] = False

# ==========================================
# 4. ESTILO DARK MODE + FIX MOBILE SCROLL
# ==========================================
st.markdown("""
<style>
    :root { --primary: #5D9CEC; --bg: #0E1117; --sec-bg: #262730; --text: #FAFAFA; }
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    div[data-testid="stVerticalBlockBorderWrapper"] { background-color: #262730; border: 1px solid #4A4A4A; border-radius: 8px; padding: 15px; }
    
    /* INPUTS */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stDateInput input, .stNumberInput input { color: white !important; background-color: #262730 !important; border: 1px solid #4A4A4A !important; }
    
    /* DROPDOWN MENU FIX - MOBILE SCROLL */
    div[data-baseweb="menu"] { 
        background-color: #262730 !important; 
        color: white !important;
        max-height: 300px !important; 
        overflow-y: auto !important;
        -webkit-overflow-scrolling: touch !important; /* Importante para iPhone/Android */
    }
    div[data-baseweb="popover"], div[role="listbox"] { background-color: #262730 !important; color: white !important; }

    div.stButton > button { background-color: #004E8C; color: white; border: none; border-radius: 6px; font-weight: bold; }
    h1, h2, h3, h4, p, li, label, div { color: #E0E0E0; }
    
    .info-box { background-color: #1C1E26; border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 20px; font-size: 0.9em; }
    .map-btn { display: inline-block; background-color: #4CAF50; color: white !important; padding: 5px 15px; border-radius: 4px; text-decoration: none; font-weight: bold; margin-top: 5px; }
    
    .hist-alert { padding: 10px; border-radius: 5px; margin-top: 10px; font-weight: bold; }
    .hist-ok { background-color: #155724; color: #d4edda; border: 1px solid #155724; }
    .hist-warning { background-color: #856404; color: #fff3cd; border: 1px solid #856404; }
    .admin-card { background-color: #323542; padding: 10px; border-left: 4px solid #5D9CEC; margin-bottom: 5px; border-radius: 4px; }
    
    /* Botão Link */
    a[data-testid="stLinkButton"] { background-color: #4CAF50 !important; color: white !important; border:none !important; font-weight:bold; }
    
    /* Bloco Vermelho para Bloqueios */
    .block-card { background-color: #3e1212; border: 1px solid #8a2be2; border-left: 5px solid #ff4444; padding: 10px; margin-bottom: 5px; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

ICONES = {"Ancião": "🛡️", "Servo Ministerial": "💼", "Outro": "👤"}
MAPA_MESES = {"Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12}

# ==========================================
# 5. ÁREA PÚBLICA
# ==========================================
def area_publica():
    # --- CABEÇALHO ---
    with st.container(border=True):
        st.markdown(f"""
        <div style="font-size:1.1em; font-weight:bold; color:#5D9CEC;">📍 Congregação Parque Jataí</div>
        <div style="font-size:0.9em; margin-bottom:5px;">{ENDERECO_SALAO}</div>
        <div style="font-size:0.9em; margin-bottom:10px;">🕒 <b>Reunião:</b> {HORARIO_REUNIAO}</div>
        """, unsafe_allow_html=True)
        
        # Colunas ajustadas para o botão aparecer bem
        col_btn, col_copy = st.columns(2)
        with col_btn:
            st.link_button("🗺️ Abrir Mapa", LINK_MAPS, use_container_width=True)
        
        with col_copy:
            # TEXTO FORMATADO PARA O WHATSAPP
            mensagem_zap = f"""🏛️ *Salão do Reino - Cong. Parque Jataí*
📍 {ENDERECO_SALAO}

🕒 *Reunião:* {HORARIO_REUNIAO}
🗺️ *Localização:* {LINK_MAPS}"""
            
            # Botão de Copiar (Sem mostrar o texto na tela)
            st_copy_to_clipboard(mensagem_zap, "📋 Copiar Convite")
    
    st.title("Solicitação de Oradores")

    with st.container(border=True):
        st.caption("📍 **Identificação da Congregação**")
        c1, c2 = st.columns(2)
        cidade = c1.text_input("Sua Cidade:")
        congregacao = c2.text_input("Sua Congregação:")
        mes_ref = st.selectbox("Mês Pretendido:", ["Selecione..."] + list(MAPA_MESES.keys()))

    if not cidade or not congregacao or mes_ref == "Selecione...":
        st.info("👆 Preencha os dados acima para ver os oradores.")
        return

    solicitante = f"{cidade} - {congregacao}"
    hoje = date.today()
    mes_num = MAPA_MESES[mes_ref]
    ano = hoje.year + 1 if mes_num < hoje.month else hoje.year
    data_padrao = date(ano, mes_num, 1)

    if st.session_state['carrinho']:
        st.markdown("---")
        with st.container(border=True):
            st.markdown(f"#### 📋 Seu Pedido ({len(st.session_state['carrinho'])} oradores)")
            for idx, item in enumerate(st.session_state['carrinho']):
                d_fmt = datetime.strptime(item['data'], '%Y-%m-%d').strftime('%d/%m')
                c_txt, c_btn = st.columns([4, 1])
                c_txt.markdown(f"**{d_fmt}** - {item['orador']}<br><span style='color:#AAA; font-size:0.9em'>{item['tema']}</span>", unsafe_allow_html=True)
                if c_btn.button("❌", key=f"del_top_{idx}"):
                    st.session_state['carrinho'].pop(idx); st.rerun()
            st.write("")
            if st.button("🚀 ENVIAR PEDIDO AGORA", type="primary", use_container_width=True):
                novo = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "solicitante": solicitante,
                    "mes": f"{mes_ref}/{ano}",
                    "data_envio": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "itens": st.session_state['carrinho']
                }
                if "solicitacoes" not in db: db["solicitacoes"] = []
                db['solicitacoes'].append(novo)
                salvar_solicitacao_safe(novo)
                st.session_state['carrinho'] = []
                st.success("Pedido Enviado com Sucesso!"); st.balloons()
        st.markdown("---")
    
    # VISUALIZAÇÃO DE BLOQUEIOS (CORRIGIDO PARA EXIBIR)
    if db.get('bloqueios'):
        st.divider()
        st.subheader("🚫 Temas Bloqueados / Recentes")
        st.write("Estes temas **não devem ser solicitados** pois já foram designados recentemente:")
        
        for b in db['bloqueios']:
            tema_nome = b.get('tema', '')
            st.warning(f"🔒 {tema_nome}")
        st.divider()

    if not db['oradores']:
        st.warning("Nenhum orador cadastrado.")
        return

    st.subheader("🗣️ Escolha os Oradores")
    cols = st.columns(3)
    
    for i, orador in enumerate(db['oradores']):
        with cols[i % 3]:
            with st.container(border=True):
                icone = ICONES.get(orador['cargo'], "👤")
                st.markdown(f"""<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;"><div style="font-weight:bold; font-size:1.1rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{icone} {orador['nome']}</div><div style="font-size:0.8rem; color:#aaa; white-space:nowrap; margin-left:5px;">{orador['cargo']}</div></div>""", unsafe_allow_html=True)
                d_pref = st.date_input("Data", value=data_padrao, min_value=hoje, format="DD/MM/YYYY", key=f"d_{i}", label_visibility="collapsed")
                temas_ids = orador.get('temas_ids', [])
                tema_sel = None
                if temas_ids:
                    st.markdown("<div style='margin-top:8px; font-size:0.9em; font-weight:bold;'>📖 Escolha o Tema:</div>", unsafe_allow_html=True)
                    lista_t = [t for t in db['temas'] if t['numero'] in temas_ids]
                    lista_t.sort(key=lambda x: x['numero'])
                    opcoes = [f"{t['numero']} - {t['titulo']}" for t in lista_t]
                    with st.container(height=150):
                        tema_sel = st.radio("Temas", opcoes, key=f"r_{i}", label_visibility="collapsed", index=None)
                else: st.warning("Sem temas.")
                st.write("")
                if st.button("Adicionar ao Pedido", key=f"btn_{i}", use_container_width=True):
                    if tema_sel:
                        st.session_state['carrinho'].append({"orador": orador['nome'], "cargo": orador['cargo'], "tema": tema_sel, "data": d_pref.strftime("%Y-%m-%d")})
                        st.toast(f"{orador['nome']} adicionado!", icon="✅"); st.rerun()
                    else: st.error("Escolha um tema!")

# ==========================================
# 6. ÁREA ADMIN
# ==========================================
def area_admin():
    st.title("🔒 Painel de Controle")
    tab1, tab2, tab3 = st.tabs(["📩 Pedidos", "📜 Histórico/Bloqueios", "👥 Gerenciar Oradores"])
    
    # --- PEDIDOS ---
    with tab1:
        if not db['solicitacoes']: 
            st.info("Nenhum pedido na lista.")
        else:
            for solic in reversed(db['solicitacoes']):
                with st.expander(f"📍 {solic.get('solicitante', '?')} - {solic.get('mes', '?')}"):
                    txt_zap = f"*CONFIRMAÇÃO DE DISCURSOS*\n"
                    txt_zap += f"🏛️ *{solic.get('solicitante')}*\n"
                    txt_zap += f"📅 Ref: {solic.get('mes')}\n"
                    txt_zap += "----------------------------------\n\n"
                    for item in solic.get('itens', []):
                        dt_fmt = datetime.strptime(item['data'], "%Y-%m-%d").strftime("%d/%m")
                        icone = ICONES.get(item['cargo'], "👤")
                        st.markdown(f"""<div class="admin-card"><div style="font-size:1.1em; font-weight:bold;">{icone} {item['orador']}</div><div>🗓️ <b>{dt_fmt}</b></div><div style="opacity:0.8">📖 {item['tema']}</div></div>""", unsafe_allow_html=True)
                        txt_zap += f"🗓️ *{dt_fmt}* - {icone} {item['orador']}\n📖 {item['tema']}\n\n"
                    txt_zap += "----------------------------------\nAtt, Ricardo Rosa - Parque Jataí."
                    
                    st.divider()
                    st.caption("Texto para WhatsApp:")
                    st_copy_to_clipboard(txt_zap, "📋 Copiar Confirmação")
                        
                    if st.button("🗑️ Excluir Pedido", key=f"del_{solic['id']}", type="primary", use_container_width=True):
                        db['solicitacoes'] = [s for s in db['solicitacoes'] if s['id'] != solic['id']]
                        excluir_pedido_safe(solic['id'])
                        st.rerun()

    # --- HISTÓRICO E BLOQUEIOS ---
    with tab2:
        # Seção 1: BLOQUEIOS
        st.subheader("🚫 Temas a Não Escolher (Bloqueados)")
        st.caption("Adicione aqui temas que não devem ser feitos (ex: feitos recentemente).")
        
        with st.container(border=True):
            # Form para adicionar
            todos_temas = [f"{t['numero']} - {t['titulo']}" for t in db['temas']]
            novo_bloqueio = st.selectbox("Selecione o tema para bloquear:", ["-- Selecione --"] + todos_temas)
            
            if st.button("Bloquear Tema", use_container_width=True):
                if novo_bloqueio != "-- Selecione --":
                    db['bloqueios'].append({"tema": novo_bloqueio, "data": str(date.today())})
                    salvar_bloqueio_safe(novo_bloqueio)
                    st.success("Bloqueado!"); st.rerun()
            
            st.divider()
            st.write("##### 📋 Lista de Bloqueios Ativos")
            if db['bloqueios']:
                # Iterar sobre uma cópia da lista para não dar erro ao remover
                for b in list(db['bloqueios']):
                    c_txt, c_btn = st.columns([4, 1])
                    c_txt.markdown(f"<div class='block-card'>🚫 {b['tema']}</div>", unsafe_allow_html=True)
                    if c_btn.button("X", key=f"rm_b_{b['tema']}"):
                        # 1. Remove do Banco de Dados
                        remover_bloqueio_safe(b['tema'])
                        # 2. Remove da Memória do Site (CORREÇÃO AQUI)
                        db['bloqueios'] = [x for x in db['bloqueios'] if x['tema'] != b['tema']]
                        # 3. Recarrega a tela
                        st.rerun()
            else:
                st.info("Nenhum tema bloqueado no momento.")

        st.divider()
        
        # Seção 2: HISTÓRICO NORMAL
        st.subheader("📜 Histórico de Realizações")
        c_busca, c_reg = st.columns([1, 1.5], gap="large")
        with c_busca:
            st.info("🔍 **Pesquisar Tema**")
            num_busca = st.number_input("Nº do Tema:", min_value=1, step=1)
            if num_busca:
                encontrados = [h for h in db['historico'] if int(h['tema_numero']) == num_busca]
                if encontrados:
                    recente = max(encontrados, key=lambda x: datetime.strptime(x['data'], "%Y-%m-%d"))
                    d_rec = datetime.strptime(recente['data'], "%Y-%m-%d").strftime("%d/%m/%Y")
                    st.markdown(f"<div class='hist-alert hist-warning'>⚠️ ÚLTIMA VEZ: {d_rec}<br><small>{recente['tema_titulo']}</small></div>", unsafe_allow_html=True)
                else: st.markdown("<div class='hist-alert hist-ok'>✅ Nunca registrado.</div>", unsafe_allow_html=True)
        with c_reg:
            with st.container(border=True):
                st.write("#### ➕ Registrar Realização")
                tema_hist = st.selectbox("Tema:", [f"{t['numero']} - {t['titulo']}" for t in db['temas']])
                data_hist = st.date_input("Data:", format="DD/MM/YYYY")
                if st.button("💾 Salvar Histórico", use_container_width=True):
                    num_t = int(tema_hist.split(' - ')[0])
                    tit_t = tema_hist.split(' - ')[1] if ' - ' in tema_hist else tema_hist
                    data_str = data_hist.strftime("%Y-%m-%d")
                    item_h = {"tema_numero": num_t, "tema_titulo": tit_t, "data": data_str}
                    db['historico'].append(item_h)
                    salvar_historico_safe(item_h)
                    anteriores = [h for h in db['historico'] if int(h['tema_numero']) == num_t]
                    if len(anteriores) > 1: st.warning("Salvo! (Já tinha registro anterior)")
                    else: st.success("Salvo! Primeira vez deste tema.")
        with st.expander("Ver Tabela Completa"):
            if db['historico']:
                df_hist = pd.DataFrame(db['historico'])
                df_hist['data'] = pd.to_datetime(df_hist['data'])
                st.dataframe(df_hist.sort_values(by='data', ascending=False), use_container_width=True)
            else: st.caption("Vazio.")

    with tab3:
        st.subheader("Gerenciar Oradores")
        if db['oradores']:
            df = pd.DataFrame(db['oradores'])
            df['temas_ids'] = df['temas_ids'].apply(lambda x: str(x).replace('[','').replace(']',''))
            st.dataframe(df, use_container_width=True)
        else: st.warning("Nenhum orador.")
        st.divider()
        opcao = st.radio("O que deseja fazer?", ["➕ Adicionar Novo Orador", "✏️ Editar/Excluir Existente"], horizontal=True)
        if opcao == "➕ Adicionar Novo Orador":
            with st.container(border=True):
                with st.form("new_or"):
                    c1, c2 = st.columns(2)
                    n_nome = c1.text_input("Nome Completo")
                    n_cargo = c2.selectbox("Cargo", ["Ancião", "Servo Ministerial", "Outro"])
                    all_temas = [f"{t['numero']} - {t['titulo']}" for t in db['temas']]
                    n_temas = st.multiselect("Selecione os Temas Habilitados:", all_temas)
                    if st.form_submit_button("💾 Salvar Novo Orador"):
                        ids = [int(t.split(' - ')[0]) for t in n_temas]
                        novo_obj = {"nome": n_nome, "cargo": n_cargo, "temas_ids": ids}
                        db['oradores'].append(novo_obj)
                        adicionar_orador_safe(novo_obj)
                        st.success("Salvo!"); time.sleep(1); st.rerun()
        elif opcao == "✏️ Editar/Excluir Existente":
            with st.container(border=True):
                if not db['oradores']:
                    st.info("Nada para editar.")
                else:
                    lista_nomes = [o['nome'] for o in db['oradores']]
                    sel_nome = st.selectbox("Selecione o Orador para Editar:", lista_nomes)
                    idx = next(i for i, o in enumerate(db['oradores']) if o['nome'] == sel_nome)
                    dados = db['oradores'][idx]
                    with st.form("edit_form"):
                        c1, c2 = st.columns(2)
                        e_nome = c1.text_input("Nome", value=dados['nome'])
                        idx_c = ["Ancião", "Servo Ministerial", "Outro"].index(dados['cargo']) if dados['cargo'] in ["Ancião", "Servo Ministerial", "Outro"] else 0
                        e_cargo = c2.selectbox("Cargo", ["Ancião", "Servo Ministerial", "Outro"], index=idx_c)
                        all_temas = [f"{t['numero']} - {t['titulo']}" for t in db['temas']]
                        def_temas = [f"{t['numero']} - {t['titulo']}" for t in db['temas'] if t['numero'] in dados['temas_ids']]
                        e_temas = st.multiselect("Temas Habilitados:", all_temas, default=def_temas)
                        col_save, col_del = st.columns([3, 1])
                        if col_save.form_submit_button("🔄 Atualizar Dados"):
                            ids = [int(t.split(' - ')[0]) for t in e_temas]
                            novos_dados = {"nome": e_nome, "cargo": e_cargo, "temas_ids": ids}
                            db['oradores'][idx] = novos_dados
                            atualizar_orador_safe(dados['nome'], novos_dados)
                            st.success("Dados Atualizados!"); time.sleep(1); st.rerun()
                        if col_del.form_submit_button("🗑️ Excluir Orador", type="primary"):
                            excluir_orador_safe(dados['nome'])
                            db['oradores'].pop(idx)
                            st.rerun()

# ==========================================
# 7. RODAPÉ / LOGIN
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
