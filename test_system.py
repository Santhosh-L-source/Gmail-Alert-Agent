"""
System Verification Suite — Tests all pipeline components end-to-end.
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Windows console UTF-8 fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv(override=True)

from src.main import load_config
from src.gmail_trigger import GmailTrigger
from src.ai_agent import AIAgent
from src.condition import Condition
from src.slack_sender import SlackSender


def run_all_tests():
    print("=" * 65)
    print(" 🧪 GMAIL ALERT AGENT - SYSTEM VERIFICATION SUITE")
    print("=" * 65)

    passed = 0
    total = 5

    # ── Test 1: Configuration ────────────────────────────────────────────────
    print("\n[TEST 1/5] Checking Configuration & Environment...")
    try:
        config = load_config()
        print(f"  ✅ Config loaded successfully")
        print(f"     • Gmail: {config['GMAIL_EMAIL']}")
        print(f"     • Groq Model: {config['GROQ_MODEL']}")
        print(f"     • Webhook: {config['SLACK_WEBHOOK_URL'][:40]}...")
        passed += 1
    except Exception as e:
        print(f"  ❌ Config test failed: {e}")

    # ── Test 2: Slack Webhook ────────────────────────────────────────────────
    print("\n[TEST 2/5] Testing Slack Webhook Connectivity...")
    try:
        slack = SlackSender(config["SLACK_WEBHOOK_URL"])
        res = slack.send_startup_message()
        if res:
            print("  ✅ Slack Webhook connection verified (sent startup message to #new-channel)")
            passed += 1
        else:
            print("  ❌ Slack Webhook failed to deliver")
    except Exception as e:
        print(f"  ❌ Slack test failed: {e}")

    # ── Test 3: Gmail IMAP ───────────────────────────────────────────────────
    print("\n[TEST 3/5] Testing Gmail IMAP Authentication & Inbox Search...")
    try:
        gmail = GmailTrigger(config["GMAIL_EMAIL"], config["GMAIL_APP_PASSWORD"])
        emails = gmail.fetch_new_emails(max_emails=2)
        print(f"  ✅ Gmail IMAP connected and fetched {len(emails)} sample unread email(s)")
        passed += 1
    except Exception as e:
        print(f"  ❌ Gmail IMAP test failed: {e}")

    # ── Test 4: Groq AI Classification ───────────────────────────────────────
    print("\n[TEST 4/5] Testing Groq AI LLM Model & JSON Output...")
    try:
        ai = AIAgent(config["GROQ_API_KEY"], config["GROQ_MODEL"])
        sample_email = {
            "sender": "Hiring Manager <recruiting@techcorp.com>",
            "subject": "Final Interview Schedule - Senior AI Engineer",
            "body": "Please confirm if you are available for the interview on Monday at 10 AM.",
            "date": "2026-09-18",
        }
        res = ai.classify_email(sample_email)
        print(f"  ✅ Groq AI classified sample email:")
        print(f"     • Important: {res.is_important}")
        print(f"     • Category: {res.category}")
        print(f"     • Confidence: {res.confidence:.0%}")
        print(f"     • Reason: {res.reason}")
        if res.is_important:
            passed += 1
        else:
            print("  ⚠️ Warning: Sample interview email was unexpectedly classified as not important")
    except Exception as e:
        print(f"  ❌ Groq AI test failed: {e}")

    # ── Test 5: End-to-End Pipeline Routing ──────────────────────────────────
    print("\n[TEST 5/5] Testing If-Condition Gate & Alert Dispatch...")
    try:
        cond = Condition(min_confidence=0.0)
        route_res = cond.check(sample_email, res)
        if route_res.should_send:
            alert_ok = slack.send_alert(
                sample_email,
                {
                    "category": res.category,
                    "confidence": res.confidence,
                    "reason": res.reason,
                    "summary": res.summary,
                },
            )
            if alert_ok:
                print("  ✅ If-Condition passed and dispatched alert to Slack successfully")
                passed += 1
            else:
                print("  ❌ Slack delivery failed during pipeline dispatch")
        else:
            print("  ❌ Condition routing blocked the alert")
    except Exception as e:
        print(f"  ❌ Pipeline test failed: {e}")

    # ── Final Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f" 📊 TEST RESULTS: {passed}/{total} PASSED")
    print("=" * 65)
    if passed == total:
        print(" 🎉 ALL SYSTEMS ARE FUNCTIONING PERFECTLY!\n")
    else:
        print(f" ⚠️ {total - passed} test(s) failed. Check details above.\n")


if __name__ == "__main__":
    run_all_tests()
