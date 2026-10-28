"""Disposable PostgreSQL + API fixture for the browser acceptance test; run from repo root.

Requires local Web on :3100, STOCKLAB_PG_BIN, and Playwright module (see delivery doc).
Uses only generated test users, never the configured application database.
"""

import json
import os
import subprocess
import tempfile
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from uuid import uuid4

from app.db.models import Instrument, PortfolioPrivacyAcceptance, User
from app.security import create_access_token
from app.services.portfolio import POLICY, POLICY_SHA256, create_account
from app.settings import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

root = Path.cwd()
binary = Path(os.environ["STOCKLAB_PG_BIN"])
work = Path(tempfile.mkdtemp(prefix="stock-v251r-live-"))
url = "postgresql+psycopg://stocktest@127.0.0.1:55454/postgres"
env = {
    **os.environ,
    "STOCKLAB_DATABASE_URL": url,
    "STOCKLAB_PORTFOLIO_ENABLED": "true",
    "PYTHONPATH": str(root / "apps/api") + os.pathsep + str(root),
}
python = str(root / ".venv/bin/python")
api = None
started = False
try:
    with (work / "init.log").open("w") as log:
        subprocess.run(
            [
                str(binary / "initdb"),
                "-D",
                str(work / "data"),
                "-U",
                "stocktest",
                "-A",
                "trust",
            ],
            check=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    subprocess.run(
        [
            str(binary / "pg_ctl"),
            "-D",
            str(work / "data"),
            "-l",
            str(work / "pg.log"),
            "-o",
            f"-p 55454 -h 127.0.0.1 -k {work}",
            "-w",
            "start",
        ],
        check=True,
    )
    started = True
    subprocess.run(
        [python, "-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head"],
        env=env,
        check=True,
    )
    engine = create_engine(url)
    settings.portfolio_enabled = True
    with Session(engine) as s:
        owner = User(
            email="browser-ledger@example.com",
            email_verified_at=datetime.now(UTC),
            plan="free",
        )
        s.add_all(
            [
                owner,
                Instrument(code="600036", name="招商银行", type="stock", exchange="SH"),
                Instrument(code="601088", name="中国神华", type="stock", exchange="SH"),
            ]
        )
        s.flush()
        a = create_account(
            s,
            owner.id,
            "浏览器验收账本",
            {"accepted": True, "version": POLICY["version"], "sha256": POLICY_SHA256},
        )
        old = PortfolioPrivacyAcceptance(
            id=str(uuid4()),
            user_id=owner.id,
            policy_version="portfolio-account-2026-10-27.v1",
            policy_sha256="a" * 64,
            policy_snapshot={"scope": "private_account_metadata"},
            accepted_at=datetime.now(UTC),
        )
        s.add(old)
        s.flush()
        a.privacy_acceptance_id = old.id
        s.commit()
        (work / "fixture.json").write_text(
            json.dumps({"token": create_access_token(owner), "account_id": a.id})
        )
    (work / "fixture.json").chmod(0o600)
    env["STOCKLAB_BROWSER_FIXTURE"] = str(work / "fixture.json")
    env["STOCKLAB_BROWSER_OUTPUT"] = str(work)
    with (work / "api.log").open("w") as log:
        api = subprocess.Popen(
            [
                python,
                "-m",
                "uvicorn",
                "app.main:app",
                "--port",
                "8012",
                "--host",
                "127.0.0.1",
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        for i in range(100):
            try:
                urllib.request.urlopen("http://127.0.0.1:8012/healthz", timeout=1)
                break
            except (URLError, TimeoutError, ConnectionError):
                time.sleep(0.2)
        else:
            raise RuntimeError("Disposable API did not become ready")
        subprocess.run(
            ["node", str(root / "apps/web/tests/portfolio-positions.browser.cjs")],
            env=env,
            check=True,
        )
    engine.dispose()
finally:
    if api:
        api.terminate()
        api.wait(timeout=10)
    if started:
        subprocess.run(
            [
                str(binary / "pg_ctl"),
                "-D",
                str(work / "data"),
                "-w",
                "-m",
                "fast",
                "stop",
            ],
            check=True,
        )
    print("Evidence", work, flush=True)
