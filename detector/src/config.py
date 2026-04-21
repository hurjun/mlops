"""
모든 환경변수를 한 곳에서 읽어 타입이 붙은 Config 객체로 변환한다.
os.getenv 호출이 여기에만 존재하므로, 설정 변경이 미치는 범위가 명확하다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


# frozen=True: 생성 후 값을 바꿀 수 없다.
# 설정값은 프로그램 실행 중 바뀌면 안 되므로 불변 객체로 만든다.
@dataclass(frozen=True)
class Config:
    # ── 중앙 API 서버 연결 ────────────────────────────────────────────────────
    api_url: str   # 예: http://api:8000  (docker 내부) or http://localhost:8000
    site_id: str   # 예: site-001  → 어느 현장에서 온 이벤트인지 구분하는 식별자

    # ── 프레임 소스 ───────────────────────────────────────────────────────────
    # frame_source: "webcam" | "rtsp" | "file" 세 가지 중 하나
    #   webcam → 로컬 웹캠 (webcam_index 사용)
    #   rtsp   → IP 카메라 스트림 (rtsp_url 사용)
    #   file   → 테스트용 mp4 파일 (video_file 사용)
    frame_source: str
    webcam_index: int   # webcam 모드일 때: 0 = 첫 번째 카메라
    rtsp_url: str       # rtsp 모드일 때: rtsp://카메라IP/stream
    video_file: str     # file 모드일 때: samples/sample.mp4

    # ── YOLO 추론 설정 ────────────────────────────────────────────────────────
    model_path: str              # yolov8n.pt (COCO) or PPE fine-tuned 모델 경로
    confidence_threshold: float  # 이 값 이상인 탐지 결과만 사용 (0.0 ~ 1.0)

    # ── 파이프라인 동작 ───────────────────────────────────────────────────────
    # inference_interval: 5 → 5프레임마다 1번만 YOLO 실행
    # PPE 착용 상태는 초 단위로 바뀌지 않으므로 매 프레임 추론할 필요가 없다.
    inference_interval: int

    # violation_cooldown_sec: 같은 종류의 위반을 이 시간(초) 동안 재발행하지 않음
    # 예: 10초 → 헬멧 미착용이 계속 감지돼도 API에는 10초에 1번만 전송
    violation_cooldown_sec: float


def load_config() -> Config:
    """환경변수(.env 파일 or docker-compose environment)를 읽어 Config를 만든다."""
    return Config(
        api_url=os.getenv("API_URL", "http://localhost:8000"),
        site_id=os.getenv("SITE_ID", "site-001"),
        frame_source=os.getenv("FRAME_SOURCE", "file"),
        webcam_index=int(os.getenv("WEBCAM_INDEX", "0")),
        rtsp_url=os.getenv("RTSP_URL", ""),
        video_file=os.getenv("VIDEO_FILE", "samples/sample.mp4"),
        model_path=os.getenv("MODEL_PATH", "yolov8n.pt"),
        confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.4")),
        inference_interval=int(os.getenv("INFERENCE_INTERVAL", "5")),
        violation_cooldown_sec=float(os.getenv("VIOLATION_COOLDOWN_SEC", "10")),
    )
