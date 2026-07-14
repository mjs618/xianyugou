"""闲鱼账号服务 - CRUD、Cookie 加密、校验、触发订单同步。"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import XianyuAccount, XianyuSyncLog
from ...utils.crypto import encrypt_field, decrypt_field
from ...utils.helpers import now_utc
from .cookie_utils import parse_cookie_string, validate_cookies
from .cookiecloud_service import CookieCloudError, fetch_cookie_header_from_cookiecloud, get_cookiecloud_config_status


class XianyuAccountError(ValueError):
    pass


class XianyuSyncPausedError(XianyuAccountError):
    pass


class XianyuSyncRateLimitedError(XianyuAccountError):
    pass


logger = logging.getLogger(__name__)

MIN_MANUAL_SYNC_INTERVAL_MINUTES = 60


def ensure_account_not_paused(account: XianyuAccount) -> None:
    if account.status == "paused":
        raise XianyuSyncPausedError("账号已暂停，请更新 Cookie 并显式恢复后再同步")


async def ensure_manual_order_sync_allowed(
    db: AsyncSession, account_id: int
) -> XianyuAccount:
    account = await get_account(db, account_id)
    if account is None:
        raise XianyuAccountError("闲鱼账号不存在")
    # P2-3 软删除：已删除账号禁止同步
    if account.deleted_at is not None:
        raise XianyuAccountError("闲鱼账号已删除")
    ensure_account_not_paused(account)
    if account.last_sync_at is not None:
        earliest_retry = account.last_sync_at + timedelta(
            minutes=MIN_MANUAL_SYNC_INTERVAL_MINUTES
        )
        if now_utc() < earliest_retry:
            raise XianyuSyncRateLimitedError("手动同步间隔不能少于 60 分钟")
    return account


def _mask(account: XianyuAccount) -> XianyuAccount:
    """对外返回时脱敏：不暴露完整 cookies，只保留状态信息。"""
    # cookies 字段在 schema 中已不暴露（XianyuAccountOut 不含 cookies）
    return account


async def list_accounts(db: AsyncSession) -> list[XianyuAccount]:
    # P2-3 软删除：列表只返回未删除的账号
    stmt = (
        select(XianyuAccount)
        .where(XianyuAccount.deleted_at.is_(None))
        .order_by(XianyuAccount.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_account(db: AsyncSession, account_id: int) -> Optional[XianyuAccount]:
    return await db.get(XianyuAccount, account_id)


async def create_account(db: AsyncSession, *, nickname: str, cookies: str) -> XianyuAccount:
    """创建闲鱼账号。解析 Cookie 提取 unb，加密存储 cookies。"""
    valid, unb, message = validate_cookies(cookies)
    if not valid:
        raise XianyuAccountError(message)

    account = XianyuAccount(
        nickname=nickname.strip(),
        unb=unb,
        cookies=encrypt_field(cookies),
        status="online",
        last_error=None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(account)
    await db.flush()
    return account


async def update_account(db: AsyncSession, account_id: int, patch: dict) -> XianyuAccount:
    account = await get_account(db, account_id)
    if account is None:
        raise XianyuAccountError("闲鱼账号不存在")
    # P2-3 软删除：已删除账号禁止修改
    if account.deleted_at is not None:
        raise XianyuAccountError("闲鱼账号已删除，无法修改")
    if "nickname" in patch and patch["nickname"] is not None:
        account.nickname = patch["nickname"].strip()
    if "cookies" in patch and patch["cookies"]:
        valid, unb, message = validate_cookies(patch["cookies"])
        if not valid:
            raise XianyuAccountError(message)
        account.cookies = encrypt_field(patch["cookies"])
        account.unb = unb
        # 更新 Cookie 本身不自动解除暂停；暂停需走 recover_account 显式恢复
        if account.status != "paused":
            account.status = "online"
            account.last_error = None
            account.consecutive_failures = 0
    # P3 自动同步配置（min 60 分钟由 schema 层保证）
    if "auto_sync_enabled" in patch and patch["auto_sync_enabled"] is not None:
        account.auto_sync_enabled = bool(patch["auto_sync_enabled"])
    if (
        "auto_sync_interval_minutes" in patch
        and patch["auto_sync_interval_minutes"] is not None
    ):
        account.auto_sync_interval_minutes = patch["auto_sync_interval_minutes"]
    account.updated_at = now_utc()
    await db.flush()
    return account


async def recover_account(db: AsyncSession, account_id: int) -> XianyuAccount:
    """从熔断暂停状态恢复。

    对应设计文档 P3：「暂停后必须人工更新 Cookie、通过只读校验并点击恢复」。
    两项前置条件：
    1. 账号自暂停后必须已更新过 Cookie（updated_at > paused_at）；
    2. 当前 Cookie 通过只读格式校验（含 unb 与 _m_h5_tk）。
    满足后才清零失败计数、解除暂停。
    """
    account = await get_account(db, account_id)
    if account is None:
        raise XianyuAccountError("闲鱼账号不存在")
    # P2-3 软删除：已删除账号禁止恢复
    if account.deleted_at is not None:
        raise XianyuAccountError("闲鱼账号已删除")
    if account.status != "paused":
        raise XianyuAccountError("账号未处于暂停状态，无需恢复")
    if account.paused_at is not None and account.updated_at <= account.paused_at:
        raise XianyuAccountError(
            "恢复前请先更新账号 Cookie（暂停后未检测到 Cookie 更新）"
        )
    plain_cookies = decrypt_field(account.cookies)
    valid, unb, message = validate_cookies(plain_cookies)
    if not valid:
        raise XianyuAccountError(f"Cookie 校验未通过：{message}")
    account.status = "online"
    account.paused_at = None
    account.consecutive_failures = 0
    account.last_error = None
    account.updated_at = now_utc()
    from ..notification_service import create_account_recovered_notification
    try:
        await create_account_recovered_notification(db, account_id, account.nickname)
    except Exception as notify_err:
        # 通知创建失败不应阻断账号恢复，仅记录日志
        logger.warning("创建账号恢复通知失败（账号 %s）: %s", account_id, notify_err)
    await db.flush()
    return account


async def delete_account(db: AsyncSession, account_id: int) -> None:
    """软删除账号：标记 deleted_at，保留关联数据可追溯。

    硬删除会破坏 XianyuOrder / XianyuSyncLog / XianyuItem 等外键关系，
    软删除既保留历史数据又使账号在列表中不可见。
    """
    account = await get_account(db, account_id)
    if account is None:
        return
    if account.deleted_at is not None:
        # 已软删除，幂等返回
        return
    account.deleted_at = now_utc()
    account.status = "disabled"
    await db.flush()
    # P2-2 修复：清理该账号的同步锁缓存，避免字典泄漏
    # 用局部 import 避免循环导入（order_service 已 import account_service）
    from .order_service import release_sync_lock
    release_sync_lock(account_id)


async def test_account(db: AsyncSession, account_id: int) -> dict:
    """校验账号 Cookie 有效性（仅本地解析校验，不发起网络请求）。"""
    account = await get_account(db, account_id)
    if account is None:
        raise XianyuAccountError("闲鱼账号不存在")
    # P2-3 软删除：已删除账号禁止测试
    if account.deleted_at is not None:
        raise XianyuAccountError("闲鱼账号已删除")
    plain_cookies = decrypt_field(account.cookies)
    valid, unb, message = validate_cookies(plain_cookies)
    return {"valid": valid, "unb": unb or account.unb, "message": message}


def get_plain_cookies(account: XianyuAccount) -> str:
    """解密获取明文 cookies（仅供订单同步内部使用）。"""
    return decrypt_field(account.cookies)


async def refresh_account_cookies_from_cookiecloud(
    db: AsyncSession,
    account: XianyuAccount,
) -> bool:
    """从 CookieCloud 拉取最新 goofish Cookie 并更新账号。

    返回 False 表示未能安全刷新；错误详情只写通用原因，不包含 Cookie 内容。
    """
    try:
        cookie_header = await fetch_cookie_header_from_cookiecloud()
        valid, unb, message = validate_cookies(cookie_header)
        if not valid:
            account.last_error = (
                f"Cookie 已过期，CookieCloud 已配置但拉到的 Cookie 无效：{message}。"
                "下一步：确认浏览器已登录闲鱼 Web，并通过 CookieCloud 插件重新同步 goofish.com Cookie；"
                "如仍失败，请手动更新账号 Cookie。"
            )
            account.status = "invalid"
            account.updated_at = now_utc()
            await db.flush()
            return False
        account.cookies = encrypt_field(cookie_header)
        account.unb = unb
        account.status = "online"
        account.last_error = None
        account.updated_at = now_utc()
        await db.flush()
        return True
    except (CookieCloudError, httpx.HTTPError, ValueError) as exc:
        status = get_cookiecloud_config_status()
        if status["enabled"]:
            account.last_error = (
                f"Cookie 已过期，CookieCloud 已配置但自动续 Cookie 失败：{exc}。"
                "下一步：确认 CookieCloud 服务可访问、插件已同步 goofish.com Cookie；"
                "如仍失败，请手动更新账号 Cookie。"
            )
        else:
            missing_text = "、".join(status["missing_keys"])
            account.last_error = (
                f"Cookie 已过期，CookieCloud 自动续 Cookie 未启用：缺少 {missing_text}。"
                f"下一步：{status['next_step']}"
            )
        account.status = "invalid"
        account.updated_at = now_utc()
        await db.flush()
        return False


async def list_sync_logs(db: AsyncSession, account_id: int, limit: int = 20) -> list[XianyuSyncLog]:
    stmt = (
        select(XianyuSyncLog)
        .where(XianyuSyncLog.account_id == account_id)
        .order_by(XianyuSyncLog.created_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())
