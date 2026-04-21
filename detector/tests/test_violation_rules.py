"""violation_rules.py의 순수 로직을 검증한다. 외부 의존성 없음."""
from __future__ import annotations

import pytest

from src.inference import Detection
from src.violation_rules import ViolationRules


def _det(label: str, conf: float = 0.8) -> Detection:
    return Detection(label=label, confidence=conf, bbox_xyxy_norm=(0.1, 0.1, 0.5, 0.9))


class TestCaseA_DirectViolationLabels:
    """PPE fine-tuned 모델이 no_helmet 같은 직접 위반 클래스를 반환하는 경우."""

    def test_no_helmet_detected(self) -> None:
        rules = ViolationRules(required_ppe=["helmet"])
        violations = rules.evaluate([_det("no_helmet", conf=0.9)])
        assert len(violations) == 1
        assert violations[0].kind == "no_helmet"
        assert violations[0].confidence == pytest.approx(0.9)

    def test_no_vest_detected(self) -> None:
        rules = ViolationRules(required_ppe=["helmet", "vest"])
        violations = rules.evaluate([_det("no_vest", conf=0.75)])
        assert len(violations) == 1
        assert violations[0].kind == "no_vest"

    def test_violation_not_in_required_ppe_ignored(self) -> None:
        """required에 없는 PPE 위반은 무시한다."""
        rules = ViolationRules(required_ppe=["helmet"])  # vest는 required 아님
        violations = rules.evaluate([_det("no_vest")])
        assert violations == []


class TestCaseB_CocoFallback:
    """COCO pretrained weights 사용 시 person이 있고 PPE 클래스가 없으면 위반."""

    def test_person_without_helmet_triggers_violation(self) -> None:
        rules = ViolationRules(required_ppe=["helmet"])
        violations = rules.evaluate([_det("person")])
        assert len(violations) == 1
        assert violations[0].kind == "no_helmet"

    def test_person_with_helmet_no_violation(self) -> None:
        rules = ViolationRules(required_ppe=["helmet"])
        violations = rules.evaluate([_det("person"), _det("helmet")])
        assert violations == []

    def test_person_missing_multiple_ppe(self) -> None:
        rules = ViolationRules(required_ppe=["helmet", "vest"])
        violations = rules.evaluate([_det("person")])
        kinds = {v.kind for v in violations}
        assert kinds == {"no_helmet", "no_vest"}

    def test_no_person_no_violation(self) -> None:
        """사람이 없으면 PPE가 없어도 위반이 아니다."""
        rules = ViolationRules(required_ppe=["helmet"])
        violations = rules.evaluate([_det("car"), _det("truck")])
        assert violations == []

    def test_empty_detections(self) -> None:
        rules = ViolationRules(required_ppe=["helmet"])
        assert rules.evaluate([]) == []
