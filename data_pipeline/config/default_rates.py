"""업종별 기본 부도율 및 CONTAGION 파라미터 (v20: EDA 실제 부도율 반영)

v19 → v20 변경사항:
  금융보험업  base_dr: 0.020 → 0.050  (EDA 실제DR 괴리 수정)
  정보통신업  base_dr: 0.022 → 0.040  (EDA 실제DR 괴리 수정)
  에너지환경업 base_dr: 0.020 → 0.035  (EDA 실제DR 괴리 수정)
"""
from config.macro import PHASE_MAP

# 업종별 기본 부도율 승수 (기업 규모별 base_dr에 곱함)
IND_DEFAULT_MULT = {
    '숙박업':      1.45,
    '건설업':      1.20,
    '부동산업':    1.10,
    '음식업':      1.05,
    '도매소매업':  1.05,
    '기타서비스':  1.05,
    '교육서비스업':0.85,
    '농림어업':    0.65,
    '보건사회복지':0.50,
    '첨단제조업':  0.80,
    '에너지환경업':0.70,
    # 일반제조업: 1.0 (기본값)
}

# CONTAGION 설정
CONTAGION_PROB       = 0.40     # 기본 CONTAGION 확률
CONTAGION_LAG        = (3, 7)   # 보증인 부도 후 연쇄부도 지연 범위 (개월)
CONTAGION_CHAIN_PROB = 0.50     # 2차 체인 전파 확률 (1차 확률 대비)

CONTAGION_PHASE_PROB = {
    'COVID_SHOCK_RAW':      0.60,
    'RATE_HIKE_STRESS':     0.55,
    'HIGH_RATE_STABLE':     0.48,
    'RATE_CUT_CYCLE':       0.38,
    'COVID_POLICY_SUPPORT': 0.25,
    'POLICY_RECOVERY':      0.30,
    'PRE_LOW_RATE_RISE':    0.32,
    'PRE_COVID_LOW_RATE':   0.30,
}

# 업종별 보증 친화 관계 (원청-하청 구조)
IND_GUARANTEE_AFFINITY = {
    '건설업':      {'건설업': 3.5, '일반제조업': 2.0, '운수창고업': 1.8, '도매소매업': 1.2},
    '일반제조업':  {'일반제조업': 2.5, '도매소매업': 1.8, '운수창고업': 1.5, '건설업': 1.2},
    '첨단제조업':  {'첨단제조업': 2.0, '일반제조업': 1.5, '정보통신업': 1.3},
    '도매소매업':  {'도매소매업': 2.0, '일반제조업': 1.5, '운수창고업': 1.2},
    '정보통신업':  {'정보통신업': 2.5, '전문과학기술': 2.0, '첨단제조업': 1.5},
    '부동산업':    {'부동산업': 2.0, '건설업': 1.8},
    '금융보험업':  {},
    '에너지환경업':{},
}


def get_contagion_prob(def_ym: int) -> float:
    """부도 발생 월의 거시 국면에 따른 CONTAGION 확률 반환"""
    from config.macro import YM_END
    phase_name = PHASE_MAP.get(def_ym, PHASE_MAP[YM_END])[0]
    return CONTAGION_PHASE_PROB.get(phase_name, CONTAGION_PROB)


def base_dr_for_ind(ind: str) -> float:
    """업종별 기준 부도율 (ref_industry_stress 계산용)"""
    mapping = {
        '일반제조업':   0.04,
        '첨단제조업':   0.025,
        '건설업':       0.06,
        '도매소매업':   0.05,
        '금융보험업':   0.050,   # v20: 0.020 → 0.050
        '정보통신업':   0.040,   # v20: 0.022 → 0.040
        '부동산업':     0.05,
        '숙박업':       0.10,
        '음식업':       0.065,
        '운수창고업':   0.04,
        '전문과학기술': 0.03,
        '기타서비스':   0.05,
        '에너지환경업': 0.035,   # v20: 0.020 → 0.035
    }
    return mapping.get(ind, 0.04)
