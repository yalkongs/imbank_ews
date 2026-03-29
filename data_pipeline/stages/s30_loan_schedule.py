"""
s30_loan_schedule.py — 여신 상환 스케줄 생성 (v23 신규)

테이블:
  fact_loan_schedule — 여신별 월별 원리금 상환 스케줄

상환 방식:
  BULLET      — 만기 일시상환 (단기운전자금 多)
  INSTALLMENT — 원금균등 분할상환
  ANNUITY     — 원리금균등 분할상환 (가장 일반적)
  REVOLVING   — 한도대출 (자동 재조달)

부도 기업은 실제 상환 여부를 delinquency와 연동하여 생성.

단위: 억원
"""
import time
import numpy as np
from config.macro import YM_START, YM_END, MONTHS, ym_add
from config.companies import get_size_code

REPAYMENT_METHODS = ["BULLET", "INSTALLMENT", "ANNUITY", "REVOLVING"]

# 기업 규모·업종별 상환방식 선호도
METHOD_PROBS = {
    "L": [0.20, 0.25, 0.40, 0.15],  # 대기업: ANNUITY 多
    "M": [0.25, 0.30, 0.35, 0.10],
    "S": [0.40, 0.20, 0.25, 0.15],  # 소기업: BULLET 多 (단기)
}

# 업종별 금리 기준 (%)
IND_RATE = {
    "K00": 4.5, "K01A": 4.2, "K01B": 3.8, "K02": 4.8, "K03": 3.9,
    "K04": 4.3, "K05": 3.5, "K06": 3.2, "K07": 4.0, "K08": 4.0,
    "K09": 4.2, "K10": 4.5, "K11": 4.8, "K12": 4.3, "K13": 4.6,
}


def _annuity_payment(principal, rate_monthly, n_months):
    """원리금균등 월 납입액"""
    if rate_monthly == 0 or n_months == 0:
        return principal / n_months if n_months > 0 else 0.0
    return principal * rate_monthly * (1 + rate_monthly) ** n_months / ((1 + rate_monthly) ** n_months - 1)


def s30_loan_schedule(conn, companies, rng):
    t0 = time.time()
    print("  [s30] 여신 상환 스케줄 생성", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_loan_schedule")
    conn.execute("""
        CREATE TABLE fact_loan_schedule (
            schedule_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id          TEXT NOT NULL,
            facility_id          TEXT NOT NULL,
            payment_ym           INTEGER NOT NULL,
            repayment_method     TEXT NOT NULL,
            scheduled_principal_억 REAL,
            scheduled_interest_억  REAL,
            scheduled_total_억     REAL,
            actual_principal_억   REAL,
            actual_interest_억    REAL,
            actual_total_억        REAL,
            outstanding_balance_억 REAL,
            interest_rate_annual  REAL,
            days_past_due        INTEGER DEFAULT 0,
            payment_status       TEXT DEFAULT 'ON_SCHEDULE',
            UNIQUE(facility_id, payment_ym)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_bid ON fact_loan_schedule(borrower_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_fac ON fact_loan_schedule(facility_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_ym  ON fact_loan_schedule(payment_ym)")

    # 여신 목록
    facilities = conn.execute(
        "SELECT f.facility_id, f.borrower_id, f.committed_amount_억, "
        "       c.default_flag, c.exit_ym, c.entry_ym, c.industry_cd, c.firm_size_cd "
        "FROM dim_facility f JOIN dim_company c ON f.borrower_id = c.borrower_id"
    ).fetchall()

    # DPD 캐시 (부실 여신 상환 지연용)
    dpd_cache = {}
    if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fact_delinquency'"
    ).fetchone():
        for row in conn.execute(
            "SELECT borrower_id, overdue_ym, max_dpd FROM fact_delinquency"
        ).fetchall():
            key = (row[0], row[1])
            dpd_cache[key] = max(dpd_cache.get(key, 0), int(row[2]) if row[2] else 0)

    bid_to_company = {c['borrower_id']: c for c in companies}

    rows = []
    BATCH = 100_000

    for fac in facilities:
        fac_id, bid, limit_억, default_flag, exit_ym, entry_ym, ind, firm_size_cd = fac
        exit_ym = exit_ym or YM_END + 1
        entry_ym = entry_ym or YM_START
        ind = ind or 'K01A'
        limit = float(limit_억) if limit_억 else 10.0
        firm_size = get_size_code(firm_size_cd or '소기업')

        # 상환 방식 결정
        probs = METHOD_PROBS.get(firm_size, METHOD_PROBS["S"])
        method = REPAYMENT_METHODS[rng.choice(len(REPAYMENT_METHODS), p=probs)]

        # 금리 (기준금리 + 가산금리)
        base_rate = IND_RATE.get(ind, 4.0) / 100.0
        spread = rng.uniform(0.005, 0.030) + (0.02 if default_flag else 0.0)
        annual_rate = base_rate + spread
        monthly_rate = annual_rate / 12.0

        # 만기 설정
        if method == "BULLET":
            tenor = int(rng.integers(3, 13))  # 3~12개월
        elif method in ("INSTALLMENT", "ANNUITY"):
            tenor = int(rng.integers(12, 61))  # 1~5년
        else:  # REVOLVING
            tenor = int(rng.integers(6, 25))   # 6~24개월

        maturity_ym = ym_add(entry_ym, tenor)
        if maturity_ym > YM_END + 1:
            maturity_ym = YM_END + 1

        balance = limit  # 잔액
        monthly_principal = limit / tenor if method == "INSTALLMENT" else 0.0
        annuity_pmt = _annuity_payment(limit, monthly_rate, tenor) if method == "ANNUITY" else 0.0

        month_num = 0
        for ym in MONTHS:
            if ym < entry_ym or ym >= maturity_ym or ym >= exit_ym:
                continue
            if balance <= 0:
                break

            month_num += 1
            months_to_exit = (exit_ym - ym) if default_flag and exit_ym <= YM_END else 999
            is_final = (ym_add(ym, 1) >= maturity_ym)

            # 예정 원금/이자
            scheduled_interest = balance * monthly_rate
            if method == "BULLET":
                scheduled_principal = balance if is_final else 0.0
            elif method == "INSTALLMENT":
                scheduled_principal = min(monthly_principal, balance)
            elif method == "ANNUITY":
                scheduled_principal = min(annuity_pmt - scheduled_interest, balance)
            else:  # REVOLVING
                scheduled_principal = 0.0  # 만기 일시

            if is_final:
                scheduled_principal = balance

            scheduled_total = scheduled_principal + scheduled_interest

            # 실제 상환 (부도 기업은 지연)
            dpd = dpd_cache.get((bid, ym), 0)
            if dpd > 0 and default_flag:
                # DPD에 따른 미납율
                shortfall_rate = min(dpd / 90.0, 1.0) * rng.uniform(0.5, 1.0)
                actual_principal = scheduled_principal * (1 - shortfall_rate)
                actual_interest = scheduled_interest * (1 - shortfall_rate * 0.5)
                payment_status = "PARTIAL" if shortfall_rate < 0.9 else "DELINQUENT"
            else:
                actual_principal = scheduled_principal
                actual_interest = scheduled_interest
                payment_status = "ON_SCHEDULE"

            actual_total = actual_principal + actual_interest

            # 잔액 업데이트
            balance = max(0.0, balance - actual_principal)

            rows.append((
                bid, fac_id, ym, method,
                round(scheduled_principal, 4), round(scheduled_interest, 4), round(scheduled_total, 4),
                round(actual_principal, 4), round(actual_interest, 4), round(actual_total, 4),
                round(balance, 4),
                round(annual_rate * 100, 4),
                dpd, payment_status,
            ))

            if len(rows) >= BATCH:
                conn.executemany("""
                    INSERT OR IGNORE INTO fact_loan_schedule
                      (borrower_id, facility_id, payment_ym, repayment_method,
                       scheduled_principal_억, scheduled_interest_억, scheduled_total_억,
                       actual_principal_억, actual_interest_억, actual_total_억,
                       outstanding_balance_억, interest_rate_annual, days_past_due, payment_status)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, rows)
                conn.commit()
                rows = []

    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO fact_loan_schedule
              (borrower_id, facility_id, payment_ym, repayment_method,
               scheduled_principal_억, scheduled_interest_억, scheduled_total_억,
               actual_principal_억, actual_interest_억, actual_total_억,
               outstanding_balance_억, interest_rate_annual, days_past_due, payment_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM fact_loan_schedule").fetchone()[0]
    method_dist = conn.execute(
        "SELECT repayment_method, COUNT(*) FROM fact_loan_schedule GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    status_dist = conn.execute(
        "SELECT payment_status, COUNT(*) FROM fact_loan_schedule GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    elapsed = round(time.time() - t0, 1)
    print(f"    fact_loan_schedule: {total:,}행", flush=True)
    for m, cnt in method_dist:
        print(f"      {m}: {cnt:,}행", flush=True)
    for s, cnt in status_dist:
        print(f"      {s}: {cnt:,}행", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
