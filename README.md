# 📧 Gmail Alert Agent

An intelligent email monitoring agent that watches your Gmail inbox, uses **Groq AI** to classify email importance, and sends instant alerts to your **Slack channel**.

## 🔄 Flow

```
Gmail Trigger (IMAP) → AI Agent (Groq) → If (is_important?) → Slack Alert
```

| Component | Description |
|-----------|-------------|
| **Gmail Trigger** | Polls Gmail IMAP for new unread emails (newest first) |
| **AI Agent** | Uses Groq LLM (`openai/gpt-oss-20b`) to classify email importance |
| **If Condition** | Routes important emails to Slack, skips non-urgent mail |
| **Slack Sender** | Posts rich Block Kit alerts to your Slack channel |

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.10+**
- A **Gmail account** with an [App Password](https://myaccount.google.com/apppasswords)
- A **Groq API key** ([get one here](https://console.groq.com/keys))
- A **Slack Webhook URL** ([create an incoming webhook](https://api.slack.com/messaging/webhooks))

### 2. Install Dependencies

```bash
cd Gmail_Alert_Agent
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and set:

```env
GROQ_API_KEY=gsk_...
GMAIL_EMAIL=you@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 4. Run the Agent

```bash
python -m src.main
```

### 5. Clean Unwanted Emails (Optional)

To scan and move existing promotional/spam/marketing emails to your Gmail Trash:

```bash
python clean_unwanted_emails.py
```

## 📂 Project Structure

```
Gmail_Alert_Agent/
├── .env                    # API keys & Slack Webhook URL (gitignored)
├── .env.example            # Template for keys
├── .gitignore
├── requirements.txt
├── README.md
├── clean_unwanted_emails.py # Cleans promotional/spam mail to Trash
├── send_test_email.py       # Sends a test urgent email via SMTP
└── src/
    ├── __init__.py
    ├── main.py             # Entry point — runs the polling loop
    ├── gmail_trigger.py    # Gmail IMAP polling (newest first)
    ├── ai_agent.py         # Groq LLM email classification
    ├── condition.py        # If-gate routing logic
    └── slack_sender.py     # Slack Block Kit webhook sender
```

## 🤖 What Gets Classified as Important?

| 🔴 IMPORTANT (Alerted & Kept) | ⚪ NOT IMPORTANT (Skipped / Cleaned) |
|-------------------------------|--------------------------------------|
| 🏆 Hackathons & Competitions (Devpost, Unstop, Kaggle) | Marketing newsletters |
| 💻 Coding Contests (Codeforces, LeetCode, AtCoder) | Commercial sales & discounts |
| 💼 Work & Manager Communications | Social media notifications |
| 🎓 Job & Interview Invitations | Generic promotional blasts |
| 🔒 Security Alerts & OTPs | Spam & junk |
| 💰 Financial & Bank Alerts | |
