"""
EWS 경보 액션 관리 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..core.database import get_db

router = APIRouter(prefix="/api/ews-action", tags=["EWSAction"])


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """액션 전체 요약"""
    row = db.execute(text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) as open_cnt,
            SUM(CASE WHEN status='IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status='WAIVED' THEN 1 ELSE 0 END) as waived
        FROM demo_ews_action
    """)).fetchone()

    total     = row[0] or 0
    completed = row[3] or 0
    comp_pct  = round(completed / total * 100, 1) if total > 0 else 0.0

    by_type = db.execute(text("""
        SELECT action_type, COUNT(*) as cnt
        FROM demo_ews_action
        GROUP BY action_type
        ORDER BY cnt DESC
    """)).fetchall()

    by_grade = db.execute(text("""
        SELECT ews_grade, COUNT(*) as cnt
        FROM demo_ews_action
        GROUP BY ews_grade
        ORDER BY ews_grade
    """)).fetchall()

    return {
        "total": total,
        "open": row[1] or 0,
        "in_progress": row[2] or 0,
        "completed": completed,
        "waived": row[4] or 0,
        "completion_pct": comp_pct,
        "by_type": [{"action_type": r[0], "count": r[1]} for r in by_type],
        "by_grade": [{"grade": r[0], "count": r[1]} for r in by_grade],
    }


@router.get("/list")
def get_list(
    ym: Optional[int] = Query(None),
    grade: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    rm_id: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db)
):
    """액션 목록 (필터링)"""
    conditions = ["1=1"]
    params: dict = {}

    if ym:
        conditions.append("a.ym = :ym")
        params["ym"] = ym
    if grade:
        conditions.append("a.ews_grade = :grade")
        params["grade"] = grade
    if status:
        conditions.append("a.status = :status")
        params["status"] = status
    if rm_id:
        conditions.append("a.rm_id = :rm_id")
        params["rm_id"] = rm_id
    if region:
        conditions.append("c.region = :region")
        params["region"] = region

    where = " AND ".join(conditions)
    params["limit"] = limit

    rows = db.execute(text(f"""
        SELECT a.action_id, a.borrower_id, c.company_name, a.ym, a.ews_grade,
               a.action_type, a.action_date, a.rm_id, r.rm_name, a.status, a.due_date, a.note
        FROM demo_ews_action a
        JOIN demo_company c ON a.borrower_id = c.borrower_id
        LEFT JOIN demo_rm r ON a.rm_id = r.rm_id
        WHERE {where}
        ORDER BY a.action_date DESC
        LIMIT :limit
    """), params).fetchall()

    return [
        {
            "action_id": r[0],
            "borrower_id": r[1],
            "company_name": r[2],
            "ym": r[3],
            "ews_grade": r[4],
            "action_type": r[5],
            "action_date": r[6],
            "rm_id": r[7],
            "rm_name": r[8],
            "status": r[9],
            "due_date": r[10],
            "note": r[11],
        }
        for r in rows
    ]


@router.get("/by-company/{borrower_id}")
def get_by_company(borrower_id: str, db: Session = Depends(get_db)):
    """특정 기업의 액션 이력"""
    rows = db.execute(text("""
        SELECT a.action_id, a.borrower_id, a.ym, a.ews_grade,
               a.action_type, a.action_date, a.rm_id, r.rm_name,
               a.status, a.due_date, a.note
        FROM demo_ews_action a
        LEFT JOIN demo_rm r ON a.rm_id = r.rm_id
        WHERE a.borrower_id = :bid
        ORDER BY a.action_date DESC
    """), {"bid": borrower_id}).fetchall()

    return [
        {
            "action_id": r[0],
            "borrower_id": r[1],
            "ym": r[2],
            "ews_grade": r[3],
            "action_type": r[4],
            "action_date": r[5],
            "rm_id": r[6],
            "rm_name": r[7],
            "status": r[8],
            "due_date": r[9],
            "note": r[10],
        }
        for r in rows
    ]
