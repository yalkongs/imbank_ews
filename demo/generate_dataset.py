"""
generate_dataset.py — EWS 데모용 샘플 데이터셋 생성기 (v5)

대상: 20,000개 기업 / 36개월 (2023-01 ~ 2025-12)
  - 정상 기업 16,000개 (80%)
  - 부실 기업  2,400개 (12%) — 데모 기간 내 부도 발생
  - 회복 기업  1,600개  (8%) — 부실 징후 후 회복

im뱅크(구 대구은행) 영업 특성 반영:
  지역: 대구경북 50% / 부산경남 25% / 수도권 25%
  업종: 제조(섬유·자동차부품·철강) 비중 높음, 도소매·서비스 다음
  규모: 소기업 50% / 중소기업 35% / 중견기업 13% / 대기업 2%
  RM  : 15개 지점 × 4명 = 60명
"""

import sqlite3
import datetime
import time
import uuid
import numpy as np
from pathlib import Path

SEED      = 99
MONTHS_36 = [int(f"{y}{m:02d}") for y in range(2023, 2026) for m in range(1, 13)]
YM_START  = MONTHS_36[0]   # 202301
YM_END    = MONTHS_36[-1]  # 202512

N_NORMAL   = 16_000
N_DEFAULT  =  2_400
N_RECOVERY =  1_600
N_TOTAL    = N_NORMAL + N_DEFAULT + N_RECOVERY   # 20,000

DB_PATH = Path(__file__).parent / "demo.db"

# ── 업종 코드 & 지역별 가중치 ────────────────────────────────────────────────
INDUSTRY_CODES = ["K01A", "K01B", "K02", "K03", "K04", "K05",
                  "K07",  "K08",  "K09", "K10", "K11", "K13"]

# im뱅크 지역별 업종 특성
INDUSTRY_DIST_BY_REGION = {
    # 대구경북: 섬유(K01A) / 자동차·전자부품(K01B) 강세
    "대구경북": [0.18, 0.17, 0.12, 0.15, 0.10, 0.04, 0.05, 0.06, 0.07, 0.01, 0.02, 0.03],
    # 부산경남: 도소매(K03) / 운수물류(K08) / 건설(K02) 강세
    "부산경남": [0.11, 0.10, 0.14, 0.19, 0.13, 0.04, 0.05, 0.12, 0.08, 0.01, 0.01, 0.02],
    # 수도권:   서비스(K04) / IT(K05) / 도소매(K03) 강세
    "수도권":   [0.10, 0.12, 0.11, 0.20, 0.18, 0.10, 0.05, 0.05, 0.06, 0.01, 0.01, 0.01],
}

FIRM_SIZES = ["대기업", "중견기업", "중소기업", "소기업"]
SIZE_DIST  = [0.02, 0.13, 0.35, 0.50]

REGIONS    = ["대구경북", "부산경남", "수도권"]
REGION_DIST = [0.50, 0.25, 0.25]

QUARTER_MONTHS = [ym for ym in MONTHS_36 if ym % 100 in (3, 6, 9, 12)]

FACILITY_TYPES       = ["운전자금", "시설자금", "무역금융", "보증"]
COLLATERAL_TYPES_FAC = ["부동산", "기계", "무담보"]
COLLATERAL_TYPES_COL = ["부동산", "기계", "재고"]
WORKOUT_TYPES        = ["RESTRUCTURING", "FORECLOSURE", "AUCTION", "WRITE_OFF", "RECOVERY"]
WORKOUT_OUTCOMES     = ["COMPLETED", "ONGOING", "FAILED"]
COVENANT_TYPES       = ["부채비율", "ICR", "유동비율", "DSCR"]

COLLATERAL_SUBTYPES = {
    "부동산": ["아파트", "빌라/연립", "상가", "공장부지", "토지", "오피스텔"],
    "기계":   ["기계장치", "공장설비", "특수장비", "운반장비"],
    "재고":   ["상품", "반제품", "원재료"],
}

# 지역별 부동산 주소 풀
REAL_ESTATE_ADDRESSES = {
    "대구경북": [
        "대구 달서구", "대구 수성구", "대구 북구", "대구 남구", "대구 동구", "대구 중구",
        "경북 구미시", "경북 포항시", "경북 경주시", "경북 경산시", "경북 안동시",
        "경북 김천시", "경북 영천시", "경북 상주시", "경북 칠곡군",
    ],
    "부산경남": [
        "부산 해운대구", "부산 사상구", "부산 남구", "부산 강서구", "부산 기장군",
        "경남 창원시", "경남 양산시", "경남 김해시", "경남 진주시", "경남 거제시",
        "울산 남구", "울산 울주군",
    ],
    "수도권": [
        "서울 강남구", "서울 서초구", "서울 영등포구", "서울 마포구", "서울 성동구",
        "경기 수원시", "경기 성남시", "경기 고양시", "경기 화성시", "경기 부천시",
        "경기 안산시", "경기 용인시", "인천 남동구", "인천 부평구",
    ],
}

APPRAISERS = ["한국감정원", "나라감정", "새한감정", "아시아감정", "신한감정", "대한감정", "경북감정"]
RECOGNITION_RATIO = {"부동산": (0.60, 0.80), "기계": (0.40, 0.60), "재고": (0.30, 0.50)}

BATCH_SIZE = 2_000   # 배치 INSERT 단위

# ── 기업명 구성 풀 ───────────────────────────────────────────────────────────
PREFIXES = ["(주)", "주식회사", "㈜", "유한회사"]

NAMES_POOL = [
    # 지역명 기반 (대구경북·부산경남 중심)
    "가야",    "경산",    "경주",    "경천",    "고령",    "구미",    "금강",    "금오",
    "금호",    "김천",    "낙동",    "낙산",    "남강",    "남해",    "대경",    "대구",
    "달구벌",  "달성",    "달서",    "동대구",  "마산",    "밀양",    "반월당",  "부산",
    "사상",    "수성",    "안동",    "양산",    "영일",    "영천",    "울산",    "의성",
    "청도",    "청송",    "포항",    "합천",    "해운대",  "경운",    "경북",
    # 한자어 비즈니스명
    "가람",    "가온",    "건국",    "경성",    "경원",    "경일",    "고려",    "공영",
    "광명",    "국제",    "기린",    "나라",    "내일",    "누리",    "다올",    "단성",
    "대동",    "대명",    "대보",    "대성",    "대아",    "대양",    "대영",    "대원",
    "대일",    "대진",    "대화",    "대흥",    "덕성",    "동광",    "동국",    "동남",
    "동방",    "동보",    "동서",    "동성",    "동아",    "동양",    "동원",    "동일",
    "동진",    "두레",    "마루",    "명성",    "명신",    "명운",    "미래",    "미성",
    "미소",    "반석",    "보람",    "보성",    "부강",    "부민",    "부성",    "부창",
    "삼광",    "삼남",    "삼덕",    "삼보",    "삼원",    "삼일",    "삼진",    "상록",
    "상아",    "새빛",    "서경",    "서광",    "서남",    "서부",    "서성",    "서영",
    "서원",    "성공",    "성도",    "성보",    "성산",    "성신",    "성원",    "성일",
    "성진",    "세경",    "세광",    "세기",    "세명",    "세아",    "세영",    "세원",
    "세일",    "세화",    "소강",    "송광",    "수도",    "신광",    "신남",    "신동",
    "신성",    "신한",    "신흥",    "아람",    "아성",    "안성",    "양지",    "연성",
    "영광",    "영우",    "영진",    "오성",    "온누",    "우리",    "우성",    "우신",
    "우일",    "원성",    "원일",    "유성",    "이레",    "이원",    "인성",    "일광",
    "일성",    "일신",    "일진",    "전진",    "정광",    "정보",    "정성",    "정우",
    "정진",    "제일",    "조광",    "중앙",    "지성",    "지평",    "진성",    "진일",
    "창성",    "청구",    "청호",    "청화",    "태경",    "태광",    "태성",    "태양",
    "태영",    "통일",    "파워",    "포스",    "풍성",    "풍국",    "하나",    "하람",
    "한가",    "한국",    "한남",    "한대",    "한성",    "한솔",    "한신",    "한양",
    "한일",    "한진",    "한화",    "해성",    "해원",    "현대",    "현성",    "협성",
    "화성",    "화원",    "흥국",    "흥덕",    "흥성",    "흥신",    "희성",    "희망",
]

NAME_SUFFIXES = [
    "산업",    "기업",    "실업",    "공업",    "제조",    "건설",    "유통",    "상사",
    "물산",    "에너지",  "테크",    "시스템",  "솔루션",  "네트웍스","인터내셔널","코리아",
    "글로벌",  "파트너스","엔지니어링","정밀",   "금속",    "화학",    "식품",    "섬유",
    "전자",    "통신",    "물류",    "개발",    "투자",    "교역",    "무역",    "서비스",
    "그룹",    "코퍼레이션","컴퍼니", "홀딩스",  "인더스트리","창업",   "혁신",    "상회",
]

# ── RM 데이터 (15개 지점 × 4명 = 60명) ──────────────────────────────────────
FAMILY_NAMES = ["김","이","박","최","정","강","조","윤","장","임",
                "오","한","신","서","권","황","안","송","류","전",
                "홍","고","문","양","손","배","백","허","유","남"]
GIVEN_NAMES  = [
    "민준","서연","지훈","유진","수호","다은","현우","소희","태양","나리",
    "지원","영식","상민","은지","성현","미래","도현","예린","준혁","수민",
    "경호","다영","태민","혜리","재원","소연","현준","지연","민호","예진",
    "승현","다혜","준서","혜진","지수","태희","민재","은서","진혁","수아",
    "종현","예은","동현","세연","형준","나영","재훈","미소","상현","지윤",
    "광수","정민","혜영","윤성","태준","서현","민성","지혜","우람","선아",
]

RM_BRANCHES = [
    # (지점명, 팀명, 담당지역)
    ("대구본점",    "기업금융1팀", "대구경북"),
    ("동대구지점",  "기업금융1팀", "대구경북"),
    ("수성지점",    "기업금융2팀", "대구경북"),
    ("달서지점",    "기업금융2팀", "대구경북"),
    ("북구지점",    "기업금융3팀", "대구경북"),
    ("달구벌지점",  "기업금융3팀", "대구경북"),
    ("구미지점",    "경북영업팀",  "대구경북"),
    ("포항지점",    "경북영업팀",  "대구경북"),
    ("경주지점",    "경북영업팀",  "대구경북"),
    ("경산지점",    "경북영업팀",  "대구경북"),
    ("부산지점",    "부산경남팀",  "부산경남"),
    ("창원지점",    "부산경남팀",  "부산경남"),
    ("울산지점",    "부산경남팀",  "부산경남"),
    ("서울지점",    "수도권영업팀","수도권"),
    ("수원지점",    "수도권영업팀","수도권"),
]
RM_PER_BRANCH = 4   # 지점당 RM 수


# ── 유틸 함수 ────────────────────────────────────────────────────────────────
def _ym_diff(ym_future, ym_past):
    yf, mf = divmod(ym_future, 100)
    yp, mp = divmod(ym_past,   100)
    return (yf - yp) * 12 + (mf - mp)


def ym_add(ym, months):
    y, m = divmod(ym, 100)
    m += months
    while m > 12: m -= 12; y += 1
    while m < 1:  m += 12; y -= 1
    return y * 100 + m


def ews_to_grade(ews):
    if ews >= 70:   return "A"
    elif ews >= 50: return "B"
    elif ews >= 30: return "C"
    else:           return "D"


def ews_to_asset_class(ews):
    if ews >= 60:   return "NORMAL"
    elif ews >= 40: return "PRECAUTIONARY"
    elif ews >= 20: return "SUBSTANDARD"
    elif ews >= 10: return "DOUBTFUL"
    else:           return "LOSS"


def ews_to_rating(ews):
    if ews >= 90:   return "AAA"
    elif ews >= 80: return "AA"
    elif ews >= 70: return "A"
    elif ews >= 60: return "BBB"
    elif ews >= 50: return "BB"
    elif ews >= 40: return "B"
    elif ews >= 30: return "CCC"
    elif ews >= 20: return "CC"
    elif ews >= 10: return "C"
    else:           return "D"


# ── DB 빌드 ──────────────────────────────────────────────────────────────────
def build_demo_db(rng):
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-65536")   # 64 MB cache

    # ── 테이블 생성 ──────────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE demo_company (
            borrower_id     TEXT PRIMARY KEY,
            company_name    TEXT NOT NULL,
            firm_size_cd    TEXT NOT NULL,
            industry_cd     TEXT NOT NULL,
            listed_flag     INTEGER DEFAULT 0,
            scenario        TEXT NOT NULL,
            default_ym      INTEGER,
            recovery_ym     INTEGER,
            region          TEXT NOT NULL DEFAULT '수도권',
            rm_id           TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE demo_monthly_signal (
            signal_id               INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id             TEXT NOT NULL,
            ym                      INTEGER NOT NULL,
            debt_to_equity_ratio    REAL,
            current_ratio           REAL,
            interest_coverage_ratio REAL,
            dscr_ratio              REAL,
            ebitda_margin_pct       REAL,
            sales_growth_pct        REAL,
            limit_utilization_ratio REAL,
            principal_past_due_days INTEGER,
            covenant_breach_count_12m INTEGER,
            avg_deposit_balance_억  REAL,
            inflow_outflow_ratio    REAL,
            ews_score               REAL,
            ews_grade               TEXT,
            ifrs9_stage             INTEGER,
            industry_stress_score   REAL,
            news_sentiment_score    REAL,
            seizure_flag            INTEGER DEFAULT 0,
            lawsuit_count_12m       INTEGER DEFAULT 0,
            bankruptcy_filing_flag  INTEGER DEFAULT 0,
            data_completeness_pct   REAL DEFAULT 100.0,
            ews_tier                INTEGER DEFAULT 2,
            confidence_adj_score    REAL,
            UNIQUE(borrower_id, ym)
        )
    """)
    conn.execute("CREATE INDEX idx_ds_bid ON demo_monthly_signal(borrower_id)")
    conn.execute("CREATE INDEX idx_ds_ym  ON demo_monthly_signal(ym)")
    conn.execute("CREATE INDEX idx_ds_grade ON demo_monthly_signal(ews_grade)")

    conn.execute("""
        CREATE TABLE demo_answer_key (
            borrower_id     TEXT PRIMARY KEY,
            scenario        TEXT NOT NULL,
            first_signal_ym INTEGER,
            default_ym      INTEGER,
            lead_months     INTEGER,
            notes           TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE demo_facility (
            facility_id         TEXT PRIMARY KEY,
            borrower_id         TEXT NOT NULL,
            facility_type       TEXT NOT NULL,
            committed_amount_억  REAL,
            outstanding_amount_억 REAL,
            interest_rate       REAL,
            maturity_ym         INTEGER,
            collateral_type     TEXT
        )
    """)
    conn.execute("CREATE INDEX idx_fac_bid ON demo_facility(borrower_id)")

    conn.execute("""
        CREATE TABLE demo_collateral (
            collateral_id           TEXT PRIMARY KEY,
            borrower_id             TEXT NOT NULL,
            facility_id             TEXT NOT NULL,
            collateral_type         TEXT,
            collateral_subtype      TEXT,
            address                 TEXT,
            area_m2                 REAL,
            prior_lien_amount_억     REAL,
            recognition_ratio       REAL,
            appraised_value_억       REAL,
            ltv_pct                 REAL,
            appraiser               TEXT
        )
    """)
    conn.execute("CREATE INDEX idx_col_bid ON demo_collateral(borrower_id)")

    conn.execute("""
        CREATE TABLE demo_asset_class (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id     TEXT NOT NULL,
            ym              INTEGER NOT NULL,
            classification  TEXT NOT NULL,
            ews_score       REAL,
            UNIQUE(borrower_id, ym)
        )
    """)
    conn.execute("CREATE INDEX idx_ac_bid ON demo_asset_class(borrower_id)")
    conn.execute("CREATE INDEX idx_ac_ym  ON demo_asset_class(ym)")

    conn.execute("""
        CREATE TABLE demo_ecl (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id     TEXT NOT NULL,
            ym              INTEGER NOT NULL,
            stage           INTEGER NOT NULL,
            ecl_amount_억    REAL,
            pd_value        REAL,
            lgd             REAL,
            ead_억           REAL,
            UNIQUE(borrower_id, ym)
        )
    """)
    conn.execute("CREATE INDEX idx_ecl_bid ON demo_ecl(borrower_id)")
    conn.execute("CREATE INDEX idx_ecl_ym  ON demo_ecl(ym)")

    conn.execute("""
        CREATE TABLE demo_credit_rating (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id     TEXT NOT NULL,
            rating_ym       INTEGER NOT NULL,
            grade           TEXT NOT NULL,
            UNIQUE(borrower_id, rating_ym)
        )
    """)
    conn.execute("CREATE INDEX idx_cr_bid ON demo_credit_rating(borrower_id)")

    conn.execute("""
        CREATE TABLE demo_covenant (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id     TEXT NOT NULL,
            check_ym        INTEGER NOT NULL,
            covenant_type   TEXT NOT NULL,
            result          TEXT NOT NULL,
            actual_value    REAL,
            threshold_value REAL,
            UNIQUE(borrower_id, check_ym, covenant_type)
        )
    """)
    conn.execute("CREATE INDEX idx_cov_bid ON demo_covenant(borrower_id)")

    conn.execute("""
        CREATE TABLE demo_workout (
            workout_id          TEXT PRIMARY KEY,
            borrower_id         TEXT NOT NULL,
            workout_type        TEXT NOT NULL,
            workout_start_ym    INTEGER NOT NULL,
            original_balance_억  REAL,
            recovery_rate       REAL,
            outcome             TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX idx_wo_bid ON demo_workout(borrower_id)")

    conn.execute("""
        CREATE TABLE demo_collateral_valuation (
            valuation_id        TEXT PRIMARY KEY,
            collateral_id       TEXT NOT NULL,
            borrower_id         TEXT NOT NULL,
            valuation_ym        INTEGER NOT NULL,
            appraised_value_억   REAL,
            market_value_억      REAL,
            ltv_pct             REAL,
            valuation_method    TEXT,
            change_pct          REAL
        )
    """)
    conn.execute("CREATE INDEX idx_cv_bid ON demo_collateral_valuation(borrower_id)")
    conn.execute("CREATE INDEX idx_cv_col ON demo_collateral_valuation(collateral_id)")

    conn.execute("""
        CREATE TABLE demo_recovery_scenario (
            scenario_id             TEXT PRIMARY KEY,
            workout_id              TEXT NOT NULL,
            borrower_id             TEXT NOT NULL,
            scenario_type           TEXT NOT NULL,
            recovery_method         TEXT NOT NULL,
            recovery_amount_억       REAL,
            recovery_timeline_months INTEGER,
            discount_rate           REAL,
            npv_억                   REAL,
            irr_pct                 REAL,
            probability_pct         REAL
        )
    """)
    conn.execute("CREATE INDEX idx_rs_wid ON demo_recovery_scenario(workout_id)")
    conn.execute("CREATE INDEX idx_rs_bid ON demo_recovery_scenario(borrower_id)")

    # ── 신규 테이블 5개 ──────────────────────────────────────────────────────

    # 1. 월별 거래 행동
    conn.execute("""
        CREATE TABLE demo_ews_transaction (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id           TEXT NOT NULL,
            ym                    INTEGER NOT NULL,
            avg_daily_balance_억   REAL,
            balance_change_pct    REAL,
            incoming_amount_억     REAL,
            outgoing_amount_억     REAL,
            payment_delay_count   INTEGER,
            check_bounce_count    INTEGER,
            overdraft_count       INTEGER,
            salary_transfer_flag  INTEGER,
            card_spending_change_pct REAL,
            UNIQUE(borrower_id, ym)
        )
    """)
    conn.execute("CREATE INDEX idx_txn_bid ON demo_ews_transaction(borrower_id, ym)")

    # 2. 공공 이벤트
    conn.execute("""
        CREATE TABLE demo_ews_public_event (
            event_id        TEXT PRIMARY KEY,
            borrower_id     TEXT NOT NULL,
            event_ym        INTEGER NOT NULL,
            event_type      TEXT NOT NULL,
            severity        TEXT NOT NULL,
            description     TEXT,
            resolved_flag   INTEGER DEFAULT 0,
            resolved_ym     INTEGER
        )
    """)
    conn.execute("CREATE INDEX idx_pe_bid ON demo_ews_public_event(borrower_id)")

    # 3. 월별 뉴스 감성
    conn.execute("""
        CREATE TABLE demo_ews_news_monthly (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id         TEXT NOT NULL,
            ym                  INTEGER NOT NULL,
            article_count       INTEGER,
            positive_count      INTEGER,
            negative_count      INTEGER,
            neutral_count       INTEGER,
            avg_sentiment_score REAL,
            top_category        TEXT,
            UNIQUE(borrower_id, ym)
        )
    """)
    conn.execute("CREATE INDEX idx_nm_bid ON demo_ews_news_monthly(borrower_id, ym)")

    # 4. 시장 신호 (상장사만)
    conn.execute("""
        CREATE TABLE demo_ews_market_signal (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id            TEXT NOT NULL,
            ym                     INTEGER NOT NULL,
            stock_price_change_pct REAL,
            stock_volatility_30d   REAL,
            cds_spread_bps         REAL,
            bond_yield_spread_bps  REAL,
            short_interest_ratio   REAL,
            market_cap_억           REAL,
            UNIQUE(borrower_id, ym)
        )
    """)
    conn.execute("CREATE INDEX idx_ms_bid ON demo_ews_market_signal(borrower_id, ym)")

    # 5. 공급망 위험
    conn.execute("""
        CREATE TABLE demo_ews_supply_chain (
            relation_id              TEXT PRIMARY KEY,
            borrower_id              TEXT NOT NULL,
            counterparty_id          TEXT NOT NULL,
            counterparty_name        TEXT,
            relation_type            TEXT NOT NULL,
            exposure_ratio           REAL,
            contagion_risk_score     REAL,
            is_internal_counterparty INTEGER,
            as_of_ym                 INTEGER
        )
    """)
    conn.execute("CREATE INDEX idx_sc_bid ON demo_ews_supply_chain(borrower_id)")

    # ── RM 테이블 (먼저 생성 — 기업 생성 시 즉시 배정) ──────────────────────
    conn.execute("""
        CREATE TABLE demo_rm (
            rm_id   TEXT PRIMARY KEY,
            rm_name TEXT,
            branch  TEXT,
            team    TEXT
        )
    """)

    rm_data = []
    used_rm_names = set()
    rng_names = rng.bit_generator  # 동일 rng 사용

    for branch_idx, (branch, team, _region) in enumerate(RM_BRANCHES):
        for k in range(RM_PER_BRANCH):
            rm_id = f"RM{branch_idx * RM_PER_BRANCH + k + 1:03d}"
            # 중복 없는 한국 이름 생성
            for _ in range(50):
                fn = FAMILY_NAMES[rng.integers(0, len(FAMILY_NAMES))]
                gn = GIVEN_NAMES[rng.integers(0, len(GIVEN_NAMES))]
                full = fn + gn
                if full not in used_rm_names:
                    used_rm_names.add(full)
                    break
            rm_data.append((rm_id, full, branch, team))

    conn.executemany("INSERT INTO demo_rm VALUES (?,?,?,?)", rm_data)
    conn.commit()

    # 지점별 담당 지역 → rm_id 풀 매핑
    rm_by_region = {"대구경북": [], "부산경남": [], "수도권": []}
    for branch_idx, (branch, team, region) in enumerate(RM_BRANCHES):
        for k in range(RM_PER_BRANCH):
            rm_id = f"RM{branch_idx * RM_PER_BRANCH + k + 1:03d}"
            rm_by_region[region].append(rm_id)

    all_rm_ids = [r[0] for r in rm_data]

    # ── 기업 생성 ────────────────────────────────────────────────────────────
    print("  [1/6] 기업 마스터 생성 중...")
    companies      = []
    company_rows   = []
    used_cnames    = set()
    bid_counter    = 1

    def make_company(scenario, default_ym=None, recovery_ym=None):
        nonlocal bid_counter
        bid    = f"DEMO{bid_counter:05d}"
        bid_counter += 1
        region = str(rng.choice(REGIONS, p=REGION_DIST))
        # 지역별 업종 가중치
        ind_dist = INDUSTRY_DIST_BY_REGION[region]
        industry = INDUSTRY_CODES[int(rng.choice(len(INDUSTRY_CODES), p=ind_dist))]
        firm_size = str(rng.choice(FIRM_SIZES, p=SIZE_DIST))
        listed = 1 if firm_size == "대기업" and rng.random() < 0.5 else 0
        # 지역 기반 RM 배정 (70% 확률로 동일 지역 RM)
        if rng.random() < 0.70:
            rm_pool = rm_by_region[region]
        else:
            rm_pool = all_rm_ids
        rm_id = rm_pool[rng.integers(0, len(rm_pool))]

        # 중복 없는 기업명 생성
        for attempt in range(30):
            pref   = PREFIXES[rng.integers(0, len(PREFIXES))]
            name_a = NAMES_POOL[rng.integers(0, len(NAMES_POOL))]
            name_b = NAME_SUFFIXES[rng.integers(0, len(NAME_SUFFIXES))]
            cname  = f"{pref}{name_a}{name_b}"
            if cname not in used_cnames:
                used_cnames.add(cname)
                break
            if attempt == 29:
                cname = f"{cname}{bid_counter}"
        used_cnames.add(cname)

        # tier / completeness 계산
        if firm_size == "대기업":
            tier = 1
            completeness = float(rng.uniform(0.75, 0.95))
        elif firm_size in ("중견기업", "중소기업"):
            tier = 2
            completeness = float(rng.uniform(0.45, 0.75))
        else:  # 소기업
            tier = 3
            completeness = float(rng.uniform(0.15, 0.50))

        companies.append({
            "borrower_id": bid, "firm_size_cd": firm_size,
            "industry_cd": industry, "scenario": scenario,
            "default_ym": default_ym, "recovery_ym": recovery_ym,
            "region": region, "tier": tier, "completeness_pct": completeness,
        })
        company_rows.append((bid, cname, firm_size, industry, listed,
                              scenario, default_ym, recovery_ym, region, rm_id))
        return bid

    for _ in range(N_NORMAL):
        make_company("NORMAL")
    for _ in range(N_DEFAULT):
        def_ym = MONTHS_36[rng.integers(6, 30)]
        make_company("DEFAULT", default_ym=def_ym)
    for _ in range(N_RECOVERY):
        rec_ym = MONTHS_36[rng.integers(12, 24)]
        make_company("RECOVERY", recovery_ym=rec_ym)

    conn.executemany(
        "INSERT INTO demo_company VALUES (?,?,?,?,?,?,?,?,?,?)",
        company_rows
    )
    conn.commit()
    print(f"    → {N_TOTAL:,}개 기업 INSERT 완료")

    # ── 월별 신호 생성 (배치) ────────────────────────────────────────────────
    print(f"  [2/6] 월별 신호 생성 중 ({N_TOTAL:,}개 기업 × 36개월)...")
    answer_rows = []

    NEWS_CATEGORIES = ["FINANCIAL", "LEGAL", "OPERATIONAL", "MANAGEMENT", "INDUSTRY"]

    SIGNAL_SQL = """
        INSERT OR IGNORE INTO demo_monthly_signal
          (borrower_id, ym, debt_to_equity_ratio, current_ratio,
           interest_coverage_ratio, dscr_ratio, ebitda_margin_pct, sales_growth_pct,
           limit_utilization_ratio, principal_past_due_days, covenant_breach_count_12m,
           avg_deposit_balance_억, inflow_outflow_ratio,
           ews_score, ews_grade, ifrs9_stage,
           industry_stress_score, news_sentiment_score,
           seizure_flag, lawsuit_count_12m, bankruptcy_filing_flag,
           data_completeness_pct, ews_tier, confidence_adj_score)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """

    for batch_start in range(0, N_TOTAL, BATCH_SIZE):
        batch = companies[batch_start: batch_start + BATCH_SIZE]
        signal_rows   = []
        asset_rows    = []
        ecl_rows      = []
        rating_rows   = []
        covenant_rows = []
        transaction_rows = []
        news_rows     = []

        for c in batch:
            bid        = c["borrower_id"]
            scenario   = c["scenario"]
            default_ym = c.get("default_ym")
            recovery_ym = c.get("recovery_ym")
            firm_size  = c["firm_size_cd"]
            tier       = c.get("tier", 2)
            completeness = c.get("completeness_pct", 0.6)

            dte_base = {"대기업": 80,  "중견기업": 130, "중소기업": 180, "소기업": 250}.get(firm_size, 180)
            cr_base  = {"대기업": 200, "중견기업": 150, "중소기업": 120, "소기업": 90 }.get(firm_size, 120)
            icr_base = {"대기업": 8.0, "중견기업": 4.0, "중소기업": 2.5, "소기업": 1.5}.get(firm_size, 2.5)
            ews_base = {"대기업": 75.0,"중견기업": 65.0,"중소기업": 55.0,"소기업": 45.0}.get(firm_size, 55.0)
            dep_base = float(rng.uniform(5, 300))
            ead_base = {"대기업": 800.0,"중견기업": 200.0,"중소기업": 60.0,"소기업": 12.0}.get(firm_size, 60.0)
            ead_base *= float(rng.uniform(0.5, 1.5))

            first_signal_ym = None

            for ym in MONTHS_36:
                if scenario == "DEFAULT" and default_ym and ym >= default_ym:
                    break

                months_to_event = 999
                deterioration   = 0.0

                if scenario == "DEFAULT" and default_ym:
                    months_to_event = max(0, _ym_diff(default_ym, ym))
                    if months_to_event < 24:
                        t = months_to_event / 24.0
                        deterioration = float(1.0 / (1.0 + np.exp(6.0 * (t - 0.5))))

                elif scenario == "RECOVERY" and recovery_ym:
                    dist_to_rec = _ym_diff(recovery_ym, ym)
                    if dist_to_rec < 12:
                        deterioration = float(0.5 * (1.0 - dist_to_rec / 12.0))
                    elif dist_to_rec < 0:
                        deterioration = max(0.0, 0.3 + dist_to_rec * 0.05)

                dte    = round(dte_base * (1 + deterioration * 3.0) + rng.normal(0, 15), 1)
                cr     = round(max(10, cr_base * (1 - deterioration * 0.6) + rng.normal(0, 15)), 1)
                icr    = round(max(0.1, icr_base * (1 - deterioration * 0.7) + rng.normal(0, 0.5)), 2)
                dscr   = round(max(0.1, icr * 0.6 + rng.normal(0, 0.2)), 2)
                ebitda = round(max(-30, 15 - deterioration * 30 + rng.normal(0, 3)), 1)
                sales_g = round(5 - deterioration * 20 + rng.normal(0, 3), 1)

                util       = round(min(1.5, 0.40 + deterioration * 0.80 + rng.normal(0, 0.05)), 3)
                dpd        = 0
                if deterioration > 0.5 and rng.random() < deterioration * 0.6:
                    dpd = int(rng.integers(1, min(90, int(deterioration * 120) + 1)))
                cov_breach = 1 if deterioration > 0.4 and rng.random() < deterioration * 0.7 else 0
                dep        = round(max(0.1, dep_base * (1 - deterioration * 0.5) + rng.normal(0, dep_base * 0.1)), 2)
                io_ratio   = round(max(0.3, 1.0 - deterioration * 0.4 + rng.normal(0, 0.05)), 3)

                ews = round(max(1, min(100, ews_base - deterioration * 50 + rng.normal(0, 3))), 1)
                ews_grade = ews_to_grade(ews)
                if ews_grade in ("C", "D") and first_signal_ym is None:
                    first_signal_ym = ym

                if deterioration > 0.6 or dpd >= 90:
                    stage = 3
                elif deterioration > 0.25 or dpd >= 30 or cov_breach:
                    stage = 2
                else:
                    stage = 1

                ind_stress = round(15 + deterioration * 30 + rng.normal(0, 5), 1)
                news_sent  = round(max(0, min(1, 0.6 - deterioration * 0.5 + rng.normal(0, 0.05))), 3)
                seizure    = 1 if deterioration > 0.7 and rng.random() < 0.3 else 0
                lawsuit    = int(rng.integers(0, 2)) if deterioration > 0.5 else 0
                bk_filing  = 1 if scenario == "DEFAULT" and default_ym and months_to_event <= 3 else 0

                # confidence_adj_score 계산
                conf_adj = round(max(1.0, ews - (1.0 - completeness) * 25), 1)

                signal_rows.append((
                    bid, ym,
                    dte, cr, icr, dscr, ebitda, sales_g,
                    util, dpd, cov_breach, dep, io_ratio,
                    ews, ews_grade, stage,
                    ind_stress, news_sent,
                    seizure, lawsuit, bk_filing,
                    round(completeness * 100, 1), tier, conf_adj,
                ))
                asset_rows.append((bid, ym, ews_to_asset_class(ews), ews))

                ecl_stage = 3 if ews_grade == "D" else (2 if ews_grade == "C" else 1)
                ead = round(max(1.0, ead_base * (0.8 + deterioration * 0.4) + rng.normal(0, ead_base * 0.1)), 2)
                if ecl_stage == 1:
                    pd_val  = round(float(rng.uniform(0.01, 0.04)), 4)
                    lgd     = round(float(rng.uniform(0.30, 0.40)), 3)
                    ecl_amt = round(ead * pd_val * lgd, 3)
                elif ecl_stage == 2:
                    pd_val  = round(float(rng.uniform(0.08, 0.20)), 4)
                    lgd     = round(float(rng.uniform(0.40, 0.55)), 3)
                    fwd_adj = float(rng.uniform(0.3, 0.6))
                    ecl_amt = round(ead * pd_val * lgd * (1 + fwd_adj), 3)
                else:
                    pd_val  = round(float(rng.uniform(0.50, 0.90)), 4)
                    lgd     = round(float(rng.uniform(0.60, 0.80)), 3)
                    ecl_amt = round(ead * pd_val * lgd, 3)
                ecl_rows.append((bid, ym, ecl_stage, ecl_amt, pd_val, lgd, ead))

                if ym % 100 in (3, 6, 9, 12):
                    rating_rows.append((bid, ym, ews_to_rating(ews)))
                    for ct in COVENANT_TYPES:
                        if ct == "ICR":
                            av, th, breached = icr, 1.0, icr < 1.0
                        elif ct == "부채비율":
                            av, th, breached = dte, 300.0, dte > 300.0
                        elif ct == "유동비율":
                            av, th, breached = cr, 80.0, cr < 80.0
                        else:  # DSCR
                            av, th, breached = dscr, 1.0, dscr < 1.0
                        if breached:
                            result = "WAIVED" if rng.random() < 0.15 else "BREACH"
                        else:
                            result = "PASS"
                        covenant_rows.append((bid, ym, ct, result, round(av, 2), th))

                # ── 거래 행동 데이터 생성 ────────────────────────────────────
                bal_chg = round(float(rng.normal(-5, 10)) - deterioration * 15, 2)
                incoming = round(dep * float(rng.uniform(3, 8)), 2)
                outgoing = round(incoming * float(rng.uniform(0.8, 1.2 + deterioration * 0.3)), 2)
                pay_delay = max(0, int(deterioration * 5 + int(rng.integers(0, 3))))
                chk_bounce = 1 if deterioration > 0.6 and rng.random() < 0.4 else 0
                overdraft = max(0, int(deterioration * 3 + int(rng.integers(0, 2))))
                salary_flag = 0 if deterioration > 0.7 and rng.random() < 0.4 else 1
                card_chg = round(float(rng.normal(-5, 10)) - deterioration * 20, 2)
                transaction_rows.append((
                    bid, ym,
                    dep, bal_chg, incoming, outgoing,
                    pay_delay, chk_bounce, overdraft,
                    salary_flag, card_chg,
                ))

                # ── 뉴스 감성 데이터 생성 ────────────────────────────────────
                if firm_size == "대기업":
                    coverage_prob = 0.95
                    art_lo, art_hi = 8, 20
                elif firm_size == "중견기업":
                    coverage_prob = 0.65
                    art_lo, art_hi = 3, 10
                elif firm_size == "중소기업":
                    coverage_prob = 0.30
                    art_lo, art_hi = 1, 5
                else:  # 소기업
                    coverage_prob = 0.10
                    art_lo, art_hi = 1, 2

                if rng.random() < coverage_prob:
                    art_cnt = int(rng.integers(art_lo, art_hi + 1))
                    if ews >= 70:
                        pos_ratio = float(rng.uniform(0.50, 0.80))
                        neg_ratio = float(rng.uniform(0.05, 0.20))
                        avg_sent  = round(float(rng.uniform(0.55, 0.85)), 3)
                    elif ews >= 50:
                        pos_ratio = float(rng.uniform(0.30, 0.50))
                        neg_ratio = float(rng.uniform(0.20, 0.40))
                        avg_sent  = round(float(rng.uniform(0.40, 0.60)), 3)
                    elif ews >= 30:
                        pos_ratio = float(rng.uniform(0.10, 0.30))
                        neg_ratio = float(rng.uniform(0.40, 0.60))
                        avg_sent  = round(float(rng.uniform(0.20, 0.40)), 3)
                    else:
                        pos_ratio = float(rng.uniform(0.05, 0.20))
                        neg_ratio = float(rng.uniform(0.60, 0.85))
                        avg_sent  = round(float(rng.uniform(0.05, 0.25)), 3)
                    neg_ratio = min(neg_ratio, 1.0 - pos_ratio)
                    neu_ratio = max(0.0, 1.0 - pos_ratio - neg_ratio)
                    pos_cnt = max(0, round(art_cnt * pos_ratio))
                    neg_cnt = max(0, round(art_cnt * neg_ratio))
                    neu_cnt = max(0, art_cnt - pos_cnt - neg_cnt)
                    top_cat = NEWS_CATEGORIES[rng.integers(0, len(NEWS_CATEGORIES))]
                    news_rows.append((
                        bid, ym, art_cnt, pos_cnt, neg_cnt, neu_cnt, avg_sent, top_cat,
                    ))

            # 정답 키
            lead = None
            if scenario == "DEFAULT" and first_signal_ym and default_ym:
                lead = _ym_diff(default_ym, first_signal_ym)
            answer_rows.append((bid, scenario, first_signal_ym, default_ym, lead, f"{scenario} 시나리오"))

        # 배치 INSERT
        conn.executemany(SIGNAL_SQL, signal_rows)
        conn.executemany(
            "INSERT OR IGNORE INTO demo_asset_class (borrower_id, ym, classification, ews_score) VALUES (?,?,?,?)",
            asset_rows
        )
        conn.executemany(
            "INSERT OR IGNORE INTO demo_ecl (borrower_id, ym, stage, ecl_amount_억, pd_value, lgd, ead_억) VALUES (?,?,?,?,?,?,?)",
            ecl_rows
        )
        conn.executemany(
            "INSERT OR IGNORE INTO demo_credit_rating (borrower_id, rating_ym, grade) VALUES (?,?,?)",
            rating_rows
        )
        conn.executemany(
            "INSERT OR IGNORE INTO demo_covenant (borrower_id, check_ym, covenant_type, result, actual_value, threshold_value) VALUES (?,?,?,?,?,?)",
            covenant_rows
        )
        conn.executemany(
            "INSERT OR IGNORE INTO demo_ews_transaction "
            "(borrower_id, ym, avg_daily_balance_억, balance_change_pct, incoming_amount_억, "
            "outgoing_amount_억, payment_delay_count, check_bounce_count, overdraft_count, "
            "salary_transfer_flag, card_spending_change_pct) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            transaction_rows
        )
        conn.executemany(
            "INSERT OR IGNORE INTO demo_ews_news_monthly "
            "(borrower_id, ym, article_count, positive_count, negative_count, neutral_count, "
            "avg_sentiment_score, top_category) VALUES (?,?,?,?,?,?,?,?)",
            news_rows
        )
        conn.commit()
        done = min(batch_start + BATCH_SIZE, N_TOTAL)
        print(f"    → {done:,}/{N_TOTAL:,} 처리 완료")

    conn.executemany("INSERT INTO demo_answer_key VALUES (?,?,?,?,?,?)", answer_rows)
    conn.commit()

    # ── 여신 & 담보 ──────────────────────────────────────────────────────────
    print("  [3/6] 여신 및 담보 생성 중...")
    facility_rows   = []
    collateral_rows = []

    for c in companies:
        bid        = c["borrower_id"]
        scenario   = c["scenario"]
        firm_size  = c["firm_size_cd"]
        region     = c["region"]
        default_ym = c.get("default_ym")

        n_fac = int(rng.integers(1, 4))
        committed_pool = {
            "대기업": (60, 600), "중견기업": (10, 110),
            "중소기업": (2, 20),  "소기업":   (0.3, 4.5),
        }.get(firm_size, (2, 20))
        util_factor = 0.9 if scenario == "DEFAULT" else rng.uniform(0.3, 0.8)

        for _ in range(n_fac):
            fid       = f"F{uuid.uuid4().hex[:10].upper()}"
            ftype     = FACILITY_TYPES[rng.integers(0, len(FACILITY_TYPES))]
            committed = round(float(rng.uniform(*committed_pool)), 1)
            outstanding = round(committed * util_factor * float(rng.uniform(0.5, 1.0)), 1)
            rate      = round(float(rng.uniform(3.5, 9.5)), 2)
            mat_ym    = ym_add(YM_END, int(rng.integers(1, 36)))
            col_type  = COLLATERAL_TYPES_FAC[rng.integers(0, len(COLLATERAL_TYPES_FAC))]
            facility_rows.append((fid, bid, ftype, committed, outstanding, rate, mat_ym, col_type))

            if col_type != "무담보":
                cid      = f"C{uuid.uuid4().hex[:10].upper()}"
                appraised = round(committed * float(rng.uniform(1.0, 2.5)), 1)
                ltv       = round(outstanding / appraised * 100, 1) if appraised > 0 else 0.0
                col_type2 = COLLATERAL_TYPES_COL[rng.integers(0, len(COLLATERAL_TYPES_COL))]
                subtypes  = COLLATERAL_SUBTYPES.get(col_type2, ["기타"])
                subtype   = subtypes[rng.integers(0, len(subtypes))]
                if col_type2 == "부동산":
                    addr_pool = REAL_ESTATE_ADDRESSES.get(region, REAL_ESTATE_ADDRESSES["수도권"])
                    address   = addr_pool[rng.integers(0, len(addr_pool))]
                    area_m2   = round(float(rng.uniform(50, 3000)), 0)
                else:
                    address = None
                    area_m2 = None
                prior_lien = round(appraised * float(rng.uniform(0.3, 0.6) if scenario == "DEFAULT" else rng.uniform(0.0, 0.25)), 1)
                lo, hi = RECOGNITION_RATIO.get(col_type2, (0.5, 0.7))
                rec_ratio = round(float(rng.uniform(lo, hi)), 2)
                appraiser = APPRAISERS[rng.integers(0, len(APPRAISERS))]
                collateral_rows.append((cid, bid, fid, col_type2, subtype, address, area_m2,
                                        prior_lien, rec_ratio, appraised, ltv, appraiser))

    conn.executemany("INSERT INTO demo_facility VALUES (?,?,?,?,?,?,?,?)", facility_rows)
    conn.executemany("INSERT INTO demo_collateral VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", collateral_rows)
    conn.commit()
    print(f"    → 여신 {len(facility_rows):,}건, 담보 {len(collateral_rows):,}건")

    # ── Workout ──────────────────────────────────────────────────────────────
    print("  [4/6] Workout 및 담보 평가이력 생성 중...")
    workout_rows = []
    for c in companies:
        if c["scenario"] != "DEFAULT":
            continue
        bid     = c["borrower_id"]
        def_ym  = c.get("default_ym")
        if def_ym is None:
            continue
        firm_size = c["firm_size_cd"]
        wtype   = WORKOUT_TYPES[rng.integers(0, len(WORKOUT_TYPES))]
        wstart  = ym_add(def_ym, int(rng.integers(1, 4)))
        bal_pool = {
            "대기업": (300, 1500), "중견기업": (50, 400),
            "중소기업": (10, 100), "소기업":   (1, 20),
        }.get(firm_size, (10, 100))
        balance  = round(float(rng.uniform(*bal_pool)), 1)
        rec_rate = round(float(rng.uniform(0.1, 0.7)), 3)
        outcome  = WORKOUT_OUTCOMES[rng.integers(0, len(WORKOUT_OUTCOMES))]
        wid      = f"W{uuid.uuid4().hex[:10].upper()}"
        workout_rows.append((wid, bid, wtype, wstart, balance, rec_rate, outcome))

    conn.executemany("INSERT INTO demo_workout VALUES (?,?,?,?,?,?,?)", workout_rows)
    conn.commit()

    # ── 담보 분기별 가치평가 ─────────────────────────────────────────────────
    QUARTER_YMS = [ym for ym in MONTHS_36 if ym % 100 in (3, 6, 9, 12)]
    valuation_rows = []
    company_scenario_map = {c["borrower_id"]: c for c in companies}

    for row in collateral_rows:
        cid, bid, fid, col_type2, subtype, address, area_m2, prior_lien, rec_ratio, base_appraised, base_ltv, appraiser = row
        c = company_scenario_map[bid]
        scenario   = c["scenario"]
        default_ym = c.get("default_ym")
        prev_appraised = base_appraised

        for q_idx, val_ym in enumerate(QUARTER_YMS):
            if scenario == "DEFAULT" and default_ym:
                months_to_def = _ym_diff(default_ym, val_ym)
                if months_to_def <= 0:
                    change = float(rng.uniform(-0.15, -0.05))
                elif months_to_def <= 6:
                    change = float(rng.uniform(-0.08, -0.02))
                else:
                    change = float(rng.uniform(-0.03, 0.03))
            else:
                change = float(rng.uniform(-0.03, 0.03))

            if q_idx == 0:
                appraised  = base_appraised
                change_pct = 0.0
            else:
                appraised  = round(max(0.1, prev_appraised * (1 + change)), 2)
                change_pct = round(change * 100, 2)

            market_val  = round(appraised * float(rng.uniform(0.85, 1.10)), 2)
            outstanding_approx = base_appraised * base_ltv / 100.0 if base_ltv > 0 else base_appraised * 0.6
            ltv = round(min(200.0, outstanding_approx / appraised * 100), 1) if appraised > 0 else 0.0
            val_method  = ["APPRAISAL", "MARKET", "BOOK"][rng.integers(0, 3)]
            vid = f"V{uuid.uuid4().hex[:10].upper()}"
            valuation_rows.append((vid, cid, bid, val_ym, appraised, market_val, ltv, val_method, change_pct))
            prev_appraised = appraised

    conn.executemany(
        "INSERT INTO demo_collateral_valuation VALUES (?,?,?,?,?,?,?,?,?)",
        valuation_rows
    )
    conn.commit()
    print(f"    → Workout {len(workout_rows):,}건, 담보평가 {len(valuation_rows):,}건")

    # ── Workout 회수 시나리오 ─────────────────────────────────────────────────
    scenario_rows = []
    for wid, bid, wtype, wstart, balance, rec_rate, outcome in workout_rows:
        base_recovery = round(balance * rec_rate, 2)
        base_timeline = int(rng.integers(12, 36))
        base_discount = round(float(rng.uniform(0.05, 0.12)), 3)
        for stype, rec_mult, tl_mult, prob in [
            ("OPTIMISTIC",  1.3, 0.7, 25.0),
            ("BASE",        1.0, 1.0, 50.0),
            ("PESSIMISTIC", 0.6, 1.4, 25.0),
        ]:
            rec_amt  = round(base_recovery * rec_mult, 2)
            timeline = max(1, int(base_timeline * tl_mult))
            npv      = round(rec_amt / ((1 + base_discount) ** (timeline / 12.0)), 3)
            cost_base = base_recovery if base_recovery > 0 else 1.0
            irr = round(((rec_amt / cost_base) ** (12.0 / timeline) - 1) * 100, 2) if rec_amt > 0 and timeline > 0 else 0.0
            sid = f"S{uuid.uuid4().hex[:10].upper()}"
            scenario_rows.append((sid, wid, bid, stype, wtype, rec_amt, timeline, base_discount, npv, irr, prob))

    conn.executemany("INSERT INTO demo_recovery_scenario VALUES (?,?,?,?,?,?,?,?,?,?,?)", scenario_rows)
    conn.commit()

    # ── 추가 생성 단계: 공공 이벤트 / 시장 신호 / 공급망 ─────────────────────
    print("  [4.5/6] 공공이벤트 / 시장신호 / 공급망 생성 중...")

    # ── demo_ews_public_event ────────────────────────────────────────────────
    public_event_rows = []

    # seizure_flag=1인 기업-ym → SEIZURE 이벤트
    seizure_recs = conn.execute(
        "SELECT borrower_id, ym FROM demo_monthly_signal WHERE seizure_flag=1"
    ).fetchall()
    for sbid, sym in seizure_recs:
        eid = f"PE{uuid.uuid4().hex[:10].upper()}"
        resolved = 1 if rng.random() < 0.3 else 0
        resolved_ym = ym_add(sym, int(rng.integers(1, 4))) if resolved else None
        public_event_rows.append((
            eid, sbid, sym, "SEIZURE", "HIGH",
            "채권 압류 발생", resolved, resolved_ym
        ))

    # DEFAULT 기업 중 default_ym-ym<=6 구간에 TAX_DELINQUENT, SOCIAL_INSURANCE 이벤트
    default_company_map = {
        c["borrower_id"]: c for c in companies if c["scenario"] == "DEFAULT" and c.get("default_ym")
    }
    tax_recs = conn.execute(
        "SELECT borrower_id, ym FROM demo_monthly_signal WHERE bankruptcy_filing_flag=0"
    ).fetchall()
    for tbid, tym in tax_recs:
        if tbid not in default_company_map:
            continue
        def_ym = default_company_map[tbid]["default_ym"]
        diff = _ym_diff(def_ym, tym)
        if 0 < diff <= 6 and rng.random() < 0.25:
            etype = "TAX_DELINQUENT" if rng.random() < 0.5 else "SOCIAL_INSURANCE"
            eid = f"PE{uuid.uuid4().hex[:10].upper()}"
            resolved = 1 if rng.random() < 0.4 else 0
            resolved_ym = ym_add(tym, int(rng.integers(1, 3))) if resolved else None
            public_event_rows.append((
                eid, tbid, tym, etype, "MEDIUM",
                f"{etype} 발생", resolved, resolved_ym
            ))

    # DEFAULT 기업 50% → MGMT_CHANGE 이벤트 (default_ym 3~6개월 전)
    for dbid, dc in default_company_map.items():
        if rng.random() < 0.50:
            def_ym = dc["default_ym"]
            months_before = int(rng.integers(3, 7))
            event_ym = ym_add(def_ym, -months_before)
            if event_ym < YM_START:
                continue
            eid = f"PE{uuid.uuid4().hex[:10].upper()}"
            public_event_rows.append((
                eid, dbid, event_ym, "MGMT_CHANGE", "LOW",
                "대표이사 변경", 1, ym_add(event_ym, 1)
            ))

    conn.executemany(
        "INSERT OR IGNORE INTO demo_ews_public_event "
        "(event_id, borrower_id, event_ym, event_type, severity, description, resolved_flag, resolved_ym) "
        "VALUES (?,?,?,?,?,?,?,?)",
        public_event_rows
    )
    conn.commit()
    print(f"    → 공공이벤트 {len(public_event_rows):,}건")

    # ── demo_ews_market_signal ───────────────────────────────────────────────
    listed_bids = [row[0] for row in conn.execute(
        "SELECT borrower_id FROM demo_company WHERE listed_flag=1"
    ).fetchall()]

    # 기업별 최신 ews_score 매핑 (기업×월 → ews)
    ews_score_map = {}
    for row in conn.execute(
        "SELECT borrower_id, ym, ews_score FROM demo_monthly_signal"
    ).fetchall():
        ews_score_map[(row[0], row[1])] = row[2]

    market_signal_rows = []
    for lbid in listed_bids:
        # 기업 기본 시가총액 설정
        base_mktcap = float(rng.uniform(500, 50000))
        for ym in MONTHS_36:
            ews_val = ews_score_map.get((lbid, ym), 55.0)
            # EWS 점수 기반 주가 변화
            ews_norm = (ews_val - 50.0) / 50.0  # -1 ~ 1
            price_chg = round(float(rng.normal(ews_norm * 3, 8)), 2)
            volatility = round(max(5.0, float(rng.normal(20 - ews_norm * 10, 5))), 2)
            cds_spread = round(max(10.0, float(rng.normal(200 - ews_norm * 150, 30))), 1)
            bond_spread = round(max(5.0, float(rng.normal(150 - ews_norm * 100, 25))), 1)
            short_ratio = round(max(0.0, float(rng.normal(0.05 - ews_norm * 0.03, 0.02))), 4)
            mktcap = round(max(10.0, base_mktcap * (1 + price_chg / 100.0)), 1)
            base_mktcap = mktcap
            market_signal_rows.append((
                lbid, ym, price_chg, volatility, cds_spread,
                bond_spread, short_ratio, mktcap
            ))

    conn.executemany(
        "INSERT OR IGNORE INTO demo_ews_market_signal "
        "(borrower_id, ym, stock_price_change_pct, stock_volatility_30d, cds_spread_bps, "
        "bond_yield_spread_bps, short_interest_ratio, market_cap_억) VALUES (?,?,?,?,?,?,?,?)",
        market_signal_rows
    )
    conn.commit()
    print(f"    → 시장신호 {len(market_signal_rows):,}건 (상장사 {len(listed_bids)}개)")

    # ── demo_ews_supply_chain ────────────────────────────────────────────────
    supply_chain_rows = []
    relation_types = ["CUSTOMER", "SUPPLIER", "GUARANTOR"]
    default_bid_set = set(default_company_map.keys())
    all_bids = [c["borrower_id"] for c in companies]

    for c in companies:
        sbid = c["borrower_id"]
        firm_size = c["firm_size_cd"]

        # 참여 확률: 소기업 30%, 나머지 60%
        include_prob = 0.30 if firm_size == "소기업" else 0.60
        if rng.random() >= include_prob:
            continue

        n_relations = int(rng.integers(1, 5))
        for _ in range(n_relations):
            is_internal = 1 if rng.random() < 0.30 else 0
            if is_internal:
                # 내부 거래처: DEMO* 기업
                cp_idx = rng.integers(0, len(all_bids))
                cp_id = all_bids[cp_idx]
                cp_name = f"내부거래처_{cp_id}"
                if cp_id in default_bid_set:
                    contagion = round(float(rng.uniform(50, 95)), 1)
                else:
                    contagion = round(float(rng.uniform(5, 30)), 1)
            else:
                cp_id = f"EXT{uuid.uuid4().hex[:8].upper()}"
                cp_name = f"외부거래처_{cp_id[-6:]}"
                contagion = round(float(rng.uniform(3, 25)), 1)

            rel_type = relation_types[rng.integers(0, len(relation_types))]
            exposure = round(float(rng.uniform(0.05, 0.60)), 3)
            rid = f"SC{uuid.uuid4().hex[:10].upper()}"
            as_of = MONTHS_36[-1]
            supply_chain_rows.append((
                rid, sbid, cp_id, cp_name,
                rel_type, exposure, contagion, is_internal, as_of
            ))

    conn.executemany(
        "INSERT OR IGNORE INTO demo_ews_supply_chain "
        "(relation_id, borrower_id, counterparty_id, counterparty_name, relation_type, "
        "exposure_ratio, contagion_risk_score, is_internal_counterparty, as_of_ym) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        supply_chain_rows
    )
    conn.commit()
    print(f"    → 공급망 관계 {len(supply_chain_rows):,}건")

    # ── EWS 액션 ─────────────────────────────────────────────────────────────
    print("  [5/6] EWS 액션 및 부가 테이블 생성 중...")
    conn.execute("""
        CREATE TABLE demo_ews_action (
            action_id   TEXT PRIMARY KEY,
            borrower_id TEXT,
            ym          INTEGER,
            ews_grade   TEXT,
            action_type TEXT,
            action_date TEXT,
            rm_id       TEXT,
            status      TEXT,
            due_date    TEXT,
            note        TEXT
        )
    """)

    alert_rows = conn.execute("""
        SELECT s.borrower_id, s.ym, s.ews_grade, c.rm_id
        FROM demo_monthly_signal s
        JOIN demo_company c ON s.borrower_id = c.borrower_id
        WHERE s.ews_grade IN ('C','D')
    """).fetchall()

    action_types   = ["VISIT","CALL","DOCUMENT_REQUEST","MONITORING","LIMIT_REDUCTION","COLLATERAL_ADD"]
    action_weights = [0.30, 0.25, 0.20, 0.15, 0.07, 0.03]
    action_weights_default = [0.20, 0.15, 0.15, 0.10, 0.25, 0.15]
    statuses       = ["COMPLETED","IN_PROGRESS","OPEN","WAIVED"]
    status_weights = [0.55, 0.25, 0.15, 0.05]
    notes_pool     = ["현장 방문 점검 완료", "전화 상담 진행", "서류 제출 요청", "지속 모니터링",
                      "한도 축소 검토", "추가 담보 설정", "대표이사 면담", "재무제표 수신 완료",
                      "대출 조건 재협의", "연체 해소 확인", "사업계획서 제출 요청", "현장 실사 완료"]

    default_bids = set(r[0] for r in conn.execute(
        "SELECT borrower_id FROM demo_company WHERE scenario='DEFAULT'").fetchall())

    action_rows = []
    for row in alert_rows:
        if rng.random() > 0.6:
            continue
        bid, ym_val, grade, rm_id = row
        if rm_id is None:
            rm_id = all_rm_ids[rng.integers(0, len(all_rm_ids))]
        w      = action_weights_default if bid in default_bids else action_weights
        atype  = str(rng.choice(action_types, p=w))
        status = str(rng.choice(statuses, p=status_weights))
        ym_year, ym_month = divmod(ym_val, 100)
        act_day  = int(rng.integers(1, 28))
        act_date = f"{ym_year}-{ym_month:02d}-{act_day:02d}"
        due_days = int(rng.integers(7, 30))
        due_dt   = datetime.date(ym_year, ym_month, act_day) + datetime.timedelta(days=due_days)
        due_date = due_dt.strftime("%Y-%m-%d")
        note     = notes_pool[rng.integers(0, len(notes_pool))]
        aid      = f"A{uuid.uuid4().hex[:10].upper()}"
        action_rows.append((aid, bid, ym_val, grade, atype, act_date, rm_id, status, due_date, note))

    conn.executemany("INSERT INTO demo_ews_action VALUES (?,?,?,?,?,?,?,?,?,?)", action_rows)
    conn.commit()

    # ── 한도집중 ──────────────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE demo_concentration_limit (
            limit_id        TEXT PRIMARY KEY,
            dimension       TEXT,
            dimension_value TEXT,
            limit_pct       REAL,
            warning_pct     REAL
        )
    """)
    conc_rows = []
    industry_limits = {
        "K01A":15,"K01B":15,"K02":10,"K03":18,"K04":15,
        "K05":8, "K07":6, "K08":8, "K09":8, "K10":3,"K11":3,"K13":3
    }
    for ind, lim in industry_limits.items():
        conc_rows.append((f"LI_{ind}", "INDUSTRY", ind, float(lim), round(lim * 0.85, 2)))
    size_limits = {"대기업":25,"중견기업":30,"중소기업":50,"소기업":35}
    for sz, lim in size_limits.items():
        conc_rows.append((f"LS_{sz}", "FIRM_SIZE", sz, float(lim), round(lim * 0.85, 2)))
    region_limits = {"대구경북":60,"부산경남":35,"수도권":35}
    for reg, lim in region_limits.items():
        conc_rows.append((f"LR_{reg}", "REGION", reg, float(lim), round(lim * 0.85, 2)))
    conn.executemany("INSERT INTO demo_concentration_limit VALUES (?,?,?,?,?)", conc_rows)

    # ── 스트레스 시나리오 ─────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE demo_stress_scenario (
            scenario_id             TEXT PRIMARY KEY,
            scenario_name           TEXT,
            description             TEXT,
            rate_shock_bps          INTEGER,
            gdp_shock_pct           REAL,
            credit_spread_bps       INTEGER,
            base_pd_multiplier      REAL,
            base_lgd_multiplier     REAL,
            expected_npl_ratio_pct  REAL,
            expected_ecl_change_pct REAL
        )
    """)
    conn.executemany("INSERT INTO demo_stress_scenario VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ("BASE",   "기준 시나리오",    "현행 경제 여건 유지",
         0,    0.0,  0,   1.0, 1.0, 12.0,   0.0),
        ("ADVERSE","부정적 시나리오", "금리 인상 및 경기 둔화",
         200, -2.0, 150,  1.8, 1.3, 21.0,  65.0),
        ("SEVERE", "심각 시나리오",   "금융 위기 수준 충격",
         400, -5.0, 350,  3.2, 1.6, 38.0, 180.0),
    ])

    # ── 월별 보고서 ──────────────────────────────────────────────────────────
    print("  [6/6] 월별 집계 보고서 생성 중...")
    conn.execute("""
        CREATE TABLE demo_monthly_report (
            report_ym           INTEGER PRIMARY KEY,
            total_companies     INTEGER,
            grade_a_cnt         INTEGER,
            grade_b_cnt         INTEGER,
            grade_c_cnt         INTEGER,
            grade_d_cnt         INTEGER,
            upgraded_cnt        INTEGER,
            downgraded_cnt      INTEGER,
            new_alert_cnt       INTEGER,
            resolved_alert_cnt  INTEGER,
            total_exposure_억    REAL,
            alert_exposure_억    REAL,
            action_completion_pct REAL
        )
    """)

    report_months = [ym for ym in MONTHS_36 if ym >= 202302]
    prev_grades   = {}
    grade_order   = {"A": 3, "B": 2, "C": 1, "D": 0}

    for ym_val in report_months:
        grade_rows = conn.execute(
            "SELECT ews_grade, COUNT(*) FROM demo_monthly_signal WHERE ym=? GROUP BY ews_grade",
            (ym_val,)
        ).fetchall()
        grade_map = {r[0]: r[1] for r in grade_rows}
        total = sum(grade_map.values())
        a_cnt = grade_map.get("A", 0)
        b_cnt = grade_map.get("B", 0)
        c_cnt = grade_map.get("C", 0)
        d_cnt = grade_map.get("D", 0)

        cur_grades = {r[0]: r[1] for r in conn.execute(
            "SELECT borrower_id, ews_grade FROM demo_monthly_signal WHERE ym=?", (ym_val,)
        ).fetchall()}

        up_cnt = dn_cnt = new_alert = resolved = 0
        for bid, cur_g in cur_grades.items():
            prev_g = prev_grades.get(bid)
            if prev_g:
                if grade_order.get(cur_g, 0) > grade_order.get(prev_g, 0):
                    up_cnt += 1
                elif grade_order.get(cur_g, 0) < grade_order.get(prev_g, 0):
                    dn_cnt += 1
                if prev_g in ("A", "B") and cur_g in ("C", "D"):
                    new_alert += 1
                if prev_g in ("C", "D") and cur_g in ("A", "B"):
                    resolved += 1
        prev_grades = cur_grades

        total_exp = round(float(conn.execute(
            "SELECT SUM(outstanding_amount_억) FROM demo_facility").fetchone()[0] or 0), 1)
        alert_exp = round(float(conn.execute("""
            SELECT SUM(f.outstanding_amount_억)
            FROM demo_facility f
            JOIN demo_monthly_signal s ON f.borrower_id=s.borrower_id
            WHERE s.ym=? AND s.ews_grade IN ('C','D')
        """, (ym_val,)).fetchone()[0] or 0), 1)
        act_row  = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) FROM demo_ews_action WHERE ym=?",
            (ym_val,)
        ).fetchone()
        act_total = act_row[0] or 0
        act_done  = act_row[1] or 0
        comp_pct  = round(act_done / act_total * 100, 1) if act_total > 0 else 0.0

        conn.execute(
            "INSERT INTO demo_monthly_report VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ym_val, total, a_cnt, b_cnt, c_cnt, d_cnt,
             up_cnt, dn_cnt, new_alert, resolved,
             total_exp, alert_exp, comp_pct)
        )

    conn.commit()
    return conn


def main():
    t0  = time.time()
    rng = np.random.default_rng(SEED)
    print("=" * 60)
    print(" EWS 데모 데이터셋 생성 (v5 — im뱅크 특성 반영)")
    print(f" 기간: {YM_START} ~ {YM_END} ({len(MONTHS_36)}개월)")
    print(f" 기업: {N_TOTAL:,}개  (정상 {N_NORMAL:,} / 부실 {N_DEFAULT:,} / 회복 {N_RECOVERY:,})")
    print(f" 지역: 대구경북 50% / 부산경남 25% / 수도권 25%")
    print(f" RM  : {len(RM_BRANCHES) * RM_PER_BRANCH}명 ({len(RM_BRANCHES)}개 지점)")
    print("=" * 60)

    conn = build_demo_db(rng)

    tables = [
        "demo_company", "demo_monthly_signal", "demo_answer_key",
        "demo_facility", "demo_collateral", "demo_asset_class",
        "demo_ecl", "demo_credit_rating", "demo_covenant",
        "demo_workout", "demo_collateral_valuation", "demo_recovery_scenario",
        "demo_rm", "demo_ews_action", "demo_concentration_limit",
        "demo_stress_scenario", "demo_monthly_report",
        "demo_ews_transaction", "demo_ews_public_event",
        "demo_ews_news_monthly", "demo_ews_market_signal",
        "demo_ews_supply_chain",
    ]

    print("\n[테이블 행 수]")
    for t in tables:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<32}: {cnt:>10,} 행")

    db_size = DB_PATH.stat().st_size / (1024 ** 2)
    conn.close()
    print(f"\n  저장: {DB_PATH}  ({db_size:.1f} MB)")
    print(f"  소요: {round(time.time() - t0, 1)}초")


if __name__ == "__main__":
    main()
