"""
detector 서비스의 엔트리포인트.
설정을 읽고 의존성을 조립한 뒤 파이프라인을 실행한다.
"""
from __future__ import annotations

import logging
import signal
import sys

from .config import load_config
from .event_publisher import HttpEventPublisher
from .frame_source import build_frame_source
from .inference import YoloDetector
from .pipeline import Pipeline
from .violation_rules import ViolationRules

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
log = logging.getLogger(__name__)


def main() -> None:
    cfg = load_config()
    log.info("Starting PPE Watchman detector — site=%s", cfg.site_id)

    frame_source = build_frame_source(
        kind=cfg.frame_source,
        webcam_index=cfg.webcam_index,
        rtsp_url=cfg.rtsp_url,
        video_file=cfg.video_file,
    )

    try:
        detector = YoloDetector(cfg.model_path, cfg.confidence_threshold)
        rules = ViolationRules(required_ppe=["helmet", "vest"])
        publisher = HttpEventPublisher(cfg.api_url)

        pipeline = Pipeline(
            frame_source=frame_source,
            detector=detector,
            rules=rules,
            publisher=publisher,
            site_id=cfg.site_id,
            inference_interval=cfg.inference_interval,
            violation_cooldown_sec=cfg.violation_cooldown_sec,
        )

        # SIGTERM 수신 시(docker-compose down) 클린 종료
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

        pipeline.run()

    except KeyboardInterrupt:
        log.info("Interrupted by user.")
    finally:
        frame_source.close()
        log.info("Detector stopped.")


if __name__ == "__main__":
    main()
