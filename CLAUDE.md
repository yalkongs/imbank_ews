# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

**imbank EWS** — iM뱅크 기업여신 조기경보 시스템 POC.
- 학습 데이터: `data_pipeline/ews_corporate_v24.db` (심볼릭 링크 → `CSS/v24/ews_corporate_v24.db`, 12GB)
- ML 모델: T1/T2/T3 Tier별 독립 LightGBM (`ml/models/lgbm_t1/t2/t3.pkl`)
- 데모 DB: `demo/demo_imbank.db` (약 1,000개 기업, 검증용)
- 스택: FastAPI (포트 8000) + React/TypeScript (포트 3000) + SQLite

## 실행 명령

```bash
# 데모 시스템 원클릭 실행
bash start.sh

# 백엔드 단독
cd backend && uvicorn app.main:app --reload --port 8000

# 프론트엔드 단독
cd frontend && npm run dev

# 프론트엔드 빌드
cd frontend && npm run build

# 학습 데이터 재빌드 (전체 ~90분)
cd data_pipeline && python3 build.py

# Tier별 ML 모델 재훈련
cd ml && python3 train_tier.py
```

## 코드 구조

### data_pipeline/ — 학습용 데이터 생성 (v24 기준)
- `build.py` — s01~s35 단계별 빌드 오케스트레이터
- `stages/` — 35개 단계 모듈 (s01_company.py ~ s35_regulatory_capital.py)
- `config/` — 거시환경(macro.py), 기업규모(companies.py), 부도율(default_rates.py), MNAR(mnar.py)
- `cache/` — 단계별 RNG 상태 (재현성)

### ml/ — ML 모델
- `train_tier.py` — T1/T2/T3 Tier별 LightGBM 훈련 (Walk-Forward 12-Fold)
- `models/` — `lgbm_t1.pkl`, `lgbm_t2.pkl`, `lgbm_t3.pkl` (실제 학습 결과)
- `results/` — fold_metrics.csv, feature_importance.csv

### backend/app/api/ — FastAPI 라우터
주요 엔드포인트: company, ews, portfolio, ecl, workout, model-perf, search, stress-test, rm, concentration, maturity, monthly-report, migration, benchmark

### frontend/src/pages/ — React 페이지 (10개)
Dashboard, EWSAlerts, Companies, Portfolio, AssetClassification, ECL, Covenant, Workout, ModelPerf, SystemReport

## 핵심 파라미터

- **학습 타겟**: `label_default_6m` (6개월 선행 부도 예측)
- **Tier 정의**: T1=대기업(101K행, 부도율 0.13%), T2=중소+중견(3.95M행, 0.46%), T3=소기업(1.1M행, 0.86%)
- **데모 DB**: `demo/demo_imbank.db` (검증용, 실제 학습 DB와 별개)
- **관리자 비밀번호**: 재학습 UI 인증에 사용 (model_perf.py 참조)

## 주의사항

- `ews_corporate_v24.db`는 심볼릭 링크 — 실제 파일은 `CSS/v24/ews_corporate_v24.db` (12GB)
- 합성 데이터이므로 AUROC가 과도하게 높음 (Oracle 오염) — 실제 모델 기대치 0.80~0.88
- `demo/demo_imbank.db`는 약 1,000개 기업 검증용 데이터, '데모용' 아닌 'POC용'으로 표기
- API 라우터 추가 시 `backend/app/main.py`에 router 등록 필요
