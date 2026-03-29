#!/usr/bin/env python3
"""
add_collateral_history.py — v21 담보 평가 이력 추가

1. dim_collateral     — 담보 유형 세분화, 신규 컬럼 추가
2. fact_collateral_appraisal (신규) — 감정평가 이력 전체 생성
3. fact_collateral_disposal  — 부도 기업 담보 처분 이력 생성

실행: python3 add_collateral_history.py
"""
import sqlite3
import time
import uuid
from pathlib import Path

import numpy as np

DB_PATH = Path("ews_corporate_v21.db")
SEED = 42

# ─────────────────────────────────────────────────────────────
# 담보 유형 세분화
# ─────────────────────────────────────────────────────────────
# (대분류, 소분류, 평가방법, 평가주기_개월, 처분방법, 감정기관유형)
COLLATERAL_SUBTYPES = {
    "부동산": [
        ("토지",      "거래사례비교법",  24, "공매",    "감정평가법인"),
        ("건물",      "원가법",         24, "공매",    "감정평가법인"),
        ("공장",      "원가법",         24, "공매",    "감정평가법인"),
        ("아파트",    "거래사례비교법",  12, "임의경매", "한국부동산원"),
        ("상가",      "수익환원법",      12, "임의경매", "감정평가법인"),
        ("오피스텔",  "거래사례비교법",  12, "임의경매", "한국부동산원"),
    ],
    "유가증권": [
        ("상장주식",   "시가평가",        1, "증권사매각", "증권사"),
        ("비상장주식", "DCF/순자산",     12, "장외매각",  "회계법인"),
        ("국채",       "시가평가",        1, "증권사매각", "증권사"),
        ("회사채",     "시가평가",        1, "증권사매각", "증권사"),
        ("MBS",        "시가평가",        3, "증권사매각", "증권사"),
    ],
    "예금": [
        ("정기예금",  "액면가",          0, "즉시상계",  "은행자체"),
        ("정기적금",  "액면가",          0, "즉시상계",  "은행자체"),
        ("MMF",       "시가평가",        1, "즉시환매",  "은행자체"),
        ("외화예금",  "액면가(환산)",    1, "즉시상계",  "은행자체"),
    ],
    "동산": [
        ("기계/설비",  "원가법",         12, "공장경매", "감정평가법인"),
        ("자동차",     "시세비교법",      6, "공매",    "보험개발원"),
        ("재고자산",   "장부가",          3, "협의매각", "감정평가법인"),
        ("선박",       "원가법",         12, "공매",    "선박감정원"),
    ],
    "보증서": [
        ("은행보증서",    "액면가",  0, "보증이행청구", "은행자체"),
        ("신용보증기금",  "액면가",  0, "보증이행청구", "신용보증기금"),
        ("기술보증기금",  "액면가",  0, "보증이행청구", "기술보증기금"),
        ("보험증권",      "액면가",  0, "보험금청구",  "보험사"),
    ],
}

# 감정평가법인 이름
APPRAISERS = {
    "감정평가법인": ["한국감정원", "대한감정법인", "나라감정", "하나감정법인",
                     "국제감정", "태평양감정법인", "감정원코리아"],
    "한국부동산원": ["한국부동산원"],
    "증권사":       ["미래에셋증권", "삼성증권", "NH투자증권", "KB증권", "한국투자증권"],
    "회계법인":     ["삼일회계법인", "안진회계법인", "삼정KPMG", "한영회계법인"],
    "은행자체":     ["은행자체평가"],
    "보험개발원":   ["보험개발원"],
    "선박감정원":   ["한국선박감정원"],
    "신용보증기금": ["신용보증기금"],
    "기술보증기금": ["기술보증기금"],
    "보험사":       ["삼성화재", "현대해상", "KB손해보험", "DB손해보험"],
}

# 부동산 시장 트렌드 (연도별 가격 변동률 %)
# 2017~2021 상승장, 2022 급락, 2023~2025 회복세
RE_TREND = {
    2017: +4.5, 2018: +5.2, 2019: +3.8, 2020: +7.2, 2021: +11.3,
    2022: -8.4, 2023: +1.2, 2024: +2.8, 2025: +3.1,
}
# 주식시장 변동률
STOCK_TREND = {
    2017: +21.8, 2018: -17.3, 2019: +7.7, 2020: +30.8, 2021: +3.6,
    2022: -24.9, 2023: +18.7, 2024: +9.2, 2025: +5.4,
}


def ym_add(ym: int, months: int) -> int:
    y, m = divmod(ym, 100)
    m += months
    while m > 12:
        m -= 12; y += 1
    while m < 1:
        m += 12; y -= 1
    return y * 100 + m


def ym_diff(ym2: int, ym1: int) -> int:
    y2, m2 = divmod(ym2, 100)
    y1, m1 = divmod(ym1, 100)
    return (y2 - y1) * 12 + (m2 - m1)


def main():
    rng = np.random.default_rng(SEED)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    t0 = time.time()

    print("=" * 65)
    print("  v21 담보 평가 이력 추가")
    print("=" * 65)

    # ─────────────────────────────────────────────────────────
    # STEP 1: dim_collateral 유형 세분화 및 컬럼 추가
    # ─────────────────────────────────────────────────────────
    print("\n[STEP 1] dim_collateral 유형 세분화 및 컬럼 추가")

    existing_cols = {c[1] for c in conn.execute("PRAGMA table_info(dim_collateral)").fetchall()}
    new_cols = {
        "collateral_subtype":    "TEXT",    # 세부 담보 종류
        "appraisal_method":      "TEXT",    # 평가 방법
        "appraisal_cycle_months":"INTEGER", # 재감정 주기 (개월)
        "disposal_method":       "TEXT",    # 처분 방법
        "appraiser_type":        "TEXT",    # 감정기관 유형
        "ltv_limit_pct":         "REAL",    # LTV 한도 (%)
        "pledge_rank":           "INTEGER", # 담보 순위 (1순위, 2순위)
        "secured_amount_억":     "REAL",    # 채권최고액
    }
    for col, dtype in new_cols.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE dim_collateral ADD COLUMN {col} {dtype}")
    conn.commit()

    # 기존 대분류별로 세부 유형 배정
    collaterals = conn.execute(
        "SELECT collateral_id, borrower_id, collateral_type, appraised_value_억 FROM dim_collateral"
    ).fetchall()

    updates = []
    for c in collaterals:
        ctype = c["collateral_type"]
        subtypes = COLLATERAL_SUBTYPES.get(ctype, COLLATERAL_SUBTYPES["동산"])
        sub = subtypes[rng.integers(0, len(subtypes))]
        subtype_name, method, cycle, disposal, appraiser_type = sub

        # LTV 한도: 담보 유형별
        ltv_limits = {
            "부동산": rng.uniform(60, 80),
            "유가증권": rng.uniform(50, 70),
            "예금": 95.0,
            "동산": rng.uniform(40, 60),
            "보증서": 100.0,
        }
        ltv = ltv_limits.get(ctype, 60.0)
        pledge = int(rng.choice([1, 1, 1, 2], p=[0.75, 0, 0, 0.25]))  # 1순위 75%
        secured = round(float(c["appraised_value_억"]) * rng.uniform(1.1, 1.3), 1)  # 채권최고액 = 감정가 × 110~130%

        updates.append((
            subtype_name, method, int(cycle), disposal, appraiser_type,
            round(ltv, 1), pledge, secured,
            c["collateral_id"],
        ))

    conn.executemany("""
        UPDATE dim_collateral SET
          collateral_subtype=?, appraisal_method=?, appraisal_cycle_months=?,
          disposal_method=?, appraiser_type=?, ltv_limit_pct=?,
          pledge_rank=?, secured_amount_억=?
        WHERE collateral_id=?
    """, updates)
    conn.commit()
    print(f"  dim_collateral {len(updates):,}건 유형 세분화 완료")

    # ─────────────────────────────────────────────────────────
    # STEP 2: fact_collateral_appraisal 테이블 생성
    # ─────────────────────────────────────────────────────────
    print("\n[STEP 2] fact_collateral_appraisal 테이블 생성")
    conn.execute("DROP TABLE IF EXISTS fact_collateral_appraisal")
    conn.execute("""
        CREATE TABLE fact_collateral_appraisal (
            appraisal_id         TEXT PRIMARY KEY,
            collateral_id        TEXT NOT NULL,
            borrower_id          TEXT NOT NULL,
            appraisal_ym         INTEGER NOT NULL,
            appraisal_value_억    REAL NOT NULL,
            prev_appraisal_value_억 REAL,
            value_change_pct     REAL,
            appraisal_method     TEXT NOT NULL,
            appraisal_reason     TEXT NOT NULL,
            appraiser_name       TEXT NOT NULL,
            appraiser_type       TEXT NOT NULL,
            ltv_at_appraisal     REAL,
            market_index_ref     REAL,
            notes                TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cap_coll ON fact_collateral_appraisal(collateral_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cap_bor  ON fact_collateral_appraisal(borrower_id, appraisal_ym)")
    conn.commit()

    # 부도 기업 목록 (default_ym 포함)
    defaulted = {
        r["borrower_id"]: r["default_ym_internal"]
        for r in conn.execute(
            "SELECT borrower_id, default_ym_internal FROM dim_company WHERE default_flag=1 AND default_ym_internal IS NOT NULL"
        ).fetchall()
    }

    # 담보 목록 (전체)
    coll_list = conn.execute("""
        SELECT d.collateral_id, d.borrower_id, d.registration_ym,
               d.appraised_value_억, d.collateral_type, d.collateral_subtype,
               d.appraisal_method, d.appraisal_cycle_months, d.appraiser_type,
               d.ltv_limit_pct,
               dc.committed_amount_억
        FROM dim_collateral d
        LEFT JOIN dim_facility dc ON d.borrower_id = dc.borrower_id
    """).fetchall()

    # collateral_id별로 deduplicate (LEFT JOIN으로 중복 발생)
    coll_map = {}
    for c in coll_list:
        cid = c["collateral_id"]
        if cid not in coll_map:
            coll_map[cid] = dict(c)

    APPRAISAL_REASONS = ["정기재평가", "정기재평가", "담보추가", "여신심사", "처분검토", "부도대응"]
    YM_END = 202512

    appraisal_rows = []
    print(f"  담보 {len(coll_map):,}건 평가 이력 생성 중...")

    for cid, c in coll_map.items():
        reg_ym   = c["registration_ym"] or 201701
        ctype    = c["collateral_type"]
        subtype  = c["collateral_subtype"] or ""
        method   = c["appraisal_method"] or "거래사례비교법"
        cycle    = c["appraisal_cycle_months"] or 12
        app_type = c["appraiser_type"] or "감정평가법인"
        init_val = float(c["appraised_value_억"] or 10.0)
        ltv_lim  = float(c["ltv_limit_pct"] or 70.0)
        bid      = c["borrower_id"]
        def_ym   = defaulted.get(bid)
        committed = float(c["committed_amount_억"] or init_val)

        # 예금/보증서: 평가 이력 단순 (최초 + 연 1회 확인)
        if ctype in ("예금", "보증서"):
            cycle = 12

        # 최초 감정 시점부터 YM_END까지 재감정 스케줄 생성
        appraisal_yms = [reg_ym]
        if cycle > 0:
            next_ym = ym_add(reg_ym, cycle)
            while next_ym <= YM_END:
                appraisal_yms.append(next_ym)
                next_ym = ym_add(next_ym, cycle)

        # 부도 기업: 처분 검토 감정 추가 (부도 3개월 전)
        if def_ym:
            pre_disposal_ym = ym_add(def_ym, -3)
            if pre_disposal_ym not in appraisal_yms and reg_ym <= pre_disposal_ym <= YM_END:
                appraisal_yms.append(pre_disposal_ym)
                appraisal_yms.sort()

        appraisers = APPRAISERS.get(app_type, ["감정평가법인"])

        prev_val = None
        curr_val = init_val

        for i, aym in enumerate(appraisal_yms):
            year = aym // 100

            # 담보 유형별 가치 변동 모델
            if ctype == "부동산":
                annual_trend = RE_TREND.get(year, 2.0)
                noise = rng.normal(0, 2.0)
                change_pct = annual_trend / 12 * (cycle if cycle > 0 else 12) + noise
                if i > 0:
                    curr_val = curr_val * (1 + change_pct / 100)

            elif ctype == "유가증권":
                if subtype in ("상장주식", "국채", "회사채", "MBS", "MMF"):
                    annual_trend = STOCK_TREND.get(year, 5.0)
                    noise = rng.normal(0, 8.0)
                    change_pct = annual_trend / 12 + noise
                    if i > 0:
                        curr_val = max(curr_val * (1 + change_pct / 100), init_val * 0.1)
                else:
                    change_pct = rng.normal(0, 3.0)
                    if i > 0:
                        curr_val = max(curr_val * (1 + change_pct / 100), init_val * 0.3)

            elif ctype == "예금":
                change_pct = 0.0  # 예금은 변동 없음

            elif ctype == "동산":
                # 기계/설비: 감가상각
                depr_rate = -8.0 if subtype == "기계/설비" else -15.0
                noise = rng.normal(0, 1.5)
                change_pct = depr_rate / 12 * (cycle if cycle > 0 else 12) + noise
                if i > 0:
                    curr_val = max(curr_val * (1 + change_pct / 100), init_val * 0.05)

            else:  # 보증서
                change_pct = 0.0

            curr_val = round(float(curr_val), 2)
            ltv_now = round(committed / curr_val * 100, 1) if curr_val > 0 else 0.0

            # 감정 사유
            if i == 0:
                reason = "최초설정"
            elif def_ym and aym == ym_add(def_ym, -3):
                reason = "부도대응"
            elif i == len(appraisal_yms) - 1 and def_ym:
                reason = "처분검토"
            else:
                reason = rng.choice(APPRAISAL_REASONS[:3])  # 정기재평가 위주

            appraisal_rows.append((
                str(uuid.uuid4()),
                cid,
                bid,
                aym,
                curr_val,
                round(float(prev_val), 2) if prev_val is not None else None,
                round((curr_val - prev_val) / prev_val * 100, 2) if prev_val and prev_val > 0 else None,
                method,
                reason,
                rng.choice(appraisers),
                app_type,
                round(ltv_now, 1),
                round(curr_val / init_val, 4),   # 기준가 대비 현재 지수
                None,
            ))
            prev_val = curr_val

    conn.executemany("""
        INSERT INTO fact_collateral_appraisal VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, appraisal_rows)
    conn.commit()
    print(f"  fact_collateral_appraisal {len(appraisal_rows):,}건 생성 완료")

    # ─────────────────────────────────────────────────────────
    # STEP 3: fact_collateral_disposal — 부도 기업 처분 이력
    # ─────────────────────────────────────────────────────────
    print("\n[STEP 3] fact_collateral_disposal — 부도 기업 담보 처분 이력")

    # 기존 테이블에 컬럼 추가
    disp_cols = {c[1] for c in conn.execute("PRAGMA table_info(fact_collateral_disposal)").fetchall()}
    add_disp = {
        "disposal_method":    "TEXT",
        "appraiser_name":     "TEXT",
        "disposal_notes":     "TEXT",
        "principal_balance_억": "REAL",
        "interest_arrears_억":  "REAL",
        "collection_gap_억":    "REAL",
    }
    for col, dtype in add_disp.items():
        if col not in disp_cols:
            conn.execute(f"ALTER TABLE fact_collateral_disposal ADD COLUMN {col} {dtype}")
    conn.commit()

    # 부도 기업 담보 목록
    def_collaterals = conn.execute("""
        SELECT d.collateral_id, d.borrower_id, d.collateral_type,
               d.appraised_value_억, d.disposal_method, d.appraiser_type,
               c.default_ym_internal
        FROM dim_collateral d
        JOIN dim_company c ON d.borrower_id = c.borrower_id
        WHERE c.default_flag = 1 AND c.default_ym_internal IS NOT NULL
    """).fetchall()

    disposal_rows = []
    DISPOSAL_METHODS = {
        "부동산":   ["임의경매", "공매", "협의매각"],
        "유가증권": ["증권사매각", "장외매각"],
        "예금":     ["즉시상계"],
        "동산":     ["공장경매", "협의매각", "공매"],
        "보증서":   ["보증이행청구"],
    }

    for dc in def_collaterals:
        def_ym   = dc["default_ym_internal"]
        disp_ym  = ym_add(def_ym, rng.integers(1, 13))  # 부도 후 1~12개월 내 처분
        init_val = float(dc["appraised_value_억"])
        ctype    = dc["collateral_type"]

        # 처분 시 감정가 (부동산: 급매할인 10~30%, 동산: 20~50% 할인)
        discount = {"부동산": 0.80, "유가증권": 0.85, "예금": 1.0, "동산": 0.65, "보증서": 1.0}
        disp_val = round(init_val * rng.uniform(discount.get(ctype, 0.7), discount.get(ctype, 0.8) + 0.1), 2)

        # 회수율
        principal = round(init_val * rng.uniform(0.6, 0.9), 2)
        interest  = round(principal * rng.uniform(0.02, 0.15), 2)
        total_debt = principal + interest
        recovery_rate = round(min(disp_val / total_debt * 100, 100), 1)
        gap = round(disp_val - total_debt, 2)

        methods = DISPOSAL_METHODS.get(ctype, ["협의매각"])
        method  = rng.choice(methods)
        appraisers_list = APPRAISERS.get(dc["appraiser_type"] or "감정평가법인", ["감정평가법인"])

        disposal_rows.append((
            dc["collateral_id"],
            dc["borrower_id"],
            disp_ym,
            disp_val,
            recovery_rate,
            method,
            rng.choice(appraisers_list),
            f"{ctype} 처분 — {method}",
            principal,
            interest,
            gap,
        ))

    conn.executemany("""
        INSERT OR REPLACE INTO fact_collateral_disposal
        (collateral_id, borrower_id, disposal_ym,
         disposal_amount_억, recovery_rate_pct,
         disposal_method, appraiser_name, disposal_notes,
         principal_balance_억, interest_arrears_억, collection_gap_억)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, disposal_rows)
    conn.commit()
    print(f"  fact_collateral_disposal {len(disposal_rows):,}건 생성 완료")

    conn.close()
    print(f"\n  총 소요: {time.time() - t0:.1f}초")
    print("=" * 65)

    # ─── 검증 출력 ────────────────────────────────────────────
    conn2 = sqlite3.connect(DB_PATH)
    conn2.row_factory = sqlite3.Row

    print("\n[검증] dim_collateral 세부 유형")
    st = conn2.execute("""
        SELECT collateral_type, collateral_subtype, COUNT(*) n,
               AVG(appraised_value_억) avg_val, AVG(ltv_limit_pct) avg_ltv
        FROM dim_collateral
        GROUP BY collateral_type, collateral_subtype
        ORDER BY collateral_type, collateral_subtype
    """).fetchall()
    print(f"  {'대분류':<8} {'소분류':<12} {'건수':>6} {'평균감정가(억)':>12} {'LTV한도':>8}")
    for r in st:
        print(f"  {r['collateral_type']:<8} {r['collateral_subtype']:<12} "
              f"{r['n']:>6,} {r['avg_val']:>12.1f} {r['avg_ltv']:>8.1f}%")

    print("\n[검증] fact_collateral_appraisal 감정 사유별")
    ar = conn2.execute("""
        SELECT appraisal_reason, COUNT(*) n, AVG(value_change_pct) avg_chg
        FROM fact_collateral_appraisal
        GROUP BY appraisal_reason ORDER BY n DESC
    """).fetchall()
    for r in ar:
        chg = r["avg_chg"] or 0
        print(f"  {r['appraisal_reason']:<12} {r['n']:>10,}건  평균변화율={chg:+.2f}%")

    print("\n[검증] 담보 가치 변동 사례 (부동산 3건)")
    samples = conn2.execute("""
        SELECT ca.collateral_id, ca.appraisal_ym, ca.appraisal_value_억,
               ca.value_change_pct, ca.appraisal_reason, ca.appraiser_name,
               d.collateral_subtype
        FROM fact_collateral_appraisal ca
        JOIN dim_collateral d ON ca.collateral_id = d.collateral_id
        WHERE d.collateral_type = '부동산'
          AND ca.appraisal_reason != '최초설정'
        ORDER BY RANDOM() LIMIT 6
    """).fetchall()
    for s in samples:
        chg = s["value_change_pct"] or 0
        print(f"  {s['collateral_id'][:8]}..  ym={s['appraisal_ym']}  "
              f"{s['collateral_subtype']:<6}  {s['appraisal_value_억']:>8.1f}억  "
              f"변화={chg:+.1f}%  [{s['appraisal_reason']}] {s['appraiser_name']}")

    print("\n[검증] 담보 처분 회수율 분포")
    dr = conn2.execute("""
        SELECT collateral_type,
               COUNT(*) n,
               ROUND(AVG(recovery_rate_pct),1) avg_rr,
               ROUND(MIN(recovery_rate_pct),1) min_rr,
               ROUND(MAX(recovery_rate_pct),1) max_rr,
               ROUND(SUM(collection_gap_억),1) total_gap
        FROM fact_collateral_disposal
        GROUP BY collateral_type ORDER BY n DESC
    """).fetchall()
    print(f"  {'담보유형':<8} {'건수':>6} {'평균회수율':>10} {'최저':>8} {'최고':>8} {'손실합계(억)':>12}")
    for r in dr:
        print(f"  {r['collateral_type']:<8} {r['n']:>6,} {r['avg_rr']:>10.1f}% "
              f"{r['min_rr']:>8.1f}% {r['max_rr']:>8.1f}% {r['total_gap']:>12.1f}")

    conn2.close()


if __name__ == "__main__":
    main()
