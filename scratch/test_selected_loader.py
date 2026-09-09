import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))
from src.csv_loader import load_teams_from_csv, TeamData, Participant

def load_selected_teams(
    selected_csv_path: str = "Selected team for internal round.csv",
    master_csv_path: str = "SIH 2026 Registrations (Responses) - Complete teams with Mentor alloc (29_08).csv"
) -> list[TeamData]:
    # 1. Load master teams lookup by team_number
    master_by_id = {}
    master_by_name = {}
    master_by_email = {}
    
    if Path(master_csv_path).exists():
        master_list = load_teams_from_csv(master_csv_path)
        for t in master_list:
            master_by_id[t.team_number] = t
            master_by_name[t.team_name.lower().strip()] = t
            if t.leader_email:
                master_by_email[t.leader_email.lower().strip()] = t

    # Manual fixes for known typos in selected CSV
    manual_email_map = {
        "85": "toyogeshkumar99@gmail.com",
        "97": "vishallakshya2004@gmail.com",
        "SIH-85": "toyogeshkumar99@gmail.com",
        "SIH-97": "vishallakshya2004@gmail.com",
    }

    selected_teams = []
    with open(selected_csv_path, mode="r", newline="", encoding="utf-8") as f:
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

            tid = f"SIH-{raw_tid}" if not raw_tid.upper().startswith("SIH-") else raw_tid
            
            # Resolve master match
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

    return selected_teams

if __name__ == "__main__":
    teams = load_selected_teams()
    print(f"Loaded {len(teams)} selected teams successfully!")
    for idx, t in enumerate(teams, 1):
        if not t.leader_email or "@" not in t.leader_email:
            print(f"ERROR: Team {t.team_number} has invalid email: '{t.leader_email}'")
        if t.team_number in ["SIH-85", "SIH-97", "SIH-64", "SIH-1", "SIH-114"]:
            print(f"Sample [{idx}]: {t.team_number} | {t.team_name} | Leader: {t.leader_name} <{t.leader_email}> | Mentor: {t.mentor_allocated} | Members: {len(t.members)}")
