import os
import smtplib
import time
import logging
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader, TemplateError
from src.config import AppConfig
from src.csv_loader import TeamData

logger = logging.getLogger("mailer")

class EmailRenderer:
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.env = Environment(loader=FileSystemLoader(self.templates_dir))
        
        # Plain text template structures for fallbacks
        self.text_templates = {
            "invitation": (
                "Smart India Hackathon 2026 - Internal Invitation\n"
                "Indian Institute of Information Technology, Bhopal\n\n"
                "Dear {{ leader_name }},\n\n"
                "Your team has been shortlisted for the Internal SIH Invitation at IIIT Bhopal. Below are your assigned team details.\n\n"
                "--- Team Information ---\n"
                "Team ID: {{ team_number }}\n"
                "Team Name: {{ team_name }}\n"
                "{% if track %}Category of PS: {{ track }}\n{% endif %}"
                "{% if mentor_allocated %}Mentor Allocated: {{ mentor_allocated }}\n{% endif %}\n"
                "Team Members:\n"
                "  - {{ leader.name }} (Leader) | Scholar No: {{ leader.scholar_id }} | Gender: {{ leader.gender }}\n"
                "{% for m in members %}"
                "  - {{ m.name }} | Scholar No: {{ m.scholar_id }} | Gender: {{ m.gender }}\n"
                "{% endfor %}\n"
                "--- Event Schedule ---\n"
                "Date: {{ event_date }}\n"
                "Venue: {{ event_venue }}\n\n"
                "--- Participant Guidelines ---\n"
                "1. Each team must consist of exactly 6 members from the same institution.\n"
                "2. At least one female member is mandatory in every team.\n"
                "3. Registrations are processed solely via College SPOC nomination.\n"
                "4. Nominated teams must submit their project ideas under the selected problem theme.\n"
                "5. The final rounds are conducted as a physical 36-hour hackathon.\n\n"
                "For any queries, contact the institutional SPOC:\n"
                "{{ spoc_name }} ({{ spoc_role }})\n"
                "Email: {{ spoc_email }}\n\n"
                "Regards,\n"
                "SIH Organizing Committee, IIIT Bhopal"
            ),
            "reminder": (
                "SIH Internal Hackathon - Tomorrow!\n"
                "Indian Institute of Information Technology, Bhopal\n\n"
                "Dear {{ leader_name }},\n\n"
                "This is a quick final reminder that the Internal SIH Selection Round begins tomorrow.\n"
                "Your team, {{ team_name }} (Team Number: {{ team_number }}), is scheduled to participate at:\n\n"
                "--- Event Schedule ---\n"
                "Date/Time: {{ event_date }}\n"
                "Venue: {{ event_venue }}\n\n"
                "--- Quick Checklist ---\n"
                "- Arrive at the NTB registration desk by 8:30 AM.\n"
                "- Bring your college student ID cards (mandatory).\n"
                "- Bring your laptops, power strips, and required chargers.\n"
                "- Ensure all development tools and IDEs are configured.\n\n"
                "Best of luck, Team {{ team_name }}!\n\n"
                "Regards,\n"
                "SIH Organizing Committee, IIIT Bhopal"
            ),
            "thankyou": (
                "SIH Internal Hackathon - Thank You\n"
                "Indian Institute of Information Technology, Bhopal\n\n"
                "Dear {{ leader_name }},\n\n"
                "Thank you for participating in the Smart India Hackathon 2026 Internal Selection Round at IIIT Bhopal. "
                "We appreciate the hard work, creativity, and dedication that your team, {{ team_name }}, demonstrated.\n\n"
                "Participation certificates for all 6 of your registered team members are attached to this email.\n\n"
                "Regards,\n"
                "SIH Organizing Committee, IIIT Bhopal"
            )
        }

    def render(self, team: TeamData, config: AppConfig, template_type: str) -> tuple[str, str]:
        """Renders both HTML and plain-text versions of the selected invitation type."""
        template_files = {
            "invitation": "1_invitation.html.j2",
            "reminder": "2_reminder.html.j2",
            "thankyou": "3_thankyou.html.j2"
        }
        
        if template_type not in template_files:
            raise ValueError(f"Unknown template type: '{template_type}'")
            
        template_name = template_files[template_type]
        
        try:
            html_template = self.env.get_template(template_name)
        except TemplateError as e:
            raise RuntimeError(f"Failed to load HTML template '{template_name}': {e}")
            
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
            "spoc_email": config.spoc_email,
            "mentor_allocated": getattr(team, "mentor_allocated", "")
        }
        
        try:
            html_content = html_template.render(**render_context)
            text_str = self.text_templates[template_type]
            text_template = self.env.from_string(text_str)
            text_content = text_template.render(**render_context)
            return html_content, text_content
        except TemplateError as e:
            raise RuntimeError(f"Failed to render templates for {template_type}: {e}")


class Mailer:
    def __init__(self, config: AppConfig, renderer: EmailRenderer):
        self.config = config
        self.renderer = renderer
        self.preview_dir = Path("preview")

    def send_email(self, team: TeamData, template_type: str, attachments: List[Path] = None) -> bool:
        """
        Sends the personalized email with the selected template type.
        Supports attachments for post-event certificates.
        """
        try:
            html_body, text_body = self.renderer.render(team, self.config, template_type)
        except Exception as e:
            logger.error(f"Error rendering email for team {team.team_number} ({template_type}): {e}")
            return False

        # Build subject line
        subject_prefixes = {
            "invitation": "Internal Invitation",
            "reminder": "Internal Hackathon - Tomorrow!",
            "thankyou": "Thank You for Participating"
        }
        subject = f"Smart India Hackathon 2026 - {subject_prefixes[template_type]} (Team: {team.team_number})"

        # If dry-run, save preview to file
        if self.config.dry_run:
            tmpl_preview_dir = self.preview_dir / template_type
            tmpl_preview_dir.mkdir(parents=True, exist_ok=True)
            preview_file = tmpl_preview_dir / f"team_{team.team_number}.html"
            try:
                with open(preview_file, "w", encoding="utf-8") as f:
                    f.write(html_body)
                logger.info(f"[DRY RUN] Generated preview for team {team.team_number} ({template_type}) at: {preview_file}")
            except Exception as e:
                logger.error(f"[DRY RUN] Failed to write preview file for team {team.team_number}: {e}")
            
            # If a test recipient is specified, also transmit the email to that recipient
            if self.config.test_recipient:
                logger.info(f"[DRY RUN] Redirecting email to test address: {self.config.test_recipient}")
                return self._transmit_smtp(
                    to_email=self.config.test_recipient,
                    cc_emails=[], # Don't spam CCs during test
                    subject=f"[DRY RUN] {subject}",
                    html_body=html_body,
                    text_body=text_body,
                    attachments=attachments
                )
            return True
            
        else:
            # Live run
            # Note: CC addresses are supplied from config. In sandbox test mode, they are stripped upstream.
            cc_list = self.config.cc_emails
            return self._transmit_smtp(
                to_email=team.leader_email,
                cc_emails=cc_list,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                attachments=attachments
            )

    def _transmit_smtp(self, to_email: str, cc_emails: List[str], subject: str, html_body: str, text_body: str, attachments: List[Path] = None) -> bool:
        """Handles low-level SMTP message creation and transmission with retry-backoff logic."""
        msg = MIMEMultipart("mixed")  # Use mixed to support both alternative bodies and attachments
        msg["From"] = f"SIH IIIT Bhopal Invitation <{self.config.smtp_username}>"
        msg["To"] = to_email
        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)
        msg["Subject"] = subject

        # Create alternative body part for text/html
        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(text_body, "plain", "utf-8"))
        alt_part.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt_part)

        # Attach certificate files
        if attachments:
            for filepath in attachments:
                if not filepath.exists():
                    logger.warning(f"Attachment path '{filepath}' does not exist, skipping.")
                    continue
                try:
                    with open(filepath, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{filepath.name}"'
                    )
                    msg.attach(part)
                except Exception as e:
                    logger.error(f"Failed to attach file '{filepath.name}': {e}")
                    return False

        all_recipients = [to_email] + cc_emails

        # Retry loop
        for attempt in range(1, self.config.retry_attempts + 1):
            try:
                if self.config.smtp_port == 465:
                    server = smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, timeout=15)
                else:
                    server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=15)
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
