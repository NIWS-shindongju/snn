"""CarbonSNN Streamlit Dashboard (5 pages).

Pages:
    1. Dashboard Home — summary cards + world map
    2. Project Management — CRUD
    3. Analysis Results — 4-panel map + charts
    4. Deforestation Alerts — timeline view
    5. API Key Management
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import folium
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_folium import st_folium

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
API_PREFIX = f"{API_BASE}/api/v1"


def get_headers() -> dict[str, str]:
    """Return authenticated request headers using the stored API key."""
    api_key = st.session_state.get("api_key", "")
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def api_get(endpoint: str, params: dict | None = None) -> Any:
    """Make an authenticated GET request to the API.

    Args:
        endpoint: Path relative to API_PREFIX.
        params: Optional query parameters.

    Returns:
        Parsed JSON response or None on error.
    """
    try:
        resp = requests.get(
            f"{API_PREFIX}{endpoint}",
            headers=get_headers(),
            params=params,
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        st.error(f"API error {resp.status_code}: {resp.text[:200]}")
    except requests.exceptions.ConnectionError:
        st.warning("Cannot connect to API. Is the server running?")
    return None


def api_post(endpoint: str, data: dict) -> Any:
    """Make an authenticated POST request to the API.

    Args:
        endpoint: Path relative to API_PREFIX.
        data: JSON request body.

    Returns:
        Parsed JSON response or None on error.
    """
    try:
        resp = requests.post(
            f"{API_PREFIX}{endpoint}",
            headers=get_headers(),
            json=data,
            timeout=10,
        )
        if resp.status_code in (200, 201, 202):
            return resp.json()
        st.error(f"API error {resp.status_code}: {resp.text[:200]}")
    except requests.exceptions.ConnectionError:
        st.warning("Cannot connect to API.")
    return None


def api_delete(endpoint: str) -> bool:
    """Make an authenticated DELETE request.

    Args:
        endpoint: Path relative to API_PREFIX.

    Returns:
        True if deletion succeeded.
    """
    try:
        resp = requests.delete(
            f"{API_PREFIX}{endpoint}", headers=get_headers(), timeout=10
        )
        return resp.status_code == 204
    except requests.exceptions.ConnectionError:
        return False


# ──────────────────────────────────────────────────────────
# Page: Dashboard Home
# ──────────────────────────────────────────────────────────

def page_dashboard_home() -> None:
    """Render the dashboard home page with KPI cards and world map."""
    st.title("🌍 CarbonSNN Dashboard")
    st.caption("Satellite-based deforestation monitoring powered by Spiking Neural Networks")

    projects = api_get("/projects") or []
    alerts = api_get("/alerts") or []

    # ── KPI cards ─────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active Projects", len([p for p in projects if p.get("is_active")]))
    with col2:
        total_alerts = len(alerts)
        unack = len([a for a in alerts if not a.get("is_acknowledged")])
        st.metric("Total Alerts", total_alerts, delta=f"{unack} unacknowledged", delta_color="inverse")
    with col3:
        total_area = sum(a.get("area_ha", 0) for a in alerts)
        st.metric("Deforested Area", f"{total_area:.1f} ha")
    with col4:
        # Approximate CO2 equivalent
        co2_eq = total_area * 200 * 1.26 * 3.667
        st.metric("CO₂ Equiv. (est.)", f"{co2_eq:,.0f} Mg CO₂e")

    st.divider()

    # ── World map ─────────────────────────────────────────
    st.subheader("Project Locations")
    m = folium.Map(location=[0, 0], zoom_start=2, tiles="CartoDB positron")

    severity_colors = {"low": "green", "medium": "orange", "high": "red"}

    for project in projects:
        lat = (project.get("bbox_south", 0) + project.get("bbox_north", 0)) / 2
        lon = (project.get("bbox_west", 0) + project.get("bbox_east", 0)) / 2
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(
                f"<b>{project['name']}</b><br>{project['country']}", max_width=200
            ),
            icon=folium.Icon(color="blue", icon="tree-deciduous", prefix="glyphicon"),
        ).add_to(m)

    for alert in alerts[:50]:  # Limit to 50 most recent
        lat = alert.get("centroid_lat", 0)
        lon = alert.get("centroid_lon", 0)
        severity = alert.get("severity", "low")
        folium.CircleMarker(
            location=[lat, lon],
            radius=8 if severity == "high" else 5,
            color=severity_colors.get(severity, "orange"),
            fill=True,
            fill_opacity=0.8,
            popup=f"Alert: {alert['area_ha']:.1f} ha ({severity})",
        ).add_to(m)

    st_folium(m, width=None, height=450)

    # ── Recent alerts summary ─────────────────────────────
    st.subheader("Recent Alerts (last 30 days)")
    if alerts:
        df_data = [
            {
                "Date": a.get("detected_date", "")[:10],
                "Project": a.get("project_id", "")[:8] + "…",
                "Area (ha)": a.get("area_ha", 0),
                "Severity": a.get("severity", ""),
                "Acknowledged": "✓" if a.get("is_acknowledged") else "✗",
            }
            for a in alerts[:10]
        ]
        st.dataframe(df_data, use_container_width=True)
    else:
        st.info("No alerts yet. Projects will be scanned automatically each Monday.")


# ──────────────────────────────────────────────────────────
# Page: Project Management
# ──────────────────────────────────────────────────────────

def page_projects() -> None:
    """Render the project management page with CRUD operations."""
    st.title("📁 Project Management")

    tab_list, tab_create = st.tabs(["My Projects", "Create New Project"])

    with tab_list:
        projects = api_get("/projects") or []
        if not projects:
            st.info("No projects found. Create your first project →")
        for project in projects:
            with st.expander(f"**{project['name']}** — {project['country']} ({'Active' if project['is_active'] else 'Inactive'})"):
                col_info, col_actions = st.columns([3, 1])
                with col_info:
                    st.write(f"**ID:** `{project['id']}`")
                    st.write(f"**Description:** {project.get('description') or 'N/A'}")
                    bbox = (
                        f"W:{project['bbox_west']:.3f} S:{project['bbox_south']:.3f} "
                        f"E:{project['bbox_east']:.3f} N:{project['bbox_north']:.3f}"
                    )
                    st.write(f"**Bounding Box:** {bbox}")
                    st.write(f"**Created:** {project['created_at'][:10]}")
                with col_actions:
                    if st.button("🗑 Delete", key=f"del_{project['id']}"):
                        if api_delete(f"/projects/{project['id']}"):
                            st.success("Project deleted")
                            st.rerun()

    with tab_create:
        st.subheader("Register a New Forest Monitoring Area")
        with st.form("create_project_form"):
            name = st.text_input("Project Name", placeholder="Amazon Basin Monitoring")
            country = st.text_input("Country", placeholder="Brazil")
            description = st.text_area("Description (optional)", height=80)
            st.write("**Bounding Box (EPSG:4326)**")
            col_w, col_s, col_e, col_n = st.columns(4)
            west = col_w.number_input("West", value=-65.0, min_value=-180.0, max_value=180.0)
            south = col_s.number_input("South", value=-15.0, min_value=-90.0, max_value=90.0)
            east = col_e.number_input("East", value=-50.0, min_value=-180.0, max_value=180.0)
            north = col_n.number_input("North", value=-5.0, min_value=-90.0, max_value=90.0)

            submitted = st.form_submit_button("Create Project", type="primary")
            if submitted:
                if not name or not country:
                    st.error("Name and country are required")
                elif east <= west:
                    st.error("East must be greater than West")
                elif north <= south:
                    st.error("North must be greater than South")
                else:
                    result = api_post(
                        "/projects",
                        {
                            "name": name,
                            "country": country,
                            "description": description or None,
                            "bbox": {"west": west, "south": south, "east": east, "north": north},
                        },
                    )
                    if result:
                        st.success(f"Project created: {result['id']}")
                        st.rerun()


# ──────────────────────────────────────────────────────────
# Page: Analysis Results
# ──────────────────────────────────────────────────────────

def page_analysis() -> None:
    """Render the analysis results viewer with 4-panel layout."""
    st.title("🔬 Analysis Results")

    projects = api_get("/projects") or []
    if not projects:
        st.warning("Create a project first.")
        return

    project_options = {p["name"]: p["id"] for p in projects}
    selected_name = st.selectbox("Select Project", list(project_options.keys()))
    project_id = project_options[selected_name]

    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        if st.button("▶ Run Analysis", type="primary"):
            result = api_post("/analyses", {"project_id": project_id})
            if result:
                st.success(f"Analysis submitted: `{result['id']}`")

    analyses = api_get(f"/analyses/project/{project_id}") or []

    if not analyses:
        st.info("No analyses yet for this project.")
        return

    # Select analysis to view
    analysis_options = {
        f"{a['created_at'][:16]} — {a['status']}": a["id"] for a in analyses
    }
    selected_analysis_label = st.selectbox("Select Analysis", list(analysis_options.keys()))
    analysis = next((a for a in analyses if a["id"] == analysis_options[selected_analysis_label]), None)

    if not analysis:
        return

    # ── Status badge ──────────────────────────────────────
    status_colors = {"pending": "🟡", "running": "🔵", "completed": "🟢", "failed": "🔴"}
    st.write(f"**Status:** {status_colors.get(analysis['status'], '⚪')} {analysis['status'].title()}")

    if analysis["status"] != "completed":
        st.info("Analysis still processing…")
        if st.button("🔄 Refresh"):
            st.rerun()
        return

    # ── 4-panel layout ────────────────────────────────────
    st.divider()
    st.subheader("Analysis Results")

    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    project_data = next((p for p in projects if p["id"] == project_id), {})
    lat_c = (project_data.get("bbox_south", 0) + project_data.get("bbox_north", 0)) / 2
    lon_c = (project_data.get("bbox_west", 0) + project_data.get("bbox_east", 0)) / 2

    # Panel 1: Project map
    with col1:
        st.write("**Project Area Map**")
        m = folium.Map(location=[lat_c, lon_c], zoom_start=8, tiles="Esri.WorldImagery")
        folium.Rectangle(
            bounds=[
                [project_data.get("bbox_south", 0), project_data.get("bbox_west", 0)],
                [project_data.get("bbox_north", 0), project_data.get("bbox_east", 0)],
            ],
            color="red",
            fill=True,
            fill_opacity=0.1,
        ).add_to(m)
        st_folium(m, width=350, height=300)

    # Panel 2: Carbon stock breakdown
    with col2:
        st.write("**Carbon Stock Summary**")
        metrics_data = {
            "Metric": ["Area (ha)", "Deforested (ha)", "Carbon Stock", "CO₂ Equiv."],
            "Value": [
                f"{analysis['area_ha']:.1f} ha",
                f"{analysis['deforestation_ha']:.1f} ha",
                f"{analysis['carbon_stock_mg']:,.0f} Mg C",
                f"{analysis['co2_equivalent_mg']:,.0f} Mg CO₂e",
            ],
        }
        st.dataframe(metrics_data, use_container_width=True, hide_index=True)

    # Panel 3: NDVI comparison chart (simulated)
    with col3:
        st.write("**Vegetation Index Trend**")
        dates = [
            datetime.now() - timedelta(days=i * 30)
            for i in range(6, 0, -1)
        ]
        import random
        ndvi_vals = [0.7 - i * 0.02 + random.uniform(-0.03, 0.03) for i in range(6)]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[d.strftime("%Y-%m") for d in dates],
            y=ndvi_vals,
            mode="lines+markers",
            name="Mean NDVI",
            line={"color": "#2E8B57"},
        ))
        fig.update_layout(margin={"t": 10, "b": 10}, height=280, xaxis_title="Date", yaxis_title="NDVI")
        st.plotly_chart(fig, use_container_width=True)

    # Panel 4: Land cover pie chart (simulated)
    with col4:
        st.write("**Land Cover Distribution**")
        classes = ["Tropical Forest", "Shrubland", "Grassland", "Cropland", "Bare Land"]
        values = [65, 12, 10, 8, 5]
        colors = ["#1A6B1A", "#D2B48C", "#98FB98", "#FFD700", "#D2691E"]
        fig_pie = px.pie(
            values=values,
            names=classes,
            color_discrete_sequence=colors,
            hole=0.4,
        )
        fig_pie.update_layout(margin={"t": 10, "b": 10}, height=280, showlegend=True)
        st.plotly_chart(fig_pie, use_container_width=True)


# ──────────────────────────────────────────────────────────
# Page: Alerts Timeline
# ──────────────────────────────────────────────────────────

def page_alerts() -> None:
    """Render the deforestation alerts timeline."""
    st.title("🚨 Deforestation Alerts")

    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        show_unacked_only = st.checkbox("Show unacknowledged only", value=False)
    with col_filter2:
        severity_filter = st.multiselect(
            "Filter by severity", ["low", "medium", "high"], default=["low", "medium", "high"]
        )

    params: dict = {}
    if show_unacked_only:
        params["unacknowledged_only"] = "true"

    alerts = api_get("/alerts", params=params) or []
    alerts = [a for a in alerts if a.get("severity") in severity_filter]

    if not alerts:
        st.info("No alerts match the current filters.")
        return

    # ── Summary chart ──────────────────────────────────────
    df_alerts = [
        {
            "date": a.get("detected_date", "")[:10],
            "severity": a.get("severity", ""),
            "area_ha": a.get("area_ha", 0),
        }
        for a in alerts
    ]
    from collections import Counter

    date_counts = Counter(a["date"] for a in df_alerts)
    if date_counts:
        fig_timeline = px.bar(
            x=list(date_counts.keys()),
            y=list(date_counts.values()),
            labels={"x": "Date", "y": "Number of Alerts"},
            title="Alert Timeline",
            color_discrete_sequence=["#E74C3C"],
        )
        st.plotly_chart(fig_timeline, use_container_width=True)

    # ── Alert cards ────────────────────────────────────────
    st.divider()
    for alert in alerts:
        severity = alert.get("severity", "low")
        color = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(severity, "⚪")
        ack_badge = "✓ Ack'd" if alert.get("is_acknowledged") else "Pending"

        with st.expander(
            f"{color} **{alert['area_ha']:.1f} ha** — {alert.get('detected_date', '')[:10]} — {ack_badge}"
        ):
            col_details, col_map = st.columns([2, 1])
            with col_details:
                st.write(f"**Alert ID:** `{alert['id']}`")
                st.write(f"**Project:** `{alert['project_id']}`")
                st.write(f"**Severity:** {severity.title()}")
                st.write(f"**Centroid:** ({alert.get('centroid_lon', 0):.4f}, {alert.get('centroid_lat', 0):.4f})")
                if not alert.get("is_acknowledged"):
                    if st.button("✓ Acknowledge", key=f"ack_{alert['id']}"):
                        r = requests.post(
                            f"{API_PREFIX}/alerts/{alert['id']}/acknowledge",
                            headers=get_headers(),
                            timeout=10,
                        )
                        if r.status_code == 200:
                            st.success("Alert acknowledged")
                            st.rerun()
            with col_map:
                mini_map = folium.Map(
                    location=[alert.get("centroid_lat", 0), alert.get("centroid_lon", 0)],
                    zoom_start=10,
                    tiles="CartoDB positron",
                )
                folium.CircleMarker(
                    location=[alert.get("centroid_lat", 0), alert.get("centroid_lon", 0)],
                    radius=10,
                    color="red",
                    fill=True,
                ).add_to(mini_map)
                st_folium(mini_map, width=200, height=150, key=f"map_{alert['id']}")


# ──────────────────────────────────────────────────────────
# Page: API Key Management
# ──────────────────────────────────────────────────────────

def page_api_keys() -> None:
    """Render the API key management page."""
    st.title("🔑 API Key Management")

    # ── Set working API key ────────────────────────────────
    st.subheader("Active API Key")
    current_key = st.session_state.get("api_key", "")
    new_key = st.text_input(
        "API Key (X-API-Key)",
        value=current_key,
        type="password",
        help="Enter your CarbonSNN API key to authenticate dashboard requests.",
    )
    if new_key != current_key:
        st.session_state["api_key"] = new_key
        st.success("API key updated")

    st.divider()

    # ── Key creation form ──────────────────────────────────
    st.subheader("Create New API Key")
    st.info(
        "API key creation requires a superuser account. "
        "Contact your administrator or use the /api/v1/users endpoint directly."
    )
    with st.form("create_key_form"):
        key_name = st.text_input("Key Name", placeholder="Production Dashboard")
        if st.form_submit_button("Generate Key", type="primary"):
            result = api_post("/api-keys", {"name": key_name})
            if result and "raw_key" in result:
                st.success("API key created!")
                st.code(result["raw_key"], language=None)
                st.warning("⚠️ Copy this key now — it will not be shown again.")

    st.divider()

    # ── Connection status ──────────────────────────────────
    st.subheader("API Connection Status")
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            st.success(f"✅ API connected — version {data.get('version', '?')}")
        else:
            st.error(f"API returned status {resp.status_code}")
    except Exception:
        st.error("❌ Cannot reach API server")


# ──────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────

def main() -> None:
    """Entry point for the Streamlit dashboard."""
    st.set_page_config(
        page_title="CarbonSNN",
        page_icon="🌳",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Session state initialisation
    if "api_key" not in st.session_state:
        st.session_state["api_key"] = os.getenv("CARBONSNN_API_KEY", "")

    # ── Sidebar navigation ────────────────────────────────
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/oak-tree.png", width=60)
        st.title("CarbonSNN")
        st.caption("v0.1.0 — Forest MRV Platform")
        st.divider()

        page = st.radio(
            "Navigation",
            options=[
                "🏠 Dashboard",
                "📁 Projects",
                "🔬 Analysis",
                "🚨 Alerts",
                "🔑 API Keys",
            ],
            label_visibility="collapsed",
        )

        st.divider()
        api_key_display = st.session_state.get("api_key", "")
        if api_key_display:
            st.caption(f"🔐 Key: `{api_key_display[:8]}…`")
        else:
            st.warning("No API key set — go to API Keys page")

    # ── Route to page ──────────────────────────────────────
    if page == "🏠 Dashboard":
        page_dashboard_home()
    elif page == "📁 Projects":
        page_projects()
    elif page == "🔬 Analysis":
        page_analysis()
    elif page == "🚨 Alerts":
        page_alerts()
    elif page == "🔑 API Keys":
        page_api_keys()


if __name__ == "__main__":
    main()
