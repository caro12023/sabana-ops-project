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
    
    /* Botón de eliminar con caneca */
    .del-btn button { background-color: #fee2e2 !important; color: #991b1b !important; border: 1px solid #f87171 !important; font-weight: bold !important; border-radius: 6px !important; }
    .del-btn button:hover { background-color: #fecaca !important; }
    
    /* Estilos de la tabla centrada y definida */
    .table-head-cell { text-align: center; font-weight: bold; background-color: #e2e8f0; color: #0f172a; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 14px;}
    .table-data-cell { text-align: center; padding: 8px; border-bottom: 1px solid #e2e8f0; color: #334155; font-size: 14px; display: flex; justify-content: center; align-items: center; height: 100%;}
    </style>
""", unsafe_allow_html=True)

# --- MEMORIA DEL SISTEMA ---
if 'history' not in st.session_state: st.session_state.history = [] 
if 'active_session' not in st.session_state: st.session_state.active_session = None 
if 'customers' not in st.session_state: st.session_state.customers = [] 
if 'counter' not in st.session_state: st.session_state.counter = 1
if 'max_q' not in st.session_state: st.session_state.max_q = 0
if 'selected_history' not in st.session_state: st.session_state.selected_history = None

# --- EXCEL ENRIQUECIDO (NÚMEROS EXACTOS) ---
def export_excel(cust_data, session_info):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    if cust_data:
        df = pd.DataFrame(cust_data)
        df['Wait Time (Min)'] = (df['Wait_Sec'] / 60.0).round(2)
        df['Service Time (Min)'] = (df['Service_Sec'] / 60.0).round(2)
        df['Total Time (Min)'] = (df['Total_Sec'] / 60.0).round(2)
        
        df['Wait Time (Min)'] = df['Wait Time (Min)'].fillna(0)
        df['Service Time (Min)'] = df['Service Time (Min)'].fillna(0)
        df['Total Time (Min)'] = df['Total Time (Min)'].fillna(0)
        
        cols = ['Customer ID', 'Arrival Time', 'Service Start Time', 'Service End Time', 'Status', 'Wait Time (Min)', 'Service Time (Min)', 'Total Time (Min)']
        df[cols].to_excel(writer, index=False, sheet_name='Observation_Data')
        
        comp = df[df['Status'] == 'Completed']
        summary_data = {
            'Metric': ['Total Arrivals', 'Completed Services', 'Average Wait (Min)', 'Average Service (Min)', 'Average Total Time (Min)'],
            'Value': [
                len(df), len(comp), 
                round(comp['Wait_Sec'].mean() / 60, 2) if not comp.empty else 0, 
                round(comp['Service_Sec'].mean() / 60, 2) if not comp.empty else 0, 
                round(comp['Total_Sec'].mean() / 60, 2) if not comp.empty else 0
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, index=False, sheet_name='Metrics_Summary')
        
        workbook = writer.book
        header_format = workbook.add_format({'bold': True, 'fg_color': '#1e293b', 'font_color': 'white', 'border': 1, 'align': 'center'})
        data_format = workbook.add_format({'align': 'center'})
        
        for sheet_name in ['Observation_Data', 'Metrics_Summary']:
            worksheet = writer.sheets[sheet_name]
            for col_num in range(10): worksheet.set_column(col_num, col_num, 18, data_format)
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
    
    pdf.set_font("Arial", size=10)
    pdf.ln(5)
    pdf.cell(100, 6, txt=f"Observer: {session_info['observer']}", ln=0)
    pdf.cell(100, 6, txt=f"Date: {session_info['date']}", ln=1)
    pdf.cell(100, 6, txt=f"Period: {start_str} to {end_str}", ln=0)
    pdf.cell(100, 6, txt=f"Total Customers: {len(cust_data)}", ln=1)
    
    df = pd.DataFrame(cust_data)
    comp = df[df['Status'] == 'Completed'] if not df.empty else pd.DataFrame()
    avg_w = f"{comp['Wait_Sec'].mean() / 60:.2f} min" if not comp.empty else "0.00 min"
    avg_s = f"{comp['Service_Sec'].mean() / 60:.2f} min" if not comp.empty else "0.00 min"
    
    pdf.ln(2)
    pdf.set_font("Arial", size=10, style='B')
    pdf.cell(200, 6, txt=f"Average Wait: {avg_w} | Average Service: {avg_s}", ln=1)
    
    pdf.ln(5)
    
    pdf.set_font("Arial", size=9, style='B')
    pdf.set_fill_color(226, 232, 240)
    pdf.cell(20, 10, 'ID', 1, 0, 'C', True)
    pdf.cell(35, 10, 'Arrival Time', 1, 0, 'C', True)
    pdf.cell(35, 10, 'Wait (Min)', 1, 0, 'C', True)
    pdf.cell(35, 10, 'Service (Min)', 1, 0, 'C', True)
    pdf.cell(35, 10, 'Status', 1, 1, 'C', True)
    
    pdf.set_font("Arial", size=9)
    for c in cust_data:
        w_min = f"{c['Wait_Sec']/60:.2f}" if c['Wait_Sec'] is not None else "-"
        s_min = f"{c['Service_Sec']/60:.2f}" if c['Service_Sec'] is not None else "-"
        pdf.cell(20, 9, str(c['Customer ID']), 1, 0, 'C')
        pdf.cell(35, 9, str(c['Arrival Time']), 1, 0, 'C')
        pdf.cell(35, 9, w_min, 1, 0, 'C')
        pdf.cell(35, 9, s_min, 1, 0, 'C')
        pdf.cell(35, 9, str(c['Status']).replace('✅ ', ''), 1, 1, 'C')
        
    return pdf.output(dest='S').encode('latin-1')

# --- DASHBOARD CON CÁLCULOS CLAVE ---
def render_pro_dashboard(cust_data, max_q):
    df = pd.DataFrame(cust_data)
    if df.empty: return st.info("Not enough data to graph yet.")
    
    comp = df[df['Status'] == 'Completed'].copy()
    
    st.markdown("### 📊 System Analytics (High Precision)")
    
    avg_w_min = comp['Wait_Sec'].mean() / 60 if not comp.empty else 0
    avg_s_min = comp['Service_Sec'].mean() / 60 if not comp.empty else 0
    avg_sys_min = comp['Total_Sec'].mean() / 60 if not comp.empty else 0

    # Quitamos "Current Queue" y dejamos tres métricas clave, bien distribuidas
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Arrivals", len(df))
    m2.metric("Max Queue Length 👤", max_q)
    m3.metric("Completed Services", len(comp))

    st.write("---")
    m5, m6, m7 = st.columns(3)
    m5.metric("Average Waiting Time", f"{avg_w_min:.2f} min")
    m6.metric("Average Service Time", f"{avg_s_min:.2f} min")
    m7.metric("Average Time in System", f"{avg_sys_min:.2f} min")

    st.write("---")
    st.markdown("### Charts and Visual Analysis")
    
    if not comp.empty:
        comp['Wait_Min'] = comp['Wait_Sec'] / 60.0
        comp['Service_Min'] = comp['Service_Sec'] / 60.0
    
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
                    if col3.button("📊 Dashboard", key=f"d_{s['info']['system_start_ts']}"):
                        st.session_state.selected_history = s
                        st.rerun()
                    if col4.button("🗑️ Delete", key=f"del_{s['info']['system_start_ts']}"):
                        st.session_state.history = [h for h in st.session_state.history if h['info']['system_start_ts'] != s['info']['system_start_ts']]
                        st.rerun()
        else:
            st.info("No completed sessions yet.")

else:
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
            st.markdown("""
                <div style="display:flex; margin-bottom: 5px;">
                    <div style="flex:1;" class="table-head-cell">Customer ID</div>
                    <div style="flex:1.5; margin-left: 2px;" class="table-head-cell">Arrival Time</div>
                    <div style="flex:1.5; margin-left: 2px;" class="table-head-cell">Start Service</div>
                    <div style="flex:1.5; margin-left: 2px;" class="table-head-cell">End Service</div>
                    <div style="flex:1; margin-left: 2px;" class="table-head-cell">Wait (Min)</div>
                    <div style="flex:1; margin-left: 2px;" class="table-head-cell">Service (Min)</div>
                    <div style="flex:1.2; margin-left: 2px;" class="table-head-cell">Status</div>
                    <div style="flex:1; margin-left: 2px;" class="table-head-cell">Action</div>
                </div>
            """, unsafe_allow_html=True)

            for c in st.session_state.customers:
                w_val = f"{c['Wait_Sec']/60:.2f}" if c['Wait_Sec'] is not None else "-"
                s_val = f"{c['Service_Sec']/60:.2f}" if c['Service_Sec'] is not None else "-"
                status_icon = "⏳ Waiting" if c['Status'] == 'Waiting' else "⚙️ In Service" if c['Status'] == 'In Service' else "✅ Completed"

                cols = st.columns([1, 1.5, 1.5, 1.5, 1, 1, 1.2, 1])
                cols[0].markdown(f"<div class='table-data-cell'><b>{c['Customer ID']}</b></div>", unsafe_allow_html=True)
                cols[1].markdown(f"<div class='table-data-cell'>{c['Arrival Time']}</div>", unsafe_allow_html=True)
                cols[2].markdown(f"<div class='table-data-cell'>{c['Service Start Time']}</div>", unsafe_allow_html=True)
                cols[3].markdown(f"<div class='table-data-cell'>{c['Service End Time']}</div>", unsafe_allow_html=True)
                cols[4].markdown(f"<div class='table-data-cell'>{w_val}</div>", unsafe_allow_html=True)
                cols[5].markdown(f"<div class='table-data-cell'>{s_val}</div>", unsafe_allow_html=True)
                cols[6].markdown(f"<div class='table-data-cell'>{status_icon}</div>", unsafe_allow_html=True)
                
                with cols[7]:
                    st.markdown('<div class="table-data-cell del-btn" style="border:none;">', unsafe_allow_html=True)
                    if st.button("🗑️ Delete", key=f"del_row_{c['Customer ID']}", use_container_width=True):
                        st.session_state.customers = [item for item in st.session_state.customers if item['Customer ID'] != c['Customer ID']]
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

            st.write("")
            col_export1, col_export2 = st.columns([1, 1])
            with col_export1: st.download_button("💾 Export to Excel", export_excel(st.session_state.customers, st.session_state.active_session), f"Live_Data.xlsx")
            with col_export2: st.download_button("📄 Export to PDF", export_pdf(st.session_state.active_session, st.session_state.customers), f"Live_Report.pdf")
        else:
            st.caption("Records will appear here once you register an arrival.")

    with tab_dash:
        render_pro_dashboard(st.session_state.customers, st.session_state.max_q)
