"""
s35_regulatory_capital.py — 규제자본 버퍼 참조 테이블 생성 (v24 신규)

테이블:
  regulatory_capital_buffer — 기업규모×업종×EWS등급별 필요 자본 버퍼율

바젤III 기준:
  - 보통주자본(CET1) 최저: 4.5%
  - 자본보전 버퍼:        2.5%
  - 경기대응 버퍼:        0.0~2.5%
  - 내부 추가 버퍼 (신용위험): 등급별 0.5~5.0%

EWS 등급: A(양호), B(주의), C(위험), D(부실)
"""
import time

# 기업규모 코드
FIRM_SIZES = ["대기업", "중견기업", "중소기업", "소기업"]

# 업종 코드 (주요 업종)
INDUSTRY_CODES = [
    "K00", "K01A", "K01B", "K02", "K03",
    "K04", "K05", "K06", "K07", "K08",
    "K09", "K10", "K11", "K12", "K13",
]

# EWS 등급별 기본 내부 버퍼율 (%)
EWS_BASE_BUFFER = {
    "A": 0.5,   # 양호
    "B": 1.5,   # 주의
    "C": 3.0,   # 위험
    "D": 5.0,   # 부실
}

# 기업규모별 추가 버퍼율 (%)
SIZE_ADDON = {
    "대기업":  0.0,   # 대기업은 관리 능력 우수 (SIFI 제외)
    "중견기업": 0.3,
    "중소기업": 0.8,
    "소기업":  1.2,
}

# 업종별 추가 버퍼율 (경기민감도 반영)
IND_ADDON = {
    "K00": 0.3,   # 복합
    "K01A": 0.2,  # 제조(일반)
    "K01B": 0.1,  # 제조(첨단)
    "K02": 0.5,   # 건설 (경기 민감)
    "K03": 0.2,   # 도소매
    "K04": 0.3,   # 운수
    "K05": 0.1,   # IT (낮은 실물 리스크)
    "K06": 0.0,   # 금융 (별도 규제)
    "K07": 0.2,   # 부동산
    "K08": 0.2,   # 전문서비스
    "K09": 0.3,   # 보건
    "K10": 0.4,   # 숙박/음식
    "K11": 0.4,   # 농림어업
    "K12": 0.3,   # 광업
    "K13": 0.2,   # 에너지/환경
}

# 업종별 설명
IND_NOTES = {
    "K00": "복합업종",
    "K01A": "제조업(일반)",
    "K01B": "제조업(첨단)",
    "K02": "건설업",
    "K03": "도소매업",
    "K04": "운수업",
    "K05": "정보통신업",
    "K06": "금융보험업",
    "K07": "부동산업",
    "K08": "전문서비스업",
    "K09": "보건사회서비스",
    "K10": "숙박음식업",
    "K11": "농림어업",
    "K12": "광업",
    "K13": "에너지환경업",
}

EWS_NOTES = {
    "A": "양호 — CET1 기본 버퍼 적용",
    "B": "주의 — SICR 발생, 추가 충당금 적립",
    "C": "위험 — Stage2/3 전이, 집중 감시",
    "D": "부실 — 부도 인정, 최대 버퍼 적용",
}


def s35_regulatory_capital(conn, companies, rng):
    t0 = time.time()
    print("  [s35] 규제자본 버퍼 참조 테이블 생성", flush=True)

    conn.execute("DELETE FROM regulatory_capital_buffer")

    rows = []

    for firm_size in FIRM_SIZES:
        for ind_cd in INDUSTRY_CODES:
            for ews_grade in ["A", "B", "C", "D"]:
                base = EWS_BASE_BUFFER[ews_grade]
                size_add = SIZE_ADDON[firm_size]
                ind_add = IND_ADDON.get(ind_cd, 0.3)

                required_buffer = round(base + size_add + ind_add, 2)

                ind_note = IND_NOTES.get(ind_cd, ind_cd)
                ews_note = EWS_NOTES[ews_grade]
                note = f"{ind_note} | {firm_size} | EWS-{ews_grade}: {ews_note}"

                rows.append((firm_size, ind_cd, ews_grade, required_buffer, note))

    conn.executemany(
        "INSERT INTO regulatory_capital_buffer "
        "(firm_size_cd, industry_cd, ews_grade, required_buffer_pct, notes) "
        "VALUES (?,?,?,?,?)",
        rows
    )
    conn.commit()

    total = len(rows)

    # 등급별 평균 버퍼율
    avg_dist = conn.execute(
        "SELECT ews_grade, ROUND(AVG(required_buffer_pct),2) "
        "FROM regulatory_capital_buffer GROUP BY 1 ORDER BY 1"
    ).fetchall()

    elapsed = round(time.time() - t0, 1)
    print(f"    regulatory_capital_buffer: {total:,}건", flush=True)
    for grade, avg_buf in avg_dist:
        print(f"      EWS-{grade}: 평균 {avg_buf}%", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
