"""
s17_delinquency.py — 연체 이력 및 수금 활동 데이터 생성 (v23 개선)

테이블:
  fact_delinquency        — 여신별 연체 발생/해결 이력
  fact_collection_activity — 연체 건별 수금 추진 기록
  (dim_facility에 dpd, max_dpd_12m, first_delinquency_date, classification 컬럼 추가)

v23 개선:
  - 생존기업 DPD: 0일 80%, 1~30일 13%, 31~60일 5%, 61~90일 1.5%, 91+일 0.5% (편향 분포)
  - 부도기업 경로별 분기 (ACUTE/CHRONIC/EVENT/CONTAGION)
  - 부도기업 status: OPEN 80%, WORKOUT 15%, RESOLVED 5% (기존 RESOLVED 30% 수정)
  - 수금활동 건수 버그 수정: max_dpd // 20 + rng.integers(1, 4)
"""
import time
import uuid
from datetime import datetime, timezone

import numpy as np

from config.macro import YM_START, YM_END, MONTHS, ym_add

# 연체 단계 기준
DPD_STAGE = [
    (0,   "NORMAL"),
    (1,   "EARLY"),      # 1~30일
    (31,  "MID"),        # 31~60일
    (61,  "LATE"),       # 61~90일
    (91,  "NPL"),        # 91~180일
    (181, "WRITEOFF"),   # 181일+
]

# 해결 유형 (연체 해소 방식)
RESOLUTION_TYPES = {
    "EARLY":    [("PAID", 0.88), ("RESTRUCTURED", 0.07), ("WORKOUT", 0.05)],
    "MID":      [("PAID", 0.65), ("RESTRUCTURED", 0.20), ("WORKOUT", 0.15)],
    "LATE":     [("PAID", 0.35), ("RESTRUCTURED", 0.30), ("WORKOUT", 0.35)],
    "NPL":      [("PAID", 0.15), ("RESTRUCTURED", 0.20), ("WORKOUT", 0.40), ("WRITEOFF", 0.25)],
    "WRITEOFF": [("PAID", 0.05), ("RESTRUCTURED", 0.05), ("WORKOUT", 0.30), ("WRITEOFF", 0.60)],
}

# 수금 활동 유형 및 결과
ACTIVITY_TYPES = ["CALL", "SMS", "EMAIL", "VISIT", "LETTER", "LEGAL_NOTICE"]
CONTACT_RESULTS = {
    "CALL":  [("REACHED", 0.55), ("NO_ANSWER", 0.30), ("PROMISE_TO_PAY", 0.15)],
    "SMS":   [("DELIVERED", 0.90), ("UNDELIVERED", 0.10)],
    "EMAIL": [("DELIVERED", 0.88), ("BOUNCED", 0.12)],
    "VISIT": [("REACHED", 0.70), ("ABSENT", 0.30)],
    "LETTER":       [("DELIVERED", 0.85), ("RETURNED", 0.15)],
    "LEGAL_NOTICE": [("DELIVERED", 0.92), ("RETURNED", 0.08)],
}

OFFICERS = [
    "김수금", "이채권", "박관리", "최여신", "정대출",
    "한회수", "조담당", "윤처리", "장수금", "임관리",
]


def _dpd_stage(dpd: int) -> str:
    stage = "NORMAL"
    for thresh, s in DPD_STAGE:
        if dpd >= thresh:
            stage = s
    return stage


def _pick_weighted(choices, rng):
    items, weights = zip(*choices)
    return items[rng.choice(len(items), p=list(weights))]


def _survivor_max_dpd(rng) -> int:
    """생존기업 DPD: 0일 80%, 1~30일 13%, 31~60일 5%, 61~90일 1.5%, 91+일 0.5%"""
    roll = rng.random()
    if roll < 0.80:
        return 0
    elif roll < 0.93:   # 13%: 1~30
        return int(rng.integers(1, 31))
    elif roll < 0.98:   # 5%: 31~60
        return int(rng.integers(31, 61))
    elif roll < 0.995:  # 1.5%: 61~90
        return int(rng.integers(61, 91))
    else:               # 0.5%: 91~180
        return int(rng.integers(91, 181))


def _default_max_dpd(path_type: str, rng) -> int:
    """부도기업 경로별 DPD 분포"""
    if path_type == 'ACUTE':
        # 급성 악화: 61~365일 (후반부 집중)
        return int(rng.integers(91, 366))
    elif path_type == 'CHRONIC':
        # 만성 악화: 비교적 낮은 DPD로 시작 (30~180일)
        return int(rng.integers(30, 181))
    elif path_type == 'EVENT':
        # 돌발 이벤트: 이벤트 충격 후 급상승 (61~270일)
        return int(rng.integers(61, 271))
    else:
        # CONTAGION 또는 기타
        return int(rng.integers(61, 365))


def _default_overdue_window(path_type: str, exit_ym: int, rng) -> tuple:
    """부도기업 연체 발생 시점 창 (start, end)"""
    if path_type == 'ACUTE':
        # 급성: exit 6~12개월 전 발생
        start = max(YM_START, ym_add(exit_ym, -12))
        end = max(start + 100, ym_add(exit_ym, -3))
    elif path_type == 'CHRONIC':
        # 만성: exit 18~30개월 전 첫 연체
        start = max(YM_START, ym_add(exit_ym, -30))
        end = max(start + 100, ym_add(exit_ym, -12))
    elif path_type == 'EVENT':
        # 이벤트: s19 이벤트 후 2~4개월, exit 3~9개월 전
        start = max(YM_START, ym_add(exit_ym, -9))
        end = max(start + 100, ym_add(exit_ym, -3))
    else:
        # CONTAGION
        start = max(YM_START, ym_add(exit_ym, -18))
        end = max(start + 100, ym_add(exit_ym, -3))
    return start, end


def s17_delinquency(conn, companies, rng):
    t0 = time.time()
    print("  [s17] 연체 이력 및 수금 활동 생성", flush=True)

    # ── 스키마 ──────────────────────────────────────────────────────────────
    conn.execute("DROP TABLE IF EXISTS fact_delinquency")
    conn.execute("DROP TABLE IF EXISTS fact_collection_activity")

    conn.execute("""
        CREATE TABLE fact_delinquency (
            delinquency_id       TEXT PRIMARY KEY,
            borrower_id          TEXT NOT NULL,
            facility_id          TEXT,
            overdue_date         TEXT NOT NULL,
            overdue_ym           INTEGER NOT NULL,
            overdue_amount_억     REAL NOT NULL,
            overdue_type         TEXT NOT NULL,
            max_dpd              INTEGER NOT NULL,
            current_dpd          INTEGER NOT NULL,
            delinquency_stage    TEXT NOT NULL,
            resolved_date        TEXT,
            resolved_ym          INTEGER,
            resolved_amount_억    REAL,
            resolution_type      TEXT,
            status               TEXT NOT NULL,
            assigned_officer     TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_delin_bid ON fact_delinquency(borrower_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_delin_ym  ON fact_delinquency(overdue_ym)")

    conn.execute("""
        CREATE TABLE fact_collection_activity (
            activity_id      TEXT PRIMARY KEY,
            delinquency_id   TEXT NOT NULL,
            borrower_id      TEXT NOT NULL,
            activity_date    TEXT NOT NULL,
            activity_ym      INTEGER NOT NULL,
            activity_type    TEXT NOT NULL,
            contact_result   TEXT NOT NULL,
            promised_date    TEXT,
            promised_amount_억 REAL,
            notes            TEXT,
            officer          TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_coll_delin ON fact_collection_activity(delinquency_id)")

    # ── dim_facility에 연체 컬럼 추가 ──────────────────────────────────────
    existing_cols = {c[1] for c in conn.execute("PRAGMA table_info(dim_facility)").fetchall()}
    new_cols = {
        "dpd":                    "INTEGER DEFAULT 0",
        "max_dpd_12m":            "INTEGER DEFAULT 0",
        "first_delinquency_date": "TEXT",
        "asset_classification":   "TEXT DEFAULT 'NORMAL'",
    }
    for col, dtype in new_cols.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE dim_facility ADD COLUMN {col} {dtype}")
    conn.commit()

    # ── 여신 목록 로드 ──────────────────────────────────────────────────────
    facilities = conn.execute(
        "SELECT f.facility_id, f.borrower_id, f.committed_amount_억, "
        "       c.default_flag, c.exit_ym "
        "FROM dim_facility f "
        "JOIN dim_company c ON f.borrower_id = c.borrower_id"
    ).fetchall()

    if not facilities:
        # dim_facility가 없으면 dim_company 기반으로 가상 여신 ID 생성
        facilities = [
            (f"{c['borrower_id']}_F1", c['borrower_id'],
             float(c.get('credit_limit_억', 10.0) if c.get('credit_limit_억') else 10.0),
             c['default_flag'], c.get('exit_ym'))
            for c in companies
        ]
    else:
        facilities = [tuple(r) for r in facilities]

    bid_to_company = {c['borrower_id']: c for c in companies}

    delinquency_rows = []
    activity_rows = []
    facility_dpd_updates = []  # (max_dpd, current_dpd, first_date, classification, facility_id)

    for fac in facilities:
        fac_id, bid, limit_억, default_flag, exit_ym = fac
        company = bid_to_company.get(bid)
        if not company:
            continue

        exit_ym = exit_ym or YM_END + 1
        path_type = company.get('default_path_type') or 'ACUTE'

        # 연체 발생 확률
        if default_flag:
            delin_prob = rng.uniform(0.65, 0.90)   # 부도 기업 65~90%
        else:
            delin_prob = rng.uniform(0.03, 0.12)   # 생존 기업 3~12%

        if rng.random() > delin_prob:
            continue

        # 연체 발생 시점
        if default_flag and exit_ym <= YM_END:
            start_search, end_search = _default_overdue_window(path_type, exit_ym, rng)
        else:
            start_search = YM_START
            end_search = YM_END

        valid_months = [m for m in MONTHS if start_search <= m <= end_search]
        if not valid_months:
            continue

        overdue_ym = valid_months[rng.integers(0, len(valid_months))]
        year, month = divmod(overdue_ym, 100)
        overdue_date = f"{year}-{month:02d}-{rng.integers(1, 29):02d}"

        # 연체 금액 (여신의 5~80%)
        limit = float(limit_억) if limit_억 else 5.0
        overdue_pct = rng.uniform(0.05, 0.80) if default_flag else rng.uniform(0.03, 0.30)
        overdue_amount = round(limit * overdue_pct, 2)
        overdue_type = rng.choice(["PRINCIPAL", "INTEREST", "BOTH"],
                                   p=[0.25, 0.35, 0.40])

        # 최대 DPD 결정 (경로별 분기)
        if default_flag:
            max_dpd = _default_max_dpd(path_type, rng)
        else:
            max_dpd = _survivor_max_dpd(rng)

        # DPD=0이면 연체 이력 불필요
        if max_dpd == 0:
            continue

        stage = _dpd_stage(max_dpd)

        # 해결 여부
        resolution_choices = RESOLUTION_TYPES.get(stage, RESOLUTION_TYPES["EARLY"])
        if default_flag:
            # 부도기업: OPEN 80%, WORKOUT 15%, RESOLVED 5%
            roll_status = rng.random()
            if roll_status < 0.80:
                status = "OPEN"
            elif roll_status < 0.95:
                status = "WORKOUT"
            else:
                status = "RESOLVED"
        else:
            # 생존기업: RESOLVED 75%, OPEN 25%
            status = "RESOLVED" if rng.random() < 0.75 else "OPEN"

        resolved_date, resolved_ym, resolved_amount, resolution_type = None, None, None, None
        if status == "RESOLVED":
            resolve_months = max(1, max_dpd // 30 + int(rng.integers(1, 4)))
            resolved_ym = ym_add(overdue_ym, resolve_months)
            if resolved_ym > YM_END:
                resolved_ym = None
                status = "OPEN"
            else:
                r_year, r_month = divmod(resolved_ym, 100)
                resolved_date = f"{r_year}-{r_month:02d}-{rng.integers(1, 29):02d}"
                resolved_amount = round(overdue_amount * rng.uniform(0.7, 1.0), 2)
                resolution_type = _pick_weighted(resolution_choices, rng)

        current_dpd = 0 if status == "RESOLVED" else max_dpd
        officer = OFFICERS[rng.integers(0, len(OFFICERS))]

        delin_id = str(uuid.uuid4())
        delinquency_rows.append((
            delin_id, bid, fac_id, overdue_date, overdue_ym,
            overdue_amount, overdue_type, max_dpd, current_dpd, stage,
            resolved_date, resolved_ym, resolved_amount, resolution_type,
            status, officer
        ))

        # 수금 활동 생성 (수정: max_dpd // 20 + rng.integers(1, 4))
        n_activities = max_dpd // 20 + int(rng.integers(1, 4))
        n_activities = min(n_activities, 12)  # 최대 12건 상한
        for act_i in range(n_activities):
            act_ym = ym_add(overdue_ym, act_i)
            if act_ym > YM_END:
                break
            a_year, a_month = divmod(act_ym, 100)
            act_date = f"{a_year}-{a_month:02d}-{rng.integers(1, 29):02d}"
            act_type = ACTIVITY_TYPES[rng.integers(0, len(ACTIVITY_TYPES))]

            # 연체 심화될수록 강화 활동
            if max_dpd > 90:
                act_type = rng.choice(["VISIT", "LEGAL_NOTICE", "CALL"], p=[0.35, 0.40, 0.25])

            contact_result = _pick_weighted(CONTACT_RESULTS[act_type], rng)
            promised_date = None
            promised_amount = None
            if contact_result == "PROMISE_TO_PAY":
                p_ym = ym_add(act_ym, 1)
                p_year, p_month = divmod(p_ym, 100)
                promised_date = f"{p_year}-{p_month:02d}-{rng.integers(1, 29):02d}"
                promised_amount = round(overdue_amount * rng.uniform(0.3, 1.0), 2)

            activity_rows.append((
                str(uuid.uuid4()), delin_id, bid, act_date, act_ym,
                act_type, contact_result, promised_date, promised_amount,
                None, OFFICERS[rng.integers(0, len(OFFICERS))]
            ))

        # dim_facility 업데이트 정보
        asset_class = "NORMAL"
        if max_dpd >= 181:
            asset_class = "LOSS"
        elif max_dpd >= 91:
            asset_class = "DOUBTFUL"
        elif max_dpd >= 61:
            asset_class = "SUBSTANDARD"
        elif max_dpd >= 31:
            asset_class = "PRECAUTIONARY"

        facility_dpd_updates.append((
            max_dpd, current_dpd, overdue_date, asset_class, fac_id
        ))

    # ── INSERT ──────────────────────────────────────────────────────────────
    conn.executemany("""
        INSERT INTO fact_delinquency
          (delinquency_id, borrower_id, facility_id, overdue_date, overdue_ym,
           overdue_amount_억, overdue_type, max_dpd, current_dpd, delinquency_stage,
           resolved_date, resolved_ym, resolved_amount_억, resolution_type,
           status, assigned_officer)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, delinquency_rows)

    conn.executemany("""
        INSERT INTO fact_collection_activity
          (activity_id, delinquency_id, borrower_id, activity_date, activity_ym,
           activity_type, contact_result, promised_date, promised_amount_억,
           notes, officer)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, activity_rows)

    conn.executemany("""
        UPDATE dim_facility
        SET max_dpd_12m=?, dpd=?, first_delinquency_date=?, asset_classification=?
        WHERE facility_id=?
    """, facility_dpd_updates)

    conn.commit()

    # 통계 출력
    stage_dist = {}
    status_dist = {}
    for row in delinquency_rows:
        stage_dist[row[9]] = stage_dist.get(row[9], 0) + 1
        status_dist[row[14]] = status_dist.get(row[14], 0) + 1

    elapsed = round(time.time() - t0, 1)
    print(f"    fact_delinquency: {len(delinquency_rows):,}건", flush=True)
    print(f"      단계별: {dict(sorted(stage_dist.items()))}", flush=True)
    print(f"      상태별: {status_dist}", flush=True)
    print(f"    fact_collection_activity: {len(activity_rows):,}건", flush=True)
    print(f"    dim_facility 연체 컬럼 업데이트: {len(facility_dpd_updates):,}건", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
