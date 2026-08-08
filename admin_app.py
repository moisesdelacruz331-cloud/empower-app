import hashlib
import gspread
import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="EMPOWER Teacher & Counselor Portal", page_icon="📊", layout="wide"
)

# Salt Key for Anonymization Alignment
SALT_KEY = st.secrets.get("SALT_KEY", "EMPOWER_2026_SECURE_SALT")


# --- ANONYMIZATION UTILITIES ---
def generate_anonymous_id(raw_id: str, salt: str = SALT_KEY) -> str:
    """Generates the same salted SHA-256 token used in student check-ins."""
    if not raw_id or str(raw_id).strip() == "":
        return ""
    clean_id = str(raw_id).strip()
    salted_bytes = f"{clean_id}{salt}".encode("utf-8")
    hash_digest = hashlib.sha256(salted_bytes).hexdigest()
    return f"STU-{hash_digest[:4].upper()}"


# Custom Styling
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


# --- SOCIOMETRIC GRAPH ANALYSIS MODULE ---
def render_sociogram_analytics(df_pulse):
    """Generates an interactive Plotly sociogram network graph from peer nominations,

    identifies structurally isolated nodes, and provides real-time teacher interpretations.
    """
    if df_pulse.empty:
        st.info("No check-in data available to build network graph.")
        return []

    # Initialize Directed Network Graph
    G = nx.DiGraph()

    # Populate Nodes and Edges from Peer Nominations
    for _, row in df_pulse.iterrows():
        sender = str(row.get("Student LRN", "")).strip()
        kind_peer = str(row.get("Kind Peer", "")).strip()
        preferred_peer = str(row.get("Preferred Groupmate", "")).strip()

        if sender and sender.lower() != "nan":
            G.add_node(sender)

            # Directed Edge: Sender -> Nominated Peer
            if (
                kind_peer
                and kind_peer.lower() != "nan"
                and sender != kind_peer
            ):
                G.add_edge(sender, kind_peer, relation="Kindness")

            if (
                preferred_peer
                and preferred_peer.lower() != "nan"
                and sender != preferred_peer
            ):
                G.add_edge(sender, preferred_peer, relation="Preferred Partner")

    if G.number_of_nodes() == 0:
        st.info("Insufficient peer nomination records to render sociogram.")
        return []

    # Calculate Network Centrality Metrics
    in_degree = dict(G.in_degree())
    n_nodes = G.number_of_nodes()

    # Degree Centrality Formula: C_d(v) = in_degree(v) / (N - 1)
    centrality = (
        {node: deg / (n_nodes - 1) for node, deg in in_degree.items()}
        if n_nodes > 1
        else {node: 0.0 for node in G.nodes()}
    )

    # Generate 2D Node Positions using Fruchterman-Reingold Force-Directed Layout
    pos = nx.spring_layout(G, k=0.6, seed=42)

    # Edge Traces (Lines)
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

    # Node Traces (Markers)
    node_x, node_y = [], []
    node_colors, node_sizes = [], []
    node_labels, node_hover = [], []

    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)

        deg = in_degree[node]
        c_d = centrality[node]

        # Red for isolated nodes; Green for connected nodes
        if deg == 0:
            node_colors.append("#EF4444")
            node_sizes.append(22)
        else:
            node_colors.append("#10B981")
            node_sizes.append(18 + (deg * 6))

        node_labels.append(str(node))
        node_hover.append(
            f"<b>Student Identifier:</b> {node}<br>"
            f"<b>Nominations Received ($deg^- $):</b> {deg}<br>"
            f"<b>In-Degree Centrality ($C_d$):</b> {c_d:.3f}"
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

    # Render Plotly Figure
    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title=dict(
            text="<b>Classroom Sociogram: Peer Inclusion & Isolation Network</b>",
            font=dict(size=16),
        ),
        showlegend=False,
        hovermode="closest",
        margin=dict(b=20, l=10, r=10, t=50),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Visual Legend & Quick Metrics
    st.markdown("##### 🔑 Visual Key & Quick Indicators")
    col_k1, col_k2, col_k3 = st.columns(3)
    col_k1.markdown("🔴 **Red Node:** 0 nominations (At-risk / Isolated)")
    col_k2.markdown(
        "🟢 **Green Node:** Connected (Larger = Higher popularity)"
    )
    col_k3.markdown("🔗 **Gray Line:** Incoming peer nomination")

    # Extract Key Analytical Insights
    isolated_nodes = [node for node, deg in in_degree.items() if deg == 0]
    max_deg = max(in_degree.values()) if in_degree else 0
    top_peers = [
        node for node, deg in in_degree.items() if deg == max_deg and deg > 0
    ]
    inclusion_rate = (
        ((n_nodes - len(isolated_nodes)) / n_nodes * 100) if n_nodes > 0 else 0
    )

    st.markdown("---")

    # REAL-TIME INTERPRETATION BREAKDOWN FOR TEACHERS
    st.subheader("💡 Real-Time Sociogram Interpretation")

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Classroom Inclusion Rate", f"{inclusion_rate:.1f}%")
    col_m2.metric(
        "Top Connected Peer Anchor(s)",
        f"{', '.join(top_peers) if top_peers else 'None'}",
        f"{max_deg} nominations received",
    )
    col_m3.metric("Isolated Students", f"{len(isolated_nodes)} of {n_nodes}")

    with st.expander(
        "📖 **Teacher Guidance & Pedagogical Action Plan**", expanded=True
    ):
        st.markdown(f"""
        * **Social Climate Summary:** **{inclusion_rate:.1f}%** of students in this section were nominated by at least one peer as a preferred groupmate or kind classmate.
        * **Peer Anchors (Bridge Builders):** Student(s) **{', '.join(top_peers) if top_peers else 'None'}** hold the highest centrality. They are trusted by peers and can serve as positive group leaders.
        * **Isolated Nodes:** Student(s) **{', '.join(isolated_nodes) if isolated_nodes else 'None'}** received zero nominations, putting them at structural risk for social isolation or low participation.

        **Recommended Classroom Actions:**
        1. **Avoid Unstructured Grouping:** Avoid asking students to "pick your own partners," as this deepens isolation for red-node students.
        2. **Strategic Pairing:** Quietly group isolated students with central peer anchors (**{', '.join(top_peers[:2]) if top_peers else 'leaders'}**) during upcoming group activities to build inclusive social ties.
        3. **Observation Check:** Check in privately with red-node students to evaluate their emotional comfort and integration in class.
        """)

    return isolated_nodes


# --- COUNSELOR DE-ANONYMIZATION MODULE ---
def render_student_lookup_tool():
    """Provides authorized guidance personnel with two-way token resolution

    to identify flagged high-risk or isolated students.
    """
    st.subheader("🔍 Confidential Student De-Anonymization Tool")
    st.caption(
        "Authorized Guidance Counselor Feature — Compliant with Data Privacy"
        " Act of 2012 (RA 10173)"
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
                f"✅ **MATCH CONFIRMED:** LRN `{input_lrn}` maps directly to"
                f" **{generated_token}**."
            )
        else:
            st.info(f"LRN `{input_lrn}` generates token: **{generated_token}**")

    st.markdown("---")
    st.markdown("##### 📋 Batch Roster Resolver")
    st.caption(
        "Upload an official section roster (CSV containing 'LRN' and 'Student"
        " Name') to match anonymous flags locally."
    )

    uploaded_file = st.file_uploader(
        "Upload Class Roster CSV",
        type=["csv"],
        help="Processed entirely in-memory; student details are never stored to cloud servers.",
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
                    matched_student = roster_df[
                        roster_df["Anonymous Token"] == target_token
                    ]
                    if not matched_student.empty:
                        student_info = matched_student.iloc[0]
                        st.error(
                            f"🚨 **MATCH FOUND FOR {target_token}:**\n\n"
                            f"* **Student Name:**"
                            f" {student_info.get('Student Name', 'N/A')}\n"
                            f"* **LRN:** {student_info.get('LRN')}"
                        )
                    else:
                        st.warning(
                            f"No student matching token **{target_token}**"
                            " found in this uploaded roster."
                        )

                with st.expander("View Full Section Anonymization Mapping"):
                    st.dataframe(roster_df, use_container_width=True)
            else:
                st.error("CSV file must contain an 'LRN' column.")
        except Exception as e:
            st.error(f"Error processing roster file: {e}")


# --- DATABASE CONNECTIONS ---
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
        return pd.DataFrame(
            columns=["Class/Section", "Student PIN", "Teacher PIN"]
        )


def parse_mood_and_requests(df):
    if df.empty:
        df["Mood"] = []
        df["Clean_Counselor_Request"] = []
        return df

    if "Counselor Request" in df.columns:
        df["Mood"] = (
            df["Counselor Request"]
            .astype(str)
            .str.extract(r"\[Mood:\s*([^\]]+)\]")
        )
        df["Mood"] = df["Mood"].fillna("🌱 Not Specified")
        df["Clean_Counselor_Request"] = (
            df["Counselor Request"]
            .astype(str)
            .str.replace(r"\[Mood:\s*([^\]]+)\]\s*", "", regex=True)
        )
    else:
        df["Mood"] = "🌱 Not Specified"
        df["Clean_Counselor_Request"] = ""

    return df


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
            "Enter Teacher PIN / Passcode:", type="password"
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
                        st.error("Invalid Passcode or Teacher PIN.")
                else:
                    st.error("Invalid Passcode.")

else:
    # --- LOGGED IN DASHBOARD ---
    role = st.session_state.auth_role
    assigned_section = st.session_state.auth_section

    st.sidebar.image("fatimanhslogo.png", width=100)
    st.sidebar.title("📊 Staff Analytics")
    st.sidebar.write(f"Role: **{role}**")
    st.sidebar.write(f"Assigned Scope: **{assigned_section}**")

    if st.sidebar.button("Logout"):
        st.session_state.auth_role = None
        st.session_state.auth_section = None
        st.cache_data.clear()
        st.rerun()

    sh = connect_to_gsheet()

    try:
        ws_pulse = sh.worksheet("Pulse Checkins")
        df_pulse = parse_mood_and_requests(
            pd.DataFrame(ws_pulse.get_all_records())
        )
    except Exception:
        df_pulse = pd.DataFrame()

    try:
        ws_badges = sh.worksheet("Kindness Badges")
        df_badges = pd.DataFrame(ws_badges.get_all_records())
    except Exception:
        df_badges = pd.DataFrame()

    if assigned_section != "ALL":
        if not df_pulse.empty and "Class/Section" in df_pulse.columns:
            df_pulse = df_pulse[df_pulse["Class/Section"] == assigned_section]
        if not df_badges.empty and "Class/Section" in df_badges.columns:
            df_badges = df_badges[
                df_badges["Class/Section"] == assigned_section
            ]

    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        st.image("fatimanhslogo.png", width=70)
    with col_title:
        st.title(f"Classroom Wellbeing Overview: {assigned_section}")
        st.caption(
            "Real-time emotional climate, student check-ins, kindness badge"
            " log, and support alerts."
        )

    # Top Metrics
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)

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

    col_m1.metric("💬 Pulse Check-Ins", total_pulse)
    col_m2.metric("🏅 Badges Awarded", total_badges)
    col_m3.metric("🌧️ Overwhelmed Students", overwhelmed_count)
    col_m4.metric("🕊️ Counselor Requests", counselor_req_count)

    st.markdown("---")

    # Priority Alert Banner
    if not df_pulse.empty:
        high_risk = df_pulse[
            (df_pulse["Mood"].str.contains("Overwhelmed", na=False))
            | (df_pulse["Clean_Counselor_Request"].str.strip() != "")
        ]

        if not high_risk.empty:
            st.markdown(
                f"""
                <div class="alert-high">
                    <b>⚠️ Priority Support Needed:</b> {len(high_risk)} student entry/entries indicate distress or requested a private chat.
                </div>
            """,
                unsafe_allow_html=True,
            )

            with st.expander(
                "🚨 View High-Priority Support Requests", expanded=False
            ):
                st.dataframe(
                    high_risk[
                        [
                            "Timestamp",
                            "Class/Section",
                            "Student LRN",
                            "Mood",
                            "Clean_Counselor_Request",
                        ]
                    ],
                    use_container_width=True,
                )

    # Dashboard Tabs
    if role == "Counselor":
        (
            tab_mood,
            tab_pulse,
            tab_badges,
            tab_peer,
            tab_lookup,
            tab_pin,
        ) = st.tabs([
            "📈 Mood Visualizations",
            "💬 Pulse Check-Ins",
            "🏅 Kindness Badges",
            "🫂 Peer Inclusion Watchlist",
            "🔍 Student De-Anonymization",
            "⚙️ PIN Manager",
        ])
    else:
        tab_mood, tab_pulse, tab_badges, tab_peer = st.tabs([
            "📈 Mood Visualizations",
            "💬 Pulse Check-Ins",
            "🏅 Kindness Badges",
            "🫂 Peer Inclusion Watchlist",
        ])

    # TAB 1: MOOD VISUALIZATIONS
    with tab_mood:
        st.subheader("📈 Classroom Emotional Climate")
        if not df_pulse.empty and "Mood" in df_pulse.columns:
            col_chart1, col_chart2 = st.columns(2)
            mood_counts = df_pulse["Mood"].value_counts().reset_index()
            mood_counts.columns = ["Mood", "Count"]

            with col_chart1:
                fig_bar = px.bar(
                    mood_counts,
                    x="Mood",
                    y="Count",
                    color="Mood",
                    title="Student Mood Counts",
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                )
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)

            with col_chart2:
                fig_pie = px.pie(
                    mood_counts,
                    names="Mood",
                    values="Count",
                    hole=0.4,
                    title="Mood Share Breakdown",
                    color_discrete_sequence=px.colors.qualitative.Set3,
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No student check-in data available yet for graphs.")

    # TAB 2: PULSE CHECK-INS LOG
    with tab_pulse:
        st.subheader("💬 Confidential Student Pulse Check-Ins")
        if not df_pulse.empty:
            display_cols = [
                "Timestamp",
                "Class/Section",
                "Student LRN",
                "Mood",
                "Kind Peer",
                "Preferred Groupmate",
                "Isolated Peer",
                "Clean_Counselor_Request",
            ]
            available_cols = [c for c in display_cols if c in df_pulse.columns]

            st.dataframe(df_pulse[available_cols], use_container_width=True)

            csv_pulse = df_pulse.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Export Pulse Check-Ins (CSV)",
                data=csv_pulse,
                file_name=f"pulse_checkins_{assigned_section}.csv",
                mime="text/csv",
            )
        else:
            st.info("No pulse check-in entries found for this section yet.")

    # TAB 3: KINDNESS BADGES LOG
    with tab_badges:
        st.subheader("🏅 Peer Kindness Badges Log")
        if not df_badges.empty:
            st.dataframe(df_badges, use_container_width=True)

            csv_badges = df_badges.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Export Kindness Badges (CSV)",
                data=csv_badges,
                file_name=f"kindness_badges_{assigned_section}.csv",
                mime="text/csv",
            )
        else:
            st.info("No kindness badges sent in this section yet.")

    # TAB 4: PEER INCLUSION WATCHLIST & SOCIOGRAM NETWORK
    with tab_peer:
        st.subheader("🫂 Peer Inclusion & Sociometric Analytics")
        st.caption(
            "Interactive network graph identifying peer centrality and"
            " structurally isolated students ($deg^- = 0$)."
        )

        # Render Network Graph, Interpretation, & Extract Isolated Identifiers
        isolated_students = render_sociogram_analytics(df_pulse)

        if isolated_students:
            st.markdown(
                f"""
                <div class="alert-watch">
                    <b>🚨 Sociometric Isolation Alert:</b> {len(isolated_students)} student(s) received 0 incoming peer nominations:<br>
                    <b>Isolated Node Identifiers:</b> {', '.join(isolated_students)}
                </div>
            """,
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.subheader("📋 Peer-Nominated Isolation Reports")

        if not df_pulse.empty and "Isolated Peer" in df_pulse.columns:
            isolated_df = df_pulse[
                df_pulse["Isolated Peer"].astype(str).str.strip() != ""
            ]

            if not isolated_df.empty:
                show_cols = [
                    c
                    for c in [
                        "Timestamp",
                        "Class/Section",
                        "Isolated Peer",
                        "Kind Peer",
                        "Preferred Groupmate",
                    ]
                    if c in isolated_df.columns
                ]
                st.dataframe(isolated_df[show_cols], use_container_width=True)
            else:
                st.info(
                    "No manual peer isolation reports submitted in this"
                    " section."
                )
        else:
            st.info("No peer isolation data available.")

    # COUNSELOR-ONLY TABS
    if role == "Counselor":
        # TAB 5: STUDENT DE-ANONYMIZATION LOOKUP
        with tab_lookup:
            render_student_lookup_tool()

        # TAB 6: COUNSELOR PIN MANAGEMENT
        with tab_pin:
            st.subheader("⚙️ Manage Sections & Access PINs")
            pin_df = load_pin_config()

            with st.form("add_sec_form", clear_on_submit=True):
                st.write("➕ **Add New Class Section**")
                col_a, col_b, col_c = st.columns(3)
                nsec = col_a.text_input(
                    "Section Name", placeholder="10 - Emerald"
                )
                spin = col_b.text_input("Student PIN", placeholder="1001")
                tpin = col_c.text_input(
                    "Teacher PIN", placeholder="EMERALD2026"
                )

                if st.form_submit_button("Save Section & PINs"):
                    if nsec.strip() and spin.strip() and tpin.strip():
                        ws_c = sh.worksheet("Class Configuration")
                        ws_c.append_row(
                            [nsec.strip(), spin.strip(), tpin.strip()]
                        )
                        st.cache_data.clear()
                        st.success(f"Added section {nsec} successfully!")
                        st.rerun()
                    else:
                        st.error("Please fill in all fields.")

            st.markdown("---")
            st.write("📋 **Active Class PIN Configurations**")
            st.dataframe(pin_df, use_container_width=True)
