"""
s09_model.py — model_registry / model_performance_monthly / feature_importance_history /
               pd_rating_band / cost_matrix_config 생성
v18의 s11_model_tables() → v19 s09_model_tables()
"""
import time


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s09_model_tables(conn, rng):
    section("S09 model_registry / performance / importance")
    t0 = time.time()

    conn.executemany("INSERT OR IGNORE INTO model_registry VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ('M001', 'EWS-v3.0', 'LightGBM', 201701, 202212, 0, 202301, 0.88, 0.56, 'v9 champion (legacy)'),
        ('M002', 'EWS-v3.1', 'XGBoost', 201701, 202212, 0, 202301, 0.86, 0.53, 'v9 challenger'),
        ('M003', 'EWS-v3.2', 'TabNet', 201701, 202212, 0, 202303, 0.84, 0.51, 'v9 experimental'),
        ('M004', 'EWS-v4.0', 'LightGBM', 201701, 202512, 0, 202501, 0.90, 0.59, 'v10 champion (60K+CONTAGION+FX)'),
        ('M005', 'EWS-v5.0', 'LightGBM', 201701, 202512, 1, 202501, 0.91, 0.61, 'v11 champion (CONTAGION3K+EWS변별력)'),
        ('M006', 'EWS-v5.1', 'GNN+GBM', 201701, 202512, 0, 202503, 0.89, 0.58, 'v11 contagion network model'),
    ])

    perf_rows = []
    for split in ['synthetic_train', 'synthetic_validation', 'synthetic_test',
                  'real_shadow_validation', 'real_retraining', 'real_production_scoring',
                  'real_production_scoring_2025']:
        for ym_p in [202101, 202201, 202301, 202401, 202501]:
            perf_rows.append(('EWS-v4.0', ym_p, split,
                              round(float(rng.uniform(0.85, 0.92)), 3), round(float(rng.uniform(0.48, 0.63)), 3),
                              round(float(rng.uniform(0.57, 0.74)), 3), round(float(rng.uniform(0.24, 0.40)), 3),
                              round(float(rng.uniform(0.34, 0.50)), 3), round(float(rng.uniform(0.21, 0.34)), 3),
                              int(rng.integers(100000, 400000)), int(rng.integers(300, 1600))))
    conn.executemany("INSERT INTO model_performance_monthly(model_version,ym,split_set,auroc,"
                     "ks_stat,recall,precision_val,f1_score,avg_precision,n_samples,n_defaults) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?)", perf_rows)

    top_features = ['ews_score', 'ews_score_change_3m', 'dscr_ratio', 'principal_past_due_days',
                    'limit_utilization_ratio', 'debt_to_equity_ratio', 'interest_coverage_ratio',
                    'ebitda_margin_pct', 'behavior_risk_score', 'deposit_slope_6m',
                    'sales_growth_pct', 'ltv_ratio', 'rm_contact_failed_rate', 'macro_factor',
                    'fx_rate_usdkrw', 'contagion_exposure_flag', 'payroll_amount_pct', 'tax_arrears_months']
    imp_rows = [(i + 1, 'EWS-v4.0', 202501, f, round(float(rng.uniform(0.01, 0.15)), 4), i + 1)
                for i, f in enumerate(top_features)]
    conn.executemany("INSERT INTO feature_importance_history(importance_id,model_version,ym,"
                     "feature_name,importance_score,importance_rank) VALUES (?,?,?,?,?,?)", imp_rows)

    conn.executemany("INSERT INTO pd_rating_band(model_version,rating_band,pd_lower_pct,"
                     "pd_upper_pct,avg_pd_pct,sample_count,actual_dr_pct) VALUES (?,?,?,?,?,?,?)", [
        ('EWS-v4.0', '정상(70-100)', 0.01, 0.03, 0.015, 36000, 0.012),
        ('EWS-v4.0', '관심(50-69)', 0.03, 0.15, 0.07, 20000, 0.065),
        ('EWS-v4.0', '주의(35-49)', 0.15, 0.45, 0.28, 10000, 0.260),
        ('EWS-v4.0', '경계(20-34)', 0.45, 1.20, 0.80, 4000, 0.750),
        ('EWS-v4.0', '위기(0-19)', 1.20, 4.00, 2.30, 1000, 2.200),
    ])
    conn.executemany("INSERT INTO cost_matrix_config VALUES (?,?,?,?,?,?,?)", [
        (1, 'label_default_3m', 13.5, 0.45, 30.0, 0.15, 'FN:FP=30:1'),
        (2, 'label_default_6m', 10.0, 0.45, 22.0, 0.18, '6m horizon'),
    ])
    conn.commit()
    log(f"모델 테이블 완료 → {time.time() - t0:.1f}초")
