"""
EWS 경보센터 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..core.database import get_db

router = APIRouter(prefix="/api/ews", tags=["EWS"])


@router.get("/alerts")
def get_alerts(
    ym: Optional[int] = Query(None),
    grade: Optional[str] = Query(None),
    firm_size: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """EWS 경보 기업 목록 (필터링 가능)"""
    if not ym:
        latest_row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
        ym = latest_row[0] if latest_row else 202512

    conditions = ["s.ym = :ym"]
    params: dict = {"ym": ym}

    if grade:
        conditions.append("s.ews_grade = :grade")
        params["grade"] = grade
    else:
        conditions.append("s.ews_grade IN ('C', 'D')")

    if firm_size:
        conditions.append("c.firm_size_cd = :firm_size")
        params["firm_size"] = firm_size

    if industry:
        conditions.append("c.industry_cd = :industry")
        params["industry"] = industry

    if region:
        conditions.append("c.region = :region")
        params["region"] = region

    where_clause = " AND ".join(conditions)

    rows = db.execute(text(f"""
        SELECT s.borrower_id, c.company_name, s.ews_grade, s.ews_score,
               s.ifrs9_stage, s.principal_past_due_days, s.seizure_flag,
               s.lawsuit_count_12m, c.firm_size_cd, c.industry_cd, c.region,
               COALESCE(s.ews_tier, 2) as ews_tier,
               COALESCE(s.data_completeness_pct, 60.0) as data_completeness_pct
        FROM demo_monthly_signal s
        JOIN demo_company c ON s.borrower_id = c.borrower_id
        WHERE {where_clause}
        ORDER BY s.ews_score ASC
        LIMIT 200
    """), params).fetchall()

    TIER_LABEL = {1: "T1", 2: "T2", 3: "T3"}
    TIER_COLOR = {1: "text-green-700 bg-green-100", 2: "text-blue-700 bg-blue-100", 3: "text-gray-600 bg-gray-100"}

    return [
        {
            "borrower_id": r[0],
            "company_name": r[1],
            "ews_grade": r[2],
            "ews_score": round(float(r[3]), 1) if r[3] is not None else 0,
            "ifrs9_stage": r[4],
            "principal_past_due_days": r[5] or 0,
            "seizure_flag": r[6] or 0,
            "lawsuit_count_12m": r[7] or 0,
            "firm_size_cd": r[8],
            "industry_cd": r[9],
            "region": r[10],
            "ews_tier": r[11],
            "tier_label": TIER_LABEL.get(r[11], "T2"),
            "tier_color": TIER_COLOR.get(r[11], "text-blue-700 bg-blue-100"),
            "data_completeness_pct": round(float(r[12]), 1),
        }
        for r in rows
    ]


@router.get("/grade-distribution")
def get_grade_distribution(ym: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """특정 월 EWS 등급 분포"""
    if not ym:
        latest_row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
        ym = latest_row[0] if latest_row else 202512

    rows = db.execute(text("""
        SELECT ews_grade, COUNT(*) as cnt
        FROM demo_monthly_signal
        WHERE ym = :ym
        GROUP BY ews_grade
        ORDER BY ews_grade
    """), {"ym": ym}).fetchall()

    return [{"grade": r[0], "count": r[1]} for r in rows]


@router.get("/company/{borrower_id}/history")
def get_company_history(borrower_id: str, db: Session = Depends(get_db)):
    """기업 월별 EWS 신호 이력 (전체)"""
    rows = db.execute(text("""
        SELECT signal_id, borrower_id, ym, debt_to_equity_ratio, current_ratio,
               interest_coverage_ratio, dscr_ratio, ebitda_margin_pct, sales_growth_pct,
               limit_utilization_ratio, principal_past_due_days, covenant_breach_count_12m,
               avg_deposit_balance_억, inflow_outflow_ratio, ews_score, ews_grade,
               ifrs9_stage, industry_stress_score, news_sentiment_score,
               seizure_flag, lawsuit_count_12m, bankruptcy_filing_flag
        FROM demo_monthly_signal
        WHERE borrower_id = :bid
        ORDER BY ym
    """), {"bid": borrower_id}).fetchall()

    cols = [
        "signal_id", "borrower_id", "ym", "debt_to_equity_ratio", "current_ratio",
        "interest_coverage_ratio", "dscr_ratio", "ebitda_margin_pct", "sales_growth_pct",
        "limit_utilization_ratio", "principal_past_due_days", "covenant_breach_count_12m",
        "avg_deposit_balance_억", "inflow_outflow_ratio", "ews_score", "ews_grade",
        "ifrs9_stage", "industry_stress_score", "news_sentiment_score",
        "seizure_flag", "lawsuit_count_12m", "bankruptcy_filing_flag"
    ]

    def safe_float(v):
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            return v

    return [
        {cols[i]: (safe_float(v) if i not in (0, 1, 15, 16) else v) for i, v in enumerate(row)}
        for row in rows
    ]


@router.get("/company/{borrower_id}/profile")
def get_company_profile(borrower_id: str, db: Session = Depends(get_db)):
    """기업 프로필 + 현재 EWS 상태"""
    company = db.execute(text("""
        SELECT borrower_id, company_name, firm_size_cd, industry_cd,
               listed_flag, scenario, default_ym, recovery_ym
        FROM demo_company
        WHERE borrower_id = :bid
    """), {"bid": borrower_id}).fetchone()

    if not company:
        return {}

    latest_signal = db.execute(text("""
        SELECT ews_grade, ews_score, ifrs9_stage, ym
        FROM demo_monthly_signal
        WHERE borrower_id = :bid
        ORDER BY ym DESC LIMIT 1
    """), {"bid": borrower_id}).fetchone()

    return {
        "borrower_id": company[0],
        "company_name": company[1],
        "firm_size_cd": company[2],
        "industry_cd": company[3],
        "listed_flag": company[4],
        "scenario": company[5],
        "default_ym": company[6],
        "recovery_ym": company[7],
        "current_ews_grade": latest_signal[0] if latest_signal else None,
        "current_ews_score": round(float(latest_signal[1]), 1) if latest_signal and latest_signal[1] is not None else None,
        "current_ifrs9_stage": latest_signal[2] if latest_signal else None,
        "latest_ym": latest_signal[3] if latest_signal else None
    }
