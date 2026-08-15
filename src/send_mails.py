import os
import csv
import sys
import argparse
import logging
from datetime import datetime
import time
from pathlib import Path
from typing import Set

from src.config import AppConfig, ConfigError
from src.csv_loader import load_teams_from_csv, TeamData
from src.mailer import EmailRenderer, Mailer

# Set up logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("mail_automator_debug.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("app")

LOG_FILE_PATH = "send_log.csv"

def init_send_log_file() -> None:
    """Creates the send log CSV file with headers if it does not already exist."""
    path = Path(LOG_FILE_PATH)
    if not path.exists():
        with open(path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "team_number", "recipient", "status", "error"])

def get_already_sent_teams() -> Set[str]:
    """Reads the send log CSV file and returns a set of team numbers that were successfully sent."""
    sent_teams = set()
    path = Path(LOG_FILE_PATH)
    if not path.exists():
        return sent_teams
        
    with open(path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status") == "SUCCESS":
                team_num = row.get("team_number")
                if team_num:
                    sent_teams.add(team_num.strip())
    return sent_teams

def append_to_send_log(team_number: str, recipient: str, status: str, error: str = "") -> None:
    """Appends a new sending result row to the send log CSV file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, team_number, recipient, status, error])

def main() -> None:
    # 1. Setup CLI argument parsing
    parser = argparse.ArgumentParser(
        description="SIH Internal Selection Bulk Mail Automator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="data/sample_teams_test.csv",
        help="Path to the teams CSV data file"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Disable dry-run mode and send actual emails to recipients"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Resend emails to teams even if they are marked as successfully sent in the log"
    )
    parser.add_argument(
        "--test-email",
        type=str,
        default="",
        help="Override/set test email address to redirect all emails to during dry-run"
    )
    args = parser.parse_args()

    # 2. Load Configuration
    try:
        config = AppConfig()
    except ConfigError as ce:
        logger.error(f"Configuration error: {ce}")
        sys.exit(1)

    # 3. Apply CLI command overrides to config
    if args.live:
        config.dry_run = False
    if args.test_email:
        config.test_recipient = args.test_email

    # Print current mode
    if config.dry_run:
        logger.info("====================================================")
        logger.info("                  DRY RUN ACTIVE                    ")
        logger.info("====================================================")
        if config.test_recipient:
            logger.info(f"Emails will be redirect-sent to test: {config.test_recipient}")
        else:
            logger.info("Emails will only be rendered and saved to preview/")
        logger.info("====================================================")
    else:
        logger.info("====================================================")
        logger.info("                !!! LIVE MODE !!!                  ")
        logger.info("====================================================")
        try:
            config.validate_for_live()
        except ConfigError as ce:
            logger.error(f"Cannot run in LIVE mode: {ce}")
            sys.exit(1)
        logger.info(f"Targeting real team leaders with CC to: {config.cc_emails}")
        logger.info("====================================================")

    # 4. Load & Parse CSV data
    logger.info(f"Loading teams from: {args.csv}")
    try:
        teams = load_teams_from_csv(args.csv)
    except FileNotFoundError:
        logger.error(f"CSV file not found at: {args.csv}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error reading CSV: {e}")
        sys.exit(1)

    logger.info(f"Successfully loaded {len(teams)} valid team rows from CSV.")

    # 5. Initialize logs and load sending state for idempotency
    init_send_log_file()
    sent_teams = get_already_sent_teams()
    logger.info(f"Found {len(sent_teams)} teams already successfully emailed in log.")

    # 6. Initialize Mailer components
    renderer = EmailRenderer()
    mailer = Mailer(config, renderer)

    # Metrics
    total = len(teams)
    skipped_sent = 0
    success_count = 0
    failed_count = 0

    # 7. Processing Loop
    for idx, team in enumerate(teams, 1):
        # Idempotency check
        if team.team_number in sent_teams and not args.force:
            logger.info(f"[{idx}/{total}] Skipping team {team.team_number}: Already sent in previous run.")
            skipped_sent += 1
            continue

        # Print progress
        recipient_display = config.test_recipient if (config.dry_run and config.test_recipient) else team.leader_email
        logger.info(f"[{idx}/{total}] Processing team {team.team_number} ({team.team_name}) -> {recipient_display}")

        # Send mail
        success = mailer.send_email(team)

        if success:
            success_count += 1
            # Record success in log (only if not a preview-only dry run without email delivery)
            # If it is a dry run with NO test email set, it's just saving previews. We log it as PREVIEW.
            if config.dry_run and not config.test_recipient:
                append_to_send_log(team.team_number, "PREVIEW", "PREVIEW", "")
            else:
                append_to_send_log(team.team_number, recipient_display, "SUCCESS", "")
        else:
            failed_count += 1
            append_to_send_log(team.team_number, recipient_display, "FAILED", "SMTP or Render error")

        # Rate limiting: wait if there are more emails left to send
        # We only throttle when sending actual emails (live mode or test-directed dry-run)
        need_throttle = (not config.dry_run) or (config.dry_run and config.test_recipient)
        if need_throttle and idx < total:
            logger.info(f"Throttling for {config.rate_limit_delay} seconds...")
            time.sleep(config.rate_limit_delay)

    # 8. Render summary report
    logger.info("====================================================")
    logger.info("                EXECUTION SUMMARY                   ")
    logger.info("====================================================")
    logger.info(f"Total teams loaded: {total}")
    logger.info(f"Skipped (already sent): {skipped_sent}")
    logger.info(f"Successfully processed: {success_count}")
    logger.info(f"Failed to process:      {failed_count}")
    logger.info("====================================================")

if __name__ == "__main__":
    main()
