import csv

with open('Selected team for internal round.csv', encoding='utf-8') as f:
    reader = csv.reader(f)
    headers = next(reader)
    print("Headers:", headers)
    for idx, row in enumerate(reader, start=2):
        if len(row) < 3:
            print(f"Line {idx}: Short row: {row}")
            continue
        email, team_id, team_name = row[0].strip(), row[1].strip(), row[2].strip()
        if "@" not in email:
            print(f"Line {idx}: Non-email in col 1 -> '{email}' (Team ID: {team_id}, Team Name: {team_name})")
        if not team_id:
            print(f"Line {idx}: Empty team_id (Email: {email}, Team Name: {team_name})")
        if not team_name:
            print(f"Line {idx}: Empty team_name (Email: {email}, Team ID: {team_id})")
