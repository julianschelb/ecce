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
.box { border: 1px solid #d0d7de; border-radius: .5rem; padding: 0 1rem .5rem; background: #fff; }
"""


def address_lines(settings: Settings) -> list[str]:
    """``LEGAL_ADDRESS`` may separate lines with newlines or ``|``."""
    raw = (settings.legal_address or "").replace("|", "\n")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def operator_html(settings: Settings) -> str | None:
    """Name, postal address, e-mail and contact form of the operator, or ``None``.

    Name and e-mail are required; ``LEGAL_ADDRESS`` is shown when set (§ 5 DDG asks for an
    address at which documents can be served, so set it for a public instance)."""
    if not (settings.legal_name and settings.legal_email):
        return None
    lines = [escape(settings.legal_name), *(escape(line) for line in address_lines(settings))]
    email = escape(settings.legal_email)
    return (
        "<address>"
        + "<br>".join(lines)
        + f'<br>E-mail: <a href="mailto:{email}">{email}</a>'
        + '<br>Contact form: <a href="/contact">/contact</a></address>'
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
    "(settings <code>LEGAL_NAME</code> and <code>LEGAL_EMAIL</code>, and <code>LEGAL_ADDRESS</code>).</p>"
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
        '<p><a href="/privacy">Privacy policy</a> · <a href="/contact">Contact</a></p>'
    )
    return page("Legal notice", body)


def privacy_policy(settings: Settings) -> str:
    operator = operator_html(settings)
    on_railway = bool(settings.railway_project_id)
    days = settings.log_retention_days
    hosting = (
        f"<p>This site is hosted by {RAILWAY}, which processes the data described here on our "
        "behalf under a data processing agreement (Art. 28 GDPR). Railway processes data mainly in "
        "the United States. Railway is certified under the EU–U.S. Data Privacy Framework, for "
        "which the European Commission has adopted an adequacy decision (Art. 45 GDPR); in "
        "addition, Railway’s "
        '<a href="https://railway.com/legal/dpa">Data Processing Addendum</a> contains the EU '
        "Standard Contractual Clauses (Art. 46(2)(c) GDPR).</p>"
        if on_railway
        else "<p>This site is hosted on a server run by or on behalf of the operator.</p>"
    )
    mail_copy = (
        " A copy of each message is sent by e-mail to the operator’s mailbox; the operator’s "
        "e-mail provider stores it according to the operator’s mailbox settings."
        if settings.smtp_host
        else ""
    )
    body = (
        f'<p class="muted">Last updated: {UPDATED}</p>'
        "<h2>Controller</h2>"
        + (operator or NOT_CONFIGURED)
        + "<p>No data protection officer is required for this site.</p>"
        "<h2>Visiting this site (server logs)</h2>"
        "<p>Your browser sends each request to our server, which necessarily receives your IP "
        "address together with the date and time, the requested address, the referring page and "
        "your browser’s user agent. They are used to deliver the pages and are written to a "
        "technical log to detect and fix errors and to protect the service against attacks. "
        f"The log is deleted automatically after {days} days. The application itself does not "
        "store IP addresses in its database. Administrator sign-in attempts and contact form "
        "submissions are counted per IP address in memory (for one minute and one hour "
        "respectively) to prevent password guessing and spam; the address is then discarded. "
        "Legal basis: our legitimate interest in providing a secure and reliable website "
        "(Art. 6(1)(f) GDPR).</p>"
        "<h2>Contact form and e-mail</h2>"
        "<p>If you write to us through the contact form, we store your e-mail address, the "
        "optional name and your message with the time of sending, in order to answer you. Legal "
        "basis: our legitimate interest in answering enquiries, or the steps you requested "
        "(Art. 6(1)(f) and (b) GDPR). Messages are deleted once they are dealt with and "
        f"automatically after {settings.contact_retention_days} days at the latest.{mail_copy} "
        "The same applies if you write to us by e-mail.</p>"
        "<h2>Hosting</h2>" + hosting + "<h2>No cookies, no tracking, no consent needed</h2>"
        "<p>This site sets no cookies and uses no analytics, advertising or tracking, so no "
        "processing is based on your consent. Fonts, scripts and the API documentation are "
        "served from this server; no content is loaded from third parties. Links to other "
        "websites (for example the paper, GitHub or PyPI) only take you there when you click "
        "them.</p>"
        "<p>Only when an administrator signs in does the browser’s local storage keep the "
        "session token, until sign-out or expiry. This is strictly necessary for the requested "
        "sign-in (§ 25(2) no. 2 TDDDG).</p>"
        "<h2>Your rights</h2>"
        "<p>You have the right to access your personal data (Art. 15 GDPR), to rectification "
        "(Art. 16), erasure (Art. 17), restriction of processing (Art. 18) and data portability "
        "(Art. 20). To exercise them, contact the controller named above.</p>"
        '<div class="box"><h2>Right to object (Art. 21 GDPR)</h2>'
        "<p>Where we process your data on the basis of our legitimate interests "
        "(Art. 6(1)(f) GDPR), you have the right to object at any time, on grounds relating to "
        "your particular situation. We will then no longer process the data unless we can "
        "demonstrate compelling legitimate grounds which override your interests, rights and "
        "freedoms, or the processing serves the establishment, exercise or defence of legal "
        "claims.</p></div>"
        "<h2>Right to lodge a complaint</h2>"
        "<p>You can complain to a data protection supervisory authority (Art. 77 GDPR), in "
        "particular in the member state of your residence. The authority responsible for us is "
        "the Landesbeauftragte für den Datenschutz und die Informationsfreiheit Baden-Württemberg, "
        "Lautenschlagerstraße 20, 70173 Stuttgart, Germany, "
        '<a href="https://www.baden-wuerttemberg.datenschutz.de">baden-wuerttemberg.datenschutz.de</a>.</p>'
        '<p><a href="/legal">Legal notice</a> · <a href="/contact">Contact</a></p>'
    )
    return page("Privacy policy", body)
