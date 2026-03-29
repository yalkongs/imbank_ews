"""
s32_collateral_disposal.py — 담보처분 기록 생성 (v24 신규)

테이블:
  fact_collateral_disposal — 부도기업 담보 실행/처분 기록

처분 방법:
  AUCTION       — 경매 (법원 경매)
  NEGOTIATION   — 임의 매각 (채권자-채무자 협의)
  FORECLOSURE   — 담보권 실행 (은행 직접 처분)
  WRITE_OFF     — 담보 포기 (담보가치 미미)

대상:
  - 부도기업(default_flag=1)의 담보 자산
  - fact_npl_workout의 FORECLOSURE/AUCTION 케이스 연동
"""
import time
import uuid
import numpy as np
from config.macro import YM_START, YM_END, ym_add
from config.companies import get_size_code

DISPOSAL_METHODS = ["AUCTION", "NEGOTIATION", "FORECLOSURE", "WRITE_OFF"]

# Workout 유형별 처분 방법 선호도
WORKOUT_METHOD_MAP = {
    "FORECLOSURE": [(0, 0.60), (2, 0.25), (1, 0.10), (3, 0.05)],  # AUCTION 우선
    "AUCTION":     [(0, 0.75), (1, 0.15), (2, 0.08), (3, 0.02)],
    "RESTRUCTURING": [(1, 0.50), (0, 0.25), (2, 0.20), (3, 0.05)],
    "WRITE_OFF":   [(3, 0.70), (0, 0.20), (1, 0.10), (2, 0.00)],
}

# 담보 유형별 평균 회수율 (%)
COLLATERAL_RECOVERY = {
    "REAL_ESTATE": (60.0, 85.0),
    "MACHINERY":   (30.0, 60.0),
    "INVENTORY":   (20.0, 50.0),
    "SECURITIES":  (50.0, 90.0),
    "OTHER":       (25.0, 55.0),
}


def s32_collateral_disposal(conn, companies, rng):
    t0 = time.time()
    print("  [s32] 담보처분 기록 생성", flush=True)

    conn.execute("DELETE FROM fact_collateral_disposal")

    # 담보 목록 (부도기업 한정)
    defaulted_bids = {
        c['borrower_id'] for c in companies
        if c['default_flag'] and (c.get('exit_ym') or 0) <= YM_END
    }

    collaterals = conn.execute(
        "SELECT collateral_id, borrower_id, collateral_type, appraised_value_억 "
        "FROM dim_collateral WHERE borrower_id IN ({})".format(
            ",".join("?" * len(defaulted_bids))
        ),
        list(defaulted_bids)
    ).fetchall() if defaulted_bids else []

    # Workout 정보 — exit_ym 기준으로 처분 시점 결정
    workout_map = {}
    if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fact_npl_workout'"
    ).fetchone():
        for row in conn.execute(
            "SELECT borrower_id, workout_type, workout_start_ym FROM fact_npl_workout"
        ).fetchall():
            if row[0] not in workout_map:
                workout_map[row[0]] = (row[1], row[2])

    # 기업 exit_ym 맵
    exit_map = {c['borrower_id']: c.get('exit_ym') or YM_END for c in companies}

    rows = []

    for col in collaterals:
        col_id, bid, col_type, appraised = col
        appraised = float(appraised) if appraised else 10.0
        col_type = col_type or "OTHER"

        # 처분 시점: exit_ym + 1~6개월
        exit_ym = exit_map.get(bid, YM_END)
        wk_type, wk_start = workout_map.get(bid, ("FORECLOSURE", exit_ym))
        disposal_ym = ym_add(wk_start or exit_ym, int(rng.integers(1, 7)))
        if disposal_ym > YM_END:
            disposal_ym = YM_END

        # 처분 방법
        method_probs_raw = WORKOUT_METHOD_MAP.get(wk_type, WORKOUT_METHOD_MAP["FORECLOSURE"])
        idxs, probs = zip(*method_probs_raw)
        chosen_idx = idxs[rng.choice(len(idxs), p=list(probs))]
        method = DISPOSAL_METHODS[chosen_idx]

        # 회수율
        rec_lo, rec_hi = COLLATERAL_RECOVERY.get(col_type, (25.0, 55.0))
        if method == "WRITE_OFF":
            rec_pct = float(rng.uniform(0.0, 15.0))
        elif method == "NEGOTIATION":
            rec_pct = float(rng.uniform(rec_lo * 0.8, rec_hi * 0.9))
        else:
            rec_pct = float(rng.uniform(rec_lo, rec_hi))

        disposal_amount = round(appraised * rec_pct / 100.0, 2)

        rows.append((
            col_id, bid, disposal_ym,
            round(disposal_amount, 2),
            round(rec_pct, 2),
            method,
        ))

    if rows:
        conn.executemany(
            "INSERT INTO fact_collateral_disposal "
            "(collateral_id, borrower_id, disposal_ym, disposal_amount_억, "
            " recovery_rate_pct, disposal_method) "
            "VALUES (?,?,?,?,?,?)",
            rows
        )
        conn.commit()

    total = len(rows)
    method_dist = {}
    for r in rows:
        method_dist[r[5]] = method_dist.get(r[5], 0) + 1

    elapsed = round(time.time() - t0, 1)
    print(f"    fact_collateral_disposal: {total:,}건", flush=True)
    for m, cnt in sorted(method_dist.items()):
        print(f"      {m}: {cnt:,}건", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
