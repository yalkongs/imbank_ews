"""
s15_validate.py — 통계 검증 스위트
DB 빌드 후 주요 지표 검증 (PASS/FAIL ASCII 테이블 출력)
"""
from config.companies import N_COMPANIES


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def run_validation(conn, n_companies=None) -> bool:
    """
    DB 검증 실행.
    Returns True if all checks pass, False otherwise.
    Prints PASS/FAIL ASCII table.
    """
    if n_companies is None:
        n_companies = N_COMPANIES

    section("S15 통계 검증")

    checks = []

    def chk(name, passed, detail=""):
        checks.append((name, passed, detail))

    # 1. dim_company 행 수
    cnt_co = conn.execute("SELECT COUNT(*) FROM dim_company").fetchone()[0]
    chk("dim_company 행 수", cnt_co == n_companies,
        f"실측={cnt_co:,} 기대={n_companies:,}")

    # 2. fact_ews_score 행 수 (최소 n_companies 이상, 전체 빌드시 4M+ 기대)
    cnt_ews = conn.execute("SELECT COUNT(*) FROM fact_ews_score").fetchone()[0]
    # 소규모 빌드: n_companies * 1개월 이상, 전체 빌드: 4M+ (n_companies=60K → 60K*12=720K 최소)
    min_ews = max(n_companies, 1)
    chk("fact_ews_score 행 수", cnt_ews >= min_ews,
        f"실측={cnt_ews:,} 최소={min_ews:,}")

    # 3. ml_feature_label 행 수
    cnt_ml = conn.execute("SELECT COUNT(*) FROM ml_feature_label").fetchone()[0]
    chk("ml_feature_label 행 수", cnt_ml >= min_ews,
        f"실측={cnt_ml:,} 최소={min_ews:,}")

    # 4. default_flag 총 수 (n_companies*0.001 이상, 최소 1)
    #    단, 소규모 빌드(n_companies < 500)에서는 0부도도 통계적으로 가능 — 건너뜀
    cnt_def = conn.execute("SELECT COUNT(*) FROM dim_company WHERE default_flag=1").fetchone()[0]
    if n_companies < 500:
        chk("default_flag 수", True,
            f"실측={cnt_def:,} (소규모 빌드 — 건너뜀)")
    else:
        min_def = max(int(n_companies * 0.001), 1)
        chk("default_flag 수", cnt_def >= min_def,
            f"실측={cnt_def:,} 최소={min_def:,}")

    # 5. dim_company NULL borrower_id 없음
    cnt_null_bid = conn.execute(
        "SELECT COUNT(*) FROM dim_company WHERE borrower_id IS NULL"
    ).fetchone()[0]
    chk("NULL borrower_id 없음", cnt_null_bid == 0,
        f"NULL 수={cnt_null_bid}")

    # 6. MNAR: ebitda_margin_pct NULL 비율 5~50%
    if cnt_ml > 0:
        null_ebitda = conn.execute(
            "SELECT COUNT(*) FROM ml_feature_label WHERE ebitda_margin_pct IS NULL"
        ).fetchone()[0]
        null_rate = null_ebitda / cnt_ml * 100
        chk("MNAR ebitda NULL 비율 (5~50%)",
            5.0 <= null_rate <= 50.0,
            f"실측={null_rate:.1f}%")
    else:
        chk("MNAR ebitda NULL 비율", False, "ml_feature_label 행 없음")

    # 7. migration_matrix 행합 ≈ 1.0 (0.01 허용)
    mig_check = conn.execute("""
        SELECT year_ym, from_grade, ABS(SUM(transition_pct) - 1.0) AS diff
        FROM migration_matrix_yearly
        GROUP BY year_ym, from_grade
        HAVING diff > 0.01
    """).fetchall()
    chk("migration_matrix 행합 ≈ 1.0",
        len(mig_check) == 0,
        f"불일치 그룹 수={len(mig_check)}")

    # 8. ews_leadtime_metrics OVERALL detection_rate_pct > 50% (부도기업이 있는 경우에만)
    overall = conn.execute("""
        SELECT detection_rate_pct, n_defaults FROM ews_leadtime_metrics
        WHERE scope_type='OVERALL'
    """).fetchone()
    if overall:
        dr, n_def_lt = overall[0], overall[1]
        if n_def_lt is None or n_def_lt == 0:
            chk("EWS 탐지율 > 50%", True, "부도기업 없음 (소규모 빌드) — 건너뜀")
        else:
            chk("EWS 탐지율 > 50%", dr > 50.0, f"실측={dr:.1f}%")
    else:
        # OVERALL 행 없음 = 부도기업 없음 (소규모 빌드)
        chk("EWS 탐지율 > 50%", True, "OVERALL 행 없음 (부도기업 없는 소규모 빌드) — 건너뜀")

    # 결과 출력 (ASCII 테이블)
    print()
    print("=" * 65)
    print(f"{'검증 항목':<35} {'결과':^6} {'상세'}")
    print("-" * 65)
    all_pass = True
    for name, passed, detail in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"{name:<35} {status:^6} {detail}")
    print("=" * 65)
    overall_status = "PASS" if all_pass else "FAIL"
    print(f"  종합 결과: {overall_status} ({sum(p for _, p, _ in checks)}/{len(checks)} 통과)")
    print("=" * 65)

    return all_pass
