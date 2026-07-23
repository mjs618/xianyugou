"""Pure parsing helpers for raw Xianyu item payloads."""
from typing import Any, Optional


def _nested(source: dict, *path: str) -> Any:
    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _coerce_price(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("price", "priceText", "value", "amount", "cent"):
            price = _coerce_price(value.get(key))
            if price is not None:
                return price
        return None
    text = str(value).strip().replace("¥", "").replace("￥", "").replace(",", "")
    if not text:
        return None
    try:
        amount = float(text)
    except ValueError:
        return None
    if amount > 1000 and amount == int(amount):
        return round(amount / 100, 2)
    return round(amount, 2)


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _unwrap_item(item: dict) -> dict:
    for key in (
        "cardData",
        "item",
        "itemDO",
        "itemVO",
        "itemInfo",
        "data",
        "detailParams",
    ):
        nested = item.get(key)
        if isinstance(nested, dict):
            return {**item, **nested}
    return item


def extract_item_id(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(
        data.get("itemId"),
        data.get("item_id"),
        data.get("id"),
        data.get("fishId"),
        data.get("auctionId"),
        data.get("itemID"),
    )


def extract_title(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(
        data.get("title"),
        data.get("itemTitle"),
        data.get("name"),
        data.get("subject"),
        _nested(data, "titleInfo", "title"),
    )


def extract_price(item: dict) -> float:
    data = _unwrap_item(item)
    for value in (
        data.get("price"),
        data.get("soldPrice"),
        data.get("currentPrice"),
        data.get("reservePrice"),
        _nested(data, "priceInfo", "price"),
        _nested(data, "priceInfo", "priceText"),
        _nested(data, "priceVO", "price"),
        _nested(data, "priceVO", "realPrice"),
    ):
        price = _coerce_price(value)
        if price is not None:
            return price
    return 0.0


def extract_status(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(
        data.get("itemStatus"),
        data.get("status"),
        data.get("statusText"),
        data.get("publishStatus"),
        data.get("soldStatus"),
    )


def extract_image_url(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(
        data.get("picUrl"),
        data.get("image"),
        data.get("itemPicUrl"),
        data.get("cover"),
        _nested(data, "picInfo", "picUrl"),
        _nested(data, "imageInfo", "url"),
    )


def parse_items(response: dict) -> list[dict]:
    if not isinstance(response, dict):
        return []
    for path in (
        ("module", "items"),
        ("module", "list"),
        ("module", "itemList"),
        ("module", "cardList"),
        ("cardList",),
        ("items",),
        ("itemList",),
        ("list",),
        ("result", "items"),
        ("result", "itemList"),
        ("data",),
    ):
        current: Any = response
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if isinstance(current, list):
                return [item for item in current if isinstance(item, dict)]
    return []


def extract_user_id(response: dict) -> Optional[str]:
    for path in (
        ("module", "base", "userId"),
        ("module", "base", "uid"),
        ("module", "userId"),
        ("base", "userId"),
        ("userId",),
    ):
        text = _first_text(_nested(response, *path))
        if text:
            return text
    return None
