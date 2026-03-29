"""
s08_collateral.py — dim_facility / dim_collateral / fact_collateral_monthly 생성
v18의 s08_collateral_and_misc() → v19 s08_collateral()
ca는 메모리에서 전달받거나, _raw_company_arrays 테이블에서 로드
"""
import time

from config.macro import PHASE_MAP, YM_END, ym_add, ym_diff


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s08_collateral(conn, companies, ca, rng):
    section("S08 collateral / facility")
    t0 = time.time()

    # ca가 None이면 DB에서 로드
    if ca is None:
        from stages.s01_company import load_ca_from_db
        ca = load_ca_from_db(conn)

    fac_rows, col_rows, col_mo_rows = [], [], []
    for co in companies:
        bid = co['borrower_id']
        eff_exit = co['_eff_exit']
        n_fac = int(rng.integers(1, 4))
        for f in range(n_fac):
            fid = f"{bid}_F{f + 1}"
            f_type = rng.choice(['운전자금', '시설자금', '무역금융', '보증'])
            orig_ym = co['entry_ym']
            mat_ym = ym_add(orig_ym, int(rng.integers(12, 60)))
            amt = round(float(rng.lognormal(3, 1)), 1)
            rate = round(float(rng.normal(
                {'대기업': 2.5, '중견기업': 3.5, '중소기업': 5.0, '소기업': 7.0}[co['firm_size_cd']], 0.5)), 2)
            fac_rows.append((fid, bid, f_type, orig_ym, mat_ym, amt, rate,
                             1 if rng.random() < 0.6 else 0))

            if rng.random() < 0.5:
                cid = f"{bid}_C{f + 1}"
                c_type = rng.choice(['부동산', '동산', '예금담보', '보증서'])
                appr = round(float(rng.lognormal(3.5, 0.8)), 1)
                col_rows.append((cid, bid, c_type, appr, orig_ym, '정상'))

                prev_val = appr
                for k_offset in range(0, ym_diff(eff_exit, orig_ym) + 1, 3):
                    cym = ym_add(orig_ym, k_offset)
                    if cym > eff_exit or cym > YM_END:
                        break
                    ph = PHASE_MAP.get(cym, PHASE_MAP[YM_END])
                    mf = ph[4]
                    price_chg = mf * 0.03 + rng.normal(0, 0.025)
                    val = round(max(prev_val * (1 + price_chg), appr * 0.2), 1)
                    prev_val = val
                    ltv_v = round(amt / max(val, 0.1) * 100, 1)
                    rcr = round(max(val, 0.1) / max(amt, 0.1), 2)
                    slope = round(price_chg, 4)
                    col_mo_rows.append((bid, cym, ltv_v, val, 0, rcr, slope))

    conn.executemany("INSERT OR IGNORE INTO dim_facility VALUES (?,?,?,?,?,?,?,?)", fac_rows)
    conn.executemany("INSERT OR IGNORE INTO dim_collateral VALUES (?,?,?,?,?,?)", col_rows)
    conn.executemany("INSERT OR IGNORE INTO fact_collateral_monthly VALUES (?,?,?,?,?,?,?)", col_mo_rows)
    conn.commit()
    log(f"facility:{len(fac_rows)} col:{len(col_rows)} col_monthly:{len(col_mo_rows)} → {time.time() - t0:.1f}초")
