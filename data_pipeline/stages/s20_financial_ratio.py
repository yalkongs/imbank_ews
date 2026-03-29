"""
s20_financial_ratio.py — 재무비율 자동 산출 (v22 신규)

테이블:
  fact_financial_ratio — 연도별 재무비율 (ml_feature_monthly 기반 역산)

지표:
  - debt_ratio        : 부채비율 = 총부채/자기자본 × 100
  - current_ratio     : 유동비율 = 유동자산/유동부채 × 100
  - ier               : 이자보상배율 = 영업이익/이자비용
  - dscr              : DSCR = EBITDA / (원리금상환액)
  - ocf_ratio         : 영업현금흐름비율
  - op_margin         : 영업이익률 = 영업이익/매출 × 100
  - roa               : ROA = 순이익/총자산 × 100
  - roe               : ROE = 순이익/자기자본 × 100
  - revenue_growth    : 매출 성장률 YoY
  - op_growth         : 영업이익 성장률 YoY
  - altman_z          : Altman Z'-Score (비상장 중소기업)
  - risk_signal       : SAFE / GREY / DANGER
"""
import time
import numpy as np
from config.macro import YM_START, YM_END


def _altman_z_prime(wc_ta, re_ta, ebit_ta, bv_eq_tl, s_ta):
    """
    Altman Z'-Score (비상장 기업용)
    Z' = 0.717*X1 + 0.847*X2 + 3.107*X3 + 0.420*X4 + 0.998*X5
    SAFE: Z' > 2.9, GREY: 1.23 < Z' ≤ 2.9, DANGER: Z' ≤ 1.23
    """
    z = (0.717 * wc_ta + 0.847 * re_ta + 3.107 * ebit_ta
         + 0.420 * bv_eq_tl + 0.998 * s_ta)
    return round(float(z), 4)


def s20_financial_ratio(conn, companies, rng):
    t0 = time.time()
    print("  [s20] 재무비율 자동 산출", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_financial_ratio")
    conn.execute("""
        CREATE TABLE fact_financial_ratio (
            ratio_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id       TEXT NOT NULL,
            fiscal_year       INTEGER NOT NULL,
            debt_ratio        REAL,
            current_ratio     REAL,
            ier               REAL,
            dscr              REAL,
            ocf_ratio         REAL,
            op_margin         REAL,
            roa               REAL,
            roe               REAL,
            revenue_growth    REAL,
            op_growth         REAL,
            altman_z          REAL,
            risk_signal       TEXT,
            UNIQUE(borrower_id, fiscal_year)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fratio_bid ON fact_financial_ratio(borrower_id)")

    # ml_feature_monthly에서 연간 재무 피처 집계
    # YM 기준 각 연도의 12월 데이터(혹은 마지막 달) 사용
    years = list(range(YM_START // 100, YM_END // 100 + 1))

    rows = []
    BATCH = 20_000

    for c in companies:
        bid = c['borrower_id']
        default_flag = c['default_flag']
        exit_ym = c.get('exit_ym') or (YM_END + 1)
        entry_ym = c.get('entry_ym') or YM_START
        firm_size = c.get('firm_size_cd', 'S')

        prev_revenue = None
        prev_op_profit = None

        for yr in years:
            yr_ym = yr * 100 + 12
            if yr_ym < entry_ym or yr_ym >= exit_ym:
                continue

            # ml_feature_label에서 해당 연도 피처 조회 (12월 또는 마지막 달)
            feat = conn.execute("""
                SELECT debt_to_equity_ratio, interest_coverage_ratio, dscr_ratio,
                       ebitda_margin_pct, sales_growth_pct
                FROM ml_feature_label
                WHERE borrower_id=? AND ym=?
            """, (bid, yr_ym)).fetchone()

            if feat:
                dte, icr, de_ratio, ebitda_margin, rev_growth = feat
                ocf_r = None
            else:
                # 해당 월 데이터 없으면 해당 연도 데이터 중 마지막 달 사용
                feat = conn.execute("""
                    SELECT debt_to_equity_ratio, interest_coverage_ratio, dscr_ratio,
                           ebitda_margin_pct, sales_growth_pct
                    FROM ml_feature_label
                    WHERE borrower_id=? AND ym BETWEEN ? AND ?
                    ORDER BY ym DESC LIMIT 1
                """, (bid, yr * 100 + 1, yr * 100 + 12)).fetchone()
                if feat:
                    dte, icr, de_ratio, ebitda_margin, rev_growth = feat
                    ocf_r = None
                else:
                    continue

            # 부도 기업은 exit 전 악화 반영
            months_to_exit = ((exit_ym - yr_ym) if default_flag and exit_ym <= YM_END else 999)
            deterioration = max(0.0, 1.0 - months_to_exit / 24.0) if months_to_exit < 24 else 0.0

            # 재무비율 계산
            debt_ratio = float(de_ratio * 100) if de_ratio is not None else None

            # 유동비율: ICR 높으면 유동비율도 높은 경향
            if icr is not None:
                current_ratio = float(np.clip(
                    100 + icr * 20 - deterioration * 80 + rng.normal(0, 15),
                    10, 500
                ))
            else:
                current_ratio = None

            ier = float(icr) if icr is not None else None

            # DSCR = EBITDA / (원리금) — ebitda_margin에서 역산
            if ebitda_margin is not None:
                dscr = float(np.clip(
                    ebitda_margin / 100.0 * rng.uniform(1.5, 4.0) - deterioration * 1.5,
                    -1.0, 10.0
                ))
            else:
                dscr = None

            ocf_ratio = float(ocf_r) if ocf_r is not None else None
            op_margin = float(ebitda_margin * 0.7) if ebitda_margin is not None else None

            # ROA, ROE
            if dte is not None and op_margin is not None:
                roa = float(np.clip(op_margin * 0.6 + rng.normal(0, 2), -30, 30))
                equity_ratio = 1.0 / (1.0 + dte) if dte > 0 else 0.5
                roe = float(np.clip(roa / max(equity_ratio, 0.01), -50, 50))
            else:
                roa, roe = None, None

            revenue_growth = float(rev_growth) if rev_growth is not None else None
            op_growth = float(revenue_growth * rng.uniform(0.5, 1.5)) if revenue_growth is not None else None

            # Altman Z'-Score
            # X1 = 운전자본/총자산, X2 = 이익잉여금/총자산, X3 = EBIT/총자산
            # X4 = 장부가자본/총부채, X5 = 매출/총자산
            if dte is not None and op_margin is not None:
                total_assets = 1.0  # 정규화
                debt_ta = dte / (1 + dte) if dte > 0 else 0.3
                equity_ta = 1.0 - debt_ta
                x1 = float(np.clip(equity_ta * 0.3 - deterioration * 0.2, -0.3, 0.5))
                x2 = float(np.clip(equity_ta * 0.4 - deterioration * 0.3, -0.5, 0.6))
                x3 = float(np.clip(op_margin / 100.0 * 0.8, -0.3, 0.4))
                x4 = float(np.clip(equity_ta / max(debt_ta, 0.01) * 0.5, 0.0, 5.0))
                x5 = float(np.clip(0.8 + rng.normal(0, 0.15) - deterioration * 0.3, 0.1, 3.0))
                altman_z = _altman_z_prime(x1, x2, x3, x4, x5)
            else:
                altman_z = None

            if altman_z is not None:
                if altman_z > 2.9:
                    risk_signal = "SAFE"
                elif altman_z > 1.23:
                    risk_signal = "GREY"
                else:
                    risk_signal = "DANGER"
            else:
                risk_signal = None

            rows.append((
                bid, yr,
                round(debt_ratio, 2) if debt_ratio is not None else None,
                round(current_ratio, 1) if current_ratio is not None else None,
                round(ier, 3) if ier is not None else None,
                round(dscr, 3) if dscr is not None else None,
                round(ocf_ratio, 4) if ocf_ratio is not None else None,
                round(op_margin, 2) if op_margin is not None else None,
                round(roa, 2) if roa is not None else None,
                round(roe, 2) if roe is not None else None,
                round(revenue_growth, 4) if revenue_growth is not None else None,
                round(op_growth, 4) if op_growth is not None else None,
                altman_z,
                risk_signal,
            ))

            if len(rows) >= BATCH:
                conn.executemany("""
                    INSERT OR IGNORE INTO fact_financial_ratio
                      (borrower_id, fiscal_year, debt_ratio, current_ratio,
                       ier, dscr, ocf_ratio, op_margin, roa, roe,
                       revenue_growth, op_growth, altman_z, risk_signal)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, rows)
                conn.commit()
                rows = []

    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO fact_financial_ratio
              (borrower_id, fiscal_year, debt_ratio, current_ratio,
               ier, dscr, ocf_ratio, op_margin, roa, roe,
               revenue_growth, op_growth, altman_z, risk_signal)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM fact_financial_ratio").fetchone()[0]
    # Altman Z 분포 확인
    z_dist = conn.execute(
        "SELECT risk_signal, COUNT(*) FROM fact_financial_ratio GROUP BY 1"
    ).fetchall()
    elapsed = round(time.time() - t0, 1)
    print(f"    fact_financial_ratio: {total:,}행", flush=True)
    for sig, cnt in z_dist:
        print(f"      {sig}: {cnt:,}행", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
