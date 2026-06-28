"""
render_drafts.py — Turn drafts.json into a nice HTML page + notify
==================================================================
Call render_and_notify() at the end of your run.
It builds drafts.html (clean, email-like), pops a Windows notification,
and opens the HTML in your browser.

Setup:
    pip install plyer
"""

import json
import os
import html
import webbrowser
from datetime import datetime

DRAFTS_FILE = "drafts.json"
HTML_FILE = "drafts.html"


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                content = f.read().strip()
                return json.loads(content) if content else default
        except (json.JSONDecodeError, ValueError):
            return default
    return default


def build_html(drafts):
    """Build a clean HTML page from the drafts list."""
    today = datetime.now().strftime("%A, %d %B %Y · %I:%M %p")

    cards = ""
    for d in drafts:
        # escape user/content text so it renders safely
        name = html.escape(d.get("company_name", "Unknown"))
        email = html.escape(d.get("email", "") or "")
        subject = html.escape(d.get("subject", ""))
        body = html.escape(d.get("body", "")).replace("\n", "<br>")
        url = html.escape(d.get("url", ""))

        email_line = (
            f'<a href="mailto:{email}" class="email">{email}</a>'
            if email else '<span class="noemail">no email — find manually</span>'
        )

        cards += f"""
        <article class="card">
          <header class="card-head">
            <h2>{name}</h2>
            <a href="{url}" target="_blank" class="site">{url}</a>
          </header>
          <div class="meta">
            <span class="label">To</span> {email_line}
          </div>
          <div class="meta">
            <span class="label">Subject</span> <span class="subject">{subject}</span>
          </div>
          <div class="body">{body}</div>
        </article>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Internship Drafts</title>
<style>
  :root {{
    --ink: #1a1a2e;
    --muted: #6b7280;
    --line: #e5e7eb;
    --accent: #2563eb;
    --bg: #f7f8fa;
    --card: #ffffff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px 16px;
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
    line-height: 1.6;
  }}
  .wrap {{ max-width: 720px; margin: 0 auto; }}
  .page-head {{ margin-bottom: 28px; }}
  .page-head h1 {{ margin: 0 0 4px; font-size: 26px; letter-spacing: -0.02em; }}
  .page-head p {{ margin: 0; color: var(--muted); font-size: 14px; }}
  .count {{
    display: inline-block; margin-top: 12px; padding: 4px 12px;
    background: var(--accent); color: #fff; border-radius: 999px;
    font-size: 13px; font-weight: 600;
  }}
  .card {{
    background: var(--card); border: 1px solid var(--line);
    border-radius: 14px; padding: 22px 24px; margin-bottom: 18px;
  }}
  .card-head {{ display: flex; justify-content: space-between;
    align-items: baseline; gap: 12px; margin-bottom: 14px; }}
  .card-head h2 {{ margin: 0; font-size: 19px; }}
  .site {{ font-size: 12px; color: var(--muted); text-decoration: none;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 240px; }}
  .site:hover {{ color: var(--accent); }}
  .meta {{ font-size: 14px; margin-bottom: 6px; }}
  .label {{ display: inline-block; width: 64px; color: var(--muted);
    font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }}
  .email {{ color: var(--accent); text-decoration: none; }}
  .noemail {{ color: #b45309; font-style: italic; }}
  .subject {{ font-weight: 600; }}
  .body {{ margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line);
    font-size: 15px; white-space: normal; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="page-head">
      <h1>Internship Email Drafts</h1>
      <p>Generated {today}</p>
      <span class="count">{len(drafts)} drafts ready</span>
    </div>
    {cards}
  </div>
</body>
</html>"""


def render_and_notify():
    drafts = load_json(DRAFTS_FILE, [])
    if not drafts:
        print("No drafts to render.")
        return

    # Build + write the HTML
    page = build_html(drafts)
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(page)

    # Pop a Windows notification (optional — won't crash if plyer missing)
    try:
        from plyer import notification
        notification.notify(
            title="Internship Agent",
            message=f"{len(drafts)} drafts ready — opening now",
            timeout=10,
        )
    except Exception:
        pass  # notification is a nice-to-have, not essential

    # Open the HTML in the default browser
    full_path = os.path.abspath(HTML_FILE)
    webbrowser.open(f"file://{full_path}")
    print(f"Opened {HTML_FILE} with {len(drafts)} drafts.")


if __name__ == "__main__":
    render_and_notify()