import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
import re

# Page Configuration
st.set_page_config(page_title="EMPOWER Teacher & Counselor Portal", page_icon="📊", layout="wide")

# Custom CSS for Teacher Dashboard
st.markdown("""
    <style>
    .metric-card {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 16px;
        border: 1px solid #E2E8F0;
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.03);
    }
    .alert-high {
        background-color: #FEF2F2;
        border-left: 5px solid #EF4444;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .alert-watch {
        background-color: #FFFBEB;
        border-left: 5px solid #F59E0B;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTIONS ---
@st.cache_resource
def connect_to_gsheet():
    creds = dict(st.secrets["connections"]["gsheets"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds)
    return gc.open_by_url(creds.get("spreadsheet"))

@st.cache_data(ttl=10)
def load_pin_config():
    try:
        sh = connect_to_gsheet()
        ws = sh.worksheet("Class Configuration")
        df = pd.DataFrame(ws.get_all_records())
        return df
    except Exception:
        return pd.DataFrame(columns=["Class/Section", "Student PIN", "Teacher PIN"])

# Helper function to extract Mood and clean text
def parse_mood_and_requests(df):
    if df.empty:
        df["Mood"] = []
        df["Clean_Counselor_Request"] = []
        return df
    
    if "Counselor Request" in df.columns:
        # Extract mood tag like [Mood: 🌧️ Overwhelmed]
        df['Mood'] = df['Counselor Request'].astype(str).str.extract(r'\[Mood:\s*([^\]]+)\]')
        df['Mood'] = df['Mood'].fillna("🌱 Not Specified")
        
        # Clean request string for display
        df['Clean_Counselor_Request'] = df['Counselor Request'].astype(str).str.replace(r'\[Mood:\s*([^\]]+)\]\s*', '', regex=True)
    else:
        df['Mood'] = "🌱 Not Specified"
        df['Clean_Counselor_Request'] = ""
        
    return df

# --- AUTHENTICATION ---
if "auth_role" not in st.session_state:
    st.session_state.auth_role = None
    st.session_state.auth_section = None

if not st.session_state.auth_role:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔒 EMPOWER Staff Portal")
        login_pin = st.text_input("Enter Teacher PIN / Passcode:", type="password").strip()
        
        if st.button("Login to Analytics"):
            counselor_pass = str(st.secrets.get("ADMIN_PASSWORD", "COUNSELOR2026")).strip()
            
            if login_pin == counselor_pass:
                st.session_state.auth_role = "Counselor"
                st.session_state.auth_section = "ALL"
                st.rerun()
            else:
                pin_df = load_pin_config()
                if not pin_df.empty and "Teacher PIN" in pin_df.columns:
                    matched = pin_df[pin_df["Teacher PIN"].astype(str).str.strip() == login_pin]
                    if not matched.empty:
                        st.session_state.auth_role = "Teacher"
                        st.session_state.auth_section = matched.iloc[0]["Class/Section"]
                        st.rerun()
                    else:
                        st.error("Invalid Passcode or Teacher PIN.")
                else:
                    st.error("Invalid Passcode.")

else:
    # --- LOGGED IN DASHBOARD ---
    role = st.session_state.auth_role
    assigned_section = st.session_state.auth_section
    
    st.sidebar.title("📊 Staff Analytics")
    st.sidebar.write(f"Role: **{role}**")
    st.sidebar.write(f"Assigned Scope: **{assigned_section}**")
    
    if st.sidebar.button("Logout"):
        st.session_state.auth_role = None
        st.session_state.auth_section = None
        st.cache_data.clear()
        st.rerun()

    sh = connect_to_gsheet()

    # Load Data
    ws_pulse = sh.worksheet("Pulse Checkins")
    raw_pulse = pd.DataFrame(ws_pulse.get_all_records())
    df_pulse = parse_mood_and_requests(raw_pulse)

    if not df_pulse.empty and "Class/Section" in df_pulse.columns:
        if assigned_section != "ALL":
            df_pulse = df_pulse[df_pulse["Class/Section"] == assigned_section]

    st.title(f"🏫 Classroom Wellbeing Overview: {assigned_section}")
    st.caption("Real-time emotional climate, peer support dynamics, and intervention alerts.")

    # --- TOP LEVEL METRICS ---
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    
    total_submissions = len(df_pulse) if not df_pulse.empty else 0
    overwhelmed_count = len(df_pulse[df_pulse['Mood'].str.contains("Overwhelmed", na=False)]) if not df_pulse.empty else 0
    counselor_req_count = len(df_pulse[df_pulse['Clean_Counselor_Request'].str.strip() != ""]) if not df_pulse.empty else 0
    
    # Isolated peers count
    isolated_list = df_pulse['Isolated Peer'].dropna().astype(str).str.strip() if not df_pulse.empty else pd.Series()
    isolated_list = isolated_list[isolated_list != ""]
    
    col_m1.metric("Total Check-Ins", total_submissions)
    col_m2.metric("Overwhelmed Students", overwhelmed_count, delta_color="inverse")
    col_m3.metric("Counselor Requests", counselor_req_count)
    col_m4.metric("Isolated Peers Flagged", len(isolated_list))

    st.markdown("---")

    # --- DECISION SUPPORT & IMMEDIATE RISK ALERTS ---
    st.subheader("🚨 Priority Action & Support Center")
    
    if not df_pulse.empty:
        # High Priority: Overwhelmed OR Requested Counselor
        high_risk = df_pulse[
            (df_pulse['Mood'].str.contains("Overwhelmed", na=False)) | 
            (df_pulse['Clean_Counselor_Request'].str.strip() != "")
        ]
        
        if not high_risk.empty:
            st.markdown(f"""
                <div class="alert-high">
                    <b>⚠️ Attention Needed:</b> {len(high_risk)} student submission(s) indicate emotional distress or request guidance support.
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("View High-Priority Student List", expanded=True):
                st.dataframe(
                    high_risk[["Timestamp", "Class/Section", "Student LRN", "Mood", "Clean_Counselor_Request"]],
                    use_container_width=True
                )
        else:
            st.success("✅ No critical distress alerts or pending counselor requests in this view.")

    # --- MAIN NAVIGATION TABS ---
    if role == "Counselor":
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Mood Visualizations", "🫂 Peer Inclusion Watchlist", "📋 Full Logs", "⚙️ PIN Manager"])
    else:
        tab1, tab2, tab3 = st.tabs(["📈 Mood Visualizations", "🫂 Peer Inclusion Watchlist", "📋 Full Logs"])

    # TAB 1: VISUAL ANALYTICS
    with tab1:
        st.subheader("📊 Emotional Climate Analytics")
        col_chart1, col_chart2 = st.columns(2)
        
        if not df_pulse.empty and "Mood" in df_pulse.columns:
            with col_chart1:
                st.markdown("##### Mood Distribution")
                mood_counts = df_pulse['Mood'].value_counts().reset_index()
                mood_counts.columns = ['Mood', 'Count']
                
                fig_bar = px.bar(
                    mood_counts, 
                    x='Mood', 
                    y='Count', 
                    color='Mood',
                    title="Student Self-Reported Moods",
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)
                
            with col_chart2:
                st.markdown("##### Emotional Breakdown Share")
                fig_pie = px.pie(
                    mood_counts, 
                    names='Mood', 
                    values='Count', 
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No mood data available yet to display graphs.")

    # TAB 2: PEER INCLUSION & ISOLATION WATCHLIST
    with tab2:
        st.subheader("🫂 Classroom Social Health & Isolation Watchlist")
        st.caption("Students listed here were identified by classmates as quiet, overwhelmed, or left out.")

        if not df_pulse.empty and "Isolated Peer" in df_pulse.columns:
            isolated_df = df_pulse[df_pulse['Isolated Peer'].astype(str).str.strip() != ""][["Timestamp", "Class/Section", "Isolated Peer", "Kind Peer", "Preferred Groupmate"]]
            
            if not isolated_df.empty:
                st.markdown("""
                    <div class="alert-watch">
                        <b>💡 Advisory Action:</b> Consider pairing students flagged as quiet/left out with nominated 'Kind Peers' or preferred groupmates during class activities.
                    </div>
                """, unsafe_allow_html=True)
                
                st.dataframe(isolated_df, use_container_width=True)
            else:
                st.info("No students have been flagged as left out or quiet by peers yet.")
        else:
            st.info("No isolation data recorded yet.")

    # TAB 3: FULL LOGS
    with tab3:
        st.subheader("📋 Complete Pulse Check-In Records")
        if not df_pulse.empty:
            st.dataframe(df_pulse[["Timestamp", "Class/Section", "Student LRN", "Mood", "Kind Peer", "Preferred Groupmate", "Isolated Peer", "Clean_Counselor_Request"]], use_container_width=True)
            
            csv = df_pulse.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export Records (CSV)", data=csv, file_name="student_pulse_records.csv", mime="text/csv")
        else:
            st.info("No records found.")

    # TAB 4: COUNSELOR PIN MANAGEMENT
    if role == "Counselor":
        with tab4:
            st.subheader("⚙️ Manage Sections & Access PINs")
            pin_df = load_pin_config()

            with st.form("add_sec_form", clear_on_submit=True):
                col_a, col_b, col_c = st.columns(3)
                nsec = col_a.text_input("Section Name")
                spin = col_b.text_input("Student PIN")
                tpin = col_c.text_input("Teacher PIN")
                
                if st.form_submit_button("Save Section"):
                    if nsec and spin and tpin:
                        ws_c = sh.worksheet("Class Configuration")
                        ws_c.append_row([nsec.strip(), spin.strip(), tpin.strip()])
                        st.cache_data.clear()
                        st.success("Section added!")
                        st.rerun()

            st.dataframe(pin_df, use_container_width=True)
