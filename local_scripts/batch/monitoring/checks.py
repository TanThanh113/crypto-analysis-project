from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from monitoring.bq_client import BigQueryMonitoringClient


GOOD_STATUS_VALUES = {
    "fresh",
    "ok",
    "healthy",
    "pass",
    "passed",
    "success",
    "good",
}


@dataclass
class HealthCheckResult:
    check_ts: datetime
    run_id: str
    check_id: str
    check_type: str
    severity: str
    success: bool
    metric_value: str
    threshold: str
    message: str
    details_json: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def make_result(
    *,
    run_id: str,
    check_id: str,
    check_type: str,
    severity: str,
    success: bool,
    metric_value: Any,
    threshold: Any,
    message: str,
    details: dict[str, Any] | None = None,
) -> HealthCheckResult:
    return HealthCheckResult(
        check_ts=now_utc(),
        run_id=run_id,
        check_id=check_id,
        check_type=check_type,
        severity=severity,
        success=success,
        metric_value=str(metric_value),
        threshold=str(threshold),
        message=message,
        details_json=json.dumps(details or {}, default=str),
    )


def check_table_non_empty(
    *,
    bq: BigQueryMonitoringClient,
    spec: dict[str, Any],
) -> HealthCheckResult:
    check_id = spec["id"]
    severity = spec.get("severity", "critical")
    dataset = spec["dataset"]
    table = spec["table"]
    min_rows = int(spec.get("min_rows", 1))

    if not bq.table_exists(dataset, table):
        return make_result(
            run_id=spec["run_id"],
            check_id=check_id,
            check_type="table_non_empty",
            severity=severity,
            success=False,
            metric_value="missing_table",
            threshold=f"min_rows={min_rows}",
            message=f"Table does not exist: {bq.table_id(dataset, table)}",
        )

    sql = f"SELECT COUNT(*) AS row_count FROM {bq.table_ref_sql(dataset, table)}"
    df = bq.read_dataframe(sql)
    row_count = int(df.loc[0, "row_count"])

    success = row_count >= min_rows

    return make_result(
        run_id=spec["run_id"],
        check_id=check_id,
        check_type="table_non_empty",
        severity=severity,
        success=success,
        metric_value=row_count,
        threshold=f">= {min_rows}",
        message=(
            f"{bq.table_id(dataset, table)} row_count={row_count}, "
            f"expected >= {min_rows}"
        ),
        details={"dataset": dataset, "table": table, "row_count": row_count},
    )


def _detect_bad_freshness_count(df: pd.DataFrame) -> tuple[int, str]:
    if "bad_freshness_count" in df.columns:
        value = pd.to_numeric(df["bad_freshness_count"], errors="coerce").max()
        if pd.isna(value):
            return 0, "bad_freshness_count_null"
        return int(value), "bad_freshness_count"

    if "is_fresh" in df.columns:
        series = df["is_fresh"].fillna(False).astype(bool)
        return int((~series).sum()), "is_fresh"

    for column in ["freshness_status", "status", "quality_status"]:
        if column in df.columns:
            normalized = df[column].astype(str).str.lower().str.strip()
            bad_count = int((~normalized.isin(GOOD_STATUS_VALUES)).sum())
            return bad_count, column

    return 0, "no_explicit_status_column"


def _detect_latest_ts(df: pd.DataFrame) -> tuple[pd.Timestamp | None, str | None]:
    candidates = [
        "latest_data_update",
        "latest_data_ts",
        "latest_source_ts",
        "latest_update_ts",
        "latest_loaded_at",
        "max_event_ts",
        "hour_ts",
        "updated_at",
    ]

    for column in candidates:
        if column in df.columns:
            ts = pd.to_datetime(df[column], errors="coerce", utc=True).max()
            if pd.notna(ts):
                return ts, column

    return None, None


def check_data_freshness_mart(
    *,
    bq: BigQueryMonitoringClient,
    spec: dict[str, Any],
) -> HealthCheckResult:
    check_id = spec["id"]
    severity = spec.get("severity", "critical")
    dataset = spec["dataset"]
    table = spec["table"]
    max_bad_rows = int(spec.get("max_bad_rows", 0))
    max_age_hours = spec.get("max_age_hours")

    if not bq.table_exists(dataset, table):
        return make_result(
            run_id=spec["run_id"],
            check_id=check_id,
            check_type="data_freshness_mart",
            severity=severity,
            success=False,
            metric_value="missing_table",
            threshold=f"max_bad_rows={max_bad_rows}",
            message=f"Freshness mart does not exist: {bq.table_id(dataset, table)}",
        )

    sql = f"SELECT * FROM {bq.table_ref_sql(dataset, table)} LIMIT 5000"
    df = bq.read_dataframe(sql)

    if df.empty:
        return make_result(
            run_id=spec["run_id"],
            check_id=check_id,
            check_type="data_freshness_mart",
            severity=severity,
            success=False,
            metric_value="0 rows",
            threshold="row_count > 0",
            message=f"Freshness mart is empty: {bq.table_id(dataset, table)}",
        )

    bad_count, bad_source = _detect_bad_freshness_count(df)
    latest_ts, latest_ts_column = _detect_latest_ts(df)

    stale = False
    age_hours = None

    if latest_ts is not None and max_age_hours is not None:
        age_seconds = (pd.Timestamp.now(tz="UTC") - latest_ts).total_seconds()
        age_hours = age_seconds / 3600
        stale = age_hours > float(max_age_hours)

    success = bad_count <= max_bad_rows and not stale

    message = (
        f"bad_freshness_count={bad_count} from {bad_source}; "
        f"latest_ts={latest_ts} from {latest_ts_column}; "
        f"age_hours={age_hours}"
    )

    return make_result(
        run_id=spec["run_id"],
        check_id=check_id,
        check_type="data_freshness_mart",
        severity=severity,
        success=success,
        metric_value=f"bad={bad_count}, age_hours={age_hours}",
        threshold=f"bad <= {max_bad_rows}, age_hours <= {max_age_hours}",
        message=message,
        details={
            "row_count": len(df),
            "bad_count": bad_count,
            "bad_source": bad_source,
            "latest_ts": latest_ts,
            "latest_ts_column": latest_ts_column,
            "age_hours": age_hours,
            "max_age_hours": max_age_hours,
        },
    )


def check_ge_latest_audit(
    *,
    bq: BigQueryMonitoringClient,
    spec: dict[str, Any],
) -> HealthCheckResult:
    check_id = spec["id"]
    severity = spec.get("severity", "critical")
    dataset = spec["dataset"]
    table = spec["table"]
    recent_hours = int(spec.get("recent_hours", 48))
    max_failed_critical = int(spec.get("max_failed_critical", 0))

    if not bq.table_exists(dataset, table):
        return make_result(
            run_id=spec["run_id"],
            check_id=check_id,
            check_type="ge_latest_audit",
            severity=severity,
            success=False,
            metric_value="missing_table",
            threshold=f"failed_critical <= {max_failed_critical}",
            message=f"GE audit results table does not exist: {bq.table_id(dataset, table)}",
        )

    sql = f"""
    SELECT
      COUNT(*) AS total_checks,
      COUNTIF(severity = 'critical' AND success = FALSE) AS failed_critical,
      COUNTIF(severity = 'warning' AND success = FALSE) AS failed_warning,
      MAX(audit_ts) AS latest_audit_ts
    FROM {bq.table_ref_sql(dataset, table)}
    WHERE audit_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {recent_hours} HOUR)
    """
    df = bq.read_dataframe(sql)

    total_checks = int(df.loc[0, "total_checks"])
    failed_critical = int(df.loc[0, "failed_critical"])
    failed_warning = int(df.loc[0, "failed_warning"])
    latest_audit_ts = df.loc[0, "latest_audit_ts"]

    success = total_checks > 0 and failed_critical <= max_failed_critical

    return make_result(
        run_id=spec["run_id"],
        check_id=check_id,
        check_type="ge_latest_audit",
        severity=severity,
        success=success,
        metric_value=f"failed_critical={failed_critical}",
        threshold=f"<= {max_failed_critical}",
        message=(
            f"GE recent_hours={recent_hours}, total_checks={total_checks}, "
            f"failed_critical={failed_critical}, failed_warning={failed_warning}, "
            f"latest_audit_ts={latest_audit_ts}"
        ),
        details={
            "total_checks": total_checks,
            "failed_critical": failed_critical,
            "failed_warning": failed_warning,
            "latest_audit_ts": latest_audit_ts,
            "recent_hours": recent_hours,
        },
    )


def check_prediction_freshness(
    *,
    bq: BigQueryMonitoringClient,
    spec: dict[str, Any],
) -> HealthCheckResult:
    check_id = spec["id"]
    severity = spec.get("severity", "warning")
    dataset = spec["dataset"]
    table = spec["table"]
    timestamp_column = spec.get("timestamp_column", "prediction_ts")
    max_age_hours = float(spec.get("max_age_hours", 6))
    allow_missing_table = bool(spec.get("allow_missing_table", True))

    if not bq.table_exists(dataset, table):
        return make_result(
            run_id=spec["run_id"],
            check_id=check_id,
            check_type="prediction_freshness",
            severity=severity,
            success=allow_missing_table,
            metric_value="missing_table",
            threshold=f"max_age_hours={max_age_hours}",
            message=f"Prediction table missing: {bq.table_id(dataset, table)}",
            details={"allow_missing_table": allow_missing_table},
        )

    sql = f"""
    SELECT
      COUNT(*) AS row_count,
      MAX({timestamp_column}) AS latest_prediction_ts
    FROM {bq.table_ref_sql(dataset, table)}
    """
    df = bq.read_dataframe(sql)

    row_count = int(df.loc[0, "row_count"])
    latest_prediction_ts = df.loc[0, "latest_prediction_ts"]

    if row_count == 0 or pd.isna(latest_prediction_ts):
        return make_result(
            run_id=spec["run_id"],
            check_id=check_id,
            check_type="prediction_freshness",
            severity=severity,
            success=False,
            metric_value=f"row_count={row_count}",
            threshold=f"max_age_hours={max_age_hours}",
            message="No model prediction rows found.",
        )

    latest_ts = pd.Timestamp(latest_prediction_ts)
    if latest_ts.tzinfo is None:
        latest_ts = latest_ts.tz_localize("UTC")

    age_hours = (pd.Timestamp.now(tz="UTC") - latest_ts).total_seconds() / 3600
    success = age_hours <= max_age_hours

    return make_result(
        run_id=spec["run_id"],
        check_id=check_id,
        check_type="prediction_freshness",
        severity=severity,
        success=success,
        metric_value=f"age_hours={age_hours:.2f}",
        threshold=f"<= {max_age_hours}",
        message=f"Latest prediction ts={latest_ts}, age_hours={age_hours:.2f}",
        details={
            "row_count": row_count,
            "latest_prediction_ts": latest_ts,
            "age_hours": age_hours,
            "max_age_hours": max_age_hours,
        },
    )
