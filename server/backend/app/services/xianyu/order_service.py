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
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import ProductTemplate, Transaction, XianyuAccount, XianyuOrder, XianyuSyncLog, Customer
from ...utils.crypto import encrypt_field
from ...utils.helpers import calc_warranty_end, now_utc
from ..customer_service import create_customer, find_by_nickname
from ..transaction_service import create_transaction
from .account_service import get_plain_cookies, refresh_account_cookies_from_cookiecloud
from .mtop_client import MtopClient, MtopError

logger = logging.getLogger(__name__)

# 卖家订单列表 API
SOLD_GET_API = "mtop.taobao.idle.trade.merchant.sold.get"
ORDER_API_VERSION = "1.0"

# 默认成本价（闲鱼订单不含成本，记账系统需手动填或用此默认值）
DEFAULT_COST_PRICE = 0.0
PROJECTABLE_NEW_TRANSACTION_STATUSES = {"pending", "completed", "aftersales"}
PENDING_PLATFORM_STATUSES = {
    "已付款",
    "待发货",
    "已发货",
    "待收货",
    "WAIT_SELLER_SEND_GOODS",
    "WAIT_BUYER_CONFIRM_GOODS",
    "SELLER_CONSIGNED_PART",
}
COMPLETED_PLATFORM_STATUSES = {
    "交易成功",
    "交易完成",
    "部分退款成功",
    "SUCCESS",
    "TRADE_FINISHED",
    "COMPLETED",
    "PARTIAL_REFUND_SUCCESS",
}
AFTERSALES_PLATFORM_STATUSES = {
    "退款中",
    "退款处理中",
    "售后中",
    "REFUNDING",
    "REFUND_PROCESSING",
    "TRADE_REFUNDING",
}
CLOSED_PLATFORM_STATUSES = {
    "全额退款成功",
    "FULL_REFUND_SUCCESS",
}
UNPROJECTED_PLATFORM_STATUSES = {
    "待付款",
    "待支付",
    "未付款关闭",
    "已关闭",
    "交易关闭",
    "WAIT_BUYER_PAY",
    "CLOSED",
    "TRADE_CLOSED",
    "TRADE_CLOSED_BY_TAOBAO",
}


class SyncAlreadyRunningError(RuntimeError):
    pass


_sync_locks: dict[int, asyncio.Lock] = {}


def _get_sync_lock(account_id: int) -> asyncio.Lock:
    lock = _sync_locks.get(account_id)
    if lock is None:
        lock = asyncio.Lock()
        _sync_locks[account_id] = lock
    return lock


async def _ensure_customer(db: AsyncSession, nickname: str) -> Customer:
    """按昵称查找客户，不存在则创建。复用客户唯一性逻辑。"""
    existing = await find_by_nickname(db, nickname)
    if existing:
        return existing
    return await create_customer(db, xianyu_nickname=nickname, log=False)


def _extract_order_no(order: dict) -> Optional[str]:
    """从订单数据提取订单号（多字段兼容）。"""
    common_data = order.get("commonData")
    sources = (order, common_data) if isinstance(common_data, dict) else (order,)
    for source in sources:
        for key in ("bizOrderId", "bizOderId", "orderId", "tradeId"):
            if source.get(key):
                return str(source[key])
    return None


def _extract_price(order: dict) -> float:
    """提取成交价。闲鱼订单价格字段多样，分单位换算（分→元）。"""
    price_data = order.get("priceVO")
    sources = (order, price_data) if isinstance(price_data, dict) else (order,)
    for source in sources:
        for key in ("confirmFee", "actualFee", "realTotalPrice", "totalFee", "totalPrice"):
            val = source.get(key)
            if val is None:
                continue
            try:
                # 闲鱼价格多为分（整数），>1000 粗判为分单位
                fval = float(val)
                if fval > 1000 and fval == int(fval):
                    return round(fval / 100, 2)
                return round(fval, 2)
            except (ValueError, TypeError):
                continue
    return 0.0


def _extract_buyer_nick(order: dict) -> Optional[str]:
    buyer_info = order.get("buyerInfoVO")
    if isinstance(buyer_info, dict) and buyer_info.get("userNick"):
        return str(buyer_info["userNick"])
    for key in ("buyerNick", "buyer", "buyerName"):
        if order.get(key):
            return str(order[key])
    return None


def _extract_product_name(order: dict) -> Optional[str]:
    item_info = order.get("itemVO")
    if isinstance(item_info, dict) and item_info.get("title"):
        return str(item_info["title"])
    for key in ("title", "itemTitle"):
        if order.get(key):
            return str(order[key])
    return None


def _extract_item_id(order: dict) -> Optional[str]:
    item_info = order.get("itemVO")
    sources = (item_info, order) if isinstance(item_info, dict) else (order,)
    for source in sources:
        for key in ("itemId", "item_id", "id", "fishId", "auctionId", "itemID"):
            if source.get(key):
                return str(source[key])
    return None


def _extract_order_status(order: dict) -> Optional[str]:
    common_data = order.get("commonData")
    status = common_data.get("orderStatus") if isinstance(common_data, dict) else None
    status = status or order.get("orderStatus") or order.get("status")
    return str(status) if status else None


def _normalize_platform_status(status: str) -> str:
    return status.strip().upper().replace(" ", "_")


def _project_transaction_status(order: dict) -> Optional[str]:
    status = _extract_order_status(order)
    if not status:
        return "completed"

    normalized = _normalize_platform_status(status)
    if normalized in PENDING_PLATFORM_STATUSES:
        return "pending"
    if normalized in COMPLETED_PLATFORM_STATUSES:
        return "completed"
    if normalized in AFTERSALES_PLATFORM_STATUSES:
        return "aftersales"
    if normalized in CLOSED_PLATFORM_STATUSES:
        return "closed"
    if normalized in UNPROJECTED_PLATFORM_STATUSES:
        return None
    if "退款" in status and ("处理中" in status or "中" in status):
        return "aftersales"
    return None


def _apply_order_projection_to_transaction(tx: Transaction, order: dict, projected_status: str) -> None:
    changed = False
    if tx.status != projected_status:
        tx.status = projected_status
        changed = True

    if projected_status == "completed":
        shipped_at = _extract_shipped_time(order) or tx.shipped_at
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


async def upsert_order_mirror(
    db: AsyncSession, account_id: int, order: dict
) -> Optional[XianyuOrder]:
    """幂等写入闲鱼订单镜像；不直接覆盖交易投影。"""
    order_no = _extract_order_no(order)
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
    mirror.order_status = _extract_order_status(order)
    mirror.buyer_nick = _extract_buyer_nick(order)
    mirror.product_name = _extract_product_name(order)
    mirror.sale_price = _extract_price(order)
    mirror.trade_at = _parse_trade_time(order)
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
    item_id = _extract_item_id(order)
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

        orders = _parse_orders(resp)
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


def _parse_orders(resp: dict) -> list[dict]:
    """从 MTOP 响应提取订单列表（兼容多种返回结构）。"""
    if not isinstance(resp, dict):
        return []
    # 常见路径：data.orders / data.orderList / data.result / 直接是 list
    for path in (
        ("module", "items"),
        ("orders",),
        ("orderList",),
        ("result", "orders"),
        ("result", "orderList"),
        ("data",),
    ):
        cur: object = resp
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and isinstance(cur, list):
            return cur
    return []


async def sync_orders_for_account(
    db: AsyncSession, account_id: int, *, max_pages: int = 10
) -> dict:
    lock = _get_sync_lock(account_id)
    if lock.locked():
        raise SyncAlreadyRunningError("该账号订单同步正在进行中，请稍后再试")
    async with lock:
        return await _sync_orders_for_account_unlocked(db, account_id, max_pages=max_pages)


async def _sync_orders_for_account_unlocked(
    db: AsyncSession, account_id: int, *, max_pages: int = 10
) -> dict:
    """为指定账号同步订单：拉取 → 去重 → 写入交易（含级联）。返回统计。"""
    account = await db.get(XianyuAccount, account_id)
    if account is None:
        raise ValueError("闲鱼账号不存在")

    plain_cookies = get_plain_cookies(account)
    mtop = MtopClient(plain_cookies)
    fetched: list[dict] = []
    created_count = 0
    skipped_count = 0
    error: Optional[str] = None

    try:
        fetched = await fetch_orders(mtop, max_pages=max_pages)
    except MtopError as e:
        if e.auth_fail:
            refreshed = await refresh_account_cookies_from_cookiecloud(db, account)
            if not refreshed:
                error = account.last_error or str(e)
            else:
                try:
                    plain_cookies = get_plain_cookies(account)
                    mtop = MtopClient(plain_cookies)
                    fetched = await fetch_orders(mtop, max_pages=max_pages)
                except MtopError as retry_error:
                    error = str(retry_error)
                    account.status = "risk" if retry_error.risk else "invalid"
                    account.last_error = error
        else:
            error = str(e)
            account.status = "risk" if e.risk else "invalid"
            account.last_error = error
    except Exception as e:
        error = f"拉取异常: {e}"
        account.status = "invalid"
        account.last_error = error

    if mtop.cookies_changed:
        account.cookies = encrypt_field(mtop.cookie_str)
        account.updated_at = now_utc()

    # 逐单去重写入
    for order in fetched:
        mirror = await upsert_order_mirror(db, account_id, order)
        order_no = mirror.order_no if mirror else None
        if not order_no:
            skipped_count += 1
            continue
        projected_status = _project_transaction_status(order)
        # 去重：已存在该订单号则更新原投影，不重复创建交易
        existing_tx = (
            await db.execute(
                select(Transaction)
                .where(Transaction.xianyu_order_no == order_no)
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing_tx is not None:
            if mirror and mirror.projected_transaction_id is None:
                mirror.projected_transaction_id = existing_tx.id
            if projected_status:
                _apply_order_projection_to_transaction(existing_tx, order, projected_status)
            skipped_count += 1
            continue
        if projected_status not in PROJECTABLE_NEW_TRANSACTION_STATUSES:
            skipped_count += 1
            continue

        buyer_nick = _extract_buyer_nick(order) or f"闲鱼买家{order_no[-4:]}"
        product_name = _extract_product_name(order) or "闲鱼商品"
        sale_price = _extract_price(order)
        template = await _find_template_for_order(db, account_id, order)
        product_template_id = template.id if template else None
        cost_price = template.default_cost if template else DEFAULT_COST_PRICE
        warranty_days = template.warranty_days if template else None
        # 交易时间
        trade_at = _parse_trade_time(order)
        shipped_at = _extract_shipped_time(order)

        try:
            customer = await _ensure_customer(db, str(buyer_nick))
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

    if error is None:
        account.status = "online"
        account.last_error = None
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


def _parse_trade_time(order: dict) -> datetime:
    """从订单提取交易时间，兜底当前时间。"""
    return _parse_order_time(
        order,
        (
            "finishTime",
            "paySuccessTime",
            "createTime",
            "tradeTime",
            "gmtCreate",
            "payTime",
            "orderTime",
        ),
        fallback=now_utc(),
    )


def _extract_shipped_time(order: dict) -> Optional[datetime]:
    """从订单提取卖家发货时间。"""
    return _parse_order_time(
        order,
        (
            "consignTime",
            "sellerShipTime",
            "shipTime",
            "sendTime",
            "deliveryTime",
            "gmtConsign",
            "gmtSend",
        ),
    )


def _parse_order_time(
    order: dict,
    keys: tuple[str, ...],
    *,
    fallback: Optional[datetime] = None,
) -> Optional[datetime]:
    common_data = order.get("commonData")
    sources = (common_data, order) if isinstance(common_data, dict) else (order,)
    for source in sources:
        for key in keys:
            val = source.get(key)
            if not val:
                continue
            if isinstance(val, str):
                try:
                    return datetime.fromisoformat(val.replace("Z", "+00:00"))
                except ValueError:
                    pass
            try:
                ts = float(val)
                # 毫秒 → 秒
                if ts > 1e12:
                    ts = ts / 1000
                return datetime.utcfromtimestamp(ts)
            except (ValueError, TypeError):
                continue
    return fallback
