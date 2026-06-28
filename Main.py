"""
Internship Outreach Agent — v4
===============================
New in v4 — better at rejecting news articles / aggregators:
  - Expanded blocklist (news sites, press release wires)
  - Claude now checks "is this the company's OWN website?"
  - Negative keywords in queries (-news -article) to push search away from articles

Setup:
    pip install tavily-python anthropic

Run:
    python agent.py
"""

from tavily import TavilyClient
import anthropic
import json
import os
import re
import draft_emails
import render_drafts
from urllib.parse import urlparse
from dotenv import load_dotenv

# =========================================================
#  CONFIG
# =========================================================
load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-haiku-4-5-20251001"

SEEN_FILE = "seen_companies.json"
SEEN_NAMES_FILE = "seen_names.json"
APPLIED_FILE = "applied_companies.json"
RESULTS_FILE = "companies_ready.json"
TRIED_TOPICS_FILE = "tried_topics.json"

NUM_QUERIES = 5
RESULTS_PER_QUERY = 10

# Appended to every query to steer the search engine away from articles
NEGATIVE_KEYWORDS = "-news -article -press -funding"

BLOCKLIST = [
    # job boards / aggregators / directories
    "glassdoor", "seek.com", "indeed", "linkedin.com", "wellfound.com",
    "jora", "adzuna", "jobsearch", "gradconnection", "prosple", "f6s.com",
    "builtinsydney", "builtin.com", "themartec", "startupblink", "crunchbase",
    "clutch.co", "goodfirms", "designrush",
    # news sites / press wires
    "itnews", "startupdaily", "techcrunch", "afr.com", "smartcompany",
    "businessnewsaus", "ibtimes", "smh.com.au", "theaustralian", "forbes",
    "prnewswire", "businesswire", "yahoo", "msn.com", "news.com.au",
    "theguardian", "abc.net.au", "zdnet", "ft.com",
    # tech giants
    "google.com", "amazon", "microsoft", "meta.com", "apple.com",
    "ibm.com", "oracle.com", "deloitte", "accenture", "kpmg", "pwc", "ey.com",
    # misc
    "reddit.com", "wikipedia", "youtube", "facebook", "medium.com",
]

# =========================================================
#  CLIENTS
# =========================================================
tavily = TavilyClient(api_key=TAVILY_API_KEY)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# =========================================================
#  JSON helpers
# =========================================================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                content = f.read().strip()
                if not content:          # empty file
                    return default
                return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            print(f"    ⚠️ {path} was empty or corrupted, starting fresh")
            return default
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# =========================================================
#  STEP 0 — Claude generates fresh queries
# =========================================================
def generate_queries(num_queries, avoid_topics):
    avoid_text = ""
    if avoid_topics:
        recent = avoid_topics[-20:]
        avoid_text = f"\nAvoid repeating these already-tried angles:\n{', '.join(recent)}"

    prompt = f"""Generate {num_queries} diverse web search queries to find
small-to-medium DATA / ANALYTICS / TECH companies based in SYDNEY that a
data science student could approach for an internship.

Vary the angle each time: different industries (fintech, healthtech, proptech,
logistics, climate, retail...), different Sydney areas, different stages.{avoid_text}

Respond ONLY with a JSON array of strings. Example:
["fintech data startup Sydney", "healthtech analytics Sydney"]"""

    message = claude.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip().replace("```json", "").replace("```", "").strip()

    try:
        queries = json.loads(raw)
        if isinstance(queries, list):
            return queries
    except json.JSONDecodeError:
        pass
    return ["data analytics startup Sydney", "AI startup Sydney data analyst"]


# =========================================================
#  STEP 1 — Search (with negative keywords)
# =========================================================
def search_all(queries, max_results):
    seen_this_run = set()
    results = []

    for query in queries:
        full_query = f"{query} {NEGATIVE_KEYWORDS}"
        print(f"  Searching: {full_query}")
        response = tavily.search(query=full_query, max_results=max_results, search_depth="basic")
        for item in response.get("results", []):
            url = item.get("url")
            if url in seen_this_run:
                continue
            seen_this_run.add(url)
            results.append({
                "title": item.get("title"),
                "url": url,
                "content": item.get("content"),
            })

    return results


# =========================================================
#  Blocklist
# =========================================================
def is_blocked(url):
    return any(b in url.lower() for b in BLOCKLIST)


def clean_name(name):
    """Lowercase + strip common suffixes so 'Synogize Pty Ltd' == 'Synogize'."""
    name = name.lower()
    name = re.sub(r'\b(pty|ltd|limited|inc|group|technologies|tech|analytics|consulting|solutions)\b', '', name)
    name = re.sub(r'[^a-z0-9]', '', name)   # keep only letters/numbers
    return name.strip()


# =========================================================
#  STEP 2 — Judge with Claude (now checks official site)
# =========================================================
def analyse_company(company):
    prompt = f"""You are helping a student find companies to approach for an internship.

Page found via web search:
Title: {company['title']}
URL: {company['url']}
Description: {company['content']}

IMPORTANT: This is about ONE company only. Return a SINGLE JSON object, never a list.

Respond ONLY with valid JSON:
{{
  "company_name": "<clean company name>",
  "is_official_site": <true/false — is this URL the company's OWN website, NOT a news article, press release, blog post, or third-party listing ABOUT the company?>,
  "is_real_company": <true/false — a real company with its own product/service, NOT a job board/aggregator/directory>,
  "is_sydney": <true/false>,
  "relevant": <true/false — data/analytics/tech>,
  "is_right_size": <true/false — startup or SME, NOT a global giant>,
  "summary": "<one sentence on what they do>"
}}"""

    message = claude.messages.create(
        model=MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip().replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(f"    ⚠️ Could not parse response")
        return None

    if not isinstance(parsed, dict):
        print(f"    ⚠️ Claude returned a list, skipping")
        return None
    return parsed


# =========================================================
#  STEP 3 — Find a contact email
# =========================================================
EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

PREFERRED_PREFIXES = [
    "careers", "talent", "jobs", "recruiting", "recruitment", "hr",
    "people", "work", "join", "hello", "contact", "info", "team", "enquiries",
]


def extract_domain(url):
    """
    From 'https://www.synogize.io/about' return 'synogize.io'.
    Strips www. so matching is reliable.
    """
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def score_email(email, company_domain):
    """
    Lower score = better. Used to rank candidate emails.
    -100 bonus if the prefix is HR/careers related.
    """
    prefix = email.split("@")[0].lower()
    for i, p in enumerate(PREFERRED_PREFIXES):
        if prefix.startswith(p):
            return i  # earlier in the list = better (smaller number)
    return 999  # not a preferred prefix


def find_email(company, tavily):
    """
    Search for the company's contact email, but ONLY accept emails whose
    domain matches the company's own website domain.
    Returns the best matching email, or '' if none found.
    """
    company_domain = extract_domain(company["url"])
    if not company_domain:
        return ""

    # Search a couple of angles to gather candidate emails
    queries = [
        f"{company['company_name']} careers contact email",
        f"{company['company_name']} contact email",
    ]

    blob = ""
    for q in queries:
        try:
            response = tavily.search(query=q, max_results=3, search_depth="basic")
            for item in response.get("results", []):
                blob += " " + (item.get("content") or "")
        except Exception:
            continue

    # Find all emails, keep only ones on the company's own domain
    candidates = []
    for m in re.findall(EMAIL_REGEX, blob):
        low = m.lower()
        # skip obvious junk
        if any(bad in low for bad in [
            "example.com", "sentry", ".png", ".jpg", "wixpress", "@2x",
            "john.doe", "jane.doe", "firstname", "lastname", "yourname",
            "email@", "name@", "user@", "someone@"
        ]):
            continue
        # KEY FILTER: domain must match the company's website
        if company_domain in low:
            candidates.append(low)

    if not candidates:
        return ""

    # De-duplicate, then pick the best (HR/careers preferred)
    candidates = list(set(candidates))
    candidates.sort(key=lambda e: score_email(e, company_domain))
    return candidates[0]


# =========================================================
#  MAIN
# =========================================================
def main():
    seen = set(load_json(SEEN_FILE, []))
    seen_names = set(load_json(SEEN_NAMES_FILE, []))          # NEW
    tried_topics = load_json(TRIED_TOPICS_FILE, [])

    # NEW: load companies you've already applied to, add their names to seen_names
    applied = load_json(APPLIED_FILE, [])
    for a in applied:
        seen_names.add(clean_name(a["company_name"]))

    print(f"Loaded {len(seen)} seen URLs, {len(seen_names)} known company names.\n")

    print("=" * 55)
    print("STEP 0: Claude generating fresh queries...")
    print("=" * 55)
    queries = generate_queries(NUM_QUERIES, tried_topics)
    for q in queries:
        print(f"  • {q}")
    tried_topics.extend(queries)

    print("\n" + "=" * 55)
    print("STEP 1: Searching...")
    print("=" * 55)
    companies = search_all(queries, RESULTS_PER_QUERY)
    new_companies = [c for c in companies if c["url"] not in seen]
    print(f"\nFound {len(companies)} ({len(new_companies)} new).\n")

    print("=" * 55)
    print("STEP 2+3: Filtering + finding emails...")
    print("=" * 55)

    keepers = []
    for i, company in enumerate(new_companies, 1):
        url = company["url"]
        print(f"[{i}/{len(new_companies)}] {url}")
        seen.add(url)

        if is_blocked(url):
            print("    ⛔ BLOCKED")
            continue

        result = analyse_company(company)
        if result is None:
            continue

        # Now requires is_official_site to be true as well
        passed = (result.get("is_official_site")
                  and result.get("is_real_company")
                  and result.get("is_sydney")
                  and result.get("relevant")
                  and result.get("is_right_size"))

        if not passed:
            reason = "not official site" if not result.get("is_official_site") else "failed filter"
            print(f"    ❌ SKIP: {result.get('company_name', 'Unknown')} ({reason})")
            continue

            # NEW: skip if we've already seen/applied to this company (by name)
        name_key = clean_name(result["company_name"])
        if name_key in seen_names:
            print(f"    ⏭️  ALREADY KNOWN: {result['company_name']}")
            continue
        seen_names.add(name_key)

        result["url"] = url
        result["email"] = find_email(result, tavily)

        email_note = result["email"] if result["email"] else "(no email found)"
        keepers.append(result)
        print(f"    ✅ KEEP: {result['company_name']} — {email_note}")

    save_json(SEEN_FILE, list(seen))
    save_json(SEEN_NAMES_FILE, list(seen_names))  # NEW
    save_json(TRIED_TOPICS_FILE, tried_topics)

    existing = load_json(RESULTS_FILE, [])
    existing_urls = {c["url"] for c in existing}
    for k in keepers:
        if k["url"] not in existing_urls:
            existing.append(k)
    save_json(RESULTS_FILE, existing)

    print("\n" + "=" * 55)
    print(f"DONE! {len(keepers)} new companies this run.")
    print(f"Master list now has {len(existing)} companies in {RESULTS_FILE}")
    print("=" * 55)

    print("\n\n--- NEW COMPANIES THIS RUN ---\n")
    for k in keepers:
        print(f"### {k['company_name']}  ({k['url']})")
        print(f"    {k['summary']}")
        print(f"    📧 {k['email'] or '(no email found)'}\n")

if __name__ == "__main__":
    main()
    draft_emails.main()
    render_drafts.render_and_notify()