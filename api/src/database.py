"""
데이터베이스 연결과 세션을 관리한다.

SQLAlchemy: Python 코드로 DB를 다룰 수 있게 해주는 라이브러리.
            SQL 쿼리를 직접 쓰지 않아도 Python 객체로 DB를 조작할 수 있다.

Session: DB와의 대화 채널 1개.
         요청이 들어올 때마다 세션을 열고, 응답이 나갈 때 닫는다.
         (마치 DB에 전화 걸고, 볼일 끝나면 끊는 것)
"""
from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import load_config

cfg = load_config()

# ── 엔진 생성 ──────────────────────────────────────────────────────────────────
# 엔진 = DB 연결 풀. 실제 DB 파일(또는 서버)과의 연결을 관리한다.
# check_same_thread=False: SQLite는 기본적으로 한 스레드에서만 쓸 수 있는데,
# FastAPI는 async(비동기) 환경이므로 이 제한을 풀어줘야 한다.
connect_args = {"check_same_thread": False} if "sqlite" in cfg.database_url else {}
engine = create_engine(cfg.database_url, connect_args=connect_args)

# ── 세션 팩토리 ────────────────────────────────────────────────────────────────
# SessionLocal(): 세션(DB 대화 채널)을 만드는 공장.
# autocommit=False: 명시적으로 commit() 해야 DB에 반영됨 (실수 방지)
# autoflush=False:  commit 전에 자동으로 DB에 쓰지 않음
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── ORM Base 클래스 ────────────────────────────────────────────────────────────
# ORM(Object-Relational Mapping): Python 클래스 ↔ DB 테이블을 1:1로 매핑
# Base를 상속하면 그 클래스가 DB 테이블이 된다. (models.py에서 사용)
class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """
    앱 시작 시 호출. DB 파일과 테이블을 생성한다.
    SQLite는 파일 기반이므로, 파일이 저장될 디렉터리도 미리 만들어줘야 한다.
    """
    # SQLite 파일 경로에서 디렉터리 부분 추출해서 미리 생성
    # 예: "sqlite:///./data/events.db" → "./data" 디렉터리 생성
    if "sqlite" in cfg.database_url:
        db_path = cfg.database_url.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Base를 상속한 모든 클래스(= 테이블)를 DB에 생성
    # 이미 존재하면 무시 (checkfirst=True 동작)
    from . import models  # noqa: F401 — models 임포트해야 Base가 테이블 구조를 앎
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI의 Depends()와 함께 쓰는 DB 세션 의존성 함수.

    요청 1개 → 세션 1개 열기 → 응답 완료 → 세션 닫기

    yield: 제너레이터. yield 전=세션 열기, yield 후=세션 닫기.
    try/finally: 에러가 나도 반드시 세션을 닫는다 (DB 연결 누수 방지).
    """
    db = SessionLocal()
    try:
        yield db       # 여기서 라우터 함수에 세션을 넘겨줌
    finally:
        db.close()     # 요청이 끝나면 반드시 세션 반환
