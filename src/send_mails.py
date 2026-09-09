import os
import csv
import sys
import argparse
import logging
from datetime import datetime
import time
from pathlib import Path
from typing import Set, List

from src.config import AppConfig, ConfigError
from src.csv_loader import load_teams_from_csv, load_selected_teams_from_csv, TeamData
from src.mailer import EmailRenderer, Mailer
from src.certificates import get_certificate_files, CertificateError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("mail_automator_debug.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("app")

def get_log_path(mode: str, template: str) -> Path:
    """Returns the correct log file path based on mode and template type."""
    if mode == "test":
        return Path("test_send_log.csv")
    return Path(f"send_log_{template}.csv")

def init_send_log_file(log_path: Path) -> None:
    """Creates the log CSV file with headers if it does not already exist."""
    if not log_path.exists():
        with open(log_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "team_number", "recipient", "status", "error", "attachments"])

def get_already_sent_teams(log_path: Path) -> Set[str]:
    """Reads the log file and returns a set of team numbers that were successfully sent."""
    sent_teams = set()
    if not log_path.exists():
        return sent_teams
        
    with open(log_path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status") == "SUCCESS":
                team_num = row.get("team_number")
                if team_num:
                    sent_teams.add(team_num.strip())
    return sent_teams

def append_to_send_log(log_path: Path, team_number: str, recipient: str, status: str, error: str = "", attachments: List[Path] = None) -> None:
    """Appends a new sending result row to the log CSV file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    attach_str = ";".join([p.name for p in attachments]) if attachments else ""
    with open(log_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, team_number, recipient, status, error, attach_str])

def main() -> None:
    # 1. Parse CLI arguments
    parser = argparse.ArgumentParser(
        description="SIH Internal Hackathon Bulk Mail Automator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--template",
        type=str,
        required=True,
        choices=["invitation", "reminder", "thankyou", "member_notification", "presentation_invitation"],
        help="Select the lifecycle email template to send"
    )
    parser.add_argument(
        "--mode",
        type=str,
        required=True,
        choices=["test", "dry-run", "live"],
        help="Execution mode: 'test' runs real sends against sandbox; 'dry-run' compiles previews; 'live' runs production sends."
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="",
        help="Override path to the CSV data file (ignored in 'test' mode)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore sending logs and force resend emails to all targets"
    )
    parser.add_argument(
        "--team",
        type=str,
        default="",
        help="Only process the team with this team ID/number (e.g. SIH-64 or 64)"
    )
    parser.add_argument(
        "--no-cc",
        action="store_true",
        help="Do not include CC recipients in sent emails"
    )
    args = parser.parse_args()

    # 2. Load Configuration
    try:
        config = AppConfig()
    except ConfigError as ce:
        logger.error(f"Configuration error: {ce}")
        sys.exit(1)

    if args.no_cc or args.template == "member_notification":
        config.cc_emails = []
        logger.info("CC list has been explicitly disabled.")

    # 3. Apply mode overrides
    if args.mode == "test":
        # Sandbox paths
        csv_path = args.csv if args.csv else "test/test_teams.csv"
        certs_dir = Path("test/certificates")
        
        # Test mode defaults: enforce NO CCs and trigger real sends to test recipients
        config.cc_emails = []
        config.dry_run = False
        
        logger.info("====================================================")
        logger.info("             TEST MODE - SANDBOX RUN                ")
        logger.info("====================================================")
        logger.info(f"Targeting sandbox CSV: {csv_path}")
        logger.info("Coordinators CC list has been completely REMOVED for safety.")
        logger.info("====================================================")
        
    elif args.mode == "dry-run":
        if args.csv:
            csv_path = args.csv
        elif args.template == "presentation_invitation":
            csv_path = "Selected team for internal round.csv"
        else:
            csv_path = "data/sample_teams_test.csv"
        certs_dir = Path("data/certificates")
        config.dry_run = True
        
        logger.info("====================================================")
        logger.info("                 DRY RUN ACTIVE                     ")
        logger.info("====================================================")
        logger.info(f"Writing rendered HTML files to preview/{args.template}/")
        logger.info("====================================================")
        
    else:  # live
        if args.csv:
            csv_path = args.csv
        elif args.template == "presentation_invitation":
            csv_path = "Selected team for internal round.csv"
        else:
            csv_path = "data/sample_teams_test.csv"
        certs_dir = Path("data/certificates")
        config.dry_run = False
        
        logger.info("====================================================")
        logger.info("                !!! LIVE RUN !!!                    ")
        logger.info("====================================================")
        try:
            config.validate_for_live()
        except ConfigError as ce:
            logger.error(f"Cannot run in LIVE mode: {ce}")
            sys.exit(1)
        logger.info(f"Targeting real recipients with CC to: {config.cc_emails}")
        logger.info("====================================================")

    # Verify certificates directory exists if template is thankyou
    if args.template == "thankyou":
        if not certs_dir.exists():
            logger.error(f"Certificates directory does not exist: {certs_dir.absolute()}")
            sys.exit(1)

    # 4. Load CSV data
    logger.info(f"Loading teams from: {csv_path}")
    try:
        if args.template == "presentation_invitation" or "selected" in str(csv_path).lower():
            teams = load_selected_teams_from_csv(csv_path)
        else:
            teams = load_teams_from_csv(csv_path)
    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading CSV data: {e}")
        sys.exit(1)

    logger.info(f"Loaded {len(teams)} valid team rows from CSV.")

    if args.team:
        target = args.team.strip()
        teams = [t for t in teams if t.team_number == target or t.team_number == f"SIH-{target}" or target == f"SIH-{t.team_number}"]
        if not teams:
            logger.error(f"Team '{args.team}' not found in loaded CSV.")
            sys.exit(1)
        logger.info(f"Filtered teams list to run only for team: {teams[0].team_number}")

    # 5. Initialize tracking log and fetch sent states
    log_path = get_log_path(args.mode, args.template)
    init_send_log_file(log_path)

    # 6. Initialize Mailer components
    renderer = EmailRenderer()
    mailer = Mailer(config, renderer)

    # Progress stats
    skipped_sent = 0
    success_count = 0
    failed_count = 0

    # 7. Processing Loop (Branches for member_notification vs team leader templates)
    if args.template == "member_notification":
        # Member Notification Workflow
        already_sent_recipients = set()
        if log_path.exists():
            with open(log_path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("status") == "SUCCESS":
                        rec = row.get("recipient")
                        if rec:
                            already_sent_recipients.add(rec.strip().lower())

        all_member_tasks = []
        for team in teams:
            for member in team.members:
                if member.email and member.email != "N/A" and "@" in member.email:
                    all_member_tasks.append((team, member))
                else:
                    logger.warning(f"Skipping team {team.team_number} member '{member.name}': no valid email ({member.email})")

        total = len(all_member_tasks)
        logger.info(f"Prepared {total} non-leader member emails across {len(teams)} teams.")

        for idx, (team, member) in enumerate(all_member_tasks, 1):
            rec_email = member.email.strip()
            if rec_email.lower() in already_sent_recipients and not args.force:
                logger.info(f"[{idx}/{total}] Skipping member {member.name} ({rec_email}): Already sent in previous run.")
                skipped_sent += 1
                continue

            logger.info(f"[{idx}/{total}] Sending member notification to {member.name} ({team.team_number}) -> {rec_email}")
            success = mailer.send_member_email(team, member, args.template)

            if success:
                success_count += 1
                if config.dry_run:
                    append_to_send_log(log_path, team.team_number, "PREVIEW", "PREVIEW", "")
                else:
                    append_to_send_log(log_path, team.team_number, rec_email, "SUCCESS", "")
            else:
                failed_count += 1
                append_to_send_log(log_path, team.team_number, rec_email, "FAILED", "SMTP/Render failure")

            need_throttle = not config.dry_run
            if need_throttle and idx < total:
                logger.info(f"Throttling for {config.rate_limit_delay} seconds...")
                time.sleep(config.rate_limit_delay)

    else:
        # Standard Team Leader Templates (invitation, reminder, thankyou)
        already_sent = get_already_sent_teams(log_path)
        logger.info(f"Found {len(already_sent)} teams already successfully processed in {log_path.name}.")
        total = len(teams)

        for idx, team in enumerate(teams, 1):
            # Idempotency check
            if team.team_number in already_sent and not args.force:
                logger.info(f"[{idx}/{total}] Skipping team {team.team_number}: Already sent in previous run.")
                skipped_sent += 1
                continue

            # Certificate mapping (Only for Thank You emails)
            attachments = []
            if args.template == "thankyou":
                try:
                    attachments = get_certificate_files(team.team_number, certs_dir)
                except (CertificateError, FileNotFoundError) as err:
                    logger.error(f"[{idx}/{total}] Skipping team {team.team_number} due to certificate error: {err}")
                    append_to_send_log(log_path, team.team_number, team.leader_email, "FAILED", f"Certificate error: {err}")
                    failed_count += 1
                    continue

            # Print progress info
            recipient_display = config.test_recipient if (config.dry_run and config.test_recipient) else team.leader_email
            logger.info(f"[{idx}/{total}] Sending '{args.template}' email to team {team.team_number} -> {recipient_display}")
            if attachments:
                logger.info(f"   Attached certificates: {', '.join([p.name for p in attachments])}")

            # Send email
            success = mailer.send_email(team, args.template, attachments)

            if success:
                success_count += 1
                if config.dry_run and not config.test_recipient:
                    append_to_send_log(log_path, team.team_number, "PREVIEW", "PREVIEW", "", attachments)
                else:
                    append_to_send_log(log_path, team.team_number, recipient_display, "SUCCESS", "", attachments)
            else:
                failed_count += 1
                append_to_send_log(log_path, team.team_number, recipient_display, "FAILED", "SMTP/Render failure", attachments)

            # Rate limiting: wait if there are more emails left to send
            need_throttle = (not config.dry_run) or (config.dry_run and config.test_recipient)
            if need_throttle and idx < total:
                logger.info(f"Throttling for {config.rate_limit_delay} seconds...")
                time.sleep(config.rate_limit_delay)

    # 8. Report final metrics
    logger.info("====================================================")
    logger.info("                EXECUTION SUMMARY                   ")
    logger.info("====================================================")
    logger.info(f"Template:               {args.template}")
    logger.info(f"Mode:                   {args.mode}")
    logger.info(f"Total targets:          {total}")
    logger.info(f"Skipped (already sent): {skipped_sent}")
    logger.info(f"Successfully processed: {success_count}")
    logger.info(f"Failed to process:      {failed_count}")
    logger.info("====================================================")

if __name__ == "__main__":
    main()
