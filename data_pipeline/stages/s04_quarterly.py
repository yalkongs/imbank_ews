"""
s04_quarterly.py — stub: fact_quarterly_financial는 s03에서 이미 기록됨.
단순히 행 수 확인.
"""


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s04_check_quarterly(conn):
    section("S04 fact_quarterly_financial (stub: written by s03)")
    cnt = conn.execute("SELECT COUNT(*) FROM fact_quarterly_financial").fetchone()[0]
    log(f"fact_quarterly_financial: {cnt:,}행 (s03에서 생성됨)")
    if cnt == 0:
        raise RuntimeError("fact_quarterly_financial 행이 없음 — s03을 먼저 실행하세요")
