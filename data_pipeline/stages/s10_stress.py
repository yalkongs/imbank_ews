"""
s10_stress.py — stress_macro_scenario / industry_stress_sensitivity 생성
v18의 s12_s13_stress_network() 중 스트레스 부분 → v19 s10_stress_sensitivity()
"""
import time

from config.companies import INDUSTRIES, IND_CODE, IND_STRESS_MULT, FX_IND_IMPACT


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s10_stress_sensitivity(conn):
    section("S10 stress_macro_scenario / industry_stress_sensitivity")
    t0 = time.time()

    conn.executemany("INSERT INTO stress_macro_scenario VALUES (?,?,?,?,?,?,?)", [
        (1, '기준시나리오', 'base', 0.0, 0, 1.0, 0.0),
        (2, '경기침체', 'adverse', -2.5, 200, 2.2, 3.0),
        (3, '금융위기', 'severe', -5.0, 500, 4.5, 8.0),
        (4, '환율급등', 'fx_shock', -1.5, 150, 1.8, 2.5),
    ])

    for ind in INDUSTRIES:
        conn.execute(
            "INSERT INTO industry_stress_sensitivity(industry_cd,scenario_name,"
            "pd_elasticity,revenue_shock_pct) VALUES (?,?,?,?)",
            (IND_CODE[ind], '경기침체',
             round(float(IND_STRESS_MULT[ind] * 1.5), 2),
             round(float(-IND_STRESS_MULT[ind] * 8), 2)))
        conn.execute(
            "INSERT INTO industry_stress_sensitivity(industry_cd,scenario_name,"
            "pd_elasticity,revenue_shock_pct) VALUES (?,?,?,?)",
            (IND_CODE[ind], '환율급등',
             round(float(FX_IND_IMPACT[ind] * 2.0), 2),
             round(float(-FX_IND_IMPACT[ind] * 12), 2)))

    # K07A/K07B 분리 탄력성
    k07_split_rows = [
        ('K07A', '경기침체', 3.2, -18.0),
        ('K07A', '환율급등', 0.5, -3.0),
        ('K07B', '경기침체', 2.3, -11.5),
        ('K07B', '환율급등', 0.4, -2.4),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO industry_stress_sensitivity VALUES (?,?,?,?)",
        k07_split_rows)

    conn.commit()
    log(f"stress/sensitivity 완료 → {time.time() - t0:.1f}초")
