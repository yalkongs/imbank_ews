"""
iM뱅크 EWS 데모 시스템 - FastAPI 메인 애플리케이션
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from .core.database import engine, Base
from .api import (
    dashboard, ews, company, portfolio, asset_classification, ecl, covenant, workout, model_perf,
    ews_action, maturity, monthly_report, migration, benchmark, stress_test, rm, concentration, search,
    ews_advanced
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="iM뱅크 EWS 데모 시스템",
    description="""
    기업여신 조기경보 시스템 (Early Warning System) 데모

    ## 주요 기능
    - **EWS 대시보드**: 경보 현황, 등급 분포, 추이 분석
    - **EWS 경보센터**: 등급별/업종별 경보 기업 목록
    - **기업 조회**: 기업별 EWS 신호, 여신, ECL, 코베넌트 상세
    - **포트폴리오 분석**: 업종별/규모별 여신 집중도
    - **자산건전성 분류**: IFRS9 자산건전성 분류 현황
    - **ECL 관리**: 충당금 산출, Stage별 분석
    - **코베넌트 모니터링**: 위반 현황, 추이 분석
    - **NPL/Workout**: 부실채권 관리, 회수율 분석
    - **모델 성능**: AUROC, KS, 혼동행렬, 선행 시간
    - **부실탐지 시뮬레이션**: 부도 기업 EWS 경보 타임라인
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(dashboard.router)
app.include_router(ews.router)
app.include_router(company.router)
app.include_router(portfolio.router)
app.include_router(asset_classification.router)
app.include_router(ecl.router)
app.include_router(covenant.router)
app.include_router(workout.router)
app.include_router(model_perf.router)
app.include_router(ews_action.router)
app.include_router(maturity.router)
app.include_router(monthly_report.router)
app.include_router(migration.router)
app.include_router(benchmark.router)
app.include_router(stress_test.router)
app.include_router(rm.router)
app.include_router(concentration.router)
app.include_router(search.router)
app.include_router(ews_advanced.router)


@app.get("/health")
def health_check():
    """헬스체크 엔드포인트"""
    return {"status": "healthy"}


# 프론트엔드 빌드 파일 서빙
FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend", "dist"
)

if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA 라우팅 - 모든 비-API 경로를 index.html로"""
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
