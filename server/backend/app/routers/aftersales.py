"""售后工单路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import AfterSalesCreate, AfterSalesUpdate, AfterSalesOut
from ..services import aftersales_service
from ..services.aftersales_service import AfterSalesError

router = APIRouter(prefix="/api/aftersales", tags=["aftersales"])


@router.get("", response_model=list[AfterSalesOut])
async def list_aftersales(db: AsyncSession = Depends(get_db)):
    items = await aftersales_service.list_aftersales(db)
    await db.commit()
    return items


@router.get("/by-transaction/{tx_id}", response_model=list[AfterSalesOut])
async def by_transaction(tx_id: int, db: AsyncSession = Depends(get_db)):
    items = await aftersales_service.list_by_transaction(db, tx_id)
    await db.commit()
    return items


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    data = await aftersales_service.get_after_sales_stats(db)
    await db.commit()
    return data


@router.get("/top-issues")
async def top_issues(limit: int = 10, db: AsyncSession = Depends(get_db)):
    data = await aftersales_service.get_top_issue_products(db, limit)
    await db.commit()
    return data


@router.get("/{ticket_id}", response_model=AfterSalesOut)
async def get_aftersales(ticket_id: int, db: AsyncSession = Depends(get_db)):
    a = await aftersales_service.get_aftersales(db, ticket_id)
    if a is None:
        raise HTTPException(404, "工单不存在")
    await db.commit()
    return a


@router.post("", response_model=AfterSalesOut)
async def create_aftersales(payload: AfterSalesCreate, db: AsyncSession = Depends(get_db)):
    try:
        a = await aftersales_service.create_aftersales(
            db,
            transaction_id=payload.transaction_id,
            issue_desc=payload.issue_desc,
            attachments=payload.attachments,
        )
        await db.commit()
        return a
    except AfterSalesError as e:
        raise HTTPException(400, str(e))


@router.patch("/{ticket_id}", response_model=AfterSalesOut)
async def update_aftersales(ticket_id: int, payload: AfterSalesUpdate, db: AsyncSession = Depends(get_db)):
    try:
        a = await aftersales_service.update_status(
            db, ticket_id, payload.status, payload.solution_type, payload.solution_desc
        )
        await db.commit()
        return a
    except AfterSalesError as e:
        raise HTTPException(400, str(e))


@router.delete("/{ticket_id}")
async def delete_aftersales(ticket_id: int, db: AsyncSession = Depends(get_db)):
    try:
        await aftersales_service.delete_aftersales(db, ticket_id)
        await db.commit()
        return {"message": "已删除"}
    except AfterSalesError as e:
        raise HTTPException(400, str(e))
