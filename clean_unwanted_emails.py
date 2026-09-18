"""
Clean Unwanted Emails — Moves marketing, spam, newsletters, and test emails to Trash.

Uses Groq AI to classify each email and safely moves unwanted ones to Gmail Trash/Bin
(recoverable for 30 days in your Gmail Bin).
"""

import os
import sys
import imaplib
import email
from email.header import decode_header
from email.message import Message
import logging
from dotenv import load_dotenv

# Windows console UTF-8 fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

from src.ai_agent import AIAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Cleaner")


def decode_header_val(val: str) -> str:
    if not val:
        return ""
    parts = decode_header(val)
    res = []
    for part, charset in parts:
        if isinstance(part, bytes):
            res.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            res.append(str(part))
    return " ".join(res)


def extract_text(msg: Message) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
    else:
        if msg.get_content_type() == "text/plain":
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
    return body[:2000].strip()


def get_trash_folder_name(conn: imaplib.IMAP4_SSL) -> str:
    """Find the exact IMAP Trash folder name in this Gmail account."""
    status, folders = conn.list()
    if status == "OK":
        for folder in folders:
            folder_str = folder.decode("utf-8", errors="replace")
            if "\\Trash" in folder_str or "[Gmail]/Trash" in folder_str or "[Gmail]/Bin" in folder_str:
                # Extract quoted name at the end
                name = folder_str.split(' "/" ')[-1].strip('"')
                return name
    return "[Gmail]/Trash"


def clean_inbox(batch_size: int = 50):
    gmail_email = os.getenv("GMAIL_EMAIL")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    groq_api_key = os.getenv("GROQ_API_KEY")
    groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    if not gmail_email or not gmail_password or not groq_api_key:
        logger.error("Missing credentials in .env")
        return

    logger.info("Connecting to Gmail IMAP...")
    conn = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    conn.login(gmail_email, gmail_password)

    trash_folder = get_trash_folder_name(conn)
    logger.info(f"Using Trash folder: {trash_folder}")

    ai = AIAgent(api_key=groq_api_key, model=groq_model)

    conn.select("INBOX")
    status, data = conn.search(None, "UNSEEN")
    if status != "OK" or not data[0]:
        logger.info("No unread emails found to clean.")
        conn.logout()
        return

    email_ids = data[0].split()
    total_unseen = len(email_ids)
    logger.info(f"Found {total_unseen} unread email(s). Processing batch of {min(batch_size, total_unseen)}...")

    # Process newest first
    batch_ids = email_ids[::-1][:batch_size]

    trashed_count = 0
    kept_count = 0

    print("\n" + "=" * 65)
    print(" 🧹 CLEANING UNWANTED EMAILS (Moving to Trash/Bin) ")
    print("=" * 65 + "\n")

    for i, eid in enumerate(batch_ids, 1):
        status, msg_data = conn.fetch(eid, "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            continue

        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        sender = decode_header_val(msg.get("From", ""))
        subject = decode_header_val(msg.get("Subject", "(No Subject)"))
        body = extract_text(msg)

        email_data = {
            "sender": sender,
            "subject": subject,
            "body": body,
            "date": msg.get("Date", ""),
        }

        # Check if it's our test email
        is_test_email = "Technical Interview Invitation" in subject and "Recruitment Team" in sender

        # Check if it's a Hackathon / Coding Contest / Challenge update
        hackathon_keywords = [
            "hackathon", "hack", "devpost", "datathon", "ml challenge",
            "coding contest", "codeforces", "leetcode", "atcoder", "hackerearth",
            "hack2skill", "unstop", "hackerank", "hackerrank", "kaggle",
            "competition", "cohort"
        ]
        is_hackathon = any(kw in subject.lower() or kw in sender.lower() for kw in hackathon_keywords)

        if is_test_email:
            logger.info(f"[{i}/{len(batch_ids)}] 🗑️  TEST EMAIL -> Trashing: \"{subject}\"")
            conn.copy(eid, f'"{trash_folder}"')
            conn.store(eid, "+FLAGS", "\\Deleted")
            trashed_count += 1
            continue

        if is_hackathon:
            logger.info(f"[{i}/{len(batch_ids)}] 🏆  KEEPING HACKATHON / CONTEST UPDATE: \"{subject[:50]}\"")
            kept_count += 1
            continue

        # Classify with AI
        res = ai.classify_email(email_data)

        if not res.is_important or res.category in ["Marketing", "Newsletter", "Promotions", "Social", "Spam"]:
            logger.info(f"[{i}/{len(batch_ids)}] 🗑️  UNWANTED ({res.category}) -> Trashing: \"{subject[:45]}\"")
            logger.info(f"         Reason: {res.reason}")
            # Move to Trash
            conn.copy(eid, f'"{trash_folder}"')
            conn.store(eid, "+FLAGS", "\\Deleted")
            trashed_count += 1
        else:
            logger.info(f"[{i}/{len(batch_ids)}] 🛡️  KEEPING IMPORTANT ({res.category}): \"{subject[:45]}\"")
            kept_count += 1

        # Respect Groq rate limits smoothly
        import time
        time.sleep(1.5)

    # Expunge deleted from INBOX
    conn.expunge()
    conn.logout()

    print("\n" + "=" * 65)
    print(" 📊 CLEANING SUMMARY")
    print("=" * 65)
    print(f"  🗑️  Moved to Trash: {trashed_count} emails")
    print(f"  🛡️  Kept in Inbox:  {kept_count} emails")
    print("  ℹ️   Trashed emails can be restored from your Gmail Trash/Bin anytime for 30 days.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    # Clean top 30 unread emails
    clean_inbox(batch_size=30)
