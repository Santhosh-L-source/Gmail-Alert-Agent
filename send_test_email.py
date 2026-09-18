"""
Send a test urgent email using Gmail SMTP to verify the pipeline.
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
    print("[ERROR] Missing GMAIL_EMAIL or GMAIL_APP_PASSWORD in .env")
    exit(1)

msg = MIMEMultipart()
msg["From"] = f"Recruitment Team <{GMAIL_EMAIL}>"
msg["To"] = GMAIL_EMAIL
msg["Subject"] = "URGENT: Technical Interview Invitation - Senior Software Engineer Role"

body = """Dear Santhosh,

Congratulations! Following your recent application, we are pleased to invite you for the Final Round Technical Interview for the Senior Software Engineer position.

Interview Details:
- Date: Tomorrow at 2:00 PM IST
- Duration: 45 minutes
- Platform: Google Meet
- Meeting Link: https://meet.google.com/abc-defg-hij

Please reply to this email within 24 hours to confirm your availability. This is time-sensitive.

Best regards,
Google Talent Acquisition Team
"""

msg.attach(MIMEText(body, "plain"))

try:
    print("Connecting to Gmail SMTP server (smtp.gmail.com:587)...")
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
    server.send_message(msg)
    server.quit()
    print("[SUCCESS] Test email sent successfully to " + str(GMAIL_EMAIL))
except Exception as e:
    print(f"[ERROR] Failed to send email: {e}")
