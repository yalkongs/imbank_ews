"""
s06_network.py — guarantee_network + company_relationship 생성
v18의 s12_s13_stress_network() 중 네트워크 부분 → v19 s06_network()
"""
import time


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s06_network(conn, companies, guarantee_pairs):
    section("S06 guarantee_network / company_relationship")
    t0 = time.time()

    # guarantee_network 테이블
    guar_rows = []
    for g_idx, b_idx, amt, s_ym, e_ym in guarantee_pairs:
        g_bid = companies[g_idx]['borrower_id']
        b_bid = companies[b_idx]['borrower_id']
        guar_rows.append((None, g_bid, b_bid, amt, s_ym, e_ym))
    conn.executemany("INSERT INTO guarantee_network VALUES (?,?,?,?,?,?)", guar_rows)

    # company_relationship (보증관계 기반, 상위 300쌍)
    rel_rows = []
    for g_idx, b_idx, amt, s_ym, e_ym in guarantee_pairs[:300]:
        g_bid = companies[g_idx]['borrower_id']
        b_bid = companies[b_idx]['borrower_id']
        rel_rows.append((None, g_bid, b_bid, '보증관계', round(float(amt / 100), 2)))
    conn.executemany("INSERT INTO company_relationship VALUES (?,?,?,?,?)", rel_rows)

    conn.commit()
    log(f"guarantee_network {len(guar_rows)}쌍 | company_relationship {len(rel_rows)}건 → {time.time() - t0:.1f}초")
