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
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Transaction, XianyuAccount, XianyuOrder, XianyuSyncLog, Customer
from ...utils.crypto import encrypt_field
from ...utils.helpers import now_utc
from ..customer_service import create_customer, find_by_nickname
from ..transaction_service import create_transaction
from .account_service import get_plain_cookies
from .mtop_client import MtopClient, MtopError

logger = logging.getLogger(__name__)

# 卖家订单列表 API
SOLD_GET_API = "mtop.taobao.idle.trade.merchant.sold.get"
ORDER_API_VERSION = "1.0"

# 默认成本价（闲鱼订单不含成本，记账系统需手动填或用此默认值）
DEFAULT_COST_PRICE = 0.0


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


def _is_completed_order(order: dict) -> bool:
    common_data = order.get("commonData")
    status = common_data.get("orderStatus") if isinstance(common_data, dict) else None
    status = status or order.get("orderStatus") or order.get("status")
    if not status:
        return True
    return str(status).strip().upper() in {
        "交易成功",
        "交易完成",
        "SUCCESS",
        "TRADE_FINISHED",
        "COMPLETED",
    }


def _extract_order_status(order: dict) -> Optional[str]:
    common_data = order.get("commonData")
    status = common_data.get("orderStatus") if isinstance(common_data, dict) else None
    status = status or order.get("orderStatus") or order.get("status")
    return str(status) if status else None


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
        # 去重：已存在该订单号则跳过
        existing_tx_id = (
            await db.execute(
                select(Transaction.id)
                .where(Transaction.xianyu_order_no == order_no)
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing_tx_id is not None:
            if mirror and mirror.projected_transaction_id is None:
                mirror.projected_transaction_id = existing_tx_id
            skipped_count += 1
            continue
        if not _is_completed_order(order):
            skipped_count += 1
            continue

        buyer_nick = _extract_buyer_nick(order) or f"闲鱼买家{order_no[-4:]}"
        product_name = _extract_product_name(order) or "闲鱼商品"
        sale_price = _extract_price(order)
        # 交易时间
        trade_at = _parse_trade_time(order)

        try:
            customer = await _ensure_customer(db, str(buyer_nick))
            tx = await create_transaction(
                db,
                customer_id=customer.id,
                product_name=str(product_name),
                sale_price=sale_price,
                cost_price=DEFAULT_COST_PRICE,
                trade_at=trade_at,
                status="completed",
                source_type="direct",
                xianyu_order_no=order_no,
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
    common_data = order.get("commonData")
    sources = (common_data, order) if isinstance(common_data, dict) else (order,)
    for source in sources:
        for key in (
            "finishTime",
            "paySuccessTime",
            "createTime",
            "tradeTime",
            "gmtCreate",
            "payTime",
            "orderTime",
        ):
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
    return now_utc()
