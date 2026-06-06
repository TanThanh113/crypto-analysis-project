#!/usr/bin/env python3
"""
Train crypto 4H direction model from dbt marts/ml.

This script:
1. Reads feature contract from feature_list.yml
2. Reads training data from BigQuery mart_ml_training_dataset_hourly
3. Trains Logistic Regression baseline and/or LightGBM
4. Evaluates train / validation / test splits
5. Saves local model artifact
6. Writes model metrics to BigQuery ml_outputs.model_metrics

Important:
- This script uses only feature columns declared in feature_list.yml.
- It does not use future_* columns as features.
- model_name and model_version should match dim_ml_model_registry.
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
from typing import Any, Dict, Iterable, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import yaml
from urllib.parse import urlparse
from google.cloud import bigquery, storage
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    log_loss,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from feature_contract import get_feature_contract_metadata
from mlflow_utils import handle_mlflow_error, is_mlflow_enabled, log_training_run
from mlflow_registry import MLflowRegistryResult, register_model_if_enabled
from optuna_tuning import (
    OptunaTuningResult,
    OptunaTuningSettings,
    get_optuna_settings,
    tune_lightgbm_pipeline,
)
from promotion_gate import (
    PromotionGateConfig,
    PromotionGateResult,
    evaluate_promotion_gate,
)
from strategy_config import (
    TrainingStrategy,
    get_strategy,
    list_strategies,
    list_strategy_names,
)
from time_split import apply_train_window

DEFAULT_VALID_CLASSES = ["UP", "DOWN", "FLAT"]
TRUE_VALUES = {"1", "true", "yes", "y", "on"}
MODEL_KEY_BY_CHOICE = {
    "logistic": "logistic_regression_baseline",
    "lightgbm": "lightgbm_classifier",
}

# To structure the configuration settings, making the code clearer and easier to manage:
# Use a dataclass to define the configuration settings(BigQuery, Model, Training, etc.)
# Note: @dataclass: Automatically generate basic functions such as __init__ and __repr__.
#                   frozen=True: Makes this class an "immutable" object.
#                   @property: Turns a function into a property.

# Contains connection information to Google BigQuery
@dataclass(frozen=True)
class BigQueryConfig:
    project_id: str
    analytics_dataset: str
    ml_outputs_dataset: str
    training_table: str
    metrics_table: str

    @property # Fully qualified name of the training table
    def training_table_fqn(self) -> str:
        return f"{self.project_id}.{self.analytics_dataset}.{self.training_table}"
    @property # Fully qualified name of the metrics table
    def metrics_table_fqn(self) -> str:
        return f"{self.project_id}.{self.ml_outputs_dataset}.{self.metrics_table}"

# Contains the model configuration(name, version, family, algorithm, etc.)
@dataclass(frozen=True)
class ModelConfig:
    model_name: str
    model_version: str
    model_family: str
    algorithm: str
    target_name: str
    split_column: str
    sample_weight_column: str
    primary_metric: str
    random_state: int
    valid_classes: List[str]

    # List of input data columns in both text (categorized) and numerical formats.
    categorical_features: List[str]
    numeric_features: List[str]

    # This function automatically adds the two column lists above together to return all the input features that the model will use for learning.
    @property
    def all_features(self) -> List[str]:
        return self.categorical_features + self.numeric_features

# Contains the training configuration(min_total_rows, min_rows_per_split, min_classes_per_split, etc.)
@dataclass(frozen=True) 
class TrainingConfig:
    min_total_rows: int
    min_rows_per_split: int
    min_classes_per_split: int
    fill_numeric_null_with: float
    fill_categorical_null_with: str
    drop_rows_with_null_target: bool


# Returns the current UTC time
def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# Check if the URI is a GCS URI.
def is_gcs_uri(uri: Optional[str]) -> bool:
    return bool(uri and uri.startswith("gs://"))

# Parse a GCS URI into bucket and blob.
def parse_gcs_uri(uri: str) -> tuple[str, str]:
    if not is_gcs_uri(uri):
        raise ValueError(f"Invalid GCS URI: {uri}")

    parsed = urlparse(uri)
    bucket = parsed.netloc
    blob = parsed.path.lstrip("/")

    if not bucket or not blob:
        raise ValueError(f"Invalid GCS URI: {uri}")

    return bucket, blob

# Join a GCS URI with a filename.
def join_gcs_uri(root_uri: str, filename: str) -> str:
    if not is_gcs_uri(root_uri):
        raise ValueError(f"Invalid GCS root URI: {root_uri}")

    return root_uri.rstrip("/") + "/" + filename.lstrip("/")

# Upload a local file to GCS.
def upload_file_to_gcs(local_path: Path, destination_uri: str) -> str:
    bucket_name, blob_name = parse_gcs_uri(destination_uri)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    blob.upload_from_filename(str(local_path))

    print(f"[artifact] Uploaded {local_path} -> {destination_uri}")
    return destination_uri

# Read and load the feature_list file.
def load_yaml(path: Path) -> Dict[str, Any]:
    # If the file does not exist, raise an error.
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    # Open the file and read its contents.
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # If the data is not a dictionary, raise an error.
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML config: {path}")

    return data

# Build the BigQuery, Model, and Training configurations from the feature_list.yml file.
def build_configs(config: Dict[str, Any]) -> Tuple[BigQueryConfig, ModelConfig, TrainingConfig]:
    bq = config.get("bigquery", {}) # Get the BigQuery configuration from the feature_list.yml file.
    model = config.get("model", {}) # Get the Model configuration from the feature_list.yml file.
    training = config.get("training", {}) # Get the Training configuration from the feature_list.yml file.

    project_env = bq.get("project_id_env", "GCP_PROJECT_ID")
    analytics_env = bq.get("analytics_dataset_env", "BQ_ANALYTICS_DATASET")
    outputs_env = bq.get("ml_outputs_dataset_env", "BQ_ML_OUTPUTS_DATASET")

    project_id = os.environ.get(project_env)
    if not project_id:
        raise ValueError(f"Missing required environment variable: {project_env}")

    # Create a BigQueryConfig object with the project ID, analytics dataset, and ML outputs dataset.
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
        training_table=bq.get("training_table", "mart_ml_training_dataset_hourly"),
        metrics_table=bq.get("metrics_table", "model_metrics"),
    )

    # Create a ModelConfig object with the model name, version, family, algorithm, target name, split column,...
    model_config = ModelConfig(
        model_name=model.get("model_name", "crypto_direction_lgbm_v1"),
        model_version=model.get("model_version", "v1"),
        model_family=model.get("model_family", "crypto_direction"),
        algorithm=model.get("algorithm", "lightgbm"),
        target_name=model.get("target_name", "future_direction_4h"),
        split_column=model.get("split_column", "split_name"),
        sample_weight_column=model.get("sample_weight_column", "sample_weight_4h"),
        primary_metric=model.get("primary_metric", "f1_macro"),
        random_state=int(model.get("random_state", 42)),
        valid_classes=list(model.get("valid_classes", DEFAULT_VALID_CLASSES)),
        categorical_features=list(model.get("categorical_features", ["symbol"])),
        numeric_features=list(model.get("numeric_features", [])),
    )

    # If the numeric_features list is empty, raise an error.
    if not model_config.numeric_features:
        raise ValueError("feature_list.yml must contain model.numeric_features")

    # Create a TrainingConfig object with the training configuration settings.
    training_config = TrainingConfig(
        min_total_rows=int(training.get("min_total_rows", 200)),
        min_rows_per_split=int(training.get("min_rows_per_split", 20)),
        min_classes_per_split=int(training.get("min_classes_per_split", 2)),
        fill_numeric_null_with=float(training.get("fill_numeric_null_with", 0)),
        fill_categorical_null_with=str(training.get("fill_categorical_null_with", "UNKNOWN")),
        drop_rows_with_null_target=bool(training.get("drop_rows_with_null_target", True)),
    )

    return bq_config, model_config, training_config


def query_training_data(client: bigquery.Client, bq_config: BigQueryConfig, model_config: ModelConfig,) -> pd.DataFrame:
    # Retrieve the necessary columns
    base_columns = [
        "hour_ts",
        "symbol",
        model_config.split_column,
        "is_training_row",
        model_config.sample_weight_column,
        model_config.target_name,
    ]

    # Deduplicate the columns
    columns = list(dict.fromkeys(base_columns + model_config.all_features))
    # Build the SQL query
    select_expr = ",\n        ".join([f"`{column}`" for column in columns])

    query = f"""
    SELECT
        {select_expr}
    FROM `{bq_config.training_table_fqn}`
    WHERE is_training_row = TRUE
      AND `{model_config.target_name}` IS NOT NULL
      AND UPPER(CAST(`{model_config.target_name}` AS STRING)) IN UNNEST(@valid_classes)
      AND `{model_config.split_column}` IN ('train', 'validation', 'test')
    """
    # Add the valid_classes parameter
    # This aims to increase security and prevent errors such as others adding malicious code to orders.
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter(
                "valid_classes",
                "STRING",
                model_config.valid_classes,
            )
        ]
    )

    # Execute the query(BigQuery) and return the result as a pandas DataFrame
    return client.query(query, job_config=job_config).to_dataframe()

# Check the quality of the data
def validate_training_data(df: pd.DataFrame, model_config: ModelConfig, training_config: TrainingConfig,) -> None:

    # Check if the required columns are present
    required_columns = set(
        [
            "hour_ts",
            "symbol",
            model_config.split_column,
            model_config.target_name,
        ]
        + model_config.all_features
    )

    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Training data is missing required columns: {missing_columns}")

    # Check if the data is empty
    if df.empty:
        raise ValueError(
            "Training query returned 0 rows. "
            "Backfill more hourly data first, then rerun dbt marts/ml."
        )

    # Check if the data has enough rows
    if len(df) < training_config.min_total_rows:
        raise ValueError(
            f"Training data has only {len(df)} rows. "
            f"Need at least {training_config.min_total_rows} rows."
        )

    # Check the number of lines in each set.
    split_counts = df[model_config.split_column].value_counts().to_dict()
    for split_name in ["train", "validation", "test"]:
        count = split_counts.get(split_name, 0)
        if count < training_config.min_rows_per_split:
            raise ValueError(
                f"Split '{split_name}' has only {count} rows. "
                f"Need at least {training_config.min_rows_per_split} rows."
            )

    # Convert to a string and capitalize and check the number of classes
    normalized_target = df[model_config.target_name].astype(str).str.upper()
    total_class_counts = normalized_target.value_counts().to_dict()

    if len(total_class_counts) < 2:
        raise ValueError(
            f"Target has fewer than 2 classes: {total_class_counts}. "
            "Need more historical data."
        )

    for split_name in ["train", "validation", "test"]:
        # Check the number of classes
        split_target = (
            df.loc[df[model_config.split_column] == split_name, model_config.target_name]
            .astype(str)
            .str.upper()
        )
        split_classes = split_target.nunique()
        
        # If the number of classes is less than the minimum, raise an error.
        if split_classes < training_config.min_classes_per_split:
            raise ValueError(
                f"Split '{split_name}' has only {split_classes} target class(es). "
                f"Need at least {training_config.min_classes_per_split}. "
                "Backfill more data or relax training.min_classes_per_split for demo."
            )

# Clean the features in the training data.
def clean_features(df: pd.DataFrame, model_config: ModelConfig, training_config: TrainingConfig,) -> pd.DataFrame:
    cleaned = df.copy()

    for column in model_config.numeric_features:
        # Convert to numeric, but don't fail on NaN
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    for column in model_config.categorical_features:
        # Convert to string, fill NaN with training config value, and convert to uppercase
        cleaned[column] = (
            cleaned[column]
            .astype("string")
            .fillna(training_config.fill_categorical_null_with)
            .str.upper()
        )

    # Convert target to string and uppercase
    cleaned[model_config.target_name] = cleaned[model_config.target_name].astype(str).str.upper()

    return cleaned

# Its task is to "digitize" the columns of text into strings of 0s and 1s.
def make_one_hot_encoder() -> OneHotEncoder:
    # OneHotEncoder does not support sparse output, so we need to use a different encoder.
    # The request returns a standard NumPy array.
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def make_preprocessor(model_config: ModelConfig, scale_numeric: bool) -> ColumnTransformer:
    numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        # Imputer: Fill in the blank cells (NaN) with the median value of that column.
        # Scaler: Scale the values to have a mean of 0 and a standard deviation of 1.
        numeric_steps.append(("scaler", StandardScaler()))

    numeric_pipeline = Pipeline(steps=numeric_steps)

    categorical_pipeline = Pipeline(
        steps=[("imputer", SimpleImputer(strategy="most_frequent")),("onehot", make_one_hot_encoder())]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, model_config.numeric_features),
            ("cat", categorical_pipeline, model_config.categorical_features),
        ],
        # If the original DataFrame contains columns other than those listed, they will be removed and not included in the model.
        remainder="drop",
        # When you export the processed data, Pandas will automatically add a prefix to the column names.
        verbose_feature_names_out=True,
    )


def build_models(model_config: ModelConfig) -> Dict[str, Pipeline]:
    # Logistic Regression(Baseline)
    logistic = Pipeline(
        steps=[
            # Scale the numeric features: This helps the model converge faster.
            ("preprocess", make_preprocessor(model_config, scale_numeric=True)),
            (
                "model",
                LogisticRegression(
                    max_iter=2000, # Increase the maximum number of iterations to ensure the model has enough time to find the optimal point (convergence).
                    class_weight="balanced", # Automatically adjust weights if the data is unbalanced.
                    solver="lbfgs", # Optimization algorithm
                    random_state=model_config.random_state, # This helps to fix the results after each code run.
                    n_jobs=-1, # Utilizing all of the computer's CPU cores for parallel computing helps it run faster.
                ),
            ),
        ]
    )

    # LightGBM(Gradient Boosting)
    lightgbm = Pipeline(
        steps=[
            # Since this is a tree-based model, StandardScaler is not needed here; we can disable it for faster calculations.
            ("preprocess", make_preprocessor(model_config, scale_numeric=False)),
            (
                "model",
                LGBMClassifier(
                    objective="multiclass", # Identify this as a problem involving classifying more than two groups.
                    n_estimators=300, # Number of trees in the forest.
                    learning_rate=0.03, # Each subsequent tree will correct the mistakes of the previous trees.
                    num_leaves=31, # Number of leaves in each tree.
                    max_depth=-1, # No limit on the depth of the tree.
                    min_child_samples=10, # Minimum number of samples required to make a split.

                    subsample=0.80, # Each time a new tree is planted, the model randomly selects only 80% of the data rows.
                    colsample_bytree=0.80, # Each time a new tree is planted, the model randomly selects only 80% of the features.

                    # Two additional mathematical penalties are added to the loss function.
                    reg_alpha=0.10,
                    reg_lambda=0.30,
                    class_weight="balanced",
                    random_state=model_config.random_state,
                    n_jobs=-1,
                    verbosity=-1, # This means requesting LightGBM to "be silent".
                ),
            ),
        ]
    )

    return {
        "logistic_regression_baseline": logistic,
        "lightgbm_classifier": lightgbm,
    }


def filter_models_for_choice(
    models: Dict[str, Pipeline],
    model_choice: str,
) -> Dict[str, Pipeline]:
    if model_choice == "auto":
        return models

    model_key = MODEL_KEY_BY_CHOICE[model_choice]
    return {model_key: models[model_key]}


def resolve_requested_strategies(args: argparse.Namespace) -> List[TrainingStrategy]:
    if args.strategy and args.strategy_matrix:
        raise ValueError("Use either --strategy or --strategy-matrix, not both.")

    if args.strategy_matrix:
        return list_strategies()

    if args.strategy:
        return [get_strategy(args.strategy)]

    return []


# Calculate the weight for each data row.
def get_sample_weight(df: pd.DataFrame, model_config: ModelConfig,) -> Optional[np.ndarray]:
    column = model_config.sample_weight_column
    if column not in df.columns:
        return None

    weights = (
        pd.to_numeric(df[column], errors="coerce")
        .fillna(1.0)
        .clip(lower=0.1, upper=10.0) # It limits (clips the top and blocks the base) the weighted value.
    )

    return weights.to_numpy()

# Separate the data into characteristic variables (X) and labels (Y).
def split_xy(
    df: pd.DataFrame,
    split_name: str,
    model_config: ModelConfig,
) -> Tuple[pd.DataFrame, pd.Series, Optional[np.ndarray]]:
    # Filter out data rows that belong to a specific set.
    part = df[df[model_config.split_column] == split_name].copy()

    # Combine all the attribute columns (such as Age, Income, City) into a variable X to use as input data for the model.
    x = part[model_config.all_features]
    # Take the target/label column (Answer) and put it into the variable Y, while also applying uppercase font style to match the previous cleaning step.
    y = part[model_config.target_name].astype(str).str.upper()
    # Get the sample weight for each data row.
    weights = get_sample_weight(part, model_config)

    return x, y, weights


# When you want to know which class a percentage of a data sample's prediction model belongs to
# You will use the .predict_proba() function.
def safe_predict_proba(model: Pipeline, x: pd.DataFrame) -> Optional[np.ndarray]:
    # This function checks if the current model has probability prediction capabilities. If it does, it calls model.predict_proba(x).
    try:
        if hasattr(model, "predict_proba"):
            return model.predict_proba(x)
    except Exception:
        return None

    return None

# Calculate the AUC (Class Separation) score.
# Practical purpose: To measure the ability of the model to sort and differentiate between classes.
def safe_auc(y_true: pd.Series, proba: Optional[np.ndarray], classes: Iterable[str]) -> Optional[float]:
    if proba is None:
        return None

    classes_list = list(classes)
    unique_classes = set(y_true.dropna().unique())

    if len(unique_classes) < 2:
        return None

    try:
        if len(classes_list) == 2:
            positive_index = classes_list.index("UP") if "UP" in classes_list else 1
            return float(roc_auc_score(y_true, proba[:, positive_index]))

        return float(
            roc_auc_score(
                y_true,
                proba,
                multi_class="ovr",
                labels=classes_list,
            )
        )
    except Exception:
        return None

# Calculate the Log Loss score.
# Practical purpose: To measure the accuracy of the probability. It absolutely hates it when the model is wrong but overconfident.
def safe_log_loss(y_true: pd.Series, proba: Optional[np.ndarray], classes: Iterable[str]) -> Optional[float]:
    if proba is None:
        return None

    try:
        return float(log_loss(y_true, proba, labels=list(classes)))
    except Exception:
        return None

# Calculate the Brier Score.
# Practical purpose: Similar to Log Loss, Brier score is used to measure the "deviation" between the model's predicted probability 
# and the actual probability, but using the squared distance formula.
def brier_multiclass(y_true: pd.Series, proba: Optional[np.ndarray], classes: Iterable[str]) -> Optional[float]:
    if proba is None:
        return None

    classes_list = list(classes)

    try:
        # Create an empty matrix of zeros with the same size as the probability matrix.
        y_onehot = np.zeros_like(proba, dtype=float)
        class_index = {label: idx for idx, label in enumerate(classes_list)}

        # Iterate through each row of actual data. Whatever label a row has, set the 
        # corresponding column to 1.0. This is called the absolute answer matrix.
        for row_idx, label in enumerate(y_true):
            if label in class_index:
                y_onehot[row_idx, class_index[label]] = 1.0

        return float(np.mean(np.sum((proba - y_onehot) ** 2, axis=1)))
    except Exception:
        return None

# Evaluate the model's performance.
def evaluate_model(model: Pipeline, x: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
    pred = model.predict(x) # Extract the straight prediction label.

    estimator = model.named_steps["model"]
    # Retrieve a list of classes sorted in the order the model has learned them.
    classes = list(getattr(estimator, "classes_", sorted(y.unique())))

    # Get proba matrix for each class.
    proba = safe_predict_proba(model, x)

    # precision_recall_fscore_support(...): Calculates the traditional triple-metric set based on the correct/incorrect prediction label:
    precision, recall, f1, _ = precision_recall_fscore_support(
        y,
        pred,
        average="macro",
        zero_division=0,
    )
    _, per_class_recall, _, _ = precision_recall_fscore_support(
        y,
        pred,
        labels=classes,
        average=None,
        zero_division=0,
    )

    # Return all calculated metrics for evaluation.
    return {
        "row_count": int(len(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "precision_macro": float(precision),
        "recall_macro": float(recall),
        "per_class_recall_min": float(np.min(per_class_recall)) if len(per_class_recall) else None,
        "f1_macro": float(f1),
        "auc_ovr": safe_auc(y, proba, classes),
        "log_loss": safe_log_loss(y, proba, classes),
        "brier_score": brier_multiclass(y, proba, classes),
    }

# Return the model metadata for the given model key.
def model_metadata(model_key: str) -> Tuple[str, str, str]:
    try:
        strategy = get_strategy(model_key)
    except KeyError:
        strategy = None

    if strategy is not None:
        return model_metadata(strategy.base_model_key)

    if model_key == "logistic_regression_baseline":
        return "linear_baseline", "logistic_regression", "classification"

    if model_key == "lightgbm_classifier":
        return "gradient_boosted_trees", "lightgbm", "classification"

    return "unknown", model_key, "classification"

# Choose the best model
def choose_best_model(results: Dict[str, Dict[str, Any]], primary_metric: str) -> str:
    scored: List[Tuple[float, str]] = []

    # Iterate over all models and calculate the validation metric.
    for model_key, result in results.items():
        validation_metric = result["metrics"]["validation"].get(primary_metric)

        if validation_metric is None or pd.isna(validation_metric):
            validation_metric = -1.0

        # Tie-breaker for LightGBM models.
        _, algorithm, _ = model_metadata(model_key)
        tie_breaker = 0.000001 if algorithm == "lightgbm" else 0.0
        scored.append((float(validation_metric) + tie_breaker, model_key))

    return sorted(scored, reverse=True)[0][1]

# Bundle and store a Machine Learning model.
def save_bundle(
    model: Pipeline,
    model_config: ModelConfig,
    model_key: str,
    base_model_key: str,
    artifact_version: str,
    artifact_dir: Path,
    metrics: Dict[str, Any],
    training_table_fqn: str,
    run_id: str,
    strategy: Optional[TrainingStrategy] = None,
    optuna_result: Optional[OptunaTuningResult] = None,
) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)

    model_family, algorithm, problem_type = model_metadata(model_key)
    estimator = model.named_steps["model"]

    # This line will retrieve a list of labels/classes that the model has learned.
    classes = list(getattr(estimator, "classes_", []))

    bundle = {
        "model": model,
        "model_name": model_config.model_name,
        "model_version": model_config.model_version,
        "artifact_version": artifact_version,
        "model_key": model_key,
        "base_model_key": base_model_key,
        "model_family": model_family,
        "algorithm": algorithm,
        "problem_type": problem_type,
        "target_name": model_config.target_name,
        "features": model_config.all_features,
        "numeric_features": model_config.numeric_features,
        "categorical_features": model_config.categorical_features,
        "classes": classes,
        "valid_classes": model_config.valid_classes,
        "training_table": training_table_fqn,
        "metrics": metrics,
        "run_id": run_id,
        "saved_at": utc_now().isoformat(),
    }

    if strategy is not None:
        bundle.update(strategy.metadata())

    if optuna_result is not None and optuna_result.enabled:
        bundle["optuna"] = optuna_result.to_dict()

    artifact_path = artifact_dir / (
        f"{model_config.model_name}__{model_key}__{artifact_version}.joblib"
    )

    joblib.dump(bundle, artifact_path)
    return artifact_path

# Return the path of the best model.
def save_latest_manifest(
    artifact_dir: Path,
    best_bundle_path: Path,
    best_model_key: str,
    model_config: ModelConfig,
    run_id: str,
    artifact_uri: Optional[str] = None,
    manifest_name: str = "latest_model.json",
    promotion_result: Optional[PromotionGateResult] = None,
) -> Path:
    manifest = {
        "model_name": model_config.model_name,
        "model_version": model_config.model_version,
        "target_name": model_config.target_name,
        "best_model_key": best_model_key,
        "artifact_path": str(best_bundle_path),
        "artifact_uri": artifact_uri or str(best_bundle_path),
        "artifact_gcs_uri": artifact_uri if is_gcs_uri(artifact_uri) else None,
        "run_id": run_id,
        "updated_at": utc_now().isoformat(),
    }

    if promotion_result is not None:
        manifest.update(
            {
                "promotion_status": promotion_result.status,
                "promotion_passed": promotion_result.passed,
                "promotion_reasons": promotion_result.reasons,
                "promotion_checked_at": promotion_result.checked_at,
            }
        )

    manifest_path = artifact_dir / manifest_name

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def load_local_champion_metrics(
    artifact_dir: Path,
    manifest_name: str,
) -> Optional[Dict[str, Any]]:
    manifest_path = artifact_dir / manifest_name
    if not manifest_path.exists():
        return None

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)

        artifact_path = manifest.get("artifact_path") or manifest.get("local_artifact_path")
        if not artifact_path or is_gcs_uri(str(artifact_path)):
            return None

        local_artifact_path = Path(str(artifact_path)).expanduser().resolve()
        if not local_artifact_path.exists():
            return None

        bundle = joblib.load(local_artifact_path)
        metrics = bundle.get("metrics")
        if isinstance(metrics, dict):
            return metrics

    except Exception as exc:
        print(f"[promotion][WARN] Could not load local champion metrics: {exc}")

    return None


def build_promotion_gate_config(
    config: Dict[str, Any],
    training_config: TrainingConfig,
) -> PromotionGateConfig:
    promotion = config.get("promotion", {})

    def float_setting(name: str, env_name: str, default: float) -> float:
        env_value = os.environ.get(env_name)
        if env_value is not None:
            return float(env_value)
        return float(promotion.get(name, default))

    def int_setting(name: str, env_name: str, default: int) -> int:
        env_value = os.environ.get(env_name)
        if env_value is not None:
            return int(env_value)
        return int(promotion.get(name, default))

    return PromotionGateConfig(
        margin=float_setting("margin", "ML_PROMOTION_MARGIN", 0.0),
        max_test_f1_degradation=float_setting(
            "max_test_f1_degradation",
            "ML_PROMOTION_MAX_TEST_F1_DEGRADATION",
            0.05,
        ),
        max_log_loss_degradation=float_setting(
            "max_log_loss_degradation",
            "ML_PROMOTION_MAX_LOG_LOSS_DEGRADATION",
            0.10,
        ),
        min_row_count=int_setting(
            "min_row_count",
            "ML_PROMOTION_MIN_ROW_COUNT",
            training_config.min_rows_per_split,
        ),
        min_per_class_recall=float_setting(
            "min_per_class_recall",
            "ML_PROMOTION_MIN_PER_CLASS_RECALL",
            0.0,
        ),
        min_feature_completeness_score=float_setting(
            "min_feature_completeness_score",
            "ML_PROMOTION_MIN_FEATURE_COMPLETENESS_SCORE",
            0.0,
        ),
    )


def promotion_fail_on_reject(config: Dict[str, Any]) -> bool:
    env_value = os.environ.get("ML_PROMOTION_FAIL_ON_REJECT")
    if env_value is not None:
        return env_value.strip().lower() in TRUE_VALUES

    promotion = config.get("promotion", {})
    return bool(promotion.get("fail_on_reject", False))


def save_promotion_gate_artifact(
    artifact_dir: Path,
    run_id: str,
    promotion_result: PromotionGateResult,
) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    promotion_path = artifact_dir / f"promotion_gate_{run_id}.json"

    with promotion_path.open("w", encoding="utf-8") as f:
        json.dump(promotion_result.to_dict(), f, indent=2, default=str)

    return promotion_path


def update_manifest_with_registry_result(
    manifest_path: Path,
    registry_result: MLflowRegistryResult,
) -> None:
    if not manifest_path.exists():
        return

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    manifest.update(
        {
            "registry_status": registry_result.status,
            "registry_reasons": registry_result.reasons or [],
            "mlflow_registered_model_name": registry_result.registered_model_name,
            "mlflow_model_version": registry_result.model_version,
            "mlflow_model_alias": registry_result.model_alias,
            "mlflow_model_uri": registry_result.model_uri,
            "mlflow_registry_run_id": registry_result.run_id,
        }
    )

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)


def _metric_value(
    metrics: Dict[str, Any],
    split_name: str,
    metric_name: str,
) -> Optional[float]:
    split_metrics = metrics.get(split_name, {})
    if not isinstance(split_metrics, dict):
        return None

    value = split_metrics.get(metric_name)
    if value is None:
        return None

    try:
        metric_value = float(value)
    except (TypeError, ValueError):
        return None

    if metric_value != metric_value:
        return None

    return metric_value


def build_registry_tags(
    *,
    config_path: Path,
    args: argparse.Namespace,
    bq_config: BigQueryConfig,
    model_config: ModelConfig,
    results: Dict[str, Dict[str, Any]],
    best_model_key: str,
    promotion_result: PromotionGateResult,
) -> Dict[str, Any]:
    best_result = results[best_model_key]
    strategy_metadata = dict(best_result.get("strategy_metadata", {}) or {})
    metrics = best_result.get("metrics", {})

    feature_contract_metadata = get_feature_contract_metadata(config_path)
    validation_f1 = _metric_value(metrics, "validation", "f1_macro")
    test_f1 = _metric_value(metrics, "test", "f1_macro")
    log_loss_value = _metric_value(metrics, "validation", "log_loss")

    tags: Dict[str, Any] = {
        "strategy_name": strategy_metadata.get("strategy_name", best_model_key),
        "model_choice": strategy_metadata.get("model_choice", args.model_choice),
        "model_name": model_config.model_name,
        "model_version": model_config.model_version,
        "feature_contract_hash": feature_contract_metadata.get("feature_contract_hash"),
        "promotion_status": promotion_result.status,
        "promotion_passed": promotion_result.passed,
        "git_sha": args.git_sha,
        "training_table": bq_config.training_table_fqn,
        "target_name": model_config.target_name,
        "created_by": "crypto-analysis-project",
        "phase": "mlflow_mlops_upgrade",
    }

    if validation_f1 is not None:
        tags["validation_f1_macro"] = validation_f1
    if test_f1 is not None:
        tags["test_f1_macro"] = test_f1
    if log_loss_value is not None:
        tags["log_loss"] = log_loss_value

    optuna_result = best_result.get("optuna")
    if isinstance(optuna_result, dict):
        tags["optuna_enabled"] = optuna_result.get("enabled", False)
        tags["optuna_metric"] = optuna_result.get("metric_name")
        tags["optuna_best_trial_number"] = optuna_result.get("best_trial_number")

    return tags


def train_and_store_candidate(
    *,
    model_key: str,
    base_model_key: str,
    model: Pipeline,
    df: pd.DataFrame,
    model_config: ModelConfig,
    artifact_dir: Path,
    artifact_storage: str,
    artifact_gcs_uri: Optional[str],
    artifact_ts: str,
    bq_config: BigQueryConfig,
    run_id: str,
    dry_run: bool,
    strategy: Optional[TrainingStrategy] = None,
    optuna_settings: Optional[OptunaTuningSettings] = None,
) -> Dict[str, Any]:
    print(f"[train] Training {model_key}...")

    x_train, y_train, w_train = split_xy(df, "train", model_config)
    x_val, y_val, _ = split_xy(df, "validation", model_config)
    x_test, y_test, _ = split_xy(df, "test", model_config)

    fit_kwargs = {}
    if w_train is not None:
        fit_kwargs["model__sample_weight"] = w_train

    optuna_result: Optional[OptunaTuningResult] = None
    if optuna_settings is not None and optuna_settings.enabled:
        optuna_result = tune_lightgbm_pipeline(
            model_key=model_key,
            base_model_key=base_model_key,
            model=model,
            x_train=x_train,
            y_train=y_train,
            x_val=x_val,
            y_val=y_val,
            sample_weight=w_train,
            settings=optuna_settings,
            random_state=model_config.random_state,
        )

        if optuna_result.enabled:
            for reason in optuna_result.reasons:
                print(f"[optuna] {model_key}: {reason}")

            if optuna_result.best_params:
                model.set_params(
                    **{
                        f"model__{key}": value
                        for key, value in optuna_result.best_params.items()
                    }
                )
                print(
                    f"[optuna] {model_key}: best "
                    f"{optuna_result.metric_name}={optuna_result.best_value} "
                    f"trial={optuna_result.best_trial_number}"
                )

    model.fit(x_train, y_train, **fit_kwargs)

    split_metrics = {
        "train": evaluate_model(model, x_train, y_train),
        "validation": evaluate_model(model, x_val, y_val),
        "test": evaluate_model(model, x_test, y_test),
    }

    artifact_version = f"{model_config.model_version}__{model_key}__{artifact_ts}"

    artifact_path = save_bundle(
        model=model,
        model_config=model_config,
        model_key=model_key,
        base_model_key=base_model_key,
        artifact_version=artifact_version,
        artifact_dir=artifact_dir,
        metrics=split_metrics,
        training_table_fqn=bq_config.training_table_fqn,
        run_id=run_id,
        strategy=strategy,
        optuna_result=optuna_result,
    )

    model_artifact_uri = str(artifact_path)

    if artifact_storage in ("gcs", "both"):
        if dry_run:
            print("[artifact] Dry run enabled. Skipping GCS artifact upload.")
        else:
            model_artifact_uri = upload_file_to_gcs(
                local_path=artifact_path,
                destination_uri=join_gcs_uri(
                    artifact_gcs_uri,
                    artifact_path.name,
                ),
            )

    result: Dict[str, Any] = {
        "model": model,
        "artifact_path": artifact_path,
        "model_artifact_uri": model_artifact_uri,
        "metrics": split_metrics,
        "base_model_key": base_model_key,
        "training_summary": summarize_training_data(df, model_config),
    }

    if strategy is not None:
        result["strategy_metadata"] = strategy.metadata()

    if optuna_result is not None and optuna_result.enabled:
        result["optuna"] = optuna_result.to_dict()

    print(f"[train] Saved artifact: {artifact_path}")
    print(
        f"[train] Validation metrics for {model_key}:\n"
        f"{json.dumps(split_metrics['validation'], indent=2)}"
    )

    return result

# Write the evaluation metrics to BigQuery.
def write_metrics_to_bigquery(
    client: bigquery.Client,
    bq_config: BigQueryConfig,
    model_config: ModelConfig,
    results: Dict[str, Dict[str, Any]],
    trained_at: datetime,
    run_id: str,
    git_sha: Optional[str], # Git hash (commit hash) at the time of training.
) -> None:
    rows: List[Dict[str, Any]] = []

    for model_key, result in results.items():
        model_family, algorithm, problem_type = model_metadata(model_key)

        for split_name, metrics in result["metrics"].items():
            rows.append(
                {
                    "model_name": model_config.model_name,
                    "model_version": model_config.model_version,
                    "trained_at": trained_at,
                    "evaluated_at": utc_now(),
                    "target_name": model_config.target_name,
                    "split_name": split_name,
                    "row_count": metrics.get("row_count"),
                    "accuracy": metrics.get("accuracy"),
                    "precision_macro": metrics.get("precision_macro"),
                    "recall_macro": metrics.get("recall_macro"),
                    "f1_macro": metrics.get("f1_macro"),
                    "auc_ovr": metrics.get("auc_ovr"),
                    "log_loss": metrics.get("log_loss"),
                    "brier_score": metrics.get("brier_score"),
                    "feature_table": bq_config.training_table_fqn,
                    "training_table": bq_config.training_table_fqn,
                    "model_artifact_uri": str(result.get("model_artifact_uri", result["artifact_path"])),
                    "git_sha": git_sha,
                    "run_id": run_id,
                    "model_key": model_key,
                    "model_family": model_family,
                    "algorithm": algorithm,
                    "problem_type": problem_type,
                }
            )

    # Create a DataFrame from the rows.
    metrics_df = pd.DataFrame(rows)

    # Append the metrics to BigQuery.
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
    )

    # Load the DataFrame into BigQuery.
    client.load_table_from_dataframe(
        metrics_df,
        bq_config.metrics_table_fqn,
        job_config=job_config,
    ).result()


def summarize_training_data(
    df: pd.DataFrame,
    model_config: ModelConfig,
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "total_row_count": int(len(df)),
        "split_counts": {},
        "split_date_ranges": {},
    }

    if model_config.split_column in df.columns:
        split_counts = df[model_config.split_column].value_counts().to_dict()
        summary["split_counts"] = {
            str(split_name): int(row_count)
            for split_name, row_count in split_counts.items()
        }

    if "hour_ts" not in df.columns or model_config.split_column not in df.columns:
        return summary

    for split_name, split_df in df.groupby(model_config.split_column):
        timestamps = pd.to_datetime(split_df["hour_ts"], errors="coerce", utc=True).dropna()
        if timestamps.empty:
            continue

        summary["split_date_ranges"][str(split_name)] = {
            "start": timestamps.min().isoformat(),
            "end": timestamps.max().isoformat(),
        }

    return summary


def flatten_model_metrics(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    flattened: Dict[str, Any] = {}

    for model_key, result in results.items():
        for split_name, metrics in result.get("metrics", {}).items():
            for metric_name, metric_value in metrics.items():
                flattened[f"{model_key}.{split_name}.{metric_name}"] = metric_value

        optuna_result = result.get("optuna")
        if isinstance(optuna_result, dict) and optuna_result.get("best_value") is not None:
            flattened[f"{model_key}.optuna_best_value"] = optuna_result.get("best_value")

    return flattened


def collect_optuna_results(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return {
        model_key: result["optuna"]
        for model_key, result in results.items()
        if isinstance(result.get("optuna"), dict)
    }


def save_optuna_summary_artifact(
    *,
    artifact_dir: Path,
    run_id: str,
    results: Dict[str, Dict[str, Any]],
    best_model_key: str,
) -> Optional[Path]:
    optuna_results = collect_optuna_results(results)
    if not optuna_results:
        return None

    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary_path = artifact_dir / f"optuna_summary_{run_id}.json"
    payload = {
        "run_id": run_id,
        "best_model_key": best_model_key,
        "optuna": optuna_results,
        "created_at": utc_now().isoformat(),
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    return summary_path


def build_training_summary_artifact(
    artifact_dir: Path,
    run_id: str,
    summary: Dict[str, Any],
    feature_contract_metadata: Dict[str, Any],
    best_model_key: str,
    best_artifact_uri: str,
    promotion_result: Optional[PromotionGateResult] = None,
) -> Path:
    summary_path = artifact_dir / f"training_summary_{run_id}.json"
    payload = {
        "run_id": run_id,
        "best_model_key": best_model_key,
        "best_artifact_uri": best_artifact_uri,
        "training_summary": summary,
        "feature_contract": feature_contract_metadata,
        "promotion_gate": (
            promotion_result.to_dict()
            if promotion_result is not None
            else None
        ),
        "created_at": utc_now().isoformat(),
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    return summary_path


def log_optional_mlflow_training_run(
    *,
    config_path: Path,
    artifact_dir: Path,
    args: argparse.Namespace,
    bq_config: BigQueryConfig,
    model_config: ModelConfig,
    df: pd.DataFrame,
    results: Dict[str, Dict[str, Any]],
    run_id: str,
    best_model_key: str,
    best_artifact_uri: str,
    manifest_path: Path,
    promotion_result: Optional[PromotionGateResult] = None,
    promotion_gate_path: Optional[Path] = None,
    optuna_summary_path: Optional[Path] = None,
) -> None:
    if not is_mlflow_enabled():
        return

    try:
        feature_contract_metadata = get_feature_contract_metadata(config_path)
        training_summary = summarize_training_data(df, model_config)
        best_result = results.get(best_model_key, {})
        strategy_metadata = dict(best_result.get("strategy_metadata", {}) or {})
        effective_model_choice = strategy_metadata.get("model_choice", args.model_choice)
        training_mode = (
            "strategy_matrix"
            if args.strategy_matrix
            else "strategy"
            if args.strategy
            else "legacy"
        )

        params: Dict[str, Any] = {
            "model_name": model_config.model_name,
            "model_version": model_config.model_version,
            "model_choice": effective_model_choice,
            "cli_model_choice": args.model_choice,
            "training_mode": training_mode,
            "target_name": model_config.target_name,
            "primary_metric": model_config.primary_metric,
            "training_table": bq_config.training_table_fqn,
            "feature_table": bq_config.training_table_fqn,
            "metrics_table": bq_config.metrics_table_fqn,
            "best_model_key": best_model_key,
            "total_row_count": training_summary["total_row_count"],
        }

        if promotion_result is not None:
            params.update(
                {
                    "promotion_status": promotion_result.status,
                    "promotion_passed": promotion_result.passed,
                    "promotion_reason_count": len(promotion_result.reasons),
                    "promotion_candidate_score": promotion_result.candidate_score,
                    "promotion_champion_score": promotion_result.champion_score,
                    "promotion_margin": promotion_result.margin,
                }
            )

        for split_name, row_count in training_summary.get("split_counts", {}).items():
            params[f"split.{split_name}.row_count"] = row_count

        for split_name, date_range in training_summary.get("split_date_ranges", {}).items():
            params[f"split.{split_name}.start"] = date_range.get("start")
            params[f"split.{split_name}.end"] = date_range.get("end")

        params.update(feature_contract_metadata)
        params.update(strategy_metadata)

        optuna_results = collect_optuna_results(results)
        best_optuna = best_result.get("optuna")
        params.update(
            {
                "optuna_enabled": bool(optuna_results),
                "optuna_requested": bool(args.enable_optuna),
                "optuna_n_trials": args.optuna_n_trials,
                "optuna_timeout_seconds": args.optuna_timeout_seconds,
                "optuna_metric": args.optuna_metric,
                "optuna_direction": args.optuna_direction,
                "optuna_strategy": args.optuna_strategy,
            }
        )

        if isinstance(best_optuna, dict):
            params.update(
                {
                    "optuna_best_trial_number": best_optuna.get("best_trial_number"),
                    "optuna_best_value": best_optuna.get("best_value"),
                    "optuna_study_name": best_optuna.get("study_name"),
                    "optuna_completed_trials": best_optuna.get("n_trials"),
                }
            )
            for param_name, param_value in dict(best_optuna.get("best_params") or {}).items():
                params[f"optuna_best_{param_name}"] = param_value

        if args.strategy_matrix:
            strategy_names = [
                result.get("strategy_metadata", {}).get("strategy_name")
                for result in results.values()
                if result.get("strategy_metadata")
            ]
            params["strategy_matrix.names"] = ",".join(
                str(strategy_name)
                for strategy_name in strategy_names
                if strategy_name
            )

        tags = {
            "mlflow_phase": (
                "phase_2_strategy_matrix"
                if strategy_metadata
                else "phase_1_experiment_logging"
            ),
            "training_mode": training_mode,
            "model_name": model_config.model_name,
            "model_version": model_config.model_version,
            "model_choice": effective_model_choice,
            "target_name": model_config.target_name,
            "training_table": bq_config.training_table_fqn,
            "feature_contract_hash": feature_contract_metadata.get("feature_contract_hash"),
            "git_sha": args.git_sha,
            "best_model_key": best_model_key,
            "optuna_enabled": str(bool(optuna_results)).lower(),
        }
        tags.update(strategy_metadata)
        if isinstance(best_optuna, dict):
            tags.update(
                {
                    "optuna_metric": best_optuna.get("metric_name"),
                    "optuna_best_trial_number": best_optuna.get("best_trial_number"),
                }
            )
        if promotion_result is not None:
            tags.update(
                {
                    "promotion_status": promotion_result.status,
                    "promotion_passed": str(promotion_result.passed).lower(),
                    "promotion_reason_count": len(promotion_result.reasons),
                }
            )

        summary_artifact = build_training_summary_artifact(
            artifact_dir=artifact_dir,
            run_id=run_id,
            summary=training_summary,
            feature_contract_metadata=feature_contract_metadata,
            best_model_key=best_model_key,
            best_artifact_uri=best_artifact_uri,
            promotion_result=promotion_result,
        )

        artifact_paths: List[Path] = [config_path, summary_artifact]
        if manifest_path.exists():
            artifact_paths.append(manifest_path)
        if promotion_gate_path and promotion_gate_path.exists():
            artifact_paths.append(promotion_gate_path)
        if optuna_summary_path and optuna_summary_path.exists():
            artifact_paths.append(optuna_summary_path)

        for result in results.values():
            artifact_path = result.get("artifact_path")
            if artifact_path:
                artifact_paths.append(Path(artifact_path))

        mlflow_metrics = flatten_model_metrics(results)
        if isinstance(best_optuna, dict) and best_optuna.get("best_value") is not None:
            mlflow_metrics["optuna_best_value"] = best_optuna.get("best_value")

        log_training_run(
            run_name=f"{model_config.model_name}_{model_config.model_version}_{run_id}",
            params=params,
            metrics=mlflow_metrics,
            tags=tags,
            artifact_paths=artifact_paths,
        )

    except Exception as exc:
        handle_mlflow_error("Optional MLflow training logging failed", exc)

# Parse the command-line arguments.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train crypto 4H direction model.")

    parser.add_argument(
        "--config",
        default="feature_list.yml",
        help="Path to feature_list.yml",
    )

    parser.add_argument(
        "--artifact-dir",
        default="artifacts",
        help="Local artifact directory",
    )

    parser.add_argument(
        "--model-choice",
        choices=["auto", "logistic", "lightgbm"],
        default="auto",
        help="Which model to train.",
    )

    parser.add_argument(
        "--strategy",
        choices=list_strategy_names(),
        default=None,
        help="Train exactly one named strategy. Overrides --model-choice for that run.",
    )

    parser.add_argument(
        "--strategy-matrix",
        action="store_true",
        help="Train all configured strategies and choose the best by the primary metric.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Train and save locally, but do not write metrics to BigQuery.",
    )

    parser.add_argument(
        "--git-sha",
        default=os.environ.get("GIT_SHA"),
        help="Optional git SHA for lineage.",
    )
    parser.add_argument(
        "--artifact-storage",
        choices=["local", "gcs", "both"],
        default=os.environ.get("ML_ARTIFACT_STORAGE"),
        help=(
            "Where to persist model artifacts. "
            "'local' keeps current behavior, 'gcs' uploads to GCS, "
            "'both' saves locally and uploads to GCS."
        ),
    )

    parser.add_argument(
        "--artifact-gcs-uri",
        default=os.environ.get("ML_ARTIFACT_GCS_URI"),
        help=(
            "GCS folder for model artifacts, for example "
            "gs://your-bucket/ml-artifacts/crypto_direction_lgbm_v1"
        ),
    )

    parser.add_argument(
        "--enable-optuna",
        action="store_true",
        default=os.environ.get("ML_OPTUNA_ENABLED", "").strip().lower() in TRUE_VALUES,
        help="Enable optional Optuna tuning for LightGBM candidates.",
    )

    parser.add_argument(
        "--optuna-n-trials",
        type=int,
        default=int(os.environ.get("ML_OPTUNA_N_TRIALS", "20")),
        help="Number of Optuna trials when tuning is enabled.",
    )

    parser.add_argument(
        "--optuna-timeout-seconds",
        type=int,
        default=(
            int(os.environ["ML_OPTUNA_TIMEOUT_SECONDS"])
            if os.environ.get("ML_OPTUNA_TIMEOUT_SECONDS")
            else None
        ),
        help="Optional Optuna timeout in seconds.",
    )

    parser.add_argument(
        "--optuna-study-name",
        default=os.environ.get("ML_OPTUNA_STUDY_NAME"),
        help="Optional Optuna study name.",
    )

    parser.add_argument(
        "--optuna-storage-uri",
        default=os.environ.get("ML_OPTUNA_STORAGE_URI"),
        help="Optional Optuna storage URI, for example sqlite:///tmp/optuna.db.",
    )

    parser.add_argument(
        "--optuna-direction",
        choices=["maximize", "minimize"],
        default=os.environ.get("ML_OPTUNA_DIRECTION", "maximize"),
        help="Optuna optimization direction.",
    )

    parser.add_argument(
        "--optuna-metric",
        choices=["f1_macro", "accuracy", "log_loss"],
        default=os.environ.get("ML_OPTUNA_METRIC", "f1_macro"),
        help="Validation metric optimized by Optuna.",
    )

    parser.add_argument(
        "--optuna-strategy",
        default=os.environ.get("ML_OPTUNA_STRATEGY"),
        help=(
            "Optional strategy or model key to tune. "
            "When empty, all selected LightGBM candidates can be tuned."
        ),
    )

    parser.add_argument(
        "--optuna-fail-on-error",
        action="store_true",
        default=os.environ.get("ML_OPTUNA_FAIL_ON_ERROR", "").strip().lower() in TRUE_VALUES,
        help="Fail training if optional Optuna tuning fails.",
    )

    return parser.parse_args()

def resolve_artifact_gcs_uri(config: Dict[str, Any], cli_artifact_gcs_uri: Optional[str]) -> Optional[str]:
    if cli_artifact_gcs_uri:
        return cli_artifact_gcs_uri

    artifact = config.get("artifact", {})
    explicit_uri = artifact.get("gcs_uri") or artifact.get("artifact_gcs_uri")
    if explicit_uri:
        return explicit_uri

    bucket_env = artifact.get("gcs_bucket_env", "GCP_BUCKET_NAME")
    bucket_name = os.environ.get(bucket_env)
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
    # Parse the command-line arguments.
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

    if artifact_storage not in ("local", "gcs", "both"):
        raise ValueError(
            f"Invalid artifact storage mode: {artifact_storage}. "
            "Use local, gcs, or both."
        )

    if artifact_storage in ("gcs", "both") and not artifact_gcs_uri:
        raise ValueError(
            "GCS artifact storage is enabled, but no GCS URI was provided. "
            "Set --artifact-gcs-uri, ML_ARTIFACT_GCS_URI, or artifact.gcs_bucket_env + artifact.gcs_prefix."
        )

    run_id = str(uuid.uuid4())
    trained_at = utc_now()
    artifact_ts = trained_at.strftime("%Y%m%d_%H%M%S")
    
    bq_config, model_config, training_config = build_configs(config) # Build the configurations.
    optuna_settings = get_optuna_settings(
        enabled=args.enable_optuna,
        n_trials=args.optuna_n_trials,
        timeout_seconds=args.optuna_timeout_seconds,
        study_name=args.optuna_study_name,
        storage_uri=args.optuna_storage_uri,
        direction=args.optuna_direction,
        metric_name=args.optuna_metric,
        strategy_name=args.optuna_strategy,
        fail_on_error=args.optuna_fail_on_error,
    )

    # Connect to BigQuery.
    client = bigquery.Client(project=bq_config.project_id)

    print(f"[train] Project: {bq_config.project_id}")
    print(f"[train] Training table: {bq_config.training_table_fqn}")
    print(f"[train] Metrics table: {bq_config.metrics_table_fqn}")
    print(f"[train] Model: {model_config.model_name}:{model_config.model_version}")
    print(f"[train] Target: {model_config.target_name}")
    if optuna_settings.enabled:
        print(
            "[optuna] Enabled: "
            f"trials={optuna_settings.n_trials}, "
            f"metric={optuna_settings.metric_name}, "
            f"direction={optuna_settings.direction}, "
            f"target={optuna_settings.strategy_name or 'selected_lightgbm_candidates'}"
        )

    df = query_training_data(client, bq_config, model_config) # To retrieve raw data from BigQuery to the machine in DataFrame format.
    df = clean_features(df, model_config, training_config) # Clean the data.

    validate_training_data(df, model_config, training_config) # Validate the data.

    print("[train] Row counts by split:")
    print(df[model_config.split_column].value_counts().to_string())

    print("[train] Target distribution:")
    print(df[model_config.target_name].value_counts().to_string())

    results: Dict[str, Dict[str, Any]] = {} # Store the results of each model.
    requested_strategies = resolve_requested_strategies(args)

    if requested_strategies:
        print("[train] Strategy mode enabled:")
        for strategy in requested_strategies:
            print(
                "  - "
                f"{strategy.name} "
                f"(model={strategy.model_type}, "
                f"window_days={strategy.train_window_days or 'all_history'})"
            )

            strategy_df = apply_train_window(
                df,
                split_column=model_config.split_column,
                train_window_days=strategy.train_window_days,
            )
            validate_training_data(strategy_df, model_config, training_config)

            strategy_models = build_models(model_config)
            model = strategy_models[strategy.base_model_key]
            results[strategy.name] = train_and_store_candidate(
                model_key=strategy.name,
                base_model_key=strategy.base_model_key,
                model=model,
                df=strategy_df,
                model_config=model_config,
                artifact_dir=artifact_dir,
                artifact_storage=artifact_storage,
                artifact_gcs_uri=artifact_gcs_uri,
                artifact_ts=artifact_ts,
                bq_config=bq_config,
                run_id=run_id,
                dry_run=args.dry_run,
                strategy=strategy,
                optuna_settings=optuna_settings,
            )
    else:
        models = filter_models_for_choice(build_models(model_config), args.model_choice)
        for model_key, model in models.items():
            results[model_key] = train_and_store_candidate(
                model_key=model_key,
                base_model_key=model_key,
                model=model,
                df=df,
                model_config=model_config,
                artifact_dir=artifact_dir,
                artifact_storage=artifact_storage,
                artifact_gcs_uri=artifact_gcs_uri,
                artifact_ts=artifact_ts,
                bq_config=bq_config,
                run_id=run_id,
                dry_run=args.dry_run,
                optuna_settings=optuna_settings,
            )

    # Choose the best model.
    best_model_key = choose_best_model(results, model_config.primary_metric)
    best_artifact_path = results[best_model_key]["artifact_path"]

    best_artifact_uri = results[best_model_key].get(
        "model_artifact_uri",
        str(best_artifact_path),
    )
    optuna_summary_path = save_optuna_summary_artifact(
        artifact_dir=artifact_dir,
        run_id=run_id,
        results=results,
        best_model_key=best_model_key,
    )

    champion_metrics = load_local_champion_metrics(
        artifact_dir=artifact_dir,
        manifest_name=latest_manifest_name,
    )
    best_training_summary = results[best_model_key].get(
        "training_summary",
        summarize_training_data(df, model_config),
    )
    promotion_result = evaluate_promotion_gate(
        candidate_metrics=results[best_model_key]["metrics"],
        champion_metrics=champion_metrics,
        config=build_promotion_gate_config(config, training_config),
        split_date_ranges=best_training_summary.get("split_date_ranges"),
    )
    promotion_gate_path = save_promotion_gate_artifact(
        artifact_dir=artifact_dir,
        run_id=run_id,
        promotion_result=promotion_result,
    )

    print(
        f"[promotion] Status: {promotion_result.status} "
        f"(passed={promotion_result.passed})"
    )
    for reason in promotion_result.reasons:
        print(f"[promotion] - {reason}")

    if not promotion_result.passed and promotion_fail_on_reject(config):
        raise RuntimeError(
            "Promotion gate rejected the candidate and "
            "ML_PROMOTION_FAIL_ON_REJECT=true."
        )

    # Save the latest model manifest.
    manifest_path = save_latest_manifest(
        artifact_dir=artifact_dir,
        best_bundle_path=best_artifact_path,
        best_model_key=best_model_key,
        model_config=model_config,
        run_id=run_id,
        artifact_uri=best_artifact_uri,
        manifest_name=latest_manifest_name,
        promotion_result=promotion_result,
    )

    if artifact_storage in ("gcs", "both"):
        if args.dry_run:
            print("[artifact] Dry run enabled. Skipping GCS manifest upload.")
        else:
            upload_file_to_gcs(
                local_path=manifest_path,
                destination_uri=join_gcs_uri(
                    artifact_gcs_uri,
                    latest_manifest_name,
                ),
            )

    print(f"[train] Best model: {best_model_key}")
    print(f"[train] Best artifact: {best_artifact_path}")

    # Write the evaluation metrics to BigQuery.
    if args.dry_run:
        print("[train] Dry run enabled. Skipping BigQuery metrics write.")
    else:
        print(f"[train] Writing metrics to BigQuery: {bq_config.metrics_table_fqn}")
        write_metrics_to_bigquery(
            client=client,
            bq_config=bq_config,
            model_config=model_config,
            results=results,
            trained_at=trained_at,
            run_id=run_id,
            git_sha=args.git_sha,
        )

    log_optional_mlflow_training_run(
        config_path=config_path,
        artifact_dir=artifact_dir,
        args=args,
        bq_config=bq_config,
        model_config=model_config,
        df=df,
        results=results,
        run_id=run_id,
        best_model_key=best_model_key,
        best_artifact_uri=best_artifact_uri,
        manifest_path=manifest_path,
        promotion_result=promotion_result,
        promotion_gate_path=promotion_gate_path,
        optuna_summary_path=optuna_summary_path,
    )

    registry_result = register_model_if_enabled(
        model=results[best_model_key]["model"],
        run_name=f"{model_config.model_name}_{model_config.model_version}_{run_id}_registry",
        default_registered_model_name=model_config.model_name,
        promotion_result=promotion_result,
        tags=build_registry_tags(
            config_path=config_path,
            args=args,
            bq_config=bq_config,
            model_config=model_config,
            results=results,
            best_model_key=best_model_key,
            promotion_result=promotion_result,
        ),
    )
    update_manifest_with_registry_result(manifest_path, registry_result)

    if registry_result.status == "disabled":
        print("[registry] Disabled. Skipping MLflow Model Registry.")
    else:
        print(f"[registry] Status: {registry_result.status}")
        for reason in registry_result.reasons or []:
            print(f"[registry] - {reason}")

    print("[train] Done.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[train][ERROR] {exc}", file=sys.stderr)
        raise
