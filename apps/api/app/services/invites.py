from __future__ import annotations

import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InviteCode

ALPHABET = string.ascii_uppercase + string.digits


def new_invite_code() -> str:
    return "INV" + "".join(secrets.choice(ALPHABET) for _ in range(10))


def generate_invites(
    session: Session,
    *,
    count: int,
    max_uses: int = 1,
    valid_days: int = 90,
    note: str | None = None,
) -> tuple[str, list[InviteCode]]:
    batch_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=valid_days)
    rows: list[InviteCode] = []
    for _ in range(count):
        code = new_invite_code()
        for _attempt in range(5):
            if session.get(InviteCode, code) is None:
                break
            code = new_invite_code()
        else:
            raise RuntimeError("failed to generate a unique invite code")
        row = InviteCode(
            code=code,
            batch_id=batch_id,
            max_uses=max_uses,
            note=note,
            expires_at=expires_at,
        )
        session.add(row)
        rows.append(row)
    session.commit()
    return batch_id, rows


def consume_invite_code(session: Session, raw_code: str) -> InviteCode:
    code = raw_code.strip().upper()
    row = session.scalar(
        select(InviteCode).where(InviteCode.code == code).with_for_update()
    )
    if row is None or row.status != "issued":
        raise ValueError("邀请码无效或已用完")
    expires = row.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires is not None and expires < datetime.now(UTC):
        row.status = "expired"
        raise ValueError("邀请码已过期")
    if row.used_count >= row.max_uses:
        raise ValueError("邀请码无效或已用完")
    row.used_count += 1
    if row.used_count >= row.max_uses:
        row.status = "redeemed"
    return row
