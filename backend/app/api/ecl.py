"""
IFRS9 ECL 관리 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db

router = APIRouter(prefix="/api/ecl", tags=["ECL"])


@router.get("/summary")
def get_ecl_summary(db: Session = Depends(get_db)):
    """ECL 요약 (Stage별 총액, 평균 PD/LGD)"""
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_ecl")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    rows = db.execute(text("""
        SELECT stage, COUNT(*) as cnt,
               COALESCE(SUM(ecl_amount_억), 0) as total_ecl,
               COALESCE(SUM(ead_억), 0) as total_ead,
               AVG(pd_value) as avg_pd,
               AVG(lgd) as avg_lgd
        FROM demo_ecl
        WHERE ym = :ym
        GROUP BY stage
        ORDER BY stage
    """), {"ym": latest_ym}).fetchall()

    total_ecl = sum(float(r[2]) for r in rows)
    total_ead = sum(float(r[3]) for r in rows)

    return {
        "latest_ym": latest_ym,
        "total_ecl_억": round(total_ecl, 2),
        "total_ead_억": round(total_ead, 1),
        "ecl_rate_pct": round(total_ecl / total_ead * 100, 3) if total_ead > 0 else 0,
        "by_stage": [
            {
                "stage": r[0],
                "count": r[1],
                "ecl_억": round(float(r[2]), 2),
                "ead_억": round(float(r[3]), 1),
                "avg_pd": round(float(r[4]), 4) if r[4] is not None else 0,
                "avg_lgd": round(float(r[5]), 4) if r[5] is not None else 0
            }
            for r in rows
        ]
    }


@router.get("/trend")
def get_ecl_trend(db: Session = Depends(get_db)):
    """최근 12개월 ECL 추이 (Stage별 분류 포함)"""
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_ecl")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    # 12개월 ym
    yms = []
    ym = latest_ym
    for _ in range(12):
        yms.append(ym)
        month = ym % 100
        year = ym // 100
        if month == 1:
            ym = (year - 1) * 100 + 12
        else:
            ym = year * 100 + (month - 1)
    min_ym = min(yms)

    rows = db.execute(text("""
        SELECT ym, COALESCE(SUM(ecl_amount_억), 0) as total_ecl,
               COALESCE(SUM(ead_억), 0) as total_ead,
               COALESCE(SUM(CASE WHEN stage=1 THEN ecl_amount_억 ELSE 0 END), 0) as s1_ecl,
               COALESCE(SUM(CASE WHEN stage=2 THEN ecl_amount_억 ELSE 0 END), 0) as s2_ecl,
               COALESCE(SUM(CASE WHEN stage=3 THEN ecl_amount_억 ELSE 0 END), 0) as s3_ecl
        FROM demo_ecl
        WHERE ym >= :min_ym
        GROUP BY ym
        ORDER BY ym
    """), {"min_ym": min_ym}).fetchall()

    return [
        {
            "ym": str(r[0]),
            "label": f"{str(r[0])[:4]}-{str(r[0])[4:]}",
            "ecl_억": round(float(r[1]), 2),
            "ead_억": round(float(r[2]), 1),
            "ecl_rate_pct": round(float(r[1]) / float(r[2]) * 100, 3) if float(r[2]) > 0 else 0,
            "by_stage": {
                "stage1_ecl": round(float(r[3]), 2),
                "stage2_ecl": round(float(r[4]), 2),
                "stage3_ecl": round(float(r[5]), 2),
            }
        }
        for r in rows
    ]


@router.get("/by-stage-trend")
def get_ecl_by_stage_trend(db: Session = Depends(get_db)):
    """전체 기간 Stage별 ECL 추이 (스택 차트용)"""
    rows = db.execute(text("""
        SELECT ym,
               COALESCE(SUM(CASE WHEN stage=1 THEN ecl_amount_억 ELSE 0 END), 0) as s1_ecl,
               COALESCE(SUM(CASE WHEN stage=2 THEN ecl_amount_억 ELSE 0 END), 0) as s2_ecl,
               COALESCE(SUM(CASE WHEN stage=3 THEN ecl_amount_억 ELSE 0 END), 0) as s3_ecl
        FROM demo_ecl
        GROUP BY ym
        ORDER BY ym
    """)).fetchall()

    return [
        {
            "ym": str(r[0]),
            "label": f"{str(r[0])[:4]}-{str(r[0])[4:]}",
            "stage1_ecl": round(float(r[1]), 2),
            "stage2_ecl": round(float(r[2]), 2),
            "stage3_ecl": round(float(r[3]), 2),
        }
        for r in rows
    ]


@router.get("/by-grade")
def get_ecl_by_grade(db: Session = Depends(get_db)):
    """EWS 등급별 ECL 분포"""
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_ecl")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    rows = db.execute(text("""
        SELECT s.ews_grade, COUNT(*) as cnt,
               COALESCE(SUM(e.ecl_amount_억), 0) as total_ecl,
               COALESCE(SUM(e.ead_억), 0) as total_ead
        FROM demo_ecl e
        JOIN demo_monthly_signal s ON e.borrower_id = s.borrower_id AND e.ym = s.ym
        WHERE e.ym = :ym
        GROUP BY s.ews_grade
        ORDER BY s.ews_grade
    """), {"ym": latest_ym}).fetchall()

    return [
        {
            "ews_grade": r[0],
            "count": r[1],
            "ecl_억": round(float(r[2]), 2),
            "ead_억": round(float(r[3]), 1)
        }
        for r in rows
    ]
