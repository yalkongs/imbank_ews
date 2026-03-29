"""
자산건전성 분류 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..core.database import get_db

router = APIRouter(prefix="/api/asset-classification", tags=["AssetClassification"])

CLASSIFICATION_ORDER = ["NORMAL", "PRECAUTIONARY", "SUBSTANDARD", "DOUBTFUL", "LOSS"]


@router.get("/distribution")
def get_distribution(ym: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """특정 월 자산건전성 분류 분포"""
    if not ym:
        latest_row = db.execute(text("SELECT MAX(ym) FROM demo_asset_class")).fetchone()
        ym = latest_row[0] if latest_row else 202512

    rows = db.execute(text("""
        SELECT classification, COUNT(*) as cnt
        FROM demo_asset_class
        WHERE ym = :ym
        GROUP BY classification
    """), {"ym": ym}).fetchall()

    dist = {c: 0 for c in CLASSIFICATION_ORDER}
    for r in rows:
        if r[0] in dist:
            dist[r[0]] = r[1]

    colors = {
        "NORMAL": "#10b981",
        "PRECAUTIONARY": "#f59e0b",
        "SUBSTANDARD": "#f97316",
        "DOUBTFUL": "#ef4444",
        "LOSS": "#dc2626"
    }

    return {
        "ym": ym,
        "distribution": [
            {"classification": c, "count": dist[c], "color": colors[c]}
            for c in CLASSIFICATION_ORDER
        ]
    }


@router.get("/trend")
def get_trend(db: Session = Depends(get_db)):
    """12개월 자산건전성 분류 추이"""
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_asset_class")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    # 최근 12개월 ym 계산
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
    yms_sorted = sorted(yms)
    min_ym = yms_sorted[0]

    rows = db.execute(text("""
        SELECT ym, classification, COUNT(*) as cnt
        FROM demo_asset_class
        WHERE ym >= :min_ym
        GROUP BY ym, classification
        ORDER BY ym
    """), {"min_ym": min_ym}).fetchall()

    trend_map: dict = {y: {"ym": y, "NORMAL": 0, "PRECAUTIONARY": 0, "SUBSTANDARD": 0, "DOUBTFUL": 0, "LOSS": 0} for y in yms_sorted}
    for r in rows:
        if r[0] in trend_map and r[1] in CLASSIFICATION_ORDER:
            trend_map[r[0]][r[1]] = r[2]

    return [
        {
            "ym": str(v["ym"]),
            "label": f"{str(v['ym'])[:4]}-{str(v['ym'])[4:]}",
            **{c: v[c] for c in CLASSIFICATION_ORDER}
        }
        for v in trend_map.values()
    ]


@router.get("/list")
def get_non_normal_list(db: Session = Depends(get_db)):
    """최신 월 정상 외 기업 목록"""
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_asset_class")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    rows = db.execute(text("""
        SELECT a.borrower_id, co.company_name, a.classification, a.ews_score,
               co.firm_size_cd, co.industry_cd
        FROM demo_asset_class a
        JOIN demo_company co ON a.borrower_id = co.borrower_id
        WHERE a.ym = :ym AND a.classification != 'NORMAL'
        ORDER BY CASE a.classification
            WHEN 'LOSS' THEN 1
            WHEN 'DOUBTFUL' THEN 2
            WHEN 'SUBSTANDARD' THEN 3
            WHEN 'PRECAUTIONARY' THEN 4
            ELSE 5 END
    """), {"ym": latest_ym}).fetchall()

    return [
        {
            "borrower_id": r[0],
            "company_name": r[1],
            "classification": r[2],
            "ews_score": round(float(r[3]), 1) if r[3] is not None else 0,
            "firm_size_cd": r[4],
            "industry_cd": r[5]
        }
        for r in rows
    ]
