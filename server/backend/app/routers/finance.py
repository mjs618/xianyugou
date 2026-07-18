"""Finance reporting routes.

读端点统一限流 100 req/min/IP（project_memory 硬约束）；
backfill-cost 是写操作且开销大（涉及全表扫描 + 客户统计重算），限流 3 req/min/IP。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import BackfillCostResponse
from ..security import limiter
from ..services import finance_service, transaction_service
from ..utils.helpers import parse_date


router = APIRouter(prefix="/api/finance", tags=["finance"])


@router.get("/overview")
@limiter.limit("100/minute")
async def finance_overview(
    request: Request,
    channel: Optional[str] = Query(None, description="销售渠道过滤：xianyu/wechat/other"),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_finance_overview(db, channel=channel)
    await db.commit()
    return data


@router.get("/products")
@limiter.limit("100/minute")
async def product_profit_stats(
    request: Request,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    channel: Optional[str] = Query(None, description="销售渠道过滤：xianyu/wechat/other"),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_product_profit_stats(
        db,
        parse_date(start) if start else None,
        parse_date(end) if end else None,
        channel=channel,
    )
    await db.commit()
    return data


@router.get("/customers")
@limiter.limit("100/minute")
async def customer_value_stats(
    request: Request,
    limit: int = Query(100),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_customer_value_stats(db, limit)
    await db.commit()
    return data


@router.get("/overview-by-range")
@limiter.limit("100/minute")
async def finance_overview_by_range(
    request: Request,
    start: str = Query(...),
    end: str = Query(...),
    channel: Optional[str] = Query(None, description="销售渠道过滤：xianyu/wechat/other"),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_finance_overview_by_range(
        db,
        parse_date(start),
        parse_date(end),
        channel=channel,
    )
    await db.commit()
    return data


@router.get("/trend")
@limiter.limit("100/minute")
async def trend(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    channel: Optional[str] = Query(None, description="销售渠道过滤：xianyu/wechat/other"),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_trend(db, days, channel=channel)
    await db.commit()
    return data


@router.get("/monthly-comparison")
@limiter.limit("100/minute")
async def monthly_comparison(
    request: Request,
    months: int = Query(6, ge=1, le=24),
    channel: Optional[str] = Query(None, description="销售渠道过滤：xianyu/wechat/other"),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_monthly_comparison(db, months, channel=channel)
    await db.commit()
    return data


@router.get("/channel-breakdown")
@limiter.limit("100/minute")
async def channel_breakdown(
    request: Request,
    start: str = Query(...),
    end: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """按销售渠道 GROUP BY 聚合，返回各渠道收入/成本/利润/笔数占比。"""
    data = await finance_service.get_channel_breakdown(
        db,
        parse_date(start),
        parse_date(end),
    )
    await db.commit()
    return data


@router.get("/new-customer-count")
@limiter.limit("100/minute")
async def new_customer_count(
    request: Request,
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


@router.post("/backfill-cost", response_model=BackfillCostResponse)
@limiter.limit("3/minute")
async def backfill_cost(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """一次性回填历史 cost_price=0 交易的成本价与模板关联。

    只回填 cost_price=0 的交易，不覆盖用户已手动设置的成本价。
    通过 xianyu_orders 镜像 raw_order.itemId 反查 product_templates.source_xianyu_item_id
    匹配模板，回填 product_template_id / cost_price / profit。
    回填后重算受影响客户的累计消费/笔数/等级。

    限流 3 次/分钟：写操作 + 全表扫描 + 客户统计重算，开销大。
    """
    result = await transaction_service.backfill_transaction_cost_from_templates(db)
    await db.commit()
    return BackfillCostResponse(**result)
