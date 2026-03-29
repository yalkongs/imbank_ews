"""
포트폴리오 분석 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])


@router.get("/summary")
def get_portfolio_summary(db: Session = Depends(get_db)):
    """포트폴리오 요약"""
    total_row = db.execute(text("""
        SELECT COUNT(*) as cnt,
               COALESCE(SUM(outstanding_amount_억), 0) as total_outstanding,
               COALESCE(SUM(committed_amount_억), 0) as total_committed
        FROM demo_facility
    """)).fetchone()

    by_size = db.execute(text("""
        SELECT c.firm_size_cd, COUNT(DISTINCT f.borrower_id) as borrower_cnt,
               COALESCE(SUM(f.outstanding_amount_억), 0) as amount
        FROM demo_facility f
        JOIN demo_company c ON f.borrower_id = c.borrower_id
        GROUP BY c.firm_size_cd
        ORDER BY amount DESC
    """)).fetchall()

    by_industry = db.execute(text("""
        SELECT c.industry_cd, COUNT(DISTINCT f.borrower_id) as borrower_cnt,
               COALESCE(SUM(f.outstanding_amount_억), 0) as amount
        FROM demo_facility f
        JOIN demo_company c ON f.borrower_id = c.borrower_id
        GROUP BY c.industry_cd
        ORDER BY amount DESC
    """)).fetchall()

    by_facility_type = db.execute(text("""
        SELECT facility_type, COUNT(*) as cnt,
               COALESCE(SUM(outstanding_amount_억), 0) as amount
        FROM demo_facility
        GROUP BY facility_type
        ORDER BY amount DESC
    """)).fetchall()

    return {
        "total_facilities": total_row[0] if total_row else 0,
        "total_outstanding_억": round(float(total_row[1]), 1) if total_row and total_row[1] else 0,
        "total_committed_억": round(float(total_row[2]), 1) if total_row and total_row[2] else 0,
        "by_firm_size": [
            {
                "firm_size_cd": r[0],
                "borrower_count": r[1],
                "outstanding_억": round(float(r[2]), 1)
            }
            for r in by_size
        ],
        "by_industry": [
            {
                "industry_cd": r[0],
                "borrower_count": r[1],
                "outstanding_억": round(float(r[2]), 1)
            }
            for r in by_industry
        ],
        "by_facility_type": [
            {
                "facility_type": r[0],
                "count": r[1],
                "outstanding_억": round(float(r[2]), 1)
            }
            for r in by_facility_type
        ]
    }


@router.get("/concentration")
def get_concentration(db: Session = Depends(get_db)):
    """업종별 여신 집중도 (HHI)"""
    rows = db.execute(text("""
        SELECT c.industry_cd,
               COALESCE(SUM(f.outstanding_amount_억), 0) as amount
        FROM demo_facility f
        JOIN demo_company c ON f.borrower_id = c.borrower_id
        GROUP BY c.industry_cd
        ORDER BY amount DESC
    """)).fetchall()

    total = sum(float(r[1]) for r in rows) or 1.0
    items = [{"industry_cd": r[0], "amount_억": round(float(r[1]), 1), "share_pct": round(float(r[1]) / total * 100, 2)} for r in rows]
    hhi = sum((item["share_pct"] ** 2) for item in items)

    return {
        "hhi": round(hhi, 1),
        "items": items
    }


@router.get("/ecl-summary")
def get_ecl_summary(db: Session = Depends(get_db)):
    """ECL 요약 (Stage별)"""
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_ecl")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    rows = db.execute(text("""
        SELECT stage, COUNT(*) as cnt,
               COALESCE(SUM(ecl_amount_억), 0) as total_ecl,
               COALESCE(SUM(ead_억), 0) as total_ead
        FROM demo_ecl
        WHERE ym = :ym
        GROUP BY stage
        ORDER BY stage
    """), {"ym": latest_ym}).fetchall()

    total_ecl = sum(float(r[2]) for r in rows)

    return {
        "latest_ym": latest_ym,
        "total_ecl_억": round(total_ecl, 2),
        "by_stage": [
            {
                "stage": r[0],
                "count": r[1],
                "ecl_억": round(float(r[2]), 2),
                "ead_억": round(float(r[3]), 1)
            }
            for r in rows
        ]
    }
