from __future__ import annotations

from promotion_gate import PromotionGateConfig, evaluate_promotion_gate


def _metrics(
    *,
    validation_f1: float,
    validation_row_count: int = 100,
    test_f1: float | None = 0.60,
    validation_log_loss: float | None = 0.70,
    per_class_recall_min: float | None = 0.20,
    feature_completeness_score: float | None = 1.0,
):
    validation = {
        "f1_macro": validation_f1,
        "row_count": validation_row_count,
    }
    if validation_log_loss is not None:
        validation["log_loss"] = validation_log_loss
    if per_class_recall_min is not None:
        validation["per_class_recall_min"] = per_class_recall_min
    if feature_completeness_score is not None:
        validation["feature_completeness_score"] = feature_completeness_score

    metrics = {"validation": validation}
    if test_f1 is not None:
        metrics["test"] = {"f1_macro": test_f1, "row_count": 80}

    return metrics


def _split_ranges():
    return {
        "train": {
            "start": "2024-01-01T00:00:00+00:00",
            "end": "2024-01-31T23:00:00+00:00",
        },
        "validation": {
            "start": "2024-02-01T00:00:00+00:00",
            "end": "2024-02-07T23:00:00+00:00",
        },
    }


def test_promotion_gate_accepts_better_candidate():
    result = evaluate_promotion_gate(
        candidate_metrics=_metrics(validation_f1=0.63, test_f1=0.61),
        champion_metrics=_metrics(validation_f1=0.60, test_f1=0.60),
        config=PromotionGateConfig(margin=0.02, min_row_count=20),
        split_date_ranges=_split_ranges(),
    )

    assert result.passed is True
    assert result.status == "accepted"
    assert result.candidate_score == 0.63
    assert result.champion_score == 0.60


def test_promotion_gate_rejects_low_f1():
    result = evaluate_promotion_gate(
        candidate_metrics=_metrics(validation_f1=0.61),
        champion_metrics=_metrics(validation_f1=0.60),
        config=PromotionGateConfig(margin=0.02, min_row_count=20),
        split_date_ranges=_split_ranges(),
    )

    assert result.passed is False
    assert result.status == "rejected"
    assert any("validation_f1_macro" in reason for reason in result.reasons)


def test_promotion_gate_rejects_test_degradation():
    result = evaluate_promotion_gate(
        candidate_metrics=_metrics(validation_f1=0.70, test_f1=0.50),
        champion_metrics=_metrics(validation_f1=0.60, test_f1=0.60),
        config=PromotionGateConfig(
            margin=0.01,
            max_test_f1_degradation=0.05,
            min_row_count=20,
        ),
        split_date_ranges=_split_ranges(),
    )

    assert result.passed is False
    assert any("test_f1_macro" in reason for reason in result.reasons)


def test_promotion_gate_handles_missing_optional_metrics():
    result = evaluate_promotion_gate(
        candidate_metrics=_metrics(
            validation_f1=0.70,
            test_f1=None,
            validation_log_loss=None,
            per_class_recall_min=None,
            feature_completeness_score=None,
        ),
        champion_metrics=_metrics(
            validation_f1=0.60,
            test_f1=None,
            validation_log_loss=None,
            per_class_recall_min=None,
            feature_completeness_score=None,
        ),
        config=PromotionGateConfig(margin=0.01, min_row_count=20),
        split_date_ranges=_split_ranges(),
    )

    assert result.passed is True
    assert result.status == "accepted"
    assert any("skipped" in reason for reason in result.reasons)


def test_promotion_gate_no_champion_accept_or_skip_behavior():
    result = evaluate_promotion_gate(
        candidate_metrics=_metrics(validation_f1=0.55),
        champion_metrics=None,
        config=PromotionGateConfig(margin=0.01, min_row_count=20),
        split_date_ranges=_split_ranges(),
    )

    assert result.passed is True
    assert result.status == "accepted"
    assert "no existing champion metrics; accepting best candidate" in result.reasons
