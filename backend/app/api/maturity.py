"""
만기 도래 여신 관리 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..core.database import get_db

router = APIRouter(prefix="/api/maturity", tags=["Maturity"])


def _ym_add(ym: int, months: int) -> int:
    y, m = divmod(ym, 100)
    m += months
    while m > 12:
        m -= 12
        y += 1
    return y * 100 + m


@router.get("/calendar")
def get_calendar(ref_ym: int = Query(202512), db: Session = Depends(get_db)):
    """만기 도래 여신 (30/60/90/180일 버킷)"""
    buckets = {30: 1, 60: 2, 90: 3, 180: 6}
    result = {}

    for days, months in buckets.items():
        ym_from = _ym_add(ref_ym, 1)
        ym_to   = _ym_add(ref_ym, months)

        rows = db.execute(text("""
            SELECT f.borrower_id, c.company_name, f.facility_type,
                   f.outstanding_amount_억, f.maturity_ym,
                   s.ews_grade, c.rm_id, r.rm_name
            FROM demo_facility f
            JOIN demo_company c ON f.borrower_id = c.borrower_id
            LEFT JOIN demo_rm r ON c.rm_id = r.rm_id
            LEFT JOIN (
                SELECT borrower_id, ews_grade
                FROM demo_monthly_signal
                WHERE ym = (SELECT MAX(ym) FROM demo_monthly_signal)
            ) s ON f.borrower_id = s.borrower_id
            WHERE f.maturity_ym >= :ym_from AND f.maturity_ym <= :ym_to
            ORDER BY f.maturity_ym ASC
        """), {"ym_from": ym_from, "ym_to": ym_to}).fetchall()

        result[f"within_{days}"] = [
            {
                "borrower_id": r[0],
                "company_name": r[1],
                "facility_type": r[2],
                "outstanding_amount_억": round(float(r[3] or 0), 1),
                "maturity_ym": r[4],
                "ews_grade": r[5],
                "rm_id": r[6],
                "rm_name": r[7],
            }
            for r in rows
        ]

    return result


@router.get("/heatmap")
def get_heatmap(ref_ym: int = Query(202512), db: Session = Depends(get_db)):
    """향후 12개월 만기 분포"""
    ym_from = _ym_add(ref_ym, 1)
    ym_to   = _ym_add(ref_ym, 12)

    rows = db.execute(text("""
        SELECT maturity_ym, COUNT(*) as cnt, SUM(outstanding_amount_억) as amt
        FROM demo_facility
        WHERE maturity_ym >= :ym_from AND maturity_ym <= :ym_to
        GROUP BY maturity_ym
        ORDER BY maturity_ym
    """), {"ym_from": ym_from, "ym_to": ym_to}).fetchall()

    return [
        {
            "ym": r[0],
            "count": r[1],
            "amount_억": round(float(r[2] or 0), 1),
        }
        for r in rows
    ]


@router.get("/summary")
def get_summary(ref_ym: int = Query(202512), db: Session = Depends(get_db)):
    """만기 도래 요약 수치"""
    result = {}
    for days, months in [(30, 1), (60, 2), (90, 3)]:
        ym_from = _ym_add(ref_ym, 1)
        ym_to   = _ym_add(ref_ym, months)
        row = db.execute(text("""
            SELECT COUNT(*), SUM(outstanding_amount_억)
            FROM demo_facility
            WHERE maturity_ym >= :ym_from AND maturity_ym <= :ym_to
        """), {"ym_from": ym_from, "ym_to": ym_to}).fetchone()
        result[f"within_{days}_cnt"] = row[0] or 0
        result[f"within_{days}_amt"] = round(float(row[1] or 0), 1)
    return result
