"""TraceCheck Streamlit Dashboard — EUDR Supply Chain Pre-screening.

Pages:
  1. Login / Register
  2. Projects list (create, select, delete)
  3. Plot Upload (CSV / GeoJSON + sample download)
  4. Run Analysis + live auto-polling
  5. Assessment Results (table, chart, CSV export)
  6. Evidence Export (PDF / JSON / CSV generation & download)
  7. Audit History (per-project log)
"""

from __future__ import annotations

import io
import json
import os
import time
from datetime import datetime
from typing import Any

import pandas as pd
import requests
import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────
API_URL = os.getenv("TRACECHECK_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="TraceCheck – EUDR Risk Screening",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Colour scheme ─────────────────────────────────────────────────────────────
RISK_COLOURS = {"low": "🟢", "review": "🟡", "high": "🔴"}
RISK_BG = {"low": "#d4edda", "review": "#fff3cd", "high": "#f8d7da"}

SAMPLE_CSV = """plot_ref,supplier_name,commodity,country,latitude,longitude
COL-001,Finca La Esperanza,coffee,CO,2.1234,-76.5432
COL-002,Cooperativa del Sur,coffee,CO,1.8621,-76.4089
COL-003,Hacienda Buena Vista,coffee,CO,2.4521,-76.2341
IDN-001,PT Sawit Makmur,palm_oil,ID,-2.3456,113.4567
IDN-002,Kebun Rakyat Kalimantan,palm_oil,ID,-1.9876,114.1234
GHA-001,Kwame Cocoa Farm,cocoa,GH,6.5432,-1.2345
BRA-001,Fazenda Amazonia,soy,BR,-8.4567,-53.2345
"""


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _headers() -> dict:
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{API_URL}{path}", headers=_headers(), timeout=30, **kwargs)


def api_post(path: str, **kwargs) -> requests.Response:
    return requests.post(f"{API_URL}{path}", headers=_headers(), timeout=30, **kwargs)


def api_delete(path: str) -> requests.Response:
    return requests.delete(f"{API_URL}{path}", headers=_headers(), timeout=30)


# ── Session helpers ───────────────────────────────────────────────────────────

def is_logged_in() -> bool:
    return bool(st.session_state.get("token"))


def logout() -> None:
    for key in ["token", "user", "current_project", "view_job_id", "latest_job_id"]:
        st.session_state.pop(key, None)


def current_project() -> dict | None:
    return st.session_state.get("current_project")


# ── Auth pages ────────────────────────────────────────────────────────────────

def page_login() -> None:
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.markdown(
            "<h1 style='text-align:center'>🌿 TraceCheck</h1>"
            "<p style='text-align:center;color:#555'>EUDR 공급망 산림전용 리스크 사전점검 플랫폼</p>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        tab_login, tab_register = st.tabs(["🔑 로그인", "✏️ 회원가입"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("이메일", placeholder="your@company.com")
                password = st.text_input("비밀번호", type="password")
                submitted = st.form_submit_button("로그인", use_container_width=True, type="primary")

            if submitted:
                if not email or not password:
                    st.error("이메일과 비밀번호를 입력하세요.")
                    return
                # JSON endpoint (more friendly than form-data)
                resp = requests.post(
                    f"{API_URL}/api/auth/token",
                    json={"email": email, "password": password},
                    timeout=10,
                )
                if resp.status_code == 200:
                    st.session_state["token"] = resp.json()["access_token"]
                    me = api_get("/api/auth/me").json()
                    st.session_state["user"] = me
                    st.success(f"환영합니다, {me.get('org_name') or me['email']}!")
                    st.rerun()
                else:
                    try:
                        msg = resp.json().get("detail", resp.text)
                    except Exception:
                        msg = resp.text
                    st.error(f"로그인 실패: {msg}")

            st.markdown("---")
            st.info("**Demo 계정**: `demo@tracecheck.io` / `TraceCheck2024!`")

        with tab_register:
            with st.form("register_form"):
                r_email = st.text_input("이메일", key="reg_email")
                r_org = st.text_input("조직명 (선택)", key="reg_org")
                r_pw = st.text_input("비밀번호", type="password", key="reg_pw")
                r_pw2 = st.text_input("비밀번호 확인", type="password", key="reg_pw2")
                submitted_r = st.form_submit_button("가입하기", use_container_width=True)

            if submitted_r:
                if r_pw != r_pw2:
                    st.error("비밀번호가 일치하지 않습니다.")
                    return
                resp = requests.post(
                    f"{API_URL}/api/auth/register",
                    json={"email": r_email, "org_name": r_org or None, "password": r_pw},
                    timeout=10,
                )
                if resp.status_code == 201:
                    st.success("가입 완료! 위 탭에서 로그인하세요.")
                else:
                    try:
                        detail = resp.json().get("detail", resp.text)
                    except Exception:
                        detail = resp.text
                    st.error(f"가입 실패: {detail}")


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar() -> str:
    """Render sidebar nav, return selected page name."""
    user = st.session_state.get("user", {})

    st.sidebar.title("🌿 TraceCheck")
    st.sidebar.caption(f"**{user.get('org_name') or user.get('email', '')}**")

    proj = current_project()
    if proj:
        commodity_icons = {
            "coffee": "☕", "cocoa": "🍫", "palm_oil": "🌴",
            "soy": "🌱", "cattle": "🐄", "wood": "🪵", "rubber": "⚫",
        }
        icon = commodity_icons.get(proj.get("commodity", ""), "📦")
        st.sidebar.success(f"📂 {icon} **{proj['name']}**")

    st.sidebar.markdown("---")

    pages = {
        "📋 프로젝트 목록": "projects",
        "📍 필지 업로드": "upload",
        "🔬 분석 실행": "analysis",
        "📊 결과 보기": "results",
        "📥 증빙 내보내기": "reports",
        "🕐 감사 이력": "history",
    }

    page = st.sidebar.radio("메뉴", list(pages.keys()), label_visibility="hidden")

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 로그아웃", use_container_width=True):
        logout()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "⚠️ **법적 고지**: 본 도구는 EUDR 사전 선별 지원만 제공하며, "
        "법적 구속력 있는 컴플라이언스 판정을 구성하지 않습니다. "
        "최종 책임은 운영자에게 있습니다."
    )

    return pages[page]


# ── Projects page ─────────────────────────────────────────────────────────────

def page_projects() -> None:
    st.header("📋 EUDR 컴플라이언스 프로젝트")

    # ── Create new project ──
    with st.expander("➕ 새 프로젝트 생성", expanded=False):
        with st.form("new_project"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("프로젝트명 *", placeholder="Colombia Coffee Q1-2025")
                commodity = st.selectbox(
                    "규제 원자재 *",
                    ["coffee", "cocoa", "palm_oil", "soy", "cattle", "wood", "rubber"],
                    format_func=lambda x: {
                        "coffee": "☕ 커피", "cocoa": "🍫 코코아", "palm_oil": "🌴 팜유",
                        "soy": "🌱 대두", "cattle": "🐄 소", "wood": "🪵 목재", "rubber": "⚫ 고무",
                    }.get(x, x),
                )
            with col2:
                origin_country = st.text_input("원산지 국가코드", placeholder="CO (ISO 3166-1 alpha-2)")
                cutoff_date = st.date_input("EUDR 기준일", value=datetime(2020, 12, 31))
            description = st.text_area("설명 (선택)", placeholder="프로젝트 메모")
            submitted = st.form_submit_button("✅ 생성", type="primary")

        if submitted and name:
            resp = api_post("/api/projects/", json={
                "name": name,
                "commodity": commodity,
                "origin_country": origin_country or None,
                "cutoff_date": str(cutoff_date),
                "description": description or None,
            })
            if resp.status_code == 201:
                st.success(f"프로젝트 '{name}' 생성 완료!")
                st.rerun()
            else:
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text
                st.error(f"생성 실패: {detail}")

    # ── List projects ──
    resp = api_get("/api/projects/")
    if resp.status_code != 200:
        st.error("프로젝트 목록 로딩 실패")
        return

    projects = resp.json()
    if not projects:
        st.info("프로젝트가 없습니다. 위에서 새 프로젝트를 생성하세요.")
        return

    st.markdown(f"**총 {len(projects)}개 프로젝트**")
    st.markdown("---")

    commodity_icons = {
        "coffee": "☕", "cocoa": "🍫", "palm_oil": "🌴",
        "soy": "🌱", "cattle": "🐄", "wood": "🪵", "rubber": "⚫",
    }

    for proj in projects:
        icon = commodity_icons.get(proj["commodity"], "📦")
        is_selected = (current_project() or {}).get("id") == proj["id"]
        border_style = "border: 2px solid #28a745; border-radius: 8px; padding: 12px;" if is_selected else "border: 1px solid #dee2e6; border-radius: 8px; padding: 12px;"

        with st.container():
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
            with col1:
                st.markdown(
                    f"**{icon} {proj['name']}**"
                    f"{'  ✅ *선택됨*' if is_selected else ''}"
                )
                st.caption(
                    f"원산지: **{proj.get('origin_country') or 'N/A'}**  |  "
                    f"기준일: **{proj['cutoff_date']}**  |  "
                    f"필지: **{proj.get('plot_count', 0)}개**  |  "
                    f"생성: {proj['created_at'][:10]}"
                )
                if proj.get("description"):
                    st.caption(f"📝 {proj['description']}")
            with col2:
                commodity_kr = {
                    "coffee": "커피", "cocoa": "코코아", "palm_oil": "팜유",
                    "soy": "대두", "cattle": "소", "wood": "목재", "rubber": "고무",
                }.get(proj["commodity"], proj["commodity"])
                st.metric("원자재", commodity_kr)
            with col3:
                if st.button("📂 선택", key=f"sel_{proj['id']}", use_container_width=True, type="primary" if not is_selected else "secondary"):
                    st.session_state["current_project"] = proj
                    st.session_state.pop("view_job_id", None)
                    st.rerun()
            with col4:
                if st.button("🗑️ 삭제", key=f"del_{proj['id']}", use_container_width=True):
                    del_resp = api_delete(f"/api/projects/{proj['id']}")
                    if del_resp.status_code == 204:
                        if (current_project() or {}).get("id") == proj["id"]:
                            st.session_state.pop("current_project", None)
                        st.success(f"'{proj['name']}' 삭제됨")
                        st.rerun()
                    else:
                        st.error("삭제 실패")
            st.divider()


# ── Upload page ───────────────────────────────────────────────────────────────

def page_upload() -> None:
    st.header("📍 필지 업로드")

    proj = current_project()
    if not proj:
        st.warning("먼저 '프로젝트 목록'에서 프로젝트를 선택하세요.")
        return

    st.info(f"📂 현재 프로젝트: **{proj['name']}** ({proj['commodity'].upper()}, {proj.get('origin_country') or 'N/A'})")

    # Sample CSV download
    with st.expander("📎 지원 형식 및 샘플 파일"):
        st.markdown("""
**CSV 컬럼 (필수: `latitude`, `longitude` 또는 WKT geometry)**

| 컬럼 | 필수 | 설명 |
|------|------|------|
| `plot_ref` | ✅ | 필지 고유 참조 코드 |
| `supplier_name` | ✅ | 공급업체명 |
| `latitude` | ✅* | 위도 (소수점 표기) |
| `longitude` | ✅* | 경도 (소수점 표기) |
| `commodity` | 선택 | 원자재 종류 |
| `country` | 선택 | 국가 코드 (ISO 2자리) |

> *polygon GeoJSON 파일 업로드 시 latitude/longitude 불필요
        """)
        st.download_button(
            "📥 샘플 CSV 다운로드",
            data=SAMPLE_CSV.encode("utf-8"),
            file_name="tracecheck_sample_plots.csv",
            mime="text/csv",
        )

    uploaded_file = st.file_uploader(
        "파일 선택 (CSV 또는 GeoJSON)",
        type=["csv", "json", "geojson"],
        help="최대 10 MB, 최대 5,000 필지",
    )

    if uploaded_file:
        st.success(f"파일 선택됨: `{uploaded_file.name}` ({uploaded_file.size:,} bytes)")

        if uploaded_file.name.endswith(".csv"):
            try:
                df = pd.read_csv(io.StringIO(uploaded_file.read().decode("utf-8")))
                uploaded_file.seek(0)
                st.dataframe(df.head(10), use_container_width=True)
                st.caption(f"미리보기: 총 {len(df)}행")
            except Exception as e:
                st.warning(f"미리보기 실패: {e}")
                uploaded_file.seek(0)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 검증만 (미리보기)", use_container_width=True):
                uploaded_file.seek(0)
                with st.spinner("검증 중..."):
                    resp = api_post(
                        f"/api/projects/{proj['id']}/plots/validate",
                        files={"file": (uploaded_file.name, uploaded_file.read(), "application/octet-stream")},
                    )
                if resp.status_code == 200:
                    v = resp.json()
                    st.info(f"✅ 유효: **{v['valid_count']}개** | ❌ 오류: **{v['invalid_count']}개**")
                    if v.get("preview"):
                        st.dataframe(pd.DataFrame(v["preview"]), use_container_width=True)
                    if v.get("errors"):
                        with st.expander(f"⚠️ {len(v['errors'])}개 오류 상세"):
                            for err in v["errors"][:20]:
                                st.text(err)
                else:
                    st.error(f"검증 실패 ({resp.status_code})")

        with col2:
            if st.button("📤 업로드 & 저장", type="primary", use_container_width=True):
                uploaded_file.seek(0)
                with st.spinner("업로드 중..."):
                    resp = api_post(
                        f"/api/projects/{proj['id']}/plots/upload",
                        files={"file": (uploaded_file.name, uploaded_file.read(), "application/octet-stream")},
                    )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    created = data.get("created_count", data.get("valid_count", 0))
                    skipped = data.get("skipped_count", data.get("invalid_count", 0))
                    st.success(f"✅ 업로드 완료: **{created}개** 필지 저장 | **{skipped}개** 검증 실패")
                    if data.get("errors"):
                        with st.expander(f"⚠️ {len(data['errors'])}개 오류"):
                            for err in data["errors"][:20]:
                                st.text(err)
                    # refresh project info
                    updated = api_get(f"/api/projects/{proj['id']}").json()
                    st.session_state["current_project"] = updated
                else:
                    try:
                        detail = resp.json().get("detail", resp.text)
                    except Exception:
                        detail = resp.text
                    st.error(f"업로드 실패 ({resp.status_code}): {detail}")

    # ── Existing plots ──
    st.markdown("---")
    st.subheader("현재 등록된 필지")

    resp = api_get(f"/api/projects/{proj['id']}/plots")
    if resp.status_code == 200:
        plots = resp.json()
        if plots:
            rows = []
            for p in plots:
                try:
                    geom = json.loads(p.get("geojson", "{}"))
                    coords = geom.get("geometry", {}).get("coordinates", [])
                    if geom.get("geometry", {}).get("type") == "Point":
                        lat_val = round(coords[1], 4)
                        lon_val = round(coords[0], 4)
                    else:
                        lat_val, lon_val = "polygon", "polygon"
                except Exception:
                    lat_val, lon_val = "-", "-"

                rows.append({
                    "Ref": p.get("plot_ref") or "-",
                    "공급업체": p.get("supplier_name") or "-",
                    "유형": p.get("geometry_type", "point"),
                    "위도": lat_val,
                    "경도": lon_val,
                    "면적(ha)": round(p["area_ha"], 2) if p.get("area_ha") else "-",
                    "국가": p.get("country") or "-",
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.caption(f"총 **{len(plots)}개** 필지 등록")

            # Allow deleting all plots
            if st.button("🗑️ 모든 필지 삭제", type="secondary"):
                for p in plots:
                    api_delete(f"/api/plots/{p['id']}")
                st.success("모든 필지가 삭제되었습니다.")
                st.rerun()
        else:
            st.info("등록된 필지가 없습니다. 위에서 CSV 파일을 업로드하세요.")
    else:
        st.error("필지 목록 로딩 실패")


# ── Analysis page ─────────────────────────────────────────────────────────────

def page_analysis() -> None:
    st.header("🔬 변화탐지 리스크 분석")

    proj = current_project()
    if not proj:
        st.warning("먼저 '프로젝트 목록'에서 프로젝트를 선택하세요.")
        return

    st.info(f"📂 현재 프로젝트: **{proj['name']}**")

    # ── Metrics ──
    plots_resp = api_get(f"/api/projects/{proj['id']}/plots")
    plot_count = len(plots_resp.json()) if plots_resp.status_code == 200 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("등록 필지", plot_count)
    col2.metric("EUDR 기준일", proj["cutoff_date"])
    col3.metric("원자재", proj["commodity"].upper())

    st.markdown("---")

    # ── Trigger analysis ──
    btn_col, info_col = st.columns([2, 3])
    with btn_col:
        if st.button(
            "🚀 분석 시작",
            type="primary",
            use_container_width=True,
            disabled=(plot_count == 0),
        ):
            with st.spinner("분석 작업 제출 중..."):
                resp = api_post(f"/api/projects/{proj['id']}/analyze")
            if resp.status_code == 202:
                job = resp.json()
                st.session_state["latest_job_id"] = job["id"]
                st.session_state["polling_job_id"] = job["id"]
                st.success(f"분석 작업 생성: `{job['id'][:12]}...`")
                time.sleep(1)
                st.rerun()
            else:
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text
                st.error(f"분석 시작 실패: {detail}")

    with info_col:
        if plot_count == 0:
            st.warning("⚠️ 필지가 없습니다. 먼저 '필지 업로드' 메뉴에서 CSV 파일을 업로드하세요.")
        else:
            st.info(
                "💡 분석 방식: Sentinel-2 dNDVI/dNBR 기반 변화탐지 (DEMO_MODE=true 일 때 결정론적 모의 분석)\n\n"
                "분석 시간: 필지 1개당 약 1~3초"
            )

    # ── Job list with auto-refresh ──
    st.markdown("---")
    st.subheader("분석 이력")

    jobs_resp = api_get(f"/api/projects/{proj['id']}/jobs")
    polling_id = st.session_state.get("polling_job_id")

    if jobs_resp.status_code == 200:
        jobs = jobs_resp.json()
        if not jobs:
            st.info("아직 실행된 분석이 없습니다.")
        else:
            running_jobs = [j for j in jobs if j["status"] in ("pending", "running")]

            for job in jobs:
                jstatus = job["status"]
                status_icon = {
                    "pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌",
                }.get(jstatus, "❓")

                total_p = job.get("total_plots", job.get("total_parcels", 0))
                processed_p = job.get("processed_plots", job.get("processed_parcels", 0))

                with st.container():
                    c1, c2, c3, c4 = st.columns([3, 1, 2, 1])
                    with c1:
                        st.markdown(f"**{status_icon} Job** `{job['id'][:12]}...`")
                        st.caption(f"생성: {job['created_at'][:19]}")
                    with c2:
                        st.metric("상태", jstatus.upper())
                    with c3:
                        if jstatus in ("pending", "running"):
                            pct = (processed_p / total_p) if total_p > 0 else 0
                            st.progress(pct, text=f"{processed_p}/{total_p} 처리 중...")
                        else:
                            st.metric("처리", f"{processed_p}/{total_p}")
                    with c4:
                        if jstatus == "done" and st.button("📊 결과", key=f"view_{job['id']}", use_container_width=True):
                            st.session_state["view_job_id"] = job["id"]
                            st.session_state.pop("polling_job_id", None)

                    if job.get("error_message"):
                        st.caption(f"⚠️ 오류: {job['error_message']}")
                    st.divider()

            # Auto-refresh while jobs are running
            if running_jobs:
                st.info("🔄 분석 실행 중... 3초마다 자동 새로고침")
                time.sleep(3)
                st.rerun()

    col_r, _ = st.columns([1, 4])
    with col_r:
        if st.button("🔄 수동 새로고침"):
            st.rerun()


# ── Results page ──────────────────────────────────────────────────────────────

def page_results() -> None:
    st.header("📊 분석 결과")

    proj = current_project()
    if not proj:
        st.warning("먼저 '프로젝트 목록'에서 프로젝트를 선택하세요.")
        return

    jobs_resp = api_get(f"/api/projects/{proj['id']}/jobs")
    if jobs_resp.status_code != 200 or not jobs_resp.json():
        st.info("분석 결과가 없습니다. 먼저 '분석 실행' 메뉴에서 분석을 시작하세요.")
        return

    jobs_all = jobs_resp.json()
    jobs_done = [j for j in jobs_all if j["status"] in ("done", "failed")]
    if not jobs_done:
        st.info("완료된 분석이 없습니다.")
        # Show running jobs
        running = [j for j in jobs_all if j["status"] in ("pending", "running")]
        if running:
            st.warning(f"⏳ {len(running)}개 작업이 실행 중입니다. '분석 실행' 탭에서 상태를 확인하세요.")
        return

    # Job selector
    job_options = {
        f"Job {j['id'][:8]}… ({j['created_at'][:10]}) — {j['status'].upper()}": j["id"]
        for j in jobs_done
    }
    # Pre-select from session state
    default_ix = 0
    if st.session_state.get("view_job_id"):
        keys = list(job_options.keys())
        vals = list(job_options.values())
        if st.session_state["view_job_id"] in vals:
            default_ix = vals.index(st.session_state["view_job_id"])

    selected_label = st.selectbox("분석 작업 선택", list(job_options.keys()), index=default_ix)
    selected_job_id = job_options[selected_label]

    # ── Summary metrics ──
    summary_resp = api_get(f"/api/jobs/{selected_job_id}/results/summary")
    if summary_resp.status_code == 200:
        summary = summary_resp.json()
        total = summary.get("total", 0)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📍 전체 필지", total)
        col2.metric("🟢 LOW (저위험)", f"{summary.get('low', 0)}  ({summary.get('low_pct', 0):.0f}%)")
        col3.metric("🟡 REVIEW (검토)", f"{summary.get('review', 0)}  ({summary.get('review_pct', 0):.0f}%)")
        col4.metric("🔴 HIGH (고위험)", f"{summary.get('high', 0)}  ({summary.get('high_pct', 0):.0f}%)")

        # Donut chart
        if total > 0:
            try:
                import plotly.express as px
                fig = px.pie(
                    values=[summary.get("low", 0), summary.get("review", 0), summary.get("high", 0)],
                    names=["LOW", "REVIEW", "HIGH"],
                    color_discrete_sequence=["#28a745", "#ffc107", "#dc3545"],
                    title="필지별 리스크 등급 분포",
                    hole=0.45,
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                # Fallback bar chart with st.bar_chart
                st.bar_chart({
                    "LOW": summary.get("low", 0),
                    "REVIEW": summary.get("review", 0),
                    "HIGH": summary.get("high", 0),
                })

    st.markdown("---")

    # ── Detailed results table ──
    st.subheader("필지별 상세 결과")

    filter_risk = st.multiselect(
        "리스크 등급 필터",
        ["🔴 HIGH", "🟡 REVIEW", "🟢 LOW"],
        default=["🔴 HIGH", "🟡 REVIEW", "🟢 LOW"],
    )

    results_resp = api_get(f"/api/jobs/{selected_job_id}/results")
    if results_resp.status_code == 200:
        results = results_resp.json()
        if results:
            rows = []
            for r in results:
                risk = r.get("risk_level", "review")
                icon = RISK_COLOURS.get(risk, "⚪")
                rows.append({
                    "위험도": f"{icon} {risk.upper()}",
                    "필지 Ref": r.get("plot_ref") or r.get("parcel_ref") or r.get("plot_id", "")[:8],
                    "공급업체": r.get("supplier_name") or "-",
                    "dNDVI": f"{r.get('delta_ndvi', 0):.3f}" if r.get("delta_ndvi") is not None else "-",
                    "변화면적(ha)": f"{r.get('changed_area_ha', 0):.2f}" if r.get("changed_area_ha") is not None else "-",
                    "구름(%)": f"{r.get('cloud_fraction', 0)*100:.0f}%" if r.get("cloud_fraction") is not None else "-",
                    "신뢰도": f"{r.get('confidence', 0)*100:.0f}%" if r.get("confidence") is not None else "-",
                    "판정 사유": r.get("flag_reason") or "-",
                    "Before 촬영일": (r.get("before_scene_date") or "-")[:10],
                    "After 촬영일": (r.get("after_scene_date") or "-")[:10],
                })

            df = pd.DataFrame(rows)

            # Apply filter
            _map = {"🔴 HIGH": "🔴 HIGH", "🟡 REVIEW": "🟡 REVIEW", "🟢 LOW": "🟢 LOW"}
            selected_risks = {_map[f] for f in filter_risk}
            if selected_risks:
                df = df[df["위험도"].isin(selected_risks)]

            st.dataframe(
                df,
                use_container_width=True,
                column_config={"위험도": st.column_config.TextColumn(width="small")},
            )

            # CSV export
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 결과 CSV 다운로드 (Excel용)",
                data=csv,
                file_name=f"tracecheck_results_{selected_job_id[:8]}.csv",
                mime="text/csv",
            )
        else:
            st.info("결과가 없습니다.")
    else:
        st.error(f"결과 로딩 실패 ({results_resp.status_code})")

    st.markdown("---")
    st.caption(
        "⚠️ **데이터 출처**: Copernicus Sentinel-2 (DEMO_MODE에서는 결정론적 모의 데이터)  |  "
        "리스크 등급은 법적 판정이 아닙니다."
    )


# ── Reports / Export page ─────────────────────────────────────────────────────

def page_reports() -> None:
    st.header("📥 증빙 패키지 내보내기")

    proj = current_project()
    if not proj:
        st.warning("먼저 '프로젝트 목록'에서 프로젝트를 선택하세요.")
        return

    jobs_resp = api_get(f"/api/projects/{proj['id']}/jobs")
    if jobs_resp.status_code != 200 or not jobs_resp.json():
        st.info("분석 결과가 없습니다.")
        return

    jobs = [j for j in jobs_resp.json() if j["status"] == "done"]
    if not jobs:
        st.info("완료된 분석이 없습니다.")
        return

    job_options = {f"Job {j['id'][:8]} ({j['created_at'][:10]})": j["id"] for j in jobs}
    selected_label = st.selectbox("보고서를 생성할 분석 선택", list(job_options.keys()))
    selected_job_id = job_options[selected_label]

    # ── Summary (quick reference) ──
    summary_resp = api_get(f"/api/jobs/{selected_job_id}/results/summary")
    if summary_resp.status_code == 200:
        s = summary_resp.json()
        col1, col2, col3 = st.columns(3)
        col1.metric("🟢 LOW", s.get("low", 0))
        col2.metric("🟡 REVIEW", s.get("review", 0))
        col3.metric("🔴 HIGH", s.get("high", 0))

    st.markdown("---")
    st.markdown("### 보고서 생성")
    st.caption("보고서를 생성하면 즉시 다운로드 버튼이 나타납니다.")

    col1, col2, col3 = st.columns(3)

    def _gen_download(fmt: str, mime: str, col, key_sfx: str) -> None:
        with col:
            fmt_icons = {"pdf": "📄", "json": "📋", "csv": "📊"}
            fmt_names = {"pdf": "PDF 증빙 보고서", "json": "JSON 증빙 패키지", "csv": "CSV 요약"}
            fmt_descs = {
                "pdf": "규제 당국 제출용 전체 증빙 패키지 (리스크 요약 + 필지 목록 + 법적 고지)",
                "json": "기계 가독 증빙 패키지 (API 연동·시스템 통합·공급망 추적 시스템용)",
                "csv": "Excel 친화적 필지별 리스크 요약표 (공급업체 공유용)",
            }
            st.markdown(f"#### {fmt_icons[fmt]} {fmt_names[fmt]}")
            st.caption(fmt_descs[fmt])

            if st.button(f"{fmt.upper()} 생성 & 다운로드", key=f"btn_{fmt}_{key_sfx}", use_container_width=True, type="primary"):
                with st.spinner(f"{fmt.upper()} 생성 중..."):
                    resp = api_post(
                        f"/api/jobs/{selected_job_id}/reports",
                        json={"format": fmt},
                    )
                if resp.status_code in (200, 201):
                    rpt = resp.json()
                    dl = api_get(f"/api/reports/{rpt['id']}/download")
                    if dl.status_code == 200:
                        st.download_button(
                            f"📥 {fmt.upper()} 다운로드",
                            data=dl.content,
                            file_name=f"tracecheck_eudr_{selected_job_id[:8]}.{fmt}",
                            mime=mime,
                            key=f"dl_{fmt}_{key_sfx}_{int(time.time())}",
                        )
                        st.success(f"✅ {fmt.upper()} 생성 완료 ({rpt.get('file_size_bytes', 0):,} bytes)")
                    else:
                        st.error("다운로드 실패")
                else:
                    try:
                        detail = resp.json().get("detail", resp.text)
                    except Exception:
                        detail = resp.text
                    st.error(f"{fmt.upper()} 생성 실패: {detail}")

    _gen_download("pdf", "application/pdf", col1, "1")
    _gen_download("json", "application/json", col2, "1")
    _gen_download("csv", "text/csv", col3, "1")

    # ── Existing reports ──
    st.markdown("---")
    st.subheader("생성된 보고서 목록")
    rpts_resp = api_get(f"/api/jobs/{selected_job_id}/reports")
    if rpts_resp.status_code == 200:
        rpts = rpts_resp.json()
        if rpts:
            for rpt in rpts:
                c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
                fmt = rpt["format"].upper()
                fmt_icon = {"PDF": "📄", "JSON": "📋", "CSV": "📊"}.get(fmt, "📁")
                with c1:
                    st.markdown(f"**{fmt_icon} {fmt}**")
                with c2:
                    st.caption(f"ID: `{rpt['id'][:8]}`")
                with c3:
                    st.caption(f"생성: {rpt['generated_at'][:19]}")
                with c4:
                    if rpt.get("file_size_bytes"):
                        st.caption(f"{rpt['file_size_bytes']:,} bytes")
                st.divider()
        else:
            st.info("생성된 보고서가 없습니다.")

    # ── Legal disclaimer ──
    st.markdown("---")
    st.warning(
        "**⚠️ 법적 고지 / Legal Disclaimer**\n\n"
        "본 TraceCheck 시스템의 모든 보고서 및 리스크 등급은 Copernicus Sentinel-2 위성 영상의 "
        "**자동화된 사전 선별(pre-screening) 지원 도구**입니다.\n\n"
        "- 본 출력물은 EUDR(Regulation (EU) 2023/1115) 또는 그 밖의 법규에 따른 "
        "**공식 컴플라이언스 판정을 구성하지 않습니다**.\n"
        "- 최종 공급망 실사·법적 판단·인증 결정은 **자격을 갖춘 전문가의 인간 검토**를 통해 이루어져야 합니다.\n"
        "- 구름·계절 변동·데이터 공백으로 인한 **위양성·위음성**이 발생할 수 있습니다.\n"
        "- 최종 EUDR 의무 이행 책임은 **고객사(운영자)**에게 있습니다."
    )


# ── History page ──────────────────────────────────────────────────────────────

def page_history() -> None:
    st.header("🕐 프로젝트 감사 이력")

    proj = current_project()
    if not proj:
        st.warning("먼저 '프로젝트 목록'에서 프로젝트를 선택하세요.")
        return

    st.info(f"📂 현재 프로젝트: **{proj['name']}**")

    resp = api_get(f"/api/projects/{proj['id']}/history")
    if resp.status_code != 200:
        st.error("감사 이력 로딩 실패")
        return

    logs = resp.json()
    if not logs:
        st.info("아직 감사 이력이 없습니다.")
        return

    st.markdown(f"**총 {len(logs)}개 이력** (최근 100개)")
    st.markdown("---")

    action_icons = {
        "project.created": "🆕",
        "plots.upload": "📤",
        "job.started": "🚀",
        "export.created": "📥",
        "job.completed": "✅",
        "job.failed": "❌",
    }

    rows = []
    for log in logs:
        icon = action_icons.get(log["action"], "📋")
        detail_str = ""
        if log.get("detail"):
            try:
                d = log["detail"] if isinstance(log["detail"], dict) else json.loads(log["detail"])
                # Format nicely
                parts = []
                for k, v in d.items():
                    if isinstance(v, str) and len(v) > 36:
                        v = v[:8] + "..."
                    parts.append(f"{k}: {v}")
                detail_str = " | ".join(parts)
            except Exception:
                detail_str = str(log["detail"])[:80]

        rows.append({
            "시각": log["occurred_at"][:19],
            "액션": f"{icon} {log['action']}",
            "상세": detail_str,
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        column_config={
            "시각": st.column_config.TextColumn(width="medium"),
            "액션": st.column_config.TextColumn(width="medium"),
            "상세": st.column_config.TextColumn(width="large"),
        },
    )

    # Export history as CSV
    csv_data = pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 감사 이력 CSV 다운로드",
        data=csv_data,
        file_name=f"tracecheck_history_{proj['id'][:8]}.csv",
        mime="text/csv",
    )

    if st.button("🔄 새로고침"):
        st.rerun()


# ── Main app ──────────────────────────────────────────────────────────────────

def main() -> None:
    if not is_logged_in():
        page_login()
        return

    page = render_sidebar()

    # Project breadcrumb
    proj = current_project()
    if proj and page != "projects":
        commodity_kr = {
            "coffee": "커피", "cocoa": "코코아", "palm_oil": "팜유",
            "soy": "대두", "cattle": "소", "wood": "목재", "rubber": "고무",
        }.get(proj["commodity"], proj["commodity"])
        st.markdown(
            f"<small style='color:#888'>📂 선택된 프로젝트: <b>{proj['name']}</b> — "
            f"{commodity_kr} | {proj.get('origin_country', 'N/A')} | 기준일 {proj['cutoff_date']}</small>",
            unsafe_allow_html=True,
        )
        st.markdown("")

    dispatch = {
        "projects": page_projects,
        "upload": page_upload,
        "analysis": page_analysis,
        "results": page_results,
        "reports": page_reports,
        "history": page_history,
    }
    dispatch.get(page, page_projects)()


if __name__ == "__main__":
    main()
