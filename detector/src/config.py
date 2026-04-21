"""
모든 환경변수를 한 곳에서 읽어 타입이 붙은 Config 객체로 변환한다.
os.getenv 호출이 여기에만 존재하므로, 설정 변경이 미치는 범위가 명확하다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # API 연결
    api_url: str
    site_id: str

    # 프레임 소스 종류: webcam | rtsp | file
    frame_source: str
    webcam_index: int
    rtsp_url: str
    video_file: str

    # 추론 설정
    model_path: str
    confidence_threshold: float

    # 파이프라인 동작
    # 매 N번째 프레임에만 추론 → GPU/CPU 부하 절감
    inference_interval: int
    # 같은 종류의 위반을 이 시간(초) 동안 재발행하지 않음 → API 스팸 방지
    violation_cooldown_sec: float


def load_config() -> Config:
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
