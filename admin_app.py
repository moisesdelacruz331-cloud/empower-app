import streamlit as st
import pandas as pd
import gspread

st.set_page_config(page_title="EMPOWER Admin Portal", page_icon="🔒", layout="wide")

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

# --- AUTHENTICATION ---
if "auth_role" not in st.session_state:
    st.session_state.auth_role = None
    st.session_state.auth_section = None

if not st.session_state.auth_role:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔒 EMPOWER Staff Portal")
        login_pin = st.text_input("Enter Passcode / Teacher PIN:", type="password").strip()
        
        if st.button("Login"):
            counselor_pass = str(st.secrets.get("ADMIN_PASSWORD", "COUNSELOR2026")).strip()
            
            # 1. Master Counselor Access
            if login_pin == counselor_pass:
                st.session_state.auth_role = "Counselor"
                st.session_state.auth_section = "ALL"
                st.rerun()
            
            # 2. Dynamic Teacher Access
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
    
    st.sidebar.title("Staff Panel")
    st.sidebar.write(f"Role: **{role}**")
    st.sidebar.write(f"Section: **{assigned_section}**")
    
    if st.sidebar.button("Logout"):
        st.session_state.auth_role = None
        st.session_state.auth_section = None
        st.cache_data.clear()
        st.rerun()

    sh = connect_to_gsheet()

    # Counselor gets an extra tab for PIN Management
    if role == "Counselor":
        tab1, tab2, tab3 = st.tabs(["💬 Pulse Check-Ins", "🏅 Kindness Badges", "⚙️ Section & PIN Manager"])
    else:
        tab1, tab2 = st.tabs(["💬 Pulse Check-Ins", "🏅 Kindness Badges"])

    # TAB 1: PULSE CHECK-INS
    with tab1:
        st.header("Weekly Pulse Check-Ins")
        ws = sh.worksheet("Pulse Checkins")
        df = pd.DataFrame(ws.get_all_records())

        if not df.empty and "Class/Section" in df.columns:
            filtered_df = df if assigned_section == "ALL" else df[df["Class/Section"] == assigned_section]
            st.subheader(f"Total Entries: {len(filtered_df)}")
            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.info("No entries recorded yet.")

    # TAB 2: KINDNESS BADGES
    with tab2:
        st.header("Kindness Badges Log")
        ws_b = sh.worksheet("Kindness Badges")
        df_b = pd.DataFrame(ws_b.get_all_records())

        if not df_b.empty and "Class/Section" in df_b.columns:
            filtered_df_b = df_b if assigned_section == "ALL" else df_b[df_b["Class/Section"] == assigned_section]
            st.subheader(f"Total Badges: {len(filtered_df_b)}")
            st.dataframe(filtered_df_b, use_container_width=True)
        else:
            st.info("No badges recorded yet.")

    # TAB 3: COUNSELOR PIN MANAGEMENT
    if role == "Counselor":
        with tab3:
            st.header("⚙️ Manage Sections & Access PINs")
            st.caption("Create section PINs for students and teachers. Changes take effect immediately.")

            pin_df = load_pin_config()

            # Form to add new section
            with st.form("add_section_form", clear_on_submit=True):
                st.subheader("➕ Add New Class Section")
                col_a, col_b, col_c = st.columns(3)
                
                new_section = col_a.text_input("Section Name", placeholder="e.g., 10 - Emerald")
                new_student_pin = col_b.text_input("Student Class PIN", placeholder="e.g., 1001")
                new_teacher_pin = col_c.text_input("Teacher Passcode/PIN", placeholder="e.g., EMERALD2026")
                
                submitted = st.form_submit_button("Save Section & Assign PINs")

                if submitted:
                    if new_section.strip() and new_student_pin.strip() and new_teacher_pin.strip():
                        try:
                            ws_config = sh.worksheet("Class Configuration")
                            ws_config.append_row([
                                new_section.strip(),
                                new_student_pin.strip(),
                                new_teacher_pin.strip()
                            ])
                            st.cache_data.clear()
                            st.success(f"Added section **{new_section}** successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error saving to Google Sheet: {e}")
                    else:
                        st.error("Please fill in all 3 fields.")

            st.markdown("---")
            st.subheader("📋 Existing Class Configurations")
            if not pin_df.empty:
                st.dataframe(pin_df, use_container_width=True)
            else:
                st.info("No class sections configured yet.")
