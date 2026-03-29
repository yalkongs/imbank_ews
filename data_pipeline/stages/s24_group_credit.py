"""
s24_group_credit.py — 그룹여신 및 계열사 보증 관계 생성 (v22 신규)

테이블:
  dim_borrower_group      — 기업 그룹 마스터 (재벌/중견그룹)
  fact_group_member       — 그룹 구성원 (지분관계)
  fact_group_guarantee    — 계열사 간 보증 관계
  fact_group_exposure     — 월별 그룹 총 익스포저 집계

그룹 유형:
  CHAEBOL  — 상호출자제한기업집단 (자산 5조 이상)
  MEDIUM   — 중견기업 그룹 (자산 1~5조)
  SMALL    — 소규모 기업군 (계열 2~3개)
"""
import time
import uuid
import numpy as np
from config.macro import YM_START, YM_END, MONTHS
from config.companies import get_size_code

GROUP_NAMES_CHAEBOL = [
    "삼강홀딩스", "대동그룹", "한울기업", "동방산업", "나라홀딩스",
    "태양그룹", "청호기업", "서울인더스트리", "동일그룹", "미래산업",
]

GROUP_NAMES_MEDIUM = [
    "경북산업", "대구실업", "영남기업", "낙동산업", "금호실업",
    "한국제조그룹", "대한기업", "현대산업", "동양실업", "서강기업",
    "아시아그룹", "한양홀딩스", "동서산업", "중앙기업", "남부실업",
]

GROUP_NAMES_SMALL = [
    "성림그룹", "진흥기업", "일신산업", "화성기업", "우성그룹",
    "청풍기업", "한빛산업", "대성기업", "동진실업", "신성그룹",
    "광명기업", "평화산업", "삼보기업", "세종홀딩스", "대원기업",
]

RELATION_TYPES = ["SUBSIDIARY", "AFFILIATE", "ASSOCIATE", "PARENT"]
GUARANTEE_TYPES = ["JOINT", "INDIVIDUAL", "MORTGAGE"]


def s24_group_credit(conn, companies, guarantee_pairs, rng):
    t0 = time.time()
    print("  [s24] 그룹여신 및 계열사 보증 생성", flush=True)

    conn.execute("DROP TABLE IF EXISTS dim_borrower_group")
    conn.execute("DROP TABLE IF EXISTS fact_group_member")
    conn.execute("DROP TABLE IF EXISTS fact_group_guarantee")
    conn.execute("DROP TABLE IF EXISTS fact_group_exposure")

    conn.execute("""
        CREATE TABLE dim_borrower_group (
            group_id          TEXT PRIMARY KEY,
            group_name        TEXT NOT NULL,
            group_type        TEXT NOT NULL,
            parent_company_id TEXT,
            total_exposure_억  REAL DEFAULT 0,
            group_limit_억     REAL DEFAULT 0,
            member_count      INTEGER DEFAULT 0,
            established_year  INTEGER,
            industry_cd       TEXT,
            default_risk_level TEXT DEFAULT 'LOW'
        )
    """)

    conn.execute("""
        CREATE TABLE fact_group_member (
            member_id        TEXT PRIMARY KEY,
            group_id         TEXT NOT NULL,
            borrower_id      TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            ownership_pct    REAL,
            is_parent        INTEGER DEFAULT 0,
            join_ym          INTEGER,
            exit_ym          INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_grpmem_gid ON fact_group_member(group_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_grpmem_bid ON fact_group_member(borrower_id)")

    conn.execute("""
        CREATE TABLE fact_group_guarantee (
            guarantee_id     TEXT PRIMARY KEY,
            group_id         TEXT NOT NULL,
            guarantor_id     TEXT NOT NULL,
            beneficiary_id   TEXT NOT NULL,
            guarantee_type   TEXT NOT NULL,
            guarantee_amount_억 REAL NOT NULL,
            effective_from   INTEGER NOT NULL,
            effective_to     INTEGER,
            status           TEXT DEFAULT 'ACTIVE'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_grpgua_gid ON fact_group_guarantee(group_id)")

    conn.execute("""
        CREATE TABLE fact_group_exposure (
            exposure_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id         TEXT NOT NULL,
            base_ym          INTEGER NOT NULL,
            total_exposure_억 REAL,
            utilized_amount_억 REAL,
            utilization_rate REAL,
            member_count     INTEGER,
            default_member_count INTEGER DEFAULT 0,
            group_risk_level TEXT,
            UNIQUE(group_id, base_ym)
        )
    """)

    # ── 기업 분류 ───────────────────────────────────────────────────────────
    bid_to_company = {c['borrower_id']: c for c in companies}
    large_cos = [c for c in companies if c.get('firm_size_cd') == '대기업']
    medium_cos = [c for c in companies if c.get('firm_size_cd') == '중견기업']
    small_cos = [c for c in companies if c.get('firm_size_cd') in ('중소기업', '소기업')]

    group_rows = []
    member_rows = []
    guarantee_rows = []
    exposure_rows = []

    # 그룹 구성: 대기업 중심 재벌그룹, 중견 그룹, 소규모 그룹
    used_bids = set()

    def form_group(parent, subsidiaries, group_type, name_pool, name_idx):
        group_id = str(uuid.uuid4())[:12]
        gname = name_pool[name_idx % len(name_pool)]
        members = [parent] + subsidiaries

        total_exp = sum(
            float(c.get('credit_limit_억') or c.get('asset_size_억', 0) or 0) for c in members
        )
        group_limit = total_exp * rng.uniform(1.2, 1.8)

        has_default = any(c['default_flag'] for c in members)
        risk_level = "HIGH" if has_default else ("MEDIUM" if total_exp > 500 else "LOW")

        group_rows.append((
            group_id, gname, group_type,
            parent['borrower_id'],
            round(total_exp, 1), round(group_limit, 1),
            len(members),
            parent.get('incorporation_year') or 2005,
            parent.get('industry_cd', 'K01A'),
            risk_level
        ))

        # 구성원
        for i, m in enumerate(members):
            if m['borrower_id'] in used_bids:
                continue
            used_bids.add(m['borrower_id'])
            is_parent = 1 if i == 0 else 0
            rel = "PARENT" if is_parent else RELATION_TYPES[rng.integers(0, len(RELATION_TYPES) - 1)]
            ownership = 100.0 if is_parent else float(rng.uniform(20, 100))
            join_ym = m.get('entry_ym') or YM_START

            member_rows.append((
                str(uuid.uuid4()), group_id, m['borrower_id'],
                rel, round(ownership, 1), is_parent, join_ym, None
            ))

        # 계열사 간 보증 (2~4쌍)
        if len(members) >= 2:
            n_guar = int(rng.integers(1, min(4, len(members))))
            for _ in range(n_guar):
                idx1, idx2 = rng.choice(len(members), size=2, replace=False)
                g = members[idx1]
                b = members[idx2]
                gtype = GUARANTEE_TYPES[rng.integers(0, len(GUARANTEE_TYPES))]
                gamt = round(float(rng.uniform(5, 100)), 1)
                eff_from = max(g.get('entry_ym', YM_START), b.get('entry_ym', YM_START))
                guarantee_rows.append((
                    str(uuid.uuid4()), group_id,
                    g['borrower_id'], b['borrower_id'],
                    gtype, gamt, eff_from, None, "ACTIVE"
                ))

        # 월별 익스포저 (분기별 스냅샷)
        for ym in MONTHS[::3]:  # 분기
            util_rate = float(rng.uniform(0.40, 0.85))
            utilized = round(total_exp * util_rate, 1)
            default_cnt = sum(1 for m in members
                              if m['default_flag'] and (m.get('exit_ym') or YM_END + 1) <= ym)
            grp_risk = "CRITICAL" if default_cnt > 0 else ("HIGH" if util_rate > 0.80 else "NORMAL")
            exposure_rows.append((
                group_id, ym, round(total_exp, 1), utilized,
                round(util_rate, 4), len(members), default_cnt, grp_risk
            ))

        return group_id

    # 재벌그룹 (대기업 중심, 5~12개 계열사)
    n_chaebol = min(len(large_cos), 20)
    rng.shuffle(large_cos)
    chaebol_idx = 0
    for i in range(n_chaebol):
        if not large_cos:
            break
        parent = large_cos[i]
        n_subs = int(rng.integers(4, 12))
        subs = [c for c in medium_cos + small_cos
                if c['borrower_id'] not in used_bids
                and c.get('industry_cd', '') == parent.get('industry_cd', '')
                ][:n_subs]
        if not subs:
            subs = [c for c in medium_cos if c['borrower_id'] not in used_bids][:n_subs]
        form_group(parent, subs, "CHAEBOL", GROUP_NAMES_CHAEBOL, chaebol_idx)
        chaebol_idx += 1

    # 중견그룹 (중기업 중심, 3~6개 계열사)
    medium_free = [c for c in medium_cos if c['borrower_id'] not in used_bids]
    n_medium = min(len(medium_free), 40)
    for i in range(n_medium):
        if i >= len(medium_free):
            break
        parent = medium_free[i]
        n_subs = int(rng.integers(2, 6))
        subs = [c for c in small_cos if c['borrower_id'] not in used_bids][:n_subs]
        form_group(parent, subs, "MEDIUM", GROUP_NAMES_MEDIUM, i)

    # 소규모 그룹 (소기업 2~3개)
    small_free = [c for c in small_cos if c['borrower_id'] not in used_bids]
    n_small = min(len(small_free) // 3, 80)
    for i in range(n_small):
        idx = i * 3
        if idx + 1 >= len(small_free):
            break
        parent = small_free[idx]
        subs = [c for c in small_free[idx+1:idx+3] if c['borrower_id'] not in used_bids]
        form_group(parent, subs, "SMALL", GROUP_NAMES_SMALL, i)

    # ── INSERT ───────────────────────────────────────────────────────────────
    conn.executemany("""
        INSERT INTO dim_borrower_group
          (group_id, group_name, group_type, parent_company_id,
           total_exposure_억, group_limit_억, member_count,
           established_year, industry_cd, default_risk_level)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, group_rows)

    conn.executemany("""
        INSERT INTO fact_group_member
          (member_id, group_id, borrower_id, relationship_type,
           ownership_pct, is_parent, join_ym, exit_ym)
        VALUES (?,?,?,?,?,?,?,?)
    """, member_rows)

    conn.executemany("""
        INSERT INTO fact_group_guarantee
          (guarantee_id, group_id, guarantor_id, beneficiary_id,
           guarantee_type, guarantee_amount_억, effective_from, effective_to, status)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, guarantee_rows)

    conn.executemany("""
        INSERT OR IGNORE INTO fact_group_exposure
          (group_id, base_ym, total_exposure_억, utilized_amount_억,
           utilization_rate, member_count, default_member_count, group_risk_level)
        VALUES (?,?,?,?,?,?,?,?)
    """, exposure_rows)

    conn.commit()

    elapsed = round(time.time() - t0, 1)
    print(f"    dim_borrower_group: {len(group_rows):,}건", flush=True)
    print(f"    fact_group_member: {len(member_rows):,}건", flush=True)
    print(f"    fact_group_guarantee: {len(guarantee_rows):,}건", flush=True)
    print(f"    fact_group_exposure: {len(exposure_rows):,}건", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
