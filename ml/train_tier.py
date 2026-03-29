"""
train_tier.py — Tier별 EWS ML 모델 훈련 파이프라인

T1: 대기업          (101K행, 부도율 ~0.13%)
T2: 중소기업+중견기업 (3.95M행, 부도율 ~0.44%)
T3: 소기업          (1.1M행,  부도율 ~0.86%)

각 Tier 독립 LightGBM 모델 학습 + Walk-Forward 12-Fold 검증
출력:
  models/lgbm_t1.pkl, lgbm_t2.pkl, lgbm_t3.pkl
  results/fold_metrics_t1.csv, fold_metrics_t2.csv, fold_metrics_t3.csv
"""

import os
import sys
import time
import pickle
import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

BASE_DIR  = Path(__file__).parent
DB_PATH   = BASE_DIR.parent / "data_pipeline" / "ews_corporate_v24.db"
MODEL_DIR = BASE_DIR / "models"
RESULT_DIR = BASE_DIR / "results"
MODEL_DIR.mkdir(exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)

# ── 피처 정의 (champion 모델과 동일) ────────────────────────────────────────
EXCLUDE_COLS = {
    "borrower_id", "ym",
    "label_default_3m", "label_default_6m",
    "label_downgrade_next_m", "label_watchlist_next_m", "label_ews_grade_next_m",
    "split_set", "label_status", "observation_horizon_end_ym",
    "scoring_run_id", "backfill_version", "production_snapshot_flag",
    "industry_sub_cd",
    # Oracle 오염 피처
    "ews_score", "ews_score_change_3m", "ews_score_slope_6m",
    "ews_score_prev3m_avg", "ews_score_std_6m",
    "legal_risk_score", "supply_chain_risk_score",
    "governance_risk_score", "supply_chain_disruption_score",
    "seizure_flag", "seizure_count_12m",
    "bankruptcy_filing_flag",
    "key_customer_default_flag",
    "asset_quality_cd", "ifrs9_stage_cd",
    "watchlist_flag",
    "principal_past_due_days", "past_due_count_12m",
    "alert_signal_count", "alert_signal_severity",
    "employee_count_change_pct",
}

TARGET   = "label_default_6m"
CAT_COLS = ["firm_size_cd", "industry_cd"]

# ── Tier 정의 ─────────────────────────────────────────────────────────────────
TIER_CONFIG = {
    "t1": {
        "label": "T1 — 대기업",
        "firm_sizes": ["대기업"],
        "description": "대기업 전용 EWS 모델. 공시 재무데이터·채권시장 신호·공급망 분석 등 고품질 데이터 활용.",
        "data_completeness_range": "75~95%",
        # T1은 샘플이 적으므로 전량 사용 (샘플링 없음)
        "sample_default": None,   # 전수
        "sample_normal": None,    # 전수
        # T1 전용 LightGBM 파라미터 (소규모 데이터, 강한 정규화)
        "lgbm_overrides": {
            "num_leaves": 31,
            "min_child_samples": 10,
            "n_estimators": 400,
            "reg_alpha": 0.2,
            "reg_lambda": 2.0,
        },
        "top_features": [
            "interest_coverage_ratio", "debt_to_equity_ratio",
            "ebitda_margin_pct", "credit_spread_bps", "bond_yield_bps",
            "market_cap_억", "inflow_outflow_ratio", "sales_growth_pct",
            "current_ratio", "credit_rating_numeric",
        ],
        "notes": (
            "대기업은 공시 의무가 명확하여 데이터 완성도가 높습니다. "
            "채권시장 신호(credit_spread_bps, bond_yield_bps)와 "
            "거시경제 국면 변수가 예측력에 가장 크게 기여합니다."
        ),
    },
    "t2": {
        "label": "T2 — 중소·중견기업",
        "firm_sizes": ["중소기업", "중견기업"],
        "description": "중소기업·중견기업 전용 EWS 모델. 여신 한도 활용률·대금 결제 패턴·보증/담보 데이터 활용.",
        "data_completeness_range": "45~75%",
        "sample_default": None,    # 부도 전수
        "sample_normal": 350_000,  # 생존 샘플 (3.95M이라 샘플링 필요)
        "lgbm_overrides": {
            "num_leaves": 63,
            "min_child_samples": 50,
            "n_estimators": 500,
        },
        "top_features": [
            "limit_utilization_ratio", "debt_to_equity_ratio",
            "inflow_outflow_ratio", "interest_coverage_ratio",
            "avg_deposit_balance_억", "covenant_breach_count_12m",
            "current_ratio", "dscr_ratio",
            "sales_growth_pct", "ebitda_margin_pct",
        ],
        "notes": (
            "중소·중견기업은 한도 활용률과 결제 계좌 입출금 패턴이 "
            "부실 선행지표로서 가장 효과적입니다. "
            "코베넌트 위반 이력도 중요한 예측 신호로 작동합니다."
        ),
    },
    "t3": {
        "label": "T3 — 소기업",
        "firm_sizes": ["소기업"],
        "description": "소기업 전용 EWS 모델. 결제 계좌 행동·보증 네트워크·단순 재무비율 위주의 경량 모델.",
        "data_completeness_range": "15~50%",
        "sample_default": None,    # 부도 전수
        "sample_normal": 200_000,  # 생존 샘플
        "lgbm_overrides": {
            "num_leaves": 47,
            "min_child_samples": 30,
            "n_estimators": 400,
            "reg_alpha": 0.15,
            "reg_lambda": 1.5,
        },
        "top_features": [
            "inflow_outflow_ratio", "limit_utilization_ratio",
            "avg_deposit_balance_억", "debt_to_equity_ratio",
            "current_ratio", "interest_coverage_ratio",
            "covenant_breach_count_12m", "industry_stress_score",
            "sales_growth_pct", "news_sentiment_score",
        ],
        "notes": (
            "소기업은 재무제표 신뢰도가 낮아 결제 계좌 행동 데이터 "
            "(inflow_outflow_ratio, avg_deposit_balance)의 예측 기여도가 높습니다. "
            "결측이 많아 Champion 대비 AUROC가 낮으며, 임계값 최적화가 중요합니다."
        ),
    },
}

BASE_LGBM_PARAMS = {
    "objective":        "binary",
    "metric":           "auc",
    "learning_rate":    0.05,
    "num_leaves":       63,
    "max_depth":        6,
    "min_child_samples":50,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq":     5,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "n_estimators":     500,
    "verbose":          -1,
    "n_jobs":           -1,
    "seed":             42,
}


def ks_stat(y_true, y_prob):
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    return float(np.max(tpr - fpr))


def load_tier_data(conn, firm_sizes: list, sample_normal: int | None, seed: int = 42) -> pd.DataFrame:
    sizes_sql = ", ".join(f"'{s}'" for s in firm_sizes)

    # 부도 레코드 전수
    df_def = pd.read_sql_query(
        f"SELECT * FROM ml_feature_label WHERE firm_size_cd IN ({sizes_sql}) AND {TARGET}=1",
        conn
    )
    n_def = len(df_def)

    # 생존 레코드
    if sample_normal is None:
        df_nor = pd.read_sql_query(
            f"SELECT * FROM ml_feature_label WHERE firm_size_cd IN ({sizes_sql}) AND {TARGET}=0",
            conn
        )
    else:
        df_nor = pd.read_sql_query(
            f"SELECT * FROM ml_feature_label WHERE firm_size_cd IN ({sizes_sql}) AND {TARGET}=0 "
            f"ORDER BY RANDOM() LIMIT {sample_normal}",
            conn
        )

    df = pd.concat([df_def, df_nor], ignore_index=True)
    print(f"    로드: 부도 {n_def:,} + 생존 {len(df_nor):,} = 총 {len(df):,}행  "
          f"부도율={n_def/len(df):.4f}", flush=True)
    return df


def preprocess(df: pd.DataFrame):
    if df["listed_flag"].dtype == object:
        df["listed_flag"] = df["listed_flag"].apply(
            lambda x: int.from_bytes(x, "little") if isinstance(x, (bytes, bytearray)) else int(x or 0)
        )
    le_map = {}
    for col in CAT_COLS:
        if col in df.columns:
            df[col] = df[col].fillna("UNKNOWN").astype(str)
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col])
            le_map[col] = le

    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS and c != TARGET]
    return df, feature_cols, le_map


def load_splits(conn):
    return pd.read_sql_query(
        "SELECT * FROM ml_walk_forward_splits ORDER BY fold_id", conn
    )


def train_fold(df, feature_cols, cat_cols, lgbm_params,
               train_start, train_end, test_start, test_end, fold_id):
    train_mask = (df["ym"] >= train_start) & (df["ym"] <= train_end)
    test_mask  = (df["ym"] >= test_start)  & (df["ym"] <= test_end)

    X_tr = df.loc[train_mask, feature_cols]
    y_tr = df.loc[train_mask, TARGET].astype(int)
    X_te = df.loc[test_mask,  feature_cols]
    y_te = df.loc[test_mask,  TARGET].astype(int)

    if len(y_tr) == 0 or len(y_te) == 0 or y_te.sum() == 0:
        print(f"      Fold {fold_id}: 샘플 부족 — 스킵", flush=True)
        return None, None, None

    pos_rate  = y_tr.mean()
    scale_pos = (1 - pos_rate) / pos_rate if pos_rate > 0 else 1.0
    params = {**lgbm_params, "scale_pos_weight": scale_pos}

    model = lgb.LGBMClassifier(**params)
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_te, y_te)],
        callbacks=[
            lgb.early_stopping(stopping_rounds=30, verbose=False),
            lgb.log_evaluation(period=0),
        ],
        categorical_feature=[c for c in cat_cols if c in feature_cols],
    )

    y_prob = model.predict_proba(X_te)[:, 1]
    auroc  = roc_auc_score(y_te, y_prob)
    ks     = ks_stat(y_te, y_prob)
    ap     = average_precision_score(y_te, y_prob)

    print(f"      Fold {fold_id} ({train_start}~{train_end}→{test_start}~{test_end}): "
          f"AUROC={auroc:.4f}  KS={ks:.4f}  AP={ap:.4f}  "
          f"n_train={len(y_tr):,}  n_def={y_te.sum()}", flush=True)

    return model, auroc, {
        "fold_id": fold_id,
        "train_start": train_start, "train_end": train_end,
        "test_start": test_start,   "test_end": test_end,
        "auroc": auroc, "ks": ks, "ap": ap,
        "default_rate": float(y_te.mean()),
        "n_train": len(y_tr), "n_test": len(y_te),
    }


def train_final(df, feature_cols, cat_cols, lgbm_params):
    X = df[feature_cols]
    y = df[TARGET].astype(int)
    pos_rate  = y.mean()
    scale_pos = (1 - pos_rate) / pos_rate if pos_rate > 0 else 1.0
    params = {**lgbm_params, "scale_pos_weight": scale_pos, "n_estimators": 300}
    params.pop("early_stopping_rounds", None)
    model = lgb.LGBMClassifier(**params)
    model.fit(X, y, categorical_feature=[c for c in cat_cols if c in feature_cols])
    return model


def train_tier(tier_key: str, cfg: dict, splits: pd.DataFrame, conn):
    t0 = time.time()
    print(f"\n{'='*60}", flush=True)
    print(f" [{tier_key.upper()}] {cfg['label']} 학습 시작", flush=True)
    print(f"{'='*60}", flush=True)

    # 데이터 로드
    df = load_tier_data(conn, cfg["firm_sizes"], cfg["sample_normal"])
    df, feature_cols, le_map = preprocess(df)
    print(f"  피처 수: {len(feature_cols)}", flush=True)

    # LightGBM 파라미터 (Tier별 오버라이드 적용)
    lgbm_params = {**BASE_LGBM_PARAMS, **cfg.get("lgbm_overrides", {})}

    # Walk-Forward 훈련
    print(f"  Walk-Forward {len(splits)}-Fold 훈련", flush=True)
    fold_metrics = []

    for _, row in splits.iterrows():
        model, auroc, metrics = train_fold(
            df, feature_cols, CAT_COLS, lgbm_params,
            int(row.train_start_ym), int(row.train_end_ym),
            int(row.test_start_ym),  int(row.test_end_ym),
            int(row.fold_id),
        )
        if model is not None:
            fold_metrics.append(metrics)

    if not fold_metrics:
        print(f"  [{tier_key.upper()}] 유효한 Fold 없음 — 스킵", flush=True)
        return None

    avg_auroc = np.mean([m["auroc"] for m in fold_metrics])
    avg_ks    = np.mean([m["ks"]    for m in fold_metrics])
    avg_ap    = np.mean([m["ap"]    for m in fold_metrics])
    print(f"\n  [{tier_key.upper()}] Walk-Forward 평균: "
          f"AUROC={avg_auroc:.4f}  KS={avg_ks:.4f}  AP={avg_ap:.4f}", flush=True)

    # 결과 저장
    pd.DataFrame(fold_metrics).to_csv(
        RESULT_DIR / f"fold_metrics_{tier_key}.csv", index=False
    )

    # 최종 모델 훈련
    print(f"  [{tier_key.upper()}] 최종 모델 훈련 (전체 데이터)...", flush=True)
    final_model = train_final(df, feature_cols, CAT_COLS, lgbm_params)

    # 피처 중요도
    fi = pd.DataFrame({
        "feature": feature_cols,
        "importance_gain": final_model.booster_.feature_importance(importance_type="gain"),
    }).sort_values("importance_gain", ascending=False)
    fi.to_csv(RESULT_DIR / f"feature_importance_{tier_key}.csv", index=False)

    top_features_actual = fi.head(10)["feature"].tolist()
    print(f"  [{tier_key.upper()}] 실제 피처 중요도 Top 10: {top_features_actual}", flush=True)

    elapsed = round(time.time() - t0, 1)
    print(f"  [{tier_key.upper()}] 소요: {elapsed}초", flush=True)

    # pkl 저장
    artifact = {
        "model":          final_model,
        "feature_cols":   feature_cols,
        "le_map":         le_map,
        "cat_cols":       CAT_COLS,
        "target":         TARGET,
        "tier":           tier_key.upper(),
        "tier_label":     cfg["label"],
        "firm_size":      cfg["firm_sizes"],
        "description":    cfg["description"],
        "data_completeness_range": cfg["data_completeness_range"],
        "target_company_count": len(df["borrower_id"].unique()) if "borrower_id" in df.columns else 0,
        "avg_auroc":      round(avg_auroc, 4),
        "avg_ks":         round(avg_ks, 4),
        "avg_ap":         round(avg_ap, 4),
        "n_folds":        len(fold_metrics),
        "top_features":   top_features_actual,
        "notes":          cfg["notes"],
        "is_poc_model":   False,  # 실제 학습 모델
        "model_file":     f"lgbm_{tier_key}.pkl",
        "file_exists":    True,
    }

    out_path = MODEL_DIR / f"lgbm_{tier_key}.pkl"
    with open(out_path, "wb") as f:
        pickle.dump(artifact, f)
    print(f"  [{tier_key.upper()}] 모델 저장 → {out_path.name}", flush=True)

    return artifact


def main():
    t_total = time.time()
    print("=" * 60, flush=True)
    print(" EWS Tier별 ML 파이프라인 — 훈련 시작", flush=True)
    print(f" DB: {DB_PATH}", flush=True)
    print("=" * 60, flush=True)

    if not DB_PATH.exists():
        print(f"[오류] DB를 찾을 수 없습니다: {DB_PATH}", flush=True)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    splits = load_splits(conn)
    print(f"Walk-Forward {len(splits)}-Fold 분할 로드 완료", flush=True)

    results = {}
    for tier_key, cfg in TIER_CONFIG.items():
        artifact = train_tier(tier_key, cfg, splits, conn)
        if artifact:
            results[tier_key] = {
                "auroc": artifact["avg_auroc"],
                "ks":    artifact["avg_ks"],
                "ap":    artifact["avg_ap"],
            }

    conn.close()

    print("\n" + "=" * 60, flush=True)
    print(" 훈련 결과 요약", flush=True)
    print("=" * 60, flush=True)
    for k, v in results.items():
        cfg = TIER_CONFIG[k]
        print(f"  {cfg['label']:<20} AUROC={v['auroc']:.4f}  KS={v['ks']:.4f}  AP={v['ap']:.4f}")

    elapsed = round(time.time() - t_total, 1)
    print(f"\n  총 소요: {elapsed}초", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
