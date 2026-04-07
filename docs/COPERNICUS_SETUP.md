# Copernicus Sentinel-2 실제 연동 가이드

## 개요
TraceCheck는 Copernicus Data Space Ecosystem의 Sentinel-2 L2A 데이터를 사용합니다.
현재 mock 모드가 기본이며, 실제 위성 데이터를 사용하려면 아래 설정이 필요합니다.

## 1. Copernicus 계정 생성
1. https://dataspace.copernicus.eu/ 접속
2. "Register" 클릭 → 무료 계정 생성
3. 이메일 인증 완료

## 2. API 자격증명 발급
1. https://dataspace.copernicus.eu/profile 접속
2. "API Access" 섹션에서 Client ID/Secret 생성
3. 또는 OAuth2 토큰 발급:
```bash
curl -X POST "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token" \
  -d "grant_type=password" \
  -d "client_id=cdse-public" \
  -d "username=YOUR_EMAIL" \
  -d "password=YOUR_PASSWORD"
```

## 3. 환경변수 설정
```bash
# .env 파일
COPERNICUS_CLIENT_ID=your_client_id
COPERNICUS_CLIENT_SECRET=your_client_secret
# 또는
COPERNICUS_USERNAME=your_email
COPERNICUS_PASSWORD=your_password
```

## 4. 실제 모드 활성화
환경변수가 설정되면 `eudr_pipeline.py`가 자동으로 실제 모드로 전환됩니다.
```python
# tracecheck/config.py
COPERNICUS_CLIENT_ID = os.getenv("COPERNICUS_CLIENT_ID")
# 이 값이 있으면 실제 Sentinel-2 데이터 다운로드
# 없으면 결정론적 mock 모드로 폴백
```

## 5. 데이터 사양
- **위성**: Sentinel-2 L2A (대기 보정 완료)
- **밴드**: B02(Blue), B03(Green), B04(Red), B05-B07(Red Edge), B08(NIR), B11(SWIR1), B12(SWIR2)
- **해상도**: 10m (B02-B04, B08), 20m (B05-B07, B11-B12)
- **분석 기간**: 2020-12-31 기준일 이후 변화 탐지
- **구름 필터**: 자동 (NIR 밴드 기반 구름 피복률 추정)

## 6. API 사용량 제한
- Copernicus Data Space: 무료 계정 기준 월 10,000 API 호출
- Pro 계정: 월 100,000+ 호출 (유료)
- TraceCheck 분석 1건당 약 2-4 API 호출 (before/after 이미지)

## 7. 검증 방법
```bash
# 실제 모드 테스트 (단일 필지)
cd /home/work/.openclaw/workspace/snn
source .venv/bin/activate
python -c "
from tracecheck.core.sentinel_fetcher import SentinelFetcher
fetcher = SentinelFetcher()
print('Mode:', 'REAL' if fetcher.has_credentials() else 'MOCK')
"
```

## 주의사항
- 실제 모드에서는 분석 시간이 크게 증가합니다 (필지당 10-30초 → 1-5분)
- 네트워크 오류 시 자동으로 mock 모드로 폴백
- 구름이 많은 지역/시기는 결과 신뢰도가 낮을 수 있음 → 복수 날짜 비교 권장
