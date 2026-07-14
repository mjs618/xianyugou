"""闲鱼订单拉取 + 同步服务 - 把真实订单同步进记账系统的 transactions 表。

参考 xianyu-auto-reply 项目 common/services/order_service.py 的拉取思路重写：
- 调用 mtop.taobao.idle.trade.merchant.sold.get（卖家订单列表）
- 翻页拉取已成交订单
- 映射为 Transaction 结构，去重后复用 transaction_service.create_transaction 级联写入

订单字段映射（闲鱼订单 → Transaction）：
- bizOrderId/orderId → xianyu_order_no（唯一去重键）
- title → product_name
- actualFee/realTotalPrice → sale_price
- buyerNick/buyer → 客户昵称（自动建客户）
"""
import asyncio
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import ProductTemplate, Transaction, XianyuAccount, XianyuOrder, XianyuSyncLog, Customer
from ...utils.crypto import encrypt_field
from ...utils.helpers import calc_profit, calc_warranty_end, now_utc
from ..customer_service import create_customer, find_by_nickname, recalc_customer_stats
from ..notification_service import create_account_paused_notification
from ..transaction_service import create_transaction
from .account_service import (
    ensure_account_not_paused,
    get_plain_cookies,
    refresh_account_cookies_from_cookiecloud,
)
from .mtop_client import MtopClient, MtopError
from .order_parser import (
    extract_buyer_nick,
    extract_item_id,
    extract_order_no,
    extract_order_status,
    extract_price,
    extract_product_name,
    extract_shipped_time,
    parse_orders,
    parse_trade_time,
    project_transaction_status,
)

logger = logging.getLogger(__name__)

# 卖家订单列表 API
SOLD_GET_API = "mtop.taobao.idle.trade.merchant.sold.get"
ORDER_API_VERSION = "1.0"

# 默认成本价（闲鱼订单不含成本，记账系统需手动填或用此默认值）
DEFAULT_COST_PRICE = 0.0
PROJECTABLE_NEW_TRANSACTION_STATUSES = {"pending", "completed", "aftersales"}
# 连续未知失败达到此阈值即熔断暂停账号（对应设计文档 P3）
PAUSE_FAILURE_THRESHOLD = 3


class SyncAlreadyRunningError(RuntimeError):
    pass


_sync_locks: dict[int, asyncio.Lock] = {}
# 正在同步的账号集合（原子 check-and-set，避免 TOCTOU 竞态）
# set.add() / set.discard() 是同步操作，不会被 event loop 打断
_syncing_accounts: set[int] = set()


def _get_sync_lock(account_id: int) -> asyncio.Lock:
    lock = _sync_locks.get(account_id)
    if lock is None:
        lock = asyncio.Lock()
        _sync_locks[account_id] = lock
    return lock


def release_sync_lock(account_id: int) -> None:
    """清理账号对应的同步锁缓存条目。

    账号删除后调用，避免 _sync_locks 字典无限增长。
    注意：仅在账号被删除时调用；正在使用中的锁不应被清理（否则会丢失串行约束）。
    """
    _sync_locks.pop(account_id, None)
    _syncing_accounts.discard(account_id)


async def _ensure_customer(
    db: AsyncSession,
    nickname: str,
    customer_map: Optional[dict[str, Customer]] = None,
) -> Customer:
    """按昵称查找客户，不存在则创建。复用客户唯一性逻辑。

    若提供 customer_map，优先从内存命中；新创建或查到的客户会增量写回 map，
    避免同批次内对同一昵称重复查询或重复创建。
    customer_map 的键约定为「小写昵称」（与 find_by_nickname 的不区分大小写一致）。
    """
    key = nickname.strip().lower()
    if customer_map is not None and key in customer_map:
        return customer_map[key]
    existing = await find_by_nickname(db, nickname)
    if existing:
        if customer_map is not None:
            customer_map[key] = existing
        return existing
    created = await create_customer(db, xianyu_nickname=nickname, log=False)
    if customer_map is not None:
        customer_map[key] = created
    return created


def _apply_order_projection_to_transaction(tx: Transaction, order: dict, projected_status: str) -> bool:
    """将平台投影状态应用到交易记录。

    返回 True 表示交易状态发生了变更（调用方需据此重算客户统计）。
    """
    status_changed = False
    changed = False
    if tx.status != projected_status:
        tx.status = projected_status
        changed = True
        status_changed = True

    if projected_status == "completed":
        shipped_at = extract_shipped_time(order) or tx.shipped_at
        if shipped_at and tx.shipped_at != shipped_at:
            tx.shipped_at = shipped_at
            changed = True
        warranty_start = tx.shipped_at or tx.trade_at
        warranty_end = calc_warranty_end(warranty_start, tx.warranty_days) if tx.warranty_days > 0 else None
        if tx.warranty_end != warranty_end:
            tx.warranty_end = warranty_end
            changed = True
    elif projected_status == "pending":
        if tx.shipped_at is not None:
            tx.shipped_at = None
            changed = True
        if tx.warranty_end is not None:
            tx.warranty_end = None
            changed = True
    elif projected_status == "closed":
        if tx.warranty_end is not None:
            tx.warranty_end = None
            changed = True

    if changed:
        tx.version += 1
        tx.updated_at = now_utc()
    return status_changed


async def upsert_order_mirror(
    db: AsyncSession, account_id: int, order: dict
) -> Optional[XianyuOrder]:
    """幂等写入闲鱼订单镜像；不直接覆盖交易投影。"""
    order_no = extract_order_no(order)
    if not order_no:
        return None

    existing = (
        await db.execute(
            select(XianyuOrder).where(
                XianyuOrder.account_id == account_id,
                XianyuOrder.order_no == order_no,
            )
        )
    ).scalar_one_or_none()
    mirror = existing or XianyuOrder(account_id=account_id, order_no=order_no)
    mirror.order_status = extract_order_status(order)
    mirror.buyer_nick = extract_buyer_nick(order)
    mirror.product_name = extract_product_name(order)
    mirror.sale_price = extract_price(order)
    mirror.trade_at = parse_trade_time(order, fallback=now_utc())
    mirror.raw_order = order
    mirror.last_seen_at = now_utc()
    if existing is None:
        db.add(mirror)
    await db.flush()
    return mirror


async def list_order_mirrors(
    db: AsyncSession, account_id: int, *, limit: int = 100
) -> list[XianyuOrder]:
    stmt = (
        select(XianyuOrder)
        .where(XianyuOrder.account_id == account_id)
        .order_by(XianyuOrder.last_seen_at.desc(), XianyuOrder.id.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _find_template_for_order(
    db: AsyncSession,
    account_id: int,
    order: dict,
) -> Optional[ProductTemplate]:
    item_id = extract_item_id(order)
    if not item_id:
        return None
    return (
        await db.execute(
            select(ProductTemplate)
            .where(
                ProductTemplate.source_xianyu_account_id == account_id,
                ProductTemplate.source_xianyu_item_id == item_id,
                ProductTemplate.is_active.is_(True),
            )
            .order_by(ProductTemplate.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _prefetch_sync_lookups(
    db: AsyncSession,
    account_id: int,
    orders: list[dict],
) -> tuple[dict[str, Transaction], dict[str, ProductTemplate], dict[str, Customer]]:
    """批量预取本轮订单所需的去重表，避免主循环内逐单 DB 查询。

    返回 (existing_tx_map, template_map, customer_map)：
    - existing_tx_map: {xianyu_order_no: Transaction}
    - template_map: {source_xianyu_item_id: ProductTemplate}（同 item_id 多条取 id 最大）
    - customer_map: {xianyu_nickname.lower(): Customer}（与 find_by_nickname 大小写一致）

    空集时返回空 dict，调用方需做空判。
    """
    # 1. 批量预取已存在的交易（按 xianyu_order_no）
    order_nos = [extract_order_no(o) for o in orders]
    order_nos = [n for n in order_nos if n]
    existing_tx_map: dict[str, Transaction] = {}
    if order_nos:
        existing_tx_map = {
            tx.xianyu_order_no: tx
            for tx in (await db.execute(
                select(Transaction).where(Transaction.xianyu_order_no.in_(order_nos))
            )).scalars().all()
        }

    # 2. 批量预取商品模板（按 item_id + account_id + is_active）
    item_ids = {extract_item_id(o) for o in orders}
    item_ids.discard(None)
    template_map: dict[str, ProductTemplate] = {}
    if item_ids:
        rows = (await db.execute(
            select(ProductTemplate).where(
                ProductTemplate.source_xianyu_account_id == account_id,
                ProductTemplate.source_xianyu_item_id.in_(item_ids),
                ProductTemplate.is_active.is_(True),
            )
        )).scalars().all()
        # 同一 item_id 可能有多条历史记录，取 id 最大（最新）的一条
        # （与原 _find_template_for_order 的 order_by(id.desc()).limit(1) 等价）
        by_item: dict[str, ProductTemplate] = {}
        for t in rows:
            existing_t = by_item.get(t.source_xianyu_item_id)
            if existing_t is None or t.id > existing_t.id:
                by_item[t.source_xianyu_item_id] = t
        template_map = by_item

    # 3. 批量预取客户（按 xianyu_nickname，不区分大小写）
    buyer_nicks = {extract_buyer_nick(o) for o in orders}
    buyer_nicks = {n for n in buyer_nicks if n}
    customer_map: dict[str, Customer] = {}
    if buyer_nicks:
        # find_by_nickname 用 func.lower 比较，此处保持一致：用小写键存储
        from sqlalchemy import func
        rows = (await db.execute(
            select(Customer).where(
                Customer.deleted_at.is_(None),
                func.lower(Customer.xianyu_nickname).in_(
                    [n.strip().lower() for n in buyer_nicks]
                ),
            )
        )).scalars().all()
        customer_map = {c.xianyu_nickname.strip().lower(): c for c in rows}

    return existing_tx_map, template_map, customer_map


def _lookup_customer(
    customer_map: Optional[dict[str, Customer]], nickname: str
) -> Optional[Customer]:
    """从 customer_map 中按小写键查找客户。"""
    if not customer_map:
        return None
    return customer_map.get(nickname.strip().lower())


async def fetch_orders(mtop: MtopClient, *, max_pages: int = 10) -> list[dict]:
    """翻页拉取卖家全部成交订单。返回原始订单列表。"""
    all_orders: list[dict] = []
    page = 1
    while page <= max_pages:
        data = {
            "queryCode": "ALL",
            "pageNumber": page,
            "pageSize": 40,
        }
        try:
            resp = await mtop.request(SOLD_GET_API, data, version=ORDER_API_VERSION)
        except MtopError as e:
            # 第一页就失败：通常是鉴权/风控问题，必须上抛，避免误报"同步成功0单"
            # 后续页失败：数据已部分拉取，记录后中止即可
            if page == 1:
                raise
            logger.warning("拉取订单第 %s 页失败（已有部分数据）: %s", page, e)
            break

        orders = parse_orders(resp)
        if not orders:
            break
        all_orders.extend(orders)
        module = resp.get("module") if isinstance(resp, dict) else None
        if isinstance(module, dict) and isinstance(module.get("nextPage"), bool):
            has_next_page = module["nextPage"]
        else:
            has_next_page = len(orders) >= 40
        if not has_next_page:
            break
        page += 1
    return all_orders


async def sync_orders_for_account(
    db: AsyncSession, account_id: int, *, max_pages: int = 10
) -> dict:
    """原子 acquire-or-reject：用同步 set 实现 check-and-set，避免 TOCTOU 竞态。

    旧实现 `if lock.locked(): raise; async with lock: ...` 在 locked() 与
    async with 之间存在 yield 间隙，导致两个协程可能都通过 locked() 检查后
    排队进入临界区，第二个协程不会抛 SyncAlreadyRunningError 而是默默等待。

    新实现用 `_syncing_accounts` 集合做原子 check-and-set：
    - `account_id in _syncing_accounts` 与 `_syncing_accounts.add(account_id)` 之间
      没有任何 await，Python 单线程 + GIL 保证此检查-添加是原子的
    - 同步过程中持有 set 条目，finally 块清理
    """
    if account_id in _syncing_accounts:
        raise SyncAlreadyRunningError("该账号订单同步正在进行中，请稍后再试")
    _syncing_accounts.add(account_id)
    try:
        # asyncio.Lock 仍保留作为进程内串行化的二级保障
        # 但实际拒绝逻辑由 _syncing_accounts 完成，acquire 不会阻塞
        lock = _get_sync_lock(account_id)
        async with lock:
            return await _sync_orders_for_account_unlocked(db, account_id, max_pages=max_pages)
    finally:
        _syncing_accounts.discard(account_id)


async def _sync_orders_for_account_unlocked(
    db: AsyncSession, account_id: int, *, max_pages: int = 10
) -> dict:
    """为指定账号同步订单：拉取 → 去重 → 写入交易（含级联）。返回统计。"""
    account = await db.get(XianyuAccount, account_id)
    if account is None:
        raise ValueError("闲鱼账号不存在")
    ensure_account_not_paused(account)

    plain_cookies = get_plain_cookies(account)
    mtop = MtopClient(plain_cookies)
    fetched: list[dict] = []
    created_count = 0
    skipped_count = 0
    error: Optional[str] = None
    # 失败分类：None=成功；"auth_fail"/"risk"=立即熔断；"unknown"=计数熔断
    failure_kind: Optional[str] = None

    try:
        fetched = await fetch_orders(mtop, max_pages=max_pages)
    except MtopError as e:
        if e.auth_fail:
            refreshed = await refresh_account_cookies_from_cookiecloud(db, account)
            if not refreshed:
                error = account.last_error or str(e)
                # CookieCloud 未能续期 → 登录态失效，立即熔断
                failure_kind = "auth_fail"
            else:
                try:
                    plain_cookies = get_plain_cookies(account)
                    mtop = MtopClient(plain_cookies)
                    fetched = await fetch_orders(mtop, max_pages=max_pages)
                except MtopError as retry_error:
                    error = str(retry_error)
                    account.last_error = error
                    if retry_error.risk:
                        failure_kind = "risk"
                    elif retry_error.auth_fail:
                        failure_kind = "auth_fail"
                    else:
                        failure_kind = "unknown"
        elif e.risk:
            # 风控响应立即熔断，不自动恢复
            error = str(e)
            account.last_error = error
            failure_kind = "risk"
        else:
            # 业务失败：计数熔断
            error = str(e)
            account.last_error = error
            failure_kind = "unknown"
    except Exception as e:
        # 网络/解析等未知异常：计数熔断，等待下一周期重试
        error = f"拉取异常: {e}"
        account.last_error = error
        failure_kind = "unknown"

    if mtop.cookies_changed:
        account.cookies = encrypt_field(mtop.cookie_str)
        account.updated_at = now_utc()

    # 批量预取本轮订单的去重表，避免主循环内逐单 DB 查询
    # （200 单场景下，把 ~600 次 SELECT 降为 3 次批量 SELECT）
    existing_tx_map, template_map, customer_map = await _prefetch_sync_lookups(
        db, account_id, fetched
    )
    affected_customer_ids: set[int] = set()
    for order in fetched:
        mirror = await upsert_order_mirror(db, account_id, order)
        order_no = mirror.order_no if mirror else None
        if not order_no:
            skipped_count += 1
            continue
        projected_status = project_transaction_status(order)
        # 内存查表替代逐单 SELECT（existing_tx_map 在 _prefetch_sync_lookups 中已预取）
        existing_tx = existing_tx_map.get(order_no)
        if existing_tx is not None:
            if mirror and mirror.projected_transaction_id is None:
                mirror.projected_transaction_id = existing_tx.id
            if projected_status:
                # 状态变更时需重算客户统计（累计消费/笔数/等级）
                if _apply_order_projection_to_transaction(existing_tx, order, projected_status):
                    if existing_tx.customer_id is not None:
                        affected_customer_ids.add(existing_tx.customer_id)
            # 防回归：历史同步时未关联模板/未填成本的交易，再次同步时补回填
            # （模板可能在交易首次同步之后才建立或才填成本）
            if existing_tx.cost_price == 0.0 and existing_tx.product_template_id is None:
                # 内存查表替代 _find_template_for_order
                template = template_map.get(extract_item_id(order)) if extract_item_id(order) else None
                if template is not None and template.default_cost > 0:
                    existing_tx.product_template_id = template.id
                    existing_tx.cost_price = template.default_cost
                    existing_tx.profit = calc_profit(existing_tx.sale_price, existing_tx.cost_price)
                    existing_tx.version += 1
                    existing_tx.updated_at = now_utc()
                    if existing_tx.customer_id is not None:
                        affected_customer_ids.add(existing_tx.customer_id)
            skipped_count += 1
            continue
        if projected_status not in PROJECTABLE_NEW_TRANSACTION_STATUSES:
            skipped_count += 1
            continue

        buyer_nick = extract_buyer_nick(order) or f"闲鱼买家{order_no[-4:]}"
        product_name = extract_product_name(order) or "闲鱼商品"
        sale_price = extract_price(order)
        # 内存查表替代 _find_template_for_order
        item_id = extract_item_id(order)
        template = template_map.get(item_id) if item_id else None
        product_template_id = template.id if template else None
        cost_price = template.default_cost if template else DEFAULT_COST_PRICE
        warranty_days = template.warranty_days if template else None
        # 交易时间
        trade_at = parse_trade_time(order, fallback=now_utc())
        shipped_at = extract_shipped_time(order)

        try:
            # 优先从 customer_map 内存命中；未命中则查 DB 并增量缓存
            customer = _lookup_customer(customer_map, str(buyer_nick))
            if customer is None:
                customer = await _ensure_customer(db, str(buyer_nick), customer_map)
            tx = await create_transaction(
                db,
                customer_id=customer.id,
                product_name=str(product_name),
                sale_price=sale_price,
                cost_price=cost_price,
                trade_at=trade_at,
                shipped_at=shipped_at,
                status=projected_status,
                source_type="direct",
                channel="xianyu",
                xianyu_order_no=order_no,
                product_template_id=product_template_id,
                warranty_days=warranty_days,
                notes="由闲鱼订单同步自动创建",
                log=False,
            )
            if mirror:
                mirror.projected_transaction_id = tx.id
            created_count += 1
        except Exception as e:
            logger.warning("写入订单 %s 失败: %s", order_no, e)
            skipped_count += 1

    # 状态变更后重算受影响客户的累计消费/笔数/等级
    for cid in affected_customer_ids:
        try:
            await recalc_customer_stats(db, cid)
        except Exception as e:
            logger.warning("重算客户 %s 统计失败: %s", cid, e)

    # 根据失败分类应用熔断策略（对应设计文档 P3）
    if failure_kind is None:
        # 成功：清零失败计数，恢复正常状态
        account.status = "online"
        account.last_error = None
        account.consecutive_failures = 0
    elif failure_kind in ("auth_fail", "risk"):
        # 登录失效/风控：立即熔断，需人工更新 Cookie 并通过只读校验后恢复
        account.status = "paused"
        account.paused_at = now_utc()
        account.consecutive_failures = 0
        reason = "登录失效" if failure_kind == "auth_fail" else "平台风控响应"
        try:
            await create_account_paused_notification(db, account_id, account.nickname, reason)
        except Exception as notify_err:
            # 通知创建失败不应阻断熔断状态写入，仅记录日志
            logger.warning("创建账号熔断通知失败（账号 %s）: %s", account_id, notify_err)
    else:
        # 未知失败：累计计数，达到阈值熔断；否则保留状态等待下一周期重试
        account.consecutive_failures = (account.consecutive_failures or 0) + 1
        if account.consecutive_failures >= PAUSE_FAILURE_THRESHOLD:
            account.status = "paused"
            account.paused_at = now_utc()
            reason = f"连续失败 {account.consecutive_failures} 次"
            try:
                await create_account_paused_notification(db, account_id, account.nickname, reason)
            except Exception as notify_err:
                logger.warning("创建账号熔断通知失败（账号 %s）: %s", account_id, notify_err)
    account.last_sync_at = now_utc()

    # 记录同步日志
    db.add(XianyuSyncLog(
        account_id=account_id,
        status="failed" if error else "success",
        fetched=len(fetched),
        created_count=created_count,
        skipped_count=skipped_count,
        error=error,
    ))
    await db.flush()

    return {
        "success": error is None,
        "fetched": len(fetched),
        "created_count": created_count,
        "skipped_count": skipped_count,
        "error": error,
    }
