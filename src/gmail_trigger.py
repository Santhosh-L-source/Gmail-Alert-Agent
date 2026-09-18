"""
Gmail Trigger — Polls Gmail via IMAP for new unread emails.

Connects using App Password authentication, fetches UNSEEN messages (newest first),
extracts sender/subject/date/body, and marks them as SEEN after processing.
"""

import imaplib
import email
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Represents a parsed email message."""
    uid: str
    sender: str
    subject: str
    date: Optional[datetime]
    body: str
    snippet: str = field(init=False)

    def __post_init__(self):
        # Create a short snippet (first 300 chars) for display
        self.snippet = self.body[:300].strip().replace("\n", " ")

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "sender": self.sender,
            "subject": self.subject,
            "date": self.date.isoformat() if self.date else "Unknown",
            "body": self.body,
            "snippet": self.snippet,
        }


class GmailTrigger:
    """
    Polls Gmail IMAP for new unread emails.

    Usage:
        trigger = GmailTrigger(email_addr, app_password)
        emails = trigger.fetch_new_emails(max_emails=10)
    """

    IMAP_SERVER = "imap.gmail.com"
    IMAP_PORT = 993

    def __init__(self, email_address: str, app_password: str):
        self.email_address = email_address
        self.app_password = app_password
        self._connection: Optional[imaplib.IMAP4_SSL] = None

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Establish IMAP SSL connection to Gmail."""
        try:
            conn = imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT)
            conn.login(self.email_address, self.app_password)
            logger.info("Connected to Gmail IMAP successfully")
            return conn
        except imaplib.IMAP4.error as e:
            logger.error(f"Gmail IMAP login failed: {e}")
            raise ConnectionError(
                f"Failed to connect to Gmail. Check your email and App Password. Error: {e}"
            )

    def _decode_header_value(self, value: str) -> str:
        """Decode an email header value (handles encoded subjects/senders)."""
        if value is None:
            return ""
        decoded_parts = decode_header(value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return " ".join(result)

    def _extract_body(self, msg: Message) -> str:
        """Extract plain text body from an email message."""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode(charset, errors="replace")
                            break
                    except Exception as e:
                        logger.warning(f"Failed to decode email part: {e}")
                        continue
        else:
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                try:
                    charset = msg.get_content_charset() or "utf-8"
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body = payload.decode(charset, errors="replace")
                except Exception as e:
                    logger.warning(f"Failed to decode email body: {e}")

        # Truncate very long emails to avoid token waste
        max_length = 3000
        if len(body) > max_length:
            body = body[:max_length] + "\n... [truncated]"

        return body.strip()

    def _parse_email(self, uid: str, raw_email: bytes) -> Optional[EmailMessage]:
        """Parse raw email bytes into an EmailMessage object."""
        try:
            msg = email.message_from_bytes(raw_email)

            sender = self._decode_header_value(msg.get("From", ""))
            subject = self._decode_header_value(msg.get("Subject", "(No Subject)"))
            date_str = msg.get("Date", "")

            # Parse date
            email_date = None
            if date_str:
                try:
                    email_date = parsedate_to_datetime(date_str)
                except Exception:
                    logger.warning(f"Could not parse date: {date_str}")

            body = self._extract_body(msg)

            return EmailMessage(
                uid=uid,
                sender=sender,
                subject=subject,
                date=email_date,
                body=body,
            )
        except Exception as e:
            logger.error(f"Failed to parse email UID {uid}: {e}")
            return None

    def fetch_new_emails(self, max_emails: int = 15) -> list[EmailMessage]:
        """
        Fetch unread emails from the INBOX (newest first).

        Args:
            max_emails: Maximum number of recent unread emails to process per cycle.
        """
        emails = []
        conn = None

        try:
            conn = self._connect()
            conn.select("INBOX")

            # Search for unseen (unread) emails
            status, data = conn.search(None, "UNSEEN")
            if status != "OK":
                logger.warning("No unread emails or search failed")
                return emails

            email_ids = data[0].split()
            if not email_ids:
                logger.info("No new unread emails found")
                return emails

            total_unread = len(email_ids)
            # Reverse order so we fetch newest first
            recent_ids = email_ids[::-1][:max_emails]

            logger.info(
                f"Found {total_unread} unread email(s). Processing top {len(recent_ids)} newest..."
            )

            for email_id in recent_ids:
                try:
                    # Fetch the email & mark as SEEN
                    status, msg_data = conn.fetch(email_id, "(RFC822)")
                    if status != "OK" or not msg_data or not msg_data[0]:
                        continue

                    raw_email = msg_data[0][1]
                    uid = email_id.decode("utf-8")
                    parsed = self._parse_email(uid, raw_email)

                    if parsed:
                        logger.info(
                            f"  [{parsed.uid}] From: {parsed.sender} | "
                            f"Subject: {parsed.subject}"
                        )
                        emails.append(parsed)

                except Exception as e:
                    logger.error(f"Error fetching email {email_id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Gmail polling error: {e}")
        finally:
            if conn:
                try:
                    conn.logout()
                except Exception:
                    pass

        return emails
