"""
s21_covenant.py — 코베넌트(약정 조건) 및 점검 이력 생성 (v23 개선)

v23 개선:
  - 위반율 단계별 상향: exit 3개월 전 95%, 6개월 전 85%, 12개월 전 65%
  - Sigmoid 악화 곡선으로 교체 (24개월 창)
  - 재무비율 임의 생성 시 열화 강도 증가

테이블:
  fact_covenant       — 여신별 재무·행동 약정 조건
  fact_covenant_check — 코베넌트 정기 점검 이력

코베넌트 유형:
  FC01: 부채비율 ≤ 300%
  FC02: DSCR ≥ 1.2
  FC03: 이자보상배율(ICR) ≥ 1.5
  FC04: 유동비율 ≥ 100%
  BC01: 배당 제한
  BC02: 추가 차입 사전 동의
  BC03: 경영진 변경 통보
  IC01: 분기 재무제표 제출
  IC02: 연간 감사보고서 제출

부도 기업은 exit 전 코베넌트 위반 확률 高
"""
import time
import uuid
import numpy as np
from config.macro import YM_START, YM_END, MONTHS, ym_add
from config.companies import get_size_code

COVENANT_DEFS = [
    # (code, name, type, metric, operator, threshold, check_freq_months)
    ("FC01", "부채비율 300% 이하 유지",   "FINANCIAL",   "debt_ratio",    "LE", 300.0,  12),
    ("FC02", "DSCR 1.2 이상 유지",         "FINANCIAL",   "dscr",          "GE",   1.2,  12),
    ("FC03", "이자보상배율 1.5 이상 유지", "FINANCIAL",   "ier",           "GE",   1.5,   6),
    ("FC04", "유동비율 100% 이상 유지",    "FINANCIAL",   "current_ratio", "GE", 100.0,  12),
    ("BC01", "배당 제한",                  "BEHAVIORAL",  None,            None,  None,  12),
    ("BC02", "추가 차입 사전 동의",        "BEHAVIORAL",  None,            None,  None,   6),
    ("BC03", "경영진 변경 사전 통보",      "BEHAVIORAL",  None,            None,  None,  12),
    ("IC01", "분기 재무제표 제출",         "INFORMATION", None,            None,  None,   3),
    ("IC02", "연간 감사보고서 제출",       "INFORMATION", None,            None,  None,  12),
]

OPERATORS = {"LE": "<=", "GE": ">=", "EQ": "="}


def _sigmoid_deterioration(months_to_exit: int, window: int = 24) -> float:
    """Sigmoid 기반 열화 계수: exit 직전 급격 상승 (0→1)"""
    if months_to_exit >= window:
        return 0.0
    t = months_to_exit / window   # 1.0 → 0.0
    return float(1.0 / (1.0 + np.exp(6.0 * (t - 0.5))))


def _check_result(metric, operator, threshold, actual_value, rng, deterioration):
    """코베넌트 점검 결과 결정 (v23: 위반 확률 단계별 상향)

    deterioration=1.0 시 breach_prob ≈ 0.95 (exit 직전)
    deterioration=0.7 시 breach_prob ≈ 0.85 (exit 6개월 전 기준)
    deterioration=0.3 시 breach_prob ≈ 0.65 (exit 12개월 전 기준)
    """
    if metric is None:
        # 행동/정보 코베넌트 — Sigmoid 기반 위반 확률
        breach_prob = 0.03 + deterioration * 0.92
        breach_prob = min(breach_prob, 0.95)
        if rng.random() < breach_prob:
            return "BREACH", actual_value
        return "PASS", None

    if actual_value is None:
        return "PENDING", None

    if operator == "LE":
        passed = actual_value <= threshold
    elif operator == "GE":
        passed = actual_value >= threshold
    else:
        passed = abs(actual_value - threshold) < 0.01

    if passed:
        return "PASS", actual_value
    else:
        return "BREACH", actual_value


def s21_covenant(conn, companies, rng):
    t0 = time.time()
    print("  [s21] 코베넌트 및 점검 이력 생성", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_covenant")
    conn.execute("DROP TABLE IF EXISTS fact_covenant_check")

    conn.execute("""
        CREATE TABLE fact_covenant (
            covenant_id       TEXT PRIMARY KEY,
            borrower_id       TEXT NOT NULL,
            facility_id       TEXT,
            covenant_type     TEXT NOT NULL,
            covenant_code     TEXT NOT NULL,
            covenant_name     TEXT NOT NULL,
            metric            TEXT,
            operator          TEXT,
            threshold_value   REAL,
            check_frequency_months INTEGER NOT NULL,
            effective_from    INTEGER NOT NULL,
            effective_to      INTEGER,
            waiver_count      INTEGER DEFAULT 0,
            status            TEXT DEFAULT 'ACTIVE'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cov_bid ON fact_covenant(borrower_id)")

    conn.execute("""
        CREATE TABLE fact_covenant_check (
            check_id         TEXT PRIMARY KEY,
            covenant_id      TEXT NOT NULL,
            borrower_id      TEXT NOT NULL,
            check_ym         INTEGER NOT NULL,
            actual_value     REAL,
            threshold_value  REAL,
            result           TEXT NOT NULL,
            breach_severity  TEXT,
            waived           INTEGER DEFAULT 0,
            action_taken     TEXT,
            next_check_ym    INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_covchk_bid ON fact_covenant_check(borrower_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_covchk_cov ON fact_covenant_check(covenant_id)")

    covenant_rows = []
    check_rows = []

    # 재무비율 데이터 사전 로드 (코베넌트 점검 실제값 조회용)
    ratio_cache = {}
    ratio_data = conn.execute(
        "SELECT borrower_id, fiscal_year, debt_ratio, dscr, ier, current_ratio "
        "FROM fact_financial_ratio"
    ).fetchall()
    for bid, yr, dr, dc, ie, cr in ratio_data:
        ratio_cache[(bid, yr)] = {"debt_ratio": dr, "dscr": dc, "ier": ie, "current_ratio": cr}

    for c in companies:
        bid = c['borrower_id']
        default_flag = c['default_flag']
        exit_ym = c.get('exit_ym') or (YM_END + 1)
        entry_ym = c.get('entry_ym') or YM_START
        firm_size = get_size_code(c.get('firm_size_cd', '소기업'))

        # 여신 보유 기업만 코베넌트 설정 (대기업/중기업 비율 높음)
        cov_prob = {"L": 0.95, "M": 0.80, "S": 0.45}.get(firm_size, 0.40)
        if rng.random() > cov_prob:
            continue

        # 코베넌트 수 (1~5개 랜덤)
        n_covenants = int(rng.integers(2, 6))
        selected_covs = [COVENANT_DEFS[i] for i in rng.choice(
            len(COVENANT_DEFS), size=n_covenants, replace=False
        )]

        facility_id = f"{bid}_F1"

        for cov_def in selected_covs:
            code, name, ctype, metric, operator, threshold, freq = cov_def
            cov_id = str(uuid.uuid4())

            effective_to = exit_ym if exit_ym <= YM_END else None

            covenant_rows.append((
                cov_id, bid, facility_id,
                ctype, code, name, metric, operator, threshold,
                freq, entry_ym, effective_to, 0, "ACTIVE"
            ))

            # 점검 이력 생성 (freq 개월마다)
            check_ym = ym_add(entry_ym, freq)
            waiver_count = 0
            total_breach = 0

            while check_ym <= min(YM_END, exit_ym if exit_ym <= YM_END else YM_END):
                yr = check_ym // 100
                months_to_exit = (exit_ym - check_ym) if default_flag and exit_ym <= YM_END else 999
                # Sigmoid 열화 (24개월 창): 3개월 전 ≈0.96, 6개월 전 ≈0.88, 12개월 전 ≈0.62
                deterioration = _sigmoid_deterioration(months_to_exit, window=24)

                # 실제값 조회
                ratio = ratio_cache.get((bid, yr), {})
                if metric:
                    actual_val = ratio.get(metric)
                    if actual_val is None:
                        # 없으면 임의 생성 (열화 강도 증가)
                        if metric == "debt_ratio":
                            actual_val = float(rng.uniform(100, 400 + deterioration * 500))
                        elif metric == "dscr":
                            actual_val = float(rng.uniform(0.5, 3.0) - deterioration * 2.5)
                        elif metric == "ier":
                            actual_val = float(rng.uniform(0.5, 5.0) - deterioration * 4.5)
                        elif metric == "current_ratio":
                            actual_val = float(rng.uniform(50, 250) - deterioration * 180)
                else:
                    actual_val = None

                result, _ = _check_result(metric, operator, threshold, actual_val, rng, deterioration)

                breach_severity = None
                waived = 0
                action_taken = None

                if result == "BREACH":
                    total_breach += 1
                    # 위반 심각도
                    if deterioration > 0.7 or total_breach >= 3:
                        breach_severity = "MAJOR"
                    elif deterioration > 0.3:
                        breach_severity = "MINOR"
                    else:
                        breach_severity = "MINOR"

                    # 면제 가능성 (첫 번째 위반, 가벼운 경우)
                    if breach_severity == "MINOR" and waiver_count < 2 and rng.random() < 0.40:
                        waived = 1
                        waiver_count += 1
                        result = "WAIVED"
                        action_taken = "서면 면제 동의서 수취"
                    else:
                        action_taken = "RM 통보 및 개선 계획 요청"

                next_check_ym = ym_add(check_ym, freq)

                check_rows.append((
                    str(uuid.uuid4()), cov_id, bid, check_ym,
                    round(actual_val, 3) if actual_val is not None else None,
                    threshold,
                    result, breach_severity, waived, action_taken, next_check_ym
                ))

                check_ym = next_check_ym

            # waiver_count 업데이트
            if waiver_count > 0:
                for i, row in enumerate(covenant_rows):
                    if row[0] == cov_id:
                        covenant_rows[i] = row[:12] + (waiver_count,) + row[13:]
                        break

    conn.executemany("""
        INSERT INTO fact_covenant
          (covenant_id, borrower_id, facility_id,
           covenant_type, covenant_code, covenant_name,
           metric, operator, threshold_value,
           check_frequency_months, effective_from, effective_to,
           waiver_count, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, covenant_rows)

    conn.executemany("""
        INSERT INTO fact_covenant_check
          (check_id, covenant_id, borrower_id, check_ym,
           actual_value, threshold_value, result, breach_severity,
           waived, action_taken, next_check_ym)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, check_rows)
    conn.commit()

    breach_cnt = sum(1 for r in check_rows if r[6] in ("BREACH", "WAIVED"))
    elapsed = round(time.time() - t0, 1)
    print(f"    fact_covenant: {len(covenant_rows):,}건", flush=True)
    print(f"    fact_covenant_check: {len(check_rows):,}건 (위반/면제: {breach_cnt:,}건)", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
