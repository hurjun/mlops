"""
위반 이벤트 수신(POST)과 조회(GET) 엔드포인트.

POST /events : detector가 위반 발생 시 호출 → DB 저장 + 브로드캐스트
GET  /events : dashboard가 초기 로드 시 최근 이벤트 목록 요청
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..broadcaster import broadcaster
from ..database import get_db
from ..models import ViolationEvent
from ..schemas import ViolationEventIn, ViolationEventOut

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", status_code=201)
async def create_event(
    payload: ViolationEventIn,   # 요청 body를 자동으로 파싱 + 유효성 검사
    db: Session = Depends(get_db),  # DB 세션 자동 주입 (요청마다 새 세션)
) -> ViolationEventOut:
    """
    detector로부터 위반 이벤트를 받아 저장하고 대시보드에 브로드캐스트한다.

    처리 순서:
      1. payload(JSON) → ViolationEvent(DB 모델) 변환
      2. DB에 저장 (commit)
      3. broadcaster로 연결된 모든 대시보드에 실시간 전송
         (snapshot은 용량이 크므로 브로드캐스트에서 제외)
      4. 저장된 이벤트 반환 (201 Created)
    """
    # DB 모델 객체 생성
    db_event = ViolationEvent(
        site_id=payload.site_id,
        kind=payload.kind,
        confidence=payload.confidence,
        bbox=json.dumps(payload.bbox_xyxy_norm),  # 리스트 → JSON 문자열로 저장
        description=payload.description,
        snapshot_b64=payload.snapshot_b64,
    )

    # DB에 저장
    db.add(db_event)    # INSERT 준비
    db.commit()         # 실제 DB에 반영
    db.refresh(db_event)  # DB가 자동 생성한 id, occurred_at 등을 객체에 반영

    # 대시보드에 실시간 전송 (snapshot 제외 — 용량 절감)
    await broadcaster.publish({
        "id": db_event.id,
        "site_id": db_event.site_id,
        "kind": db_event.kind,
        "confidence": db_event.confidence,
        "bbox_xyxy_norm": payload.bbox_xyxy_norm,
        "description": db_event.description,
        "occurred_at": db_event.occurred_at.isoformat(),
    })

    return ViolationEventOut(
        id=db_event.id,
        site_id=db_event.site_id,
        kind=db_event.kind,
        confidence=db_event.confidence,
        bbox_xyxy_norm=payload.bbox_xyxy_norm,
        description=db_event.description,
        occurred_at=db_event.occurred_at,
    )


@router.get("", response_model=list[ViolationEventOut])
def list_events(
    limit: int = Query(default=20, ge=1, le=100),  # 최대 100개까지 요청 가능
    site_id: str | None = Query(default=None),      # 특정 현장만 필터링 (선택)
    kind: str | None = Query(default=None),          # 특정 위반 종류만 필터링 (선택)
    db: Session = Depends(get_db),
) -> list[ViolationEventOut]:
    """
    최근 위반 이벤트 목록을 반환한다.
    dashboard 초기 로드 시 사용 (이후는 WebSocket으로 실시간 수신).

    예: GET /events?limit=20&site_id=site-001&kind=no_helmet
    """
    query = db.query(ViolationEvent)

    # 필터 조건이 있으면 적용
    if site_id:
        query = query.filter(ViolationEvent.site_id == site_id)
    if kind:
        query = query.filter(ViolationEvent.kind == kind)

    # 최신순 정렬 후 limit 개수만 가져오기
    rows = query.order_by(ViolationEvent.occurred_at.desc()).limit(limit).all()

    return [
        ViolationEventOut(
            id=row.id,
            site_id=row.site_id,
            kind=row.kind,
            confidence=row.confidence,
            bbox_xyxy_norm=json.loads(row.bbox),  # JSON 문자열 → 리스트로 복원
            description=row.description,
            occurred_at=row.occurred_at,
        )
        for row in rows
    ]
