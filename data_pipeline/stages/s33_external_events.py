"""
s33_external_events.py — 외부 이벤트 생성 (v24 신규)

테이블:
  fact_external_events — 기업별 외부 신용 관련 이벤트

이벤트 유형:
  CREDIT_DOWNGRADE   — 외부 신용등급 하향 (무디스/S&P/한기평 등)
  LEGAL_JUDGMENT     — 소송 판결 (패소, 배상)
  REGULATORY_ACTION  — 감독당국 제재/경고
  INDUSTRY_SHOCK     — 업종 충격 (원자재 급등, 규제 변화)
  MERGER_ACQUISITION — M&A 발표/완료
  EXEC_CHANGE        — 대표이사 교체/사임
  MARKET_SHOCK       — 시장 충격 (환율/금리 급변)

severity: 1(미미) ~ 5(심각)
"""
import time
import numpy as np
from config.macro import YM_START, YM_END, MONTHS, PHASE_MAP
from config.companies import get_size_code

EVENT_TYPES = [
    "CREDIT_DOWNGRADE", "LEGAL_JUDGMENT", "REGULATORY_ACTION",
    "INDUSTRY_SHOCK", "MERGER_ACQUISITION", "EXEC_CHANGE", "MARKET_SHOCK",
]

# 생존기업 월별 이벤트 발생 기본 확률
BASE_PROB = {
    "CREDIT_DOWNGRADE": 0.003,
    "LEGAL_JUDGMENT":   0.005,
    "REGULATORY_ACTION":0.002,
    "INDUSTRY_SHOCK":   0.008,
    "MERGER_ACQUISITION":0.002,
    "EXEC_CHANGE":      0.004,
    "MARKET_SHOCK":     0.006,
}

# 부도 기업 이벤트 확률 배수 (악화기)
DEFAULT_BOOST = {
    "CREDIT_DOWNGRADE": 4.0,
    "LEGAL_JUDGMENT":   3.5,
    "REGULATORY_ACTION":2.0,
    "INDUSTRY_SHOCK":   1.5,
    "EXEC_CHANGE":      3.0,
    "MARKET_SHOCK":     1.5,
}

# Phase별 시장/업종 충격 배수
PHASE_EVENT_BOOST = {
    "CRISIS": 3.0, "RECESSION": 2.0, "RECOVERY": 1.0, "EXPANSION": 0.8,
}

DESCRIPTIONS = {
    "CREDIT_DOWNGRADE": ["외부 신용등급 1단계 하향", "외부 신용등급 2단계 하향", "신용등급 부정적 전망 변경"],
    "LEGAL_JUDGMENT":   ["손해배상 소송 패소", "계약 분쟁 패소", "세금 부과 처분 확정"],
    "REGULATORY_ACTION":["금융감독원 경고 조치", "공정거래위원회 시정명령", "환경부 과태료 부과"],
    "INDUSTRY_SHOCK":   ["주요 원자재 가격 30% 급등", "핵심 수출 시장 관세 부과", "업종 규제 강화"],
    "MERGER_ACQUISITION":["경쟁사 인수 발표", "핵심 사업부 매각", "전략적 투자자 유치"],
    "EXEC_CHANGE":      ["대표이사 갑작스러운 사임", "주요 경영진 교체", "창업주 경영 일선 퇴진"],
    "MARKET_SHOCK":     ["원/달러 환율 급등", "기준금리 급격 인상", "글로벌 금융시장 변동성 확대"],
}


def _phase_type(ym):
    entry = PHASE_MAP.get(ym)
    if entry is None:
        return "NORMAL"
    # PHASE_MAP 값은 (phase_name, stress) 튜플
    phase = entry[0] if isinstance(entry, tuple) else "NORMAL"
    return phase


def s33_external_events(conn, companies, rng):
    t0 = time.time()
    print("  [s33] 외부 이벤트 생성", flush=True)

    conn.execute("DELETE FROM fact_external_events")

    rows = []
    BATCH = 50_000

    for c in companies:
        bid = c['borrower_id']
        default_flag = c['default_flag']
        exit_ym = c.get('exit_ym') or (YM_END + 1)
        entry_ym = c.get('entry_ym') or YM_START
        firm_size = get_size_code(c.get('firm_size_cd', '소기업'))

        # 대기업/중견은 이벤트 발생 빈도 높음
        size_mult = {"L": 2.0, "M": 1.5, "S": 0.8}.get(firm_size, 1.0)

        for ym in MONTHS:
            if ym < entry_ym or ym >= exit_ym:
                continue

            months_to_exit = (exit_ym - ym) if default_flag and exit_ym <= YM_END else 999
            deterioration = max(0.0, 1.0 - months_to_exit / 24.0) if months_to_exit < 24 else 0.0

            phase = _phase_type(ym)
            phase_boost = PHASE_EVENT_BOOST.get(phase, 1.0)

            for etype in EVENT_TYPES:
                base = BASE_PROB[etype] * size_mult * phase_boost
                if default_flag and deterioration > 0:
                    boost = DEFAULT_BOOST.get(etype, 1.5)
                    prob = min(0.30, base + deterioration * base * boost)
                else:
                    prob = base

                if rng.random() > prob:
                    continue

                # severity: 부도 악화기일수록 높음
                sev_base = 1 + int(deterioration * 3)
                severity = int(np.clip(sev_base + rng.integers(0, 2), 1, 5))

                descs = DESCRIPTIONS[etype]
                desc = descs[rng.integers(0, len(descs))]

                rows.append((bid, ym, etype, severity, desc))

        if len(rows) >= BATCH:
            conn.executemany(
                "INSERT INTO fact_external_events "
                "(borrower_id, ym, event_type, event_severity, event_description) "
                "VALUES (?,?,?,?,?)",
                rows
            )
            conn.commit()
            rows = []

    if rows:
        conn.executemany(
            "INSERT INTO fact_external_events "
            "(borrower_id, ym, event_type, event_severity, event_description) "
            "VALUES (?,?,?,?,?)",
            rows
        )
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM fact_external_events").fetchone()[0]
    type_dist = conn.execute(
        "SELECT event_type, COUNT(*) FROM fact_external_events GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    elapsed = round(time.time() - t0, 1)
    print(f"    fact_external_events: {total:,}건", flush=True)
    for et, cnt in type_dist:
        print(f"      {et}: {cnt:,}건", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
