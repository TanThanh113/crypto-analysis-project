#!/usr/bin/env python3
"""
Local source-coverage and parity debug for Step B1 safe microstructure features.

The script reads the dev dbt training table read-only, compares the 16 safe dbt
features with the local Python engineered parquet, and writes only local
artifacts under ml/artifacts/local_research/.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import yaml
from google.cloud import bigquery


ML_ROOT = Path(__file__).resolve().parent
LOCAL_RESEARCH_ROOT = ML_ROOT / "artifacts" / "local_research"
DEFAULT_LOCAL_PARQUET = (
    LOCAL_RESEARCH_ROOT
    / "feature_engineering_v1"
    / "engineered_training_features.parquet"
)
DEFAULT_ARTIFACT_DIR = LOCAL_RESEARCH_ROOT / "microstructure_safe_v1_parity_debug"
DEFAULT_REPORT_PATH = LOCAL_RESEARCH_ROOT / "microstructure_safe_v1_parity_debug_report.md"


@dataclass(frozen=True)
class SafeFeatureSpec:
    dbt_feature: str
    python_feature: str
    depends_on_sources: tuple[str, ...]
    source_available_flag: str
    prediction_available_flag: str
    should_keep_for_step_b2: bool
    availability_note: str


@dataclass(frozen=True)
class CoverageRow:
    feature: str
    scope: str
    group: str
    row_count: int
    non_null_count: int
    non_null_pct: Optional[float]
    depends_on_sources: str
    source_available_flag: str
    prediction_available_flag: str
    should_keep_for_step_b2: bool


@dataclass(frozen=True)
class ParityRow:
    feature: str
    matched_rows: int
    dbt_non_null_pct: Optional[float]
    python_non_null_pct: Optional[float]
    both_non_null_rows: int
    mean_abs_diff: Optional[float]
    max_abs_diff: Optional[float]
    parity_status: str
    note: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_local_research_path(path: Path) -> Path:
    resolved = path.resolve()
    root = LOCAL_RESEARCH_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path must stay under {root}: {resolved}")
    return resolved


def safe_feature_specs() -> list[SafeFeatureSpec]:
    binance = ("binance_trades",)
    return [
        SafeFeatureSpec("quote_volume_lag_1h", "quote_volume_lag_1h_research", binance, "full_backfill", "available", True, "Binance market volume lag."),
        SafeFeatureSpec("quote_volume_24h_lag_1h", "quote_volume_24h_lag_1h_research", binance, "full_backfill", "available", True, "Binance rolling volume lag."),
        SafeFeatureSpec("quote_volume_zscore_24h", "quote_volume_zscore_24h_research", binance, "full_backfill", "available", True, "Past-only volume z-score."),
        SafeFeatureSpec("volume_zscore_24h_lag_1h", "volume_zscore_24h_lag_1h_research", binance, "full_backfill", "available", True, "Lag of existing Binance volume z-score."),
        SafeFeatureSpec("liquidity_regime_high", "liquidity_regime_high_research", binance, "full_backfill", "available", True, "Derived from quote_volume_zscore_24h."),
        SafeFeatureSpec("liquidity_regime_low", "liquidity_regime_low_research", binance, "full_backfill", "available", True, "Derived from quote_volume_zscore_24h."),
        SafeFeatureSpec("liquidity_risk_score_lag_1h", "liquidity_risk_score_lag_1h_research", ("stablecoin", "exchange_reserve", "liquidation", "market_context"), "partial_coverage", "partial_context", False, "Composite context score; current project data may not have full backfill coverage."),
        SafeFeatureSpec("is_eth_x_quote_volume_zscore_24h", "is_eth_x_quote_volume_zscore_24h_research", binance, "full_backfill", "available", True, "ETH interaction over Binance volume z-score."),
        SafeFeatureSpec("return_4h_lag_1h", "return_4h_lag_1h_research", binance, "full_backfill", "available", True, "Lagged price return."),
        SafeFeatureSpec("return_24h_lag_1h", "return_24h_lag_1h_research", binance, "full_backfill", "available", True, "Lagged price return."),
        SafeFeatureSpec("return_24h_symbol_zscore", "return_24h_symbol_zscore_research", binance, "full_backfill", "available_with_history", True, "Expanding history z-score; needs warmup history."),
        SafeFeatureSpec("return_1h_rolling_mean_4h", "return_1h_rolling_mean_4h_research", binance, "full_backfill", "available_with_history", True, "Past-only rolling return mean."),
        SafeFeatureSpec("return_1h_rolling_sum_4h", "return_1h_rolling_sum_4h_research", binance, "full_backfill", "available_with_history", True, "Past-only rolling return sum."),
        SafeFeatureSpec("return_1h_rolling_mean_24h", "return_1h_rolling_mean_24h_research", binance, "full_backfill", "available_with_history", True, "Past-only rolling return mean."),
        SafeFeatureSpec("return_1h_rolling_sum_24h", "return_1h_rolling_sum_24h_research", binance, "full_backfill", "available_with_history", True, "Past-only rolling return sum."),
        SafeFeatureSpec("rolling_drawdown_24h", "rolling_drawdown_24h_research", binance, "full_backfill", "available_with_history", True, "Past-only log-return drawdown; parity sensitive."),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug safe microstructure feature coverage/parity.")
    parser.add_argument("--config", default="research/configs/feature_list_microstructure_safe_v1.yml")
    parser.add_argument("--local-parquet", default=str(DEFAULT_LOCAL_PARQUET))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--skip-bigquery", action="store_true")
    parser.add_argument("--max-rows", type=int, default=None)
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def table_fqn_from_config(config: dict[str, Any]) -> str:
    bq = config.get("bigquery", {})
    project = os.environ.get(str(bq.get("project_id_env", "GCP_PROJECT_ID")))
    if not project:
        project = str(bq.get("default_project_id", "project-lambda-crypto"))
    dataset = os.environ.get(
        str(bq.get("analytics_dataset_env", "BQ_ANALYTICS_DATASET")),
        str(bq.get("default_analytics_dataset", "dbt_quants_dev")),
    )
    table = str(bq.get("training_table", "mart_ml_training_dataset_hourly"))
    return f"{project}.{dataset}.{table}"


def read_bigquery_training_frame(
    *,
    table_fqn: str,
    specs: list[SafeFeatureSpec],
    max_rows: Optional[int] = None,
) -> pd.DataFrame:
    columns = [
        "hour_ts",
        "symbol",
        "split_name",
        "is_training_row",
        *[spec.dbt_feature for spec in specs],
    ]
    select_expr = ",\n        ".join(f"`{column}`" for column in columns)
    limit_expr = f"\nLIMIT {int(max_rows)}" if max_rows else ""
    query = f"""
    SELECT
        {select_expr}
    FROM `{table_fqn}`
    WHERE is_training_row = TRUE
      AND split_name IN ('train', 'validation', 'test')
    {limit_expr}
    """
    client = bigquery.Client(project=table_fqn.split(".")[0])
    return client.query(query).to_dataframe()


def normalize_keys(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["hour_ts"] = pd.to_datetime(normalized["hour_ts"], errors="coerce", utc=True)
    normalized["symbol"] = normalized["symbol"].astype(str).str.upper()
    if "split_name" not in normalized.columns:
        normalized["split_name"] = "unknown"
    return normalized


def coverage_rows(frame: pd.DataFrame, specs: list[SafeFeatureSpec]) -> list[CoverageRow]:
    rows: list[CoverageRow] = []
    normalized = normalize_keys(frame)
    normalized["month"] = normalized["hour_ts"].dt.strftime("%Y-%m")
    scopes = [
        ("all", None),
        ("split", "split_name"),
        ("symbol", "symbol"),
        ("month", "month"),
    ]
    for spec in specs:
        if spec.dbt_feature not in normalized.columns:
            for scope, _ in scopes[:1]:
                rows.append(
                    CoverageRow(
                        feature=spec.dbt_feature,
                        scope=scope,
                        group="missing_column",
                        row_count=len(normalized),
                        non_null_count=0,
                        non_null_pct=None,
                        depends_on_sources=", ".join(spec.depends_on_sources),
                        source_available_flag=spec.source_available_flag,
                        prediction_available_flag=spec.prediction_available_flag,
                        should_keep_for_step_b2=False,
                    )
                )
            continue

        values = normalized[spec.dbt_feature]
        for scope, group_col in scopes:
            if group_col is None:
                grouped = [("all", normalized)]
            else:
                grouped = list(normalized.groupby(group_col, dropna=False))
            for group, group_df in grouped:
                count = int(group_df.shape[0])
                non_null = int(group_df[spec.dbt_feature].notna().sum())
                pct = float(non_null / count) if count else None
                rows.append(
                    CoverageRow(
                        feature=spec.dbt_feature,
                        scope=scope,
                        group=str(group),
                        row_count=count,
                        non_null_count=non_null,
                        non_null_pct=pct,
                        depends_on_sources=", ".join(spec.depends_on_sources),
                        source_available_flag=spec.source_available_flag,
                        prediction_available_flag=spec.prediction_available_flag,
                        should_keep_for_step_b2=bool(spec.should_keep_for_step_b2 and (pct is not None and pct >= 0.95)),
                    )
                )
    return rows


def compare_parity(
    dbt_df: pd.DataFrame,
    python_df: pd.DataFrame,
    specs: list[SafeFeatureSpec],
) -> list[ParityRow]:
    dbt = normalize_keys(dbt_df)
    py = normalize_keys(python_df)
    required_py_cols = ["hour_ts", "symbol", *[spec.python_feature for spec in specs if spec.python_feature in py.columns]]
    merged = dbt.merge(py[required_py_cols], on=["hour_ts", "symbol"], how="inner", suffixes=("_dbt", "_python"))
    rows: list[ParityRow] = []
    for spec in specs:
        if spec.dbt_feature not in merged.columns:
            rows.append(ParityRow(spec.dbt_feature, len(merged), None, None, 0, None, None, "missing_dbt_column", "DBT column missing."))
            continue
        if spec.python_feature not in merged.columns:
            rows.append(ParityRow(spec.dbt_feature, len(merged), float(merged[spec.dbt_feature].notna().mean()) if len(merged) else None, None, 0, None, None, "missing_python_column", "Python research column missing."))
            continue
        dbt_values = pd.to_numeric(merged[spec.dbt_feature], errors="coerce")
        py_values = pd.to_numeric(merged[spec.python_feature], errors="coerce")
        both = dbt_values.notna() & py_values.notna()
        diff = (dbt_values[both] - py_values[both]).abs()
        mean_abs = None if diff.empty else float(diff.mean())
        max_abs = None if diff.empty else float(diff.max())
        if both.sum() == 0:
            status = "no_overlap"
            note = "No rows where both DBT and Python feature are non-null."
        elif max_abs is not None and max_abs <= 1e-9:
            status = "exact"
            note = "Exact within tolerance."
        elif mean_abs is not None and mean_abs <= 1e-6:
            status = "close"
            note = "Close within tolerance."
        else:
            status = "mismatch"
            note = "Potential formula or window mismatch."
        rows.append(
            ParityRow(
                feature=spec.dbt_feature,
                matched_rows=int(len(merged)),
                dbt_non_null_pct=float(dbt_values.notna().mean()) if len(merged) else None,
                python_non_null_pct=float(py_values.notna().mean()) if len(merged) else None,
                both_non_null_rows=int(both.sum()),
                mean_abs_diff=mean_abs,
                max_abs_diff=max_abs,
                parity_status=status,
                note=note,
            )
        )
    return rows


def summary_payload(
    *,
    table_fqn: str,
    coverage: pd.DataFrame,
    parity: pd.DataFrame,
    specs: list[SafeFeatureSpec],
    read_bigquery: bool,
) -> dict[str, Any]:
    all_scope = coverage[coverage["scope"] == "all"].copy()
    high_coverage = all_scope[all_scope["non_null_pct"].fillna(0) >= 0.95]["feature"].tolist()
    low_coverage = all_scope[all_scope["non_null_pct"].fillna(0) < 0.95]["feature"].tolist()
    mismatch = parity[~parity["parity_status"].isin(["exact", "close"])]["feature"].tolist()
    prediction_risk = [
        spec.dbt_feature
        for spec in specs
        if spec.prediction_available_flag not in {"available", "available_with_history"}
    ]
    backfilled = [
        spec.dbt_feature
        for spec in specs
        if set(spec.depends_on_sources).issubset({"binance_trades", "etf", "macro", "funding"})
    ]
    parity_ok = set(parity[parity["parity_status"].isin(["exact", "close"])]["feature"].tolist())
    keep = all_scope[
        (all_scope["should_keep_for_step_b2"] == True)  # noqa: E712
        & (all_scope["feature"].isin(parity_ok))
    ]["feature"].tolist()
    return {
        "created_at": utc_now_iso(),
        "table_fqn": table_fqn,
        "read_bigquery": read_bigquery,
        "wrote_gcs": False,
        "wrote_bigquery_output": False,
        "updated_registry": False,
        "production_feature_list_changed": False,
        "safe_feature_count": len(specs),
        "features_depending_only_on_backfilled_sources": backfilled,
        "high_coverage_features": high_coverage,
        "low_coverage_features": low_coverage,
        "parity_attention_features": mismatch,
        "prediction_availability_risk_features": prediction_risk,
        "safe_subset_for_step_b2": keep,
    }


def markdown_table(frame: pd.DataFrame, max_rows: int = 30) -> str:
    if frame.empty:
        return "_No data._"
    visible = frame.head(max_rows).copy()
    headers = list(visible.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in visible.iterrows():
        cells = []
        for header in headers:
            value = row[header]
            if pd.isna(value):
                cells.append("")
            elif isinstance(value, float):
                cells.append(f"{value:.4f}")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_outputs(
    *,
    artifact_dir: Path,
    report_path: Path,
    coverage: pd.DataFrame,
    parity: pd.DataFrame,
    summary: dict[str, Any],
    specs: list[SafeFeatureSpec],
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    coverage_path = artifact_dir / "feature_coverage.csv"
    parity_path = artifact_dir / "feature_parity.csv"
    summary_path = artifact_dir / "research_summary.json"
    spec_path = artifact_dir / "feature_source_matrix.csv"
    pd.DataFrame([asdict(spec) for spec in specs]).to_csv(spec_path, index=False)
    coverage.to_csv(coverage_path, index=False)
    parity.to_csv(parity_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    all_coverage = coverage[coverage["scope"] == "all"].sort_values("non_null_pct", ascending=True)
    report = f"""# Microstructure Safe V1 Parity Debug Report

## Safety

- GCS output written: `false`
- BigQuery output tables written: `false`
- Registry updated: `false`
- Production `ml/feature_list.yml` changed: `false`
- BigQuery read-only input used: `{summary["read_bigquery"]}`
- DBT table: `{summary["table_fqn"]}`

## Coverage Summary

{markdown_table(all_coverage[[
    "feature",
    "non_null_pct",
    "depends_on_sources",
    "source_available_flag",
    "prediction_available_flag",
    "should_keep_for_step_b2",
]], max_rows=20)}

## Parity Summary

{markdown_table(parity[[
    "feature",
    "dbt_non_null_pct",
    "python_non_null_pct",
    "both_non_null_rows",
    "mean_abs_diff",
    "max_abs_diff",
    "parity_status",
    "note",
]], max_rows=20)}

## Current Answers

- Features depending only on current full-backfill sources: `{", ".join(summary["features_depending_only_on_backfilled_sources"])}`
- Features with low DBT coverage: `{", ".join(summary["low_coverage_features"]) or "none"}`
- Features needing parity attention: `{", ".join(summary["parity_attention_features"]) or "none"}`
- Prediction-time risk features: `{", ".join(summary["prediction_availability_risk_features"]) or "none"}`
- Proposed safe subset for Step B2: `{", ".join(summary["safe_subset_for_step_b2"]) or "none"}`

## Interpretation

The 16-feature set should not be judged only by the model score. Coverage,
prediction-time availability, and formula parity must be checked first. The
current project has full historical backfill primarily for Binance trades, ETF,
Macro, and Funding. Among the 16 Step B1 features, most are Binance-derived
market/return/volume features. `liquidity_risk_score_lag_1h` depends on broader
context inputs and should stay under review until source coverage is confirmed.

Do not enable production `ml/feature_list.yml` until the parity attention list is
empty or explicitly accepted, and until A/B dry-run confirms the safe subset is
worth activating.

## Output Files

- Coverage CSV: `{coverage_path}`
- Parity CSV: `{parity_path}`
- Summary JSON: `{summary_path}`
- Source matrix CSV: `{spec_path}`
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")


def run_debug(args: argparse.Namespace) -> dict[str, Any]:
    artifact_dir = ensure_local_research_path(Path(args.artifact_dir))
    report_path = ensure_local_research_path(Path(args.report_path))
    config = load_yaml(Path(args.config))
    specs = safe_feature_specs()
    table_fqn = table_fqn_from_config(config)

    python_df = pd.read_parquet(Path(args.local_parquet))
    if args.skip_bigquery:
        dbt_df = python_df.rename(columns={spec.python_feature: spec.dbt_feature for spec in specs})
        read_bigquery = False
    else:
        dbt_df = read_bigquery_training_frame(table_fqn=table_fqn, specs=specs, max_rows=args.max_rows)
        read_bigquery = True

    coverage = pd.DataFrame([asdict(row) for row in coverage_rows(dbt_df, specs)])
    parity = pd.DataFrame([asdict(row) for row in compare_parity(dbt_df, python_df, specs)])
    summary = summary_payload(
        table_fqn=table_fqn,
        coverage=coverage,
        parity=parity,
        specs=specs,
        read_bigquery=read_bigquery,
    )
    write_outputs(
        artifact_dir=artifact_dir,
        report_path=report_path,
        coverage=coverage,
        parity=parity,
        summary=summary,
        specs=specs,
    )
    print(f"[parity-debug] Coverage: {artifact_dir / 'feature_coverage.csv'}")
    print(f"[parity-debug] Parity: {artifact_dir / 'feature_parity.csv'}")
    print(f"[parity-debug] Summary: {artifact_dir / 'research_summary.json'}")
    print(f"[parity-debug] Report: {report_path}")
    return summary


def main() -> int:
    args = parse_args()
    run_debug(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
