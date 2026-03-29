"""
s19_public_registry.py — 공적정보 이벤트 생성 (v23 개선)

v23 개선:
  - EVENT 경로 기업: SEIZURE/COURT_FILING/AUDIT_OPINION 확률 1.8~2.5× 상향
  - EVENT 경로 이벤트 타이밍: exit 3~6개월 전 집중 (기존 lead_months 유지하되 좁혀짐)

테이블:
  fact_public_registry — 법원/국세청/건강보험공단 공시 이벤트

이벤트 유형:
  TAX_DELINQUENT     — 국세청 세금 체납 공개
  SOCIAL_INSURANCE   — 건강보험공단 사회보험 체납
  SEIZURE            — 재산 압류 (법원)
  AUDIT_OPINION      — 외부감사 의견 한정/거절
  MGMT_CHANGE        — 대표자/임원 변경 (중요 이벤트)
  COURT_FILING       — 법원 신청(회생/파산)
  RATING_DOWNGRADE   — 신용등급 하락 이벤트
  TAX_INVESTIGATION  — 세무조사 착수
"""
import time
import uuid
from config.macro import YM_START, YM_END, MONTHS, ym_add

import numpy as np

EVENT_CONFIG = {
    "TAX_DELINQUENT": {
        "base_prob_default": 0.55, "base_prob_survive": 0.03,
        "severity_dist": [("HIGH", 0.45), ("MEDIUM", 0.35), ("LOW", 0.20)],
        "lead_months": (-18, -3),
    },
    "SOCIAL_INSURANCE": {
        "base_prob_default": 0.40, "base_prob_survive": 0.02,
        "severity_dist": [("MEDIUM", 0.55), ("HIGH", 0.25), ("LOW", 0.20)],
        "lead_months": (-12, -1),
    },
    "SEIZURE": {
        "base_prob_default": 0.35, "base_prob_survive": 0.01,
        "severity_dist": [("HIGH", 0.60), ("CRITICAL", 0.25), ("MEDIUM", 0.15)],
        "lead_months": (-15, -2),
    },
    "AUDIT_OPINION": {
        "base_prob_default": 0.30, "base_prob_survive": 0.02,
        "severity_dist": [("HIGH", 0.50), ("CRITICAL", 0.30), ("MEDIUM", 0.20)],
        "lead_months": (-24, -6),
    },
    "MGMT_CHANGE": {
        "base_prob_default": 0.45, "base_prob_survive": 0.10,
        "severity_dist": [("MEDIUM", 0.50), ("HIGH", 0.30), ("LOW", 0.20)],
        "lead_months": (-18, -3),
    },
    "COURT_FILING": {
        "base_prob_default": 0.25, "base_prob_survive": 0.001,
        "severity_dist": [("CRITICAL", 0.75), ("HIGH", 0.25)],
        "lead_months": (-6, 0),
    },
    "RATING_DOWNGRADE": {
        "base_prob_default": 0.50, "base_prob_survive": 0.05,
        "severity_dist": [("HIGH", 0.50), ("MEDIUM", 0.35), ("LOW", 0.15)],
        "lead_months": (-12, -2),
    },
    "TAX_INVESTIGATION": {
        "base_prob_default": 0.20, "base_prob_survive": 0.02,
        "severity_dist": [("MEDIUM", 0.55), ("HIGH", 0.30), ("LOW", 0.15)],
        "lead_months": (-24, -6),
    },
}

AMOUNT_RANGE = {
    "TAX_DELINQUENT":    (0.1, 30.0),
    "SOCIAL_INSURANCE":  (0.05, 5.0),
    "SEIZURE":           (0.5, 50.0),
    "AUDIT_OPINION":     (0.0, 0.0),
    "MGMT_CHANGE":       (0.0, 0.0),
    "COURT_FILING":      (5.0, 500.0),
    "RATING_DOWNGRADE":  (0.0, 0.0),
    "TAX_INVESTIGATION": (0.1, 20.0),
}

DESCRIPTIONS = {
    "TAX_DELINQUENT":    ["국세 체납 공개 명단 등재", "부가가치세 체납 발생", "법인세 체납 확인"],
    "SOCIAL_INSURANCE":  ["건강보험료 체납 발생", "국민연금 체납 확인", "고용보험 미납"],
    "SEIZURE":           ["법인 계좌 압류 결정", "부동산 가압류 신청", "동산 강제집행"],
    "AUDIT_OPINION":     ["감사의견 한정 수령", "감사의견 거절 수령", "계속기업 의구심 주석"],
    "MGMT_CHANGE":       ["대표이사 교체 확인", "주요 임원 집단 사임", "최대주주 변경"],
    "COURT_FILING":      ["법원 회생절차 개시 신청", "파산 신청 접수", "기업구조조정 신청"],
    "RATING_DOWNGRADE":  ["신용등급 2단계 이상 하락", "신용등급 부정적 전망 부여", "워치리스트 편입"],
    "TAX_INVESTIGATION": ["세무조사 착수 통보", "특별 세무조사 시작", "국세청 세무조사 진행"],
}

SOURCES = {
    "TAX_DELINQUENT":    "국세청",
    "SOCIAL_INSURANCE":  "건강보험공단",
    "SEIZURE":           "법원경매",
    "AUDIT_OPINION":     "금융감독원/DART",
    "MGMT_CHANGE":       "기업공시",
    "COURT_FILING":      "법원",
    "RATING_DOWNGRADE":  "신용평가사",
    "TAX_INVESTIGATION": "국세청",
}


def _pick_weighted(choices, rng):
    items, weights = zip(*choices)
    return items[rng.choice(len(items), p=list(weights))]


def s19_public_registry(conn, companies, rng):
    t0 = time.time()
    print("  [s19] 공적정보 이벤트 생성", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_public_registry")
    conn.execute("""
        CREATE TABLE fact_public_registry (
            event_id      TEXT PRIMARY KEY,
            borrower_id   TEXT NOT NULL,
            event_date    TEXT NOT NULL,
            event_ym      INTEGER NOT NULL,
            event_type    TEXT NOT NULL,
            severity      TEXT NOT NULL,
            description   TEXT,
            source        TEXT,
            amount_억      REAL,
            resolved      INTEGER DEFAULT 0,
            resolved_date TEXT,
            action_required INTEGER DEFAULT 1,
            impact_score  REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pub_bid ON fact_public_registry(borrower_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pub_ym  ON fact_public_registry(event_ym)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pub_type ON fact_public_registry(event_type)")

    rows = []

    # EVENT 경로에서 확률이 높아지는 이벤트 유형
    EVENT_PATH_BOOST = {
        "SEIZURE":         2.5,
        "COURT_FILING":    2.0,
        "AUDIT_OPINION":   1.8,
        "TAX_DELINQUENT":  1.5,
        "RATING_DOWNGRADE": 1.5,
    }

    for c in companies:
        bid = c['borrower_id']
        default_flag = c['default_flag']
        exit_ym = c.get('exit_ym') or (YM_END + 1)
        entry_ym = c.get('entry_ym') or YM_START
        path_type = c.get('default_path_type') or 'ACUTE'
        is_event_path = (default_flag and path_type == 'EVENT')

        for event_type, cfg in EVENT_CONFIG.items():
            prob = cfg["base_prob_default"] if default_flag else cfg["base_prob_survive"]

            # EVENT 경로 기업은 특정 이벤트 확률 상향
            if is_event_path:
                boost = EVENT_PATH_BOOST.get(event_type, 1.0)
                prob = min(0.95, prob * boost)

            if rng.random() > prob:
                continue

            lead_min, lead_max = cfg["lead_months"]

            # EVENT 경로 기업은 타이밍을 exit 3~6개월 전으로 집중
            if is_event_path and exit_ym <= YM_END:
                lead_min = max(lead_min, -8)
                lead_max = min(lead_max, -2)

            # 이벤트 발생 시점
            if default_flag and exit_ym <= YM_END:
                base_ym = exit_ym
                event_ym = ym_add(base_ym, int(rng.integers(lead_min, lead_max + 1)))
            else:
                event_ym = MONTHS[rng.integers(0, len(MONTHS))]

            event_ym = max(entry_ym, min(YM_END, event_ym))
            year, month = divmod(event_ym, 100)
            event_date = f"{year}-{month:02d}-{rng.integers(1, 29):02d}"

            severity = _pick_weighted(cfg["severity_dist"], rng)

            # 금액
            amt_min, amt_max = AMOUNT_RANGE[event_type]
            amount = round(float(rng.uniform(amt_min, amt_max)), 2) if amt_max > 0 else None

            desc_list = DESCRIPTIONS[event_type]
            description = desc_list[rng.integers(0, len(desc_list))]

            # 해결 여부 (부도 기업은 거의 해결 안 됨)
            if default_flag:
                resolved = 1 if rng.random() < 0.15 else 0
            else:
                resolved = 1 if rng.random() < 0.65 else 0

            resolved_date = None
            if resolved:
                r_ym = ym_add(event_ym, int(rng.integers(1, 7)))
                if r_ym <= YM_END:
                    r_year, r_month = divmod(r_ym, 100)
                    resolved_date = f"{r_year}-{r_month:02d}-{rng.integers(1, 29):02d}"
                else:
                    resolved = 0

            # 영향도 점수 (0~1)
            sev_score = {"CRITICAL": 1.0, "HIGH": 0.75, "MEDIUM": 0.50, "LOW": 0.25}.get(severity, 0.5)
            impact_score = round(sev_score * rng.uniform(0.7, 1.0), 3)

            action_required = 1 if severity in ("HIGH", "CRITICAL") else (1 if rng.random() < 0.4 else 0)

            rows.append((
                str(uuid.uuid4()), bid, event_date, event_ym,
                event_type, severity, description,
                SOURCES[event_type], amount,
                resolved, resolved_date, action_required, impact_score
            ))

    conn.executemany("""
        INSERT INTO fact_public_registry
          (event_id, borrower_id, event_date, event_ym,
           event_type, severity, description, source, amount_억,
           resolved, resolved_date, action_required, impact_score)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()

    elapsed = round(time.time() - t0, 1)
    # 유형별 집계
    type_counts = conn.execute(
        "SELECT event_type, COUNT(*) FROM fact_public_registry GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    total = sum(r[1] for r in type_counts)
    print(f"    fact_public_registry: {total:,}건", flush=True)
    for etype, cnt in type_counts:
        print(f"      {etype}: {cnt:,}건", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
