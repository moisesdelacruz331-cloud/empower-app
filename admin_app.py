import streamlit as st
import pandas as pd
import gspread

st.set_page_config(page_title="EMPOWER Teacher Portal", page_icon="🔒", layout="wide")

# --- TEACHER PIN MAPPING ---
# Format: "PASSCODE": "SECTION_NAME"
# Use "ALL" for Guidance Counselor access across all classes
TEACHER_PINS = {
    "EMERALD2026": "10 - Emerald",
    "RUBY2026": "10 - Ruby",
    "SAPPHIRE2026": "10 - Sapphire",
    "COUNSELOR2026": "ALL"
}

@st.cache_resource
def connect_to_gsheet():
    creds = dict(st.secrets["connections"]["gsheets"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds)
    return gc.open_by_url(creds.get("spreadsheet"))

# LOGIN FUNCTIONALITY
if "auth_section" not in st.session_state:
    st.session_state.auth_section = None

if not st.session_state.auth_section:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔒 Teacher & Counselor Portal")
        teacher_pin = st.text_input("Enter Teacher Passcode:", type="password")
        if st.button("Login"):
            pin_clean = teacher_pin.strip()
            if pin_clean in TEACHER_PINS:
                st.session_state.auth_section = TEACHER_PINS[pin_clean]
                st.rerun()
            else:
                st.error("Invalid Passcode. Access Denied.")
else:
    assigned_section = st.session_state.auth_section
    
    st.sidebar.title("Teacher Panel")
    st.sidebar.write(f"Logged in for: **{assigned_section}**")
    if st.sidebar.button("Logout"):
        st.session_state.auth_section = None
        st.rerun()

    st.title(f"📊 Responses for {assigned_section}")

    try:
        sh = connect_to_gsheet()
        tab1, tab2 = st.tabs(["💬 Pulse Check-Ins", "🏅 Kindness Badges"])

        # TAB 1: PULSE CHECK-INS
        with tab1:
            ws = sh.worksheet("Pulse Checkins")
            df = pd.DataFrame(ws.get_all_records())

            if not df.empty and "Class/Section" in df.columns:
                # Filter data for specific section unless logged in as Counselor (ALL)
                if assigned_section != "ALL":
                    filtered_df = df[df["Class/Section"] == assigned_section]
                else:
                    filtered_df = df

                st.subheader(f"Total Submissions: {len(filtered_df)}")
                st.dataframe(filtered_df, use_container_width=True)
            else:
                st.info("No responses found for your section yet.")

        # TAB 2: KINDNESS BADGES
        with tab2:
            ws_b = sh.worksheet("Kindness Badges")
            df_b = pd.DataFrame(ws_b.get_all_records())

            if not df_b.empty and "Class/Section" in df_b.columns:
                if assigned_section != "ALL":
                    filtered_df_b = df_b[df_b["Class/Section"] == assigned_section]
                else:
                    filtered_df_b = df_b

                st.subheader(f"Total Badges Sent: {len(filtered_df_b)}")
                st.dataframe(filtered_df_b, use_container_width=True)
            else:
                st.info("No badges found for your section yet.")

    except Exception as e:
        st.error(f"Error loading Google Sheet data: {e}")
