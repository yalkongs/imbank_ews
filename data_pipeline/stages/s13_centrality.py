"""
s13_centrality.py — network_centrality / GNN 인프라 생성
v18의 s16_network_centrality() → v19 s13_network_centrality()
"""
import time

import numpy as np

from config.companies import INDUSTRIES


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s13_network_centrality(conn, companies, guarantee_pairs, rng):
    section("S13 network_centrality / GNN 인프라")
    t0 = time.time()
    N = len(companies)
    bids = [c['borrower_id'] for c in companies]

    # 인접 리스트 구성
    out_nb = [[] for _ in range(N)]
    in_nb = [[] for _ in range(N)]
    for g_idx, b_idx, amt, s_ym, e_ym in guarantee_pairs:
        out_nb[g_idx].append(b_idx)
        in_nb[b_idx].append(g_idx)

    out_deg = np.array([len(out_nb[i]) for i in range(N)], dtype=float)
    in_deg = np.array([len(in_nb[i]) for i in range(N)], dtype=float)
    total_deg = out_deg + in_deg
    degree_c = total_deg / max(N - 1, 1)

    # PageRank 근사 (degree-weighted, 5회 반복)
    pr = np.ones(N, dtype=float) / N
    d = 0.85
    for _ in range(5):
        new_pr = np.full(N, (1.0 - d) / N)
        dangling_sum = d * pr[out_deg == 0].sum() / N
        new_pr += dangling_sum
        for i in range(N):
            if out_nb[i]:
                contrib = d * pr[i] / len(out_nb[i])
                for j in out_nb[i]:
                    new_pr[j] += contrib
        pr = new_pr
    pr = pr / (pr.sum() + 1e-12) * N

    # 이웃 EWS 평균 및 부도율
    ews_arr = np.array([c['_ews_mean'] for c in companies], dtype=float)
    def_arr = np.array([c['default_flag'] for c in companies], dtype=float)
    neighbor_avg_ews = np.full(N, np.nan)
    neighbor_def_rate = np.zeros(N, dtype=float)
    has_nb = np.zeros(N, dtype=bool)

    for i in range(N):
        neighbors = out_nb[i] + in_nb[i]
        if neighbors:
            has_nb[i] = True
            nb_arr = np.array(neighbors)
            neighbor_avg_ews[i] = float(np.mean(ews_arr[nb_arr]))
            neighbor_def_rate[i] = float(np.mean(def_arr[nb_arr]))

    # CONTAGION 체인 깊이
    chain_depth = np.zeros(N, dtype=int)
    for i, c in enumerate(companies):
        if c['default_path_type'] == 'CONTAGION':
            chain_depth[i] = 1
            for g_idx in in_nb[i]:
                if companies[g_idx]['default_path_type'] == 'CONTAGION':
                    chain_depth[i] = 2
                    break

    cent_rows = []
    for i in range(N):
        cent_rows.append((
            bids[i],
            round(float(degree_c[i]), 6),
            int(in_deg[i]),
            int(out_deg[i]),
            round(float(pr[i]), 8),
            round(float(neighbor_avg_ews[i]), 2) if has_nb[i] else None,
            round(float(neighbor_def_rate[i]), 4),
            int(chain_depth[i]),
        ))
    conn.executemany(
        "INSERT OR IGNORE INTO network_centrality VALUES (?,?,?,?,?,?,?,?)", cent_rows)

    # 거래 관계 + 계열사 관계 (company_relationship 확장)
    constr_pool = [i for i, c in enumerate(companies) if c['industry_category'] == '건설업']
    mfg_pool = [i for i, c in enumerate(companies) if c['industry_category'] in ('일반제조업', '첨단제조업', '운수창고업')]
    trade_rows = []
    trade_seen = set()
    n_trade = min(3000, len(constr_pool) * 2)
    attempts = 0
    while len(trade_rows) < n_trade and attempts < n_trade * 6:
        attempts += 1
        g = int(rng.choice(constr_pool)) if constr_pool else int(rng.integers(0, N))
        b = int(rng.choice(mfg_pool)) if mfg_pool else int(rng.integers(0, N))
        if g == b or (g, b) in trade_seen:
            continue
        trade_seen.add((g, b))
        trade_rows.append((None, bids[g], bids[b], '거래처',
                           round(float(rng.uniform(0.05, 0.75)), 2)))

    # 대기업 → 중견기업 계열사 관계
    large_pool = [i for i, c in enumerate(companies) if c['firm_size_cd'] == '대기업']
    mid_pool = [i for i, c in enumerate(companies) if c['firm_size_cd'] == '중견기업']
    affil_rows = []
    affil_seen = set()
    for g in large_pool[:200]:
        n_subs = int(rng.integers(1, 5))
        added = 0
        for _ in range(n_subs * 5):
            if added >= n_subs:
                break
            b = int(rng.choice(mid_pool)) if mid_pool else int(rng.integers(0, N))
            if g == b or (g, b) in affil_seen:
                continue
            affil_seen.add((g, b))
            affil_rows.append((None, bids[g], bids[b], '계열사',
                               round(float(rng.uniform(0.20, 0.85)), 2)))
            added += 1

    if trade_rows or affil_rows:
        conn.executemany(
            "INSERT INTO company_relationship VALUES (?,?,?,?,?)",
            trade_rows + affil_rows)

    conn.commit()
    log(f"network_centrality:{len(cent_rows):,} | "
        f"trade:{len(trade_rows)} | affil:{len(affil_rows)} → {time.time() - t0:.1f}초")
