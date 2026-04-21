"""
FastAPI 애플리케이션의 시작점.
앱 생성, 미들웨어 설정, 라우터 등록, 시작/종료 훅을 담당한다.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import load_config
from .database import init_db
from .routers import events, stats, stream

cfg = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    앱 시작/종료 시 실행할 코드를 정의한다.

    yield 이전: 앱 시작 시 실행 (DB 초기화)
    yield 이후: 앱 종료 시 실행 (현재는 없음)

    lifespan을 쓰는 이유:
      예전 방식(@app.on_event)은 deprecated됨.
      lifespan이 FastAPI 공식 권장 방식이다.
    """
    # 앱 시작 시: DB 파일 및 테이블 생성
    init_db()
    yield
    # 앱 종료 시: 필요한 정리 작업 (현재는 없음)


# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="PPE Watchman API",
    version="0.1.0",
    description="산업 현장 PPE 위반 이벤트 수집 및 실시간 스트리밍 API",
    lifespan=lifespan,
)

# ── CORS 미들웨어 ──────────────────────────────────────────────────────────────
# CORS(Cross-Origin Resource Sharing):
#   브라우저 보안 정책 때문에, 다른 도메인의 API를 호출하려면 서버가 허용해야 한다.
#   예: dashboard(localhost:3000) → api(localhost:8000) 호출 시 CORS 설정 필요
#
# 프로덕션에서는 allow_origins=["*"] 대신 정확한 도메인을 명시해야 한다.
# 예: allow_origins=["https://dashboard.mycompany.com"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],   # GET, POST, OPTIONS 등 모든 HTTP 메서드 허용
    allow_headers=["*"],   # 모든 헤더 허용
)

# ── 라우터 등록 ────────────────────────────────────────────────────────────────
# 각 라우터 파일에서 정의한 엔드포인트들을 앱에 연결한다.
app.include_router(events.router)   # POST /events, GET /events
app.include_router(stats.router)    # GET /stats/daily
app.include_router(stream.router)   # WebSocket /ws


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """
    서버가 정상 동작 중인지 확인하는 헬스체크 엔드포인트.
    docker-compose의 healthcheck가 이 엔드포인트를 호출한다.
    detector는 api가 healthy 상태가 될 때까지 시작을 기다린다.
    """
    return {"status": "ok"}
