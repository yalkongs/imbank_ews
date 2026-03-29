"""
RM 포트폴리오 관리 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db

router = APIRouter(prefix="/api/rm", tags=["RM"])


@router.get("/list")
def get_list(db: Session = Depends(get_db)):
    """RM 목록 + 관리 기업 수, 위험 기업 수"""
    rows = db.execute(text("""
        SELECT r.rm_id, r.rm_name, r.branch, r.team,
               COUNT(DISTINCT c.borrower_id) as total_companies
        FROM demo_rm r
        LEFT JOIN demo_company c ON r.rm_id = c.rm_id
        GROUP BY r.rm_id, r.rm_name, r.branch, r.team
        ORDER BY r.rm_id
    """)).fetchall()

    result = []
    for r in rows:
        rm_id = r[0]
        # 최신 월 기준 위험 기업 수
        alert_row = db.execute(text("""
            SELECT COUNT(DISTINCT s.borrower_id)
            FROM demo_monthly_signal s
            JOIN demo_company c ON s.borrower_id = c.borrower_id
            WHERE c.rm_id = :rm_id
              AND s.ym = (SELECT MAX(ym) FROM demo_monthly_signal)
              AND s.ews_grade IN ('C','D')
        """), {"rm_id": rm_id}).fetchone()
        result.append({
            "rm_id": rm_id,
            "rm_name": r[1],
            "branch": r[2],
            "team": r[3],
            "total_companies": r[4] or 0,
            "alert_companies": alert_row[0] if alert_row else 0,
        })
    return result


@router.get("/comparison")
def get_comparison(db: Session = Depends(get_db)):
    """전체 RM 성과 비교"""
    rows = db.execute(text("""
        SELECT r.rm_id, r.rm_name, r.branch, r.team,
               COUNT(DISTINCT c.borrower_id) as total_companies
        FROM demo_rm r
        LEFT JOIN demo_company c ON r.rm_id = c.rm_id
        GROUP BY r.rm_id
        ORDER BY r.rm_id
    """)).fetchall()

    result = []
    for r in rows:
        rm_id = r[0]
        alert_row = db.execute(text("""
            SELECT COUNT(DISTINCT s.borrower_id)
            FROM demo_monthly_signal s
            JOIN demo_company c ON s.borrower_id = c.borrower_id
            WHERE c.rm_id = :rm_id
              AND s.ym = (SELECT MAX(ym) FROM demo_monthly_signal)
              AND s.ews_grade IN ('C','D')
        """), {"rm_id": rm_id}).fetchone()

        act_row = db.execute(text("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END)
            FROM demo_ews_action WHERE rm_id = :rm_id
        """), {"rm_id": rm_id}).fetchone()
        act_total = act_row[0] or 0
        act_done  = act_row[1] or 0
        comp_pct  = round(act_done / act_total * 100, 1) if act_total > 0 else 0.0

        total_co = r[4] or 0
        alert_co = alert_row[0] if alert_row else 0
        risk_pct = round(alert_co / total_co * 100, 1) if total_co > 0 else 0.0

        result.append({
            "rm_id": rm_id,
            "rm_name": r[1],
            "branch": r[2],
            "team": r[3],
            "total_companies": total_co,
            "alert_companies": alert_co,
            "risk_ratio_pct": risk_pct,
            "action_completion_pct": comp_pct,
        })
    return result


@router.get("/{rm_id}/summary")
def get_summary(rm_id: str, db: Session = Depends(get_db)):
    """특정 RM 요약"""
    rm = db.execute(text("""
        SELECT rm_id, rm_name, branch, team FROM demo_rm WHERE rm_id = :rm_id
    """), {"rm_id": rm_id}).fetchone()
    if not rm:
        return {}

    # 기업/등급 집계
    grade_rows = db.execute(text("""
        SELECT s.ews_grade, COUNT(DISTINCT s.borrower_id)
        FROM demo_monthly_signal s
        JOIN demo_company c ON s.borrower_id = c.borrower_id
        WHERE c.rm_id = :rm_id
          AND s.ym = (SELECT MAX(ym) FROM demo_monthly_signal)
        GROUP BY s.ews_grade
    """), {"rm_id": rm_id}).fetchall()
    grade_map = {r[0]: r[1] for r in grade_rows}

    total_co = sum(grade_map.values())

    # 여신
    exp_row = db.execute(text("""
        SELECT SUM(f.outstanding_amount_억)
        FROM demo_facility f
        JOIN demo_company c ON f.borrower_id = c.borrower_id
        WHERE c.rm_id = :rm_id
    """), {"rm_id": rm_id}).fetchone()

    # ECL
    ecl_row = db.execute(text("""
        SELECT SUM(e.ecl_amount_억)
        FROM demo_ecl e
        JOIN demo_company c ON e.borrower_id = c.borrower_id
        WHERE c.rm_id = :rm_id
          AND e.ym = (SELECT MAX(ym) FROM demo_ecl)
    """), {"rm_id": rm_id}).fetchone()

    # 액션
    act_row = db.execute(text("""
        SELECT COUNT(*), SUM(CASE WHEN status IN ('OPEN','IN_PROGRESS') THEN 1 ELSE 0 END)
        FROM demo_ews_action WHERE rm_id = :rm_id
    """), {"rm_id": rm_id}).fetchone()

    return {
        "rm_id": rm[0],
        "rm_name": rm[1],
        "branch": rm[2],
        "team": rm[3],
        "total_companies": total_co,
        "total_exposure_억": round(float(exp_row[0] or 0), 1),
        "grade_a": grade_map.get("A", 0),
        "grade_b": grade_map.get("B", 0),
        "grade_c": grade_map.get("C", 0),
        "grade_d": grade_map.get("D", 0),
        "open_actions": act_row[1] or 0,
        "ecl_amount_억": round(float(ecl_row[0] or 0), 1),
    }


@router.get("/{rm_id}/portfolio")
def get_portfolio(rm_id: str, db: Session = Depends(get_db)):
    """특정 RM 담당 기업 목록"""
    rows = db.execute(text("""
        SELECT c.borrower_id, c.company_name, c.firm_size_cd, c.industry_cd,
               s.ews_grade, s.ews_score, f.total_outstanding
        FROM demo_company c
        LEFT JOIN (
            SELECT borrower_id, ews_grade, ews_score
            FROM demo_monthly_signal
            WHERE ym = (SELECT MAX(ym) FROM demo_monthly_signal)
        ) s ON c.borrower_id = s.borrower_id
        LEFT JOIN (
            SELECT borrower_id, SUM(outstanding_amount_억) as total_outstanding
            FROM demo_facility GROUP BY borrower_id
        ) f ON c.borrower_id = f.borrower_id
        WHERE c.rm_id = :rm_id
        ORDER BY s.ews_score ASC
    """), {"rm_id": rm_id}).fetchall()

    return [
        {
            "borrower_id": r[0],
            "company_name": r[1],
            "firm_size_cd": r[2],
            "industry_cd": r[3],
            "ews_grade": r[4],
            "ews_score": round(float(r[5]), 1) if r[5] is not None else None,
            "total_outstanding_억": round(float(r[6] or 0), 1),
        }
        for r in rows
    ]
