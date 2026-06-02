# This allows you to use advanced type hinting without errors, unlike older Python versions.
from __future__ import annotations

import json
import urllib.error
import urllib.request


class SlackWebhookClient:
    # Initialize the SlackWebhookClient with a webhook URL.
    def __init__(self, webhook_url: str):
        if not webhook_url:
            raise ValueError("Slack webhook URL is empty.")
        self.webhook_url = webhook_url
    
    # Post a message to Slack using the webhook URL.
    def post_message(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8") # Encode the payload as JSON.

        request = urllib.request.Request(
            self.webhook_url, # mailing address
            data=data, # data to send
            headers={"Content-Type": "application/json"}, # declare the sending format.
            method="POST", # The `post` method is used to send/create new data.
        )

        # Check and fix any errors that occur during the process of sending messages to Slack.
        try:
            # Send the data to the server(wait 20 seconds for the response).
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8", errors="replace") # Read the response.
                # Check if the response is valid.
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(
                        f"Slack webhook failed: status={response.status}, body={body}"
                    )
        # Handle any errors that may occur during the request.
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Slack webhook failed: status={exc.code}, body={body}"
            ) from exc
