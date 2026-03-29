"""
NPL/Workout 관리 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db

router = APIRouter(prefix="/api/workout", tags=["Workout"])


@router.get("/summary")
def get_workout_summary(db: Session = Depends(get_db)):
    """Workout 요약"""
    total_row = db.execute(text("SELECT COUNT(*) FROM demo_workout")).fetchone()
    avg_recovery_row = db.execute(text("""
        SELECT AVG(recovery_rate) FROM demo_workout WHERE recovery_rate IS NOT NULL
    """)).fetchone()

    by_type = db.execute(text("""
        SELECT workout_type, COUNT(*) as cnt,
               AVG(recovery_rate) as avg_rec,
               COALESCE(SUM(original_balance_억), 0) as total_balance
        FROM demo_workout
        GROUP BY workout_type
        ORDER BY cnt DESC
    """)).fetchall()

    by_outcome = db.execute(text("""
        SELECT outcome, COUNT(*) as cnt
        FROM demo_workout
        GROUP BY outcome
        ORDER BY cnt DESC
    """)).fetchall()

    return {
        "total_cases": total_row[0] if total_row else 0,
        "avg_recovery_rate": round(float(avg_recovery_row[0]), 3) if avg_recovery_row and avg_recovery_row[0] is not None else 0,
        "by_type": [
            {
                "workout_type": r[0],
                "count": r[1],
                "avg_recovery_rate": round(float(r[2]), 3) if r[2] is not None else 0,
                "total_balance_억": round(float(r[3]), 1)
            }
            for r in by_type
        ],
        "by_outcome": [
            {"outcome": r[0], "count": r[1]}
            for r in by_outcome
        ]
    }


@router.get("/list")
def get_workout_list(db: Session = Depends(get_db)):
    """Workout 전체 목록 (기업명 포함)"""
    rows = db.execute(text("""
        SELECT w.workout_id, w.borrower_id, c.company_name, w.workout_type,
               w.workout_start_ym, w.original_balance_억, w.recovery_rate, w.outcome,
               c.firm_size_cd, c.industry_cd
        FROM demo_workout w
        JOIN demo_company c ON w.borrower_id = c.borrower_id
        ORDER BY w.workout_start_ym DESC
    """)).fetchall()

    return [
        {
            "workout_id": r[0],
            "borrower_id": r[1],
            "company_name": r[2],
            "workout_type": r[3],
            "workout_start_ym": r[4],
            "original_balance_억": round(float(r[5]), 1) if r[5] is not None else 0,
            "recovery_rate": round(float(r[6]), 3) if r[6] is not None else 0,
            "outcome": r[7],
            "firm_size_cd": r[8],
            "industry_cd": r[9]
        }
        for r in rows
    ]


@router.get("/recovery-trend")
def get_recovery_trend(db: Session = Depends(get_db)):
    """Workout 유형별 회수율 분석"""
    rows = db.execute(text("""
        SELECT workout_type, outcome, AVG(recovery_rate) as avg_rec,
               COUNT(*) as cnt,
               COALESCE(SUM(original_balance_억), 0) as total_balance
        FROM demo_workout
        GROUP BY workout_type, outcome
        ORDER BY workout_type, outcome
    """)).fetchall()

    return [
        {
            "workout_type": r[0],
            "outcome": r[1],
            "avg_recovery_rate": round(float(r[2]), 3) if r[2] is not None else 0,
            "count": r[3],
            "total_balance_억": round(float(r[4]), 1)
        }
        for r in rows
    ]


@router.get("/scenarios/{workout_id}")
def get_workout_scenarios(workout_id: str, db: Session = Depends(get_db)):
    """특정 Workout 건의 3가지 회수 시나리오 (낙관/기본/비관)"""
    rows = db.execute(text("""
        SELECT scenario_id, workout_id, borrower_id, scenario_type, recovery_method,
               recovery_amount_억, recovery_timeline_months, discount_rate,
               npv_억, irr_pct, probability_pct
        FROM demo_recovery_scenario
        WHERE workout_id = :wid
        ORDER BY CASE scenario_type WHEN 'OPTIMISTIC' THEN 1 WHEN 'BASE' THEN 2 ELSE 3 END
    """), {"wid": workout_id}).fetchall()

    scenarios = [
        {
            "scenario_id": r[0],
            "workout_id": r[1],
            "borrower_id": r[2],
            "scenario_type": r[3],
            "recovery_method": r[4],
            "recovery_amount_억": round(float(r[5]), 2) if r[5] is not None else 0,
            "recovery_timeline_months": r[6],
            "discount_rate": round(float(r[7]), 4) if r[7] is not None else 0,
            "npv_억": round(float(r[8]), 3) if r[8] is not None else 0,
            "irr_pct": round(float(r[9]), 2) if r[9] is not None else 0,
            "probability_pct": round(float(r[10]), 1) if r[10] is not None else 0,
        }
        for r in rows
    ]

    # 가중평균 기대회수액
    weighted = sum(s["recovery_amount_억"] * s["probability_pct"] / 100.0 for s in scenarios)

    return {
        "workout_id": workout_id,
        "scenarios": scenarios,
        "weighted_expected_recovery_억": round(weighted, 3)
    }


@router.get("/scenario-summary")
def get_scenario_summary(db: Session = Depends(get_db)):
    """Workout 유형별 시나리오 집계 분석"""
    rows = db.execute(text("""
        SELECT
            recovery_method,
            COUNT(DISTINCT workout_id) as cnt,
            COALESCE(SUM(CASE WHEN scenario_type='OPTIMISTIC' THEN recovery_amount_억 END), 0) as opt_total,
            COALESCE(SUM(CASE WHEN scenario_type='BASE'       THEN recovery_amount_억 END), 0) as base_total,
            COALESCE(SUM(CASE WHEN scenario_type='PESSIMISTIC'THEN recovery_amount_억 END), 0) as pess_total,
            COALESCE(SUM(recovery_amount_억 * probability_pct / 100.0), 0) as weighted_total,
            COALESCE(AVG(CASE WHEN scenario_type='BASE' THEN npv_억 END), 0) as avg_npv
        FROM demo_recovery_scenario
        GROUP BY recovery_method
        ORDER BY cnt DESC
    """)).fetchall()

    by_method = [
        {
            "method": r[0],
            "count": r[1],
            "optimistic_recovery": round(float(r[2]), 2),
            "base_recovery": round(float(r[3]), 2),
            "pessimistic_recovery": round(float(r[4]), 2),
            "weighted_expected": round(float(r[5]), 2),
            "avg_npv": round(float(r[6]), 3),
        }
        for r in rows
    ]

    totals_row = db.execute(text("""
        SELECT
            COALESCE(SUM(CASE WHEN scenario_type='OPTIMISTIC'  THEN recovery_amount_억 END), 0),
            COALESCE(SUM(CASE WHEN scenario_type='BASE'        THEN recovery_amount_억 END), 0),
            COALESCE(SUM(CASE WHEN scenario_type='PESSIMISTIC' THEN recovery_amount_억 END), 0),
            COALESCE(SUM(recovery_amount_억 * probability_pct / 100.0), 0)
        FROM demo_recovery_scenario
    """)).fetchone()

    return {
        "by_method": by_method,
        "total_optimistic": round(float(totals_row[0]), 2),
        "total_base": round(float(totals_row[1]), 2),
        "total_pessimistic": round(float(totals_row[2]), 2),
        "total_weighted_recovery": round(float(totals_row[3]), 2),
    }
