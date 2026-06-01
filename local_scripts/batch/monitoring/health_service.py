from __future__ import annotations

import pandas as pd
import yaml

from monitoring.bq_client import BigQueryMonitoringClient
from monitoring.checks import (
    HealthCheckResult,
    check_data_freshness_mart,
    check_ge_latest_audit,
    check_prediction_freshness,
    check_table_non_empty,
)
from monitoring.settings import MonitoringSettings


CHECK_REGISTRY = {
    "table_non_empty": check_table_non_empty,
    "data_freshness_mart": check_data_freshness_mart,
    "ge_latest_audit": check_ge_latest_audit,
    "prediction_freshness": check_prediction_freshness,
}


class PipelineHealthService:
    def __init__(self, settings: MonitoringSettings):
        self.settings = settings
        self.bq = BigQueryMonitoringClient(settings)

    def load_specs(self) -> list[dict]:
        spec_path = self.settings.specs_dir / "health_checks.yml"

        if not spec_path.exists():
            raise FileNotFoundError(f"Health check spec not found: {spec_path}")

        with spec_path.open("r", encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}

        checks = payload.get("checks", [])
        if not checks:
            raise RuntimeError(f"No checks found in {spec_path}")

        return checks

    def run_check(self, spec: dict) -> HealthCheckResult:
        check_type = spec["type"]

        if check_type not in CHECK_REGISTRY:
            raise ValueError(f"Unsupported check type: {check_type}")

        check_fn = CHECK_REGISTRY[check_type]
        return check_fn(bq=self.bq, spec=spec)

    def run(self, fail_on_critical: bool, write_results: bool = True) -> int:
        specs = self.load_specs()

        results = []
        for spec in specs:
            print(f"[monitoring] Running check: {spec['id']} ({spec['type']})")
            result = self.run_check(spec)
            print(
                f"[monitoring] {result.check_id}: "
                f"success={result.success}, severity={result.severity}, "
                f"message={result.message}"
            )
            results.append(result)

        df = pd.DataFrame([result.to_dict() for result in results])

        if write_results:
            self.bq.write_results(df, "pipeline_health_check_results")

        failed_critical = df[
            (df["severity"] == "critical")
            & (df["success"] == False)
        ]

        failed_warning = df[
            (df["severity"] == "warning")
            & (df["success"] == False)
        ]

        print(f"[monitoring] Failed critical checks: {len(failed_critical)}")
        print(f"[monitoring] Failed warning checks: {len(failed_warning)}")

        if len(failed_critical) > 0:
            for _, row in failed_critical.iterrows():
                print(
                    "[monitoring][critical-fail] "
                    f"{row['check_id']} | {row['message']}"
                )

        if fail_on_critical and len(failed_critical) > 0:
            print("[monitoring] Pipeline health check failed.")
            return 1

        print("[monitoring] Pipeline health check completed.")
        return 0
