"""
EWS 대시보드 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """EWS 대시보드 요약 정보"""

    # 최신 ym 조회
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    # 전체 기업 수
    total_companies = db.execute(text("SELECT COUNT(*) FROM demo_company")).fetchone()[0]

    # 최신 월 EWS 등급 분포
    grade_counts_rows = db.execute(text("""
        SELECT ews_grade, COUNT(*) as cnt
        FROM demo_monthly_signal
        WHERE ym = :ym
        GROUP BY ews_grade
    """), {"ym": latest_ym}).fetchall()

    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for row in grade_counts_rows:
        if row[0] in grade_counts:
            grade_counts[row[0]] = row[1]

    # 총 여신 잔액 (억)
    total_exposure_row = db.execute(text("""
        SELECT COALESCE(SUM(outstanding_amount_억), 0) FROM demo_facility
    """)).fetchone()
    total_exposure = float(total_exposure_row[0]) if total_exposure_row[0] else 0.0

    # 평균 ECL 비율 (ECL / EAD)
    ecl_row = db.execute(text("""
        SELECT AVG(CASE WHEN ead_억 > 0 THEN ecl_amount_억 / ead_억 ELSE 0 END)
        FROM demo_ecl
        WHERE ym = :ym
    """), {"ym": latest_ym}).fetchone()
    avg_ecl_rate = float(ecl_row[0]) * 100 if ecl_row[0] else 0.0

    # 경보 수 (C + D 등급)
    alert_count = grade_counts.get("C", 0) + grade_counts.get("D", 0)

    return {
        "total_companies": total_companies,
        "ews_grade_counts": grade_counts,
        "total_exposure_억": round(total_exposure, 1),
        "avg_ecl_rate": round(avg_ecl_rate, 2),
        "alert_count": alert_count,
        "latest_ym": latest_ym
    }


@router.get("/grade-trend")
def get_grade_trend(db: Session = Depends(get_db)):
    """최근 12개월 EWS 등급 분포 추이"""
    # 최근 12개월 ym 목록 산출
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    rows = db.execute(text("""
        SELECT ym, ews_grade, COUNT(*) as cnt
        FROM demo_monthly_signal
        GROUP BY ym, ews_grade
        ORDER BY ym
    """)).fetchall()

    # 12개월 ym 계산
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
    yms = sorted(yms)

    # 데이터 집계
    trend_map: dict = {y: {"ym": y, "A": 0, "B": 0, "C": 0, "D": 0} for y in yms}
    for row in rows:
        if row[0] in trend_map and row[1] in ("A", "B", "C", "D"):
            trend_map[row[0]][row[1]] = row[2]

    return [
        {
            "ym": str(v["ym"]),
            "label": f"{str(v['ym'])[:4]}-{str(v['ym'])[4:]}",
            "A": v["A"],
            "B": v["B"],
            "C": v["C"],
            "D": v["D"]
        }
        for v in trend_map.values()
    ]


@router.get("/ews-alerts")
def get_ews_alerts(db: Session = Depends(get_db)):
    """최신 월 C/D 등급 상위 20개 기업"""
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    rows = db.execute(text("""
        SELECT s.borrower_id, c.company_name, s.ews_grade, s.ews_score,
               s.ifrs9_stage, c.firm_size_cd, c.industry_cd
        FROM demo_monthly_signal s
        JOIN demo_company c ON s.borrower_id = c.borrower_id
        WHERE s.ym = :ym AND s.ews_grade IN ('C', 'D')
        ORDER BY s.ews_score ASC
        LIMIT 20
    """), {"ym": latest_ym}).fetchall()

    return [
        {
            "borrower_id": r[0],
            "company_name": r[1],
            "ews_grade": r[2],
            "ews_score": round(float(r[3]), 1) if r[3] is not None else 0,
            "ifrs9_stage": r[4],
            "firm_size_cd": r[5],
            "industry_cd": r[6]
        }
        for r in rows
    ]
