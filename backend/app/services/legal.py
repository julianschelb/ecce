"""Legal notice (Impressum, § 5 DDG) and privacy policy (Art. 13 GDPR) as plain HTML pages.

Both pages are rendered by the backend so they are reachable without JavaScript and always name
the operator configured for this instance (``LEGAL_NAME``, ``LEGAL_ADDRESS``, ``LEGAL_EMAIL``).
The personal details live in the deployment's environment, not in the repository.
"""

from __future__ import annotations

from html import escape

from app.core.config import Settings

UPDATED = "29 September 2026"
RAILWAY = (
    "Railway Corporation, 548 Market St PMB 68956, San Francisco, CA 94104, USA "
    '(<a href="https://railway.com/legal/privacy">privacy policy</a>)'
)

STYLE = """
:root { color-scheme: light; }
body { margin: 0; background: #f7f6f2; color: #1f2328;
  font: 16px/1.6 "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 46rem; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
h1 { font: 600 2rem/1.2 "Source Serif 4", Georgia, serif; margin: 1.5rem 0 1rem; }
h2 { font: 600 1.2rem/1.3 "Source Serif 4", Georgia, serif; margin: 2rem 0 .5rem; }
a { color: #33618f; }
.back { font: 500 .8rem/1 "IBM Plex Mono", ui-monospace, monospace; text-transform: uppercase;
  letter-spacing: .05em; color: #57606a; text-decoration: none; }
.muted { color: #57606a; font-size: .9rem; }
address { font-style: normal; }
"""


def address_lines(settings: Settings) -> list[str]:
    """``LEGAL_ADDRESS`` may separate lines with newlines or ``|``."""
    raw = (settings.legal_address or "").replace("|", "\n")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def operator_html(settings: Settings) -> str | None:
    """Name, postal address and e-mail of the operator, or ``None`` when not configured."""
    if not (settings.legal_name and settings.legal_address and settings.legal_email):
        return None
    lines = [escape(settings.legal_name), *(escape(line) for line in address_lines(settings))]
    email = escape(settings.legal_email)
    return (
        "<address>"
        + "<br>".join(lines)
        + f'<br>E-mail: <a href="mailto:{email}">{email}</a></address>'
    )


def page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)} · ECCE</title>"
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
        f"<style>{STYLE}</style></head><body><main>"
        '<a class="back" href="/">← ECCE</a>'
        f"<h1>{escape(title)}</h1>{body}</main></body></html>"
    )


NOT_CONFIGURED = (
    "<p>The operator of this ECCE instance has not published contact details yet "
    "(settings <code>LEGAL_NAME</code>, <code>LEGAL_ADDRESS</code> and <code>LEGAL_EMAIL</code>).</p>"
)


def legal_notice(settings: Settings) -> str:
    operator = operator_html(settings)
    body = (
        "<p>Information according to § 5 DDG (German Digital Services Act).</p>"
        + (f"<h2>Operator</h2>{operator}" if operator else NOT_CONFIGURED)
        + "<h2>Texts</h2><p>The books in the gallery are in the public domain, except Vergil’s "
        "works, which are shared under the "
        '<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a> licence; '
        'see the <a href="https://github.com/julianschelb/ecce/blob/main/backend/data/seed/NOTICE.md">'
        "licence notice</a>. The software is open source (MIT licence).</p>"
        '<p><a href="/privacy">Privacy policy</a></p>'
    )
    return page("Legal notice", body)


def privacy_policy(settings: Settings) -> str:
    operator = operator_html(settings)
    on_railway = bool(settings.railway_project_id)
    hosting = (
        f"<p>This site is hosted by {RAILWAY}. Railway processes the data described above on "
        "our behalf (Art. 28 GDPR). Its processing takes place mainly in the United States; the "
        "transfer is based on the EU Standard Contractual Clauses (Art. 46(2)(c) GDPR) in "
        'Railway’s <a href="https://railway.com/legal/dpa">Data Processing Addendum</a>.</p>'
        if on_railway
        else "<p>This site is hosted on a server run by or on behalf of the operator.</p>"
    )
    body = (
        f'<p class="muted">Last updated: {UPDATED}</p>'
        "<h2>Controller</h2>"
        + (operator or NOT_CONFIGURED)
        + "<h2>What happens when you visit this site</h2>"
        "<p>Your browser sends each request to our server, which necessarily receives your IP "
        "address together with the date and time, the requested address, the referring page and "
        "your browser’s user agent. The server uses them to deliver the pages and writes them to a "
        "short-lived technical log to keep the service secure and working. The legal basis is our "
        "legitimate interest in providing a secure, reliable website (Art. 6(1)(f) GDPR). The "
        "application does not store IP addresses in its database; the hosting provider keeps the "
        "log for a limited period and then deletes it. Administrator sign-in attempts are counted "
        "per IP address in memory for one minute to prevent password guessing.</p>"
        "<h2>Hosting</h2>" + hosting + "<h2>No cookies, no tracking</h2>"
        "<p>This site sets no cookies and uses no analytics, advertising or tracking. Fonts, "
        "scripts and the API documentation are served from this server; no content is loaded from "
        "third parties. Links to other websites (for example the paper, GitHub or PyPI) only take "
        "you there when you click them.</p>"
        "<p>Only when an administrator signs in, the browser’s local storage keeps the session "
        "token until sign-out or expiry. This is strictly necessary for the requested sign-in "
        "(§ 25(2) no. 2 TDDDG).</p>"
        "<h2>Your rights</h2>"
        "<p>You have the right to access your personal data (Art. 15 GDPR), to rectification "
        "(Art. 16), erasure (Art. 17), restriction of processing (Art. 18) and data portability "
        "(Art. 20), and to object to processing based on legitimate interests (Art. 21). To "
        "exercise them, contact the controller named above. You also have the right to lodge a "
        "complaint with a data protection supervisory authority (Art. 77 GDPR), in particular in "
        "the member state of your residence or of the alleged infringement.</p>"
        '<p><a href="/legal">Legal notice</a></p>'
    )
    return page("Privacy policy", body)
