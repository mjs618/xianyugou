"""闲鱼账号与订单同步路由（第二阶段）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import (
    CookieCloudConfigStatus,
    XianyuAccountCreate, XianyuAccountOut, XianyuAccountTestResult, XianyuAccountUpdate, XianyuSyncResult,
    XianyuItemImportRequest, XianyuItemImportResult, XianyuItemOut, XianyuItemSyncResult,
    XianyuOrderOut,
)
from ..services.xianyu import account_service
from ..services.xianyu.account_service import XianyuAccountError
from ..services.xianyu.cookiecloud_service import get_cookiecloud_config_status
from ..services.xianyu.order_service import (
    SyncAlreadyRunningError,
    list_order_mirrors,
    sync_orders_for_account,
)
from ..services.xianyu.item_service import (
    import_item_mirrors_as_templates,
    list_item_mirrors,
    sync_items_for_account,
)

router = APIRouter(prefix="/api/xianyu", tags=["xianyu"])


@router.get("/cookiecloud/status", response_model=CookieCloudConfigStatus)
async def cookiecloud_status():
    return get_cookiecloud_config_status()


@router.get("/accounts", response_model=list[XianyuAccountOut])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    items = await account_service.list_accounts(db)
    await db.commit()
    return items


@router.post("/accounts", response_model=XianyuAccountOut)
async def create_account(payload: XianyuAccountCreate, db: AsyncSession = Depends(get_db)):
    try:
        account = await account_service.create_account(db, nickname=payload.nickname, cookies=payload.cookies)
        await db.commit()
        return account
    except XianyuAccountError as e:
        raise HTTPException(400, str(e))


@router.patch("/accounts/{account_id}", response_model=XianyuAccountOut)
async def update_account(
    account_id: int,
    payload: XianyuAccountUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        account = await account_service.update_account(
            db,
            account_id,
            payload.model_dump(exclude_unset=True),
        )
        await db.commit()
        return account
    except XianyuAccountError as e:
        status_code = 404 if str(e) == "闲鱼账号不存在" else 400
        raise HTTPException(status_code, str(e))


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    await account_service.delete_account(db, account_id)
    await db.commit()
    return {"message": "已删除"}


@router.post("/accounts/{account_id}/test", response_model=XianyuAccountTestResult)
async def test_account(account_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await account_service.test_account(db, account_id)
        await db.commit()
        return result
    except XianyuAccountError as e:
        raise HTTPException(404, str(e))


@router.post("/accounts/{account_id}/sync-orders", response_model=XianyuSyncResult)
async def sync_orders(
    account_id: int,
    max_pages: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """手动触发订单同步。拉取闲鱼订单并写入记账系统。"""
    try:
        result = await sync_orders_for_account(db, account_id, max_pages=max_pages)
        await db.commit()
        return result
    except SyncAlreadyRunningError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/accounts/{account_id}/orders", response_model=list[XianyuOrderOut])
async def list_orders(
    account_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    account = await account_service.get_account(db, account_id)
    if account is None:
        raise HTTPException(404, "闲鱼账号不存在")
    orders = await list_order_mirrors(db, account_id, limit=limit)
    await db.commit()
    return orders


@router.post("/accounts/{account_id}/sync-items", response_model=XianyuItemSyncResult)
async def sync_items(
    account_id: int,
    max_pages: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """手动触发闲鱼商品镜像同步，按账号隔离保存。"""
    try:
        result = await sync_items_for_account(db, account_id, max_pages=max_pages)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/accounts/{account_id}/items", response_model=list[XianyuItemOut])
async def list_items(
    account_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    account = await account_service.get_account(db, account_id)
    if account is None:
        raise HTTPException(404, "闲鱼账号不存在")
    items = await list_item_mirrors(db, account_id, limit=limit)
    await db.commit()
    return items


@router.post("/accounts/{account_id}/items/import-templates", response_model=XianyuItemImportResult)
async def import_items_as_templates(
    account_id: int,
    payload: XianyuItemImportRequest,
    db: AsyncSession = Depends(get_db),
):
    account = await account_service.get_account(db, account_id)
    if account is None:
        raise HTTPException(404, "闲鱼账号不存在")
    result = await import_item_mirrors_as_templates(
        db,
        account_id,
        mirror_ids=payload.mirror_ids,
        default_cost=payload.default_cost,
        warranty_days=payload.warranty_days,
    )
    await db.commit()
    return result


@router.get("/accounts/{account_id}/sync-logs")
async def list_sync_logs(
    account_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    logs = await account_service.list_sync_logs(db, account_id, limit)
    await db.commit()
    return logs
