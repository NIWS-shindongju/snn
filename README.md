# TraceCheck

**EUDR 공급망 실사 사전점검 및 증빙 관리 SaaS**

> 수입·물류 기업의 EUDR(EU 산림전용방지 규정) 의무 이행을 위해  
> 공급업체 필지의 위성 기반 산림전용 리스크를 자동 스크리닝하고  
> 규제 당국 제출용 증빙 패키지를 즉시 생성합니다.

---

## 이 제품이 해결하는 문제

2025년부터 시행되는 EU Deforestation Regulation(EUDR)은 커피·팜유·코코아·대두·목재·고무·소 등 7대 원자재를 EU로 수출·수입하는 기업에게 **공급망 내 모든 필지가 2020년 12월 31일 이후 산림전용에 관여되지 않았음을 입증**할 의무를 부과합니다.

기존 방법의 문제:
- GIS 전문가 없이는 필지 좌표를 위성 영상과 직접 비교하기 어려움
- 공급업체 수백 개의 필지를 수동으로 점검하면 수주~수개월 소요
- 규제 당국이 요구하는 형식의 증빙 문서를 빠르게 만들 수 없음

TraceCheck의 해결:
- CSV/GeoJSON 파일 업로드 → **수분 내 필지별 리스크 등급(LOW/REVIEW/HIGH) 자동 산출**
- Copernicus Sentinel-2 위성 영상(무료 공개데이터) 자동 활용
- 규제 제출용 **증빙 패키지(PDF + JSON + CSV) 즉시 생성**

---

## 대상 고객

| 고객군 | 주요 니즈 |
|--------|----------|
| 커피·코코아·팜유 수입업체 | 공급업체 필지 일괄 사전점검 |
| 중견 공급망 관리 기업 | ESG 실사 자동화, 감사 대응 |
| ESG/구매팀 | 고위험 공급업체 조기 식별 |
| 인증·컨설팅 회사 | 다수 고객사 일괄 증빙 처리 |

---

## 제품 워크플로우

```
1. 로그인
       ↓
2. 프로젝트 생성  (원자재 종류, 원산지 국가, EUDR 기준일 설정)
       ↓
3. 필지 업로드   (CSV 또는 GeoJSON — 공급업체명 + GPS 좌표)
       ↓
4. 좌표 검증     (포맷 오류, 범위 이탈, 중복 자동 탐지)
       ↓
5. 리스크 분석   (Sentinel-2 위성 영상 기반 dNDVI/dNBR 변화탐지)
       ↓
6. 결과 검토     (필지별 LOW / REVIEW / HIGH 등급 + 근거 수치)
       ↓
7. 증빙 내보내기 (PDF 보고서 + JSON 데이터 패키지 + CSV 요약)
       ↓
8. 이력 감사     (모든 작업 로그 — 누가 언제 어떤 결과를 얻었는지)
```

---

## 핵심 API (MVP)

```
POST   /api/auth/register                      회원가입
POST   /api/auth/login                         로그인 (JWT)

POST   /api/projects                           프로젝트 생성
GET    /api/projects                           프로젝트 목록
GET    /api/projects/{id}                      프로젝트 상세

POST   /api/projects/{id}/plots/upload         필지 CSV/GeoJSON 업로드
POST   /api/projects/{id}/plots/validate       좌표 유효성 검사 (저장 전 미리보기)
GET    /api/projects/{id}/plots                필지 목록

POST   /api/projects/{id}/assess               리스크 분석 시작 (비동기)
GET    /api/projects/{id}/jobs                 분석 작업 이력
GET    /api/jobs/{job_id}                      작업 상태 조회
GET    /api/jobs/{job_id}/results              필지별 결과
GET    /api/jobs/{job_id}/results/summary      리스크 요약 집계

POST   /api/jobs/{job_id}/export               증빙 내보내기 (format: pdf/json/csv)
GET    /api/exports/{export_id}/download       파일 다운로드
GET    /api/projects/{id}/history              프로젝트 감사 이력
```

---

## 리스크 등급 기준

| 등급 | 조건 | 대응 권고 |
|------|------|----------|
| 🟢 **LOW** | dNDVI < 0.10 AND 변화면적 < 0.3 ha | 증빙 패키지로 통과 처리 가능 |
| 🟡 **REVIEW** | dNDVI ≥ 0.10 OR 변화면적 ≥ 0.3 ha OR 구름 > 50% | 전문가 추가 검토 필요 |
| 🔴 **HIGH** | dNDVI ≥ 0.15 AND 변화면적 ≥ 1.0 ha | 현장 실사 또는 공급업체 교체 검토 |

**EUDR 기준일**: 2020년 12월 31일 (기본값, 프로젝트별 변경 가능)  
**위성 데이터**: Copernicus Sentinel-2 L2A (ESA 무료 공개, 10m 해상도)

---

## 기술 구조

```
TraceCheck (EUDR SaaS 레이어)
├── tracecheck/
│   ├── api/           FastAPI REST API
│   │   └── routes/    projects · plots · assess · export · history
│   ├── core/          업무 로직
│   │   ├── change_detector.py    dNDVI/dNBR 변화탐지 (NumPy 룰 기반)
│   │   ├── risk_scorer.py        LOW/REVIEW/HIGH 등급 산출
│   │   ├── geo_validator.py      좌표 검증
│   │   ├── sentinel_fetcher.py   Sentinel-2 데이터 취득
│   │   └── report_generator.py   PDF/JSON/CSV 생성
│   ├── db/            SQLAlchemy ORM + Alembic 마이그레이션
│   └── pipeline/      비동기 분석 파이프라인
│
SpikeEO (내부 엔진 레이어 — 현재 룰 기반, 향후 SNN 선택 옵션)
└── spikeeo/
    ├── io/            GeoTIFF 입출력, 식생지수, 클라우드 마스크
    └── tasks/         change_detection (핵심 재사용)
                       [classification/segmentation/detection/anomaly → 후순위]

Frontend
└── frontend/app.py    Streamlit 6-페이지 대시보드
```

---

## 데이터 모델

```
users ──< projects ──< plots
                  ──< job_runs ──< plot_assessments
                             ──< evidence_exports
```

| 테이블 | 역할 |
|--------|------|
| `users` | 조직 계정 |
| `projects` | 원자재·원산지·기준일 단위 실사 묶음 |
| `plots` | 공급업체 필지 좌표 (GeoJSON) |
| `job_runs` | 분석 작업 실행 단위 |
| `plot_assessments` | 필지별 리스크 결과 |
| `evidence_exports` | 생성된 증빙 파일 메타데이터 |

---

## 시작하기

```bash
# 1. 의존성 설치
pip install -e ".[dev]"

# 2. DB 초기화
alembic upgrade head

# 3. 데모 데이터 시딩
python scripts/seed_demo.py

# 4. 서비스 시작 (PM2)
pm2 start ecosystem.config.cjs

# 5. 접속
#   API 문서:   http://localhost:8000/docs
#   대시보드:   http://localhost:8501
#   데모 계정:  demo@tracecheck.io / TraceCheck2024!
```

### 빠른 API 테스트

```bash
# JSON 로그인
curl -X POST http://localhost:8000/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@tracecheck.io","password":"TraceCheck2024!"}'

# 프로젝트 목록
TOKEN=<위에서 받은 access_token>
curl http://localhost:8000/api/projects/ -H "Authorization: Bearer $TOKEN"
```

---

## ⚠️ 법적 고지 (Legal Disclaimer)

**[한국어]**  
본 TraceCheck 서비스는 EU 산림전용방지 규정(EUDR, Regulation (EU) 2023/1115) 대응을 위한 **사전점검 및 증빙 워크플로우 지원 도구**입니다.

- 본 서비스의 모든 출력물(리스크 등급, 보고서, 수치)은 Copernicus Sentinel-2 위성 영상의 자동 분석 결과이며, **법적 구속력 있는 컴플라이언스 판정이 아닙니다.**
- 최종 EUDR 의무 이행 책임은 **고객사(운영자)에게 있습니다.**
- 구름, 계절 변동, 데이터 공백으로 인한 **위양성·위음성**이 발생할 수 있으며, HIGH 및 REVIEW 등급 필지는 전문가 검토 및 현장 검증을 병행해야 합니다.
- 본 서비스는 법률 자문을 제공하지 않습니다.

**[English]**  
TraceCheck is a **pre-screening and evidence workflow support tool** for EU Deforestation Regulation (EUDR, Regulation (EU) 2023/1115) due diligence.

- All outputs (risk grades, reports, metrics) are results of automated satellite image analysis and do **NOT constitute legally binding compliance determinations.**
- **Final responsibility for EUDR compliance obligations remains with the operator (customer).**
- False positives and negatives may occur due to cloud cover, seasonal variation, or data gaps. HIGH and REVIEW plots must be subject to expert review and field verification where appropriate.
- This service does not provide legal advice.

---

## Repo Audit 표 (Keep / Remove / Later)

| 경로 | 판정 | 이유 |
|------|------|------|
| `tracecheck/` (전체) | ✅ **KEEP** | EUDR SaaS 핵심 — API, DB, 파이프라인, 보고서 |
| `tracecheck/core/change_detector.py` | ✅ **KEEP** | 순수 NumPy 변화탐지, 의존성 없음 |
| `tracecheck/core/sentinel_fetcher.py` | ✅ **KEEP** | Sentinel-2 취득 (mock + real) |
| `tracecheck/core/geo_validator.py` | ✅ **KEEP** | CSV/GeoJSON 필지 검증 |
| `tracecheck/core/risk_scorer.py` | ✅ **KEEP** | LOW/REVIEW/HIGH 등급 |
| `tracecheck/core/report_generator.py` | ✅ **KEEP** | PDF/JSON/CSV 증빙 생성 |
| `tracecheck/db/models.py` | ✅ **KEEP** | v2 SaaS 스키마 (plots, job_runs 등) |
| `tracecheck/pipeline/eudr_pipeline.py` | ✅ **KEEP** | 비동기 분석 오케스트레이터 |
| `frontend/app.py` | ✅ **KEEP** | Streamlit 대시보드 |
| `scripts/seed_demo.py` | ✅ **KEEP** | 데모 시딩 |
| `migrations/` | ✅ **KEEP** | Alembic 마이그레이션 이력 |
| `spikeeo/io/` | 🔵 **KEEP (참조용)** | vegetation.py, cloud_mask.py — tracecheck/core에서 재구현 |
| `spikeeo/tasks/change_detection.py` | 🔵 **KEEP (참조용)** | 핵심 룰 로직 참조 소스 |
| `spikeeo/core/snn_backbone.py` | 🟡 **LATER** | torch/SNN — MVP에서 불필요, 향후 정확도 개선 시 |
| `spikeeo/core/hybrid_router.py` | 🟡 **LATER** | SNN 라우팅 — torch 의존성 제거 후 |
| `spikeeo/core/converter.py` | 🟡 **LATER** | ANN→SNN 변환 — torch 필요 |
| `spikeeo/core/cnn_fallback.py` | 🟡 **LATER** | CNN 폴백 — torch 필요 |
| `spikeeo/benchmark/cnn_vs_snn.py` | ❌ **REMOVE** | MVP에서 불필요, 연구용 벤치마크 |
| `spikeeo/benchmark/cost_calculator.py` | ❌ **REMOVE** | MVP에서 불필요 |
| `spikeeo/tasks/anomaly.py` | ❌ **REMOVE** | 범용 이상탐지 — EUDR 업무와 무관 |
| `spikeeo/tasks/classification.py` | ❌ **REMOVE** | 범용 분류기 — EUDR 업무와 무관 |
| `spikeeo/tasks/detection.py` | ❌ **REMOVE** | 객체탐지 — EUDR 업무와 무관 |
| `spikeeo/tasks/segmentation.py` | ❌ **REMOVE** | 세그멘테이션 — EUDR 업무와 무관 |
| `spikeeo/engine.py` | 🟡 **LATER** | 범용 엔진 진입점 — SNN 통합 시 재활성화 |
| `spikeeo/api/` | ❌ **REMOVE** | 범용 추론 API — tracecheck/api로 대체됨 |
| `spikeeo/db/` | ❌ **REMOVE** | 범용 DB — tracecheck/db로 대체됨 |
| `examples/`, `results/`, `pretrained/` | ❌ **REMOVE** | 빈 또는 연구용 디렉토리 |

> ✅ KEEP: MVP에 즉시 필요 | 🔵 KEEP(참조): 코드 보존, 미사용 | 🟡 LATER: SNN 통합 시 | ❌ REMOVE: 범용 엔진 잔재

---

## 샘플 데이터

샘플 CSV 파일: [`examples/sample_plots.csv`](examples/sample_plots.csv)

```
plot_ref,supplier_name,commodity,country,latitude,longitude
COL-001,Finca La Esperanza,coffee,CO,2.1234,-76.5432
COL-002,Cooperativa del Sur,coffee,CO,1.8621,-76.4089
IDN-001,PT Sawit Makmur,palm_oil,ID,-2.3456,113.4567
...
```

> 대시보드 → 필지 업로드 → "샘플 CSV 다운로드" 버튼으로도 받을 수 있습니다.

---

## 데모 시나리오

```
1. demo@tracecheck.io / TraceCheck2024! 로 로그인
2. 프로젝트 목록에서 "Colombia Coffee Q1-2024" 선택
3. 필지 업로드 → examples/sample_plots.csv 업로드
4. 분석 실행 → "🚀 분석 시작" 클릭
5. 결과 보기 → LOW/REVIEW/HIGH 분포 차트 확인
6. 증빙 내보내기 → JSON + CSV 다운로드
7. 감사 이력 → 모든 작업 로그 확인
```

---

## 개발 상태

- **버전**: 0.4.0-Demo-Stable (5분 데모 완성)
- **브랜치**: `main`
- **GitHub**: https://github.com/NIWS-shindongju/snn
- **라이선스**: MIT
- **마지막 업데이트**: 2026-04-06

### v0.4.0 주요 변경사항 (현재)
- **DEMO 모드 결정론적 분석 엔진**: GeoTIFF 없이 UUID 해시 기반으로 LOW/REVIEW/HIGH 혼합 결과 보장
  - Copernicus 자격증명 없으면 자동으로 mock 모드 진입
  - 분석 시간: 필지 7개 기준 1초 이내
  - 결과 분포: LOW 2개(29%) / REVIEW 4개(57%) / HIGH 1개(14%)
- **`plot_ref` 컬럼 인식 추가**: geo_validator의 CSV 컬럼 자동탐지에 `plot_ref` 포함
- **E2E 8단계 검증 완료**: 로그인 → 프로젝트 → CSV업로드 → 좌표검증 → 분석 → 결과(혼합) → 증빙(PDF/JSON/CSV) → 감사이력

### v0.3.0 주요 변경사항
- **JSON 로그인 엔드포인트 추가**: `POST /api/auth/token` (Streamlit 친화적)
- **API 경로 통일**: `/assess` 별칭, `/export` 별칭 추가
- **Streamlit 대시보드 전면 개선**:
  - 7번째 페이지 "감사 이력" 추가
  - 분석 중 자동 폴링 (3초 간격)
  - 샘플 CSV 인라인 다운로드
  - 검증 미리보기 / 업로드 분리 버튼
  - 필지 삭제 버튼
- **샘플 CSV**: `examples/sample_plots.csv` (15개 필지, 4개국, 4개 원자재)
- **E2E 12단계 전체 검증 완료**: JSON 로그인 → 프로젝트 → 필지 → 분석 → 결과 → JSON/CSV 내보내기 → 감사 이력

### v0.2.0 주요 변경사항
- **DB 스키마 v2**: `parcels→plots`, `analysis_jobs→job_runs`, `parcel_results→plot_assessments`, `reports→evidence_exports` + `audit_logs` 신규
- **CRUD 전면 재작성**: 새 모델명에 맞게 crud.py 재작성
- **감사 로그**: 모든 주요 액션(프로젝트 생성, 업로드, 분석 시작, 보고서 생성) 자동 기록
- **API 호환성**: v1 경로(`/parcels`, `/parcel_ref`) → v2 경로(`/plots`, `/plot_ref`) + 구버전 alias 유지
