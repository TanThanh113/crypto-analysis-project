# This allows you to use advanced type hinting without errors, unlike older Python versions.
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from google.cloud import bigquery

from alerting.settings import AlertSettings
from alerting.slack_client import SlackWebhookClient

# Create a new dataclass to store the summary of health alerts.
@dataclass
class HealthAlertSummary:
    total_checks: int
    failed_critical: int
    failed_warning: int
    latest_check_ts: str
    failed_rows: pd.DataFrame

# Create a new class to handle health alerts.
class HealthAlertService:
    def __init__(self, settings: AlertSettings):
        self.settings = settings # Store the settings.
        # Create a BigQuery client.
        self.bq = bigquery.Client(
            project=settings.project_id,
            location=settings.location,
        )
        # Create a Slack client.
        self.slack = SlackWebhookClient(settings.slack_webhook_url)

    # Create a table reference string.
    def _table_ref(self, table: str) -> str:
        return f"`{self.settings.project_id}.{self.settings.ml_outputs_dataset}.{table}`"

    # Load recent health results from BigQuery -> DataFrame.
    def load_recent_health_results(self, recent_minutes: int) -> pd.DataFrame:
        sql = f"""
        SELECT
          check_ts,
          check_id,
          check_type,
          severity,
          success,
          metric_value,
          threshold,
          message
        FROM {self._table_ref("pipeline_health_check_results")}
        WHERE check_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {int(recent_minutes)} MINUTE)
        ORDER BY check_ts DESC
        """
        return self.bq.query(sql, location=self.settings.location).result().to_dataframe()

    # Summarize health results -> HealthAlertSummary.
    def summarize(self, df: pd.DataFrame) -> HealthAlertSummary:
        # If the DataFrame is empty, return a default summary.
        if df.empty:
            return HealthAlertSummary(
                total_checks=0,
                failed_critical=0,
                failed_warning=0,
                latest_check_ts="unknown",
                failed_rows=df,
            )

        failed = df[df["success"] == False].copy() # Filter out successful checks.
        failed_critical = int(((failed["severity"] == "critical")).sum()) # Count critical failures.
        failed_warning = int(((failed["severity"] == "warning")).sum()) # Count warning failures.

        latest_check_ts = str(pd.to_datetime(df["check_ts"], utc=True).max()) # Get the latest check timestamp.

        # Return the summary.
        return HealthAlertSummary(
            total_checks=len(df),
            failed_critical=failed_critical,
            failed_warning=failed_warning,
            latest_check_ts=latest_check_ts,
            failed_rows=failed,
        )

    # Design the Slack payload for the health alert.
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

        # Build the failed lines(get the first 10 rows).
        failed_lines = []
        for _, row in summary.failed_rows.head(10).iterrows():
            failed_lines.append(
                f"• `{row['severity']}` `{row['check_id']}` — {row['message']}"
            )

        # If there are no failed lines, use a default message.
        if not failed_lines:
            failed_text = "No failed checks."
        else:
            failed_text = "\n".join(failed_lines)

        # Build the Slack payload.
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
                            "text": f"*Latest check:*\n`{summary.latest_check_ts}`",
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
    
    # Run the health alert.
    def run(self, recent_minutes: int, only_on_failure: bool, fail_on_critical: bool) -> int:
        df = self.load_recent_health_results(recent_minutes=recent_minutes) # Load recent health results.
        summary = self.summarize(df) # Summarize the results.

        # Print the summary.
        print(
            "[slack-alert] "
            f"total_checks={summary.total_checks}, "
            f"failed_critical={summary.failed_critical}, "
            f"failed_warning={summary.failed_warning}, "
            f"latest_check_ts={summary.latest_check_ts}"
        )

        should_send = True
        if only_on_failure:
            should_send = summary.failed_critical > 0 or summary.failed_warning > 0

        if should_send:
            # Build the Slack payload.
            payload = self.build_slack_payload(summary)
            self.slack.post_message(payload) # Send the Slack payload.
            print("[slack-alert] Slack alert sent.")
        else:
            print("[slack-alert] No failure found. Slack alert skipped.")

        # Check if there are critical failures.
        if fail_on_critical and summary.failed_critical > 0:
            print("[slack-alert] Critical failures found.")
            return 1

        return 0
