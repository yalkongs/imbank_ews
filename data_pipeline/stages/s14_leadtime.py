"""
s14_leadtime.py — EWS Lead Time KPI 계산 (ews_leadtime_metrics)
v18의 s17_leadtime_metrics() → v19 s14_leadtime_metrics()
"""
import statistics as _stats
import time

from config.companies import GRADE_SEQ


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s14_leadtime_metrics(conn):
    """EWS Lead time KPI 계산 및 ews_leadtime_metrics 적재"""
    section("S14 Lead time KPI (ews_leadtime_metrics)")
    t0 = time.time()

    ALERT_THRESHOLD = 40.0

    lead_rows = conn.execute("""
        WITH first_alert AS (
            SELECT f.borrower_id, MIN(f.ym) AS first_alert_ym
            FROM fact_ews_score f
            JOIN dim_company c ON f.borrower_id = c.borrower_id
            WHERE c.default_flag = 1
              AND f.ews_score < 40.0
              AND f.ym < c.default_ym_internal
            GROUP BY f.borrower_id
        )
        SELECT
            c.borrower_id, c.default_ym_internal,
            c.default_path_type, c.industry_cd, c.industry_sub_cd, c.firm_size_cd,
            fa.first_alert_ym,
            CASE WHEN fa.first_alert_ym IS NOT NULL THEN
                (c.default_ym_internal/100 - fa.first_alert_ym/100)*12
                + (c.default_ym_internal%100 - fa.first_alert_ym%100)
            END AS lead_months
        FROM dim_company c
        LEFT JOIN first_alert fa ON c.borrower_id = fa.borrower_id
        WHERE c.default_flag = 1 AND c.default_ym_internal IS NOT NULL
    """).fetchall()
    log(f"부도기업 로드: {len(lead_rows)}개")

    folds = conn.execute(
        "SELECT fold_id, test_start_ym, test_end_ym FROM ml_walk_forward_splits"
    ).fetchall()

    def agg(subset):
        n = len(subset)
        if n == 0:
            return None
        lead = [x for x in subset if x is not None]
        n_det = len(lead)
        if not lead:
            avg_l = med_l = None
        else:
            avg_l = _stats.mean(lead)
            med_l = _stats.median(lead)

        def p(k):
            return sum(1 for x in lead if x >= k) / n * 100

        return dict(n_defaults=n, n_detected=n_det,
                    detection_rate_pct=round(n_det / n * 100, 2),
                    avg_lead_months=round(avg_l, 2) if avg_l else None,
                    median_lead_months=round(med_l, 2) if med_l else None,
                    pct_alert_before_3m=round(p(3), 2),
                    pct_alert_before_6m=round(p(6), 2),
                    pct_alert_before_12m=round(p(12), 2),
                    actionable_alert_ratio=round(p(3), 2),
                    early_detection_recall=round(p(6), 2))

    def ins(scope_type, scope_value, m):
        if m is None:
            return
        conn.execute("""
            INSERT INTO ews_leadtime_metrics
            (scope_type,scope_value,n_defaults,n_detected,detection_rate_pct,
             avg_lead_months,median_lead_months,
             pct_alert_before_3m,pct_alert_before_6m,pct_alert_before_12m,
             actionable_alert_ratio,early_detection_recall,
             alert_threshold_score,computed_ym)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,202512)
        """, (scope_type, scope_value,
              m['n_defaults'], m['n_detected'], m['detection_rate_pct'],
              m['avg_lead_months'], m['median_lead_months'],
              m['pct_alert_before_3m'], m['pct_alert_before_6m'], m['pct_alert_before_12m'],
              m['actionable_alert_ratio'], m['early_detection_recall'], ALERT_THRESHOLD))

    ins("OVERALL", "ALL", agg([r[7] for r in lead_rows]))
    for fid, ts, te in folds:
        ins("FOLD", str(fid), agg([r[7] for r in lead_rows if ts <= r[1] <= te]))
    for ind in sorted(set(r[3] for r in lead_rows)):
        ins("INDUSTRY", ind, agg([r[7] for r in lead_rows if r[3] == ind]))
    for path in ("GRADUAL", "SUDDEN", "CONTAGION"):
        ins("PATH_TYPE", path, agg([r[7] for r in lead_rows if r[2] == path]))
    for size in ("대기업", "중견기업", "중소기업", "소기업"):
        ins("SIZE", size, agg([r[7] for r in lead_rows if r[5] == size]))
    conn.commit()

    r = conn.execute(
        "SELECT n_defaults,n_detected,detection_rate_pct,avg_lead_months,median_lead_months,"
        "pct_alert_before_3m,pct_alert_before_6m FROM ews_leadtime_metrics WHERE scope_type='OVERALL'"
    ).fetchone()
    if r:
        log(f"부도:{r[0]} | 탐지:{r[1]}({r[2]:.1f}%) | 평균lead:{r[3]:.1f}m | 6m전:{r[6]:.1f}%")
    log(f"완료 ({time.time() - t0:.1f}초)")
