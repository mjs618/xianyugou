"""闲鱼账号服务 - CRUD、Cookie 加密、校验、触发订单同步。"""
from __future__ import annotations

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import XianyuAccount, XianyuSyncLog
from ...utils.crypto import encrypt_field, decrypt_field
from ...utils.helpers import now_utc
from .cookie_utils import parse_cookie_string, validate_cookies


class XianyuAccountError(ValueError):
    pass


def _mask(account: XianyuAccount) -> XianyuAccount:
    """对外返回时脱敏：不暴露完整 cookies，只保留状态信息。"""
    # cookies 字段在 schema 中已不暴露（XianyuAccountOut 不含 cookies）
    return account


async def list_accounts(db: AsyncSession) -> list[XianyuAccount]:
    stmt = select(XianyuAccount).order_by(XianyuAccount.created_at.desc())
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
    if "nickname" in patch and patch["nickname"] is not None:
        account.nickname = patch["nickname"].strip()
    if "cookies" in patch and patch["cookies"]:
        valid, unb, message = validate_cookies(patch["cookies"])
        if not valid:
            raise XianyuAccountError(message)
        account.cookies = encrypt_field(patch["cookies"])
        account.unb = unb
        account.status = "online"
        account.last_error = None
    account.updated_at = now_utc()
    await db.flush()
    return account


async def delete_account(db: AsyncSession, account_id: int) -> None:
    account = await get_account(db, account_id)
    if account is None:
        return
    await db.delete(account)


async def test_account(db: AsyncSession, account_id: int) -> dict:
    """校验账号 Cookie 有效性（仅本地解析校验，不发起网络请求）。"""
    account = await get_account(db, account_id)
    if account is None:
        raise XianyuAccountError("闲鱼账号不存在")
    plain_cookies = decrypt_field(account.cookies)
    valid, unb, message = validate_cookies(plain_cookies)
    return {"valid": valid, "unb": unb or account.unb, "message": message}


def get_plain_cookies(account: XianyuAccount) -> str:
    """解密获取明文 cookies（仅供订单同步内部使用）。"""
    return decrypt_field(account.cookies)


async def list_sync_logs(db: AsyncSession, account_id: int, limit: int = 20) -> list[XianyuSyncLog]:
    stmt = (
        select(XianyuSyncLog)
        .where(XianyuSyncLog.account_id == account_id)
        .order_by(XianyuSyncLog.created_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())
