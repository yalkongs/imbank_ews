"""
s03_monthly.py — 월별 데이터 생성 (핵심 함수, ~25분 소요)
fact_ews_score, fact_monthly_account, fact_monthly_credit,
fact_borrower_behavior_monthly, ml_feature_label, fact_quarterly_financial
"""
import time

import numpy as np

from config.macro import (
    MONTHS, YM_END, YM_INDEX, ym_add, ym_diff,
    PHASE_MAP, PHASE_STRESS, PHASE_DM, PHASE_RATE, PHASE_MF, PHASE_FX,
    FX_BASELINE, FX_SCALE, FX_COEFF,
)
from config.companies import (
    INDUSTRIES, IND_CODE, IND_STRESS_MULT, IND_MULT_ARR, FX_IND_ARR,
    AR_RHO_ARR, PHASE_RHO_ADJ,
    L_FIN, BASE_DTE, BASE_CR, BASE_ICR, BASE_DSCR, BASE_EBITDA,
    GRADE_SEQ, GRADE_RISK, score_to_grade,
)


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def generate_monthly_data(conn, companies, ca, rng_obj):
    section("S03-S07 월별 데이터 생성")
    t0 = time.time()
    FLUSH = 50_000

    bids = [c['borrower_id'] for c in companies]
    N = len(companies)

    ar1_scores = np.full(N, np.nan)
    score_t1 = np.full(N, np.nan)
    score_t3 = np.full(N, np.nan)
    score_t6 = np.full(N, np.nan)

    buf_ews, buf_acc, buf_crd, buf_beh = [], [], [], []
    zfin_qbuf = {}
    prev_ml_buf = []
    prev_state = {}

    # v18: 80 컬럼 (v17 79 + ksic_version_flag)
    ML_SQL = ("INSERT OR IGNORE INTO ml_feature_label VALUES (" + ",".join(["?"] * 80) + ")")

    norm_cdf = lambda x: np.clip(0.5 * (1.0 + np.tanh(x * 0.7071)), 0.01, 0.99)

    def flush_other():
        if buf_ews:
            conn.executemany("INSERT OR IGNORE INTO fact_ews_score VALUES (?,?,?,?,?,?,?,?,?)", buf_ews)
            buf_ews.clear()
        if buf_acc:
            conn.executemany("INSERT OR IGNORE INTO fact_monthly_account VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", buf_acc)
            buf_acc.clear()
        if buf_crd:
            conn.executemany("INSERT OR IGNORE INTO fact_monthly_credit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", buf_crd)
            buf_crd.clear()
        if buf_beh:
            conn.executemany("INSERT OR IGNORE INTO fact_borrower_behavior_monthly VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", buf_beh)
            buf_beh.clear()

    total_rows = 0
    for m_idx, ym in enumerate(MONTHS):

        active = np.where((ca['entry_yms'] <= ym) & (ca['eff_exits'] >= ym))[0]
        n = len(active)
        if n == 0:
            continue

        stress = PHASE_STRESS[m_idx]
        phase_dm = PHASE_DM[m_idx]
        phase_rate = PHASE_RATE[m_idx]
        phase_mf = PHASE_MF[m_idx]
        phase_name = PHASE_MAP[ym][0]

        phase_fx_raw = float(PHASE_FX[m_idx] + rng_obj.normal(0, 15))
        phase_fx = float(np.clip(phase_fx_raw, 900, 1600))
        fx_dev = max(0.0, (phase_fx - FX_BASELINE) / FX_SCALE)

        ews_mean_v = ca['ews_mean'][active]
        ews_std_v = ca['ews_std'][active]
        beta_v = ca['macro_beta'][active]
        ind_idx_v = ca['ind_idx'][active]
        size_idx_v = ca['size_idx'][active]
        def_flag_v = ca['def_flag'][active].astype(bool)
        def_idx_v = ca['def_ym_idx'][active]
        path_v = ca['path_type'][active]
        incorp_yr_v = ca['incorp_yr'][active]
        region_mult_v = ca['region_ind_mult'][active]

        ind_mult_v = IND_MULT_ARR[ind_idx_v]
        fx_ind_v = FX_IND_ARR[ind_idx_v]

        ind_sub_cd_active = [ca['ind_sub_cds'][i] for i in active]

        rho_phase_adj = PHASE_RHO_ADJ.get(phase_name, 0.0)
        months_to_def = np.where(def_flag_v & (def_idx_v >= 0),
                                 def_idx_v - m_idx, 999).astype(float)

        sudden_near = (path_v == 1) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 3)
        contagion_near = (path_v == 3) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 6)
        fast_drop = sudden_near | contagion_near

        rho_v = np.where(fast_drop, 0.35,
                         np.maximum(AR_RHO_ARR[active] - rho_phase_adj, 0.50))

        # 1. AR(1) EWS
        macro_adj_base = stress * beta_v * ind_mult_v * 18.0 * region_mult_v
        fx_adj_v = fx_dev * fx_ind_v * beta_v * FX_COEFF * region_mult_v
        macro_adj = macro_adj_base + fx_adj_v

        grad_drop = np.where(
            (path_v == 0) & (months_to_def >= 0) & (months_to_def <= 36),
            (36.0 - months_to_def) / 36.0 * 38.0, 0.0)
        sud_drop = np.where(
            (path_v == 1) & (months_to_def >= 0) & (months_to_def <= 3),
            np.minimum(60.0, (3.0 - months_to_def) * 22.0), 0.0)
        contagion_drop = np.where(
            contagion_near,
            np.minimum(45.0, np.maximum(0.0, (6.0 - months_to_def) * 9.0)), 0.0)
        pre_def_signal = grad_drop + sud_drop + contagion_drop

        target = np.clip(ews_mean_v - macro_adj - pre_def_signal, 0.0, 100.0)

        noise_std = ews_std_v * 0.55
        noise = rng_obj.normal(0, noise_std)
        prev = ar1_scores[active]
        is_first = np.isnan(prev)
        new_ews = np.where(is_first,
                           target + noise,
                           rho_v * prev + (1.0 - rho_v) * target + noise)
        new_ews = np.clip(new_ews, 0.0, 100.0).round(2)

        score_t6[active] = score_t3[active]
        score_t3[active] = score_t1[active]
        score_t1[active] = ar1_scores[active]
        ar1_scores[active] = new_ews

        prev3m = np.where(np.isnan(score_t3[active]), new_ews, score_t3[active])
        chg3m = (new_ews - prev3m).round(2)
        slope6m = np.where(~np.isnan(score_t6[active]),
                           ((new_ews - score_t6[active]) / 6.0), chg3m / 3.0).round(3)
        conf = np.clip(70 + new_ews * 0.25 + rng_obj.normal(0, 3, n), 50, 99).round(1)
        grades = [score_to_grade(float(s)) for s in new_ews]

        # 2. 재무비율 (Cholesky)
        z_score = (new_ews - 50.0) / 15.0
        z_raw = rng_obj.normal(0, 1, (n, 5))
        z_corr = z_raw @ L_FIN.T

        b_dte = BASE_DTE[size_idx_v]
        b_cr = BASE_CR[size_idx_v]
        b_icr = BASE_ICR[size_idx_v]
        b_dscr = BASE_DSCR[size_idx_v]
        b_ebitda = BASE_EBITDA[size_idx_v]

        dte = np.clip(b_dte - z_score * 35 + z_corr[:, 0] * 25 + stress * 45, 10, 2000).round(1)
        cr = np.clip(b_cr + z_score * 28 + z_corr[:, 1] * 18 - stress * 25, 30, 500).round(1)
        icr = np.clip(b_icr + z_score * 2.2 + z_corr[:, 2] * 0.9 - stress * 1.8, -5, 30).round(2)
        dscr = np.clip(b_dscr + z_score * 0.38 + z_corr[:, 3] * 0.14 - stress * 0.45, 0.1, 5).round(3)
        ebitda = np.clip(b_ebitda + z_score * 4.5 + z_corr[:, 4] * 2.8 - stress * 4.5, -30, 35).round(2)
        sg = np.clip(rng_obj.normal(5 - stress * 8, 5, n), -30, 40).round(2)
        ltv = np.clip(rng_obj.normal(50 + stress * 18, 10, n), 20, 150).round(1)

        if ym % 100 in (3, 6, 9, 12):
            for j, ci in enumerate(active):
                zfin_qbuf[(bids[ci], ym)] = (
                    float(dte[j]), float(cr[j]), float(icr[j]),
                    float(dscr[j]), float(ebitda[j]), float(sg[j]), float(ltv[j]))

        dte_rank = norm_cdf(-z_corr[:, 0] + z_score * 0.25).round(3)
        cr_rank = norm_cdf(z_corr[:, 1] + z_score * 0.25).round(3)
        icr_rank = norm_cdf(z_corr[:, 2] + z_score * 0.25).round(3)
        dscr_rank = norm_cdf(z_corr[:, 3] + z_score * 0.25).round(3)
        ebitda_rk = norm_cdf(z_corr[:, 4] + z_score * 0.25).round(3)
        sg_rank = norm_cdf(z_score * 0.3 + rng_obj.normal(0, 0.5, n)).round(3)

        # 3. 라벨
        label_3m = np.where(def_flag_v & (def_idx_v >= m_idx) & (def_idx_v - m_idx <= 3), 1, 0)
        label_6m = np.where(def_flag_v & (def_idx_v >= m_idx) & (def_idx_v - m_idx <= 6), 1, 0)

        # 4. 행동신호
        beh_sudden = np.where(
            (path_v == 1) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 6),
            (6.0 - months_to_def) / 6.0, 0.0)
        beh_gradual = np.where(
            (path_v == 0) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 12),
            (12.0 - months_to_def) / 12.0 * 0.7, 0.0)
        beh_contagion = np.where(
            (path_v == 3) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 6),
            (6.0 - months_to_def) / 6.0 * 0.8, 0.0)
        grade_risk_v = np.array([GRADE_RISK[g] for g in grades])
        beh_total = np.clip(grade_risk_v + beh_sudden + beh_gradual + beh_contagion, 0, 1)
        behavior_risk = np.clip(beh_total + rng_obj.normal(0, 0.05, n), 0, 1).round(3)

        rm_attempt = np.clip(2 + (beh_total * 5).astype(int) + rng_obj.poisson(0.5, n), 0, 10).astype(int)
        rm_failed = np.clip((beh_total * rm_attempt).astype(int), 0, rm_attempt)
        rm_fail_rt = np.where(rm_attempt > 0, rm_failed / rm_attempt, 0.0).round(3)
        doc_delay = np.clip(beh_total * 40 + rng_obj.exponential(5, n), 0, 90).astype(int)
        breach_cnt = np.clip((beh_total * 3 + rng_obj.poisson(0.2, n)).astype(int), 0, 5)
        mgmt_chg = (rng_obj.random(n) < beh_total * 0.1).astype(int)
        tax_arr = (beh_total > 0.70).astype(int)
        soc_arr = (beh_total > 0.75).astype(int)
        group_anom = (rng_obj.random(n) < beh_total * 0.08).astype(int)
        site_visit = (beh_total > 0.50).astype(int)
        prom_breach = np.clip((beh_total * 2 + rng_obj.poisson(0.1, n)).astype(int), 0, 5)
        cov_miss = (beh_total > 0.60).astype(int)

        # 5. 신용 피처
        p_stress = np.clip(1.0 / (1.0 + np.exp((new_ews - 45.0) / 8.0)), 0.01, 0.99)
        p_stress_overdue = np.clip(1.0 / (1.0 + np.exp((new_ews - 45.0) / 10.0)), 0.01, 0.99)
        p_overdue = np.clip(p_stress_overdue * 0.20 * (1.0 + stress * 0.25), 0, 0.75)
        overdue_mask = rng_obj.random(n) < p_overdue
        base_pd = np.where(overdue_mask,
                           np.clip(rng_obj.exponential(20, n), 1, 89).astype(int), 0)
        default_month_mask = def_flag_v & (months_to_def == 0)
        pd_days = np.where(default_month_mask,
                           np.clip(90 + rng_obj.exponential(20, n).astype(int), 90, 180),
                           base_pd).astype(int)

        ext_cnt = np.clip(rng_obj.poisson(0.3 + p_stress * 2.5, n).astype(int), 0, 8)
        cov_cnt = np.clip(rng_obj.poisson(0.05 + p_stress * 1.0, n).astype(int), 0, 5)
        io_mo = np.clip(rng_obj.poisson(0.1 + p_stress * 2.0, n).astype(int), 0, 24)
        restruct = (rng_obj.random(n) < (0.003 + p_stress * 0.10)).astype(int)
        refi_cnt = np.clip(rng_obj.poisson(0.1 + p_stress * 0.8, n).astype(int), 0, 4)

        ews_fall = np.clip(-chg3m / 15.0, 0, 1)
        ews_level = np.clip(1.0 - new_ews / 60.0, 0, 1)
        alert_base = np.clip(ews_fall * 0.6 + ews_level * 0.4, 0, 1)
        alert_c = np.clip((alert_base * 8 + rng_obj.poisson(0.5, n)).astype(int), 0, 10)
        alert_s = np.clip(alert_c * 1.3 + rng_obj.exponential(0.3, n), 0, 15).round(2)

        past_cnt = np.clip(rng_obj.poisson(pd_days / 30.0, n).astype(int), 0, 12)
        uti = np.clip(0.3 + stress * 0.3 - z_score * 0.08 + rng_obj.normal(0, 0.08, n), 0, 1).round(3)
        ov_lim = (uti > 0.90).astype(int)
        watch_fl = (new_ews < 50).astype(int)

        aq_cd = np.where(pd_days >= 90, 'C', np.where(pd_days >= 30, 'B', 'A'))
        ifrs_cd = np.where(pd_days >= 90, '3', np.where(pd_days > 0, '2', '1'))

        rtg = np.clip(np.array([{'대기업': 2, '중견기업': 4, '중소기업': 6, '소기업': 8}[
                                    companies[ci]['firm_size_cd']] for ci in active]) + rng_obj.integers(-1, 2, n), 1, 10)
        rtg_chg = np.clip(rng_obj.integers(-2, 3, n), -5, 5)
        cr_health = np.clip(new_ews * 0.6 + rng_obj.normal(0, 5, n), 0, 100).round(1)

        dep_bal = np.clip(np.array([{'대기업': 500, '중견기업': 100, '중소기업': 20, '소기업': 5}[
                                        companies[ci]['firm_size_cd']] for ci in active], dtype=float) *
                          (1 - stress * beta_v * 0.3) + rng_obj.normal(0, 5, n), 0.1, 5000).round(2)
        inf_chg = np.clip(rng_obj.normal(-stress * 10, 8, n), -50, 50).round(2)
        iof_rat = np.clip(rng_obj.normal(0.95, 0.1, n), 0.3, 2.0).round(3)
        src_conc = np.clip(rng_obj.beta(2, 3, n), 0, 1).round(3)
        xfer_spk = (rng_obj.random(n) < (0.05 + stress * 0.1)).astype(int)
        dormant = (rng_obj.random(n) < 0.02).astype(int)
        dep_sl = np.clip(rng_obj.normal(-stress * 1, 0.5, n), -5, 5).round(4)
        dep_std = np.clip(rng_obj.exponential(2, n), 0.1, 20).round(3)
        inf_cv = np.clip(rng_obj.exponential(0.2, n), 0.01, 2).round(3)
        cash_rng = np.clip(rng_obj.exponential(5, n), 0.5, 50).round(3)

        ind_str = (stress * ind_mult_v * 100).round(2)
        dscr_sl = np.clip(rng_obj.normal(-stress * 0.1, 0.05, n), -0.5, 0.5).round(4)
        ltv_sl = np.clip(rng_obj.normal(stress * 0.5, 0.3, n), -2, 5).round(4)
        sg_sl = np.clip(rng_obj.normal(-stress * 2, 1, n), -10, 10).round(4)
        hs_std = np.clip(rng_obj.exponential(5, n), 0.5, 30).round(3)
        ews_std2 = np.clip(rng_obj.exponential(4, n), 0.3, 25).round(3)
        guar_rm = np.clip(rng_obj.integers(0, 60, n), 0, 60)

        # contagion_exposure_flag
        guarantor_def_ym_v = ca['guarantor_def_ym'][active]
        contagion_exp_flag = (guarantor_def_ym_v <= ym).astype(int)

        # payroll 선행성
        payroll_sudden_intensity = np.where(
            (path_v == 1) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 8),
            (8.0 - months_to_def) / 8.0, 0.0)
        payroll_contagion_intensity = np.where(
            (path_v == 3) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 5),
            (5.0 - months_to_def) / 5.0 * 0.7, 0.0)
        payroll_lead = np.maximum(payroll_sudden_intensity, payroll_contagion_intensity)
        payroll_dl = ((payroll_lead > 0.35) | (beh_total > 0.65)).astype(int)
        payroll_amount_pct = np.clip(
            100.0 - payroll_lead * 45.0 - beh_total * 10.0 + rng_obj.normal(0, 5, n),
            30, 100).round(1)

        lam_tax = np.clip(1.0 + beh_total * 3.0 + payroll_lead * 2.0, 0.1, 10.0)
        tax_arr_months = np.where(
            tax_arr | (payroll_lead > 0.5),
            np.clip(rng_obj.poisson(lam_tax), 0, 12), 0).astype(int)

        # 대안 데이터 5종 (D1~D5)
        # D1: 카드매출 성장률
        card_sudden_int = np.where(
            (path_v == 1) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 6),
            (6.0 - months_to_def) / 6.0, 0.0)
        card_grad_int = np.where(
            (path_v == 0) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 12),
            (12.0 - months_to_def) / 12.0 * 0.65, 0.0)
        card_cont_int = np.where(
            (path_v == 3) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 6),
            (6.0 - months_to_def) / 6.0 * 0.8, 0.0)
        card_stress_v = np.maximum(np.maximum(card_sudden_int, card_grad_int), card_cont_int)
        card_sales_growth = np.clip(
            phase_mf * 5 + rng_obj.normal(0, 8, n) - card_stress_v * 30 - stress * 5,
            -50, 50).round(2)

        # D2: 전력 사용량 지수
        elect_weight = np.where(
            (ind_idx_v == INDUSTRIES.index('일반제조업')) |
            (ind_idx_v == INDUSTRIES.index('첨단제조업')), 1.60,
            np.where(ind_idx_v == INDUSTRIES.index('운수창고업'), 1.30,
                     np.where(ind_idx_v == INDUSTRIES.index('건설업'), 1.20, 1.0)))
        electricity_idx = np.clip(
            100 + phase_mf * 8 * elect_weight - card_stress_v * 15 - stress * 10
            + rng_obj.normal(0, 5, n), 55, 160).round(1)

        # D3: 수출신고 건수 지수
        fx_export_adj = -fx_dev * fx_ind_v * 25
        export_idx = np.clip(
            100 + fx_export_adj + phase_mf * 6 - card_stress_v * 10
            + rng_obj.normal(0, 8, n), 25, 220).round(1)

        # D4: 뉴스/공시 감성 지수
        news_sudden_int = np.where(
            (path_v == 1) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 4),
            (4.0 - months_to_def) / 4.0, 0.0)
        news_grad_int = np.where(
            (path_v == 0) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 9),
            (9.0 - months_to_def) / 9.0 * 0.70, 0.0)
        news_cont_int = np.where(
            (path_v == 3) & def_flag_v & (months_to_def >= 0) & (months_to_def <= 5),
            (5.0 - months_to_def) / 5.0 * 0.75, 0.0)
        news_stress_v = np.maximum(np.maximum(news_sudden_int, news_grad_int), news_cont_int)
        news_sentiment = np.clip(
            0.30 - stress * 0.35 - news_stress_v * 1.20
            + rng_obj.normal(0, 0.18, n), -1, 1).round(3)

        # D5: 임대차 계약 변동
        lease_prob = np.clip(
            0.04 + card_stress_v * 0.28
            + (ind_idx_v == INDUSTRIES.index('부동산업')).astype(float) * 0.18
            + (size_idx_v == 3).astype(float) * 0.08,
            0, 0.55)
        lease_change = np.where(
            rng_obj.random(n) < lease_prob,
            np.where(card_stress_v > 0.3, -1, 1),
            0).astype(int)

        # 6. split_set
        split_sets = []
        for j in range(n):
            if ym >= 202501:
                ss = 'real_production_scoring_2025'
            elif ym >= 202401:
                ss = 'real_production_scoring'
            elif ym >= 202307:
                ss = 'real_shadow_validation'
            elif ym >= 202301:
                ss = 'real_retraining'
            else:
                h = (abs(hash(bids[active[j]])) + ym) % 10
                ss = 'synthetic_validation' if h == 0 else 'synthetic_train'
            split_sets.append(ss)

        lbl_status = 'pending' if ym_add(ym, 12) > YM_END else 'confirmed'
        scr_run = f"BATCH_{ym}"
        prod_fl = 1 if ym == YM_END else 0
        obs_end = ym_add(ym, 12)

        # 이전 달 ml rows를 현재 달 grade로 채워 DB 기록
        if prev_ml_buf:
            curr_state_map = {bids[active[j]]: {
                'grade': grades[j],
                'gidx': GRADE_SEQ.index(grades[j]),
                'ews': float(new_ews[j])
            } for j in range(n)}
            for row in prev_ml_buf:
                bid = row[0]
                cs = curr_state_map.get(bid)
                ps = prev_state.get(bid, {})
                if cs:
                    row[5] = 1 if cs['gidx'] > ps.get('gidx', cs['gidx']) else 0
                    row[6] = 1 if (row[5] and cs['ews'] < 50) else 0
                    row[7] = cs['grade']
                else:
                    row[5] = 0
                    row[6] = 0
                    row[7] = None
            conn.executemany(ML_SQL, [tuple(r) for r in prev_ml_buf])
            prev_ml_buf.clear()

        incorp_years_obs = (ym // 100) - incorp_yr_v.astype(int)

        for j in range(n):
            ci = active[j]
            bid = bids[ci]
            row = [
                bid, ym, split_sets[j],
                int(label_3m[j]), int(label_6m[j]),
                0, 0, None,
                companies[ci]['firm_size_cd'], ca['listed'][ci],
                companies[ci]['industry_cd'],
                int(incorp_years_obs[j]),
                float(new_ews[j]), float(prev3m[j]), float(chg3m[j]), float(slope6m[j]),
                int(rtg[j]), int(rtg_chg[j]), str(aq_cd[j]), str(ifrs_cd[j]),
                int(watch_fl[j]), float(uti[j]), int(ov_lim[j]),
                int(pd_days[j]), int(past_cnt[j]), int(ext_cnt[j]),
                int(cov_cnt[j]), int(io_mo[j]), int(restruct[j]), int(refi_cnt[j]),
                float(dep_bal[j]), float(inf_chg[j]), float(iof_rat[j]),
                float(src_conc[j]), int(xfer_spk[j]), int(dormant[j]),
                float(dte[j]), float(cr[j]), float(icr[j]), float(dscr[j]),
                float(ebitda[j]), float(sg[j]), float(ltv[j]),
                float(ind_str[j]), float(phase_mf), float(phase_rate),
                float(dscr_sl[j]), float(ltv_sl[j]), float(sg_sl[j]), float(dep_sl[j]),
                float(dte_rank[j]), float(icr_rank[j]), float(cr_rank[j]),
                float(dscr_rank[j]), float(ebitda_rk[j]), float(sg_rank[j]),
                float(dep_std[j]), float(inf_cv[j]), float(hs_std[j]),
                float(ews_std2[j]), float(cash_rng[j]),
                int(alert_c[j]), float(alert_s[j]), int(guar_rm[j]),
                lbl_status, obs_end, scr_run, 1, prod_fl,
                float(phase_fx),
                int(contagion_exp_flag[j]),
                float(payroll_amount_pct[j]),
                int(tax_arr_months[j]),
                float(card_sales_growth[j]),
                float(electricity_idx[j]),
                float(export_idx[j]),
                float(news_sentiment[j]),
                int(lease_change[j]),
                ind_sub_cd_active[j],
                int(1 if ym >= 202407 else 0),
            ]
            prev_ml_buf.append(row)

        prev_state = {bids[active[j]]: {
            'grade': grades[j],
            'gidx': GRADE_SEQ.index(grades[j]),
            'ews': float(new_ews[j])
        } for j in range(n)}

        for j in range(n):
            ci = active[j]
            bid = bids[ci]
            buf_ews.append((bid, ym, float(new_ews[j]), grades[j],
                            float(prev3m[j]), float(chg3m[j]),
                            float(slope6m[j]), float(conf[j]), 'EWS-v4.0'))
            buf_acc.append((bid, ym,
                            float(dep_bal[j]), float(inf_chg[j]), float(iof_rat[j]),
                            float(src_conc[j]), int(xfer_spk[j]), int(dormant[j]),
                            float(dep_sl[j]), float(dep_std[j]), float(inf_cv[j]),
                            float(cash_rng[j])))
            buf_crd.append((bid, ym,
                            float(uti[j]), int(ov_lim[j]), int(pd_days[j]),
                            int(past_cnt[j]), int(ext_cnt[j]), int(cov_cnt[j]),
                            int(io_mo[j]), int(restruct[j]), int(refi_cnt[j]),
                            int(watch_fl[j]), int(rtg[j]), int(rtg_chg[j]),
                            str(aq_cd[j]), str(ifrs_cd[j]), float(cr_health[j])))
            buf_beh.append((bid, ym,
                            int(rm_attempt[j]), int(rm_failed[j]), float(rm_fail_rt[j]),
                            int(site_visit[j]), int(doc_delay[j]), int(prom_breach[j]),
                            int(cov_miss[j]), int(mgmt_chg[j]), int(payroll_dl[j]),
                            int(tax_arr[j]), int(soc_arr[j]), int(group_anom[j]),
                            float(behavior_risk[j]),
                            float(payroll_amount_pct[j]),
                            int(tax_arr_months[j])))

        total_rows += n
        if len(buf_ews) >= FLUSH:
            flush_other()
            conn.commit()
            log(f"  flushed {total_rows:,} rows (ym={ym})")

    flush_other()

    for row in prev_ml_buf:
        row[5] = 0
        row[6] = 0
        row[7] = None
    if prev_ml_buf:
        conn.executemany(ML_SQL, [tuple(r) for r in prev_ml_buf])
        prev_ml_buf.clear()

    # 분기 재무 — 버퍼에서 동기화 생성
    section("S06 fact_quarterly_financial (동기화)")
    t1 = time.time()
    qrows = []
    q_sql = "INSERT OR IGNORE INTO fact_quarterly_financial VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
    for m_idx, ym in enumerate(MONTHS):
        if ym % 100 not in (3, 6, 9, 12):
            continue
        active = np.where((ca['entry_yms'] <= ym) & (ca['eff_exits'] >= ym))[0]
        if len(active) == 0:
            continue
        for j, ci in enumerate(active):
            bid = bids[ci]
            base = zfin_qbuf.get((bid, ym))
            if not base:
                continue
            q_dte, q_cr, q_icr, q_dscr, q_ebit, q_sg, q_ltv = base
            q_dte = round(np.clip(q_dte + rng_obj.normal(0, 4), 10, 2000), 1)
            q_cr = round(np.clip(q_cr + rng_obj.normal(0, 3), 30, 500), 1)
            q_icr = round(np.clip(q_icr + rng_obj.normal(0, 0.15), -5, 30), 2)
            q_dscr = round(np.clip(q_dscr + rng_obj.normal(0, 0.02), 0.1, 5), 3)
            q_ebit = round(np.clip(q_ebit + rng_obj.normal(0, 0.8), -30, 35), 2)
            sz = companies[ci]['firm_size_cd']
            q_rev = round(np.clip(
                {'대기업': 5000, '중견기업': 500, '중소기업': 50, '소기업': 5}[sz] *
                (1 + rng_obj.normal(0, 0.08)), 0.5, 100000), 1)
            q_npm = round(np.clip(rng_obj.normal(3 - PHASE_STRESS[m_idx] * 5, 2.5), -20, 20), 2)
            q_ocf = round(np.clip(q_rev * (q_npm / 100) + rng_obj.normal(0, 4), -500, 5000), 1)
            qrows.append((bid, ym, q_dte, q_cr, q_icr, q_dscr, q_ebit,
                          q_sg, q_ltv, q_rev, q_npm, q_ocf))
        if len(qrows) >= 100_000:
            conn.executemany(q_sql, qrows)
            qrows.clear()
            conn.commit()
    if qrows:
        conn.executemany(q_sql, qrows)
        conn.commit()
    log(f"fact_quarterly_financial 완료 ({time.time() - t1:.1f}초)")
    conn.commit()
    log(f"generate_monthly_data 완료: 총 {total_rows:,}행 ({time.time() - t0:.1f}초)")
    return total_rows, zfin_qbuf
