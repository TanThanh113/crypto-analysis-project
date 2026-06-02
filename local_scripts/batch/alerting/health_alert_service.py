from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

from alerting.settings import AlertSettings
from alerting.slack_client import SlackWebhookClient


DEFAULT_RUN_ID_FILE = "/tmp/kestra_health_run_id.txt"


@dataclass
class HealthAlertSummary:
    run_id: str
    total_checks: int
    failed_critical: int
    failed_warning: int
    latest_check_ts: str
    failed_rows: pd.DataFrame


class HealthAlertService:
    def __init__(self, settings: AlertSettings):
        self.settings = settings
        self.bq = bigquery.Client(
            project=settings.project_id,
            location=settings.location,
        )
        self.slack = SlackWebhookClient(settings.slack_webhook_url)

    def _table_ref(self, table: str) -> str:
        return f"`{self.settings.project_id}.{self.settings.ml_outputs_dataset}.{table}`"

    def _read_target_run_id(self) -> str | None:
        env_run_id = os.environ.get("HEALTH_RUN_ID", "").strip()
        if env_run_id:
            print(f"[slack-alert] Using HEALTH_RUN_ID from env: {env_run_id}")
            return env_run_id

        run_id_file = Path(os.environ.get("HEALTH_RUN_ID_FILE", DEFAULT_RUN_ID_FILE))
        if run_id_file.exists():
            run_id = run_id_file.read_text(encoding="utf-8").strip()
            if run_id:
                print(f"[slack-alert] Using health run_id from file {run_id_file}: {run_id}")
                return run_id

        print("[slack-alert] No explicit run_id found. Falling back to latest recent run.")
        return None

    def load_recent_health_results(self, recent_minutes: int) -> pd.DataFrame:
        target_run_id = self._read_target_run_id()

        if target_run_id:
            sql = f"""
            SELECT
              check_ts,
              run_id,
              check_id,
              check_type,
              severity,
              success,
              metric_value,
              threshold,
              message
            FROM {self._table_ref("pipeline_health_check_results")}
            WHERE run_id = @run_id
            ORDER BY check_ts DESC
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("run_id", "STRING", target_run_id)
                ]
            )

            return (
                self.bq.query(sql, job_config=job_config, location=self.settings.location)
                .result()
                .to_dataframe()
            )

        sql = f"""
        WITH latest_run AS (
          SELECT run_id
          FROM {self._table_ref("pipeline_health_check_results")}
          WHERE check_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {int(recent_minutes)} MINUTE)
            AND run_id IS NOT NULL
          ORDER BY check_ts DESC
          LIMIT 1
        )
        SELECT
          check_ts,
          run_id,
          check_id,
          check_type,
          severity,
          success,
          metric_value,
          threshold,
          message
        FROM {self._table_ref("pipeline_health_check_results")}
        WHERE run_id = (SELECT run_id FROM latest_run)
        ORDER BY check_ts DESC
        """

        return self.bq.query(sql, location=self.settings.location).result().to_dataframe()

    def summarize(self, df: pd.DataFrame) -> HealthAlertSummary:
        if df.empty:
            return HealthAlertSummary(
                run_id="unknown",
                total_checks=0,
                failed_critical=0,
                failed_warning=0,
                latest_check_ts="unknown",
                failed_rows=df,
            )

        failed = df[df["success"] == False].copy()
        failed_critical = int((failed["severity"] == "critical").sum())
        failed_warning = int((failed["severity"] == "warning").sum())

        latest_check_ts = str(pd.to_datetime(df["check_ts"], utc=True).max())

        run_id = "unknown"
        if "run_id" in df.columns and not df["run_id"].dropna().empty:
            run_id = str(df["run_id"].dropna().iloc[0])

        return HealthAlertSummary(
            run_id=run_id,
            total_checks=len(df),
            failed_critical=failed_critical,
            failed_warning=failed_warning,
            latest_check_ts=latest_check_ts,
            failed_rows=failed,
        )

    def build_slack_payload(self, summary: HealthAlertSummary) -> dict:
        if summary.failed_critical > 0:
            title = "🚨 Crypto Pipeline Health Check FAILED"
            color = "#D00000"
        elif summary.failed_warning > 0:
            title = "⚠️ Crypto Pipeline Health Check Warning"
            color = "#E6A700"
        else:
            title = "✅ Crypto Pipeline Health Check Passed"
            color = "#2EB67D"

        failed_lines = []
        for _, row in summary.failed_rows.head(10).iterrows():
            failed_lines.append(
                f"• `{row['severity']}` `{row['check_id']}` — {row['message']}"
            )

        failed_text = "\n".join(failed_lines) if failed_lines else "No failed checks."

        return {
            "text": title,
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Project:*\n`{self.settings.project_id}`",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Run ID:*\n`{summary.run_id}`",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Latest check:*\n`{summary.latest_check_ts}`",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Total checks:*\n`{summary.total_checks}`",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Critical failed:*\n`{summary.failed_critical}`",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Warnings failed:*\n`{summary.failed_warning}`",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Failed checks:*\n{failed_text}",
                    },
                },
            ],
            "attachments": [
                {
                    "color": color,
                    "text": "Source: Kestra GKE pipeline health check",
                }
            ],
        }

    def run(self, recent_minutes: int, only_on_failure: bool, fail_on_critical: bool) -> int:
        df = self.load_recent_health_results(recent_minutes=recent_minutes)
        summary = self.summarize(df)

        print(
            "[slack-alert] "
            f"run_id={summary.run_id}, "
            f"total_checks={summary.total_checks}, "
            f"failed_critical={summary.failed_critical}, "
            f"failed_warning={summary.failed_warning}, "
            f"latest_check_ts={summary.latest_check_ts}"
        )

        should_send = True
        if only_on_failure:
            should_send = summary.failed_critical > 0 or summary.failed_warning > 0

        if should_send:
            payload = self.build_slack_payload(summary)
            self.slack.post_message(payload)
            print("[slack-alert] Slack alert sent.")
        else:
            print("[slack-alert] No failure found. Slack alert skipped.")

        if fail_on_critical and summary.failed_critical > 0:
            print("[slack-alert] Critical failures found.")
            return 1

        return 0
