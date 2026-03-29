"""
기업 통합 검색 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("/company")
def search_company(
    q: str = Query(""),
    region: str = Query(""),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """기업명/ID 검색 (지역 필터, 페이지네이션 지원)"""
    conditions = ["1=1"]
    params: dict = {"limit": limit, "offset": offset}

    if q:
        conditions.append("(c.company_name LIKE :q OR c.borrower_id LIKE :q)")
        params["q"] = f"%{q}%"

    if region:
        conditions.append("c.region = :region")
        params["region"] = region

    where = " AND ".join(conditions)

    rows = db.execute(text(f"""
        SELECT c.borrower_id, c.company_name, c.firm_size_cd, c.industry_cd,
               s.ews_grade, s.ews_score, c.default_ym, r.rm_name, c.region
        FROM demo_company c
        LEFT JOIN demo_rm r ON c.rm_id = r.rm_id
        LEFT JOIN (
            SELECT borrower_id, ews_grade, ews_score
            FROM demo_monthly_signal
            WHERE ym = (SELECT MAX(ym) FROM demo_monthly_signal)
        ) s ON c.borrower_id = s.borrower_id
        WHERE {where}
        ORDER BY COALESCE(s.ews_score, 999) ASC, c.company_name ASC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    total = db.execute(text(f"""
        SELECT COUNT(*) FROM demo_company c WHERE {where}
    """), count_params).fetchone()[0]

    results = [
        {
            "borrower_id": r[0],
            "company_name": r[1],
            "firm_size_cd": r[2],
            "industry_cd": r[3],
            "ews_grade": r[4],
            "ews_score": round(float(r[5]), 1) if r[5] is not None else None,
            "default_flag": r[6] is not None,
            "rm_name": r[7],
            "region": r[8],
        }
        for r in rows
    ]
    return {"results": results, "total": total, "has_more": offset + limit < total}
