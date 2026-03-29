"""
s01_company.py — dim_company 생성, 스키마 DDL, 기업 배열 준비
v19 분리: build_companies(rng), prepare_arrays(), s01_insert_dim_company(),
         save_ca_to_db(), load_ca_from_db(), load_companies_from_db()
"""
import pickle
import time

import numpy as np

from config.macro import (
    YM_START, YM_END, MONTHS, YM_INDEX, ym_add, ym_diff,
    PHASE_MAP, PHASE_STRESS, PHASE_DM, PHASE_RATE, PHASE_MF, PHASE_FX,
    FX_BASELINE, FX_SCALE, FX_COEFF,
)
from config.companies import (
    FIRM_SIZE_CFG, N_COMPANIES, FIRM_SIZE_SEG,
    INDUSTRIES, IND_CODE, IND_STRESS_MULT, IND_MULT_ARR,
    FX_IND_IMPACT, FX_IND_ARR,
    IND_PROB, REGION_PROB, REGIONS,
    DAEGU_GYEONGBUK_REGIONS, DAEGU_IND_BOOST, DAEGU_IND_STRESS_MULT,
    AR_RHO, AR_RHO_ARR, PHASE_RHO_ADJ,
    CORR_FIN, L_FIN, BASE_DTE, BASE_CR, BASE_ICR, BASE_DSCR, BASE_EBITDA,
    GRADE_SEQ, GRADE_RISK, score_to_grade, get_ind_probs,
)
from config.default_rates import (
    IND_DEFAULT_MULT, CONTAGION_PROB, CONTAGION_LAG, CONTAGION_CHAIN_PROB,
    CONTAGION_PHASE_PROB, IND_GUARANTEE_AFFINITY,
    get_contagion_prob, base_dr_for_ind,
)


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


# ──────────────────────────────────────────────
# 스키마 DDL
# ──────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dim_company (
    borrower_id             TEXT PRIMARY KEY,
    company_name            TEXT,
    industry_cd             TEXT,
    industry_category       TEXT,
    firm_size_cd            TEXT,
    firm_size_segment       TEXT,
    listed_flag             INTEGER,
    incorporation_year      INTEGER,
    incorporation_years_ref INTEGER,
    region_cd               TEXT,
    asset_size_억           REAL,
    entry_ym                INTEGER,
    exit_ym                 INTEGER,
    exit_reason             TEXT,
    default_flag            INTEGER DEFAULT 0,
    default_ym_internal     INTEGER,
    default_ym_regulatory   INTEGER,
    macro_sensitivity       REAL,
    business_cycle_beta     REAL,
    default_path_type       TEXT,
    vintage_year            INTEGER,
    zombie_flag             INTEGER DEFAULT 0,
    industry_sub_cd         TEXT
);

CREATE TABLE IF NOT EXISTS dim_facility (
    facility_id         TEXT PRIMARY KEY,
    borrower_id         TEXT NOT NULL,
    facility_type       TEXT,
    origination_ym      INTEGER,
    maturity_ym         INTEGER,
    committed_amount_억 REAL,
    interest_rate_pct   REAL,
    collateral_flag     INTEGER DEFAULT 0,
    FOREIGN KEY (borrower_id) REFERENCES dim_company(borrower_id)
);

CREATE TABLE IF NOT EXISTS dim_collateral (
    collateral_id       TEXT PRIMARY KEY,
    borrower_id         TEXT NOT NULL,
    collateral_type     TEXT,
    appraised_value_억  REAL,
    registration_ym     INTEGER,
    legal_status        TEXT,
    FOREIGN KEY (borrower_id) REFERENCES dim_company(borrower_id)
);

CREATE TABLE IF NOT EXISTS ref_macro (
    ym                  INTEGER PRIMARY KEY,
    base_rate_pct       REAL,
    macro_factor        REAL,
    gdp_growth_pct      REAL,
    unemployment_rate   REAL,
    cpi_yoy_pct         REAL,
    phase_name          TEXT,
    stress_level        REAL,
    policy_support_flag INTEGER DEFAULT 0,
    fx_rate_usdkrw      REAL,
    fx_stress_flag      INTEGER DEFAULT 0,
    ksic_version        TEXT DEFAULT 'KSIC-10'
);

CREATE TABLE IF NOT EXISTS ref_industry_macro (
    ym                  INTEGER NOT NULL,
    industry_cd         TEXT NOT NULL,
    industry_category   TEXT,
    industry_growth_pct REAL,
    industry_stress_idx REAL,
    export_growth_pct   REAL,
    PRIMARY KEY (ym, industry_cd)
);

CREATE TABLE IF NOT EXISTS ref_industry_stress (
    ym                      INTEGER NOT NULL,
    industry_cd             TEXT NOT NULL,
    stress_score            REAL,
    default_rate_industry   REAL,
    credit_tightening_idx   REAL,
    PRIMARY KEY (ym, industry_cd)
);

CREATE TABLE IF NOT EXISTS ref_region_industry_profile (
    region_cd               TEXT NOT NULL,
    industry_cd             TEXT NOT NULL,
    weight_multiplier       REAL,
    stress_sensitivity_mult REAL,
    fx_sensitivity_mult     REAL,
    notes                   TEXT,
    PRIMARY KEY (region_cd, industry_cd)
);

CREATE TABLE IF NOT EXISTS fact_ews_score (
    borrower_id             TEXT NOT NULL,
    ym                      INTEGER NOT NULL,
    ews_score               REAL,
    ews_grade               TEXT,
    ews_score_prev3m_avg    REAL,
    ews_score_change_3m     REAL,
    ews_score_slope_6m      REAL,
    confidence_pct          REAL,
    model_version           TEXT DEFAULT 'EWS-v4.0',
    PRIMARY KEY (borrower_id, ym)
);

CREATE TABLE IF NOT EXISTS fact_monthly_account (
    borrower_id                         TEXT NOT NULL,
    ym                                  INTEGER NOT NULL,
    avg_deposit_balance_3m_억           REAL,
    inflow_amt_3m_change_pct            REAL,
    inflow_outflow_ratio_1m             REAL,
    sales_receipt_concentration_top1    REAL,
    outward_transfer_spike_flag         INTEGER,
    dormant_account_flag                INTEGER,
    deposit_slope_6m                    REAL,
    deposit_std_12m                     REAL,
    inflow_cv_12m                       REAL,
    cash_inflow_range_12m               REAL,
    PRIMARY KEY (borrower_id, ym)
);

CREATE TABLE IF NOT EXISTS fact_monthly_credit (
    borrower_id                 TEXT NOT NULL,
    ym                          INTEGER NOT NULL,
    limit_utilization_ratio     REAL,
    over_limit_flag             INTEGER,
    principal_past_due_days     INTEGER,
    past_due_count_12m          INTEGER,
    extension_request_count_12m INTEGER,
    covenant_breach_count_12m   INTEGER,
    interest_only_months        INTEGER,
    restruct_request_flag       INTEGER,
    refinancing_count_12m       INTEGER,
    watchlist_flag              INTEGER,
    rating_idx                  INTEGER,
    rating_change_notches_12m   INTEGER,
    asset_quality_cd            TEXT,
    ifrs9_stage_cd              TEXT,
    credit_health_score         REAL,
    PRIMARY KEY (borrower_id, ym)
);

CREATE TABLE IF NOT EXISTS fact_quarterly_financial (
    borrower_id             TEXT NOT NULL,
    ym                      INTEGER NOT NULL,
    debt_to_equity_ratio    REAL,
    current_ratio           REAL,
    interest_coverage_ratio REAL,
    dscr_ratio              REAL,
    ebitda_margin_pct       REAL,
    sales_growth_pct        REAL,
    ltv_ratio               REAL,
    revenue_억              REAL,
    net_profit_margin_pct   REAL,
    operating_cash_flow_억  REAL,
    PRIMARY KEY (borrower_id, ym)
);

CREATE TABLE IF NOT EXISTS fact_collateral_monthly (
    borrower_id                 TEXT NOT NULL,
    ym                          INTEGER NOT NULL,
    ltv_ratio                   REAL,
    collateral_value_억         REAL,
    collateral_legal_issue_flag INTEGER,
    recovery_cover_ratio        REAL,
    ltv_slope_6m                REAL,
    PRIMARY KEY (borrower_id, ym)
);

CREATE TABLE IF NOT EXISTS fact_ifrs9_stage_history (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    borrower_id         TEXT NOT NULL,
    from_ym             INTEGER,
    to_ym               INTEGER,
    from_stage          TEXT,
    to_stage            TEXT,
    trigger_reason      TEXT,
    FOREIGN KEY (borrower_id) REFERENCES dim_company(borrower_id)
);

CREATE TABLE IF NOT EXISTS fact_external_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    borrower_id         TEXT,
    ym                  INTEGER,
    event_type          TEXT,
    event_severity      INTEGER,
    event_description   TEXT,
    FOREIGN KEY (borrower_id) REFERENCES dim_company(borrower_id)
);

CREATE TABLE IF NOT EXISTS fact_collateral_disposal (
    disposal_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    collateral_id       TEXT,
    borrower_id         TEXT,
    disposal_ym         INTEGER,
    disposal_amount_억  REAL,
    recovery_rate_pct   REAL,
    disposal_method     TEXT
);

CREATE TABLE IF NOT EXISTS fact_borrower_behavior_monthly (
    borrower_id                     TEXT NOT NULL,
    ym                              INTEGER NOT NULL,
    rm_contact_attempt_count        INTEGER,
    rm_contact_failed_count         INTEGER,
    rm_contact_failed_rate          REAL,
    site_visit_flag                 INTEGER,
    document_submission_delay_days  INTEGER,
    promised_action_breach_count    INTEGER,
    covenant_report_missing_flag    INTEGER,
    management_change_flag          INTEGER,
    payroll_delay_signal            INTEGER,
    tax_arrears_signal              INTEGER,
    social_insurance_arrears_signal INTEGER,
    intra_group_transfer_anomaly_flag INTEGER,
    behavior_risk_score             REAL,
    payroll_amount_pct              REAL,
    tax_arrears_months              INTEGER,
    PRIMARY KEY (borrower_id, ym)
);

CREATE TABLE IF NOT EXISTS ml_feature_label (
    borrower_id                     TEXT NOT NULL,
    ym                              INTEGER NOT NULL,
    split_set                       TEXT,
    label_default_3m                INTEGER,
    label_default_6m                INTEGER,
    label_downgrade_next_m          INTEGER,
    label_watchlist_next_m          INTEGER,
    label_ews_grade_next_m          TEXT,
    firm_size_cd                    TEXT,
    listed_flag                     INTEGER,
    industry_cd                     TEXT,
    incorporation_years             INTEGER,
    ews_score                       REAL,
    ews_score_prev3m_avg            REAL,
    ews_score_change_3m             REAL,
    ews_score_slope_6m              REAL,
    rating_idx                      INTEGER,
    rating_change_notches_12m       INTEGER,
    asset_quality_cd                TEXT,
    ifrs9_stage_cd                  TEXT,
    watchlist_flag                  INTEGER,
    limit_utilization_ratio         REAL,
    over_limit_flag                 INTEGER,
    principal_past_due_days         INTEGER,
    past_due_count_12m              INTEGER,
    extension_request_count_12m     INTEGER,
    covenant_breach_count_12m       INTEGER,
    interest_only_months            INTEGER,
    restruct_request_flag           INTEGER,
    refinancing_count_12m           INTEGER,
    avg_deposit_balance_3m_억       REAL,
    inflow_amt_3m_change_pct        REAL,
    inflow_outflow_ratio_1m         REAL,
    sales_receipt_concentration_top1 REAL,
    outward_transfer_spike_flag     INTEGER,
    dormant_account_flag            INTEGER,
    debt_to_equity_ratio            REAL,
    current_ratio                   REAL,
    interest_coverage_ratio         REAL,
    dscr_ratio                      REAL,
    ebitda_margin_pct               REAL,
    sales_growth_pct                REAL,
    ltv_ratio                       REAL,
    industry_stress_score           REAL,
    macro_factor                    REAL,
    base_rate_pct                   REAL,
    dscr_slope_4q                   REAL,
    ltv_slope_6m                    REAL,
    sales_growth_slope_4q           REAL,
    deposit_slope_6m                REAL,
    dte_pct_rank                    REAL,
    icr_pct_rank                    REAL,
    current_ratio_pct_rank          REAL,
    dscr_pct_rank                   REAL,
    ebitda_margin_pct_rank          REAL,
    sales_growth_pct_rank           REAL,
    deposit_std_12m                 REAL,
    inflow_cv_12m                   REAL,
    health_score_std_6m             REAL,
    ews_score_std_6m                REAL,
    cash_inflow_range_12m           REAL,
    alert_signal_count              INTEGER,
    alert_signal_severity           REAL,
    guarantee_remaining_months      INTEGER,
    label_status                    TEXT,
    observation_horizon_end_ym      INTEGER,
    scoring_run_id                  TEXT,
    backfill_version                INTEGER,
    production_snapshot_flag        INTEGER,
    fx_rate_usdkrw                  REAL,
    contagion_exposure_flag         INTEGER DEFAULT 0,
    payroll_amount_pct              REAL,
    tax_arrears_months              INTEGER,
    card_sales_growth_pct           REAL,
    electricity_usage_idx           REAL,
    export_count_idx                REAL,
    news_sentiment_score            REAL,
    lease_change_flag               INTEGER,
    industry_sub_cd                 TEXT,
    ksic_version_flag               INTEGER DEFAULT 0,
    PRIMARY KEY (borrower_id, ym)
);

CREATE TABLE IF NOT EXISTS ml_survival (
    borrower_id         TEXT PRIMARY KEY,
    entry_ym            INTEGER,
    event_ym            INTEGER,
    event_flag          INTEGER,
    duration_months     INTEGER,
    censored_flag       INTEGER,
    firm_size_cd        TEXT,
    industry_cd         TEXT,
    industry_sub_cd     TEXT
);

CREATE TABLE IF NOT EXISTS ml_walk_forward_splits (
    fold_id             INTEGER PRIMARY KEY,
    train_start_ym      INTEGER,
    train_end_ym        INTEGER,
    test_start_ym       INTEGER,
    test_end_ym         INTEGER,
    n_train_samples     INTEGER,
    n_test_samples      INTEGER,
    description         TEXT
);

CREATE TABLE IF NOT EXISTS model_registry (
    model_id            TEXT PRIMARY KEY,
    model_version       TEXT,
    algorithm           TEXT,
    train_start_ym      INTEGER,
    train_end_ym        INTEGER,
    champion_flag       INTEGER,
    deploy_ym           INTEGER,
    auroc               REAL,
    ks_stat             REAL,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS model_performance_monthly (
    model_version       TEXT,
    ym                  INTEGER,
    split_set           TEXT,
    auroc               REAL,
    ks_stat             REAL,
    recall              REAL,
    precision_val       REAL,
    f1_score            REAL,
    avg_precision       REAL,
    n_samples           INTEGER,
    n_defaults          INTEGER,
    PRIMARY KEY (model_version, ym, split_set)
);

CREATE TABLE IF NOT EXISTS feature_importance_history (
    importance_id       INTEGER PRIMARY KEY,
    model_version       TEXT,
    ym                  INTEGER,
    feature_name        TEXT,
    importance_score    REAL,
    importance_rank     INTEGER
);

CREATE TABLE IF NOT EXISTS pd_rating_band (
    model_version       TEXT,
    rating_band         TEXT,
    pd_lower_pct        REAL,
    pd_upper_pct        REAL,
    avg_pd_pct          REAL,
    sample_count        INTEGER,
    actual_dr_pct       REAL,
    PRIMARY KEY (model_version, rating_band)
);

CREATE TABLE IF NOT EXISTS cost_matrix_config (
    config_id           INTEGER PRIMARY KEY,
    label_type          TEXT,
    ead_avg_억          REAL,
    lgd_avg             REAL,
    fn_cost_ratio       REAL,
    fp_cost_ratio       REAL,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS migration_matrix_yearly (
    year_ym             INTEGER,
    from_grade          TEXT,
    to_grade            TEXT,
    transition_pct      REAL,
    company_count       INTEGER,
    PRIMARY KEY (year_ym, from_grade, to_grade)
);

CREATE TABLE IF NOT EXISTS ews_action_outcome (
    action_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    borrower_id             TEXT,
    alert_ym                INTEGER,
    ews_grade_at_alert      TEXT,
    action_code             TEXT,
    action_completed_flag   INTEGER,
    outcome_type            TEXT,
    reviewer_id             TEXT
);

CREATE TABLE IF NOT EXISTS stress_macro_scenario (
    scenario_id         INTEGER PRIMARY KEY,
    scenario_name       TEXT,
    scenario_type       TEXT,
    gdp_shock_pct       REAL,
    credit_spread_bps   INTEGER,
    pd_multiplier       REAL,
    lgd_add_pct         REAL
);

CREATE TABLE IF NOT EXISTS industry_stress_sensitivity (
    industry_cd         TEXT,
    scenario_name       TEXT,
    pd_elasticity       REAL,
    revenue_shock_pct   REAL,
    PRIMARY KEY (industry_cd, scenario_name)
);

CREATE TABLE IF NOT EXISTS guarantee_network (
    guarantee_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    guarantor_id        TEXT,
    beneficiary_id      TEXT,
    guarantee_amount_억 REAL,
    start_ym            INTEGER,
    end_ym              INTEGER
);

CREATE TABLE IF NOT EXISTS company_relationship (
    relation_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id           TEXT,
    child_id            TEXT,
    relation_type       TEXT,
    ownership_pct       REAL
);

CREATE TABLE IF NOT EXISTS network_centrality (
    borrower_id             TEXT PRIMARY KEY,
    degree_centrality       REAL,
    in_degree               INTEGER,
    out_degree              INTEGER,
    pagerank_score          REAL,
    neighbor_avg_ews        REAL,
    neighbor_default_rate   REAL,
    chain_depth             INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dataset_registry (
    dataset_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_name        TEXT,
    version             TEXT,
    created_ym          INTEGER,
    row_count           INTEGER,
    description         TEXT
);

CREATE TABLE IF NOT EXISTS feature_catalog (
    feature_name        TEXT PRIMARY KEY,
    feature_group       INTEGER,
    data_type           TEXT,
    source_system       TEXT,
    owner_team          TEXT,
    availability_grade  TEXT,
    update_frequency    TEXT,
    in_production       INTEGER,
    missing_rate_typical TEXT,
    missing_mechanism   TEXT,
    importance_score    REAL,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS regulatory_compliance_status (
    compliance_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    regulation_category     TEXT,
    requirement_name        TEXT,
    current_status          TEXT,
    implementation_level    TEXT,
    evidence_artifact       TEXT,
    last_reviewed_ym        INTEGER,
    notes                   TEXT
);

CREATE TABLE IF NOT EXISTS model_fairness_metrics (
    fairness_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version           TEXT,
    as_of_ym                INTEGER,
    group_variable          TEXT,
    group_value             TEXT,
    sample_count            INTEGER,
    default_rate            REAL,
    model_alert_rate        REAL,
    demographic_parity_diff REAL,
    equalized_odds_tpr_diff REAL,
    equalized_odds_fpr_diff REAL,
    calibration_slope       REAL,
    notes                   TEXT
);

CREATE TABLE IF NOT EXISTS drift_monitoring_config (
    monitor_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_type            TEXT,
    feature_name            TEXT,
    reference_period_start  INTEGER,
    reference_period_end    INTEGER,
    psi_threshold_caution   REAL,
    psi_threshold_alert     REAL,
    ks_stat_threshold       REAL,
    retraining_trigger      TEXT,
    monitoring_frequency    TEXT,
    active_flag             INTEGER,
    notes                   TEXT
);

CREATE TABLE IF NOT EXISTS adasyn_focal_loss_config (
    config_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    label_type      TEXT,
    method          TEXT,
    param_key       TEXT,
    param_value     REAL,
    rationale       TEXT
);

CREATE TABLE IF NOT EXISTS borrower_segment_modeling_profile (
    segment_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_name        TEXT,
    industry_scope      TEXT,
    size_scope          TEXT,
    model_type          TEXT,
    min_sample_size     INTEGER,
    imbalance_method    TEXT,
    key_features        TEXT,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS regulatory_capital_buffer (
    buffer_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    firm_size_cd        TEXT,
    industry_cd         TEXT,
    ews_grade           TEXT,
    required_buffer_pct REAL,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS credit_bureau_inquiry_log (
    inquiry_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    borrower_id         TEXT,
    inquiry_ym          INTEGER,
    inquiry_type        TEXT,
    bureau_name         TEXT,
    result_grade        TEXT
);

CREATE TABLE IF NOT EXISTS ews_leadtime_metrics (
    metric_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_type              TEXT NOT NULL,
    scope_value             TEXT NOT NULL,
    n_defaults              INTEGER,
    n_detected              INTEGER,
    detection_rate_pct      REAL,
    avg_lead_months         REAL,
    median_lead_months      REAL,
    pct_alert_before_3m     REAL,
    pct_alert_before_6m     REAL,
    pct_alert_before_12m    REAL,
    actionable_alert_ratio  REAL,
    early_detection_recall  REAL,
    alert_threshold_score   REAL DEFAULT 35.0,
    computed_ym             INTEGER
);

CREATE TABLE IF NOT EXISTS fact_legal_risk (
    borrower_id TEXT NOT NULL,
    ym          INTEGER NOT NULL,
    lawsuit_count_12m          INTEGER DEFAULT 0,
    lawsuit_amount_억           REAL    DEFAULT 0.0,
    seizure_flag               INTEGER DEFAULT 0,
    seizure_count_12m          INTEGER DEFAULT 0,
    tax_lien_amount_억          REAL    DEFAULT 0.0,
    bankruptcy_filing_flag     INTEGER DEFAULT 0,
    adverse_court_ruling_flag  INTEGER DEFAULT 0,
    legal_risk_score           REAL    DEFAULT 0.0,
    PRIMARY KEY (borrower_id, ym)
);

CREATE TABLE IF NOT EXISTS fact_supply_chain (
    borrower_id TEXT NOT NULL,
    ym          INTEGER NOT NULL,
    supplier_hhi                   REAL    DEFAULT 0.0,
    top_customer_revenue_ratio     REAL    DEFAULT 0.0,
    key_customer_default_flag      INTEGER DEFAULT 0,
    supply_chain_disruption_score  REAL    DEFAULT 0.0,
    import_dependency_ratio        REAL    DEFAULT 0.0,
    trade_balance_change_pct       REAL    DEFAULT 0.0,
    export_concentration_idx       REAL    DEFAULT 0.0,
    supply_chain_risk_score        REAL    DEFAULT 0.0,
    PRIMARY KEY (borrower_id, ym)
);

CREATE TABLE IF NOT EXISTS fact_governance_change (
    borrower_id TEXT NOT NULL,
    ym          INTEGER NOT NULL,
    ceo_change_flag                  INTEGER DEFAULT 0,
    ceo_change_count_12m             INTEGER DEFAULT 0,
    director_resignation_count_12m   INTEGER DEFAULT 0,
    major_shareholder_change_flag    INTEGER DEFAULT 0,
    ownership_concentration_pct      REAL    DEFAULT 0.0,
    embezzlement_allegation_flag     INTEGER DEFAULT 0,
    audit_opinion_qualified_flag     INTEGER DEFAULT 0,
    governance_risk_score            REAL    DEFAULT 0.0,
    employee_count_change_pct        REAL    DEFAULT 0.0,
    social_insurance_dropout_flag    INTEGER DEFAULT 0,
    business_address_change_flag     INTEGER DEFAULT 0,
    PRIMARY KEY (borrower_id, ym)
);
"""


def create_schema(conn):
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    log("스키마 생성 완료")


def build_companies(rng):
    """기업 생성 (v19: rng 파라미터로 전달)"""
    t0 = time.time()
    companies = []
    gidx = 0

    for size_cd, n_co, base_dr, ews_mean, ews_std, listed_prob, macro_beta, max_offset in FIRM_SIZE_CFG:
        estab_frac = {'대기업': 0.80, '중견기업': 0.70, '중소기업': 0.55, '소기업': 0.40}[size_cd]
        n_estab = int(n_co * estab_frac)
        reg_probs = REGION_PROB[size_cd]

        for i in range(n_co):
            bid = f"BID{gidx + 1:06d}"
            region_cd = REGIONS[int(rng.choice(len(REGIONS), p=reg_probs))]
            ind_probs = get_ind_probs(size_cd, region_cd)
            industry = INDUSTRIES[int(rng.choice(len(INDUSTRIES), p=ind_probs))]
            listed = 1 if rng.random() < listed_prob else 0
            incorp_yr = int(rng.integers(1985, 2020))

            if i < n_estab:
                entry_ym = YM_START
            else:
                offset = int(rng.integers(1, max_offset + 1))
                entry_ym = ym_add(YM_START, offset)
                if entry_ym > YM_END:
                    entry_ym = YM_START

            vintage_year = entry_ym // 100
            eligible_def = [m for m in MONTHS if m >= ym_add(entry_ym, 6)]
            default_flag = 0
            default_ym_int = None
            default_ym_reg = None
            zombie_flag = 0
            default_path_type = 'NONE'

            ind_dr_mult = IND_DEFAULT_MULT.get(industry, 1.0)
            effective_base_dr = base_dr * ind_dr_mult

            if eligible_def and rng.random() < effective_base_dr:
                def _dm(m):
                    pn = PHASE_MAP[m][0]
                    raw_dm = PHASE_MAP[m][2]
                    if pn == 'COVID_POLICY_SUPPORT':
                        return raw_dm * 0.25
                    return raw_dm ** macro_beta

                n_elig = len(eligible_def)
                stress_w = np.array([_dm(m) for m in eligible_def], dtype=float)
                stress_w /= stress_w.sum()
                uniform_w = np.ones(n_elig, dtype=float) / n_elig
                weights = 0.40 * uniform_w + 0.60 * stress_w
                weights /= weights.sum()
                candidate_ym = int(rng.choice(eligible_def, p=weights))

                if PHASE_MAP[candidate_ym][0] == 'COVID_SHOCK_RAW' and rng.random() < 0.20:
                    zombie_flag = 1
                    late_eligible = [m for m in MONTHS if 202201 <= m <= YM_END]
                    if late_eligible:
                        candidate_ym = int(rng.choice(late_eligible))

                default_ym_int = candidate_ym
                default_ym_reg = ym_add(default_ym_int, int(rng.integers(1, 4)))
                default_flag = 1
                # v23: ACUTE(급성 60%) / CHRONIC(만성 25%) / EVENT(돌발 15%)
                path_roll = rng.random()
                if path_roll < 0.60:
                    default_path_type = 'ACUTE'
                elif path_roll < 0.85:
                    default_path_type = 'CHRONIC'
                else:
                    default_path_type = 'EVENT'

            if default_flag:
                exit_ym = default_ym_int
                exit_reason = '부도'
            elif rng.random() < 0.05:
                min_exit = ym_add(entry_ym, 12)
                if min_exit < YM_END:
                    max_off = ym_diff(YM_END, min_exit)
                    exit_ym = ym_add(min_exit, int(rng.integers(0, max(1, max_off))))
                else:
                    exit_ym = None
                exit_reason = '조기상환' if exit_ym else None
            elif rng.random() < 0.01:
                off2 = int(rng.integers(24, 60))
                exit_ym = ym_add(entry_ym, off2)
                if exit_ym > YM_END:
                    exit_ym = None
                exit_reason = '포트폴리오제외' if exit_ym else None
            else:
                exit_ym = None
                exit_reason = None

            eff_exit = exit_ym if exit_ym else YM_END
            asset_sz = round(float(rng.lognormal(
                {'대기업': 5.5, '중견기업': 4.0, '중소기업': 2.5, '소기업': 1.5}[size_cd], 0.6)), 1)

            region_ind_mult = DAEGU_IND_STRESS_MULT.get(industry, 1.0) \
                if region_cd in DAEGU_GYEONGBUK_REGIONS else 1.0

            industry_sub_cd = IND_CODE.get(industry) if industry in ('숙박업', '음식업') else None

            companies.append({
                'borrower_id': bid, 'company_name': f"기업{bid}",
                'industry_cd': IND_CODE[industry], 'industry_category': industry,
                'firm_size_cd': size_cd, 'firm_size_segment': FIRM_SIZE_SEG[size_cd],
                'listed_flag': listed, 'incorporation_year': incorp_yr,
                'incorporation_years_ref': 2022 - incorp_yr,
                'region_cd': region_cd, 'asset_size_억': asset_sz,
                'entry_ym': entry_ym, 'exit_ym': exit_ym, 'exit_reason': exit_reason,
                'default_flag': default_flag,
                'default_ym_internal': default_ym_int,
                'default_ym_regulatory': default_ym_reg,
                'macro_sensitivity': round(float(macro_beta + rng.normal(0, 0.05)), 3),
                'business_cycle_beta': round(float(macro_beta), 2),
                'default_path_type': default_path_type,
                'vintage_year': vintage_year,
                'zombie_flag': zombie_flag,
                'industry_sub_cd': industry_sub_cd,
                '_ews_mean': ews_mean, '_ews_std': ews_std,
                '_macro_beta': macro_beta,
                '_eff_exit': eff_exit,
                '_region_ind_mult': region_ind_mult,
            })
            gidx += 1

    # CONTAGION 보증 관계망 생성 + 전파
    N = len(companies)
    n_pairs = N // 15
    guarantee_pairs = []
    seen_pairs = set()

    ind_to_idx = {ind: i for i, ind in enumerate(INDUSTRIES)}
    g_candidates = rng.choice(N, size=n_pairs * 5, replace=True).tolist()
    filled = 0
    for g_raw in g_candidates:
        if filled >= n_pairs:
            break
        g_idx = int(g_raw)
        g_ind = companies[g_idx]['industry_category']
        affinities = IND_GUARANTEE_AFFINITY.get(g_ind, {})

        if affinities and rng.random() < 0.35:
            aff_inds = list(affinities.keys())
            aff_weights = np.array([affinities[i] for i in aff_inds], dtype=float)
            aff_weights /= aff_weights.sum()
            target_ind = aff_inds[int(rng.choice(len(aff_inds), p=aff_weights))]
            target_pool = [i for i in range(N) if companies[i]['industry_category'] == target_ind]
            if not target_pool:
                continue
            b_idx = int(rng.choice(target_pool))
        else:
            b_idx = int(rng.choice(N))

        if g_idx == b_idx or (g_idx, b_idx) in seen_pairs:
            continue
        seen_pairs.add((g_idx, b_idx))
        amt = round(float(rng.uniform(1, 100)), 1)
        s_ym = max(companies[g_idx]['entry_ym'], companies[b_idx]['entry_ym'])
        e_ym = ym_add(s_ym, int(rng.integers(48, 108)))
        if e_ym > YM_END:
            e_ym = YM_END
        guarantee_pairs.append((g_idx, b_idx, amt, s_ym, e_ym))
        filled += 1

    # 1차 CONTAGION 전파
    for g_idx, b_idx, amt, s_ym, e_ym in guarantee_pairs:
        g = companies[g_idx]
        b = companies[b_idx]
        if g['default_flag'] and not b['default_flag']:
            g_def_ym = g['default_ym_internal']
            if s_ym <= g_def_ym <= e_ym:
                prob = get_contagion_prob(g_def_ym)
                if rng.random() < prob:
                    lag = int(rng.integers(CONTAGION_LAG[0], CONTAGION_LAG[1]))
                    c_ym = ym_add(g_def_ym, lag)
                    if c_ym <= YM_END and c_ym > b['entry_ym']:
                        b['default_flag'] = 1
                        b['default_ym_internal'] = c_ym
                        b['default_ym_regulatory'] = ym_add(c_ym, int(rng.integers(1, 4)))
                        b['default_path_type'] = 'CONTAGION'
                        b['exit_ym'] = c_ym
                        b['exit_reason'] = '부도'
                        b['_eff_exit'] = c_ym

    # 2차 CONTAGION 전파 (다단계 체인)
    for g_idx, b_idx, amt, s_ym, e_ym in guarantee_pairs:
        g = companies[g_idx]
        b = companies[b_idx]
        if (g['default_flag'] and g['default_path_type'] == 'CONTAGION'
                and not b['default_flag']):
            g_def_ym = g['default_ym_internal']
            if s_ym <= g_def_ym <= e_ym:
                base_prob = get_contagion_prob(g_def_ym)
                chain_prob = base_prob * CONTAGION_CHAIN_PROB
                if rng.random() < chain_prob:
                    lag = int(rng.integers(CONTAGION_LAG[0], CONTAGION_LAG[1] + 2))
                    c_ym = ym_add(g_def_ym, lag)
                    if c_ym <= YM_END and c_ym > b['entry_ym']:
                        b['default_flag'] = 1
                        b['default_ym_internal'] = c_ym
                        b['default_ym_regulatory'] = ym_add(c_ym, int(rng.integers(1, 4)))
                        b['default_path_type'] = 'CONTAGION'
                        b['exit_ym'] = c_ym
                        b['exit_reason'] = '부도'
                        b['_eff_exit'] = c_ym

    _path_cnt = {p: sum(1 for c in companies if c['default_path_type'] == p)
                 for p in ('ACUTE', 'CHRONIC', 'EVENT', 'CONTAGION', 'NONE')}
    log(f"기업 생성: {len(companies):,}개 ({time.time() - t0:.1f}초) | "
        f"보증쌍: {len(guarantee_pairs):,} | "
        f"ACUTE:{_path_cnt['ACUTE']} CHRONIC:{_path_cnt['CHRONIC']} "
        f"EVENT:{_path_cnt['EVENT']} CONTAGION:{_path_cnt['CONTAGION']}")
    return companies, guarantee_pairs


def prepare_arrays(companies, guarantee_pairs):
    """기업 배열 준비 (NumPy 벡터화용)"""
    N = len(companies)
    size_map = ['대기업', '중견기업', '중소기업', '소기업']
    path_map = {'ACUTE': 1, 'CHRONIC': 0, 'NONE': 2, 'CONTAGION': 3,
                'EVENT': 4, 'SUDDEN': 1, 'GRADUAL': 0}  # 하위호환 포함
    ind_map = {ind: i for i, ind in enumerate(INDUSTRIES)}

    guarantor_def_ym = np.full(N, 999999, dtype=np.int32)
    for g_idx, b_idx, amt, s_ym, e_ym in guarantee_pairs:
        g = companies[g_idx]
        if g['default_flag']:
            guarantor_def_ym[b_idx] = g['default_ym_internal']

    ca = {
        'entry_yms': np.array([c['entry_ym'] for c in companies], dtype=np.int32),
        'eff_exits': np.array([c['_eff_exit'] for c in companies], dtype=np.int32),
        'ews_mean': np.array([c['_ews_mean'] for c in companies], dtype=float),
        'ews_std': np.array([c['_ews_std'] for c in companies], dtype=float),
        'macro_beta': np.array([c['_macro_beta'] for c in companies], dtype=float),
        'def_flag': np.array([c['default_flag'] for c in companies], dtype=np.int8),
        'def_ym_idx': np.array([YM_INDEX.get(c['default_ym_internal'], -1) for c in companies], dtype=np.int32),
        'path_type': np.array([path_map[c['default_path_type']] for c in companies], dtype=np.int8),
        'size_idx': np.array([size_map.index(c['firm_size_cd']) for c in companies], dtype=np.int8),
        'ind_idx': np.array([ind_map[c['industry_category']] for c in companies], dtype=np.int8),
        'listed': np.array([c['listed_flag'] for c in companies], dtype=np.int8),
        'incorp_yr': np.array([c['incorporation_year'] for c in companies], dtype=np.int16),
        'guarantor_def_ym': guarantor_def_ym,
        'region_ind_mult': np.array([c['_region_ind_mult'] for c in companies], dtype=float),
        'ind_sub_cds': [c.get('industry_sub_cd') for c in companies],
    }
    log(f"기업 배열 준비: {N:,}개사")
    return ca


def save_ca_to_db(conn, ca):
    """ca 배열을 SQLite에 직렬화 (s08이 독립적으로 읽을 수 있도록)"""
    conn.execute("CREATE TABLE IF NOT EXISTS _raw_company_arrays (key TEXT PRIMARY KEY, data BLOB)")
    for k, v in ca.items():
        data = pickle.dumps(v)
        conn.execute("INSERT OR REPLACE INTO _raw_company_arrays VALUES (?,?)", (k, data))
    conn.commit()
    log("ca 배열 SQLite 저장 완료")


def load_ca_from_db(conn):
    """SQLite에서 ca 배열 복원"""
    ca = {}
    for row in conn.execute("SELECT key, data FROM _raw_company_arrays"):
        ca[row[0]] = pickle.loads(row[1])
    return ca


def s01_insert_dim_company(conn, companies):
    section("S01 dim_company")
    rows = [(
        c['borrower_id'], c['company_name'],
        c['industry_cd'], c['industry_category'],
        c['firm_size_cd'], c['firm_size_segment'],
        c['listed_flag'], c['incorporation_year'], c['incorporation_years_ref'],
        c['region_cd'], c['asset_size_억'],
        c['entry_ym'], c['exit_ym'], c['exit_reason'],
        c['default_flag'], c['default_ym_internal'], c['default_ym_regulatory'],
        c['macro_sensitivity'], c['business_cycle_beta'],
        c['default_path_type'], c['vintage_year'], c['zombie_flag'],
        c['industry_sub_cd']
    ) for c in companies]
    conn.executemany(
        "INSERT OR IGNORE INTO dim_company VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows)
    conn.commit()
    log(f"dim_company: {len(rows):,}행")


def load_companies_from_db(conn):
    """dim_company 테이블에서 companies 리스트 재구성 (--from 스킵 시 사용)"""
    rows = conn.execute("""
        SELECT borrower_id, company_name, industry_cd, industry_category,
               firm_size_cd, firm_size_segment, listed_flag, incorporation_year,
               incorporation_years_ref, region_cd, asset_size_억,
               entry_ym, exit_ym, exit_reason, default_flag,
               default_ym_internal, default_ym_regulatory,
               macro_sensitivity, business_cycle_beta, default_path_type,
               vintage_year, zombie_flag, industry_sub_cd
        FROM dim_company
    """).fetchall()

    size_cfg_map = {c[0]: c for c in FIRM_SIZE_CFG}

    companies = []
    for r in rows:
        (bid, name, ind_cd, ind_cat, size_cd, size_seg, listed, incorp_yr,
         incorp_yrs_ref, region, asset_sz, entry_ym, exit_ym, exit_reason,
         def_flag, def_ym_int, def_ym_reg, macro_sens, biz_beta,
         def_path, vintage_yr, zombie, ind_sub_cd) = r

        cfg = size_cfg_map.get(size_cd, FIRM_SIZE_CFG[2])
        _, _, base_dr, ews_mean, ews_std, listed_prob, macro_beta, max_offset = cfg

        eff_exit = exit_ym if exit_ym else YM_END

        from config.companies import DAEGU_GYEONGBUK_REGIONS, DAEGU_IND_STRESS_MULT
        region_ind_mult = DAEGU_IND_STRESS_MULT.get(ind_cat, 1.0) \
            if region in DAEGU_GYEONGBUK_REGIONS else 1.0

        companies.append({
            'borrower_id': bid, 'company_name': name,
            'industry_cd': ind_cd, 'industry_category': ind_cat,
            'firm_size_cd': size_cd, 'firm_size_segment': size_seg,
            'listed_flag': listed, 'incorporation_year': incorp_yr,
            'incorporation_years_ref': incorp_yrs_ref,
            'region_cd': region, 'asset_size_억': asset_sz,
            'entry_ym': entry_ym, 'exit_ym': exit_ym, 'exit_reason': exit_reason,
            'default_flag': def_flag,
            'default_ym_internal': def_ym_int,
            'default_ym_regulatory': def_ym_reg,
            'macro_sensitivity': macro_sens,
            'business_cycle_beta': biz_beta,
            'default_path_type': def_path,
            'vintage_year': vintage_yr,
            'zombie_flag': zombie,
            'industry_sub_cd': ind_sub_cd,
            '_ews_mean': ews_mean, '_ews_std': ews_std,
            '_macro_beta': macro_beta,
            '_eff_exit': eff_exit,
            '_region_ind_mult': region_ind_mult,
        })
    log(f"dim_company 로드: {len(companies):,}개사")
    return companies
