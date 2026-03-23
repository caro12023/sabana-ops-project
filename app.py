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

# --- ESTILOS PROFESIONALES (Inspirados en tus imágenes) ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    /* Estilo de los botones de la tabla */
    .btn-start button { background-color: #0d9488 !important; color: white !important; border-radius: 6px !important; border: none !important; font-weight: bold !important; }
    .btn-del button { background-color: #c2410c !important; color: white !important; border-radius: 6px !important; border: none !important; font-weight: bold !important; }
    .btn-end button { background-color: #1e40af !important; color: white !important; border-radius: 6px !important; border: none !important; font-weight: bold !important; }
    /* Navegación */
    .nav-btn button { height: 55px !important; font-size: 18px !important; font-weight: bold !important; border-radius: 10px !important; }
    /* Headers de tabla azulados */
    .table-header { color: #1e40af; font-weight: bold; font-size: 13px; text-transform: uppercase; border-bottom: 2px solid #cbd5e1; padding-bottom: 8px; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- MEMORIA ---
if 'history' not in st.session_state: st.session_state.history = [] 
if 'active_session' not in st.session_state: st.session_state.active_session = None 
if 'customers' not in st.session_state: st.session_state.customers = [] 
if 'counter' not in st.session_state: st.session_state.counter = 1
if 'max_q' not in st.session_state: st.session_state.max_q = 0
if 'view' not in st.session_state: st.session_state.view = "Table"
if 'selected_history' not in st.session_state: st.session_state.selected_history = None

# --- FUNCIONES ---
def format_time(seconds):
    if seconds is None or seconds <= 0: return "0s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"

def render_dashboard(data, session_info, max_q_val):
    st.markdown(f"## Analysis: {session_info['observer']} ({session_info['date']})")
    df = pd.DataFrame(data)
    if df.empty: return st.info("No data available.")
    
    comp = df[df['Status'] == 'Completed']
    avg_w = comp['Wait_Sec'].mean() if not comp.empty else 0
    avg_s = comp['Service_Sec'].mean() if not comp.empty else 0
    
    # Métricas Pro
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Arrivals", len(df))
    c2.metric("Max Queue 👤", max_q_val)
    c3.metric("Avg Wait Time", format_time(avg_w))
    c4.metric("Avg Service Time", format_time(avg_s))

    # Cálculos Lambda, Miu, Rho
    st.write("---")
    duration = (session_info.get('end_time', datetime.now(BOGOTA_TZ)) - session_info['start_time']).total_seconds() / 3600
    duration = max(duration, 0.001)
    lam = len(df) / duration
    miu = (3600 / avg_s) if avg_s > 0 else 0
    rho = (lam / miu) if miu > 0 else 0
    
    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("Lambda (λ)", f"{lam:.2f} c/hr")
    cc2.metric("Miu (μ)", f"{miu:.2f} c/hr")
    cc3.metric("Utilization (ρ)", f"{rho:.1%}")
    cc4.metric("Idle Time", f"{max(0, 1-rho):.1%}")

    # Gráficas (Inspiradas en imagen 8)
    st.write("---")
    g1, g2 = st.columns(2)
    with g1:
        st.write("**📈 Queue Length Over Time**")
        # Gráfica de tendencia de la cola
        q_trend = []
        for i in range(len(df)):
            q_trend.append(len(df[:i+1][df[:i+1]['Status'] == 'Waiting']))
        st.line_chart(q_trend, color="#2563eb")
        
    with g2:
        st.write("**📊 Wait vs Service (Seconds)**")
        if not comp.empty:
            chart_data = comp[['Customer ID', 'Wait_Sec', 'Service_Sec']].set_index('Customer ID')
            chart_data.columns = ['Wait Time', 'Service Time']
            st.bar_chart(chart_data)

# ==========================================
# PANTALLA 1: INICIO & HISTORIAL
# ==========================================
if st.session_state.selected_history:
    if st.button("⬅ BACK TO MENU"):
        st.session_state.selected_history = None
        st.rerun()
    render_dashboard(st.session_state.selected_history['data'], st.session_state.selected_history['info'], st.session_state.selected_history.get('max_q', 0))

elif st.session_state.active_session is None:
    st.title("🦅 Sabana Queuing System")
    st.write("---")
    c_new, c_hist = st.columns([1, 1.3], gap="large")
    
    with c_new:
        st.subheader("Start New Measurement")
        with st.container(border=True):
            name = st.text_input("Observer Name")
            if st.button("▶ START MEASURING", type="primary", use_container_width=True):
                if name:
                    st.session_state.active_session = {"observer": name, "date": datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d"), "start_time": datetime.now(BOGOTA_TZ), "system_start_ts": time.time()}
                    st.session_state.customers, st.session_state.counter, st.session_state.max_q = [], 1, 0
                    st.rerun()
    
    with c_hist:
        st.subheader("Measuring History")
        for i, s in enumerate(reversed(st.session_state.history)):
            with st.container(border=True):
                st.write(f"**{s['info']['date']}** | Obs: {s['info']['observer']}")
                col1, col2, col3 = st.columns([1.5, 1, 0.5])
                if col1.button("📊 VIEW DASHBOARD", key=f"vd_{i}", use_container_width=True):
                    st.session_state.selected_history = s
                    st.rerun()
                if col3.button("🗑️", key=f"del_{i}"):
                    st.session_state.history = [h for h in st.session_state.history if h['info']['system_start_ts'] != s['info']['system_start_ts']]
                    st.rerun()

# ==========================================
# PANTALLA 2: WORKSPACE
# ==========================================
else:
    h1, h2 = st.columns([4, 1])
    h1.title(f"🔴 Live: {st.session_state.active_session['observer']}")
    if h2.button("⏹ END SESSION", type="secondary", use_container_width=True):
        st.session_state.active_session["end_time"] = datetime.now(BOGOTA_TZ)
        st.session_state.history.append({"info": st.session_state.active_session, "data": list(st.session_state.customers), "max_q": st.session_state.max_q})
        st.session_state.active_session = None
        st.rerun()

    c_arr, _ = st.columns([1, 2.5])
    if c_arr.button("➕ REGISTER ARRIVAL 👤", type="primary", use_container_width=True):
        st.session_state.customers.append({"ID": f"C{st.session_state.counter:03d}", "Status": "Waiting", "Arrival_ts": time.time(), "Arrival": datetime.now(BOGOTA_TZ).strftime("%H:%M:%S"), "Start": "-", "End": "-", "Wait_Sec": 0, "Service_Sec": 0})
        st.session_state.counter += 1
        q_now = len([x for x in st.session_state.customers if x['Status'] == 'Waiting'])
        if q_now > st.session_state.max_q: st.session_state.max_q = q_now
        st.rerun()

    # FIFO automático: Ordenamos por tiempo de llegada
    wait_q = sorted([x for x in st.session_state.customers if x['Status'] == 'Waiting'], key=lambda x: x['Arrival_ts'])
    serv_q = [x for x in st.session_state.customers if x['Status'] == 'In Service']

    cw, cs = st.columns(2)
    with cw:
        st.subheader("Waiting ⏳")
        for c in wait_q:
            with st.container(border=True):
                st.write(f"**{c['ID']}**")
                st.markdown('<div class="btn-start">', unsafe_allow_html=True)
                if st.button(f"START SERVICE", key=f"s_{c['ID']}", use_container_width=True):
                    c['Status'], c['Start_ts'] = 'In Service', time.time()
                    c['Start'] = datetime.now(BOGOTA_TZ).strftime("%H:%M:%S")
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    with cs:
        st.subheader("Service 🧑‍💻")
        for c in serv_q:
            with st.container(border=True):
                st.write(f"**{c['ID']}**")
                st.markdown('<div class="btn-end">', unsafe_allow_html=True)
                if st.button(f"END SERVICE", key=f"e_{c['ID']}", use_container_width=True):
                    c['Status'], c['End_ts'] = 'Completed', time.time()
                    c['End'] = datetime.now(BOGOTA_TZ).strftime("%H:%M:%S")
                    c['Wait_Sec'] = c['Start_ts'] - c['Arrival_ts']
                    c['Service_Sec'] = c['End_ts'] - c['Start_ts']
                    st.rerun()

    st.write("---")
    
    n1, n2 = st.columns(2)
    if n1.button("📝 DATA TABLE", use_container_width=True, type="secondary" if st.session_state.view=="Table" else "primary"): st.session_state.view = "Table"
    if n2.button("📊 DASHBOARD", use_container_width=True, type="secondary" if st.session_state.view=="Dash" else "primary"): st.session_state.view = "Dash"

    if st.session_state.view == "Table":
        st.markdown("""
            <div class="table-header" style="display:flex;">
                <div style="flex:0.8">ID</div><div style="flex:1">Arrival</div><div style="flex:1">Start</div>
                <div style="flex:1">End</div><div style="flex:1">Wait</div><div style="flex:1">Serv</div>
                <div style="flex:1.2">Status</div><div style="flex:0.6"></div>
            </div>
        """, unsafe_allow_html=True)
        
        for c in st.session_state.customers:
            cols = st.columns([0.8, 1, 1, 1, 1, 1, 1.2, 0.6])
            cols[0].write(f"**{c['ID']}**")
            cols[1].write(c['Arrival'])
            cols[2].write(c['Start'])
            cols[3].write(c['End'])
            cols[4].write(format_time(c['Wait_Sec']))
            cols[5].write(format_time(c['Service_Sec']))
            st_text = "⏳ Waiting" if c['Status'] == 'Waiting' else "⚙️ Serving" if c['Status'] == 'In Service' else "✅ Done"
            cols[6].write(st_text)
            with cols[7]:
                st.markdown('<div class="btn-del">', unsafe_allow_html=True)
                if st.button("DEL", key=f"d_{c['ID']}", use_container_width=True):
                    st.session_state.customers = [x for x in st.session_state.customers if x['ID'] != c['ID']]
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        render_dashboard(st.session_state.customers, st.session_state.active_session, st.session_state.max_q)
