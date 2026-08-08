import streamlit as st
import gspread
from datetime import datetime

st.set_page_config(page_title="EMPOWER | Student Space", page_icon="🌱", layout="centered")

# --- CLASS PIN CONFIGURATION ---
CLASS_PINS = {
    "1001": "10 - Emerald",
    "1002": "10 - Ruby",
    "1003": "10 - Sapphire"
}

# --- DATABASE CONNECTION ---
@st.cache_resource
def connect_to_gsheet():
    creds = dict(st.secrets["connections"]["gsheets"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds)
    return gc.open_by_url(creds.get("spreadsheet"))

try:
    sh = connect_to_gsheet()
except Exception:
    st.warning("App running in demo mode.")

st.title("🌱 EMPOWER Student Space")

# --- CLASS ACCESS CONTROL ---
st.markdown("### 🔑 Step 1: Verify Your Class")
input_pin = st.text_input("Enter your 4-digit Class PIN:", type="password", help="Ask your adviser for your section's PIN.")

if input_pin.strip() in CLASS_PINS:
    assigned_section = CLASS_PINS[input_pin.strip()]
    st.success(f"Verified: **Section {assigned_section}**")
    
    st.markdown("---")
    tab1, tab2 = st.tabs(["💬 Weekly Reflection", "💌 Send Kindness Badge"])

    # TAB 1: PULSE CHECK-IN
    with tab1:
        with st.form("pulse_form", clear_on_submit=True):
            lrn = st.text_input("Learner Reference Number (LRN)", placeholder="123456789012")
            kind_peer = st.text_input("✨ Who showed kindness to you this week?")
            groupmate = st.text_input("🤝 Who would you like to sit/work with next week?")
            isolated_peer = st.text_input("🫂 Who in class seems quiet or left out lately?")
            counselor_request = st.text_area("🕊️ Request Confidential Chat with Counselor (Optional)")
            
            submitted = st.form_submit_button("Submit Confidential Check-In")

            if submitted:
                if lrn.strip():
                    try:
                        ws = sh.worksheet("Pulse Checkins")
                        row_data = [
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            assigned_section,
                            lrn.strip(),
                            kind_peer,
                            groupmate,
                            isolated_peer,
                            counselor_request
                        ]
                        ws.append_row(row_data)
                        st.success("💚 Response saved successfully!")
                    except Exception as e:
                        st.error(f"Error saving entry: {e}")
                else:
                    st.error("Please enter your LRN.")

    # TAB 2: KINDNESS BADGES
    with tab2:
        with st.form("badge_form", clear_on_submit=True):
            recipient = st.text_input("Recipient Student Name")
            badge_type = st.selectbox("Badge Type", ["Quiet Hero", "Good Listener", "Team Player", "Sunshine Friend"])
            note = st.text_area("Appreciation Note (Optional)")
            
            badge_submitted = st.form_submit_button("Send Kindness Badge ✨")

            if badge_submitted:
                if recipient.strip():
                    try:
                        ws = sh.worksheet("Kindness Badges")
                        row_data = [
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            assigned_section,
                            recipient.strip(),
                            badge_type,
                            note
                        ]
                        ws.append_row(row_data)
                        st.balloons()
                        st.success(f"Badge sent to {recipient}!")
                    except Exception as e:
                        st.error(f"Error sending badge: {e}")
                else:
                    st.error("Please enter the recipient's name.")

elif input_pin:
    st.error("Invalid Class PIN. Please check with your teacher.")
