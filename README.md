# SIH Internal Mail Automator

A production-quality bulk email automation tool developed for the Internal Smart India Hackathon (SIH) selection round at IIIT Bhopal.

This tool compiles student details from a CSV file, validates team compositions, and dispatches rich, responsive HTML emails to team leaders with a text fallback. It supports three lifecycle templates, sequential certificate attachment loops, and includes an isolated sandbox environment.

---

## 🛠️ CLI Arguments and Usage

The entry-point is `src/send_mails.py` which takes two mandatory flags:

```bash
python -m src.send_mails --template {invitation|reminder|thankyou} --mode {test|dry-run|live} [--force] [--csv CUSTOM_PATH]
```

### 1. Templates (`--template`)
* **`invitation`**: Dispatches the initial team details, event schedule, and condensed guidelines (Template 1).
* **`reminder`**: Nudges teams the day before the event with checklists and coordinates (Template 2).
* **`thankyou`**: Sends participation appreciation and automatically attaches 6 individual certificates per team (Template 3).

### 2. Execution Modes (`--mode`)
* **`test`**: Runs real sends against sandbox data `/test/test_teams.csv` and `/test/certificates/`. **Enforces NO coordinator CCs for safety.**
* **`dry-run`**: Compiles preview HTML emails to disk (`/preview/{template_name}/`) without sending actual emails.
* **`live`**: Production mode using real CSV data and certificate pools, with CCs to Dr. Sourabh Jain and Rekha Kaushik.

---

## 📊 Roster Data Schema (CSV)

Each row in the CSV contains:

| Column | Status | Description / Notes |
|---|---|---|
| `team_number` | **Required** | Sequential, zero-padded integer string (e.g. `01`, `02`, `03`...) |
| `team_name` | Optional | Team Name (defaults to "Unnamed Team") |
| `leader_details` | **Required** | Formatted string: `Name, Scholar ID, Phone, Email, Gender` |
| `member_2_details` ... `member_6_details` | Optional | Student details matching leader's format for other members |
| `problem_theme` | Optional | Problem theme selected by the team |
| `track` | Optional | Track/Category (e.g. `Software` / `Hardware`) |

### Generate Mock Production CSV
To regenerate a mock test CSV dataset containing 3 valid teams and 3 invalid rows:
```bash
python src/csv_loader.py
```
This generates mock data at `data/sample_teams_test.csv`.

---

## 📜 Certificate Assignment Rules

For Template 3 (`thankyou`), certificates are stored in `/data/certificates/` (or `/test/certificates/` in test mode) using 3-digit zero-padded filenames (`001.png`, `002.png`, ...).

* **Assignment formula**: For a team at sequential integer position `n` (parsed from `team_number`), the files attached are `((n-1)*6 + 1)` through `(n*6)`.
  * Team `01` ➔ `001.png` to `006.png`
  * Team `02` ➔ `007.png` to `012.png`
  * Team `n` ➔ `((n-1)*6+1)` to `(n*6)`
* **Validation**: The tool checks file existence on disk before attempting to email. If any certificate is missing, it logs a warning/error and skips that team to avoid partial or incorrect delivery.

---

## 🧪 Isolated Sandbox Testing (`--mode test`)

To ensure development changes never accidentally email coordinators or pollute production records, we run inside a sandbox environment:

1. **Test Data**: Reads from `test/test_teams.csv` (exactly 2 rows, pointing to test inboxes) and `test/certificates/`.
2. **Generate Test Certificates**: To compile the 12 placeholder PNG files (`001.png`–`012.png`):
   ```bash
   python test/generate_test_certificates.py
   ```
3. **Run Test Send**:
   ```bash
   python -m src.send_mails --mode test --template thankyou
   ```
   * Enforces `cc = []` in the code, guaranteeing coordinators are not CC'd.
   * Outputs logging records to `test_send_log.csv`.

---

## 🔒 Security & SMTP setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Configure credentials in `.env`:
   * Set `SMTP_USERNAME=your-username@gmail.com` and `SMTP_PASSWORD=your-google-app-password`.
3. Set `DRY_RUN=true` to preview HTML, or specify `TEST_RECIPIENT` to redirect dry-run SMTP sends to a safe mailbox.
