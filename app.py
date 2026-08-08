from datetime import datetime
import hashlib
import re
import gspread
import pandas as pd
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="EMPOWER | Student Safe Haven", page_icon="🌱", layout="centered"
)

# --- HIDE STREAMLIT BRANDING & UI ELEMENTS ---
hide_streamlit_ui = """
    <style>
    /* Hide top header bar and navigation links */
    [data-testid="stHeader"] {
        display: none !important;
    }
    
    /* Hide bottom footer ("Made with Streamlit") */
    footer {
        visibility: hidden !important;
        display: none !important;
    }
    
    /* Hide top-right hamburger menu and deploy button */
    #MainMenu {
        visibility: hidden !important;
    }
    .stAppDeployButton {
        display: none !important;
    }
    [data-testid="stToolbar"] {
        display: none !important;
    }
    
    /* Hide top accent decoration bar */
    [data-testid="stDecoration"] {
        display: none !important;
    }
    </style>
"""
st.markdown(hide_streamlit_ui, unsafe_allow_html=True)

# --- SAFEGUARDING & PRIVACY UTILITIES ---
SALT_KEY = st.secrets.get("SALT_KEY", "EMPOWER_2026_SECURE_SALT")
PROFANITY_REGEX = r"(?i)\b(gago|tanga|bobo|tangina|penta|pUTA|ulol|fuck|shit|bitch|asshole|bastard)\b"
MALICIOUS_INPUT_REGEX = (
    r"(?i)(<script.*?>.*?</script>|<[^>]+>|SELECT\s+.*?\s+FROM|DROP\s+TABLE|OR\s+1=1)"
)


def generate_anonymous_id(raw_id: str, salt: str = SALT_KEY) -> str:
    """Converts a raw Learner Reference Number (LRN) or student identifier into a

    salted SHA-256 unique anonymous ID (e.g., STU-8A2F). Ensures raw identities
    are never stored in cloud databases.
    """
    if not raw_id or str(raw_id).strip() == "":
        return ""
    clean_id = str(raw_id).strip()
    salted_bytes = f"{clean_id}{salt}".encode("utf-8")
    hash_digest = hashlib.sha256(salted_bytes).hexdigest()
    return f"STU-{hash_digest[:4].upper()}"


def sanitize_input(text: str) -> str:
    """Filters profane language using regex and strips malicious injection vectors

    before persisting input to Google Sheets.
    """
    if not text or not isinstance(text, str):
        return ""

    sanitized = re.sub(
        MALICIOUS_INPUT_REGEX, "[BLOCKED_INPUT]", text, flags=re.IGNORECASE
    )
    sanitized = re.sub(
        PROFANITY_REGEX, "*****", sanitized, flags=re.IGNORECASE
    )

    return sanitized.strip()


# --- DAILY INSPIRATIONAL QUOTES & BIBLE VERSES ---
DAILY_INSPIRATIONS = [
    {
        "type": "📖 Scripture",
        "text": (
            "“For I know the plans I have for you,” declares the LORD, “plans"
            " to prosper you and not to harm you, plans to give you hope and a"
            " future.”"
        ),
        "author": "Jeremiah 29:11",
    },
    {
        "type": "🌱 Daily Affirmation",
        "text": (
            "“You are braver than you believe, stronger than you seem, and"
            " smarter than you think.”"
        ),
        "author": "A.A. Milne",
    },
    {
        "type": "📖 Scripture",
        "text": (
            "“Be strong and courageous. Do not be afraid; do not be"
            " discouraged, for the LORD your God will be with you wherever you"
            " go.”"
        ),
        "author": "Joshua 1:9",
    },
    {
        "type": "✨ Reflection",
        "text": (
            "“You don't have to carry everything all at once. Just focus on"
            " taking one gentle step today.”"
        ),
        "author": "Self-Care Reflection",
    },
    {
        "type": "📖 Scripture",
        "text": (
            "“Cast all your anxiety on Him because He cares for you.”"
        ),
        "author": "1 Peter 5:7",
    },
    {
        "type": "🌱 Daily Affirmation",
        "text": (
            "“Your feelings are valid, your voice matters, and your presence in"
            " this classroom makes a difference.”"
        ),
        "author": "EMPOWER Care Team",
    },
    {
        "type": "📖 Scripture",
        "text": (
            "“Peace I leave with you; my peace I give you. I do not give to you"
            " as the world gives. Do not let your hearts be troubled.”"
        ),
        "author": "John 14:27",
    },
]

day_of_year = datetime.now().timetuple().tm_yday
today_quote = DAILY_INSPIRATIONS[day_of_year % len(DAILY_INSPIRATIONS)]

# --- BADGES DICTIONARY ---
BADGE_DETAILS = {
    "🌟 Quiet Hero": {
        "icon": "🌟",
        "title": "Quiet Hero",
        "badge_tag": "Quiet Hero",
        "description": (
            "Always helping behind the scenes quietly without expecting praise"
            " or spotlight."
        ),
        "color": "#FFFBEB",
        "border": "#FCD34D",
    },
    "🎧 Good Listener": {
        "icon": "🎧",
        "title": "Good Listener",
        "badge_tag": "Good Listener",
        "description": (
            "Listens patiently with an open heart, offering comfort when a"
            " friend needs to talk."
        ),
        "color": "#EFF6FF",
        "border": "#93C5FD",
    },
    "🤝 Team Player": {
        "icon": "🤝",
        "title": "Team Player",
        "badge_tag": "Team Player",
        "description": (
            "Makes sure everyone is included, valued, and never left out during"
            " group activities."
        ),
        "color": "#F0FDF4",
        "border": "#86EFAC",
    },
    "☀️ Sunshine Friend": {
        "icon": "☀️",
        "title": "Sunshine Friend",
        "badge_tag": "Sunshine Friend",
        "description": (
            "Brings warmth, smiles, and positive energy that brightens up the"
            " whole classroom."
        ),
        "color": "#FEF3C7",
        "border": "#F59E0B",
    },
    "🛡️ Safe Harbor": {
        "icon": "🛡️",
        "title": "Safe Harbor",
        "badge_tag": "Safe Harbor",
        "description": (
            "A calm, trustworthy classmate who makes others feel physically and"
            " emotionally safe."
        ),
        "color": "#F3E8FF",
        "border": "#C084FC",
    },
}

# --- CUSTOM APP STYLING ---
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #F4F8F7 0%, #EBF3F5 100%);
    }

    .quote-box {
        background: #FFFFFF;
        border-left: 5px solid #52B788;
        padding: 16px 20px;
        border-radius: 12px;
        box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.03);
        margin-bottom: 20px;
    }
    
    .privacy-badge {
        background-color: #EBF5EE;
        border: 1px solid #B8E0D2;
        color: #2D6A4F;
        padding: 10px 16px;
        border-radius: 12px;
        font-size: 0.88rem;
        margin-bottom: 20px;
    }

    .badge-card {
        padding: 14px;
        border-radius: 14px;
        margin-top: 10px;
        margin-bottom: 15px;
    }

    .stButton > button {
        background-color: #52B788 !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        border: none !important;
        box-shadow: 0px 4px 12px rgba(82, 183, 136, 0.25) !important;
    }

    .stButton > button:hover {
        background-color: #40916C !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# --- DATABASE CONNECTIONS & ROSTER ISOLATION ---
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
        pin_map = {}
        for _, row in df.iterrows():
            s_pin = str(row["Student PIN"]).strip()
            sec = str(row["Class/Section"]).strip()
            if s_pin and sec:
                pin_map[s_pin] = sec
        return pin_map
    except Exception:
        return {}


@st.cache_data(ttl=300)
def fetch_master_roster_df():
    """Fetches the entire 'Class Rosters' tab once every 5 minutes to avoid API limits."""
    try:
        sh = connect_to_gsheet()
        ws = sh.worksheet("Class Rosters")
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame()


def get_isolated_section_roster(assigned_section: str) -> dict:
    """Strictly filters the master roster down to ONLY the active assigned section.

    Maps plain student names to salted STU-XXXX tokens dynamically in memory.
    """
    df = fetch_master_roster_df()
    if df.empty:
        return {}

    # Strict section query isolation
    section_df = df[
        df["Class/Section"].astype(str).str.strip() == str(assigned_section).strip()
    ]

    roster_map = {}
    for _, row in section_df.iterrows():
        name = str(row.get("Student Name", "")).strip()
        lrn = str(row.get("LRN", "")).strip()
        if name and lrn:
            roster_map[name] = generate_anonymous_id(lrn)

    return roster_map


try:
    sh = connect_to_gsheet()
except Exception:
    st.warning("🌱 Running in offline preview mode.")

# --- HEADER WITH SCHOOL LOGO & DAILY INSPIRATION ---
col_logo, col_title = st.columns([1, 4])

with col_logo:
    st.image("fatimanhslogo.png", width=90)

with col_title:
    st.markdown("## 🌱 EMPOWER Safe Space")
    st.caption("Fatima National High School | Guidance & Peer Support Hub")

st.markdown(
    f"""
    <div class="quote-box">
        <small style="color: #52B788; font-weight: 700;">{today_quote['type']} for Today</small>
        <p style="color: #2D3748; font-size: 0.98rem; font-style: italic; margin: 6px 0 2px 0;">{today_quote['text']}</p>
        <small style="color: #718096; font-weight: 600;">— {today_quote['author']}</small>
    </div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="privacy-badge">
        🔒 <b>Safe & Anonymous:</b> Your identity is protected using cryptographic anonymity tokens (`STU-XXXX`) in compliance with the Data Privacy Act.
    </div>
""",
    unsafe_allow_html=True,
)

# --- STEP 1: CLASS PIN VERIFICATION & SECTION AUTHORIZATION ---
student_pins = load_student_pins()
input_pin = st.text_input(
    "🔑 Enter your 4-digit Class PIN to begin:",
    type="password",
    help="Ask your adviser or counselor for your PIN.",
).strip()

if input_pin in student_pins:
    assigned_section = student_pins[input_pin]
    st.success(f"Welcome! Connected to **Section {assigned_section}**")

    # Load Strictly Isolated Section Roster
    roster_map = get_isolated_section_roster(assigned_section)
    has_roster = len(roster_map) > 0

    if has_roster:
        sorted_names = sorted(list(roster_map.keys()))
        select_options_required = ["-- Select Your Name --"] + sorted_names
        select_options_optional = ["-- None / Skip --"] + sorted_names

    # Interactive Mood Check
    st.markdown("##### How are you feeling right now?")
    mood = st.select_slider(
        "Move the slider to share your current mood:",
        options=[
            "🌧️ Overwhelmed",
            "⛅ A bit tired",
            "🌱 Neutral / OK",
            "☀️ Feeling Good",
            "🎉 Excited & Happy",
        ],
        value="🌱 Neutral / OK",
    )

    st.markdown("---")
    tab1, tab2 = st.tabs(["💬 Weekly Reflection", "💌 Send Kindness Badge"])

    # --- TAB 1: PULSE CHECK-IN ---
    with tab1:
        st.markdown("##### Weekly Student Check-In")
        st.caption(
            "Select classmate names easily from the dropdowns. Choices are automatically converted to anonymous tokens (STU-XXXX) before saving."
        )

        with st.form("pulse_form", clear_on_submit=True):
            if has_roster:
                sender_name = st.selectbox(
                    "Your Name (Stored anonymously as STU-XXXX):",
                    select_options_required,
                )
                kind_peer_name = st.selectbox(
                    "✨ Peer Appreciation (Who showed kindness or helped you this week?):",
                    select_options_optional,
                )
                groupmate_name = st.selectbox(
                    "🤝 Preferred Groupmate (Who would you feel comfortable working/sitting with next week?):",
                    select_options_optional,
                )
                isolated_peer_name = st.selectbox(
                    "🫂 Reaching Out (Who in class seems quiet, overwhelmed, or left out lately?):",
                    select_options_optional,
                )
            else:
                # Fallback if Class Rosters tab is not configured for this section
                st.info("💡 Note: Class roster dropdown is unavailable for this section. Using manual input mode.")
                lrn_input = st.text_input(
                    "Learner Reference Number (LRN)",
                    placeholder="e.g., 123456789012",
                )
                kind_peer_input = st.text_input(
                    "✨ Peer Appreciation (LRN or Identifier)"
                )
                groupmate_input = st.text_input(
                    "🤝 Preferred Groupmate (LRN or Identifier)"
                )
                isolated_peer_input = st.text_input(
                    "🫂 Reaching Out (LRN or Identifier)"
                )

            counselor_request = st.text_area(
                "🕊️ Confidential Counselor Support",
                placeholder=(
                    "Would you like a private, friendly chat with the counselor?"
                    " Tell us how we can help..."
                ),
                height=90,
            )

            submitted = st.form_submit_button("Submit Confidential Reflection")

            if submitted:
                try:
                    if has_roster:
                        if sender_name == "-- Select Your Name --":
                            st.error("Please select your name before submitting.")
                        else:
                            anon_sender = roster_map.get(sender_name, "")
                            anon_kind_peer = (
                                roster_map.get(kind_peer_name, "")
                                if kind_peer_name != "-- None / Skip --"
                                else ""
                            )
                            anon_groupmate = (
                                roster_map.get(groupmate_name, "")
                                if groupmate_name != "-- None / Skip --"
                                else ""
                            )
                            anon_isolated_peer = (
                                roster_map.get(isolated_peer_name, "")
                                if isolated_peer_name != "-- None / Skip --"
                                else ""
                            )
                            clean_counselor_req = sanitize_input(counselor_request)

                            ws = sh.worksheet("Pulse Checkins")
                            ws.append_row([
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                assigned_section,
                                anon_sender,
                                anon_kind_peer,
                                anon_groupmate,
                                anon_isolated_peer,
                                f"[Mood: {mood}] {clean_counselor_req}",
                            ])
                            st.success(
                                f"💚 Thank you! Your reflection has been saved securely as **{anon_sender}**."
                            )
                    else:
                        if lrn_input.strip():
                            anon_sender = generate_anonymous_id(lrn_input)
                            anon_kind_peer = generate_anonymous_id(kind_peer_input)
                            anon_groupmate = generate_anonymous_id(groupmate_input)
                            anon_isolated_peer = generate_anonymous_id(isolated_peer_input)
                            clean_counselor_req = sanitize_input(counselor_request)

                            ws = sh.worksheet("Pulse Checkins")
                            ws.append_row([
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                assigned_section,
                                anon_sender,
                                anon_kind_peer,
                                anon_groupmate,
                                anon_isolated_peer,
                                f"[Mood: {mood}] {clean_counselor_req}",
                            ])
                            st.success(
                                f"💚 Reflection saved securely as **{anon_sender}**."
                            )
                        else:
                            st.error("Please enter your LRN before submitting.")
                except Exception as e:
                    st.error(f"Unable to save response right now: {e}")

    # --- TAB 2: KINDNESS BADGES ---
    with tab2:
        st.markdown("##### Send a Secret Kindness Badge")
        st.caption(
            "Recognize a classmate's positive impact with a quiet note of appreciation!"
        )

        selected_badge_key = st.selectbox(
            "Select Badge to Award:", list(BADGE_DETAILS.keys())
        )
        badge_info = BADGE_DETAILS[selected_badge_key]

        st.markdown(
            f"""
            <div class="badge-card" style="background-color: {badge_info['color']}; border: 1.5px solid {badge_info['border']};">
                <h4 style="margin:0; color: #1E293B;">{badge_info['icon']} {badge_info['title']}</h4>
                <p style="margin: 6px 0 0 0; color: #475569; font-size: 0.9rem;">{badge_info['description']}</p>
            </div>
        """,
            unsafe_allow_html=True,
        )

        with st.form("badge_form", clear_on_submit=True):
            if has_roster:
                recipient_name = st.selectbox(
                    "Who are you sending this badge to?",
                    ["-- Select Classmate --"] + sorted_names,
                )
            else:
                recipient_input = st.text_input(
                    "Who are you sending this badge to?",
                    placeholder="Classmate's LRN / Identifier",
                )

            note = st.text_area(
                "Write a short note of encouragement (Optional)",
                placeholder="e.g., Thank you for helping me during math practice today!",
                height=80,
            )

            badge_submitted = st.form_submit_button("Send Kindness Badge ✨")

            if badge_submitted:
                try:
                    clean_note = sanitize_input(note)
                    if has_roster:
                        if recipient_name == "-- Select Classmate --":
                            st.error("Please select a recipient from the list.")
                        else:
                            anon_recipient = roster_map.get(recipient_name, "")
                            ws = sh.worksheet("Kindness Badges")
                            ws.append_row([
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                assigned_section,
                                anon_recipient,
                                badge_info["badge_tag"],
                                clean_note,
                            ])
                            st.balloons()
                            st.success(
                                f"🎉 Kindness badge successfully awarded to **{anon_recipient}**!"
                            )
                    else:
                        if recipient_input.strip():
                            anon_recipient = generate_anonymous_id(recipient_input)
                            ws = sh.worksheet("Kindness Badges")
                            ws.append_row([
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                assigned_section,
                                anon_recipient,
                                badge_info["badge_tag"],
                                clean_note,
                            ])
                            st.balloons()
                            st.success(
                                f"🎉 Kindness badge successfully awarded to **{anon_recipient}**!"
                            )
                        else:
                            st.error("Please enter recipient details.")
                except Exception as e:
                    st.error(f"Error sending badge: {e}")

elif input_pin:
    st.error("Invalid Class PIN. Please check with your adviser or counselor.")

# --- METHODOLOGY & LEGAL COMPLIANCE FOOTER ---
st.markdown("---")
st.markdown("##### 🛡️ Institutional Compliance & Data Safeguarding")
st.info("""
**Regulatory Standards & Privacy Protocols:**
* **DepEd Order No. 40, s. 2012 (Child Protection Policy):** The EMPOWER platform implements automated regex filtering to restrict inappropriate content, abusive language, or harassment, promoting a safe learning environment.
* **Data Privacy Act of 2012 (Republic Act No. 10173):** Learner Reference Numbers (LRNs) are processed through a salted SHA-256 cryptographic function, generating unique anonymous tokens (`STU-XXXX`). Plaintext student identities are mapped locally in client memory and are never saved to cloud sheets.
""")
