import streamlit as st
import pandas as pd
import time
from datetime import datetime
import io
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sabana Queuing", layout="wide", page_icon="🦅")

# --- DISEÑO ESTÉTICO ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    div[data-testid="stVerticalBlock"] > div[style*="border"] { 
        border-radius: 12px; border: 1px solid #cbd5e1; background-color: white; box-shadow: 0 1px 2px rgba(0,0,0,0.05); 
    }
    .pill-orange { background-color: #fef3c7; color: #b45309; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: bold; }
    .pill-blue { background-color: #e0f2fe; color: #0369a1; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- MEMORIA DEL SISTEMA ---
if 'history' not in st.session_state: st.session_state.history = [] 
if 'active_session' not in st.session_state: st.session_state.active_session = None 
if 'customers' not in st.session_state: st.session_state.customers = [] 
if 'counter' not in st.session_state: st.session_state.counter = 1

# --- FUNCIONES ---
def format_time(seconds):
    if pd.isna(seconds) or seconds is None or seconds < 0: return "-"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"

def export_excel(cust_data):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    if cust_data:
        df = pd.DataFrame(cust_data)
        cols = ['Customer ID', 'Arrival Time', 'Service Start Time', 'Service End Time', 'Status', 'Waiting Time', 'Service Time', 'Total Time in System', 'Notes']
        df[cols].to_excel(writer, index=False, sheet_name='Data')
        workbook = writer.book
        worksheet = writer.sheets['Data']
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
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Date: {session_info['date']}", ln=1)
    pdf.cell(200, 10, txt=f"Observer: {session_info['observer']}", ln=1)
    pdf.cell(200, 10, txt=f"Total Customers Recorded: {len(cust_data)}", ln=1)
    
    pdf.set_font("Arial", size=10)
    pdf.ln(10)
    pdf.cell(30, 10, 'ID', 1)
    pdf.cell(45, 10, 'Arrival Time', 1)
    pdf.cell(40, 10, 'Status', 1)
    pdf.cell(40, 10, 'Total Time', 1)
    pdf.ln(10)
    
    for c in cust_data:
        pdf.cell(30, 10, str(c['Customer ID']), 1)
        pdf.cell(45, 10, str(c['Arrival Time']), 1)
        pdf.cell(40, 10, str(c['Status'].replace('✅ ', '')), 1)
        tot = format_time(c['Total_Sec']) if c['Total_Sec'] else "-"
        pdf.cell(40, 10, str(tot), 1)
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
            if st.button("▶ START RECORDING", type="primary", use_container_width=True):
                if obs_name:
                    st.session_state.active_session = {
                        "date": datetime.today().strftime("%Y-%m-%d"),
                        "observer": obs_name,
                        "start_ts": time.time()
                    }
                    st.session_state.customers = []
                    st.session_state.counter = 1
                    st.rerun()
                else:
                    st.error("Please enter the Observer Name.")
                    
    with c2:
        st.subheader("Session History")
        if st.session_state.history:
            for s in reversed(st.session_state.history):
                with st.container(border=True):
                    st.write(f"**Date:** {s['info']['date']} | **Observer:** {s['info']['observer']}")
                    col_ex1, col_ex2 = st.columns(2)
                    with col_ex1:
                        st.download_button("💾 Excel", export_excel(s['data']), f"Queue_{s['info']['date']}.xlsx", key=f"ex_{s['info']['start_ts']}")
                    with col_ex2:
                        st.download_button("📄 PDF", export_pdf(s['info'], s['data']), f"Report_{s['info']['date']}.pdf", key=f"pdf_{s['info']['start_ts']}")
        else:
            st.info("No completed sessions yet.")

# ==========================================
# PANTALLA 2: WORKSPACE (ÁREA DE TRABAJO)
# ==========================================
else:
    h1, h2 = st.columns([4, 1])
    h1.title("Real-Time Queue Registration")
    
    if h2.button("⏹ END SESSION", type="secondary", use_container_width=True):
        st.session_state.history.append({"info": st.session_state.active_session, "data": list(st.session_state.customers)})
        st.session_state.active_session = None
        st.rerun()

    st.write("---")

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        if st.button("➕ REGISTER NEW ARRIVAL", type="primary", use_container_width=True):
            st.session_state.customers.append({
                "Customer ID": f"C{st.session_state.counter:03d}",
                "Status": "Waiting",
                "Queue Position": "-",
                "Arrival_ts": time.time(),
                "Arrival Time": datetime.now().strftime("%I:%M:%S %p"),
                "Start_ts": None, "Service Start Time": "-", 
                "End_ts": None, "Service End Time": "-",
                "Wait_Sec": None, "Service_Sec": None, "Total_Sec": None, "Notes": ""
            })
            st.session_state.counter += 1
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
                    sc1.markdown(f"**{c['Customer ID']}**")
                    sc2.markdown(f'<div class="pill-orange" style="float:right;">Position {i+1}</div>', unsafe_allow_html=True)
                    st.caption(f"Arrival: {c['Arrival Time']}")
                    
                    if st.button("Start Service", key=f"s_{c['Customer ID']}", type="primary"):
                        for item in st.session_state.customers:
                            if item['Customer ID'] == c['Customer ID']:
                                item['Status'] = 'In Service'
                                item['Queue Position'] = "-"
                                item['Start_ts'] = time.time()
                                item['Service Start Time'] = datetime.now().strftime("%I:%M:%S %p")
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
                    sc1.markdown(f"**{c['Customer ID']}**")
                    sc2.markdown('<div class="pill-blue" style="float:right;">In Service</div>', unsafe_allow_html=True)
                    st.caption(f"Service start: {c['Service Start Time']}")
                    
                    if st.button("End Service", key=f"e_{c['Customer ID']}", type="primary"):
                        for item in st.session_state.customers:
                            if item['Customer ID'] == c['Customer ID']:
                                item['Status'] = 'Completed'
                                item['End_ts'] = time.time()
                                item['Service End Time'] = datetime.now().strftime("%I:%M:%S %p")
                                item['Wait_Sec'] = item['Start_ts'] - item['Arrival_ts']
                                item['Service_Sec'] = item['End_ts'] - item['Start_ts']
                                item['Total_Sec'] = item['End_ts'] - item['Arrival_ts']
                        st.rerun()

    st.markdown(f'<div class="pill-blue" style="display:inline-block; margin-top:10px;">Completed customers: {len(comp_list)}</div>', unsafe_allow_html=True)
    st.write("---")

    st.subheader("📝 Live Registration Database")
    
    if st.session_state.customers:
        df = pd.DataFrame(st.session_state.customers)
        
        wait_counter = 1
        for index, row in df.iterrows():
            if row['Status'] == 'Waiting':
                df.at[index, 'Queue Position'] = wait_counter
                wait_counter += 1
            elif row['Status'] == 'Completed':
                df.at[index, 'Status'] = '✅ Completed'

        df['Waiting Time'] = df['Wait_Sec'].apply(format_time)
        df['Service Time'] = df['Service_Sec'].apply(format_time)
        df['Total Time in System'] = df['Total_Sec'].apply(format_time)
        
        show_cols = ['Customer ID', 'Arrival Time', 'Service Start Time', 'Service End Time', 'Status', 'Queue Position', 'Waiting Time', 'Service Time', 'Total Time in System', 'Notes']
        
        st.data_editor(df[show_cols], use_container_width=True, hide_index=True, num_rows="dynamic")
        
        st.write("")
        with st.expander("🗑️ Delete a Record (Correction)"):
            st.write("Select the Customer ID below to delete it from the database.")
            col_del1, col_del2 = st.columns([2, 1])
            with col_del1:
                id_to_delete = st.selectbox("Select Customer ID", [c['Customer ID'] for c in st.session_state.customers])
            with col_del2:
                st.write("")
                st.write("")
                if st.button("Delete Customer", type="primary"):
                    st.session_state.customers = [c for c in st.session_state.customers if c['Customer ID'] != id_to_delete]
                    st.rerun()
                    
        st.write("")
        col_export1, col_export2 = st.columns([1, 1])
        with col_export1:
            st.download_button("💾 Export Data to Excel", export_excel(st.session_state.customers), f"Live_Data_{st.session_state.active_session['date']}.xlsx")
        with col_export2:
            st.download_button("📄 Export Data to PDF", export_pdf(st.session_state.active_session, st.session_state.customers), f"Live_Report_{st.session_state.active_session['date']}.pdf")
            
    else:
        st.caption("Records will appear here once you register an arrival.")
