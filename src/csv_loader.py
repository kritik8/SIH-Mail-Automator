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
            
        import re
        original_s = s
        
        # Strip outer brackets if present
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1].strip()
            
        # Helper to remove a match by span index
        def remove_span(string, match):
            if match:
                start, end = match.span()
                return string[:start] + string[end:]
            return string

        # 1. Extract email
        email = "N/A"
        email_match = re.search(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", s)
        if email_match:
            email = email_match.group(0).strip()
            s = remove_span(s, email_match)
            
        # 2. Extract scholar number
        scholar_id = "N/A"
        scholar_match = re.search(r"\b\d{2}[uUpP][a-zA-Z0-9]{2,10}\b", s)
        if scholar_match:
            scholar_id = scholar_match.group(0).strip()
            s = remove_span(s, scholar_match)
            
        # 3. Extract gender
        gender = "N/A"
        gender_match = re.search(r"\b(male|female|other|m|f|o)\b", s, re.IGNORECASE)
        if gender_match:
            g_str = gender_match.group(0).strip().upper()
            if g_str.startswith("M"):
                gender = "M"
            elif g_str.startswith("F"):
                gender = "F"
            elif g_str.startswith("O"):
                gender = "O"
            s = remove_span(s, gender_match)
            
        # 4. Extract phone number
        phone = "N/A"
        phone_match = re.search(r"\+?[\d\s-]{8,16}", s)
        if phone_match:
            ph = phone_match.group(0).strip()
            if sum(c.isdigit() for c in ph) >= 7:
                phone = ph
                s = remove_span(s, phone_match)
                
        # 5. Extract name (remaining text)
        name = re.sub(r"[\s,;.-]+", " ", s).strip()
        if not name:
            parts = original_s.split(",")
            if parts:
                name = parts[0].strip()
                
        return cls(
            name=name,
            scholar_id=scholar_id,
            phone=phone,
            email=email,
            gender=gender
        )

class TeamData(BaseModel):
    team_number: str = Field(..., min_length=1)
    team_name: str = "Unnamed Team"
    leader: Participant = Field(default_factory=Participant)
    problem_theme: str = ""
    track: str = ""
    members: List[Participant] = Field(default_factory=list)
    mentor_allocated: str = ""

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
            "01", "CodeCrafters", 
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
            "02", "ElectroWaves", 
            "Vikram Rathore, 23U02001, 9876543220, vikram.test@example.com, M",
            "Karan Malhotra, 23U02002, 9876543221, karan.m@example.com, M", 
            "Anjali Gupta, 23U02003, 9876543222, anjali.g@example.com, F", 
            "", "", "",
            "AI Powered Solar Panel Alignment", "Hardware"
        ],
        # Valid Row 3 - Software, leader only
        [
            "03", "DevDynasty", 
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
            "04", "ErrorTeam", 
            "",
            "", "", "", "", "",
            "Some Theme", "Software"
        ],
        # Invalid Row 6 - Malformed email in leader details (Should be skipped)
        [
            "05", "BadEmailTeam", 
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
        # Handle cases where reader.fieldnames is None
        fieldnames = reader.fieldnames or []
        
        # Helper to find header key matching a substring (case-insensitive)
        def find_header_key(substrings: list[str]) -> Optional[str]:
            for field in fieldnames:
                for sub in substrings:
                    if sub.lower() in field.lower():
                        return field
            return None

        # Resolve header keys
        key_team_num = find_header_key(["team id/no", "team_number", "team id"])
        key_team_name = find_header_key(["team name", "team_name"])
        key_leader_details = find_header_key(["participant 1 details (leader)", "leader_details"])
        key_leader_email = find_header_key(["email address of team leader", "leader_email"])
        key_track = find_header_key(["type", "track"])
        key_mentor_allocated = find_header_key(["mentor allocated", "mentor_allocated"])
        
        # Member details keys 2 to 6
        key_members = []
        for i in range(2, 7):
            m_key = find_header_key([f"participant {i} details", f"member_{i}_details", f"member_{i}_name"])
            key_members.append(m_key)
            
        for line_num, row in enumerate(reader, start=2): # 1-based csv indexing (line 1 is headers)
            # 1. Team number
            raw_team_num = ""
            if key_team_num:
                raw_team_num = (row.get(key_team_num) or "").strip()
            
            if not raw_team_num:
                logger.warning(f"[Line {line_num}] Skipping row: Team number is empty.")
                continue
                
            # Prefix team number with "SIH-" if not already present
            if not raw_team_num.upper().startswith("SIH-"):
                team_num = f"SIH-{raw_team_num}"
            else:
                team_num = raw_team_num
                
            # 2. Extract and parse leader details
            leader = Participant()
            leader_details = ""
            if key_leader_details:
                leader_details = (row.get(key_leader_details) or "").strip()
                
            if leader_details:
                leader = Participant.from_string(leader_details)
            
            # If email is not parsed correctly or is N/A, fallback to the direct email column
            if key_leader_email and (not leader.email or leader.email == "N/A"):
                direct_email = (row.get(key_leader_email) or "").strip()
                if direct_email:
                    leader.email = direct_email
                    
            if not leader.name:
                # If leader name is still missing, fallback to parsing it
                leader.name = "Team Leader"
                
            if not leader.email or leader.email == "N/A":
                logger.warning(f"[Line {line_num}] Skipping team {team_num}: Leader email is empty or invalid.")
                continue
                
            # Basic email syntax check (must have @)
            if "@" not in leader.email:
                logger.warning(f"[Line {line_num}] Skipping team {team_num}: Leader email '{leader.email}' is invalid.")
                continue
                
            # 3. Collect other details
            team_name = "Unnamed Team"
            if key_team_name:
                team_name = (row.get(key_team_name) or "Unnamed Team").strip()
                
            track = ""
            if key_track:
                track = (row.get(key_track) or "").strip()
                
            # 4. Extract other 5 members
            members = []
            for m_key in key_members:
                if m_key:
                    m_str = (row.get(m_key) or "").strip()
                    if m_str:
                        m_obj = Participant.from_string(m_str)
                        if m_obj.name:
                            members.append(m_obj)
                            
            mentor_allocated = ""
            if key_mentor_allocated:
                mentor_allocated = (row.get(key_mentor_allocated) or "").strip()

            team = TeamData(
                team_number=team_num,
                team_name=team_name,
                leader=leader,
                problem_theme="", # Omit theme as requested
                track=track,
                members=members,
                mentor_allocated=mentor_allocated
            )
            valid_teams.append(team)
            
    # Validate that team numbers are sequential and gapless
    if valid_teams:
        try:
            team_indices = []
            for t in valid_teams:
                # Strip "SIH-" prefix for sequential validation
                num_str = t.team_number.strip()
                if num_str.upper().startswith("SIH-"):
                    num_str = num_str[4:]
                team_indices.append(int(num_str))
            
            # Check for duplicates
            if len(team_indices) != len(set(team_indices)):
                dups = sorted(list(set([x for x in team_indices if team_indices.count(x) > 1])))
                logger.error(f"LOUD WARNING: Duplicate team numbers found in CSV: {dups}")
            
            # Check for gaps/sequence starting at 1
            team_indices_sorted = sorted(team_indices)
            expected = list(range(1, len(valid_teams) + 1))
            if team_indices_sorted != expected:
                missing = sorted(list(set(expected) - set(team_indices)))
                out_of_bounds = sorted(list(set(team_indices) - set(expected)))
                logger.error(
                    f"LOUD WARNING: Team numbers are not sequential and gapless!\n"
                    f"Expected sequence: 1 to {len(valid_teams)}\n"
                    f"Missing expected team numbers: {missing}\n"
                    f"Unexpected/Out-of-bounds numbers: {out_of_bounds}"
                )
        except ValueError as e:
            logger.error(f"LOUD WARNING: Could not validate team number sequence (non-integer detected): {e}")
            
    return valid_teams

def load_selected_teams_from_csv(
    selected_csv_path: str,
    master_csv_path: str = "SIH 2026 Registrations (Responses) - Complete teams with Mentor alloc (29_08).csv"
) -> List[TeamData]:
    """Reads shortlisted teams from the selected CSV and enriches them with master registration data."""
    sel_path = Path(selected_csv_path)
    if not sel_path.exists():
        raise FileNotFoundError(f"Selected teams CSV not found at: {selected_csv_path}")

    # Build lookup dictionaries from master registration data if available
    master_by_id = {}
    master_by_name = {}
    master_by_email = {}

    master_path = Path(master_csv_path)
    if master_path.exists():
        try:
            master_list = load_teams_from_csv(str(master_path))
            for t in master_list:
                master_by_id[t.team_number.upper()] = t
                master_by_name[t.team_name.lower().strip()] = t
                if t.leader_email:
                    master_by_email[t.leader_email.lower().strip()] = t
        except Exception as e:
            logger.warning(f"Could not load master registration data for enrichment: {e}")

    # Explicit manual mapping overrides for edge cases
    manual_email_map = {
        "85": "toyogeshkumar99@gmail.com",
        "97": "vishallakshya2004@gmail.com",
        "SIH-85": "toyogeshkumar99@gmail.com",
        "SIH-97": "vishallakshya2004@gmail.com",
    }

    selected_teams = []
    with open(sel_path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        for line_num, row in enumerate(reader, start=2):
            if not row or not any(row):
                continue
            raw_email = row[0].strip() if len(row) > 0 else ""
            raw_tid = row[1].strip() if len(row) > 1 else ""
            raw_tname = row[2].strip() if len(row) > 2 else ""

            if not raw_tid and not raw_tname and not raw_email:
                continue

            tid = f"SIH-{raw_tid}" if not raw_tid.upper().startswith("SIH-") else raw_tid.upper()

            # Find matching master record
            master = master_by_id.get(tid)
            if not master:
                master = master_by_name.get(raw_tname.lower())
            if not master and "@" in raw_email:
                master = master_by_email.get(raw_email.lower())

            # Determine email
            email = raw_email
            if raw_tid in manual_email_map:
                email = manual_email_map[raw_tid]
            elif "@" not in email and master:
                email = master.leader_email

            leader_name = master.leader_name if master else "Team Leader"
            scholar_id = master.leader.scholar_id if master else "N/A"
            gender = master.leader.gender if master else "N/A"
            phone = master.leader.phone if master else "N/A"

            leader = Participant(
                name=leader_name,
                email=email,
                scholar_id=scholar_id,
                gender=gender,
                phone=phone
            )

            team = TeamData(
                team_number=tid,
                team_name=raw_tname or (master.team_name if master else "Unnamed Team"),
                leader=leader,
                problem_theme=master.problem_theme if master else "",
                track=master.track if master else "",
                members=master.members if master else [],
                mentor_allocated=master.mentor_allocated if master else ""
            )
            selected_teams.append(team)

    logger.info(f"Loaded {len(selected_teams)} shortlisted teams from {sel_path.name}")
    return selected_teams

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_sample_csv()
    teams = load_teams_from_csv("data/sample_teams_test.csv")
    print(f"\nSuccessfully loaded {len(teams)} valid teams:")
    for t in teams:
        print(f"- {t.team_number}: {t.team_name} (Leader: {t.leader.name} <{t.leader.email}>), Theme: {t.problem_theme or 'None'}, Track: {t.track or 'None'}, Members count: {len(t.members)}")
