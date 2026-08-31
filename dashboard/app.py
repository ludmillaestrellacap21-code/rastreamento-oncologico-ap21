from pathlib import Path
import os
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

# =========================================================
# CONFIGURAÇÃO
# =========================================================
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

def get_setting(nome, padrao=""):
    """Lê primeiro variável de ambiente (.env/local) e depois Streamlit Secrets (cloud)."""
    valor = os.getenv(nome)
    if valor:
        return valor

    try:
        return st.secrets.get(nome, padrao)
    except Exception:
        return padrao


SUPABASE_URL = get_setting("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = get_setting("SUPABASE_PUBLISHABLE_KEY")
APP_URL_CONFIG = get_setting(
    "APP_URL",
    "https://rastreamento-oncologico-ap21.streamlit.app",
)

st.set_page_config(
    page_title="Rastreamento Oncológico | CAP 2.1",
    page_icon="🎗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

RIO_BLUE = "#005CA9"
RIO_BLUE_2 = "#0072CE"
RIO_NAVY = "#17365D"
RIO_LIGHT = "#EAF3F9"
RIO_BG = "#F5F7F9"
RIO_BORDER = "#D9E2E8"
RIO_TEXT = "#243746"
RIO_MUTED = "#667985"

STATUS_COLORS = {
    "Em dia": "#2E7D32",
    "Em atraso": "#F39C12",
    "Agendado": "#1976D2",
    "Falta - Reconvocar": "#C62828",
    "Nunca realizado": "#7A8691",
    "Realizado/Confirmado": "#2E7D32",
}

st.markdown(
    f"""
    <style>
    .stApp {{ background: {RIO_BG}; color: {RIO_TEXT}; }}
    [data-testid="stHeader"] {{
        background: rgba(255,255,255,.96);
        border-bottom: 1px solid {RIO_BORDER};
    }}
    [data-testid="stSidebar"] {{
        background: white;
        border-right: 1px solid {RIO_BORDER};
    }}
    .rio-topbar {{
        background: linear-gradient(90deg, {RIO_NAVY}, {RIO_BLUE} 65%, {RIO_BLUE_2});
        border-radius: 12px;
        padding: 18px 24px;
        margin-bottom: 14px;
        color: white;
        box-shadow: 0 3px 12px rgba(23,54,93,.12);
    }}
    .rio-title {{
        font-size: 1.72rem;
        font-weight: 750;
        line-height: 1.15;
        margin: 0;
    }}
    .rio-subtitle {{
        font-size: .92rem;
        margin-top: 6px;
        opacity: .92;
    }}
    .section-title {{
        font-size: 1.15rem;
        font-weight: 700;
        color: {RIO_NAVY};
        margin: 10px 0 4px 0;
    }}
    .section-note {{
        font-size: .84rem;
        color: {RIO_MUTED};
        margin-bottom: 12px;
    }}
    [data-testid="stMetric"] {{
        background: white;
        border: 1px solid {RIO_BORDER};
        border-radius: 10px;
        padding: 12px 14px;
        box-shadow: 0 1px 4px rgba(0,0,0,.035);
    }}
    [data-testid="stMetricValue"] {{
        color: {RIO_NAVY};
        font-weight: 750;
    }}
    div[data-baseweb="tab-list"] {{
        gap: 4px;
        background: white;
        border: 1px solid {RIO_BORDER};
        padding: 4px;
        border-radius: 10px;
    }}
    button[data-baseweb="tab"] {{
        font-weight: 650;
        border-radius: 7px;
    }}
    .login-box {{
        max-width: 520px;
        margin: 55px auto 0 auto;
    }}

    div.stButton > button[kind="primary"],
    div[data-testid="stLinkButton"] a {{
        background: #005CA9 !important;
        color: white !important;
        border-color: #005CA9 !important;
    }}

    div.stButton > button[kind="primary"]:hover,
    div[data-testid="stLinkButton"] a:hover {{
        background: #004A87 !important;
        color: white !important;
        border-color: #004A87 !important;
    }}
    .metric-card {{
        background: white;
        border: 1px solid #D9E2E8;
        border-left: 6px solid #8A9BA8;
        border-radius: 10px;
        padding: 14px 14px 12px 14px;
        min-height: 108px;
        box-shadow: 0 1px 4px rgba(0,0,0,.035);
    }}

    .metric-card.neutral {{
        border-left-color: #5B7083;
        background: #FFFFFF;
    }}

    .metric-card.success {{
        border-left-color: #2E7D32;
        background: #F1F8F2;
    }}

    .metric-card.warning {{
        border-left-color: #F39C12;
        background: #FFF8E8;
    }}

    .metric-card.info {{
        border-left-color: #1976D2;
        background: #EEF5FC;
    }}

    .metric-card.danger {{
        border-left-color: #C62828;
        background: #FDEEEE;
    }}

    .metric-label {{
        color: #667985;
        font-size: .80rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 6px;
    }}

    .metric-value {{
        color: #17365D;
        font-size: 1.70rem;
        font-weight: 800;
        line-height: 1.05;
    }}

    .metric-percent {{
        margin-top: 7px;
        font-size: .86rem;
        font-weight: 750;
        color: #405565;
    }}

    footer {{ visibility: hidden; }}
    </style>
    """,
    unsafe_allow_html=True,
)

if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
    st.error("Configure SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY no arquivo .env.")
    st.stop()


@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)


sb = get_supabase()

if "session" not in st.session_state:
    st.session_state.session = None

# =========================================================
# CALLBACK GOOGLE OAUTH
# =========================================================
if st.session_state.session is None:
    oauth_code = st.query_params.get("code")

    if oauth_code:
        try:
            resp = sb.auth.exchange_code_for_session({"auth_code": oauth_code})
            if resp.session:
                st.session_state.session = resp.session
                st.session_state.pop("google_oauth_url", None)
                st.query_params.clear()
                st.rerun()
        except Exception as e:
            st.error("Não foi possível concluir o login com Google.")
            st.caption(str(e))


def obter_url_atual():
    """Retorna a URL base correta para OAuth em ambiente local ou Streamlit Cloud."""
    try:
        headers = st.context.headers
        host = headers.get("Host", "") if headers else ""
        proto = headers.get("X-Forwarded-Proto", "") if headers else ""

        if host:
            host_lower = host.lower()

            if host_lower.startswith("localhost") or host_lower.startswith("127.0.0.1"):
                return f"http://{host}"

            return f"{proto or 'https'}://{host}"

    except Exception:
        pass

    return APP_URL_CONFIG.rstrip("/")


REDIRECT_URL = obter_url_atual()


def header():
    st.markdown(
        """
        <div class="rio-topbar">
            <div class="rio-title">CAP 2.1 — Rastreamento Oncológico</div>
            <div class="rio-subtitle">
                Monitoramento de elegibilidade, situação do rastreamento, agendamentos e busca ativa
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# LOGIN — SOMENTE GOOGLE
# =========================================================
if st.session_state.session is None:
    header()
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.subheader("Acesso ao painel")
    st.caption("Área restrita a usuários autorizados.")

    try:
        oauth_result = sb.auth.sign_in_with_oauth(
            {
                "provider": "google",
                "options": {
                    "redirect_to": REDIRECT_URL,
                    "scopes": (
                        "openid "
                        "https://www.googleapis.com/auth/userinfo.email "
                        "https://www.googleapis.com/auth/userinfo.profile"
                    ),
                },
            }
        )

        if oauth_result.url:
            st.link_button(
                "Entrar com Google",
                oauth_result.url,
                use_container_width=True,
                type="primary",
            )

    except Exception as e:
        st.error("Não foi possível iniciar o login com Google.")
        st.caption(str(e))

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

try:
    sb.auth.set_session(
        st.session_state.session.access_token,
        st.session_state.session.refresh_token,
    )
except Exception:
    pass


# =========================================================
# CONTROLE DE ACESSO POR E-MAIL
# =========================================================
def obter_acesso_usuario():
    try:
        email = st.session_state.session.user.email
    except Exception:
        return None

    if not email:
        return None

    try:
        resp = (
            sb.table("usuarios_autorizados")
            .select("email,perfil,unidade,ativo")
            .eq("email", email)
            .eq("ativo", True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        return None


acesso_usuario = obter_acesso_usuario()

if not acesso_usuario:
    header()

    st.error("Acesso não autorizado.")
    st.info(
        "Seu login Google foi reconhecido, mas este e-mail não está autorizado "
        "a acessar o painel."
    )

    try:
        email_bloqueado = st.session_state.session.user.email
        st.caption(f"E-mail autenticado: {email_bloqueado}")
    except Exception:
        pass

    if st.button("Sair", type="primary"):
        try:
            sb.auth.sign_out()
        except Exception:
            pass

        st.session_state.session = None
        st.cache_data.clear()
        st.rerun()

    st.stop()

PERFIL_USUARIO = acesso_usuario.get("perfil")
UNIDADE_USUARIO = acesso_usuario.get("unidade")


def rpc(nome, params=None):
    try:
        r = sb.rpc(nome, params or {}).execute()
        return r.data
    except Exception as e:
        st.error(f"Erro ao consultar {nome}.")
        st.caption(str(e))
        st.stop()


def fmt(n):
    return f"{int(n or 0):,}".replace(",", ".")


def param(v):
    return v if v not in ("", "Todos") else None


@st.cache_data(ttl=300, show_spinner=False)
def filtros_disponiveis():
    return rpc("dashboard_filtros")


filtros = filtros_disponiveis() or {}

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("### Rastreamento Oncológico")

    try:
        email_usuario = st.session_state.session.user.email
    except Exception:
        email_usuario = ""

    if email_usuario:
        st.caption(email_usuario)

    if PERFIL_USUARIO == "admin":
        st.caption("Perfil: Administração · acesso total")
    elif PERFIL_USUARIO == "cap":
        st.caption("Perfil: CAP · acesso total")
    elif PERFIL_USUARIO == "unidade":
        st.caption(f"Perfil: Unidade · {UNIDADE_USUARIO or 'não definida'}")

    if st.button("Sair", use_container_width=True):
        try:
            sb.auth.sign_out()
        except Exception:
            pass
        st.session_state.session = None
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("### Filtros")

    unidades_disponiveis = list(filtros.get("unidades", []))

    if PERFIL_USUARIO == "unidade":
        unidades = [UNIDADE_USUARIO] if UNIDADE_USUARIO else []
    else:
        unidades = ["Todos"] + unidades_disponiveis

    equipes = ["Todos"] + list(filtros.get("equipes", []))
    microareas = ["Todos"] + list(filtros.get("microareas", []))

    programas_raw = filtros.get("programas", [])
    programa_map = {"Todos": None}
    for p in programas_raw:
        if isinstance(p, dict):
            programa_map[p.get("nome") or p.get("codigo")] = p.get("codigo")

    status_list = ["Todos"] + list(filtros.get("status", []))

    if PERFIL_USUARIO == "unidade":
        if not UNIDADE_USUARIO:
            st.error("Seu perfil de unidade não possui uma unidade vinculada.")
            st.stop()
        st.text_input("Unidade", value=UNIDADE_USUARIO, disabled=True)
        f_unidade = UNIDADE_USUARIO
    else:
        f_unidade = st.selectbox("Unidade", unidades)

    f_equipe = st.selectbox("Equipe", equipes)
    f_micro = st.selectbox("Microárea", microareas)
    f_programa_nome = st.selectbox("Programa", list(programa_map.keys()))
    f_status = st.selectbox("Status", status_list)

    f_programa = programa_map.get(f_programa_nome)

params_base = {
    "p_unidade": param(f_unidade),
    "p_equipe": param(f_equipe),
    "p_microarea": param(f_micro),
    "p_programa": f_programa,
    "p_status": param(f_status),
}


@st.cache_data(ttl=120, show_spinner=False)
def get_resumo(unidade, equipe, microarea, programa, status):
    data = rpc(
        "dashboard_resumo",
        {
            "p_unidade": unidade,
            "p_equipe": equipe,
            "p_microarea": microarea,
            "p_programa": programa,
            "p_status": status,
        },
    )
    return data[0] if data else {}


@st.cache_data(ttl=120, show_spinner=False)
def get_status(unidade, equipe, microarea, programa):
    return rpc(
        "dashboard_status",
        {
            "p_unidade": unidade,
            "p_equipe": equipe,
            "p_microarea": microarea,
            "p_programa": programa,
        },
    ) or []


@st.cache_data(ttl=120, show_spinner=False)
def get_programas(unidade, equipe, microarea):
    return rpc(
        "dashboard_programas",
        {
            "p_unidade": unidade,
            "p_equipe": equipe,
            "p_microarea": microarea,
        },
    ) or []


@st.cache_data(ttl=120, show_spinner=False)
def get_unidades(programa, status):
    return rpc(
        "dashboard_unidades",
        {"p_programa": programa, "p_status": status},
    ) or []


def status_chart(rows, titulo):
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    fig = px.bar(
        df,
        x="status_rastreamento",
        y="total",
        color="status_rastreamento",
        text="total",
        color_discrete_map=STATUS_COLORS,
        title=titulo,
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        showlegend=False,
        margin=dict(l=10, r=10, t=55, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="",
        yaxis_title="Total",
    )
    st.plotly_chart(fig, use_container_width=True)


def unidade_chart(rows, titulo):
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    df = df.sort_values("total")
    fig = px.bar(
        df,
        x="total",
        y="unidade",
        orientation="h",
        text="total",
        title=titulo,
        color_discrete_sequence=[RIO_BLUE],
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        margin=dict(l=10, r=20, t=55, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="Total",
        yaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True)


def pct(valor, total):
    valor = int(valor or 0)
    total = int(total or 0)
    if total <= 0:
        return "0,0%"
    return f"{(valor / total) * 100:.1f}%".replace(".", ",")


def metric_card(label, value, css_class="neutral", percent=None):
    extra = f'<div class="metric-percent">{percent}</div>' if percent is not None else ""
    st.markdown(
        f"""
        <div class="metric-card {css_class}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{fmt(value)}</div>
            {extra}
        </div>
        """,
        unsafe_allow_html=True,
    )


def cards(resumo, colonoscopia=False):
    total = int(resumo.get("elegibilidades") or 0)

    if colonoscopia:
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            metric_card("Pessoas acompanhadas", resumo.get("pessoas_unicas"), "neutral")
        with c2:
            metric_card("Registros", resumo.get("elegibilidades"), "neutral")
        with c3:
            metric_card("Realizado/Confirmado", resumo.get("realizado_confirmado"), "success", pct(resumo.get("realizado_confirmado"), total))
        with c4:
            metric_card("Agendados", resumo.get("agendados"), "info", pct(resumo.get("agendados"), total))
        with c5:
            metric_card("Busca ativa", resumo.get("busca_ativa"), "danger", pct(resumo.get("busca_ativa"), total))
    else:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            metric_card("Pessoas únicas", resumo.get("pessoas_unicas"), "neutral")
        with c2:
            metric_card("Elegibilidades", resumo.get("elegibilidades"), "neutral")
        with c3:
            metric_card("Em dia", resumo.get("em_dia"), "success", pct(resumo.get("em_dia"), total))
        with c4:
            metric_card("Em atraso", resumo.get("em_atraso"), "warning", pct(resumo.get("em_atraso"), total))
        with c5:
            metric_card("Agendados", resumo.get("agendados"), "info", pct(resumo.get("agendados"), total))
        with c6:
            metric_card("Busca ativa", resumo.get("busca_ativa"), "danger", pct(resumo.get("busca_ativa"), total))



def pagina_administracao():
    st.markdown("## ⚙️ Administração e manutenção")
    st.caption(
        "Área exclusiva para atualização das fontes de dados e acompanhamento das cargas."
    )

    st.markdown("### 📄 Fonte 1 — Planilha Excel mensal")
    st.info(
        "Selecione a planilha Excel que substitui a base mensal. "
        "Nesta etapa o arquivo é apenas validado e não altera o Supabase."
    )

    arquivo_excel = st.file_uploader(
        "Selecionar planilha mensal",
        type=["xlsx", "xls"],
        key="admin_excel_mensal",
        help="Selecione o arquivo correspondente à nova competência.",
    )

    if arquivo_excel is not None:
        tamanho_mb = arquivo_excel.size / (1024 * 1024)
        st.success(
            f"Arquivo selecionado: {arquivo_excel.name} — {tamanho_mb:.2f} MB"
        )

        try:
            preview = pd.read_excel(arquivo_excel, nrows=20)

            st.markdown("#### Prévia do arquivo")
            st.dataframe(
                preview,
                use_container_width=True,
                hide_index=True,
            )

            c1, c2 = st.columns(2)
            with c1:
                st.metric("Colunas identificadas", len(preview.columns))
            with c2:
                st.metric("Linhas na prévia", len(preview))

            if st.button(
                "Validar arquivo para atualização",
                type="primary",
                use_container_width=True,
                key="admin_validar_excel",
            ):
                st.session_state["excel_validado"] = True

            if st.session_state.get("excel_validado"):
                st.success("✅ Arquivo validado para processamento.")
                st.warning(
                    "A gravação no Supabase ainda não está ativada. "
                    "Na próxima etapa conectaremos este upload ao processo mensal."
                )

        except Exception as e:
            st.error("Não foi possível ler a planilha selecionada.")
            st.caption(str(e))

    st.divider()

    st.markdown("### ☁️ Fonte 2 — Planilha do Google Drive")
    st.info(
        "Esta fonte será sincronizada automaticamente uma vez por mês."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Periodicidade planejada", "Mensal")
    with c2:
        st.metric("Automação", "A configurar")

    st.warning(
        "A conexão com o Google Drive e o agendamento mensal serão configurados "
        "na próxima etapa."
    )

    st.divider()

    st.markdown("### 🕘 Histórico de atualizações")
    st.caption(
        "Quando ativarmos as cargas, esta área registrará data, fonte, competência, "
        "quantidade de registros, usuário responsável e status."
    )

    historico = pd.DataFrame(
        columns=[
            "Data",
            "Fonte",
            "Competência",
            "Registros",
            "Usuário",
            "Status",
        ]
    )

    st.dataframe(
        historico,
        use_container_width=True,
        hide_index=True,
    )

    st.info("Nenhuma atualização registrada pela nova rotina ainda.")


def busca_ativa(chave, programa_forcado=None):
    st.markdown('<div class="section-title">Busca ativa nominal</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">A consulta é paginada e busca diretamente no Supabase.</div>',
        unsafe_allow_html=True,
    )

    busca = st.text_input(
        "Buscar por nome ou CNS",
        key=f"busca_{chave}",
        placeholder="Digite parte do nome ou CNS",
    )

    page_size = st.selectbox(
        "Registros por página",
        [50, 100, 250, 500],
        index=1,
        key=f"ps_{chave}",
    )

    if f"page_{chave}" not in st.session_state:
        st.session_state[f"page_{chave}"] = 0

    col_a, col_b, _ = st.columns([1, 1, 4])

    with col_a:
        if st.button("← Anterior", key=f"prev_{chave}"):
            st.session_state[f"page_{chave}"] = max(
                0, st.session_state[f"page_{chave}"] - 1
            )

    with col_b:
        if st.button("Próxima →", key=f"next_{chave}"):
            st.session_state[f"page_{chave}"] += 1

    page = st.session_state[f"page_{chave}"]
    offset = page * page_size

    rows = rpc(
        "dashboard_busca",
        {
            "p_busca": busca.strip() or None,
            "p_unidade": param(f_unidade),
            "p_equipe": param(f_equipe),
            "p_microarea": param(f_micro),
            "p_programa": programa_forcado or f_programa,
            "p_status": param(f_status),
            "p_limit": page_size,
            "p_offset": offset,
        },
    ) or []

    total = rows[0].get("total_registros", 0) if rows else 0
    st.caption(
        f"Página {page + 1} · {fmt(total)} registro(s) encontrado(s)"
    )

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Nenhum registro encontrado.")
        return

    if "total_registros" in df.columns:
        df = df.drop(columns=["total_registros"])

    rename = {
        "nome": "Nome",
        "cns": "CNS",
        "idade": "Idade",
        "unidade": "Unidade",
        "equipe": "Equipe",
        "microarea": "Microárea",
        "programa": "Programa",
        "status_rastreamento": "Status",
        "data_agendamento": "Data de agendamento",
        "situacao": "Situação",
        "risco": "Risco",
    }

    cols = [
        "nome",
        "cns",
        "idade",
        "unidade",
        "equipe",
        "microarea",
        "programa",
        "status_rastreamento",
        "data_agendamento",
        "situacao",
        "risco",
    ]
    cols = [c for c in cols if c in df.columns]

    st.dataframe(
        df[cols].rename(columns=rename),
        use_container_width=True,
        hide_index=True,
        height=500,
    )


# =========================================================
# PAINEL
# =========================================================
header()

nomes_abas = [
    "Visão Geral",
    "Mamografia",
    "Colo do Útero",
    "Colorretal",
    "Busca Ativa",
]

if PERFIL_USUARIO == "admin":
    nomes_abas.append("⚙️ Administração")

tabs = st.tabs(nomes_abas)

u = param(f_unidade)
e = param(f_equipe)
m = param(f_micro)
s = param(f_status)

with tabs[0]:
    resumo = get_resumo(u, e, m, f_programa, s)
    cards(resumo)

    left, right = st.columns(2)
    with left:
        status_chart(
            get_status(u, e, m, f_programa),
            "Situação atual do rastreamento",
        )

    with right:
        prog = pd.DataFrame(get_programas(u, e, m))
        if not prog.empty:
            fig = px.bar(
                prog,
                x="programa",
                y="total",
                color="status_rastreamento",
                color_discrete_map=STATUS_COLORS,
                title="Situação por programa",
            )
            fig.update_layout(
                margin=dict(l=10, r=10, t=55, b=10),
                paper_bgcolor="white",
                plot_bgcolor="white",
                xaxis_title="",
                yaxis_title="Total",
                legend_title="Status",
            )
            st.plotly_chart(fig, use_container_width=True)

    unidade_chart(
        get_unidades(f_programa, s),
        "Distribuição por unidade",
    )

with tabs[1]:
    programa = "mamografia"
    resumo = get_resumo(u, e, m, programa, s)
    cards(resumo)

    left, right = st.columns(2)
    with left:
        status_chart(
            get_status(u, e, m, programa),
            "Situação — Mamografia",
        )
    with right:
        unidade_chart(
            get_unidades(programa, s),
            "Mamografia por unidade",
        )

    busca_ativa("mamografia", programa)

with tabs[2]:
    programa = "citopatologico"
    resumo = get_resumo(u, e, m, programa, s)
    cards(resumo)

    left, right = st.columns(2)
    with left:
        status_chart(
            get_status(u, e, m, programa),
            "Situação — Citopatológico",
        )
    with right:
        unidade_chart(
            get_unidades(programa, s),
            "Citopatológico por unidade",
        )

    busca_ativa("citopatologico", programa)

with tabs[3]:
    st.markdown("### Sangue oculto / FIT")
    programa = "sangue_oculto"
    resumo = get_resumo(u, e, m, programa, s)
    cards(resumo)

    left, right = st.columns(2)
    with left:
        status_chart(
            get_status(u, e, m, programa),
            "Situação — Sangue oculto / FIT",
        )
    with right:
        unidade_chart(
            get_unidades(programa, s),
            "Sangue oculto / FIT por unidade",
        )

    st.divider()
    st.markdown("### Colonoscopia — seguimento")
    programa_c = "colonoscopia"
    resumo_c = get_resumo(u, e, m, programa_c, s)
    cards(resumo_c, colonoscopia=True)

    left, right = st.columns(2)
    with left:
        status_chart(
            get_status(u, e, m, programa_c),
            "Situação — Colonoscopia",
        )
    with right:
        unidade_chart(
            get_unidades(programa_c, s),
            "Colonoscopia por unidade",
        )

with tabs[4]:
    busca_ativa("geral", None)

if PERFIL_USUARIO == "admin" and len(tabs) > 5:
    with tabs[5]:
        pagina_administracao()

st.caption(
    "CAP 2.1 — Rastreamento Oncológico | Painel operacional para apoio ao monitoramento e à busca ativa."
)
