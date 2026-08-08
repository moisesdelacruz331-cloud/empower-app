from datetime import datetime
import hashlib
import gspread
import networkx as nx
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="EMPOWER Teacher & Counselor Portal", page_icon="📊", layout="wide"
)

SALT_KEY = st.secrets.get("SALT_KEY", "EMPOWER_2026_SECURE_SALT")


# --- ANONYMIZATION UTILITIES ---
def generate_anonymous_id(raw_id: str, salt: str = SALT_KEY) -> str:
    if not raw_id or str(raw_id).strip() == "":
        return ""
    clean_id = str(raw_id).strip()
    salted_bytes = f"{clean_id}{salt}".encode("utf-8")
    hash_digest = hashlib.sha256(salted_bytes).hexdigest()
    return f"STU-{hash_digest[:4].upper()}"


# Styling
st.markdown(
    """
    <style>
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
    </style>
""",
    unsafe_allow_html=True,
)


# --- 3. ANTI-PRANK & ANOMALY FILTERING PIPELINE ---
def clean_pulse_data(df_pulse: pd.DataFrame) -> pd.DataFrame:
    """Pre-cleaning pipeline to filter out trolling, duplicate submissions, and self-nominations."""
    if df_pulse.empty:
        return df_pulse

    df_clean = df_pulse.copy()

    # Ensure Timestamp ordering and keep only latest submission per student
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

    # Sanitize self-nominations
    if "Kind Peer" in df_clean.columns:
        df_clean["Kind Peer"] = df_clean.apply(
            lambda r: (
                ""
                if str(r["Student LRN"]).strip()
                == str(r["Kind Peer"]).strip()
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


# --- 1 & 2. SOCIOGRAM ANALYTICS (DUAL-FILTER ANCHORS & ABSENTEEISM MASKING) ---
def render_sociogram_analytics(
    df_pulse, df_badges, section_roster=None, section_label="Active View"
):
    """Calculates network graph, masks absent students, and applies dual-filter peer anchor logic."""
    df_clean = clean_pulse_data(df_pulse)

    if df_clean.empty:
        st.info(f"No valid check-in data available for {section_label}.")
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
                G.add_edge(sender, preferred_peer, relation="Preferred Partner")

    if G.number_of_nodes() == 0:
        st.info(f"Insufficient network data for {section_label}.")
        return []

    in_degree = dict(G.in_degree())
    n_nodes = G.number_of_nodes()
    centrality = (
        {node: deg / (n_nodes - 1) for node, deg in in_degree.items()}
        if n_nodes > 1
        else {node: 0.0 for node in G.nodes()}
    )

    # 2. ACTIVE ABSENTEEISM DATA MASKING
    present_students = set(df_clean["Student LRN"].astype(str).str.strip().unique())
    if section_roster and len(section_roster) > 0:
        full_roster = set([str(x).strip() for x in section_roster])
        absent_students = full_roster - present_students
    else:
        absent_students = set()

    # Filter isolated nodes: degree 0 AND not marked absent
    isolated_nodes = [
        node
        for node, deg in in_degree.items()
        if deg == 0 and node not in absent_students
    ]

    # 1. DUAL-FILTER PEER ANCHOR LOGIC
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
        if c_val >= centrality_threshold and earned_badges >= badge_median and deg > 0:
            eligible_anchors.append(node)

    # Plot Layout
    pos = nx.spring_layout(G, k=0.6, seed=42)
    edge_x, edge_y = [], []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, line=dict(width=1.2, color="#CBD5E1"), hoverinfo="none", mode="lines"
    )

    node_x, node_y, node_colors, node_sizes, node_labels, node_hover = [], [], [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        deg = in_degree[node]

        if node in isolated_nodes:
            node_colors.append("#EF4444")
            node_sizes.append(22)
        elif node in eligible_anchors:
            node_colors.append("#3B82F6")  # Blue for Dual-Filter Peer Anchors
            node_sizes.append(24)
        else:
            node_colors.append("#10B981")
            node_sizes.append(16 + (deg * 5))

        node_labels.append(str(node))
        node_hover.append(
            f"<b>Student ID:</b> {node}<br>"
            f"<b>Nominations Received:</b> {deg}<br>"
            f"<b>Badges Earned:</b> {badge_counts.get(node, 0)}<br>"
            f"<b>Status:</b> {'Dual-Filter Peer Anchor' if node in eligible_anchors else 'Isolated' if node in isolated_nodes else 'Standard'}"
        )

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers+text", hoverinfo="text",
        text=node_labels, textposition="top center", hovertext=node_hover,
        marker=dict(color=node_colors, size=node_sizes, line=dict(width=2, color="#FFFFFF"))
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title=f"<b>Sociogram Network — Section: {section_label}</b>",
        showlegend=False, margin=dict(b=20, l=10, r=10, t=50),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Key Display
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.markdown("🔴 **Red:** Isolated (Present, 0 Nominations)")
    col_k2.markdown("🔵 **Blue:** Qualified Peer Anchor (Centrality + Badges)")
    col_k3.markdown("🟢 **Green:** Connected Peer")
    col_k4.markdown(f"⚪ **Masked Absentees:** {len(absent_students)}")

    st.markdown("---")
    st.subheader(f"💡 Real-Time Sociogram Analysis ({section_label})")

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Section Inclusion Rate", f"{((n_nodes - len(isolated_nodes)) / n_nodes * 100):.1f}%")
    col_m2.metric("Dual-Filter Peer Anchors", f"{len(eligible_anchors)} identified", f"{', '.join(eligible_anchors[:2]) if eligible_anchors else 'None'}")
    col_m3.metric("Verified Isolated Students", f"{len(isolated_nodes)}")

    return isolated_nodes


# --- 4. IMPLEMENTATION FIDELITY RATE (IFR) TRACKER TOOL ---
def render_ifr_tracker():
    """Renders the Implementation Fidelity Rate tracker to monitor teacher intervention adherence."""
    st.subheader("📐 Implementation Fidelity Rate ($IFR$) Tracker")
    st.caption("Track pedagogical adherence to peer-shielding and deliberate grouping strategies.")

    col1, col2 = st.columns(2)
    with col1:
        total_assigned = st.number_input("Total Assigned Group Activities", min_value=1, value=10, step=1)
        correctly_paired = st.number_input("Correctly Paired/Shielded Activities", min_value=0, max_value=int(total_assigned), value=8, step=1)

    ifr_value = (correctly_paired / total_assigned) * 100

    st.markdown("### $IFR$ Benchmark Result")
    if ifr_value >= 85:
        st.success(f"🟢 **IFR = {ifr_value:.1f}%** — Target Met (≥ 85%). High pairing fidelity.")
    else:
        st.error(f"🔴 **IFR = {ifr_value:.1f}%** — Below Target (< 85%). Pairing protocols require adjustment.")

    st.latex(r"IFR = \left( \frac{\text{Correctly Paired Activities}}{\text{Total Assigned Activities}} \right) \times 100")


# --- DATABASE & DATA LOADING ---
@st.cache_resource
def connect_to_gsheet():
    creds = dict(st.secrets["connections"]["gsheets"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds)
    return gc.open_by_url(creds.get("spreadsheet"))


@st.cache_data(ttl=10)
def load_pin_config():
    try:
        sh = connect_to_gsheet()
        ws = sh.worksheet("Class Configuration")
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame(columns=["Class/Section", "Student PIN", "Teacher PIN"])


def parse_mood_and_requests(df):
    if df.empty:
        df["Mood"] = []
        df["Clean_Counselor_Request"] = []
        return df
    if "Counselor Request" in df.columns:
        df["Mood"] = df["Counselor Request"].astype(str).str.extract(r"\[Mood:\s*([^\]]+)\]").fillna("🌱 Not Specified")
        df["Clean_Counselor_Request"] = df["Counselor Request"].astype(str).str.replace(r"\[Mood:\s*([^\]]+)\]\s*", "", regex=True)
    else:
        df["Mood"] = "🌱 Not Specified"
        df["Clean_Counselor_Request"] = ""
    return df


# --- AUTHENTICATION & APP LAYOUT ---
if "auth_role" not in st.session_state:
    st.session_state.auth_role = None
    st.session_state.auth_section = None

if not st.session_state.auth_role:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("fatimanhslogo.png", width=80)
        st.title("🔒 EMPOWER Staff Portal")
        login_pin = st.text_input("Enter Teacher PIN / Passcode:", type="password").strip()

        if st.button("Login to Dashboard"):
            counselor_pass = str(st.secrets.get("ADMIN_PASSWORD", "COUNSELOR2026")).strip()
            if login_pin == counselor_pass:
                st.session_state.auth_role = "Counselor"
                st.session_state.auth_section = "ALL"
                st.rerun()
            else:
                pin_df = load_pin_config()
                if not pin_df.empty and "Teacher PIN" in pin_df.columns:
                    matched = pin_df[pin_df["Teacher PIN"].astype(str).str.strip() == login_pin]
                    if not matched.empty:
                        st.session_state.auth_role = "Teacher"
                        st.session_state.auth_section = matched.iloc[0]["Class/Section"]
                        st.rerun()
                    else:
                        st.error("Invalid Passcode.")
                else:
                    st.error("Invalid Passcode.")
else:
    role = st.session_state.auth_role
    assigned_section = st.session_state.auth_section

    st.sidebar.image("fatimanhslogo.png", width=100)
    st.sidebar.title("📊 Staff Analytics")
    sh = connect_to_gsheet()

    try:
        ws_pulse = sh.worksheet("Pulse Checkins")
        df_pulse_raw = parse_mood_and_requests(pd.DataFrame(ws_pulse.get_all_records()))
    except Exception:
        df_pulse_raw = pd.DataFrame()

    try:
        ws_badges = sh.worksheet("Kindness Badges")
        df_badges_raw = pd.DataFrame(ws_badges.get_all_records())
    except Exception:
        df_badges_raw = pd.DataFrame()

    # Apply global anti-prank cleaning
    df_pulse_clean = clean_pulse_data(df_pulse_raw)

    pin_df = load_pin_config()
    if role == "Counselor":
        available_sections = sorted(list(set(df_pulse_clean["Class/Section"].dropna().astype(str).unique()))) if not df_pulse_clean.empty else []
        selected_view_scope = st.sidebar.selectbox("🎯 Counselor View Scope:", options=["ALL"] + available_sections)
        active_section_filter = selected_view_scope
    else:
        active_section_filter = assigned_section

    if st.sidebar.button("Logout"):
        st.session_state.auth_role = None
        st.cache_data.clear()
        st.rerun()

    # Filtered View Data
    df_pulse = df_pulse_clean.copy()
    df_badges = df_badges_raw.copy()
    if active_section_filter != "ALL":
        if not df_pulse.empty and "Class/Section" in df_pulse.columns:
            df_pulse = df_pulse[df_pulse["Class/Section"].astype(str).str.strip() == active_section_filter]
        if not df_badges.empty and "Class/Section" in df_badges.columns:
            df_badges = df_badges[df_badges["Class/Section"].astype(str).str.strip() == active_section_filter]

    st.title(f"Classroom Wellbeing Overview: {active_section_filter}")

    # Tabs Structure
    tabs = ["📈 Mood Visualizations", "💬 Pulse Check-Ins", "🏅 Kindness Badges", "🫂 Peer Inclusion & Sociogram", "📐 IFR Tracker"]
    if role == "Counselor":
        tabs.extend(["🔍 Student De-Anonymization", "⚙️ PIN Manager"])

    tab_objects = st.tabs(tabs)

    with tab_objects[0]:
        st.subheader("📈 Emotional Climate")
        if not df_pulse.empty and "Mood" in df_pulse.columns:
            mood_counts = df_pulse["Mood"].value_counts().reset_index()
            mood_counts.columns = ["Mood", "Count"]
            fig_bar = px.bar(mood_counts, x="Mood", y="Count", color="Mood")
            st.plotly_chart(fig_bar, use_container_width=True)

    with tab_objects[1]:
        st.subheader("💬 Confidential Pulse Log")
        st.dataframe(df_pulse, use_container_width=True)

    with tab_objects[2]:
        st.subheader("🏅 Kindness Badges")
        st.dataframe(df_badges, use_container_width=True)

    with tab_objects[3]:
        st.subheader("🫂 Peer Inclusion & Sociometric Analytics")
        # Optional Roster Input for Absenteeism Masking
        roster_input = st.text_area("Optional Section Roster LRNs (Comma-separated for absenteeism masking):", value="")
        roster_list = [x.strip() for x in roster_input.split(",") if x.strip()] if roster_input else None

        render_sociogram_analytics(df_pulse, df_badges, section_roster=roster_list, section_label=active_section_filter)

    with tab_objects[4]:
        render_ifr_tracker()
