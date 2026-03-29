"""
s07_ews.py — ews_action_outcome / migration_matrix_yearly 생성
v18의 s10_action_and_migration() → v19 s07_action_and_migration()
"""
import time

import numpy as np

from config.macro import PHASE_MAP, YM_END, ym_add
from config.companies import GRADE_SEQ


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s07_action_and_migration(conn, companies, rng):
    section("S07 ews_action_outcome / migration_matrix")
    t0 = time.time()

    action_rows = []
    outcomes = ['조기상환완료', '재구조화', '모니터링지속', '연체전환', '부도']
    actions = ['한도축소', '현장방문', '서류징구', '보증강화', '회수착수']
    for co in companies:
        if co['default_flag'] or co['exit_reason'] == '조기상환':
            alert_ym = ym_add(co['entry_ym'], int(rng.integers(6, 30)))
            if alert_ym > co['_eff_exit']:
                alert_ym = co['entry_ym']
            action_rows.append((
                co['borrower_id'], alert_ym,
                rng.choice(['주의', '경계', '위기']),
                rng.choice(actions), 1,
                '부도' if co['default_flag'] else rng.choice(outcomes),
                f"RM{rng.integers(1, 50):03d}"
            ))
    conn.executemany(
        "INSERT INTO ews_action_outcome(borrower_id,alert_ym,ews_grade_at_alert,"
        "action_code,action_completed_flag,outcome_type,reviewer_id) VALUES (?,?,?,?,?,?,?)",
        action_rows)

    BASE_ALPHA = {
        '정상': [8.0, 1.5, 0.3, 0.1, 0.05],
        '관심': [2.0, 6.0, 1.5, 0.3, 0.1],
        '주의': [0.5, 2.0, 5.0, 1.5, 0.3],
        '경계': [0.2, 0.5, 1.5, 4.0, 1.5],
        '위기': [0.1, 0.2, 0.5, 1.5, 6.0],
    }
    STRESS_SHIFT = {
        '정상': [-0.4, 0.0, 0.15, 0.15, 0.1],
        '관심': [-0.3, -0.2, 0.2, 0.2, 0.1],
        '주의': [-0.2, -0.2, -0.1, 0.3, 0.2],
        '경계': [-0.1, -0.1, -0.1, -0.2, 0.5],
        '위기': [0.0, 0.0, -0.1, -0.2, 0.3],
    }
    mig_rows = []
    for yr in range(2017, 2026):
        ym_yr = yr * 100 + 12
        stress = PHASE_MAP.get(ym_yr, PHASE_MAP[YM_END])[1]
        total_n = int(rng.integers(10000, 25000))
        for fg in GRADE_SEQ:
            alpha_base = np.array(BASE_ALPHA[fg], dtype=float)
            shift = np.array(STRESS_SHIFT[fg]) * stress
            alpha_adj = np.maximum(alpha_base + shift * alpha_base, 0.05)
            trans_probs = rng.dirichlet(alpha_adj)
            fg_total = int(total_n * rng.uniform(0.1, 0.35))
            row_probs = []
            acc = 0.0
            for k, tg in enumerate(GRADE_SEQ):
                if k < len(GRADE_SEQ) - 1:
                    p = round(float(trans_probs[k]), 4)
                else:
                    p = round(1.0 - acc, 4)
                acc += p
                cnt = max(int(fg_total * trans_probs[k]), 0)
                mig_rows.append((ym_yr, fg, tg, p, cnt))
    conn.executemany("INSERT OR IGNORE INTO migration_matrix_yearly VALUES (?,?,?,?,?)", mig_rows)
    conn.commit()
    log(f"ews_action_outcome:{len(action_rows)} / migration:{len(mig_rows)} → {time.time() - t0:.1f}초")
