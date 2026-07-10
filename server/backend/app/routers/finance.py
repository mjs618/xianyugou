"""Finance reporting routes."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services import finance_service
from ..utils.helpers import parse_date


router = APIRouter(prefix="/api/finance", tags=["finance"])


@router.get("/overview")
async def finance_overview(db: AsyncSession = Depends(get_db)):
    data = await finance_service.get_finance_overview(db)
    await db.commit()
    return data


@router.get("/products")
async def product_profit_stats(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_product_profit_stats(
        db,
        parse_date(start) if start else None,
        parse_date(end) if end else None,
    )
    await db.commit()
    return data


@router.get("/customers")
async def customer_value_stats(
    limit: int = Query(100),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_customer_value_stats(db, limit)
    await db.commit()
    return data


@router.get("/overview-by-range")
async def finance_overview_by_range(
    start: str = Query(...),
    end: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_finance_overview_by_range(
        db,
        parse_date(start),
        parse_date(end),
    )
    await db.commit()
    return data


@router.get("/trend")
async def trend(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_trend(db, days)
    await db.commit()
    return data


@router.get("/monthly-comparison")
async def monthly_comparison(
    months: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_monthly_comparison(db, months)
    await db.commit()
    return data


@router.get("/new-customer-count")
async def new_customer_count(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    count = (
        await finance_service.get_new_customer_count_by_range(
            db,
            parse_date(start),
            parse_date(end),
        )
        if start and end
        else await finance_service.get_new_customer_count(db)
    )
    await db.commit()
    return {"count": count}
