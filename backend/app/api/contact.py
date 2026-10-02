"""Contact form (the second contact channel of the legal notice) and the admin inbox.

Messages are stored in the application's own database, so no third-party form service sees
them, and are deleted after ``CONTACT_RETENTION_DAYS``. The sender's IP address is not stored;
it is only held in memory for an hour to rate-limit the form. With ``SMTP_HOST`` configured, a
copy of each message is e-mailed to ``LEGAL_EMAIL``.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlmodel import Session, col, delete, select

from app.core.config import Settings
from app.core.database import get_session
from app.core.security import LoginRateLimiter, require_admin, settings_dependency
from app.models.entities import ContactMessage
from app.models.schemas import ContactCreate, ContactOut, ContactUpdate

log = logging.getLogger(__name__)

router = APIRouter(tags=["contact"])
admin_router = APIRouter(
    prefix="/admin/messages", tags=["admin"], dependencies=[Depends(require_admin)]
)


def purge_expired(session: Session, retention_days: int) -> None:
    """Delete messages older than the retention period (storage limitation, Art. 5(1)(e) GDPR)."""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    session.exec(delete(ContactMessage).where(col(ContactMessage.created_at) < cutoff))  # type: ignore[call-overload]
    session.commit()


def _limiter(request: Request) -> LoginRateLimiter:
    limiter = getattr(request.app.state, "contact_limiter", None)
    if limiter is None:
        settings: Settings = request.app.state.settings
        limiter = LoginRateLimiter(
            settings.contact_messages_per_hour,
            window=3600,
            message="Too many messages, please try again later",
        )
        request.app.state.contact_limiter = limiter
    return limiter


def notify(settings: Settings, message: ContactCreate) -> None:
    """E-mail a copy of the message to the operator (only with SMTP configured)."""
    if not (settings.smtp_host and settings.legal_email):
        return
    mail = EmailMessage()
    mail["Subject"] = "ECCE contact form"
    mail["From"] = settings.smtp_from or settings.smtp_username or settings.legal_email
    mail["To"] = settings.legal_email
    mail["Reply-To"] = message.email
    mail.set_content(f"From: {message.name or '-'} <{message.email}>\n\n{message.message}\n")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(mail)
    except Exception:  # noqa: BLE001  (the message is stored either way)
        log.exception("contact notification e-mail failed")


@router.post("/contact", status_code=status.HTTP_202_ACCEPTED)
def send_message(
    body: ContactCreate,
    request: Request,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    settings: Settings = Depends(settings_dependency),
    limiter: LoginRateLimiter = Depends(_limiter),
) -> dict[str, str]:
    """Store a message for the operator."""
    if body.website:  # honeypot filled in: answer like a success, store nothing
        return {"status": "received"}
    limiter.check(request.client.host if request.client else "anonymous")
    purge_expired(session, settings.contact_retention_days)
    session.add(
        ContactMessage(name=body.name.strip(), email=body.email.strip(), message=body.message)
    )
    session.commit()
    background.add_task(notify, settings, body)
    return {"status": "received"}


@admin_router.get("", response_model=list[ContactOut])
def list_messages(
    session: Session = Depends(get_session),
    settings: Settings = Depends(settings_dependency),
) -> list[ContactMessage]:
    purge_expired(session, settings.contact_retention_days)
    query = select(ContactMessage).order_by(col(ContactMessage.created_at).desc())
    return list(session.exec(query).all())


@admin_router.patch("/{message_id}", response_model=ContactOut)
def update_message(
    message_id: int, body: ContactUpdate, session: Session = Depends(get_session)
) -> ContactMessage:
    message = session.get(ContactMessage, message_id)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    message.handled = body.handled
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


@admin_router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(message_id: int, session: Session = Depends(get_session)) -> None:
    message = session.get(ContactMessage, message_id)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    session.delete(message)
    session.commit()
