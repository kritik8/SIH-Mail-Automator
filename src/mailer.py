import os
import smtplib
import time
import logging
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader, TemplateError
from src.config import AppConfig
from src.csv_loader import TeamData

logger = logging.getLogger("mailer")

class EmailRenderer:
    def __init__(self, templates_dir: str = "templates", template_name: str = "team_invite.html.j2"):
        self.templates_dir = Path(templates_dir)
        self.template_name = template_name
        self.env = Environment(loader=FileSystemLoader(self.templates_dir))
        
        # Plain text template string
        self.text_template_str = (
            "Smart India Hackathon - Internal Invitation\n"
            "Indian Institute of Information Technology, Bhopal\n\n"
            "Dear {{ leader_name }},\n\n"
            "Congratulations! Your team has been shortlisted for the Internal SIH Invitation at IIIT Bhopal.\n\n"
            "--- Team Details ---\n"
            "Team Number: {{ team_number }}\n"
            "Team Name: {{ team_name }}\n"
            "{% if track %}Category / Track: {{ track }}\n{% endif %}"
            "{% if problem_theme %}Problem Theme: {{ problem_theme }}\n{% endif %}\n"
            "--- Team Roster & Contact Details ---\n"
            "  - {{ leader.name }} (Leader) | Scholar ID: {{ leader.scholar_id }} | Phone: {{ leader.phone }} | Email: {{ leader.email }} | Gen: {{ leader.gender }}\n"
            "{% for m in members %}"
            "  - {{ m.name }} | Scholar ID: {{ m.scholar_id }} | Phone: {{ m.phone }} | Email: {{ m.email }} | Gen: {{ m.gender }}\n"
            "{% endfor %}\n"
            "--- Event Schedule ---\n"
            "Date: {{ event_date }}\n"
            "Venue: {{ event_venue }}\n\n"
            "--- Participant Guidelines (SIH Official) ---\n"
            "1. Team Composition: Each team must consist of exactly 6 members (including the leader) from the same college.\n"
            "2. Female Representation: At least one female member is mandatory in every team.\n"
            "3. SPOC Registration Only: Individual registrations are not allowed on the national portal. Nomination is handled by the SPOC.\n"
            "4. Idea Submission: Nominated teams must submit their proposals under their selected problem theme.\n"
            "5. Grand Finale Format: Selected teams are invited to a 36-hour physical hackathon at national nodal centers.\n\n"
            "For queries, contact the institutional SPOC:\n"
            "{{ spoc_name }} ({{ spoc_role }})\n"
            "Email: {{ spoc_email }}\n\n"
            "Regards,\n"
            "SIH Organizing Committee, IIIT Bhopal"
        )
        self.text_template = self.env.from_string(self.text_template_str)

    def render(self, team: TeamData, config: AppConfig) -> tuple[str, str]:
        """Renders both HTML and plain-text versions of the email invitation."""
        try:
            html_template = self.env.get_template(self.template_name)
        except TemplateError as e:
            raise RuntimeError(f"Failed to load HTML template '{self.template_name}': {e}")
            
        render_context = {
            "team_number": team.team_number,
            "team_name": team.team_name,
            "leader": team.leader,
            "leader_name": team.leader_name,
            "track": team.track,
            "problem_theme": team.problem_theme,
            "members": team.members,
            "event_date": config.event_date,
            "event_venue": config.event_venue,
            "spoc_name": config.spoc_name,
            "spoc_role": config.spoc_role,
            "spoc_email": config.spoc_email
        }
        
        try:
            html_content = html_template.render(**render_context)
            text_content = self.text_template.render(**render_context)
            return html_content, text_content
        except TemplateError as e:
            raise RuntimeError(f"Failed to render templates: {e}")


class Mailer:
    def __init__(self, config: AppConfig, renderer: EmailRenderer):
        self.config = config
        self.renderer = renderer
        self.preview_dir = Path("preview")
        self.preview_dir.mkdir(exist_ok=True)

    def send_email(self, team: TeamData) -> bool:
        """
        Sends the personalized invitation email. 
        Supports dry-run preview saving/redirecting and live SMTP transmission with retries.
        """
        try:
            html_body, text_body = self.renderer.render(team, self.config)
        except Exception as e:
            logger.error(f"Error rendering email for team {team.team_number}: {e}")
            return False

        # If dry-run, save preview to file
        if self.config.dry_run:
            preview_file = self.preview_dir / f"team_{team.team_number}.html"
            try:
                with open(preview_file, "w", encoding="utf-8") as f:
                    f.write(html_body)
                logger.info(f"[DRY RUN] Generated preview for team {team.team_number} at: {preview_file}")
            except Exception as e:
                logger.error(f"[DRY RUN] Failed to write preview file for team {team.team_number}: {e}")
            
            # If a test recipient is specified, also transmit the email to that recipient
            if self.config.test_recipient:
                logger.info(f"[DRY RUN] Redirecting email to test address: {self.config.test_recipient}")
                return self._transmit_smtp(
                    to_email=self.config.test_recipient,
                    cc_emails=[], # Don't spam CCs during test
                    subject=f"[DRY RUN] SIH Internal Invitation - Team {team.team_number}",
                    html_body=html_body,
                    text_body=text_body
                )
            return True
            
        else:
            # Live run
            subject = f"Smart India Hackathon 2026 - Internal Invitation (Team: {team.team_number})"
            return self._transmit_smtp(
                to_email=team.leader_email,
                cc_emails=self.config.cc_emails,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )

    def _transmit_smtp(self, to_email: str, cc_emails: List[str], subject: str, html_body: str, text_body: str) -> bool:
        """Handles low-level SMTP message creation and transmission with retry-backoff logic."""
        msg = MIMEMultipart("alternative")
        msg["From"] = f"SIH IIIT Bhopal Invitation <{self.config.smtp_username}>"
        msg["To"] = to_email
        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)
        msg["Subject"] = subject

        # Attach alternative bodies
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        all_recipients = [to_email] + cc_emails

        # Retry loop
        for attempt in range(1, self.config.retry_attempts + 1):
            try:
                # Setup SMTP client connection
                if self.config.smtp_port == 465:
                    server = smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, timeout=10)
                else:
                    server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=10)
                    server.starttls()
                
                # Authenticate if username/password are set
                if self.config.smtp_username and self.config.smtp_password:
                    server.login(self.config.smtp_username, self.config.smtp_password)
                
                # Send email
                server.sendmail(self.config.smtp_username or "sih-automator@iiitbhopal.ac.in", all_recipients, msg.as_string())
                server.quit()
                
                logger.info(f"Successfully sent email to {to_email} (Attempt {attempt})")
                return True
                
            except Exception as e:
                logger.warning(f"SMTP send attempt {attempt}/{self.config.retry_attempts} failed for {to_email}: {e}")
                if attempt < self.config.retry_attempts:
                    time.sleep(self.config.retry_backoff)
                else:
                    logger.error(f"Failed to send email to {to_email} after {self.config.retry_attempts} attempts.")
                    return False
        return False
