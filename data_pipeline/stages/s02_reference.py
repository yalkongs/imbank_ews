"""
s02_reference.py — ref_macro / ref_industry_macro / ref_industry_stress /
                   ref_region_industry_profile 생성
"""
from config.macro import (
    MONTHS, QUARTER_MONTHS, PHASE_MAP, YM_END,
)
from config.companies import (
    INDUSTRIES, IND_CODE, IND_STRESS_MULT,
    DAEGU_GYEONGBUK_REGIONS, DAEGU_IND_BOOST, DAEGU_IND_STRESS_MULT,
    FX_IND_IMPACT,
)
from config.default_rates import base_dr_for_ind


def log(msg):
    print(f"  {msg}", flush=True)


def section(t):
    print(f"\n[{t}]", flush=True)


def s02_ref_tables(conn, rng):
    section("S02 ref_macro / ref_industry / ref_region_industry_profile")
    macro_rows = []
    for ym in MONTHS:
        ph = PHASE_MAP[ym]
        gdp = round(float(rng.normal(3.0 - ph[1] * 4, 0.5)), 2)
        unemp = round(float(rng.normal(3.5 + ph[1] * 1.5, 0.3)), 2)
        cpi = round(float(rng.normal(1.5 + ph[1] * 3, 0.5)), 2)
        fx = round(float(ph[5] + rng.normal(0, 15)), 0)
        ksic_ver = 'KSIC-11' if ym >= 202407 else 'KSIC-10'
        macro_rows.append((ym, ph[3], ph[4], gdp, unemp, cpi, ph[0], ph[1],
                           1 if ph[0] == 'COVID_POLICY_SUPPORT' else 0,
                           fx, 1 if fx >= 1300 else 0, ksic_ver))
    conn.executemany("INSERT OR IGNORE INTO ref_macro VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", macro_rows)

    ind_rows = []
    for ym_q in QUARTER_MONTHS:
        st = PHASE_MAP[ym_q][1]
        for ind in INDUSTRIES:
            mult = IND_STRESS_MULT[ind]
            ind_rows.append((ym_q, IND_CODE[ind], ind,
                             round(float(rng.normal(3 - st * 5 * mult, 2)), 2),
                             round(float(st * mult * 100), 2),
                             round(float(rng.normal(5 - st * 8, 3)), 2)))
    conn.executemany("INSERT OR IGNORE INTO ref_industry_macro VALUES (?,?,?,?,?,?)", ind_rows)

    stress_rows = []
    for ym_q in QUARTER_MONTHS:
        st = PHASE_MAP[ym_q][1]
        for ind in INDUSTRIES:
            mult = IND_STRESS_MULT[ind]
            stress_rows.append((ym_q, IND_CODE[ind],
                                round(float(st * mult * 100), 2),
                                round(float(st * mult * base_dr_for_ind(ind)), 4),
                                round(float(st * mult), 3)))
    conn.executemany("INSERT OR IGNORE INTO ref_industry_stress VALUES (?,?,?,?,?)", stress_rows)

    # ref_region_industry_profile (대구/경북/울산 특화)
    rip_rows = []
    for region_cd in ['대구', '경북', '울산']:
        for ind in INDUSTRIES:
            ind_cd = IND_CODE[ind]
            w_mult = DAEGU_IND_BOOST.get(ind, 1.0)
            s_mult = DAEGU_IND_STRESS_MULT.get(ind, 1.0)
            fx_mult = round(FX_IND_IMPACT[ind] * s_mult, 3)
            rip_rows.append((region_cd, ind_cd, round(w_mult, 2), round(s_mult, 2), fx_mult,
                             f"IM뱅크 {region_cd} {ind} 특화 프로파일"))
    conn.executemany("INSERT OR IGNORE INTO ref_region_industry_profile VALUES (?,?,?,?,?,?)", rip_rows)

    conn.execute("""
        UPDATE ref_region_industry_profile
        SET stress_sensitivity_mult = 1.6,
            notes = '경북 관광지역(경주·안동·포항) 숙박업 집중 — v15 K07A 추가 상향'
        WHERE region_cd = '경북' AND industry_cd = 'K07A'
    """)
    conn.execute("""
        UPDATE ref_region_industry_profile
        SET stress_sensitivity_mult = 1.25,
            notes = '경북 포항·영덕 에너지·광업 법인 집중 — v17 K13 추가 상향'
        WHERE region_cd = '경북' AND industry_cd = 'K13'
    """)

    conn.commit()
    log("ref 테이블 완료")
