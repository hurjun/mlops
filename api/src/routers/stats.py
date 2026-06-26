"""
일일 위반 통계 엔드포인트.
대시보드 상단의 "오늘 위반 총계" 카운터에 사용된다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ViolationEvent
from ..schemas import DailyStats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/daily", response_model=DailyStats)
def daily_stats(db: Session = Depends(get_db)) -> DailyStats:
    """
    오늘(UTC 기준) 발생한 위반 이벤트를 집계해서 반환한다.

    반환 예시:
    {
        "date": "2026-04-21",
        "by_site": {"site-001": 12, "site-002": 5},
        "by_kind": {"no_helmet": 10, "no_vest": 7},
        "total": 17
    }
    """
    # 오늘 UTC 자정 계산
    # occurred_at은 UTC 기준으로 저장되므로 "오늘"도 반드시 UTC로 계산해야 한다.
    # date.today()(로컬 날짜)를 쓰면 로컬-UTC 시차 때문에 집계가 어긋난다
    # (예: KST(UTC+9) 자정 직후에는 로컬 날짜가 UTC보다 하루 앞서 0건이 잡힘).
    today_utc = datetime.now(timezone.utc).date()
    today_start = datetime(
        today_utc.year, today_utc.month, today_utc.day, tzinfo=timezone.utc
    )

    # 오늘 발생한 모든 위반 이벤트 조회
    rows = (
        db.query(ViolationEvent)
        .filter(ViolationEvent.occurred_at >= today_start)
        .all()
    )

    # 현장별 카운트 집계
    by_site: dict[str, int] = {}
    for row in rows:
        by_site[row.site_id] = by_site.get(row.site_id, 0) + 1

    # 위반 종류별 카운트 집계
    by_kind: dict[str, int] = {}
    for row in rows:
        by_kind[row.kind] = by_kind.get(row.kind, 0) + 1

    return DailyStats(
        date=today_utc,
        by_site=by_site,
        by_kind=by_kind,
        total=len(rows),
    )
