import streamlit as st
import pandas as pd
import time
from datetime import datetime
import io
from fpdf import FPDF
import pytz
import altair as alt

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
    .del-btn button { background-color: #fee2e2 !important; color: #991b1b !important; border: 1px solid #f87171 !important; padding: 4px 12px !important; font-weight: bold !important; }
    .del-btn button:hover { background-color: #fecaca !important; }
    .table-header { font-size: 14px; font-weight: bold; color: #0f172a; border-bottom: 2px solid #cbd5e1; padding-bottom: 5px; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- MEMORIA DEL SISTEMA ---
if 'history' not in st.session_state: st.session_state.history = [] 
if 'active_session' not in st.session_state: st.session_state.active_session = None 
if 'customers' not in st.session_state: st.session_state.customers = [] 
if 'counter' not in st.session_state: st.session_state.counter = 1
if 'max_q' not in st.session_state: st.session_state.max_q = 0
if 'selected_history' not in st.session_state: st.session_state.selected_history = None

# --- FUNCIONES DE FORMATO ---
def format_time(seconds):
    if pd.isna(seconds) or seconds is None or seconds < 0: return "-"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"

def format_time_exact(seconds):
    if pd.isna(seconds) or seconds is None or seconds <= 0: return "0m 0.00s"
    m, s = divmod(seconds, 60)
    return f"{int(m)}m {s:.2f}s"

# --- EXCEL ENRIQUECIDO ---
def export_excel(cust_data, session_info):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    if cust_data:
        df = pd.DataFrame(cust_data)
        df['Wait Time (Formatted)'] = df['Wait_Sec'].apply(format_time)
        df['Service Time (Formatted)'] = df['Service_Sec'].apply(format_time)
        df['Total Time (Formatted)'] = df['Total_Sec'].apply(format_time)
        
        # Hoja 1: Datos Puros
        cols = ['Customer ID', 'Arrival Time', 'Service Start Time', 'Service End Time', 'Status', 'Wait Time (Formatted)', 'Service Time (Formatted)', 'Total Time (Formatted)']
        df[cols].to_excel(writer, index=False, sheet_name='Observation_Data')
        
        # Hoja 2: Resumen Analítico
        comp = df[df['Status'] == 'Completed']
        summary_data = {
            'Metric': ['Total Arrivals', 'Completed Services', 'Average Wait (Sec)', 'Average Service (Sec)', 'Average Total Time (Sec)'],
            'Value': [len(df), len(comp), comp['Wait_Sec'].mean() if not comp.empty else 0, comp['Service_Sec'].mean() if not comp.empty else 0, comp['Total_Sec'].mean() if not comp.empty else 0]
        }
        pd.DataFrame(summary_data).to_excel(writer, index=False, sheet_name='Metrics_Summary')
        
        # Formatos
        workbook = writer.book
        header_format = workbook.add_format({'bold': True, 'fg_color': '#e2e8f0', 'font_color': '#0f172a', 'border': 1})
        for sheet_name in ['Observation_Data', 'Metrics_Summary']:
            worksheet = writer.sheets[sheet_name]
            for col_num in range(10): worksheet.set_column(col_num, col_num, 18)
            if sheet_name == 'Observation_Data':
                for col_num, value in enumerate(cols): worksheet.write(0, col_num, value, header_format)
                
    writer.close()
    return output.getvalue()

# --- PDF ENRIQUECIDO ---
def export_pdf(session_info, cust_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=18, style='B')
    pdf.cell(200, 10, txt="SABANA QUEUING REPORT", ln=1, align='C')
    
    start_str = session_info['start_time'].strftime('%I:%M %p')
    end_str = session_info.get('end_time', datetime.now(BOGOTA_TZ)).strftime('%I:%M %p')
    
    # Resumen Ejecutivo
    pdf.set_font("Arial", size=10)
    pdf.ln(5)
    pdf.cell(100, 6, txt=f"Observer: {session_info['observer']}", ln=0)
    pdf.cell(100, 6, txt=f"Date: {session_info['date']}", ln=1)
    pdf.cell(100, 6, txt=f"Period: {start_str} to {end_str}", ln=0)
    pdf.cell(100, 6, txt=f"Total Customers: {len(cust_data)}", ln=1)
    
    # Cálculos para el PDF
    df = pd.DataFrame(cust_data)
    comp = df[df['Status'] == 'Completed'] if not df.empty else pd.DataFrame()
    avg_w = format_time_exact(comp['Wait_Sec'].mean()) if not comp.empty else "0s"
    avg_s = format_time_exact(comp['Service_Sec'].mean()) if not comp.empty else "0s"
    
    pdf.ln(2)
    pdf.set_font("Arial", size=10, style='B')
    pdf.cell(200, 6, txt=f"Average Wait: {avg_w} | Average Service: {avg_s}", ln=1)
    
    pdf.ln(5)
    
    # Tabla
    pdf.set_font("Arial", size=9, style='B')
    pdf.set_fill_color(226, 232, 240)
    pdf.cell(20, 10, 'ID', 1, 0, 'C', True)
    pdf.cell(35, 10, 'Arrival Time', 1, 0, 'C', True)
    pdf.cell(35, 10, 'Wait Time', 1, 0, 'C', True)
    pdf.cell(35, 10, 'Service Time', 1, 0, 'C', True)
    pdf.cell(35, 10, 'Status', 1, 1, 'C', True)
    
    pdf.set_font("Arial", size=9)
    for c in cust_data:
        pdf.cell(20, 9, str(c['Customer ID']), 1)
        pdf.cell(35, 9, str(c['Arrival Time']), 1)
        pdf.cell(35, 9, format_time(c['Wait_Sec']), 1)
        pdf.cell(35, 9, format_time(c['Service_Sec']), 1)
        pdf.cell(35, 9, str(c['Status']).replace('✅ ', ''), 1, 1)
        
    return pdf.output(dest='S').encode('latin-1')

# --- GRÁFICAS PRO CON ALTAIR ---
def render_pro_dashboard(cust_data, max_q):
    df = pd.DataFrame(cust_data)
    if df.empty: return st.info("Not enough data to graph yet.")
    
    comp = df[df['Status'] == 'Completed'].copy()
    
    # Pre-procesamiento de tiempos a Minutos para las gráficas
    if not comp.empty:
        comp['Wait_Min'] = comp['Wait_Sec'] / 60.0
        comp['Service_Min'] = comp['Service_Sec'] / 60.0
    
    st.markdown("### Charts and Visual Analysis")
    
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    
    with col1:
        st.write("**Arrivals Over Time**")
        df['Arrival_DT'] = pd.to_datetime(df['Arrival_ts'], unit='s').dt.tz_localize('UTC').dt.tz_convert(BOGOTA_TZ)
        df_arr = df.sort_values('Arrival_DT').copy()
        df_arr['Cumulative Customers'] = range(1, len(df_arr) + 1)
        
        chart_arr = alt.Chart(df_arr).mark_line(point=True, color="#1d4ed8").encode(
            x=alt.X('Arrival_DT:T', title='Time', axis=alt.Axis(format='%I:%M %p')),
            y=alt.Y('Cumulative Customers:Q', title='Customers')
        ).properties(height=250)
        st.altair_chart(chart_arr, use_container_width=True)

    with col2:
        st.write("**Queue Length Over Time**")
        # Calcular el tamaño de la cola en el tiempo
        events = []
        for _, row in df.iterrows():
            events.append({'Time': pd.to_datetime(row['Arrival_ts'], unit='s').tz_localize('UTC').tz_convert(BOGOTA_TZ), 'Change': 1})
            if pd.notna(row['Start_ts']):
                events.append({'Time': pd.to_datetime(row['Start_ts'], unit='s').tz_localize('UTC').tz_convert(BOGOTA_TZ), 'Change': -1})
        
        if events:
            df_q = pd.DataFrame(events).sort_values('Time')
            df_q['Waiting'] = df_q['Change'].cumsum()
            chart_q = alt.Chart(df_q).mark_line(point=True, color="#b45309").encode(
                x=alt.X('Time:T', title='Time', axis=alt.Axis(format='%I:%M %p')),
                y=alt.Y('Waiting:Q', title='Waiting')
            ).properties(height=250)
            st.altair_chart(chart_q, use_container_width=True)
        else: st.info("No queue data yet.")

    with col3:
        st.write("**Waiting Times (Minutes)**")
        if not comp.empty:
            chart_w = alt.Chart(comp).mark_bar(color="#c27a4d").encode(
                x=alt.X('Customer ID:N', title='Customer', sort=None),
                y=alt.Y('Wait_Min:Q', title='Minutes')
            ).properties(height=250)
            st.altair_chart(chart_w, use_container_width=True)
        else: st.info("Awaiting completed services.")

    with col4:
        st.write("**Service Times (Minutes)**")
        if not comp.empty:
            chart_s = alt.Chart(comp).mark_bar(color="#459c86").encode(
                x=alt.X('Customer ID:N', title='Customer', sort=None),
                y=alt.Y('Service_Min:Q', title='Minutes')
            ).properties(height=250)
            st.altair_chart(chart_s, use_container_width=True)
        else: st.info("Awaiting completed services.")

# ==========================================
# RUTEO DE PANTALLAS
# ==========================================
if st.session_state.selected_history:
    if st.button("⬅️ BACK TO HISTORY"):
        st.session_state.selected_history = None
        st.rerun()
    s = st.session_state.selected_history
    st.title(f"Dashboard: {s['info']['date']}")
    render_pro_dashboard(s['data'], s.get('max_q', 0))

elif st.session_state.active_session is None:
    # --- PANTALLA DE INICIO ---
    st.title("🦅 Sabana Queuing System")
    st.write("Academic operations tracker. Fill the details below to start.")
    st.write("---")
    
    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        st.subheader("Start New Session")
        with st.container(border=True):
            obs_name = st.text_input("Observer Name")
            if st.button("▶ START MEASURING", type="primary", use_container_width=True):
                if obs_name:
                    st.session_state.active_session = {
                        "date": datetime.now(BOGOTA_TZ).strftime("%Y-%m-%d"), "start_time": datetime.now(BOGOTA_TZ),
                        "observer": obs_name, "system_start_ts": time.time()
                    }
                    st.session_state.customers, st.session_state.counter, st.session_state.max_q = [], 1, 0
                    st.rerun()
                else: st.error("Please enter the Observer Name.")
                    
    with c2:
        st.subheader("Session History")
        if st.session_state.history:
            for s in reversed(st.session_state.history):
                with st.container(border=True):
                    st.write(f"**Date:** {s['info']['date']} | **Obs:** {s['info']['observer']}")
                    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
                    col1.download_button("💾 Excel", export_excel(s['data'], s['info']), f"Data_{s['info']['date']}.xlsx", key=f"ex_{s['info']['system_start_ts']}")
                    col2.download_button("📄 PDF", export_pdf(s['info'], s['data']), f"Report_{s['info']['date']}.pdf", key=f"pdf_{s['info']['system_start_ts']}")
                    if col3.button("📊 Dash", key=f"d_{s['info']['system_start_ts']}"):
                        st.session_state.selected_history = s
                        st.rerun()
                    if col4.button("🗑️ Delete", key=f"del_{s['info']['system_start_ts']}"):
                        st.session_state.history = [h for h in st.session_state.history if h['info']['system_start_ts'] != s['info']['system_start_ts']]
                        st.rerun()
        else:
            st.info("No completed sessions yet.")

else:
    # --- PANTALLA DE MEDICIÓN EN VIVO ---
    h1, h2 = st.columns([4, 1])
    h1.title("Real-Time Queue Registration")
    if h2.button("⏹ END SESSION", type="secondary", use_container_width=True):
        st.session_state.active_session["end_time"] = datetime.now(BOGOTA_TZ)
        st.session_state.history.append({"info": st.session_state.active_session, "data": list(st.session_state.customers), "max_q": st.session_state.max_q})
        st.session_state.active_session = None
        st.rerun()

    st.write("---")

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        if st.button("➕ REGISTER NEW ARRIVAL 👤", type="primary", use_container_width=True):
            st.session_state.customers.append({
                "Customer ID": f"C{st.session_state.counter:03d}", "Status": "Waiting",
                "Arrival_ts": time.time(), "Arrival Time": datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p"),
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

    col_w, col_s = st.columns(2)
    with col_w:
        with st.container(border=True):
            cw1, cw2 = st.columns([3, 1])
            cw1.subheader("Waiting Queue")
            cw2.markdown(f'<div class="pill-blue" style="text-align:center;">{len(wait_list)} waiting</div>', unsafe_allow_html=True)
            for i, c in enumerate(wait_list):
                with st.container(border=True):
                    sc1, sc2 = st.columns([3, 1])
                    sc1.markdown(f"**{c['Customer ID']}** 👤 | Arrived: {c['Arrival Time']}")
                    if st.button("Start Service", key=f"s_{c['Customer ID']}", type="primary"):
                        for item in st.session_state.customers:
                            if item['Customer ID'] == c['Customer ID']:
                                item['Status'], item['Start_ts'] = 'In Service', time.time()
                                item['Service Start Time'] = datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p")
                        st.rerun()

    with col_s:
        with st.container(border=True):
            cs1, cs2 = st.columns([3, 1])
            cs1.subheader("Customers In Service")
            cs2.markdown(f'<div class="pill-blue" style="text-align:center;">{len(serv_list)} in service</div>', unsafe_allow_html=True)
            for c in serv_list:
                with st.container(border=True):
                    sc1, sc2 = st.columns([3, 1])
                    sc1.markdown(f"**{c['Customer ID']}** 🧑‍💻 | Started: {c['Service Start Time']}")
                    if st.button("End Service", key=f"e_{c['Customer ID']}", type="primary"):
                        for item in st.session_state.customers:
                            if item['Customer ID'] == c['Customer ID']:
                                item['Status'], item['End_ts'] = 'Completed', time.time()
                                item['Service End Time'] = datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p")
                                item['Wait_Sec'], item['Service_Sec'] = item['Start_ts'] - item['Arrival_ts'], item['End_ts'] - item['Start_ts']
                                item['Total_Sec'] = item['End_ts'] - item['Arrival_ts']
                        st.rerun()

    st.write("---")
    tab_table, tab_dash = st.tabs(["📝 Detailed Data Table", "📊 Live Dashboard & Charts"])
    
    with tab_table:
        if st.session_state.customers:
            # Encabezados Completos y Bien Distribuidos
            st.markdown("""
                <div style="display:flex; font-weight:bold; color:#0f172a; border-bottom:2px solid #cbd5e1; padding-bottom:5px; margin-bottom:10px;">
                    <div style="flex:1">Customer ID</div><div style="flex:1.5">Arrival Time</div>
                    <div style="flex:1.5">Start Service</div><div style="flex:1.5">End Service</div>
                    <div style="flex:1">Wait Time</div><div style="flex:1">Service Time</div>
                    <div style="flex:1.2">Status</div><div style="flex:1">Action</div>
                </div>
            """, unsafe_allow_html=True)

            for c in st.session_state.customers:
                cols = st.columns([1, 1.5, 1.5, 1.5, 1, 1, 1.2, 1])
                cols[0].write(f"**{c['Customer ID']}**")
                cols[1].write(c['Arrival Time'])
                cols[2].write(c['Service Start Time'])
                cols[3].write(c['Service End Time'])
                cols[4].write(format_time(c['Wait_Sec']))
                cols[5].write(format_time(c['Service_Sec']))
                status_icon = "⏳ Waiting" if c['Status'] == 'Waiting' else "⚙️ In Service" if c['Status'] == 'In Service' else "✅ Completed"
                cols[6].write(status_icon)
                
                with cols[7]:
                    st.markdown('<div class="del-btn">', unsafe_allow_html=True)
                    if st.button("Delete", key=f"del_row_{c['Customer ID']}", use_container_width=True):
                        st.session_state.customers = [item for item in st.session_state.customers if item['Customer ID'] != c['Customer ID']]
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                st.markdown('<hr style="margin: 2px 0px; border-top: 1px solid #f1f5f9;">', unsafe_allow_html=True)

            st.write("")
            col_export1, col_export2 = st.columns([1, 1])
            with col_export1: st.download_button("💾 Export to Excel", export_excel(st.session_state.customers, st.session_state.active_session), f"Live_Data.xlsx")
            with col_export2: st.download_button("📄 Export to PDF", export_pdf(st.session_state.active_session, st.session_state.customers), f"Live_Report.pdf")
        else:
            st.caption("Records will appear here once you register an arrival.")

    with tab_dash:
        render_pro_dashboard(st.session_state.customers, st.session_state.max_q)
