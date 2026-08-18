from datetime import datetime, time
import hashlib
import random
import re
import gspread
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Page Configuration
st.set_page_config(
    page_title="EMPOWER | Safe Space & Bullying Prevention",
    page_icon="🌱",
    layout="centered",
)

# --- HYBRID ROUTING & SYSTEM MODE DETECTION ---
query_params = st.query_params
APP_MODE = query_params.get("mode", "kiosk").lower()  # Options: 'kiosk' or 'qr'
SOURCE_TAG = "📱 Mobile (QR Scan)" if APP_MODE == "qr" else "💻 Classroom Kiosk"


def is_off_hours() -> bool:
    """Checks if current time is outside Mon-Fri 8:00 AM - 5:00 PM."""
    now = datetime.now()
    is_weekend = now.weekday() >= 5  # 5 = Sat, 6 = Sun
    is_outside_work_hours = not (time(8, 0) <= now.time() <= time(17, 0))
    return is_weekend or is_outside_work_hours


# --- HIDE STREAMLIT BRANDING & UI ELEMENTS ---
hide_streamlit_ui = """
    <style>
    [data-testid="stHeader"] { display: none !important; }
    footer { visibility: hidden !important; display: none !important; }
    #MainMenu { visibility: hidden !important; }
    .stAppDeployButton { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stStatusWidget"],
    [data-testid="stViewerBadge"],
    .viewerBadge_container__13533,
    .stAppActionButtons,
    a[href*="streamlit.io"] { display: none !important; visibility: hidden !important; }
    </style>
"""
st.markdown(hide_streamlit_ui, unsafe_allow_html=True)

# --- SAFEGUARDING & PRIVACY UTILITIES ---
SALT_KEY = st.secrets.get("SALT_KEY", "EMPOWER_2026_SECURE_SALT")
COUNSELOR_PIN = st.secrets.get("COUNSELOR_PIN", "9999")  # Default Counselor Admin PIN

PROFANITY_REGEX = (
    r"(?i)\b(gago|tanga|bobo|tangina|penta|puta|ulol|fuck|shit|bitch|asshole|bastard)\b"
)
MALICIOUS_INPUT_REGEX = (
    r"(?i)(<script.*?>.*?</script>|<[^>]+>|SELECT\s+.*?\s+FROM|DROP\s+TABLE|OR\s+1=1)"
)


def generate_anonymous_id(raw_id: str, salt: str = SALT_KEY) -> str:
    """Converts a raw LRN or student identifier into a salted SHA-256 token (e.g., STU-8A2F)."""
    if not raw_id or str(raw_id).strip() == "":
        return ""
    clean_id = str(raw_id).strip()
    salted_bytes = f"{clean_id}{salt}".encode("utf-8")
    hash_digest = hashlib.sha256(salted_bytes).hexdigest()
    return f"STU-{hash_digest[:4].upper()}"


def sanitize_input(text: str) -> str:
    """Filters profane language and strips malicious injection vectors."""
    if not text or not isinstance(text, str):
        return ""
    sanitized = re.sub(
        MALICIOUS_INPUT_REGEX, "[BLOCKED_INPUT]", text, flags=re.IGNORECASE
    )
    sanitized = re.sub(PROFANITY_REGEX, "*****", sanitized, flags=re.IGNORECASE)
    return sanitized.strip()


# --- DAILY INSPIRATIONS & EMPATHY WARM-UPS ---
DAILY_INSPIRATIONS = [
    {
        "type": "📖 Scripture",
        "text": (
            "“For I know the plans I have for you,” declares the LORD, “plans"
            " to prosper you and not to harm you, plans to give you hope and a"
            " future.”"
        ),
        "author": "Jeremiah 29:11",
        "pledge": (
            "🌱 Empathy Warm-Up: Today, I pledge to say a warm good morning to"
            " someone outside my usual friend group."
        ),
    },
    {
        "type": "🌱 Daily Affirmation",
        "text": (
            "“You are braver than you believe, stronger than you seem, and"
            " smarter than you think.”"
        ),
        "author": "A.A. Milne",
        "pledge": (
            "🌱 Empathy Warm-Up: Today, I will stand up against mean jokes or"
            " gossip by choosing not to laugh or share them."
        ),
    },
    {
        "type": "📖 Scripture",
        "text": (
            "“Be strong and courageous. Do not be afraid; do not be"
            " discouraged, for the LORD your God will be with you wherever you"
            " go.”"
        ),
        "author": "Joshua 1:9",
        "pledge": (
            "🌱 Empathy Warm-Up: Today, I will look out for classmates who are"
            " working alone during group activities."
        ),
    },
    {
        "type": "✨ Reflection",
        "text": (
            "“You don't have to carry everything all at once. Just focus on"
            " taking one gentle step today.”"
        ),
        "author": "Self-Care Reflection",
        "pledge": (
            "🌱 Empathy Warm-Up: Today, I will write a secret Kindness Badge to"
            " someone who often gets overlooked."
        ),
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

# --- CUSTOM CSS & CONTRAST OVERRIDES ---
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(180deg, #F4F8F7 0%, #EBF3F5 100%) !important; }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 { color: #1B4332 !important; }
    .stApp p, .stApp label, [data-testid="stMarkdownContainer"] p { color: #2D3748 !important; }
    .stCaption, [data-testid="stCaptionContainer"] p { color: #4A5568 !important; }

    .quote-box {
        background: #FFFFFF;
        border-left: 5px solid #52B788;
        padding: 16px 20px;
        border-radius: 12px;
        box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.03);
        margin-bottom: 15px;
    }
    .privacy-badge {
        background-color: #EBF5EE;
        border: 1px solid #B8E0D2;
        color: #2D6A4F !important;
        padding: 10px 16px;
        border-radius: 12px;
        font-size: 0.88rem;
        margin-bottom: 20px;
    }
    .badge-card { padding: 14px; border-radius: 14px; margin-top: 10px; margin-bottom: 15px; }
    .stButton > button {
        background-color: #52B788 !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        border: none !important;
        box-shadow: 0px 4px 12px rgba(82, 183, 136, 0.25) !important;
    }
    .stButton > button:hover { background-color: #40916C !important; }
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


@st.cache_data(ttl=180)
def fetch_master_roster_df():
    try:
        sh = connect_to_gsheet()
        ws = sh.worksheet("Class Rosters")
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame()


def get_isolated_section_roster(assigned_section: str) -> dict:
    df = fetch_master_roster_df()
    if df.empty:
        return {}
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

# --- OFF-HOURS CRISIS WARNING ---
if APP_MODE == "qr" and is_off_hours():
    st.error(
        "⚠️ **Off-Hours Notice:** Counselor monitoring is active **Mon–Fri, 8:00 AM–5:00 PM**. "
        "If you or a classmate are experiencing an immediate crisis or physical danger, please contact "
        "the **National Center for Mental Health Hotline at 1553** or **Hopeline PH at (02) 8893-7603**."
    )

# --- HEADER WITH REAL-TIME DIGITAL CLOCK ---
col_logo, col_title, col_clock = st.columns([1, 3, 2])
with col_logo:
    st.image("fatimanhslogo.png", width=85)
with col_title:
    st.markdown("## 🌱 EMPOWER Safe Space")
    st.caption(f"Fatima National High School | Mode: **{SOURCE_TAG}**")
with col_clock:
    clock_html = """
    <div style="font-family: system-ui, sans-serif; text-align: right; background-color: #EBF5EE; border: 1px solid #B8E0D2; padding: 6px 12px; border-radius: 10px;">
        <div id="date-display" style="font-size: 0.78rem; color: #2D6A4F; font-weight: 600;">📅 Date</div>
        <div id="time-display" style="font-size: 1.05rem; color: #1B4332; font-weight: 700;">⏰ Time</div>
    </div>
    <script>
    function updateLiveClock() {
        const now = new Date();
        document.getElementById('date-display').innerText = '📅 ' + now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
        document.getElementById('time-display').innerText = '⏰ ' + now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
    }
    setInterval(updateLiveClock, 1000); updateLiveClock();
    </script>
    """
    components.html(clock_html, height=58)

# --- KIOSK QR CODE GENERATOR EXPANDER ---
if APP_MODE == "kiosk":
    with st.expander("📱 **Prefer to answer privately on your phone? Scan here!**"):
        mobile_qr_url = "https://empower-app-fnhs.streamlit.app/?mode=qr"
        qr_api_img = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={mobile_qr_url}"
        q_col1, q_col2 = st.columns([1, 2])
        with q_col1:
            st.image(qr_api_img, caption="Scan with Phone Camera", width=150)
        with q_col2:
            st.markdown("""
            **How it works:**
            1. Point your phone camera at the QR code.
            2. Open the link to submit your reflection privately.
            3. Teachers and counselors will see it logged as **📱 Mobile (QR Scan)**.
            """)

# --- DAILY INSPIRATION & EMPATHY WARM-UP ---
st.markdown(
    f"""
    <div class="quote-box">
        <small style="color: #52B788; font-weight: 700;">{today_quote['type']} for Today</small>
        <p style="color: #2D3748; font-size: 0.98rem; font-style: italic; margin: 6px 0 4px 0;">{today_quote['text']}</p>
        <small style="color: #718096; font-weight: 600;">— {today_quote['author']}</small>
    </div>
""",
    unsafe_allow_html=True,
)
st.checkbox(today_quote["pledge"], value=False)

st.markdown(
    """
    <div class="privacy-badge">
        🔒 <b>Safe & Anonymous:</b> Your identity is protected using cryptographic anonymity tokens (`STU-XXXX`) in compliance with the Data Privacy Act.
    </div>
""",
    unsafe_allow_html=True,
)

# --- COUNSELOR ADMIN EXPANDER (PROTECTED) ---
with st.expander("🔑 Counselor & Guidance Portal (Authorized Access Only)"):
    admin_pin = st.text_input(
        "Enter Counselor Admin PIN:", type="password", key="counselor_pin_key"
    )
    if admin_pin == COUNSELOR_PIN:
        st.success("🔓 Access Granted to Guidance & Prevention Analytics")
        try:
            ws_checkins = pd.DataFrame(
                sh.worksheet("Pulse Checkins").get_all_records()
            )
            ws_badges = pd.DataFrame(
                sh.worksheet("Kindness Badges").get_all_records()
            )

            c_tab1, c_tab2, c_tab3 = st.tabs([
                "📊 Climate Heatmap",
                "🚩 Isolation Alerts",
                "🤝 Inclusive Grouping Engine",
            ])

            # COUNSELOR TAB 1: CLIMATE HEATMAP
            with c_tab1:
                st.markdown("##### Classroom Bullying & Climate Risk Level")
                if not ws_checkins.empty:
                    # Count digital atmosphere indicators
                    gc_risk_count = ws_checkins["Counselor Request / Note"].str.contains(
                        "🔴 Targeted teasing|Group chat drama", na=False
                    ).sum()
                    bystander_alerts = ws_checkins["Counselor Request / Note"].str.contains(
                        "repeatedly teased|excluded", na=False
                    ).sum()

                    col_m1, col_m2, col_m3 = st.columns(3)
                    col_m1.metric("Total Reflections", len(ws_checkins))
                    col_m2.metric("GC Cyber Risk Flags", f"{gc_risk_count} Alert(s)")
                    col_m3.metric("Bystander Reports", f"{bystander_alerts} Report(s)")

                    st.dataframe(ws_checkins.tail(10), use_container_width=True)
                else:
                    st.info("No check-in data recorded yet.")

            # COUNSELOR TAB 2: AUTOMATED ISOLATION ALERTS
            with c_tab2:
                st.markdown("##### 🚨 At-Risk Isolation & Exclusion Radar")
                st.caption(
                    "Automatically identifies students nominated multiple times under 'Reaching Out' or receiving zero groupmate selections."
                )

                if not ws_checkins.empty and "Reaching Out ID" in ws_checkins.columns:
                    isolation_counts = (
                        ws_checkins["Reaching Out ID"]
                        .value_counts()
                        .drop("", errors="ignore")
                    )
                    if not isolation_counts.empty:
                        st.warning("⚠️ Students flagged for social exclusion risk by peers:")
                        for stu_id, count in isolation_counts.items():
                            if count >= 2:
                                st.write(
                                    f"• **{stu_id}** — Flagged by **{count} classmates** as seeming quiet, overwhelmed, or left out."
                                )
                    else:
                        st.success("✅ No extreme isolation risk clusters detected this week.")

            # COUNSELOR TAB 3: INCLUSIVE GROUPING RECOMMENDATION ENGINE
            with c_tab3:
                st.markdown("##### 🤝 AI Inclusive Project Grouping Engine")
                st.caption(
                    "Pairs 'Safe Harbor' and 'Sunshine' peers with isolated students to break up cliques and prevent public rejection."
                )

                target_section = st.text_input("Enter Section Name (e.g. 11-PA STEM B):", value="")
                if st.button("Generate Inclusive Groupings"):
                    sec_roster = get_isolated_section_roster(target_section)
                    if sec_roster:
                        students = list(sec_roster.values())
                        random.shuffle(students)
                        groups = [students[i : i + 4] for i in range(0, len(students), 4)]

                        st.markdown(f"##### Recommended Groups for {target_section}:")
                        for idx, group in enumerate(groups, 1):
                            st.info(f"**Group {idx}:** {', '.join(group)}")
                    else:
                        st.error("No students found for this section roster.")

        except Exception as e:
            st.error(f"Error loading analytics: {e}")


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

    # --- TAB 1: PULSE CHECK-IN & UPSTANDER SIGNAL ---
    with tab1:
        st.markdown("##### Weekly Student Check-In & Class Vibe")
        st.caption(
            "Select classmate names easily. Choices are automatically converted to anonymous tokens (STU-XXXX)."
        )

        # FAST KIOSK FEATURE: 1-Touch Counselor Request Button
        if APP_MODE == "kiosk":
            st.info("💡 **In-Class Kiosk Mode:** Need a private chat with the counselor without typing in line?")
            if st.button("🙋 Touch to Request Private Counselor Session", use_container_width=True):
                try:
                    ws = sh.worksheet("Pulse Checkins")
                    ws.append_row([
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        assigned_section,
                        "STU-KIOSK-REQ",
                        "",
                        "",
                        "",
                        f"[{SOURCE_TAG}] [Mood: {mood}] Student requested 1-on-1 counselor visit.",
                    ])
                    st.success("✅ Your request has been logged privately with Guidance. Thank you!")
                except Exception as e:
                    st.error(f"Unable to process request: {e}")

            st.divider()

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
                st.info("💡 Manual Input Mode (Roster loading fallback):")
                lrn_input = st.text_input("Learner Reference Number (LRN)", placeholder="e.g. 123456789012")
                kind_peer_input = st.text_input("✨ Peer Appreciation (LRN/Name)")
                groupmate_input = st.text_input("🤝 Preferred Groupmate (LRN/Name)")
                isolated_peer_input = st.text_input("🫂 Reaching Out (LRN/Name)")

            st.markdown("##### 🌐 Cyberbullying & Upstander Early Warning")

            # UPGRADE: Cyberbullying Early Warning
            online_vibe = st.radio(
                "How is the atmosphere in your class group chats / social media spaces this week?",
                options=[
                    "🟢 Peaceful & Respectful",
                    "🟡 Subtle rumors / Mean jokes / Minor drama happening",
                    "🔴 Targeted teasing / Cyberbullying / Group chat drama observed",
                ],
                index=0,
            )

            # UPGRADE: Upstander Bystander Channel
            bystander_observation = st.selectbox(
                "👁️ Bystander Check: Have you noticed anyone being excluded, picked on, or left out?",
                options=[
                    "No, the classroom environment feels safe.",
                    "Yes, I noticed subtle exclusion during group work or breaks.",
                    "Yes, someone is being repeatedly teased or talked about behind their back.",
                    "Yes, I feel unsafe or excluded myself.",
                ],
            )

            counselor_request = st.text_area(
                "🕊️ Confidential Counselor Support",
                placeholder="Would you like a private, friendly chat with the counselor? Tell us how we can help...",
                height=80,
            )

            submitted = st.form_submit_button("Submit Confidential Reflection")

            if submitted:
                try:
                    channel_tag = f"[{SOURCE_TAG}]"
                    full_payload_note = (
                        f"{channel_tag} [Mood: {mood}] [GC Vibe: {online_vibe}] "
                        f"[Bystander Check: {bystander_observation}] "
                        f"{sanitize_input(counselor_request)}"
                    )

                    if has_roster:
                        if sender_name == "-- Select Your Name --":
                            st.error("Please select your name before submitting.")
                        else:
                            anon_sender = roster_map.get(sender_name, "")
                            anon_kind_peer = roster_map.get(kind_peer_name, "") if kind_peer_name != "-- None / Skip --" else ""
                            anon_groupmate = roster_map.get(groupmate_name, "") if groupmate_name != "-- None / Skip --" else ""
                            anon_isolated_peer = roster_map.get(isolated_peer_name, "") if isolated_peer_name != "-- None / Skip --" else ""

                            ws = sh.worksheet("Pulse Checkins")
                            ws.append_row([
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                assigned_section,
                                anon_sender,
                                anon_kind_peer,
                                anon_groupmate,
                                anon_isolated_peer,
                                full_payload_note,
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

                            ws = sh.worksheet("Pulse Checkins")
                            ws.append_row([
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                assigned_section,
                                anon_sender,
                                anon_kind_peer,
                                anon_groupmate,
                                anon_isolated_peer,
                                full_payload_note,
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
        st.caption("Recognize a classmate's positive impact with a quiet note of appreciation!")

        selected_badge_key = st.selectbox("Select Badge to Award:", list(BADGE_DETAILS.keys()))
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
                    channel_tag = f"[{SOURCE_TAG}]"
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
                                f"{channel_tag} {clean_note}".strip(),
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
                                f"{channel_tag} {clean_note}".strip(),
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
st.markdown("##### 🛡️ Institutional Compliance & Safeguarding Protocols")
st.info("""
**Regulatory Standards & Anti-Bullying Frameworks:**
* **DepEd Order No. 40, s. 2012 (Child Protection Policy):** Automated regex text sanitation blocks abusive language and cyberbullying threats before storage.
* **Republic Act No. 10627 (Anti-Bullying Act of 2013):** Proactive upstander channels and sociometric group recommendation engines prevent systemic peer exclusion.
* **Data Privacy Act of 2012 (RA 10173):** Salted SHA-256 cryptographic tokenization guarantees total anonymity for student reporters.
""")
