"""
등급 전이 행렬 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..core.database import get_db

router = APIRouter(prefix="/api/migration", tags=["Migration"])

GRADE_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "D"]


@router.get("/matrix")
def get_matrix(
    from_ym: int = Query(202301),
    to_ym: int   = Query(202312),
    db: Session  = Depends(get_db)
):
    """N×N 등급 전이 행렬"""
    rows = db.execute(text("""
        SELECT f.grade as from_grade, t.grade as to_grade, COUNT(*) as cnt
        FROM demo_credit_rating f
        JOIN demo_credit_rating t ON f.borrower_id = t.borrower_id AND t.rating_ym = :to_ym
        WHERE f.rating_ym = :from_ym
        GROUP BY f.grade, t.grade
    """), {"from_ym": from_ym, "to_ym": to_ym}).fetchall()

    # 초기화
    matrix: dict = {g: {g2: 0 for g2 in GRADE_ORDER} for g in GRADE_ORDER}
    totals: dict = {g: 0 for g in GRADE_ORDER}

    for r in rows:
        fg, tg, cnt = r[0], r[1], r[2]
        if fg in matrix and tg in matrix[fg]:
            matrix[fg][tg] += cnt
            totals[fg] += cnt

    # 비율 행렬
    pct_matrix: dict = {}
    for fg in GRADE_ORDER:
        pct_matrix[fg] = {}
        tot = totals[fg]
        for tg in GRADE_ORDER:
            cnt = matrix[fg][tg]
            pct_matrix[fg][tg] = round(cnt / tot * 100, 1) if tot > 0 else 0.0

    return {
        "matrix": matrix,
        "pct_matrix": pct_matrix,
        "totals": totals,
        "from_ym": from_ym,
        "to_ym": to_ym,
    }


@router.get("/trend")
def get_trend(grade: str = Query("BB"), db: Session = Depends(get_db)):
    """특정 등급에서 하향된 기업 수 월별 추이"""
    grade_order_map = {g: i for i, g in enumerate(GRADE_ORDER)}
    from_idx = grade_order_map.get(grade, 4)

    rows = db.execute(text("""
        SELECT t.rating_ym, COUNT(*) as downgraded
        FROM demo_credit_rating f
        JOIN demo_credit_rating t ON f.borrower_id = t.borrower_id
        WHERE f.grade = :grade
          AND f.rating_ym < t.rating_ym
        GROUP BY t.rating_ym
        ORDER BY t.rating_ym
    """), {"grade": grade}).fetchall()

    # 실제 하향 여부 필터는 파이썬에서 처리
    all_pairs = db.execute(text("""
        SELECT f.rating_ym, t.rating_ym, f.grade, t.grade
        FROM demo_credit_rating f
        JOIN demo_credit_rating t
          ON f.borrower_id = t.borrower_id
        WHERE f.grade = :grade
        ORDER BY f.rating_ym, t.rating_ym
    """), {"grade": grade}).fetchall()

    trend: dict = {}
    for r in all_pairs:
        fym, tym, fg, tg = r
        if tym <= fym:
            continue
        fi = grade_order_map.get(fg, 0)
        ti = grade_order_map.get(tg, 0)
        if ti > fi:  # 숫자 클수록 하위 등급 (AAA=0, D=7)
            trend[tym] = trend.get(tym, 0) + 1

    return [{"ym": ym, "downgraded": cnt} for ym, cnt in sorted(trend.items())]
