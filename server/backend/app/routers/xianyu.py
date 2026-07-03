"""闲鱼账号与订单同步路由（第二阶段）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import (
    XianyuAccountCreate, XianyuAccountOut, XianyuAccountTestResult, XianyuSyncResult,
)
from ..services.xianyu import account_service
from ..services.xianyu.account_service import XianyuAccountError
from ..services.xianyu.order_service import sync_orders_for_account

router = APIRouter(prefix="/api/xianyu", tags=["xianyu"])


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
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/accounts/{account_id}/sync-logs")
async def list_sync_logs(
    account_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    logs = await account_service.list_sync_logs(db, account_id, limit)
    await db.commit()
    return logs
