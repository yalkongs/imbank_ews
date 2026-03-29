"""
s27_ecl.py — IFRS9 ECL(기대신용손실) 충당금 산출 (v23 신규)

테이블:
  fact_ecl_calculation — 여신별 월별 ECL Stage 및 충당금

IFRS9 3단계:
  Stage 1: 신용위험 유의적 증가 없음  → 12개월 ECL
  Stage 2: 신용위험 유의적 증가       → 전기간 ECL
  Stage 3: 손상 발생                  → 전기간 ECL (개별 산정)

ECL = EAD × PD × LGD × (Stage에 따른 기간 계수)

SICR(유의적 신용위험 증가) 트리거:
  - PD가 origination 대비 2배 이상 증가
  - 30+ DPD 발생
  - 코베넌트 위반
  - 신용등급 2단계 이상 하락
"""
import time
import numpy as np
from config.macro import YM_START, YM_END, MONTHS, ym_add
from config.companies import get_size_code

# Stage별 ECL 기간 계수
STAGE_HORIZON = {"1": 1.0 / 12, "2": 1.0, "3": 1.0}

# LGD 기준값 (담보 유형별)
LGD_BASE = {
    "REAL_ESTATE": 0.25, "FINANCIAL":  0.20, "MACHINERY":  0.45,
    "GUARANTEE":   0.30, "UNSECURED":  0.65,
}

# 업종별 기본 LGD
IND_LGD = {
    "K00": 0.45, "K01A": 0.40, "K01B": 0.35, "K02": 0.50, "K03": 0.38,
    "K04": 0.42, "K05": 0.30, "K06": 0.25, "K07": 0.32, "K08": 0.35,
    "K09": 0.38, "K10": 0.40, "K11": 0.45, "K12": 0.40, "K13": 0.45,
}


def _stage_from_signals(default_flag, months_to_exit, dpd, pd_val, orig_pd, covenant_breach):
    """IFRS9 Stage 결정"""
    if default_flag and months_to_exit <= 3:
        return "3"  # 손상 발생
    # Stage 3 트리거: 90+ DPD
    if dpd is not None and dpd >= 90:
        return "3"
    # Stage 2 트리거: SICR
    sicr = False
    if pd_val and orig_pd and pd_val >= orig_pd * 2.0:
        sicr = True
    if dpd is not None and dpd >= 30:
        sicr = True
    if covenant_breach:
        sicr = True
    if default_flag and months_to_exit <= 12:
        sicr = True
    return "2" if sicr else "1"


def s27_ecl(conn, companies, rng):
    t0 = time.time()
    print("  [s27] IFRS9 ECL 충당금 산출", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_ecl_calculation")
    conn.execute("""
        CREATE TABLE fact_ecl_calculation (
            ecl_id               INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id          TEXT NOT NULL,
            facility_id          TEXT,
            base_ym              INTEGER NOT NULL,
            stage                TEXT NOT NULL,
            prev_stage           TEXT,
            stage_changed        INTEGER DEFAULT 0,
            ead_억                REAL,
            pd_12m               REAL,
            pd_lifetime          REAL,
            lgd                  REAL,
            ecl_12m_억            REAL,
            ecl_lifetime_억       REAL,
            ecl_recognized_억     REAL,
            sicr_trigger         TEXT,
            provision_change_억   REAL,
            UNIQUE(borrower_id, facility_id, base_ym)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ecl_bid ON fact_ecl_calculation(borrower_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ecl_ym  ON fact_ecl_calculation(base_ym)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ecl_stage ON fact_ecl_calculation(stage)")

    # 여신 로드
    facilities = conn.execute(
        "SELECT f.facility_id, f.borrower_id, f.committed_amount_억, "
        "       f.dpd, c.default_flag, c.exit_ym, c.industry_cd "
        "FROM dim_facility f JOIN dim_company c ON f.borrower_id = c.borrower_id"
    ).fetchall()

    # PD 캐시 (월별 EWS PD)
    pd_cache = {}
    if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ews_monthly_alert'"
    ).fetchone():
        for row in conn.execute(
            "SELECT borrower_id, ym, pd_12m FROM ews_monthly_alert "
            "WHERE pd_12m IS NOT NULL"
        ).fetchall():
            pd_cache[(row[0], row[1])] = float(row[2])

    # 코베넌트 위반 월 캐시
    breach_cache = set()
    if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fact_covenant_check'"
    ).fetchone():
        for row in conn.execute(
            "SELECT borrower_id, check_ym FROM fact_covenant_check WHERE result='BREACH'"
        ).fetchall():
            breach_cache.add((row[0], row[1]))

    bid_to_company = {c['borrower_id']: c for c in companies}

    rows = []
    BATCH = 50_000

    for fac in facilities:
        fac_id, bid, limit_억, fac_dpd, default_flag, exit_ym, ind = fac
        company = bid_to_company.get(bid)
        if not company:
            continue

        exit_ym = exit_ym or YM_END + 1
        entry_ym = company.get('entry_ym') or YM_START
        ind = ind or 'K01A'
        limit = float(limit_억) if limit_억 else 10.0

        # LGD (업종 기준)
        lgd = IND_LGD.get(ind, 0.45) * rng.uniform(0.85, 1.15)
        lgd = float(np.clip(lgd, 0.10, 0.90))

        # Origination PD (최초 PD)
        if default_flag:
            orig_pd = float(rng.uniform(0.005, 0.03))
        else:
            orig_pd = float(rng.uniform(0.001, 0.008))

        prev_stage = "1"
        prev_ecl = 0.0

        for ym in MONTHS:
            if ym < entry_ym or ym >= exit_ym:
                continue

            months_to_exit = (exit_ym - ym) if default_flag and exit_ym <= YM_END else 999

            # PD 조회
            pd_val = pd_cache.get((bid, ym))
            if pd_val is None:
                if default_flag and months_to_exit <= 24:
                    det = max(0.0, 1.0 - months_to_exit / 24.0)
                    pd_val = float(np.clip(orig_pd * (1 + det * 40), 0.0001, 0.9999))
                else:
                    pd_val = orig_pd * rng.uniform(0.8, 1.2)

            # DPD
            dpd = int(fac_dpd) if fac_dpd else 0
            if default_flag and months_to_exit <= 6:
                dpd = max(dpd, int(rng.uniform(91, 180)))

            # 코베넌트 위반 여부
            covenant_breach = (bid, ym) in breach_cache

            # SICR 트리거 이름
            if default_flag and months_to_exit <= 3:
                sicr_trigger = "DEFAULT"
            elif dpd >= 90:
                sicr_trigger = "DPD_90"
            elif dpd >= 30:
                sicr_trigger = "DPD_30"
            elif pd_val >= orig_pd * 2.0:
                sicr_trigger = "PD_DOUBLED"
            elif covenant_breach:
                sicr_trigger = "COVENANT_BREACH"
            elif default_flag and months_to_exit <= 12:
                sicr_trigger = "FORWARD_LOOKING"
            else:
                sicr_trigger = None

            stage = _stage_from_signals(default_flag, months_to_exit, dpd, pd_val, orig_pd, covenant_breach)

            # EAD: 한도의 utilization 반영
            util = float(np.clip(0.5 + (1 - months_to_exit / 24.0) * 0.3 if months_to_exit < 24 else 0.5, 0.1, 1.0))
            ead = limit * util

            # Lifetime PD (잔존만기 기준, 단순화)
            remaining_months = max(12, months_to_exit) if exit_ym <= YM_END else 36
            pd_lifetime = float(np.clip(1 - (1 - pd_val) ** (remaining_months / 12.0), 0.0, 0.9999))

            # ECL 계산
            ecl_12m = ead * pd_val * lgd
            ecl_lifetime = ead * pd_lifetime * lgd

            if stage == "1":
                ecl_recognized = ecl_12m
            else:
                ecl_recognized = ecl_lifetime

            stage_changed = 1 if stage != prev_stage else 0
            provision_change = ecl_recognized - prev_ecl

            rows.append((
                bid, fac_id, ym,
                stage, prev_stage, stage_changed,
                round(ead, 2),
                round(float(pd_val), 6), round(float(pd_lifetime), 6),
                round(float(lgd), 4),
                round(float(ecl_12m), 4), round(float(ecl_lifetime), 4),
                round(float(ecl_recognized), 4),
                sicr_trigger,
                round(float(provision_change), 4),
            ))

            prev_stage = stage
            prev_ecl = ecl_recognized

            if len(rows) >= BATCH:
                conn.executemany("""
                    INSERT OR IGNORE INTO fact_ecl_calculation
                      (borrower_id, facility_id, base_ym, stage, prev_stage, stage_changed,
                       ead_억, pd_12m, pd_lifetime, lgd, ecl_12m_억, ecl_lifetime_억,
                       ecl_recognized_억, sicr_trigger, provision_change_억)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, rows)
                conn.commit()
                rows = []

    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO fact_ecl_calculation
              (borrower_id, facility_id, base_ym, stage, prev_stage, stage_changed,
               ead_억, pd_12m, pd_lifetime, lgd, ecl_12m_억, ecl_lifetime_억,
               ecl_recognized_억, sicr_trigger, provision_change_억)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM fact_ecl_calculation").fetchone()[0]
    stage_dist = conn.execute(
        "SELECT stage, COUNT(*) FROM fact_ecl_calculation GROUP BY 1 ORDER BY 1"
    ).fetchall()
    elapsed = round(time.time() - t0, 1)
    print(f"    fact_ecl_calculation: {total:,}행", flush=True)
    for st, cnt in stage_dist:
        print(f"      Stage {st}: {cnt:,}행 ({cnt/total*100:.1f}%)", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
