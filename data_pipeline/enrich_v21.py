#!/usr/bin/env python3
"""
enrich_v21.py — v21 DB 현실화 보강 스크립트

빌드 완료 후 실행:
  python3 enrich_v21.py

추가/변경 내용:
  1. dim_company      — company_name, ceo_name, business_registration_no,
                        address, phone, established_year
  2. fact_governance_change — new_ceo_name, outgoing_ceo_name, change_reason
  3. fact_legal_risk  — lawsuit_type, plaintiff_type, case_court
  4. fact_supply_chain — key_customer_name, key_supplier_name, disruption_reason
  5. dim_facility     — facility_purpose
  6. dim_collateral   — collateral_description, collateral_address
"""
import sqlite3
import time
from pathlib import Path

import numpy as np

DB_PATH = Path("ews_corporate_v21.db")
SEED = 42

# ──────────────────────────────────────────────────────────────────────────────
# 지역별 시/구/동 매핑
# ──────────────────────────────────────────────────────────────────────────────
REGION_CITIES = {
    "R01": ("서울", ["강남구", "강동구", "마포구", "종로구", "영등포구", "서초구", "송파구"]),
    "R02": ("부산", ["해운대구", "사하구", "사상구", "금정구", "동래구", "부산진구"]),
    "R03": ("대구", ["달서구", "북구", "수성구", "중구", "달성군", "동구"]),
    "R04": ("인천", ["남동구", "서구", "연수구", "부평구", "계양구", "미추홀구"]),
    "R05": ("광주", ["남구", "북구", "광산구", "서구", "동구"]),
    "R06": ("대전", ["유성구", "서구", "중구", "동구", "대덕구"]),
    "R07": ("울산", ["남구", "북구", "동구", "중구", "울주군"]),
    "R08": ("경기", ["수원시", "성남시", "고양시", "용인시", "화성시", "안양시", "평택시"]),
}

# 업종별 도로명 패턴
INDUSTRY_ROAD = {
    "K00": ["농업로", "산업단지로", "영농길"],
    "K01A": ["공단로", "산업로", "공업단지길", "제조단지로"],
    "K01B": ["첨단산업로", "테크노파크로", "혁신로", "R&D단지길"],
    "K02": ["건설로", "시공로", "현장길", "개발대로"],
    "K03": ["유통단지로", "물류센터로", "상업로", "시장대로"],
    "K04": ["금융로", "중앙대로", "은행로", "증권로"],
    "K05": ["IT밸리로", "테크로", "정보통신로", "디지털로"],
    "K06": ["에너지로", "발전로", "산업단지로"],
    "K07A": ["중공업로", "조선단지로", "산업로"],
    "K07B": ["자동차로", "부품단지로", "모빌리티로"],
    "K08": ["관광로", "리조트로", "해변길", "호텔대로"],
    "K09": ["의료로", "병원길", "바이오로", "헬스케어로"],
    "K10": ["화학단지로", "석유화학로", "정밀화학길"],
    "K11": ["부동산로", "개발대로", "단지길"],
    "K12": ["서비스로", "비즈니스로", "상업대로"],
    "K13": ["에코로", "신재생에너지로", "그린에너지길"],
}

# 업종별 기업명 요소
INDUSTRY_NAME_PARTS = {
    "K00": {
        "prefix": ["강원", "충북", "전남", "경북", "경남", "제주", "전북"],
        "middle": ["", "종합", "친환경", "유기", ""],
        "suffix": ["농업", "축산", "식품", "원예", "영농조합", "농산"],
    },
    "K01A": {
        "prefix": ["동방", "대한", "한국", "태평양", "국제", "영남", "금호"],
        "middle": ["", "정밀", "종합", "특수", ""],
        "suffix": ["기계", "공업", "제조", "산업", "철강", "금속", "소재"],
    },
    "K01B": {
        "prefix": ["첨단", "미래", "혁신", "스마트", "넥스트", "하이"],
        "middle": ["", "테크", "나노", ""],
        "suffix": ["소재", "반도체", "전자", "디스플레이", "첨단소재", "광학"],
    },
    "K02": {
        "prefix": ["대림", "동아", "남광", "성원", "신세계", "경호", "한양"],
        "middle": ["", "종합", ""],
        "suffix": ["건설", "토건", "개발", "엔지니어링", "주택", "건축"],
    },
    "K03": {
        "prefix": ["동서", "한일", "글로벌", "대성", "평화", "한국"],
        "middle": ["", "종합", ""],
        "suffix": ["유통", "물류", "상사", "무역", "마트", "도매"],
    },
    "K04": {
        "prefix": ["하나", "신한", "우리", "국민", "IBK", "대구", "경북"],
        "middle": ["", "파이낸스", ""],
        "suffix": ["금융", "투자", "증권", "보험", "캐피탈", "저축은행"],
    },
    "K05": {
        "prefix": ["카카오", "네이버", "라인", "코스콤", "케이", "디지털"],
        "middle": ["", "테크", "소프트", ""],
        "suffix": ["IT", "소프트웨어", "시스템", "데이터", "솔루션", "플랫폼"],
    },
    "K06": {
        "prefix": ["한전", "GS", "SK", "지역", "한화", "동서"],
        "middle": ["", "에너지", ""],
        "suffix": ["에너지", "전력", "가스", "열공급", "발전"],
    },
    "K07A": {
        "prefix": ["현대", "삼성", "대우", "한진", "STX", "성동"],
        "middle": ["", "중공업", ""],
        "suffix": ["중공업", "조선", "기계", "플랜트", "해양"],
    },
    "K07B": {
        "prefix": ["현대", "기아", "르노", "쌍용", "한국", "영진"],
        "middle": ["", "자동차", ""],
        "suffix": ["자동차", "부품", "모빌리티", "운송기기", "오토"],
    },
    "K08": {
        "prefix": ["대한", "아시아나", "롯데", "하나", "모두", "대명"],
        "middle": ["", ""],
        "suffix": ["관광", "호텔", "리조트", "여행사", "레저"],
    },
    "K09": {
        "prefix": ["서울", "연세", "성모", "보건", "한양", "경북"],
        "middle": ["", "의료", ""],
        "suffix": ["의료", "병원", "제약", "바이오", "헬스케어", "메디컬"],
    },
    "K10": {
        "prefix": ["대우", "포스코", "현대", "삼성", "한화", "롯데"],
        "middle": ["", "정밀", "석유"],
        "suffix": ["화학", "정밀화학", "석유화학", "페인트", "소재"],
    },
    "K11": {
        "prefix": ["GS", "현대", "대우", "두산", "호반", "태영"],
        "middle": ["", "산업", ""],
        "suffix": ["부동산", "임대", "개발", "리츠", "자산관리", "건설"],
    },
    "K12": {
        "prefix": ["신세계", "현대", "롯데", "이랜드", "한국", "대성"],
        "middle": ["", ""],
        "suffix": ["서비스", "컨설팅", "광고", "미디어", "커뮤니케이션"],
    },
    "K13": {
        "prefix": ["한국", "태양광", "풍력", "그린", "에코", "클린"],
        "middle": ["", "에너지", ""],
        "suffix": ["환경", "에코", "그린에너지", "재생에너지", "태양광"],
    },
}

CORP_TYPES = ["(주)", "(주)", "(주)", "(유)", "주식회사", ""]  # (주) 비중 높게

KOREAN_SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
                   "한", "오", "서", "신", "권", "황", "안", "송", "류", "홍"]
KOREAN_GIVEN = ["성호", "민준", "영수", "재원", "동현", "성훈", "지훈", "준혁",
                "승현", "태양", "수진", "지영", "민지", "혜원", "지현", "은정",
                "수현", "상훈", "성민", "태호", "종수", "재환", "경호", "명수"]

CEO_CHANGE_REASONS = ["임기만료", "임기만료", "사임", "선임", "경영승계", "사망", "합의퇴임"]
LAWSUIT_TYPES = ["어음부도", "매매대금", "임금체불", "손해배상", "채무불이행", "약정위반", "부당이득반환"]
PLAINTIFF_TYPES = ["금융기관", "거래처", "임직원", "세무서", "주주", "하도급업체"]
COURTS = {
    "R01": "서울중앙지법",
    "R02": "부산지법",
    "R03": "대구지법",
    "R04": "인천지법",
    "R05": "광주지법",
    "R06": "대전지법",
    "R07": "울산지법",
    "R08": "수원지법",
}
KEY_CUSTOMERS = {
    "K01A": ["현대자동차(주)", "삼성전자(주)", "POSCO(주)", "LG전자(주)", "SK하이닉스"],
    "K01B": ["삼성전자(주)", "SK하이닉스(주)", "LG디스플레이", "삼성SDI", "현대모비스"],
    "K02": ["한국도로공사", "한국토지주택공사", "서울시", "국방부", "한국수자원공사"],
    "K03": ["이마트(주)", "롯데쇼핑(주)", "홈플러스(주)", "쿠팡(주)", "GS리테일"],
    "K07A": ["현대오일뱅크", "한국전력공사", "삼성중공업", "대우조선해양"],
    "K07B": ["현대자동차(주)", "기아(주)", "GM코리아", "르노코리아자동차"],
    "K10": ["롯데케미칼(주)", "LG화학(주)", "SK이노베이션", "한화솔루션"],
}
KEY_SUPPLIERS = {
    "K01A": ["POSCO(주)", "현대제철(주)", "동국제강(주)", "세아베스틸"],
    "K01B": ["삼성전자(주)", "SK하이닉스(주)", "LG이노텍", "일본공작기계"],
    "K07A": ["POSCO(주)", "현대제철(주)", "두산중공업", "한국조선해양"],
    "K07B": ["현대모비스(주)", "만도(주)", "한온시스템", "HL만도"],
    "K10": ["한국석유공사", "GS칼텍스", "SK에너지", "에쓰오일"],
}
DISRUPTION_REASONS = ["원자재가격급등", "운송차질", "거래처부도", "수입제한", "환율급등", "수급불안"]
FACILITY_PURPOSES = ["운전자금", "운전자금", "시설자금", "무역금융", "기업어음", "구매자금", "수출금융"]
COLLATERAL_TYPES_BY_INDUSTRY = {
    "K01A": "공장건물 및 부속토지",
    "K01B": "연구시설 및 설비",
    "K02": "건설장비 및 현장자산",
    "K03": "물류창고 및 토지",
    "K04": "금융자산 및 유가증권",
    "K05": "서버장비 및 소프트웨어",
    "K06": "발전설비 및 토지",
    "K07A": "생산설비 및 공장",
    "K07B": "자동차부품 생산설비",
    "K08": "호텔건물 및 토지",
    "K09": "의료기기 및 건물",
    "K10": "화학공장 및 설비",
    "K11": "토지 및 건물",
    "K12": "영업권 및 인테리어",
    "K13": "태양광패널 및 풍력터빈",
}


def gen_company_name(industry_cd, rng):
    parts = INDUSTRY_NAME_PARTS.get(industry_cd, INDUSTRY_NAME_PARTS["K12"])
    prefix = rng.choice(parts["prefix"])
    middle = rng.choice(parts["middle"])
    suffix = rng.choice(parts["suffix"])
    corp = rng.choice(CORP_TYPES)
    name = f"{prefix}{middle}{suffix}"
    if corp == "주식회사":
        return f"주식회사 {name}"
    return f"{name}{corp}" if corp else name


def gen_ceo_name(rng):
    return rng.choice(KOREAN_SURNAMES) + rng.choice(KOREAN_GIVEN)


def gen_brn(rng):
    head = rng.integers(101, 999)
    mid = rng.integers(10, 99)
    tail = rng.integers(10000, 99999)
    return f"{head:03d}-{mid:02d}-{tail:05d}"


def gen_address(region_cd, industry_cd, rng):
    city, districts = REGION_CITIES.get(region_cd, ("경기", ["시흥시", "안산시"]))
    district = rng.choice(districts)
    roads = INDUSTRY_ROAD.get(industry_cd, ["산업로"])
    road = rng.choice(roads)
    num = rng.integers(1, 999)
    return f"{city} {district} {road} {num}"


def gen_phone(region_cd, rng):
    area_codes = {
        "R01": "02", "R02": "051", "R03": "053", "R04": "032",
        "R05": "062", "R06": "042", "R07": "052", "R08": "031",
    }
    area = area_codes.get(region_cd, "02")
    mid = rng.integers(1000, 9999)
    last = rng.integers(1000, 9999)
    return f"{area}-{mid}-{last}"


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────
def main():
    rng = np.random.default_rng(SEED)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    t0 = time.time()

    print("=" * 60)
    print("  v21 DB 현실화 보강 (enrich_v21.py)")
    print("=" * 60)

    # ── 1. dim_company 컬럼 추가 ────────────────────────────────────────────
    print("\n[1] dim_company 컬럼 추가 및 현실적 데이터 입력")
    existing_cols = {c[1] for c in conn.execute("PRAGMA table_info(dim_company)").fetchall()}
    new_cols = {
        "company_name":            "TEXT",
        "ceo_name":                "TEXT",
        "business_registration_no":"TEXT",
        "address":                 "TEXT",
        "phone":                   "TEXT",
        "established_year":        "INTEGER",
    }
    for col, dtype in new_cols.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE dim_company ADD COLUMN {col} {dtype}")
    conn.commit()

    companies = conn.execute(
        "SELECT borrower_id, industry_cd, region_cd, entry_ym FROM dim_company"
    ).fetchall()

    updates = []
    for co in companies:
        ind = co["industry_cd"] or "K12"
        reg = co["region_cd"] or "R01"
        entry_ym = co["entry_ym"] or 201701
        est_year = entry_ym // 100 - rng.integers(0, 20)
        updates.append((
            gen_company_name(ind, rng),
            gen_ceo_name(rng),
            gen_brn(rng),
            gen_address(reg, ind, rng),
            gen_phone(reg, rng),
            int(est_year),
            co["borrower_id"],
        ))

    conn.executemany("""
        UPDATE dim_company SET
          company_name=?, ceo_name=?, business_registration_no=?,
          address=?, phone=?, established_year=?
        WHERE borrower_id=?
    """, updates)
    conn.commit()
    print(f"  dim_company {len(updates):,}개 기업 현실화 완료")

    # ── 2. fact_governance_change 컬럼 추가 ──────────────────────────────────
    print("\n[2] fact_governance_change 컬럼 추가")
    try:
        gov_cols = {c[1] for c in conn.execute("PRAGMA table_info(fact_governance_change)").fetchall()}
        gov_new = {"new_ceo_name": "TEXT", "outgoing_ceo_name": "TEXT", "change_reason": "TEXT"}
        for col, dtype in gov_new.items():
            if col not in gov_cols:
                conn.execute(f"ALTER TABLE fact_governance_change ADD COLUMN {col} {dtype}")
        conn.commit()

        # ceo_change_flag=1인 행에만 이름 입력
        ceo_changes = conn.execute(
            "SELECT rowid, borrower_id, ym FROM fact_governance_change WHERE ceo_change_flag=1"
        ).fetchall()
        gov_updates = []
        for r in ceo_changes:
            gov_updates.append((
                gen_ceo_name(rng),          # new_ceo_name
                gen_ceo_name(rng),          # outgoing_ceo_name
                rng.choice(CEO_CHANGE_REASONS),
                r["rowid"],
            ))
        conn.executemany(
            "UPDATE fact_governance_change SET new_ceo_name=?, outgoing_ceo_name=?, change_reason=? WHERE rowid=?",
            gov_updates,
        )
        conn.commit()
        print(f"  fact_governance_change CEO변경 {len(gov_updates):,}건 이름 입력")
    except Exception as e:
        print(f"  fact_governance_change 처리 중 오류: {e}")

    # ── 3. fact_legal_risk 컬럼 추가 ─────────────────────────────────────────
    print("\n[3] fact_legal_risk 컬럼 추가")
    try:
        leg_cols = {c[1] for c in conn.execute("PRAGMA table_info(fact_legal_risk)").fetchall()}
        leg_new = {"lawsuit_type": "TEXT", "plaintiff_type": "TEXT", "case_court": "TEXT"}
        for col, dtype in leg_new.items():
            if col not in leg_cols:
                conn.execute(f"ALTER TABLE fact_legal_risk ADD COLUMN {col} {dtype}")
        conn.commit()

        # lawsuit_count_12m > 0 인 행에만 입력
        lawsuits = conn.execute("""
            SELECT f.rowid, f.borrower_id, c.region_cd
            FROM fact_legal_risk f
            JOIN dim_company c ON f.borrower_id = c.borrower_id
            WHERE f.lawsuit_count_12m > 0
        """).fetchall()
        leg_updates = []
        for r in lawsuits:
            reg = r["region_cd"] or "R01"
            leg_updates.append((
                rng.choice(LAWSUIT_TYPES),
                rng.choice(PLAINTIFF_TYPES),
                COURTS.get(reg, "서울중앙지법"),
                r["rowid"],
            ))
        conn.executemany(
            "UPDATE fact_legal_risk SET lawsuit_type=?, plaintiff_type=?, case_court=? WHERE rowid=?",
            leg_updates,
        )
        conn.commit()
        print(f"  fact_legal_risk 소송 {len(leg_updates):,}건 현실화")
    except Exception as e:
        print(f"  fact_legal_risk 처리 중 오류: {e}")

    # ── 4. fact_supply_chain 컬럼 추가 ───────────────────────────────────────
    print("\n[4] fact_supply_chain 컬럼 추가")
    try:
        sc_cols = {c[1] for c in conn.execute("PRAGMA table_info(fact_supply_chain)").fetchall()}
        sc_new = {
            "key_customer_name": "TEXT",
            "key_supplier_name": "TEXT",
            "disruption_reason": "TEXT",
        }
        for col, dtype in sc_new.items():
            if col not in sc_cols:
                conn.execute(f"ALTER TABLE fact_supply_chain ADD COLUMN {col} {dtype}")
        conn.commit()

        # supply_chain_disruption_score > 0.4 인 행
        disruptions = conn.execute("""
            SELECT f.rowid, c.industry_cd
            FROM fact_supply_chain f
            JOIN dim_company c ON f.borrower_id = c.borrower_id
            WHERE f.supply_chain_disruption_score > 0.4
        """).fetchall()
        sc_updates = []
        for r in disruptions:
            ind = r["industry_cd"] or "K01A"
            customers = KEY_CUSTOMERS.get(ind, ["현대자동차(주)", "삼성전자(주)"])
            suppliers = KEY_SUPPLIERS.get(ind, ["POSCO(주)", "현대제철(주)"])
            sc_updates.append((
                rng.choice(customers),
                rng.choice(suppliers),
                rng.choice(DISRUPTION_REASONS),
                r["rowid"],
            ))
        conn.executemany(
            "UPDATE fact_supply_chain SET key_customer_name=?, key_supplier_name=?, disruption_reason=? WHERE rowid=?",
            sc_updates,
        )
        conn.commit()
        print(f"  fact_supply_chain 교란 {len(sc_updates):,}건 현실화")
    except Exception as e:
        print(f"  fact_supply_chain 처리 중 오류: {e}")

    # ── 5. dim_facility 현실화 ────────────────────────────────────────────────
    print("\n[5] dim_facility facility_purpose 추가")
    try:
        fac_cols = {c[1] for c in conn.execute("PRAGMA table_info(dim_facility)").fetchall()}
        if "facility_purpose" not in fac_cols:
            conn.execute("ALTER TABLE dim_facility ADD COLUMN facility_purpose TEXT")
        conn.commit()
        fac_rows = conn.execute("SELECT rowid FROM dim_facility").fetchall()
        fac_updates = [(rng.choice(FACILITY_PURPOSES), r["rowid"]) for r in fac_rows]
        conn.executemany("UPDATE dim_facility SET facility_purpose=? WHERE rowid=?", fac_updates)
        conn.commit()
        print(f"  dim_facility {len(fac_updates):,}건 목적 입력")
    except Exception as e:
        print(f"  dim_facility 처리 중 오류: {e}")

    # ── 6. dim_collateral 현실화 ──────────────────────────────────────────────
    print("\n[6] dim_collateral 담보 설명 추가")
    try:
        col_cols = {c[1] for c in conn.execute("PRAGMA table_info(dim_collateral)").fetchall()}
        col_new = {"collateral_description": "TEXT", "collateral_address": "TEXT"}
        for col, dtype in col_new.items():
            if col not in col_cols:
                conn.execute(f"ALTER TABLE dim_collateral ADD COLUMN {col} {dtype}")
        conn.commit()
        collaterals = conn.execute("""
            SELECT dc.rowid, c.industry_cd, c.region_cd
            FROM dim_collateral dc
            JOIN dim_company c ON dc.borrower_id = c.borrower_id
        """).fetchall()
        col_updates = []
        for r in collaterals:
            ind = r["industry_cd"] or "K01A"
            reg = r["region_cd"] or "R01"
            desc = COLLATERAL_TYPES_BY_INDUSTRY.get(ind, "건물 및 토지")
            addr = gen_address(reg, ind, rng)
            col_updates.append((desc, addr, r["rowid"]))
        conn.executemany(
            "UPDATE dim_collateral SET collateral_description=?, collateral_address=? WHERE rowid=?",
            col_updates,
        )
        conn.commit()
        print(f"  dim_collateral {len(col_updates):,}건 담보 설명 입력")
    except Exception as e:
        print(f"  dim_collateral 처리 중 오류: {e}")

    # ── 7. dataset_registry 업데이트 ─────────────────────────────────────────
    conn.execute("""
        UPDATE dataset_registry SET description = description || '|현실화데이터(기업명/대표자/주소/소송유형/공급망)'
        WHERE version = 'v21.0'
    """)
    conn.commit()

    conn.close()
    print(f"\n  완료: {time.time() - t0:.1f}초")
    print("=" * 60)

    # ── 검증 샘플 출력 ────────────────────────────────────────────────────────
    print("\n[샘플 확인]")
    conn2 = sqlite3.connect(DB_PATH)
    conn2.row_factory = sqlite3.Row
    samples = conn2.execute("""
        SELECT borrower_id, company_name, ceo_name, address, established_year, industry_cd
        FROM dim_company ORDER BY RANDOM() LIMIT 10
    """).fetchall()
    print(f"  {'borrower_id':<15} {'company_name':<25} {'ceo_name':<8} {'업종':<5} {'설립':<6} {'주소'}")
    for s in samples:
        print(f"  {s['borrower_id']:<15} {s['company_name']:<25} {s['ceo_name']:<8} "
              f"{s['industry_cd']:<5} {s['established_year']:<6} {s['address']}")
    conn2.close()


if __name__ == "__main__":
    main()
