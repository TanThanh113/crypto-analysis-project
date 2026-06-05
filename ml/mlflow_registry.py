from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass
from typing import Any, Mapping


TRUE_VALUES = {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class MLflowRegistrySettings:
    enabled: bool
    tracking_uri: str | None
    experiment_name: str
    artifact_root: str | None
    update_alias: bool
    registered_model_name: str | None
    model_alias: str
    fail_on_error: bool


@dataclass(frozen=True)
class MLflowRegistryResult:
    status: str
    registered_model_name: str | None = None
    model_version: str | None = None
    model_alias: str | None = None
    model_uri: str | None = None
    run_id: str | None = None
    reasons: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons or [])
        return payload


def get_registry_settings(
    *,
    default_registered_model_name: str | None = None,
    env: Mapping[str, str] | None = None,
) -> MLflowRegistrySettings:
    source = os.environ if env is None else env
    enabled = source.get("MLFLOW_ENABLE_MODEL_REGISTRY", "").strip().lower() in TRUE_VALUES
    update_alias = source.get("MLFLOW_UPDATE_MODEL_ALIAS", "").strip().lower() in TRUE_VALUES
    fail_on_error = source.get("MLFLOW_REGISTRY_FAIL_ON_ERROR", "").strip().lower() in TRUE_VALUES

    return MLflowRegistrySettings(
        enabled=enabled,
        tracking_uri=source.get("MLFLOW_TRACKING_URI"),
        experiment_name=source.get("MLFLOW_EXPERIMENT_NAME", "crypto_direction_4h"),
        artifact_root=source.get("MLFLOW_ARTIFACT_ROOT"),
        update_alias=update_alias,
        registered_model_name=(
            source.get("MLFLOW_REGISTERED_MODEL_NAME")
            or default_registered_model_name
        ),
        model_alias=source.get("MLFLOW_MODEL_ALIAS", "champion"),
        fail_on_error=fail_on_error,
    )


def _clean_tag_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _clean_tags(tags: Mapping[str, Any] | None) -> dict[str, str]:
    if not tags:
        return {}

    return {
        str(key): _clean_tag_value(value)
        for key, value in tags.items()
        if value is not None
    }


def _handle_registry_error(
    message: str,
    exc: Exception,
    settings: MLflowRegistrySettings,
) -> MLflowRegistryResult:
    if settings.fail_on_error:
        raise exc

    print(f"[registry][WARN] {message}: {exc}", file=sys.stderr)
    return MLflowRegistryResult(
        status="error",
        registered_model_name=settings.registered_model_name,
        model_alias=settings.model_alias,
        reasons=[f"{message}: {exc}"],
    )


def _get_or_create_experiment_id(mlflow: Any, settings: MLflowRegistrySettings) -> str:
    experiment = mlflow.get_experiment_by_name(settings.experiment_name)
    if experiment is not None:
        return experiment.experiment_id

    if settings.artifact_root:
        return mlflow.create_experiment(
            settings.experiment_name,
            artifact_location=settings.artifact_root,
        )

    return mlflow.create_experiment(settings.experiment_name)


def _promotion_is_accepted(promotion_result: Any) -> bool:
    if promotion_result is None:
        return False

    if isinstance(promotion_result, Mapping):
        return bool(promotion_result.get("passed")) or promotion_result.get("status") == "accepted"

    return bool(getattr(promotion_result, "passed", False)) or getattr(
        promotion_result,
        "status",
        None,
    ) == "accepted"


def register_model_if_enabled(
    *,
    model: Any,
    run_name: str,
    default_registered_model_name: str,
    promotion_result: Any,
    tags: Mapping[str, Any] | None = None,
    settings: MLflowRegistrySettings | None = None,
) -> MLflowRegistryResult:
    active_settings = settings or get_registry_settings(
        default_registered_model_name=default_registered_model_name
    )

    if not active_settings.enabled:
        return MLflowRegistryResult(
            status="disabled",
            registered_model_name=active_settings.registered_model_name,
            model_alias=active_settings.model_alias,
            reasons=["MLFLOW_ENABLE_MODEL_REGISTRY is not true"],
        )

    if not active_settings.tracking_uri:
        return MLflowRegistryResult(
            status="skipped",
            registered_model_name=active_settings.registered_model_name,
            model_alias=active_settings.model_alias,
            reasons=["MLFLOW_TRACKING_URI is required for MLflow Model Registry"],
        )

    if not active_settings.registered_model_name:
        return MLflowRegistryResult(
            status="skipped",
            model_alias=active_settings.model_alias,
            reasons=["registered model name is missing"],
        )

    if not _promotion_is_accepted(promotion_result):
        return MLflowRegistryResult(
            status="skipped",
            registered_model_name=active_settings.registered_model_name,
            model_alias=active_settings.model_alias,
            reasons=["promotion gate is not accepted; skipping registry update"],
        )

    try:
        import mlflow
        import mlflow.sklearn
        from mlflow.exceptions import MlflowException
        from mlflow.tracking import MlflowClient

        mlflow.set_tracking_uri(active_settings.tracking_uri)
        experiment_id = _get_or_create_experiment_id(mlflow, active_settings)
        cleaned_tags = _clean_tags(tags)

        with mlflow.start_run(experiment_id=experiment_id, run_name=run_name) as run:
            if cleaned_tags:
                mlflow.set_tags(cleaned_tags)

            try:
                model_info = mlflow.sklearn.log_model(model, name="model")
            except TypeError:
                model_info = mlflow.sklearn.log_model(model, artifact_path="model")

            run_id = run.info.run_id
            model_uri = getattr(model_info, "model_uri", None) or f"runs:/{run_id}/model"

        client = MlflowClient(tracking_uri=active_settings.tracking_uri)
        try:
            client.create_registered_model(active_settings.registered_model_name)
        except MlflowException as exc:
            if "already exists" not in str(exc).lower():
                raise

        model_version = mlflow.register_model(
            model_uri,
            active_settings.registered_model_name,
        )

        for key, value in cleaned_tags.items():
            client.set_model_version_tag(
                active_settings.registered_model_name,
                model_version.version,
                key,
                value,
            )

        client.set_registered_model_tag(
            active_settings.registered_model_name,
            "created_by",
            "crypto-analysis-project",
        )
        client.set_registered_model_tag(
            active_settings.registered_model_name,
            "phase",
            "mlflow_mlops_upgrade",
        )

        reasons = ["registered model version"]
        alias = None
        if active_settings.update_alias:
            client.set_registered_model_alias(
                active_settings.registered_model_name,
                active_settings.model_alias,
                model_version.version,
            )
            alias = active_settings.model_alias
            reasons.append(f"updated alias {active_settings.model_alias}")
        else:
            reasons.append("MLFLOW_UPDATE_MODEL_ALIAS is not true; alias not updated")

        return MLflowRegistryResult(
            status="registered",
            registered_model_name=active_settings.registered_model_name,
            model_version=str(model_version.version),
            model_alias=alias,
            model_uri=model_uri,
            run_id=run_id,
            reasons=reasons,
        )

    except Exception as exc:
        return _handle_registry_error(
            "MLflow Model Registry update skipped",
            exc,
            active_settings,
        )
