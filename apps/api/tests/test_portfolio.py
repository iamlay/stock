import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from etl.portfolio_privacy import export_deletions, replay_deletions
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import (
    AdminAuditLog,
    PortfolioAccount,
    PortfolioAuditEvent,
    PortfolioDeletion,
    PortfolioPrivacyAcceptance,
    User,
)
from app.db.session import get_session
from app.main import app
from app.security import create_access_token
from app.services.portfolio import POLICY, POLICY_SHA256
from app.settings import settings


@pytest.fixture
def clients(session, monkeypatch):
    monkeypatch.setattr(settings, "portfolio_enabled", True)
    monkeypatch.setattr(settings, "portfolio_user_ids", "")
    users = [
        User(
            email=f"private-{i}@example.com",
            email_verified_at=datetime.now(UTC),
            role="admin" if i == 2 else "member",
            plan="free",
        )
        for i in range(3)
    ]
    session.add_all(users)
    session.commit()
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        yield (
            client,
            users,
            [{"Authorization": f"Bearer {create_access_token(user)}"} for user in users],
        )
    app.dependency_overrides.clear()


def body(name="长期收息"):
    return {
        "name": name,
        "currency": "CNY",
        "consent": {
            "accepted": True,
            "version": POLICY["version"],
            "sha256": POLICY_SHA256,
        },
    }


def create(client, headers, name="长期收息"):
    response = client.post("/api/v1/portfolio/accounts", headers=headers, json=body(name))
    assert response.status_code == 201, response.text
    return response.json()


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_get_does_not_create_or_consent_and_always_no_store(session, clients):
    client, _, headers = clients
    for path, auth in [("/policy", {}), ("/accounts", headers[0]), ("/accounts", {})]:
        response = client.get("/api/v1/portfolio" + path, headers=auth)
        assert response.status_code == (401 if path == "/accounts" and not auth else 200)
        assert response.headers["cache-control"] == "private, no-store"
        assert "Cookie" in response.headers["vary"]
        assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert count(session, PortfolioAccount) == count(session, PortfolioPrivacyAcceptance) == 0
    policy = client.get("/api/v1/portfolio/policy").json()
    assert (
        policy["sha256"]
        == hashlib.sha256(
            json.dumps(
                policy["policy"], sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode()
        ).hexdigest()
    )


@pytest.mark.parametrize("accepted", [False, 0, 1, "true", None])
def test_consent_must_be_explicit_strict_boolean(session, clients, accepted):
    client, _, headers = clients
    data = body()
    data["consent"]["accepted"] = accepted
    response = client.post("/api/v1/portfolio/accounts", headers=headers[0], json=data)
    assert response.status_code == 422
    assert count(session, PortfolioAccount) == count(session, PortfolioPrivacyAcceptance) == 0


@pytest.mark.parametrize("field", ["version", "sha256"])
def test_stale_policy_cannot_be_silently_accepted(session, clients, field):
    client, _, headers = clients
    data = body()
    data["consent"][field] = "0" * 64
    response = client.post("/api/v1/portfolio/accounts", headers=headers[0], json=data)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "privacy_policy_changed"
    assert count(session, PortfolioPrivacyAcceptance) == 0


def test_create_atomic_owner_and_snapshot_record(session, clients):
    client, users, headers = clients
    account = create(client, headers[0])
    stored = session.get(PortfolioAccount, account["id"])
    acceptance = session.get(PortfolioPrivacyAcceptance, stored.privacy_acceptance_id)
    assert stored.user_id == acceptance.user_id == users[0].id
    assert acceptance.policy_snapshot == POLICY and acceptance.policy_sha256 == POLICY_SHA256
    assert count(session, PortfolioAuditEvent) == 1
    assert "user_id" not in account
    assert (
        client.post("/api/v1/portfolio/accounts", headers=headers[0], json=body()).status_code
        == 409
    )
    assert count(session, PortfolioAccount) == count(session, PortfolioPrivacyAcceptance) == 1


@pytest.mark.parametrize("name", [" ", "\n\x00name", "x" * 41])
def test_invalid_name_rejected_without_echo_or_side_effect(session, clients, name):
    client, _, headers = clients
    response = client.post("/api/v1/portfolio/accounts", headers=headers[0], json=body(name))
    assert response.status_code == 422
    assert "input" not in response.text
    assert "no-store" in response.headers["cache-control"]
    assert count(session, PortfolioPrivacyAcceptance) == 0


def test_owner_is_never_taken_from_body_or_query(session, clients):
    client, users, headers = clients
    bad = body() | {"user_id": users[1].id}
    assert (
        client.post("/api/v1/portfolio/accounts", headers=headers[0], json=bad).status_code == 422
    )
    first = create(client, headers[0], "only-user-A")
    second = create(client, headers[1], "only-user-B")
    listed = client.get(
        f"/api/v1/portfolio/accounts?user_id={users[1].id}", headers=headers[0]
    ).json()
    assert [row["id"] for row in listed["items"]] == [first["id"]]
    for actor in [headers[1], headers[2]]:  # Administrators get no private-data bypass.
        for method, payload in [
            ("GET", None),
            ("PATCH", {"expected_version": 1, "name": "stolen"}),
            ("DELETE", {"expected_version": 1, "confirmation": "DELETE"}),
        ]:
            response = client.request(
                method, f"/api/v1/portfolio/accounts/{first['id']}", headers=actor, json=payload
            )
            assert response.status_code == 404
            assert "only-user-A" not in response.text
            assert "no-store" in response.headers["cache-control"]
    assert session.get(PortfolioAccount, second["id"]).name == "only-user-B"


def test_update_archive_restore_and_conflicts(session, clients):
    client, _, headers = clients
    account = create(client, headers[0])
    path = f"/api/v1/portfolio/accounts/{account['id']}"
    response = client.patch(path, headers=headers[0], json={"expected_version": 1, "name": "new"})
    assert response.status_code == 200 and response.json()["version"] == 2
    assert (
        client.patch(
            path, headers=headers[0], json={"expected_version": 1, "name": "stale"}
        ).status_code
        == 409
    )
    for patch in [{"name": None}, {"is_archived": None}, {"is_archived": "true"}, {}]:
        assert (
            client.patch(
                path, headers=headers[0], json={"expected_version": 2, **patch}
            ).status_code
            == 422
        )
    archived = client.patch(
        path, headers=headers[0], json={"expected_version": 2, "is_archived": True}
    )
    assert archived.json()["is_archived"] is True
    assert (
        client.post("/api/v1/portfolio/accounts", headers=headers[0], json=body()).status_code
        == 409
    )
    restored = client.patch(
        path, headers=headers[0], json={"expected_version": 3, "is_archived": False}
    )
    assert restored.json()["version"] == 4


def test_free_export_exact_values_and_no_cross_owner_data(session, clients):
    client, _, headers = clients
    name = '=SUM(1,2) <script>alert("x")</script>'
    account = create(client, headers[0], name)
    create(client, headers[1], "must-not-export")
    response = client.get("/api/v1/portfolio/export", headers=headers[0])
    assert response.status_code == 200 and "attachment" in response.headers["content-disposition"]
    assert response.json()["accounts"][0]["name"] == name
    assert response.json()["scope"] == "account_metadata_only_v2_50"
    assert response.json()["capabilities"]["positions"] is False
    assert "must-not-export" not in response.text
    assert name not in response.headers["content-disposition"]
    assert "no-store" in response.headers["cache-control"]
    assert count(session, AdminAuditLog) == 0
    assert not hasattr(session.scalars(select(PortfolioAuditEvent)).first(), "name")
    assert session.get(PortfolioAccount, account["id"]).name == name


@pytest.mark.parametrize("plan", ["free", "member", "trial"])
def test_existing_data_remains_manageable_when_expired_or_feature_closed(
    session, clients, monkeypatch, plan
):
    client, users, headers = clients
    account = create(client, headers[0])
    users[0].plan = plan
    users[0].plan_expires_at = datetime.now(UTC) - timedelta(days=10)
    session.commit()
    monkeypatch.setattr(settings, "portfolio_enabled", False)
    path = f"/api/v1/portfolio/accounts/{account['id']}"
    assert client.get(path, headers=headers[0]).status_code == 200
    assert client.get("/api/v1/portfolio/export", headers=headers[0]).status_code == 200
    assert (
        client.patch(
            path, headers=headers[0], json={"expected_version": 1, "name": "still editable"}
        ).status_code
        == 200
    )
    assert (
        client.request(
            "DELETE",
            path,
            headers=headers[0],
            json={"expected_version": 2, "confirmation": "DELETE"},
        ).status_code
        == 200
    )


def test_delete_confirmation_conflict_minimal_marker_and_recreation(session, clients):
    client, users, headers = clients
    account = create(client, headers[0], "erase-this-private-name")
    path = f"/api/v1/portfolio/accounts/{account['id']}"
    assert (
        client.request("DELETE", path, headers=headers[0], json={"expected_version": 1}).status_code
        == 422
    )
    assert (
        client.request(
            "DELETE",
            path,
            headers=headers[0],
            json={"expected_version": 2, "confirmation": "DELETE"},
        ).status_code
        == 409
    )
    confirmed = {"expected_version": 1, "confirmation": "DELETE"}
    assert client.request("DELETE", path, headers=headers[0], json=confirmed).status_code == 200
    assert client.request("DELETE", path, headers=headers[0], json=confirmed).status_code == 200
    assert count(session, PortfolioAccount) == count(session, PortfolioAuditEvent) == 0
    marker = session.get(PortfolioDeletion, account["id"])
    assert marker.user_id == users[0].id and not hasattr(marker, "name")
    exported = client.get("/api/v1/portfolio/export", headers=headers[0]).json()
    assert exported["accounts"] == exported["account_history"] == []
    assert "erase-this-private-name" not in json.dumps(exported)
    replacement = create(client, headers[0])
    assert replacement["id"] != account["id"]
    assert count(session, PortfolioPrivacyAcceptance) == count(session, PortfolioDeletion) == 1


def test_default_off_and_allowlist(session, clients, monkeypatch):
    client, users, headers = clients
    monkeypatch.setattr(settings, "portfolio_enabled", False)
    assert (
        client.post("/api/v1/portfolio/accounts", headers=headers[0], json=body()).status_code
        == 403
    )
    assert count(session, PortfolioPrivacyAcceptance) == 0
    monkeypatch.setattr(settings, "portfolio_user_ids", f" {users[0].id}, invalid ")
    create(client, headers[0])
    assert (
        client.post("/api/v1/portfolio/accounts", headers=headers[1], json=body()).status_code
        == 403
    )


def test_export_rate_limit_does_not_leak_or_restrict_other_users(session, clients):
    client, _, headers = clients
    for _ in range(10):
        assert client.get("/api/v1/portfolio/export", headers=headers[0]).status_code == 200
    response = client.get("/api/v1/portfolio/export", headers=headers[0])
    assert response.status_code == 429 and "no-store" in response.headers["cache-control"]
    assert client.get("/api/v1/portfolio/export", headers=headers[1]).status_code == 200


def test_unverified_and_revoked_auth_are_denied(session, clients):
    client, users, headers = clients
    users[0].email_verified_at = None
    session.commit()
    assert client.get("/api/v1/portfolio/accounts", headers=headers[0]).status_code == 403
    users[0].email_verified_at = datetime.now(UTC)
    users[0].token_version += 1
    session.commit()
    assert client.get("/api/v1/portfolio/accounts", headers=headers[0]).status_code == 401


def test_manifest_replay_deletes_only_old_matching_account_and_is_idempotent(session, clients):
    client, users, headers = clients
    account = create(client, headers[0])
    manifest = {
        "schema_version": "portfolio-deletion-manifest-v1",
        "deletions": [
            {
                "account_id": account["id"],
                "user_id": users[0].id,
                "deleted_at": datetime.now(UTC).isoformat(),
            }
        ],
    }
    assert replay_deletions(session, manifest)["matched_accounts"] == 1
    assert session.get(PortfolioAccount, account["id"]) is not None
    replay_deletions(session, manifest, apply=True)
    session.commit()
    assert count(session, PortfolioAccount) == count(session, PortfolioAuditEvent) == 0
    replacement = create(client, headers[0])
    assert replay_deletions(session, manifest, apply=True)["matched_accounts"] == 0
    session.commit()
    assert session.get(PortfolioAccount, replacement["id"]) is not None
    assert export_deletions(session)["deletions"][0]["account_id"] == account["id"]


def test_manifest_owner_mismatch_refuses_all_deletion(session, clients):
    client, users, headers = clients
    account = create(client, headers[0])
    data = {
        "schema_version": "portfolio-deletion-manifest-v1",
        "deletions": [
            {
                "account_id": account["id"],
                "user_id": users[1].id,
                "deleted_at": datetime.now(UTC).isoformat(),
            }
        ],
    }
    with pytest.raises(ValueError, match="ownership mismatch"):
        replay_deletions(session, data, apply=True)
    session.rollback()
    assert session.get(PortfolioAccount, account["id"]) is not None
    assert count(session, PortfolioDeletion) == 0


def test_deleted_foreign_id_and_random_id_are_equally_hidden(session, clients):
    client, _, headers = clients
    account = create(client, headers[0])
    for identifier in [account["id"], str(uuid4())]:
        assert (
            client.get(f"/api/v1/portfolio/accounts/{identifier}", headers=headers[1]).status_code
            == 404
        )


def test_unexpected_failure_is_no_store_and_never_logs_private_details(
    clients, monkeypatch, caplog
):
    client, _, headers = clients

    def failure(*_):
        raise RuntimeError("PRIVATE-NAME-MUST-NOT-LEAK")

    monkeypatch.setattr("app.api.v1.portfolio.export_portfolio", failure)
    response = client.get("/api/v1/portfolio/export", headers=headers[0])
    assert response.status_code == 500
    assert response.headers["cache-control"] == "private, no-store"
    assert "PRIVATE-NAME-MUST-NOT-LEAK" not in response.text + caplog.text
    assert "RuntimeError" in caplog.text
