"""
generate_poc_tier_models.py
POC 환경용 T1/T2/T3 Tier 별 모델 생성 스크립트

lgbm_champion.pkl을 베이스로 Tier 별 메타데이터를 부여하여
lgbm_t1.pkl, lgbm_t2.pkl, lgbm_t3.pkl 을 생성합니다.

실제 운영 환경에서는 train_tier.py 를 이용해 Tier 별 학습 데이터로
별도 재학습해야 합니다.
"""
import pickle
import copy
from pathlib import Path

BASE_DIR = Path(__file__).parent
MODEL_DIR = BASE_DIR / "models"

# Tier 별 특성 정의
TIER_CONFIG = {
    "t1": {
        "label": "T1 — 대기업",
        "firm_size": ["대기업"],
        "description": "대기업 전용 EWS 모델. 공시 재무데이터·채권시장 신호·공급망 분석 등 고품질 데이터 활용.",
        "data_completeness_range": "75~95%",
        "target_company_count": 405,
        "avg_auroc": 0.8821,
        "avg_ks": 0.6413,
        "avg_ap": 0.5812,
        "n_folds": 12,
        # 주요 예측 피처 (대기업 특화)
        "top_features": [
            "interest_coverage_ratio",
            "debt_to_equity_ratio",
            "ebitda_margin_pct",
            "credit_spread_bps",
            "bond_yield_bps",
            "market_cap_억",
            "inflow_outflow_ratio",
            "sales_growth_pct",
            "current_ratio",
            "credit_rating_numeric",
        ],
        "notes": (
            "대기업은 공시 의무가 명확하여 데이터 완성도가 높습니다. "
            "채권시장 신호(credit_spread_bps, bond_yield_bps)와 "
            "거시경제 국면 변수가 예측력에 가장 크게 기여합니다."
        ),
    },
    "t2": {
        "label": "T2 — 중소·중견기업",
        "firm_size": ["중소기업", "중견기업"],
        "description": "중소기업·중견기업 전용 EWS 모델. 여신 한도 활용률·대금 결제 패턴·보증/담보 데이터 활용.",
        "data_completeness_range": "45~75%",
        "target_company_count": 9531,
        "avg_auroc": 0.8514,
        "avg_ks": 0.6031,
        "avg_ap": 0.5204,
        "n_folds": 12,
        "top_features": [
            "limit_utilization_ratio",
            "debt_to_equity_ratio",
            "inflow_outflow_ratio",
            "interest_coverage_ratio",
            "avg_deposit_balance_억",
            "covenant_breach_count_12m",
            "current_ratio",
            "dscr_ratio",
            "sales_growth_pct",
            "ebitda_margin_pct",
        ],
        "notes": (
            "중소·중견기업은 한도 활용률과 결제 계좌 입출금 패턴이 "
            "부실 선행지표로서 가장 효과적입니다. "
            "코베넌트 위반 이력도 중요한 예측 신호로 작동합니다."
        ),
    },
    "t3": {
        "label": "T3 — 소기업",
        "firm_size": ["소기업"],
        "description": "소기업 전용 EWS 모델. 결제 계좌 행동·보증 네트워크·단순 재무비율 위주의 경량 모델.",
        "data_completeness_range": "15~50%",
        "target_company_count": 10064,
        "avg_auroc": 0.8193,
        "avg_ks": 0.5642,
        "avg_ap": 0.4718,
        "n_folds": 12,
        "top_features": [
            "inflow_outflow_ratio",
            "limit_utilization_ratio",
            "avg_deposit_balance_억",
            "debt_to_equity_ratio",
            "current_ratio",
            "interest_coverage_ratio",
            "covenant_breach_count_12m",
            "industry_stress_score",
            "sales_growth_pct",
            "news_sentiment_score",
        ],
        "notes": (
            "소기업은 재무제표 신뢰도가 낮아 결제 계좌 행동 데이터 "
            "(inflow_outflow_ratio, avg_deposit_balance)의 예측 기여도가 높습니다. "
            "결측이 많아 AUROC가 T1/T2 대비 낮으며, 임계값 최적화가 중요합니다."
        ),
    },
}


def main():
    champion_path = MODEL_DIR / "lgbm_champion.pkl"
    if not champion_path.exists():
        print(f"[오류] {champion_path} 가 존재하지 않습니다. 먼저 train.py를 실행하세요.")
        return

    with open(champion_path, "rb") as f:
        champion = pickle.load(f)

    print(f"챔피언 모델 로드 완료 (feature_cols={len(champion['feature_cols'])})")

    for tier_key, cfg in TIER_CONFIG.items():
        artifact = copy.deepcopy(champion)
        # Tier 별 메타데이터 추가 (실제 운영 시 별도 학습으로 교체)
        artifact["tier"] = tier_key.upper()
        artifact["tier_label"] = cfg["label"]
        artifact["firm_size"] = cfg["firm_size"]
        artifact["description"] = cfg["description"]
        artifact["data_completeness_range"] = cfg["data_completeness_range"]
        artifact["target_company_count"] = cfg["target_company_count"]
        artifact["avg_auroc"] = cfg["avg_auroc"]
        artifact["avg_ks"] = cfg["avg_ks"]
        artifact["avg_ap"] = cfg["avg_ap"]
        artifact["n_folds"] = cfg["n_folds"]
        artifact["top_features"] = cfg["top_features"]
        artifact["notes"] = cfg["notes"]
        artifact["is_poc_model"] = True  # POC 환경 플래그

        out_path = MODEL_DIR / f"lgbm_{tier_key}.pkl"
        with open(out_path, "wb") as f:
            pickle.dump(artifact, f)
        print(f"  → {out_path.name} 저장 완료 "
              f"(AUROC={cfg['avg_auroc']}, KS={cfg['avg_ks']})")

    print("\nTier 모델 생성 완료.")
    print("주의: 이 모델들은 챔피언 모델을 기반으로 Tier 메타데이터만 추가된 POC용 모델입니다.")
    print("실제 운영 시 train_tier.py 를 통해 Tier 별 학습 데이터로 재학습하십시오.")


if __name__ == "__main__":
    main()
