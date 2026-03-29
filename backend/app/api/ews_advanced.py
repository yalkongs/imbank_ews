"""
EWS 선행지표 고도화 API
- 거래 행동 (demo_ews_transaction)
- 공공 이벤트 (demo_ews_public_event)
- 뉴스 감성 (demo_ews_news_monthly)
- 시장 신호 (demo_ews_market_signal)
- 공급망 위험 (demo_ews_supply_chain)
- 데이터 완성도 프로파일
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..core.database import get_db

router = APIRouter(prefix="/api/ews-advanced", tags=["EWS Advanced"])


@router.get("/company/{borrower_id}/transaction")
def get_transaction(borrower_id: str, db: Session = Depends(get_db)):
    """월별 거래 행동 이력"""
    rows = db.execute(text("""
        SELECT ym, avg_daily_balance_억, balance_change_pct,
               incoming_amount_억, outgoing_amount_억,
               payment_delay_count, check_bounce_count,
               overdraft_count, salary_transfer_flag, card_spending_change_pct
        FROM demo_ews_transaction
        WHERE borrower_id = :bid
        ORDER BY ym
    """), {"bid": borrower_id}).fetchall()

    return [
        {
            "ym": r[0],
            "avg_daily_balance_억": round(float(r[1] or 0), 2),
            "balance_change_pct": round(float(r[2] or 0), 1),
            "incoming_amount_억": round(float(r[3] or 0), 2),
            "outgoing_amount_억": round(float(r[4] or 0), 2),
            "payment_delay_count": r[5] or 0,
            "check_bounce_count": r[6] or 0,
            "overdraft_count": r[7] or 0,
            "salary_transfer_flag": r[8] or 1,
            "card_spending_change_pct": round(float(r[9] or 0), 1),
        }
        for r in rows
    ]


@router.get("/company/{borrower_id}/public-events")
def get_public_events(borrower_id: str, db: Session = Depends(get_db)):
    """공공 이벤트 타임라인"""
    rows = db.execute(text("""
        SELECT event_id, event_ym, event_type, severity,
               description, resolved_flag, resolved_ym
        FROM demo_ews_public_event
        WHERE borrower_id = :bid
        ORDER BY event_ym DESC
    """), {"bid": borrower_id}).fetchall()

    EVENT_LABEL = {
        "SEIZURE": "자산 압류",
        "TAX_DELINQUENT": "세금 체납",
        "SOCIAL_INSURANCE": "사회보험료 미납",
        "MGMT_CHANGE": "대표이사 변경",
        "AUDIT_OPINION": "감사의견 비적정",
        "COURT_ORDER": "법원 결정",
    }
    SEVERITY_STYLE = {
        "HIGH":   "bg-red-100 text-red-700",
        "MEDIUM": "bg-yellow-100 text-yellow-700",
        "LOW":    "bg-gray-100 text-gray-600",
    }

    return [
        {
            "event_id": r[0],
            "event_ym": r[1],
            "event_type": r[2],
            "event_label": EVENT_LABEL.get(r[2], r[2]),
            "severity": r[3],
            "severity_style": SEVERITY_STYLE.get(r[3], ""),
            "description": r[4],
            "resolved_flag": r[5] or 0,
            "resolved_ym": r[6],
        }
        for r in rows
    ]


@router.get("/company/{borrower_id}/news")
def get_news_monthly(borrower_id: str, db: Session = Depends(get_db)):
    """월별 뉴스 감성 집계"""
    rows = db.execute(text("""
        SELECT ym, article_count, positive_count, negative_count,
               neutral_count, avg_sentiment_score, top_category
        FROM demo_ews_news_monthly
        WHERE borrower_id = :bid
        ORDER BY ym
    """), {"bid": borrower_id}).fetchall()

    return [
        {
            "ym": r[0],
            "article_count": r[1] or 0,
            "positive_count": r[2] or 0,
            "negative_count": r[3] or 0,
            "neutral_count": r[4] or 0,
            "avg_sentiment_score": round(float(r[5] or 0), 3),
            "top_category": r[6],
        }
        for r in rows
    ]


@router.get("/company/{borrower_id}/market-signal")
def get_market_signal(borrower_id: str, db: Session = Depends(get_db)):
    """시장 신호 (상장사만)"""
    # listed 여부 확인
    company = db.execute(text(
        "SELECT listed_flag FROM demo_company WHERE borrower_id = :bid"
    ), {"bid": borrower_id}).fetchone()

    if not company or not company[0]:
        return {"listed": False, "data": []}

    rows = db.execute(text("""
        SELECT ym, stock_price_change_pct, stock_volatility_30d,
               cds_spread_bps, bond_yield_spread_bps,
               short_interest_ratio, market_cap_억
        FROM demo_ews_market_signal
        WHERE borrower_id = :bid
        ORDER BY ym
    """), {"bid": borrower_id}).fetchall()

    return {
        "listed": True,
        "data": [
            {
                "ym": r[0],
                "stock_price_change_pct": round(float(r[1] or 0), 2),
                "stock_volatility_30d": round(float(r[2] or 0), 2),
                "cds_spread_bps": round(float(r[3] or 0), 1),
                "bond_yield_spread_bps": round(float(r[4] or 0), 1),
                "short_interest_ratio": round(float(r[5] or 0), 3),
                "market_cap_억": round(float(r[6] or 0), 1),
            }
            for r in rows
        ],
    }


@router.get("/company/{borrower_id}/supply-chain")
def get_supply_chain(borrower_id: str, db: Session = Depends(get_db)):
    """공급망 위험 관계"""
    rows = db.execute(text("""
        SELECT sc.relation_id, sc.counterparty_id, sc.counterparty_name,
               sc.relation_type, sc.exposure_ratio, sc.contagion_risk_score,
               sc.is_internal_counterparty,
               COALESCE(c.company_name, sc.counterparty_name) as display_name,
               COALESCE(s.ews_grade, '?') as cp_ews_grade,
               COALESCE(s.ews_score, 0) as cp_ews_score
        FROM demo_ews_supply_chain sc
        LEFT JOIN demo_company c ON sc.counterparty_id = c.borrower_id
        LEFT JOIN demo_monthly_signal s
            ON s.borrower_id = sc.counterparty_id
            AND s.ym = (SELECT MAX(ym) FROM demo_monthly_signal WHERE borrower_id = sc.counterparty_id)
        WHERE sc.borrower_id = :bid
        ORDER BY sc.contagion_risk_score DESC
    """), {"bid": borrower_id}).fetchall()

    REL_LABEL = {"CUSTOMER": "고객사", "SUPPLIER": "공급사", "GUARANTOR": "보증인"}

    return [
        {
            "relation_id": r[0],
            "counterparty_id": r[1],
            "counterparty_name": r[7],
            "relation_type": r[3],
            "relation_label": REL_LABEL.get(r[3], r[3]),
            "exposure_ratio": round(float(r[4] or 0), 2),
            "contagion_risk_score": round(float(r[5] or 0), 1),
            "is_internal": bool(r[6]),
            "cp_ews_grade": r[8],
            "cp_ews_score": round(float(r[9] or 0), 1),
        }
        for r in rows
    ]


@router.get("/company/{borrower_id}/completeness")
def get_completeness(borrower_id: str, db: Session = Depends(get_db)):
    """데이터 완성도 프로파일"""
    # 최신 월 신호에서 tier/completeness 조회
    signal = db.execute(text("""
        SELECT ews_tier, data_completeness_pct, confidence_adj_score, ews_score, ews_grade, ym
        FROM demo_monthly_signal
        WHERE borrower_id = :bid
        ORDER BY ym DESC LIMIT 1
    """), {"bid": borrower_id}).fetchone()

    company = db.execute(text(
        "SELECT firm_size_cd, listed_flag FROM demo_company WHERE borrower_id = :bid"
    ), {"bid": borrower_id}).fetchone()

    if not signal or not company:
        return {}

    tier = signal[0] or 2
    completeness = signal[1] or 60.0
    firm_size = company[0]
    listed = bool(company[1])

    # 피처 그룹별 가용 여부
    has_transaction = db.execute(text(
        "SELECT COUNT(*) FROM demo_ews_transaction WHERE borrower_id=:bid"
    ), {"bid": borrower_id}).fetchone()[0] > 0

    has_news = db.execute(text(
        "SELECT COUNT(*) FROM demo_ews_news_monthly WHERE borrower_id=:bid"
    ), {"bid": borrower_id}).fetchone()[0] > 0

    has_market = listed and db.execute(text(
        "SELECT COUNT(*) FROM demo_ews_market_signal WHERE borrower_id=:bid"
    ), {"bid": borrower_id}).fetchone()[0] > 0

    has_public_event = db.execute(text(
        "SELECT COUNT(*) FROM demo_ews_public_event WHERE borrower_id=:bid"
    ), {"bid": borrower_id}).fetchone()[0] > 0

    has_supply_chain = db.execute(text(
        "SELECT COUNT(*) FROM demo_ews_supply_chain WHERE borrower_id=:bid"
    ), {"bid": borrower_id}).fetchone()[0] > 0

    feature_groups = [
        {"name": "재무제표", "available": True, "weight": 30},
        {"name": "거래행동", "available": has_transaction, "weight": 25},
        {"name": "공공이벤트", "available": has_public_event, "weight": 15},
        {"name": "뉴스감성", "available": has_news, "weight": 15},
        {"name": "시장신호", "available": has_market, "weight": 10},
        {"name": "공급망", "available": has_supply_chain, "weight": 5},
    ]

    tier_label = {1: "T1 (완전)", 2: "T2 (표준)", 3: "T3 (기본)"}.get(tier, "T2 (표준)")
    tier_color = {1: "text-green-700 bg-green-100", 2: "text-blue-700 bg-blue-100", 3: "text-gray-600 bg-gray-100"}.get(tier, "text-blue-700 bg-blue-100")

    return {
        "ews_tier": tier,
        "tier_label": tier_label,
        "tier_color": tier_color,
        "data_completeness_pct": round(completeness, 1),
        "confidence_adj_score": round(float(signal[2] or signal[3] or 0), 1),
        "raw_ews_score": round(float(signal[3] or 0), 1),
        "ews_grade": signal[4],
        "as_of_ym": signal[5],
        "feature_groups": feature_groups,
    }


@router.get("/alerts/summary")
def get_advanced_alert_summary(db: Session = Depends(get_db)):
    """선행지표 기반 경보 요약"""
    latest_ym = db.execute(text("SELECT MAX(ym) FROM demo_monthly_signal")).fetchone()[0] or 202512

    # 공공 이벤트 최근 3개월 건수
    ym_3m_ago = latest_ym - 3 if (latest_ym % 100) > 3 else (latest_ym - 100 + 9)
    public_events = db.execute(text("""
        SELECT event_type, COUNT(*) as cnt
        FROM demo_ews_public_event
        WHERE event_ym >= :ym AND resolved_flag = 0
        GROUP BY event_type ORDER BY cnt DESC LIMIT 5
    """), {"ym": ym_3m_ago}).fetchall()

    # 공급망 고위험 관계 (contagion >= 60)
    high_contagion = db.execute(text("""
        SELECT COUNT(DISTINCT sc.borrower_id)
        FROM demo_ews_supply_chain sc
        WHERE sc.contagion_risk_score >= 60
    """)).fetchone()[0] or 0

    # 티어별 분포
    tier_dist = db.execute(text("""
        SELECT ews_tier, COUNT(DISTINCT borrower_id)
        FROM demo_monthly_signal WHERE ym = :ym
        GROUP BY ews_tier ORDER BY ews_tier
    """), {"ym": latest_ym}).fetchall()

    # 평균 신뢰도 (C/D 등급)
    avg_confidence = db.execute(text("""
        SELECT AVG(data_completeness_pct)
        FROM demo_monthly_signal
        WHERE ym = :ym AND ews_grade IN ('C','D')
    """), {"ym": latest_ym}).fetchone()[0] or 0

    return {
        "recent_public_events": [{"event_type": r[0], "count": r[1]} for r in public_events],
        "high_contagion_companies": high_contagion,
        "tier_distribution": [{"tier": r[0], "count": r[1]} for r in tier_dist],
        "alert_avg_completeness_pct": round(float(avg_confidence), 1),
    }
