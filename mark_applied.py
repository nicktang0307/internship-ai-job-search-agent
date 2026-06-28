"""
mark_applied.py — Track which companies you actually emailed
=============================================================
Reads drafts.json, shows each draft, asks if you sent it.
- 'y' → recorded in applied_companies.json AND removed from drafts.json
- 'n' → removed from drafts.json (you decided to skip it)
- 'q' → quit, saving progress so far

So once you've answered for a company, it won't show up again next time.

Run:
    python mark_applied.py
"""

import json
import os
from datetime import date

DRAFTS_FILE = "drafts.json"
APPLIED_FILE = "applied_companies.json"


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


def main():
    drafts = load_json(DRAFTS_FILE, [])
    if not drafts:
        print(f"No drafts found in {DRAFTS_FILE}. Run draft_emails.py first.")
        return

    applied = load_json(APPLIED_FILE, [])

    print(f"{len(drafts)} drafts to review.")
    print("For each: 'y' = sent it, 'n' = skip it, 'q' = quit.")
    print("Either way (y or n), the company is removed from drafts.\n")

    # We'll keep only the drafts we DIDN'T get to (in case of quit)
    remaining = []

    quit_early = False
    for i, d in enumerate(drafts, 1):
        if quit_early:
            remaining.append(d)   # keep the rest untouched
            continue

        print("=" * 55)
        print(f"[{i}/{len(drafts)}] {d['company_name']}")
        print(f"To: {d['email'] or '(no email — find manually)'}")
        print(f"Subject: {d['subject']}")
        print(f"\n{d['body']}\n")

        answer = input("Did you send this? (y/n/q): ").strip().lower()

        if answer == "q":
            print("Quitting — progress saved.")
            remaining.append(d)   # this one wasn't decided, keep it
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
            # not added to remaining → removed from drafts
        else:  # 'n' or anything else
            print("    ⏭️  Skipped + removed from drafts\n")
            # not added to remaining → removed from drafts

    # Save: applied list grows, drafts shrinks to only what's left
    save_json(APPLIED_FILE, applied)
    save_json(DRAFTS_FILE, remaining)

    print("=" * 55)
    print(f"Done! {len(applied)} companies in {APPLIED_FILE}")
    print(f"{len(remaining)} drafts left in {DRAFTS_FILE}")


if __name__ == "__main__":
    main()