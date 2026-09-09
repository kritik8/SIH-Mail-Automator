import csv

with open('SIH 2026 Registrations (Responses) - Complete teams with Mentor alloc (29_08).csv', encoding='utf-8') as f:
    reader = csv.reader(f)
    headers = next(reader)
    for i, r in enumerate(reader, 2):
        if 'i.am.anonymous.nil2005@gmail.com' in str(r) or 'Dhoomketu' in str(r):
            print(f"Line {i}:")
            for h, v in zip(headers, r):
                print(f"  {h} -> {v}")
