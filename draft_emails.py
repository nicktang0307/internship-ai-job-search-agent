"""
draft_emails.py — Draft personalised cold emails
=================================================
Reads companies_ready.json (from the agent), drafts an email for EACH company
(whether or not an email address was found), and saves them to drafts.json.

You review drafts.json, send the ones you want, then run mark_applied.py.

Setup:
    pip install anthropic

Run:
    python draft_emails.py
"""

import anthropic
import json
import os
import re
from dotenv import load_dotenv

# =========================================================
#  CONFIG
# =========================================================
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-haiku-4-5-20251001"

RESULTS_FILE = "companies_ready.json"      # input (from agent)
APPLIED_FILE = "applied_companies.json"    # companies already emailed
REJECTED_FILE = "rejected.json"
DRAFTS_FILE = "drafts.json"                # output

# Your background — Claude uses this to personalise each email
MY_PROFILE = """
Name: 
Status: 

What I'm looking for:


Background:


Skills: 

Tone preference: 
"""

# =========================================================
#  CLIENT
# =========================================================
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                content = f.read().strip()
                return json.loads(content) if content else default
        except (json.JSONDecodeError, ValueError):
            print(f"⚠️ {path} was empty or corrupted, starting fresh")
            return default
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def clean_name(name):
    name = name.lower()
    name = re.sub(r'\b(pty|ltd|limited|inc|group|technologies|tech|analytics|consulting|solutions|media|agency|digital|studio|studios|labs|co)\b', '', name)
    name = re.sub(r'[^a-z0-9]', '', name)
    return name.strip()


def draft_email(company):
    prompt = f"""You are helping a student write a cold email for an internship.

Student profile:
{MY_PROFILE}

Company:
Name: {company['company_name']}
What they do: {company['summary']}
Website: {company['url']}

Write a short, casual cold email (under 80 words) asking about an unpaid internship.
Mention something specific about what the company does so it feels personalised.

Respond ONLY with valid JSON:
{{
  "subject": "<subject line>",
  "body": "<email body, starting with 'Hi [Company] team,'>"
}}"""

    message = claude.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip().replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return None


def main():
    companies = load_json(RESULTS_FILE, [])
    if not companies:
        print(f"No companies found in {RESULTS_FILE}. Run the agent first.")
        return

    # Build a set of names we should NOT draft for:
    #   1) companies already applied to
    #   2) companies already drafted (avoid re-drafting)
    applied = load_json(APPLIED_FILE, [])
    applied_names = {clean_name(a["company_name"]) for a in applied}
    applied_urls = {a["url"] for a in applied}

    rejected = load_json(REJECTED_FILE, [])
    rejected_names = {clean_name(r["company_name"]) for r in rejected}
    rejected_urls = {r["url"] for r in rejected}

    existing_drafts = load_json(DRAFTS_FILE, [])
    drafted_names = {clean_name(d["company_name"]) for d in existing_drafts}
    drafted_urls = {d["url"] for d in existing_drafts}

    # Decide which companies still need a draft
    to_draft = []
    for c in companies:
        name_key = clean_name(c["company_name"])
        if name_key in applied_names or c["url"] in applied_urls:
            continue  # already applied — skip
        if name_key in rejected_names or c["url"] in rejected_urls:
            continue  # rejected — skip
        if name_key in drafted_names or c["url"] in drafted_urls:
            continue  # already drafted — skip
        to_draft.append(c)

    print(f"{len(companies)} in master list, {len(applied)} applied, "
          f"{len(to_draft)} need drafting.\n")

    for i, company in enumerate(to_draft, 1):
        print(f"[{i}/{len(to_draft)}] Drafting for {company['company_name']}...")
        draft = draft_email(company)
        if draft is None:
            print("    ⚠️ Draft failed, skipping")
            continue

        existing_drafts.append({
            "company_name": company["company_name"],
            "url": company["url"],
            "email": company.get("email", ""),
            "subject": draft["subject"],
            "body": draft["body"],
        })

    save_json(DRAFTS_FILE, existing_drafts)
    print(f"\nDone! {len(existing_drafts)} total drafts in {DRAFTS_FILE}\n")

    print("=" * 55)
    print("DRAFTS FOR REVIEW")
    print("=" * 55)
    for d in existing_drafts:
        print(f"\n### {d['company_name']}")
        print(f"To: {d['email'] or '(no email — find manually)'}")
        print(f"Subject: {d['subject']}")
        print(f"\n{d['body']}")
        print("-" * 50)


if __name__ == "__main__":
    main()
