import streamlit as st
import pandas as pd
import gspread

# Page Configuration
st.set_page_config(page_title="EMPOWER Teacher Portal", page_icon="🔒", layout="wide")

# --- DATABASE CONNECTION ---
@st.cache_resource
def connect_to_gsheet():
    creds = dict(st.secrets["connections"]["gsheets"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds)
    sheet_url = creds.get("spreadsheet")
    return gc.open_by_url(sheet_url)

# --- LOGIN & AUTHENTICATION ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔒 Teacher & Counselor Portal")
        st.subheader("Fatima National High School - EMPOWER Admin")
        
        password = st.text_input("Enter Passcode:", type="password")
        if st.button("Login to Dashboard"):
            # Fetch passcode from Streamlit secrets (default fallback provided)
            admin_pass = st.secrets.get("ADMIN_PASSWORD", "fnhs2026")
            if password == admin_pass:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect Passcode. Access Denied.")
    return False

# --- MAIN ADMIN DASHBOARD ---
if check_password():
    st.sidebar.title("Teacher Panel")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

    st.title("📊 EMPOWER Response Analytics")
    
    try:
        sh = connect_to_gsheet()
        tab1, tab2 = st.tabs(["📋 Weekly Pulse Check-Ins", "🏅 Kindness Badges Log"])

        # TAB 1: PULSE CHECK-INS
        with tab1:
            st.header("Pulse Check-Ins & Counselor Requests")
            ws = sh.worksheet("Pulse Checkins")
            df = pd.DataFrame(ws.get_all_records())

            if not df.empty:
                # Highlight Urgent Counselor Requests
                if "Counselor Request" in df.columns:
                    reqs = df[df["Counselor Request"].astype(str).str.strip() != ""]
                    if not reqs.empty:
                        st.warning(f"⚠️ **{len(reqs)} Student(s) Requested Confidential Counselor Support**")
                        st.dataframe(reqs[["Timestamp", "Student LRN", "Counselor Request"]], use_container_width=True)

                st.subheader("All Student Submissions")
                st.dataframe(df, use_container_width=True)

                # Export Option
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Pulse Check-Ins (CSV)", data=csv, file_name="pulse_checkins.csv", mime="text/csv")
            else:
                st.info("No pulse check-ins submitted yet.")

        # TAB 2: KINDNESS BADGES
        with tab2:
            st.header("Kindness Badges Sent")
            ws_b = sh.worksheet("Kindness Badges")
            df_b = pd.DataFrame(ws_b.get_all_records())

            if not df_b.empty:
                st.dataframe(df_b, use_container_width=True)
                csv_b = df_b.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Kindness Badges (CSV)", data=csv_b, file_name="kindness_badges.csv", mime="text/csv")
            else:
                st.info("No kindness badges sent yet.")

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {e}")
