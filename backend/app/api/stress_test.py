"""
스트레스 테스트 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..core.database import get_db

router = APIRouter(prefix="/api/stress-test", tags=["StressTest"])

# 업종별 충격 가중치 (건설/부동산 고위험)
INDUSTRY_WEIGHTS = {
    "K10": 1.5,   # 건설
    "K11": 1.4,   # 부동산
    "K01A": 0.9,  # 제조
    "K01B": 0.8,  # 첨단제조
    "K05": 0.85,  # IT
    "K07": 1.1,   # 도소매
    "K09": 1.2,   # 숙박/음식
    "K02": 1.0,
    "K03": 1.0,
    "K04": 1.0,
    "K08": 1.0,
    "K13": 1.1,
}

INDUSTRY_NAMES = {
    "K00": "제조업",
    "K01A": "일반제조",
    "K01B": "첨단제조",
    "K02": "화학",
    "K03": "금속",
    "K04": "운수",
    "K05": "IT",
    "K07": "도소매",
    "K08": "금융",
    "K09": "숙박/음식",
    "K10": "건설",
    "K11": "부동산",
    "K13": "에너지",
}


@router.get("/scenarios")
def get_scenarios(db: Session = Depends(get_db)):
    """시나리오 전체 목록"""
    rows = db.execute(text("""
        SELECT scenario_id, scenario_name, description,
               rate_shock_bps, gdp_shock_pct, credit_spread_bps,
               base_pd_multiplier, base_lgd_multiplier,
               expected_npl_ratio_pct, expected_ecl_change_pct
        FROM demo_stress_scenario
        ORDER BY base_pd_multiplier
    """)).fetchall()

    return [
        {
            "scenario_id": r[0],
            "scenario_name": r[1],
            "description": r[2],
            "rate_shock_bps": r[3],
            "gdp_shock_pct": r[4],
            "credit_spread_bps": r[5],
            "base_pd_multiplier": r[6],
            "base_lgd_multiplier": r[7],
            "expected_npl_ratio_pct": r[8],
            "expected_ecl_change_pct": r[9],
        }
        for r in rows
    ]


def _calc_impact(db: Session, pd_mult: float, lgd_mult: float,
                 npl_pct: float, ecl_chg_pct: float):
    """공통 충격 계산 로직"""
    ecl_row = db.execute(text("""
        SELECT SUM(ecl_amount_억)
        FROM demo_ecl
        WHERE ym = (SELECT MAX(ym) FROM demo_ecl)
    """)).fetchone()
    current_ecl = round(float(ecl_row[0] or 0), 1)
    stressed_ecl = round(current_ecl * pd_mult * lgd_mult, 1)

    # 등급 전이 추정 (단순화)
    total = db.execute(text("""
        SELECT COUNT(*) FROM demo_monthly_signal
        WHERE ym = (SELECT MAX(ym) FROM demo_monthly_signal)
    """)).fetchone()[0] or 1

    grade_shift = {
        "A_to_B": max(0, int(total * 0.05 * (pd_mult - 1))),
        "B_to_C": max(0, int(total * 0.08 * (pd_mult - 1))),
        "C_to_D": max(0, int(total * 0.04 * (pd_mult - 1))),
    }

    # 업종별 영향
    ind_rows = db.execute(text("""
        SELECT c.industry_cd, SUM(e.ecl_amount_억) as ecl
        FROM demo_ecl e
        JOIN demo_company c ON e.borrower_id = c.borrower_id
        WHERE e.ym = (SELECT MAX(ym) FROM demo_ecl)
        GROUP BY c.industry_cd
    """)).fetchall()

    industry_impact = []
    for r in ind_rows:
        ind = r[0]
        ecl = float(r[1] or 0)
        w = INDUSTRY_WEIGHTS.get(ind, 1.0)
        stressed = round(ecl * pd_mult * lgd_mult * w, 1)
        chg_pct  = round((stressed - ecl) / ecl * 100, 1) if ecl > 0 else 0.0
        industry_impact.append({
            "industry_cd": ind,
            "industry_name": INDUSTRY_NAMES.get(ind, ind),
            "current_ecl_억": round(ecl, 1),
            "stressed_ecl_억": stressed,
            "ecl_increase_pct": chg_pct,
        })
    industry_impact.sort(key=lambda x: -x["ecl_increase_pct"])

    return {
        "portfolio_impact": {
            "current_ecl_억": current_ecl,
            "stressed_ecl_억": stressed_ecl,
            "ecl_increase_억": round(stressed_ecl - current_ecl, 1),
            "ecl_increase_pct": ecl_chg_pct,
            "current_npl_pct": 12.0,
            "stressed_npl_pct": npl_pct,
            "grade_shift": grade_shift,
        },
        "industry_impact": industry_impact,
    }


@router.get("/impact/{scenario_id}")
def get_impact(scenario_id: str, db: Session = Depends(get_db)):
    """시나리오 충격 분석"""
    sc = db.execute(text("""
        SELECT scenario_id, scenario_name, description,
               rate_shock_bps, gdp_shock_pct, credit_spread_bps,
               base_pd_multiplier, base_lgd_multiplier,
               expected_npl_ratio_pct, expected_ecl_change_pct
        FROM demo_stress_scenario WHERE scenario_id = :sid
    """), {"sid": scenario_id}).fetchone()

    if not sc:
        return {}

    scenario = {
        "scenario_id": sc[0],
        "scenario_name": sc[1],
        "description": sc[2],
        "rate_shock_bps": sc[3],
        "gdp_shock_pct": sc[4],
        "credit_spread_bps": sc[5],
        "base_pd_multiplier": sc[6],
        "base_lgd_multiplier": sc[7],
        "expected_npl_ratio_pct": sc[8],
        "expected_ecl_change_pct": sc[9],
    }

    impact = _calc_impact(db, sc[6], sc[7], sc[8], sc[9])
    return {"scenario": scenario, **impact}


@router.get("/custom")
def get_custom(
    rate_shock_bps: int = Query(0),
    gdp_shock_pct: float = Query(0.0),
    credit_spread_bps: int = Query(0),
    db: Session = Depends(get_db)
):
    """사용자 정의 파라미터 즉석 계산"""
    # 간단한 PD/LGD 배수 추정
    pd_mult  = 1.0 + max(0, rate_shock_bps) / 200 * 0.5 + max(0, -gdp_shock_pct) / 5 * 1.0
    lgd_mult = 1.0 + max(0, credit_spread_bps) / 350 * 0.4
    npl_pct  = round(12.0 * pd_mult, 1)
    ecl_chg  = round((pd_mult * lgd_mult - 1) * 100, 1)

    impact = _calc_impact(db, pd_mult, lgd_mult, npl_pct, ecl_chg)
    return {
        "params": {
            "rate_shock_bps": rate_shock_bps,
            "gdp_shock_pct": gdp_shock_pct,
            "credit_spread_bps": credit_spread_bps,
            "pd_multiplier": round(pd_mult, 3),
            "lgd_multiplier": round(lgd_mult, 3),
        },
        **impact,
    }
