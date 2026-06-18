import time
import requests
import unicodedata
import json
import base64
from datetime import datetime
import streamlit as st

# ─── Configuração da Página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitor de Incêndios — TTM",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background-color: #0f1117;
    color: #e8eaf0;
    font-family: 'Inter', sans-serif;
}
[data-testid="stSidebar"] {
    background-color: #161b27;
    border-right: 1px solid #1e2535;
}
.metric-card {
    background: #161b27;
    border: 1px solid #1e2535;
    border-radius: 10px;
    padding: 18px 22px;
    text-align: center;
}
.metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2.2rem;
    font-weight: 700;
    color: #ff4d4d;
    line-height: 1;
}
.metric-label {
    font-size: 0.78rem;
    color: #7a8099;
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.inc-card {
    background: #161b27;
    border: 1px solid #1e2535;
    border-left: 4px solid #ff4d4d;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 14px;
}
.inc-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 10px;
}
.inc-title {
    font-size: 1rem;
    font-weight: 600;
    color: #ffffff;
}
.inc-status {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    background: #ff4d4d22;
    color: #ff7070;
    white-space: nowrap;
}
.inc-status.dominio  { background: #f97316aa; color: #fed7aa; }
.inc-status.extincao { background: #22c55e33; color: #86efac; }
.inc-status.conclusao{ background: #22c55e55; color: #bbf7d0; }
.inc-meta {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 8px;
    font-size: 0.82rem;
}
.meta-item { color: #9aa3b8; }
.meta-item span { color: #cbd5e1; font-weight: 500; }
.badge-aerial { color: #60a5fa; }
.badge-men    { color: #f472b6; }
.badge-truck  { color: #fb923c; }
.timestamp-bar {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #4b5568;
    text-align: right;
    margin-bottom: 8px;
}
.status-badge {
    font-size: 0.78rem;
    padding: 6px 12px;
    border-radius: 6px;
    margin-bottom: 8px;
    text-align: center;
}
.badge-ok  { background: #22c55e22; color: #86efac; border: 1px solid #22c55e44; }
.badge-off { background: #ff4d4d22; color: #fca5a5; border: 1px solid #ff4d4d44; }
.badge-warn{ background: #f9731622; color: #fed7aa; border: 1px solid #f9731644; }
div[data-testid="stButton"] button {
    background-color: #ff4d4d;
    color: #fff;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 0.45rem 1.2rem;
}
div[data-testid="stButton"] button:hover { background-color: #e03c3c; }
h1 { font-size: 1.5rem !important; font-weight: 700 !important; color: #fff !important; }
h2 { font-size: 1.1rem !important; font-weight: 600 !important; color: #cbd5e1 !important; margin-top: 1.4rem !important; }
</style>
""", unsafe_allow_html=True)

# ─── Constantes ────────────────────────────────────────────────────────────────
API_URL = "https://api.fogos.pt/v2/incidents/active"

CONCELHOS_ALVO_DEFAULT = [
    "Alfândega da Fé",
    "Bragança",
    "Macedo de Cavaleiros",
    "Miranda do Douro",
    "Mirandela",
    "Mogadouro",
    "Vila Flor",
    "Vimioso",
    "Vinhais",
]

# ─── Secrets ───────────────────────────────────────────────────────────────────
WEBHOOK_URL:  str = st.secrets.get("DISCORD_WEBHOOK_URL", "")
GH_TOKEN:     str = st.secrets.get("GITHUB_TOKEN", "")
GH_REPO:      str = st.secrets.get("GITHUB_REPO", "")        # ex: "utilizador/repositorio"
GH_LOG_PATH:  str = st.secrets.get("GITHUB_LOG_PATH", "data/incident_log.json")
GH_STATE_PATH:str = st.secrets.get("GITHUB_STATE_PATH", "data/incident_states.json")

GITHUB_API = "https://api.github.com"


# ─── GitHub helpers ────────────────────────────────────────────────────────────
def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def gh_read(path: str) -> tuple[any, str | None]:
    """
    Lê um ficheiro JSON do repositório.
    Devolve (conteúdo_parsed, sha) ou (valor_default, None) se não existir.
    """
    if not GH_TOKEN or not GH_REPO:
        return None, None
    url = f"{GITHUB_API}/repos/{GH_REPO}/contents/{path}"
    try:
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data = r.json()
        content = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
        return content, data["sha"]
    except Exception:
        return None, None


def gh_write(path: str, content: any, sha: str | None, commit_msg: str) -> bool:
    """
    Cria ou actualiza um ficheiro JSON no repositório.
    sha=None cria o ficheiro; sha=<valor> actualiza.
    """
    if not GH_TOKEN or not GH_REPO:
        return False
    url = f"{GITHUB_API}/repos/{GH_REPO}/contents/{path}"
    payload = {
        "message": commit_msg,
        "content": base64.b64encode(
            json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8"),
    }
    if sha:
        payload["sha"] = sha
    try:
        r = requests.put(url, headers=_gh_headers(), json=payload, timeout=15)
        r.raise_for_status()
        return True
    except Exception:
        return False


def github_configured() -> bool:
    return bool(GH_TOKEN and GH_REPO)


# ─── Helpers gerais ────────────────────────────────────────────────────────────
def normalize(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().strip().lower()


def get_incidents() -> list:
    try:
        r = requests.get(API_URL, timeout=15)
        r.raise_for_status()
        return r.json().get("data", [])
    except requests.RequestException:
        return []


def status_class(status: str) -> str:
    s = (status or "").lower()
    if "domínio" in s or "dominio" in s:
        return "dominio"
    if "extinção" in s or "extincao" in s:
        return "extincao"
    if "conclusão" in s or "conclusao" in s:
        return "conclusao"
    return ""


def send_discord(message: str):
    if not WEBHOOK_URL:
        return
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
    except requests.RequestException:
        pass


def format_new(inc: dict) -> str:
    loc = inc.get("distrito") or inc.get("concelho") or inc.get("location") or "N/A"
    return (
        f"🔥 **Novo incêndio em {loc}**\n"
        f"🏘️ **Local** ▶ {inc.get('location','N/A')}\n"
        f"🏡 **Concelho** ▶ {inc.get('concelho','N/A')}\n"
        f"🏠 **Freguesia** ▶ {inc.get('freguesia','N/A')}\n"
        f"🏞️ **Natureza** ▶ {inc.get('natureza','N/A')}\n"
        f"🕒 **Início** ▶ {inc.get('date','N/A')} {inc.get('hour','')}\n"
        f"📊 **Estado** ▶ {inc.get('status','N/A')}\n"
        f"👩‍🚒 **Operacionais** ▶ {inc.get('man',0)}\n"
        f"🚒 **Veículos** ▶ {inc.get('terrain',0)}\n"
        f"✈️ **Meios Aéreos** ▶ {inc.get('aerial',0)}\n"
        f"🆔 **ID** ▶ {inc.get('id')}\n"
        f"📍 https://www.google.com/maps/search/?api=1&query={inc.get('lat','')},{inc.get('lng','')}"
    )


def format_status(inc: dict, old_s: str, new_s: str, now: str) -> str:
    return (
        f"🔄 **Estado alterado — {inc.get('concelho','N/A')}, {inc.get('freguesia','N/A')}**\n"
        f"📊 `{old_s}` → `{new_s}` às {now}\n"
        f"👩‍🚒 {inc.get('man',0)} operacionais · 🚒 {inc.get('terrain',0)} veículos · ✈️ {inc.get('aerial',0)} aéreos\n"
        f"🆔 {inc.get('id','N/A')}"
    )


def format_resolved(inc: dict, now: str) -> str:
    return (
        f"✅ **Incêndio extinto — {inc.get('location','N/A')} às {now}**\n"
        f"🆔 {inc.get('id','N/A')}"
    )


# ─── Estado da Sessão ──────────────────────────────────────────────────────────
if "incident_states" not in st.session_state:
    # Ao arrancar, tenta carregar o estado guardado no GitHub
    saved, sha = gh_read(GH_STATE_PATH)
    st.session_state.incident_states     = saved if isinstance(saved, dict) else {}
    st.session_state.incident_states_sha = sha

if "log" not in st.session_state:
    # Ao arrancar, tenta carregar o log persistido no GitHub
    saved_log, log_sha = gh_read(GH_LOG_PATH)
    st.session_state.log     = saved_log if isinstance(saved_log, list) else []
    st.session_state.log_sha = log_sha

if "last_refresh"     not in st.session_state: st.session_state.last_refresh     = None
if "auto_refresh"     not in st.session_state: st.session_state.auto_refresh     = True
if "refresh_interval" not in st.session_state: st.session_state.refresh_interval = 30
if "selected_concelhos" not in st.session_state:
    st.session_state.selected_concelhos = list(CONCELHOS_ALVO_DEFAULT)


# ─── Poll principal ────────────────────────────────────────────────────────────
def poll():
    concelhos    = st.session_state.selected_concelhos
    normalized_t = [normalize(c) for c in concelhos]
    incidents    = get_incidents()
    now          = datetime.now().strftime("%H:%M")
    ts           = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    filtered   = [
        inc for inc in incidents
        if any(t in normalize(inc.get("concelho", "")) for t in normalized_t)
    ]
    new_states = {str(inc["id"]): inc for inc in filtered}
    old_states = st.session_state.incident_states
    new_entries = []

    # Novos incidentes
    for iid, inc in new_states.items():
        if iid not in old_states:
            msg = format_new(inc)
            entry = {"type": "new", "time": now, "timestamp": ts, "msg": msg, "inc": inc}
            new_entries.append(entry)
            send_discord(msg)

    # Mudanças de estado
    for iid, inc in new_states.items():
        if iid in old_states:
            old_s = old_states[iid].get("status")
            new_s = inc.get("status")
            if old_s != new_s:
                msg = format_status(inc, old_s, new_s, now)
                entry = {"type": "status", "time": now, "timestamp": ts, "msg": msg, "inc": inc}
                new_entries.append(entry)
                send_discord(msg)

    # Resolvidos
    for iid, inc in old_states.items():
        if iid not in new_states and inc.get("status") not in ["Extinção", "Conclusão"]:
            msg = format_resolved(inc, now)
            entry = {"type": "resolved", "time": now, "timestamp": ts, "msg": msg, "inc": inc}
            new_entries.append(entry)
            send_discord(msg)

    # Actualiza session_state
    st.session_state.incident_states = new_states
    st.session_state.last_refresh    = datetime.now().strftime("%H:%M:%S")

    if new_entries:
        st.session_state.log = new_entries + st.session_state.log
        st.session_state.log = st.session_state.log[:500]

        # ── Persistir log no GitHub ──────────────────────────────────────────
        if github_configured():
            ok = gh_write(
                GH_LOG_PATH,
                st.session_state.log,
                st.session_state.get("log_sha"),
                f"chore: {len(new_entries)} novo(s) evento(s) — {ts}",
            )
            if ok:
                # Actualizar sha para o próximo write não falhar com conflito
                _, new_sha = gh_read(GH_LOG_PATH)
                st.session_state.log_sha = new_sha

    # ── Persistir estado activo no GitHub (sempre, para sobreviver a restarts) ──
    if github_configured():
        ok = gh_write(
            GH_STATE_PATH,
            st.session_state.incident_states,
            st.session_state.get("incident_states_sha"),
            f"chore: estado atualizado — {ts}",
        )
        if ok:
            _, new_sha = gh_read(GH_STATE_PATH)
            st.session_state.incident_states_sha = new_sha


# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configurações")

    if WEBHOOK_URL:
        st.markdown('<div class="status-badge badge-ok">✅ Discord configurado</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-badge badge-off">⚠️ Discord não configurado</div>', unsafe_allow_html=True)

    if github_configured():
        st.markdown(f'<div class="status-badge badge-ok">✅ GitHub: <code>{GH_REPO}</code></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-badge badge-warn">⚠️ GitHub não configurado<br><small>Registo não será persistido</small></div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("**Concelhos monitorizados**")
    selected = []
    for c in CONCELHOS_ALVO_DEFAULT:
        if st.checkbox(c, value=True, key=f"cb_{c}"):
            selected.append(c)

    custom = st.text_input("Adicionar concelho", placeholder="ex: Chaves, Valpaços")
    if custom:
        for item in custom.split(","):
            item = item.strip()
            if item and item not in selected:
                selected.append(item)

    st.session_state.selected_concelhos = selected

    st.divider()
    st.session_state.refresh_interval = st.select_slider(
        "Intervalo de atualização (s)",
        options=[10, 15, 30, 60, 120],
        value=st.session_state.refresh_interval,
    )
    st.session_state.auto_refresh = st.toggle(
        "Auto-atualização",
        value=st.session_state.auto_refresh,
    )

    st.divider()
    if st.button("🔄 Atualizar agora", use_container_width=True):
        poll()
        st.rerun()

    if st.button("🗑️ Limpar registo local", use_container_width=True):
        st.session_state.log = []
        st.rerun()

# ─── Cabeçalho ─────────────────────────────────────────────────────────────────
col_title, col_time = st.columns([3, 1])
with col_title:
    st.markdown("# 🔥 Monitor de Incêndios — Terras de Trás-os-Montes")
with col_time:
    if st.session_state.last_refresh:
        st.markdown(
            f'<div class="timestamp-bar">Última atualização: {st.session_state.last_refresh}</div>',
            unsafe_allow_html=True,
        )

# ─── Métricas ──────────────────────────────────────────────────────────────────
active       = st.session_state.incident_states
total_ops    = sum(int(i.get("man",     0) or 0) for i in active.values())
total_trucks = sum(int(i.get("terrain", 0) or 0) for i in active.values())
total_aerial = sum(int(i.get("aerial",  0) or 0) for i in active.values())

m1, m2, m3, m4 = st.columns(4)
for col, val, label in [
    (m1, len(active),    "Incêndios ativos"),
    (m2, total_ops,      "Operacionais"),
    (m3, total_trucks,   "Veículos"),
    (m4, total_aerial,   "Meios aéreos"),
]:
    col.markdown(
        f'<div class="metric-card"><div class="metric-value">{val}</div>'
        f'<div class="metric-label">{label}</div></div>',
        unsafe_allow_html=True,
    )

# ─── Incêndios Ativos ──────────────────────────────────────────────────────────
st.markdown("## Incêndios ativos")
if not active:
    st.info("Nenhum incêndio ativo nos concelhos monitorizados.")
else:
    for iid, inc in sorted(active.items(), key=lambda x: x[1].get("date", ""), reverse=True):
        sc       = status_class(inc.get("status", ""))
        maps_url = f"https://www.google.com/maps/search/?api=1&query={inc.get('lat','')},{inc.get('lng','')}"
        st.markdown(f"""
<div class="inc-card">
  <div class="inc-header">
    <div class="inc-title">📍 {inc.get('location','N/A')} — {inc.get('concelho','N/A')}</div>
    <div class="inc-status {sc}">{inc.get('status','N/A')}</div>
  </div>
  <div class="inc-meta">
    <div class="meta-item">🏠 Freguesia: <span>{inc.get('freguesia','N/A')}</span></div>
    <div class="meta-item">🏞️ Natureza: <span>{inc.get('natureza','N/A')}</span></div>
    <div class="meta-item">🕒 Início: <span>{inc.get('date','N/A')} {inc.get('hour','')}</span></div>
    <div class="meta-item badge-men">👩‍🚒 Operacionais: <span>{inc.get('man',0)}</span></div>
    <div class="meta-item badge-truck">🚒 Veículos: <span>{inc.get('terrain',0)}</span></div>
    <div class="meta-item badge-aerial">✈️ Meios aéreos: <span>{inc.get('aerial',0)}</span></div>
    <div class="meta-item">🆔 ID: <span>{iid}</span></div>
    <div class="meta-item"><a href="{maps_url}" target="_blank" style="color:#60a5fa;">📌 Ver no mapa</a></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Registo de Eventos ────────────────────────────────────────────────────────
st.markdown("## Registo de eventos")
if not st.session_state.log:
    st.info("Nenhum evento registado.")
else:
    for entry in st.session_state.log[:100]:
        icon = {"new": "🔥", "status": "🔄", "resolved": "✅"}.get(entry["type"], "ℹ️")
        ts_label = entry.get("timestamp", entry.get("time", ""))
        with st.expander(
            f"{icon} [{ts_label}] {entry['inc'].get('location','N/A')} — {entry['inc'].get('concelho','N/A')}"
        ):
            st.code(entry["msg"], language=None)

# ─── Auto-refresh ──────────────────────────────────────────────────────────────
if st.session_state.auto_refresh:
    time.sleep(st.session_state.refresh_interval)
    poll()
    st.rerun()
