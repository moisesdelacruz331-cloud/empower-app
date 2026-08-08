import streamlit as st
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="EMPOWER - Student Check-In", page_icon="💙", layout="centered")

st.title("💙 EMPOWER App")
st.subheader("Fatima National High School")

# Tab Navigation
tab1, tab2 = st.tabs(["📋 Weekly Pulse Check-In", "🤝 Send Kindness Badge"])

# Tab 1: Weekly Pulse Check-In
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
                st.success("Thank you! Your response has been submitted confidentially.")
            else:
                st.error("Please enter your LRN before submitting.")

# Tab 2: Secret Kindness Badges
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
                st.balloons()
                st.success(f"Kindness badge '{badge_type}' sent to {recipient}!")
            else:
                st.error("Please enter the recipient's name.")
