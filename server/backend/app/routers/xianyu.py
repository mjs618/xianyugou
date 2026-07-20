"""闲鱼账号与订单同步路由（第二阶段）

限流策略（project_memory 硬约束：100 req/min for read, stricter for write）：
- GET /api/xianyu/cookiecloud/status → 100/minute（读端点）
- GET /api/xianyu/accounts → 100/minute（读端点）
- POST /api/xianyu/accounts → 30/minute（写端点）
- PATCH /api/xianyu/accounts/{id} → 30/minute（写端点）
- DELETE /api/xianyu/accounts/{id} → 30/minute（写端点）
- POST /api/xianyu/accounts/{id}/test → 30/minute（写端点）
- POST /api/xianyu/accounts/{id}/recover → 30/minute（写端点）
- POST /api/xianyu/accounts/{id}/sync-orders → 30/minute（写端点，触发同步）
- GET /api/xianyu/accounts/{id}/orders → 100/minute（读端点）
- POST /api/xianyu/accounts/{id}/sync-items → 30/minute（写端点）
- GET /api/xianyu/accounts/{id}/items → 100/minute（读端点）
- POST /api/xianyu/accounts/{id}/items/import-templates → 30/minute（写端点）
- GET /api/xianyu/accounts/{id}/sync-logs → 100/minute（读端点）
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import (
    CookieCloudConfigStatus,
    XianyuAccountCreate, XianyuAccountOut, XianyuAccountTestResult, XianyuAccountUpdate, XianyuSyncResult,
    XianyuItemImportRequest, XianyuItemImportResult, XianyuItemOut, XianyuItemSyncResult,
    XianyuOrderOut,
)
from ..security import limiter
from ..services.xianyu import account_service
from ..services.xianyu.account_service import (
    XianyuAccountError,
    XianyuAccountNotFoundError,
    XianyuSyncPausedError,
    XianyuSyncRateLimitedError,
)
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
@limiter.limit("100/minute")
async def cookiecloud_status(request: Request):
    return get_cookiecloud_config_status()


@router.get("/accounts", response_model=list[XianyuAccountOut])
@limiter.limit("100/minute")
async def list_accounts(request: Request, db: AsyncSession = Depends(get_db)):
    items = await account_service.list_accounts(db)
    await db.commit()
    return items


@router.post("/accounts", response_model=XianyuAccountOut)
@limiter.limit("30/minute")
async def create_account(
    request: Request,
    payload: XianyuAccountCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        account = await account_service.create_account(db, nickname=payload.nickname, cookies=payload.cookies)
        await db.commit()
        return account
    except XianyuAccountError as e:
        raise HTTPException(400, str(e))


@router.patch("/accounts/{account_id}", response_model=XianyuAccountOut)
@limiter.limit("30/minute")
async def update_account(
    request: Request,
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
    except XianyuAccountNotFoundError as e:
        raise HTTPException(404, str(e))
    except XianyuAccountError as e:
        raise HTTPException(400, str(e))


@router.delete("/accounts/{account_id}")
@limiter.limit("30/minute")
async def delete_account(
    request: Request, account_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        await account_service.delete_account(db, account_id)
        await db.commit()
        return {"message": "已删除"}
    except XianyuAccountNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/accounts/{account_id}/test", response_model=XianyuAccountTestResult)
@limiter.limit("30/minute")
async def test_account(
    request: Request, account_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        result = await account_service.test_account(db, account_id)
        await db.commit()
        return result
    except XianyuAccountNotFoundError as e:
        raise HTTPException(404, str(e))
    except XianyuAccountError as e:
        raise HTTPException(400, str(e))


@router.post("/accounts/{account_id}/recover", response_model=XianyuAccountOut)
@limiter.limit("30/minute")
async def recover_account(
    request: Request, account_id: int, db: AsyncSession = Depends(get_db)
):
    """从熔断暂停状态恢复。

    对应设计文档 P3：暂停后必须人工更新 Cookie、通过只读校验并点击恢复。
    前置条件由 account_service.recover_account 校验：
    1. 账号自暂停后已更新过 Cookie；
    2. 当前 Cookie 通过只读格式校验。
    """
    try:
        account = await account_service.recover_account(db, account_id)
        await db.commit()
        return account
    except XianyuAccountNotFoundError as e:
        raise HTTPException(404, str(e))
    except XianyuAccountError as e:
        raise HTTPException(400, str(e))


@router.post("/accounts/{account_id}/sync-orders", response_model=XianyuSyncResult)
@limiter.limit("30/minute")
async def sync_orders(
    request: Request,
    account_id: int,
    max_pages: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """手动触发订单同步。拉取闲鱼订单并写入记账系统。"""
    try:
        await account_service.ensure_manual_order_sync_allowed(db, account_id)
        result = await sync_orders_for_account(db, account_id, max_pages=max_pages)
        await db.commit()
        return result
    except XianyuSyncRateLimitedError as e:
        raise HTTPException(429, str(e))
    except XianyuSyncPausedError as e:
        raise HTTPException(409, str(e))
    except SyncAlreadyRunningError as e:
        raise HTTPException(409, str(e))
    except XianyuAccountNotFoundError as e:
        raise HTTPException(404, str(e))
    except XianyuAccountError as e:
        raise HTTPException(400, str(e))


@router.get("/accounts/{account_id}/orders", response_model=list[XianyuOrderOut])
@limiter.limit("100/minute")
async def list_orders(
    request: Request,
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
@limiter.limit("30/minute")
async def sync_items(
    request: Request,
    account_id: int,
    max_pages: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """手动触发闲鱼商品镜像同步，按账号隔离保存。"""
    try:
        result = await sync_items_for_account(db, account_id, max_pages=max_pages)
        await db.commit()
        return result
    except XianyuSyncPausedError as e:
        raise HTTPException(409, str(e))
    except XianyuAccountNotFoundError as e:
        raise HTTPException(404, str(e))
    except XianyuAccountError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/accounts/{account_id}/items", response_model=list[XianyuItemOut])
@limiter.limit("100/minute")
async def list_items(
    request: Request,
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
@limiter.limit("30/minute")
async def import_items_as_templates(
    request: Request,
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
@limiter.limit("100/minute")
async def list_sync_logs(
    request: Request,
    account_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    logs = await account_service.list_sync_logs(db, account_id, limit)
    await db.commit()
    return logs
