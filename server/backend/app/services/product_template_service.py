"""商品模板服务"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ProductTemplate


async def list_templates(db: AsyncSession) -> list[ProductTemplate]:
    stmt = select(ProductTemplate).order_by(ProductTemplate.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def list_active_templates(db: AsyncSession) -> list[ProductTemplate]:
    stmt = select(ProductTemplate).where(ProductTemplate.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def create_template(db: AsyncSession, **kwargs) -> ProductTemplate:
    t = ProductTemplate(**kwargs)
    db.add(t)
    await db.flush()
    return t


async def update_template(db: AsyncSession, tpl_id: int, patch: dict) -> ProductTemplate:
    t = await db.get(ProductTemplate, tpl_id)
    if t is None:
        raise ValueError("模板不存在")
    for k, v in patch.items():
        if hasattr(t, k):
            setattr(t, k, v)
    await db.flush()
    return t


async def delete_template(db: AsyncSession, tpl_id: int) -> None:
    t = await db.get(ProductTemplate, tpl_id)
    if t is not None:
        await db.delete(t)


async def toggle_active(db: AsyncSession, tpl_id: int) -> ProductTemplate:
    """切换模板启用状态。"""
    from ..utils.helpers import now_utc
    t = await db.get(ProductTemplate, tpl_id)
    if t is None:
        raise ValueError("模板不存在")
    t.is_active = not t.is_active
    t.updated_at = now_utc()  # 显式设值，避免依赖 onupdate 导致 commit 后懒加载失败
    await db.flush()
    return t
