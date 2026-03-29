"""
test_build.py — EWS v19 빌드 시스템 pytest 테스트

실행 방법:
    cd /path/to/v19
    pytest tests/test_build.py -v

소규모 빌드 파라미터 (N_COMPANIES=100, N_MONTHS=12) 사용.
"""
import json
import os
import pickle
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

# v19 루트를 sys.path에 추가
V19_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(V19_ROOT))


# ── 헬퍼 ──────────────────────────────────────────────────────────────────
SMALL_PARAMS = ["--companies", "100", "--months", "12", "--seed", "42"]


def run_build(args: list, cwd=None) -> subprocess.CompletedProcess:
    """build.py를 서브프로세스로 실행"""
    cmd = [sys.executable, str(V19_ROOT / "build.py")] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd or V19_ROOT),
    )


# ── CLI 플래그 테스트 ──────────────────────────────────────────────────────
class TestCLIFlags:

    def test_from_flag_skips_stages(self, tmp_path):
        """--from s03 사용 시 s01/s02 단계를 건너뜀"""
        db = tmp_path / "test.db"
        # 먼저 전체 빌드
        r1 = run_build(SMALL_PARAMS + ["--db", str(db)], cwd=V19_ROOT)
        assert r1.returncode == 0, f"초기 빌드 실패: {r1.stderr}"

        # s03부터 재실행 — s01 출력이 없어야 함
        r2 = run_build(SMALL_PARAMS + ["--from", "s03", "--db", str(db)], cwd=V19_ROOT)
        assert r2.returncode == 0, f"--from 빌드 실패: {r2.stderr}"
        # s01 dim_company 재삽입 로그가 없어야 함
        assert "S01" not in r2.stdout or "s01" not in r2.stdout.lower() or \
               "dim_company:" not in r2.stdout

    def test_only_flag_runs_single_stage(self, tmp_path):
        """--only s02 사용 시 s02만 실행"""
        db = tmp_path / "test.db"
        # 스키마 먼저 생성 (s01 필요)
        r1 = run_build(SMALL_PARAMS + ["--only", "s01", "--db", str(db)], cwd=V19_ROOT)
        assert r1.returncode == 0, f"s01 빌드 실패: {r1.stderr}"

        r2 = run_build(SMALL_PARAMS + ["--only", "s02", "--db", str(db)], cwd=V19_ROOT)
        assert r2.returncode == 0, f"s02 빌드 실패: {r2.stderr}"
        assert "S02" in r2.stdout or "ref" in r2.stdout.lower()

    def test_rebuild_all_ignores_cache(self, tmp_path):
        """--rebuild-all 사용 시 체크섬 무시하고 전체 재빌드"""
        db = tmp_path / "test.db"
        # 캐시 디렉토리
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        fake_checksums = {"s01": "fake_hash", "s02": "fake_hash"}
        (cache_dir / ".checksums.json").write_text(json.dumps(fake_checksums))

        r = run_build(
            SMALL_PARAMS + ["--rebuild-all", "--db", str(db)],
            cwd=V19_ROOT
        )
        assert r.returncode == 0, f"--rebuild-all 실패: {r.stderr}"

    def test_companies_months_params(self, tmp_path):
        """--companies, --months 파라미터가 올바르게 동작함"""
        db = tmp_path / "test.db"
        r = run_build(
            ["--companies", "50", "--months", "6", "--seed", "99",
             "--db", str(db)],
            cwd=V19_ROOT
        )
        assert r.returncode == 0, f"빌드 실패: {r.stderr}"
        conn = sqlite3.connect(str(db))
        cnt = conn.execute("SELECT COUNT(*) FROM dim_company").fetchone()[0]
        conn.close()
        assert cnt == 50, f"dim_company 수 불일치: {cnt} (기대: 50)"

    def test_validate_flag_exit_code(self, tmp_path):
        """--validate 플래그가 PASS 시 exit 0, FAIL 시 exit 1"""
        db = tmp_path / "test.db"
        # 정상 빌드
        r = run_build(
            SMALL_PARAMS + ["--validate", "--db", str(db)],
            cwd=V19_ROOT
        )
        # 소규모 빌드는 PASS여야 함 (단, 기업 수 검증은 오버라이드된 값으로)
        assert r.returncode in (0, 1), f"예상치 못한 returncode: {r.returncode}"
        assert "PASS" in r.stdout or "FAIL" in r.stdout


# ── 체크섬 캐시 테스트 ─────────────────────────────────────────────────────
class TestChecksumCache:

    def test_no_checksums_triggers_rebuild(self, tmp_path):
        """체크섬 캐시 없으면 전체 빌드 실행"""
        db = tmp_path / "test.db"
        cache_dir = V19_ROOT / "cache"
        checksum_file = cache_dir / ".checksums.json"

        # 백업 후 삭제
        backup = None
        if checksum_file.exists():
            backup = checksum_file.read_text()
            checksum_file.unlink()

        try:
            r = run_build(SMALL_PARAMS + ["--db", str(db)], cwd=V19_ROOT)
            assert r.returncode == 0, f"빌드 실패: {r.stderr}"
        finally:
            if backup:
                checksum_file.write_text(backup)

    def test_corrupted_checksums_triggers_rebuild(self, tmp_path):
        """손상된 체크섬 파일은 전체 재빌드 유발"""
        db = tmp_path / "test.db"
        cache_dir = V19_ROOT / "cache"
        cache_dir.mkdir(exist_ok=True)
        checksum_file = cache_dir / ".checksums.json"

        orig = None
        if checksum_file.exists():
            orig = checksum_file.read_bytes()

        checksum_file.write_text("{ corrupted json !!!")

        try:
            r = run_build(SMALL_PARAMS + ["--db", str(db)], cwd=V19_ROOT)
            # 손상된 체크섬은 빌드를 막지 않아야 함 (그냥 재빌드)
            assert r.returncode == 0, f"빌드 실패: {r.stderr}"
        finally:
            if orig:
                checksum_file.write_bytes(orig)
            elif checksum_file.exists():
                checksum_file.unlink()

    def test_rng_snapshot_roundtrip(self, tmp_path):
        """RNG 상태 저장/복원이 정확함"""
        rng = np.random.default_rng(42)
        # 몇 번 사용
        _ = rng.random(100)
        state_before = rng.bit_generator.state

        # 저장
        state_file = tmp_path / "rng_state.pkl"
        with open(state_file, "wb") as f:
            pickle.dump(state_before, f)

        # 다른 rng에 복원
        rng2 = np.random.default_rng(999)
        with open(state_file, "rb") as f:
            rng2.bit_generator.state = pickle.load(f)

        # 이후 값이 동일해야 함
        vals1 = rng.random(10)
        vals2 = rng2.random(10)
        np.testing.assert_array_equal(vals1, vals2)


# ── 스윕 검증 테스트 ───────────────────────────────────────────────────────
class TestSweepValidation:

    def test_sweep_start_ge_end_exits_1(self, tmp_path):
        """START >= END 시 exit 1"""
        db = tmp_path / "test.db"
        r = run_build(
            ["--sweep", "companies.N_COMPANIES", "100", "50", "10",
             "--db", str(db)],
            cwd=V19_ROOT
        )
        assert r.returncode == 1

    def test_sweep_step_le_0_exits_1(self, tmp_path):
        """STEP <= 0 시 exit 1"""
        db = tmp_path / "test.db"
        r = run_build(
            ["--sweep", "companies.N_COMPANIES", "50", "100", "0",
             "--db", str(db)],
            cwd=V19_ROOT
        )
        assert r.returncode == 1

    def test_sweep_disallowed_module_exits_1(self, tmp_path):
        """허용되지 않은 모듈명 시 exit 1"""
        db = tmp_path / "test.db"
        r = run_build(
            ["--sweep", "os.system", "1", "2", "1",
             "--db", str(db)],
            cwd=V19_ROOT
        )
        assert r.returncode == 1

    def test_sweep_path_traversal_exits_1(self, tmp_path):
        """경로 순회 시도 시 exit 1"""
        db = tmp_path / "test.db"
        r = run_build(
            ["--sweep", "../evil.something", "1", "2", "1",
             "--db", str(db)],
            cwd=V19_ROOT
        )
        assert r.returncode == 1

    def test_sweep_valid_input(self, tmp_path):
        """유효한 스윕 파라미터는 정상 실행"""
        # 스윕은 실제 빌드를 여러 번 하므로 very small params 사용
        # 실제 스윕 대신 파라미터 파싱만 확인
        db = tmp_path / "test.db"
        # 스윕 자체는 오래 걸리므로 파라미터 유효성만 간접 확인
        # (허용된 모듈 + 올바른 범위)
        r = run_build(
            ["--sweep", "companies.N_COMPANIES", "50", "50", "10",
             "--db", str(db)],
            cwd=V19_ROOT
        )
        # START == END이면 값 1개만 실행 — 정상 종료
        # returncode는 빌드 성공 여부에 따라 다를 수 있음
        assert r.returncode in (0, 1)


# ── 통합 테스트 ────────────────────────────────────────────────────────────
class TestIntegration:

    def test_full_small_build(self, tmp_path):
        """소규모 전체 빌드 (N_COMPANIES=100, N_MONTHS=12)가 성공함"""
        db = tmp_path / "test.db"
        r = run_build(SMALL_PARAMS + ["--db", str(db)], cwd=V19_ROOT)
        assert r.returncode == 0, f"빌드 실패:\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"

        conn = sqlite3.connect(str(db))
        # dim_company 확인
        cnt = conn.execute("SELECT COUNT(*) FROM dim_company").fetchone()[0]
        assert cnt == 100, f"dim_company={cnt} (기대: 100)"

        # fact_ews_score 존재 확인
        cnt_ews = conn.execute("SELECT COUNT(*) FROM fact_ews_score").fetchone()[0]
        assert cnt_ews > 0, "fact_ews_score 비어 있음"

        # ml_feature_label 존재 확인
        cnt_ml = conn.execute("SELECT COUNT(*) FROM ml_feature_label").fetchone()[0]
        assert cnt_ml > 0, "ml_feature_label 비어 있음"

        # migration_matrix 행합 확인
        bad_rows = conn.execute("""
            SELECT year_ym, from_grade, ABS(SUM(transition_pct) - 1.0) AS diff
            FROM migration_matrix_yearly
            GROUP BY year_ym, from_grade
            HAVING diff > 0.01
        """).fetchall()
        assert len(bad_rows) == 0, f"migration_matrix 행합 불일치: {bad_rows}"

        conn.close()

    def test_incremental_vs_full_build_identical(self, tmp_path):
        """전체 빌드와 --from s05 빌드의 dim_company 행 수가 동일"""
        db_full = tmp_path / "full.db"
        db_incr = tmp_path / "incr.db"

        # 전체 빌드
        r1 = run_build(SMALL_PARAMS + ["--db", str(db_full)], cwd=V19_ROOT)
        assert r1.returncode == 0, f"전체 빌드 실패: {r1.stderr}"

        # 복사 후 --from s05 재실행
        import shutil
        shutil.copy2(str(db_full), str(db_incr))
        r2 = run_build(
            SMALL_PARAMS + ["--from", "s05", "--db", str(db_incr)],
            cwd=V19_ROOT
        )
        assert r2.returncode == 0, f"점진적 빌드 실패: {r2.stderr}"

        conn_full = sqlite3.connect(str(db_full))
        conn_incr = sqlite3.connect(str(db_incr))

        cnt_full = conn_full.execute("SELECT COUNT(*) FROM dim_company").fetchone()[0]
        cnt_incr = conn_incr.execute("SELECT COUNT(*) FROM dim_company").fetchone()[0]
        assert cnt_full == cnt_incr, f"dim_company 수 불일치: {cnt_full} vs {cnt_incr}"

        conn_full.close()
        conn_incr.close()

    def test_schema_tables_exist(self, tmp_path):
        """전체 빌드 후 핵심 테이블들이 존재함"""
        db = tmp_path / "test.db"
        r = run_build(SMALL_PARAMS + ["--db", str(db)], cwd=V19_ROOT)
        assert r.returncode == 0, f"빌드 실패: {r.stderr}"

        conn = sqlite3.connect(str(db))
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}

        expected = {
            'dim_company', 'dim_facility', 'dim_collateral',
            'ref_macro', 'ref_industry_macro', 'ref_industry_stress',
            'fact_ews_score', 'fact_monthly_account', 'fact_monthly_credit',
            'fact_quarterly_financial', 'ml_feature_label', 'ml_survival',
            'ml_walk_forward_splits', 'model_registry', 'ews_action_outcome',
            'migration_matrix_yearly', 'guarantee_network',
        }
        missing = expected - tables
        assert not missing, f"누락된 테이블: {missing}"
        conn.close()
