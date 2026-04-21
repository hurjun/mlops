"""
WebSocket 엔드포인트. 대시보드에 위반 이벤트를 실시간으로 push한다.

WebSocket vs HTTP 차이:
  HTTP:      클라이언트가 요청할 때만 서버가 응답 (단방향, 매번 연결)
  WebSocket: 한 번 연결하면 서버가 언제든 데이터를 push 가능 (양방향, 지속 연결)

이 엔드포인트가 하는 일:
  1. 대시보드가 ws://api/ws 로 연결
  2. broadcaster에 Queue 등록
  3. 이벤트가 Queue에 들어오면 즉시 대시보드로 전송
  4. 연결 끊기면 Queue 제거
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..broadcaster import broadcaster

router = APIRouter(tags=["stream"])
log = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_stream(ws: WebSocket) -> None:
    """
    WebSocket 연결을 수락하고, 이벤트가 올 때마다 클라이언트에 전송한다.

    흐름:
      연결 수락 → Queue 등록 → 이벤트 대기 루프 → 연결 끊기면 Queue 제거
    """
    await ws.accept()  # WebSocket 연결 수락 (HTTP → WebSocket 프로토콜 업그레이드)
    q = broadcaster.subscribe()  # 이 클라이언트 전용 Queue 등록
    log.info("WebSocket client connected.")

    try:
        while True:
            # Queue에 이벤트가 들어올 때까지 대기 (블로킹하지 않고 비동기 대기)
            event = await q.get()

            # 이벤트를 JSON으로 직렬화해서 클라이언트에 전송
            await ws.send_json(event)

    except WebSocketDisconnect:
        # 대시보드가 탭을 닫거나 새로고침하면 여기로 옴
        log.info("WebSocket client disconnected.")
    finally:
        # 연결이 끊기면 반드시 Queue를 제거해야 메모리 누수가 없다
        broadcaster.unsubscribe(q)
