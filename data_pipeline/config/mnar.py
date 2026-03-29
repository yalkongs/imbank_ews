"""MNAR(Missing Not At Random) 파라미터 (v18 → v19 분리)"""

# 기업 규모별 기본 결측 확률
BASE_MNAR = {
    '대기업':  0.02,
    '중견기업':0.05,
    '중소기업':0.12,
    '소기업':  0.14,
}

# 비상장 기업 추가 결측 확률
UNLISTED_ADD = 0.06

# 업종별 추가 결측 확률 (v18: 16개 업종)
IND_ADD = {
    '건설업':      0.05,
    '숙박업':      0.08,
    '음식업':      0.06,
    '부동산업':    0.03,
    '도매소매업':  0.02,
    '농림어업':    0.12,
    '교육서비스업':0.05,
    '보건사회복지':0.03,
    '첨단제조업':  0.03,   # R&D기업 외감지연
    '에너지환경업':0.02,
}

# 결측 확률 상한
MP_CAP = 0.45

# 피처별 결측 비율 (기업별 mp 기준)
# ebitda_margin: mp * 100%
# dscr_ratio: mp * 80%
# sales_growth_pct: mp * 60%
FEATURE_MP_RATIO = {
    'ebitda_margin_pct': 1.00,
    'dscr_ratio':        0.80,
    'sales_growth_pct':  0.60,
}

# 계좌 유입 노이즈 (account inflow noise)
INFLOW_NOISE_PROB  = 0.08   # 8% 행에 노이즈 추가
INFLOW_NOISE_RANGE = 15     # ±15% 범위


def calc_mp(firm_size_cd: str, listed_flag: int, industry_category: str) -> float:
    """기업별 결측 확률 계산"""
    mp = BASE_MNAR[firm_size_cd]
    if not listed_flag:
        mp += UNLISTED_ADD
    mp += IND_ADD.get(industry_category, 0)
    return min(mp, MP_CAP)
