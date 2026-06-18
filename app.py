import time
import requests
import json
import unicodedata
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
.inc-card.resolved {
    border-left-color: #22c55e;
    opacity: 0.7;
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
.inc-status.dominio { background: #f97316aa; color: #fed7aa; }
.inc-status.extincao { background: #22c55e33; color: #86efac; }
.inc-status.conclusao { background: #22c55e55; color: #bbf7d0; }

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

div[data-testid="stButton"] button {
    background-color: #ff4d4d;
    color: #fff;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 0.45rem 1.2rem;
}
div[data-testid="stButton"] button:hover {
    background-color: #e03c3c;
}

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

# ─── Helpers ───────────────────────────────────────────────────────────────────
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


def send_discord(webhook_url: str, message: str):
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json={"content": message}, timeout=10)
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
    st.session_state.incident_states = {}
if "log" not in st.session_state:
    st.session_state.log = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False


def poll(concelhos: list, webhook_url: str):
    """Consulta a API e actualiza o estado."""
    normalized_targets = [normalize(c) for c in concelhos]
    incidents = get_incidents()
    now = datetime.now().strftime("%H:%M")

    filtered = [
        inc for inc in incidents
        if any(t in normalize(inc.get("concelho", "")) for t in normalized_targets)
    ]
    new_states = {str(inc["id"]): inc for inc in filtered}
    old_states = st.session_state.incident_states

    # Novos incidentes
    for iid, inc in new_states.items():
        if iid not in old_states:
            msg = format_new(inc)
            st.session_state.log.insert(0, {"type": "new", "time": now, "msg": msg, "inc": inc})
            send_discord(webhook_url, msg)

    # Mudanças de estado
    for iid, inc in new_states.items():
        if iid in old_states:
            old_s = old_states[iid].get("status")
            new_s = inc.get("status")
            if old_s != new_s:
                msg = format_status(inc, old_s, new_s, now)
                st.session_state.log.insert(0, {"type": "status", "time": now, "msg": msg, "inc": inc})
                send_discord(webhook_url, msg)

    # Resolvidos
    for iid, inc in old_states.items():
        if iid not in new_states and inc.get("status") not in ["Extinção", "Conclusão"]:
            msg = format_resolved(inc, now)
            st.session_state.log.insert(0, {"type": "resolved", "time": now, "msg": msg, "inc": inc})
            send_discord(webhook_url, msg)

    st.session_state.incident_states = new_states
    st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
    # Limitar log a 200 entradas
    st.session_state.log = st.session_state.log[:200]


# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configurações")

    webhook_url = st.text_input(
        "Discord Webhook URL",
        type="password",
        placeholder="https://discord.com/api/webhooks/...",
        help="Opcional — se vazio as notificações Discord estão desativadas.",
    )

    st.markdown("**Concelhos monitorizados**")
    selected = []
    for c in CONCELHOS_ALVO_DEFAULT:
        if st.checkbox(c, value=True, key=f"cb_{c}"):
            selected.append(c)

    custom = st.text_input(
        "Adicionar concelho (separado por vírgulas)",
        placeholder="ex: Chaves, Valpaços",
    )
    if custom:
        for item in custom.split(","):
            item = item.strip()
            if item and item not in selected:
                selected.append(item)

    st.divider()
    refresh_interval = st.select_slider(
        "Intervalo de atualização (s)",
        options=[10, 15, 30, 60, 120],
        value=30,
    )
    auto = st.toggle("Auto-atualização", value=st.session_state.auto_refresh)
    st.session_state.auto_refresh = auto

    st.divider()
    if st.button("🔄 Atualizar agora", use_container_width=True):
        poll(selected, webhook_url)
        st.rerun()

    if st.button("🗑️ Limpar registo", use_container_width=True):
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
active = st.session_state.incident_states
total_ops = sum(int(i.get("man", 0) or 0) for i in active.values())
total_trucks = sum(int(i.get("terrain", 0) or 0) for i in active.values())
total_aerial = sum(int(i.get("aerial", 0) or 0) for i in active.values())

m1, m2, m3, m4 = st.columns(4)
for col, val, label in [
    (m1, len(active), "Incêndios ativos"),
    (m2, total_ops, "Operacionais"),
    (m3, total_trucks, "Veículos"),
    (m4, total_aerial, "Meios aéreos"),
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
        sc = status_class(inc.get("status", ""))
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
    st.info("Nenhum evento registado nesta sessão.")
else:
    for entry in st.session_state.log[:50]:
        icon = {"new": "🔥", "status": "🔄", "resolved": "✅"}.get(entry["type"], "ℹ️")
        with st.expander(f"{icon} [{entry['time']}] {entry['inc'].get('location','N/A')} — {entry['inc'].get('concelho','N/A')}"):
            st.code(entry["msg"], language=None)

# ─── Auto-refresh ──────────────────────────────────────────────────────────────
if st.session_state.auto_refresh:
    time.sleep(refresh_interval)
    poll(selected, webhook_url)
    st.rerun()
