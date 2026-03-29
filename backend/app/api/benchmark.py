"""
업종 평균 재무 비교 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..core.database import get_db

router = APIRouter(prefix="/api/benchmark", tags=["Benchmark"])

METRICS = [
    "debt_to_equity_ratio",
    "current_ratio",
    "interest_coverage_ratio",
    "dscr_ratio",
    "ebitda_margin_pct",
    "sales_growth_pct",
]


@router.get("/industry")
def get_industry(
    industry_cd: str = Query("K05"),
    ym: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """업종 평균 + 분위 지표"""
    if not ym:
        row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
        ym = row[0] if row[0] else 202512

    metrics_result = {}
    for metric in METRICS:
        row = db.execute(text(f"""
            SELECT AVG(s.{metric}),
                   MIN(s.{metric}),
                   MAX(s.{metric})
            FROM demo_monthly_signal s
            JOIN demo_company c ON s.borrower_id = c.borrower_id
            WHERE c.industry_cd = :ind AND s.ym = :ym
              AND s.{metric} IS NOT NULL
        """), {"ind": industry_cd, "ym": ym}).fetchone()

        # SQLite에 percentile 없어 min/max로 대신
        rows_sorted = db.execute(text(f"""
            SELECT s.{metric}
            FROM demo_monthly_signal s
            JOIN demo_company c ON s.borrower_id = c.borrower_id
            WHERE c.industry_cd = :ind AND s.ym = :ym
              AND s.{metric} IS NOT NULL
            ORDER BY s.{metric}
        """), {"ind": industry_cd, "ym": ym}).fetchall()

        vals = [float(r[0]) for r in rows_sorted]
        n = len(vals)
        p25 = vals[n // 4] if n > 3 else (vals[0] if vals else 0)
        p75 = vals[3 * n // 4] if n > 3 else (vals[-1] if vals else 0)
        avg = float(row[0]) if row[0] is not None else 0.0

        metrics_result[metric] = {
            "industry_avg": round(avg, 2),
            "industry_p25": round(p25, 2),
            "industry_p75": round(p75, 2),
        }

    return {
        "industry_cd": industry_cd,
        "ym": ym,
        "metrics": metrics_result,
    }


@router.get("/company/{borrower_id}")
def get_company(
    borrower_id: str,
    ym: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """특정 기업 재무비율 + 업종 평균 비교"""
    if not ym:
        row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
        ym = row[0] if row[0] else 202512

    comp = db.execute(text("""
        SELECT industry_cd, company_name FROM demo_company WHERE borrower_id = :bid
    """), {"bid": borrower_id}).fetchone()

    if not comp:
        return {}

    industry_cd = comp[0]
    company_name = comp[1]

    sig = db.execute(text("""
        SELECT debt_to_equity_ratio, current_ratio, interest_coverage_ratio,
               dscr_ratio, ebitda_margin_pct, sales_growth_pct
        FROM demo_monthly_signal
        WHERE borrower_id = :bid AND ym = :ym
    """), {"bid": borrower_id, "ym": ym}).fetchone()

    company_values = {}
    if sig:
        for i, metric in enumerate(METRICS):
            company_values[metric] = round(float(sig[i]), 2) if sig[i] is not None else None

    # 업종 평균
    metrics_result = {}
    for metric in METRICS:
        row = db.execute(text(f"""
            SELECT AVG(s.{metric})
            FROM demo_monthly_signal s
            JOIN demo_company c ON s.borrower_id = c.borrower_id
            WHERE c.industry_cd = :ind AND s.ym = :ym
              AND s.{metric} IS NOT NULL
        """), {"ind": industry_cd, "ym": ym}).fetchone()
        avg = round(float(row[0]), 2) if row[0] is not None else 0.0
        metrics_result[metric] = {
            "company_value": company_values.get(metric),
            "industry_avg": avg,
        }

    return {
        "borrower_id": borrower_id,
        "company_name": company_name,
        "industry_cd": industry_cd,
        "ym": ym,
        "metrics": metrics_result,
    }
