"""
프레임 공급원을 추상화한다. pipeline.py는 프레임이 어디서 오는지 알 필요가 없다.
웹캠 인덱스, RTSP URL, 로컬 파일 — 모두 동일한 인터페이스로 소비된다.

엣지 배포 확장 포인트:
  Jetson에서 GStreamer pipeline string을 OpenCV에 넘기면 NVDEC 하드웨어 디코딩을 쓸 수 있다.
  그 경우에도 이 인터페이스는 그대로이고 OpenCVFrameSource 생성자에 string만 넘기면 된다.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator

import cv2
import numpy as np

log = logging.getLogger(__name__)


class FrameSource(ABC):
    @abstractmethod
    def frames(self) -> Iterator[np.ndarray]:
        """BGR numpy 배열을 무한(또는 파일 끝까지) 제공한다."""

    @abstractmethod
    def close(self) -> None:
        """자원을 해제한다."""


class OpenCVFrameSource(FrameSource):
    """
    webcam 인덱스(int), RTSP URL(str), 파일 경로(str) 를 모두 수용한다.
    reconnect=True 이면 RTSP 연결 끊김 시 재시도한다.
    프로덕션에서는 exponential backoff + dead-letter queue가 필요하다.
    """

    def __init__(self, source: int | str, reconnect: bool = True) -> None:
        self._source = source
        self._reconnect = reconnect
        self._cap: cv2.VideoCapture | None = None

    def _open(self) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(self._source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open frame source: {self._source}")
        log.info("Opened frame source: %s", self._source)
        return cap

    def frames(self) -> Iterator[np.ndarray]:
        self._cap = self._open()
        while True:
            ok, frame = self._cap.read()
            if not ok:
                if self._reconnect and isinstance(self._source, str):
                    log.warning("Frame read failed, reconnecting in 2s …")
                    self._cap.release()
                    time.sleep(2)
                    self._cap = self._open()
                    continue
                # 파일 소스는 루프 재생
                if isinstance(self._source, str) and self._source.endswith(
                    (".mp4", ".avi", ".mov")
                ):
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                break
            yield frame

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            log.info("Frame source closed.")


def build_frame_source(
    kind: str,
    webcam_index: int = 0,
    rtsp_url: str = "",
    video_file: str = "",
) -> FrameSource:
    """환경변수 kind 값에 따라 알맞은 FrameSource를 반환하는 팩토리."""
    if kind == "webcam":
        return OpenCVFrameSource(webcam_index)
    if kind == "rtsp":
        return OpenCVFrameSource(rtsp_url, reconnect=True)
    if kind == "file":
        return OpenCVFrameSource(video_file, reconnect=False)
    raise ValueError(f"Unknown FRAME_SOURCE: {kind!r}. Choose webcam | rtsp | file")
