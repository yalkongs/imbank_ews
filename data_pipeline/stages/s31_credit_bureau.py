"""
s31_credit_bureau.py — 신용조회 이력 생성 (v24 신규)

테이블:
  credit_bureau_inquiry_log — 차주별 신용조회 기록

조회 유형:
  NEW_LOAN     — 신규 여신 신청 시 조회
  RENEWAL      — 여신 갱신 심사 시 조회
  MONITORING   — 정기 모니터링 조회
  DELINQUENCY  — 연체 발생 후 조회

조회 기관:
  NICE    — NICE신용평가정보
  KCB     — 한국신용평가(코리아크레딧뷰로)
  KODIT   — 신용보증기금
  KIBO    — 기술보증기금
"""
import time
import numpy as np
from config.macro import YM_START, YM_END, MONTHS, ym_add
from config.companies import get_size_code

INQUIRY_TYPES = ["NEW_LOAN", "RENEWAL", "MONITORING", "DELINQUENCY"]
BUREAU_NAMES  = ["NICE", "KCB", "KODIT", "KIBO"]

# 기업 규모별 조회 빈도 (연간 평균)
INQUIRY_FREQ = {"L": 2.0, "M": 2.5, "S": 3.0}

# 결과 등급 (신용조회 기관 반환 등급)
RESULT_GRADES = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]

# 기업 규모별 초기 조회 결과 등급 분포 (좋은 등급=낮은 숫자)
GRADE_DIST = {
    "L": [0.10, 0.20, 0.25, 0.20, 0.15, 0.05, 0.03, 0.01, 0.01, 0.00],
    "M": [0.05, 0.10, 0.20, 0.25, 0.20, 0.10, 0.05, 0.03, 0.01, 0.01],
    "S": [0.02, 0.05, 0.10, 0.15, 0.20, 0.20, 0.13, 0.08, 0.05, 0.02],
}


def s31_credit_bureau(conn, companies, rng):
    t0 = time.time()
    print("  [s31] 신용조회 이력 생성", flush=True)

    conn.execute("DELETE FROM credit_bureau_inquiry_log")

    # DPD 캐시 — 연체 발생 시 DELINQUENCY 조회 추가
    dpd_cache = set()
    if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fact_delinquency'"
    ).fetchone():
        for row in conn.execute(
            "SELECT borrower_id, overdue_ym FROM fact_delinquency WHERE max_dpd > 0"
        ).fetchall():
            dpd_cache.add((row[0], row[1]))

    rows = []
    BATCH = 50_000

    for c in companies:
        bid = c['borrower_id']
        default_flag = c['default_flag']
        exit_ym = c.get('exit_ym') or (YM_END + 1)
        entry_ym = c.get('entry_ym') or YM_START
        firm_size = get_size_code(c.get('firm_size_cd', '소기업'))

        freq = INQUIRY_FREQ.get(firm_size, 2.5)
        grade_dist = GRADE_DIST.get(firm_size, GRADE_DIST["S"])
        grade_idx = int(rng.choice(10, p=grade_dist))

        # 입점 시 신규여신 조회
        bureau = BUREAU_NAMES[rng.integers(0, len(BUREAU_NAMES))]
        result = RESULT_GRADES[grade_idx]
        rows.append((bid, entry_ym, "NEW_LOAN", bureau, result))

        # 갱신/모니터링 조회 (연간 freq회 확률적 발생)
        for ym in MONTHS:
            if ym <= entry_ym or ym >= exit_ym:
                continue

            months_to_exit = (exit_ym - ym) if default_flag and exit_ym <= YM_END else 999
            deterioration = max(0.0, 1.0 - months_to_exit / 24.0) if months_to_exit < 24 else 0.0

            # 월별 조회 발생 확률 (연간 freq / 12)
            if rng.random() > freq / 12.0:
                # 연체 발생 시 DELINQUENCY 조회는 별도
                if (bid, ym) in dpd_cache:
                    bureau = BUREAU_NAMES[rng.integers(0, len(BUREAU_NAMES))]
                    # 등급 악화 반영
                    det_shift = int(deterioration * 3)
                    g = min(grade_idx + det_shift, 9)
                    rows.append((bid, ym, "DELINQUENCY", bureau, RESULT_GRADES[g]))
                continue

            # 조회 유형 결정
            if (bid, ym) in dpd_cache:
                inq_type = "DELINQUENCY"
            elif ym % 12 == entry_ym % 12:  # 연주기 갱신
                inq_type = "RENEWAL"
            else:
                inq_type = "MONITORING"

            bureau = BUREAU_NAMES[rng.integers(0, len(BUREAU_NAMES))]
            det_shift = int(deterioration * 3 + rng.integers(0, 2))
            g = min(grade_idx + det_shift, 9)
            result = RESULT_GRADES[g]

            rows.append((bid, ym, inq_type, bureau, result))

        if len(rows) >= BATCH:
            conn.executemany(
                "INSERT INTO credit_bureau_inquiry_log "
                "(borrower_id, inquiry_ym, inquiry_type, bureau_name, result_grade) "
                "VALUES (?,?,?,?,?)",
                rows
            )
            conn.commit()
            rows = []

    if rows:
        conn.executemany(
            "INSERT INTO credit_bureau_inquiry_log "
            "(borrower_id, inquiry_ym, inquiry_type, bureau_name, result_grade) "
            "VALUES (?,?,?,?,?)",
            rows
        )
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM credit_bureau_inquiry_log").fetchone()[0]
    type_dist = conn.execute(
        "SELECT inquiry_type, COUNT(*) FROM credit_bureau_inquiry_log GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    elapsed = round(time.time() - t0, 1)
    print(f"    credit_bureau_inquiry_log: {total:,}행", flush=True)
    for itype, cnt in type_dist:
        print(f"      {itype}: {cnt:,}건", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
