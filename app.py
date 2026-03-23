import streamlit as st
import pandas as pd
import time
from datetime import datetime
import io
from fpdf import FPDF
import pytz

# --- ZONA HORARIA Y CONFIGURACIÓN ---
st.set_page_config(page_title="Sabana Queuing", layout="wide", page_icon="🦅")
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

def export_excel(cust_data):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    if cust_data:
        df = pd.DataFrame(cust_data)
        df['Waiting Time'] = df['Wait_Sec'].apply(format_time)
        df['Service Time'] = df['Service_Sec'].apply(format_time)
        df['Total Time in System'] = df['Total_Sec'].apply(format_time)
        
        cols = ['Customer ID', 'Arrival Time', 'Service Start Time', 'Service End Time', 'Status', 'Waiting Time', 'Service Time', 'Total Time in System']
        df_export = df[cols].copy()
        
        df_export.to_excel(writer, index=False, sheet_name='Observation_Data')
        workbook = writer.book
        worksheet = writer.sheets['Observation_Data']
        header_format = workbook.add_format({'bold': True, 'fg_color': '#e2e8f0', 'font_color': '#0f172a', 'border': 1})
        for col_num, value in enumerate(cols):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(col_num, col_num, 18)
    writer.close()
    return output.getvalue()

def export_pdf(session_info, cust_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16, style='B')
    pdf.cell(200, 10, txt="Observation Summary Report", ln=1, align='C')
    
    # Extraemos las horas automáticas que grabó el sistema
    start_str = session_info['start_time'].strftime('%I:%M %p')
    end_str = session_info.get('end_time', session_info['start_time']).strftime('%I:%M %p')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 8, txt=f"Date: {session_info['date']}", ln=1)
    pdf.cell(200, 8, txt=f"Observer: {session_info['observer']}", ln=1)
    pdf.cell(200, 8, txt=f"Observation Period: {start_str} to {end_str}", ln=1)
    pdf.cell(200, 8, txt=f"Total Customers Recorded: {len(cust_data)}", ln=1)
    
    pdf.ln(5)
    pdf.set_font("Arial", size=9, style='B')
    pdf.cell(25, 10, 'ID', 1)
    pdf.cell(35, 10, 'Arrival Time', 1)
    pdf.cell(35, 10, 'Status', 1)
    pdf.cell(35, 10, 'Total Time', 1)
    pdf.ln(10)
    
    pdf.set_font("Arial", size=9)
    for c in cust_data:
        pdf.cell(25, 10, str(c['Customer ID']), 1)
        pdf.cell(35, 10, str(c['Arrival Time']), 1)
        pdf.cell(35, 10, str(c['Status'].replace('✅ ', '')), 1)
        tot = format_time(c['Total_Sec']) if c['Total_Sec'] else "-"
        pdf.cell(35, 10, str(tot), 1)
        pdf.ln(10)
        
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# PANTALLA 1: SETUP (INICIO DE SESIÓN)
# ==========================================
if st.session_state.active_session is None:
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
                    # El sistema graba automáticamente la hora de inicio aquí
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
        st.subheader("Session History")
        if st.session_state.history:
            for s in reversed(st.session_state.history):
                with st.container(border=True):
                    st.write(f"**Date:** {s['info']['date']} | **Observer:** {s['info']['observer']}")
                    col_ex1, col_ex2, col_del = st.columns([1, 1, 1])
                    with col_ex1:
                        st.download_button("💾 Excel", export_excel(s['data']), f"Queue_{s['info']['date']}.xlsx", key=f"ex_hist_{s['info']['system_start_ts']}")
                    with col_ex2:
                        st.download_button("📄 PDF", export_pdf(s['info'], s['data']), f"Report_{s['info']['date']}.pdf", key=f"pdf_hist_{s['info']['system_start_ts']}")
                    with col_del:
                        if st.button("🗑️ Delete Session", key=f"del_hist_{s['info']['system_start_ts']}"):
                            st.session_state.history = [h for h in st.session_state.history if h['info']['system_start_ts'] != s['info']['system_start_ts']]
                            st.rerun()
        else:
            st.info("No completed sessions yet.")

# ==========================================
# PANTALLA 2: WORKSPACE (ÁREA DE TRABAJO)
# ==========================================
else:
    h1, h2 = st.columns([4, 1])
    h1.title("Real-Time Queue Registration")
    
    if h2.button("⏹ END SESSION", type="secondary", use_container_width=True):
        # El sistema graba automáticamente la hora de fin aquí
        st.session_state.active_session["end_time"] = datetime.now(BOGOTA_TZ)
        st.session_state.history.append({"info": st.session_state.active_session, "data": list(st.session_state.customers)})
        st.session_state.active_session = None
        st.rerun()

    st.write("---")

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        if st.button("➕ REGISTER NEW ARRIVAL 👤", type="primary", use_container_width=True):
            st.session_state.customers.append({
                "Customer ID": f"C{st.session_state.counter:03d}",
                "Status": "Waiting",
                "Queue Position": "-",
                "Arrival_ts": time.time(),
                "Arrival Time": datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p"),
                "Start_ts": None, "Service Start Time": "-", 
                "End_ts": None, "Service End Time": "-",
                "Wait_Sec": None, "Service_Sec": None, "Total_Sec": None
            })
            st.session_state.counter += 1
            
            current_q = len([c for c in st.session_state.customers if c['Status'] == 'Waiting'])
            if current_q > st.session_state.max_q: 
                st.session_state.max_q = current_q
            st.rerun()
    
    st.write("")

    wait_list = [c for c in st.session_state.customers if c['Status'] == 'Waiting']
    serv_list = [c for c in st.session_state.customers if c['Status'] == 'In Service']
    comp_list = [c for c in st.session_state.customers if c['Status'] == 'Completed']

    col_w, col_s = st.columns(2)

    with col_w:
        with st.container(border=True):
            cw1, cw2 = st.columns([3, 1])
            cw1.subheader("Waiting Queue")
            cw2.markdown(f'<div class="pill-blue" style="text-align:center;">{len(wait_list)} waiting</div>', unsafe_allow_html=True)
            
            if not wait_list:
                st.write("No customers currently waiting.")
            
            for i, c in enumerate(wait_list):
                with st.container(border=True):
                    sc1, sc2 = st.columns([3, 1])
                    sc1.markdown(f"**{c['Customer ID']}** 👤")
                    sc2.markdown(f'<div class="pill-orange" style="float:right;">Position {i+1}</div>', unsafe_allow_html=True)
                    st.caption(f"Arrival: {c['Arrival Time']}")
                    
                    if st.button("Start Service", key=f"s_{c['Customer ID']}", type="primary"):
                        for item in st.session_state.customers:
                            if item['Customer ID'] == c['Customer ID']:
                                item['Status'] = 'In Service'
                                item['Queue Position'] = "-"
                                item['Start_ts'] = time.time()
                                item['Service Start Time'] = datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p")
                        st.rerun()

    with col_s:
        with st.container(border=True):
            cs1, cs2 = st.columns([3, 1])
            cs1.subheader("Customers In Service")
            cs2.markdown(f'<div class="pill-blue" style="text-align:center;">{len(serv_list)} in service</div>', unsafe_allow_html=True)
            
            if not serv_list:
                st.write("No active service at the moment.")
            
            for c in serv_list:
                with st.container(border=True):
                    sc1, sc2 = st.columns([3, 1])
                    # Reemplazado el chef por un analista/operador
                    sc1.markdown(f"**{c['Customer ID']}** 🧑‍💻")
                    sc2.markdown('<div class="pill-blue" style="float:right;">⚙️ In Service</div>', unsafe_allow_html=True)
                    st.caption(f"Service start: {c['Service Start Time']}")
                    
                    if st.button("End Service", key=f"e_{c['Customer ID']}", type="primary"):
                        for item in st.session_state.customers:
                            if item['Customer ID'] == c['Customer ID']:
                                item['Status'] = 'Completed'
                                item['End_ts'] = time.time()
                                item['Service End Time'] = datetime.now(BOGOTA_TZ).strftime("%I:%M:%S %p")
                                item['Wait_Sec'] = item['Start_ts'] - item['Arrival_ts']
                                item['Service_Sec'] = item['End_ts'] - item['Start_ts']
                                item['Total_Sec'] = item['End_ts'] - item['Arrival_ts']
                        st.rerun()

    st.markdown(f'<div class="pill-blue" style="display:inline-block; margin-top:10px;">Completed customers: {len(comp_list)}</div>', unsafe_allow_html=True)
    st.write("---")

    # --- PESTAÑAS: TABLA Y DASHBOARD ---
    tab_table, tab_dash = st.tabs(["📝 Detailed Data Table", "📊 Live Dashboard & Charts"])
    
    with tab_table:
        if st.session_state.customers:
            
            col_heads = st.columns([1, 1.5, 1.5, 1.5, 1.5, 1.2, 1.2, 1.2, 0.8])
            col_heads[0].markdown("**ID**")
            col_heads[1].markdown("**Arrival**")
            col_heads[2].markdown("**Start**")
            col_heads[3].markdown("**End**")
            col_heads[4].markdown("**Status**")
            col_heads[5].markdown("**Wait**")
            col_heads[6].markdown("**Service**")
            col_heads[7].markdown("**Total**")
            col_heads[8].markdown("**Action**")
            
            st.markdown('<hr style="margin: 0px 0px 10px 0px; border-top: 2px solid #cbd5e1;">', unsafe_allow_html=True)

            wait_counter = 1
            for c in st.session_state.customers:
                if c['Status'] == 'Waiting':
                    c['Queue Position'] = wait_counter
                    wait_counter += 1

            for c in st.session_state.customers:
                cols = st.columns([1, 1.5, 1.5, 1.5, 1.5, 1.2, 1.2, 1.2, 0.8])
                cols[0].write(f"**{c['Customer ID']}**")
                cols[1].write(c['Arrival Time'])
                cols[2].write(c['Service Start Time'])
                cols[3].write(c['Service End Time'])
                
                status_icon = "⏳ Waiting" if c['Status'] == 'Waiting' else "⚙️ In Service" if c['Status'] == 'In Service' else "✅ Completed"
                cols[4].write(status_icon)
                
                cols[5].write(format_time(c['Wait_Sec']))
                cols[6].write(format_time(c['Service_Sec']))
                cols[7].write(format_time(c['Total_Sec']))
                
                with cols[8]:
                    st.markdown('<div class="del-btn">', unsafe_allow_html=True)
                    if st.button("🗑️ Del", key=f"del_row_{c['Customer ID']}", use_container_width=True):
                        st.session_state.customers = [item for item in st.session_state.customers if item['Customer ID'] != c['Customer ID']]
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown('<hr style="margin: 5px 0px; border-top: 1px solid #f1f5f9;">', unsafe_allow_html=True)

            st.write("")
            col_export1, col_export2 = st.columns([1, 1])
            with col_export1:
                st.download_button("💾 Export Data to Excel", export_excel(st.session_state.customers), f"Live_Data_{st.session_state.active_session['date']}.xlsx")
            with col_export2:
                # El botón de Live Data no tiene hora de fin aún, así que le pasamos el objeto activo
                st.download_button("📄 Export Data to PDF", export_pdf(st.session_state.active_session, st.session_state.customers), f"Live_Report_{st.session_state.active_session['date']}.pdf")
                
        else:
            st.caption("Records will appear here once you register an arrival.")

    with tab_dash:
        st.subheader("System Analytics (High Precision)")
        st.write("Calculations are based strictly on 'Completed' customers.")
        
        df_stats = pd.DataFrame(comp_list)
        avg_wait = df_stats['Wait_Sec'].mean() if len(comp_list) > 0 else 0
        avg_serv = df_stats['Service_Sec'].mean() if len(comp_list) > 0 else 0
        avg_sys = df_stats['Total_Sec'].mean() if len(comp_list) > 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Arrivals", len(st.session_state.customers))
        m2.metric("Current Queue", len(wait_list))
        m3.metric("Max Queue Length", st.session_state.max_q)
        m4.metric("Completed Services", len(comp_list))

        st.divider()
        
        m5, m6, m7 = st.columns(3)
        m5.metric("Avg Waiting Time", format_time_exact(avg_wait))
        m6.metric("Avg Service Time", format_time_exact(avg_serv))
        m7.metric("Avg Time in System", format_time_exact(avg_sys))
        
        st.write("---")
        
        st.subheader("Distributions")
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("**📉 Arrivals per Minute (Poisson-like observed)**")
            if len(st.session_state.customers) > 0:
                df_all = pd.DataFrame(st.session_state.customers)
                df_all['Arrival_Min'] = pd.to_datetime(df_all['Arrival_ts'], unit='s').dt.tz_localize('UTC').dt.tz_convert(BOGOTA_TZ).dt.strftime('%I:%M %p')
                arrivals_per_min = df_all.groupby('Arrival_Min').size()
                st.bar_chart(arrivals_per_min, color="#2563eb")
            else:
                st.info("Not enough data to graph arrivals yet.")
                
        with chart_col2:
            st.markdown("**📉 Service Time Frequency (Exponential-like observed)**")
            if len(comp_list) > 0:
                df_stats['Service_Bin'] = (df_stats['Service_Sec'] // 5) * 5
                serv_dist = df_stats.groupby('Service_Bin').size()
                serv_dist.index = serv_dist.index.astype(int).astype(str) + "s - " + (serv_dist.index + 5).astype(int).astype(str) + "s"
                st.bar_chart(serv_dist, color="#10b981")
            else:
                st.info("Not enough completed services to graph yet.")
