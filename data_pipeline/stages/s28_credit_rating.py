"""
s28_credit_rating.py — 내부신용등급 이력 생성 (v23 신규)

테이블:
  fact_credit_rating_history — 차주별 내부신용등급 변동 이력

등급 체계 (AAA~D, 10단계):
  AAA, AA, A, BBB, BB, B, CCC, CC, C, D

등급별 기준 PD:
  AAA: 0.03%, AA: 0.06%, A: 0.12%, BBB: 0.30%,
  BB: 0.80%, B: 1.80%, CCC: 5.0%, CC: 12%, C: 25%, D: 100%

등급 이력:
  - 생존기업: 완만한 등급 변화 (업그레이드/다운그레이드 ≈ 균형)
  - 부도기업: 점진적 하락 (exit 24개월 전부터 가속)
"""
import time
import uuid
import numpy as np
from config.macro import YM_START, YM_END, MONTHS, ym_add
from config.companies import get_size_code

GRADES = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]
GRADE_IDX = {g: i for i, g in enumerate(GRADES)}

# 등급별 1년 부도율 (참고)
GRADE_PD = {
    "AAA": 0.0003, "AA": 0.0006, "A": 0.0012, "BBB": 0.0030,
    "BB": 0.0080, "B": 0.0180, "CCC": 0.050, "CC": 0.120,
    "C":  0.250,  "D": 1.000,
}

# 기업 규모별 초기 등급 분포 (index → GRADES)
INIT_GRADE_DIST = {
    "L": [("AAA", 0.05), ("AA", 0.15), ("A", 0.30), ("BBB", 0.30), ("BB", 0.15), ("B", 0.05)],
    "M": [("AA", 0.05), ("A", 0.15), ("BBB", 0.30), ("BB", 0.30), ("B", 0.15), ("CCC", 0.05)],
    "S": [("BBB", 0.05), ("BB", 0.15), ("B", 0.30), ("CCC", 0.30), ("CC", 0.15), ("C", 0.05)],
}

REVIEW_TYPES = ["ANNUAL", "INTERIM", "TRIGGERED", "PERIODIC"]


def _pick_weighted(choices, rng):
    items, weights = zip(*choices)
    return items[rng.choice(len(items), p=list(weights))]


def _init_grade(firm_size, default_flag, rng):
    """초기 등급 결정"""
    dist = INIT_GRADE_DIST.get(firm_size, INIT_GRADE_DIST["S"])
    grade = _pick_weighted(dist, rng)
    # 부도기업은 초기 등급도 약간 하향
    if default_flag:
        idx = GRADE_IDX[grade]
        idx = min(idx + rng.integers(0, 3), len(GRADES) - 2)
        grade = GRADES[idx]
    return grade


def _transition(grade_idx, deterioration, rng):
    """등급 전이 (1단계씩)

    Returns:
        new_idx, direction ('UP'/'DOWN'/'STABLE')
    """
    # 하락 확률: 생존=10~15%, 부도 악화기=최대 60%
    down_prob = 0.12 + deterioration * 0.48
    up_prob = max(0.0, 0.08 - deterioration * 0.06)
    stable_prob = 1.0 - down_prob - up_prob
    stable_prob = max(0.0, stable_prob)

    roll = rng.random()
    if roll < down_prob and grade_idx < len(GRADES) - 1:
        return grade_idx + 1, "DOWN"
    elif roll < down_prob + up_prob and grade_idx > 0:
        return grade_idx - 1, "UP"
    return grade_idx, "STABLE"


def s28_credit_rating(conn, companies, rng):
    t0 = time.time()
    print("  [s28] 내부신용등급 이력 생성", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_credit_rating_history")
    conn.execute("""
        CREATE TABLE fact_credit_rating_history (
            rating_id            TEXT PRIMARY KEY,
            borrower_id          TEXT NOT NULL,
            rating_ym            INTEGER NOT NULL,
            grade                TEXT NOT NULL,
            prev_grade           TEXT,
            grade_direction      TEXT,
            notches_changed      INTEGER DEFAULT 0,
            pd_implied           REAL,
            review_type          TEXT NOT NULL,
            reviewed_by          TEXT DEFAULT 'SYSTEM',
            trigger_reason       TEXT,
            valid_until_ym       INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rating_bid ON fact_credit_rating_history(borrower_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rating_ym  ON fact_credit_rating_history(rating_ym)")

    rows = []
    BATCH = 30_000

    for c in companies:
        bid = c['borrower_id']
        default_flag = c['default_flag']
        exit_ym = c.get('exit_ym') or (YM_END + 1)
        entry_ym = c.get('entry_ym') or YM_START
        firm_size = get_size_code(c.get('firm_size_cd', '소기업'))

        # 초기 등급
        curr_idx = GRADE_IDX[_init_grade(firm_size, default_flag, rng)]
        prev_grade = None

        # 등급 검토 주기: 6개월 or 12개월 (연간 검토 + 트리거)
        review_freq = 12  # 기본 연간
        check_ym = ym_add(entry_ym, review_freq)

        while check_ym < exit_ym and check_ym <= YM_END:
            months_to_exit = (exit_ym - check_ym) if default_flag and exit_ym <= YM_END else 999
            # Sigmoid 열화
            det = float(1.0 / (1.0 + np.exp(6.0 * (months_to_exit / 24.0 - 0.5)))) if months_to_exit < 24 else 0.0

            new_idx, direction = _transition(curr_idx, det, rng)

            # 트리거 이유
            if det > 0.6:
                trigger = "재무악화 심화"
            elif det > 0.3:
                trigger = "신용위험 증가"
            elif direction == "UP":
                trigger = "재무개선"
            elif direction == "DOWN":
                trigger = "정기검토결과"
            else:
                trigger = None

            # 연간 검토는 ANNUAL, 트리거 발생 시 TRIGGERED
            review_type = "TRIGGERED" if det > 0.4 else "ANNUAL"
            notches = abs(new_idx - curr_idx)

            curr_grade = GRADES[curr_idx]
            new_grade = GRADES[new_idx]
            pd_implied = GRADE_PD.get(new_grade, 0.01)

            rows.append((
                str(uuid.uuid4()), bid, check_ym,
                new_grade, prev_grade if prev_grade else curr_grade,
                direction, notches, round(pd_implied, 6),
                review_type, "SYSTEM", trigger,
                ym_add(check_ym, review_freq),
            ))

            prev_grade = curr_grade
            curr_idx = new_idx

            # 부도 임박 시 반기 검토로 전환
            review_freq = 6 if det > 0.3 else 12
            check_ym = ym_add(check_ym, review_freq)

            if len(rows) >= BATCH:
                conn.executemany("""
                    INSERT INTO fact_credit_rating_history
                      (rating_id, borrower_id, rating_ym, grade, prev_grade, grade_direction,
                       notches_changed, pd_implied, review_type, reviewed_by, trigger_reason,
                       valid_until_ym)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, rows)
                conn.commit()
                rows = []

    if rows:
        conn.executemany("""
            INSERT INTO fact_credit_rating_history
              (rating_id, borrower_id, rating_ym, grade, prev_grade, grade_direction,
               notches_changed, pd_implied, review_type, reviewed_by, trigger_reason,
               valid_until_ym)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM fact_credit_rating_history").fetchone()[0]
    grade_dist = conn.execute(
        "SELECT grade, COUNT(*) FROM fact_credit_rating_history GROUP BY 1 ORDER BY 1"
    ).fetchall()
    elapsed = round(time.time() - t0, 1)
    print(f"    fact_credit_rating_history: {total:,}행", flush=True)
    for g, cnt in grade_dist:
        print(f"      {g}: {cnt:,}건", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
