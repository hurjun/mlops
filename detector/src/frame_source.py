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
from abc import ABC, abstractmethod       # ABC = Abstract Base Class (인터페이스 역할)
from collections.abc import Iterator

import cv2
import numpy as np

log = logging.getLogger(__name__)


class FrameSource(ABC):
    """
    프레임 공급원 인터페이스.
    이 클래스를 상속하면 반드시 frames()와 close()를 구현해야 한다.
    pipeline.py는 이 타입만 알고, 실제 구현체(webcam/rtsp/file)는 모른다.
    """

    @abstractmethod
    def frames(self) -> Iterator[np.ndarray]:
        """BGR numpy 배열(프레임)을 하나씩 yield한다. 무한 또는 파일 끝까지."""

    @abstractmethod
    def close(self) -> None:
        """카메라/파일 자원을 해제한다."""


class OpenCVFrameSource(FrameSource):
    """
    OpenCV를 이용해 webcam / RTSP / 파일을 동일하게 처리한다.

    source에 넘길 수 있는 값:
      0, 1, 2 ...     → 로컬 웹캠 인덱스
      "rtsp://..."    → IP 카메라 RTSP 스트림
      "samples/a.mp4" → 로컬 영상 파일 (테스트용)

    reconnect=True 이면 RTSP 연결이 끊겼을 때 자동 재접속한다.
    (프로덕션에서는 exponential backoff가 필요하다 — 여기서는 단순 2초 대기)
    """

    def __init__(self, source: int | str, reconnect: bool = True) -> None:
        self._source = source
        self._reconnect = reconnect
        self._cap: cv2.VideoCapture | None = None  # OpenCV 캡처 객체

    def _open(self) -> cv2.VideoCapture:
        """cv2.VideoCapture를 열고 반환한다. 실패하면 예외를 발생시킨다."""
        cap = cv2.VideoCapture(self._source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open frame source: {self._source}")
        log.info("Opened frame source: %s", self._source)
        return cap

    def frames(self) -> Iterator[np.ndarray]:
        """
        프레임을 하나씩 yield하는 제너레이터.
        - 제너레이터: 모든 프레임을 메모리에 올리지 않고 하나씩 꺼내 쓴다.
        - 파일 소스: 끝에 도달하면 처음부터 다시 재생(루프)한다.
        - RTSP 소스: 연결이 끊기면 2초 후 재접속 시도한다.
        """
        self._cap = self._open()
        while True:
            ok, frame = self._cap.read()  # ok=False 이면 프레임 읽기 실패

            if not ok:
                # RTSP 연결 끊김 → 재접속
                if self._reconnect and isinstance(self._source, str):
                    log.warning("Frame read failed, reconnecting in 2s …")
                    self._cap.release()
                    time.sleep(2)
                    self._cap = self._open()
                    continue

                # mp4 파일 끝 → 처음부터 다시 (루프 재생)
                if isinstance(self._source, str) and self._source.endswith(
                    (".mp4", ".avi", ".mov")
                ):
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # 0번 프레임으로 이동
                    continue

                break  # 그 외(webcam 오류 등)는 루프 종료

            yield frame  # 프레임 1장을 pipeline.py에 넘겨준다

    def close(self) -> None:
        """VideoCapture 자원 해제. finally 블록에서 반드시 호출해야 한다."""
        if self._cap:
            self._cap.release()
            log.info("Frame source closed.")


def build_frame_source(
    kind: str,
    webcam_index: int = 0,
    rtsp_url: str = "",
    video_file: str = "",
) -> FrameSource:
    """
    환경변수 FRAME_SOURCE 값에 따라 적절한 FrameSource를 만들어 반환하는 팩토리 함수.
    main.py에서 이 함수 하나만 호출하면 된다.
    """
    if kind == "webcam":
        return OpenCVFrameSource(webcam_index)
    if kind == "rtsp":
        return OpenCVFrameSource(rtsp_url, reconnect=True)
    if kind == "file":
        return OpenCVFrameSource(video_file, reconnect=False)
    raise ValueError(f"Unknown FRAME_SOURCE: {kind!r}. Choose webcam | rtsp | file")
