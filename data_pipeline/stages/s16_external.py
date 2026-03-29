"""
s16_external.py — 외부 데이터 피처 생성 (v21 신규)

3개 테이블 생성:
  - fact_legal_risk        (소송/법적 리스크)
  - fact_supply_chain      (공급망)
  - fact_governance_change (지배구조/경영진 변동)

그리고 ml_feature_label에 27개 신규 컬럼을 추가한다.
"""
import time

import numpy as np

from config.macro import MONTHS, YM_INDEX, PHASE_MAP, ym_add, ym_diff


SEED = 42
BATCH_SIZE = 500  # 월별 배치 처리 기업 수


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def _months_before_default(company, ym):
    """부도 전 몇 개월인지 반환 (부도 없거나 이미 지났으면 None)"""
    if not company['default_flag']:
        return None
    d_ym = company['default_ym_internal']
    if d_ym is None:
        return None
    diff = ym_diff(d_ym, ym)  # d_ym - ym (양수면 아직 부도 안남)
    if diff < 0:
        return None  # 이미 부도 지남
    return diff


def s16_external_data(conn, companies):
    section("S16 외부 데이터 피처 (v21 신규)")
    t0 = time.time()

    rng = np.random.default_rng(SEED)

    # ── 기업별 고정 파라미터 사전 계산 ─────────────────────────────────────
    n_companies = len(companies)
    log(f"기업 수: {n_companies:,}")

    # 기업 인덱스 매핑
    bid_to_idx = {c['borrower_id']: i for i, c in enumerate(companies)}

    # 기업별 고정 파라미터 (numpy 배열로 관리)
    # 업종 코드 → 공급망 HHI 기반값
    IND_HHI_BASE = {
        'K01A': 0.22, 'K01B': 0.18,
        'K02':  0.22,
        'K03':  0.35,
        'K04':  0.30,
        'K05':  0.42,
        'K06':  0.28,
        'K07A': 0.45, 'K07B': 0.48,
        'K08':  0.32,
        'K09':  0.35,
        'K10':  0.40,
        'K11':  0.45,
        'K12':  0.38,
        'K13':  0.30,
    }
    # 업종별 수입의존도 기본값
    IND_IMPORT_BASE = {
        'K01A': 0.45, 'K01B': 0.35,
        'K02':  0.20,
        'K03':  0.30,
        'K04':  0.25,
        'K05':  0.50,
        'K06':  0.15,
        'K07A': 0.10, 'K07B': 0.08,
        'K08':  0.20,
        'K09':  0.30,
        'K10':  0.35,
        'K11':  0.05,
        'K12':  0.25,
        'K13':  0.40,
    }

    # 기업별 고정 소유집중도 (30~90%)
    ownership_base = rng.uniform(30, 90, size=n_companies).astype(np.float32)

    # 기업별 고정 HHI 기반값
    hhi_base_arr = np.array([
        IND_HHI_BASE.get(c['industry_cd'], 0.35) for c in companies
    ], dtype=np.float32)

    # 기업별 고정 import_dependency 기반값
    import_base_arr = np.array([
        IND_IMPORT_BASE.get(c['industry_cd'], 0.25) for c in companies
    ], dtype=np.float32)

    # 기업별 고정 top_customer_revenue_ratio 기반값 (0.1~0.9)
    top_cust_base = rng.uniform(0.1, 0.9, size=n_companies).astype(np.float32)

    # 기업별 export_concentration (0~1)
    export_conc_base = rng.uniform(0.0, 0.8, size=n_companies).astype(np.float32)

    # ── 테이블 비우기 (재실행 대비) ─────────────────────────────────────────
    conn.execute("DELETE FROM fact_legal_risk")
    conn.execute("DELETE FROM fact_supply_chain")
    conn.execute("DELETE FROM fact_governance_change")
    conn.commit()

    # ── 월별 배치 생성 ──────────────────────────────────────────────────────
    legal_buf = []
    supply_buf = []
    gov_buf = []

    N_MONTHS = len(MONTHS)
    INSERT_EVERY = 10  # 10개월마다 flush

    for m_idx, ym in enumerate(MONTHS):
        if m_idx % 20 == 0:
            log(f"  월 {ym} 처리 중... ({m_idx + 1}/{N_MONTHS})")

        # 이 월의 거시 국면 정보
        phase_info = PHASE_MAP.get(ym, ('NORMAL', 0.2, 0.8, 2.0, 0.3, 1200))
        phase_stress = float(phase_info[1])
        phase_mf = float(phase_info[4])
        # 경기 국면 반영 지표: trade_balance_change_pct 범위
        # 스트레스 높을수록 무역수지 악화
        tb_center = -20.0 * phase_stress + 10.0 * max(0, phase_mf)

        # 각 기업에 대해 이 월의 데이터 생성
        for co in companies:
            bid = co['borrower_id']
            entry_ym = co['entry_ym']
            eff_exit = co['_eff_exit']

            # 관측 기간 밖이면 스킵
            if ym < entry_ym or ym > eff_exit:
                continue

            idx = bid_to_idx[bid]
            is_default = bool(co['default_flag'])
            mbd = _months_before_default(co, ym)  # 부도 전 N개월 (None이면 비해당)

            # 위험도 계수 (0~1): 부도 기업의 부도 전 기간에 높아짐
            risk_factor = 0.0
            if is_default and mbd is not None:
                if mbd <= 3:
                    risk_factor = 0.85
                elif mbd <= 6:
                    risk_factor = 0.65
                elif mbd <= 12:
                    risk_factor = 0.40
                else:
                    risk_factor = 0.15
            elif is_default:
                # 부도 이후 (관측 종료 구간)
                risk_factor = 0.05

            # ── 법적 리스크 ─────────────────────────────────────────────────
            # lawsuit_count_12m: 포아송 분포, 위험 기업은 lambda 높음
            lam_lawsuit = 0.05 + 2.5 * risk_factor
            lawsuit_count = int(rng.poisson(lam_lawsuit))

            # lawsuit_amount_억
            if lawsuit_count > 0:
                lawsuit_amt = float(rng.exponential(1.0 + 4.0 * risk_factor) * lawsuit_count)
                lawsuit_amt = min(lawsuit_amt, 50.0)
            else:
                lawsuit_amt = 0.0

            # seizure_flag: 위험기업 부도 전 3개월 내 30%
            seizure_flag = 0
            if mbd is not None and mbd <= 3:
                seizure_flag = 1 if rng.random() < 0.30 else 0
            elif risk_factor > 0.3:
                seizure_flag = 1 if rng.random() < 0.05 else 0

            seizure_count = int(rng.integers(1, 4)) if seizure_flag else 0

            # tax_lien_amount_억: tax_arrears와 연관, 0~10억
            tax_lien = float(rng.exponential(0.5 + 3.0 * risk_factor))
            tax_lien = min(tax_lien, 10.0) if risk_factor > 0.1 else 0.0

            # bankruptcy_filing_flag: 부도 직전 월에만 5%
            bk_flag = 0
            if mbd is not None and mbd == 0:
                bk_flag = 1 if rng.random() < 0.05 else 0

            # adverse_court_ruling_flag: 위험기업 2%
            adverse_flag = 0
            if risk_factor > 0.3:
                adverse_flag = 1 if rng.random() < 0.02 else 0

            # legal_risk_score: 가중합 → sigmoid
            legal_raw = (
                0.20 * min(lawsuit_count / 5.0, 1.0)
                + 0.15 * min(lawsuit_amt / 50.0, 1.0)
                + 0.20 * seizure_flag
                + 0.15 * min(tax_lien / 10.0, 1.0)
                + 0.15 * bk_flag
                + 0.15 * adverse_flag
                - 2.0
            )
            legal_risk_score = float(_sigmoid(legal_raw + 4.0 * risk_factor))

            legal_buf.append((
                bid, ym,
                lawsuit_count,
                round(lawsuit_amt, 2),
                seizure_flag,
                seizure_count,
                round(tax_lien, 2),
                bk_flag,
                adverse_flag,
                round(legal_risk_score, 4),
            ))

            # ── 공급망 ───────────────────────────────────────────────────────
            hhi_base = float(hhi_base_arr[idx])
            # HHI에 약간의 월별 노이즈 + 위험기업 높음
            supplier_hhi = float(np.clip(
                hhi_base + rng.normal(0, 0.05) + 0.2 * risk_factor,
                0.1, 1.0
            ))

            top_cust = float(np.clip(
                float(top_cust_base[idx]) + rng.normal(0, 0.03),
                0.1, 0.9
            ))

            # key_customer_default_flag: 위험기업 부도 전 6개월 내 10%
            kc_def_flag = 0
            if mbd is not None and mbd <= 6:
                kc_def_flag = 1 if rng.random() < 0.10 else 0

            # supply_chain_disruption_score [0,1]
            scd_raw = 0.3 * risk_factor + 0.2 * (supplier_hhi - 0.3) + rng.uniform(0, 0.2)
            scd_score = float(np.clip(scd_raw, 0.0, 1.0))

            import_dep = float(np.clip(
                float(import_base_arr[idx]) + rng.normal(0, 0.05),
                0.0, 0.8
            ))

            # trade_balance_change_pct: 경기 국면 반영 [-50, 50]
            tb_change = float(np.clip(
                tb_center + rng.normal(0, 15.0) - 20.0 * risk_factor,
                -50.0, 50.0
            ))

            export_conc = float(np.clip(
                float(export_conc_base[idx]) + rng.normal(0, 0.05),
                0.0, 1.0
            ))

            # supply_chain_risk_score: 가중합 → sigmoid
            sc_raw = (
                0.25 * supplier_hhi
                + 0.20 * top_cust
                + 0.15 * kc_def_flag
                + 0.15 * scd_score
                + 0.10 * import_dep
                + 0.10 * max(0, -tb_change / 50.0)
                + 0.05 * export_conc
                - 0.5
            )
            supply_chain_risk = float(_sigmoid(sc_raw * 2.0 + 2.0 * risk_factor))

            supply_buf.append((
                bid, ym,
                round(supplier_hhi, 4),
                round(top_cust, 4),
                kc_def_flag,
                round(scd_score, 4),
                round(import_dep, 4),
                round(tb_change, 2),
                round(export_conc, 4),
                round(supply_chain_risk, 4),
            ))

            # ── 지배구조/경영진 ───────────────────────────────────────────────
            # ceo_change_flag: 연간 3%, 위험기업 부도 전 12개월 내 15%
            ceo_annual_p = 0.03 / 12.0  # 월 확률
            if mbd is not None and mbd <= 12:
                ceo_p = 0.15 / 12.0
            else:
                ceo_p = ceo_annual_p
            ceo_flag = 1 if rng.random() < ceo_p else 0

            # ceo_change_count_12m: 0~3 누적 근사
            # 실제로는 과거 12개월 집계여야 하나, 합성 데이터이므로 단순 시뮬레이션
            if risk_factor > 0.3:
                ceo_count = int(rng.choice([0, 1, 2, 3], p=[0.60, 0.25, 0.10, 0.05]))
            else:
                ceo_count = int(rng.choice([0, 1, 2], p=[0.90, 0.08, 0.02]))

            # director_resignation_count_12m
            dir_p = 0.20 if risk_factor > 0.3 else 0.05
            if rng.random() < dir_p:
                dir_count = int(rng.integers(1, 4)) if risk_factor > 0.3 else 1
            else:
                dir_count = 0

            # major_shareholder_change_flag
            ms_p = 0.08 / 12.0 if is_default else 0.02 / 12.0
            ms_flag = 1 if rng.random() < ms_p else 0

            # ownership_concentration_pct (기업별 고정 + 약간의 변동)
            own_conc = float(np.clip(
                float(ownership_base[idx]) + rng.normal(0, 1.5),
                30.0, 90.0
            ))

            # embezzlement_allegation_flag: 위험기업 부도 전 6개월 내 5%
            emb_flag = 0
            if mbd is not None and mbd <= 6:
                emb_flag = 1 if rng.random() < 0.05 else 0

            # audit_opinion_qualified_flag: 위험기업 부도 전 12개월 내 20%
            audit_flag = 0
            if mbd is not None and mbd <= 12:
                audit_flag = 1 if rng.random() < 0.20 else 0

            # employee_count_change_pct: [-30, +20]%, 경기 국면 반영
            # 위험기업 -20~-30%
            emp_center = -5.0 * phase_stress + 3.0 * max(0, phase_mf)
            if risk_factor > 0.4:
                emp_chg = float(np.clip(rng.normal(-25.0, 5.0), -30.0, -15.0))
            else:
                emp_chg = float(np.clip(rng.normal(emp_center, 8.0), -30.0, 20.0))

            # social_insurance_dropout_flag: emp_chg < -15%이면 50%
            si_dropout = 0
            if emp_chg < -15.0:
                si_dropout = 1 if rng.random() < 0.50 else 0

            # business_address_change_flag: 연간 5%, 위험기업 부도 전 12개월 내 15%
            ba_p_month = 0.15 / 12.0 if (mbd is not None and mbd <= 12) else 0.05 / 12.0
            ba_flag = 1 if rng.random() < ba_p_month else 0

            # governance_risk_score: 가중합 → sigmoid
            gov_raw = (
                0.15 * ceo_flag
                + 0.12 * min(ceo_count / 3.0, 1.0)
                + 0.10 * min(dir_count / 3.0, 1.0)
                + 0.10 * ms_flag
                + 0.08 * (own_conc / 90.0)
                + 0.15 * emb_flag
                + 0.20 * audit_flag
                + 0.05 * si_dropout
                + 0.05 * ba_flag
                - 0.3
            )
            gov_risk_score = float(_sigmoid(gov_raw * 3.0 + 2.5 * risk_factor))

            gov_buf.append((
                bid, ym,
                ceo_flag,
                ceo_count,
                dir_count,
                ms_flag,
                round(own_conc, 2),
                emb_flag,
                audit_flag,
                round(gov_risk_score, 4),
                round(emp_chg, 2),
                si_dropout,
                ba_flag,
            ))

        # 주기적 flush
        if (m_idx + 1) % INSERT_EVERY == 0 or m_idx == N_MONTHS - 1:
            if legal_buf:
                conn.executemany(
                    "INSERT OR REPLACE INTO fact_legal_risk VALUES (?,?,?,?,?,?,?,?,?,?)",
                    legal_buf
                )
                legal_buf.clear()
            if supply_buf:
                conn.executemany(
                    "INSERT OR REPLACE INTO fact_supply_chain VALUES (?,?,?,?,?,?,?,?,?,?)",
                    supply_buf
                )
                supply_buf.clear()
            if gov_buf:
                conn.executemany(
                    "INSERT OR REPLACE INTO fact_governance_change VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    gov_buf
                )
                gov_buf.clear()
            conn.commit()

    # 잔여 flush
    if legal_buf:
        conn.executemany(
            "INSERT OR REPLACE INTO fact_legal_risk VALUES (?,?,?,?,?,?,?,?,?,?)",
            legal_buf
        )
    if supply_buf:
        conn.executemany(
            "INSERT OR REPLACE INTO fact_supply_chain VALUES (?,?,?,?,?,?,?,?,?,?)",
            supply_buf
        )
    if gov_buf:
        conn.executemany(
            "INSERT OR REPLACE INTO fact_governance_change VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            gov_buf
        )
    conn.commit()

    # 행수 확인
    n_legal = conn.execute("SELECT COUNT(*) FROM fact_legal_risk").fetchone()[0]
    n_supply = conn.execute("SELECT COUNT(*) FROM fact_supply_chain").fetchone()[0]
    n_gov = conn.execute("SELECT COUNT(*) FROM fact_governance_change").fetchone()[0]
    log(f"fact_legal_risk: {n_legal:,}행")
    log(f"fact_supply_chain: {n_supply:,}행")
    log(f"fact_governance_change: {n_gov:,}행")

    # ── ml_feature_label에 신규 컬럼 추가 ─────────────────────────────────
    log("ml_feature_label 신규 컬럼 추가 중...")

    new_columns = [
        # 법적 리스크
        ("lawsuit_count_12m",         "INTEGER DEFAULT 0"),
        ("lawsuit_amount_억",          "REAL    DEFAULT 0.0"),
        ("seizure_flag",               "INTEGER DEFAULT 0"),
        ("seizure_count_12m",          "INTEGER DEFAULT 0"),
        ("tax_lien_amount_억",          "REAL    DEFAULT 0.0"),
        ("bankruptcy_filing_flag",     "INTEGER DEFAULT 0"),
        ("adverse_court_ruling_flag",  "INTEGER DEFAULT 0"),
        ("legal_risk_score",           "REAL    DEFAULT 0.0"),
        # 공급망
        ("supplier_hhi",               "REAL    DEFAULT 0.0"),
        ("top_customer_revenue_ratio", "REAL    DEFAULT 0.0"),
        ("key_customer_default_flag",  "INTEGER DEFAULT 0"),
        ("supply_chain_disruption_score", "REAL DEFAULT 0.0"),
        ("import_dependency_ratio",    "REAL    DEFAULT 0.0"),
        ("trade_balance_change_pct",   "REAL    DEFAULT 0.0"),
        ("export_concentration_idx",   "REAL    DEFAULT 0.0"),
        ("supply_chain_risk_score",    "REAL    DEFAULT 0.0"),
        # 지배구조
        ("ceo_change_flag",                "INTEGER DEFAULT 0"),
        ("ceo_change_count_12m",           "INTEGER DEFAULT 0"),
        ("director_resignation_count_12m", "INTEGER DEFAULT 0"),
        ("major_shareholder_change_flag",  "INTEGER DEFAULT 0"),
        ("ownership_concentration_pct",    "REAL    DEFAULT 0.0"),
        ("embezzlement_allegation_flag",   "INTEGER DEFAULT 0"),
        ("audit_opinion_qualified_flag",   "INTEGER DEFAULT 0"),
        ("governance_risk_score",          "REAL    DEFAULT 0.0"),
        ("employee_count_change_pct",      "REAL    DEFAULT 0.0"),
        ("social_insurance_dropout_flag",  "INTEGER DEFAULT 0"),
        ("business_address_change_flag",   "INTEGER DEFAULT 0"),
    ]

    # 기존 컬럼 확인 후 없는 것만 추가
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(ml_feature_label)").fetchall()}
    for col_name, col_def in new_columns:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE ml_feature_label ADD COLUMN {col_name} {col_def}")
    conn.commit()
    log("ml_feature_label 컬럼 추가 완료")

    # ── ml_feature_label UPDATE (fact 테이블에서 JOIN) ──────────────────────
    log("ml_feature_label UPDATE — 법적 리스크...")
    conn.execute("""
        UPDATE ml_feature_label
        SET
            lawsuit_count_12m         = (SELECT l.lawsuit_count_12m         FROM fact_legal_risk l WHERE l.borrower_id = ml_feature_label.borrower_id AND l.ym = ml_feature_label.ym),
            lawsuit_amount_억          = (SELECT l.lawsuit_amount_억          FROM fact_legal_risk l WHERE l.borrower_id = ml_feature_label.borrower_id AND l.ym = ml_feature_label.ym),
            seizure_flag               = (SELECT l.seizure_flag               FROM fact_legal_risk l WHERE l.borrower_id = ml_feature_label.borrower_id AND l.ym = ml_feature_label.ym),
            seizure_count_12m          = (SELECT l.seizure_count_12m          FROM fact_legal_risk l WHERE l.borrower_id = ml_feature_label.borrower_id AND l.ym = ml_feature_label.ym),
            tax_lien_amount_억          = (SELECT l.tax_lien_amount_억          FROM fact_legal_risk l WHERE l.borrower_id = ml_feature_label.borrower_id AND l.ym = ml_feature_label.ym),
            bankruptcy_filing_flag     = (SELECT l.bankruptcy_filing_flag     FROM fact_legal_risk l WHERE l.borrower_id = ml_feature_label.borrower_id AND l.ym = ml_feature_label.ym),
            adverse_court_ruling_flag  = (SELECT l.adverse_court_ruling_flag  FROM fact_legal_risk l WHERE l.borrower_id = ml_feature_label.borrower_id AND l.ym = ml_feature_label.ym),
            legal_risk_score           = (SELECT l.legal_risk_score           FROM fact_legal_risk l WHERE l.borrower_id = ml_feature_label.borrower_id AND l.ym = ml_feature_label.ym)
        WHERE EXISTS (SELECT 1 FROM fact_legal_risk l WHERE l.borrower_id = ml_feature_label.borrower_id AND l.ym = ml_feature_label.ym)
    """)
    conn.commit()

    log("ml_feature_label UPDATE — 공급망...")
    conn.execute("""
        UPDATE ml_feature_label
        SET
            supplier_hhi                   = (SELECT s.supplier_hhi                   FROM fact_supply_chain s WHERE s.borrower_id = ml_feature_label.borrower_id AND s.ym = ml_feature_label.ym),
            top_customer_revenue_ratio     = (SELECT s.top_customer_revenue_ratio     FROM fact_supply_chain s WHERE s.borrower_id = ml_feature_label.borrower_id AND s.ym = ml_feature_label.ym),
            key_customer_default_flag      = (SELECT s.key_customer_default_flag      FROM fact_supply_chain s WHERE s.borrower_id = ml_feature_label.borrower_id AND s.ym = ml_feature_label.ym),
            supply_chain_disruption_score  = (SELECT s.supply_chain_disruption_score  FROM fact_supply_chain s WHERE s.borrower_id = ml_feature_label.borrower_id AND s.ym = ml_feature_label.ym),
            import_dependency_ratio        = (SELECT s.import_dependency_ratio        FROM fact_supply_chain s WHERE s.borrower_id = ml_feature_label.borrower_id AND s.ym = ml_feature_label.ym),
            trade_balance_change_pct       = (SELECT s.trade_balance_change_pct       FROM fact_supply_chain s WHERE s.borrower_id = ml_feature_label.borrower_id AND s.ym = ml_feature_label.ym),
            export_concentration_idx       = (SELECT s.export_concentration_idx       FROM fact_supply_chain s WHERE s.borrower_id = ml_feature_label.borrower_id AND s.ym = ml_feature_label.ym),
            supply_chain_risk_score        = (SELECT s.supply_chain_risk_score        FROM fact_supply_chain s WHERE s.borrower_id = ml_feature_label.borrower_id AND s.ym = ml_feature_label.ym)
        WHERE EXISTS (SELECT 1 FROM fact_supply_chain s WHERE s.borrower_id = ml_feature_label.borrower_id AND s.ym = ml_feature_label.ym)
    """)
    conn.commit()

    log("ml_feature_label UPDATE — 지배구조...")
    conn.execute("""
        UPDATE ml_feature_label
        SET
            ceo_change_flag                  = (SELECT g.ceo_change_flag                  FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym),
            ceo_change_count_12m             = (SELECT g.ceo_change_count_12m             FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym),
            director_resignation_count_12m   = (SELECT g.director_resignation_count_12m   FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym),
            major_shareholder_change_flag    = (SELECT g.major_shareholder_change_flag    FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym),
            ownership_concentration_pct      = (SELECT g.ownership_concentration_pct      FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym),
            embezzlement_allegation_flag     = (SELECT g.embezzlement_allegation_flag     FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym),
            audit_opinion_qualified_flag     = (SELECT g.audit_opinion_qualified_flag     FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym),
            governance_risk_score            = (SELECT g.governance_risk_score            FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym),
            employee_count_change_pct        = (SELECT g.employee_count_change_pct        FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym),
            social_insurance_dropout_flag    = (SELECT g.social_insurance_dropout_flag    FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym),
            business_address_change_flag     = (SELECT g.business_address_change_flag     FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym)
        WHERE EXISTS (SELECT 1 FROM fact_governance_change g WHERE g.borrower_id = ml_feature_label.borrower_id AND g.ym = ml_feature_label.ym)
    """)
    conn.commit()

    log(f"S16 완료 → {time.time() - t0:.1f}초")
