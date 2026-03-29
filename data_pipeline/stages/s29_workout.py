"""
s29_workout.py — 부실채권(NPL) Workout 관리 데이터 생성 (v23 신규)

테이블:
  fact_npl_workout — 부실채권 Workout 케이스 관리

Workout 유형:
  RESTRUCTURING  — 채무재조정 (원금감면, 이자율 인하, 만기 연장)
  FORECLOSURE    — 담보 실행 (부동산·기계 처분)
  AUCTION        — 경매 신청 및 낙찰
  WRITE_OFF      — 상각 처리
  RECOVERY       — 상각채권 사후 회수

부도 기업(default_flag=1, exit_ym<=YM_END)만 대상.
"""
import time
import uuid
import numpy as np
from config.macro import YM_START, YM_END, ym_add
from config.companies import get_size_code

WORKOUT_TYPES = [
    "RESTRUCTURING", "FORECLOSURE", "AUCTION", "WRITE_OFF", "RECOVERY"
]

WORKOUT_PROBS = {
    "L": [0.50, 0.10, 0.15, 0.15, 0.10],  # 대기업: 채무재조정 선호
    "M": [0.35, 0.20, 0.20, 0.15, 0.10],
    "S": [0.20, 0.25, 0.25, 0.20, 0.10],  # 소기업: 담보실행/상각 多
}

RESTRUCTURE_TYPES = ["PRINCIPAL_REDUCTION", "RATE_REDUCTION", "MATURITY_EXTENSION", "COMBINED"]
OUTCOMES = {
    "RESTRUCTURING": [("COMPLETED", 0.45), ("FAILED", 0.30), ("ONGOING", 0.25)],
    "FORECLOSURE":   [("COMPLETED", 0.70), ("FAILED", 0.10), ("ONGOING", 0.20)],
    "AUCTION":       [("COMPLETED", 0.65), ("FAILED", 0.15), ("ONGOING", 0.20)],
    "WRITE_OFF":     [("COMPLETED", 0.95), ("FAILED", 0.02), ("ONGOING", 0.03)],
    "RECOVERY":      [("COMPLETED", 0.55), ("FAILED", 0.30), ("ONGOING", 0.15)],
}


def _pick_weighted(choices, rng):
    items, weights = zip(*choices)
    return items[rng.choice(len(items), p=list(weights))]


def s29_workout(conn, companies, rng):
    t0 = time.time()
    print("  [s29] 부실채권 Workout 관리 생성", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_npl_workout")
    conn.execute("""
        CREATE TABLE fact_npl_workout (
            workout_id           TEXT PRIMARY KEY,
            borrower_id          TEXT NOT NULL,
            facility_id          TEXT,
            workout_start_ym     INTEGER NOT NULL,
            workout_end_ym       INTEGER,
            workout_type         TEXT NOT NULL,
            restructure_type     TEXT,
            original_balance_억   REAL,
            restructured_balance_억 REAL,
            principal_reduction_억 REAL,
            new_interest_rate    REAL,
            new_maturity_ym      INTEGER,
            collateral_value_억   REAL,
            recovery_amount_억    REAL,
            recovery_rate        REAL,
            loss_amount_억        REAL,
            outcome              TEXT NOT NULL,
            assigned_rm          TEXT,
            notes                TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wko_bid ON fact_npl_workout(borrower_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wko_type ON fact_npl_workout(workout_type)")

    # 부도 기업만 대상
    defaulted = [c for c in companies if c['default_flag'] and (c.get('exit_ym') or 0) <= YM_END]

    # 여신 정보
    facility_map = {}
    for row in conn.execute(
        "SELECT borrower_id, facility_id, committed_amount_억 FROM dim_facility"
    ).fetchall():
        if row[0] not in facility_map:
            facility_map[row[0]] = (row[1], float(row[2]) if row[2] else 10.0)

    # 담보 정보
    collateral_map = {}
    if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='dim_collateral'"
    ).fetchone():
        for row in conn.execute(
            "SELECT borrower_id, SUM(appraised_value_억) FROM dim_collateral GROUP BY 1"
        ).fetchall():
            collateral_map[row[0]] = float(row[1]) if row[1] else 0.0

    RMS = ["김워크아웃", "이구조조정", "박채권관리", "최NPL", "정회수", "한처리"]

    rows = []

    for c in defaulted:
        bid = c['borrower_id']
        exit_ym = c['exit_ym']
        firm_size = get_size_code(c.get('firm_size_cd', '소기업'))

        fac_info = facility_map.get(bid, (f"{bid}_F1", 10.0))
        fac_id, balance = fac_info
        collateral_val = collateral_map.get(bid, balance * rng.uniform(0.3, 0.8))

        probs = WORKOUT_PROBS.get(firm_size, WORKOUT_PROBS["S"])
        workout_type = WORKOUT_TYPES[rng.choice(len(WORKOUT_TYPES), p=probs)]

        # Workout 시작: exit_ym ~ exit_ym+3개월
        start_ym = ym_add(exit_ym, int(rng.integers(0, 4)))
        if start_ym > YM_END:
            start_ym = exit_ym

        # 소요 기간: 3~24개월
        duration = int(rng.integers(3, 25))
        end_ym = ym_add(start_ym, duration)
        if end_ym > YM_END:
            end_ym = None

        # 유형별 계산
        restructure_type = None
        restructured_balance = None
        principal_reduction = None
        new_rate = None
        new_maturity = None

        if workout_type == "RESTRUCTURING":
            restructure_type = RESTRUCTURE_TYPES[rng.integers(0, len(RESTRUCTURE_TYPES))]
            principal_reduction = balance * rng.uniform(0.10, 0.40)
            restructured_balance = balance - principal_reduction
            new_rate = float(np.clip(rng.uniform(0.01, 0.05), 0.01, 0.10))
            new_maturity = ym_add(start_ym, int(rng.integers(24, 72)))
        else:
            restructured_balance = balance
            principal_reduction = 0.0

        # 회수율
        if workout_type in ("FORECLOSURE", "AUCTION"):
            recovery_rate = float(np.clip(
                collateral_val / balance * rng.uniform(0.7, 0.95), 0.1, 0.95
            ))
        elif workout_type == "RESTRUCTURING":
            recovery_rate = float(np.clip(rng.uniform(0.40, 0.85), 0.10, 0.95))
        elif workout_type == "WRITE_OFF":
            recovery_rate = float(np.clip(rng.uniform(0.0, 0.20), 0.0, 0.50))
        else:  # RECOVERY
            recovery_rate = float(np.clip(rng.uniform(0.20, 0.55), 0.0, 0.80))

        recovery_amount = round(balance * recovery_rate, 2)
        loss_amount = round(balance - recovery_amount, 2)

        outcome = _pick_weighted(OUTCOMES[workout_type], rng)

        rows.append((
            str(uuid.uuid4()), bid, fac_id,
            start_ym, end_ym, workout_type, restructure_type,
            round(balance, 2),
            round(restructured_balance, 2) if restructured_balance else None,
            round(principal_reduction, 2) if principal_reduction else None,
            new_rate, new_maturity,
            round(collateral_val, 2), recovery_amount,
            round(recovery_rate, 4), loss_amount,
            outcome,
            RMS[rng.integers(0, len(RMS))],
            None,
        ))

    conn.executemany("""
        INSERT INTO fact_npl_workout
          (workout_id, borrower_id, facility_id, workout_start_ym, workout_end_ym,
           workout_type, restructure_type, original_balance_억, restructured_balance_억,
           principal_reduction_억, new_interest_rate, new_maturity_ym,
           collateral_value_억, recovery_amount_억, recovery_rate,
           loss_amount_억, outcome, assigned_rm, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()

    total = len(rows)
    type_dist = {}
    for row in rows:
        type_dist[row[5]] = type_dist.get(row[5], 0) + 1

    elapsed = round(time.time() - t0, 1)
    print(f"    fact_npl_workout: {total:,}건", flush=True)
    for wt, cnt in sorted(type_dist.items()):
        print(f"      {wt}: {cnt:,}건", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
