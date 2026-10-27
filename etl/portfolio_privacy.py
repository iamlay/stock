"""Operator-only deletion manifest export/replay. Keep manifests outside restored backups."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from app.db.models import PortfolioAccount, PortfolioAuditEvent, PortfolioDeletion, User
from app.services.portfolio import lock_owner
from sqlalchemy import delete, select
from sqlalchemy.orm import Session


def export_deletions(session: Session) -> dict:
    rows = session.scalars(select(PortfolioDeletion).order_by(PortfolioDeletion.account_id)).all()
    return {
        "schema_version": "portfolio-deletion-manifest-v1",
        "deletions": [
            {
                "account_id": row.account_id,
                "user_id": row.user_id,
                "deleted_at": (
                    row.deleted_at if row.deleted_at.tzinfo else row.deleted_at.replace(tzinfo=UTC)
                ).isoformat(),
            }
            for row in rows
        ],
    }


def replay_deletions(session: Session, manifest: dict, *, apply: bool = False) -> dict:
    if manifest.get("schema_version") != "portfolio-deletion-manifest-v1":
        raise ValueError("unsupported deletion manifest")
    rows = manifest.get("deletions")
    if not isinstance(rows, list) or len(rows) > 100_000:
        raise ValueError("manifest must contain at most 100000 deletion records")
    parsed = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"account_id", "user_id", "deleted_at"}:
            raise ValueError("invalid deletion record")
        account_id = str(UUID(row["account_id"]))
        user_id = row["user_id"]
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 1:
            raise ValueError("invalid owner ID")
        stamp = datetime.fromisoformat(row["deleted_at"])
        if account_id in parsed or stamp.tzinfo is None:
            raise ValueError("duplicate account or missing timestamp timezone")
        parsed[account_id] = (user_id, stamp)
    for owner in sorted({user_id for user_id, _ in parsed.values()}):
        if session.get(User, owner):
            lock_owner(session, owner)
    # Validate every owner before ANY destructive statement.
    found = []
    for account_id, (user_id, _) in parsed.items():
        account = session.get(PortfolioAccount, account_id)
        if account:
            if account.user_id != user_id:
                raise ValueError("manifest ownership mismatch; no accounts deleted")
            found.append(account)
        marker = session.get(PortfolioDeletion, account_id)
        if marker and marker.user_id != user_id:
            raise ValueError("manifest marker ownership mismatch")
    if apply:
        from app.services.portfolio_ledger import clear_ledger

        for account in found:
            clear_ledger(session, account.user_id, account.id)
            session.execute(
                delete(PortfolioAuditEvent).where(
                    PortfolioAuditEvent.account_id == account.id,
                    PortfolioAuditEvent.user_id == account.user_id,
                )
            )
            session.delete(account)
        for account_id, (user_id, stamp) in parsed.items():
            if session.get(User, user_id) and not session.get(PortfolioDeletion, account_id):
                session.add(
                    PortfolioDeletion(account_id=account_id, user_id=user_id, deleted_at=stamp)
                )
        session.flush()
    return {"manifest_records": len(parsed), "matched_accounts": len(found), "applied": apply}


def main(argv: list[str] | None = None) -> int:
    from app.db.session import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export-deletions")
    export.add_argument("--output", type=Path, required=True)
    replay = commands.add_parser("replay-deletions")
    replay.add_argument("--manifest", type=Path, required=True)
    replay.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    with SessionLocal() as session:
        if args.command == "export-deletions":
            data = export_deletions(session)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            # New file only, mode 0600. Do not overwrite a previous recovery manifest.
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
            print(json.dumps({"exported": len(data["deletions"])}))
        else:
            if args.manifest.stat().st_size > 25_000_000:
                raise ValueError("manifest too large")
            result = replay_deletions(
                session, json.loads(args.manifest.read_text()), apply=args.apply
            )
            if args.apply:
                session.commit()
            print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
