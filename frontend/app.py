"""TraceCheck Streamlit Dashboard — EUDR Supply Chain Pre-screening.

Multi-page app:
  - Login / Register
  - Projects list
  - Project detail (parcels + analysis jobs)
  - Upload parcels (CSV / GeoJSON)
  - Run analysis + live status polling
  - Results view + risk map
  - Download reports (PDF / JSON / CSV)
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


# ── Session state helpers ─────────────────────────────────────────────────────

def is_logged_in() -> bool:
    return bool(st.session_state.get("token"))


def logout() -> None:
    for key in ["token", "user", "current_project"]:
        st.session_state.pop(key, None)


# ── Auth pages ────────────────────────────────────────────────────────────────

def page_login() -> None:
    st.title("🌿 TraceCheck")
    st.subheader("EUDR Deforestation Risk Screening")
    st.markdown("---")

    tab_login, tab_register = st.tabs(["로그인", "회원가입"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("이메일", placeholder="your@company.com")
            password = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button("로그인", use_container_width=True, type="primary")

        if submitted:
            if not email or not password:
                st.error("이메일과 비밀번호를 입력하세요.")
                return
            resp = requests.post(
                f"{API_URL}/api/auth/login",
                data={"username": email, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                st.session_state["token"] = resp.json()["access_token"]
                me = api_get("/api/auth/me").json()
                st.session_state["user"] = me
                st.success(f"환영합니다, {me.get('org_name') or me['email']}!")
                st.rerun()
            else:
                st.error("로그인 실패: 이메일 또는 비밀번호를 확인하세요.")

        st.markdown("---")
        st.caption("**Demo 계정**: demo@tracecheck.io / TraceCheck2024!")

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
                json={"email": r_email, "org_name": r_org, "password": r_pw},
                timeout=10,
            )
            if resp.status_code == 201:
                st.success("가입 완료! 이제 로그인하세요.")
            else:
                st.error(f"가입 실패: {resp.json().get('detail', resp.text)}")


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar() -> str:
    """Render sidebar nav, return selected page name."""
    user = st.session_state.get("user", {})

    st.sidebar.title("🌿 TraceCheck")
    st.sidebar.caption(f"**{user.get('org_name') or user.get('email', '')}**")
    st.sidebar.markdown("---")

    pages = {
        "📋 프로젝트 목록": "projects",
        "📍 필지 업로드": "upload",
        "🔬 분석 실행": "analysis",
        "📊 결과 보기": "results",
        "📥 보고서 다운로드": "reports",
    }

    page = st.sidebar.radio("메뉴", list(pages.keys()), label_visibility="hidden")

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 로그아웃"):
        logout()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "⚠️ **Disclaimer**: 본 도구는 사전 선별 지원만 제공하며 "
        "EUDR 또는 관련 법규에 따른 최종 컴플라이언스 결정을 구성하지 않습니다."
    )

    return pages[page]


# ── Projects page ─────────────────────────────────────────────────────────────

def page_projects() -> None:
    st.header("📋 EUDR 컴플라이언스 프로젝트")

    # Create new project
    with st.expander("➕ 새 프로젝트 생성"):
        with st.form("new_project"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("프로젝트명 *", placeholder="Colombia Coffee Q1-2024")
                commodity = st.selectbox(
                    "규제 원자재 *",
                    ["coffee", "cocoa", "palm_oil", "soy", "cattle", "wood", "rubber"],
                    format_func=lambda x: {
                        "coffee": "☕ 커피",
                        "cocoa": "🍫 코코아",
                        "palm_oil": "🌴 팜유",
                        "soy": "🌱 대두",
                        "cattle": "🐄 소",
                        "wood": "🪵 목재",
                        "rubber": "⚫ 고무",
                    }.get(x, x),
                )
            with col2:
                origin_country = st.text_input("원산지 국가코드", placeholder="CO (ISO 3166-1 alpha-2)")
                cutoff_date = st.date_input("EUDR 기준일", value=datetime(2020, 12, 31))
            description = st.text_area("설명 (선택)")
            submitted = st.form_submit_button("생성", type="primary")

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
                st.error(f"생성 실패: {resp.json().get('detail', resp.text)}")

    # List projects
    resp = api_get("/api/projects/")
    if resp.status_code != 200:
        st.error("프로젝트 목록 로딩 실패")
        return

    projects = resp.json()
    if not projects:
        st.info("프로젝트가 없습니다. 위에서 새 프로젝트를 생성하세요.")
        return

    st.markdown(f"**총 {len(projects)}개 프로젝트**")

    for proj in projects:
        commodity_icons = {
            "coffee": "☕", "cocoa": "🍫", "palm_oil": "🌴",
            "soy": "🌱", "cattle": "🐄", "wood": "🪵", "rubber": "⚫",
        }
        icon = commodity_icons.get(proj["commodity"], "📦")

        with st.container():
            col1, col2, col3 = st.columns([4, 2, 1])
            with col1:
                st.markdown(f"### {icon} {proj['name']}")
                st.caption(
                    f"원산지: **{proj.get('origin_country', 'N/A')}** | "
                    f"기준일: **{proj['cutoff_date']}** | "
                    f"생성: {proj['created_at'][:10]}"
                )
                if proj.get("description"):
                    st.caption(proj["description"])
            with col2:
                st.metric("상태", proj["status"].upper())
            with col3:
                if st.button("선택 →", key=f"sel_{proj['id']}"):
                    st.session_state["current_project"] = proj
                    st.success(f"'{proj['name']}' 선택됨")
                    st.rerun()
            st.divider()


# ── Upload page ───────────────────────────────────────────────────────────────

def page_upload() -> None:
    st.header("📍 필지 업로드")

    proj = st.session_state.get("current_project")
    if not proj:
        st.warning("먼저 '프로젝트 목록'에서 프로젝트를 선택하세요.")
        return

    st.info(f"📂 현재 프로젝트: **{proj['name']}**")

    st.markdown("""
### 지원 파일 형식
- **CSV**: `parcel_ref`, `supplier_name`, `latitude`, `longitude` (또는 WKT geometry 컬럼)
- **GeoJSON**: FeatureCollection 또는 단일 Feature

### CSV 예시
```
parcel_ref,supplier_name,latitude,longitude
COL-001,Finca La Esperanza,2.1,-76.5
COL-002,Cooperativa del Sur,1.86,-76.41
```
""")

    uploaded_file = st.file_uploader(
        "파일 선택 (CSV 또는 GeoJSON)",
        type=["csv", "json", "geojson"],
    )

    if uploaded_file:
        st.success(f"파일 선택됨: `{uploaded_file.name}` ({uploaded_file.size:,} bytes)")

        # Preview
        if uploaded_file.name.endswith(".csv"):
            try:
                df = pd.read_csv(uploaded_file)
                uploaded_file.seek(0)
                st.dataframe(df.head(10), use_container_width=True)
                st.caption(f"총 {len(df)}행")
            except Exception as e:
                st.warning(f"미리보기 실패: {e}")
                uploaded_file.seek(0)

        if st.button("📤 업로드 & 검증", type="primary", use_container_width=True):
            with st.spinner("업로드 중..."):
                resp = api_post(
                    f"/api/projects/{proj['id']}/parcels/upload",
                    files={"file": (uploaded_file.name, uploaded_file.read(), "application/octet-stream")},
                )
            if resp.status_code in (200, 201):
                data = resp.json()
                # v2: created_count/skipped_count (v1: valid_count/invalid_count)
                created = data.get('created_count', data.get('valid_count', 0))
                skipped = data.get('skipped_count', data.get('invalid_count', 0))
                st.success(
                    f"✅ 업로드 완료: **{created}개** 필지 저장, "
                    f"**{skipped}개** 검증 실패"
                )
                if data.get("errors"):
                    with st.expander(f"⚠️ {len(data['errors'])}개 오류"):
                        for err in data["errors"][:20]:
                            st.text(err)
            else:
                try:
                    detail = resp.json().get('detail', resp.text)
                except Exception:
                    detail = resp.text
                st.error(f"업로드 실패 ({resp.status_code}): {detail}")

    st.markdown("---")
    # Show existing plots
    st.subheader("현재 등록된 필지")
    # v2: /plots endpoint (v1: /parcels)
    resp = api_get(f"/api/projects/{proj['id']}/plots")
    if resp.status_code == 200:
        plots = resp.json()
        if plots:
            rows = []
            for p in plots:
                geom = json.loads(p.get("geojson", "{}"))
                coords = geom.get("geometry", {}).get("coordinates", [])
                if geom.get("geometry", {}).get("type") == "Point":
                    lat, lon = coords[1], coords[0]
                else:
                    lat, lon = "poly", "poly"
                # v2: plot_ref (v1: parcel_ref)
                rows.append({
                    "Ref": p.get("plot_ref") or p.get("parcel_ref", "-"),
                    "공급업체": p.get("supplier_name", "-"),
                    "유형": p.get("geometry_type", "-"),
                    "위도": lat,
                    "경도": lon,
                    "면적(ha)": p.get("area_ha", "-"),
                    "국가": p.get("country", "-"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.caption(f"총 **{len(plots)}개** 필지 등록")
        else:
            st.info("등록된 필지가 없습니다.")
    else:
        st.error("필지 목록 로딩 실패")


# ── Analysis page ─────────────────────────────────────────────────────────────

def page_analysis() -> None:
    st.header("🔬 변화탐지 분석")

    proj = st.session_state.get("current_project")
    if not proj:
        st.warning("먼저 '프로젝트 목록'에서 프로젝트를 선택하세요.")
        return

    st.info(f"📂 현재 프로젝트: **{proj['name']}**")

    # Plot count
    count_resp = api_get(f"/api/projects/{proj['id']}/plots")
    parcel_count = len(count_resp.json()) if count_resp.status_code == 200 else "?"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("등록 필지", parcel_count)
    with col2:
        st.metric("기준일", proj["cutoff_date"])
    with col3:
        st.metric("원자재", proj["commodity"].upper())

    st.markdown("---")

    if st.button("🚀 분석 시작", type="primary", use_container_width=True, disabled=(parcel_count == 0)):
        with st.spinner("분석 작업 제출 중..."):
            resp = api_post(f"/api/projects/{proj['id']}/analyze")
        if resp.status_code == 202:
            job = resp.json()
            job_id = job["id"]
            st.success(f"분석 작업 생성: `{job_id[:12]}...`")
            st.session_state["latest_job_id"] = job_id
        else:
            st.error(f"분석 시작 실패: {resp.json().get('detail', resp.text)}")

    # Job list
    st.subheader("분석 이력")
    jobs_resp = api_get(f"/api/projects/{proj['id']}/jobs")
    if jobs_resp.status_code == 200:
        jobs = jobs_resp.json()
        if not jobs:
            st.info("아직 실행된 분석이 없습니다.")
        else:
            for job in jobs:
                status = job["status"]
                status_icon = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}.get(status, "❓")
                progress = 0
                if job.get("total_parcels", 0) > 0:
                    progress = job.get("processed_parcels", 0) / job["total_parcels"]

                with st.container():
                    c1, c2, c3, c4 = st.columns([3, 1, 2, 1])
                    with c1:
                        st.markdown(f"**{status_icon} Job `{job['id'][:12]}...`**")
                        st.caption(f"생성: {job['created_at'][:19]}")
                    with c2:
                        st.metric("상태", status.upper())
                    with c3:
                        # v2: total_plots/processed_plots (v1: total_parcels/processed_parcels)
                        total_p = job.get('total_plots', job.get('total_parcels', 0))
                        processed_p = job.get('processed_plots', job.get('processed_parcels', 0))
                        if status == "running":
                            st.progress(
                                processed_p / total_p if total_p > 0 else 0,
                                text=f"{processed_p}/{total_p}"
                            )
                        else:
                            st.metric("처리 완료", f"{processed_p}/{total_p}")
                    with c4:
                        if st.button("결과 보기", key=f"view_{job['id']}"):
                            st.session_state["view_job_id"] = job["id"]

                    if job.get("error_message"):
                        st.caption(f"⚠️ {job['error_message']}")
                    st.divider()

    # Auto-refresh for running jobs
    if st.button("🔄 새로고침"):
        st.rerun()


# ── Results page ──────────────────────────────────────────────────────────────

def page_results() -> None:
    st.header("📊 분석 결과")

    proj = st.session_state.get("current_project")
    if not proj:
        st.warning("먼저 '프로젝트 목록'에서 프로젝트를 선택하세요.")
        return

    job_id = st.session_state.get("view_job_id")

    # Job selector
    jobs_resp = api_get(f"/api/projects/{proj['id']}/jobs")
    if jobs_resp.status_code != 200 or not jobs_resp.json():
        st.info("분석 결과가 없습니다. 먼저 분석을 실행하세요.")
        return

    jobs = [j for j in jobs_resp.json() if j["status"] in ("done", "failed")]
    if not jobs:
        st.info("완료된 분석이 없습니다.")
        return

    job_options = {f"Job {j['id'][:8]} ({j['created_at'][:10]}) — {j['status']}": j["id"] for j in jobs}
    selected_label = st.selectbox("분석 작업 선택", list(job_options.keys()))
    selected_job_id = job_options[selected_label]

    # Results summary
    summary_resp = api_get(f"/api/jobs/{selected_job_id}/results/summary")
    if summary_resp.status_code == 200:
        summary = summary_resp.json()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🟢 LOW (저위험)", summary.get("low", 0))
        with col2:
            st.metric("🟡 REVIEW (검토)", summary.get("review", 0))
        with col3:
            st.metric("🔴 HIGH (고위험)", summary.get("high", 0))
        with col4:
            st.metric("📍 전체 필지", summary.get("total", 0))

        # Risk donut chart
        if summary.get("total", 0) > 0:
            try:
                import plotly.express as px
                risk_data = {
                    "리스크 등급": ["LOW", "REVIEW", "HIGH"],
                    "필지 수": [summary.get("low", 0), summary.get("review", 0), summary.get("high", 0)],
                    "색상": ["#28a745", "#ffc107", "#dc3545"],
                }
                fig = px.pie(
                    risk_data, values="필지 수", names="리스크 등급",
                    color="리스크 등급",
                    color_discrete_map={"LOW": "#28a745", "REVIEW": "#ffc107", "HIGH": "#dc3545"},
                    title="필지별 리스크 분포",
                    hole=0.4,
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                pass

    # Detailed results table
    st.subheader("필지별 상세 결과")
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
                    # v2: plot_ref/plot_id (v1: parcel_ref/parcel_id)
                    "필지 Ref": r.get("plot_ref") or r.get("parcel_ref") or r.get("plot_id", r.get("parcel_id", ""))[:8],
                    "공급업체": r.get("supplier_name", "-"),
                    "dNDVI": f"{r.get('delta_ndvi', 0):.3f}" if r.get("delta_ndvi") else "-",
                    "변화면적(ha)": f"{r.get('changed_area_ha', 0):.2f}" if r.get("changed_area_ha") else "-",
                    "구름(%)" : f"{r.get('cloud_fraction', 0)*100:.0f}%" if r.get("cloud_fraction") else "-",
                    "신뢰도": f"{r.get('confidence', 0)*100:.0f}%" if r.get("confidence") else "-",
                    "사유": r.get("flag_reason", "-"),
                    "Before 촬영일": r.get("before_scene_date", "-"),
                    "After 촬영일": r.get("after_scene_date", "-"),
                })

            df = pd.DataFrame(rows)

            # Filter by risk level
            filter_risk = st.multiselect(
                "리스크 등급 필터",
                ["🔴 HIGH", "🟡 REVIEW", "🟢 LOW"],
                default=["🔴 HIGH", "🟡 REVIEW", "🟢 LOW"],
            )
            if filter_risk:
                mapping = {"🔴 HIGH": "🔴 HIGH", "🟡 REVIEW": "🟡 REVIEW", "🟢 LOW": "🟢 LOW"}
                df = df[df["위험도"].isin([mapping[f] for f in filter_risk])]

            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "위험도": st.column_config.TextColumn(width="small"),
                },
            )

            # Export as CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 결과 CSV 다운로드",
                data=csv,
                file_name=f"tracecheck_results_{selected_job_id[:8]}.csv",
                mime="text/csv",
            )
        else:
            st.info("결과가 없습니다.")
    else:
        st.error("결과 로딩 실패")


# ── Reports page ──────────────────────────────────────────────────────────────

def page_reports() -> None:
    st.header("📥 증빙 보고서 다운로드")

    proj = st.session_state.get("current_project")
    if not proj:
        st.warning("먼저 '프로젝트 목록'에서 프로젝트를 선택하세요.")
        return

    # Job selector
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

    st.markdown("---")
    st.markdown("### 보고서 생성")
    
    col1, col2, col3 = st.columns(3)

    def _generate_and_download(fmt: str, mime: str, btn_key: str) -> None:
        with st.spinner(f"{fmt.upper()} 생성 중..."):
            resp = api_post(
                f"/api/jobs/{selected_job_id}/reports",
                json={"format": fmt},
            )
        if resp.status_code in (200, 201):
            rpt_data = resp.json()
            dl_resp = api_get(f"/api/reports/{rpt_data['id']}/download")
            if dl_resp.status_code == 200:
                st.download_button(
                    f"📥 {fmt.upper()} 다운로드",
                    data=dl_resp.content,
                    file_name=f"tracecheck_eudr_{selected_job_id[:8]}.{fmt}",
                    mime=mime,
                    key=f"dl_{btn_key}",
                )
            else:
                st.error(f"다운로드 실패")
        else:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            st.error(f"{fmt.upper()} 생성 실패: {detail}")

    with col1:
        st.markdown("#### 📄 PDF 보고서")
        st.caption("전체 증빙 패키지 (Sentinel-2 분석 결과 + 리스크 요약 + 법적 고지)")
        if st.button("PDF 생성 & 다운로드", key="btn_pdf", use_container_width=True):
            _generate_and_download("pdf", "application/pdf", "pdf")

    with col2:
        st.markdown("#### 📋 JSON 증빙")
        st.caption("기계 가독 증빙 패키지 (API 연동 / 시스템 통합용)")
        if st.button("JSON 생성 & 다운로드", key="btn_json", use_container_width=True):
            _generate_and_download("json", "application/json", "json")

    with col3:
        st.markdown("#### 📊 CSV 요약")
        st.caption("Excel 친화적 필지별 리스크 요약표")
        if st.button("CSV 생성 & 다운로드", key="btn_csv", use_container_width=True):
            _generate_and_download("csv", "text/csv", "csv")

    st.markdown("---")
    # List existing reports
    st.subheader("생성된 보고서 목록")
    reports_resp = api_get(f"/api/jobs/{selected_job_id}/reports")
    if reports_resp.status_code == 200:
        reports = reports_resp.json()
        if reports:
            for rpt in reports:
                c1, c2, c3 = st.columns([2, 2, 2])
                with c1:
                    fmt = rpt["format"].upper()
                    fmt_icon = {"PDF": "📄", "JSON": "📋", "CSV": "📊"}.get(fmt, "📁")
                    st.markdown(f"**{fmt_icon} {fmt}** — `{rpt['id'][:8]}`")
                with c2:
                    st.caption(f"생성일: {rpt['generated_at'][:19]}")
                with c3:
                    if rpt.get("file_size_bytes"):
                        st.caption(f"크기: {rpt['file_size_bytes']:,} bytes")
                st.divider()
        else:
            st.info("생성된 보고서가 없습니다. 위에서 생성하세요.")

    # Disclaimer
    st.markdown("---")
    st.warning("""
**⚠️ 법적 고지 / Legal Disclaimer**

본 TraceCheck 시스템이 생성하는 모든 보고서 및 리스크 등급은 **Copernicus Sentinel-2 위성 영상 데이터를 기반으로 한 자동화된 사전 선별(pre-screening) 지원 도구**입니다.

- 본 도구의 출력물은 EU 산림전용방지 규정(EUDR Regulation (EU) 2023/1115) 또는 그 밖의 법규에 따른 **공식 컴플라이언스 판정을 구성하지 않습니다**.
- 최종 공급망 실사 결론, 법적 판단, 인증 결정은 반드시 **자격을 갖춘 전문가의 인간 검토**를 통해 이루어져야 합니다.
- 위성 데이터의 특성상 구름, 계절적 변동, 데이터 가용성에 따라 **위양성(false positive) 및 위음성(false negative)** 이 발생할 수 있습니다.
- 본 도구는 인간 검토를 지원하기 위한 보조 수단이며, 이를 대체하지 않습니다.
""")


# ── Main app ──────────────────────────────────────────────────────────────────

def main() -> None:
    if not is_logged_in():
        page_login()
        return

    page = render_sidebar()

    # Show current project in header
    proj = st.session_state.get("current_project")
    if proj and page != "projects":
        st.markdown(
            f"<small>📂 선택된 프로젝트: <b>{proj['name']}</b> "
            f"({proj['commodity'].upper()}, {proj.get('origin_country', 'N/A')})</small>",
            unsafe_allow_html=True,
        )

    if page == "projects":
        page_projects()
    elif page == "upload":
        page_upload()
    elif page == "analysis":
        page_analysis()
    elif page == "results":
        page_results()
    elif page == "reports":
        page_reports()


if __name__ == "__main__":
    main()
