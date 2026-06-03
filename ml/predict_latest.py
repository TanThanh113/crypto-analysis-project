#!/usr/bin/env python3
"""
Run latest crypto direction inference.

This script:
1. Reads feature contract from feature_list.yml
2. Reads latest inference rows from mart_ml_prediction_input_latest
3. Loads latest model artifact from artifacts/latest_model.json
4. Generates UP / DOWN / FLAT prediction
5. Writes predictions to BigQuery ml_outputs.model_predictions

Important:
- Output schema matches Terraform table: ml_outputs.model_predictions
- model_name/model_version must match dim_ml_model_registry
- train_model.py and predict_latest.py must use the same feature_list.yml
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import joblib
import numpy as np
import pandas as pd
import yaml
from google.cloud import bigquery, storage


@dataclass(frozen=True)
class BigQueryConfig:
    project_id: str
    analytics_dataset: str
    ml_outputs_dataset: str
    prediction_input_table: str
    predictions_table: str

    @property
    def prediction_input_table_fqn(self) -> str:
        return (
            f"{self.project_id}."
            f"{self.analytics_dataset}."
            f"{self.prediction_input_table}"
        )

    @property
    def predictions_table_fqn(self) -> str:
        return (
            f"{self.project_id}."
            f"{self.ml_outputs_dataset}."
            f"{self.predictions_table}"
        )


@dataclass(frozen=True)
class ModelConfig:
    model_name: str
    model_version: str
    target_name: str
    valid_classes: List[str]
    categorical_features: List[str]
    numeric_features: List[str]

    @property
    def all_features(self) -> List[str]:
        return self.categorical_features + self.numeric_features


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def is_gcs_uri(uri: Optional[str]) -> bool:
    return bool(uri and uri.startswith("gs://"))


def parse_gcs_uri(uri: str) -> tuple[str, str]:
    if not is_gcs_uri(uri):
        raise ValueError(f"Invalid GCS URI: {uri}")

    parsed = urlparse(uri)
    bucket = parsed.netloc
    blob = parsed.path.lstrip("/")

    if not bucket or not blob:
        raise ValueError(f"Invalid GCS URI: {uri}")

    return bucket, blob


def join_gcs_uri(root_uri: str, filename: str) -> str:
    if not is_gcs_uri(root_uri):
        raise ValueError(f"Invalid GCS root URI: {root_uri}")

    return root_uri.rstrip("/") + "/" + filename.lstrip("/")


def gcs_filename(uri: str) -> str:
    _, blob_name = parse_gcs_uri(uri)
    return Path(blob_name).name


def download_file_from_gcs(source_uri: str, local_path: Path) -> Path:
    bucket_name, blob_name = parse_gcs_uri(source_uri)

    local_path.parent.mkdir(parents=True, exist_ok=True)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    blob.download_to_filename(str(local_path))

    print(f"[artifact] Downloaded {source_uri} -> {local_path}")
    return local_path

def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML config: {path}")

    return data


def build_configs(config: Dict[str, Any]) -> Tuple[BigQueryConfig, ModelConfig]:
    bq = config.get("bigquery", {})
    model = config.get("model", {})

    project_env = bq.get("project_id_env", "GCP_PROJECT_ID")
    analytics_env = bq.get("analytics_dataset_env", "BQ_ANALYTICS_DATASET")
    outputs_env = bq.get("ml_outputs_dataset_env", "BQ_ML_OUTPUTS_DATASET")

    project_id = os.environ.get(project_env)
    if not project_id:
        raise ValueError(f"Missing required environment variable: {project_env}")

    bq_config = BigQueryConfig(
        project_id=project_id,
        analytics_dataset=os.environ.get(
            analytics_env,
            bq.get("default_analytics_dataset", "dbt_quants_dev"),
        ),
        ml_outputs_dataset=os.environ.get(
            outputs_env,
            bq.get("default_ml_outputs_dataset", "ml_outputs"),
        ),
        prediction_input_table=bq.get(
            "prediction_input_table",
            "mart_ml_prediction_input_latest",
        ),
        predictions_table=bq.get("predictions_table", "model_predictions"),
    )

    model_config = ModelConfig(
        model_name=model.get("model_name", "crypto_direction_lgbm_v1"),
        model_version=model.get("model_version", "v1"),
        target_name=model.get("target_name", "future_direction_4h"),
        valid_classes=list(model.get("valid_classes", ["UP", "DOWN", "FLAT"])),
        categorical_features=list(model.get("categorical_features", ["symbol"])),
        numeric_features=list(model.get("numeric_features", [])),
    )

    if not model_config.numeric_features:
        raise ValueError("feature_list.yml must contain model.numeric_features")

    return bq_config, model_config


def load_latest_artifact(
    artifact_dir: Path,
    artifact_path: Optional[str],
    artifact_storage: str,
    artifact_gcs_uri: Optional[str],
    latest_manifest_name: str = "latest_model.json",
) -> Dict[str, Any]:
    artifact_dir.mkdir(parents=True, exist_ok=True)

    artifact_storage = artifact_storage.lower()

    if artifact_path:
        if is_gcs_uri(artifact_path):
            local_path = artifact_dir / gcs_filename(artifact_path)
            download_file_from_gcs(artifact_path, local_path)
            bundle = joblib.load(local_path)
            bundle["artifact_path"] = artifact_path
            bundle["local_artifact_path"] = str(local_path)
            return bundle

        path = Path(artifact_path).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found: {path}")

        bundle = joblib.load(path)
        bundle["artifact_path"] = str(path)
        bundle["local_artifact_path"] = str(path)
        return bundle

    if artifact_storage == "gcs":
        if not artifact_gcs_uri:
            raise ValueError(
                "--artifact-gcs-uri is required when --artifact-storage is 'gcs'."
            )

        manifest_uri = join_gcs_uri(artifact_gcs_uri, latest_manifest_name)
        manifest_path = artifact_dir / latest_manifest_name

        download_file_from_gcs(manifest_uri, manifest_path)

        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)

        model_gcs_uri = (
            manifest.get("artifact_gcs_uri")
            or manifest.get("artifact_uri")
            or manifest.get("artifact_path")
        )

        if not is_gcs_uri(model_gcs_uri):
            raise ValueError(
                "GCS artifact manifest does not contain a valid artifact_gcs_uri/artifact_uri."
            )

        local_model_path = artifact_dir / gcs_filename(model_gcs_uri)
        download_file_from_gcs(model_gcs_uri, local_model_path)

        bundle = joblib.load(local_model_path)
        bundle["artifact_path"] = model_gcs_uri
        bundle["local_artifact_path"] = str(local_model_path)
        return bundle

    manifest_path = artifact_dir / latest_manifest_name

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"{latest_manifest_name} not found in {artifact_dir}. "
            "Run train_model.py first or pass --artifact-path."
        )

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    path_from_manifest = (
        manifest.get("artifact_path")
        or manifest.get("local_artifact_path")
    )

    if not path_from_manifest:
        raise ValueError("latest_model.json does not contain artifact_path.")

    path = Path(path_from_manifest).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {path}")

    bundle = joblib.load(path)
    bundle["artifact_path"] = str(path)
    bundle["local_artifact_path"] = str(path)

    return bundle


def check_bigquery_table_exists(
    client: bigquery.Client,
    table_fqn: str,
) -> None:
    try:
        client.get_table(table_fqn)
    except Exception as exc:
        raise RuntimeError(
            f"BigQuery table not found or inaccessible: {table_fqn}. "
            "Make sure Terraform created it and your service account has access."
        ) from exc


def query_prediction_input(
    client: bigquery.Client,
    bq_config: BigQueryConfig,
    model_config: ModelConfig,
) -> pd.DataFrame:
    columns = [
        "hour_ts",
        "feature_available_at",
        "symbol",
        "pair_symbol",
    ] + model_config.all_features

    columns = list(dict.fromkeys(columns))
    select_expr = ",\n        ".join([f"`{column}`" for column in columns])

    query = f"""
    SELECT
        {select_expr}
    FROM `{bq_config.prediction_input_table_fqn}`
    WHERE symbol IN ('BTC', 'ETH')
      AND hour_ts IS NOT NULL
      AND feature_available_at IS NOT NULL
    """

    return client.query(query).to_dataframe()


def validate_prediction_input(
    df: pd.DataFrame,
    model_config: ModelConfig,
) -> None:
    required_columns = set(
        ["hour_ts", "symbol", "feature_available_at"] + model_config.all_features
    )

    missing_columns = sorted(required_columns - set(df.columns))

    if missing_columns:
        raise ValueError(
            f"Prediction input is missing required columns: {missing_columns}"
        )

    if df.empty:
        raise ValueError(
            "Prediction input returned 0 rows. "
            "Check mart_ml_prediction_input_latest and streaming/core data."
        )


def clean_prediction_features(
    df: pd.DataFrame,
    model_config: ModelConfig,
) -> pd.DataFrame:
    cleaned = df.copy()

    for column in model_config.numeric_features:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    for column in model_config.categorical_features:
        cleaned[column] = (
            cleaned[column]
            .astype("string")
            .fillna("UNKNOWN")
            .str.upper()
        )

    return cleaned


def get_model_classes(bundle: Dict[str, Any]) -> List[str]:
    model = bundle["model"]

    try:
        classes = list(model.named_steps["model"].classes_)
    except Exception:
        classes = list(bundle.get("classes", []))

    return [str(label).upper() for label in classes]


def class_probability(
    proba: Optional[np.ndarray],
    classes: List[str],
    class_name: str,
    row_idx: int,
) -> Optional[float]:
    if proba is None:
        return None

    class_name = class_name.upper()

    if class_name not in classes:
        return None

    return float(proba[row_idx, classes.index(class_name)])


def signal_from_class(
    predicted_class: str,
    confidence_0_to_1: float,
) -> str:
    predicted_class = predicted_class.upper()

    if predicted_class == "UP":
        return "BULLISH" if confidence_0_to_1 >= 0.60 else "WEAK_BULLISH"

    if predicted_class == "DOWN":
        return "BEARISH" if confidence_0_to_1 >= 0.60 else "WEAK_BEARISH"

    if predicted_class == "FLAT":
        return "NEUTRAL"

    return "UNKNOWN"


def validate_artifact_matches_config(
    bundle: Dict[str, Any],
    model_config: ModelConfig,
) -> None:
    bundle_model_name = bundle.get("model_name")
    bundle_model_version = bundle.get("model_version")
    bundle_target = bundle.get("target_name")

    if bundle_model_name and bundle_model_name != model_config.model_name:
        raise ValueError(
            f"Artifact model_name={bundle_model_name} does not match "
            f"config model_name={model_config.model_name}"
        )

    if bundle_model_version and bundle_model_version != model_config.model_version:
        raise ValueError(
            f"Artifact model_version={bundle_model_version} does not match "
            f"config model_version={model_config.model_version}"
        )

    if bundle_target and bundle_target != model_config.target_name:
        raise ValueError(
            f"Artifact target_name={bundle_target} does not match "
            f"config target_name={model_config.target_name}"
        )


def make_predictions(
    df: pd.DataFrame,
    bundle: Dict[str, Any],
    model_config: ModelConfig,
) -> pd.DataFrame:
    validate_artifact_matches_config(bundle, model_config)

    model = bundle["model"]
    model_features = list(bundle.get("features") or model_config.all_features)

    missing_features = sorted(set(model_features) - set(df.columns))
    if missing_features:
        raise ValueError(
            f"Prediction input is missing model artifact features: {missing_features}"
        )

    x = df[model_features].copy()

    predicted = model.predict(x)
    proba = model.predict_proba(x) if hasattr(model, "predict_proba") else None
    classes = get_model_classes(bundle)

    predicted_at = utc_now()
    rows: List[Dict[str, Any]] = []

    for i, row in df.reset_index(drop=True).iterrows():
        predicted_class = str(predicted[i]).upper()

        prob_up = class_probability(proba, classes, "UP", i)
        prob_down = class_probability(proba, classes, "DOWN", i)
        prob_flat = class_probability(proba, classes, "FLAT", i)

        probability_values = [
            p for p in [prob_up, prob_down, prob_flat]
            if p is not None and not pd.isna(p)
        ]

        confidence_0_to_1 = (
            float(max(probability_values))
            if probability_values
            else 0.0
        )

        rows.append(
            {
                "prediction_id": str(uuid.uuid4()),
                "model_name": model_config.model_name,
                "model_version": model_config.model_version,
                "predicted_at": predicted_at,
                "hour_ts": pd.to_datetime(row["hour_ts"]).to_pydatetime(),
                "symbol": str(row["symbol"]).upper(),
                "target_name": model_config.target_name,
                "predicted_class": predicted_class,
                "prob_up": prob_up,
                "prob_down": prob_down,
                "prob_flat": prob_flat,
                "predicted_return_4h": None,
                "confidence_score": confidence_0_to_1 * 100.0,
                "signal": signal_from_class(
                    predicted_class,
                    confidence_0_to_1,
                ),
                "model_artifact_uri": bundle.get("artifact_path"),
                "feature_available_at": pd.to_datetime(
                    row["feature_available_at"]
                ).to_pydatetime(),
            }
        )

    output_columns = [
        "prediction_id",
        "model_name",
        "model_version",
        "predicted_at",
        "hour_ts",
        "symbol",
        "target_name",
        "predicted_class",
        "prob_up",
        "prob_down",
        "prob_flat",
        "predicted_return_4h",
        "confidence_score",
        "signal",
        "model_artifact_uri",
        "feature_available_at",
    ]

    return pd.DataFrame(rows)[output_columns]


def write_predictions(
    client: bigquery.Client,
    bq_config: BigQueryConfig,
    predictions: pd.DataFrame,
) -> None:
    check_bigquery_table_exists(client, bq_config.predictions_table_fqn)

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
    )

    client.load_table_from_dataframe(
        predictions,
        bq_config.predictions_table_fqn,
        job_config=job_config,
    ).result()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predict latest crypto 4H direction."
    )

    parser.add_argument(
        "--config",
        default="feature_list.yml",
        help="Path to feature_list.yml",
    )

    parser.add_argument(
        "--artifact-dir",
        default="artifacts",
        help="Local artifact directory containing latest_model.json",
    )

    parser.add_argument(
        "--artifact-path",
        default=None,
        help="Specific model artifact path. Overrides latest_model.json.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print predictions but do not write to BigQuery.",
    )

    parser.add_argument(
        "--artifact-storage",
        choices=["local", "gcs"],
        default=os.environ.get("ML_ARTIFACT_STORAGE"),
        help=(
            "Where to load model artifacts from. "
            "'local' uses local latest_model.json, 'gcs' downloads latest_model.json and model artifact from GCS."
        ),
    )

    parser.add_argument(
        "--artifact-gcs-uri",
        default=os.environ.get("ML_ARTIFACT_GCS_URI"),
        help=(
            "GCS folder containing latest_model.json and model artifacts, for example "
            "gs://your-bucket/ml-artifacts/crypto_direction_lgbm_v1"
        ),
    )

    return parser.parse_args()

def read_env_with_legacy(primary_env: str, legacy_env: Optional[str] = None) -> Optional[str]:
    primary_value = os.environ.get(primary_env)
    if primary_value:
        return primary_value

    if legacy_env:
        legacy_value = os.environ.get(legacy_env)
        if legacy_value:
            logging.warning("%s is deprecated; use %s instead.", legacy_env, primary_env)
            return legacy_value

    return None


def resolve_artifact_gcs_uri(config: Dict[str, Any], cli_artifact_gcs_uri: Optional[str]) -> Optional[str]:
    if cli_artifact_gcs_uri:
        return cli_artifact_gcs_uri

    artifact = config.get("artifact", {})
    explicit_uri = artifact.get("gcs_uri") or artifact.get("artifact_gcs_uri")
    if explicit_uri:
        return explicit_uri

    bucket_env = artifact.get("gcs_bucket_env", "GCS_BUCKET_NAME")
    legacy_bucket_env = artifact.get("legacy_gcs_bucket_env", "GCP_BUCKET_NAME")
    bucket_name = read_env_with_legacy(bucket_env, legacy_bucket_env)
    gcs_prefix = artifact.get("gcs_prefix")

    if bucket_name and gcs_prefix:
        return f"gs://{bucket_name}/{str(gcs_prefix).strip('/')}"

    return None


def resolve_artifact_storage(
    config: Dict[str, Any],
    cli_artifact_storage: Optional[str],
    default: str,
) -> str:
    if cli_artifact_storage:
        return cli_artifact_storage.lower()

    artifact = config.get("artifact", {})
    return str(artifact.get("storage_mode", default)).lower()

def resolve_latest_manifest_name(config: Dict[str, Any]) -> str:
    artifact = config.get("artifact", {})
    return str(artifact.get("latest_manifest_name", "latest_model.json"))

def main() -> int:
    args = parse_args()

    config_path = Path(args.config).resolve()
    artifact_dir = Path(args.artifact_dir).resolve()

    config = load_yaml(config_path)

    latest_manifest_name = resolve_latest_manifest_name(config)

    artifact_storage = resolve_artifact_storage(
        config=config,
        cli_artifact_storage=args.artifact_storage,
        default="local",
    )

    artifact_gcs_uri = resolve_artifact_gcs_uri(
        config=config,
        cli_artifact_gcs_uri=args.artifact_gcs_uri,
    )

    if artifact_storage not in ("local", "gcs"):
        raise ValueError(
            f"Invalid artifact storage mode for prediction: {artifact_storage}. "
            "Use local or gcs."
        )

    if artifact_storage == "gcs" and not artifact_gcs_uri:
        raise ValueError(
            "GCS artifact storage is enabled, but no GCS URI was provided. "
            "Set --artifact-gcs-uri, ML_ARTIFACT_GCS_URI, or artifact.gcs_bucket_env + artifact.gcs_prefix."
        )
    
    bq_config, model_config = build_configs(config)

    client = bigquery.Client(project=bq_config.project_id)

    print(f"[predict] Project: {bq_config.project_id}")
    print(f"[predict] Prediction input: {bq_config.prediction_input_table_fqn}")
    print(f"[predict] Prediction output: {bq_config.predictions_table_fqn}")
    print(f"[predict] Model config: {model_config.model_name}:{model_config.model_version}")

    print(f"[predict] Loading model artifact from: {artifact_dir}")
    bundle = load_latest_artifact(
        artifact_dir=artifact_dir,
        artifact_path=args.artifact_path,
        artifact_storage=artifact_storage,
        artifact_gcs_uri=artifact_gcs_uri,
        latest_manifest_name=latest_manifest_name,
    )

    print(
        "[predict] Loaded artifact: "
        f"{bundle.get('model_name')}:{bundle.get('model_version')} "
        f"({bundle.get('model_key')})"
    )

    print("[predict] Reading latest prediction input...")
    df = query_prediction_input(
        client=client,
        bq_config=bq_config,
        model_config=model_config,
    )

    validate_prediction_input(df, model_config)
    df = clean_prediction_features(df, model_config)

    predictions = make_predictions(
        df=df,
        bundle=bundle,
        model_config=model_config,
    )

    print("[predict] Predictions:")
    print(
        predictions[
            [
                "symbol",
                "hour_ts",
                "predicted_class",
                "prob_up",
                "prob_down",
                "prob_flat",
                "confidence_score",
                "signal",
            ]
        ].to_string(index=False)
    )

    if args.dry_run:
        print("[predict] Dry run enabled. Skipping BigQuery write.")
    else:
        print(f"[predict] Writing predictions to BigQuery: {bq_config.predictions_table_fqn}")
        write_predictions(
            client=client,
            bq_config=bq_config,
            predictions=predictions,
        )

    print("[predict] Done.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[predict][ERROR] {exc}", file=sys.stderr)
        raise
