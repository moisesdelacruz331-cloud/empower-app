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
        data = ws.get_all_values()  # 3x-5x faster than get_all_records()
        if not data or len(data) < 2:
            return pd.DataFrame(
                columns=["Class/Section", "Student PIN", "Teacher PIN"]
            )

        df = pd.DataFrame(data[1:], columns=data[0])
        # Clean column spaces if present
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
    """Pre-cleaning pipeline: Deduplicates per student & strips self-nominations."""
    if df_pulse.empty:
        return df_pulse

    df_clean = df_pulse.copy()

    if "Timestamp" in df_clean.columns and "Student LRN" in df_clean.columns:
        df_clean["Timestamp"] = pd.to_datetime(
            df_clean["Timestamp"], errors="coerce"
        )
        df_clean = (
            df_clean.sort_values("Timestamp")
            .groupby("Student LRN")
            .last()
            .reset_index()
        )

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
                # Instant check from pre-warmed cache
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

    if st.sidebar.button("🔄 Refresh Live Data"):
        st.cache_data.clear()
        st.rerun()

    if st.sidebar.button("Logout"):
        st.session_state.auth_role = None
        st.session_state.auth_section = None
        st.cache_data.clear()
        st.rerun()

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

    st.title(f"Classroom Wellbeing Overview: {active_section_filter}")
    st.caption(
        f"Logged in as: **{role}** | Real-time wellbeing tracking, proactive"
        " cyberbullying early-warning, and anti-prank filtered metrics."
    )

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

    with tabs[0]:
        st.subheader(
            f"🛡️ Proactive Anti-Bullying Radar & Mood Climate ({active_section_filter})"
        )
        if not df_pulse.empty:
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                vibe_counts = df_pulse["GC_Vibe"].value_counts().reset_index()
                vibe_counts.columns = ["Atmosphere Vibe", "Count"]
                fig_vibe = px.pie(
                    vibe_counts,
                    names="Atmosphere Vibe",
                    values="Count",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Bold,
                    title="Online Vibe Check",
                )
                st.plotly_chart(fig_vibe, use_container_width=True)

            with col_chart2:
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
                    title="Bystander Bullying Signals",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig_bystander.update_layout(
                    showlegend=False, yaxis={"autorange": "reversed"}
                )
                st.plotly_chart(fig_bystander, use_container_width=True)
        else:
            st.info("No check-in data available yet.")

    with tabs[1]:
        st.subheader(
            f"💬 Confidential Student Pulse Check-Ins ({active_section_filter})"
        )
        if not df_pulse.empty:
            st.dataframe(df_pulse, use_container_width=True)

    with tabs[2]:
        st.subheader(f"🏅 Kindness Badges Log ({active_section_filter})")
        if not df_badges.empty:
            st.dataframe(df_badges, use_container_width=True)

    with tabs[3]:
        render_sociogram_analytics(
            df_pulse, df_badges, section_label=active_section_filter
        )

    with tabs[4]:
        render_ifr_tracker()

    if role == "Counselor":
        with tabs[5]:
            render_student_lookup_tool()
        with tabs[6]:
            st.subheader("⚙️ PIN & Section Configuration Manager")
            st.dataframe(pin_df, use_container_width=True)
