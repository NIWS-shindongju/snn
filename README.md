# TraceCheck — EUDR 공급망 사전점검 SaaS

> **EUDR(EU Deforestation Regulation) 대응 위성 기반 산림전용 리스크 사전스크리닝 도구**  
> 기존 SpikeEO/CarbonSNN 자산(Sentinel-2 변화탐지, 규칙 기반 분석) 재사용, 별도 SNN 학습 불필요

---

## 🎯 제품 정의 (One-liner)

> "CSV/GeoJSON으로 공급업체 필지를 업로드하면 Sentinel-2 변화탐지로 EUDR 산림전용 리스크를 LOW/REVIEW/HIGH로 자동 분류하고, 증빙 보고서(PDF/JSON/CSV)를 즉시 다운로드할 수 있는 SaaS"

---

## ✅ 현재 완성된 기능

| 기능 | 상태 | 설명 |
|------|------|------|
| JWT 인증 | ✅ | 회원가입/로그인/토큰 갱신 |
| 프로젝트 관리 | ✅ | EUDR 규제 원자재 기준 프로젝트 생성/조회/삭제 |
| 필지 업로드 | ✅ | CSV/GeoJSON 파일 업로드 + 좌표 검증 |
| 변화탐지 분석 | ✅ | 비동기 Sentinel-2 기반 dNDVI/dNBR 계산 |
| 리스크 등급화 | ✅ | LOW / REVIEW / HIGH 자동 분류 |
| 증빙 보고서 | ✅ | PDF, JSON, CSV 생성 및 다운로드 |
| Streamlit 대시보드 | ✅ | 로그인, 프로젝트, 분석, 결과, 보고서 UI |
| 데모 데이터 | ✅ | 콜롬비아 커피 5필지 + 인도네시아 팜유 2필지 |
| Alembic 마이그레이션 | ✅ | DB 스키마 버전 관리 |
| Docker Compose | ✅ | API + 대시보드 컨테이너 구성 |

---

## 🚧 미구현 / 후순위 항목

- Copernicus 실데이터 연동 (현재 Mock 모드 동작)
- 지도 시각화 (Folium/Leaflet 필지 위치 표시)
- 이메일 알림 (분석 완료 시)
- 팀 다중 계정 (Organization 기능)
- SNN 하이브리드 탐지 (전력 절감 옵션)
- CI/CD 파이프라인

---

## 🌐 접속 URL (로컬 개발)

| 서비스 | URL | 비고 |
|--------|-----|------|
| FastAPI REST API | http://localhost:8000 | |
| Swagger 문서 | http://localhost:8000/docs | API 전체 스펙 |
| Streamlit 대시보드 | http://localhost:8501 | |

### 데모 계정
```
이메일:    demo@tracecheck.io
비밀번호:  TraceCheck2024!
```

---

## 📁 프로젝트 구조

```
webapp/
├── tracecheck/               # 핵심 패키지
│   ├── api/
│   │   ├── main.py          # FastAPI 앱 엔트리포인트
│   │   ├── auth.py          # JWT 인증 헬퍼
│   │   ├── schemas.py       # Pydantic 스키마
│   │   └── routes/
│   │       ├── auth.py      # /api/auth/*
│   │       ├── projects.py  # /api/projects/*
│   │       ├── parcels.py   # /api/projects/{id}/parcels/*
│   │       ├── analysis.py  # /api/projects/{id}/analyze, /api/jobs/*
│   │       └── reports.py   # /api/jobs/{id}/reports, /api/reports/*
│   ├── core/
│   │   ├── change_detector.py   # dNDVI/dNBR 규칙기반 탐지기
│   │   ├── risk_scorer.py       # LOW/REVIEW/HIGH 등급 산출
│   │   ├── sentinel_fetcher.py  # Sentinel-2 다운로드 (Mock+Real)
│   │   ├── geo_validator.py     # CSV/GeoJSON 좌표 검증
│   │   └── report_generator.py  # PDF/JSON/CSV 증빙 생성
│   ├── db/
│   │   ├── models.py   # SQLAlchemy ORM 모델
│   │   ├── crud.py     # 비동기 CRUD 함수
│   │   └── session.py  # DB 엔진 + 세션 팩토리
│   ├── pipeline/
│   │   └── eudr_pipeline.py  # 전체 분석 오케스트레이터
│   └── config.py             # Pydantic Settings
├── frontend/
│   └── app.py           # Streamlit 멀티페이지 대시보드
├── migrations/           # Alembic 마이그레이션
├── scripts/
│   ├── seed_demo.py      # 데모 데이터 시딩
│   └── download_sentinel2.py
├── spikeeo/              # 원본 SpikeEO 엔진 (참조용)
├── ecosystem.config.cjs  # PM2 서비스 설정
├── docker-compose.yml    # Docker 배포 구성
├── Dockerfile            # 컨테이너 빌드 파일
├── pyproject.toml        # 의존성 + CLI
└── alembic.ini           # Alembic 설정
```

---

## 🔑 핵심 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/auth/register` | 회원가입 |
| POST | `/api/auth/login` | 로그인 (JWT 발급) |
| GET  | `/api/auth/me` | 현재 사용자 정보 |
| GET  | `/api/projects` | 프로젝트 목록 |
| POST | `/api/projects` | 프로젝트 생성 |
| POST | `/api/projects/{id}/parcels/upload` | 필지 CSV/GeoJSON 업로드 |
| GET  | `/api/projects/{id}/parcels` | 필지 목록 |
| POST | `/api/projects/{id}/analyze` | 분석 시작 (비동기 202) |
| GET  | `/api/projects/{id}/jobs` | 분석 이력 |
| GET  | `/api/jobs/{id}` | 작업 상태 조회 |
| GET  | `/api/jobs/{id}/results` | 필지별 결과 |
| GET  | `/api/jobs/{id}/results/summary` | 리스크 요약 집계 |
| POST | `/api/jobs/{id}/reports` | 보고서 생성 (format: pdf/json/csv) |
| GET  | `/api/reports/{id}/download` | 보고서 다운로드 |

---

## 🗄️ 데이터 모델

```
User ──< Project ──< Parcel
                ──< AnalysisJob ──< ParcelResult
                                ──< Report
```

| 테이블 | 주요 필드 |
|--------|----------|
| users | id, email, hashed_password, org_name |
| projects | id, owner_id, name, commodity, origin_country, cutoff_date |
| parcels | id, project_id, geojson, supplier_name, parcel_ref, area_ha |
| analysis_jobs | id, project_id, status, total_parcels, processed_parcels |
| parcel_results | id, job_id, parcel_id, risk_level, delta_ndvi, changed_area_ha |
| reports | id, job_id, format, file_path, file_size_bytes |

---

## 🚀 로컬 실행 가이드

### 1. 의존성 설치
```bash
pip install -e ".[api,dashboard]"
```

### 2. DB 마이그레이션
```bash
alembic upgrade head
```

### 3. 데모 데이터 시딩
```bash
python scripts/seed_demo.py
```

### 4. 서비스 시작 (PM2)
```bash
pm2 start ecosystem.config.cjs
pm2 logs --nostream
```

### 5. Docker Compose
```bash
docker-compose up -d
```

---

## 🔬 리스크 등급 기준

| 등급 | 기준 |
|------|------|
| 🟢 LOW | dNDVI < 0.10 AND 변화면적 < 0.3ha |
| 🟡 REVIEW | dNDVI ≥ 0.10 OR 변화면적 ≥ 0.3ha OR 구름 > 50% |
| 🔴 HIGH | dNDVI ≥ 0.15 AND 변화면적 ≥ 1.0ha |

EUDR 기준일: **2020년 12월 31일** (기본값)

---

## ⚠️ 법적 고지 (Legal Disclaimer)

본 TraceCheck 시스템이 생성하는 모든 보고서 및 리스크 등급은 Copernicus Sentinel-2 위성 영상 데이터를 기반으로 한 **자동화된 사전 선별(pre-screening) 지원 도구**입니다.

- 본 도구의 출력물은 EU 산림전용방지 규정(EUDR Regulation (EU) 2023/1115) 또는 그 밖의 법규에 따른 **공식 컴플라이언스 판정을 구성하지 않습니다**.
- 최종 공급망 실사 결론, 법적 판단, 인증 결정은 반드시 **자격을 갖춘 전문가의 인간 검토**를 통해 이루어져야 합니다.
- 위성 데이터의 특성상 구름, 계절적 변동, 데이터 가용성에 따라 **위양성(false positive) 및 위음성(false negative)**이 발생할 수 있습니다.

---

## 📅 개발 상태

- **플랫폼**: FastAPI + SQLite (aiosqlite) + Streamlit
- **분석 엔진**: Sentinel-2 dNDVI/dNBR 규칙 기반 (SpikeEO 자산 재사용)
- **버전**: 0.1.0-MVP
- **업데이트**: 2026-04-06
- **GitHub**: https://github.com/NIWS-shindongju/snn

---

## 📋 12주 로드맵 진행 현황

| 주차 | 항목 | 상태 |
|------|------|------|
| W1-2 | 기반 인프라, DB, 인증 | ✅ 완료 |
| W3-4 | 필지 업로드, 좌표 검증 | ✅ 완료 |
| W5-6 | Sentinel-2 연동, 변화탐지 | ✅ 완료 |
| W7-8 | 비동기 분석, 리스크 등급화 | ✅ 완료 |
| W9-10 | 증빙 보고서, 대시보드 UI | ✅ 완료 |
| W11 | 데모 데이터, Docker | ✅ 완료 |
| W12 | 베타 고객 접촉, 피드백 수렴 | 🔄 진행 중 |
