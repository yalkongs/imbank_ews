# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

**imbank EWS** — iM뱅크 기업여신 조기경보 시스템(EWS) 데모.
- 스택: FastAPI (포트 8000) + React/TypeScript + Vite (포트 3000) + SQLite
- 데모 DB: `demo/demo.db` (20,000개 기업, ~581MB) — `demo/generate_dataset.py`로 생성
- 학습 DB: `data_pipeline/` 경유, CSS 프로젝트의 `ews_corporate_v18.db` 참조 (별도)
- 배포: Railway(백엔드) + Vercel(프론트엔드) 분리 배포

## 실행 명령

```bash
# 백엔드 (포트 8000)
cd backend && python3 -m uvicorn app.main:app --reload --port 8000

# 프론트엔드 (포트 3000)
cd frontend && npm run dev

# 데모 DB 재생성 (~57초)
cd demo && python3 generate_dataset.py

# 프론트엔드 프로덕션 빌드
cd frontend && npm run build
```

## 코드 구조

### backend/app/api/ — FastAPI 라우터
각 라우터는 `backend/app/main.py`에 등록 필요.

| 파일 | 엔드포인트 | 비고 |
|------|-----------|------|
| `dashboard.py` | `/api/dashboard/*` | summary, grade-trend, ews-alerts, industry-breakdown, region-breakdown |
| `ews.py` | `/api/ews/*` | alerts, grade-distribution, company history/profile |
| `company.py` | `/api/company/*` | list, search, collateral-valuation |
| `portfolio.py` | `/api/portfolio/*` | summary, concentration, ecl-summary |
| `ecl.py` | `/api/ecl/*` | summary, trend, by-grade, by-stage-trend |
| `maturity.py` | `/api/maturity/*` | calendar, heatmap, summary — ref_ym 자동감지 |
| `workout.py` | `/api/workout/*` | summary, list, scenarios |
| `concentration.py` | `/api/concentration/*` | status, trend |
| `rm.py` | `/api/rm/*` | list, portfolio, summary, comparison |
| `monthly_report.py` | `/api/monthly-report/*` | summary, grade-change, trend |
| `model_perf.py` | `/api/model-perf/*` | summary, confusion, retrain |
| `stress_test.py` | `/api/stress-test/*` | scenarios, impact, custom |

### frontend/src/pages/ — React 페이지 (18개)

| 페이지 | 경로 | 설명 |
|--------|------|------|
| Dashboard | `/` | EWS 대시보드 (핵심 KPI + 차트) |
| EWSAlerts | `/ews-alerts` | 경보 기업 목록 |
| CompanyBrowser | `/companies` | 기업 상세 조회 |
| Portfolio | `/portfolio` | 포트폴리오 분석 |
| AssetClassification | `/asset-classification` | 자산건전성 분류 |
| ECLManagement | `/ecl` | ECL 충당금 관리 |
| Covenant | `/covenant` | 재무특약 모니터링 |
| Workout | `/workout` | NPL/Workout 관리 |
| ModelPerf | `/model-perf` | 모델 성능 |
| Simulation | `/simulation` | 시뮬레이션 |
| Search | `/search` | 기업 검색 |
| EWSAction | `/ews-action` | EWS 액션 현황 |
| MonthlyReport | `/monthly-report` | 월간 보고서 |
| MaturityCalendar | `/maturity-calendar` | 만기 도래 캘린더 |
| ConcentrationLimit | `/concentration` | 집중도 한도 관리 |
| MigrationMatrix | `/migration-matrix` | 등급 이행 행렬 |
| StressTest | `/stress-test` | 스트레스 테스트 |
| RMPortfolio | `/rm-portfolio` | RM 포트폴리오 |

### frontend/src/utils/
- `api.ts` — axios 기반 API 클라이언트, 엔드포인트별 함수 집합
- `format.ts` — `formatEok()`, `formatNumber()`, `formatPercent()`, `formatYm()`, `getEWSGradeColor()` 등

### frontend/src/components/
- `Card.tsx` — `Card`, `StatCard`, `GaugeCard`(반원형 recharts 게이지) 컴포넌트
- `Charts.tsx` — `TrendChart`, `DonutChart`, `GroupedBarChart` 등 recharts 래퍼
- `Table.tsx` — 공통 테이블

## 데모 DB 주요 사항

- **규모**: 20,000개 기업, iM뱅크 기업여신 기준으로 설계 (~349,610억원, 실제 347,100억원 대비 0.7% 오차)
- **기간**: 202301~202512 (36개월)
- **지역 분포**: 대구경북 50%, 부산경남 25%, 수도권 25% (iM뱅크 실제 비중 반영)
- **만기 데이터**: `demo_facility.maturity_ym` 범위 202601~202811 (YM_END+1 ~ YM_END+36)
- **여신 규모**: 대기업 (60~600억), 중견기업 (10~110억), 중소기업 (2~20억), 소기업 (0.3~4.5억)

## 핵심 기술 결정 및 주의사항

### API 방어 코드 (Dashboard.tsx)
SPA fallback으로 없는 엔드포인트에 HTML이 200 OK로 반환될 수 있어 `Promise.allSettled` + `Array.isArray` 체크 필수:
```tsx
if (industryR.status === 'fulfilled' && Array.isArray(industryR.value.data))
  setIndustryBreakdown(industryR.value.data);
```

### F5 새로고침 처리 (main.tsx)
`/` 이외 경로에서 reload 시 대시보드로 이동 (SPA 라우팅 문제 방지):
```tsx
if (navEntry?.type === 'reload' && window.location.pathname !== '/') {
  window.location.replace('/');
}
```

### 만기 캘린더 ref_ym 자동감지 (maturity.py)
`demo_monthly_signal`의 `MAX(ym)`을 기준월로 자동 사용:
```python
def _get_ref_ym(db, requested):
    if requested is not None: return requested
    row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
    return row[0] if row and row[0] else 202512
```

### 숫자 포맷팅 원칙
- 억원 단위 금액: `formatEok(v)` 또는 `formatNumber(v, 1)` — 절대 `.toFixed(1)` 날 것으로 사용 금지
- 건수/기업수: `.toLocaleString()` 또는 `formatNumber(v, 0)`
- `format.ts`에 `formatEok`, `formatNumber`, `formatPercent`, `formatYm` 등 유틸 함수 존재

### GaugeCard (반원형 게이지)
`Card.tsx`에 recharts `PieChart` 기반 반원형 게이지 구현. `startAngle=180, endAngle=0`, 정상/주의/위험 색상 자동 분기.

## 로컬 개발 환경

- 프론트엔드 프록시: Vite가 `/api` → `http://localhost:8000` 프록시 (vite.config.ts 확인)
- 백엔드 DB 경로: `backend/app/core/database.py` → `demo/demo.db`
- 백엔드 재시작: `lsof -ti:8000 | xargs kill -9` 후 uvicorn 재실행
- HMR 주의: 코드 변경 후 상태가 보존되므로 데이터 로딩 안 될 때는 F5 강제 새로고침

## 배포 (Railway + Vercel)

- `railway.toml` — Railway 백엔드 배포 설정
- `vercel.json` — Vercel 프론트엔드 배포 설정
- `Dockerfile` — 컨테이너 배포용
- 환경변수: 프론트엔드 `VITE_API_URL`에 Railway URL 설정 시 분리 배포 작동
