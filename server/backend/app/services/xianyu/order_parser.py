"""Pure parsing helpers for raw Xianyu order payloads."""
from datetime import datetime, timezone
from typing import Optional


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


def extract_order_no(order: dict) -> Optional[str]:
    """Extract an order number from supported payload shapes."""
    common_data = order.get("commonData")
    sources = (order, common_data) if isinstance(common_data, dict) else (order,)
    for source in sources:
        for key in ("bizOrderId", "bizOderId", "orderId", "tradeId"):
            if source.get(key):
                return str(source[key])
    return None


def extract_price(order: dict) -> float:
    """Extract the order price while preserving the existing cent heuristic."""
    price_data = order.get("priceVO")
    sources = (order, price_data) if isinstance(price_data, dict) else (order,)
    for source in sources:
        for key in ("confirmFee", "actualFee", "realTotalPrice", "totalFee", "totalPrice"):
            value = source.get(key)
            if value is None:
                continue
            try:
                amount = float(value)
                if amount > 1000 and amount == int(amount):
                    return round(amount / 100, 2)
                return round(amount, 2)
            except (ValueError, TypeError):
                continue
    return 0.0


def extract_buyer_nick(order: dict) -> Optional[str]:
    buyer_info = order.get("buyerInfoVO")
    if isinstance(buyer_info, dict) and buyer_info.get("userNick"):
        return str(buyer_info["userNick"])
    for key in ("buyerNick", "buyer", "buyerName"):
        if order.get(key):
            return str(order[key])
    return None


def extract_product_name(order: dict) -> Optional[str]:
    item_info = order.get("itemVO")
    if isinstance(item_info, dict) and item_info.get("title"):
        return str(item_info["title"])
    for key in ("title", "itemTitle"):
        if order.get(key):
            return str(order[key])
    return None


def extract_item_id(order: dict) -> Optional[str]:
    item_info = order.get("itemVO")
    sources = (item_info, order) if isinstance(item_info, dict) else (order,)
    for source in sources:
        for key in ("itemId", "item_id", "id", "fishId", "auctionId", "itemID"):
            if source.get(key):
                return str(source[key])
    return None


def extract_order_status(order: dict) -> Optional[str]:
    common_data = order.get("commonData")
    status = common_data.get("orderStatus") if isinstance(common_data, dict) else None
    status = status or order.get("orderStatus") or order.get("status")
    return str(status) if status else None


def _normalize_platform_status(status: str) -> str:
    return status.strip().upper().replace(" ", "_")


def project_transaction_status(order: dict) -> Optional[str]:
    status = extract_order_status(order)
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


def parse_orders(response: dict) -> list[dict]:
    """Extract the order list from supported MTOP response shapes."""
    if not isinstance(response, dict):
        return []
    for path in (
        ("module", "items"),
        ("orders",),
        ("orderList",),
        ("result", "orders"),
        ("result", "orderList"),
        ("data",),
    ):
        current: object = response
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if isinstance(current, list):
                return current
    return []


def parse_trade_time(
    order: dict,
    *,
    fallback: Optional[datetime] = None,
) -> Optional[datetime]:
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
        fallback=fallback,
    )


def extract_shipped_time(order: dict) -> Optional[datetime]:
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
            value = source.get(key)
            if not value:
                continue
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    pass
            try:
                timestamp = float(value)
                if timestamp > 1e12:
                    timestamp /= 1000
                # naive UTC，与 helpers.parse_date 口径一致
                return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
            except (ValueError, TypeError):
                continue
    return fallback
