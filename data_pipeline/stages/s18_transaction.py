"""
s18_transaction.py — 거래행태 월별 데이터 생성 (v23 개선)

v23 개선:
  - Sigmoid 악화 곡선 적용 (선형 deterioration 대체 → exit 직전 급격 악화 표현)
  - salary_transfer 소멸 확률 경로별 분기 (ACUTE/CHRONIC/EVENT)

테이블:
  fact_transaction_behavior — 차주별 월별 자행 거래 행태

피처:
  - limit_utilization    : 한도소진율 (0~1) — 급상승 시 유동성 위기 신호
  - deposit_outflow_rate : 예금유출률 (0~1) — 큰 유출은 운전자금 부족
  - payment_delay_days   : 결제지연일수 — 내부 거래 지연
  - salary_transfer      : 급여이체 여부 — 소멸 시 핵심 경보
  - avg_balance_억        : 평잔
  - transaction_count    : 거래건수
  - overdraft_count      : 당좌대월 발생 횟수
  - card_payment_ratio   : 카드결제 비중
  - foreign_transfer_ratio: 해외송금 비중 (자본유출 위험)
"""
import time

import numpy as np

from config.macro import YM_START, YM_END, MONTHS, PHASE_MAP
from config.companies import get_size_code


def _phase_stress(ym):
    """해당 월의 거시 스트레스 계수"""
    entry = PHASE_MAP.get(ym)
    if entry is not None:
        return entry[1]  # stress 값은 튜플의 두 번째 원소
    return 0.3


def s18_transaction_behavior(conn, companies, rng):
    t0 = time.time()
    print("  [s18] 거래행태 월별 데이터 생성", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_transaction_behavior")
    conn.execute("""
        CREATE TABLE fact_transaction_behavior (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id          TEXT NOT NULL,
            reference_ym         INTEGER NOT NULL,
            avg_balance_억        REAL,
            limit_utilization    REAL,
            deposit_outflow_rate REAL,
            payment_delay_days   INTEGER,
            salary_transfer      INTEGER,
            transaction_count    INTEGER,
            overdraft_count      INTEGER,
            card_payment_ratio   REAL,
            foreign_transfer_ratio REAL,
            behavior_score       REAL,
            behavior_signal      TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_txbeh_bid_ym
        ON fact_transaction_behavior(borrower_id, reference_ym)
    """)

    bid_to_company = {c['borrower_id']: c for c in companies}

    rows = []
    BATCH = 50_000

    for c in companies:
        bid = c['borrower_id']
        default_flag = c['default_flag']
        exit_ym = c.get('exit_ym') or YM_END + 1
        entry_ym = c.get('entry_ym') or YM_START
        firm_size = get_size_code(c.get('firm_size_cd', '소기업'))
        credit_limit = float(c.get('credit_limit_억') or c.get('asset_size_억', 10.0) or 10.0)

        # 기업 기초 행태 파라미터
        base_utilization = rng.uniform(0.20, 0.60)
        base_balance = credit_limit * rng.uniform(0.3, 1.5)
        base_tx_count = {"L": 150, "M": 80, "S": 30}.get(firm_size, 30) + int(rng.integers(-15, 15))

        # 경로별 salary_transfer 소멸 시작 기준
        path_type = c.get('default_path_type') or 'ACUTE'
        if path_type == 'CHRONIC':
            salary_deterioration_window = 18  # 18개월 전부터 점진 소멸
        elif path_type == 'EVENT':
            salary_deterioration_window = 6   # 이벤트 후 급격 소멸
        else:
            salary_deterioration_window = 12  # ACUTE/CONTAGION: 12개월

        # 초기 salary_transfer 상태 (대기업은 거의 항상 1)
        has_salary = 1 if firm_size == 'L' else (1 if rng.random() < 0.72 else 0)

        prev_utilization = base_utilization

        for ym in MONTHS:
            if ym < entry_ym or ym >= exit_ym:
                continue

            phase_stress = _phase_stress(ym)
            months_to_exit = (exit_ym - ym) if default_flag and exit_ym <= YM_END else 999

            # 부도 기업 악화 곡선 (Sigmoid: exit 직전 급격 악화, 24개월 전부터)
            if default_flag and exit_ym <= YM_END and months_to_exit <= 24:
                t = months_to_exit / 24.0  # 1.0 → 0.0 (exit 가까울수록 0)
                deterioration = float(1.0 / (1.0 + np.exp(6.0 * (t - 0.5))))
            else:
                deterioration = 0.0

            # 한도소진율 (부도 기업은 exit 전 급상승)
            util_drift = deterioration * 0.55 + phase_stress * 0.08
            noise = rng.normal(0, 0.04)
            utilization = float(np.clip(prev_utilization + util_drift * 0.15 + noise, 0.01, 0.99))
            prev_utilization = utilization * 0.7 + base_utilization * 0.3

            # 예금유출률
            outflow_base = 0.05 + deterioration * 0.40 + phase_stress * 0.05
            deposit_outflow = float(np.clip(outflow_base + rng.normal(0, 0.03), 0.0, 0.95))

            # 결제지연일수
            delay_base = int(deterioration * 20 + phase_stress * 5)
            payment_delay = max(0, int(delay_base + rng.integers(-3, 10)))

            # 급여이체 (경로별 소멸 확률 분기)
            if has_salary == 1 and default_flag and months_to_exit <= salary_deterioration_window:
                # Sigmoid 기반 소멸 확률: 창 초반 낮고 exit 직전 급등
                t_sal = months_to_exit / salary_deterioration_window
                salary_exit_prob = 0.02 + 0.10 * (1.0 / (1.0 + np.exp(5.0 * (t_sal - 0.3))))
                if rng.random() < salary_exit_prob:
                    has_salary = 0  # 급여이체 소멸
            salary_transfer = has_salary

            # 평잔
            balance = max(0.1, base_balance * (1 - deterioration * 0.6) * rng.uniform(0.7, 1.3))

            # 거래건수
            tx_count = max(1, int(base_tx_count * (1 - deterioration * 0.3) + rng.integers(-10, 10)))

            # 당좌대월
            overdraft = int(rng.integers(0, max(1, int(deterioration * 8 + 1))))

            # 카드결제 비중
            card_ratio = float(np.clip(0.15 + rng.normal(0, 0.05), 0.0, 0.9))

            # 해외송금 비중 (자본유출)
            fx_ratio = float(np.clip(deterioration * 0.15 + rng.uniform(0, 0.05), 0.0, 0.5))

            # 행태 점수 (0~1, 높을수록 위험)
            bscore = (
                utilization * 0.30
                + deposit_outflow * 0.25
                + min(payment_delay / 30.0, 1.0) * 0.20
                + (1 - salary_transfer) * 0.15
                + min(overdraft / 5.0, 1.0) * 0.10
            )
            bscore = float(np.clip(bscore, 0.0, 1.0))

            if bscore >= 0.70:
                signal = "CRITICAL"
            elif bscore >= 0.50:
                signal = "WARNING"
            elif bscore >= 0.30:
                signal = "CAUTION"
            else:
                signal = "NORMAL"

            rows.append((
                bid, ym,
                round(balance, 2),
                round(utilization, 4),
                round(deposit_outflow, 4),
                payment_delay,
                salary_transfer,
                tx_count,
                overdraft,
                round(card_ratio, 4),
                round(fx_ratio, 4),
                round(bscore, 4),
                signal,
            ))

            if len(rows) >= BATCH:
                conn.executemany("""
                    INSERT INTO fact_transaction_behavior
                      (borrower_id, reference_ym, avg_balance_억,
                       limit_utilization, deposit_outflow_rate,
                       payment_delay_days, salary_transfer,
                       transaction_count, overdraft_count,
                       card_payment_ratio, foreign_transfer_ratio,
                       behavior_score, behavior_signal)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, rows)
                conn.commit()
                rows = []

    if rows:
        conn.executemany("""
            INSERT INTO fact_transaction_behavior
              (borrower_id, reference_ym, avg_balance_억,
               limit_utilization, deposit_outflow_rate,
               payment_delay_days, salary_transfer,
               transaction_count, overdraft_count,
               card_payment_ratio, foreign_transfer_ratio,
               behavior_score, behavior_signal)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM fact_transaction_behavior").fetchone()[0]
    elapsed = round(time.time() - t0, 1)
    print(f"    fact_transaction_behavior: {total:,}행", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
