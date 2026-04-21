"""
현장별 PPE 착용 규칙을 평가한다. 이 파일이 고객사별 커스터마이징 포인트다.

건설현장 → required_ppe=["helmet"]
화학공장 → required_ppe=["helmet", "vest", "goggles"]
냉동창고 → required_ppe=["thermal_suit"]

JD의 '고객 요구사항 기반 프로토콜/알고리즘 설계'와 직접 대응한다.
Temporal smoothing(연속 N 프레임 위반 시에만 이벤트 발생)은 pipeline 레이어에서 처리한다.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .inference import Detection

# PPE fine-tuned 모델의 위반 클래스명 → 표준 kind 매핑
# 예: keremberke/yolov8n-hard-hat-detection 의 클래스명을 여기에 추가
_DIRECT_VIOLATION_LABELS: dict[str, str] = {
    "no_helmet": "no_helmet",
    "no_hardhat": "no_helmet",
    "no_vest": "no_vest",
    "no_safety_vest": "no_vest",
    "no_goggles": "no_goggles",
}

# PPE 착용 상태를 나타내는 클래스명 (이게 보이면 해당 PPE는 착용 중)
_PPE_PRESENT_LABELS: dict[str, str] = {
    "helmet": "helmet",
    "hardhat": "helmet",
    "hard hat": "helmet",
    "safety vest": "vest",
    "vest": "vest",
}


@dataclass(frozen=True)
class Violation:
    kind: str                                          # 위반 종류 (예: "no_helmet")
    confidence: float
    bbox_xyxy_norm: tuple[float, float, float, float]  # 위반 감지 위치
    description: str                                   # 사람이 읽을 수 있는 설명


class ViolationRules:
    """
    두 가지 평가 경로를 지원한다.

    Case A (PPE fine-tuned 모델):
      no_helmet, no_vest 같은 전용 클래스가 있으면 직접 매핑.

    Case B (COCO pretrained fallback — 프로토타입용):
      전용 클래스가 없으면 'person'이 감지됐는데 required PPE 클래스가
      같은 프레임에 없을 경우 위반 stub을 발생시킨다.
      end-to-end 파이프라인 동작을 확인하기 위한 경로이며,
      실제 배포 전 fine-tuned 모델로 교체해야 한다.
    """

    def __init__(self, required_ppe: Iterable[str]) -> None:
        # 예: {"helmet", "vest"}
        self._required: set[str] = set(required_ppe)

    def evaluate(self, detections: list[Detection]) -> list[Violation]:
        violations: list[Violation] = []

        # Case A: fine-tuned 모델의 직접 위반 클래스
        for det in detections:
            kind = _DIRECT_VIOLATION_LABELS.get(det.label.lower())
            if kind and _ppe_kind_from_violation(kind) in self._required:
                violations.append(
                    Violation(
                        kind=kind,
                        confidence=det.confidence,
                        bbox_xyxy_norm=det.bbox_xyxy_norm,
                        description=f"{kind.replace('_', ' ')} detected (conf={det.confidence:.2f})",
                    )
                )

        # Case A에서 위반이 발견되면 Case B는 건너뜀
        if violations:
            return violations

        # Case B: COCO weights fallback — person은 있는데 PPE 클래스가 없으면 위반
        labels = {d.label.lower() for d in detections}
        if "person" not in labels:
            return []

        present_ppe: set[str] = set()
        for label in labels:
            ppe_kind = _PPE_PRESENT_LABELS.get(label)
            if ppe_kind:
                present_ppe.add(ppe_kind)

        # person 감지의 대표 bbox (첫 번째 person)
        person_det = next(d for d in detections if d.label.lower() == "person")

        for required in self._required:
            if required not in present_ppe:
                violations.append(
                    Violation(
                        kind=f"no_{required}",
                        confidence=person_det.confidence,
                        bbox_xyxy_norm=person_det.bbox_xyxy_norm,
                        description=(
                            f"Person detected without {required} "
                            f"(COCO fallback — replace with fine-tuned model)"
                        ),
                    )
                )

        return violations


def _ppe_kind_from_violation(violation_kind: str) -> str:
    """'no_helmet' → 'helmet' 처럼 위반 kind에서 PPE 종류를 추출한다."""
    return violation_kind.removeprefix("no_")
