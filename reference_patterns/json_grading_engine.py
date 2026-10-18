### reference_patterns/json_grading_engine.py`
```python
"""
Reference Pattern: Dynamic Tenant Assessment & Grading Engine
Demonstrates how EduSleek validates and computes custom per-school grading
blueprints stored in PostgreSQL JSONB fields without requiring schema migrations.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, TypedDict, Optional
from django.core.exceptions import ValidationError


class ComponentRule(TypedDict):
    key: str          # e.g., "ca1", "ca2", "project", "exam"
    label: str        # e.g., "First Continuous Assessment"
    max_score: float  # e.g., 15.0


class GradeBoundary(TypedDict):
    min_score: float
    max_score: float
    grade: str        # e.g., "A", "B", "C"
    remark: str       # e.g., "Excellent", "Very Good"


class TenantGradingBlueprintEvaluator:
    """
    Evaluates a student's raw assessment scores against a school's custom
    JSON grading blueprint and returns normalized totals and grade metadata.
    """

    def __init__(self, components: List[ComponentRule], boundaries: List[GradeBoundary]):
        self.components = {comp["key"]: comp for comp in components}
        self.boundaries = sorted(boundaries, key=lambda b: b["min_score"], reverse=True)
        self._validate_blueprint_integrity()

    def _validate_blueprint_integrity(self) -> None:
        total_weight = sum(Decimal(str(c["max_score"])) for c in self.components.values())
        if total_weight != Decimal("100.00"):
            raise ValidationError(
                f"Invalid tenant blueprint: component max scores must sum to 100 (got {total_weight})."
            )

    def evaluate_student_scores(self, raw_scores: Dict[str, float]) -> Dict[str, object]:
        """
        Validates individual component scores and calculates total and grade.
        """
        total = Decimal("0.00")
        validated_breakdown: Dict[str, float] = {}

        for key, rule in self.components.items():
            score = Decimal(str(raw_scores.get(key, 0.0)))
            max_allowed = Decimal(str(rule["max_score"]))

            if score < Decimal("0.00") or score > max_allowed:
                raise ValidationError(
                    f"Score {score} for '{rule['label']}' exceeds allowed range (0 - {max_allowed})."
                )

            validated_breakdown[key] = float(score)
            total += score

        rounded_total = float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        grade_meta = self._resolve_grade(rounded_total)

        return {
            "breakdown": validated_breakdown,
            "total_score": rounded_total,
            "grade": grade_meta["grade"],
            "remark": grade_meta["remark"],
        }

    def _resolve_grade(self, total_score: float) -> Dict[str, str]:
        for boundary in self.boundaries:
            if boundary["min_score"] <= total_score <= boundary["max_score"]:
                return {"grade": boundary["grade"], "remark": boundary["remark"]}
        return {"grade": "F", "remark": "Needs Improvement"}
