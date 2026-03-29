"""거시 국면 파라미터 (v18 → v19 분리)"""
import numpy as np

# 시간 범위
YM_START = 201701
YM_END   = 202512


def ym_add(ym: int, n: int) -> int:
    y, m = ym // 100, ym % 100
    m += n; y += (m - 1) // 12; m = (m - 1) % 12 + 1
    return y * 100 + m


def ym_diff(a: int, b: int) -> int:
    return (a // 100 - b // 100) * 12 + (a % 100 - b % 100)


# 월 목록 빌드
MONTHS = []
_ym = YM_START
while _ym <= YM_END:
    MONTHS.append(_ym)
    _ym = ym_add(_ym, 1)
N_MONTHS = len(MONTHS)          # 108
YM_INDEX = {m: i for i, m in enumerate(MONTHS)}
QUARTER_MONTHS = [m for m in MONTHS if m % 100 in (3, 6, 9, 12)]

# 거시 국면 8단계
# Tuple: (start, end, name, stress, delta_m, rate, macro_factor, fx_rate_avg)
MACRO_PHASE_DEF = [
    (201701, 201812, 'PRE_LOW_RATE_RISE',    0.15, 0.75, 1.50,  0.72, 1100),
    (201901, 201912, 'PRE_COVID_LOW_RATE',   0.20, 0.80, 1.75,  0.62, 1165),
    (202001, 202003, 'COVID_SHOCK_RAW',      0.90, 3.00, 0.50, -1.40, 1260),
    (202004, 202006, 'COVID_POLICY_SUPPORT', 0.10, 0.40, 0.50,  0.05, 1210),
    (202007, 202112, 'POLICY_RECOVERY',      0.30, 0.60, 0.75,  0.48, 1155),
    (202201, 202306, 'RATE_HIKE_STRESS',     0.65, 1.50, 3.25, -0.41, 1325),
    (202307, 202412, 'HIGH_RATE_STABLE',     0.42, 1.00, 3.50,  0.15, 1360),
    (202501, 202512, 'RATE_CUT_CYCLE',       0.28, 0.80, 2.75,  0.22, 1370),
]

PHASE_MAP: dict = {}
for _s, _e, _pn, _st, _dm, _rt, _mf, _fx in MACRO_PHASE_DEF:
    _ym2 = _s
    while _ym2 <= _e:
        PHASE_MAP[_ym2] = (_pn, _st, _dm, _rt, _mf, _fx)
        _ym2 = ym_add(_ym2, 1)

PHASE_STRESS = np.array([PHASE_MAP[m][1] for m in MONTHS])
PHASE_DM     = np.array([PHASE_MAP[m][2] for m in MONTHS])
PHASE_RATE   = np.array([PHASE_MAP[m][3] for m in MONTHS])
PHASE_MF     = np.array([PHASE_MAP[m][4] for m in MONTHS])
PHASE_FX     = np.array([PHASE_MAP[m][5] for m in MONTHS])

# FX 파라미터
FX_BASELINE = 1100.0
FX_SCALE    = 400.0
FX_COEFF    = 8.0
