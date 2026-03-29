#!/usr/bin/env python3
"""EWS Corporate Credit Database v24 — Build Orchestrator

모듈형 점진적 빌드 시스템.
v18 단일 스크립트(2617줄) → v19 단계별 모듈 분리

사용 예:
  python3 build.py                          # 전체 빌드
  python3 build.py --from s05              # s05부터 재실행
  python3 build.py --only s02             # s02만 실행
  python3 build.py --rebuild-all          # 체크섬 무시, 전체 재빌드
  python3 build.py --validate             # 검증만 실행
  python3 build.py --compare v18.db v19.db # 두 DB 통계 비교
  python3 build.py --benchmark            # 단계별 타이밍 측정
  python3 build.py --companies 100 --months 12  # 소규모 테스트 빌드
"""
import argparse
import hashlib
import json
import os
import pickle
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

# Stage imports
from stages.s01_company import (
    build_companies, prepare_arrays, s01_insert_dim_company,
    create_schema, save_ca_to_db, load_ca_from_db, load_companies_from_db,
)
from stages.s02_reference import s02_ref_tables
from stages.s03_monthly import generate_monthly_data
from stages.s04_quarterly import s04_check_quarterly
from stages.s05_ml import s05_ml_tables
from stages.s06_network import s06_network
from stages.s07_ews import s07_action_and_migration
from stages.s08_collateral import s08_collateral
from stages.s09_model import s09_model_tables
from stages.s10_stress import s10_stress_sensitivity
from stages.s11_extensions import s11_extensions
from stages.s12_mnar import s12_mnar_noise
from stages.s13_centrality import s13_network_centrality
from stages.s14_leadtime import s14_leadtime_metrics
from stages.s15_validate import run_validation
from stages.s16_external import s16_external_data
from stages.s17_delinquency import s17_delinquency
from stages.s18_transaction import s18_transaction_behavior
from stages.s19_public_registry import s19_public_registry
from stages.s20_financial_ratio import s20_financial_ratio
from stages.s21_covenant import s21_covenant
from stages.s22_market_signal import s22_market_signal
from stages.s23_asset_class import s23_asset_classification
from stages.s24_group_credit import s24_group_credit
from stages.s25_esg import s25_esg
from stages.s26_financial_statement import s26_financial_statement
from stages.s27_ecl import s27_ecl
from stages.s28_credit_rating import s28_credit_rating
from stages.s29_workout import s29_workout
from stages.s30_loan_schedule import s30_loan_schedule
from stages.s31_credit_bureau import s31_credit_bureau
from stages.s32_collateral_disposal import s32_collateral_disposal
from stages.s33_external_events import s33_external_events
from stages.s34_ifrs9_stage_history import s34_ifrs9_stage_history
from stages.s35_regulatory_capital import s35_regulatory_capital

# ── 상수 ───────────────────────────────────────────────────────────────────
STAGES = ['s01', 's02', 's03', 's04', 's05', 's06', 's07',
          's08', 's09', 's10', 's11', 's12', 's13', 's14', 's16',
          's17', 's18', 's19', 's20', 's21', 's22', 's23', 's24', 's25',
          's26', 's27', 's28', 's29', 's30',
          's31', 's32', 's33', 's34', 's35']
ALLOWED_CONFIG_MODULES = ["companies", "macro", "default_rates", "mnar"]
CACHE_DIR = Path("cache")
DEFAULT_DB = Path("ews_corporate_v24.db")
DEFAULT_SEED = 42


def ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ── 체크섬 캐시 ────────────────────────────────────────────────────────────
def _stage_hash(stage_name: str) -> str:
    """단계 파일 + 관련 config 파일들의 해시"""
    h = hashlib.md5()
    # 단계 파일
    stage_file = Path("stages") / f"{stage_name}.py"
    if stage_file.exists():
        h.update(stage_file.read_bytes())
    # config 파일들
    for cfg in ALLOWED_CONFIG_MODULES:
        cfg_file = Path("config") / f"{cfg}.py"
        if cfg_file.exists():
            h.update(cfg_file.read_bytes())
    return h.hexdigest()


def load_checksums() -> dict:
    checksum_file = CACHE_DIR / ".checksums.json"
    if checksum_file.exists():
        try:
            return json.loads(checksum_file.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_checksums(checksums: dict):
    ensure_cache_dir()
    checksum_file = CACHE_DIR / ".checksums.json"
    checksum_file.write_text(json.dumps(checksums, indent=2))


def is_stage_cached(stage_name: str, checksums: dict) -> bool:
    return checksums.get(stage_name) == _stage_hash(stage_name)


def mark_stage_cached(stage_name: str, checksums: dict):
    checksums[stage_name] = _stage_hash(stage_name)


# ── RNG 스냅샷 ─────────────────────────────────────────────────────────────
def save_rng_state(rng, stage_name: str):
    ensure_cache_dir()
    state_file = CACHE_DIR / f"rng_state_{stage_name}.pkl"
    with open(state_file, "wb") as f:
        pickle.dump(rng.bit_generator.state, f)


def load_rng_state(rng, stage_name: str) -> bool:
    state_file = CACHE_DIR / f"rng_state_{stage_name}.pkl"
    if state_file.exists():
        with open(state_file, "rb") as f:
            rng.bit_generator.state = pickle.load(f)
        return True
    return False


# ── guarantee_pairs 복원 ──────────────────────────────────────────────────
def load_guarantee_pairs_from_db(conn, companies):
    """guarantee_network 테이블에서 guarantee_pairs 복원"""
    bid_to_idx = {c['borrower_id']: i for i, c in enumerate(companies)}
    rows = conn.execute(
        "SELECT guarantor_id, beneficiary_id, guarantee_amount_억, start_ym, end_ym "
        "FROM guarantee_network"
    ).fetchall()
    pairs = []
    for g_bid, b_bid, amt, s_ym, e_ym in rows:
        g_idx = bid_to_idx.get(g_bid)
        b_idx = bid_to_idx.get(b_bid)
        if g_idx is not None and b_idx is not None:
            pairs.append((g_idx, b_idx, amt, s_ym, e_ym))
    return pairs


# ── 메인 빌드 로직 ─────────────────────────────────────────────────────────
def run_build(args):
    db_path = Path(args.db)
    seed = args.seed or DEFAULT_SEED

    # --from / --only 파싱
    from_stage = args.from_stage.lower() if args.from_stage else None
    only_stage = args.only.lower() if args.only else None

    if from_stage and from_stage not in STAGES:
        print(f"오류: --from {from_stage} 는 유효하지 않은 단계입니다. 유효: {STAGES}")
        sys.exit(1)
    if only_stage and only_stage not in STAGES:
        print(f"오류: --only {only_stage} 는 유효하지 않은 단계입니다. 유효: {STAGES}")
        sys.exit(1)

    # 실행할 단계 목록
    if only_stage:
        stages_to_run = [only_stage]
    elif from_stage:
        start_idx = STAGES.index(from_stage)
        stages_to_run = STAGES[start_idx:]
    else:
        stages_to_run = list(STAGES)

    # DB 연결
    need_fresh = (not from_stage and not only_stage) or (from_stage == 's01') or (only_stage == 's01')
    if need_fresh and db_path.exists():
        db_path.unlink()

    # 새 DB 생성 시 캐시 무효화 (DB 연결 전에 확인 — connect()가 파일을 생성하기 때문)
    db_is_fresh = not db_path.exists()
    if db_is_fresh or args.rebuild_all:
        checksums = {}
    else:
        checksums = load_checksums()

    # config 오버라이드는 DB 연결 전에 먼저 실행 (배열/월 목록이 이후 코드에 반영되도록)
    if args.companies:
        _override_n_companies(args.companies)
    if args.months:
        _override_n_months(args.months)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=400000")

    # RNG 초기화
    rng = np.random.default_rng(seed)

    # --from 시 이전 단계 RNG 상태 복원
    if from_stage:
        prev_idx = STAGES.index(from_stage) - 1
        if prev_idx >= 0:
            prev_stage = STAGES[prev_idx]
            if not load_rng_state(rng, prev_stage):
                print(f"경고: {prev_stage} RNG 상태 파일 없음 — seed={seed}로 초기화")

    companies = None
    guarantee_pairs = None
    ca = None
    total_rows = 0
    zfin_qbuf = {}
    stage_timings = {}

    print("=" * 70)
    print(f" EWS Corporate Credit Database v24.0 — 빌드 시작")
    print(f" DB: {db_path} | seed={seed} | 단계: {stages_to_run}")
    print("=" * 70)
    t_global = time.time()

    for stage in stages_to_run:
        # 체크섬 캐시 확인
        if (not args.rebuild_all and is_stage_cached(stage, checksums)
                and stage not in ('s01', 's02')):
            print(f"\n  [{stage}] 캐시 유효 — 건너뜀")
            continue

        t_stage = time.time()
        save_rng_state(rng, stage)

        print(f"\n  [{stage}] 시작...", flush=True)

        if stage == 's01':
            create_schema(conn)
            companies, guarantee_pairs = build_companies(rng)
            ca = prepare_arrays(companies, guarantee_pairs)
            s01_insert_dim_company(conn, companies)
            save_ca_to_db(conn, ca)

        elif stage == 's02':
            if companies is None:
                companies = load_companies_from_db(conn)
            s02_ref_tables(conn, rng)

        elif stage == 's03':
            if companies is None:
                companies = load_companies_from_db(conn)
            if ca is None:
                ca = load_ca_from_db(conn)
            total_rows, zfin_qbuf = generate_monthly_data(conn, companies, ca, rng)

        elif stage == 's04':
            s04_check_quarterly(conn)

        elif stage == 's05':
            if companies is None:
                companies = load_companies_from_db(conn)
            s05_ml_tables(conn, companies)

        elif stage == 's06':
            if companies is None:
                companies = load_companies_from_db(conn)
            if guarantee_pairs is None:
                guarantee_pairs = load_guarantee_pairs_from_db(conn, companies)
            s06_network(conn, companies, guarantee_pairs)

        elif stage == 's07':
            if companies is None:
                companies = load_companies_from_db(conn)
            s07_action_and_migration(conn, companies, rng)

        elif stage == 's08':
            if companies is None:
                companies = load_companies_from_db(conn)
            if ca is None:
                ca = load_ca_from_db(conn)
            s08_collateral(conn, companies, ca, rng)

        elif stage == 's09':
            s09_model_tables(conn, rng)

        elif stage == 's10':
            s10_stress_sensitivity(conn)

        elif stage == 's11':
            s11_extensions(conn, rng)

        elif stage == 's12':
            if companies is None:
                companies = load_companies_from_db(conn)
            s12_mnar_noise(conn, companies)

        elif stage == 's13':
            if companies is None:
                companies = load_companies_from_db(conn)
            if guarantee_pairs is None:
                guarantee_pairs = load_guarantee_pairs_from_db(conn, companies)
            s13_network_centrality(conn, companies, guarantee_pairs, rng)

        elif stage == 's14':
            s14_leadtime_metrics(conn)

        elif stage == 's16':
            if companies is None:
                companies = load_companies_from_db(conn)
            s16_external_data(conn, companies)

        elif stage == 's17':
            if companies is None:
                companies = load_companies_from_db(conn)
            s17_delinquency(conn, companies, rng)

        elif stage == 's18':
            if companies is None:
                companies = load_companies_from_db(conn)
            s18_transaction_behavior(conn, companies, rng)

        elif stage == 's19':
            if companies is None:
                companies = load_companies_from_db(conn)
            s19_public_registry(conn, companies, rng)

        elif stage == 's20':
            if companies is None:
                companies = load_companies_from_db(conn)
            s20_financial_ratio(conn, companies, rng)

        elif stage == 's21':
            if companies is None:
                companies = load_companies_from_db(conn)
            s21_covenant(conn, companies, rng)

        elif stage == 's22':
            if companies is None:
                companies = load_companies_from_db(conn)
            s22_market_signal(conn, companies, rng)

        elif stage == 's23':
            if companies is None:
                companies = load_companies_from_db(conn)
            s23_asset_classification(conn, companies, rng)

        elif stage == 's24':
            if companies is None:
                companies = load_companies_from_db(conn)
            if guarantee_pairs is None:
                guarantee_pairs = load_guarantee_pairs_from_db(conn, companies)
            s24_group_credit(conn, companies, guarantee_pairs, rng)

        elif stage == 's25':
            if companies is None:
                companies = load_companies_from_db(conn)
            s25_esg(conn, companies, rng)

        elif stage == 's26':
            if companies is None:
                companies = load_companies_from_db(conn)
            s26_financial_statement(conn, companies, rng)

        elif stage == 's27':
            if companies is None:
                companies = load_companies_from_db(conn)
            s27_ecl(conn, companies, rng)

        elif stage == 's28':
            if companies is None:
                companies = load_companies_from_db(conn)
            s28_credit_rating(conn, companies, rng)

        elif stage == 's29':
            if companies is None:
                companies = load_companies_from_db(conn)
            s29_workout(conn, companies, rng)

        elif stage == 's30':
            if companies is None:
                companies = load_companies_from_db(conn)
            s30_loan_schedule(conn, companies, rng)

        elif stage == 's31':
            if companies is None:
                companies = load_companies_from_db(conn)
            s31_credit_bureau(conn, companies, rng)

        elif stage == 's32':
            if companies is None:
                companies = load_companies_from_db(conn)
            s32_collateral_disposal(conn, companies, rng)

        elif stage == 's33':
            if companies is None:
                companies = load_companies_from_db(conn)
            s33_external_events(conn, companies, rng)

        elif stage == 's34':
            if companies is None:
                companies = load_companies_from_db(conn)
            s34_ifrs9_stage_history(conn, companies, rng)

        elif stage == 's35':
            if companies is None:
                companies = load_companies_from_db(conn)
            s35_regulatory_capital(conn, companies, rng)

        elapsed_stage = time.time() - t_stage
        stage_timings[stage] = elapsed_stage
        mark_stage_cached(stage, checksums)
        save_checksums(checksums)
        print(f"  [{stage}] 완료 ({elapsed_stage:.1f}초)", flush=True)

    # dataset_registry 업데이트
    if total_rows > 0:
        conn.execute(
            "UPDATE dataset_registry SET row_count=?, description=? WHERE version='v23.0'",
            (total_rows,
             'v24 합성 데이터셋 — 60K기업|108개월|v23기반+신용조회이력+담보처분+외부이벤트+IFRS9스테이지이력+규제자본버퍼'))
        conn.commit()

    # WAL 체크포인트
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass

    # --validate 실행
    if args.validate or (not only_stage and not from_stage):
        print("\n[검증 실행]")
        n_co_param = args.companies or None
        passed = run_validation(conn, n_companies=n_co_param)
        conn.close()
        elapsed_total = time.time() - t_global

        if args.benchmark:
            _print_benchmark(stage_timings)

        print(f"\n  총 소요: {elapsed_total:.1f}초")
        sys.exit(0 if passed else 1)

    conn.close()
    elapsed_total = time.time() - t_global

    if args.benchmark:
        _print_benchmark(stage_timings)

    print(f"\n  빌드 완료: {db_path}")
    print(f"  총 소요: {elapsed_total:.1f}초")


def _print_benchmark(stage_timings: dict):
    print("\n[단계별 타이밍]")
    print(f"  {'단계':<8} {'소요(초)':>10}")
    print(f"  {'-' * 20}")
    for stage, t in stage_timings.items():
        print(f"  {stage:<8} {t:>10.1f}")


def _override_n_companies(n: int):
    """config.companies의 N_COMPANIES를 런타임에 오버라이드 (테스트용).
    stage 모듈들이 from config.companies import X 로 바인딩한 이름도 함께 패치.
    """
    import config.companies as cc
    import numpy as _np

    # FIRM_SIZE_CFG 비율 유지하며 스케일
    original_total = sum(c[1] for c in cc.FIRM_SIZE_CFG)
    scale = n / original_total
    new_cfg = []
    allocated = 0
    for i, (size_cd, n_co, *rest) in enumerate(cc.FIRM_SIZE_CFG):
        if i < len(cc.FIRM_SIZE_CFG) - 1:
            new_n = max(1, int(n_co * scale))
            allocated += new_n
        else:
            new_n = max(1, n - allocated)
        new_cfg.append((size_cd, new_n) + tuple(rest))
    cc.FIRM_SIZE_CFG = new_cfg
    cc.N_COMPANIES = sum(c[1] for c in cc.FIRM_SIZE_CFG)
    cc.AR_RHO_ARR = _np.array([cc.AR_RHO[c[0]] for c in cc.FIRM_SIZE_CFG
                                for _ in range(c[1])], dtype=float)

    # stage 모듈 네임스페이스도 패치 (from config.companies import X 바인딩)
    import sys
    _CO_ATTRS = {
        'FIRM_SIZE_CFG': cc.FIRM_SIZE_CFG,
        'N_COMPANIES': cc.N_COMPANIES,
        'AR_RHO_ARR': cc.AR_RHO_ARR,
    }
    for mod_name, mod in list(sys.modules.items()):
        if mod_name.startswith('stages.') or mod_name.startswith('config.'):
            for attr, val in _CO_ATTRS.items():
                if hasattr(mod, attr):
                    setattr(mod, attr, val)

    print(f"  [override] N_COMPANIES={cc.N_COMPANIES}")


def _override_n_months(n: int):
    """config.macro의 N_MONTHS를 런타임에 오버라이드 (테스트용).
    stage 모듈들이 from config.macro import X 로 바인딩한 이름도 함께 패치.
    """
    import config.macro as cm
    import numpy as _np

    new_months = []
    ym = cm.YM_START
    for _ in range(n):
        if ym > 202512:
            break
        new_months.append(ym)
        ym = cm.ym_add(ym, 1)

    cm.MONTHS = new_months
    cm.N_MONTHS = len(new_months)
    cm.YM_END = new_months[-1] if new_months else cm.YM_START
    cm.YM_INDEX = {m: i for i, m in enumerate(cm.MONTHS)}
    cm.QUARTER_MONTHS = [m for m in cm.MONTHS if m % 100 in (3, 6, 9, 12)]
    cm.PHASE_STRESS = _np.array([cm.PHASE_MAP[m][1] for m in cm.MONTHS])
    cm.PHASE_DM = _np.array([cm.PHASE_MAP[m][2] for m in cm.MONTHS])
    cm.PHASE_RATE = _np.array([cm.PHASE_MAP[m][3] for m in cm.MONTHS])
    cm.PHASE_MF = _np.array([cm.PHASE_MAP[m][4] for m in cm.MONTHS])
    cm.PHASE_FX = _np.array([cm.PHASE_MAP[m][5] for m in cm.MONTHS])

    # stage 모듈 네임스페이스도 패치
    import sys
    _MACRO_ATTRS = {
        'MONTHS': cm.MONTHS, 'N_MONTHS': cm.N_MONTHS, 'YM_END': cm.YM_END,
        'YM_INDEX': cm.YM_INDEX, 'QUARTER_MONTHS': cm.QUARTER_MONTHS,
        'PHASE_STRESS': cm.PHASE_STRESS, 'PHASE_DM': cm.PHASE_DM,
        'PHASE_RATE': cm.PHASE_RATE, 'PHASE_MF': cm.PHASE_MF, 'PHASE_FX': cm.PHASE_FX,
    }
    for mod_name, mod in list(sys.modules.items()):
        if mod_name.startswith('stages.'):
            for attr, val in _MACRO_ATTRS.items():
                if hasattr(mod, attr):
                    setattr(mod, attr, val)

    print(f"  [override] N_MONTHS={cm.N_MONTHS} YM_END={cm.YM_END}")


# ── --compare ──────────────────────────────────────────────────────────────
def run_compare(old_db: str, new_db: str):
    """두 DB의 통계 분포 비교 (Chi-squared + KS test)"""
    try:
        from scipy import stats as sp_stats
    except ImportError:
        print("오류: scipy가 필요합니다 (pip install scipy)")
        sys.exit(1)

    print(f"\n[비교] {old_db} vs {new_db}")
    conn_old = sqlite3.connect(old_db)
    conn_new = sqlite3.connect(new_db)

    # 1. dim_company default_flag 분포 — Chi-squared
    def get_default_dist(conn):
        r = conn.execute(
            "SELECT default_flag, COUNT(*) FROM dim_company GROUP BY default_flag"
        ).fetchall()
        return {row[0]: row[1] for row in r}

    old_dist = get_default_dist(conn_old)
    new_dist = get_default_dist(conn_new)
    keys = sorted(set(old_dist) | set(new_dist))
    old_vals = [old_dist.get(k, 0) for k in keys]
    new_vals = [new_dist.get(k, 0) for k in keys]
    if sum(old_vals) > 0 and sum(new_vals) > 0:
        # 정규화
        old_f = [v / sum(old_vals) for v in old_vals]
        new_f = [v / sum(new_vals) for v in new_vals]
        chi2, p_chi2 = sp_stats.chisquare(new_f, f_exp=old_f)
        print(f"  default_flag Chi-squared: chi2={chi2:.4f}  p={p_chi2:.4f}  "
              f"{'PASS' if p_chi2 > 0.05 else 'FAIL'}")
    else:
        print("  default_flag Chi-squared: 데이터 없음")

    # 2. fact_ews_score 분포 — KS test
    def get_ews_sample(conn, n=10000):
        rows = conn.execute(
            f"SELECT ews_score FROM fact_ews_score LIMIT {n}"
        ).fetchall()
        return [r[0] for r in rows if r[0] is not None]

    old_ews = get_ews_sample(conn_old)
    new_ews = get_ews_sample(conn_new)
    if old_ews and new_ews:
        ks_stat, p_ks = sp_stats.ks_2samp(old_ews, new_ews)
        print(f"  ews_score KS-test:         ks={ks_stat:.4f}  p={p_ks:.4f}  "
              f"{'PASS' if p_ks > 0.05 else 'FAIL'}")
    else:
        print("  ews_score KS-test: 데이터 없음")

    conn_old.close()
    conn_new.close()


# ── --sweep ────────────────────────────────────────────────────────────────
def run_sweep(config_module: str, config_key: str, start: float, end: float, step: float,
              base_args):
    """파라미터 스윕 (화이트리스트 검증 + 디스크 공간 확인)"""
    # 보안: 화이트리스트 검증
    if config_module not in ALLOWED_CONFIG_MODULES:
        print(f"오류: --sweep 허용 모듈: {ALLOWED_CONFIG_MODULES}")
        sys.exit(1)

    # 경로 순회 방지
    if '..' in config_module or '/' in config_module or '\\' in config_module:
        print("오류: config_module에 경로 문자 불가")
        sys.exit(1)

    if start >= end:
        print("오류: START >= END")
        sys.exit(1)
    if step <= 0:
        print("오류: STEP <= 0")
        sys.exit(1)

    values = []
    v = start
    while v <= end + 1e-9:
        values.append(v)
        v += step

    # 디스크 공간 확인 (반복 수 × ~5GB)
    n_iter = len(values)
    required_bytes = n_iter * 5 * 1024 ** 3
    free_bytes = shutil.disk_usage('.').free
    if free_bytes < required_bytes:
        print(f"경고: 디스크 공간 부족 "
              f"(필요={required_bytes / 1024 ** 3:.1f}GB, "
              f"여유={free_bytes / 1024 ** 3:.1f}GB)")
        print("  계속하려면 Enter, 중단하려면 Ctrl+C")
        try:
            input()
        except KeyboardInterrupt:
            sys.exit(1)

    print(f"\n[스윕] {config_module}.{config_key}: {start}~{end} step={step} ({n_iter}회)")

    sweep_dir = Path("sweeps")
    sweep_dir.mkdir(exist_ok=True)

    results = []
    for i, val in enumerate(values):
        print(f"\n  반복 {i + 1}/{n_iter}: {config_key}={val}")
        # config 오버라이드
        import importlib
        mod = importlib.import_module(f"config.{config_module}")
        orig_val = getattr(mod, config_key, None)
        setattr(mod, config_key, val)

        db_name = f"sweep_{config_module}_{config_key}_{val:.4f}.db"
        db_path = sweep_dir / db_name

        # 간단한 빌드 실행 (s01+s02 캐시 활용 의도)
        import copy
        sweep_args = copy.copy(base_args)
        sweep_args.db = str(db_path)
        sweep_args.validate = False
        sweep_args.benchmark = False
        sweep_args.from_stage = None
        sweep_args.only = None
        sweep_args.rebuild_all = True
        sweep_args.compare = None

        try:
            run_build(sweep_args)
            # 간단한 결과 수집
            conn = sqlite3.connect(str(db_path))
            n_def = conn.execute(
                "SELECT COUNT(*) FROM dim_company WHERE default_flag=1"
            ).fetchone()[0]
            conn.close()
            results.append({'value': val, 'n_defaults': n_def, 'db': str(db_path)})
            print(f"    부도 수: {n_def:,}")
        except Exception as e:
            print(f"    오류: {e}")
            results.append({'value': val, 'error': str(e)})
        finally:
            # 원래 값 복원
            if orig_val is not None:
                setattr(mod, config_key, orig_val)

    # 결과 저장
    result_file = sweep_dir / f"sweep_{config_module}_{config_key}.json"
    result_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n  스윕 결과 저장: {result_file}")


# ── CLI ────────────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(
        description="EWS Corporate Credit Database v21 Build Orchestrator"
    )
    p.add_argument("--from", dest="from_stage", metavar="SNN",
                   help="이 단계부터 실행 (예: --from s05)")
    p.add_argument("--only", metavar="SNN",
                   help="이 단계만 실행 (예: --only s02)")
    p.add_argument("--rebuild-all", action="store_true",
                   help="체크섬 무시, 전체 재빌드")
    p.add_argument("--validate", action="store_true",
                   help="s15_validate 실행 후 exit 0/1")
    p.add_argument("--compare", nargs=2, metavar=("OLD_DB", "NEW_DB"),
                   help="두 DB 통계 비교 (Chi-squared + KS)")
    p.add_argument("--sweep", nargs=4,
                   metavar=("CONFIG_MODULE.KEY", "START", "END", "STEP"),
                   help="파라미터 스윕")
    p.add_argument("--benchmark", action="store_true",
                   help="단계별 타이밍 측정 출력")
    p.add_argument("--companies", type=int, metavar="N",
                   help="N_COMPANIES 오버라이드")
    p.add_argument("--months", type=int, metavar="N",
                   help="N_MONTHS 오버라이드")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED,
                   help=f"난수 시드 (기본값: {DEFAULT_SEED})")
    p.add_argument("--db", default=str(DEFAULT_DB),
                   help=f"출력 DB 경로 (기본값: {DEFAULT_DB})")
    return p.parse_args()


def main():
    args = parse_args()

    # --compare
    if args.compare:
        run_compare(args.compare[0], args.compare[1])
        return

    # --sweep
    if args.sweep:
        module_key = args.sweep[0]
        if '.' not in module_key:
            print("오류: --sweep 형식: MODULE.KEY START END STEP")
            sys.exit(1)
        config_module, config_key = module_key.split('.', 1)
        try:
            start = float(args.sweep[1])
            end = float(args.sweep[2])
            step = float(args.sweep[3])
        except ValueError:
            print("오류: START, END, STEP은 숫자여야 합니다")
            sys.exit(1)
        run_sweep(config_module, config_key, start, end, step, args)
        return

    # 일반 빌드
    run_build(args)


if __name__ == "__main__":
    main()
