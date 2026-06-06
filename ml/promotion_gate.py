from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class PromotionGateConfig:
    margin: float = 0.0
    max_test_f1_degradation: float = 0.05
    max_log_loss_degradation: float = 0.10
    min_row_count: int = 20
    min_per_class_recall: float = 0.0
    min_feature_completeness_score: float = 0.0


@dataclass(frozen=True)
class PromotionGateResult:
    passed: bool
    status: str
    reasons: list[str]
    candidate_score: float | None
    champion_score: float | None
    margin: float
    checked_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_metrics(metrics: Mapping[str, Any] | None, split_name: str) -> Mapping[str, Any]:
    if not metrics:
        return {}

    split = metrics.get(split_name)
    if isinstance(split, Mapping):
        return split

    return metrics


def _metric(
    metrics: Mapping[str, Any] | None,
    split_name: str,
    metric_name: str,
) -> float | None:
    split = _split_metrics(metrics, split_name)
    value = split.get(metric_name)

    if value is None:
        return None

    try:
        metric_value = float(value)
    except (TypeError, ValueError):
        return None

    if metric_value != metric_value:
        return None

    return metric_value


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _check_time_leakage(
    split_date_ranges: Mapping[str, Any] | None,
    reasons: list[str],
) -> None:
    if not split_date_ranges:
        reasons.append("split date ranges missing; skipped time leakage check")
        return

    train = split_date_ranges.get("train", {})
    validation = split_date_ranges.get("validation", {})

    train_end = _timestamp(train.get("end") if isinstance(train, Mapping) else None)
    validation_start = _timestamp(
        validation.get("start") if isinstance(validation, Mapping) else None
    )
    validation_end = _timestamp(
        validation.get("end") if isinstance(validation, Mapping) else None
    )

    if train_end is None or validation_start is None or validation_end is None:
        reasons.append("split date ranges incomplete; skipped time leakage check")
        return

    if train_end >= validation_start:
        reasons.append(
            "time leakage detected: train_end must be before validation_start "
            f"({train_end.isoformat()} >= {validation_start.isoformat()})"
        )
        return

    if validation_start > validation_end:
        reasons.append("invalid validation date range")


def evaluate_promotion_gate(
    *,
    candidate_metrics: Mapping[str, Any],
    champion_metrics: Mapping[str, Any] | None = None,
    config: PromotionGateConfig | None = None,
    split_date_ranges: Mapping[str, Any] | None = None,
) -> PromotionGateResult:
    gate_config = config or PromotionGateConfig()
    reasons: list[str] = []

    candidate_score = _metric(candidate_metrics, "validation", "f1_macro")
    champion_score = _metric(champion_metrics, "validation", "f1_macro")

    if candidate_score is None:
        reasons.append("candidate validation_f1_macro is missing")

    row_count = _metric(candidate_metrics, "validation", "row_count")
    if row_count is None:
        reasons.append("candidate validation row_count is missing")
    elif row_count < gate_config.min_row_count:
        reasons.append(
            f"candidate validation row_count {int(row_count)} is below minimum "
            f"{gate_config.min_row_count}"
        )

    per_class_recall = _metric(candidate_metrics, "validation", "per_class_recall_min")
    if per_class_recall is None:
        reasons.append("per_class_recall_min missing; skipped recall threshold check")
    elif per_class_recall < gate_config.min_per_class_recall:
        reasons.append(
            f"candidate per_class_recall_min {per_class_recall:.6f} is below "
            f"threshold {gate_config.min_per_class_recall:.6f}"
        )

    completeness = _metric(
        candidate_metrics,
        "validation",
        "feature_completeness_score",
    )
    if completeness is None:
        reasons.append(
            "feature_completeness_score missing; skipped feature completeness check"
        )
    elif completeness < gate_config.min_feature_completeness_score:
        reasons.append(
            f"candidate feature_completeness_score {completeness:.6f} is below "
            f"threshold {gate_config.min_feature_completeness_score:.6f}"
        )

    _check_time_leakage(split_date_ranges, reasons)

    blocking_reasons = [
        reason
        for reason in reasons
        if "missing; skipped" not in reason
        and "skipped time leakage check" not in reason
    ]

    if champion_metrics:
        if champion_score is None:
            reasons.append("champion validation_f1_macro is missing; skipped champion comparison")
        elif candidate_score is not None:
            required_score = champion_score + gate_config.margin
            if candidate_score < required_score:
                blocking_reasons.append(
                    f"candidate validation_f1_macro {candidate_score:.6f} is below "
                    f"champion + margin {required_score:.6f}"
                )

        candidate_test_f1 = _metric(candidate_metrics, "test", "f1_macro")
        champion_test_f1 = _metric(champion_metrics, "test", "f1_macro")
        if candidate_test_f1 is None or champion_test_f1 is None:
            reasons.append("test_f1_macro missing; skipped test degradation check")
        else:
            min_allowed_test_f1 = champion_test_f1 - gate_config.max_test_f1_degradation
            if candidate_test_f1 < min_allowed_test_f1:
                blocking_reasons.append(
                    f"candidate test_f1_macro {candidate_test_f1:.6f} degrades more than "
                    f"allowed threshold {gate_config.max_test_f1_degradation:.6f}"
                )

        candidate_log_loss = _metric(candidate_metrics, "validation", "log_loss")
        champion_log_loss = _metric(champion_metrics, "validation", "log_loss")
        if candidate_log_loss is None or champion_log_loss is None:
            reasons.append("validation log_loss missing; skipped log_loss degradation check")
        else:
            max_allowed_log_loss = champion_log_loss + gate_config.max_log_loss_degradation
            if candidate_log_loss > max_allowed_log_loss:
                blocking_reasons.append(
                    f"candidate validation log_loss {candidate_log_loss:.6f} is worse than "
                    f"allowed threshold {max_allowed_log_loss:.6f}"
                )
    else:
        reasons.append("no existing champion metrics; accepting best candidate")

    reasons.extend(reason for reason in blocking_reasons if reason not in reasons)
    passed = not blocking_reasons

    return PromotionGateResult(
        passed=passed,
        status="accepted" if passed else "rejected",
        reasons=reasons,
        candidate_score=candidate_score,
        champion_score=champion_score,
        margin=gate_config.margin,
        checked_at=utc_now_iso(),
    )
