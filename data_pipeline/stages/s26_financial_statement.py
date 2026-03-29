"""
s26_financial_statement.py — 재무제표 원본 데이터 생성 (v23 신규)

테이블:
  fact_income_statement  — 손익계산서 (연도별)
  fact_balance_sheet     — 재무상태표 (연도별)
  fact_cash_flow         — 현금흐름표 (연도별)

fact_financial_ratio(s20)의 비율값을 역산하여 절대금액을 생성.
일관성: 매출액 × 비율 → 각 항목 계산.

단위: 억원
"""
import time
import numpy as np
from config.macro import YM_START, YM_END
from config.companies import get_size_code

_YEARS = list(range(YM_START // 100, YM_END // 100 + 1))

# 업종별 영업이익률 기준 (%)
IND_OPM = {
    "K00": 5.0, "K01A": 6.0, "K01B": 10.0, "K02": 5.5, "K03": 4.0,
    "K04": 6.5, "K05": 15.0, "K06": 18.0, "K07": 8.0, "K08": 9.0,
    "K09": 10.0, "K10": 7.0, "K11": 5.0, "K12": 6.0, "K13": 7.0,
}

# 기업 규모별 매출 범위 (억원)
SIZE_REVENUE = {
    "L": (3_000, 50_000),
    "M": (500, 3_000),
    "S": (20, 500),
}


def _get_revenue_base(firm_size: str, ind: str, rng) -> float:
    lo, hi = SIZE_REVENUE.get(firm_size, (20, 200))
    return float(rng.uniform(lo, hi))


def s26_financial_statement(conn, companies, rng):
    t0 = time.time()
    print("  [s26] 재무제표 원본 생성", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_income_statement")
    conn.execute("DROP TABLE IF EXISTS fact_balance_sheet")
    conn.execute("DROP TABLE IF EXISTS fact_cash_flow")

    conn.execute("""
        CREATE TABLE fact_income_statement (
            stmt_id              INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id          TEXT NOT NULL,
            fiscal_year          INTEGER NOT NULL,
            revenue_억            REAL,
            cost_of_goods_억      REAL,
            gross_profit_억       REAL,
            operating_expense_억  REAL,
            operating_income_억   REAL,
            ebitda_억             REAL,
            interest_expense_억   REAL,
            pretax_income_억      REAL,
            tax_expense_억        REAL,
            net_income_억         REAL,
            gross_margin_pct     REAL,
            operating_margin_pct REAL,
            net_margin_pct       REAL,
            yoy_revenue_growth   REAL,
            UNIQUE(borrower_id, fiscal_year)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_is_bid ON fact_income_statement(borrower_id)")

    conn.execute("""
        CREATE TABLE fact_balance_sheet (
            stmt_id              INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id          TEXT NOT NULL,
            fiscal_year          INTEGER NOT NULL,
            -- 자산
            cash_억               REAL,
            receivables_억        REAL,
            inventory_억          REAL,
            current_assets_억     REAL,
            fixed_assets_억       REAL,
            total_assets_억       REAL,
            -- 부채
            short_term_debt_억    REAL,
            current_liabilities_억 REAL,
            long_term_debt_억     REAL,
            total_liabilities_억  REAL,
            -- 자본
            paid_in_capital_억    REAL,
            retained_earnings_억  REAL,
            total_equity_억       REAL,
            -- 비율 (참고용)
            debt_to_equity       REAL,
            current_ratio        REAL,
            UNIQUE(borrower_id, fiscal_year)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bs_bid ON fact_balance_sheet(borrower_id)")

    conn.execute("""
        CREATE TABLE fact_cash_flow (
            stmt_id              INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id          TEXT NOT NULL,
            fiscal_year          INTEGER NOT NULL,
            cfo_억                REAL,   -- 영업활동 현금흐름
            cfi_억                REAL,   -- 투자활동 현금흐름
            cff_억                REAL,   -- 재무활동 현금흐름
            net_change_in_cash_억 REAL,
            capex_억              REAL,
            free_cash_flow_억     REAL,
            operating_cash_ratio REAL,   -- CFO / 매출
            UNIQUE(borrower_id, fiscal_year)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cf_bid ON fact_cash_flow(borrower_id)")

    # 재무비율 캐시 (역산용)
    ratio_cache = {}
    if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fact_financial_ratio'"
    ).fetchone():
        for row in conn.execute(
            "SELECT borrower_id, fiscal_year, debt_ratio, ier, current_ratio "
            "FROM fact_financial_ratio"
        ).fetchall():
            ratio_cache[(row[0], row[1])] = {
                "debt_ratio": row[2], "ier": row[3], "current_ratio": row[4],
            }

    is_rows = []
    bs_rows = []
    cf_rows = []
    BATCH = 20_000

    def flush():
        if is_rows:
            conn.executemany("""
                INSERT OR IGNORE INTO fact_income_statement
                  (borrower_id, fiscal_year, revenue_억, cost_of_goods_억, gross_profit_억,
                   operating_expense_억, operating_income_억, ebitda_억, interest_expense_억,
                   pretax_income_억, tax_expense_억, net_income_억,
                   gross_margin_pct, operating_margin_pct, net_margin_pct, yoy_revenue_growth)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, is_rows)
            is_rows.clear()
        if bs_rows:
            conn.executemany("""
                INSERT OR IGNORE INTO fact_balance_sheet
                  (borrower_id, fiscal_year, cash_억, receivables_억, inventory_억,
                   current_assets_억, fixed_assets_억, total_assets_억,
                   short_term_debt_억, current_liabilities_억, long_term_debt_억,
                   total_liabilities_억, paid_in_capital_억, retained_earnings_억,
                   total_equity_억, debt_to_equity, current_ratio)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, bs_rows)
            bs_rows.clear()
        if cf_rows:
            conn.executemany("""
                INSERT OR IGNORE INTO fact_cash_flow
                  (borrower_id, fiscal_year, cfo_억, cfi_억, cff_억,
                   net_change_in_cash_억, capex_억, free_cash_flow_억, operating_cash_ratio)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, cf_rows)
            cf_rows.clear()
        conn.commit()

    for c in companies:
        bid = c['borrower_id']
        default_flag = c['default_flag']
        exit_ym = c.get('exit_ym') or (YM_END + 1)
        entry_ym = c.get('entry_ym') or YM_START
        firm_size = get_size_code(c.get('firm_size_cd', '소기업'))
        ind = c.get('industry_cd', 'K01A')

        entry_year = entry_ym // 100
        exit_year = exit_ym // 100

        base_rev = _get_revenue_base(firm_size, ind, rng)
        base_opm = IND_OPM.get(ind, 6.0) / 100.0
        prev_rev = None

        for yr in _YEARS:
            if yr < entry_year or yr >= exit_year:
                continue

            ratio = ratio_cache.get((bid, yr), {})
            months_to_exit = (exit_ym - yr * 100) if default_flag and exit_ym <= YM_END else 999
            det = max(0.0, 1.0 - months_to_exit / 36.0) if months_to_exit < 36 else 0.0

            # 매출액 (부도기업은 점진 하락)
            rev_growth = rng.normal(0.03, 0.08) - det * 0.12
            revenue = max(1.0, base_rev * (1 + rev_growth) * (1 - det * 0.15))
            base_rev = revenue  # 전년도 기준 갱신

            yoy_growth = (revenue / prev_rev - 1.0) if prev_rev else None
            prev_rev = revenue

            # 손익계산서
            cogs_pct = rng.uniform(0.55, 0.80) + det * 0.05
            cogs = revenue * cogs_pct
            gross_profit = revenue - cogs
            gross_margin = gross_profit / revenue

            opm = base_opm * rng.uniform(0.7, 1.3) - det * 0.08
            op_income = revenue * opm
            op_expense = gross_profit - op_income
            ebitda = op_income * rng.uniform(1.1, 1.4)

            interest_exp = revenue * rng.uniform(0.01, 0.04) * (1 + det * 2)
            pretax_income = op_income - interest_exp
            tax_rate = rng.uniform(0.18, 0.25) if pretax_income > 0 else 0.0
            tax_exp = max(0.0, pretax_income * tax_rate)
            net_income = pretax_income - tax_exp
            net_margin = net_income / revenue

            # 재무상태표 역산
            # 자산
            asset_ratio = 1.25  # asset_turnover 미제공 — 매출액 대비 자산 배율 기본값
            total_assets = revenue * asset_ratio
            cr = ratio.get("current_ratio", 120.0) or 120.0
            current_assets = total_assets * rng.uniform(0.35, 0.55)
            fixed_assets = total_assets - current_assets
            cash = current_assets * rng.uniform(0.10, 0.25)
            receivables = current_assets * rng.uniform(0.30, 0.50)
            inventory = current_assets - cash - receivables

            # 부채/자본
            dr = ratio.get("debt_ratio", 150.0) or 150.0
            total_equity = total_assets / (1 + dr / 100.0)
            total_liabilities = total_assets - total_equity
            current_liabilities = current_assets / (cr / 100.0)
            long_term_debt = max(0.0, total_liabilities - current_liabilities)
            short_term_debt = current_liabilities * rng.uniform(0.40, 0.70)
            paid_in_capital = total_equity * rng.uniform(0.30, 0.60)
            retained_earnings = total_equity - paid_in_capital
            dte = total_liabilities / total_equity if total_equity > 0 else 9.99

            # 현금흐름
            cfo = net_income * rng.uniform(0.8, 1.4) + (ebitda - op_income) * 0.5 - det * revenue * 0.05
            capex = fixed_assets * rng.uniform(0.05, 0.15)
            cfi = -(capex + rng.uniform(0, revenue * 0.02))
            cff = rng.normal(0, revenue * 0.03)
            net_cash_change = cfo + cfi + cff
            fcf = cfo - capex
            ocr = cfo / revenue if revenue > 0 else 0.0

            def r(v, n=2): return round(float(v), n)

            is_rows.append((
                bid, yr,
                r(revenue), r(cogs), r(gross_profit), r(op_expense), r(op_income),
                r(ebitda), r(interest_exp), r(pretax_income), r(tax_exp), r(net_income),
                r(gross_margin * 100, 2), r(opm * 100, 2), r(net_margin * 100, 2),
                r(yoy_growth * 100, 2) if yoy_growth is not None else None,
            ))
            bs_rows.append((
                bid, yr,
                r(cash), r(receivables), r(inventory), r(current_assets), r(fixed_assets),
                r(total_assets), r(short_term_debt), r(current_liabilities), r(long_term_debt),
                r(total_liabilities), r(paid_in_capital), r(retained_earnings), r(total_equity),
                r(dte, 4), r(cr, 2),
            ))
            cf_rows.append((
                bid, yr,
                r(cfo), r(cfi), r(cff), r(net_cash_change), r(capex), r(fcf),
                r(ocr, 4),
            ))

            if len(is_rows) >= BATCH:
                flush()

    flush()

    is_cnt = conn.execute("SELECT COUNT(*) FROM fact_income_statement").fetchone()[0]
    bs_cnt = conn.execute("SELECT COUNT(*) FROM fact_balance_sheet").fetchone()[0]
    cf_cnt = conn.execute("SELECT COUNT(*) FROM fact_cash_flow").fetchone()[0]
    elapsed = round(time.time() - t0, 1)
    print(f"    fact_income_statement: {is_cnt:,}행", flush=True)
    print(f"    fact_balance_sheet: {bs_cnt:,}행", flush=True)
    print(f"    fact_cash_flow: {cf_cnt:,}행", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
