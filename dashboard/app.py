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
    "Em dia": "#2E7D32",
    "Vence em até 90 dias": "#D79B00",
    "Em atraso": "#E67E22",
    "Sem registro de realização": "#7A8691",
    "Seguimento": "#546E7A",
}

FLUXO_COLORS = {
    "Agendado": "#1976D2",
    "Confirmado": "#1565C0",
    "Falta - Reconvocar": "#C62828",
    "Pendente regulação": "#F39C12",
    "Cancelado": "#78909C",
    "Devolvido": "#8E24AA",
    "Reenviado": "#6A1B9A",
    "Negado": "#455A64",
    "Resultado entregue": "#2E7D32",
    "Resultado alterado": "#C62828",
    "Em processamento": "#0288D1",
    "Coletado - aguardando laboratório": "#5E35B1",
    "Sem movimentação": "#90A4AE",
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
    .rio-title {{ font-size: 1.72rem; font-weight: 750; line-height: 1.15; margin: 0; }}
    .rio-subtitle {{ font-size: .92rem; margin-top: 6px; opacity: .92; }}
    .section-title {{ font-size: 1.15rem; font-weight: 700; color: {RIO_NAVY}; margin: 14px 0 4px 0; }}
    .section-note {{ font-size: .84rem; color: {RIO_MUTED}; margin-bottom: 12px; }}
    [data-testid="stMetric"] {{
        background: white;
        border: 1px solid {RIO_BORDER};
        border-radius: 10px;
        padding: 12px 14px;
        box-shadow: 0 1px 4px rgba(0,0,0,.035);
    }}
    [data-testid="stMetricValue"] {{ color: {RIO_NAVY}; font-weight: 750; }}
    div[data-baseweb="tab-list"] {{
        gap: 4px; background: white; border: 1px solid {RIO_BORDER};
        padding: 4px; border-radius: 10px;
    }}
    button[data-baseweb="tab"] {{ font-weight: 650; border-radius: 7px; }}
    .login-box {{ max-width: 520px; margin: 55px auto 0 auto; }}
    div.stButton > button[kind="primary"], div[data-testid="stLinkButton"] a {{
        background: #005CA9 !important; color: white !important; border-color: #005CA9 !important;
    }}
    div.stButton > button[kind="primary"]:hover, div[data-testid="stLinkButton"] a:hover {{
        background: #004A87 !important; color: white !important; border-color: #004A87 !important;
    }}
    .metric-card {{
        background: white; border: 1px solid #D9E2E8; border-left: 6px solid #8A9BA8;
        border-radius: 10px; padding: 14px 14px 12px 14px; min-height: 108px;
        box-shadow: 0 1px 4px rgba(0,0,0,.035);
    }}
    .metric-card.neutral {{ border-left-color: #5B7083; }}
    .metric-card.success {{ border-left-color: #2E7D32; background: #F1F8F2; }}
    .metric-card.warning {{ border-left-color: #D79B00; background: #FFF9E8; }}
    .metric-card.info {{ border-left-color: #1976D2; background: #EEF5FC; }}
    .metric-card.danger {{ border-left-color: #C62828; background: #FDEEEE; }}
    .metric-label {{ color: #667985; font-size: .80rem; font-weight: 700; line-height: 1.2; margin-bottom: 6px; }}
    .metric-value {{ color: #17365D; font-size: 1.70rem; font-weight: 800; line-height: 1.05; }}
    .metric-percent {{ margin-top: 7px; font-size: .86rem; font-weight: 750; color: #405565; }}
    .update-strip {{
        display:grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap:10px;
        margin: 4px 0 16px 0;
    }}
    .update-card {{
        background:white; border:1px solid #D9E2E8; border-radius:10px; padding:12px 14px;
    }}
    .update-label {{ font-size:.78rem; color:#667985; font-weight:700; }}
    .update-value {{ font-size:.98rem; color:#17365D; font-weight:750; margin-top:3px; }}
    .update-detail {{ font-size:.78rem; color:#667985; margin-top:3px; }}
    @media (max-width: 700px) {{ .update-strip {{ grid-template-columns:1fr; }} }}
    footer {{ visibility: hidden; }}
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
            <div class="rio-title">CAP 2.1 — Rastreamento Oncológico</div>
            <div class="rio-subtitle">Monitoramento de elegibilidade, periodicidade, fluxo operacional e busca ativa</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
            st.link_button("Entrar com Google", oauth_result.url, use_container_width=True, type="primary")
    except Exception as e:
        st.error("Não foi possível iniciar o login com Google.")
        st.caption(str(e))
    st.markdown("</div>", unsafe_allow_html=True)
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
    equipes = ["Todos"] + list(filtros.get("equipes", []))
    microareas = ["Todos"] + list(filtros.get("microareas", []))

    programa_map = {"Todos": None}
    for p in filtros.get("programas", []):
        if isinstance(p, dict):
            programa_map[p.get("nome") or p.get("codigo")] = p.get("codigo")

    status_list = ["Todos"] + list(filtros.get("status", []))
    fluxo_list = ["Todos"] + list(filtros.get("fluxos", []))

    if PERFIL_USUARIO == "unidade":
        if not UNIDADE_USUARIO:
            st.error("Seu perfil de unidade não possui uma unidade vinculada.")
            st.stop()
        st.text_input("Unidade", value=UNIDADE_USUARIO, disabled=True)
        f_unidade = UNIDADE_USUARIO
    else:
        f_unidade = st.selectbox("Unidade", ["Todos"] + unidades_disponiveis)

    f_equipe = st.selectbox("Equipe", equipes)
    f_micro = st.selectbox("Microárea", microareas)
    f_programa_nome = st.selectbox("Programa", list(programa_map.keys()))
    f_status = st.selectbox("Situação do rastreamento", status_list)
    f_fluxo = st.selectbox("Fluxo operacional", fluxo_list)
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
    if colonoscopia:
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: metric_card("Pessoas acompanhadas", resumo.get("pessoas_unicas"), "neutral")
        with c2: metric_card("Registros", resumo.get("elegibilidades"), "neutral")
        with c3: metric_card("Agendados + confirmados", int(resumo.get("agendados") or 0) + int(resumo.get("confirmados") or 0), "info")
        with c4: metric_card("Falta - Reconvocar", resumo.get("faltas"), "danger")
        with c5: metric_card("Pendente regulação", resumo.get("pendente_regulacao"), "warning")
        return

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: metric_card("Pessoas únicas", resumo.get("pessoas_unicas"), "neutral")
    with c2: metric_card("Elegibilidades", resumo.get("elegibilidades"), "neutral")
    with c3: metric_card("Em dia", resumo.get("em_dia"), "success", pct(resumo.get("em_dia"), total))
    with c4: metric_card("Vence em 90 dias", resumo.get("vence_90"), "warning", pct(resumo.get("vence_90"), total))
    with c5: metric_card("Em atraso", resumo.get("em_atraso"), "danger", pct(resumo.get("em_atraso"), total))
    with c6: metric_card("Busca ativa", resumo.get("busca_ativa"), "danger", pct(resumo.get("busca_ativa"), total))

    c7, c8, c9, c10 = st.columns(4)
    with c7: metric_card("Sem registro de realização", resumo.get("sem_registro"), "neutral", pct(resumo.get("sem_registro"), total))
    with c8: metric_card("Agendados", resumo.get("agendados"), "info")
    with c9: metric_card("Confirmados", resumo.get("confirmados"), "info")
    with c10: metric_card("Falta - Reconvocar", resumo.get("faltas"), "danger")


def status_chart(rows, titulo):
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return
    fig = px.bar(df, x="status_rastreamento", y="total", color="status_rastreamento",
                 text="total", color_discrete_map=STATUS_COLORS, title=titulo)
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False, margin=dict(l=10,r=10,t=55,b=10),
                      paper_bgcolor="white", plot_bgcolor="white", xaxis_title="", yaxis_title="Total")
    st.plotly_chart(fig, use_container_width=True)


def fluxo_chart(rows, titulo):
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Sem movimentação operacional para os filtros selecionados.")
        return
    fig = px.bar(df, x="total", y="status_fluxo", orientation="h", color="status_fluxo",
                 text="total", color_discrete_map=FLUXO_COLORS, title=titulo)
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False, margin=dict(l=10,r=20,t=55,b=10),
                      paper_bgcolor="white", plot_bgcolor="white", xaxis_title="Total", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)


def unidade_chart(rows, titulo):
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return
    df = df.sort_values("total")
    fig = px.bar(df, x="total", y="unidade", orientation="h", text="total",
                 title=titulo, color_discrete_sequence=[RIO_BLUE])
    fig.update_traces(textposition="outside")
    fig.update_layout(margin=dict(l=10,r=20,t=55,b=10), paper_bgcolor="white",
                      plot_bgcolor="white", xaxis_title="Total", yaxis_title="")
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
    st.markdown('<div class="section-title">Busca ativa nominal</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">Situação temporal e fluxo operacional aparecem separados. Agendamento confirmado não equivale a realização.</div>',
        unsafe_allow_html=True,
    )

    busca = st.text_input("Buscar por nome ou CNS", key=f"busca_{chave}", placeholder="Digite parte do nome ou CNS")
    page_size = st.selectbox("Registros por página", [50,100,250,500], index=1, key=f"ps_{chave}")
    page_key = f"page_{chave}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    col_a, col_b, _ = st.columns([1,1,4])
    with col_a:
        if st.button("← Anterior", key=f"prev_{chave}"):
            st.session_state[page_key] = max(0, st.session_state[page_key]-1)
    with col_b:
        if st.button("Próxima →", key=f"next_{chave}"):
            st.session_state[page_key] += 1

    page = st.session_state[page_key]
    rows = rpc("dashboard2_busca", {
        "p_busca": busca.strip() or None,
        "p_unidade": u, "p_equipe": e, "p_microarea": m,
        "p_programa": programa_forcado or f_programa,
        "p_status": s, "p_fluxo": fl,
        "p_limit": page_size, "p_offset": page * page_size,
    }) or []

    total = rows[0].get("total_registros",0) if rows else 0
    st.caption(f"Página {page+1} · {fmt(total)} registro(s) encontrado(s)")
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Nenhum registro encontrado.")
        return
    if "total_registros" in df.columns:
        df = df.drop(columns=["total_registros"])

    rename = {
        "nome":"Nome", "cns":"CNS", "idade":"Idade", "unidade":"Unidade",
        "equipe":"Equipe", "microarea":"Microárea", "programa":"Programa",
        "status_rastreamento":"Situação do rastreamento", "status_fluxo":"Fluxo operacional",
        "data_ultima_realizacao":"Última realização", "data_proxima_referencia":"Próxima referência",
        "dias_para_vencer":"Dias para vencer", "data_agendamento":"Agendamento",
        "data_solicitacao":"Solicitação", "situacao":"Situação origem", "risco":"Risco",
    }
    cols = [c for c in [
        "nome","cns","idade","unidade","equipe","microarea","programa",
        "status_rastreamento","status_fluxo","data_ultima_realizacao",
        "data_proxima_referencia","dias_para_vencer","data_agendamento",
        "data_solicitacao","risco"
    ] if c in df.columns]
    st.dataframe(df[cols].rename(columns=rename), use_container_width=True, hide_index=True, height=520)


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
        "O upload abaixo continua em modo de validação. A atualização manual efetiva é registrada quando a rotina local de sincronização é executada."
    )
    arquivo_excel = st.file_uploader("Selecionar planilha mensal", type=["xlsx","xls"], key="admin_excel_mensal")
    if arquivo_excel is not None:
        tamanho_mb = arquivo_excel.size/(1024*1024)
        st.success(f"Arquivo selecionado: {arquivo_excel.name} — {tamanho_mb:.2f} MB")
        try:
            preview = pd.read_excel(arquivo_excel, nrows=20)
            st.dataframe(preview, use_container_width=True, hide_index=True)
            st.caption(f"Prévia: {len(preview)} linhas · {len(preview.columns)} colunas")
        except Exception as e:
            st.error("Não foi possível ler a planilha selecionada.")
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
# PAINEL
# =========================================================
header()

nomes_abas = ["Visão Geral", "Mamografia", "Colo do Útero", "Colorretal", "Busca Ativa"]
if PERFIL_USUARIO == "admin":
    nomes_abas.append("⚙️ Administração")
tabs = st.tabs(nomes_abas)

with tabs[0]:
    atualizacoes_visao_geral()
    resumo = get_resumo(u,e,m,f_programa,s,fl)
    cards(resumo)

    left,right = st.columns(2)
    with left:
        status_chart(get_status(u,e,m,f_programa), "Situação temporal do rastreamento")
    with right:
        fluxo_chart(get_fluxo(u,e,m,f_programa), "Fluxo operacional atual")

    prog = pd.DataFrame(get_programas(u,e,m))
    if not prog.empty:
        fig = px.bar(prog, x="programa", y="total", color="status_rastreamento",
                     color_discrete_map=STATUS_COLORS, title="Situação por programa")
        fig.update_layout(margin=dict(l=10,r=10,t=55,b=10), paper_bgcolor="white",
                          plot_bgcolor="white", xaxis_title="", yaxis_title="Total", legend_title="Situação")
        st.plotly_chart(fig, use_container_width=True)

    unidade_chart(get_unidades(f_programa,s,fl,u), "Distribuição por unidade")

with tabs[1]:
    programa = "mamografia"
    st.info(
        "Mamografia: o painel usa periodicidade de 24 meses, mas somente uma data comprovada de realização coloca a pessoa 'Em dia'. "
        "Agendamento confirmado permanece como fluxo operacional e não como realização."
    )
    resumo = get_resumo(u,e,m,programa,s,fl)
    cards(resumo)
    indicadores_operacionais(programa)
    left,right = st.columns(2)
    with left: status_chart(get_status(u,e,m,programa), "Periodicidade — Mamografia")
    with right: fluxo_chart(get_fluxo(u,e,m,programa), "Fluxo — Mamografia")
    unidade_chart(get_unidades(programa,s,fl,u), "Mamografia por unidade")
    busca_ativa("mamografia", programa)

with tabs[2]:
    programa = "citopatologico"
    st.caption("Citopatológico/PAP: faixa 25–64 anos e referência de 36 meses para o exame convencional nesta versão do painel.")
    resumo = get_resumo(u,e,m,programa,s,fl)
    cards(resumo)
    indicadores_operacionais(programa)
    left,right = st.columns(2)
    with left: status_chart(get_status(u,e,m,programa), "Periodicidade — Citopatológico")
    with right: fluxo_chart(get_fluxo(u,e,m,programa), "Fluxo laboratorial — Citopatológico")
    unidade_chart(get_unidades(programa,s,fl,u), "Citopatológico por unidade")
    busca_ativa("citopatologico", programa)

with tabs[3]:
    st.markdown("### Sangue oculto / FIT")
    programa = "sangue_oculto"
    resumo = get_resumo(u,e,m,programa,s,fl)
    cards(resumo)
    indicadores_operacionais(programa)
    left,right = st.columns(2)
    with left: status_chart(get_status(u,e,m,programa), "Periodicidade — Sangue oculto / FIT")
    with right: fluxo_chart(get_fluxo(u,e,m,programa), "Fluxo laboratorial — Sangue oculto / FIT")
    unidade_chart(get_unidades(programa,s,fl,u), "Sangue oculto / FIT por unidade")

    st.divider()
    st.markdown("### Colonoscopia — seguimento")
    programa_c = "colonoscopia"
    st.caption("Colonoscopia é apresentada como seguimento/indicação, sem periodicidade populacional fixa no painel.")
    resumo_c = get_resumo(u,e,m,programa_c,s,fl)
    cards(resumo_c, colonoscopia=True)
    indicadores_operacionais(programa_c)
    left,right = st.columns(2)
    with left: status_chart(get_status(u,e,m,programa_c), "Acompanhamento — Colonoscopia")
    with right: fluxo_chart(get_fluxo(u,e,m,programa_c), "Fluxo — Colonoscopia")

with tabs[4]:
    busca_ativa("geral", None)

if PERFIL_USUARIO == "admin" and len(tabs) > 5:
    with tabs[5]:
        pagina_administracao()

st.caption("CAP 2.1 — Rastreamento Oncológico | Painel operacional para apoio ao monitoramento e à busca ativa.")
