"""
s12_mnar.py — MNAR(Missing Not At Random) 노이즈 적용
기업 특성 기반으로 ml_feature_label의 ebitda_margin_pct / dscr_ratio / sales_growth_pct를
NULL 처리 + inflow_amt_3m_change_pct에 노이즈 추가
v18의 s15_mnar_noise() → v19 s12_mnar_noise()
v18 S1: 배치 평균 방식 → 기업별 개별 mp 적용 (임시 테이블 JOIN)
"""
import time

from config.mnar import BASE_MNAR, UNLISTED_ADD, IND_ADD, MP_CAP


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s12_mnar_noise(conn, companies):
    section("S12 MNAR — 기업 특성 기반")
    t0 = time.time()

    # v18 S1: 기업별 mp를 임시 테이블에 저장 후 JOIN UPDATE
    conn.execute("""
        CREATE TEMP TABLE IF NOT EXISTS _mnar_params (
            borrower_id TEXT PRIMARY KEY,
            mp_int INTEGER,
            mp_dscr INTEGER,
            mp_sg   INTEGER
        )
    """)
    params_rows = []
    for co in companies:
        mp = BASE_MNAR[co['firm_size_cd']]
        if not co['listed_flag']:
            mp += UNLISTED_ADD
        mp += IND_ADD.get(co['industry_category'], 0)
        mp = min(mp, MP_CAP)
        params_rows.append((
            co['borrower_id'],
            int(mp * 100),
            int(mp * 80),
            int(mp * 60),
        ))
    conn.executemany("INSERT OR REPLACE INTO _mnar_params VALUES (?,?,?,?)", params_rows)
    conn.commit()

    conn.execute("""
        UPDATE ml_feature_label
        SET ebitda_margin_pct = NULL
        WHERE rowid IN (
            SELECT m.rowid FROM ml_feature_label m
            JOIN _mnar_params p ON m.borrower_id = p.borrower_id
            WHERE (ABS(CAST(SUBSTR(m.borrower_id,4) AS INTEGER)*17 + m.ym) % 100) < p.mp_int
        )
    """)
    conn.execute("""
        UPDATE ml_feature_label
        SET dscr_ratio = NULL
        WHERE rowid IN (
            SELECT m.rowid FROM ml_feature_label m
            JOIN _mnar_params p ON m.borrower_id = p.borrower_id
            WHERE (ABS(CAST(SUBSTR(m.borrower_id,4) AS INTEGER)*13 + m.ym) % 100) < p.mp_dscr
        )
    """)
    conn.execute("""
        UPDATE ml_feature_label
        SET sales_growth_pct = NULL
        WHERE rowid IN (
            SELECT m.rowid FROM ml_feature_label m
            JOIN _mnar_params p ON m.borrower_id = p.borrower_id
            WHERE (ABS(CAST(SUBSTR(m.borrower_id,4) AS INTEGER)*11 + m.ym) % 100) < p.mp_sg
        )
    """)
    conn.execute("DROP TABLE IF EXISTS _mnar_params")

    conn.execute("""
        UPDATE ml_feature_label SET inflow_amt_3m_change_pct =
            inflow_amt_3m_change_pct * (1 + (ABS(RANDOM()) % 30 - 15) / 100.0)
        WHERE (ABS(CAST(SUBSTR(borrower_id,4) AS INTEGER) + ym) % 100) < 8
    """)
    conn.commit()

    r = conn.execute("SELECT COUNT(*) FROM ml_feature_label WHERE ebitda_margin_pct IS NULL").fetchone()[0]
    r2 = conn.execute("SELECT COUNT(*) FROM ml_feature_label WHERE dscr_ratio IS NULL").fetchone()[0]
    r3 = conn.execute("SELECT COUNT(*) FROM ml_feature_label WHERE sales_growth_pct IS NULL").fetchone()[0]
    log(f"MNAR: ebitda={r:,} / dscr={r2:,} / sales_growth={r3:,} → {time.time() - t0:.1f}초")
