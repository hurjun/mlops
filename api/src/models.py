"""
DB 테이블 구조를 Python 클래스로 정의한다.
클래스 1개 = DB 테이블 1개.

예: ViolationEvent 클래스 → DB의 violation_events 테이블
    클래스의 속성(id, site_id ...) → 테이블의 컬럼
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ViolationEvent(Base):
    """
    위반 이벤트 1건을 저장하는 테이블.

    detector가 POST /events 로 보낸 데이터가 여기 저장된다.

    컬럼 설명:
      id           : 자동 증가하는 고유 번호 (1, 2, 3, ...)
      site_id      : 어느 현장에서 온 이벤트인지 (예: "site-001")
      kind         : 위반 종류 (예: "no_helmet", "no_vest")
      confidence   : YOLO 탐지 확신도 (0.0 ~ 1.0)
      bbox         : 위반 위치 (JSON 문자열로 저장)
      description  : 사람이 읽을 수 있는 설명
      snapshot_b64 : 위반 순간 캡처 이미지 (JPEG → base64 인코딩)
                     Text 타입 (크기 제한 없음). 없을 수도 있어서 nullable.
      occurred_at  : 이벤트 발생 시각 (UTC 기준)
    """

    __tablename__ = "violation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    bbox: Mapped[str] = mapped_column(String(128))         # "[0.1, 0.2, 0.5, 0.8]"
    description: Mapped[str] = mapped_column(Text)
    snapshot_b64: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),  # 저장 시점의 UTC 시각 자동 기록
    )

    # ── 인덱스 ─────────────────────────────────────────────────────────────────
    # 자주 검색하는 컬럼에 인덱스를 걸면 조회 속도가 빨라진다.
    # (책의 목차처럼, 인덱스가 없으면 전체를 다 뒤져야 함)
    __table_args__ = (
        Index("ix_violation_events_site_id", "site_id"),
        Index("ix_violation_events_kind", "kind"),
        Index("ix_violation_events_occurred_at", "occurred_at"),
    )
