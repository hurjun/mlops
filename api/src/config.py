"""
API 서버의 환경변수를 한 곳에서 관리한다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # DB 연결 문자열
    # 기본값: SQLite 파일 (api/data/events.db)
    # 프로덕션: "postgresql://user:pass@host/dbname" 으로 교체
    database_url: str

    # CORS 허용 출처 목록 (쉼표로 구분)
    # 예: "http://localhost:3000,https://dashboard.mycompany.com"
    cors_origins: list[str]


def load_config() -> Config:
    raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return Config(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/events.db"),
        cors_origins=[o.strip() for o in raw_origins.split(",")],
    )
