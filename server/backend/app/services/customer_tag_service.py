"""客户标签服务 - 复刻前端 customerTagService.ts。

含：标签 CRUD、删除标签时级联清理客户 tags 字段与关联表、
setCustomerTags 自动建标签 + 重建关联。
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CustomerTag, CustomerTagRelation, Customer
from ..utils.helpers import now_utc


class TagError(ValueError):
    pass


async def list_tags(db: AsyncSession) -> list[CustomerTag]:
    stmt = select(CustomerTag).order_by(CustomerTag.created_at.asc())
    return list((await db.execute(stmt)).scalars().all())


async def create_tag(db: AsyncSession, name: str, color: Optional[str] = None) -> CustomerTag:
    trimmed = (name or "").strip()
    if not trimmed:
        raise TagError("标签名不能为空")
    existing = (
        await db.execute(select(CustomerTag).where(CustomerTag.name == trimmed).limit(1))
    ).scalar_one_or_none()
    if existing:
        raise TagError(f'标签"{trimmed}"已存在')
    tag = CustomerTag(name=trimmed, color=color, is_system=False, created_at=now_utc())
    db.add(tag)
    await db.flush()
    return tag


async def delete_tag(db: AsyncSession, tag_id: int) -> None:
    """删除标签 + 级联清理客户 tags 字段 + 关联表。"""
    tag = await db.get(CustomerTag, tag_id)
    if tag is None:
        return
    # 查找关联了此标签的客户，从其 tags 数组移除标签名
    relations = list((await db.execute(
        select(CustomerTagRelation).where(CustomerTagRelation.tag_id == tag_id)
    )).scalars().all())
    for r in relations:
        c = await db.get(Customer, r.customer_id)
        if c:
            c.tags = [t for t in (c.tags or []) if t != tag.name]
            c.updated_at = now_utc()
    # 删除关联关系 + 标签定义
    await db.execute(delete(CustomerTagRelation).where(CustomerTagRelation.tag_id == tag_id))
    await db.delete(tag)
    await db.flush()


async def get_customer_tags(db: AsyncSession, customer_id: int) -> list[CustomerTag]:
    """获取客户的标签列表（join 关联表）。"""
    relations = list((await db.execute(
        select(CustomerTagRelation).where(CustomerTagRelation.customer_id == customer_id)
    )).scalars().all())
    tag_ids = [r.tag_id for r in relations]
    if not tag_ids:
        return []
    tags = list((await db.execute(
        select(CustomerTag).where(CustomerTag.id.in_(tag_ids))
    )).scalars().all())
    return tags


async def set_customer_tags(db: AsyncSession, customer_id: int, tag_names: list[str]) -> None:
    """为客户设置标签：自动建缺失标签 + 更新客户 tags 字段 + 重建关联。"""
    customer = await db.get(Customer, customer_id)
    if customer is None or customer.deleted_at is not None:
        raise TagError("客户不存在")

    cleaned = [n.strip() for n in tag_names if n and n.strip()]

    # 确保所有标签都存在定义（自动创建）
    all_tags = list((await db.execute(select(CustomerTag))).scalars().all())
    name_to_tag = {t.name: t for t in all_tags}
    tag_ids: list[int] = []
    for name in cleaned:
        existing = name_to_tag.get(name)
        if existing:
            tag_ids.append(existing.id)
        else:
            new_tag = CustomerTag(name=name, is_system=False, created_at=now_utc())
            db.add(new_tag)
            await db.flush()
            tag_ids.append(new_tag.id)
            name_to_tag[name] = new_tag

    # 更新客户 tags 字段
    customer.tags = cleaned
    customer.updated_at = now_utc()

    # 清理旧关联，重建新关联
    await db.execute(
        delete(CustomerTagRelation).where(CustomerTagRelation.customer_id == customer_id)
    )
    now = now_utc()
    for tid in tag_ids:
        db.add(CustomerTagRelation(customer_id=customer_id, tag_id=tid, created_at=now))
    await db.flush()
