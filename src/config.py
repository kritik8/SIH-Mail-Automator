import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

class ConfigError(Exception):
    pass

class AppConfig:
    def __init__(self, config_yaml_path="config.yaml"):
        self.config_path = Path(config_yaml_path)
        self.yaml_data = {}
        
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.yaml_data = yaml.safe_load(f) or {}
            except Exception as e:
                raise ConfigError(f"Failed to parse config.yaml: {e}")
        else:
            # Not strict error because the CLI or another tool might override
            print(f"Warning: config.yaml not found at {self.config_path}, using defaults.")

        # SMTP settings (loaded from .env)
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        
        try:
            self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        except ValueError:
            self.smtp_port = 587

        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        
        # Dry Run
        self.dry_run = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")
        self.test_recipient = os.getenv("TEST_RECIPIENT", "")

        # YAML configuration fields
        self.event_date = self.yaml_data.get("event_date", "To Be Announced")
        self.event_venue = self.yaml_data.get("event_venue", "NTB, IIIT Bhopal")
        
        self.spoc_name = self.yaml_data.get("spoc_name", "Dr. Sourabh Jain")
        self.spoc_role = self.yaml_data.get("spoc_role", "Single Point of Contact (SPOC) for SIH 2026, IIIT Bhopal")
        self.spoc_email = self.yaml_data.get("spoc_email", "sourabh.jain@iiitbhopal.ac.in")
        
        self.cc_emails = self.yaml_data.get("cc_emails", [
            "sourabh.jain@iiitbhopal.ac.in",
            "rekhakaushik@iiitbhopal.ac.in"
        ])
        
        # Send behavior parameters
        try:
            self.rate_limit_delay = float(self.yaml_data.get("rate_limit_delay_seconds", 3.0))
        except (ValueError, TypeError):
            self.rate_limit_delay = 3.0

        try:
            self.retry_attempts = int(self.yaml_data.get("retry_attempts", 3))
        except (ValueError, TypeError):
            self.retry_attempts = 3

        try:
            self.retry_backoff = float(self.yaml_data.get("retry_backoff_seconds", 2.0))
        except (ValueError, TypeError):
            self.retry_backoff = 2.0

    def validate_for_live(self):
        """Validates configuration when DRY_RUN=false."""
        if not self.smtp_username:
            raise ConfigError("SMTP_USERNAME must be provided in .env when DRY_RUN=false.")
        if not self.smtp_password:
            raise ConfigError("SMTP_PASSWORD must be provided in .env when DRY_RUN=false.")
        if self.event_date == "To Be Announced":
            raise ConfigError("event_date in config.yaml must be updated to a real date before going live.")

    def __repr__(self):
        return (
            f"AppConfig(smtp_host={self.smtp_host}, smtp_port={self.smtp_port}, "
            f"username={self.smtp_username or 'NOT_SET'}, dry_run={self.dry_run}, "
            f"test_recipient={self.test_recipient or 'NOT_SET'})"
        )
