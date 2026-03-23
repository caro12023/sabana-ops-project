import streamlit as st
import pandas as pd
import time
from datetime import datetime
import io
from fpdf import FPDF
import pytz

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sabana Queuing Pro", layout="wide", page_icon="🦅")
BOGOTA_TZ = pytz.timezone('America/Bogota')

# --- ESTILOS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-card { border-radius: 12px; border: 1px solid #cbd5e1; background-color: white; padding: 20px; }
    .nav-btn button { height: 60px !important; font-size: 20px !important; font-weight: bold !important; border-radius: 12px !important; }
    </style>
""", unsafe_allow_html=True)

# --- MEMORIA ---
if 'history' not in st.session_state: st.session_state.history = [] 
if 'active_session' not in st.session_state: st.session_state.active_session = None 
if 'customers' not in st.session_state: st.session_state.customers = [] 
if 'counter' not in st.session_state: st.session_state.counter = 1
if 'max_q' not in st.session_state: st.session_state.max_q = 0
if 'view' not in st.session_state: st.session_state.view = "Table"
if 'viewing_hist_dash' not in st.session_state: st.session_state.viewing_hist_dash = None

# --- FUNCIONES ---
def format_time(seconds):
    if seconds is None or seconds <= 0: return "0s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"

def render_dashboard(data, max_q_val, title="Dashboard Analysis"):
    st.markdown(f"## {title}")
    df = pd.DataFrame(data)
    if df.empty: return st.info("No hay datos suficientes.")
    
    comp = df[df['Status'] == 'Completed']
    avg_w = comp['Wait_Sec'].mean() if not comp.empty else 0
    avg_s = comp['Service_Sec'].mean() if not comp.empty else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Arrivals", len(df))
    c2.metric("Max Queue 👤", max_q_val)
    c3.metric("Avg Wait", format_time(avg_w))
    c4.metric("Avg Service", format_time(avg_s))
    
    st.write("---")
    g1, g2 = st.columns(2)
    with g1:
        st.write("**Arrival Distribution (By Minute)**")
        df['Min'] = pd.to_datetime(df['Arrival_ts'], unit='s').dt.tz_localize('UTC').dt.tz_convert(BOGOTA_TZ).dt.strftime('%H:%M')
        st.bar_chart(df.groupby('Min').size(), color="#2563eb")
    with g2:
        st.write("**Service Times (Per Customer)**")
        if not comp.empty: st.area_chart(comp['Service_Sec'], color="#10b981")

# ==========================================
# FLUJO DE NAVEGACIÓN
# ==========================================

# 1. SI ESTOY VIENDO UN DASHBOARD HISTÓRICO
if st.session_state.viewing_hist_dash:
    if st.button("⬅️ BACK TO MAIN MENU", type="secondary"):
        st.session_state.viewing_hist_dash = None
        st.rerun()
    
    s = st.session_state.viewing_hist_dash
    render_dashboard(s['data'], s.get('max_q', 0), title=f"History: {s['info']['observer']} ({s['info']['date']})")

# 2. PANTALLA DE INICIO
elif st.session_state.active_session is None:
    st.title("🦅 Sabana Queuing System")
    st.write("---")
    c_new, c_hist = st.columns([1, 1.2], gap="large")
    
    with c_new:
        st.subheader("Start New Measurement")
        with st.container(border=True):
            name = st.text_input("Observer Name")
            if st.button("▶ START MEASURING", type="primary", use_container_width=True):
                if name:
                    st.session_state.active_session = {"observer": name, "date": datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d"), "start_time": datetime.now(BOGOTA_TZ), "system_start_ts": time.time()}
                    st.session_state.customers, st.session_state.counter, st.session_state.max_q, st.session_state.view = [], 1, 0, "Table"
                    st.rerun()
    
    with c_hist:
        st.subheader("Measuring History")
        if not st.session_state.history:
            st.info("No hay sesiones previas.")
        for i, s in enumerate(reversed(st.session_state.history)):
            with st.container(border=True):
                st.write(f"**{s['info']['date']}** | Obs: {s['info']['observer']}")
                col1, col2, col3 = st.columns([1, 1, 0.5])
                if col1.button("📊 VIEW DASHBOARD", key=f"vd_{i}", use_container_width=True):
                    st.session_state.viewing_hist_dash = s
                    st.rerun()
                if col2.button("🗑️ DELETE", key=f"del_{i}", use_container_width=True):
                    st.session_state.history = [h for h in st.session_state.history if h['info']['system_start_ts'] != s['info']['system_start_ts']]
                    st.rerun()

# 3. PANTALLA DE MEDICIÓN EN VIVO
else:
    h1, h2 = st.columns([4, 1])
    h1.title(f"🔴 Measuring: {st.session_state.active_session['observer']}")
    if h2.button("⏹ END SESSION", type="secondary", use_container_width=True):
        st.session_state.history.append({"info": st.session_state.active_session, "data": list(st.session_state.customers), "max_q": st.session_state.max_q})
        st.session_state.active_session = None
        st.rerun()

    # Botón de llegada
    c_arr, _ = st.columns([1, 2])
    if c_arr.button("➕ REGISTER ARRIVAL 👤", type="primary", use_container_width=True):
        st.session_state.customers.append({"ID": f"C{st.session_state.counter:03d}", "Status": "Waiting", "Arrival_ts": time.time(), "Arrival": datetime.now(BOGOTA_TZ).strftime("%H:%M:%S"), "Start": "-", "End": "-", "Wait_Sec": 0, "Service_Sec": 0})
        st.session_state.counter += 1
        current_q = len([x for x in st.session_state.customers if x['Status'] == 'Waiting'])
        if current_q > st.session_state.max_q: st.session_state.max_q = current_q
        st.rerun()

    # Paneles de gestión
    cw, cs = st.columns(2)
    with cw:
        st.subheader("Queue ⏳")
        for c in [x for x in st.session_state.customers if x['Status'] == 'Waiting']:
            with st.container(border=True):
                st.write(f"**{c['ID']}**")
                if st.button(f"Atender {c['ID']}", key=f"s_{c['ID']}", type="primary"):
                    c['Status'], c['Start_ts'] = 'In Service', time.time()
                    c['Start'] = datetime.now(BOGOTA_TZ).strftime("%H:%M:%S")
                    st.rerun()
    with cs:
        st.subheader("Service ⚙️")
        for c in [x for x in st.session_state.customers if x['Status'] == 'In Service']:
            with st.container(border=True):
                st.write(f"**{c['ID']}**")
                if st.button(f"Terminar {c['ID']}", key=f"e_{c['ID']}", type="primary"):
                    c['Status'] = 'Completed'
                    c['End'] = datetime.now(BOGOTA_TZ).strftime("%H:%M:%S")
                    c['Wait_Sec'] = c['Start_ts'] - c['Arrival_ts']
                    c['Service_Sec'] = time.time() - c['Start_ts']
                    st.rerun()

    st.write("---")
    
    # Navegación Live
    nav1, nav2 = st.columns(2)
    if nav1.button("📝 VIEW DATA TABLE", use_container_width=True, type="secondary" if st.session_state.view=="Table" else "primary"):
        st.session_state.view = "Table"
    if nav2.button("📊 VIEW LIVE DASHBOARD", use_container_width=True, type="secondary" if st.session_state.view=="Dash" else "primary"):
        st.session_state.view = "Dash"

    if st.session_state.view == "Table":
        # ORDEN COHERENTE: ID -> Llegada -> Inicio -> Fin -> Espera -> Servicio -> Estatus
        st.markdown("""
            <div style="display:flex; font-weight:bold; border-bottom:2px solid #ccc; padding-bottom:10px; margin-bottom:10px;">
                <div style="flex:0.8">ID</div><div style="flex:1">Llegada</div><div style="flex:1">Inicio Serv.</div>
                <div style="flex:1">Fin Serv.</div><div style="flex:1">Espera</div><div style="flex:1">Servicio</div>
                <div style="flex:1.2">Estatus</div><div style="flex:0.5"></div>
            </div>
        """, unsafe_allow_html=True)
        for c in st.session_state.customers:
            cols = st.columns([0.8, 1, 1, 1, 1, 1, 1.2, 0.5])
            cols[0].write(c['ID'])
            cols[1].write(c['Arrival'])
            cols[2].write(c['Start'])
            cols[3].write(c['End'])
            cols[4].write(format_time(c['Wait_Sec']))
            cols[5].write(format_time(c['Service_Sec']))
            st_icon = "⏳ Cola" if c['Status'] == 'Waiting' else "⚙️ En Serv." if c['Status'] == 'In Service' else "✅ Listo"
            cols[6].write(st_icon)
            if cols[7].button("❌", key=f"del_{c['ID']}"):
                st.session_state.customers = [x for x in st.session_state.customers if x['ID'] != c['ID']]
                st.rerun()
    else:
        render_dashboard(st.session_state.customers, st.session_state.max_q, "Live Session Analysis")
