"""
YOLO 모델을 래핑하고, 추론 결과를 Detection 값 객체로 정규화한다.
이 모듈 밖에서는 YOLO API를 직접 호출하지 않는다.

모델 교체 경로:
  - Jetson 배포: TensorRT engine (.engine) → 동일 인터페이스 유지
  - CPU 서버: ONNX Runtime (.onnx) → 동일 인터페이스 유지
  YoloDetector만 교체하면 pipeline.py 는 수정이 필요 없다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Detection:
    """단일 객체 탐지 결과. bbox는 이미지 크기에 무관하게 0~1로 정규화된 값."""

    label: str
    confidence: float
    # (x1, y1, x2, y2) — 좌상단·우하단, 0~1 정규화
    bbox_xyxy_norm: tuple[float, float, float, float]


class YoloDetector:
    def __init__(self, model_path: str, confidence_threshold: float = 0.4) -> None:
        # import를 여기서 해서 ultralytics 없는 환경(테스트)에서도 모듈 로드 가능
        from ultralytics import YOLO

        self._model = YOLO(model_path)
        self._conf = confidence_threshold
        log.info("YOLO model loaded: %s (conf≥%.2f)", model_path, confidence_threshold)

    def infer(self, frame_bgr: np.ndarray) -> list[Detection]:
        """프레임 한 장을 추론하고 Detection 리스트를 반환한다."""
        h, w = frame_bgr.shape[:2]
        results = self._model.predict(frame_bgr, conf=self._conf, verbose=False)

        detections: list[Detection] = []
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            label = self._model.names[cls_id]
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append(
                Detection(
                    label=label,
                    confidence=conf,
                    bbox_xyxy_norm=(x1 / w, y1 / h, x2 / w, y2 / h),
                )
            )
        return detections
