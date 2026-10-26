from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.models import RedeemCode, User
from app.db.session import get_session
from app.main import app
from app.security import create_access_token
from app.services.membership import (
    _aware,
    activate_membership,
    entitlements_for,
    has_premium_access,
    is_member,
    quota_for,
    redeem_code,
    start_trial,
)
from app.settings import settings


def make_user(session, **kwargs):
    user = User(email="trial@example.com", email_verified_at=datetime.now(UTC), **kwargs)
    session.add(user)
    session.commit()
    return user


def test_trial_once_and_paid_transition(session):
    user = make_user(session)
    assert start_trial(session, user)
    session.commit()
    expiry = _aware(user.plan_expires_at)
    assert expiry - _aware(user.trial_started_at) == timedelta(days=7)
    assert has_premium_access(user) and not is_member(user)
    assert quota_for(session, user, "test")["limit"] == settings.free_daily_limit
    assert not start_trial(session, user)
    assert _aware(user.plan_expires_at) == expiry
    now = datetime.now(UTC)
    activate_membership(session, user, days=30, now=now, source="payment")
    session.commit()
    assert _aware(user.plan_expires_at) == now + timedelta(days=30)
    activate_membership(session, user, days=30, now=now)
    session.commit()
    assert _aware(user.plan_expires_at) == now + timedelta(days=60)
    with pytest.raises(ValueError, match="有效会员"):
        start_trial(session, user)
    session.rollback()
    user.plan_expires_at = now - timedelta(seconds=1)
    session.commit()
    assert not has_premium_access(user)
    assert not entitlements_for(user)["trial_eligible"]
    with pytest.raises(ValueError, match="仅可领取一次"):
        start_trial(session, user)


def test_distinct_trial_codes_cannot_repeat_or_consume_on_rejection(session):
    user = make_user(session)
    session.add_all([RedeemCode(code=code, plan="trial", duration_days=365)
                     for code in ["SLTRIAL1", "SLTRIAL2"]])
    session.commit()
    result = redeem_code(session, user, "SLTRIAL1")
    assert result["duration_days"] == 7
    with pytest.raises(ValueError, match="仅可领取一次"):
        redeem_code(session, user, "SLTRIAL2")
    session.rollback()
    assert session.get(RedeemCode, "SLTRIAL2").used_count == 0


@pytest.mark.parametrize("expires", [None, datetime.now(UTC) + timedelta(days=100)])
def test_trial_cannot_downgrade_paid_and_permanent_not_shortened(session, expires):
    user = make_user(session, plan="member", plan_expires_at=expires)
    with pytest.raises(ValueError, match="有效会员"):
        start_trial(session, user)
    session.rollback()
    assert _aware(user.plan_expires_at) == expires
    activate_membership(session, user, days=30)
    assert user.plan_expires_at == (expires + timedelta(days=30) if expires else None)


@pytest.mark.parametrize("plan,expiry,premium", [
    ("trial", None, False),
    ("trial", -1, False),
    ("trial", 1, True),
    ("member", -1, False),
    ("member", None, True),
    ("free", 1, False),
])
def test_effective_permissions(session, plan, expiry, premium):
    user = make_user(session, plan=plan, plan_expires_at=(
        datetime.now(UTC) + timedelta(days=expiry) if expiry else None
    ))
    assert has_premium_access(user) is premium
    caps = entitlements_for(user)["capabilities"]
    assert caps["advanced_data"] is premium
    assert caps["history"] is premium
    assert caps["advanced_alerts"] is premium


def test_trial_api_auth_eligibility_idempotence_rate_limit_and_expiry(session):
    user = make_user(session)
    headers = {"Authorization": f"Bearer {create_access_token(user)}"}
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            assert client.post("/api/v1/membership/trial").status_code == 401
            first = client.post("/api/v1/membership/trial", headers=headers)
            assert first.status_code == 200
            assert first.json()["entitlements"]["state"] == "trial"
            again = client.post("/api/v1/membership/trial", headers=headers)
            assert again.json()["plan_expires_at"] == first.json()["plan_expires_at"]
            for _ in range(8):
                assert client.post("/api/v1/membership/trial", headers=headers).status_code == 200
            assert client.post("/api/v1/membership/trial", headers=headers).status_code == 429
            user.plan_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            session.commit()
            me = client.get("/api/v1/me", headers=headers).json()
            assert me["entitlements"]["state"] == "free"
            assert me["entitlements"]["capabilities"]["history"] is False
            assert user.alert_grid is True  # Config survives expiry.
    finally:
        app.dependency_overrides.clear()


def test_phone_only_cannot_claim_trial(session):
    user = User(phone="13800001111", plan="free")
    session.add(user)
    session.commit()
    with pytest.raises(ValueError, match="验证邮箱"):
        start_trial(session, user)


def test_trial_history_and_alert_settings_expire_together(session):
    user = make_user(session)
    start_trial(session, user)
    session.commit()
    app.dependency_overrides[get_session] = lambda: session
    headers = {"Authorization": f"Bearer {create_access_token(user)}"}
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/backtests/history", headers=headers).status_code == 200
            active = client.get("/api/v1/notifications/settings", headers=headers)
            assert active.json()["grid"] and active.json()["resonance"]
            user.plan_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            session.commit()
            assert client.get("/api/v1/backtests/history", headers=headers).status_code == 403
            expired = client.get("/api/v1/notifications/settings", headers=headers).json()
            assert expired["dividend"] and not expired["grid"] and not expired["resonance"]
            assert client.patch("/api/v1/notifications/settings", headers=headers,
                                json={"grid": True}).status_code == 403
            assert client.patch("/api/v1/notifications/settings", headers=headers,
                                json={"price_pct": 8}).status_code == 200
            assert user.alert_grid and user.alert_resonance
    finally:
        app.dependency_overrides.clear()
