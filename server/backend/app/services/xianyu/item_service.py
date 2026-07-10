"""闲鱼商品拉取与镜像导入服务。"""
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import ProductTemplate, XianyuAccount, XianyuItem
from ...utils.crypto import encrypt_field
from ...utils.helpers import now_utc
from .account_service import get_plain_cookies, refresh_account_cookies_from_cookiecloud
from .mtop_client import MtopClient, MtopError

ITEM_LIST_API = "mtop.idle.web.xyh.item.list"
ACCOUNT_API = "mtop.idle.web.user.page.account"
ITEM_API_VERSION = "1.0"


def _nested(source: dict, *path: str) -> Any:
    cur: Any = source
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


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
    for key in ("cardData", "item", "itemDO", "itemVO", "itemInfo", "data", "detailParams"):
        nested = item.get(key)
        if isinstance(nested, dict):
            return {**item, **nested}
    return item


def _extract_item_id(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(
        data.get("itemId"),
        data.get("item_id"),
        data.get("id"),
        data.get("fishId"),
        data.get("auctionId"),
        data.get("itemID"),
    )


def _extract_title(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(
        data.get("title"),
        data.get("itemTitle"),
        data.get("name"),
        data.get("subject"),
        _nested(data, "titleInfo", "title"),
    )


def _extract_price(item: dict) -> float:
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


def _extract_status(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(
        data.get("itemStatus"),
        data.get("status"),
        data.get("statusText"),
        data.get("publishStatus"),
        data.get("soldStatus"),
    )


def _extract_image_url(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(
        data.get("picUrl"),
        data.get("image"),
        data.get("itemPicUrl"),
        data.get("cover"),
        _nested(data, "picInfo", "picUrl"),
        _nested(data, "imageInfo", "url"),
    )


def _parse_items(resp: dict) -> list[dict]:
    if not isinstance(resp, dict):
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
        cur: Any = resp
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and isinstance(cur, list):
            return [item for item in cur if isinstance(item, dict)]
    return []


async def upsert_item_mirror(
    db: AsyncSession, account_id: int, item: dict
) -> Optional[XianyuItem]:
    item_id = _extract_item_id(item)
    if not item_id:
        return None

    existing = (
        await db.execute(
            select(XianyuItem).where(
                XianyuItem.account_id == account_id,
                XianyuItem.item_id == item_id,
            )
        )
    ).scalar_one_or_none()
    mirror = existing or XianyuItem(account_id=account_id, item_id=item_id)
    mirror.title = _extract_title(item)
    mirror.price = _extract_price(item)
    mirror.item_status = _extract_status(item)
    mirror.image_url = _extract_image_url(item)
    mirror.raw_item = item
    mirror.last_seen_at = now_utc()
    if existing is None:
        db.add(mirror)
    await db.flush()
    return mirror


async def list_item_mirrors(
    db: AsyncSession, account_id: int, *, limit: int = 100
) -> list[XianyuItem]:
    stmt = (
        select(XianyuItem)
        .where(XianyuItem.account_id == account_id)
        .order_by(XianyuItem.last_seen_at.desc(), XianyuItem.id.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


def _extract_user_id(resp: dict) -> Optional[str]:
    for path in (
        ("module", "base", "userId"),
        ("module", "base", "uid"),
        ("module", "userId"),
        ("base", "userId"),
        ("userId",),
    ):
        value = _nested(resp, *path)
        text = _first_text(value)
        if text:
            return text
    return None


async def _fetch_user_id(mtop: MtopClient) -> Optional[str]:
    try:
        resp = await mtop.request(ACCOUNT_API, {}, version=ITEM_API_VERSION)
    except MtopError:
        return None
    return _extract_user_id(resp)


async def fetch_items(mtop: MtopClient, *, user_id: Optional[str], max_pages: int = 5) -> list[dict]:
    all_items: list[dict] = []
    page = 1
    next_page_model = None
    next_page_num = None
    while page <= max_pages:
        data = {
            "needGroupInfo": page == 1,
            "pageNumber": page,
            "pageSize": 20,
            "userId": user_id,
        }
        if next_page_model is not None:
            data["nextPageModel"] = next_page_model
        if next_page_num is not None:
            data["nextPageNum"] = next_page_num

        resp = await mtop.request(ITEM_LIST_API, data, version=ITEM_API_VERSION)
        items = _parse_items(resp)
        if not items:
            break
        all_items.extend(items)

        page_info = resp.get("module") if isinstance(resp, dict) else None
        if not isinstance(page_info, dict) and isinstance(resp, dict):
            page_info = resp
        next_page_model = page_info.get("nextPageModel") if isinstance(page_info, dict) else None
        next_page_num = page_info.get("nextPageNum") if isinstance(page_info, dict) else None
        if isinstance(page_info, dict) and isinstance(page_info.get("nextPage"), bool):
            has_next_page = page_info["nextPage"]
        else:
            has_next_page = len(items) >= 20
        if not has_next_page:
            break
        page += 1
    return all_items


async def sync_items_for_account(
    db: AsyncSession, account_id: int, *, max_pages: int = 5
) -> dict:
    account = await db.get(XianyuAccount, account_id)
    if account is None:
        raise ValueError("闲鱼账号不存在")

    mtop = MtopClient(get_plain_cookies(account))
    fetched: list[dict] = []
    upserted_count = 0
    error: Optional[str] = None
    try:
        user_id = await _fetch_user_id(mtop) or account.unb or mtop.unb
        fetched = await fetch_items(mtop, user_id=user_id, max_pages=max_pages)
    except MtopError as e:
        if e.auth_fail:
            refreshed = await refresh_account_cookies_from_cookiecloud(db, account)
            if not refreshed:
                error = account.last_error or str(e)
            else:
                try:
                    mtop = MtopClient(get_plain_cookies(account))
                    user_id = await _fetch_user_id(mtop) or account.unb or mtop.unb
                    fetched = await fetch_items(mtop, user_id=user_id, max_pages=max_pages)
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

    for item in fetched:
        mirror = await upsert_item_mirror(db, account_id, item)
        if mirror is not None:
            upserted_count += 1

    if error is None:
        account.status = "online"
        account.last_error = None
    await db.flush()
    return {
        "success": error is None,
        "fetched": len(fetched),
        "upserted_count": upserted_count,
        "error": error,
    }


async def import_item_mirrors_as_templates(
    db: AsyncSession,
    account_id: int,
    *,
    mirror_ids: list[int],
    default_cost: float = 0.0,
    warranty_days: int = 30,
) -> dict:
    created_count = 0
    skipped_count = 0
    for mirror_id in mirror_ids:
        mirror = await db.get(XianyuItem, mirror_id)
        if mirror is None or mirror.account_id != account_id or mirror.projected_template_id is not None:
            skipped_count += 1
            continue
        if not mirror.title:
            skipped_count += 1
            continue
        existing_template = (
            await db.execute(
                select(ProductTemplate)
                .where(
                    ProductTemplate.source_xianyu_account_id == account_id,
                    ProductTemplate.source_xianyu_item_id == mirror.item_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing_template is not None:
            if mirror.image_url and not existing_template.image_url:
                existing_template.image_url = mirror.image_url
            mirror.projected_template_id = existing_template.id
            skipped_count += 1
            continue
        template = ProductTemplate(
            name=mirror.title,
            default_cost=default_cost,
            default_sale_price=mirror.price,
            category="闲鱼导入",
            warranty_days=warranty_days,
            is_active=True,
            source_xianyu_account_id=account_id,
            source_xianyu_item_id=mirror.item_id,
            image_url=mirror.image_url,
        )
        db.add(template)
        await db.flush()
        mirror.projected_template_id = template.id
        created_count += 1
    await db.flush()
    return {"created_count": created_count, "skipped_count": skipped_count}
