"""
s11_extensions.py — 확장 테이블 생성 (feature_catalog, regulatory_compliance_status,
                    model_fairness_metrics, drift_monitoring_config, adasyn_focal_loss_config,
                    borrower_segment_modeling_profile, dataset_registry)
v18의 s14_extensions() → v19 s11_extensions()
"""
import time

from config.companies import INDUSTRIES, IND_CODE


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s11_extensions(conn, rng):
    section("S11 extensions")
    t0 = time.time()

    segs = [
        ('상장법인', '제조/IT', '대기업', 'LightGBM+SHAP', 500, 'ADASYN', '재무신호+공시이벤트', ''),
        ('외감비상장', '전산업', '중견기업', 'XGBoost', 300, 'Focal Loss', '재무+계좌신호', ''),
        ('비외감법인', '전산업', '중소기업', 'RandomForest', 200, 'SMOTE', '계좌+행동신호', ''),
        ('개인사업자', '도소매/음식', '소기업', 'TabNet', 150, 'ADASYN', '계좌+세무+행동', ''),
        ('PF_SPC', '부동산', '중견기업', 'SurvivalAnalysis', 100, 'None', 'PF진행률+현금흐름', ''),
        ('수출의존제조', '일반제조업', '중소기업', 'GBM+거시+FX', 200, 'Focal Loss', '재무+거시+FX신호', 'v10 FX연동'),
        ('원청의존하도급', '건설/제조', '중소기업', 'NetworkGBM', 150, 'SMOTE', '매출집중도+원청EWS', ''),
        ('지역중소건설', '건설업', '소기업', 'GBM+부동산', 100, 'ADASYN', '수주신호+현금흐름', 'v10 대구권'),
        ('프랜차이즈', '도소매', '소기업', 'Rule+GBM', 100, 'None', '계좌+행동+본부신용', ''),
        ('계열의존형', '전산업', '중견기업', 'GNN+GBM', 200, 'Focal Loss', '그룹신호+네트워크', 'v10 CONTAGION'),
    ]
    conn.executemany("INSERT INTO borrower_segment_modeling_profile VALUES (?,?,?,?,?,?,?,?,?)",
                     [(None,) + s for s in segs])

    feat_defs = [
        ('ews_score', 1, 'NUMERIC', 'EWS엔진', 'ML팀', 'A', 'monthly', 1, '낮음', '낮음', 0.18, 'AR(1) 점수'),
        ('ews_score_change_3m', 1, 'NUMERIC', 'EWS엔진', 'ML팀', 'A', 'monthly', 1, '낮음', '낮음', 0.14, '3개월 변화'),
        ('ews_score_slope_6m', 1, 'NUMERIC', 'EWS엔진', 'ML팀', 'A', 'monthly', 1, '낮음', '낮음', 0.11, '6개월 기울기'),
        ('principal_past_due_days', 2, 'NUMERIC', '계좌', 'IT팀', 'A', 'daily', 1, '낮음', '낮음', 0.16, '연체일수'),
        ('dscr_ratio', 3, 'NUMERIC', '재무', '여신팀', 'B', 'quarterly', 1, '중간', '중간', 0.13, 'DSCR'),
        ('ebitda_margin_pct', 3, 'NUMERIC', '재무', '여신팀', 'B', 'quarterly', 1, '높음', '중간', 0.11, 'MNAR대상'),
        ('debt_to_equity_ratio', 3, 'NUMERIC', '재무', '여신팀', 'B', 'quarterly', 1, '낮음', '중간', 0.10, '부채비율'),
        ('interest_coverage_ratio', 3, 'NUMERIC', '재무', '여신팀', 'B', 'quarterly', 1, '낮음', '중간', 0.09, '이자보상배율'),
        ('current_ratio', 3, 'NUMERIC', '재무', '여신팀', 'B', 'quarterly', 1, '낮음', '낮음', 0.08, '유동비율'),
        ('sales_growth_pct', 3, 'NUMERIC', '재무', '여신팀', 'B', 'quarterly', 1, '높음', '낮음', 0.07, 'MNAR대상'),
        ('limit_utilization_ratio', 4, 'NUMERIC', '계좌', 'IT팀', 'A', 'monthly', 1, '낮음', '낮음', 0.12, '한도소진율'),
        ('avg_deposit_balance_3m_억', 4, 'NUMERIC', '계좌', 'IT팀', 'A', 'monthly', 1, '낮음', '낮음', 0.09, '예금잔액'),
        ('inflow_amt_3m_change_pct', 4, 'NUMERIC', '계좌', 'IT팀', 'A', 'monthly', 1, '낮음', '낮음', 0.08, '입금변화율'),
        ('rm_contact_failed_rate', 5, 'NUMERIC', 'CRM', 'RM팀', 'A', 'monthly', 1, '낮음', '중간', 0.15, 'RM접촉실패율'),
        ('document_submission_delay_days', 5, 'NUMERIC', 'CRM', 'RM팀', 'A', 'monthly', 1, '낮음', '중간', 0.13, '서류지연'),
        ('payroll_delay_signal', 5, 'BINARY', 'CRM', 'RM팀', 'B', 'monthly', 1, '중간', '높음', 0.15, '급여지연(선행)'),
        ('payroll_amount_pct', 5, 'NUMERIC', 'CRM', 'RM팀', 'B', 'monthly', 1, '중간', '높음', 0.14, '급여지급율(v10 P5)'),
        ('tax_arrears_months', 5, 'NUMERIC', '세무', 'RM팀', 'B', 'monthly', 1, '중간', '높음', 0.12, '세금체납월수(v10 P5)'),
        ('fx_rate_usdkrw', 6, 'NUMERIC', '거시', '리스크팀', 'A', 'monthly', 1, '낮음', '낮음', 0.09, '환율(v10 P4)'),
        ('contagion_exposure_flag', 2, 'BINARY', '네트워크', 'ML팀', 'B', 'monthly', 1, '낮음', '낮음', 0.11, '보증인부도노출(v10 P2)'),
        ('macro_factor', 6, 'NUMERIC', '거시', '리스크팀', 'A', 'monthly', 1, '낮음', '낮음', 0.06, '거시팩터'),
        ('base_rate_pct', 6, 'NUMERIC', '거시', '리스크팀', 'A', 'monthly', 1, '낮음', '낮음', 0.05, '기준금리'),
        ('industry_stress_score', 6, 'NUMERIC', '업종', '리스크팀', 'A', 'monthly', 1, '낮음', '낮음', 0.04, '업종스트레스'),
        ('ltv_ratio', 7, 'NUMERIC', '담보', '심사팀', 'B', 'quarterly', 1, '낮음', '낮음', 0.07, 'LTV'),
        ('firm_size_cd', 8, 'CATEGORICAL', 'CIF', '기업팀', 'A', 'static', 1, '낮음', '낮음', 0.05, '기업규모'),
        ('industry_cd', 8, 'CATEGORICAL', 'CIF', '기업팀', 'A', 'static', 1, '낮음', '낮음', 0.04, '업종'),
        ('incorporation_years', 8, 'NUMERIC', 'CIF', '기업팀', 'A', 'yearly', 1, '낮음', '낮음', 0.03, '업력'),
        ('dscr_slope_4q', 9, 'NUMERIC', '파생', 'ML팀', 'A', 'quarterly', 1, '낮음', '낮음', 0.08, 'DSCR기울기'),
        ('deposit_slope_6m', 9, 'NUMERIC', '파생', 'ML팀', 'A', 'monthly', 1, '낮음', '낮음', 0.07, '예금기울기'),
        ('alert_signal_count', 10, 'NUMERIC', '파생', 'ML팀', 'A', 'monthly', 1, '낮음', '낮음', 0.09, '경보신호수'),
        ('alert_signal_severity', 10, 'NUMERIC', '파생', 'ML팀', 'A', 'monthly', 1, '낮음', '낮음', 0.08, '경보강도'),
        ('behavior_risk_score', 5, 'NUMERIC', 'CRM', 'RM팀', 'A', 'monthly', 1, '낮음', '중간', 0.11, '행동위험점수'),
    ]
    conn.executemany("INSERT OR IGNORE INTO feature_catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", feat_defs)

    reg_items = [
        ('EWS등급체계', '4등급EWS', '구조구현', 'v10 schema', 'v10 schema', 202512, '60K기업 5등급'),
        ('Basel_III', 'PD산출', '구조구현', 'ml_feature_label', 'ml_feature_label', 202512, 'v15: 79피처'),
        ('IFRS9', 'ECL3단계', '구조구현', 'ifrs9_stage_history', 'fact_monthly_credit', 202512, 'v9유지+CONTAGION'),
        ('모델거버넌스', '챔피언챌린저', '구조구현', 'model_registry', 'model_registry', 202512, 'EWS-v4.0 챔피언'),
        ('공정성', 'Demographic_Parity', '구조구현', 'model_fairness_metrics', 'model_fairness_metrics', 202512, ''),
        ('드리프트', 'PSI모니터링', '구조구현', 'drift_monitoring_config', 'drift_monitoring_config', 202512, ''),
        ('AI가이드라인', '설명가능성', '설계반영', 'feature_importance_history', 'feature_importance_history', 202512, ''),
        ('스트레스테스트', '시나리오(환율급등)', '구조구현', 'stress_macro_scenario', 'stress_macro_scenario', 202512, 'v10 P4'),
        ('MNAR', '기업특성기반결측', '구조구현', 'ml_feature_label MNAR', 'ml_feature_label', 202512, 'v9유지'),
        ('행동신호', '선행성강화(급여/세금)', '구조구현', 'fact_borrower_behavior_monthly', 'fact_borrower_behavior_monthly', 202512, 'v10 P5'),
        ('Walk-Forward', 'Rolling48M 12folds', '구조구현', 'ml_walk_forward_splits', 'ml_walk_forward_splits', 202512, 'v10: 108개월'),
        ('Migration', '행합=1보장', '구조구현', 'migration_matrix_yearly', 'migration_matrix_yearly', 202512, '2025 포함'),
        ('CONTAGION', '연쇄부도경로', '구조구현', 'guarantee_network', 'dim_company', 202512, 'v10 P2 신규'),
        ('지역특화', 'IM뱅크대구권', '구조구현', 'ref_region_industry_profile', 'ref_region_industry_profile', 202512, 'v10 P3'),
        ('FX충격', 'USD/KRW연동', '구조구현', 'ref_macro.fx_rate_usdkrw', 'ref_macro', 202512, 'v10 P4'),
        ('K07분리', '숙박업/음식업세분화', '구조구현', 'dim_company.industry_sub_cd', 'ml_feature_label', 202512, 'v15 K07A/K07B'),
        ('LeadTimeKPI', 'EWS선행지표탐지율', '구조구현', 'ews_leadtime_metrics', 'ews_leadtime_metrics', 202512, 'v15 신규'),
        ('K01분리', '일반/첨단제조업세분화', '구조구현', 'dim_company.industry_cd', 'ml_feature_label', 202512, 'v17 K01A/K01B'),
        ('K13신설', '에너지환경업신설', '구조구현', 'dim_company.industry_cd', 'ref_macro', 202512, 'v17 K13'),
        ('KSIC11차', 'KSIC11차ksic_version', '구조구현', 'ref_macro.ksic_version', 'ref_macro', 202512, 'v17 KSIC-11'),
    ]
    conn.executemany("INSERT INTO regulatory_compliance_status(regulation_category,requirement_name,"
                     "current_status,implementation_level,evidence_artifact,last_reviewed_ym,notes) "
                     "VALUES (?,?,?,?,?,?,?)", reg_items)

    fair_rows = []
    for gv in ['firm_size_cd', 'industry_cd', 'listed_flag']:
        vals = {'firm_size_cd': ['대기업', '중견기업', '중소기업', '소기업'],
                'industry_cd': [IND_CODE[i] for i in INDUSTRIES[:4]],
                'listed_flag': ['0', '1']}[gv]
        for v in vals:
            fair_rows.append(('EWS-v4.0', 202501, gv, v,
                              int(rng.integers(1000, 10000)), round(float(rng.uniform(0.01, 0.08)), 3),
                              round(float(rng.uniform(0.05, 0.18)), 3),
                              round(float(rng.uniform(-0.04, 0.04)), 3),
                              round(float(rng.uniform(-0.06, 0.06)), 3),
                              round(float(rng.uniform(-0.05, 0.05)), 3),
                              round(float(rng.uniform(0.92, 1.08)), 3), ''))
    conn.executemany("INSERT INTO model_fairness_metrics(model_version,as_of_ym,group_variable,"
                     "group_value,sample_count,default_rate,model_alert_rate,demographic_parity_diff,"
                     "equalized_odds_tpr_diff,equalized_odds_fpr_diff,calibration_slope,notes) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", fair_rows)

    drift_items = [
        ('DATA_DRIFT', 'ews_score', 201701, 202512, 0.10, 0.25, 0.15, 'PSI>0.25→재학습', 'monthly', 1, 'EWS점수'),
        ('DATA_DRIFT', 'dscr_ratio', 201701, 202512, 0.10, 0.25, 0.15, 'PSI>0.25→재학습', 'quarterly', 1, 'DSCR'),
        ('DATA_DRIFT', 'fx_rate_usdkrw', 201701, 202512, 0.08, 0.20, 0.12, 'PSI>0.20→검토', 'monthly', 1, 'v10 FX모니터링'),
        ('DATA_DRIFT', 'payroll_amount_pct', 201701, 202512, 0.10, 0.25, 0.15, 'PSI>0.25→검토', 'monthly', 1, 'v10 급여선행지표'),
        ('NULL_RATE', 'ebitda_margin_pct', 201701, 202512, None, None, None, 'NULL>30%→점검', 'monthly', 1, 'MNAR모니터링'),
        ('NULL_RATE', 'dscr_ratio', 201701, 202512, None, None, None, 'NULL>25%→점검', 'monthly', 1, 'MNAR모니터링'),
        ('CONCEPT_DRIFT', None, 201701, 202512, None, None, None, 'AUROC하락>5%p→검토', 'quarterly', 1, ''),
        ('MODEL_PERF', None, 201701, 202512, None, None, None, 'Recall<0.50→재학습', 'monthly', 1, ''),
    ]
    conn.executemany("INSERT INTO drift_monitoring_config(monitor_type,feature_name,"
                     "reference_period_start,reference_period_end,psi_threshold_caution,"
                     "psi_threshold_alert,ks_stat_threshold,retraining_trigger,"
                     "monitoring_frequency,active_flag,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)", drift_items)

    adasyn_items = [
        ('label_default_3m', 'ADASYN', 'beta', 1.0, '결정경계 주변 소수클래스 강화'),
        ('label_default_3m', 'ADASYN', 'k_neighbors', 5.0, 'KNN 이웃'),
        ('label_default_3m', 'FocalLoss', 'gamma', 2.0, 'FN 최소화'),
        ('label_default_3m', 'FocalLoss', 'alpha', 0.75, '소수클래스 가중치'),
        ('label_default_3m', 'Threshold', 'optimal', 0.15, 'FN:FP=30:1 최적임계값'),
        ('label_default_6m', 'FocalLoss', 'gamma', 1.5, '6m 레이블'),
        ('label_default_6m', 'Threshold', 'optimal', 0.18, '6m 최적임계값'),
    ]
    conn.executemany("INSERT INTO adasyn_focal_loss_config(label_type,method,param_key,param_value,rationale) "
                     "VALUES (?,?,?,?,?)", adasyn_items)

    conn.executemany("INSERT OR IGNORE INTO dataset_registry(dataset_name,version,created_ym,"
                     "row_count,description) VALUES (?,?,?,?,?)", [
        ('EWS_Corporate_v22', 'v22.0', 202512, 0,
         'v22 합성 데이터셋 — 60K기업|108개월|외부데이터확장(법적리스크8+공급망8+지배구조11)|v20부도율수정유지'),
    ])
    conn.commit()
    log(f"extensions 완료 → {time.time() - t0:.1f}초")
