"""
AI Agent — Uses Groq Chat Model to classify email importance.

Sends email content to Groq API with a structured prompt, and returns
a classification: IMPORTANT or NOT_IMPORTANT, along with a reason and summary.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from groq import Groq

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an intelligent email classification agent. Your job is to analyze incoming emails and determine if they are IMPORTANT and require the user's urgent attention.

## Classification Rules

An email is **IMPORTANT** if it matches ANY of the following:
- 🔴 **Urgent requests** — deadlines, time-sensitive actions, emergencies
- 💼 **Work-critical** — from a boss/manager/client, project updates, meeting changes
- 🏆 **Hackathons & Competitions** — Hackathon updates, Devpost, Unstop competitions, coding contests (LeetCode/Codeforces/AtCoder), Datathons, ML challenges, hackathon deadlines/invitations
- 💰 **Financial** — bank alerts, payment issues, invoice due, suspicious activity
- 🏥 **Health/Safety** — medical appointments, emergency contacts, security alerts
- 📋 **Action required** — password resets, account verifications, legal documents
- 🎓 **Interview/Job** — interview invitations, offer letters, job-related updates
- 📦 **Important deliveries** — order issues, delivery failures, shipping problems

An email is **NOT_IMPORTANT** if it matches:
- 📢 Marketing newsletters, promotional offers, commercial sales
- 🔔 Social media notifications (unless direct job/urgent message)
- 📊 Generic spam or junk content
- 📰 General commercial news digests

## Response Format

You MUST respond with valid JSON only. No markdown, no explanation outside the JSON.

{
    "is_important": true or false,
    "confidence": 0.0 to 1.0,
    "category": "short category label",
    "reason": "Brief explanation of why this email is or isn't important",
    "summary": "1-2 sentence summary of the email content"
}
"""


@dataclass
class ClassificationResult:
    """Result of AI email classification."""
    is_important: bool
    confidence: float
    category: str
    reason: str
    summary: str
    raw_response: str = ""

    @classmethod
    def from_dict(cls, data: dict, raw: str = "") -> "ClassificationResult":
        return cls(
            is_important=data.get("is_important", False),
            confidence=data.get("confidence", 0.0),
            category=data.get("category", "Unknown"),
            reason=data.get("reason", "No reason provided"),
            summary=data.get("summary", "No summary available"),
            raw_response=raw,
        )

    @classmethod
    def error_result(cls, error_msg: str) -> "ClassificationResult":
        """Return a safe fallback result when classification fails."""
        return cls(
            is_important=True,  # Fail-safe: treat as important if unsure
            confidence=0.0,
            category="Error",
            reason=f"Classification failed: {error_msg}. Defaulting to important.",
            summary="Could not classify email",
            raw_response="",
        )


class AIAgent:
    """
    AI Agent powered by Groq Chat Model.

    Classifies emails as important or not important using LLM reasoning.

    Usage:
        agent = AIAgent(api_key="gsk_...", model="openai/gpt-oss-20b")
        result = agent.classify_email(email_data)
    """

    def __init__(self, api_key: str, model: str = "openai/gpt-oss-20b"):
        self.client = Groq(api_key=api_key)
        self.model = model
        logger.info(f"AI Agent initialized with model: {self.model}")

    def classify_email(self, email_data: dict) -> ClassificationResult:
        """
        Classify an email's importance using the Groq Chat Model.

        Args:
            email_data: Dict with keys: sender, subject, date, body/snippet

        Returns:
            ClassificationResult with importance classification
        """
        # Build the user prompt with email details
        user_prompt = self._build_prompt(email_data)

        try:
            logger.info(f"Classifying email: \"{email_data.get('subject', 'N/A')}\"")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,  # Low temp for consistent classification
                max_tokens=600,
                response_format={"type": "json_object"},
            )

            raw_content = response.choices[0].message.content.strip()
            logger.debug(f"Raw AI response: {raw_content}")

            # Parse the JSON response
            result_data = json.loads(raw_content)
            result = ClassificationResult.from_dict(result_data, raw=raw_content)

            label = "IMPORTANT" if result.is_important else "NOT IMPORTANT"
            logger.info(
                f"  Classification: {label} "
                f"(confidence: {result.confidence:.0%}) -- {result.category}"
            )
            logger.info(f"  Reason: {result.reason}")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return ClassificationResult.error_result(f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return ClassificationResult.error_result(str(e))

    def _build_prompt(self, email_data: dict) -> str:
        """Build a structured prompt from email data."""
        return f"""Analyze the following email and classify its importance:

---
**From:** {email_data.get('sender', 'Unknown')}
**Subject:** {email_data.get('subject', '(No Subject)')}
**Date:** {email_data.get('date', 'Unknown')}

**Body:**
{email_data.get('body', email_data.get('snippet', '(No content)'))}
---

Classify this email as IMPORTANT or NOT_IMPORTANT. Respond with JSON only."""
