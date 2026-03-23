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
    div[data-testid="stVerticalBlock"] > div[style*="border"] { 
        border-radius: 12px; border: 1px solid #cbd5e1; background-color: white; padding: 15px;
    }
    .pill-orange { background-color: #fef3c7; color: #b45309; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: bold; }
    .pill-blue { background-color: #e0f2fe; color: #0369a1; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: bold; }
    .del-btn button { background-color: #fee2e2 !important; color: #991b1b !important; border: 1px solid #f87171 !important; height: 30px !important; }
    </style>
""", unsafe_allow_html=True)

# --- MEMORIA ---
if 'history' not in st.session_state: st.session_state.history = [] 
if 'active_session' not in st.session_state: st.session_state.active_session = None 
if 'customers' not in st.session_state: st.session_state.customers = [] 
if 'counter' not in st.session_state: st.session_state.counter = 1
if 'max_q' not in st.session_state: st.session_state.max_q = 0

# --- FUNCIONES ---
def format_time_exact(seconds):
    if pd.isna(seconds) or seconds <= 0: return "0.00s"
    m, s = divmod(seconds, 60)
    return f"{int(m)}m {s:.2f}s"

def export_excel(cust_data):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    if cust_data:
        df = pd.DataFrame(cust_data)
        cols_to_save = ['Customer ID', 'Arrival Time', 'Service Start Time', 'Service End Time', 'Status']
        df[cols_to_save].to_excel(writer, index=False, sheet_name='Data')
    writer.close()
    return output.getvalue()

def export_pdf(session_info, cust_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(30, 41, 59)
    pdf.rect(0, 0, 210, 30, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", size=16, style='B')
    pdf.cell(0, 10, txt="SABANA QUEUING REPORT", ln=1, align='C')
    pdf.ln(15); pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 8, txt=f"Observer: {session_info['observer']} | Date: {session_info['date']}", ln=1)
    for c in cust_data:
        pdf.cell(0, 7, txt=f"{c['Customer ID']} | Arrival: {c['Arrival Time']} | Status: {c['Status']}", ln=1, border='B')
    return pdf.output(dest='S').encode('latin-1')

def render_metrics(cust_data, session_info, max_q):
    df = pd.DataFrame(cust_data)
    if df.empty: return st.info("No hay datos para analizar.")
    
    comp = df[df['Status'] == 'Completed']
    avg_s = comp['Service_Sec'].mean() if not comp.empty else 0
    avg_w = comp['Wait_Sec'].mean() if not comp.empty else 0
    
    st.subheader("📊 Métricas de Desempeño")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Llegadas", len(df))
    m2.metric("Cola Máxima 👤", max_q)
    m3.metric("Espera Promedio", format_time_exact(avg_w))
    m4.metric("Servicio Promedio", format_time_exact(avg_s))

    st.write("---")
    st.subheader("📐 Teoría de Colas (λ, μ, ρ)")
    
    dur_hrs = (datetime.now(BOGOTA_TZ) - session_info['start_time']).total_seconds() / 3600
    if 'end_time' in session_info:
        dur_hrs = (session_info['end_time'] - session_info['start_time']).total_seconds() / 3600
    
    lam = len(df) / max(dur_hrs, 0.0001)
    miu = (3600 / avg_s) if avg_s > 0 else 0
    rho = (lam / miu) if miu > 0 else 0

    c_l, c_m, c_r, c_n = st.columns(4)
    c_l.metric("Tasa Llegada (λ)", f"{lam:.2f} c/hr")
    c_m.metric("Tasa Servicio (μ)", f"{miu:.2f} c/hr")
    c_r.metric("Utilización (ρ)", f"{rho:.1%}")
    c_n.metric("No Utilización", f"{max(0, 1-rho):.1%}")

# ==========================================
# PANTALLA 1: INICIO
# ==========================================
if st.session_state.active_session is None:
    st.title("🦅 Sabana Queuing System")
    c_new, c_hist = st.columns([1, 1.2], gap="large")
    with c_new:
        st.subheader("Start Measurement")
        with st.container(border=True):
            name = st.text_input("Observer Name")
            if st.button("▶ START MEASURING", type="primary", use_container_width=True):
                if name:
                    st.session_state.active_session = {"observer": name, "date": datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d"), "start_time": datetime.now(BOGOTA_TZ), "system_start_ts": time.time()}
                    st.session_state.customers, st.session_state.counter, st.session_state.max_q = [], 1, 0
                    st.rerun()
    with c_hist:
        st.subheader("History")
        for i, s in enumerate(reversed(st.session_state.history)):
            with st.container(border=True):
                st.write(f"**{s['info']['date']}** | {s['info']['observer']}")
                col1, col2, col3, col4 = st.columns(4)
                col1.download_button("Excel", export_excel(s['data']), f"E_{i}.xlsx", key=f"ex_{i}")
                col2.download_button("PDF", export_pdf(s['info'], s['data']), f"P_{i}.pdf", key=f"pd_{i}")
                if col3.button("📊 Dash", key=f"d_{i}"): render_metrics(s['data'], s['info'], s.get('max_q', 0))
                if col4.button("🗑️", key=f"del_{i}"):
                    st.session_state.history = [h for h in st.session_state.history if h['info']['system_start_ts'] != s['info']['system_start_ts']]
                    st.rerun()
else:
    # ==========================================
    # PANTALLA 2: WORKSPACE
    # ==========================================
    h1, h2 = st.columns([4, 1])
    h1.title("🔴 Live Measurement")
    if h2.button("⏹ END SESSION", type="secondary", use_container_width=True):
        st.session_state.active_session["end_time"] = datetime.now(BOGOTA_TZ)
        st.session_state.history.append({"info": st.session_state.active_session, "data": list(st.session_state.customers), "max_q": st.session_state.max_q})
        st.session_state.active_session = None
        st.rerun()
    
    # Botón de llegada NO alargado
    c_btn, _ = st.columns([1, 2])
    with c_btn:
        if st.button("➕ REGISTER ARRIVAL 👤", type="primary", use_container_width=True):
            st.session_state.customers.append({"Customer ID": f"C{st.session_state.counter:03d}", "Status": "Waiting", "Arrival_ts": time.time(), "Arrival Time": datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p"), "Start_ts": None, "Service Start Time": "-", "End_ts": None, "Service End Time": "-", "Wait_Sec": 0, "Service_Sec": 0, "Total_Sec": 0})
            st.session_state.counter += 1
            st.rerun()

    cw, cs = st.columns(2)
    with cw:
        st.subheader("Waiting ⏳")
        for c in [x for x in st.session_state.customers if x['Status'] == 'Waiting']:
            with st.container(border=True):
                st.write(f"**{c['Customer ID']}** 👤")
                if st.button(f"Start Service {c['Customer ID']}", type="primary"):
                    c['Status'], c['Start_ts'] = 'In Service', time.time()
                    c['Service Start Time'] = datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p")
                    st.rerun()
    with cs:
        st.subheader("In Service ⚙️")
        for c in [x for x in st.session_state.customers if x['Status'] == 'In Service']:
            with st.container(border=True):
                st.write(f"**{c['Customer ID']}** 🧑‍💻")
                if st.button(f"End Service {c['Customer ID']}", type="primary"):
                    c['Status'], c['End_ts'] = 'Completed', time.time()
                    c['Service End Time'] = datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p")
                    c['Wait_Sec'], c['Service_Sec'] = c['Start_ts'] - c['Arrival_ts'], c['End_ts'] - c['Start_ts']
                    c['Total_Sec'] = c['End_ts'] - c['Arrival_ts']
                    st.rerun()
    
    st.write("---")
    t1, t2 = st.tabs(["📝 Table", "📊 Dashboard"])
    with t1:
        # TABLA CON EMOJIS COMO TE GUSTABA
        col_h = st.columns([1, 1.5, 1, 1, 1.5, 0.8])
        col_h[0].write("**ID**"); col_h[1].write("**Arrival**"); col_h[2].write("**Wait**"); col_h[3].write("**Service**"); col_h[4].write("**Status**")
        for c in st.session_state.customers:
            cols = st.columns([1, 1.5, 1, 1, 1.5, 0.8])
            cols[0].write(c['Customer ID'])
            cols[1].write(c['Arrival Time'])
            cols[2].write(f"{c['Wait_Sec']:.1f}s")
            cols[3].write(f"{c['Service_Sec']:.1f}s")
            # Íconos visuales en la tabla
            status_icon = "⏳ Waiting" if c['Status'] == 'Waiting' else "⚙️ In Service" if c['Status'] == 'In Service' else "✅ Completed"
            cols[4].write(status_icon)
            with cols[5]:
                if st.button("Del", key=f"del_{c['Customer ID']}", use_container_width=True):
                    st.session_state.customers = [x for x in st.session_state.customers if x['Customer ID'] != c['Customer ID']]
                    st.rerun()
    with t2:
        render_metrics(st.session_state.customers, st.session_state.active_session, st.session_state.max_q)
