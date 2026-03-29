"""
모델 성능 API
fold_metrics.csv 결과 + 검증용 데이터 기반 성능 지표
"""
import csv
import pickle
import subprocess
import sys
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db

router = APIRouter(prefix="/api/model-perf", tags=["ModelPerf"])

# 경로 설정
_BASE = Path(__file__).parent.parent.parent.parent
_CSV_PATH = _BASE / "ml" / "results" / "fold_metrics.csv"
_MODEL_DIR = _BASE / "ml" / "models"

ADMIN_PASSWORD = "1111"


def _load_tier_model_meta(tier_key: str) -> dict | None:
    """Tier 모델 pkl 메타데이터 로드 (모델 객체 제외)"""
    pkl_path = _MODEL_DIR / f"lgbm_{tier_key}.pkl"
    if not pkl_path.exists():
        return None
    with open(pkl_path, "rb") as f:
        art = pickle.load(f)
    # 모델 객체는 제외하고 메타데이터만 반환
    return {
        "tier": art.get("tier"),
        "tier_label": art.get("tier_label"),
        "firm_size": art.get("firm_size", []),
        "description": art.get("description", ""),
        "data_completeness_range": art.get("data_completeness_range", ""),
        "target_company_count": art.get("target_company_count", 0),
        "avg_auroc": art.get("avg_auroc", 0.0),
        "avg_ks": art.get("avg_ks", 0.0),
        "avg_ap": art.get("avg_ap", 0.0),
        "n_folds": art.get("n_folds", 0),
        "top_features": art.get("top_features", []),
        "notes": art.get("notes", ""),
        "is_poc_model": art.get("is_poc_model", False),
        "model_file": f"lgbm_{tier_key}.pkl",
        "file_exists": pkl_path.exists(),
    }


def _load_fold_metrics():
    """fold_metrics.csv에서 실제 성능 지표 로드"""
    if not _CSV_PATH.exists():
        return []
    metrics = []
    with open(_CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            metrics.append({
                "fold_id": int(row["fold_id"]),
                "train_start": int(row["train_start"]),
                "train_end": int(row["train_end"]),
                "test_start": int(row["test_start"]),
                "test_end": int(row["test_end"]),
                "auroc": round(float(row["auroc"]), 4),
                "ks": round(float(row["ks"]), 4),
                "ap": round(float(row["ap"]), 4),
            })
    return metrics


@router.get("/summary")
def get_model_summary(db: Session = Depends(get_db)):
    """모델 성능 요약"""
    fold_metrics = _load_fold_metrics()

    if fold_metrics:
        avg_auroc = sum(f["auroc"] for f in fold_metrics) / len(fold_metrics)
        avg_ks = sum(f["ks"] for f in fold_metrics) / len(fold_metrics)
        avg_ap = sum(f["ap"] for f in fold_metrics) / len(fold_metrics)
    else:
        avg_auroc = avg_ks = avg_ap = 0.0

    default_count = db.execute(text(
        "SELECT COUNT(*) FROM demo_company WHERE scenario = 'DEFAULT'"
    )).fetchone()[0]
    total_companies = db.execute(text("SELECT COUNT(*) FROM demo_company")).fetchone()[0]

    return {
        "avg_auroc": round(avg_auroc, 4),
        "avg_ks": round(avg_ks, 4),
        "avg_ap": round(avg_ap, 4),
        "n_folds": len(fold_metrics),
        "total_companies": total_companies,
        "default_companies": default_count,
        "default_rate_pct": round(default_count / total_companies * 100, 2) if total_companies > 0 else 0,
        "fold_metrics": fold_metrics,
        # 합성 데이터 특성 안내
        "synthetic_data_note": (
            "합성 데이터 학습 결과입니다. 피처 생성 시 미래 부도 정보(months_to_def)가 "
            "risk_factor를 통해 재무/행동/외부 신호에 반영되어 있어 AUROC가 높게 나타납니다. "
            "실제 금융기관 데이터 기반 EWS 모델의 기대 AUROC는 0.80~0.88 수준입니다."
        ),
    }


@router.get("/confusion")
def get_confusion_matrix(db: Session = Depends(get_db)):
    """혼동행렬: 6개월 선행 EWS D등급 예측 vs 실제 부도 여부

    demo_monthly_signal 레코드는 default_ym - 1 까지만 존재하므로
    마지막 월(202512)이 아닌 '6개월 후 부도 기업이 가장 많은 월'을 기준월로 선택.
    """
    # 6개월 lookahead 윈도우에서 부도 기업이 가장 많은 reference month 자동 선택
    best_ref = db.execute(text("""
        SELECT s.ym, COUNT(*) as future_def_cnt
        FROM demo_monthly_signal s
        JOIN demo_company c ON s.borrower_id = c.borrower_id
        WHERE c.scenario = 'DEFAULT'
          AND c.default_ym > s.ym
          AND c.default_ym <= s.ym + 6
        GROUP BY s.ym
        ORDER BY future_def_cnt DESC
        LIMIT 1
    """)).fetchone()

    if best_ref:
        ref_ym = best_ref[0]
    else:
        # fallback: latest month
        ref_ym = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()[0]

    # 기준월 전체 기업 대상 confusion matrix
    # predicted = EWS D등급
    # actual = 향후 6개월 내 부도 (default_ym in [ref_ym+1, ref_ym+6])
    rows = db.execute(text("""
        SELECT
            CASE WHEN s.ews_grade = 'D' THEN 1 ELSE 0 END as predicted_default,
            CASE WHEN c.scenario = 'DEFAULT'
                      AND c.default_ym > :ym
                      AND c.default_ym <= :ym + 6
                 THEN 1 ELSE 0 END as actual_default
        FROM demo_monthly_signal s
        JOIN demo_company c ON s.borrower_id = c.borrower_id
        WHERE s.ym = :ym
    """), {"ym": ref_ym}).fetchall()

    tp = sum(1 for r in rows if r[0] == 1 and r[1] == 1)
    fp = sum(1 for r in rows if r[0] == 1 and r[1] == 0)
    fn = sum(1 for r in rows if r[0] == 0 and r[1] == 1)
    tn = sum(1 for r in rows if r[0] == 0 and r[1] == 0)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "ym": ref_ym,
        "ym_note": f"기준월 {ref_ym} (향후 6개월 내 부도 기업 최다 구간)",
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "total": len(rows),
    }


@router.get("/lead-time")
def get_lead_time(db: Session = Depends(get_db)):
    """부도 전 EWS 경보 선행 시간 분석"""
    rows = db.execute(text("""
        SELECT a.borrower_id, a.first_signal_ym, a.default_ym, a.lead_months, a.notes
        FROM demo_answer_key a
        WHERE a.lead_months IS NOT NULL
        ORDER BY a.lead_months DESC
    """)).fetchall()

    if not rows:
        return {
            "avg_lead_months": 0,
            "median_lead_months": 0,
            "min_lead_months": 0,
            "max_lead_months": 0,
            "total_defaulted": 0,
            "distribution": [],
        }

    lead_months = [r[3] for r in rows if r[3] is not None]
    avg_lead = sum(lead_months) / len(lead_months)
    sorted_lead = sorted(lead_months)
    n = len(sorted_lead)
    median_lead = (
        sorted_lead[n // 2]
        if n % 2 == 1
        else (sorted_lead[n // 2 - 1] + sorted_lead[n // 2]) / 2
    )

    dist_map: dict = {}
    for lm in lead_months:
        dist_map[str(lm)] = dist_map.get(str(lm), 0) + 1

    distribution = sorted(
        [{"lead_months": int(k), "count": v} for k, v in dist_map.items()],
        key=lambda x: x["lead_months"],
    )

    detail = [
        {
            "borrower_id": r[0],
            "first_signal_ym": r[1],
            "default_ym": r[2],
            "lead_months": r[3],
            "notes": r[4],
        }
        for r in rows[:50]
    ]

    return {
        "avg_lead_months": round(avg_lead, 1),
        "median_lead_months": round(float(median_lead), 1),
        "min_lead_months": min(lead_months),
        "max_lead_months": max(lead_months),
        "total_defaulted": len(lead_months),
        "distribution": distribution,
        "detail": detail,
    }


@router.get("/tier-models")
def get_tier_models():
    """T1/T2/T3 Tier 별 모델 메타데이터 조회"""
    result = {}
    for tier_key in ["t1", "t2", "t3"]:
        meta = _load_tier_model_meta(tier_key)
        if meta:
            result[tier_key] = meta
        else:
            result[tier_key] = {
                "tier": tier_key.upper(),
                "tier_label": {"t1": "T1 — 대기업", "t2": "T2 — 중소·중견기업", "t3": "T3 — 소기업"}[tier_key],
                "file_exists": False,
                "avg_auroc": 0.0,
                "avg_ks": 0.0,
                "avg_ap": 0.0,
            }
    return result


class RetainRequest(BaseModel):
    tier: str       # "champion" | "t1" | "t2" | "t3"
    password: str


@router.post("/retrain")
def retrain_model(req: RetainRequest):
    """모델 재학습 (관리자 전용)"""
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="관리자 비밀번호가 올바르지 않습니다.")

    valid_tiers = ["champion", "t1", "t2", "t3"]
    if req.tier not in valid_tiers:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 tier: {req.tier}")

    # Tier별 실제 재학습: train_tier.py 실행
    script_path = _BASE / "ml" / "train_tier.py"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail="재학습 스크립트를 찾을 수 없습니다.")

    db_path = _BASE / "data_pipeline" / "ews_corporate_v24.db"
    if not db_path.exists():
        raise HTTPException(
            status_code=500,
            detail="학습 DB(ews_corporate_v24.db)를 찾을 수 없습니다. 전체 학습 DB가 필요합니다."
        )

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=900,   # T1/T2/T3 전체 약 4~5분 소요
            cwd=str(script_path.parent),
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"재학습 실패: {result.stderr[:500]}"
            )

        # 결과 확인
        models_created = []
        for tier_key in ["t1", "t2", "t3"]:
            pkl = _MODEL_DIR / f"lgbm_{tier_key}.pkl"
            if pkl.exists():
                models_created.append(tier_key.upper())

        return {
            "success": True,
            "tier": req.tier,
            "models_created": models_created,
            "message": (
                f"Tier별 재학습 완료: {', '.join(models_created)} 모델 갱신됨. "
                "Walk-Forward 12-Fold 검증 결과가 반영되었습니다."
            ),
            "stdout": result.stdout[-800:] if result.stdout else "",
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="재학습 시간 초과 (900초). 서버에서 백그라운드 실행을 권장합니다.")
