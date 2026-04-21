"""
이벤트를 연결된 모든 WebSocket 클라이언트에게 동시에 전달하는 pub/sub 브로드캐스터.

pub/sub (Publish/Subscribe) 패턴:
  - Publisher(발행자): 이벤트를 만드는 쪽 (POST /events 라우터)
  - Subscriber(구독자): 이벤트를 받는 쪽 (WebSocket 연결된 대시보드들)
  - Broker(중개자):     이 broadcaster가 그 역할

대시보드 탭이 여러 개 열려있어도 모든 탭에 동시에 이벤트가 전달된다.

확장 주의사항:
  이 구현은 프로세스 메모리 내 in-memory pub/sub이다.
  uvicorn --workers 1 (단일 프로세스) 환경에서만 정상 동작한다.
  멀티 워커 환경(--workers 4)에서는 각 프로세스가 별도 메모리를 쓰므로
  이벤트가 일부 클라이언트에게만 전달될 수 있다.
  → 프로덕션 확장 시 Redis pub/sub으로 교체 필요 (인터페이스는 동일하게 유지)
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)


class EventBroadcaster:
    """
    연결된 모든 WebSocket 클라이언트에게 이벤트를 브로드캐스트한다.

    동작 방식:
      1. 대시보드가 WebSocket 연결 → subscribe() 로 Queue 등록
      2. detector 이벤트 도착 → publish() 로 모든 Queue에 넣기
      3. 각 WebSocket이 자기 Queue에서 꺼내서 클라이언트에 전송
      4. 대시보드 연결 끊김 → unsubscribe() 로 Queue 제거

    Queue: 선입선출(FIFO) 비동기 데이터 통로.
           publish()가 넣으면 WebSocket이 꺼내감.
    """

    def __init__(self) -> None:
        # 현재 연결된 모든 클라이언트의 Queue 집합
        # set을 쓰는 이유: 중복 없이 빠른 추가/삭제
        self._subscribers: set[asyncio.Queue[dict]] = set()

    def subscribe(self) -> asyncio.Queue[dict]:
        """
        새 WebSocket 연결 시 호출.
        이 클라이언트 전용 Queue를 만들어 등록하고 반환한다.
        """
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        log.debug("Subscriber added. Total: %d", len(self._subscribers))
        return q

    def unsubscribe(self, q: asyncio.Queue[dict]) -> None:
        """
        WebSocket 연결 끊김 시 호출.
        해당 Queue를 구독자 목록에서 제거한다.
        """
        self._subscribers.discard(q)  # 없어도 에러 안 남 (discard vs remove)
        log.debug("Subscriber removed. Total: %d", len(self._subscribers))

    async def publish(self, event: dict) -> None:
        """
        이벤트를 모든 구독자의 Queue에 넣는다.
        Queue가 가득 찼으면(100개 초과) 해당 클라이언트는 건너뛴다.
        (느린 클라이언트 때문에 전체가 막히는 것을 방지)
        """
        for q in list(self._subscribers):  # list()로 복사: 반복 중 변경 방지
            try:
                q.put_nowait(event)   # 비어있으면 즉시 넣기, 가득 차면 예외
            except asyncio.QueueFull:
                log.warning("Subscriber queue full, dropping event for slow client.")


# 앱 전체에서 공유하는 싱글톤 인스턴스
# main.py에서 import해서 라우터들이 이 객체를 공유한다.
broadcaster = EventBroadcaster()
