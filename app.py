import streamlit as st
import gspread
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="EMPOWER | Safe Student Space", 
    page_icon="🌱", 
    layout="centered"
)

# --- CUSTOM CSS: Soft, Calming, & High-Trust UI ---
st.markdown("""
    <style>
    /* Main Background: Soft, soothing pastel gradient */
    .stApp {
        background: linear-gradient(180deg, #F4F8F7 0%, #EBF3F5 100%);
    }

    /* Hide standard header/footer clutter */
    header {visibility: hidden;}
    footer {visibility: hidden;}

    /* Custom Container Styling */
    .hero-card {
        background-color: #FFFFFF;
        padding: 24px;
        border-radius: 20px;
        box-shadow: 0px 8px 20px rgba(59, 130, 246, 0.05);
        border: 1px solid #E2E8F0;
        text-align: center;
        margin-bottom: 20px;
    }

    .privacy-badge {
        background-color: #EBF5EE;
        border: 1px solid #B8E0D2;
        color: #2D6A4F;
        padding: 12px 16px;
        border-radius: 12px;
        font-size: 0.9rem;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    /* Tab Styling: Soothing & Rounded */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #E2ECCE;
        padding: 6px;
        border-radius: 16px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 12px;
        padding: 10px 20px;
        color: #4A5568;
        font-weight: 600;
    }

    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #2D6A4F !important;
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.04);
    }

    /* Buttons: Friendly, inviting, non-aggressive */
    .stButton > button {
        background-color: #52B788 !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 28px !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        transition: all 0.2s ease-in-out;
        box-shadow: 0px 4px 12px rgba(82, 183, 136, 0.3) !important;
    }

    .stButton > button:hover {
        background-color: #40916C !important;
        transform: translateY(-1px);
    }

    /* Form Fields Styling */
    .stTextInput > div > div > input, .stTextArea > div > div > textarea {
        border-radius: 12px !important;
        border: 1px solid #CBD5E1 !important;
        background-color: #FAFAFA !important;
    }

    .stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus {
        border-color: #52B788 !important;
        background-color: #FFFFFF !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION (gspread) ---
@st.cache_resource
def connect_to_gsheet():
    creds = dict(st.secrets["connections"]["gsheets"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds)
    sheet_url = creds.get("spreadsheet")
    return gc.open_by_url(sheet_url)

# Test Connection silently
try:
    sh = connect_to_gsheet()
except Exception:
    st.warning("🌱 App is running in offline demo mode.")

# --- HERO HEADER ---
st.markdown("""
    <div class="hero-card">
        <h2 style="color: #2D6A4F; margin-bottom: 4px; font-weight: 700;">🌱 EMPOWER Safe Space</h2>
        <p style="color: #64748B; margin: 0; font-size: 0.95rem;">Fatima National High School</p>
        <p style="color: #475569; margin-top: 8px; font-size: 0.9rem;">
            Take a quiet moment for yourself. Your voice matters, and your feelings are always valid.
        </p>
    </div>
""", unsafe_allow_html=True)

# --- CONFIDENTIALITY BADGE ---
st.markdown("""
    <div class="privacy-badge">
        🔒 <b>Your Privacy is Safe Here:</b> Your check-ins are completely confidential and read only by your trusted guidance counselor.
    </div>
""", unsafe_allow_html=True)

# --- MAIN TABS ---
tab1, tab2 = st.tabs(["💬 Weekly Reflection", "💌 Send Kindness Badge"])

# --- TAB 1: WEEKLY REFLECTION ---
with tab1:
    st.markdown("##### How are things going this week?")
    st.caption("Feel free to share as much or as little as you feel comfortable with.")

    with st.form("pulse_form", clear_on_submit=True):
        lrn = st.text_input("Learner Reference Number (LRN)", placeholder="e.g., 123456789012")
        
        kind_peer = st.text_input(
            "✨ Peer Appreciation", 
            placeholder="Who showed kindness or made you smile this week?"
        )
        
        groupmate = st.text_input(
            "🤝 Group Preference", 
            placeholder="Who is someone you'd feel comfortable working/sitting with next week?"
        )
        
        isolated_peer = st.text_input(
            "🫂 Reaching Out", 
            placeholder="Who in class seems quiet, overwhelmed, or might need a little extra care?"
        )
        
        counselor_request = st.text_area(
            "🕊️ Guidance Support (Confidential)", 
            placeholder="Would you like to have a private, friendly chat with your counselor? Let us know how we can support you today...",
            height=100
        )

        submitted = st.form_submit_button("Submit Confidential Check-In")

        if submitted:
            if lrn.strip():
                try:
                    worksheet = sh.worksheet("Pulse Checkins")
                    row_data = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        lrn,
                        kind_peer,
                        groupmate,
                        isolated_peer,
                        counselor_request
                    ]
                    worksheet.append_row(row_data)
                    st.success("💚 Thank you for checking in! Your response has been received safely.")
                except Exception as err:
                    st.error("We couldn't save your check-in right now. Please try again in a moment.")
            else:
                st.info("Please enter your LRN so we can associate your response correctly.")

# --- TAB 2: KINDNESS BADGES ---
with tab2:
    st.markdown("##### Spread Positivity")
    st.caption("Brighten a classmate's day by sending them a quiet note of appreciation!")

    with st.form("badge_form", clear_on_submit=True):
        recipient = st.text_input("Who are you sending this badge to?", placeholder="Classmate's Full Name")
        
        badge_type = st.selectbox(
            "Choose a Kindness Badge",
            [
                "🌟 Quiet Hero (Always helpful)", 
                "🎧 Good Listener (Comforting & present)", 
                "🤝 Team Player (Includes everyone)", 
                "💛 Sunshine Friend (Brings joy & kindness)"
            ]
        )
        
        note = st.text_area(
            "Write a short note of encouragement (Optional)", 
            placeholder="e.g., Thank you for helping me with our math problem yesterday!",
            height=80
        )

        badge_submitted = st.form_submit_button("Send Kindness Badge ✨")

        if badge_submitted:
            if recipient.strip():
                try:
                    worksheet = sh.worksheet("Kindness Badges")
                    row_data = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        recipient,
                        badge_type,
                        note
                    ]
                    worksheet.append_row(row_data)
                    st.balloons()
                    st.success(f"🎉 Kindness badge successfully sent to {recipient}!")
                except Exception as err:
                    st.error("Unable to send badge right now. Please check back shortly.")
            else:
                st.info("Please enter your classmate's name before sending.")
