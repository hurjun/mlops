"""
API 요청/응답의 데이터 형태(스키마)를 정의한다.

models.py 와의 차이:
  models.py  → DB 테이블 구조 (SQLAlchemy)
  schemas.py → API 입출력 구조 (Pydantic)

Pydantic: 데이터 유효성 검사 라이브러리.
          잘못된 타입(예: confidence에 문자열)이 들어오면 자동으로 422 에러 반환.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ViolationEventIn(BaseModel):
    """
    detector → API 로 POST 할 때 보내는 데이터 형태.

    예시 JSON:
    {
        "site_id": "site-001",
        "kind": "no_helmet",
        "confidence": 0.91,
        "bbox_xyxy_norm": [0.1, 0.2, 0.5, 0.8],
        "description": "Person detected without helmet",
        "snapshot_b64": "..."
    }
    """
    site_id: str
    kind: str
    confidence: float = Field(ge=0.0, le=1.0)  # 0.0 이상 1.0 이하만 허용
    bbox_xyxy_norm: list[float] = Field(min_length=4, max_length=4)  # 반드시 4개
    description: str
    snapshot_b64: str | None = None  # 이미지는 없을 수도 있음


class ViolationEventOut(BaseModel):
    """
    API → 클라이언트(dashboard) 로 응답할 때 보내는 데이터 형태.

    snapshot_b64는 포함하지 않는다.
    이미지는 용량이 크므로 목록 조회 시 제외 → 트래픽 절감.
    (필요하면 별도 엔드포인트로 요청하는 방식)
    """
    id: int
    site_id: str
    kind: str
    confidence: float
    bbox_xyxy_norm: list[float]
    description: str
    occurred_at: datetime

    # orm_mode: SQLAlchemy 모델 객체를 그대로 Pydantic 스키마로 변환 가능하게 함
    # 예: ViolationEventOut.model_validate(db_row) → 자동 변환
    model_config = {"from_attributes": True}


class DailyStats(BaseModel):
    """
    GET /stats/daily 응답 형태.
    오늘 발생한 위반을 현장별·종류별로 집계한 결과.

    예시:
    {
        "date": "2026-04-21",
        "by_site": {"site-001": 12, "site-002": 5},
        "by_kind": {"no_helmet": 10, "no_vest": 7},
        "total": 17
    }
    """
    date: date
    by_site: dict[str, int]   # 현장별 위반 횟수
    by_kind: dict[str, int]   # 종류별 위반 횟수
    total: int                # 전체 위반 횟수
