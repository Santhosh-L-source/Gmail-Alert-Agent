"""
Condition Check — If gate that routes emails based on AI classification.

Mirrors the "If" node in the flow diagram:
  - true  -> email is important -> pass to Slack alert sender
  - false -> email is not important -> skip
"""

import logging
from dataclasses import dataclass
from src.ai_agent import ClassificationResult

logger = logging.getLogger(__name__)


@dataclass
class ConditionResult:
    """Result of the condition check."""
    should_send: bool
    email_data: dict
    classification: ClassificationResult
    reason: str


class Condition:
    """
    If-condition gate that decides whether to trigger a Slack alert.

    Routes based on the AI Agent's classification result:
      - is_important == True  -> should_send = True  (-> Slack)
      - is_important == False -> should_send = False (-> skip)

    Usage:
        condition = Condition(min_confidence=0.0)
        result = condition.check(email_data, classification)
        if result.should_send:
            slack_sender.send_alert(...)
    """

    def __init__(self, min_confidence: float = 0.0):
        """
        Args:
            min_confidence: Minimum confidence threshold to trigger alert.
                            Set to 0.0 to trust the LLM's binary decision.
                            Set higher (e.g., 0.7) to only alert on high-confidence items.
        """
        self.min_confidence = min_confidence

    def check(
        self, email_data: dict, classification: ClassificationResult
    ) -> ConditionResult:
        """
        Evaluate whether the email should trigger a Telegram alert.

        Args:
            email_data: Original email data dict
            classification: AI Agent's classification result

        Returns:
            ConditionResult with routing decision
        """
        should_send = classification.is_important

        # Apply confidence threshold if set
        if should_send and classification.confidence < self.min_confidence:
            should_send = False
            reason = (
                f"Email classified as important but confidence ({classification.confidence:.0%}) "
                f"is below threshold ({self.min_confidence:.0%}). Skipping."
            )
            logger.info(f"  {reason}")
        elif should_send:
            reason = (
                f"IMPORTANT -- {classification.category}: {classification.reason}"
            )
            logger.info(
                f"  Condition: TRUE -> Sending Slack alert "
                f"(confidence: {classification.confidence:.0%})"
            )
        else:
            reason = f"Not important -- {classification.category}: {classification.reason}"
            logger.info(f"  Condition: FALSE -> Skipping email")

        return ConditionResult(
            should_send=should_send,
            email_data=email_data,
            classification=classification,
            reason=reason,
        )
