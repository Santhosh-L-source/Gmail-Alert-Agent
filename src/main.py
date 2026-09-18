"""
Gmail Alert Agent — Main Pipeline Orchestrator

Flow: Gmail Trigger (IMAP) -> AI Agent (Groq) -> If Condition -> Slack Alert
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime

# Configure UTF-8 encoding for standard streams on Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv

from src.gmail_trigger import GmailTrigger
from src.ai_agent import AIAgent
from src.condition import Condition
from src.slack_sender import SlackSender

# ─── Logging Setup ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agent.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ─── Globals ─────────────────────────────────────────────────────────────────

_running = True


def _signal_handler(signum, frame):
    """Handle graceful shutdown on Ctrl+C."""
    global _running
    logger.info("\n🛑 Shutdown signal received. Stopping agent...")
    _running = False


try:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
except Exception:
    pass


# ─── Configuration ───────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load and validate configuration from .env file."""
    load_dotenv(override=True)

    required_vars = [
        "GROQ_API_KEY",
        "GMAIL_EMAIL",
        "GMAIL_APP_PASSWORD",
        "SLACK_WEBHOOK_URL",
    ]

    config = {}
    missing = []

    for var in required_vars:
        val = os.getenv(var, "").strip()
        if not val or val.startswith("your_"):
            missing.append(var)
        else:
            config[var] = val

    if missing:
        logger.error("❌ Missing required environment variables in .env:")
        for var in missing:
            logger.error(f"   • {var}")
        sys.exit(1)

    config["CHECK_INTERVAL_SECONDS"] = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
    config["GROQ_MODEL"] = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    return config


# ─── Pipeline ────────────────────────────────────────────────────────────────

def process_email(
    email_msg,
    ai_agent: AIAgent,
    condition: Condition,
    slack_sender: SlackSender,
    stats: dict,
):
    """
    Process a single email through the pipeline:
    Email -> AI Agent -> If Condition -> Slack (if important)
    """
    email_data = email_msg.to_dict()

    # Step 1: AI Agent — classify importance
    classification = ai_agent.classify_email(email_data)

    # Step 2: If Condition — route based on classification
    result = condition.check(email_data, classification)

    # Step 3: Slack Alert (if condition is true)
    if result.should_send:
        classification_data = {
            "category": classification.category,
            "confidence": classification.confidence,
            "reason": classification.reason,
            "summary": classification.summary,
        }
        success = slack_sender.send_alert(email_data, classification_data)
        if success:
            stats["alerts_sent"] += 1
        else:
            stats["errors"] += 1
    else:
        stats["skipped"] += 1


def run_agent():
    """Main agent loop — polls Gmail and posts alerts to Slack."""
    global _running

    print(flush=True)
    print("================================================================", flush=True)
    print("                📧  GMAIL ALERT AGENT  📧                       ", flush=True)
    print("       Gmail -> AI Agent (Groq) -> If -> Slack Alert            ", flush=True)
    print("================================================================", flush=True)
    print(flush=True)

    config = load_config()
    interval = config["CHECK_INTERVAL_SECONDS"]

    logger.info("Configuration loaded successfully")
    logger.info(f"   Gmail: {config['GMAIL_EMAIL']}")
    logger.info(f"   Model: {config['GROQ_MODEL']}")
    logger.info(f"   Destination: Slack Webhook")
    logger.info(f"   Poll interval: {interval}s")

    gmail = GmailTrigger(
        email_address=config["GMAIL_EMAIL"],
        app_password=config["GMAIL_APP_PASSWORD"],
    )

    ai_agent = AIAgent(
        api_key=config["GROQ_API_KEY"],
        model=config["GROQ_MODEL"],
    )

    condition = Condition(min_confidence=0.0)
    slack_sender = SlackSender(config["SLACK_WEBHOOK_URL"])

    # Send startup message to Slack
    if slack_sender.send_startup_message():
        logger.info("Startup notification sent to Slack")
    else:
        logger.warning("Could not send startup notification to Slack")

    stats = {
        "total_processed": 0,
        "alerts_sent": 0,
        "skipped": 0,
        "errors": 0,
        "cycles": 0,
        "started_at": datetime.now(),
    }

    logger.info("Agent is running! Monitoring inbox for important emails...")
    logger.info("   Press Ctrl+C to stop\n")

    while _running:
        try:
            stats["cycles"] += 1
            logger.info("-" * 50)
            logger.info(f"Poll cycle #{stats['cycles']} — {datetime.now().strftime('%H:%M:%S')}")

            new_emails = gmail.fetch_new_emails(max_emails=10)

            if new_emails:
                for email_msg in new_emails:
                    if not _running:
                        break

                    stats["total_processed"] += 1
                    logger.info(f"\nProcessing email #{stats['total_processed']}:")
                    process_email(email_msg, ai_agent, condition, slack_sender, stats)

                logger.info(
                    f"Batch complete — "
                    f"Processed: {len(new_emails)} | "
                    f"Total alerts: {stats['alerts_sent']} | "
                    f"Skipped: {stats['skipped']}"
                )
            else:
                logger.info("No new unread emails found")

            if not _running:
                break

            logger.info(f"Next check in {interval}s...")
            for _ in range(interval):
                if not _running:
                    break
                time.sleep(1)

        except KeyboardInterrupt:
            break
        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            logger.info(f"Retrying in {interval}s...")
            time.sleep(interval)

    print(flush=True)
    logger.info("Final Statistics:")
    runtime = datetime.now() - stats["started_at"]
    logger.info(f"   Runtime: {runtime}")
    logger.info(f"   Poll cycles: {stats['cycles']}")
    logger.info(f"   Emails processed: {stats['total_processed']}")
    logger.info(f"   Alerts sent to Slack: {stats['alerts_sent']}")
    logger.info(f"   Skipped: {stats['skipped']}")
    logger.info(f"   Errors: {stats['errors']}")
    logger.info("Agent stopped. Goodbye!")


if __name__ == "__main__":
    run_agent()
