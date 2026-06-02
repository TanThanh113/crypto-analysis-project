from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

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


DEFAULT_RUN_ID_FILE = "/tmp/kestra_health_run_id.txt"


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

    def _write_run_id_file(self, run_id: str) -> None:
        run_id_file = Path(os.environ.get("HEALTH_RUN_ID_FILE", DEFAULT_RUN_ID_FILE))
        run_id_file.parent.mkdir(parents=True, exist_ok=True)

        tmp_file = run_id_file.with_suffix(".tmp")
        tmp_file.write_text(run_id, encoding="utf-8")
        tmp_file.replace(run_id_file)

        print(f"[monitoring] Wrote health run_id to {run_id_file}")

    def run(self, fail_on_critical: bool, write_results: bool = True) -> int:
        specs = self.load_specs()
        run_id = f"health-{uuid4().hex}"

        print(f"[monitoring] Health check run_id={run_id}")
        self._write_run_id_file(run_id)

        results = []
        for spec in specs:
            check_spec = dict(spec)
            check_spec["run_id"] = run_id

            print(f"[monitoring] Running check: {check_spec['id']} ({check_spec['type']})")
            result = self.run_check(check_spec)
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
