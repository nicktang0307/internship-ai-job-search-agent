"""
mark_applied.py — Track which companies you emailed, and which you rejected
============================================================================
Reads drafts.json, shows each draft, asks if you sent it.
- 'y' → recorded in applied_companies.json  + removed from drafts.json
- 'n' → recorded in rejected.json           + removed from drafts.json
- 'q' → quit, saving progress so far

Both applied and rejected companies are excluded from future runs,
so nothing you've already decided on comes back.

Run:
    python mark_applied.py
"""

import json
import os
import re
from datetime import date

DRAFTS_FILE = "drafts.json"
APPLIED_FILE = "applied_companies.json"
REJECTED_FILE = "rejected.json"


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                content = f.read().strip()
                return json.loads(content) if content else default
        except (json.JSONDecodeError, ValueError):
            return default
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def clean_name(name):
    """Lowercase + strip common suffixes so 'Adrenalin Media' == 'Adrenalin'."""
    name = name.lower()
    name = re.sub(r'\b(pty|ltd|limited|inc|group|technologies|tech|analytics|consulting|solutions|media|agency|digital|studio|studios|labs|co)\b', '', name)
    name = re.sub(r'[^a-z0-9]', '', name)
    return name.strip()


def main():
    drafts = load_json(DRAFTS_FILE, [])
    if not drafts:
        print(f"No drafts found in {DRAFTS_FILE}. Run draft_emails.py first.")
        return

    applied = load_json(APPLIED_FILE, [])
    rejected = load_json(REJECTED_FILE, [])

    print(f"{len(drafts)} drafts to review.")
    print("For each: 'y' = sent it, 'n' = not interested, 'q' = quit.")
    print("Either y or n removes it from drafts and stops it coming back.\n")

    remaining = []
    quit_early = False

    for i, d in enumerate(drafts, 1):
        if quit_early:
            remaining.append(d)
            continue

        print("=" * 55)
        print(f"[{i}/{len(drafts)}] {d['company_name']}")
        print(f"To: {d['email'] or '(no email — find manually)'}")
        print(f"Subject: {d['subject']}")
        print(f"\n{d['body']}\n")

        answer = input("Did you send this? (y/n/q): ").strip().lower()

        if answer == "q":
            print("Quitting — progress saved.")
            remaining.append(d)
            quit_early = True
        elif answer == "y":
            applied.append({
                "company_name": d["company_name"],
                "url": d["url"],
                "email": d["email"],
                "date_applied": str(date.today()),
                "followed_up": False,
            })
            print("    ✅ Recorded as applied + removed from drafts\n")
        else:  # 'n'
            rejected.append({
                "company_name": d["company_name"],
                "url": d["url"],
                "date_rejected": str(date.today()),
            })
            print("    🚫 Recorded as rejected + removed from drafts\n")

    save_json(APPLIED_FILE, applied)
    save_json(REJECTED_FILE, rejected)
    save_json(DRAFTS_FILE, remaining)

    print("=" * 55)
    print(f"Done! {len(applied)} applied, {len(rejected)} rejected.")
    print(f"{len(remaining)} drafts left in {DRAFTS_FILE}")


if __name__ == "__main__":
    main()
