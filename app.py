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
    .del-btn button:hover { background-color: #fecaca !important; }
    </style>
""", unsafe_allow_html=True)

# --- MEMORIA DEL SISTEMA ---
if 'history' not in st.session_state: st.session_state.history = [] 
if 'active_session' not in st.session_state: st.session_state.active_session = None 
if 'customers' not in st.session_state: st.session_state.customers = [] 
if 'counter' not in st.session_state: st.session_state.counter = 1
if 'max_q' not in st.session_state: st.session_state.max_q = 0

# --- FUNCIONES DE FORMATO ---
def format_time(seconds):
    if pd.isna(seconds) or seconds is None or seconds < 0: return "-"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"

def format_time_exact(seconds):
    if pd.isna(seconds) or seconds is None or seconds <= 0: return "0m 0.00s"
    m, s = divmod(seconds, 60)
    return f"{int(m)}m {s:.2f}s"

# --- EXPORTAR EXCEL ---
def export_excel(cust_data):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    if cust_data:
        df = pd.DataFrame(cust_data)
        df['Waiting Time'] = df['Wait_Sec'].apply(format_time)
        df['Service Time'] = df['Service_Sec'].apply(format_time)
        df['Total Time in System'] = df['Total_Sec'].apply(format_time)
        cols = ['Customer ID', 'Arrival Time', 'Service Start Time', 'Service End Time', 'Status', 'Waiting Time', 'Service Time', 'Total Time in System']
        df[cols].to_excel(writer, index=False, sheet_name='Data')
        workbook = writer.book
        worksheet = writer.sheets['Data']
        header_format = workbook.add_format({'bold': True, 'fg_color': '#1e293b', 'font_color': 'white', 'border': 1})
        for col_num, value in enumerate(cols):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(col_num, col_num, 18)
    writer.close()
    return output.getvalue()

# --- EXPORTAR PDF MEJORADO ---
def export_pdf(session_info, cust_data):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado con color
    pdf.set_fill_color(30, 41, 59) # Slate 800
    pdf.rect(0, 0, 210, 40, 'F')
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", size=22, style='B')
    pdf.cell(0, 15, txt="SABANA QUEUING REPORT", ln=1, align='L')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt=f"Professional Operations Analysis | Date: {session_info['date']}", ln=1, align='L')
    
    pdf.ln(20)
    pdf.set_text_color(0, 0, 0)
    
    # Resumen Ejecutivo
    pdf.set_font("Arial", size=14, style='B')
    pdf.cell(0, 10, txt="1. Executive Summary", ln=1)
    pdf.set_font("Arial", size=11)
    
    start_str = session_info['start_time'].strftime('%I:%M %p')
    end_str = session_info.get('end_time', datetime.now(BOGOTA_TZ)).strftime('%I:%M %p')
    
    pdf.cell(100, 8, txt=f"Observer: {session_info['observer']}", ln=0)
    pdf.cell(100, 8, txt=f"Time Window: {start_str} - {end_str}", ln=1)
    
    # Cálculos para el PDF
    df_p = pd.DataFrame(cust_data)
    comp = df_p[df_p['Status'] == 'Completed']
    avg_w = format_time_exact(comp['Wait_Sec'].mean()) if not comp.empty else "0.00s"
    avg_s = format_time_exact(comp['Service_Sec'].mean()) if not comp.empty else "0.00s"
    
    pdf.set_font("Arial", style='B', size=11)
    pdf.cell(0, 10, txt=f"Total Samples: {len(cust_data)} | Avg Wait: {avg_w} | Avg Service: {avg_s}", ln=1)
    
    pdf.ln(5)
    
    # Tabla de Datos
    pdf.set_font("Arial", size=14, style='B')
    pdf.cell(0, 10, txt="2. Detailed Observation Logs", ln=1)
    
    # Cabecera Tabla
    pdf.set_fill_color(226, 232, 240)
    pdf.set_font("Arial", size=9, style='B')
    pdf.cell(25, 10, 'ID', 1, 0, 'C', True)
    pdf.cell(40, 10, 'Arrival', 1, 0, 'C', True)
    pdf.cell(40, 10, 'Wait Time', 1, 0, 'C', True)
    pdf.cell(40, 10, 'Service Time', 1, 0, 'C', True)
    pdf.cell(45, 10, 'Status', 1, 1, 'C', True)
    
    # Filas Tabla
    pdf.set_font("Arial", size=9)
    fill = False
    for c in cust_data:
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(25, 9, str(c['Customer ID']), 1, 0, 'C', True)
        pdf.cell(40, 9, str(c['Arrival Time']), 1, 0, 'C', True)
        pdf.cell(40, 9, format_time(c['Wait_Sec']), 1, 0, 'C', True)
        pdf.cell(40, 9, format_time(c['Service_Sec']), 1, 0, 'C', True)
        status_clean = c['Status'].replace('✅ ', '').replace('⚙️ ', '')
        pdf.cell(45, 9, status_clean, 1, 1, 'C', True)
        fill = not fill
        
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# PANTALLA 1: SETUP
# ==========================================
if st.session_state.active_session is None:
    st.title("🦅 Sabana Queuing System")
    st.write("---")
    
    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        st.subheader("Start New Measurement")
        with st.container(border=True):
            obs_name = st.text_input("Observer Name")
            if st.button("▶ START MEASURING", type="primary", use_container_width=True):
                if obs_name:
                    st.session_state.active_session = {
                        "date": datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d"),
                        "start_time": datetime.now(BOGOTA_TZ),
                        "observer": obs_name,
                        "system_start_ts": time.time()
                    }
                    st.session_state.customers = []
                    st.session_state.counter = 1
                    st.session_state.max_q = 0
                    st.rerun()
                else:
                    st.error("Please enter the Observer Name.")
                    
    with c2:
        st.subheader("Stored History")
        if st.session_state.history:
            for s in reversed(st.session_state.history):
                with st.container(border=True):
                    st.write(f"**{s['info']['date']}** | Obs: {s['info']['observer']}")
                    cx1, cx2, cx3 = st.columns(3)
                    cx1.download_button("💾 Excel", export_excel(s['data']), f"Data_{s['info']['date']}.xlsx", key=f"ex_{s['info']['system_start_ts']}")
                    cx2.download_button("📄 PDF", export_pdf(s['info'], s['data']), f"Report_{s['info']['date']}.pdf", key=f"pd_{s['info']['system_start_ts']}")
                    if cx3.button("🗑️ Delete", key=f"del_{s['info']['system_start_ts']}"):
                        st.session_state.history = [h for h in st.session_state.history if h['info']['system_start_ts'] != s['info']['system_start_ts']]
                        st.rerun()
        else:
            st.info("No saved sessions.")

# ==========================================
# PANTALLA 2: WORKSPACE
# ==========================================
else:
    h1, h2 = st.columns([4, 1])
    h1.title("Real-Time Queue Registration")
    if h2.button("⏹ END SESSION", type="secondary", use_container_width=True):
        st.session_state.active_session["end_time"] = datetime.now(BOGOTA_TZ)
        st.session_state.history.append({"info": st.session_state.active_session, "data": list(st.session_state.customers)})
        st.session_state.active_session = None
        st.rerun()

    st.write("---")

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        if st.button("➕ REGISTER NEW ARRIVAL 👤", type="primary", use_container_width=True):
            st.session_state.customers.append({
                "Customer ID": f"C{st.session_state.counter:03d}", "Status": "Waiting", "Arrival_ts": time.time(),
                "Arrival Time": datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p"),
                "Start_ts": None, "Service Start Time": "-", "End_ts": None, "Service End Time": "-",
                "Wait_Sec": None, "Service_Sec": None, "Total_Sec": None
            })
            st.session_state.counter += 1
            cur_q = len([c for c in st.session_state.customers if c['Status'] == 'Waiting'])
            if cur_q > st.session_state.max_q: st.session_state.max_q = cur_q
            st.rerun()
    
    st.write("")

    wait_list = [c for c in st.session_state.customers if c['Status'] == 'Waiting']
    serv_list = [c for c in st.session_state.customers if c['Status'] == 'In Service']
    comp_list = [c for c in st.session_state.customers if c['Status'] == 'Completed']

    col_w, col_s = st.columns(2)
    with col_w:
        with st.container(border=True):
            st.subheader(f"Waiting Queue ({len(wait_list)})")
            for i, c in enumerate(wait_list):
                with st.container(border=True):
                    sc1, sc2 = st.columns([3, 1])
                    sc1.markdown(f"**{c['Customer ID']}** 👤")
                    sc2.markdown(f'<div class="pill-orange">Pos {i+1}</div>', unsafe_allow_html=True)
                    if st.button("Start Service", key=f"s_{c['Customer ID']}", use_container_width=True):
                        for item in st.session_state.customers:
                            if item['Customer ID'] == c['Customer ID']:
                                item['Status'], item['Start_ts'] = 'In Service', time.time()
                                item['Service Start Time'] = datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p")
                        st.rerun()

    with col_s:
        with st.container(border=True):
            st.subheader(f"In Service ({len(serv_list)})")
            for c in serv_list:
                with st.container(border=True):
                    st.markdown(f"**{c['Customer ID']}** 🧑‍💻")
                    if st.button("End Service", key=f"e_{c['Customer ID']}", type="primary", use_container_width=True):
                        for item in st.session_state.customers:
                            if item['Customer ID'] == c['Customer ID']:
                                item['Status'], item['End_ts'] = 'Completed', time.time()
                                item['Service End Time'] = datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p")
                                item['Wait_Sec'] = item['Start_ts'] - item['Arrival_ts']
                                item['Service_Sec'] = item['End_ts'] - item['Start_ts']
                                item['Total_Sec'] = item['End_ts'] - item['Arrival_ts']
                        st.rerun()

    st.write("---")
    tab_t, tab_d = st.tabs(["📝 Table", "📊 Dashboard"])
    
    with tab_t:
        if st.session_state.customers:
            st.columns([1, 1.5, 1.5, 1.5, 1.5, 1.2, 1.2, 1.2, 0.8]) # Header visual
            for c in st.session_state.customers:
                cols = st.columns([1, 1.5, 1.5, 1.5, 1.5, 1.2, 1.2, 1.2, 0.8])
                cols[0].write(c['Customer ID'])
                cols[1].write(c['Arrival Time'])
                cols[4].write(c['Status'])
                cols[5].write(format_time(c['Wait_Sec']))
                cols[6].write(format_time(c['Service_Sec']))
                cols[7].write(format_time(c['Total_Sec']))
                with cols[8]:
                    st.markdown('<div class="del-btn">', unsafe_allow_html=True)
                    if st.button("Del", key=f"d_{c['Customer ID']}"):
                        st.session_state.customers = [x for x in st.session_state.customers if x['Customer ID'] != c['Customer ID']]
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            
            st.divider()
            cx1, cx2 = st.columns(2)
            cx1.download_button("💾 Export Excel", export_excel(st.session_state.customers), "Live_Data.xlsx")
            cx2.download_button("📄 Export PDF", export_pdf(st.session_state.active_session, st.session_state.customers), "Live_Report.pdf")

    with tab_d:
        df_s = pd.DataFrame(comp_list)
        avg_w = df_s['Wait_Sec'].mean() if not df_s.empty else 0
        avg_s = df_s['Service_Sec'].mean() if not df_s.empty else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Arrivals", len(st.session_state.customers))
        c2.metric("Avg Wait Time", format_time_exact(avg_w))
        c3.metric("Avg Service Time", format_time_exact(avg_s))
        
        st.write("---")
        # Gráficas
        g1, g2 = st.columns(2)
        with g1:
            st.write("**Arrivals per Minute**")
            if not df_s.empty:
                df_all = pd.DataFrame(st.session_state.customers)
                df_all['Min'] = pd.to_datetime(df_all['Arrival_ts'], unit='s').dt.tz_localize('UTC').dt.tz_convert(BOGOTA_TZ).dt.strftime('%H:%M')
                st.bar_chart(df_all.groupby('Min').size())
        with g2:
            st.write("**Service Times (Sec)**")
            if not df_s.empty:
                st.area_chart(df_s['Service_Sec'])
