"""
app.py — EWS 기업여신 조기경보 시스템 (Streamlit v2)

은행 기업여신 실무자용 EWS 시스템.
실행: streamlit run app.py
"""

import pickle
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── 경로 ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DEMO_DB    = BASE_DIR / "demo.db"
MODEL_PATH = BASE_DIR.parent / "ml" / "models" / "lgbm_champion.pkl"
RESULTS_DIR = BASE_DIR.parent / "ml" / "results"

# ── 페이지 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EWS — 기업여신 조기경보 시스템",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

GRADE_COLOR  = {"A": "#27ae60", "B": "#f39c12", "C": "#e67e22", "D": "#e74c3c"}
GRADE_LABEL  = {"A": "정상(A)", "B": "주의(B)", "C": "위험(C)", "D": "부실(D)"}
STAGE_COLOR  = {1: "#27ae60", 2: "#f39c12", 3: "#e74c3c"}
CLASS_ORDER  = ["NORMAL", "PRECAUTIONARY", "SUBSTANDARD", "DOUBTFUL", "LOSS"]
CLASS_COLOR  = {
    "NORMAL": "#27ae60",
    "PRECAUTIONARY": "#f39c12",
    "SUBSTANDARD": "#e67e22",
    "DOUBTFUL": "#e74c3c",
    "LOSS": "#7f1d1d",
}
CLASS_KO = {
    "NORMAL": "정상",
    "PRECAUTIONARY": "요주의",
    "SUBSTANDARD": "고정",
    "DOUBTFUL": "회수의문",
    "LOSS": "추정손실",
}

# ── 데이터 로드 ──────────────────────────────────────────────────────────────
@st.cache_resource
def load_db():
    conn = sqlite3.connect(DEMO_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=300)
def load_companies():
    conn = load_db()
    return pd.read_sql("SELECT * FROM demo_company ORDER BY borrower_id", conn)


@st.cache_data(ttl=300)
def get_name_map():
    companies = load_companies()
    return dict(zip(companies["borrower_id"], companies["company_name"]))


@st.cache_data(ttl=300)
def load_signals():
    conn = load_db()
    return pd.read_sql(
        "SELECT * FROM demo_monthly_signal ORDER BY borrower_id, ym", conn
    )


@st.cache_data(ttl=300)
def load_asset_class():
    conn = load_db()
    return pd.read_sql("SELECT * FROM demo_asset_class ORDER BY borrower_id, ym", conn)


@st.cache_data(ttl=300)
def load_ecl():
    conn = load_db()
    return pd.read_sql("SELECT * FROM demo_ecl ORDER BY borrower_id, ym", conn)


@st.cache_data(ttl=300)
def load_credit_rating():
    conn = load_db()
    return pd.read_sql("SELECT * FROM demo_credit_rating ORDER BY borrower_id, rating_ym", conn)


@st.cache_data(ttl=300)
def load_covenant():
    conn = load_db()
    return pd.read_sql("SELECT * FROM demo_covenant ORDER BY borrower_id, check_ym", conn)


@st.cache_data(ttl=300)
def load_facility():
    conn = load_db()
    return pd.read_sql("SELECT * FROM demo_facility", conn)


@st.cache_data(ttl=300)
def load_collateral():
    conn = load_db()
    return pd.read_sql("SELECT * FROM demo_collateral", conn)


@st.cache_data(ttl=300)
def load_workout():
    conn = load_db()
    return pd.read_sql("SELECT * FROM demo_workout", conn)


@st.cache_data(ttl=300)
def load_answer_key():
    conn = load_db()
    return pd.read_sql("SELECT * FROM demo_answer_key", conn)


@st.cache_resource
def load_model():
    if MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    return None


def get_all_yms():
    sigs = load_signals()
    return sorted(sigs["ym"].unique().tolist())


def fmt_억(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    return f"{v:,.1f}억"


def fmt_pct(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    return f"{v:.1f}%"


# ── 사이드바 네비게이션 ───────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏦 EWS 시스템")
    st.caption("기업여신 조기경보")
    st.divider()
    page = st.radio(
        "페이지 선택",
        [
            "📊 종합 대시보드",
            "⚠️ EWS 경보 센터",
            "🔍 기업 상세 분석",
            "📈 포트폴리오 분석",
            "🏦 자산건전성 관리",
            "💰 IFRS9 ECL 관리",
            "📋 코베넌트 모니터링",
            "🔧 NPL/Workout 관리",
            "📊 모델 성능",
            "🎬 부실 탐지 시뮬레이션",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Demo DB: demo.db")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 📊 종합 대시보드
# ═══════════════════════════════════════════════════════════════════════════════
if page == "📊 종합 대시보드":
    st.title("📊 종합 대시보드")

    all_yms   = get_all_yms()
    companies = load_companies()
    signals   = load_signals()
    asset_cls = load_asset_class()
    ecl_df    = load_ecl()
    name_map  = get_name_map()

    # 상단 필터
    col_f1, col_f2 = st.columns([3, 1])
    with col_f1:
        base_ym = st.select_slider("기준월", options=all_yms, value=all_yms[-1])
    with col_f2:
        industry_filter = st.selectbox(
            "업종 필터",
            ["전체"] + sorted(companies["industry_cd"].unique().tolist()),
        )

    st.caption(f"기준월: {base_ym}")

    # 필터링
    sig_ym = signals[signals["ym"] == base_ym].copy()
    if industry_filter != "전체":
        bids_filtered = companies[companies["industry_cd"] == industry_filter]["borrower_id"].tolist()
        sig_ym = sig_ym[sig_ym["borrower_id"].isin(bids_filtered)]

    total_firms   = len(sig_ym)
    alert_firms   = len(sig_ym[sig_ym["ews_grade"].isin(["C", "D"])])
    total_loan    = ecl_df[ecl_df["ym"] == base_ym]["ead_억"].sum()
    avg_ews       = sig_ym["ews_score"].mean()
    overdue_firms = len(sig_ym[sig_ym["principal_past_due_days"] > 0])

    # KPI 카드
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("전체 기업", f"{total_firms:,}개")
    k2.metric("EWS 경보 (C+D)", f"{alert_firms:,}개",
              delta=None if total_firms == 0 else f"{alert_firms/total_firms*100:.1f}%")
    k3.metric("총 여신 (억)", f"{total_loan:,.0f}")
    k4.metric("평균 EWS 점수", f"{avg_ews:.1f}")
    k5.metric("연체 기업 수", f"{overdue_firms:,}개")

    st.divider()

    # 2열: EWS 등급 도넛 + 월별 경보 추이
    col_l, col_r = st.columns(2)
    with col_l:
        grade_cnt = sig_ym["ews_grade"].value_counts().reset_index()
        grade_cnt.columns = ["grade", "count"]
        grade_cnt["label"] = grade_cnt["grade"].map(GRADE_LABEL)
        grade_cnt["color"] = grade_cnt["grade"].map(GRADE_COLOR)
        fig_donut = go.Figure(go.Pie(
            labels=grade_cnt["label"],
            values=grade_cnt["count"],
            hole=0.5,
            marker_colors=grade_cnt["color"].tolist(),
            textinfo="label+percent",
        ))
        fig_donut.update_layout(title="EWS 등급 분포", height=320, margin=dict(t=40, b=0))
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_r:
        recent_12 = all_yms[-12:]
        trend_sig = signals[signals["ym"].isin(recent_12)]
        if industry_filter != "전체":
            trend_sig = trend_sig[trend_sig["borrower_id"].isin(bids_filtered)]
        trend = trend_sig.groupby(["ym", "ews_grade"]).size().reset_index(name="count")
        fig_bar = px.bar(
            trend, x="ym", y="count", color="ews_grade",
            color_discrete_map=GRADE_COLOR,
            title="월별 EWS 경보 추이 (최근 12개월)",
            labels={"ym": "기준월", "count": "기업 수", "ews_grade": "등급"},
            barmode="stack",
        )
        fig_bar.update_layout(height=320, margin=dict(t=40, b=0))
        st.plotly_chart(fig_bar, use_container_width=True)

    # 2열: 자산건전성 파이 + IFRS9 Stage 막대
    col_l2, col_r2 = st.columns(2)
    with col_l2:
        ac_ym = asset_cls[asset_cls["ym"] == base_ym].copy()
        if industry_filter != "전체":
            ac_ym = ac_ym[ac_ym["borrower_id"].isin(bids_filtered)]
        ac_cnt = ac_ym["classification"].value_counts().reset_index()
        ac_cnt.columns = ["cls", "count"]
        ac_cnt["ko"] = ac_cnt["cls"].map(CLASS_KO)
        ac_cnt["color"] = ac_cnt["cls"].map(CLASS_COLOR)
        fig_pie = go.Figure(go.Pie(
            labels=ac_cnt["ko"],
            values=ac_cnt["count"],
            marker_colors=ac_cnt["color"].tolist(),
            textinfo="label+percent",
        ))
        fig_pie.update_layout(title="자산건전성 분류", height=320, margin=dict(t=40, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_r2:
        ecl_ym = ecl_df[ecl_df["ym"] == base_ym].copy()
        if industry_filter != "전체":
            ecl_ym = ecl_ym[ecl_ym["borrower_id"].isin(bids_filtered)]
        stage_cnt = ecl_ym["stage"].value_counts().reset_index()
        stage_cnt.columns = ["stage", "count"]
        stage_cnt["label"] = stage_cnt["stage"].apply(lambda x: f"Stage {x}")
        stage_cnt["color"] = stage_cnt["stage"].map(STAGE_COLOR)
        fig_stage = px.bar(
            stage_cnt, x="label", y="count",
            color="label",
            color_discrete_map={f"Stage {k}": v for k, v in STAGE_COLOR.items()},
            title="IFRS9 Stage 분포",
            labels={"label": "Stage", "count": "기업 수"},
        )
        fig_stage.update_layout(height=320, margin=dict(t=40, b=0), showlegend=False)
        st.plotly_chart(fig_stage, use_container_width=True)

    st.divider()

    # 경보 기업 TOP 10
    st.subheader("경보 기업 TOP 10")
    alert_top = sig_ym[sig_ym["ews_grade"].isin(["C", "D"])].copy()
    alert_top["company_name"] = alert_top["borrower_id"].map(name_map)
    alert_top = alert_top.merge(
        companies[["borrower_id", "firm_size_cd"]], on="borrower_id", how="left"
    )
    alert_top = alert_top.sort_values("ews_score").head(10)
    display_cols = {
        "company_name": "회사명",
        "firm_size_cd": "규모",
        "ews_grade": "EWS등급",
        "ews_score": "EWS점수",
        "principal_past_due_days": "DPD(일)",
        "interest_coverage_ratio": "ICR",
    }
    st.dataframe(
        alert_top[list(display_cols.keys())].rename(columns=display_cols),
        use_container_width=True, hide_index=True
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ⚠️ EWS 경보 센터
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "⚠️ EWS 경보 센터":
    st.title("⚠️ EWS 경보 센터")

    all_yms   = get_all_yms()
    companies = load_companies()
    signals   = load_signals()
    name_map  = get_name_map()

    # 필터
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        base_ym = st.selectbox("기준월", all_yms, index=len(all_yms)-1)
    with col_f2:
        grade_filter = st.multiselect("등급 필터", ["B", "C", "D"], default=["C", "D"])
    with col_f3:
        size_filter = st.multiselect(
            "기업규모",
            ["대기업", "중견기업", "중소기업", "소기업"],
            default=["대기업", "중견기업", "중소기업", "소기업"],
        )

    st.caption(f"기준월: {base_ym}")

    sig_ym = signals[signals["ym"] == base_ym].copy()
    sig_ym = sig_ym.merge(companies[["borrower_id", "firm_size_cd", "industry_cd"]], on="borrower_id", how="left")
    sig_ym["company_name"] = sig_ym["borrower_id"].map(name_map)

    # 필터 적용
    if grade_filter:
        alert_df = sig_ym[sig_ym["ews_grade"].isin(grade_filter)].copy()
    else:
        alert_df = sig_ym.copy()
    if size_filter:
        alert_df = alert_df[alert_df["firm_size_cd"].isin(size_filter)]

    tabs = st.tabs(["통합 경보", "재무 신호", "행동 신호", "공적 신호", "시장/업종 신호", "종합 스코어카드"])

    # 탭1: 통합 경보
    with tabs[0]:
        st.markdown(f"**경보 기업: {len(alert_df)}개**")
        disp = alert_df[["company_name", "firm_size_cd", "ews_grade", "ews_score",
                          "interest_coverage_ratio", "principal_past_due_days",
                          "seizure_flag", "lawsuit_count_12m"]].rename(columns={
            "company_name": "회사명", "firm_size_cd": "규모",
            "ews_grade": "등급", "ews_score": "EWS점수",
            "interest_coverage_ratio": "ICR", "principal_past_due_days": "DPD",
            "seizure_flag": "가압류", "lawsuit_count_12m": "소송건수",
        })
        st.dataframe(disp.sort_values("EWS점수"), use_container_width=True, hide_index=True)

    # 탭2: 재무 신호
    with tabs[1]:
        st.info("ICR < 1.0, 부채비율 > 300%, DSCR < 1.0 위반 기업 현황")
        fin_df = sig_ym.copy()
        fin_df["ICR위반"]  = fin_df["interest_coverage_ratio"] < 1.0
        fin_df["부채비율위반"] = fin_df["debt_to_equity_ratio"] > 300
        fin_df["DSCR위반"] = fin_df["dscr_ratio"] < 1.0
        fin_breached = fin_df[fin_df["ICR위반"] | fin_df["부채비율위반"] | fin_df["DSCR위반"]]

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("재무지표 위반 기업", f"{len(fin_breached)}개")
            disp2 = fin_breached[["company_name", "interest_coverage_ratio",
                                   "debt_to_equity_ratio", "dscr_ratio",
                                   "ICR위반", "부채비율위반", "DSCR위반"]].rename(columns={
                "company_name": "회사명", "interest_coverage_ratio": "ICR",
                "debt_to_equity_ratio": "부채비율", "dscr_ratio": "DSCR",
            })
            st.dataframe(disp2, use_container_width=True, hide_index=True)
        with col_b:
            fig_icr = px.histogram(sig_ym, x="interest_coverage_ratio",
                                   nbins=30, title="ICR 분포",
                                   labels={"interest_coverage_ratio": "ICR"})
            fig_icr.add_vline(x=1.0, line_dash="dash", line_color="red", annotation_text="기준(1.0)")
            st.plotly_chart(fig_icr, use_container_width=True)

    # 탭3: 행동 신호
    with tabs[2]:
        st.info("한도소진율 > 80%, DPD > 30, 입출금비율 이상 기업")
        beh_df = sig_ym.copy()
        beh_df["한도소진율위반"] = beh_df["limit_utilization_ratio"] > 0.8
        beh_df["DPD위반"]     = beh_df["principal_past_due_days"] > 30
        beh_df["입출금이상"]   = beh_df["inflow_outflow_ratio"] < 0.7
        beh_breached = beh_df[beh_df["한도소진율위반"] | beh_df["DPD위반"] | beh_df["입출금이상"]]

        st.metric("행동지표 위반 기업", f"{len(beh_breached)}개")
        disp3 = beh_breached[["company_name", "limit_utilization_ratio",
                               "principal_past_due_days", "inflow_outflow_ratio",
                               "한도소진율위반", "DPD위반", "입출금이상"]].rename(columns={
            "company_name": "회사명",
            "limit_utilization_ratio": "한도소진율",
            "principal_past_due_days": "DPD(일)",
            "inflow_outflow_ratio": "입출금비율",
        })
        st.dataframe(disp3, use_container_width=True, hide_index=True)

    # 탭4: 공적 신호
    with tabs[3]:
        st.info("가압류, 소송, 파산신청 발생 기업 목록")
        pub_df = sig_ym[(sig_ym["seizure_flag"] == 1) |
                        (sig_ym["lawsuit_count_12m"] > 0) |
                        (sig_ym["bankruptcy_filing_flag"] == 1)].copy()
        st.metric("공적 신호 발생 기업", f"{len(pub_df)}개")
        disp4 = pub_df[["company_name", "seizure_flag", "lawsuit_count_12m",
                         "bankruptcy_filing_flag", "ews_grade"]].rename(columns={
            "company_name": "회사명", "seizure_flag": "가압류",
            "lawsuit_count_12m": "소송건수", "bankruptcy_filing_flag": "파산신청",
            "ews_grade": "EWS등급",
        })
        st.dataframe(disp4, use_container_width=True, hide_index=True)

    # 탭5: 시장/업종 신호
    with tabs[4]:
        st.info("업종스트레스지수 및 뉴스감성점수 분포")
        col_a, col_b = st.columns(2)
        with col_a:
            ind_agg = sig_ym.groupby("industry_cd").agg(
                avg_stress=("industry_stress_score", "mean"),
                firm_count=("borrower_id", "count"),
            ).reset_index().sort_values("avg_stress", ascending=False)
            fig_ind = px.bar(ind_agg, x="industry_cd", y="avg_stress",
                             color="avg_stress", color_continuous_scale="RdYlGn_r",
                             title="업종별 평균 스트레스 지수",
                             labels={"industry_cd": "업종", "avg_stress": "스트레스 지수"})
            st.plotly_chart(fig_ind, use_container_width=True)
        with col_b:
            fig_news = px.histogram(sig_ym, x="news_sentiment_score", nbins=20,
                                    title="뉴스 감성 점수 분포",
                                    labels={"news_sentiment_score": "감성 점수"})
            st.plotly_chart(fig_news, use_container_width=True)

        # 위험 업종 (스트레스 상위 3)
        top3_ind = ind_agg.head(3)["industry_cd"].tolist()
        st.markdown(f"**위험 업종 TOP3**: {', '.join(top3_ind)}")
        risk_ind_df = sig_ym[sig_ym["industry_cd"].isin(top3_ind)][
            ["company_name", "industry_cd", "ews_grade", "ews_score", "industry_stress_score"]
        ].rename(columns={"company_name": "회사명", "industry_cd": "업종",
                           "ews_grade": "EWS등급", "ews_score": "EWS점수",
                           "industry_stress_score": "스트레스지수"})
        st.dataframe(risk_ind_df.sort_values("스트레스지수", ascending=False),
                     use_container_width=True, hide_index=True)

    # 탭6: 종합 스코어카드
    with tabs[5]:
        st.info("기업별 신호 카운트 히트맵")
        sc_df = sig_ym.copy()
        sc_df["재무신호"] = ((sc_df["interest_coverage_ratio"] < 1.0).astype(int) +
                             (sc_df["debt_to_equity_ratio"] > 300).astype(int) +
                             (sc_df["dscr_ratio"] < 1.0).astype(int))
        sc_df["행동신호"] = ((sc_df["limit_utilization_ratio"] > 0.8).astype(int) +
                             (sc_df["principal_past_due_days"] > 30).astype(int) +
                             (sc_df["inflow_outflow_ratio"] < 0.7).astype(int))
        sc_df["공적신호"] = (sc_df["seizure_flag"] + sc_df["bankruptcy_filing_flag"] +
                             (sc_df["lawsuit_count_12m"] > 0).astype(int))
        sc_df["시장신호"] = (sc_df["industry_stress_score"] > 35).astype(int)
        sc_df["총신호"]   = sc_df["재무신호"] + sc_df["행동신호"] + sc_df["공적신호"] + sc_df["시장신호"]

        top_alert = sc_df.sort_values("총신호", ascending=False).head(20)
        heat_df = top_alert[["company_name", "재무신호", "행동신호", "공적신호", "시장신호"]].set_index("company_name")
        fig_hm = px.imshow(heat_df, color_continuous_scale="RdYlGn_r",
                           title="기업별 신호 히트맵 (상위 20개)", aspect="auto")
        fig_hm.update_layout(height=500)
        st.plotly_chart(fig_hm, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 🔍 기업 상세 분석
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 기업 상세 분석":
    st.title("🔍 기업 상세 분석")

    companies = load_companies()
    signals   = load_signals()
    ecl_df    = load_ecl()
    cr_df     = load_credit_rating()
    cov_df    = load_covenant()
    fac_df    = load_facility()
    wo_df     = load_workout()

    # 기업 선택
    name_map  = get_name_map()
    cname_to_bid = {v: k for k, v in name_map.items()}
    sorted_names = sorted(name_map.values())

    sel_name = st.selectbox("기업 선택", sorted_names)
    bid = cname_to_bid[sel_name]
    comp = companies[companies["borrower_id"] == bid].iloc[0]

    # 기업 정보 카드
    badge_color = {"NORMAL": "green", "DEFAULT": "red", "RECOVERY": "orange"}.get(comp["scenario"], "gray")
    st.markdown(f"""
    <div style="background:#f0f2f6;padding:1rem;border-radius:8px;margin-bottom:1rem">
    <b>{comp['company_name']}</b> &nbsp;|&nbsp;
    규모: {comp['firm_size_cd']} &nbsp;|&nbsp;
    업종: {comp['industry_cd']} &nbsp;|&nbsp;
    상장: {'Y' if comp['listed_flag'] else 'N'} &nbsp;|&nbsp;
    <span style="background:{'#27ae60' if badge_color=='green' else '#e74c3c' if badge_color=='red' else '#f39c12'};
    color:white;padding:2px 8px;border-radius:4px;font-size:0.85em">
    {comp['scenario']}
    </span>
    </div>
    """, unsafe_allow_html=True)

    sig_c = signals[signals["borrower_id"] == bid].sort_values("ym")
    all_yms = get_all_yms()
    base_ym = all_yms[-1]
    st.caption(f"기준월: {base_ym} | 관측 기간: {sig_c['ym'].min()} ~ {sig_c['ym'].max()}")

    tabs = st.tabs(["EWS 현황", "재무 지표", "신용등급/ECL", "코베넌트/여신", "연체/Workout"])

    # 탭1: EWS 현황
    with tabs[0]:
        col_a, col_b = st.columns(2)
        with col_a:
            fig_ews = px.line(sig_c, x="ym", y="ews_score", title="EWS 스코어 추이",
                              markers=True, labels={"ym": "월", "ews_score": "EWS 점수"})
            fig_ews.add_hline(y=70, line_dash="dash", line_color="#27ae60", annotation_text="A기준(70)")
            fig_ews.add_hline(y=50, line_dash="dash", line_color="#f39c12", annotation_text="B기준(50)")
            fig_ews.add_hline(y=30, line_dash="dash", line_color="#e67e22", annotation_text="C기준(30)")
            fig_ews.update_layout(height=300)
            st.plotly_chart(fig_ews, use_container_width=True)
        with col_b:
            # PD 추이
            ecl_c = ecl_df[ecl_df["borrower_id"] == bid].sort_values("ym")
            fig_pd = px.line(ecl_c, x="ym", y="pd_value", title="PD 추이",
                             markers=True, labels={"ym": "월", "pd_value": "PD"})
            fig_pd.update_layout(height=300)
            st.plotly_chart(fig_pd, use_container_width=True)

        # 등급 타임라인
        grade_timeline = sig_c[["ym", "ews_grade"]].copy()
        grade_timeline["color"] = grade_timeline["ews_grade"].map(GRADE_COLOR)
        fig_gt = go.Figure()
        for _, row in grade_timeline.iterrows():
            fig_gt.add_trace(go.Scatter(
                x=[row["ym"]], y=[1],
                mode="markers",
                marker=dict(color=row["color"], size=16, symbol="square"),
                name=row["ews_grade"],
                showlegend=False,
                hovertext=f"{row['ym']}: {row['ews_grade']}",
            ))
        fig_gt.update_layout(title="EWS 등급 타임라인", height=120,
                              yaxis=dict(visible=False), xaxis_title="월")
        st.plotly_chart(fig_gt, use_container_width=True)

    # 탭2: 재무 지표
    with tabs[1]:
        col_a, col_b = st.columns(2)
        with col_a:
            fig_icr = px.line(sig_c, x="ym", y="interest_coverage_ratio",
                              title="ICR 추이", markers=True)
            fig_icr.add_hline(y=1.0, line_dash="dash", line_color="red")
            fig_icr.update_layout(height=260)
            st.plotly_chart(fig_icr, use_container_width=True)

            fig_lev = px.line(sig_c, x="ym", y="debt_to_equity_ratio",
                              title="부채비율 추이", markers=True)
            fig_lev.add_hline(y=300, line_dash="dash", line_color="red")
            fig_lev.update_layout(height=260)
            st.plotly_chart(fig_lev, use_container_width=True)
        with col_b:
            fig_dscr = px.line(sig_c, x="ym", y="dscr_ratio",
                               title="DSCR 추이", markers=True)
            fig_dscr.add_hline(y=1.0, line_dash="dash", line_color="red")
            fig_dscr.update_layout(height=260)
            st.plotly_chart(fig_dscr, use_container_width=True)

            fig_cr = px.line(sig_c, x="ym", y="current_ratio",
                             title="유동비율 추이", markers=True)
            fig_cr.add_hline(y=80, line_dash="dash", line_color="red")
            fig_cr.update_layout(height=260)
            st.plotly_chart(fig_cr, use_container_width=True)

    # 탭3: 신용등급/ECL
    with tabs[2]:
        cr_c  = cr_df[cr_df["borrower_id"] == bid].sort_values("rating_ym")
        ecl_c = ecl_df[ecl_df["borrower_id"] == bid].sort_values("ym")

        col_a, col_b = st.columns(2)
        with col_a:
            RATING_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]
            cr_c["rating_num"] = cr_c["grade"].apply(
                lambda g: RATING_ORDER.index(g) if g in RATING_ORDER else 9
            )
            fig_cr2 = px.bar(cr_c, x="rating_ym", y="rating_num", color="grade",
                             title="내부신용등급 이력",
                             labels={"rating_ym": "분기", "rating_num": "등급(낮을수록 우량)"},
                             text="grade")
            fig_cr2.update_layout(height=300, yaxis=dict(
                tickvals=list(range(len(RATING_ORDER))),
                ticktext=RATING_ORDER,
            ))
            st.plotly_chart(fig_cr2, use_container_width=True)
        with col_b:
            fig_stage2 = px.bar(ecl_c, x="ym", y="stage", color="stage",
                                color_discrete_map={1: "#27ae60", 2: "#f39c12", 3: "#e74c3c"},
                                title="IFRS9 Stage 이력",
                                labels={"ym": "월", "stage": "Stage"})
            fig_stage2.update_layout(height=300)
            st.plotly_chart(fig_stage2, use_container_width=True)

        st.subheader("ECL 추이")
        fig_ecl = px.line(ecl_c, x="ym", y="ecl_amount_억", title="ECL 충당금 (억)",
                          markers=True)
        st.plotly_chart(fig_ecl, use_container_width=True)

    # 탭4: 코베넌트/여신
    with tabs[3]:
        cov_c = cov_df[cov_df["borrower_id"] == bid].copy()
        fac_c = fac_df[fac_df["borrower_id"] == bid].copy()

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("코베넌트 체크 현황")
            cov_disp = cov_c[["check_ym", "covenant_type", "result",
                               "actual_value", "threshold_value"]].rename(columns={
                "check_ym": "분기", "covenant_type": "유형", "result": "결과",
                "actual_value": "실제값", "threshold_value": "기준값",
            })
            st.dataframe(cov_disp.sort_values("분기", ascending=False),
                         use_container_width=True, hide_index=True)
        with col_b:
            st.subheader("여신 현황")
            fac_disp = fac_c[["facility_type", "committed_amount_억",
                               "outstanding_amount_억", "interest_rate",
                               "maturity_ym", "collateral_type"]].rename(columns={
                "facility_type": "여신유형",
                "committed_amount_억": "한도(억)",
                "outstanding_amount_억": "잔액(억)",
                "interest_rate": "금리(%)",
                "maturity_ym": "만기",
                "collateral_type": "담보유형",
            })
            st.dataframe(fac_disp, use_container_width=True, hide_index=True)

    # 탭5: 연체/Workout
    with tabs[4]:
        fig_dpd = px.bar(sig_c, x="ym", y="principal_past_due_days",
                         title="DPD 추이 (일)", labels={"ym": "월", "principal_past_due_days": "DPD(일)"})
        st.plotly_chart(fig_dpd, use_container_width=True)

        wo_c = wo_df[wo_df["borrower_id"] == bid]
        if len(wo_c) > 0:
            st.subheader("Workout 현황")
            wo_disp = wo_c[["workout_type", "workout_start_ym", "original_balance_억",
                             "recovery_rate", "outcome"]].rename(columns={
                "workout_type": "유형", "workout_start_ym": "시작월",
                "original_balance_억": "원잔액(억)", "recovery_rate": "회수율", "outcome": "결과",
            })
            st.dataframe(wo_disp, use_container_width=True, hide_index=True)
        else:
            st.info("Workout 데이터 없음 (정상 또는 회복 기업)")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 📈 포트폴리오 분석
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📈 포트폴리오 분석":
    st.title("📈 포트폴리오 분석")

    all_yms   = get_all_yms()
    companies = load_companies()
    signals   = load_signals()

    base_ym = st.select_slider("기준월", options=all_yms, value=all_yms[-1])
    st.caption(f"기준월: {base_ym}")

    sig_ym = signals[signals["ym"] == base_ym].merge(
        companies[["borrower_id", "firm_size_cd", "industry_cd"]], on="borrower_id", how="left"
    )

    col_l, col_r = st.columns(2)
    with col_l:
        ind_grade = sig_ym.groupby(["industry_cd", "ews_grade"]).size().reset_index(name="count")
        fig_ind = px.bar(ind_grade, x="industry_cd", y="count", color="ews_grade",
                         color_discrete_map=GRADE_COLOR,
                         title="업종별 EWS 등급 분포",
                         labels={"industry_cd": "업종", "count": "기업 수", "ews_grade": "등급"},
                         barmode="stack")
        st.plotly_chart(fig_ind, use_container_width=True)

    with col_r:
        sz_grade = sig_ym.groupby(["firm_size_cd", "ews_grade"]).size().reset_index(name="count")
        fig_sz = px.bar(sz_grade, x="firm_size_cd", y="count", color="ews_grade",
                        color_discrete_map=GRADE_COLOR,
                        title="기업규모별 EWS 등급 분포",
                        labels={"firm_size_cd": "규모", "count": "기업 수", "ews_grade": "등급"},
                        barmode="stack")
        st.plotly_chart(fig_sz, use_container_width=True)

    # EWS등급 × 업종 히트맵
    pivot = sig_ym.pivot_table(values="ews_score", index="ews_grade", columns="industry_cd",
                                aggfunc="count", fill_value=0)
    fig_hm = px.imshow(pivot, color_continuous_scale="RdYlGn_r",
                       title="EWS등급 × 업종 히트맵 (기업 수)",
                       labels=dict(color="기업 수"))
    fig_hm.update_layout(height=300)
    st.plotly_chart(fig_hm, use_container_width=True)

    # 집중도
    st.subheader("업종 집중도")
    ind_cnt  = sig_ym.groupby("industry_cd").size().reset_index(name="count")
    total    = ind_cnt["count"].sum()
    ind_cnt["share"] = ind_cnt["count"] / total
    top5     = ind_cnt.sort_values("count", ascending=False).head(5)
    hhi      = (ind_cnt["share"] ** 2).sum()

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Top 5 업종 집중도**")
        st.dataframe(
            top5.rename(columns={"industry_cd": "업종", "count": "기업 수", "share": "비중"}),
            use_container_width=True, hide_index=True
        )
    with col_b:
        st.metric("HHI 지수", f"{hhi:.4f}", help="0~1, 높을수록 집중")

    # 월별 평균 EWS 추이
    st.subheader("월별 포트폴리오 평균 EWS 추이")
    monthly_avg = signals.groupby("ym")["ews_score"].mean().reset_index()
    fig_avg = px.line(monthly_avg, x="ym", y="ews_score",
                      markers=True, labels={"ym": "월", "ews_score": "평균 EWS"})
    fig_avg.update_layout(height=300)
    st.plotly_chart(fig_avg, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 🏦 자산건전성 관리
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🏦 자산건전성 관리":
    st.title("🏦 자산건전성 관리")

    all_yms   = get_all_yms()
    asset_cls = load_asset_class()
    name_map  = get_name_map()

    base_ym = st.select_slider("기준월", options=all_yms, value=all_yms[-1])
    st.caption(f"기준월: {base_ym}")

    ac_ym = asset_cls[asset_cls["ym"] == base_ym]
    total = len(ac_ym)

    def pct_class(cls):
        return len(ac_ym[ac_ym["classification"] == cls]) / total * 100 if total > 0 else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("정상(%)", f"{pct_class('NORMAL'):.1f}%")
    k2.metric("요주의(%)", f"{pct_class('PRECAUTIONARY'):.1f}%")
    k3.metric("고정이하(%)", f"{pct_class('SUBSTANDARD')+pct_class('DOUBTFUL')+pct_class('LOSS'):.1f}%")

    # 월별 스택드바
    ac_monthly = asset_cls.groupby(["ym", "classification"]).size().reset_index(name="count")
    ac_monthly["분류"] = ac_monthly["classification"].map(CLASS_KO)
    fig_ac = px.bar(ac_monthly, x="ym", y="count", color="classification",
                    color_discrete_map=CLASS_COLOR,
                    title="자산건전성 월별 분포",
                    labels={"ym": "월", "count": "기업 수", "classification": "분류"},
                    barmode="stack")
    fig_ac.update_layout(height=350)
    st.plotly_chart(fig_ac, use_container_width=True)

    # 이동 테이블
    st.subheader("자산건전성 변화 (전월 대비)")
    prev_ym  = all_yms[all_yms.index(base_ym) - 1] if all_yms.index(base_ym) > 0 else base_ym
    ac_cur   = asset_cls[asset_cls["ym"] == base_ym][["borrower_id", "classification"]].rename(
        columns={"classification": "current"})
    ac_prev  = asset_cls[asset_cls["ym"] == prev_ym][["borrower_id", "classification"]].rename(
        columns={"classification": "previous"})
    ac_merge = ac_cur.merge(ac_prev, on="borrower_id", how="left")
    ac_merge["변화"] = ac_merge.apply(
        lambda r: "악화" if (CLASS_ORDER.index(r["current"]) > CLASS_ORDER.index(r["previous"]))
        else ("개선" if CLASS_ORDER.index(r["current"]) < CLASS_ORDER.index(r["previous"]) else "유지")
        if pd.notna(r["previous"]) else "신규",
        axis=1,
    )
    change_cnt = ac_merge["변화"].value_counts().reset_index()
    change_cnt.columns = ["변화", "건수"]
    st.dataframe(change_cnt, use_container_width=True, hide_index=True)

    # 요주의 이하 기업 목록
    st.subheader("요주의 이하 기업 목록")
    below_normal = ac_ym[ac_ym["classification"] != "NORMAL"].copy()
    below_normal["company_name"] = below_normal["borrower_id"].map(name_map)
    below_normal["분류"] = below_normal["classification"].map(CLASS_KO)
    disp = below_normal[["company_name", "분류", "ews_score"]].rename(columns={
        "company_name": "회사명", "ews_score": "EWS점수"
    })
    disp = disp.merge(
        ac_merge[["borrower_id", "변화"]],
        left_on=below_normal["borrower_id"].values,
        right_on=ac_merge["borrower_id"].values,
        how="left",
    ).drop(columns=["key_0", "borrower_id"], errors="ignore")
    st.dataframe(disp.sort_values("EWS점수"), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 💰 IFRS9 ECL 관리
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "💰 IFRS9 ECL 관리":
    st.title("💰 IFRS9 ECL 관리")

    all_yms = get_all_yms()
    ecl_df  = load_ecl()
    name_map = get_name_map()

    base_ym = st.select_slider("기준월", options=all_yms, value=all_yms[-1])
    st.caption(f"기준월: {base_ym}")

    ecl_ym = ecl_df[ecl_df["ym"] == base_ym]
    total  = len(ecl_ym)

    def stage_pct(s):
        return len(ecl_ym[ecl_ym["stage"] == s]) / total * 100 if total > 0 else 0

    total_ecl = ecl_ym["ecl_amount_억"].sum()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Stage1 기업(%)", f"{stage_pct(1):.1f}%")
    k2.metric("Stage2 기업(%)", f"{stage_pct(2):.1f}%")
    k3.metric("Stage3 기업(%)", f"{stage_pct(3):.1f}%")
    k4.metric("총 ECL 충당금(억)", f"{total_ecl:,.1f}")

    # Stage 월별 추이
    stage_monthly = ecl_df.groupby(["ym", "stage"]).size().reset_index(name="count")
    fig_sm = px.bar(stage_monthly, x="ym", y="count", color="stage",
                    color_discrete_map={1: "#27ae60", 2: "#f39c12", 3: "#e74c3c"},
                    title="IFRS9 Stage 월별 분포",
                    labels={"ym": "월", "count": "기업 수", "stage": "Stage"},
                    barmode="stack")
    fig_sm.update_layout(height=350)
    st.plotly_chart(fig_sm, use_container_width=True)

    # Stage 전이
    st.subheader("Stage 전이 현황")
    if all_yms.index(base_ym) > 0:
        prev_ym   = all_yms[all_yms.index(base_ym) - 1]
        ecl_cur   = ecl_df[ecl_df["ym"] == base_ym][["borrower_id", "stage"]].rename(
            columns={"stage": "cur_stage"})
        ecl_prev  = ecl_df[ecl_df["ym"] == prev_ym][["borrower_id", "stage"]].rename(
            columns={"stage": "prev_stage"})
        ecl_trans = ecl_cur.merge(ecl_prev, on="borrower_id", how="inner")
        ecl_trans = ecl_trans[ecl_trans["cur_stage"] != ecl_trans["prev_stage"]]

        trans_summary = ecl_trans.groupby(["prev_stage", "cur_stage"]).size().reset_index(name="건수")
        trans_summary["전이"] = trans_summary.apply(
            lambda r: f"Stage{r['prev_stage']}→Stage{r['cur_stage']}", axis=1
        )
        st.dataframe(trans_summary[["전이", "건수"]], use_container_width=True, hide_index=True)

    # Stage2/3 상세 목록
    st.subheader("Stage 2/3 기업 목록")
    late_stage = ecl_ym[ecl_ym["stage"] >= 2].copy()
    late_stage["company_name"] = late_stage["borrower_id"].map(name_map)
    disp = late_stage[["company_name", "stage", "ecl_amount_억", "pd_value", "lgd", "ead_억"]].rename(columns={
        "company_name": "회사명", "ecl_amount_억": "ECL(억)",
        "pd_value": "PD", "ead_억": "EAD(억)",
    })
    st.dataframe(disp.sort_values(["stage", "ECL(억)"], ascending=[False, False]),
                 use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. 📋 코베넌트 모니터링
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📋 코베넌트 모니터링":
    st.title("📋 코베넌트 모니터링")

    cov_df   = load_covenant()
    signals  = load_signals()
    name_map = get_name_map()

    all_qyms = sorted(cov_df["check_ym"].unique().tolist())
    base_qym = st.selectbox("기준 분기", all_qyms, index=len(all_qyms)-1)
    st.caption(f"기준 분기: {base_qym}")

    cov_ym = cov_df[cov_df["check_ym"] == base_qym]

    total_checks  = len(cov_ym)
    breach_count  = len(cov_ym[cov_ym["result"] == "BREACH"])
    waived_count  = len(cov_ym[cov_ym["result"] == "WAIVED"])
    breach_rate   = breach_count / total_checks * 100 if total_checks > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 체크건수", f"{total_checks:,}")
    k2.metric("위반건수",   f"{breach_count:,}")
    k3.metric("위반율(%)",  f"{breach_rate:.1f}%")
    k4.metric("면제건수",   f"{waived_count:,}")

    # 유형별 위반
    type_breach = cov_ym[cov_ym["result"] == "BREACH"].groupby("covenant_type").size().reset_index(name="위반건수")
    fig_tb = px.bar(type_breach, x="covenant_type", y="위반건수",
                    title="코베넌트 유형별 위반 현황",
                    labels={"covenant_type": "코베넌트 유형"},
                    color="위반건수", color_continuous_scale="Reds")
    st.plotly_chart(fig_tb, use_container_width=True)

    # 위반 기업 목록
    st.subheader("위반 기업 목록")
    breach_df = cov_ym[cov_ym["result"] == "BREACH"].copy()
    breach_df["company_name"] = breach_df["borrower_id"].map(name_map)
    disp = breach_df[["company_name", "covenant_type", "actual_value", "threshold_value"]].rename(columns={
        "company_name": "회사명", "covenant_type": "위반유형",
        "actual_value": "실제값", "threshold_value": "기준값",
    })
    st.dataframe(disp, use_container_width=True, hide_index=True)

    # 월별 위반 추이
    st.subheader("분기별 위반 추이")
    breach_monthly = cov_df[cov_df["result"] == "BREACH"].groupby(["check_ym", "covenant_type"]).size().reset_index(name="count")
    fig_bm = px.line(breach_monthly, x="check_ym", y="count", color="covenant_type",
                     title="코베넌트 유형별 위반 추이",
                     labels={"check_ym": "분기", "count": "위반 건수", "covenant_type": "유형"},
                     markers=True)
    st.plotly_chart(fig_bm, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. 🔧 NPL/Workout 관리
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🔧 NPL/Workout 관리":
    st.title("🔧 NPL/Workout 관리")

    wo_df     = load_workout()
    companies = load_companies()
    name_map  = get_name_map()

    wo_df["company_name"] = wo_df["borrower_id"].map(name_map)

    total_npl  = len(wo_df)
    ongoing    = len(wo_df[wo_df["outcome"] == "ONGOING"])
    avg_rec    = wo_df["recovery_rate"].mean() * 100 if len(wo_df) > 0 else 0
    total_loss = wo_df[wo_df["outcome"] == "FAILED"]["original_balance_억"].sum() * (
        1 - wo_df[wo_df["outcome"] == "FAILED"]["recovery_rate"].mean()
        if len(wo_df[wo_df["outcome"] == "FAILED"]) > 0 else 0
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("부실기업수",   f"{total_npl:,}개")
    k2.metric("Workout 진행중", f"{ongoing:,}개")
    k3.metric("평균 회수율(%)", f"{avg_rec:.1f}%")
    k4.metric("총 손실 추정(억)", f"{total_loss:,.1f}")

    col_l, col_r = st.columns(2)
    with col_l:
        type_cnt = wo_df["workout_type"].value_counts().reset_index()
        type_cnt.columns = ["유형", "건수"]
        fig_wt = px.pie(type_cnt, names="유형", values="건수",
                        title="Workout 유형별 현황")
        st.plotly_chart(fig_wt, use_container_width=True)
    with col_r:
        out_cnt = wo_df["outcome"].value_counts().reset_index()
        out_cnt.columns = ["결과", "건수"]
        out_color = {"COMPLETED": "#27ae60", "ONGOING": "#f39c12", "FAILED": "#e74c3c"}
        fig_out = px.bar(out_cnt, x="결과", y="건수",
                         color="결과", color_discrete_map=out_color,
                         title="Outcome 분포")
        st.plotly_chart(fig_out, use_container_width=True)

    st.subheader("부실 기업 Workout 목록")
    disp = wo_df[["company_name", "workout_type", "workout_start_ym",
                  "original_balance_억", "recovery_rate", "outcome"]].rename(columns={
        "company_name": "회사명", "workout_type": "Workout 유형",
        "workout_start_ym": "시작월", "original_balance_억": "원잔액(억)",
        "recovery_rate": "회수율", "outcome": "결과",
    })
    disp["회수율"] = disp["회수율"].apply(lambda v: f"{v*100:.1f}%")
    st.dataframe(disp, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. 📊 모델 성능
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📊 모델 성능":
    st.title("📊 모델 성능")
    st.markdown("walk-forward 교차검증 기반 모델 성능 지표.")

    fold_metrics_path = RESULTS_DIR / "fold_metrics.csv"
    feat_imp_path     = RESULTS_DIR / "feature_importance.csv"

    if fold_metrics_path.exists():
        fold_df = pd.read_csv(fold_metrics_path)
        avg_auroc = fold_df["auroc"].mean() if "auroc" in fold_df.columns else None
        avg_ks    = fold_df["ks"].mean()    if "ks"    in fold_df.columns else None

        # 모델 정보 카드
        model = load_model()
        n_features = len(model.get("feature_cols", [])) if model else "N/A"
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("알고리즘", "LightGBM")
        col_b.metric("타겟", "12개월 부도 여부")
        col_c.metric("피처 수", str(n_features))
        col_d.metric("평균 AUROC", f"{avg_auroc:.4f}" if avg_auroc else "N/A")

        # fold별 AUROC/KS
        fig_fold = go.Figure()
        if "auroc" in fold_df.columns:
            fig_fold.add_trace(go.Scatter(
                x=fold_df.index, y=fold_df["auroc"],
                mode="lines+markers", name="AUROC",
                line=dict(color="#27ae60"),
            ))
        if "ks" in fold_df.columns:
            fig_fold.add_trace(go.Scatter(
                x=fold_df.index, y=fold_df["ks"],
                mode="lines+markers", name="KS",
                line=dict(color="#3498db"),
            ))
        fig_fold.update_layout(
            title="Fold별 AUROC / KS 성능",
            xaxis_title="Fold",
            yaxis_title="Score",
            height=350,
        )
        st.plotly_chart(fig_fold, use_container_width=True)
    else:
        st.warning(f"fold_metrics.csv를 찾을 수 없습니다: {fold_metrics_path}")

    if feat_imp_path.exists():
        fi_df = pd.read_csv(feat_imp_path)
        # 컬럼명 정규화
        if "feature" not in fi_df.columns and len(fi_df.columns) >= 2:
            fi_df.columns = ["feature", "importance"] + list(fi_df.columns[2:])
        fi_df = fi_df.sort_values("importance", ascending=False).head(20)
        fig_fi = px.bar(
            fi_df, x="importance", y="feature", orientation="h",
            title="피처 중요도 상위 20개",
            labels={"importance": "중요도", "feature": "피처"},
        )
        fig_fi.update_layout(height=550, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_fi, use_container_width=True)
    else:
        st.warning(f"feature_importance.csv를 찾을 수 없습니다: {feat_imp_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# 10. 🎬 부실 탐지 시뮬레이션
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🎬 부실 탐지 시뮬레이션":
    st.title("🎬 부실 탐지 시뮬레이션")
    st.markdown("EWS 경보의 부실 탐지 선행성 분석 — 실제 부도 기업 대상.")

    answer_df = load_answer_key()
    signals   = load_signals()
    name_map  = get_name_map()

    def_df = answer_df[answer_df["scenario"] == "DEFAULT"].copy()
    def_df["company_name"] = def_df["borrower_id"].map(name_map)

    detected     = def_df[def_df["first_signal_ym"].notna() & def_df["lead_months"].notna()]
    not_detected = def_df[def_df["first_signal_ym"].isna()]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("부실기업 총수",   f"{len(def_df)}")
    k2.metric("경보 탐지 성공",  f"{len(detected)}")
    k3.metric("탐지 실패",       f"{len(not_detected)}")
    k4.metric("평균 선행기간(월)", f"{detected['lead_months'].mean():.1f}" if len(detected) > 0 else "N/A")

    # 선행기간 히스토그램
    if len(detected) > 0:
        fig_lead = px.histogram(
            detected, x="lead_months", nbins=20,
            title="경보 선행기간 분포 (월)",
            labels={"lead_months": "선행 기간(월)", "count": "기업 수"},
            color_discrete_sequence=["#3498db"],
        )
        fig_lead.update_layout(height=300)
        st.plotly_chart(fig_lead, use_container_width=True)

    st.divider()

    # 개별 기업 타임라인
    st.subheader("개별 기업 탐지 타임라인")
    sorted_names = sorted(def_df["company_name"].dropna().tolist())
    sel_name = st.selectbox("부실 기업 선택", sorted_names)

    sel_row = def_df[def_df["company_name"] == sel_name]
    if len(sel_row) > 0:
        sel = sel_row.iloc[0]
        bid = sel["borrower_id"]
        sig_c = signals[signals["borrower_id"] == bid].sort_values("ym")

        fig_sim = px.line(sig_c, x="ym", y="ews_score",
                          title=f"{sel_name} — EWS 스코어 추이",
                          markers=True,
                          labels={"ym": "월", "ews_score": "EWS 점수"})
        fig_sim.add_hline(y=30, line_dash="dash", line_color="#e67e22",
                          annotation_text="C등급 기준(30)")

        if sel["first_signal_ym"] and not pd.isna(sel["first_signal_ym"]):
            fig_sim.add_vline(
                x=int(sel["first_signal_ym"]),
                line_dash="solid", line_color="#f39c12",
                annotation_text=f"최초경보({int(sel['first_signal_ym'])})",
            )

        if sel["default_ym"] and not pd.isna(sel["default_ym"]):
            fig_sim.add_vline(
                x=int(sel["default_ym"]),
                line_dash="solid", line_color="#e74c3c",
                annotation_text=f"부도({int(sel['default_ym'])})",
            )

        fig_sim.update_layout(height=380)
        st.plotly_chart(fig_sim, use_container_width=True)

        # 성과 메시지
        if sel["lead_months"] and not pd.isna(sel["lead_months"]):
            lead = int(sel["lead_months"])
            if lead >= 6:
                st.success(f"경보가 부도 {lead}개월 전에 발생했습니다 — 충분한 대응 시간 확보.")
            elif lead >= 3:
                st.warning(f"경보가 부도 {lead}개월 전에 발생했습니다 — 즉각 조치 필요.")
            else:
                st.error(f"경보가 부도 {lead}개월 전에 발생했습니다 — 선행성 부족.")
        elif sel["first_signal_ym"] is None or pd.isna(sel["first_signal_ym"]):
            st.error("이 기업은 부도 전 EWS 경보가 발생하지 않았습니다 (미탐지).")
