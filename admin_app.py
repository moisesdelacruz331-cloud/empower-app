from datetime import datetime
import hashlib
import gspread
import networkx as nx
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EMPOWER Staff Portal | Proactive Anti-Bullying & Wellbeing",
    page_icon="📊",
    layout="wide",
)

SALT_KEY = st.secrets.get("SALT_KEY", "EMPOWER_2026_SECURE_SALT")


# --- ANONYMIZATION UTILITIES ---
def generate_anonymous_id(raw_id: str, salt: str = SALT_KEY) -> str:
    """Generates the salted SHA-256 token for student check-ins."""
    if not raw_id or str(raw_id).strip() == "":
        return ""
    clean_id = str(raw_id).strip()
    salted_bytes = f"{clean_id}{salt}".encode("utf-8")
    hash_digest = hashlib.sha256(salted_bytes).hexdigest()
    return f"STU-{hash_digest[:4].upper()}"


# --- CUSTOM STYLING ---
st.markdown(
    """
    <style>
    .role-badge {
        background-color: #3B82F6;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 14px;
    }
    .alert-high {
        background-color: #FEF2F2;
        border-left: 5px solid #EF4444;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 16px;
    }
    .alert-watch {
        background-color: #FFFBEB;
        border-left: 5px solid #F59E0B;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 16px;
    }
    .guidance-box {
        background-color: #F0FDF4;
        border-left: 5px solid #10B981;
        padding: 12px 16px;
        border-radius: 8px;
        margin-top: 12px;
        margin-bottom: 16px;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# --- DATABASE CONNECTIONS & FAST CACHING ---
@st.cache_resource
def connect_to_gsheet():
    creds = dict(st.secrets["connections"]["gsheets"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds)
    return gc.open_by_url(creds.get("spreadsheet"))


@st.cache_data(ttl=600)
def load_pin_config():
    """Fast raw-value fetcher for PIN configuration."""
    try:
        sh = connect_to_gsheet()
        ws = sh.worksheet("Class Configuration")
        data = ws.get_all_values()
        if not data or len(data) < 2:
            return pd.DataFrame(
                columns=["Class/Section", "Student PIN", "Teacher PIN"]
            )

        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip()
        return df
    except Exception:
        return pd.DataFrame(
            columns=["Class/Section", "Student PIN", "Teacher PIN"]
        )


@st.cache_data(ttl=60)
def fetch_pulse_records():
    """Caches raw Pulse Check-ins using fast value fetching."""
    try:
        sh = connect_to_gsheet()
        ws_pulse = sh.worksheet("Pulse Checkins")
        data = ws_pulse.get_all_values()
        if not data or len(data) < 2:
            return parse_mood_and_requests(pd.DataFrame())

        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip()
        return parse_mood_and_requests(df)
    except Exception:
        return parse_mood_and_requests(pd.DataFrame())


@st.cache_data(ttl=60)
def fetch_badge_records():
    """Caches raw Kindness Badges."""
    try:
        sh = connect_to_gsheet()
        ws_badges = sh.worksheet("Kindness Badges")
        data = ws_badges.get_all_values()
        if not data or len(data) < 2:
            return pd.DataFrame()

        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=120)
def compute_graph_layout(_G):
    """Caches NetworkX layout computation."""
    return nx.spring_layout(_G, k=0.6, seed=42)


# --- ANTI-PRANK & ANOMALY FILTERING PIPELINE ---
def clean_pulse_data(df_pulse: pd.DataFrame) -> pd.DataFrame:
    """Pre-cleaning pipeline: Deduplicates per student & parses timestamps."""
    if df_pulse.empty:
        return df_pulse

    df_clean = df_pulse.copy()

    if "Timestamp" in df_clean.columns:
        df_clean["Timestamp_DT"] = pd.to_datetime(
            df_clean["Timestamp"], errors="coerce"
        )
        df_clean["Date_Only"] = df_clean["Timestamp_DT"].dt.date

        if "Student LRN" in df_clean.columns:
            # Keep latest submission per student per date
            df_clean = (
                df_clean.sort_values("Timestamp_DT")
                .groupby(["Date_Only", "Student LRN"])
                .last()
                .reset_index(drop=True)
            )

    if "Kind Peer" in df_clean.columns and "Student LRN" in df_clean.columns:
        df_clean["Kind Peer"] = df_clean.apply(
            lambda r: (
                ""
                if str(r["Student LRN"]).strip() == str(r["Kind Peer"]).strip()
                else r["Kind Peer"]
            ),
            axis=1,
        )

    if (
        "Preferred Groupmate" in df_clean.columns
        and "Student LRN" in df_clean.columns
    ):
        df_clean["Preferred Groupmate"] = df_clean.apply(
            lambda r: (
                ""
                if str(r["Student LRN"]).strip()
                == str(r["Preferred Groupmate"]).strip()
                else r["Preferred Groupmate"]
            ),
            axis=1,
        )

    return df_clean


# --- ADVANCED PAYLOAD PARSER ---
def parse_mood_and_requests(df: pd.DataFrame) -> pd.DataFrame:
    """Extracts Mood, GC Cyberbullying Vibe, Bystander Observation, Source Tag, and Notes."""
    if df.empty:
        for col in [
            "Mood",
            "GC_Vibe",
            "Bystander_Check",
            "Source_Tag",
            "Clean_Counselor_Request",
        ]:
            df[col] = []
        return df

    if "Counselor Request" in df.columns:
        req_str = df["Counselor Request"].astype(str)

        df["Mood"] = req_str.str.extract(r"\[Mood:\s*([^\]]+)\]").fillna(
            "🌱 Not Specified"
        )
        df["GC_Vibe"] = req_str.str.extract(r"\[GC Vibe:\s*([^\]]+)\]").fillna(
            "🟢 Peaceful & Respectful"
        )
        df["Bystander_Check"] = req_str.str.extract(
            r"\[Bystander Check:\s*([^\]]+)\]"
        ).fillna("No, the classroom environment feels safe.")
        df["Source_Tag"] = req_str.str.extract(
            r"\[(📱 Mobile \(QR Scan\)|💻 Classroom Kiosk)\]"
        ).fillna("💻 Classroom Kiosk")

        clean_text = req_str
        patterns = [
            r"\[📱 Mobile \(QR Scan\)\]",
            r"\[💻 Classroom Kiosk\]",
            r"\[Mood:\s*[^\]]+\]",
            r"\[GC Vibe:\s*[^\]]+\]",
            r"\[Bystander Check:\s*[^\]]+\]",
        ]
        for p in patterns:
            clean_text = clean_text.str.replace(p, "", regex=True)

        df["Clean_Counselor_Request"] = clean_text.str.strip()
    else:
        df["Mood"] = "🌱 Not Specified"
        df["GC_Vibe"] = "🟢 Peaceful & Respectful"
        df["Bystander_Check"] = "No, the classroom environment feels safe."
        df["Source_Tag"] = "💻 Classroom Kiosk"
        df["Clean_Counselor_Request"] = ""

    return df


# --- SOCIOGRAM & DUAL-FILTER ANCHORS ---
def render_sociogram_analytics(
    df_pulse, df_badges, section_roster=None, section_label="Active View"
):
    """Calculates network centrality and renders sociogram."""
    df_clean = clean_pulse_data(df_pulse)

    if df_clean.empty:
        st.info(f"No check-in data available for {section_label}.")
        return []

    G = nx.DiGraph()

    for _, row in df_clean.iterrows():
        sender = str(row.get("Student LRN", "")).strip()
        kind_peer = str(row.get("Kind Peer", "")).strip()
        preferred_peer = str(row.get("Preferred Groupmate", "")).strip()

        if sender and sender.lower() != "nan":
            G.add_node(sender)
            if kind_peer and kind_peer.lower() != "nan" and sender != kind_peer:
                G.add_edge(sender, kind_peer, relation="Kindness")
            if (
                preferred_peer
                and preferred_peer.lower() != "nan"
                and sender != preferred_peer
            ):
                G.add_edge(
                    sender, preferred_peer, relation="Preferred Partner"
                )

    if G.number_of_nodes() == 0:
        st.info(f"Insufficient peer nomination data for {section_label}.")
        return []

    in_degree = dict(G.in_degree())
    n_nodes = G.number_of_nodes()
    centrality = (
        {node: deg / (n_nodes - 1) for node, deg in in_degree.items()}
        if n_nodes > 1
        else {node: 0.0 for node in G.nodes()}
    )

    present_students = set(
        df_clean["Student LRN"].astype(str).str.strip().unique()
    )
    if section_roster and len(section_roster) > 0:
        full_roster = set([str(x).strip() for x in section_roster])
        absent_students = full_roster - present_students
    else:
        absent_students = set()

    isolated_nodes = [
        node
        for node, deg in in_degree.items()
        if deg == 0 and node not in absent_students
    ]

    badge_counts = {}
    if not df_badges.empty and "Recipient LRN" in df_badges.columns:
        badge_counts = (
            df_badges["Recipient LRN"]
            .astype(str)
            .str.strip()
            .value_counts()
            .to_dict()
        )

    badge_median = (
        np.median(list(badge_counts.values())) if badge_counts else 0
    )
    centrality_threshold = (
        np.median(list(centrality.values())) if centrality else 0
    )

    eligible_anchors = []
    for node, deg in in_degree.items():
        earned_badges = badge_counts.get(node, 0)
        c_val = centrality.get(node, 0)
        if (
            c_val >= centrality_threshold
            and earned_badges >= badge_median
            and deg > 0
        ):
            eligible_anchors.append(node)

    pos = compute_graph_layout(G)
    edge_x, edge_y = [], []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=1.2, color="#CBD5E1"),
        hoverinfo="none",
        mode="lines",
    )

    node_x, node_y, node_colors, node_sizes, node_labels, node_hover = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        deg = in_degree[node]

        if node in isolated_nodes:
            node_colors.append("#EF4444")
            node_sizes.append(22)
        elif node in eligible_anchors:
            node_colors.append("#3B82F6")
            node_sizes.append(24)
        else:
            node_colors.append("#10B981")
            node_sizes.append(16 + (deg * 5))

        node_labels.append(str(node))
        node_hover.append(
            f"<b>Student ID:</b> {node}<br>"
            f"<b>Nominations Received:</b> {deg}<br>"
            f"<b>Badges Earned:</b> {badge_counts.get(node, 0)}<br>"
            f"<b>Status:</b> {'Dual-Filter Peer Anchor' if node in eligible_anchors else 'Isolated (Present)' if node in isolated_nodes else 'Standard'}"
        )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        hoverinfo="text",
        text=node_labels,
        textposition="top center",
        hovertext=node_hover,
        marker=dict(
            color=node_colors,
            size=node_sizes,
            line=dict(width=2, color="#FFFFFF"),
        ),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title=f"<b>Sociogram Network — Section: {section_label}</b>",
        showlegend=False,
        margin=dict(b=20, l=10, r=10, t=50),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown(
        f"#### 💡 Sociogram Interpretation & Action Plan ({section_label})"
    )

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric(
        "Section Inclusion Rate",
        f"{((n_nodes - len(isolated_nodes)) / n_nodes * 100):.1f}%",
    )
    col_m2.metric(
        "Dual-Filter Peer Anchors",
        f"{len(eligible_anchors)} identified",
        f"{', '.join(eligible_anchors[:2]) if eligible_anchors else 'None'}",
    )
    col_m3.metric(
        "Verified Isolated Students",
        f"{len(isolated_nodes)} of {n_nodes} present",
    )

    st.markdown(
        f"""
    <div class="guidance-box">
        <b>What This Graph Implies:</b><br>
        * <b>🔴 Red Nodes ({len(isolated_nodes)}):</b> Students present during check-in with zero peer nominations.<br>
        * <b>🔵 Blue Nodes ({len(eligible_anchors)}):</b> Validated Peer Anchors with high network centrality and kindness badges.<br><br>
        <b>Recommended Staff Action Items:</b><br>
        1. <b>Eliminate Free Grouping:</b> Pre-assign groups.<br>
        2. <b>Implement Peer-Shielding:</b> Pair isolated students (🔴) with Dual-Filter Peer Anchors (🔵).
    </div>
    """,
        unsafe_allow_html=True,
    )

    return isolated_nodes


# --- IFR TRACKER TOOL ---
def render_ifr_tracker():
    st.subheader("📐 Implementation Fidelity Rate ($IFR$) Tracker")
    st.caption(
        "Quantifies teacher adherence to deliberate grouping interventions and"
        " peer-shielding protocols."
    )

    col1, col2 = st.columns(2)
    with col1:
        total_assigned = st.number_input(
            "Total Assigned Collaborative Group Activities:",
            min_value=1,
            value=10,
            step=1,
        )
        correctly_paired = st.number_input(
            "Activities with Correct Peer-Shielding Pairings:",
            min_value=0,
            max_value=int(total_assigned),
            value=8,
            step=1,
        )

    ifr_value = (correctly_paired / total_assigned) * 100

    st.markdown("##### Formula Implemented")
    st.latex(
        r"IFR = \left( \frac{\text{Correctly Paired"
        r" Activities}}{\text{Total Assigned Activities}} \right) \times 100"
    )

    st.markdown("##### Benchmark Result")
    if ifr_value >= 85:
        st.success(
            f"🟢 **IFR = {ifr_value:.1f}%** — Target High Fidelity Met (≥ 85%)."
        )
    else:
        st.error(
            f"🔴 **IFR = {ifr_value:.1f}%** — Below Target Threshold (< 85%)."
        )


# --- COUNSELOR DE-ANONYMIZATION MODULE ---
def render_student_lookup_tool():
    st.subheader("🔍 Confidential Student De-Anonymization Tool")
    st.caption("Authorized Counselor Feature — RA 10173 Compliant")

    col1, col2 = st.columns(2)
    with col1:
        target_token = (
            st.text_input(
                "Enter Flagged Anonymous Token (e.g., STU-8A2F):",
                placeholder="STU-8A2F",
            )
            .strip()
            .upper()
        )
    with col2:
        input_lrn = st.text_input(
            "Verify Known Student LRN:", placeholder="e.g., 123456789012"
        ).strip()

    if input_lrn:
        generated_token = generate_anonymous_id(input_lrn)
        if target_token and generated_token == target_token:
            st.success(
                f"✅ **MATCH CONFIRMED:** LRN `{input_lrn}` maps to"
                f" **{generated_token}**."
            )
        else:
            st.info(f"LRN `{input_lrn}` generates token: **{generated_token}**")


# --- AUTHENTICATION & PRE-WARM CACHE ---
if "auth_role" not in st.session_state:
    st.session_state.auth_role = None
    st.session_state.auth_section = None

# Pre-warm PIN config cache silently in background on load
pin_df = load_pin_config()

if not st.session_state.auth_role:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("fatimanhslogo.png", width=80)
        st.title("🔒 EMPOWER Staff Portal")
        login_pin = st.text_input(
            "Enter Staff Passcode / Teacher PIN:", type="password"
        ).strip()

        if st.button("Login to Dashboard"):
            counselor_pass = str(
                st.secrets.get("ADMIN_PASSWORD", "COUNSELOR2026")
            ).strip()

            if login_pin == counselor_pass:
                st.session_state.auth_role = "Counselor"
                st.session_state.auth_section = "ALL"
                st.rerun()
            else:
                if not pin_df.empty and "Teacher PIN" in pin_df.columns:
                    matched = pin_df[
                        pin_df["Teacher PIN"].astype(str).str.strip()
                        == login_pin
                    ]
                    if not matched.empty:
                        st.session_state.auth_role = "Teacher"
                        st.session_state.auth_section = matched.iloc[0][
                            "Class/Section"
                        ]
                        st.rerun()
                    else:
                        st.error("Invalid Passcode or PIN.")
                else:
                    st.error("Invalid Passcode.")

else:
    # --- MAIN APPLICATION DASHBOARD ---
    role = st.session_state.auth_role
    assigned_section = st.session_state.auth_section

    st.sidebar.image("fatimanhslogo.png", width=90)
    st.sidebar.title("📊 Staff Analytics")
    st.sidebar.markdown(
        f"**Active User Role:** <span class='role-badge'>{role}</span>",
        unsafe_allow_html=True,
    )

    # FAST CACHED DATA LOAD
    df_pulse_raw = fetch_pulse_records()
    df_badges_raw = fetch_badge_records()
    df_pulse_clean = clean_pulse_data(df_pulse_raw)

    # 🎯 SCOPE FILTER (Counselor vs Teacher)
    if role == "Counselor":
        available_sections = (
            sorted(
                list(
                    set(
                        df_pulse_clean["Class/Section"]
                        .dropna()
                        .astype(str)
                        .unique()
                    )
                )
            )
            if not df_pulse_clean.empty
            else []
        )
        selected_view_scope = st.sidebar.selectbox(
            "🎯 Counselor View Scope:",
            options=["ALL (Aggregated)"] + available_sections,
        )
        active_section_filter = (
            "ALL"
            if selected_view_scope == "ALL (Aggregated)"
            else selected_view_scope
        )
    else:
        active_section_filter = assigned_section

    st.sidebar.write(f"Active Scope: **{active_section_filter}**")

    # Apply Section Filter First
    df_pulse = df_pulse_clean.copy()
    df_badges = df_badges_raw.copy()

    if active_section_filter != "ALL":
        if not df_pulse.empty and "Class/Section" in df_pulse.columns:
            df_pulse = df_pulse[
                df_pulse["Class/Section"].astype(str).str.strip()
                == active_section_filter
            ]
        if not df_badges.empty and "Class/Section" in df_badges.columns:
            df_badges = df_badges[
                df_badges["Class/Section"].astype(str).str.strip()
                == active_section_filter
            ]

    # 📅 PER-DAY DATE FILTER TOOL FOR TEACHERS/COUNSELORS
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Date Selection")

    if not df_pulse.empty and "Date_Only" in df_pulse.columns:
        valid_dates = sorted(
            [d for d in df_pulse["Date_Only"].dropna().unique()], reverse=True
        )
        date_options = ["All Dates"] + [d.strftime("%Y-%m-%d") for d in valid_dates]
        selected_date_str = st.sidebar.selectbox(
            "Filter Student Responses By Day:", options=date_options, index=0
        )

        if selected_date_str != "All Dates":
            selected_date_obj = datetime.strptime(
                selected_date_str, "%Y-%m-%d"
            ).date()
            df_pulse = df_pulse[df_pulse["Date_Only"] == selected_date_obj]
            view_date_label = f"Day: {selected_date_str}"
        else:
            view_date_label = "All Dates Aggregated"
    else:
        view_date_label = "All Dates"

    st.sidebar.caption(f"Currently Showing Data For: **{view_date_label}**")

    if st.sidebar.button("🔄 Refresh Live Data"):
        st.cache_data.clear()
        st.rerun()

    if st.sidebar.button("Logout"):
        st.session_state.auth_role = None
        st.session_state.auth_section = None
        st.cache_data.clear()
        st.rerun()

    # --- DASHBOARD HEADER ---
    st.title(f"Classroom Wellbeing Overview: {active_section_filter}")
    st.caption(
        f"Logged in as: **{role}** | Filter Mode: **{view_date_label}** |"
        " Real-time mood check-ins, proactive cyberbullying early-warning, and"
        " student response logs."
    )

    # --- TOP METRICS & ALERTS ---
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    total_pulse = len(df_pulse) if not df_pulse.empty else 0
    total_badges = len(df_badges) if not df_badges.empty else 0

    overwhelmed_count = (
        len(
            df_pulse[
                df_pulse["Mood"].str.contains(
                    "Overwhelmed|Sad|Anxious|Stressed", na=False, case=False
                )
            ]
        )
        if not df_pulse.empty
        else 0
    )
    
    # Filter out casual non-urgent greetings from metric requests count
    CASUAL_GREETINGS = r"^(hello|hi|hey|test|none|n/a|no|nothing|ok|okay|good morning|good afternoon)\.?$"
    
    counselor_req_count = (
        len(
            df_pulse[
                (df_pulse["Clean_Counselor_Request"].str.strip() != "")
                & (~df_pulse["Clean_Counselor_Request"].str.strip().str.lower().str.match(CASUAL_GREETINGS, na=False))
            ]
        )
        if not df_pulse.empty
        else 0
    )

    cyberbullying_flags = (
        len(
            df_pulse[
                df_pulse["GC_Vibe"].str.contains(
                    "Targeted teasing|Cyberbullying", na=False, case=False
                )
            ]
        )
        if not df_pulse.empty
        else 0
    )
    bystander_flags = (
        len(
            df_pulse[
                df_pulse["Bystander_Check"].str.contains(
                    "teased|excluded|unsafe", na=False, case=False
                )
            ]
        )
        if not df_pulse.empty
        else 0
    )

    col_m1.metric("💬 Daily Check-Ins", total_pulse)
    col_m2.metric("🏅 Badges Awarded", total_badges)
    col_m3.metric("🌧️ High-Stress Moods", overwhelmed_count)
    col_m4.metric("🕊️ Counselor Requests", counselor_req_count)
    col_m5.metric(
        "🛡️ Cyberbullying / Safety Flags",
        f"{cyberbullying_flags + bystander_flags}",
        delta=f"{cyberbullying_flags} GC / {bystander_flags} Bystander",
        delta_color="inverse",
    )

    st.markdown("---")

    # --- DYNAMIC STUDENT MOOD & SAFETY ALERT BANNER ---
    if not df_pulse.empty:
        # High-risk keywords that explicitly indicate urgency or distress
        DISTRESS_KEYWORDS = r"kill|die|bomb|hurt|abuse|suicide|harm|help|scared|unsafe|depressed|threat|bully|afraid"

        # Check if counselor request contains non-greeting content or distress keywords
        is_concerning_request = (
            df_pulse["Clean_Counselor_Request"].str.contains(DISTRESS_KEYWORDS, na=False, case=False)
        ) | (
            (df_pulse["Clean_Counselor_Request"].str.strip() != "")
            & (~df_pulse["Clean_Counselor_Request"].str.strip().str.lower().str.match(CASUAL_GREETINGS, na=False))
        )

        critical_submissions = df_pulse[
            (
                df_pulse["Mood"].str.contains(
                    "Overwhelmed|Sad|Anxious|Stressed", na=False, case=False
                )
            )
            | is_concerning_request
            | (
                df_pulse["GC_Vibe"].str.contains(
                    "Targeted teasing|Cyberbullying", na=False, case=False
                )
            )
            | (
                df_pulse["Bystander_Check"].str.contains(
                    "teased|excluded|unsafe", na=False, case=False
                )
            )
        ]

        if not critical_submissions.empty:
            percentage_distressed = (
                len(critical_submissions) / len(df_pulse)
            ) * 100
            st.markdown(
                f"""
                <div class="alert-high">
                    <b>🚨 ACTIVE STUDENT MOOD & SAFETY ALERT ({view_date_label}):</b><br>
                    <b>{len(critical_submissions)} out of {len(df_pulse)} student responses ({percentage_distressed:.1f}%)</b> reported emotional distress, negative mood check-ins, urgent counselor help requests, or active classroom/online bullying signals.
                </div>
            """,
                unsafe_allow_html=True,
            )

    # --- DYNAMIC TABS SETUP ---
    tab_titles = [
        "📊 Student Mood Check-In Analytics",
        "💬 Daily Responses Log",
        "🏅 Kindness Badges Log",
        "🫂 Peer Inclusion & Sociogram",
        "📐 IFR Tracker",
    ]

    if role == "Counselor":
        tab_titles.extend(["🔍 Student De-Anonymization", "⚙️ PIN Manager"])

    tabs = st.tabs(tab_titles)

    # =========================================================================
    # TAB 1: STUDENT MOOD CHECK-IN ANALYTICS, INTERPRETATION & ALERTS
    # =========================================================================
    with tabs[0]:
        st.subheader(
            f"📊 Student Mood Check-In & Wellbeing Analysis ({view_date_label})"
        )

        if not df_pulse.empty and "Mood" in df_pulse.columns:
            col_chart1, col_chart2 = st.columns([3, 2])

            with col_chart1:
                st.markdown("##### 🎭 Student Mood Breakdown")
                mood_counts = (
                    df_pulse["Mood"]
                    .value_counts()
                    .reset_index()
                )
                mood_counts.columns = ["Mood State", "Student Count"]

                # Custom color mapping for emotional states
                color_map = {
                    "🌱 Happy & Energized": "#10B981",
                    "🟢 Peaceful & Respectful": "#3B82F6",
                    "🙂 Calm / Ready to Learn": "#0EA5E9",
                    "😴 Tired / Low Energy": "#F59E0B",
                    "🌧️ Anxious / Stressed": "#F97316",
                    "🚨 Overwhelmed / Need Help": "#EF4444",
                }

                fig_mood = px.bar(
                    mood_counts,
                    x="Mood State",
                    y="Student Count",
                    color="Mood State",
                    text="Student Count",
                    title=f"Mood Check-In Distribution — {view_date_label}",
                    color_discrete_map=color_map,
                )
                fig_mood.update_traces(
                    textposition="outside", marker_line_color="rgb(8,48,107)"
                )
                fig_mood.update_layout(
                    showlegend=False,
                    xaxis_title="Reported Mood State",
                    yaxis_title="Number of Students",
                    margin=dict(t=40, b=20),
                )
                st.plotly_chart(fig_mood, use_container_width=True)

            with col_chart2:
                st.markdown("##### 🌐 Online Atmosphere (GC Check)")
                vibe_counts = df_pulse["GC_Vibe"].value_counts().reset_index()
                vibe_counts.columns = ["Atmosphere Vibe", "Count"]

                fig_vibe = px.pie(
                    vibe_counts,
                    names="Atmosphere Vibe",
                    values="Count",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    title="Class Group Chat Vibe",
                )
                st.plotly_chart(fig_vibe, use_container_width=True)

            st.markdown("---")

            # --- DETAILED MOOD INTERPRETATION & TEACHER GUIDANCE BOX ---
            st.markdown("#### 💡 Mood Check-In Interpretation & Daily Action Plan")

            # Calculate proportions for interpretation
            high_stress_pct = (overwhelmed_count / total_pulse) * 100 if total_pulse > 0 else 0

            st.markdown(
                f"""
            <div class="guidance-box">
                <b>What Today's Mood Data Means:</b><br>
                * <b>Emotional Readiness Level:</b> <b>{total_pulse - overwhelmed_count}</b> out of <b>{total_pulse}</b> students are in a positive or neutral state, while <b>{overwhelmed_count} student(s) ({high_stress_pct:.1f}%)</b> indicate high stress, anxiety, or emotional fatigue.<br>
                * <b>Classroom Climate Impact:</b> High-stress mood reports often correlate with reduced academic focus, lower participation, or heightened peer conflict during collaborative work.<br><br>
                <b>Recommended Daily Teacher Action Items:</b><br>
                1. <b>Incorporate a 3-Minute Reset:</b> If high-stress moods exceed 20%, start class with a brief mindfulness, breathing, or quiet reflection exercise.<br>
                2. <b>Discreet Wellbeing Check:</b> Approach students who checked in as <i>Overwhelmed</i> quietly at their desks or after class without calling public attention.<br>
                3. <b>Structure Peer Activities:</b> Use the <i>Peer Inclusion & Sociogram</i> tab to ensure anxious or low-energy students are paired with supportive Peer Anchors.
            </div>
            """,
                unsafe_allow_html=True,
            )

        else:
            st.info(
                f"No mood check-in records found for the selected view scope: **{view_date_label}**."
            )

    # =========================================================================
    # TAB 2: DAILY RESPONSES LOG (PER-DAY STUDENT RESPONSE TABLE)
    # =========================================================================
    with tabs[1]:
        st.subheader(
            f"💬 Student Response Log per Day ({active_section_filter} | {view_date_label})"
        )
        st.caption(
            "Filter responses per day using the sidebar widget to examine"
            " individual student reflections."
        )

        if not df_pulse.empty:
            display_cols = [
                "Timestamp",
                "Class/Section",
                "Student LRN",
                "Mood",
                "Kind Peer",
                "Preferred Groupmate",
                "GC_Vibe",
                "Bystander_Check",
                "Clean_Counselor_Request",
                "Source_Tag",
            ]
            avail_cols = [c for c in display_cols if c in df_pulse.columns]

            st.dataframe(
                df_pulse[avail_cols].sort_values("Timestamp", ascending=False),
                use_container_width=True,
            )

            st.markdown(
                f"""
            <div class="guidance-box">
                <b>Log Analysis Guidelines ({view_date_label}):</b><br>
                * <b>Counselor Requests:</b> Check the <i>Clean_Counselor_Request</i> column for confidential help messages submitted by students.<br>
                * <b>Peer Nominations:</b> Use <i>Kind Peer</i> and <i>Preferred Groupmate</i> entries to gauge organic social connections formed in class.
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.info(
                f"No student check-in responses recorded for **{view_date_label}**."
            )

    # =========================================================================
    # TAB 3: KINDNESS BADGES LOG
    # =========================================================================
    with tabs[2]:
        st.subheader(f"🏅 Kindness Badges Log ({active_section_filter})")
        if not df_badges.empty:
            st.dataframe(df_badges, use_container_width=True)
        else:
            st.info("No kindness badges awarded yet.")

    # =========================================================================
    # TAB 4: PEER INCLUSION & SOCIOGRAM
    # =========================================================================
    with tabs[3]:
        render_sociogram_analytics(
            df_pulse, df_badges, section_label=active_section_filter
        )

    # =========================================================================
    # TAB 5: IFR TRACKER
    # =========================================================================
    with tabs[4]:
        render_ifr_tracker()

    # =========================================================================
    # TAB 6 & 7: COUNSELOR-ONLY MODULES
    # =========================================================================
    if role == "Counselor":
        with tabs[5]:
            render_student_lookup_tool()
        with tabs[6]:
            st.subheader("⚙️ PIN Manager")
            if not pin_df.empty:
                st.dataframe(pin_df, use_container_width=True)
            else:
                st.info("No PIN configuration data found.")
