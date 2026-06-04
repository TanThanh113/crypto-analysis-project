from __future__ import annotations

from pathlib import Path

from mlflow_utils import get_mlflow_settings, log_training_run


def test_mlflow_disabled_path_does_not_fail(monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)

    assert get_mlflow_settings().enabled is False
    assert log_training_run(run_name="disabled") is False


def test_mlflow_enabled_logs_to_local_sqlite(monkeypatch, tmp_path):
    tracking_db = tmp_path / "mlflow.db"
    artifact_root = tmp_path / "artifacts"
    sample_artifact = tmp_path / "sample.txt"
    sample_artifact.write_text("artifact", encoding="utf-8")

    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tracking_db}")
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "phase_1_test_experiment")
    monkeypatch.setenv("MLFLOW_ARTIFACT_ROOT", artifact_root.as_uri())

    assert log_training_run(
        run_name="enabled",
        params={"model_name": "crypto_direction"},
        metrics={"validation.f1_macro": 0.42},
        tags={"phase": "phase_1"},
        artifact_paths=[sample_artifact],
    ) is True

    import mlflow

    mlflow.set_tracking_uri(f"sqlite:///{tracking_db}")
    experiment = mlflow.get_experiment_by_name("phase_1_test_experiment")

    assert experiment is not None
    assert experiment.artifact_location == artifact_root.as_uri()


def test_existing_experiment_artifact_location_is_not_mutated(monkeypatch, tmp_path):
    tracking_db = tmp_path / "mlflow.db"
    first_artifact_root = tmp_path / "first_artifacts"
    second_artifact_root = tmp_path / "second_artifacts"

    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tracking_db}")
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "existing_experiment")
    monkeypatch.setenv("MLFLOW_ARTIFACT_ROOT", first_artifact_root.as_uri())

    assert log_training_run(run_name="first") is True

    monkeypatch.setenv("MLFLOW_ARTIFACT_ROOT", second_artifact_root.as_uri())
    assert log_training_run(run_name="second") is True

    import mlflow

    mlflow.set_tracking_uri(f"sqlite:///{tracking_db}")
    experiment = mlflow.get_experiment_by_name("existing_experiment")

    assert experiment is not None
    assert experiment.artifact_location == first_artifact_root.as_uri()


def test_mlflow_error_is_swallowed_by_default(monkeypatch, tmp_path):
    tracking_db = tmp_path / "mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tracking_db}")
    monkeypatch.setenv("MLFLOW_FAIL_ON_ERROR", "false")

    import mlflow

    def raise_error(_uri):
        raise RuntimeError("boom")

    monkeypatch.setattr(mlflow, "set_tracking_uri", raise_error)

    assert log_training_run(run_name="error") is False
