"""
s23_asset_class.py — 자산건전성 5단계 분류 이력 생성 (v23 개선)

v23 개선:
  - PRECAUTIONARY 재무비율 트리거 추가:
      부채비율 > 250%, ICR < 1.0, 유동비율 < 80% 중 1개 이상 → PRECAUTIONARY
  - SUBSTANDARD 트리거: 부채비율 > 400%, ICR < 0.5 → SUBSTANDARD
  - fact_financial_ratio 사전 로드 후 연도별 JOIN

테이블:
  fact_asset_classification — 월별 자산건전성 분류 스냅샷

금감원 5단계:
  NORMAL (정상)          : DPD < 1개월 또는 PD < 0.5%
  PRECAUTIONARY (요주의) : DPD 1~3개월 또는 PD 0.5~2%
  SUBSTANDARD (고정)     : DPD 3~6개월 또는 PD 2~10%
  DOUBTFUL (회수의문)    : DPD 6~12개월 또는 PD 10~50%
  LOSS (추정손실)        : DPD > 12개월 또는 PD > 50%

충당금률 (최저):
  NORMAL: 0.85%, PRECAUTIONARY: 7%, SUBSTANDARD: 20%, DOUBTFUL: 50%, LOSS: 100%
"""
import time
import numpy as np
from config.macro import YM_START, YM_END, MONTHS

PROVISION_RATE = {
    "NORMAL":         0.0085,
    "PRECAUTIONARY":  0.07,
    "SUBSTANDARD":    0.20,
    "DOUBTFUL":       0.50,
    "LOSS":           1.00,
}

CLASS_ORDER = ["NORMAL", "PRECAUTIONARY", "SUBSTANDARD", "DOUBTFUL", "LOSS"]


def _pd_to_class(pd_val):
    if pd_val is None:
        return "NORMAL"
    if pd_val > 0.50:
        return "LOSS"
    elif pd_val > 0.10:
        return "DOUBTFUL"
    elif pd_val > 0.02:
        return "SUBSTANDARD"
    elif pd_val > 0.005:
        return "PRECAUTIONARY"
    return "NORMAL"


def _dpd_to_class(dpd):
    if dpd is None or dpd == 0:
        return "NORMAL"
    if dpd > 365:
        return "LOSS"
    elif dpd > 180:
        return "LOSS"
    elif dpd > 90:
        return "DOUBTFUL"
    elif dpd > 60:
        return "SUBSTANDARD"
    elif dpd > 30:
        return "PRECAUTIONARY"
    return "NORMAL"


def _ratio_to_class(debt_ratio, ier, current_ratio):
    """재무비율 트리거 기반 자산 분류

    SUBSTANDARD  : 부채비율 > 400% 또는 ICR < 0.5
    PRECAUTIONARY: 부채비율 > 250% 또는 ICR < 1.0 또는 유동비율 < 80%
    """
    if debt_ratio is None and ier is None and current_ratio is None:
        return "NORMAL"
    sub_triggers = 0
    pre_triggers = 0
    if debt_ratio is not None:
        if debt_ratio > 400:
            sub_triggers += 1
        elif debt_ratio > 250:
            pre_triggers += 1
    if ier is not None:
        if ier < 0.5:
            sub_triggers += 1
        elif ier < 1.0:
            pre_triggers += 1
    if current_ratio is not None and current_ratio < 80:
        pre_triggers += 1

    if sub_triggers >= 1:
        return "SUBSTANDARD"
    if pre_triggers >= 1:
        return "PRECAUTIONARY"
    return "NORMAL"


def _worst_class(*classes):
    idx = 0
    for cls in classes:
        if cls in CLASS_ORDER:
            idx = max(idx, CLASS_ORDER.index(cls))
    return CLASS_ORDER[idx]


def s23_asset_classification(conn, companies, rng):
    t0 = time.time()
    print("  [s23] 자산건전성 5단계 분류 이력 생성", flush=True)

    conn.execute("DROP TABLE IF EXISTS fact_asset_classification")
    conn.execute("""
        CREATE TABLE fact_asset_classification (
            class_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id         TEXT NOT NULL,
            base_ym             INTEGER NOT NULL,
            classification      TEXT NOT NULL,
            prev_classification TEXT,
            class_changed       INTEGER DEFAULT 0,
            dpd                 INTEGER,
            pd_value            REAL,
            pd_based_class      TEXT,
            dpd_based_class     TEXT,
            ews_based_class     TEXT,
            final_class_basis   TEXT,
            exposure_억          REAL,
            provision_rate      REAL,
            required_provision_억 REAL,
            classified_by       TEXT DEFAULT 'SYSTEM',
            UNIQUE(borrower_id, base_ym)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_acls_bid ON fact_asset_classification(borrower_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_acls_ym  ON fact_asset_classification(base_ym)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_acls_cls ON fact_asset_classification(classification)")

    # 여신 정보 사전 로드
    facility_info = {}
    for row in conn.execute(
        "SELECT borrower_id, committed_amount_억, dpd, max_dpd_12m, asset_classification "
        "FROM dim_facility"
    ).fetchall():
        bid, lmt, dpd, max_dpd, cls = row
        if bid not in facility_info:
            facility_info[bid] = {"credit_limit_억": lmt, "dpd": dpd, "max_dpd_12m": max_dpd,
                                  "asset_classification": cls}

    # 재무비율 캐시 (borrower_id, year) → {debt_ratio, ier, current_ratio}
    ratio_cache = {}
    if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fact_financial_ratio'"
    ).fetchone():
        for row in conn.execute(
            "SELECT borrower_id, fiscal_year, debt_ratio, ier, current_ratio "
            "FROM fact_financial_ratio"
        ).fetchall():
            ratio_cache[(row[0], row[1])] = {"debt_ratio": row[2], "ier": row[3], "current_ratio": row[4]}

    # EWS 알림 정보 (월별 EWS 레벨)
    ews_alerts = {}
    for row in conn.execute(
        "SELECT borrower_id, ym, alert_level FROM ews_monthly_alert"
    ).fetchall() if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ews_monthly_alert'"
    ).fetchone() else []:
        ews_alerts[(row[0], row[1])] = row[2]

    rows = []
    BATCH = 50_000

    for c in companies:
        bid = c['borrower_id']
        default_flag = c['default_flag']
        exit_ym = c.get('exit_ym') or (YM_END + 1)
        entry_ym = c.get('entry_ym') or YM_START
        fac = facility_info.get(bid, {})
        credit_limit = float(fac.get('credit_limit_억') or 10.0)

        prev_class = "NORMAL"
        base_pd = 0.001 if not default_flag else rng.uniform(0.05, 0.50)

        for ym in MONTHS:
            if ym < entry_ym or ym >= exit_ym:
                continue

            months_to_exit = (exit_ym - ym) if default_flag and exit_ym <= YM_END else 999
            deterioration = max(0.0, 1.0 - months_to_exit / 24.0) if months_to_exit < 24 else 0.0

            # PD 추정 (부도기업은 exit 전 급상승)
            pd_noise = rng.lognormal(0, 0.3)
            pd_val = float(np.clip(
                base_pd * (1 + deterioration * 20) * pd_noise,
                0.0001, 0.9999
            ))

            # DPD 추정
            if default_flag and months_to_exit <= 12:
                _max_dpd = min(months_to_exit * 30, 365)
                dpd = int(rng.uniform(_max_dpd, _max_dpd + 30))
            elif default_flag and months_to_exit <= 24:
                dpd = int(rng.uniform(1, 60) * deterioration)
            else:
                dpd = int(rng.choice([0, 0, 0, 0, 1, 3, 7], p=[0.65, 0.12, 0.08, 0.05, 0.05, 0.03, 0.02]))

            # 재무비율 기반 분류 (연도별 JOIN)
            yr = ym // 100
            ratio = ratio_cache.get((bid, yr), {})
            ratio_class = _ratio_to_class(
                ratio.get("debt_ratio"), ratio.get("ier"), ratio.get("current_ratio")
            )

            # 각 기준별 분류
            pd_class = _pd_to_class(pd_val)
            dpd_class = _dpd_to_class(dpd)

            # EWS 기반 분류
            ews_level = ews_alerts.get((bid, ym))
            if ews_level == "urgent":
                ews_class = "SUBSTANDARD"
            elif ews_level == "alert":
                ews_class = "PRECAUTIONARY"
            else:
                ews_class = "NORMAL"

            # 최종 분류: 가장 나쁜 것 채택 (보수적)
            final_class = _worst_class(pd_class, dpd_class, ews_class, ratio_class)

            # 분류 근거
            if final_class == dpd_class and dpd > 0:
                basis = "DPD"
            elif final_class == ews_class and ews_class != "NORMAL":
                basis = "EWS"
            elif final_class == ratio_class and ratio_class != "NORMAL":
                basis = "RATIO"
            elif final_class == pd_class:
                basis = "PD"
            else:
                basis = "SYSTEM"

            class_changed = 1 if final_class != prev_class else 0

            # 충당금
            prov_rate = PROVISION_RATE[final_class]
            required_prov = round(credit_limit * prov_rate, 3)

            rows.append((
                bid, ym, final_class, prev_class, class_changed,
                dpd, round(pd_val, 6),
                pd_class, dpd_class, ews_class, basis,
                round(credit_limit, 2), round(prov_rate, 4), required_prov,
                "SYSTEM"
            ))

            prev_class = final_class

            if len(rows) >= BATCH:
                conn.executemany("""
                    INSERT OR IGNORE INTO fact_asset_classification
                      (borrower_id, base_ym, classification, prev_classification, class_changed,
                       dpd, pd_value, pd_based_class, dpd_based_class, ews_based_class,
                       final_class_basis, exposure_억, provision_rate, required_provision_억,
                       classified_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, rows)
                conn.commit()
                rows = []

    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO fact_asset_classification
              (borrower_id, base_ym, classification, prev_classification, class_changed,
               dpd, pd_value, pd_based_class, dpd_based_class, ews_based_class,
               final_class_basis, exposure_억, provision_rate, required_provision_억,
               classified_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM fact_asset_classification").fetchone()[0]
    # 분류 분포
    dist = conn.execute(
        "SELECT classification, COUNT(*) FROM fact_asset_classification GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    elapsed = round(time.time() - t0, 1)
    print(f"    fact_asset_classification: {total:,}행", flush=True)
    for cls, cnt in dist:
        print(f"      {cls}: {cnt:,}행 ({cnt/total*100:.1f}%)", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
