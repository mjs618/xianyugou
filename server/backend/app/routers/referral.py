"""推荐关系路由。

读端点 100 req/min/IP（project_memory 硬约束：100 req/min for read endpoints）。
全模块仅含查询端点，写操作由 transaction 创建流程内部调用
create_referral_and_rebate 完成（非路由）。
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..security import limiter
from ..services import referral_service

router = APIRouter(prefix="/api/referral", tags=["referral"])


@router.get("/tree/{customer_id}")
@limiter.limit("100/minute")
async def referral_tree(
    request: Request, customer_id: int, db: AsyncSession = Depends(get_db)
):
    """以某客户为根的推荐树"""
    data = await referral_service.get_referral_tree(db, customer_id)
    await db.commit()
    return data


@router.get("/rankings")
@limiter.limit("100/minute")
async def referrer_rankings(request: Request, db: AsyncSession = Depends(get_db)):
    """介绍人排行"""
    data = await referral_service.get_referrer_rankings(db)
    await db.commit()
    return data


@router.get("/introduced-by/{referrer_id}")
@limiter.limit("100/minute")
async def introduced_by(
    request: Request, referrer_id: int, db: AsyncSession = Depends(get_db)
):
    """某介绍人的所有被介绍人 ID"""
    data = await referral_service.get_introduced_by(db, referrer_id)
    await db.commit()
    return {"ids": data}


@router.get("/would-cycle")
@limiter.limit("100/minute")
async def would_cycle(
    request: Request,
    referrer_id: int,
    buyer_id: int,
    db: AsyncSession = Depends(get_db),
):
    """预检：建立 referrer→buyer 推荐关系是否会成环"""
    data = await referral_service.would_create_cycle_api(db, referrer_id, buyer_id)
    await db.commit()
    return data


@router.get("/level/{buyer_id}")
@limiter.limit("100/minute")
async def level(
    request: Request, buyer_id: int, db: AsyncSession = Depends(get_db)
):
    """预检：某客户的推荐层级"""
    data = await referral_service.calc_referral_level_api(db, buyer_id)
    await db.commit()
    return data
