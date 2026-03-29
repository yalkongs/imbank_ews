"""
s22_market_signal.py — 시장신호 데이터 생성 (v22 신규, 상장사 한정)

테이블:
  fact_market_signal — 월별 시장 기반 신용 신호

피처:
  - stock_price_change  : 주가 변동률 MoM (%)
  - stock_volatility_30d: 30일 주가 변동성
  - market_cap_억        : 시가총액
  - cds_spread_bp       : CDS 스프레드 (bp) — 부도 보험료
  - bond_spread_bp      : 채권스프레드 (국고채 대비, bp)
  - distance_to_default : Merton 부도거리 (높을수록 안전)
  - implied_pd          : 시장 내재 PD (0~1)
  - market_signal       : NORMAL / WARNING / CRITICAL

대상: listed_flag=1 기업만 (약 3,000~4,000개)
"""
import time
import numpy as np
from config.macro import YM_START, YM_END, MONTHS, PHASE_MAP
try:
    from scipy.stats import norm as _scipy_norm
    _NORM_CDF = _scipy_norm.cdf
except ImportError:
    _NORM_CDF = None

# 주식시장 연간 변동률 (시장 베타)
MARKET_RETURN = {
    2017: +21.8, 2018: -17.3, 2019: +7.7, 2020: +30.8, 2021: +3.6,
    2022: -24.9, 2023: +18.7, 2024: +9.2, 2025: +5.4,
}

# 시장 CDS 기준 (bp, 한국 IG 시장)
MARKET_CDS_BASE = {
    2017: 55, 2018: 75, 2019: 60, 2020: 120, 2021: 65,
    2022: 110, 2023: 85, 2024: 75, 2025: 70,
}


def _phase_stress(ym):
    entry = PHASE_MAP.get(ym)
    if entry is not None:
        return entry[1]  # stress 값은 튜플의 두 번째 원소
    return 0.3


def s22_market_signal(conn, companies, rng):
    t0 = time.time()
    print("  [s22] 시장신호 데이터 생성 (상장사 한정)", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_market_signal")
    conn.execute("""
        CREATE TABLE fact_market_signal (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id          TEXT NOT NULL,
            reference_ym         INTEGER NOT NULL,
            stock_price_change   REAL,
            stock_volatility_30d REAL,
            market_cap_억         REAL,
            cds_spread_bp        REAL,
            bond_spread_bp       REAL,
            distance_to_default  REAL,
            implied_pd           REAL,
            market_signal        TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_mkt_bid_ym
        ON fact_market_signal(borrower_id, reference_ym)
    """)

    # 상장사만 필터
    listed = [c for c in companies if c.get('listed_flag') == 1]
    print(f"    상장사 {len(listed):,}개 처리", flush=True)

    rows = []
    BATCH = 50_000

    for c in listed:
        bid = c['borrower_id']
        default_flag = c['default_flag']
        exit_ym = c.get('exit_ym') or (YM_END + 1)
        entry_ym = c.get('entry_ym') or YM_START
        firm_size = c.get('firm_size_cd', 'S')

        # 기업 고유 파라미터
        beta = rng.uniform(0.6, 1.8)           # 시장 베타
        base_cap = float(c.get('asset_size_억', 100.0) or 100.0) * rng.uniform(0.5, 3.0)
        base_cds = MARKET_CDS_BASE.get(YM_START // 100, 70) * rng.uniform(0.5, 2.5)
        idio_vol = rng.uniform(0.10, 0.35)     # 개별 변동성

        prev_cap = base_cap
        prev_dtd = rng.uniform(2.0, 6.0)       # 초기 부도거리

        for ym in MONTHS:
            if ym < entry_ym or ym >= exit_ym:
                continue

            yr = ym // 100
            phase_stress = _phase_stress(ym)
            mkt_return = MARKET_RETURN.get(yr, 0.0) / 12.0  # 월간 환산

            months_to_exit = (exit_ym - ym) if default_flag and exit_ym <= YM_END else 999
            deterioration = max(0.0, 1.0 - months_to_exit / 24.0) if months_to_exit < 24 else 0.0

            # 주가 변동률
            idio_return = rng.normal(-deterioration * 0.05, idio_vol / 3.46)
            stock_change = float(beta * mkt_return / 100.0 + idio_return) * 100.0

            # 시가총액
            cap_change = 1.0 + stock_change / 100.0 + rng.normal(0, 0.02)
            market_cap = max(0.1, prev_cap * cap_change)
            prev_cap = market_cap * 0.8 + base_cap * 0.2

            # 30일 변동성
            vol = float(np.clip(idio_vol + deterioration * 0.20 + phase_stress * 0.05
                                + rng.normal(0, 0.02), 0.05, 0.80))

            # CDS 스프레드
            cds_base = MARKET_CDS_BASE.get(yr, 70)
            cds = float(np.clip(
                base_cds + cds_base * 0.3 + deterioration * 500 + phase_stress * 80
                + rng.normal(0, 20), 10, 2000
            ))

            # 채권 스프레드
            bond_spread = float(np.clip(cds * 0.7 + rng.normal(0, 15), 5, 1500))

            # Merton 부도거리 (악화 시 감소)
            dtd_drift = -deterioration * 3.0 - phase_stress * 0.5 + rng.normal(0, 0.3)
            dtd = float(np.clip(prev_dtd + dtd_drift * 0.2, 0.01, 15.0))
            prev_dtd = dtd * 0.8 + 3.0 * 0.2

            # 내재 PD (정규분포 역함수로 DTD → PD)
            # PD ≈ N(-DTD)
            if _NORM_CDF is not None:
                implied_pd = float(np.clip(_NORM_CDF(-dtd), 0.0001, 0.9999))
            else:
                implied_pd = float(np.clip(0.5 - dtd * 0.1, 0.001, 0.999))

            # 시장 신호
            if implied_pd > 0.15 or cds > 500:
                signal = "CRITICAL"
            elif implied_pd > 0.05 or cds > 200:
                signal = "WARNING"
            else:
                signal = "NORMAL"

            rows.append((
                bid, ym,
                round(stock_change, 3),
                round(vol, 4),
                round(market_cap, 2),
                round(cds, 1),
                round(bond_spread, 1),
                round(dtd, 4),
                round(implied_pd, 6),
                signal,
            ))

            if len(rows) >= BATCH:
                conn.executemany("""
                    INSERT INTO fact_market_signal
                      (borrower_id, reference_ym, stock_price_change,
                       stock_volatility_30d, market_cap_억,
                       cds_spread_bp, bond_spread_bp,
                       distance_to_default, implied_pd, market_signal)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, rows)
                conn.commit()
                rows = []

    if rows:
        conn.executemany("""
            INSERT INTO fact_market_signal
              (borrower_id, reference_ym, stock_price_change,
               stock_volatility_30d, market_cap_억,
               cds_spread_bp, bond_spread_bp,
               distance_to_default, implied_pd, market_signal)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM fact_market_signal").fetchone()[0]
    elapsed = round(time.time() - t0, 1)
    print(f"    fact_market_signal: {total:,}행", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
