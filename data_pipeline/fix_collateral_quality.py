#!/usr/bin/env python3
"""
fix_collateral_quality.py — dim_collateral 데이터 품질 전체 수정

발견된 오류:
  1. 예금담보 서브타입 오류 — 동산 서브타입(선박/자동차 등)으로 잘못 배정
     원인: add_collateral_history.py에서 COLLATERAL_SUBTYPES 키가 '예금'인데
           DB 값은 '예금담보'여서 매칭 실패 → 동산으로 fallback
  2. collateral_description 불일치 — 모든 유형에 무작위 할당
     (부동산>아파트에 '서버장비', 동산>선박에 '공장건물' 등)
  3. collateral_address 잘못 부여 — 동산/보증서/예금담보에 부동산 형태 주소
  4. 유가증권 담보 0건 — 19종 설계 대비 누락, 신규 추가

수정 후 기대값:
  - 예금담보 서브타입: 정기예금/정기적금/MMF/외화예금
  - collateral_description: 유형·서브타입에 적합한 설명
  - collateral_address: 부동산=소재지, 동산=보관장소(기업주소), 보증서/예금담보=NULL
  - 유가증권: ~12,000건 신규 추가 + fact_collateral_appraisal 이력 생성
"""
import sqlite3
import time
import uuid
from pathlib import Path
import numpy as np

DB_PATH = Path("ews_corporate_v21.db")
SEED = 99

rng = np.random.default_rng(SEED)

# ─────────────────────────────────────────────────────────────────
# 매핑 테이블
# ─────────────────────────────────────────────────────────────────

# 유형+서브타입별 올바른 description 후보
DESC_MAP = {
    ("부동산", "아파트"):   ["아파트 및 부속토지", "아파트 및 대지"],
    ("부동산", "건물"):     ["업무용 건물 및 토지", "상업용 건물 및 부속토지", "건물 및 부속토지"],
    ("부동산", "공장"):     ["공장건물 및 부속토지", "공장 및 부지", "제조공장 및 부지"],
    ("부동산", "상가"):     ["상가 및 대지", "근린상가 및 토지", "상업용 건물 및 토지"],
    ("부동산", "오피스텔"): ["오피스텔 및 부속토지", "오피스텔"],
    ("부동산", "토지"):     ["나대지", "공장부지", "상업지", "임야 및 토지"],

    ("동산", "기계/설비"):  ["생산설비 및 기계장치", "제조설비 일체", "자동화 생산설비"],
    ("동산", "선박"):       ["화물선", "어선", "해상운반선"],
    ("동산", "자동차"):     ["화물차량", "특수차량", "화물트럭"],
    ("동산", "재고자산"):   ["원자재 및 제품재고", "완제품 재고", "상품재고"],

    ("보증서", "은행보증서"):   ["지급보증서", "이행보증서"],
    ("보증서", "신용보증기금"): ["신용보증서"],
    ("보증서", "기술보증기금"): ["기술보증서"],
    ("보증서", "보험증권"):     ["이행보증보험증권", "계약이행보증보험"],

    ("예금담보", "정기예금"):  ["정기예금증서", "거치식 정기예금"],
    ("예금담보", "정기적금"):  ["정기적금증서", "월복리 정기적금"],
    ("예금담보", "MMF"):       ["MMF 수익증권"],
    ("예금담보", "외화예금"):  ["외화정기예금", "USD 외화예금"],

    ("유가증권", "상장주식"):   ["상장 보통주", "코스피 상장주식"],
    ("유가증권", "비상장주식"): ["비상장주식", "비상장 보통주"],
    ("유가증권", "국채"):       ["국고채", "국채증권"],
    ("유가증권", "회사채"):     ["회사채증권", "무보증 회사채"],
    ("유가증권", "MBS"):        ["MBS 수익증권", "주택저당증권"],
}

# 예금담보 서브타입 수정 매핑 (구 → 신)
DEPOSIT_SUBTYPE_FIX = {
    "기계/설비": "정기예금",
    "선박":      "정기적금",
    "자동차":    "MMF",
    "재고자산":  "외화예금",
}

# 예금담보 수정 후 method/cycle/disposal/appraiser
DEPOSIT_METHOD_FIX = {
    "정기예금": ("액면가",        0,  "즉시상계",  "은행자체"),
    "정기적금": ("액면가",        0,  "즉시상계",  "은행자체"),
    "MMF":      ("시가평가",      1,  "즉시환매",  "은행자체"),
    "외화예금": ("액면가(환산)",  1,  "즉시상계",  "은행자체"),
}

# 유가증권 서브타입 풀
EQ_SUBTYPES = [
    ("상장주식",   "시가평가",    1,  "증권사매각", "증권사",    (50, 70)),
    ("비상장주식", "DCF/순자산", 12, "장외매각",   "회계법인",  (40, 60)),
    ("국채",       "시가평가",    1,  "증권사매각", "증권사",    (70, 80)),
    ("회사채",     "시가평가",    1,  "증권사매각", "증권사",    (60, 75)),
    ("MBS",        "시가평가",    3,  "증권사매각", "증권사",    (60, 75)),
]

# 감정평가인 풀
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

# 주식시장 변동률 (유가증권 감정이력용)
STOCK_TREND = {
    2017: +21.8, 2018: -17.3, 2019: +7.7, 2020: +30.8, 2021: +3.6,
    2022: -24.9, 2023: +18.7, 2024: +9.2, 2025: +5.4,
}


def pick_desc(ctype, subtype):
    key = (ctype, subtype)
    cands = DESC_MAP.get(key, [f"{subtype}"])
    return cands[rng.integers(0, len(cands))]


def pick_appraiser(appraiser_type):
    pool = APPRAISERS.get(appraiser_type, ["감정원"])
    return pool[rng.integers(0, len(pool))]


def ym_add(ym, months):
    y, m = divmod(ym, 100)
    m += months
    while m > 12:
        m -= 12; y += 1
    return y * 100 + m


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    t0 = time.time()

    print("=" * 65)
    print("  dim_collateral 데이터 품질 전체 수정")
    print("=" * 65)

    # ─────────────────────────────────────────────────────────
    # STEP 1: 예금담보 서브타입 + 관련 필드 수정
    # ─────────────────────────────────────────────────────────
    print("\n[STEP 1] 예금담보 서브타입 및 method 수정")

    deposit_rows = conn.execute(
        "SELECT collateral_id, collateral_subtype FROM dim_collateral WHERE collateral_type='예금담보'"
    ).fetchall()

    dep_updates = []
    for r in deposit_rows:
        old_sub = r["collateral_subtype"]
        new_sub = DEPOSIT_SUBTYPE_FIX.get(old_sub, "정기예금")
        method, cycle, disposal, appraiser_type = DEPOSIT_METHOD_FIX[new_sub]
        dep_updates.append((new_sub, method, cycle, disposal, appraiser_type, 95.0,
                            r["collateral_id"]))

    conn.executemany("""
        UPDATE dim_collateral
        SET collateral_subtype=?, appraisal_method=?, appraisal_cycle_months=?,
            disposal_method=?, appraiser_type=?, ltv_limit_pct=?
        WHERE collateral_id=?
    """, dep_updates)
    conn.commit()
    print(f"  예금담보 {len(dep_updates):,}건 서브타입 수정 완료")

    # 수정 후 분포 확인
    rows = conn.execute(
        "SELECT collateral_subtype, COUNT(*) FROM dim_collateral WHERE collateral_type='예금담보'"
        " GROUP BY 1"
    ).fetchall()
    for r in rows:
        print(f"    예금담보 > {r[0]}: {r[1]}건")

    # ─────────────────────────────────────────────────────────
    # STEP 2: collateral_description 전 유형 수정
    # ─────────────────────────────────────────────────────────
    print("\n[STEP 2] collateral_description 전 유형 수정")

    all_cols = conn.execute(
        "SELECT collateral_id, collateral_type, collateral_subtype FROM dim_collateral"
    ).fetchall()

    desc_updates = []
    for r in all_cols:
        desc = pick_desc(r["collateral_type"], r["collateral_subtype"])
        desc_updates.append((desc, r["collateral_id"]))

    conn.executemany(
        "UPDATE dim_collateral SET collateral_description=? WHERE collateral_id=?",
        desc_updates
    )
    conn.commit()
    print(f"  collateral_description {len(desc_updates):,}건 수정 완료")

    # ─────────────────────────────────────────────────────────
    # STEP 3: collateral_address 수정
    #   부동산 → 현재 주소 유지
    #   동산   → 기업 본사 주소 (보관장소)
    #   보증서 → 발급기관명 (주소 아님)
    #   예금담보 → NULL
    # ─────────────────────────────────────────────────────────
    print("\n[STEP 3] collateral_address 유형별 수정")

    # 기업 주소 매핑
    company_addr = {
        r[0]: r[1]
        for r in conn.execute("SELECT borrower_id, address FROM dim_company").fetchall()
    }

    # 동산 → 기업주소
    mov_rows = conn.execute(
        "SELECT collateral_id, borrower_id FROM dim_collateral WHERE collateral_type='동산'"
    ).fetchall()
    mov_updates = [(company_addr.get(r["borrower_id"], ""), r["collateral_id"]) for r in mov_rows]
    conn.executemany(
        "UPDATE dim_collateral SET collateral_address=? WHERE collateral_id=?", mov_updates
    )

    # 보증서 → 발급기관 주소 형태
    ISSUER_ADDR = {
        "은행보증서":   "IM뱅크 본점 (대구 중구 달구벌대로 2310)",
        "신용보증기금": "신용보증기금 대구본부 (대구 동구 동대구로 489)",
        "기술보증기금": "기술보증기금 대구지역본부 (대구 북구 침산로 305)",
        "보험증권":     "서울보증보험 대구지점 (대구 중구 공평로 88)",
    }
    gur_rows = conn.execute(
        "SELECT collateral_id, collateral_subtype FROM dim_collateral WHERE collateral_type='보증서'"
    ).fetchall()
    gur_updates = [
        (ISSUER_ADDR.get(r["collateral_subtype"], ""), r["collateral_id"])
        for r in gur_rows
    ]
    conn.executemany(
        "UPDATE dim_collateral SET collateral_address=? WHERE collateral_id=?", gur_updates
    )

    # 예금담보 → NULL
    conn.execute(
        "UPDATE dim_collateral SET collateral_address=NULL WHERE collateral_type='예금담보'"
    )

    conn.commit()
    print(f"  동산 {len(mov_updates):,}건 → 기업주소")
    print(f"  보증서 {len(gur_updates):,}건 → 발급기관명")
    print(f"  예금담보 → NULL")

    # ─────────────────────────────────────────────────────────
    # STEP 4: 유가증권 담보 신규 추가 (~12,000건)
    # ─────────────────────────────────────────────────────────
    print("\n[STEP 4] 유가증권 담보 신규 추가")

    # 담보 ≤2건 보유 차주 중 유가증권 적합 업종 우선
    # (K05 IT, K06 금융보험, K02 건설, K03 도소매 순 가중치)
    borrow_col_cnt = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT borrower_id, COUNT(*) FROM dim_collateral GROUP BY borrower_id"
        ).fetchall()
    }
    # 모든 차주 (담보 없는 차주 포함)
    all_companies = conn.execute(
        "SELECT borrower_id, industry_cd, address, established_year FROM dim_company"
    ).fetchall()

    candidates = [c for c in all_companies if borrow_col_cnt.get(c["borrower_id"], 0) <= 2]

    # 업종 가중치 (유가증권 담보 설정 확률)
    IND_WEIGHT = {
        "K06": 0.35, "K05": 0.28, "K03": 0.22, "K02": 0.20, "K01A": 0.16,
        "K01B": 0.14, "K04": 0.12, "K07": 0.18, "K08": 0.10, "K10": 0.10,
        "K11": 0.08, "K12": 0.08, "K13": 0.14, "K09": 0.08, "K00": 0.06,
    }

    TARGET_EQ = 11_800
    eq_borrowers = []
    for c in candidates:
        prob = IND_WEIGHT.get(c["industry_cd"], 0.10)
        if rng.random() < prob:
            eq_borrowers.append(c)
        if len(eq_borrowers) >= TARGET_EQ:
            break

    print(f"  유가증권 담보 부여 대상: {len(eq_borrowers):,}개 차주")

    # 기존 collateral_id 전체 집합 (중복 방지)
    existing_col_ids = {
        r[0] for r in conn.execute("SELECT collateral_id FROM dim_collateral").fetchall()
    }
    # 차주별 최대 번호 추적 (동적 업데이트)
    bid_max_num = {}
    for col_id in existing_col_ids:
        parts = col_id.rsplit("_C", 1)
        if len(parts) == 2 and parts[1].isdigit():
            bid_max_num[parts[0]] = max(bid_max_num.get(parts[0], 0), int(parts[1]))

    # 유가증권 담보 레코드 생성
    eq_collaterals = []
    eq_appraisals = []

    for c in eq_borrowers:
        bid = c["borrower_id"]
        est_year = c["established_year"] or 2017
        reg_ym = max(201701, min(202412, est_year * 100 + int(rng.integers(1, 13))))

        # 서브타입 선택
        sub_idx = rng.integers(0, len(EQ_SUBTYPES))
        subtype_name, method, cycle, disposal, appraiser_type, ltv_range = EQ_SUBTYPES[sub_idx]

        appraised = round(float(rng.uniform(1.0, 50.0)), 1)
        ltv = round(float(rng.uniform(*ltv_range)), 1)
        secured = round(appraised * rng.uniform(1.1, 1.3), 1)
        pledge = int(rng.choice([1, 2], p=[0.80, 0.20]))

        # 중복 없는 collateral_id 생성
        col_num = bid_max_num.get(bid, 0) + 1
        col_id = f"{bid}_C{col_num}"
        while col_id in existing_col_ids:
            col_num += 1
            col_id = f"{bid}_C{col_num}"
        bid_max_num[bid] = col_num
        existing_col_ids.add(col_id)

        desc = pick_desc("유가증권", subtype_name)

        eq_collaterals.append((
            col_id, bid, "유가증권", appraised, reg_ym, "정상",
            desc, None,  # collateral_address = NULL
            subtype_name, method, cycle, disposal, appraiser_type, ltv, pledge, secured,
        ))

        # 감정이력 생성
        years_active = list(range(max(2017, reg_ym // 100), 2026))
        prev_val = None
        init_index = 1.0

        for i, yr in enumerate(years_active):
            trend = STOCK_TREND.get(yr, 0.0)
            if i == 0:
                val = appraised
                market_idx = 1.0
                reason = "최초설정"
            else:
                # 주식/채권: 시장변동 + 개별변동
                mkt_chg = trend / 100.0
                idio = rng.normal(0, 0.04)
                delta = mkt_chg + idio
                val = round(max(0.1, prev_val * (1 + delta)), 2)
                market_idx = round(init_index * (1 + trend / 100.0), 3)
                if i == len(years_active) - 1 and rng.random() < 0.3:
                    reason = "정기재평가"
                elif rng.random() < 0.2:
                    reason = "담보가치급변"
                else:
                    reason = "정기재평가"
                init_index = market_idx

            appraisal_ym = yr * 100 + int(rng.integers(1, 4))  # 연초 (1~3월)
            change_pct = round((val - prev_val) / prev_val * 100, 2) if prev_val else None
            appraiser = pick_appraiser(appraiser_type)
            ltv_now = round(secured / val * 100, 1) if val > 0 else None

            eq_appraisals.append((
                str(uuid.uuid4()), col_id, bid, appraisal_ym,
                val, prev_val, change_pct,
                method, reason, appraiser, appraiser_type,
                ltv_now, market_idx, None
            ))
            prev_val = val

    # INSERT dim_collateral
    conn.executemany("""
        INSERT INTO dim_collateral
          (collateral_id, borrower_id, collateral_type, appraised_value_억,
           registration_ym, legal_status, collateral_description, collateral_address,
           collateral_subtype, appraisal_method, appraisal_cycle_months,
           disposal_method, appraiser_type, ltv_limit_pct, pledge_rank, secured_amount_억)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, eq_collaterals)
    conn.commit()
    print(f"  유가증권 dim_collateral {len(eq_collaterals):,}건 추가")

    # INSERT fact_collateral_appraisal (유가증권 이력만 추가 — 기존 데이터 유지)
    conn.executemany("""
        INSERT OR IGNORE INTO fact_collateral_appraisal
          (appraisal_id, collateral_id, borrower_id, appraisal_ym,
           appraisal_value_억, prev_appraisal_value_억, value_change_pct,
           appraisal_method, appraisal_reason, appraiser_name, appraiser_type,
           ltv_at_appraisal, market_index_ref, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, eq_appraisals)
    conn.commit()
    print(f"  유가증권 fact_collateral_appraisal {len(eq_appraisals):,}건 추가")

    # ─────────────────────────────────────────────────────────
    # 검증 요약
    # ─────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  수정 후 검증")
    print("=" * 65)

    rows = conn.execute(
        "SELECT collateral_type, COUNT(*) FROM dim_collateral GROUP BY 1 ORDER BY 1"
    ).fetchall()
    total = sum(r[1] for r in rows)
    print(f"\n담보 유형별 건수 (전체 {total:,}건):")
    for r in rows:
        print(f"  {r[0]:10}: {r[1]:,}건")

    rows2 = conn.execute(
        "SELECT collateral_type, collateral_subtype, COUNT(*) FROM dim_collateral"
        " GROUP BY 1,2 ORDER BY 1,2"
    ).fetchall()
    print(f"\n서브타입별 분포:")
    for r in rows2:
        print(f"  {r[0]:10} > {r[1]:15}: {r[2]:,}건")

    print(f"\nfact_collateral_appraisal 전체: "
          f"{conn.execute('SELECT COUNT(*) FROM fact_collateral_appraisal').fetchone()[0]:,}건")

    # 샘플: 예금담보 수정 확인
    sample_dep = conn.execute(
        "SELECT collateral_id, collateral_subtype, collateral_description,"
        " appraisal_method, ltv_limit_pct, collateral_address"
        " FROM dim_collateral WHERE collateral_type='예금담보' LIMIT 5"
    ).fetchall()
    print("\n예금담보 수정 샘플:")
    for r in sample_dep:
        print(f"  {r[0]} | {r[1]} | {r[2]} | 방법={r[3]} | LTV={r[4]} | 주소={r[5]}")

    # 샘플: 유가증권 확인
    sample_eq = conn.execute(
        "SELECT d.collateral_id, d.collateral_subtype, d.collateral_description,"
        " d.appraised_value_억, d.secured_amount_억, c.company_name, c.industry_cd"
        " FROM dim_collateral d JOIN dim_company c ON d.borrower_id=c.borrower_id"
        " WHERE d.collateral_type='유가증권' LIMIT 5"
    ).fetchall()
    print("\n유가증권 신규 샘플:")
    for r in sample_eq:
        print(f"  {r[0]} | {r[1]} | {r[2]} | 감정가={r[3]}억 | {r[5]}({r[6]})")

    elapsed = round(time.time() - t0, 1)
    print(f"\n완료: {elapsed}초")
    conn.close()


if __name__ == "__main__":
    main()
