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
    """
    YOLO가 한 물체를 탐지한 결과 1건.

    label           : YOLO 클래스 이름 (예: "person", "helmet", "no_helmet")
    confidence      : 탐지 확신도 (0.0 ~ 1.0). 높을수록 확실하다.
    bbox_xyxy_norm  : 탐지된 물체의 위치.
                      (좌상단 x, 좌상단 y, 우하단 x, 우하단 y)
                      값이 0~1 사이로 정규화되어 있어 해상도에 무관하다.
                      예: (0.1, 0.2, 0.4, 0.8) → 이미지의 10~40% 가로, 20~80% 세로
    """
    label: str
    confidence: float
    bbox_xyxy_norm: tuple[float, float, float, float]


class YoloDetector:
    """
    Ultralytics YOLO 모델을 감싸는 래퍼 클래스.
    infer() 하나만 공개 API로 노출하고, YOLO 내부 구조는 밖에서 볼 수 없다.
    """

    def __init__(self, model_path: str, confidence_threshold: float = 0.4) -> None:
        # import를 __init__ 안에 넣는 이유:
        # ultralytics가 없는 환경(단위 테스트 등)에서도 이 모듈을 import할 수 있다.
        from ultralytics import YOLO

        self._model = YOLO(model_path)
        self._conf = confidence_threshold
        log.info("YOLO model loaded: %s (conf≥%.2f)", model_path, confidence_threshold)

    def infer(self, frame_bgr: np.ndarray) -> list[Detection]:
        """
        프레임 1장을 YOLO에 넣고 탐지 결과를 Detection 리스트로 반환한다.

        내부 동작:
          1. YOLO가 프레임 전체를 1번에 훑어 물체 위치와 클래스를 동시에 출력
          2. confidence_threshold 미만 결과는 버림
          3. bbox를 픽셀 좌표 → 0~1 정규화로 변환
          4. Detection 객체로 포장해서 반환
        """
        h, w = frame_bgr.shape[:2]  # 프레임의 높이(h), 너비(w) 픽셀

        # verbose=False: YOLO의 콘솔 출력 억제
        results = self._model.predict(frame_bgr, conf=self._conf, verbose=False)

        detections: list[Detection] = []
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            label = self._model.names[cls_id]   # 클래스 ID → 이름 변환 (예: 0 → "person")
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()  # 픽셀 좌표

            detections.append(
                Detection(
                    label=label,
                    confidence=conf,
                    # 픽셀 좌표를 0~1로 나눠서 해상도 독립적인 값으로 만든다
                    bbox_xyxy_norm=(x1 / w, y1 / h, x2 / w, y2 / h),
                )
            )
        return detections
