import streamlit as st
import gspread
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="EMPOWER App", page_icon="💙", layout="centered")

# --- DATABASE CONNECTION (gspread) ---
@st.cache_resource
def connect_to_gsheet():
    # Load credentials dictionary from Streamlit Secrets
    creds = dict(st.secrets["connections"]["gsheets"])
    
    # Fix newline escaping issue common in Streamlit Cloud TOML secrets
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
        
    # Authorize client
    gc = gspread.service_account_from_dict(creds)
    
    # Open spreadsheet by URL provided in secrets
    sheet_url = creds.get("spreadsheet")
    return gc.open_by_url(sheet_url)

# Test Connection on App Load
try:
    sh = connect_to_gsheet()
    st.sidebar.success("✅ Google Sheets Connected")
except Exception as e:
    st.error(f"⚠️ Database Connection Error: {e}")
    st.info("Check that your Service Account email is added as an 'Editor' on your Google Sheet.")
    st.stop()

# --- APP INTERFACE ---
st.title("💙 EMPOWER App")
st.subheader("Fatima National High School")

tab1, tab2 = st.tabs(["📋 Weekly Pulse Check-In", "🤝 Send Kindness Badge"])

# --- TAB 1: PULSE CHECK-INS ---
with tab1:
    st.header("Weekly Pulse Check-In")
    with st.form("pulse_form", clear_on_submit=True):
        lrn = st.text_input("Your LRN (Learner Reference Number)")
        kind_peer = st.text_input("Who showed kindness to you this week?")
        groupmate = st.text_input("Who would you like to sit/work with next week?")
        isolated_peer = st.text_input("Who in class seems quiet or left out lately?")
        counselor_request = st.text_area("Request Confidential Chat with Counselor (Optional)")
        
        submitted = st.form_submit_button("Submit Check-In")
        if submitted:
            if lrn:
                try:
                    # Select target worksheet tab
                    worksheet = sh.worksheet("Pulse Checkins")
                    
                    # Row data array matching column order
                    row_data = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        lrn,
                        kind_peer,
                        groupmate,
                        isolated_peer,
                        counselor_request
                    ]
                    
                    # Append row directly to sheet
                    worksheet.append_row(row_data)
                    st.success("Thank you! Your response has been submitted confidentially.")
                except Exception as err:
                    st.error(f"Failed to save entry: {err}")
            else:
                st.error("Please enter your LRN before submitting.")

# --- TAB 2: KINDNESS BADGES ---
with tab2:
    st.header("Send a Secret Kindness Badge")
    with st.form("badge_form", clear_on_submit=True):
        recipient = st.text_input("Who are you sending this badge to?")
        badge_type = st.selectbox(
            "Select Badge Type",
            ["Good Listener", "Helpful Friend", "Quiet Hero", "Team Player"]
        )
        note = st.text_area("Write a short note of appreciation (Optional)")
        
        badge_submitted = st.form_submit_button("Send Badge")
        if badge_submitted:
            if recipient:
                try:
                    # Select target worksheet tab
                    worksheet = sh.worksheet("Kindness Badges")
                    
                    # Row data array
                    row_data = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        recipient,
                        badge_type,
                        note
                    ]
                    
                    # Append row directly
                    worksheet.append_row(row_data)
                    st.balloons()
                    st.success(f"Kindness badge '{badge_type}' sent to {recipient}!")
                except Exception as err:
                    st.error(f"Failed to send badge: {err}")
            else:
                st.error("Please enter the recipient's name.")
