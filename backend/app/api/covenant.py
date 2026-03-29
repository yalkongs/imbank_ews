"""
코베넌트 모니터링 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db

router = APIRouter(prefix="/api/covenant", tags=["Covenant"])


@router.get("/summary")
def get_covenant_summary(db: Session = Depends(get_db)):
    """코베넌트 위반 요약"""
    total_row = db.execute(text("SELECT COUNT(*) FROM demo_covenant")).fetchone()
    breach_row = db.execute(text("SELECT COUNT(*) FROM demo_covenant WHERE result = 'BREACH'")).fetchone()
    waived_row = db.execute(text("SELECT COUNT(*) FROM demo_covenant WHERE result = 'WAIVED'")).fetchone()

    total = total_row[0] if total_row else 1
    breach_count = breach_row[0] if breach_row else 0
    waived_count = waived_row[0] if waived_row else 0

    by_type = db.execute(text("""
        SELECT covenant_type, result, COUNT(*) as cnt
        FROM demo_covenant
        GROUP BY covenant_type, result
        ORDER BY covenant_type
    """)).fetchall()

    type_map: dict = {}
    for r in by_type:
        ctype = r[0]
        if ctype not in type_map:
            type_map[ctype] = {"covenant_type": ctype, "total": 0, "breach": 0, "pass": 0, "waived": 0}
        type_map[ctype]["total"] += r[2]
        if r[1] == "BREACH":
            type_map[ctype]["breach"] = r[2]
        elif r[1] == "PASS":
            type_map[ctype]["pass"] = r[2]
        elif r[1] == "WAIVED":
            type_map[ctype]["waived"] = r[2]

    return {
        "total_checks": total,
        "breach_count": breach_count,
        "waived_count": waived_count,
        "breach_rate_pct": round(breach_count / total * 100, 2) if total > 0 else 0,
        "by_type": list(type_map.values())
    }


@router.get("/breaches")
def get_breaches(db: Session = Depends(get_db)):
    """최근 위반 목록"""
    rows = db.execute(text("""
        SELECT cv.id, cv.borrower_id, c.company_name, cv.check_ym,
               cv.covenant_type, cv.result, cv.actual_value, cv.threshold_value,
               c.firm_size_cd, c.industry_cd
        FROM demo_covenant cv
        JOIN demo_company c ON cv.borrower_id = c.borrower_id
        WHERE cv.result = 'BREACH'
        ORDER BY cv.check_ym DESC
        LIMIT 100
    """)).fetchall()

    return [
        {
            "id": r[0],
            "borrower_id": r[1],
            "company_name": r[2],
            "check_ym": r[3],
            "covenant_type": r[4],
            "result": r[5],
            "actual_value": round(float(r[6]), 3) if r[6] is not None else None,
            "threshold_value": round(float(r[7]), 3) if r[7] is not None else None,
            "firm_size_cd": r[8],
            "industry_cd": r[9]
        }
        for r in rows
    ]


@router.get("/trend")
def get_covenant_trend(db: Session = Depends(get_db)):
    """월별 코베넌트 위반율 추이"""
    rows = db.execute(text("""
        SELECT check_ym,
               COUNT(*) as total,
               SUM(CASE WHEN result = 'BREACH' THEN 1 ELSE 0 END) as breaches
        FROM demo_covenant
        GROUP BY check_ym
        ORDER BY check_ym
    """)).fetchall()

    return [
        {
            "ym": str(r[0]),
            "label": f"{str(r[0])[:4]}-{str(r[0])[4:]}",
            "total": r[1],
            "breaches": r[2],
            "breach_rate_pct": round(r[2] / r[1] * 100, 2) if r[1] > 0 else 0
        }
        for r in rows
    ]
