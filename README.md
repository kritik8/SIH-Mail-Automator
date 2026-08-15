# SIH Internal Mail Automator

A production-quality bulk email automation tool developed for the Internal Smart India Hackathon (SIH) selection round at IIIT Bhopal.

This tool compiles student details from a CSV file, validates team compositions, and dispatches rich, responsive HTML emails to team leaders with a text fallback. It features:
- **Dry-run mode** (default) to locally render and preview emails before sending.
- **Test redirection** to forward mock emails to a single test address.
- **State-aware idempotency** to automatically resume runs, skipping already emailed recipients.
- **SMTP connection resilience** with automatic retry backoff for transient issues.
- **Throttling/Rate Limiting** to prevent SMTP blockages and filter flags.

---

## 🛠️ Setup & Installation

### 1. Prerequisites
Ensure you have Python 3.8+ installed.

### 2. Install Dependencies
Clone the repository, then install requirements:
```bash
pip install -r requirements.txt
```

### 3. Configure Credentials (`.env`)
Create a `.env` file from the example template:
```bash
cp .env.example .env
```
Fill in the configuration details inside `.env`:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-institutional-email@iiitbhopal.ac.in
SMTP_PASSWORD=your-gmail-app-password
DRY_RUN=true
TEST_RECIPIENT=your-personal-test-email@example.com
```

> 💡 **App Password Setup:** If using a Gmail or Google Workspace institutional account, you must generate an **App Password** from your Google Account settings under Security (ensure 2-Step Verification is enabled). Use this App Password instead of your regular password.

### 4. Event Configuration (`config.yaml`)
Edit `config.yaml` to specify the event date, venue, single point of contact (SPOC), and CC lists:
```yaml
event_date: "September 20, 2026" # Fill in the actual date of the Internal Hackathon
event_venue: "NTB, IIIT Bhopal"
spoc_name: "Dr. Sourabh Jain"
spoc_email: "sourabh.jain@iiitbhopal.ac.in"
cc_emails:
  - "sourabh.jain@iiitbhopal.ac.in"
  - "rekhakaushik@iiitbhopal.ac.in"
rate_limit_delay_seconds: 3.0
```

---

## 📊 Data Source Schema (CSV)

The loader parses a comma-separated file. Malformed email addresses or rows missing critical identifiers (`team_number` or `leader_email`) are skipped automatically with a warnings log, without halting the application.

| Column | Status | Description / Notes |
|---|---|---|
| `team_number` | **Required** | Unique team identifier (e.g., `SIH-042`) |
| `leader_email` | **Required** | Primary recipient address for the team invitation |
| `team_name` | Optional | Team name (defaults to "Unnamed Team") |
| `leader_name` | Optional | Greeting name (defaults to "Team Leader") |
| `member_2_name` ... `member_6_name` | Optional | Names of other student members (dynamically listed in the template) |
| `problem_statement_id` | Optional | Official SIH problem statement code (e.g., `PS-1234`) |
| `problem_statement_title` | Optional | Title of the problem statement |
| `track` | Optional | Track/Category (e.g., `Software` or `Hardware`) |

### Generate Mock Test Data
To create a realistic test dataset containing 4 valid teams and 3 invalid rows (to verify safety skipping):
```bash
python src/csv_loader.py
```
This generates mock data at `data/sample_teams_test.csv`.

---

## 🚀 Usage Guide

### 1. Perform a Local Dry Run (Recommended First Step)
By default, the script runs in dry-run mode and writes rendered HTML preview emails to the `preview/` directory:
```bash
python -m src.send_mails --csv data/sample_teams_test.csv
```
Open files inside `preview/` in your browser to inspect alignment, typography, and content.

### 2. Send Redirection Previews to a Test Mailbox
To test actual SMTP sending without emailing real team leaders, keep `DRY_RUN=true` in your `.env` but specify a `TEST_RECIPIENT`:
```bash
python -m src.send_mails --csv data/sample_teams_test.csv --test-email your-test-address@example.com
```
This sends all generated team invitations solely to `your-test-address@example.com` (and strips the CC list to prevent spamming coordinators during testing).

### 3. Go Live
When you are ready to send invites to all real team leaders (and CC coordinators):
1. Ensure the event date in `config.yaml` is correct.
2. Run the script with the `--live` flag (this overrides `.env` dry-run values):
```bash
python -m src.send_mails --csv data/real_teams.csv --live
```

---

## 🔄 Idempotency, Resuming, and Forcing Resends

- **Tracking Progress:** Every time an email is successfully sent (or previewed with redirection), a record is appended to `send_log.csv`.
- **Resuming:** If the script stops due to network loss, running it again will automatically skip team numbers marked `SUCCESS` in `send_log.csv`.
- **Resending:** To force the automator to re-email everyone regardless of what is logged:
  ```bash
  python -m src.send_mails --csv data/real_teams.csv --live --force
  ```
