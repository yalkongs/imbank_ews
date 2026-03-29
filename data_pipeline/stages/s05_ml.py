"""
s05_ml.py — ml_survival / ml_walk_forward_splits 생성
v18의 s09_ml_tables() → v19 s05_ml_tables()
"""
import time

from config.macro import YM_START, YM_END, N_MONTHS, ym_add, ym_diff
from config.companies import N_COMPANIES


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s05_ml_tables(conn, companies):
    section("S05 ml_survival / walk_forward_splits")
    t0 = time.time()

    surv_rows = [(
        co['borrower_id'], co['entry_ym'],
        co['default_ym_internal'] if co['default_flag'] else None,
        co['default_flag'],
        ym_diff(co['_eff_exit'], co['entry_ym']) + 1,
        0 if co['default_flag'] else 1,
        co['firm_size_cd'], co['industry_cd'],
        co.get('industry_sub_cd')
    ) for co in companies]
    conn.executemany("INSERT OR IGNORE INTO ml_survival VALUES (?,?,?,?,?,?,?,?,?)", surv_rows)

    fold_rows = []
    fold_id = 1
    TRAIN_WINDOW = 60
    for step in range(0, 120, 4):
        val_start_offset = 60 + step
        val_start = ym_add(YM_START, val_start_offset)
        val_end = ym_add(val_start, 3)
        if val_end > YM_END:
            break
        train_end = ym_add(val_start, -1)
        train_start = max(ym_add(train_end, -(TRAIN_WINDOW - 1)), YM_START)

        n_tr = int(len(companies) * 0.85)
        n_te = int(len(companies) * 0.15)
        fold_rows.append((fold_id, train_start, train_end, val_start, val_end,
                          n_tr, n_te,
                          f"Fold{fold_id}: train {train_start}-{train_end}, val {val_start}-{val_end}"))
        fold_id += 1

    conn.executemany("INSERT OR IGNORE INTO ml_walk_forward_splits VALUES (?,?,?,?,?,?,?,?)", fold_rows)
    conn.commit()
    log(f"ml_survival:{len(surv_rows):,} / walk_forward:{len(fold_rows)} folds → {time.time() - t0:.1f}초")
