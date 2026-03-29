"""
기업 조회 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..core.database import get_db

router = APIRouter(prefix="/api/company", tags=["Company"])


@router.get("/list")
def get_company_list(db: Session = Depends(get_db)):
    """전체 기업 목록 (최신 EWS 등급 포함)"""
    latest_ym_row = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()
    latest_ym = latest_ym_row[0] if latest_ym_row else 202512

    rows = db.execute(text("""
        SELECT c.borrower_id, c.company_name, c.firm_size_cd, c.industry_cd,
               c.listed_flag, c.scenario, s.ews_grade, s.ews_score
        FROM demo_company c
        LEFT JOIN demo_monthly_signal s
            ON c.borrower_id = s.borrower_id AND s.ym = :ym
        ORDER BY s.ews_score ASC NULLS LAST
    """), {"ym": latest_ym}).fetchall()

    return [
        {
            "borrower_id": r[0],
            "company_name": r[1],
            "firm_size_cd": r[2],
            "industry_cd": r[3],
            "listed_flag": r[4],
            "scenario": r[5],
            "ews_grade": r[6],
            "ews_score": round(float(r[7]), 1) if r[7] is not None else None
        }
        for r in rows
    ]


@router.get("/search")
def search_companies(
    q: str = Query(""),
    region: str = Query(""),
    limit: int = Query(500),
    db: Session = Depends(get_db)
):
    """기업명 부분 검색 (지역 필터 지원)"""
    conditions = ["1=1"]
    params: dict = {"limit": limit}

    if q:
        conditions.append("company_name LIKE :q")
        params["q"] = f"%{q}%"

    if region:
        conditions.append("region = :region")
        params["region"] = region

    where = " AND ".join(conditions)

    rows = db.execute(text(f"""
        SELECT borrower_id, company_name, firm_size_cd, industry_cd, scenario, region
        FROM demo_company
        WHERE {where}
        ORDER BY company_name
        LIMIT :limit
    """), params).fetchall()

    return [
        {
            "borrower_id": r[0],
            "company_name": r[1],
            "firm_size_cd": r[2],
            "industry_cd": r[3],
            "scenario": r[4],
            "region": r[5],
        }
        for r in rows
    ]


@router.get("/{borrower_id}")
def get_company_detail(borrower_id: str, db: Session = Depends(get_db)):
    """기업 상세 정보: 프로필 + 여신 + 담보 + 자산건전성 + ECL + 신용등급 + 코베넌트 + 워크아웃"""

    company = db.execute(text("""
        SELECT borrower_id, company_name, firm_size_cd, industry_cd,
               listed_flag, scenario, default_ym, recovery_ym
        FROM demo_company WHERE borrower_id = :bid
    """), {"bid": borrower_id}).fetchone()

    if not company:
        return {"error": "Company not found"}

    # 여신
    facilities = db.execute(text("""
        SELECT facility_id, facility_type, committed_amount_억, outstanding_amount_억,
               interest_rate, maturity_ym, collateral_type
        FROM demo_facility WHERE borrower_id = :bid
    """), {"bid": borrower_id}).fetchall()

    # 담보
    collaterals = db.execute(text("""
        SELECT collateral_id, facility_id, collateral_type, collateral_subtype,
               address, area_m2, prior_lien_amount_억, recognition_ratio,
               appraised_value_억, ltv_pct, appraiser
        FROM demo_collateral WHERE borrower_id = :bid
    """), {"bid": borrower_id}).fetchall()

    # 자산건전성 추이 (최근 12개월)
    asset_class = db.execute(text("""
        SELECT id, ym, classification, ews_score
        FROM demo_asset_class
        WHERE borrower_id = :bid
        ORDER BY ym DESC LIMIT 12
    """), {"bid": borrower_id}).fetchall()

    # ECL 추이 (최근 12개월)
    ecl = db.execute(text("""
        SELECT id, ym, stage, ecl_amount_억, pd_value, lgd, ead_억
        FROM demo_ecl
        WHERE borrower_id = :bid
        ORDER BY ym DESC LIMIT 12
    """), {"bid": borrower_id}).fetchall()

    # 신용등급
    ratings = db.execute(text("""
        SELECT id, rating_ym, grade
        FROM demo_credit_rating
        WHERE borrower_id = :bid
        ORDER BY rating_ym DESC
    """), {"bid": borrower_id}).fetchall()

    # 코베넌트
    covenants = db.execute(text("""
        SELECT id, check_ym, covenant_type, result, actual_value, threshold_value
        FROM demo_covenant
        WHERE borrower_id = :bid
        ORDER BY check_ym DESC
    """), {"bid": borrower_id}).fetchall()

    # 워크아웃 + 시나리오
    workouts = db.execute(text("""
        SELECT workout_id, workout_type, workout_start_ym, original_balance_억,
               recovery_rate, outcome
        FROM demo_workout WHERE borrower_id = :bid
    """), {"bid": borrower_id}).fetchall()

    workout_history = []
    for w in workouts:
        wid = w[0]
        scenarios = db.execute(text("""
            SELECT scenario_type, recovery_amount_억, recovery_timeline_months,
                   discount_rate, npv_억, irr_pct, probability_pct
            FROM demo_recovery_scenario WHERE workout_id = :wid
            ORDER BY CASE scenario_type WHEN 'OPTIMISTIC' THEN 1 WHEN 'BASE' THEN 2 ELSE 3 END
        """), {"wid": wid}).fetchall()

        weighted = sum(float(s[1] or 0) * float(s[6] or 0) / 100.0 for s in scenarios)
        workout_history.append({
            "workout_id": w[0],
            "workout_type": w[1],
            "workout_start_ym": w[2],
            "original_balance_억": round(float(w[3]), 1) if w[3] is not None else 0,
            "recovery_rate": round(float(w[4]), 3) if w[4] is not None else 0,
            "outcome": w[5],
            "scenarios": [
                {
                    "scenario_type": s[0],
                    "recovery_amount_억": round(float(s[1]), 2) if s[1] is not None else 0,
                    "recovery_timeline_months": s[2],
                    "discount_rate": round(float(s[3]), 4) if s[3] is not None else 0,
                    "npv_억": round(float(s[4]), 3) if s[4] is not None else 0,
                    "irr_pct": round(float(s[5]), 2) if s[5] is not None else 0,
                    "probability_pct": round(float(s[6]), 1) if s[6] is not None else 0,
                }
                for s in scenarios
            ],
            "weighted_expected_recovery_억": round(weighted, 3),
        })

    # 담보 최신 가치평가
    collateral_valuation = db.execute(text("""
        SELECT cv.collateral_id, cv.valuation_ym, cv.appraised_value_억,
               cv.market_value_억, cv.ltv_pct, cv.valuation_method, cv.change_pct
        FROM demo_collateral_valuation cv
        INNER JOIN (
            SELECT collateral_id, MAX(valuation_ym) as max_ym
            FROM demo_collateral_valuation
            WHERE borrower_id = :bid
            GROUP BY collateral_id
        ) latest ON cv.collateral_id = latest.collateral_id AND cv.valuation_ym = latest.max_ym
        WHERE cv.borrower_id = :bid
    """), {"bid": borrower_id}).fetchall()

    # 거래행태 (최근 12개월)
    transaction_behavior = db.execute(text("""
        SELECT ym, avg_deposit_balance_억, inflow_outflow_ratio,
               limit_utilization_ratio, principal_past_due_days
        FROM demo_monthly_signal
        WHERE borrower_id = :bid
        ORDER BY ym DESC LIMIT 12
    """), {"bid": borrower_id}).fetchall()

    return {
        "profile": {
            "borrower_id": company[0],
            "company_name": company[1],
            "firm_size_cd": company[2],
            "industry_cd": company[3],
            "listed_flag": company[4],
            "scenario": company[5],
            "default_ym": company[6],
            "recovery_ym": company[7]
        },
        "facilities": [
            {
                "facility_id": r[0],
                "facility_type": r[1],
                "committed_amount_억": round(float(r[2]), 1) if r[2] is not None else 0,
                "outstanding_amount_억": round(float(r[3]), 1) if r[3] is not None else 0,
                "interest_rate": round(float(r[4]), 3) if r[4] is not None else 0,
                "maturity_ym": r[5],
                "collateral_type": r[6]
            }
            for r in facilities
        ],
        "collaterals": [
            {
                "collateral_id": r[0],
                "facility_id": r[1],
                "collateral_type": r[2],
                "collateral_subtype": r[3],
                "address": r[4],
                "area_m2": round(float(r[5]), 0) if r[5] is not None else None,
                "prior_lien_amount_억": round(float(r[6]), 1) if r[6] is not None else 0,
                "recognition_ratio": round(float(r[7]), 2) if r[7] is not None else 0.7,
                "appraised_value_억": round(float(r[8]), 1) if r[8] is not None else 0,
                "ltv_pct": round(float(r[9]), 1) if r[9] is not None else 0,
                "appraiser": r[10],
                # 파생 계산
                "recognized_value_억": round(float(r[8] or 0) * float(r[7] or 0.7), 1),
            }
            for r in collaterals
        ],
        "asset_class_trend": [
            {"id": r[0], "ym": r[1], "classification": r[2],
             "ews_score": round(float(r[3]), 1) if r[3] is not None else 0}
            for r in reversed(asset_class)
        ],
        "ecl_trend": [
            {
                "id": r[0], "ym": r[1], "stage": r[2],
                "ecl_amount_억": round(float(r[3]), 2) if r[3] is not None else 0,
                "pd_value": round(float(r[4]), 4) if r[4] is not None else 0,
                "lgd": round(float(r[5]), 4) if r[5] is not None else 0,
                "ead_억": round(float(r[6]), 1) if r[6] is not None else 0
            }
            for r in reversed(ecl)
        ],
        "credit_ratings": [
            {"id": r[0], "rating_ym": r[1], "grade": r[2]}
            for r in ratings
        ],
        "covenants": [
            {
                "id": r[0], "check_ym": r[1], "covenant_type": r[2],
                "result": r[3],
                "actual_value": round(float(r[4]), 3) if r[4] is not None else None,
                "threshold_value": round(float(r[5]), 3) if r[5] is not None else None
            }
            for r in covenants
        ],
        "workouts": [
            {
                "workout_id": r[0], "workout_type": r[1], "workout_start_ym": r[2],
                "original_balance_억": round(float(r[3]), 1) if r[3] is not None else 0,
                "recovery_rate": round(float(r[4]), 3) if r[4] is not None else 0,
                "outcome": r[5]
            }
            for r in workouts
        ],
        "workout_history": workout_history,
        "collateral_valuation": [
            {
                "collateral_id": r[0],
                "valuation_ym": r[1],
                "appraised_value_억": round(float(r[2]), 2) if r[2] is not None else 0,
                "market_value_억": round(float(r[3]), 2) if r[3] is not None else 0,
                "ltv_pct": round(float(r[4]), 1) if r[4] is not None else 0,
                "valuation_method": r[5],
                "change_pct": round(float(r[6]), 2) if r[6] is not None else 0,
            }
            for r in collateral_valuation
        ],
        "transaction_behavior": [
            {
                "ym": r[0],
                "avg_deposit_balance_억": round(float(r[1]), 2) if r[1] is not None else 0,
                "inflow_outflow_ratio": round(float(r[2]), 3) if r[2] is not None else 0,
                "limit_utilization_ratio": round(float(r[3]), 3) if r[3] is not None else 0,
                "principal_past_due_days": r[4] if r[4] is not None else 0,
            }
            for r in reversed(transaction_behavior)
        ],
    }


@router.get("/{borrower_id}/collateral/{collateral_id}/valuation")
def get_collateral_valuation_history(borrower_id: str, collateral_id: str, db: Session = Depends(get_db)):
    """특정 담보의 분기별 평가 이력"""
    col = db.execute(text("""
        SELECT collateral_type, collateral_subtype, address, area_m2,
               prior_lien_amount_억, recognition_ratio, appraised_value_억, appraiser
        FROM demo_collateral WHERE collateral_id = :cid AND borrower_id = :bid
    """), {"cid": collateral_id, "bid": borrower_id}).fetchone()

    rows = db.execute(text("""
        SELECT valuation_id, valuation_ym, appraised_value_억, market_value_억,
               ltv_pct, valuation_method, change_pct
        FROM demo_collateral_valuation
        WHERE collateral_id = :cid AND borrower_id = :bid
        ORDER BY valuation_ym ASC
    """), {"cid": collateral_id, "bid": borrower_id}).fetchall()

    history = []
    for i, r in enumerate(rows):
        prev_val = rows[i-1][2] if i > 0 else None
        history.append({
            "valuation_id": r[0],
            "valuation_ym": r[1],
            "label": f"{str(r[1])[:4]}-Q{(int(str(r[1])[4:]) + 2) // 3}",
            "appraised_value_억": round(float(r[2]), 2) if r[2] is not None else 0,
            "market_value_억": round(float(r[3]), 2) if r[3] is not None else 0,
            "ltv_pct": round(float(r[4]), 1) if r[4] is not None else 0,
            "valuation_method": r[5],
            "change_pct": round(float(r[6]), 2) if r[6] is not None else 0,
            "previous_value_억": round(float(prev_val), 2) if prev_val is not None else None,
        })

    return {
        "collateral_id": collateral_id,
        "collateral_info": {
            "collateral_type": col[0] if col else None,
            "collateral_subtype": col[1] if col else None,
            "address": col[2] if col else None,
            "area_m2": round(float(col[3]), 0) if col and col[3] else None,
            "prior_lien_amount_억": round(float(col[4]), 1) if col and col[4] else 0,
            "recognition_ratio": round(float(col[5]), 2) if col and col[5] else 0.7,
            "appraised_value_억": round(float(col[6]), 1) if col and col[6] else 0,
            "appraiser": col[7] if col else None,
        } if col else None,
        "history": history,
    }


@router.get("/{borrower_id}/collateral-valuation")
def get_company_collateral_valuation(borrower_id: str, db: Session = Depends(get_db)):
    """기업의 모든 담보에 대한 분기별 가치평가 이력 (차트용)"""
    rows = db.execute(text("""
        SELECT cv.collateral_id, cv.valuation_ym, cv.appraised_value_억,
               cv.market_value_억, cv.ltv_pct, cv.valuation_method, cv.change_pct,
               col.collateral_type
        FROM demo_collateral_valuation cv
        LEFT JOIN demo_collateral col ON cv.collateral_id = col.collateral_id
        WHERE cv.borrower_id = :bid
        ORDER BY cv.collateral_id, cv.valuation_ym
    """), {"bid": borrower_id}).fetchall()

    return [
        {
            "collateral_id": r[0],
            "valuation_ym": r[1],
            "label": f"{str(r[1])[:4]}-Q{(int(str(r[1])[4:]) // 3)}",
            "appraised_value_억": round(float(r[2]), 2) if r[2] is not None else 0,
            "market_value_억": round(float(r[3]), 2) if r[3] is not None else 0,
            "ltv_pct": round(float(r[4]), 1) if r[4] is not None else 0,
            "valuation_method": r[5],
            "change_pct": round(float(r[6]), 2) if r[6] is not None else 0,
            "collateral_type": r[7],
        }
        for r in rows
    ]
