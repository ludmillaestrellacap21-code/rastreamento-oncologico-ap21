from pathlib import Path
import os
from datetime import datetime

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
RIO_BG = "#F5F7F9"
RIO_BORDER = "#D9E2E8"
RIO_TEXT = "#243746"
RIO_MUTED = "#667985"

STATUS_COLORS = {
    # situação favorável
    "Em dia": "#3F8F5B",

    # atenção
    "Vence em até 90 dias": "#D6A21F",

    # prioridade
    "Em atraso": "#D65A5A",

    # ausência de informação — propositalmente discreto
    "Sem registro de realização": "#A7B4C0",

    # acompanhamento
    "Seguimento": "#4E7FA8",
}


FLUXO_COLORS = {
    # fluxo assistencial
    "Agendado": "#4A90D9",
    "Confirmado": "#1769AA",

    # prioridade
    "Falta - Reconvocar": "#D65A5A",

    # atenção / regulação
    "Pendente regulação": "#D6A21F",

    # situações administrativas
    "Cancelado": "#A7B4C0",
    "Devolvido": "#8B78A8",
    "Reenviado": "#71649A",
    "Negado": "#687987",

    # resultados
    "Resultado entregue": "#3F8F5B",
    "Resultado alterado": "#C94F5D",

    # processamento
    "Em processamento": "#4E9BBF",
    "Coletado - aguardando laboratório": "#657FB5",

    # propositalmente neutro
    "Sem movimentação": "#B3BEC7",
}

st.markdown(
    f"""
    <style>

    /* =====================================================
       ESTRUTURA GERAL
       ===================================================== */

    .stApp {{
        background: #F5F7FA;
        color: {RIO_TEXT};
    }}

    .block-container {{
        max-width: 1500px;
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }}

    [data-testid="stHeader"] {{
        background: transparent;
    }}

    [data-testid="stToolbar"] {{
        right: 1rem;
    }}


    /* =====================================================
       SIDEBAR
       ===================================================== */

    [data-testid="stSidebar"] {{
        background:
            linear-gradient(
                180deg,
                #102F50 0%,
                #173D64 58%,
                #123554 100%
            );
        border-right: none;
        box-shadow: 4px 0 18px rgba(16,47,80,.10);
    }}

    [data-testid="stSidebar"] > div:first-child {{
        padding-top: 1.2rem;
    }}

    [data-testid="stSidebar"] * {{
        color: rgba(255,255,255,.94);
    }}

    .sidebar-brand {{
        padding: 8px 4px 20px 4px;
        margin-bottom: 6px;
    }}

    .sidebar-brand-title {{
        font-size: 1.18rem;
        line-height: 1.15;
        font-weight: 800;
        color: white;
        letter-spacing: -.01em;
    }}

    .sidebar-brand-subtitle {{
        margin-top: 5px;
        font-size: .78rem;
        font-weight: 500;
        color: rgba(255,255,255,.68);
    }}


    /* Botões da navegação */

    [data-testid="stSidebar"] div.stButton > button {{
        width: 100%;
        min-height: 42px;
        border-radius: 9px;
        border: 1px solid transparent;
        background: transparent;
        color: rgba(255,255,255,.80);
        font-weight: 600;
        text-align: left;
        justify-content: flex-start;
        padding-left: 13px;
        box-shadow: none;
        transition: all .15s ease;
    }}

    [data-testid="stSidebar"] div.stButton > button:hover {{
        background: rgba(255,255,255,.09);
        border-color: rgba(255,255,255,.06);
        color: white;
    }}

    [data-testid="stSidebar"] div.stButton > button[kind="primary"] {{
        background: rgba(255,255,255,.15) !important;
        border: 1px solid rgba(255,255,255,.12) !important;
        color: white !important;
        font-weight: 700;
        box-shadow: none;
    }}

    [data-testid="stSidebar"] hr {{
        border-color: rgba(255,255,255,.13);
        margin-top: 18px;
        margin-bottom: 18px;
    }}

    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
        color: rgba(255,255,255,.66);
        font-size: .73rem;
    }}


    /* =====================================================
       CABEÇALHO
       ===================================================== */

.rio-topbar {{
    background: white;
    border: 1px solid #D9E2E8;
    border-radius: 12px;
    padding: 11px 18px;
    margin-bottom: 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,.025);
}}

.rio-brand {{
    display: flex;
    align-items: center;
    gap: 14px;
}}

.rio-cap {{
    color: #005CA9;
    font-size: .78rem;
    font-weight: 850;
    letter-spacing: .035em;
    white-space: nowrap;
}}

.rio-separator {{
    width: 1px;
    height: 30px;
    background: #D9E2E8;
}}

.rio-title {{
    color: #17365D;
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.1;
}}

.rio-subtitle {{
    color: #718096;
    font-size: .70rem;
    margin-top: 3px;
}}


    /* =====================================================
       TÍTULOS
       ===================================================== */

    h1, h2, h3 {{
        color: {RIO_NAVY};
        letter-spacing: -.015em;
    }}

    .section-title {{
        font-size: 1.05rem;
        font-weight: 750;
        color: {RIO_NAVY};
        margin: 18px 0 5px 0;
    }}

    .section-note {{
        font-size: .80rem;
        color: #718096;
        margin-bottom: 12px;
    }}


    /* =====================================================
       FILTROS
       ===================================================== */

    [data-testid="stSelectbox"] label,
    [data-testid="stTextInput"] label {{
        font-size: .73rem;
        font-weight: 700;
        color: #607386;
    }}

    [data-baseweb="select"] > div {{
        background: white;
        border-color: #DDE4EB;
        border-radius: 9px;
        min-height: 39px;
    }}

    [data-testid="stTextInput"] input {{
        background: white;
        border-color: #DDE4EB;
        border-radius: 9px;
    }}


    /* =====================================================
   CARDS DE KPI — SLIM
   ===================================================== */

/* Métricas nativas do Streamlit */
[data-testid="stMetric"] {{
    background: #FFFFFF;
    border: 1px solid #E1E7ED;
    border-radius: 10px;
    padding: 10px 12px;
    box-shadow: 0 1px 3px rgba(22,47,75,.025);
}}

[data-testid="stMetricValue"] {{
    color: {RIO_NAVY};
    font-weight: 800;
    font-size: 1.38rem;
}}

[data-testid="stMetricLabel"] {{
    color: #718096;
    font-size: .70rem;
    font-weight: 700;
}}


/* Cards personalizados */
.metric-card {{
    background: #FFFFFF;
    border: 1px solid #DCE5EC;
    border-radius: 10px;
    padding: 11px 13px;
    height: 82px;
    min-height: 82px;
    box-sizing: border-box;
    box-shadow: 0 1px 3px rgba(23,54,93,.025);
    margin-bottom: 2px;

    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}

.metric-card-top {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
    min-height: 20px;
    margin-bottom: 5px;
}}

.metric-label {{
    color: #6B7F90;
    font-size: .66rem;
    font-weight: 800;
    line-height: 1.1;
    text-transform: uppercase;
    letter-spacing: .035em;
}}

.metric-value {{
    color: #17365D;
    font-size: 1.32rem;
    font-weight: 800;
    line-height: 1;
}}


/* Percentual em formato de selo */
.metric-badge {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    padding: 3px 8px;
    font-size: .63rem;
    line-height: 1;
    font-weight: 800;
    white-space: nowrap;
    border: 1px solid transparent;
    flex: 0 0 auto;
    margin-left: auto;
}}


/* Neutro */
.metric-badge.neutral {{
    background: #F0F4F7;
    color: #607585;
    border-color: #DCE5EC;
}}


/* Em dia */
.metric-badge.success {{
    background: #EDF7EF;
    color: #2E7D32;
    border-color: #D2E9D5;
}}


/* Atenção */
.metric-badge.warning {{
    background: #FFF7E3;
    color: #A66B00;
    border-color: #F1DDA8;
}}


/* Fluxo / informação */
.metric-badge.info {{
    background: #EAF2F8;
    color: #005CA9;
    border-color: #D4E4F1;
}}


/* Prioridade */
.metric-badge.danger {{
    background: #FDEEEE;
    color: #B4232A;
    border-color: #F3D1D3;
}}

    /* =====================================================
       ATUALIZAÇÕES
       ===================================================== */

    .update-strip {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0,1fr));
        gap: 12px;
        margin: 3px 0 18px 0;
    }}

    .update-card {{
        background: white;
        border: 1px solid #E1E7ED;
        border-radius: 11px;
        padding: 12px 14px;
        min-height: 82px;
        box-shadow: 0 2px 7px rgba(22,47,75,.025);
    }}

    .update-label {{
        font-size: .70rem;
        color: #718096;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .03em;
    }}

    .update-value {{
        font-size: .91rem;
        color: {RIO_NAVY};
        font-weight: 750;
        margin-top: 5px;
    }}

    .update-detail {{
        font-size: .72rem;
        color: #8190A0;
        margin-top: 4px;
    }}


    /* =====================================================
       GRÁFICOS E TABELAS
       ===================================================== */

    [data-testid="stPlotlyChart"] {{
        background: #FFFFFF;
        border: 1px solid #E1E7ED;
        border-radius: 12px;
        padding: 8px;
        box-shadow: 0 2px 7px rgba(22,47,75,.025);
        box-sizing: border-box;
        width: 100%;
        overflow: hidden;
    }}

    /* Padroniza o espaço ocupado pelos gráficos lado a lado */
    [data-testid="stPlotlyChart"] > div {{
        width: 100% !important;
    }}

    [data-testid="stDataFrame"] {{
        border: 1px solid #E1E7ED;
        border-radius: 11px;
        overflow: hidden;
        background: white;
    }}


    /* =====================================================
       ALERTAS
       ===================================================== */

    [data-testid="stAlert"] {{
        border-radius: 10px;
        font-size: .82rem;
    }}


    /* =====================================================
       BOTÕES GERAIS
       ===================================================== */

    div.stButton > button:not([kind="primary"]) {{
        border-radius: 9px;
        font-weight: 650;
    }}

    div.stButton > button[kind="primary"],
    div[data-testid="stLinkButton"] a {{
        background: #005CA9 !important;
        color: white !important;
        border-color: #005CA9 !important;
        border-radius: 9px;
        font-weight: 700;
    }}

    div.stButton > button[kind="primary"]:hover,
    div[data-testid="stLinkButton"] a:hover {{
        background: #004A87 !important;
        border-color: #004A87 !important;
    }}


    /* =====================================================
       LOGIN
       ===================================================== */

    .login-box {{
    max-width: 460px;
    margin: 8vh auto 0 auto;
    text-align: center;
}}

.login-title {{
    font-size: 1.65rem;
    font-weight: 800;
    color: #17365D;
    margin-bottom: 6px;
}}

.login-subtitle {{
    font-size: .88rem;
    color: #718096;
    margin-bottom: 24px;
}}


    /* =====================================================
       AUXILIARES
       ===================================================== */

    .kpi-space {{
        height: 5px;
    }}

    .kpi-group-title {{
        font-size: .66rem;
        text-transform: uppercase;
        letter-spacing: .06em;
        color: #7A8B98;
        font-weight: 800;
        margin: 1px 0 6px 1px;
    }}

    hr {{
        border-color: #E4E9EE;
    }}

 /*=====================================================
   CABEÇALHO DAS PÁGINAS
   ===================================================== */

.page-heading {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    margin: 4px 0 18px 0;
}}

.page-title {{
    color: #17365D;
    font-size: 1.42rem;
    font-weight: 800;
    line-height: 1.15;
    letter-spacing: -.025em;
}}

.page-description {{
    color: #718096;
    font-size: .82rem;
    line-height: 1.45;
    margin-top: 5px;
}}

.page-badge {{
    background: #EAF2F8;
    color: #005CA9;
    border: 1px solid #D4E4F1;
    border-radius: 20px;
    padding: 6px 13px;
    font-size: .72rem;
    font-weight: 800;
    white-space: nowrap;
}}
    
    /* =====================================================
       RESPONSIVO
       ===================================================== */

    @media (max-width: 900px) {{

        .block-container {{
            padding-left: 1rem;
            padding-right: 1rem;
        }}

        .update-strip {{
            grid-template-columns: 1fr;
        }}
    }}

    </style>
    """,
    unsafe_allow_html=True,
)

if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
    st.error("Configure SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY no arquivo .env/Secrets.")
    st.stop()


@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)


sb = get_supabase()

if "session" not in st.session_state:
    st.session_state.session = None


# =========================================================
# OAUTH GOOGLE
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
    try:
        headers = st.context.headers
        host = headers.get("Host", "") if headers else ""
        proto = headers.get("X-Forwarded-Proto", "") if headers else ""
        if host:
            h = host.lower()
            if h.startswith("localhost") or h.startswith("127.0.0.1"):
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
    <div class="rio-brand">
        <span class="rio-cap">CAP 2.1</span>
        <span class="rio-separator"></span>
        <div>
            <div class="rio-title">Rastreamento Oncológico</div>
            <div class="rio-subtitle">Monitoramento, prevenção e busca ativa</div>
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

# =========================================================
# TELA DE LOGIN
# =========================================================

if st.session_state.session is None:

    st.markdown(
        """
        <div class="login-box">
            <div class="login-title">Rastreamento Oncológico</div>
            <div class="login-subtitle">CAP 2.1 · Monitoramento e Busca Ativa</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, login_col, _ = st.columns([1.15, 1, 1.15])

    with login_col:

        st.markdown(
            "<p style='text-align:center; color:#718096; "
            "font-size:.82rem; margin-bottom:14px;'>"
            "Acesso restrito a usuários autorizados"
            "</p>",
            unsafe_allow_html=True,
        )

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

        st.markdown(
            "<p style='text-align:center; color:#94A3B8; "
            "font-size:.70rem; margin-top:14px; line-height:1.5;'>"
            "Utilize uma conta Google previamente autorizada<br>"
            "para acessar o painel."
            "</p>",
            unsafe_allow_html=True,
        )

    st.stop()

try:
    sb.auth.set_session(st.session_state.session.access_token, st.session_state.session.refresh_token)
except Exception:
    pass


# =========================================================
# ACESSO
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
    st.info("Seu login Google foi reconhecido, mas este e-mail não está autorizado a acessar o painel.")
    try:
        st.caption(f"E-mail autenticado: {st.session_state.session.user.email}")
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


# =========================================================
# HELPERS / RPC
# =========================================================
def rpc(nome, params=None, stop_on_error=True):
    try:
        r = sb.rpc(nome, params or {}).execute()
        return r.data
    except Exception as e:
        if stop_on_error:
            st.error(f"Erro ao consultar {nome}.")
            st.caption(str(e))
            st.stop()
        return None


def fmt(n):
    return f"{int(n or 0):,}".replace(",", ".")


def param(v):
    return v if v not in ("", "Todos", None) else None


def pct(valor, total):
    valor = int(valor or 0)
    total = int(total or 0)
    if total <= 0:
        return "0,0%"
    return f"{(valor / total) * 100:.1f}%".replace(".", ",")


def fmt_data_hora(valor):
    if not valor:
        return "Ainda não realizada"
    try:
        dt = pd.to_datetime(valor, utc=True)
        dt = dt.tz_convert("America/Sao_Paulo")
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(valor)

def metric_card(label, value, css_class="neutral", percent=None):
    if percent is not None:
        badge = f'<span class="metric-badge {css_class}">{percent}</span>'
    else:
        badge = ""

    html = (
        f'<div class="metric-card">'
        f'<div class="metric-card-top">'
        f'<span class="metric-label">{label}</span>'
        f'{badge}'
        f'</div>'
        f'<div class="metric-value">{fmt(value)}</div>'
        f'</div>'
    )

    st.markdown(html, unsafe_allow_html=True)

@st.cache_data(ttl=300, show_spinner=False)
def filtros_disponiveis():
    return rpc("dashboard2_filtros") or {}


@st.cache_data(ttl=120, show_spinner=False)
def get_resumo(unidade, equipe, microarea, programa, status, fluxo):
    data = rpc(
        "dashboard2_resumo",
        {
            "p_unidade": unidade,
            "p_equipe": equipe,
            "p_microarea": microarea,
            "p_programa": programa,
            "p_status": status,
            "p_fluxo": fluxo,
        },
    )
    return data[0] if isinstance(data, list) and data else (data or {})


@st.cache_data(ttl=120, show_spinner=False)
def get_status(unidade, equipe, microarea, programa):
    return rpc("dashboard2_status", {
        "p_unidade": unidade, "p_equipe": equipe,
        "p_microarea": microarea, "p_programa": programa,
    }) or []


@st.cache_data(ttl=120, show_spinner=False)
def get_fluxo(unidade, equipe, microarea, programa):
    return rpc("dashboard2_fluxo", {
        "p_unidade": unidade, "p_equipe": equipe,
        "p_microarea": microarea, "p_programa": programa,
    }) or []


@st.cache_data(ttl=120, show_spinner=False)
def get_programas(unidade, equipe, microarea):
    return rpc("dashboard2_programas", {
        "p_unidade": unidade, "p_equipe": equipe, "p_microarea": microarea,
    }) or []


@st.cache_data(ttl=120, show_spinner=False)
def get_unidades(programa, status, fluxo, unidade):
    return rpc("dashboard2_unidades", {
        "p_programa": programa, "p_status": status,
        "p_fluxo": fluxo, "p_unidade": unidade,
    }) or []


@st.cache_data(ttl=120, show_spinner=False)
def get_atualizacoes():
    data = rpc("dashboard2_atualizacoes", stop_on_error=False)
    return data or {}


@st.cache_data(ttl=120, show_spinner=False)
def get_indicadores(programa, unidade, equipe, microarea):
    data = rpc("dashboard2_indicadores", {
        "p_programa": programa, "p_unidade": unidade,
        "p_equipe": equipe, "p_microarea": microarea,
    }, stop_on_error=False)
    return data or {}


# =========================================================
# SIDEBAR
# =========================================================
filtros = filtros_disponiveis()

# =========================================================
# SIDEBAR — NAVEGAÇÃO
# =========================================================

if "pagina_atual" not in st.session_state:
    st.session_state.pagina_atual = "Visão Geral"

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-title">Rastreamento</div>
            <div class="sidebar-brand-subtitle">Oncológico · CAP 2.1</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    paginas = [
    ("🏠", "Visão Geral"),
    ("🎗️", "Mamografia"),
    ("◉", "Colo do Útero"),
    ("🧬", "DNA-HPV"),
    ("▣", "Colorretal"),
    ("⌕", "Busca Ativa"),
]

    if PERFIL_USUARIO == "admin":
        paginas.append(("⚙️", "Administração"))

    for icone, nome in paginas:
        tipo = "primary" if st.session_state.pagina_atual == nome else "secondary"

        if st.button(
            f"{icone}  {nome}",
            key=f"nav_{nome}",
            use_container_width=True,
            type=tipo,
        ):
            st.session_state.pagina_atual = nome
            st.rerun()

    st.markdown("---")

    try:
        email_usuario = st.session_state.session.user.email
    except Exception:
        email_usuario = ""

    if email_usuario:
        st.caption(email_usuario)

    if PERFIL_USUARIO == "admin":
        st.caption("Administração · acesso total")
    elif PERFIL_USUARIO == "cap":
        st.caption("CAP 2.1 · acesso ao painel")
    elif PERFIL_USUARIO == "unidade":
        st.caption(f"Unidade · {UNIDADE_USUARIO or 'não definida'}")

    if st.button("Sair", use_container_width=True, key="logout"):
        try:
            sb.auth.sign_out()
        except Exception:
            pass

        st.session_state.session = None
        st.cache_data.clear()
        st.rerun()


# =========================================================
# FILTROS — BARRA HORIZONTAL
# =========================================================

unidades_disponiveis = list(filtros.get("unidades", []))
equipes = ["Todos"] + list(filtros.get("equipes", []))
microareas = ["Todos"] + list(filtros.get("microareas", []))

programa_map = {"Todos": None}

for p in filtros.get("programas", []):
    if isinstance(p, dict):
        programa_map[p.get("nome") or p.get("codigo")] = p.get("codigo")

status_list = ["Todos"] + list(filtros.get("status", []))
fluxo_list = ["Todos"] + list(filtros.get("fluxos", []))

c1, c2, c3, c4, c5, c6 = st.columns([1.3, 1.2, 1, 1.2, 1.2, 1.2])

with c1:
    if PERFIL_USUARIO == "unidade":
        if not UNIDADE_USUARIO:
            st.error("Seu perfil de unidade não possui uma unidade vinculada.")
            st.stop()

        st.text_input(
            "Unidade",
            value=UNIDADE_USUARIO,
            disabled=True,
        )
        f_unidade = UNIDADE_USUARIO
    else:
        f_unidade = st.selectbox(
            "Unidade",
            ["Todos"] + unidades_disponiveis,
        )

with c2:
    f_equipe = st.selectbox("Equipe", equipes)

with c3:
    f_micro = st.selectbox("Microárea", microareas)

with c4:
    f_programa_nome = st.selectbox(
        "Programa",
        list(programa_map.keys()),
    )

with c5:
    f_status = st.selectbox(
        "Status",
        status_list,
    )

with c6:
    f_fluxo = st.selectbox(
        "Fluxo",
        fluxo_list,
    )

f_programa = programa_map.get(f_programa_nome)

u = param(f_unidade)
e = param(f_equipe)
m = param(f_micro)
s = param(f_status)
fl = param(f_fluxo)


# =========================================================
# COMPONENTES
# =========================================================
def cards(resumo, colonoscopia=False):
    total = int(resumo.get("elegibilidades") or 0)

    # =====================================================
    # COLONOSCOPIA
    # =====================================================
    if colonoscopia:
        st.markdown(
            '<div class="kpi-group-title">Resumo do acompanhamento</div>',
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4 = st.columns(4, gap="large")

        with c1:
            metric_card(
                "Pessoas acompanhadas",
                resumo.get("pessoas_unicas"),
                "neutral",
            )

        with c2:
            metric_card(
                "Registros",
                resumo.get("elegibilidades"),
                "neutral",
            )

        with c3:
            total_agendado = (
                int(resumo.get("agendados") or 0)
                + int(resumo.get("confirmados") or 0)
            )

            metric_card(
                "Agendados / Confirmados",
                total_agendado,
                "info",
            )

        with c4:
            metric_card(
                "Falta - Reconvocar",
                resumo.get("faltas"),
                "danger",
            )

        st.markdown(
            '<div class="kpi-space"></div>',
            unsafe_allow_html=True,
        )

        c5, c6 = st.columns([1, 3], gap="large")

        with c5:
            metric_card(
                "Pendente regulação",
                resumo.get("pendente_regulacao"),
                "warning",
            )

        return

        # =====================================================
    # LINHA 1 — SITUAÇÃO GERAL
    # =====================================================

    st.markdown(
        '<div class="kpi-group-title">Situação geral</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4, gap="small")

    with c1:
        metric_card(
            "Pessoas únicas",
            resumo.get("pessoas_unicas"),
            "neutral",
        )

    with c2:
        metric_card(
            "Elegibilidades",
            resumo.get("elegibilidades"),
            "neutral",
        )

    with c3:
        metric_card(
            "Em dia",
            resumo.get("em_dia"),
            "success",
            pct(resumo.get("em_dia"), total),
        )

    with c4:
        metric_card(
            "Busca ativa",
            resumo.get("busca_ativa"),
            "danger",
            pct(resumo.get("busca_ativa"), total),
        )

    st.markdown(
        '<div class="kpi-space"></div>',
        unsafe_allow_html=True,
    )

    # =====================================================
    # LINHA 2 — TEMPORAL + FLUXO OPERACIONAL
    # =====================================================

    bloco_temporal, bloco_fluxo = st.columns(2, gap="medium")

    # -------------------------
    # SITUAÇÃO TEMPORAL
    # -------------------------
    with bloco_temporal:

        st.markdown(
            '<div class="kpi-group-title">Situação temporal</div>',
            unsafe_allow_html=True,
        )

        c5, c6, c7 = st.columns(3, gap="small")

        with c5:
            metric_card(
                "Sem registro",
                resumo.get("sem_registro"),
                "neutral",
                pct(resumo.get("sem_registro"), total),
            )

        with c6:
            metric_card(
                "Vence em 90 dias",
                resumo.get("vence_90"),
                "warning",
                pct(resumo.get("vence_90"), total),
            )

        with c7:
            metric_card(
                "Em atraso",
                resumo.get("em_atraso"),
                "danger",
                pct(resumo.get("em_atraso"), total),
            )

    # -------------------------
    # FLUXO OPERACIONAL
    # -------------------------
    with bloco_fluxo:

        st.markdown(
            '<div class="kpi-group-title">Fluxo operacional</div>',
            unsafe_allow_html=True,
        )

        c8, c9, c10 = st.columns(3, gap="small")

        with c8:
            metric_card(
                "Agendados",
                resumo.get("agendados"),
                "info",
            )

        with c9:
            metric_card(
                "Confirmados",
                resumo.get("confirmados"),
                "info",
            )

        with c10:
            metric_card(
                "Falta - Reconvocar",
                resumo.get("faltas"),
                "danger",
            )

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
    )

    fig.update_traces(
        textposition="outside",
        marker_line_width=0,
        textfont_size=11,
    )

    fig.update_layout(
        title=dict(
            text=titulo,
            font=dict(size=15),
            x=0.02,
        ),
        height=350,
        showlegend=False,
        margin=dict(l=20, r=30, t=60, b=35),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="",
        yaxis_title="",
        bargap=0.38,
    )

    fig.update_xaxes(
        showgrid=False,
        tickfont=dict(size=10, color="#6B7A90"),
        linecolor="#E5EAF0",
    )

    fig.update_yaxes(
        gridcolor="#EEF2F6",
        zeroline=False,
        tickfont=dict(size=10, color="#7A8798"),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )

def fluxo_chart(rows, titulo):
    df = pd.DataFrame(rows)

    if df.empty:
        st.info("Sem movimentação operacional para os filtros selecionados.")
        return

    df = df.sort_values("total", ascending=True)

    fig = px.bar(
        df,
        x="total",
        y="status_fluxo",
        orientation="h",
        color="status_fluxo",
        text="total",
        color_discrete_map=FLUXO_COLORS,
    )

    fig.update_traces(
        textposition="outside",
        marker_line_width=0,
        textfont_size=10,
    )

    fig.update_layout(
        title=dict(
            text=titulo,
            font=dict(size=15),
            x=0.02,
        ),
        height=330,
        showlegend=False,
        margin=dict(l=20, r=35, t=55, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="",
        yaxis_title="",
        bargap=0.30,
    )

    fig.update_xaxes(
        gridcolor="#EEF2F6",
        zeroline=False,
        tickfont=dict(size=10, color="#7A8798"),
    )

    fig.update_yaxes(
        showgrid=False,
        tickfont=dict(size=10, color="#6B7A90"),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )

def unidade_chart(rows, titulo):
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return
    df = df.sort_values("total")
    fig = px.bar(df, x="total", y="unidade", orientation="h", text="total",
                 title=titulo, color_discrete_sequence=[RIO_BLUE])
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=420,
        margin=dict(l=20, r=30, t=60, b=35),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="Total",
        yaxis_title=""
    )
    st.plotly_chart(fig, use_container_width=True)


def atualizacoes_visao_geral():
    dados = get_atualizacoes()
    auto = dados.get("automatica") if isinstance(dados, dict) else None
    manual = dados.get("manual") if isinstance(dados, dict) else None
    auto = auto or {}
    manual = manual or {}

    auto_data = fmt_data_hora(auto.get("fim_em") or auto.get("inicio_em"))
    manual_data = fmt_data_hora(manual.get("fim_em") or manual.get("inicio_em"))
    auto_det = f"{auto.get('fonte') or 'Google Sheets'} · {auto.get('status') or 'sem registro'}"
    manual_det = f"{manual.get('fonte') or 'Base mensal'} · {manual.get('status') or 'sem registro'}"

    st.markdown(
        f"""
        <div class="update-strip">
          <div class="update-card">
            <div class="update-label">Última atualização automática</div>
            <div class="update-value">{auto_data}</div>
            <div class="update-detail">{auto_det}</div>
          </div>
          <div class="update-card">
            <div class="update-label">Última atualização manual</div>
            <div class="update-value">{manual_data}</div>
            <div class="update-detail">{manual_det}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def indicadores_operacionais(programa):
    dados = get_indicadores(programa, u, e, m)
    if not isinstance(dados, dict) or not dados:
        return

    st.markdown('<div class="section-title">Indicadores operacionais</div>', unsafe_allow_html=True)
    if programa in ("mamografia", "colonoscopia"):
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Agendados", fmt(dados.get("agendados")))
        c2.metric("Confirmados", fmt(dados.get("confirmados")))
        c3.metric("Faltas", fmt(dados.get("faltas")))
        c4.metric("Pendente regulação", fmt(dados.get("pendentes")))
        media = dados.get("media_dias_solicitacao_agendamento")
        c5.metric("Média solicitação → agenda", f"{media or 0} dias")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Aguardando laboratório", fmt(dados.get("aguardando_laboratorio")))
        c2.metric("Em processamento", fmt(dados.get("processamento")))
        c3.metric("Resultado entregue", fmt(dados.get("resultados_entregues")))
        c4.metric("Resultados alterados", fmt(dados.get("alterados")))
        media = dados.get("media_dias_coleta_resultado")
        c5.metric("Média coleta → resultado", f"{media or 0} dias")


def busca_ativa(chave, programa_forcado=None):
    st.markdown(
        '<div class="section-title">Busca ativa nominal</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="section-note">
        Fila nominal organizada por prioridade.
        A situação temporal e o fluxo operacional são apresentados separadamente.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # =====================================================
    # PRIORIDADE
    # =====================================================

    prioridade_map = {
        "Todas as prioridades": None,
        "🔴 P1 — Em atraso":
            "Prioridade 1 - Em atraso",

        "🟠 P2 — Vence em até 30 dias":
            "Prioridade 2 - Vence em até 30 dias",

        "🟡 P3 — Vence entre 31 e 60 dias":
            "Prioridade 3 - Vence entre 31 e 60 dias",

        "🟢 P4 — Vence entre 61 e 90 dias":
            "Prioridade 4 - Vence entre 61 e 90 dias",

        "⚪ P5 — Sem registro de realização":
            "Prioridade 5 - Sem registro de realização",
    }

    st.markdown(
        "#### Prioridade da busca ativa"
    )

    prioridade_nome = st.selectbox(
        "Selecionar prioridade",
        list(prioridade_map.keys()),
        key=f"prioridade_{chave}",
        label_visibility="collapsed",
    )

    prioridade = prioridade_map[
        prioridade_nome
    ]

    # =====================================================
    # EXPLICAÇÃO DAS PRIORIDADES
    # =====================================================

    p1, p2, p3, p4, p5 = st.columns(5)

    with p1:
        st.markdown(
            """
            <div class="metric-card danger">
                <div class="metric-label">
                    PRIORIDADE 1
                </div>
                <div class="metric-value"
                     style="font-size:1.15rem;">
                    Em atraso
                </div>
                <div class="metric-percent">
                    Intervenção imediata
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with p2:
        st.markdown(
            """
            <div class="metric-card danger">
                <div class="metric-label">
                    PRIORIDADE 2
                </div>
                <div class="metric-value"
                     style="font-size:1.15rem;">
                    Até 30 dias
                </div>
                <div class="metric-percent">
                    Alta prioridade
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with p3:
        st.markdown(
            """
            <div class="metric-card warning">
                <div class="metric-label">
                    PRIORIDADE 3
                </div>
                <div class="metric-value"
                     style="font-size:1.15rem;">
                    31–60 dias
                </div>
                <div class="metric-percent">
                    Programar contato
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with p4:
        st.markdown(
            """
            <div class="metric-card success">
                <div class="metric-label">
                    PRIORIDADE 4
                </div>
                <div class="metric-value"
                     style="font-size:1.15rem;">
                    61–90 dias
                </div>
                <div class="metric-percent">
                    Busca preventiva
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with p5:
        st.markdown(
            """
            <div class="metric-card neutral">
                <div class="metric-label">
                    PRIORIDADE 5
                </div>
                <div class="metric-value"
                     style="font-size:1.15rem;">
                    Sem registro
                </div>
                <div class="metric-percent">
                    Avaliar histórico
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="kpi-space"></div>',
        unsafe_allow_html=True,
    )

    # =====================================================
    # BUSCA
    # =====================================================

    c_busca, c_paginas = st.columns(
        [3, 1],
        gap="large",
    )

    with c_busca:
        busca = st.text_input(
            "Buscar por nome ou CNS",
            key=f"busca_{chave}",
            placeholder="Digite parte do nome ou CNS",
        )

    with c_paginas:
        page_size = st.selectbox(
            "Registros por página",
            [50, 100, 250, 500],
            index=1,
            key=f"ps_{chave}",
        )

    page_key = f"page_{chave}"

    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    # Se mudar a prioridade, volta para primeira página.
    prioridade_state = (
        f"prioridade_anterior_{chave}"
    )

    if (
        st.session_state.get(
            prioridade_state
        ) != prioridade
    ):
        st.session_state[page_key] = 0

        st.session_state[
            prioridade_state
        ] = prioridade

    col_a, col_b, _ = st.columns(
        [1, 1, 4]
    )

    with col_a:
        if st.button(
            "← Anterior",
            key=f"prev_{chave}",
        ):
            st.session_state[
                page_key
            ] = max(
                0,
                st.session_state[
                    page_key
                ] - 1,
            )

    with col_b:
        if st.button(
            "Próxima →",
            key=f"next_{chave}",
        ):
            st.session_state[
                page_key
            ] += 1

    page = st.session_state[
        page_key
    ]

    # =====================================================
    # RPC
    # =====================================================

    rows = rpc(
        "dashboard2_busca",
        {
            "p_busca":
                busca.strip() or None,

            "p_unidade": u,

            "p_equipe": e,

            "p_microarea": m,

            "p_programa":
                programa_forcado
                or f_programa,

            "p_status": s,

            "p_fluxo": fl,

            "p_prioridade":
                prioridade,

            "p_limit":
                page_size,

            "p_offset":
                page * page_size,
        },
    ) or []

    total = (
        rows[0].get(
            "total_registros",
            0,
        )
        if rows
        else 0
    )

    # =====================================================
    # CABEÇALHO DA LISTA
    # =====================================================

    st.markdown(
        '<div class="section-title">'
        'Lista nominal'
        '</div>',
        unsafe_allow_html=True,
    )

    if prioridade:
        st.caption(
            f"{prioridade_nome} · "
            f"{fmt(total)} paciente(s)"
        )
    else:
        st.caption(
            f"Todas as prioridades · "
            f"{fmt(total)} paciente(s)"
        )

    st.caption(
        f"Página {page + 1}"
    )

    df = pd.DataFrame(rows)

    if df.empty:
        st.info(
            "Nenhum registro encontrado "
            "para os filtros selecionados."
        )
        return

    if "total_registros" in df.columns:
        df = df.drop(
            columns=[
                "total_registros"
            ]
        )

    # =====================================================
    # FORMATAÇÃO
    # =====================================================

    rename = {
    "prioridade": "Prioridade",
    "nome": "Nome",
    "cns": "CNS",
    "idade": "Idade",
    "unidade": "Unidade",
    "equipe": "Equipe",
    "programa": "Programa",
    "status_rastreamento": "Situação temporal",
    "status_fluxo": "Fluxo operacional",
    "dias_para_vencer": "Dias para vencer",
    "data_proxima_referencia": "Próxima referência",
    "microarea": "Microárea",
    "data_ultima_realizacao": "Última realização",
    "data_agendamento": "Agendamento",
    "data_solicitacao": "Solicitação",
    "risco": "Risco",
}

    cols = [
    c
    for c in [
        "prioridade",
        "nome",
        "cns",
        "idade",
        "unidade",
        "equipe",
        "programa",
        "status_rastreamento",
        "status_fluxo",
        "dias_para_vencer",
        "data_proxima_referencia",
        "microarea",
        "data_ultima_realizacao",
        "data_agendamento",
        "data_solicitacao",
        "risco",
    ]
    if c in df.columns
]

    st.dataframe(
    df[cols].rename(columns=rename),
    use_container_width=True,
    hide_index=True,
    height=560,
    column_config={
        "Prioridade": st.column_config.TextColumn(
            "Prioridade",
            width="medium",
        ),
        "Nome": st.column_config.TextColumn(
            "Nome",
            width="large",
        ),
        "CNS": st.column_config.TextColumn(
            "CNS",
            width="medium",
        ),
        "Idade": st.column_config.NumberColumn(
            "Idade",
            width="small",
        ),
        "Unidade": st.column_config.TextColumn(
            "Unidade",
            width="large",
        ),
        "Equipe": st.column_config.TextColumn(
            "Equipe",
            width="medium",
        ),
        "Programa": st.column_config.TextColumn(
            "Programa",
            width="medium",
        ),
        "Situação temporal": st.column_config.TextColumn(
            "Situação temporal",
            width="medium",
        ),
        "Fluxo operacional": st.column_config.TextColumn(
            "Fluxo operacional",
            width="medium",
        ),
        "Dias para vencer": st.column_config.NumberColumn(
            "Dias para vencer",
            width="small",
        ),
        "Próxima referência": st.column_config.DateColumn(
            "Próxima referência",
            format="DD/MM/YYYY",
            width="medium",
        ),
        "Última realização": st.column_config.DateColumn(
            "Última realização",
            format="DD/MM/YYYY",
            width="medium",
        ),
        "Agendamento": st.column_config.DateColumn(
            "Agendamento",
            format="DD/MM/YYYY",
            width="medium",
        ),
        "Solicitação": st.column_config.DateColumn(
            "Solicitação",
            format="DD/MM/YYYY",
            width="medium",
        ),
    },
)

def pagina_nao_localizados():
    st.markdown("### Qualidade cadastral — pacientes não localizados")
    st.caption(
        "Nenhuma correspondência é aplicada automaticamente. Sugestões por nome + nascimento servem apenas para conferência administrativa."
    )

    c1, c2, c3 = st.columns(3)
    programa = c1.selectbox("Programa", ["Todos","mamografia","citopatologico","sangue_oculto","colonoscopia"], key="nl_prog")
    motivo = c2.selectbox("Motivo", ["Todos","CNS não encontrado na base de pacientes","CNS ausente ou inválido"], key="nl_motivo")
    busca = c3.text_input("Nome ou CNS", key="nl_busca")

    page_size = 100
    if "nl_page" not in st.session_state:
        st.session_state.nl_page = 0
    a,b,_ = st.columns([1,1,4])
    if a.button("← Anterior", key="nl_prev"):
        st.session_state.nl_page = max(0, st.session_state.nl_page-1)
    if b.button("Próxima →", key="nl_next"):
        st.session_state.nl_page += 1

    rows = rpc("dashboard2_nao_localizados", {
        "p_programa": param(programa), "p_motivo": param(motivo),
        "p_busca": busca.strip() or None, "p_limit": page_size,
        "p_offset": st.session_state.nl_page * page_size,
    }, stop_on_error=False) or []

    total = rows[0].get("total_registros",0) if rows else 0
    st.metric("Pendências encontradas", fmt(total))
    df = pd.DataFrame(rows)
    if df.empty:
        st.success("Nenhuma pendência para os filtros selecionados.")
        return
    if "total_registros" in df.columns:
        df = df.drop(columns=["total_registros"])
    rename = {
        "fonte":"Fonte", "programa_codigo":"Programa", "cns_informado":"CNS informado",
        "nome":"Nome informado", "unidade":"Unidade origem", "data_nascimento_origem":"Nascimento",
        "sexo_origem":"Sexo", "motivo":"Motivo", "sugestao_nome":"Possível nome",
        "sugestao_cns":"Possível CNS", "sugestao_unidade":"Unidade possível", "similaridade":"Similaridade",
    }
    st.dataframe(df.rename(columns=rename), use_container_width=True, hide_index=True, height=520)
    st.info("Use a sugestão apenas para investigação. A correção deve ser feita na fonte/cadastro oficial antes da próxima carga.")


def pagina_administracao():
    st.markdown("## ⚙️ Administração e manutenção")
    st.caption("Área exclusiva para acompanhamento das cargas, qualidade cadastral e preparação da atualização mensal.")

    st.markdown("### 📄 Fonte manual — base mensal")
    st.info(
        "Envie o arquivo FICHA A exportado do VitaCare."
        "Nesta etapa o sistema realiza a validação do arquivo."
        "antes da atualização da base populacional."
    )
    arquivo_vitacare = st.file_uploader("Selecionar arquivo FICHA A do VitaCare", type=["csv"], key="admin_excel_mensal")

    if arquivo_vitacare is not None:
        tamanho_mb = arquivo_vitacare.size / (1024 * 1024)

        st.success(
            f"Arquivo selecionado: {arquivo_vitacare.name} — "
            f"{tamanho_mb:.2f} MB"
        )

        try:
            # Garante que a leitura comece do início do arquivo
            arquivo_vitacare.seek(0)

            preview = pd.read_csv(
                arquivo_vitacare,
                sep=";",
                encoding="latin1",
                dtype=str,
                nrows=20,
                low_memory=False,
            )

            COLUNAS_VITACARE_OBRIGATORIAS = [
                "N_CNS_DA_PESSOA_CADASTRADA",
                "NOME_DA_PESSOA_CADASTRADA",
                "DATA_DE_NASCIMENTO",
                "SEXO",
                "NOME_UNIDADE_DE_SAUDE",
                "NOME_EQUIPE_DE_SAUDE",
                "CODIGO_MICROAREA",
                "SITUACAO_USUARIO",
            ]

            import unicodedata
            import re

            def normalizar_coluna(nome):
                nome = str(nome).strip().upper()

                nome = unicodedata.normalize("NFKD", nome)
                nome = "".join(
                    caractere
                    for caractere in nome
                    if not unicodedata.combining(caractere)
                )

                nome = re.sub(r"[^A-Z0-9]+", "_", nome)
                nome = nome.strip("_")

                return nome

            colunas_encontradas = [
                normalizar_coluna(coluna)
                for coluna in preview.columns
            ]

            colunas_ausentes = [
                coluna
                for coluna in COLUNAS_VITACARE_OBRIGATORIAS
                if normalizar_coluna(coluna) not in colunas_encontradas
            ]

            if colunas_ausentes:
                st.error(
                    "Arquivo incompatível com a FICHA A do VitaCare."
                )

                st.warning(
                    "Colunas obrigatórias não encontradas: "
                    + ", ".join(colunas_ausentes)
                )

                st.stop()

            st.success(
                "✓ Arquivo FICHA A reconhecido e validado com sucesso."
            )

            st.caption(
                "Todas as 8 colunas obrigatórias da base "
                "populacional foram identificadas."
            )

            st.markdown("#### Atualização da base populacional")

            st.info(
                "O arquivo foi validado, mas nenhuma alteração foi "
                "realizada na base até o momento."
            )

            confirmar_atualizacao = st.checkbox(
                "Confirmo que este é o arquivo FICHA A que deverá "
                "substituir a base populacional atual.",
                key="confirmar_atualizacao_vitacare",
            )

            if st.button(
                "Atualizar base populacional",
                type="primary",
                disabled=not confirmar_atualizacao,
                use_container_width=True,
                key="btn_atualizar_base_vitacare",
            ):
                st.session_state["vitacare_confirmado"] = True
            if st.session_state.get("vitacare_confirmado"):
                st.warning(
                    "Confirmação final: a nova FICHA A será utilizada "
                    "para reconstruir a população e recalcular as "
                    "elegibilidades e rastreamentos."
                )

                col1, col2 = st.columns([1, 1])

                with col1:
                    if st.button(
                        "Cancelar",
                        use_container_width=True,
                        key="cancelar_vitacare",
                    ):
                        st.session_state["vitacare_confirmado"] = False
                        st.rerun()

                with col2:
                    if st.button(
                        "Confirmar atualização",
                        type="primary",
                        use_container_width=True,
                        key="confirmar_vitacare",
                    ):
                        st.session_state["vitacare_processar"] = True

            st.dataframe(
                preview,
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                f"Prévia: {len(preview)} linhas · "
                f"{len(preview.columns)} colunas"
            )

        except Exception as e:
            st.error(
                "Não foi possível ler o arquivo VitaCare."
            )
            st.caption(str(e))

    st.divider()
    st.markdown("### ☁️ Fonte automática — Google Sheets")
    st.success("Automação ativa: execução mensal no dia 10, além da execução manual pelo GitHub Actions.")

    st.divider()
    pagina_nao_localizados()

    st.divider()
    st.markdown("### 🕘 Histórico de atualizações")
    historico = rpc("dashboard2_historico_cargas", {"p_limit": 30}, stop_on_error=False) or []
    df = pd.DataFrame(historico)
    if df.empty:
        st.info("Ainda não há histórico disponível.")
    else:
        if "data_hora" in df.columns:
            df["data_hora"] = df["data_hora"].apply(fmt_data_hora)
        rename = {
            "data_hora":"Data/hora", "tipo_carga":"Tipo", "fonte":"Fonte",
            "competencia":"Competência", "registros_lidos":"Lidos",
            "registros_processados":"Processados", "registros_erro":"Ignorados/erros",
            "usuario":"Usuário", "status":"Status", "mensagem":"Mensagem",
        }
        st.dataframe(df.rename(columns=rename), use_container_width=True, hide_index=True, height=420)


# =========================================================
# PAINEL — NAVEGAÇÃO
# =========================================================

header()

pagina = st.session_state.get("pagina_atual", "Visão Geral")


# =========================================================
# VISÃO GERAL
# =========================================================

if pagina == "Visão Geral":

    st.markdown(
        """
    <div class="page-heading">
        <div>
             <div class="page-title">Visão Geral</div>
            <div class="page-description">Monitoramento da população-alvo, situação dos rastreamentos e prioridades para busca ativa.</div>
        </div>
        <span class="page-badge">CAP 2.1</span>
    </div>
    """,
        unsafe_allow_html=True,
)

    atualizacoes_visao_geral()

    resumo = get_resumo(
        u, e, m,
        f_programa,
        s, fl
    )

    cards(resumo)

    left, right = st.columns(2)

    with left:
        status_chart(
            get_status(u, e, m, f_programa),
            "Situação temporal do rastreamento"
        )

    with right:
        fluxo_chart(
            get_fluxo(u, e, m, f_programa),
            "Fluxo operacional atual"
        )

    prog = pd.DataFrame(
        get_programas(u, e, m)
    )

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
            margin=dict(
                l=10,
                r=10,
                t=55,
                b=10
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
            xaxis_title="",
            yaxis_title="Total",
            legend_title="Situação",
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    unidade_chart(
        get_unidades(
            f_programa,
            s,
            fl,
            u
        ),
        "Distribuição por unidade"
    )


# =========================================================
# MAMOGRAFIA
# =========================================================

elif pagina == "Mamografia":

    programa = "mamografia"

    st.info(
        "Mamografia: o painel usa periodicidade de 24 meses, "
        "mas somente uma data comprovada de realização coloca "
        "a pessoa como 'Em dia'. Agendamento confirmado permanece "
        "como fluxo operacional e não como realização."
    )

    resumo = get_resumo(
        u, e, m,
        programa,
        s, fl
    )

    cards(resumo)

    indicadores_operacionais(programa)

    left, right = st.columns(2)

    with left:
        status_chart(
            get_status(
                u, e, m,
                programa
            ),
            "Periodicidade — Mamografia"
        )

    with right:
        fluxo_chart(
            get_fluxo(
                u, e, m,
                programa
            ),
            "Fluxo — Mamografia"
        )

    unidade_chart(
        get_unidades(
            programa,
            s,
            fl,
            u
        ),
        "Mamografia por unidade"
    )

    busca_ativa(
        "mamografia",
        programa
    )


# =========================================================
# COLO DO ÚTERO
# =========================================================

elif pagina == "Colo do Útero":

    programa = "citopatologico"

    st.caption(
        "Citopatológico/PAP: faixa 25–64 anos e referência "
        "de 36 meses para o exame convencional nesta versão "
        "do painel."
    )

    resumo = get_resumo(
        u, e, m,
        programa,
        s, fl
    )

    cards(resumo)

    indicadores_operacionais(programa)

    left, right = st.columns(2)

    with left:
        status_chart(
            get_status(
                u, e, m,
                programa
            ),
            "Periodicidade — Citopatológico"
        )

    with right:
        fluxo_chart(
            get_fluxo(
                u, e, m,
                programa
            ),
            "Fluxo laboratorial — Citopatológico"
        )

    unidade_chart(
        get_unidades(
            programa,
            s,
            fl,
            u
        ),
        "Citopatológico por unidade"
    )

    busca_ativa(
        "citopatologico",
        programa
    )

# =========================================================
# DNA-HPV
# =========================================================

elif pagina == "DNA-HPV":

    programa = "dna_hpv"

    st.info(
        "DNA-HPV: rastreamento da população feminina de 25 a 64 anos. "
        "Resultados negativos permanecem em dia. "
        "Resultados que necessitam acompanhamento são classificados "
        "como Seguimento, preservando a conduta registrada."
    )

    resumo = get_resumo(
        u, e, m,
        programa,
        s, fl
    )

    cards(resumo)

    left, right = st.columns(2)

    with left:
        status_chart(
            get_status(
                u, e, m,
                programa
            ),
            "Situação — DNA-HPV"
        )

    with right:
        fluxo_chart(
            get_fluxo(
                u, e, m,
                programa
            ),
            "Conduta — DNA-HPV"
        )

    unidade_chart(
        get_unidades(
            programa,
            s,
            fl,
            u
        ),
        "DNA-HPV por unidade"
    )

    busca_ativa(
        "dna_hpv",
        programa
    )

# =========================================================
# COLORRETAL
# =========================================================

elif pagina == "Colorretal":

    st.markdown("### Sangue oculto / FIT")

    programa = "sangue_oculto"

    resumo = get_resumo(
        u, e, m,
        programa,
        s, fl
    )

    cards(resumo)

    indicadores_operacionais(programa)

    left, right = st.columns(2)

    with left:
        status_chart(
            get_status(
                u, e, m,
                programa
            ),
            "Periodicidade — Sangue oculto / FIT"
        )

    with right:
        fluxo_chart(
            get_fluxo(
                u, e, m,
                programa
            ),
            "Fluxo laboratorial — Sangue oculto / FIT"
        )

    unidade_chart(
        get_unidades(
            programa,
            s,
            fl,
            u
        ),
        "Sangue oculto / FIT por unidade"
    )

    st.divider()

    st.markdown(
        "### Colonoscopia — seguimento"
    )

    programa_c = "colonoscopia"

    st.caption(
        "Colonoscopia é apresentada como seguimento/indicação, "
        "sem periodicidade populacional fixa no painel."
    )

    resumo_c = get_resumo(
        u, e, m,
        programa_c,
        s, fl
    )

    cards(
        resumo_c,
        colonoscopia=True
    )

    indicadores_operacionais(
        programa_c
    )

    left, right = st.columns(2)

    with left:
        status_chart(
            get_status(
                u, e, m,
                programa_c
            ),
            "Acompanhamento — Colonoscopia"
        )

    with right:
        fluxo_chart(
            get_fluxo(
                u, e, m,
                programa_c
            ),
            "Fluxo — Colonoscopia"
        )


# =========================================================
# BUSCA ATIVA
# =========================================================

elif pagina == "Busca Ativa":

    busca_ativa(
        "geral",
        None
    )


# =========================================================
# ADMINISTRAÇÃO
# =========================================================

elif (
    pagina == "Administração"
    and PERFIL_USUARIO == "admin"
):

    pagina_administracao()


# =========================================================
# RODAPÉ
# =========================================================

st.markdown("---")

st.caption(
    "CAP 2.1 — Rastreamento Oncológico | "
    "Painel operacional para apoio ao monitoramento "
    "e à busca ativa."
)