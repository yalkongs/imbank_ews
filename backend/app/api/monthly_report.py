"""
월간 EWS 보고서 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..core.database import get_db

router = APIRouter(prefix="/api/monthly-report", tags=["MonthlyReport"])


def _ym_add(ym: int, months: int) -> int:
    y, m = divmod(ym, 100)
    m += months
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    return y * 100 + m


@router.get("/summary")
def get_summary(ym: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """특정 월 EWS 보고서 요약 (전월 비교 포함)"""
    if not ym:
        row = db.execute(text("SELECT MAX(report_ym) FROM demo_monthly_report")).fetchone()
        ym = row[0] if row[0] else 202512

    cur = db.execute(text("""
        SELECT report_ym, total_companies, grade_a_cnt, grade_b_cnt,
               grade_c_cnt, grade_d_cnt, upgraded_cnt, downgraded_cnt,
               new_alert_cnt, resolved_alert_cnt,
               total_exposure_억, alert_exposure_억, action_completion_pct
        FROM demo_monthly_report WHERE report_ym = :ym
    """), {"ym": ym}).fetchone()

    if not cur:
        return {}

    prev_ym = _ym_add(ym, -1)
    prev = db.execute(text("""
        SELECT grade_a_cnt, grade_b_cnt, grade_c_cnt, grade_d_cnt, alert_exposure_억
        FROM demo_monthly_report WHERE report_ym = :ym
    """), {"ym": prev_ym}).fetchone()

    def safe(v):
        return float(v) if v is not None else 0.0

    return {
        "report_ym": cur[0],
        "total_companies": cur[1],
        "grade_a_cnt": cur[2],
        "grade_b_cnt": cur[3],
        "grade_c_cnt": cur[4],
        "grade_d_cnt": cur[5],
        "upgraded_cnt": cur[6],
        "downgraded_cnt": cur[7],
        "new_alert_cnt": cur[8],
        "resolved_alert_cnt": cur[9],
        "total_exposure_억": safe(cur[10]),
        "alert_exposure_억": safe(cur[11]),
        "action_completion_pct": safe(cur[12]),
        "prev": {
            "grade_a_cnt": prev[0] if prev else None,
            "grade_b_cnt": prev[1] if prev else None,
            "grade_c_cnt": prev[2] if prev else None,
            "grade_d_cnt": prev[3] if prev else None,
            "alert_exposure_억": safe(prev[4]) if prev else None,
        }
    }


@router.get("/grade-change")
def get_grade_change(ym: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """전월 대비 등급 변동 기업 목록"""
    if not ym:
        row = db.execute(text("SELECT MAX(report_ym) FROM demo_monthly_report")).fetchone()
        ym = row[0] if row[0] else 202512

    prev_ym = _ym_add(ym, -1)

    rows = db.execute(text("""
        SELECT c.ym, p.ym, c.borrower_id, comp.company_name,
               p.ews_grade as prev_grade, c.ews_grade as cur_grade
        FROM demo_monthly_signal c
        JOIN demo_monthly_signal p ON c.borrower_id = p.borrower_id AND p.ym = :prev_ym
        JOIN demo_company comp ON c.borrower_id = comp.borrower_id
        WHERE c.ym = :ym AND c.ews_grade != p.ews_grade
        ORDER BY c.ews_grade, comp.company_name
        LIMIT 200
    """), {"ym": ym, "prev_ym": prev_ym}).fetchall()

    grade_order = {"A": 3, "B": 2, "C": 1, "D": 0}
    upgraded, downgraded = [], []
    for r in rows:
        cur_g  = r[5]
        prev_g = r[4]
        item = {
            "borrower_id": r[2],
            "company_name": r[3],
            "prev_grade": prev_g,
            "cur_grade": cur_g,
        }
        if grade_order.get(cur_g, 0) > grade_order.get(prev_g, 0):
            upgraded.append(item)
        else:
            downgraded.append(item)

    return {"ym": ym, "prev_ym": prev_ym, "upgraded": upgraded, "downgraded": downgraded}


@router.get("/trend")
def get_trend(db: Session = Depends(get_db)):
    """등급 분포 추이 (전체 월)"""
    rows = db.execute(text("""
        SELECT report_ym, grade_a_cnt, grade_b_cnt, grade_c_cnt, grade_d_cnt,
               downgraded_cnt, alert_exposure_억
        FROM demo_monthly_report
        ORDER BY report_ym
    """)).fetchall()

    return [
        {
            "ym": r[0],
            "grade_a_cnt": r[1],
            "grade_b_cnt": r[2],
            "grade_c_cnt": r[3],
            "grade_d_cnt": r[4],
            "downgraded_cnt": r[5],
            "alert_exposure_억": round(float(r[6] or 0), 1),
        }
        for r in rows
    ]
