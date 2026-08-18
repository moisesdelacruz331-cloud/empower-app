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


# --- DATABASE CONNECTIONS & OPTIMIZED CACHING ---
@st.cache_resource
def connect_to_gsheet():
    creds = dict(st.secrets["connections"]["gsheets"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds)
    return gc.open_by_url(creds.get("spreadsheet"))


@st.cache_data(ttl=300)
def load_pin_config():
    """Caches PIN mappings for 5 minutes to minimize API strain."""
    try:
        sh = connect_to_gsheet()
        ws = sh.worksheet("Class Configuration")
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame(
            columns=["Class/Section", "Student PIN", "Teacher PIN"]
        )


@st.cache_data(ttl=60)
def fetch_pulse_records():
    """Caches raw Pulse Check-ins for 60 seconds."""
    try:
        sh = connect_to_gsheet()
        ws_pulse = sh.worksheet("Pulse Checkins")
        return parse_mood_and_requests(
            pd.DataFrame(ws_pulse.get_all_records())
        )
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60)
def fetch_badge_records():
    """Caches raw Kindness Badges for 60 seconds."""
    try:
        sh = connect_to_gsheet()
        ws_badges = sh.worksheet("Kindness Badges")
        return pd.DataFrame(ws_badges.get_all_records())
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=120)
def compute_graph_layout(_G):
    """Caches NetworkX CPU-intensive spring layout for Plotly speedup."""
    return nx.spring_layout(_G, k=0.6, seed=42)


# --- ANTI-PRANK & ANOMALY FILTERING PIPELINE ---
def clean_pulse_data(df_pulse: pd.DataFrame) -> pd.DataFrame:
    """Pre-cleaning pipeline: Deduplicates per student & strips self-nominations."""
    if df_pulse.empty:
        return df_pulse

    df_clean = df_pulse.copy()

    if "Timestamp" in df_clean.columns and "Student LRN" in df_clean.columns:
        df_clean["Timestamp"] = pd.to_datetime(
            df_clean["Timestamp"], errors="coerce"
        )
        # Keep latest submission per student
        df_clean = (
            df_clean.sort_values("Timestamp")
            .groupby("Student LRN")
            .last()
            .reset_index()
        )

    # Strip self-nominations
    if "Kind Peer" in df_clean.columns:
        df_clean["Kind Peer"] = df_clean.apply(
            lambda r: (
                ""
                if str(r["Student LRN"]).strip() == str(r["Kind Peer"]).strip()
                else r["Kind Peer"]
            ),
            axis=1,
        )

    if "Preferred Groupmate" in df_clean.columns:
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


# --- ADVANCED PAYLOAD PARSER (PROACTIVE ANTI-BULLYING DATA) ---
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

        # Strip extracted metadata tags from raw note text
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
    """Calculates network centrality, masks absent students, and flags dual-filter anchors."""
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

    # Active Absenteeism Data Masking
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

    # Dual-Filter Peer Anchor Logic
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

    # Render Graph (CACHED POSITIONS FOR PERFORMANCE)
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

    # Detailed Interpretation and Action Guidance
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
        * <b>🔴 Red Nodes ({len(isolated_nodes)}):</b> Students who were present during check-in but received zero peer nominations for group work or kindness. They are at immediate risk of social exclusion.<br>
        * <b>🔵 Blue Nodes ({len(eligible_anchors)}):</b> Validated Peer Anchors who hold both high network centrality AND have earned above-average kindness badges. They demonstrate high social influence and prosocial leadership.<br>
        * <b>⚪ Masked Absentees ({len(absent_students)}):</b> Filtered out from isolation alerts so absenteeism isn't misclassified as social exclusion.<br><br>
        <b>Recommended Staff Action Items:</b><br>
        1. <b>Eliminate Free Grouping:</b> Do not allow students to self-select group members, as this deepens isolated node exclusion.<br>
        2. <b>Implement Peer-Shielding:</b> Quietly assign isolated students (🔴) into collaborative pairings with Dual-Filter Peer Anchors (🔵).<br>
        3. <b>Observational Monitoring:</b> Monitor peer dynamics in groups to verify that blue-node anchors actively facilitate inclusion.
    </div>
    """,
        unsafe_allow_html=True,
    )

    return isolated_nodes


# --- IFR TRACKER TOOL ---
def render_ifr_tracker():
    """Renders the Implementation Fidelity Rate tracker with explicit pedagogical interpretations."""
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

    st.markdown(
        """
    <div class="guidance-box">
        <b>What This Metric Implies:</b><br>
        * High $IFR$ (≥ 85%) verifies that educators are consistently executing intervention strategies by pairing isolated students with designated peer anchors.<br>
        * Low $IFR$ (< 85%) signals that unstructured student grouping or inconsistent pairing adherence is still occurring in the classroom.<br><br>
        <b>Recommended Staff Action Items:</b><br>
        1. <b>Maintain Pre-Designed Seating:</b> Prepare seating charts and group rosters ahead of time for all lab exercises and group projects.<br>
        2. <b>Log Every Activity:</b> Record each collaborative group session to maintain real-time fidelity tracking.<br>
        3. <b>Review Pairing Quality:</b> Ensure pairings prioritize pairing 🔴 isolated nodes with 🔵 peer anchors rather than simple random assignments.
    </div>
    """,
        unsafe_allow_html=True,
    )


# --- COUNSELOR DE-ANONYMIZATION MODULE ---
def render_student_lookup_tool():
    """De-anonymization tool restricted to Guidance Counselors."""
    st.subheader("🔍 Confidential Student De-Anonymization Tool")
    st.caption(
        "Authorized Counselor Feature — Data Privacy Act of 2012 (RA 10173)"
        " Compliant"
    )

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

    st.markdown("---")
    st.markdown("##### 📋 Batch Section Roster Resolver")
    uploaded_file = st.file_uploader(
        "Upload Class Roster CSV (Must include 'LRN' and 'Student Name')",
        type=["csv"],
    )

    if uploaded_file is not None:
        try:
            roster_df = pd.read_csv(uploaded_file)
            if "LRN" in roster_df.columns:
                roster_df["LRN"] = roster_df["LRN"].astype(str).str.strip()
                roster_df["Anonymous Token"] = roster_df["LRN"].apply(
                    generate_anonymous_id
                )

                if target_token:
                    matched = roster_df[
                        roster_df["Anonymous Token"] == target_token
                    ]
                    if not matched.empty:
                        info = matched.iloc[0]
                        st.error(
                            f"🚨 **MATCH FOUND FOR {target_token}:**\n\n"
                            f"* **Student Name:** {info.get('Student Name', 'N/A')}\n"
                            f"* **LRN:** {info.get('LRN')}"
                        )
                    else:
                        st.warning(
                            f"No match for **{target_token}** in this roster."
                        )

                with st.expander("View Full Section Mapping Roster"):
                    st.dataframe(roster_df, use_container_width=True)
            else:
                st.error("CSV must contain an 'LRN' column.")
        except Exception as e:
            st.error(f"Error processing roster: {e}")

    st.markdown(
        """
    <div class="guidance-box">
        <b>What This Tool Implies:</b><br>
        * Converts anonymized high-risk flags back into student identity records within local counselor memory.<br><br>
        <b>Counselor Protocol:</b><br>
        1. <b>Confidential Consultation:</b> Initiate discreet 1-on-1 counseling intake sessions for verified high-priority tokens.<br>
        2. <b>Non-Disclosure:</b> Maintain strict privacy under RA 10173; do not disclose de-anonymized records to non-authorized personnel.
    </div>
    """,
        unsafe_allow_html=True,
    )


# --- AUTHENTICATION ---
if "auth_role" not in st.session_state:
    st.session_state.auth_role = None
    st.session_state.auth_section = None

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
                pin_df = load_pin_config()
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

    # Sidebar Navigation & Context
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
    pin_df = load_pin_config()

    # Scope Selection
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

    # MANUAL REFRESH BUTTON (PURGES STALE DATA CACHE)
    if st.sidebar.button("🔄 Refresh Live Data"):
        st.cache_data.clear()
        st.rerun()

    if st.sidebar.button("Logout"):
        st.session_state.auth_role = None
        st.session_state.auth_section = None
        st.cache_data.clear()
        st.rerun()

    # Filter Datasets
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

    # App Header
    st.title(f"Classroom Wellbeing Overview: {active_section_filter}")
    st.caption(
        f"Logged in as: **{role}** | Real-time wellbeing tracking, proactive"
        " cyberbullying early-warning, and anti-prank filtered metrics."
    )

    # --- TOP KEY METRICS & PROACTIVE ANTI-BULLYING RADAR ---
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    total_pulse = len(df_pulse) if not df_pulse.empty else 0
    total_badges = len(df_badges) if not df_badges.empty else 0
    overwhelmed_count = (
        len(df_pulse[df_pulse["Mood"].str.contains("Overwhelmed", na=False)])
        if not df_pulse.empty
        else 0
    )
    counselor_req_count = (
        len(df_pulse[df_pulse["Clean_Counselor_Request"].str.strip() != ""])
        if not df_pulse.empty
        else 0
    )

    # Proactive Bullying Flags Calculation
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

    col_m1.metric("💬 Pulse Check-Ins", total_pulse)
    col_m2.metric("🏅 Badges Awarded", total_badges)
    col_m3.metric("🌧️ Overwhelmed Moods", overwhelmed_count)
    col_m4.metric("🕊️ Counselor Requests", counselor_req_count)
    col_m5.metric(
        "🛡️ Cyberbullying / Exclusion Flags",
        f"{cyberbullying_flags + bystander_flags}",
        delta=f"{cyberbullying_flags} GC / {bystander_flags} Bystander",
        delta_color="inverse",
    )

    st.markdown("---")

    # --- PROACTIVE PRIORITY SUPPORT & ANTI-BULLYING ALERT BANNER ---
    if not df_pulse.empty:
        high_risk = df_pulse[
            (df_pulse["Mood"].str.contains("Overwhelmed", na=False))
            | (df_pulse["Clean_Counselor_Request"].str.strip() != "")
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

        if not high_risk.empty:
            st.markdown(
                f"""
                <div class="alert-high">
                    <b>🚨 Priority Support & Anti-Bullying Alerts ({active_section_filter}):</b> {len(high_risk)} submission(s) indicate emotional distress, direct counseling requests, or active cyberbullying/exclusion warnings.
                </div>
            """,
                unsafe_allow_html=True,
            )

            with st.expander(
                "📋 Priority Support Log & Action Items", expanded=True
            ):
                display_risk_cols = [
                    "Timestamp",
                    "Class/Section",
                    "Student LRN",
                    "Mood",
                    "GC_Vibe",
                    "Bystander_Check",
                    "Clean_Counselor_Request",
                    "Source_Tag",
                ]
                avail_risk_cols = [
                    c for c in display_risk_cols if c in high_risk.columns
                ]
                st.dataframe(high_risk[avail_risk_cols], use_container_width=True)

                st.markdown(
                    f"""
                <div class="guidance-box">
                    <b>What This Alert Implies:</b><br>
                    * Identified submissions include students in emotional distress, active cyberbullying/GC toxic atmosphere flags, or explicit bystander concerns.<br><br>
                    <b>Proactive Anti-Bullying Action Plan (RA 10627 / DepEd Order No. 40):</b><br>
                    * <b>Teacher Action:</b> Pre-emptively adjust seating arrangements using the <b>Peer Inclusion Sociogram</b>. Do not leave seating or grouping unmanaged.<br>
                    * <b>Counselor Action:</b> Use the <b>Confidential De-Anonymization Tool</b> to schedule discreet, non-punitive 1-on-1 check-ins with flagged tokens.
                </div>
                """,
                    unsafe_allow_html=True,
                )

    # --- DYNAMIC TABS SETUP ---
    tab_titles = [
        "🛡️ Anti-Bullying & Mood Analytics",
        "💬 Pulse Check-Ins Log",
        "🏅 Kindness Badges Log",
        "🫂 Peer Inclusion & Sociogram",
        "📐 IFR Tracker",
    ]

    if role == "Counselor":
        tab_titles.extend(["🔍 Student De-Anonymization", "⚙️ PIN Manager"])

    tabs = st.tabs(tab_titles)

    # --- TAB 1: ANTI-BULLYING & MOOD VISUALIZATIONS ---
    with tabs[0]:
        st.subheader(
            f"🛡️ Proactive Anti-Bullying Radar & Mood Climate ({active_section_filter})"
        )

        if not df_pulse.empty:
            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                st.markdown("##### 🌐 Class Group Chat & Social Media Atmosphere")
                vibe_counts = df_pulse["GC_Vibe"].value_counts().reset_index()
                vibe_counts.columns = ["Atmosphere Vibe", "Count"]

                fig_vibe = px.pie(
                    vibe_counts,
                    names="Atmosphere Vibe",
                    values="Count",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Bold,
                    title="Online Vibe Check (Cyberbullying Early Warning)",
                )
                st.plotly_chart(fig_vibe, use_container_width=True)

            with col_chart2:
                st.markdown("##### 👁️ Bystander Observation Breakdown")
                bystander_counts = (
                    df_pulse["Bystander_Check"].value_counts().reset_index()
                )
                bystander_counts.columns = ["Observation", "Count"]

                fig_bystander = px.bar(
                    bystander_counts,
                    x="Count",
                    y="Observation",
                    orientation="h",
                    color="Observation",
                    title="Bystander Bullying & Exclusion Signals",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig_bystander.update_layout(
                    showlegend=False, yaxis={"autorange": "reversed"}
                )
                st.plotly_chart(fig_bystander, use_container_width=True)

            st.markdown("---")
            st.markdown("##### 📈 Emotional Mood Climate Distribution")
            mood_counts = df_pulse["Mood"].value_counts().reset_index()
            mood_counts.columns = ["Mood", "Count"]

            fig_bar = px.bar(
                mood_counts,
                x="Mood",
                y="Count",
                color="Mood",
                title=f"Classroom Mood Breakdown — {active_section_filter}",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

            st.markdown(
                f"""
            <div class="guidance-box">
                <b>What These Charts Imply:</b><br>
                * <b>Online Vibe:</b> Highlights early signals of cyberbullying in informal class group chats before physical incidents occur.<br>
                * <b>Bystander Signals:</b> Quantifies student observations of exclusion or harassment, enabling early adult intervention under DepEd Child Protection Policy.<br><br>
                <b>Recommended Staff Action:</b><br>
                1. If yellow or red online vibes emerge, conduct a teacher-led digital citizenship & empathy warm-up session.<br>
                2. Pair quiet or teased students with verified <b>Dual-Filter Peer Anchors</b> in upcoming group tasks.
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.info("No check-in data available yet for anti-bullying analytics.")

    # --- TAB 2: PULSE CHECK-INS LOG TABLE ---
    with tabs[1]:
        st.subheader(
            f"💬 Confidential Student Pulse Check-Ins ({active_section_filter})"
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

            st.dataframe(df_pulse[avail_cols], use_container_width=True)

            st.markdown(
                """
            <div class="guidance-box">
                <b>What This Table Implies:</b><br>
                * Comprehensive log of student reflections including peer appreciations, preferred partners, group chat vibes, and private notes.<br><br>
                <b>Recommended Action Items:</b><br>
                1. <b>Review Counselor Notes:</b> Flagged entries should be coordinated with the guidance office.<br>
                2. <b>Cross-reference Peer Choices:</b> Utilize preferred groupmates to structure balanced learning groups.
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.info("No check-in submissions found.")

    # --- TAB 3: KINDNESS BADGES LOG ---
    with tabs[2]:
        st.subheader(f"🏅 Kindness Badges Log ({active_section_filter})")
        if not df_badges.empty:
            st.dataframe(df_badges, use_container_width=True)
        else:
            st.info("No kindness badges awarded yet.")

    # --- TAB 4: PEER INCLUSION & SOCIOGRAM ---
    with tabs[3]:
        st.subheader(f"🫂 Peer Inclusion & Sociogram ({active_section_filter})")
        render_sociogram_analytics(
            df_pulse, df_badges, section_label=active_section_filter
        )

    # --- TAB 5: IFR TRACKER ---
    with tabs[4]:
        render_ifr_tracker()

    # --- TAB 6 & 7: COUNSELOR ONLY TOOLS ---
    if role == "Counselor":
        with tabs[5]:
            render_student_lookup_tool()

        with tabs[6]:
            st.subheader("⚙️ PIN & Section Configuration Manager")
            st.dataframe(pin_df, use_container_width=True)
