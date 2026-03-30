# iM뱅크 기업여신 EWS 시스템

> **iM Bank Corporate Loan Early Warning System (EWS)**
> 기업 차주의 신용 위험을 조기에 탐지하고 선제적인 여신 관리를 가능하게 하는 데이터 기반 리스크 관리 플랫폼

기준일: 2026년 3월 | 개발: 황원철 (Hwang Weoncheol)

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [빠른 시작](#2-빠른-시작)
3. [프로젝트 구조](#3-프로젝트-구조)
4. [데이터 생성 방법론](#4-데이터-생성-방법론)
5. [ML 모델 — Tier별 독립 LightGBM](#5-ml-모델--tier별-독립-lightgbm)
6. [EWS 판단 이론](#6-ews-판단-이론)
7. [감독 규정 호환성](#7-감독-규정-호환성)
8. [기술 아키텍처](#8-기술-아키텍처)
9. [실데이터 전환 가이드](#9-실데이터-전환-가이드)
10. [운영 KPI](#10-운영-kpi)
11. [향후 로드맵](#11-향후-로드맵)

---

## 1. 시스템 개요

iM뱅크 기업여신 조기경보 시스템(EWS: Early Warning System)은 기업 차주의 신용 위험을 조기에 탐지하고 선제적인 여신 관리를 가능하게 하는 데이터 기반 리스크 관리 플랫폼입니다. 국내 중소기업 여신 포트폴리오의 특수성과 iM뱅크의 지역 기반 영업 특성을 반영하여 설계되었습니다.

| 항목 | 내용 |
|------|------|
| 모니터링 기업 수 | 20,000개 (대구경북 50% · 부산경남 25% · 수도권 25%) |
| 데이터 기간 | 36개월 (2023-01 ~ 2025-12) |
| EWS 등급 체계 | 4단계: A(정상) / B(주의) / C(경계) / D(위험) |

### 주요 기능 범위

| 기능 영역 | 세부 기능 | 주요 산출물 |
|-----------|-----------|-------------|
| EWS 경보 | 월별 등급 산출, 경보 기업 식별, 액션 관리 | EWS 등급(A/B/C/D), 경보 리스트 |
| 여신 포트폴리오 | 업종별·규모별 집중도, 만기 도래 관리 | 집중도 지표, 만기 캘린더 |
| 자산건전성 | IFRS9 Stage 분류, ECL 충당금 산출 | Stage 분류, PD/LGD/EAD |
| 선행지표 고도화 | 거래행동, 공공이벤트, 뉴스감성, 시장신호, 공급망 | 데이터 완성도 Tier (T1/T2/T3) |
| 리스크 분석 | 등급 전이 행렬, 스트레스 테스트, 코베넌트 | 전이 확률, 시나리오 충격량 |
| NPL/Workout | 부실채권 관리, 회수율 분석, 시나리오 | 회수 예상액, NPV/IRR |
| 모델 성능 | AUROC, KS 통계, 혼동행렬, 선행시간 | 모델 검증 리포트 |

---

## 2. 빠른 시작

### 사전 요구사항

- Python 3.10+
- Node.js 18+

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/yalkongs/imbank_ews.git
cd imbank_ews

# 2. 백엔드 의존성 설치
cd backend
pip install -r requirements.txt

# 3. 검증용 DB 생성 (최초 1회, 약 60초 소요)
cd ../demo
python3 generate_dataset.py

# 4. 프론트엔드 빌드
cd ../frontend
npm install
npm run build

# 5. 원클릭 실행 (backend 포트 8000 + frontend 포트 3000)
cd ..
bash start.sh
```

접속 URL:
- **EWS 대시보드**: http://localhost:3000
- **API 문서 (Swagger)**: http://localhost:8000/docs

### 학습용 DB 재빌드 (선택)

```bash
cd data_pipeline
python3 build.py           # 전체 빌드 (~90분)
python3 build.py --from s31  # 특정 스테이지부터
python3 build.py --only s05   # 단일 스테이지만
```

### ML 모델 재훈련 (선택)

```bash
cd ml
python3 train_tier.py
# T1/T2/T3 Tier별 독립 LightGBM 모델 학습
# 출력: models/lgbm_t1.pkl, lgbm_t2.pkl, lgbm_t3.pkl
```

---

## 3. 프로젝트 구조

```
imbank_ews/
├── data_pipeline/              # (A) 학습용 데이터 생성 파이프라인 (v24)
│   ├── build.py                # 빌드 오케스트레이터 (s01~s35)
│   ├── config/                 # 거시환경, 기업규모, 부도율 설정
│   ├── stages/                 # 35개 단계 모듈
│   └── ews_corporate_v24.db   # 학습용 DB (심볼릭 링크, 12GB — git 제외)
│
├── ml/                         # (B) ML 부실 예측 모델
│   ├── train_tier.py           # T1/T2/T3 Tier별 LightGBM 훈련
│   ├── models/                 # lgbm_t1/t2/t3.pkl (git 제외)
│   └── results/                # fold_metrics, feature_importance CSV
│
├── demo/                       # (C) 검증용 샘플 데이터셋
│   ├── generate_dataset.py     # 검증용 DB 생성기 (20,000기업 × 36개월)
│   └── demo_imbank.db          # 검증용 DB (git 제외)
│
├── backend/                    # (D) FastAPI 백엔드
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                # 라우터 (20개+)
│   │   └── core/               # DB 연결, 설정
│   └── requirements.txt
│
├── frontend/                   # (E) React + TypeScript 프론트엔드
│   ├── src/
│   │   ├── pages/              # 10개 화면
│   │   ├── components/         # 공용 컴포넌트
│   │   └── utils/              # API 클라이언트
│   └── package.json
│
├── start.sh                    # 원클릭 실행 스크립트
└── README.md
```

---

## 4. 데이터 생성 방법론

본 시스템은 두 가지 데이터베이스를 사용합니다.

- **학습용 DB (`ews_corporate_v24.db`)**: 60,000개 기업 × 108개월(2017~2025), 약 12GB
- **검증용 DB (`demo_imbank.db`)**: 20,000개 기업 × 36개월(2023~2025), 약 580MB

### 4.1 기업 모집단 설계

**지역 배분 (iM뱅크 영업 특성 반영)**

| 지역 | 비중 | 주요 업종 | 특징 |
|------|------|-----------|------|
| 대구경북 | 50% | 섬유(K01A), 자동차부품(K01B), 건설(K02) | 전통 제조업 중심, 중소기업 밀집 |
| 부산경남 | 25% | 도소매(K03), 운수물류(K08), 건설(K02) | 항만·물류 기반, 조선 연관 업종 |
| 수도권 | 25% | 서비스(K04), IT(K05), 도소매(K03) | 대기업·중견기업 비중 높음 |

**기업 규모 배분**

| 규모 | 비중 | 설명 | 데이터 Tier |
|------|------|------|-------------|
| 대기업 | 2% | 총자산 5,000억 이상 | T1 (완성도 75~95%) |
| 중견기업 | 13% | 총자산 1,000~5,000억 | T2 (완성도 45~75%) |
| 중소기업 | 35% | 총자산 120~1,000억 | T2 (완성도 45~75%) |
| 소기업 | 50% | 총자산 120억 미만 | T3 (완성도 15~50%) |

### 4.2 차주 시나리오 및 부도 경로

| 시나리오 | 비중 | 설명 |
|----------|------|------|
| NORMAL | 80% | 정상 운영 기업 |
| DEFAULT | 12% | 부도 발생 기업 |
| RECOVERY | 8% | 부도 후 회생 기업 |

**부도 경로 유형 3가지:**
- **ACUTE (급성)**: 외부 충격으로 3~6개월 내 급격한 신용 악화
- **CHRONIC (만성)**: 재무 지표의 12~24개월 점진적 악화
- **EVENT (이벤트)**: 압류, 세금 체납 등 공공이벤트 연계 부도

### 4.3 거시경제 국면 8개 (시계열 현실성 확보)

| 국면 | 기간 | 리스크 계수 | 설명 |
|------|------|-------------|------|
| P1 일반 성장기 | 2017-01 ~ 2018-06 | 0.85 | 기준금리 인상 전 완만한 성장 |
| P2 미중 무역분쟁 | 2018-07 ~ 2019-06 | 1.20 | 대외 불확실성, 수출 위축 |
| P3 저금리 안정기 | 2019-07 ~ 2019-12 | 0.80 | 금리 인하 기조, 여신 확대 |
| P4 COVID 충격 | 2020-01 ~ 2020-09 | 1.80 | 급격한 경기 수축, 부도율 급등 |
| P5 경기 회복기 | 2020-10 ~ 2021-12 | 0.90 | 정책 지원 + 리오프닝 효과 |
| P6 인플레이션 | 2022-01 ~ 2022-12 | 1.35 | 금리 급등, 원가 압박 |
| P7 고금리 긴축기 | 2023-01 ~ 2024-06 | 1.45 | 기준금리 3.5% 고착, 부실 누적 |
| P8 연착륙 국면 | 2024-07 ~ 2025-12 | 1.10 | 점진적 금리 인하, 건전성 우려 지속 |

### 4.4 Walk-Forward 검증 설계 (12-fold)

시계열 금융 데이터의 Temporal Data Leakage를 방지하기 위해 Walk-Forward 교차검증 적용.

```
Fold 01: Train 2017-01~2021-12 → Test 2022-01~2022-04
Fold 02: Train 2017-05~2022-04 → Test 2022-05~2022-08
...
Fold 12: Train 2020-09~2025-08 → Test 2025-09~2025-12
```

타깃: `label_default_6m` (6개월 내 부도 여부)

### 4.5 학습용 DB Tier별 규모 (ml_feature_label 실측)

| Tier | 기업 규모 | 행 수 | 부도율 (6m) | 비고 |
|------|-----------|-------|-------------|------|
| T1 | 대기업 | 101,392행 | 0.13% | 전량 사용, Fold당 부도 1~15건 |
| T2 | 중소기업 + 중견기업 | 3,948,822행 | 0.46% | 생존 35만 건 샘플링 |
| T3 | 소기업 | 1,101,301행 | 0.86% | 생존 20만 건 샘플링 |
| 전체 | 전체 | 5,151,515행 | 0.54% | Champion 모델 기반 |

---

## 5. ML 모델 — Tier별 독립 LightGBM

T1/T2/T3 세 가지 Tier에 대해 각각 독립된 LightGBM 모델을 학습하였습니다. Walk-Forward 12-Fold 교차검증으로 검증된 실측 결과입니다.

### 5.1 실제 학습 성능

| 모델 | 대상 규모 | Walk-Forward AUROC | KS 통계 | AP | Fold 수 |
|------|-----------|--------------------|---------|----|---------|
| T1 — 대기업 | 대기업 | **0.9866** | 0.9737 | 0.7279 | 11 (Fold 4 스킵) |
| T2 — 중소·중견 | 중소기업 + 중견기업 | **0.9998** | 0.9935 | 0.9977 | 12 |
| T3 — 소기업 | 소기업 | **0.9997** | 0.9905 | 0.9957 | 12 |

> ⚠️ **주의**: T2/T3의 AUROC 0.999+는 합성 데이터의 Oracle 오염 효과입니다. 실데이터 기반 EWS 모델의 기대 AUROC: **0.80~0.88**, KS: **0.50~0.60**.

### 5.2 Tier별 Top 10 피처 (학습 결과)

| 순위 | T1 (대기업) | T2 (중소·중견) | T3 (소기업) |
|------|-------------|----------------|-------------|
| 1 | lawsuit_amount_억 | tax_lien_amount_억 | tax_lien_amount_억 |
| 2 | tax_lien_amount_억 | payroll_amount_pct | payroll_amount_pct |
| 3 | icr_pct_rank | supplier_hhi | supplier_hhi |
| 4 | electricity_usage_idx | social_insurance_dropout_flag | lawsuit_amount_억 |
| 5 | trade_balance_change_pct | tax_arrears_months | social_insurance_dropout_flag |
| 6 | tax_arrears_months | lawsuit_amount_억 | lawsuit_count_12m |
| 7 | lawsuit_count_12m | lawsuit_count_12m | tax_arrears_months |
| 8 | social_insurance_dropout_flag | industry_cd | industry_cd |
| 9 | audit_opinion_qualified_flag | audit_opinion_qualified_flag | trade_balance_change_pct |
| 10 | sales_growth_pct | trade_balance_change_pct | news_sentiment_score |

### 5.3 Tier별 LightGBM 파라미터

| 파라미터 | T1 (대기업) | T2 (중소·중견) | T3 (소기업) | 이유 |
|----------|-------------|----------------|-------------|------|
| num_leaves | 31 | 63 | 47 | T1 소규모 데이터 과적합 방지 |
| min_child_samples | 10 | 50 | 30 | T1 부도 건수 극소 → 최소 노드 완화 |
| n_estimators | 400 | 500 | 400 | T2 대용량 데이터, 더 많은 트리 허용 |
| reg_lambda | 2.0 | 1.0 | 1.5 | T1 강한 정규화, T2 완화 |
| scale_pos_weight | 자동 (부도율 기반) | 자동 | 자동 | 불균형 클래스 자동 보정 |

### 5.4 모델 재학습 (관리자)

웹 UI의 **모델 성능** 메뉴 → 재학습 버튼 → 관리자 비밀번호 입력 → T1/T2/T3 전체 재학습 실행.
또는 CLI:

```bash
cd ml && python3 train_tier.py
```

---

## 6. EWS 판단 이론

### 6.1 EWS 점수 산출 공식

```
raw_ews_score = Σ (지표값 × 가중치) — Sigmoid 정규화 → [0, 100]
confidence_adj_score = max(1, raw_score − (1 − completeness_pct/100) × 25)
```

데이터 완성도 60% 기업: 원점수에서 최대 10점 하향 조정 가능.

### 6.2 EWS 등급 경계값

| 등급 | 점수 범위 | 의미 |
|------|-----------|------|
| A | ≥ 75 | 정상 |
| B | 50 ~ 74 | 주의 |
| C | 25 ~ 49 | 경계 |
| D | < 25 | 위험 |

### 6.3 피처 카테고리 및 가중치 (기준)

| 피처 카테고리 | 가중치 | 대표 지표 |
|---------------|--------|-----------|
| 재무제표 | 30% | 부채비율, DSCR, 유동비율, ROE |
| 거래행동 | 25% | 일평균잔액, 지연건수, 급여이체 |
| 공공이벤트 | 15% | 압류, 세금체납, 감사의견 비적정 |
| 뉴스감성 | 15% | 부정기사 비율, 평균감성점수 |
| 시장신호 | 10% | CDS스프레드, 주가변화율 |
| 공급망 | 5% | 전이위험점수, 고위험 거래선 비율 |

### 6.4 Data Leakage 방지 — Oracle 피처 제외

학습 피처에서 명시적으로 제외한 피처들:

- **Level 1 (직접 누수)**: `ews_score`, `ews_score_change_3m`, `legal_risk_score`, `supply_chain_risk_score`
- **Level 1 (이진 트리거)**: `seizure_flag`, `bankruptcy_filing_flag`, `key_customer_default_flag`
- **Level 1 (IFRS9 결과)**: `asset_quality_cd`, `ifrs9_stage_cd`
- **Level 2 (간접 누수)**: `pd_12m_forecast`, `ecl_amount_억`, `recovery_rate_expectation`

---

## 7. 감독 규정 호환성

### 7.1 자산건전성 분류 (금융감독원)

| 자산건전성 분류 | 기준 | EWS 등급 매핑 | 충당금 적립률(최소) |
|-----------------|------|---------------|---------------------|
| 정상 (NORMAL) | 원금·이자 정상 상환 | A등급 | 0.5% |
| 요주의 (PRECAUTIONARY) | 1~3개월 연체 | B~C등급 | 2% |
| 고정 (SUBSTANDARD) | 3개월 이상 연체 | C~D등급 | 20% |
| 회수의문 (DOUBTFUL) | 심각한 회수 불확실 | D등급 | 50% |
| 추정손실 (LOSS) | 회수 불가능 | D등급 | 100% |

### 7.2 IFRS9 ECL 체계

```
ECL = PD × LGD × EAD × DF
```

- **PD**: EWS 점수 기반 부도 확률
- **LGD**: 담보 종류 및 LTV 반영 (부동산 30~50%, 무담보 60~80%)
- **EAD**: 현재 잔액 + 미인출 한도 × CCF
- **DF**: 할인율 적용 현재가치

| Stage | 정의 | ECL 산출 기간 | EWS 연계 |
|-------|------|---------------|----------|
| Stage 1 | 신용 위험 유의적 증가 없음 | 12개월 | A등급, 연체 0일 |
| Stage 2 | 신용 위험 유의적 증가 | 전체 존속 기간 | B~C등급, 연체 1~89일 |
| Stage 3 | 신용 손상 발생 | 전체 존속 기간 | D등급, 연체 90일 이상 |

---

## 8. 기술 아키텍처

### 8.1 전체 구성도

```
┌──────────────────────────────────────────────────────────────┐
│                   프론트엔드 (React + TypeScript)              │
│   Dashboard │ EWSAlerts │ Companies │ Portfolio │ ModelPerf   │
│                    Vite + Tailwind CSS                        │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP (Axios)
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    백엔드 (FastAPI)                            │
│  /api/ews  /api/company  /api/ecl  /api/model-perf  ...      │
│                SQLAlchemy ORM                                 │
└────────────────────────┬─────────────────────────────────────┘
                         │
                ┌────────▼────────┐
                │   SQLite DB      │
                │  demo_imbank.db  │
                │  ~580MB          │
                └─────────────────┘
```

### 8.2 기술 스택

| 레이어 | 기술 | 역할 |
|--------|------|------|
| 프론트엔드 | React 18 + TypeScript 5 | SPA UI 렌더링 |
| 프론트엔드 | Vite 5.x | 빌드 도구, HMR |
| 프론트엔드 | Tailwind CSS 3.x | 유틸리티 CSS 스타일링 |
| 프론트엔드 | Recharts 2.x | 차트 (Line, Bar, Donut) |
| 프론트엔드 | React Router 6.x | SPA 라우팅 |
| 백엔드 | FastAPI 0.1xx | REST API 서버 |
| 백엔드 | SQLAlchemy 2.x | ORM, DB 추상화 |
| 백엔드 | Uvicorn 0.3x | ASGI 서버 |
| 데이터베이스 | SQLite 3.x | POC용 파일 DB |
| ML | LightGBM | Tier별 부도 예측 모델 |
| 데이터 생성 | Python + NumPy | 합성 데이터셋 생성 (35단계) |

### 8.3 화면 구성 (10개 페이지)

| 페이지 | 경로 | 설명 |
|--------|------|------|
| 대시보드 | `/` | 기준월별 EWS 등급 분포, 경보 현황 |
| EWS 경보센터 | `/ews-alerts` | 경보 기업 목록 및 조치 현황 |
| 기업 조회 | `/companies` | 개별 기업 상세 (9개 탭: 여신·재무·담보·거래행태·Workout 등) |
| 포트폴리오 분석 | `/portfolio` | 등급별·업종별·규모별 포트폴리오 현황 |
| 자산건전성 | `/asset-classification` | NORMAL~LOSS 5단계 분류 현황 |
| IFRS9 ECL | `/ecl` | Stage 1/2/3 ECL 충당금 관리 |
| 코베넌트 | `/covenant` | 여신 약정 위반 모니터링 |
| NPL/Workout | `/workout` | 부실채권 관리, 회수 시나리오 분석 |
| 모델 성능 | `/model-perf` | Walk-forward 12-fold 검증, T1/T2/T3 성능, 재학습 UI |
| 종합 보고서 | `/system-report` | 이 문서의 인터랙티브 버전 |

---

## 9. 실데이터 전환 가이드

### 9.1 데이터 소스 매핑

| EWS 데이터 요소 | 실데이터 소스 | 수집 주기 | 가용성 |
|-----------------|---------------|-----------|--------|
| 기업 기본정보 | CLMS 차주 마스터 | 실시간 | 높음 |
| 여신 시설 정보 | CLMS 여신 원장 | 일배치 | 높음 |
| 연체 정보 | 연체관리 시스템 | 일배치 | 높음 |
| 재무제표 | KIS/NICE 신용평가 | 연 1회+ | 중간 |
| 거래행동 데이터 | 수신 원장, 결제 시스템 | 월배치 | 중간 |
| 공공이벤트 | 국세청API, 대법원, 금감원 | 주배치 | 중간 |
| 뉴스 감성 | Naver/BigKinds + NLP | 일배치 | 낮음~중간 |
| 시장 신호 | KRX, 채권 시장 | 일배치 | 상장사만 |
| 공급망 관계 | DART 공시, SCF 거래처 | 분기~반기 | 낮음 |

### 9.2 DB 교체 절차

1. `backend/app/core/database.py`의 `DATABASE_URL`을 실 DB URL로 변경
2. SQLAlchemy 드라이버 교체 (SQLite → PostgreSQL: psycopg2)
3. 각 API 모듈의 SQL 쿼리를 실 테이블명/스키마에 맞게 수정
4. 인증 미들웨어 추가 (JWT 토큰, LDAP 연동 등)
5. 환경변수 관리 (`.env` 파일)

### 9.3 피처 가용성 차이 대응 전략

1. **Tier 기반 모델 분리** — `firm_size_cd` 기반으로 T1/T2/T3 자동 선택 (구현 완료)
2. **MNAR 인코딩** — 결측 여부 자체를 이진 피처로 추가
3. **신뢰 조정 점수** — `confidence_adj_score = max(1, raw_score - (1 - completeness) × 25)`

---

## 10. 운영 KPI

| 지표 | 목표값 | 측정 주기 |
|------|--------|-----------|
| AUROC | ≥ 0.82 | 분기 |
| KS 통계 | ≥ 0.45 | 분기 |
| 정밀도 (C/D 등급) | ≥ 0.70 | 월간 |
| 재현율 (부도 포착율) | ≥ 0.80 | 월간 |
| 선행시간 (Lead Time) | 평균 6개월 | 반기 |
| 액션 완료율 | ≥ 85% | 월간 |
| 경보 피로도 (FP) | ≤ 30% | 분기 |

---

## 11. 향후 로드맵

### Phase 1 (단기)
- ✅ T1/T2/T3 Tier별 독립 모델 구현 완료
- ✅ 모델 재학습 UI (관리자 인증) 구현
- 실데이터 연계 ETL 구축
- 재무제표 자동 수집 파이프라인
- PostgreSQL 전환

### Phase 2 (중기)
- 실데이터 기반 T1/T2/T3 모델 재학습
- T1 대기업 모델 외부 시장 데이터 보강
- 뉴스 NLP 파이프라인 구축
- 공급망 네트워크 분석 고도화
- 사용자 인증 및 권한 체계

### Phase 3 (장기)
- GNN 기반 공급망 전이 위험 모델
- 실시간 이상 탐지 스트리밍
- SHAP 기반 설명 가능 AI (XAI)
- 감독 규정 자동 보고서
- Tier별 임계값 최적화 자동화

---

## 참고 규정 및 문헌

- 금융감독원, 「은행업감독규정」 제29조 (자산건전성 분류 기준), 2024
- 금융감독원, 「기업신용위험 상시평가 모범규준」, 2022
- 금융감독원, 「IFRS9 도입에 따른 대손충당금 적립기준 적용 관련 감독규정 개정」, 2018
- IASB, IFRS 9 Financial Instruments, 2014
- Basel Committee on Banking Supervision, Basel III: A global regulatory framework, 2010
- Ke, G. et al., LightGBM: A Highly Efficient Gradient Boosting Decision Tree, NIPS 2017
- Altman, E.I., Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy, Journal of Finance, 1968

---

*iM뱅크 기업여신 EWS 시스템 v2.0.0 | POC 환경 | 기준일 2026-03*
*개발: 황원철 (Hwang Weoncheol) — 설계·구현·데이터 생성 파이프라인·ML 모델링·프론트엔드·백엔드 전 영역*
