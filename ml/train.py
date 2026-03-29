"""
train.py — EWS ML 모델 훈련 파이프라인

학습 데이터: v24 DB의 ml_feature_label (5.1M 행)
모델: LightGBM 이진 분류 (6개월 내 부도 예측)
검증: Walk-forward 12-fold (ml_walk_forward_splits)
출력:
  - models/lgbm_champion.pkl  — 최종 모델
  - models/feature_importance.csv
  - results/fold_metrics.csv
  - v24 DB: model_registry, model_performance_monthly 업데이트
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

# ── 경로 설정 ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR.parent / "data_pipeline" / "ews_corporate_v24.db"
MODEL_DIR = BASE_DIR / "models"
RESULT_DIR = BASE_DIR / "results"
MODEL_DIR.mkdir(exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)

# ── 피처 정의 ───────────────────────────────────────────────────────────────
# 레이블 / 메타 컬럼 제외
EXCLUDE_COLS = {
    "borrower_id", "ym",
    "label_default_3m", "label_default_6m",
    "label_downgrade_next_m", "label_watchlist_next_m", "label_ews_grade_next_m",
    "split_set", "label_status", "observation_horizon_end_ym",
    "scoring_run_id", "backfill_version", "production_snapshot_flag",
    "industry_sub_cd",   # 대부분 NULL
    # ── Oracle 오염 피처 제거 (Data Leakage) ────────────────────────────────
    # [Level 1] ews_score: pre_def_signal = grad_drop + sud_drop (months_to_def 직접 사용)
    "ews_score", "ews_score_change_3m", "ews_score_slope_6m",
    "ews_score_prev3m_avg", "ews_score_std_6m",
    # [Level 1] 외부 리스크 점수: sigmoid(... + 4.0 * risk_factor)
    # risk_factor = 0.85 if mbd<=3, 0.65 if mbd<=6, 0.40 if mbd<=12 (s16_external.py)
    "legal_risk_score", "supply_chain_risk_score",
    "governance_risk_score", "supply_chain_disruption_score",
    # [Level 1] mbd 직접 트리거 이진 플래그
    "seizure_flag", "seizure_count_12m",       # mbd <= 3
    "bankruptcy_filing_flag",                   # mbd == 0
    "key_customer_default_flag",                # mbd <= 6
    # [Level 1] pd_days → asset quality / IFRS9 stage (mbd==0 → 90+일 연체로 직접 설정)
    "asset_quality_cd", "ifrs9_stage_cd",
    # [Level 1] watchlist = ews_score < 50 (oracle alias)
    "watchlist_flag",
    # [Level 2] pd_days 기반 파생 (강한 간접 oracle)
    "principal_past_due_days", "past_due_count_12m",
    # [Level 2] alert = f(ews_fall, ews_level) from ews_score (oracle)
    "alert_signal_count", "alert_signal_severity",
    # [Level 2] employee_count_change_pct: risk_factor > 0.4 → -25% (직접 oracle 트리거)
    "employee_count_change_pct",
}

TARGET = "label_default_6m"

# asset_quality_cd / ifrs9_stage_cd 제거 후 잔여 범주형 피처
CAT_COLS = ["firm_size_cd", "industry_cd"]

LGBM_PARAMS = {
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
    """KS 통계량"""
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    return float(np.max(tpr - fpr))


SAMPLE_PER_FOLD = 300_000   # 폴드당 최대 훈련 샘플 (메모리/속도 균형)
SAMPLE_SEED    = 42


def load_data(conn):
    """ml_feature_label 로드 — 폴드 경계 연도 기반 청크 로드"""
    print("  데이터 로드 중 (샘플링 모드)...", flush=True)
    t0 = time.time()

    # 전체 행 수 확인
    total = conn.execute("SELECT COUNT(*) FROM ml_feature_label").fetchone()[0]
    print(f"  전체 행: {total:,}행", flush=True)

    # 300K 샘플링 (계층 유지: 부도/생존 비율 보존)
    # 부도 레코드 전수 + 생존 레코드 샘플링
    n_default = conn.execute(
        f"SELECT COUNT(*) FROM ml_feature_label WHERE {TARGET}=1"
    ).fetchone()[0]
    n_sample_normal = min(SAMPLE_PER_FOLD - n_default, SAMPLE_PER_FOLD // 2)

    df_default = pd.read_sql_query(
        f"SELECT * FROM ml_feature_label WHERE {TARGET}=1", conn
    )
    df_normal = pd.read_sql_query(
        f"SELECT * FROM ml_feature_label WHERE {TARGET}=0 "
        f"ORDER BY RANDOM() LIMIT {n_sample_normal}", conn
    )
    df = pd.concat([df_default, df_normal], ignore_index=True)

    print(f"  로드 완료: {len(df):,}행 (부도 {len(df_default):,} + 생존 {len(df_normal):,}) ({time.time()-t0:.1f}초)", flush=True)
    return df


def preprocess(df):
    """전처리: 타입 정리, 범주형 인코딩, 결측 처리"""
    # listed_flag bytes → int
    if df["listed_flag"].dtype == object:
        df["listed_flag"] = df["listed_flag"].apply(
            lambda x: int.from_bytes(x, "little") if isinstance(x, (bytes, bytearray)) else int(x or 0)
        )

    # 범주형 인코딩
    le_map = {}
    for col in CAT_COLS:
        if col in df.columns:
            df[col] = df[col].fillna("UNKNOWN").astype(str)
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col])
            le_map[col] = le

    # 피처 컬럼 선택
    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS and c != TARGET]
    return df, feature_cols, le_map


def load_splits(conn):
    """Walk-forward 분할 정보 로드"""
    return pd.read_sql_query(
        "SELECT * FROM ml_walk_forward_splits ORDER BY fold_id",
        conn
    )


def train_fold(df, feature_cols, train_start, train_end, test_start, test_end, fold_id):
    """단일 fold 훈련 + 평가"""
    train_mask = (df["ym"] >= train_start) & (df["ym"] <= train_end)
    test_mask  = (df["ym"] >= test_start)  & (df["ym"] <= test_end)

    X_tr = df.loc[train_mask, feature_cols]
    y_tr = df.loc[train_mask, TARGET].astype(int)
    X_te = df.loc[test_mask,  feature_cols]
    y_te = df.loc[test_mask,  TARGET].astype(int)

    if len(y_tr) == 0 or len(y_te) == 0 or y_te.sum() == 0:
        print(f"    Fold {fold_id}: 샘플 부족 — 스킵", flush=True)
        return None, None, None

    pos_rate = y_tr.mean()
    scale_pos = (1 - pos_rate) / pos_rate if pos_rate > 0 else 1.0

    params = {**LGBM_PARAMS, "scale_pos_weight": scale_pos}

    model = lgb.LGBMClassifier(**params)
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_te, y_te)],
        callbacks=[
            lgb.early_stopping(stopping_rounds=30, verbose=False),
            lgb.log_evaluation(period=0),
        ],
        categorical_feature=[c for c in CAT_COLS if c in feature_cols],
    )

    y_prob = model.predict_proba(X_te)[:, 1]
    auroc = roc_auc_score(y_te, y_prob)
    ks    = ks_stat(y_te, y_prob)
    ap    = average_precision_score(y_te, y_prob)
    default_rate = y_te.mean()

    print(f"    Fold {fold_id} ({train_start}~{train_end} → {test_start}~{test_end}): "
          f"AUROC={auroc:.4f}  KS={ks:.4f}  AP={ap:.4f}  부도율={default_rate:.4f}", flush=True)

    return model, auroc, {"fold_id": fold_id, "train_start": train_start,
                          "train_end": train_end, "test_start": test_start,
                          "test_end": test_end, "auroc": auroc, "ks": ks,
                          "ap": ap, "default_rate": default_rate,
                          "n_train": len(y_tr), "n_test": len(y_te)}


def train_final(df, feature_cols):
    """전체 데이터로 최종 모델 훈련"""
    print("\n  최종 모델 훈련 (전체 데이터)...", flush=True)
    X = df[feature_cols]
    y = df[TARGET].astype(int)

    pos_rate = y.mean()
    scale_pos = (1 - pos_rate) / pos_rate if pos_rate > 0 else 1.0

    params = {**LGBM_PARAMS, "scale_pos_weight": scale_pos}
    # 최종 모델은 early stopping 없이 고정 라운드
    params["n_estimators"] = 300
    params.pop("early_stopping_rounds", None)

    model = lgb.LGBMClassifier(**params)
    model.fit(X, y, categorical_feature=[c for c in CAT_COLS if c in feature_cols])
    return model


def save_feature_importance(model, feature_cols):
    fi = pd.DataFrame({
        "feature": feature_cols,
        "importance_gain": model.booster_.feature_importance(importance_type="gain"),
        "importance_split": model.booster_.feature_importance(importance_type="split"),
    }).sort_values("importance_gain", ascending=False)
    fi.to_csv(RESULT_DIR / "feature_importance.csv", index=False)
    print("\n  피처 중요도 상위 15개:", flush=True)
    for _, row in fi.head(15).iterrows():
        print(f"    {row['feature']:<40} gain={row['importance_gain']:,.0f}", flush=True)
    return fi


def update_db(conn, fold_metrics, final_auroc, final_ks, feature_cols):
    """model_registry, model_performance_monthly 업데이트"""
    import uuid, datetime
    model_id = str(uuid.uuid4())[:12]
    now_ym = int(datetime.datetime.now().strftime("%Y%m"))

    conn.execute("""
        INSERT OR REPLACE INTO model_registry
          (model_id, model_version, algorithm, train_start_ym, train_end_ym,
           champion_flag, deploy_ym, auroc, ks_stat, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (model_id, "v24.0-lgbm", "LightGBM",
          201701, 202512, 1, now_ym,
          round(final_auroc, 4), round(final_ks, 4),
          f"Walk-forward 12-fold | features={len(feature_cols)}"))

    # 기존 champion 해제
    conn.execute(
        "UPDATE model_registry SET champion_flag=0 WHERE model_id != ?", (model_id,)
    )

    # model_performance_monthly에 fold 결과 저장
    for m in fold_metrics:
        conn.execute("""
            INSERT OR IGNORE INTO model_performance_monthly
              (model_version, ym, split_set, auroc, ks_stat,
               avg_precision, n_samples, n_defaults)
            VALUES (?,?,?,?,?,?,?,?)
        """, ("v24.0-lgbm", m["test_start"], f"fold_{m['fold_id']}",
              round(m["auroc"], 4), round(m["ks"], 4),
              round(m["ap"], 4), m["n_test"],
              int(m["default_rate"] * m["n_test"])))

    conn.commit()
    print(f"\n  model_registry 업데이트 완료 (model_id={model_id})", flush=True)
    return model_id


def main():
    t0 = time.time()
    print("=" * 60, flush=True)
    print(" EWS ML 파이프라인 — 훈련 시작", flush=True)
    print("=" * 60, flush=True)

    conn = sqlite3.connect(DB_PATH)

    # 1. 데이터 로드
    df = load_data(conn)
    df, feature_cols, le_map = preprocess(df)
    print(f"  피처 수: {len(feature_cols)}", flush=True)
    print(f"  부도율: {df[TARGET].mean():.4f} ({df[TARGET].sum():,}건 / {len(df):,}행)", flush=True)

    # 2. Walk-forward 훈련
    splits = load_splits(conn)
    print(f"\n  Walk-forward {len(splits)}-fold 훈련 시작", flush=True)

    fold_metrics = []
    best_model = None
    best_auroc = 0.0

    for _, row in splits.iterrows():
        model, auroc, metrics = train_fold(
            df, feature_cols,
            int(row.train_start_ym), int(row.train_end_ym),
            int(row.test_start_ym),  int(row.test_end_ym),
            int(row.fold_id)
        )
        if model is not None:
            fold_metrics.append(metrics)
            if auroc > best_auroc:
                best_auroc = auroc
                best_model = model

    if fold_metrics:
        avg_auroc = np.mean([m["auroc"] for m in fold_metrics])
        avg_ks    = np.mean([m["ks"]    for m in fold_metrics])
        print(f"\n  Walk-forward 평균 AUROC={avg_auroc:.4f}  KS={avg_ks:.4f}", flush=True)
        pd.DataFrame(fold_metrics).to_csv(RESULT_DIR / "fold_metrics.csv", index=False)

    # 3. 최종 모델 훈련
    final_model = train_final(df, feature_cols)

    # 4. 피처 중요도
    fi = save_feature_importance(final_model, feature_cols)

    # 5. 모델 저장
    artifact = {
        "model": final_model,
        "feature_cols": feature_cols,
        "le_map": le_map,
        "cat_cols": CAT_COLS,
        "target": TARGET,
        "avg_auroc": avg_auroc if fold_metrics else 0.0,
        "avg_ks": avg_ks if fold_metrics else 0.0,
    }
    model_path = MODEL_DIR / "lgbm_champion.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(artifact, f)
    print(f"\n  모델 저장: {model_path}", flush=True)

    # 6. DB 업데이트
    final_auroc = avg_auroc if fold_metrics else 0.0
    final_ks    = avg_ks    if fold_metrics else 0.0
    update_db(conn, fold_metrics, final_auroc, final_ks, feature_cols)

    conn.close()
    elapsed = round(time.time() - t0, 1)
    print(f"\n  총 소요: {elapsed}초", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
