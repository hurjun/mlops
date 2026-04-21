"""
위반 이벤트를 외부 시스템에 발행하는 인터페이스와 구현체를 정의한다.
전송 프로토콜(HTTP/MQTT/WebSocket)은 이 파일 안에 캡슐화되며,
pipeline.py는 어떤 프로토콜을 쓰는지 알 필요가 없다.

공장 네트워크 환경은 인터넷이 격리되어 MQTT broker를 경유하는 경우가 많다.
MQTT/WebSocket 구현체는 이 인터페이스를 implement하기만 하면 된다.
로봇 실시간 제어에서 MQTT를 사용한 경험이 이 설계에 직결된다.
"""
from __future__ import annotations

import base64
import logging
from abc import ABC, abstractmethod

import cv2
import numpy as np
import requests

from .violation_rules import Violation

log = logging.getLogger(__name__)


class EventPublisher(ABC):
    @abstractmethod
    def publish(
        self,
        site_id: str,
        violation: Violation,
        snapshot: np.ndarray | None = None,
    ) -> None:
        """위반 이벤트를 발행한다. 실패해도 파이프라인을 중단시키지 않는다."""


class HttpEventPublisher(EventPublisher):
    """
    중앙 API 서버로 HTTP POST 요청을 보낸다.
    requests.Session을 재사용해 TCP 연결 overhead를 줄인다.
    """

    def __init__(self, api_url: str) -> None:
        self._api_url = api_url.rstrip("/")
        self._session = requests.Session()

    def publish(
        self,
        site_id: str,
        violation: Violation,
        snapshot: np.ndarray | None = None,
    ) -> None:
        snapshot_b64: str | None = None
        if snapshot is not None:
            ok, buf = cv2.imencode(".jpg", snapshot, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                snapshot_b64 = base64.b64encode(buf).decode()

        payload = {
            "site_id": site_id,
            "kind": violation.kind,
            "confidence": violation.confidence,
            "bbox_xyxy_norm": list(violation.bbox_xyxy_norm),
            "description": violation.description,
            "snapshot_b64": snapshot_b64,
        }

        try:
            resp = self._session.post(
                f"{self._api_url}/events",
                json=payload,
                timeout=5,
            )
            resp.raise_for_status()
            log.debug("Event published: %s @ %s", violation.kind, site_id)
        except requests.RequestException as exc:
            # 네트워크 실패는 경고만 남기고 파이프라인을 계속 진행한다.
            # 프로덕션에서는 로컬 큐에 저장 후 재전송하는 store-and-forward 패턴이 필요하다.
            log.warning("Failed to publish event: %s", exc)
