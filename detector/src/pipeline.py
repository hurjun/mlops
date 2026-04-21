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
    def __init__(
        self,
        frame_source: FrameSource,
        detector: YoloDetector,
        rules: ViolationRules,
        publisher: EventPublisher,
        site_id: str,
        inference_interval: int = 5,
        violation_cooldown_sec: float = 10.0,
    ) -> None:
        self._source = frame_source
        self._detector = detector
        self._rules = rules
        self._publisher = publisher
        self._site_id = site_id
        self._inference_interval = inference_interval
        self._cooldown = violation_cooldown_sec

        # kind별 마지막 발행 시각 추적 → cooldown 동안 중복 방지
        self._last_emitted: dict[str, float] = {}

    def run(self) -> None:
        """파이프라인을 시작한다. 종료 신호(KeyboardInterrupt/SIGTERM)까지 블로킹."""
        log.info(
            "Pipeline started — site=%s interval=%d cooldown=%.0fs",
            self._site_id,
            self._inference_interval,
            self._cooldown,
        )
        frame_idx = 0
        violation_count = 0
        t_start = time.monotonic()

        for frame in self._source.frames():
            frame_idx += 1

            # 매 N번째 프레임에만 추론한다.
            # PPE 착용 상태는 초 단위로 바뀌지 않으므로 5프레임에 1회 추론으로 충분하다.
            # 30 FPS 소스 기준 약 6 FPS 추론 → GPU/CPU 부하 약 5배 절감.
            if frame_idx % self._inference_interval != 0:
                continue

            detections = self._detector.infer(frame)
            violations = self._rules.evaluate(detections)

            now = time.monotonic()
            for v in violations:
                last = self._last_emitted.get(v.kind, 0.0)
                if now - last < self._cooldown:
                    # cooldown 중 — 같은 위반이 반복 감지되어도 API에 스팸하지 않는다.
                    continue
                self._last_emitted[v.kind] = now
                self._publisher.publish(self._site_id, v, snapshot=frame)
                violation_count += 1

            # 50 추론마다 상태 로그
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
