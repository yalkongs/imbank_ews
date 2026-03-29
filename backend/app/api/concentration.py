"""
여신 집중도 한도 관리 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..core.database import get_db

router = APIRouter(prefix="/api/concentration", tags=["Concentration"])

INDUSTRY_NAMES = {
    "K00": "제조업", "K01A": "일반제조", "K01B": "첨단제조",
    "K02": "화학", "K03": "금속", "K04": "운수",
    "K05": "IT", "K07": "도소매", "K08": "금융",
    "K09": "숙박/음식", "K10": "건설", "K11": "부동산", "K13": "에너지",
}


@router.get("/status")
def get_status(ym: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """집중도 한도 현황"""
    total_row = db.execute(text(
        "SELECT SUM(outstanding_amount_억) FROM demo_facility"
    )).fetchone()
    total_exp = float(total_row[0] or 0)

    ind_rows = db.execute(text("""
        SELECT c.industry_cd, SUM(f.outstanding_amount_억) as exp
        FROM demo_facility f
        JOIN demo_company c ON f.borrower_id = c.borrower_id
        GROUP BY c.industry_cd
    """)).fetchall()

    limits = db.execute(text("""
        SELECT dimension_value, limit_pct, warning_pct
        FROM demo_concentration_limit WHERE dimension='INDUSTRY'
    """)).fetchall()
    limit_map = {r[0]: (r[1], r[2]) for r in limits}

    by_industry = []
    breach = warning = 0
    for r in ind_rows:
        ind  = r[0]
        exp  = float(r[1] or 0)
        pct  = round(exp / total_exp * 100, 2) if total_exp > 0 else 0.0
        lim, warn = limit_map.get(ind, (8.0, 6.8))
        if pct >= lim:
            status = "BREACH"
            breach += 1
        elif pct >= warn:
            status = "WARNING"
            warning += 1
        else:
            status = "NORMAL"
        by_industry.append({
            "dimension_value": ind,
            "label": INDUSTRY_NAMES.get(ind, ind),
            "exposure_억": round(exp, 1),
            "exposure_pct": pct,
            "limit_pct": lim,
            "warning_pct": warn,
            "status": status,
        })
    by_industry.sort(key=lambda x: -x["exposure_pct"])

    sz_rows = db.execute(text("""
        SELECT c.firm_size_cd, SUM(f.outstanding_amount_억) as exp
        FROM demo_facility f
        JOIN demo_company c ON f.borrower_id = c.borrower_id
        GROUP BY c.firm_size_cd
    """)).fetchall()

    sz_limits = db.execute(text("""
        SELECT dimension_value, limit_pct, warning_pct
        FROM demo_concentration_limit WHERE dimension='FIRM_SIZE'
    """)).fetchall()
    sz_limit_map = {r[0]: (r[1], r[2]) for r in sz_limits}

    by_firm_size = []
    for r in sz_rows:
        sz   = r[0]
        exp  = float(r[1] or 0)
        pct  = round(exp / total_exp * 100, 2) if total_exp > 0 else 0.0
        lim, warn = sz_limit_map.get(sz, (30.0, 25.5))
        if pct >= lim:
            st = "BREACH"
        elif pct >= warn:
            st = "WARNING"
        else:
            st = "NORMAL"
        by_firm_size.append({
            "dimension_value": sz,
            "label": sz,
            "exposure_억": round(exp, 1),
            "exposure_pct": pct,
            "limit_pct": lim,
            "warning_pct": warn,
            "status": st,
        })

    return {
        "total_exposure_억": round(total_exp, 1),
        "by_industry": by_industry,
        "by_firm_size": by_firm_size,
        "breach_count": breach,
        "warning_count": warning,
    }


@router.get("/trend")
def get_trend(
    dimension: str = Query("INDUSTRY"),
    dimension_value: str = Query("K10"),
    db: Session = Depends(get_db)
):
    """특정 집중도 지표 월별 추이"""
    col = "industry_cd" if dimension == "INDUSTRY" else "firm_size_cd"

    total_exp = float(db.execute(text(
        "SELECT SUM(outstanding_amount_억) FROM demo_facility"
    )).fetchone()[0] or 0)

    rows = db.execute(text(f"""
        SELECT s.ym, COUNT(DISTINCT c.borrower_id) as co_cnt,
               SUM(f.outstanding_amount_억) as exp
        FROM demo_monthly_signal s
        JOIN demo_company c ON s.borrower_id = c.borrower_id
        JOIN demo_facility f ON c.borrower_id = f.borrower_id
        WHERE c.{col} = :val
        GROUP BY s.ym
        ORDER BY s.ym
    """), {"val": dimension_value}).fetchall()

    return [
        {
            "ym": r[0],
            "company_cnt": r[1],
            "exposure_억": round(float(r[2] or 0), 1),
            "exposure_pct": round(float(r[2] or 0) / total_exp * 100, 2) if total_exp > 0 else 0.0,
        }
        for r in rows
    ]
