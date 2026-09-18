"""
Slack Sender — Sends rich alert messages via Slack Incoming Webhook.

Formats alerts using Slack Block Kit & color attachments:
- Urgent indicator and subject header
- Fields: From, Category, Confidence, AI Explanation
- 1-2 sentence Summary
- Code block preview of the email
"""

import logging
from typing import Optional
import requests

logger = logging.getLogger(__name__)


class SlackSender:
    """
    Sends formatted alert messages to a Slack channel via Incoming Webhook.

    Usage:
        sender = SlackSender(webhook_url="https://hooks.slack.com/services/...")
        sender.send_alert(email_data, classification)
    """

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url.strip()
        logger.info("Slack sender initialized")

    def send_alert(
        self,
        email_data: dict,
        classification: Optional[dict] = None,
    ) -> bool:
        """
        Send a formatted email alert to Slack.

        Args:
            email_data: Dict with sender, subject, date, snippet
            classification: Optional dict with category, reason, summary, confidence

        Returns:
            True if message was sent successfully, False otherwise
        """
        payload = self._build_slack_payload(email_data, classification)
        return self._send_payload(payload)

    def _build_slack_payload(
        self, email_data: dict, classification: Optional[dict] = None
    ) -> dict:
        """Construct Slack Block Kit & attachment payload."""
        subject = email_data.get("subject", "(No Subject)")
        sender = email_data.get("sender", "Unknown")
        date_str = email_data.get("date", "Unknown")
        snippet = email_data.get("snippet", "")

        category = "Important"
        confidence_str = "N/A"
        reason = "Marked as important by AI Agent"
        summary = "No summary available"

        if classification:
            category = str(classification.get("category", "Important"))
            conf = classification.get("confidence", 1.0)
            confidence_str = f"{conf:.0%}" if isinstance(conf, (int, float)) else str(conf)
            reason = str(classification.get("reason", ""))
            summary = str(classification.get("summary", ""))

        # Build Slack Block Kit
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 Urgent Email Alert",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*📌 Subject:*\n{subject}"},
                    {"type": "mrkdwn", "text": f"*📧 From:*\n`{sender}`"},
                ],
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*📂 Category:*\n{category}"},
                    {"type": "mrkdwn", "text": f"*📊 Confidence:*\n{confidence_str}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*💡 Reason:*\n{reason}\n\n*📝 Summary:*\n{summary}",
                },
            },
        ]

        if snippet:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📄 Preview:*\n```{snippet[:600]}```",
                },
            })

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📅 Received: {date_str}  |  🤖 Processed by Gmail Alert Agent (Groq AI)",
                }
            ],
        })

        return {
            "text": f"🚨 Important Email: {subject} from {sender}",
            "attachments": [
                {
                    "color": "#E01E5A",  # Urgent Slack red
                    "blocks": blocks,
                }
            ],
        }

    def _send_payload(self, payload: dict) -> bool:
        """Post the JSON payload to the Slack Webhook URL."""
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 200 and response.text.strip().lower() == "ok":
                logger.info("Slack alert sent successfully!")
                return True
            else:
                logger.error(
                    f"Slack Webhook error (HTTP {response.status_code}): {response.text}"
                )
                return False

        except requests.exceptions.Timeout:
            logger.error("Slack Webhook request timed out")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to Slack Webhook URL")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Slack alert: {e}")
            return False

    def send_startup_message(self) -> bool:
        """Send a clean startup message to the Slack channel."""
        payload = {
            "text": "🟢 *Gmail Alert Agent Started*",
            "attachments": [
                {
                    "color": "#2EB67D",  # Green
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "🟢 *Gmail Alert Agent is now running!*\nMonitoring your Gmail inbox for urgent & important emails. Alerts will be posted here.",
                            },
                        }
                    ],
                }
            ],
        }
        return self._send_payload(payload)
