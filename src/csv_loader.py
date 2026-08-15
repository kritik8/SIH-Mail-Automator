import csv
import logging
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, field_validator

logger = logging.getLogger("csv_loader")

class Participant(BaseModel):
    name: str = ""
    scholar_id: str = "N/A"
    phone: str = "N/A"
    email: str = "N/A"
    gender: str = "N/A"

    @classmethod
    def from_string(cls, s: str) -> "Participant":
        s = s.strip()
        if not s:
            return cls()
        
        # Split on commas
        parts = [p.strip() for p in s.split(",")]
        
        if len(parts) >= 5:
            return cls(
                name=parts[0],
                scholar_id=parts[1],
                phone=parts[2],
                email=parts[3],
                gender=parts[4]
            )
        elif len(parts) > 1:
            name = parts[0]
            scholar_id = parts[1] if len(parts) > 1 else "N/A"
            phone = parts[2] if len(parts) > 2 else "N/A"
            email = parts[3] if len(parts) > 3 else "N/A"
            gender = parts[4] if len(parts) > 4 else "N/A"
            return cls(name=name, scholar_id=scholar_id, phone=phone, email=email, gender=gender)
        else:
            # Fallback for simple name only
            return cls(name=s)

class TeamData(BaseModel):
    team_number: str = Field(..., min_length=1)
    team_name: str = "Unnamed Team"
    leader: Participant = Field(default_factory=Participant)
    problem_theme: str = ""
    track: str = ""
    members: List[Participant] = Field(default_factory=list)

    @property
    def leader_email(self) -> str:
        # Fallback to a placeholder if email is invalid or missing to prevent crash during parsing
        email = self.leader.email.strip()
        if not email or email == "N/A":
            return ""
        return email

    @property
    def leader_name(self) -> str:
        return self.leader.name or "Team Leader"

    @field_validator("team_number", mode="before")
    @classmethod
    def clean_team_number(cls, v):
        if v is None:
            raise ValueError("Team number cannot be null")
        return str(v).strip()

def generate_sample_csv(target_path: str = "data/sample_teams_test.csv") -> None:
    """Generates a test CSV file using the Google Form participant details format."""
    target_file = Path(target_path)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    
    headers = [
        "team_number",
        "team_name",
        "leader_details",
        "member_2_details",
        "member_3_details",
        "member_4_details",
        "member_5_details",
        "member_6_details",
        "problem_theme",
        "track"
    ]
    
    # Realistic test rows containing Name, Scholar ID, Phone, Email, Gender
    rows = [
        # Valid Row 1 - Full Team
        [
            "SIH-042", "CodeCrafters", 
            "Aditi Sharma, 23U01001, 9876543210, aditi.test@example.com, F",
            "Amit Patel, 23U01002, 9876543211, amit.patel@example.com, M", 
            "Sneha Reddy, 23U01003, 9876543212, sneha.r@example.com, F", 
            "Rajesh Kumar, 23U01004, 9876543213, rajesh.k@example.com, M", 
            "Priya Singh, 23U01005, 9876543214, priya.s@example.com, F", 
            "Rohan Verma, 23U01006, 9876543215, rohan.v@example.com, M",
            "Smart Waste Management", "Software"
        ],
        # Valid Row 2 - Hardware, partial team (3 members total)
        [
            "SIH-043", "ElectroWaves", 
            "Vikram Rathore, 23U02001, 9876543220, vikram.test@example.com, M",
            "Karan Malhotra, 23U02002, 9876543221, karan.m@example.com, M", 
            "Anjali Gupta, 23U02003, 9876543222, anjali.g@example.com, F", 
            "", "", "",
            "AI Powered Solar Panel Alignment", "Hardware"
        ],
        # Valid Row 3 - Software, leader only
        [
            "SIH-044", "DevDynasty", 
            "Kunal Sen, 23U03001, 9876543230, kunal.test@example.com, M",
            "", "", "", "", "",
            "Blockchain land registry", "Software"
        ],
        # Invalid Row 4 - Missing team_number (Should be skipped)
        [
            "", "GhostTeam", 
            "Rahul Mehra, 23U04001, 9876543240, rahul.test@example.com, M",
            "", "", "", "", "",
            "Some Theme", "Software"
        ],
        # Invalid Row 5 - Missing leader email or invalid format (Should be skipped due to empty leader details)
        [
            "SIH-045", "ErrorTeam", 
            "",
            "", "", "", "", "",
            "Some Theme", "Software"
        ],
        # Invalid Row 6 - Malformed email in leader details (Should be skipped)
        [
            "SIH-046", "BadEmailTeam", 
            "Jack Ryan, 23U05001, 9876543250, not-a-valid-email, M",
            "", "", "", "", "",
            "Some Theme", "Software"
        ]
    ]
    
    with open(target_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    logger.info(f"Sample CSV file successfully generated at: {target_file.absolute()}")

def load_teams_from_csv(csv_path: str) -> List[TeamData]:
    """Reads and validates the team CSV file, returning a list of valid TeamData objects."""
    file_path = Path(csv_path)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")
        
    valid_teams = []
    
    with open(file_path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        
        for line_num, row in enumerate(reader, start=2): # 1-based csv indexing (line 1 is headers)
            team_num = row.get("team_number") or ""
            
            # 1. Check for team number
            if not team_num.strip():
                logger.warning(f"[Line {line_num}] Skipping row: 'team_number' is empty.")
                continue
            
            # 2. Extract and parse leader details
            leader_details = row.get("leader_details") or ""
            leader = Participant()
            if leader_details.strip():
                leader = Participant.from_string(leader_details)
            else:
                # Compatibility: try legacy header names if leader_details is absent
                legacy_name = row.get("leader_name") or ""
                legacy_email = row.get("leader_email") or ""
                if legacy_name or legacy_email:
                    leader = Participant(name=legacy_name.strip(), email=legacy_email.strip())
            
            if not leader.name or not leader.email or leader.email == "N/A":
                logger.warning(f"[Line {line_num}] Skipping row: Leader name or email is empty or invalid.")
                continue
                
            # Basic email syntax check (must have @)
            if "@" not in leader.email:
                logger.warning(f"[Line {line_num}] Skipping team {team_num}: Leader email '{leader.email}' is invalid.")
                continue
                
            # 3. Collect other details
            team_name = row.get("team_name") or "Unnamed Team"
            
            # Map problem_theme, fallback to problem_statement_title or ID if theme is missing
            theme = row.get("problem_theme") or ""
            if not theme:
                ps_id = row.get("problem_statement_id") or ""
                ps_title = row.get("problem_statement_title") or ""
                if ps_id or ps_title:
                    theme = f"[{ps_id}] {ps_title}" if ps_id else ps_title
                    
            track = row.get("track") or ""
            
            # 4. Extract other 5 members
            members = []
            for i in range(2, 7):
                # Try member_X_details first, fallback to member_X_name
                m_str = row.get(f"member_{i}_details") or row.get(f"member_{i}_name") or ""
                if m_str.strip():
                    m_obj = Participant.from_string(m_str)
                    if m_obj.name:
                        members.append(m_obj)
            
            team = TeamData(
                team_number=team_num.strip(),
                team_name=team_name.strip(),
                leader=leader,
                problem_theme=theme.strip(),
                track=track.strip(),
                members=members
            )
            valid_teams.append(team)
                
    return valid_teams

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_sample_csv()
    teams = load_teams_from_csv("data/sample_teams_test.csv")
    print(f"\nSuccessfully loaded {len(teams)} valid teams:")
    for t in teams:
        print(f"- {t.team_number}: {t.team_name} (Leader: {t.leader.name} <{t.leader.email}>), Theme: {t.problem_theme or 'None'}, Track: {t.track or 'None'}, Members count: {len(t.members)}")
