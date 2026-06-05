from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class ModelLoadResult:
    bundle: dict[str, Any]
    source: str
    model_uri: str | None = None
    registered_model_name: str | None = None
    alias: str | None = None
    fallback_used: bool = False
    reasons: list[str] | None = None


def build_registry_model_uri(
    *,
    mlflow_model_uri: str | None,
    registered_model_name: str | None,
    model_alias: str,
) -> str:
    if mlflow_model_uri:
        return mlflow_model_uri

    if not registered_model_name:
        raise ValueError(
            "MLflow registry model source requires --mlflow-model-uri or "
            "--mlflow-registered-model-name."
        )

    return f"models:/{registered_model_name}@{model_alias}"


def load_registry_model_bundle(
    *,
    mlflow_model_uri: str | None,
    registered_model_name: str | None,
    model_alias: str,
    tracking_uri: str | None,
    features: Sequence[str],
    model_name: str,
    model_version: str,
    target_name: str,
    valid_classes: Sequence[str],
) -> ModelLoadResult:
    import mlflow
    import mlflow.sklearn

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)

    model_uri = build_registry_model_uri(
        mlflow_model_uri=mlflow_model_uri,
        registered_model_name=registered_model_name,
        model_alias=model_alias,
    )
    model = mlflow.sklearn.load_model(model_uri)

    if not hasattr(model, "predict"):
        raise TypeError(f"MLflow model does not support predict(): {model_uri}")

    if not hasattr(model, "predict_proba"):
        raise TypeError(f"MLflow model does not support predict_proba(): {model_uri}")

    bundle = {
        "model": model,
        "model_name": model_name,
        "model_version": model_version,
        "target_name": target_name,
        "features": list(features),
        "valid_classes": list(valid_classes),
        "artifact_path": model_uri,
        "mlflow_model_uri": model_uri,
        "registered_model_name": registered_model_name,
        "model_alias": model_alias,
        "model_source": "registry",
    }

    return ModelLoadResult(
        bundle=bundle,
        source="registry",
        model_uri=model_uri,
        registered_model_name=registered_model_name,
        alias=model_alias,
        fallback_used=False,
        reasons=["loaded model from MLflow Registry"],
    )


def _artifact_result(
    artifact_loader: Callable[[], dict[str, Any]],
    *,
    fallback_used: bool = False,
    reasons: list[str] | None = None,
) -> ModelLoadResult:
    bundle = artifact_loader()
    bundle.setdefault("model_source", "artifact")
    return ModelLoadResult(
        bundle=bundle,
        source="artifact",
        model_uri=bundle.get("artifact_path"),
        fallback_used=fallback_used,
        reasons=reasons or ["loaded artifact model"],
    )


def _has_registry_config(
    *,
    mlflow_model_uri: str | None,
    registered_model_name: str | None,
    tracking_uri: str | None,
) -> bool:
    return bool(tracking_uri and (mlflow_model_uri or registered_model_name))


def load_model_with_fallback(
    *,
    model_source: str,
    artifact_loader: Callable[[], dict[str, Any]],
    mlflow_model_uri: str | None,
    registered_model_name: str | None,
    model_alias: str,
    tracking_uri: str | None,
    fallback_to_artifact: bool,
    strict: bool,
    features: Sequence[str],
    model_name: str,
    model_version: str,
    target_name: str,
    valid_classes: Sequence[str],
) -> ModelLoadResult:
    source = model_source.lower()
    if source not in {"artifact", "registry", "auto"}:
        raise ValueError(f"Invalid model_source={model_source}. Use artifact, registry, or auto.")

    if source == "artifact":
        return _artifact_result(artifact_loader)

    if source == "auto" and not _has_registry_config(
        mlflow_model_uri=mlflow_model_uri,
        registered_model_name=registered_model_name,
        tracking_uri=tracking_uri,
    ):
        return _artifact_result(
            artifact_loader,
            reasons=["registry model source not configured; using artifact model"],
        )

    try:
        return load_registry_model_bundle(
            mlflow_model_uri=mlflow_model_uri,
            registered_model_name=registered_model_name,
            model_alias=model_alias,
            tracking_uri=tracking_uri,
            features=features,
            model_name=model_name,
            model_version=model_version,
            target_name=target_name,
            valid_classes=valid_classes,
        )
    except Exception as exc:
        reason = f"registry model load failed: {exc}"
        if strict or not fallback_to_artifact:
            raise RuntimeError(reason) from exc

        return _artifact_result(
            artifact_loader,
            fallback_used=True,
            reasons=[reason, "falling back to artifact model"],
        )
