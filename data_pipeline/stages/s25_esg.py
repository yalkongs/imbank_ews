"""
s25_esg.py — ESG 평가 데이터 생성 (v22 신규)

테이블:
  fact_esg_assessment — 연도별 ESG 평가 (E/S/G 점수 및 PD 조정)

E (환경):
  - carbon_intensity     : 탄소 집약도 (tCO2/억원 매출)
  - energy_efficiency    : 에너지 효율 점수 (0~100)
  - environmental_incidents: 환경 사건 건수
  - green_revenue_pct    : 녹색 매출 비중 (%)

S (사회):
  - employee_safety_score : 산업재해율 역수 점수
  - labor_practices_score : 노동관행 점수
  - community_impact_score: 지역사회 기여 점수

G (지배구조):
  - board_independence   : 이사회 독립성 (0~1)
  - ownership_transparency: 소유권 투명성 (0~1)
  - ethics_compliance_score: 윤리준수 점수

종합: esg_score, esg_grade (A~E), pd_adjustment (PD 할증/할인)
"""
import time
import numpy as np
from config.macro import YM_START, YM_END
from config.companies import get_size_code

# 업종별 탄소 집약도 기준 (tCO2/억원)
IND_CARBON = {
    "K00": 8.0,   # 농림어업
    "K01A": 15.0, # 일반제조
    "K01B": 8.0,  # 첨단제조
    "K02": 20.0,  # 건설
    "K03": 5.0,   # 도소매
    "K04": 12.0,  # 운수
    "K05": 3.0,   # IT
    "K06": 2.0,   # 금융보험
    "K07": 6.0,   # 부동산
    "K08": 4.0,   # 사업서비스
    "K09": 3.0,   # 교육
    "K10": 5.0,   # 의료복지
    "K11": 7.0,   # 숙박음식
    "K12": 5.0,   # 기타서비스
    "K13": 25.0,  # 에너지환경 (높지만 녹색매출도 높음)
}

# 업종별 ESG 기초 점수 (0~100)
IND_ESG_BASE = {
    "K00": 55, "K01A": 50, "K01B": 68, "K02": 45, "K03": 62,
    "K04": 55, "K05": 75, "K06": 70, "K07": 60, "K08": 65,
    "K09": 72, "K10": 70, "K11": 60, "K12": 62, "K13": 58,
}

ESG_GRADE_MAP = [
    (80, "A"), (65, "B"), (50, "C"), (35, "D"), (0, "E")
]

def _grade(score):
    for threshold, grade in ESG_GRADE_MAP:
        if score >= threshold:
            return grade
    return "E"


def s25_esg(conn, companies, rng):
    t0 = time.time()
    print("  [s25] ESG 평가 데이터 생성", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_esg_assessment")
    conn.execute("""
        CREATE TABLE fact_esg_assessment (
            assessment_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id          TEXT NOT NULL,
            fiscal_year          INTEGER NOT NULL,
            -- E 지표
            e_score              REAL,
            carbon_intensity     REAL,
            energy_efficiency    REAL,
            environmental_incidents INTEGER,
            green_revenue_pct    REAL,
            -- S 지표
            s_score              REAL,
            employee_safety_score REAL,
            labor_practices_score REAL,
            community_impact_score REAL,
            -- G 지표
            g_score              REAL,
            board_independence   REAL,
            ownership_transparency REAL,
            ethics_compliance_score REAL,
            -- 종합
            esg_score            REAL,
            esg_grade            TEXT,
            esg_trend            TEXT,
            pd_adjustment        REAL,
            pricing_adjustment_bp REAL,
            UNIQUE(borrower_id, fiscal_year)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_esg_bid ON fact_esg_assessment(borrower_id)")

    years = list(range(YM_START // 100, YM_END // 100 + 1))

    rows = []
    BATCH = 30_000

    for c in companies:
        bid = c['borrower_id']
        default_flag = c['default_flag']
        exit_ym = c.get('exit_ym') or (YM_END + 1)
        entry_ym = c.get('entry_ym') or YM_START
        firm_size = get_size_code(c.get('firm_size_cd', '소기업'))
        ind = c.get('industry_cd', 'K01A')

        base_esg = IND_ESG_BASE.get(ind, 60) + {"L": 10, "M": 3, "S": -5}.get(firm_size, 0)
        base_carbon = IND_CARBON.get(ind, 8.0)

        # 기업 고유 ESG 품질 계수 (0.7~1.3)
        esg_quality = rng.uniform(0.7, 1.3)
        prev_esg = None

        for yr in years:
            entry_year = entry_ym // 100
            if yr < entry_year or yr * 100 >= exit_ym:
                continue

            # 부도 기업은 ESG 악화
            months_to_exit = ((exit_ym - yr * 100 - 12) if default_flag and exit_ym <= YM_END else 999)
            deterioration = max(0.0, 1.0 - months_to_exit / 36.0) if months_to_exit < 36 else 0.0

            # 시간에 따른 ESG 개선 트렌드 (2019년 이후 ESG 주목)
            time_bonus = max(0, (yr - 2019) * 1.5)

            # E 지표
            carbon = float(np.clip(
                base_carbon / esg_quality * (1 + deterioration * 0.3) + rng.normal(0, 1.5),
                0.1, 100.0
            ))
            energy_eff = float(np.clip(
                60 + time_bonus + rng.normal(0, 8) - deterioration * 15,
                0, 100
            ))
            env_incidents = int(np.clip(rng.poisson(1.5 * (1 + deterioration * 2)), 0, 20))
            green_rev = float(np.clip(
                (20 if ind == "K13" else 5) + time_bonus * 0.5 + rng.normal(0, 3),
                0, 80
            ))

            e_score = float(np.clip(
                80 - carbon * 0.5 + energy_eff * 0.3 - env_incidents * 3 + green_rev * 0.2
                + time_bonus * 0.5, 0, 100
            ))

            # S 지표
            safety = float(np.clip(
                70 + rng.normal(0, 10) - deterioration * 20 + time_bonus * 0.3,
                0, 100
            ))
            labor = float(np.clip(
                65 + rng.normal(0, 8) - deterioration * 15 + {"L": 5, "M": 2, "S": -3}.get(firm_size, 0),
                0, 100
            ))
            community = float(np.clip(
                55 + rng.normal(0, 10) + {"L": 10, "M": 5, "S": 0}.get(firm_size, 0),
                0, 100
            ))
            s_score = float(np.clip((safety + labor + community) / 3, 0, 100))

            # G 지표
            board_indep = float(np.clip(
                (0.5 if firm_size == "S" else 0.7) + rng.normal(0, 0.08) - deterioration * 0.2,
                0, 1.0
            ))
            own_trans = float(np.clip(
                (0.6 if firm_size == "L" else 0.4) + rng.normal(0, 0.1) + time_bonus * 0.01,
                0, 1.0
            ))
            ethics = float(np.clip(
                65 + rng.normal(0, 10) - deterioration * 20 + time_bonus * 0.5,
                0, 100
            ))
            g_score = float(np.clip(
                board_indep * 35 + own_trans * 30 + ethics * 0.35,
                0, 100
            ))

            # 종합 ESG (E:40, S:30, G:30)
            esg_score = float(np.clip(
                e_score * 0.40 + s_score * 0.30 + g_score * 0.30
                + rng.normal(0, 2),
                0, 100
            ))

            esg_grade = _grade(esg_score)

            # 추세
            if prev_esg is None:
                trend = "STABLE"
            elif esg_score > prev_esg + 3:
                trend = "IMPROVING"
            elif esg_score < prev_esg - 3:
                trend = "DECLINING"
            else:
                trend = "STABLE"
            prev_esg = esg_score

            # PD 조정: ESG가 낮으면 PD 할증, 높으면 할인
            # E등급: +0.5% PD, A등급: -0.2% PD
            pd_adj = {"A": -0.002, "B": -0.001, "C": 0.0, "D": 0.002, "E": 0.005}.get(esg_grade, 0.0)
            pd_adj = round(pd_adj + rng.normal(0, 0.001), 5)

            # 가격 조정 (bp)
            pricing_adj = round(pd_adj * 1000 + rng.normal(0, 2), 1)

            rows.append((
                bid, yr,
                round(e_score, 2), round(carbon, 3), round(energy_eff, 2),
                env_incidents, round(green_rev, 2),
                round(s_score, 2), round(safety, 2), round(labor, 2), round(community, 2),
                round(g_score, 2), round(board_indep, 4), round(own_trans, 4), round(ethics, 2),
                round(esg_score, 2), esg_grade, trend,
                round(pd_adj, 5), round(pricing_adj, 1),
            ))

            if len(rows) >= BATCH:
                conn.executemany("""
                    INSERT OR IGNORE INTO fact_esg_assessment
                      (borrower_id, fiscal_year,
                       e_score, carbon_intensity, energy_efficiency,
                       environmental_incidents, green_revenue_pct,
                       s_score, employee_safety_score, labor_practices_score, community_impact_score,
                       g_score, board_independence, ownership_transparency, ethics_compliance_score,
                       esg_score, esg_grade, esg_trend, pd_adjustment, pricing_adjustment_bp)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, rows)
                conn.commit()
                rows = []

    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO fact_esg_assessment
              (borrower_id, fiscal_year,
               e_score, carbon_intensity, energy_efficiency,
               environmental_incidents, green_revenue_pct,
               s_score, employee_safety_score, labor_practices_score, community_impact_score,
               g_score, board_independence, ownership_transparency, ethics_compliance_score,
               esg_score, esg_grade, esg_trend, pd_adjustment, pricing_adjustment_bp)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM fact_esg_assessment").fetchone()[0]
    grade_dist = conn.execute(
        "SELECT esg_grade, COUNT(*) FROM fact_esg_assessment GROUP BY 1 ORDER BY 1"
    ).fetchall()
    elapsed = round(time.time() - t0, 1)
    print(f"    fact_esg_assessment: {total:,}행", flush=True)
    for gr, cnt in grade_dist:
        print(f"      {gr}: {cnt:,}행", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
