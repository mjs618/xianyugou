"""Operating expense routes.

读端点 100 req/min/IP，写端点 30 req/min/IP（project_memory 硬约束：
stricter for write endpoints）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import (
    OperatingExpenseCreate,
    OperatingExpenseOut,
    OperatingExpenseUpdate,
)
from ..security import limiter
from ..services import expense_service
from ..utils.helpers import parse_date


router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.get("", response_model=list[OperatingExpenseOut])
@limiter.limit("100/minute")
async def list_expenses(
    request: Request,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    data = await expense_service.list_expenses(
        db,
        parse_date(start) if start else None,
        parse_date(end) if end else None,
    )
    await db.commit()
    return data


@router.post("", response_model=OperatingExpenseOut)
@limiter.limit("30/minute")
async def create_expense(
    request: Request,
    payload: OperatingExpenseCreate,
    db: AsyncSession = Depends(get_db),
):
    data = await expense_service.create_expense(db, **payload.model_dump())
    await db.commit()
    return data


@router.patch("/{expense_id}", response_model=OperatingExpenseOut)
@limiter.limit("30/minute")
async def update_expense(
    request: Request,
    expense_id: int,
    payload: OperatingExpenseUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await expense_service.update_expense(
            db,
            expense_id,
            payload.model_dump(exclude_unset=True),
        )
        await db.commit()
        return data
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{expense_id}")
@limiter.limit("30/minute")
async def delete_expense(
    request: Request,
    expense_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        await expense_service.delete_expense(db, expense_id)
        await db.commit()
        return {"message": "已删除"}
    except ValueError as exc:
        raise HTTPException(404, str(exc))
