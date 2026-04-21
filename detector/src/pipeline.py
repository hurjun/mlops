"""
frame → infer → rules → publish 파이프라인을 오케스트레이션한다.
각 단계는 독립적으로 교체 가능하며, Pipeline은 이들을 연결하는 역할만 한다.
"""
from __future__ import annotations

import logging
import time

import numpy as np

from .event_publisher import EventPublisher
from .frame_source import FrameSource
from .inference import YoloDetector
from .violation_rules import ViolationRules

log = logging.getLogger(__name__)


class Pipeline:
    """
    detector의 핵심 루프.

    의존성을 주입받아(dependency injection) 조립한다.
    Pipeline 자체는 카메라가 뭔지, 모델이 뭔지, API가 어딘지 모른다.
    각 조각만 교체하면 Pipeline 코드는 수정할 필요가 없다.

    [흐름 요약]
    카메라 프레임 → (N프레임마다) YOLO 추론 → 위반 판정 → (cooldown 체크) → API 전송
    """

    def __init__(
        self,
        frame_source: FrameSource,      # 프레임 공급원 (webcam/rtsp/file)
        detector: YoloDetector,          # YOLO 추론기
        rules: ViolationRules,           # 현장별 위반 판정 규칙
        publisher: EventPublisher,       # 이벤트 전송기 (HTTP/MQTT)
        site_id: str,                    # 현장 식별자 (어느 사이트인지)
        inference_interval: int = 5,     # 몇 프레임마다 추론할지
        violation_cooldown_sec: float = 10.0,  # 같은 위반 재전송 금지 시간(초)
    ) -> None:
        self._source = frame_source
        self._detector = detector
        self._rules = rules
        self._publisher = publisher
        self._site_id = site_id
        self._inference_interval = inference_interval
        self._cooldown = violation_cooldown_sec

        # 위반 종류(kind)별로 마지막으로 API에 보낸 시각을 기록한다.
        # 예: {"no_helmet": 1714123456.7, "no_vest": 1714123460.2}
        # cooldown 동안은 같은 kind를 다시 보내지 않는다.
        self._last_emitted: dict[str, float] = {}

    def run(self) -> None:
        """
        파이프라인 메인 루프. KeyboardInterrupt 또는 SIGTERM 이 올 때까지 실행된다.

        30 FPS 영상 + inference_interval=5 기준:
          - 초당 30 프레임 들어옴
          - 초당 6번만 YOLO 추론 (5배 부하 절감)
          - cooldown=10s → 같은 위반은 10초에 1번만 API 전송
        """
        log.info(
            "Pipeline started — site=%s interval=%d cooldown=%.0fs",
            self._site_id,
            self._inference_interval,
            self._cooldown,
        )
        frame_idx = 0        # 지금까지 받은 전체 프레임 수
        violation_count = 0  # 지금까지 API에 전송한 위반 이벤트 수
        t_start = time.monotonic()

        for frame in self._source.frames():
            frame_idx += 1

            # ── 프레임 샘플링 ──────────────────────────────────────────────
            # inference_interval=5 이면 1, 2, 3, 4번 프레임은 건너뛰고
            # 5, 10, 15... 번 프레임만 추론한다.
            # PPE 착용 상태는 초 단위로 바뀌지 않으므로 매 프레임 추론은 낭비다.
            if frame_idx % self._inference_interval != 0:
                continue

            # ── YOLO 추론 ─────────────────────────────────────────────────
            # frame(이미지 1장) → detections(탐지된 물체 목록)
            # 예: [Detection("person", 0.9, ...), Detection("helmet", 0.8, ...)]
            detections = self._detector.infer(frame)

            # ── 위반 판정 ─────────────────────────────────────────────────
            # detections → violations(위반 목록)
            # 예: [Violation("no_helmet", 0.9, ..., "Person without helmet")]
            violations = self._rules.evaluate(detections)

            # ── cooldown 체크 + API 전송 ───────────────────────────────────
            now = time.monotonic()
            for v in violations:
                last = self._last_emitted.get(v.kind, 0.0)

                # 마지막 전송으로부터 cooldown이 안 지났으면 스킵
                # (같은 위반이 계속 감지돼도 10초에 1번만 API 전송)
                if now - last < self._cooldown:
                    continue

                self._last_emitted[v.kind] = now   # 마지막 전송 시각 업데이트
                self._publisher.publish(self._site_id, v, snapshot=frame)
                violation_count += 1

            # ── 주기적 상태 로그 ──────────────────────────────────────────
            # 50번 추론마다 FPS와 위반 횟수를 로그로 출력한다.
            infer_idx = frame_idx // self._inference_interval
            if infer_idx % 50 == 0 and infer_idx > 0:
                elapsed = time.monotonic() - t_start
                fps = frame_idx / elapsed if elapsed > 0 else 0
                log.info(
                    "frame=%d infer=%d violations=%d fps=%.1f",
                    frame_idx,
                    infer_idx,
                    violation_count,
                    fps,
                )
