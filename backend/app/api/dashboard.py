"""
EWS 대시보드 API
routes: summary, grade-trend, ews-alerts, industry-breakdown, region-breakdown
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

INDUSTRY_MAP = {
    "K01A": "일반제조", "K01B": "첨단제조", "K02": "건설",
    "K03": "도소매", "K04": "서비스", "K05": "IT/소프트",
    "K06": "금융보험", "K07": "부동산", "K08": "운수창고",
    "K09": "숙박음식", "K10": "농림수산", "K11": "광업",
    "K12": "의료교육", "K13": "에너지/환경",
}


def _prev_ym(ym: int) -> int:
    month = ym % 100
    year = ym // 100
    if month == 1:
        return (year - 1) * 100 + 12
    return year * 100 + (month - 1)


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """EWS 대시보드 요약 정보 (전월 대비 포함)"""

    # 최신 ym 조회
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512
    prev_ym = _prev_ym(latest_ym)

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

    # 전월 EWS 등급 분포
    prev_grade_rows = db.execute(text("""
        SELECT ews_grade, COUNT(*) as cnt
        FROM demo_monthly_signal
        WHERE ym = :ym
        GROUP BY ews_grade
    """), {"ym": prev_ym}).fetchall()

    prev_grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for row in prev_grade_rows:
        if row[0] in prev_grade_counts:
            prev_grade_counts[row[0]] = row[1]

    # 등급 하락 기업 수 (전월 A/B → 이번달 C/D)
    grade_down_row = db.execute(text("""
        SELECT COUNT(*)
        FROM demo_monthly_signal cur
        JOIN demo_monthly_signal prv ON cur.borrower_id = prv.borrower_id
        WHERE cur.ym = :cur_ym AND prv.ym = :prev_ym
          AND prv.ews_grade IN ('A', 'B')
          AND cur.ews_grade IN ('C', 'D')
    """), {"cur_ym": latest_ym, "prev_ym": prev_ym}).fetchone()
    grade_down_count = grade_down_row[0] if grade_down_row else 0

    # 신규 경보 기업 수 (전월 C/D 아님 → 이번달 C/D)
    new_alert_row = db.execute(text("""
        SELECT COUNT(*)
        FROM demo_monthly_signal cur
        LEFT JOIN demo_monthly_signal prv ON cur.borrower_id = prv.borrower_id AND prv.ym = :prev_ym
        WHERE cur.ym = :cur_ym AND cur.ews_grade IN ('C', 'D')
          AND (prv.borrower_id IS NULL OR prv.ews_grade NOT IN ('C', 'D'))
    """), {"cur_ym": latest_ym, "prev_ym": prev_ym}).fetchone()
    new_alert_count = new_alert_row[0] if new_alert_row else 0

    # D등급 NPL 여신 잔액
    npl_exposure_row = db.execute(text("""
        SELECT COALESCE(SUM(f.outstanding_amount_억), 0)
        FROM demo_facility f
        JOIN demo_monthly_signal s ON f.borrower_id = s.borrower_id
        WHERE s.ym = :ym AND s.ews_grade = 'D'
    """), {"ym": latest_ym}).fetchone()
    npl_exposure = float(npl_exposure_row[0]) if npl_exposure_row[0] else 0.0

    # 총 여신 잔액 (억)
    total_exposure_row = db.execute(text("""
        SELECT COALESCE(SUM(outstanding_amount_억), 0) FROM demo_facility
    """)).fetchone()
    total_exposure = float(total_exposure_row[0]) if total_exposure_row[0] else 0.0

    # 최신 월 평균 ECL 비율
    ecl_row = db.execute(text("""
        SELECT AVG(CASE WHEN ead_억 > 0 THEN ecl_amount_억 / ead_억 ELSE 0 END)
        FROM demo_ecl
        WHERE ym = :ym
    """), {"ym": latest_ym}).fetchone()
    avg_ecl_rate = float(ecl_row[0]) * 100 if ecl_row[0] else 0.0

    # 전월 평균 ECL 비율
    prev_ecl_row = db.execute(text("""
        SELECT AVG(CASE WHEN ead_억 > 0 THEN ecl_amount_억 / ead_억 ELSE 0 END)
        FROM demo_ecl
        WHERE ym = :ym
    """), {"ym": prev_ym}).fetchone()
    prev_ecl_rate = float(prev_ecl_row[0]) * 100 if prev_ecl_row[0] else 0.0

    alert_count = grade_counts.get("C", 0) + grade_counts.get("D", 0)

    return {
        "total_companies": total_companies,
        "ews_grade_counts": grade_counts,
        "prev_grade_counts": prev_grade_counts,
        "grade_down_count": grade_down_count,
        "new_alert_count": new_alert_count,
        "total_exposure_억": round(total_exposure, 1),
        "npl_exposure_억": round(npl_exposure, 1),
        "avg_ecl_rate": round(avg_ecl_rate, 2),
        "prev_ecl_rate": round(prev_ecl_rate, 2),
        "alert_count": alert_count,
        "latest_ym": latest_ym,
        "prev_ym": prev_ym,
    }


@router.get("/grade-trend")
def get_grade_trend(db: Session = Depends(get_db)):
    """최근 12개월 EWS 등급 분포 추이"""
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
        ym = _prev_ym(ym)
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
    """최신 월 C/D 등급 상위 20개 기업 (지역·여신 포함)"""
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    rows = db.execute(text("""
        SELECT s.borrower_id, c.company_name, s.ews_grade, s.ews_score,
               s.ifrs9_stage, c.firm_size_cd, c.industry_cd, c.region,
               COALESCE((
                   SELECT SUM(f.outstanding_amount_억)
                   FROM demo_facility f
                   WHERE f.borrower_id = s.borrower_id
               ), 0) as exposure_억
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
            "industry_cd": r[6],
            "region": r[7] or "-",
            "exposure_억": round(float(r[8]), 1) if r[8] else 0.0,
        }
        for r in rows
    ]


@router.get("/industry-breakdown")
def get_industry_breakdown(db: Session = Depends(get_db)):
    """업종별 EWS 등급 분포 (최신 월)"""
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    rows = db.execute(text("""
        SELECT c.industry_cd, s.ews_grade, COUNT(*) as cnt
        FROM demo_monthly_signal s
        JOIN demo_company c ON s.borrower_id = c.borrower_id
        WHERE s.ym = :ym
        GROUP BY c.industry_cd, s.ews_grade
        ORDER BY c.industry_cd, s.ews_grade
    """), {"ym": latest_ym}).fetchall()

    # 업종별 집계
    industry_map: dict = {}
    for row in rows:
        cd, grade, cnt = row[0], row[1], row[2]
        if cd not in industry_map:
            industry_map[cd] = {"industry_cd": cd, "name": INDUSTRY_MAP.get(cd, cd),
                                 "A": 0, "B": 0, "C": 0, "D": 0, "total": 0}
        if grade in ("A", "B", "C", "D"):
            industry_map[cd][grade] = cnt
            industry_map[cd]["total"] += cnt

    result = []
    for v in industry_map.values():
        alert = v["C"] + v["D"]
        result.append({
            **v,
            "alert_count": alert,
            "alert_rate": round(alert / v["total"] * 100, 1) if v["total"] > 0 else 0.0,
        })

    # 경보율 내림차순 정렬
    result.sort(key=lambda x: x["alert_rate"], reverse=True)
    return result


@router.get("/region-breakdown")
def get_region_breakdown(db: Session = Depends(get_db)):
    """지역별 EWS 등급 분포 (최신 월)"""
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    rows = db.execute(text("""
        SELECT c.region, s.ews_grade, COUNT(*) as cnt,
               COALESCE(SUM(f.outstanding_amount_억), 0) as exposure
        FROM demo_monthly_signal s
        JOIN demo_company c ON s.borrower_id = c.borrower_id
        LEFT JOIN demo_facility f ON s.borrower_id = f.borrower_id
        WHERE s.ym = :ym
        GROUP BY c.region, s.ews_grade
        ORDER BY c.region, s.ews_grade
    """), {"ym": latest_ym}).fetchall()

    region_map: dict = {}
    for row in rows:
        region, grade, cnt, exposure = row[0] or "기타", row[1], row[2], float(row[3] or 0)
        if region not in region_map:
            region_map[region] = {"region": region, "A": 0, "B": 0, "C": 0, "D": 0,
                                   "total": 0, "exposure_억": 0.0}
        if grade in ("A", "B", "C", "D"):
            region_map[region][grade] = cnt
            region_map[region]["total"] += cnt
            region_map[region]["exposure_억"] += exposure

    result = []
    for v in region_map.values():
        alert = v["C"] + v["D"]
        result.append({
            **v,
            "exposure_억": round(v["exposure_억"], 1),
            "alert_count": alert,
            "alert_rate": round(alert / v["total"] * 100, 1) if v["total"] > 0 else 0.0,
        })

    result.sort(key=lambda x: x["total"], reverse=True)
    return result
