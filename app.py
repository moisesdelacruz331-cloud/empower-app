import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

st.set_page_config(page_title="EMPOWER | Student Space", page_icon="🌱", layout="centered")

@st.cache_resource
def connect_to_gsheet():
    creds = dict(st.secrets["connections"]["gsheets"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds)
    return gc.open_by_url(creds.get("spreadsheet"))

@st.cache_data(ttl=10)
def load_student_pins():
    try:
        sh = connect_to_gsheet()
        ws = sh.worksheet("Class Configuration")
        df = pd.DataFrame(ws.get_all_records())
        # Convert to dictionary {Student_PIN: Section_Name}
        pin_map = {}
        for _, row in df.iterrows():
            s_pin = str(row["Student PIN"]).strip()
            sec = str(row["Class/Section"]).strip()
            if s_pin and sec:
                pin_map[s_pin] = sec
        return pin_map
    except Exception:
        return {}

try:
    sh = connect_to_gsheet()
except Exception:
    st.warning("Running in offline mode.")

st.title("🌱 EMPOWER Student Space")

# --- PIN VERIFICATION ---
st.markdown("### 🔑 Step 1: Verify Your Class")
student_pins = load_student_pins()

input_pin = st.text_input("Enter your Class PIN:", type="password", help="Ask your teacher or counselor for your PIN.").strip()

if input_pin in student_pins:
    assigned_section = student_pins[input_pin]
    st.success(f"Verified: **Section {assigned_section}**")
    st.markdown("---")

    tab1, tab2 = st.tabs(["💬 Weekly Reflection", "💌 Send Kindness Badge"])

    # TAB 1: REFLECTION
    with tab1:
        with st.form("pulse_form", clear_on_submit=True):
            lrn = st.text_input("Learner Reference Number (LRN)")
            kind_peer = st.text_input("✨ Who showed kindness to you this week?")
            groupmate = st.text_input("🤝 Who would you like to sit/work with next week?")
            isolated_peer = st.text_input("🫂 Who in class seems quiet or left out lately?")
            counselor_request = st.text_area("🕊️ Request Confidential Chat with Counselor (Optional)")
            
            submitted = st.form_submit_button("Submit Confidential Check-In")

            if submitted:
                if lrn.strip():
                    try:
                        ws = sh.worksheet("Pulse Checkins")
                        ws.append_row([
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            assigned_section,
                            lrn.strip(),
                            kind_peer,
                            groupmate,
                            isolated_peer,
                            counselor_request
                        ])
                        st.success("💚 Response submitted confidentially!")
                    except Exception as e:
                        st.error(f"Error submitting entry: {e}")
                else:
                    st.error("Please enter your LRN.")

    # TAB 2: KINDNESS BADGES
    with tab2:
        with st.form("badge_form", clear_on_submit=True):
            recipient = st.text_input("Recipient Name")
            badge_type = st.selectbox("Badge Type", ["Quiet Hero", "Good Listener", "Team Player", "Sunshine Friend"])
            note = st.text_area("Short Note (Optional)")
            
            badge_submitted = st.form_submit_button("Send Kindness Badge ✨")

            if badge_submitted:
                if recipient.strip():
                    try:
                        ws = sh.worksheet("Kindness Badges")
                        ws.append_row([
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            assigned_section,
                            recipient.strip(),
                            badge_type,
                            note
                        ])
                        st.balloons()
                        st.success(f"Kindness badge sent to {recipient}!")
                    except Exception as e:
                        st.error(f"Error sending badge: {e}")
                else:
                    st.error("Please enter the recipient's name.")

elif input_pin:
    st.error("Invalid Class PIN. Please double-check with your adviser.")
