"""
s34_ifrs9_stage_history.py — IFRS9 스테이지 변동 이력 생성 (v24 신규)

테이블:
  fact_ifrs9_stage_history — 차주별 IFRS9 스테이지 전이 이력

fact_ecl_calculation의 stage_changed=1 레코드를 집계하여
차주별 스테이지 변동 이력(from→to, 유효기간, 트리거 사유) 생성.

스테이지:
  1 → 2 : SICR 발생 (12개월 ECL → 전기간 ECL)
  2 → 3 : 부도 인정 (전기간 ECL, 개별 평가)
  2 → 1 : 신용위험 해소 (복원)
  3 → 2 : 부도 해소 (부분 복원)
"""
import time
from config.macro import YM_END


def s34_ifrs9_stage_history(conn, companies, rng):
    t0 = time.time()
    print("  [s34] IFRS9 스테이지 변동 이력 생성", flush=True)

    conn.execute("DELETE FROM fact_ifrs9_stage_history")

    # fact_ecl_calculation에서 stage 변동 레코드 추출
    has_ecl = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fact_ecl_calculation'"
    ).fetchone()

    rows = []

    if has_ecl:
        # stage_changed=1인 레코드 (차주별, 시간순)
        changed = conn.execute("""
            SELECT borrower_id, base_ym, stage, prev_stage, sicr_trigger
            FROM fact_ecl_calculation
            WHERE stage_changed = 1
            ORDER BY borrower_id, base_ym
        """).fetchall()

        # 차주별로 from_ym ~ to_ym 계산 (다음 변동 시점까지)
        # borrower_id별 시퀀스 구성
        bid_events = {}
        for row in changed:
            bid = row[0]
            if bid not in bid_events:
                bid_events[bid] = []
            bid_events[bid].append(row)

        for bid, events in bid_events.items():
            for i, ev in enumerate(events):
                _, from_ym, to_stage, from_stage, trigger = ev
                # to_ym: 다음 변동 시점 - 1개월, 없으면 None
                if i + 1 < len(events):
                    to_ym = events[i + 1][1]
                else:
                    to_ym = None  # 현재까지 유효

                # 트리거 사유 텍스트
                if trigger:
                    reason = trigger
                elif from_stage and to_stage:
                    fs = str(from_stage)
                    ts = str(to_stage)
                    if ts > fs:
                        reason = "신용위험 증가"
                    else:
                        reason = "신용위험 해소"
                else:
                    reason = "정기 재평가"

                rows.append((
                    bid,
                    from_ym,
                    to_ym,
                    str(from_stage) if from_stage else "1",
                    str(to_stage),
                    reason,
                ))

    if rows:
        conn.executemany(
            "INSERT INTO fact_ifrs9_stage_history "
            "(borrower_id, from_ym, to_ym, from_stage, to_stage, trigger_reason) "
            "VALUES (?,?,?,?,?,?)",
            rows
        )
        conn.commit()

    total = len(rows)

    # 전이 방향별 집계
    direction_dist = {}
    for r in rows:
        key = f"Stage{r[3]}→Stage{r[4]}"
        direction_dist[key] = direction_dist.get(key, 0) + 1

    elapsed = round(time.time() - t0, 1)
    print(f"    fact_ifrs9_stage_history: {total:,}건", flush=True)
    for d, cnt in sorted(direction_dist.items(), key=lambda x: -x[1]):
        print(f"      {d}: {cnt:,}건", flush=True)
    print(f"    완료: {elapsed}초", flush=True)
