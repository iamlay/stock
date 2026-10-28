"""Private account ownership and versioned consent; ledger replay lives separately."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    PortfolioAccount,
    PortfolioAuditEvent,
    PortfolioDeletion,
    PortfolioPrivacyAcceptance,
    User,
)
from app.settings import settings

POLICY = {
    "version": "portfolio-positions-2026-10-28.v3",
    "scope": "private_holdings_and_trades",
    "title": "私人账本数据说明",
    "sections": [
        "你可以自愿建立一个人民币私人账本。保存自定义名称、币种、归档状态、期初持仓、股票代码、日期、数量、成交价、费用、成本、备注及依据，并保存日终持仓快照、成本口径、费用是否已知、分组及个人分红参考设置，用于重算持仓和交易盈亏；收息到账尚未开放，不连接券商。",
        "名称只用于自己的账本管理，不需要填写证券账户号码、身份证、银行卡、券商密码或上传证件。其他用户和普通管理员接口均不能查看你的账本。",
        "确认后，服务器会保存本说明版本、文本摘要和确认时间。基础账户维护、JSON导出和删除免费，会员到期不影响使用。",
        "私人账本页面不加载第三方访问统计，不把名称、持仓、交易及备注存入页面地址、本地草稿、业务分析或通用后台审计。运行平台可能保留请求路径与安全日志，请勿在地址栏提交私人信息。",
        "删除会移除在线账本、持仓流水、冲正历史及其操作记录；保留不含名称的说明确认和最小删除凭据。历史备份按各存储方周期保留，GitHub加密备份当前保留14天；Railway备份期限取决于部署配置，不能承诺统一14天删除。恢复旧备份后须按最新删除清单重新清理，再开放账本服务。",
        "需要进一步访问、更正或删除个人信息，可联系1187074543@qq.com；不会要求提供券商密码。",
    ],
    "privacy_path": "/legal/privacy#portfolio-data",
}
POLICY_SHA256 = hashlib.sha256(
    json.dumps(POLICY, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


class PortfolioError(ValueError):
    def __init__(self, code: str, message: str, status: int = 409):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def enabled_for(user_id: int) -> bool:
    return settings.portfolio_enabled or str(user_id) in {
        item.strip() for item in settings.portfolio_user_ids.split(",") if item.strip().isdigit()
    }


def lock_owner(session: Session, user_id: int) -> None:
    if session.scalar(select(User.id).where(User.id == user_id).with_for_update()) is None:
        raise PortfolioError("user_unavailable", "账号不可用", 401)


def own_account(
    session: Session, user_id: int, account_id: str, *, lock: bool = False
) -> PortfolioAccount:
    query = select(PortfolioAccount).where(
        PortfolioAccount.id == account_id,
        PortfolioAccount.user_id == user_id,
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    account = session.scalar(query)
    if account is None:
        raise PortfolioError("account_not_found", "账本不存在", 404)
    return account


def clean_name(name: str) -> str:
    name = name.strip()
    if not 1 <= len(name) <= 40 or any(unicodedata.category(c).startswith("C") for c in name):
        raise PortfolioError("invalid_name", "名称需为1–40个字符，不能包含控制字符", 422)
    return name


def account_out(account: PortfolioAccount) -> dict:
    return {
        key: getattr(account, key)
        for key in (
            "id",
            "name",
            "currency",
            "is_archived",
            "version",
            "created_at",
            "updated_at",
        )
    }


def _audit(session: Session, account: PortfolioAccount, action: str) -> None:
    session.add(
        PortfolioAuditEvent(
            id=str(uuid4()),
            account_id=account.id,
            user_id=account.user_id,
            action=action,
            account_version=account.version,
            created_at=datetime.now(UTC),
        )
    )


def _acceptance(session: Session, user_id: int, consent: dict) -> PortfolioPrivacyAcceptance:
    if consent.get("accepted") is not True:
        raise PortfolioError("privacy_ack_required", "请先阅读并主动确认私人账本数据说明", 422)
    if consent.get("version") != POLICY["version"] or consent.get("sha256") != POLICY_SHA256:
        raise PortfolioError("privacy_policy_changed", "数据说明已更新，请刷新并重新确认")
    existing = session.scalar(
        select(PortfolioPrivacyAcceptance).where(
            PortfolioPrivacyAcceptance.user_id == user_id,
            PortfolioPrivacyAcceptance.policy_version == POLICY["version"],
            PortfolioPrivacyAcceptance.policy_sha256 == POLICY_SHA256,
        )
    )
    if existing:
        return existing
    existing = PortfolioPrivacyAcceptance(
        id=str(uuid4()),
        user_id=user_id,
        policy_version=POLICY["version"],
        policy_sha256=POLICY_SHA256,
        policy_snapshot=json.loads(json.dumps(POLICY)),
        accepted_at=datetime.now(UTC),
    )
    session.add(existing)
    session.flush()
    return existing


def create_account(session: Session, user_id: int, name: str, consent: dict) -> PortfolioAccount:
    lock_owner(session, user_id)
    if not enabled_for(user_id):
        raise PortfolioError("portfolio_not_enabled", "私人账本正在内测，暂未开放创建", 403)
    if session.scalar(select(PortfolioAccount.id).where(PortfolioAccount.user_id == user_id)):
        raise PortfolioError("account_limit", "首版支持一个账本，归档后可恢复原账本")
    name = clean_name(name)
    acknowledgement = _acceptance(session, user_id, consent)
    now = datetime.now(UTC)
    account = PortfolioAccount(
        id=str(uuid4()),
        user_id=user_id,
        name=name,
        currency="CNY",
        version=1,
        is_archived=False,
        privacy_acceptance_id=acknowledgement.id,
        created_at=now,
        updated_at=now,
    )
    session.add(account)
    session.flush()
    _audit(session, account, "create")
    session.flush()
    return account


def update_account(
    session: Session, user_id: int, account_id: str, expected_version: int, patch: dict
) -> PortfolioAccount:
    lock_owner(session, user_id)
    account = own_account(session, user_id, account_id, lock=True)
    if account.version != expected_version:
        raise PortfolioError("account_changed", "账本已变化，请刷新后重试")
    if not patch or patch.keys() - {"name", "is_archived"}:
        raise PortfolioError("invalid_update", "请选择需要修改的账户信息", 422)
    if "name" in patch:
        patch["name"] = clean_name(patch["name"])
    changed = {key: value for key, value in patch.items() if getattr(account, key) != value}
    if not changed:
        return account
    for key, value in changed.items():
        setattr(account, key, value)
    account.version += 1
    account.updated_at = datetime.now(UTC)
    _audit(session, account, "update")
    session.flush()
    return account


def delete_account(session: Session, user_id: int, account_id: str, expected_version: int) -> None:
    lock_owner(session, user_id)
    existing = session.scalar(
        select(PortfolioDeletion).where(
            PortfolioDeletion.account_id == account_id,
            PortfolioDeletion.user_id == user_id,
        )
    )
    if existing:
        return
    account = own_account(session, user_id, account_id, lock=True)
    if account.version != expected_version:
        raise PortfolioError("account_changed", "账本已变化，请刷新后重新确认删除")
    session.add(
        PortfolioDeletion(account_id=account_id, user_id=user_id, deleted_at=datetime.now(UTC))
    )
    from app.services.portfolio_ledger import clear_ledger

    clear_ledger(session, user_id, account_id)
    # Future private tables MUST also cascade from account+owner.
    session.execute(
        delete(PortfolioAuditEvent).where(
            PortfolioAuditEvent.account_id == account_id,
            PortfolioAuditEvent.user_id == user_id,
        )
    )
    session.delete(account)
    session.flush()


def export_portfolio(session: Session, user_id: int) -> dict:
    # Serialize with create/update/delete so one export is an internally consistent snapshot.
    lock_owner(session, user_id)
    accounts = session.scalars(
        select(PortfolioAccount).where(PortfolioAccount.user_id == user_id)
    ).all()
    acknowledgements = session.scalars(
        select(PortfolioPrivacyAcceptance)
        .where(
            PortfolioPrivacyAcceptance.user_id == user_id,
        )
        .order_by(PortfolioPrivacyAcceptance.accepted_at)
    ).all()
    history = session.scalars(
        select(PortfolioAuditEvent)
        .where(
            PortfolioAuditEvent.user_id == user_id,
        )
        .order_by(PortfolioAuditEvent.created_at, PortfolioAuditEvent.id)
    ).all()
    from app.services.portfolio_ledger import ledger_snapshot

    ledgers = [
        {"account_id": row.id, **ledger_snapshot(session, user_id, row.id)} for row in accounts
    ]
    redesigned = any(entry.get("details") for ledger in ledgers for entry in ledger["entries"])
    return {
        "schema_version": "portfolio-positions-export-v3"
        if redesigned
        else "portfolio-ledger-export-v2",
        "scope": "holdings_and_trades_v2_51",
        "generated_at": datetime.now(UTC),
        "accounts": [account_out(row) for row in accounts],
        "privacy_acknowledgements": [
            {
                "version": row.policy_version,
                "sha256": row.policy_sha256,
                "accepted_at": row.accepted_at,
                "policy": row.policy_snapshot,
            }
            for row in acknowledgements
        ],
        "account_history": [
            {
                "account_id": row.account_id,
                "action": row.action,
                "version": row.account_version,
                "at": row.created_at,
            }
            for row in history
        ],
        "ledgers": ledgers,
        "capabilities": {"positions": True, "trades": True, "automatic_dividends": False},
    }
