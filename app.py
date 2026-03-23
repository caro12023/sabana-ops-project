import streamlit as st
import pandas as pd
import time
from datetime import datetime
import io
from fpdf import FPDF
import pytz

# --- ZONA HORARIA Y CONFIGURACIÓN ---
st.set_page_config(page_title="Sabana Queuing Pro", layout="wide", page_icon="🦅")
BOGOTA_TZ = pytz.timezone('America/Bogota')

# --- DISEÑO ESTÉTICO ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    div[data-testid="stVerticalBlock"] > div[style*="border"] { 
        border-radius: 12px; border: 1px solid #cbd5e1; background-color: white; box-shadow: 0 1px 2px rgba(0,0,0,0.05); 
    }
    .pill-orange { background-color: #fef3c7; color: #b45309; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: bold; }
    .pill-blue { background-color: #e0f2fe; color: #0369a1; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: bold; }
    .del-btn button { background-color: #fee2e2 !important; color: #991b1b !important; border: 1px solid #f87171 !important; padding: 2px 10px !important; }
    </style>
""", unsafe_allow_html=True)

# --- MEMORIA DEL SISTEMA ---
if 'history' not in st.session_state: st.session_state.history = [] 
if 'active_session' not in st.session_state: st.session_state.active_session = None 
if 'customers' not in st.session_state: st.session_state.customers = [] 
if 'counter' not in st.session_state: st.session_state.counter = 1
if 'max_q' not in st.session_state: st.session_state.max_q = 0

# --- FUNCIONES ---
def format_time_exact(seconds):
    if pd.isna(seconds) or seconds is None or seconds <= 0: return "0m 0.00s"
    m, s = divmod(seconds, 60)
    return f"{int(m)}m {s:.2f}s"

def format_time_simple(seconds):
    if pd.isna(seconds) or seconds is None or seconds < 0: return "-"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"

def export_excel(cust_data):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    if cust_data:
        df = pd.DataFrame(cust_data)
        cols = ['Customer ID', 'Arrival Time', 'Service Start Time', 'Service End Time', 'Status']
        df[cols].to_excel(writer, index=False)
    writer.close()
    return output.getvalue()

def export_pdf(session_info, cust_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(30, 41, 59)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", size=20, style='B')
    pdf.cell(0, 15, txt="SABANA QUEUING REPORT", ln=1, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt=f"Professional Operations Analysis | Observer: {session_info['observer']}", ln=1, align='C')
    pdf.ln(20); pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=11, style='B')
    pdf.cell(0, 10, txt=f"Date: {session_info['date']}", ln=1)
    for c in cust_data:
        pdf.cell(0, 8, txt=f"{c['Customer ID']} | Arrival: {c['Arrival Time']} | Status: {c['Status']}", ln=1, border='B')
    return pdf.output(dest='S').encode('latin-1')

def render_full_dashboard(cust_data, session_info, max_q):
    df = pd.DataFrame(cust_data)
    if df.empty: return st.info("No data recorded yet.")
    
    comp = df[df['Status'] == 'Completed']
    avg_w = comp['Wait_Sec'].mean() if not comp.empty else 0
    avg_s = comp['Service_Sec'].mean() if not comp.empty else 0
    
    st.subheader("📊 Performance Metrics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Arrivals", len(df))
    m2.metric("Max Queue 👤", max_q)
    m3.metric("Avg Wait (Exact)", format_time_exact(avg_w))
    m4.metric("Avg Service (Exact)", format_time_exact(avg_s))

    st.write("---")
    st.subheader("📐 Queueing Theory (λ, μ, ρ)")
    
    # Tiempo transcurrido
    if 'end_time' in session_info:
        duration_hrs = (session_info['end_time'] - session_info['start_time']).total_seconds() / 3600
    else:
        duration_hrs = (datetime.now(BOGOTA_TZ) - session_info['start_time']).total_seconds() / 3600
    
    duration_hrs = max(duration_hrs, 0.001) 
    lam = len(df) / duration_hrs
    miu = (3600 / avg_s) if avg_s > 0 else 0
    rho = (lam / miu) if miu > 0 else 0
    no_util = max(0, 1 - rho) # Complemento exacto de rho

    c_l, c_m, c_r, c_n = st.columns(4)
    c_l.metric("Arrival Rate (λ)", f"{lam:.2f} c/hr")
    c_m.metric("Service Rate (μ)", f"{miu:.2f} c/hr")
    
    if rho > 1:
        c_r.metric("Utilization (ρ)", f"{rho:.1%}", delta="UNSTABLE", delta_color="inverse")
        c_n.metric("No Utilización", "0.0%", help="Sistema saturado")
    else:
        c_r.metric("Utilization (ρ)", f"{rho:.1%}", delta="STABLE")
        c_n.metric("No Utilización", f"{no_util:.1%}", help="Capacidad ociosa (1 - rho)")

    st.write("---")
    g1, g2 = st.columns(2)
    with g1:
        st.write("**📊 Arrival Frequency (Poisson)**")
        df['Min'] = pd.to_datetime(df['Arrival_ts'], unit='s').dt.tz_localize('UTC').dt.tz_convert(BOGOTA_TZ).dt.strftime('%H:%M')
        st.bar_chart(df.groupby('Min').size(), color="#2563eb")
    with g2:
        st.write("**📊 Service Times (Exponential)**")
        if not comp.empty: st.area_chart(comp['Service_Sec'], color="#10b981")

# ==========================================
# INTERFAZ
# ==========================================
if st.session_state.active_session is None:
    st.title("🦅 Sabana Queuing System")
    st.write("---")
    c_new, c_hist = st.columns([1, 1.2], gap="large")
    with c_new:
        st.subheader("Start Measurement")
        with st.container(border=True):
            name = st.text_input("Observer Name")
            if st.button("▶ START MEASURING", type="primary", use_container_width=True):
                if name:
                    st.session_state.active_session = {
                        "observer": name, "date": datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d"),
                        "start_time": datetime.now(BOGOTA_TZ), "system_start_ts": time.time()
                    }
                    st.session_state.customers, st.session_state.counter, st.session_state.max_q = [], 1, 0
                    st.rerun()
                else: st.error("Enter a name.")
    with c_hist:
        st.subheader("History")
        if st.session_state.history:
            for i, s in enumerate(reversed(st.session_state.history)):
                with st.container(border=True):
                    st.write(f"**{s['info']['date']}** | Obs: {s['info']['observer']}")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.download_button("Excel", export_excel(s['data']), f"E_{i}.xlsx", key=f"ex_{i}")
                    col2.download_button("PDF", export_pdf(s['info'], s['data']), f"P_{i}.pdf", key=f"pd_{i}")
                    if col3.button("📊 Dash", key=f"d_{i}"): render_full_dashboard(s['data'], s['info'], s.get('max_q', 0))
                    if col4.button("🗑️", key=f"del_{i}"):
                        st.session_state.history = [h for h in st.session_state.history if h['info']['system_start_ts'] != s['info']['system_start_ts']]
                        st.rerun()
else:
    # --- WORKSPACE ---
    h1, h2 = st.columns([4, 1])
    h1.title("🔴 Live Measurement")
    if h2.button("⏹ END SESSION", type="secondary", use_container_width=True):
        st.session_state.active_session["end_time"] = datetime.now(BOGOTA_TZ)
        st.session_state.history.append({"info": st.session_state.active_session, "data": list(st.session_state.customers), "max_q": st.session_state.max_q})
        st.session_state.active_session = None
        st.rerun()
    
    if st.button("➕ REGISTER ARRIVAL 👤", type="primary", use_container_width=True):
        st.session_state.customers.append({
            "Customer ID": f"C{st.session_state.counter:03d}", "Status": "Waiting", "Arrival_ts": time.time(),
            "Arrival Time": datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p"),
            "Start_ts": None, "End_ts": None, "Wait_Sec": 0, "Service_Sec": 0, "Total_Sec": 0
        })
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
                    st.rerun()
    with cs:
        st.subheader("In Service ⚙️")
        for c in [x for x in st.session_state.customers if x['Status'] == 'In Service']:
            with st.container(border=True):
                st.write(f"**{c['Customer ID']}** 🧑‍💻")
                if st.button(f"End Service {c['Customer ID']}", type="primary"):
                    c['Status'], c['End_ts'] = 'Completed', time.time()
                    c['Wait_Sec'], c['Service_Sec'] = c['Start_ts'] - c['Arrival_ts'], c['End_ts'] - c['Start_ts']
                    st.rerun()
    
    st.write("---")
    t1, t2 = st.tabs(["📝 Table", "📊 Dashboard"])
    with t1:
        for c in st.session_state.customers:
            cols = st.columns([1, 1.5, 1, 1, 1, 0.8])
            cols[0].write(c['Customer ID'])
            cols[1].write(c['Arrival Time'])
            cols[2].write(format_time_simple(c['Wait_Sec']))
            cols[3].write(format_time_simple(c['Service_Sec']))
            cols[4].write(c['Status'])
            with cols[5]:
                st.markdown('<div class="del-btn">', unsafe_allow_html=True)
                if st.button("Del", key=f"del_{c['Customer ID']}"):
                    st.session_state.customers = [x for x in st.session_state.customers if x['Customer ID'] != c['Customer ID']]
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
    with t2:
        render_full_dashboard(st.session_state.customers, st.session_state.active_session, st.session_state.max_q)
