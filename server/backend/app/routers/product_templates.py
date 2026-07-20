"""Product template routes.

限流策略（project_memory 硬约束：100 req/min for read, stricter for write）：
- GET /api/product-templates → 100/minute（读端点）
- POST /api/product-templates → 30/minute（写端点）
- PATCH /api/product-templates/{id} → 30/minute（写端点）
- DELETE /api/product-templates/{id} → 30/minute（写端点）
- POST /api/product-templates/{id}/toggle → 30/minute（写端点）
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import (
    ProductTemplateCreate,
    ProductTemplateOut,
    ProductTemplateUpdate,
)
from ..security import limiter
from ..services import product_template_service


router = APIRouter(
    prefix="/api/product-templates",
    tags=["product-templates"],
)


@router.get("", response_model=list[ProductTemplateOut])
@limiter.limit("100/minute")
async def list_templates(
    request: Request,
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    items = (
        await product_template_service.list_active_templates(db)
        if active_only
        else await product_template_service.list_templates(db)
    )
    await db.commit()
    return items


@router.post("", response_model=ProductTemplateOut)
@limiter.limit("30/minute")
async def create_template(
    request: Request,
    payload: ProductTemplateCreate,
    db: AsyncSession = Depends(get_db),
):
    template = await product_template_service.create_template(
        db,
        **payload.model_dump(),
    )
    await db.commit()
    return template


@router.patch("/{tpl_id}", response_model=ProductTemplateOut)
@limiter.limit("30/minute")
async def update_template(
    request: Request,
    tpl_id: int,
    payload: ProductTemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        template = await product_template_service.update_template(
            db,
            tpl_id,
            payload.model_dump(exclude_unset=True),
        )
        await db.commit()
        return template
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{tpl_id}")
@limiter.limit("30/minute")
async def delete_template(
    request: Request,
    tpl_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        await product_template_service.delete_template(db, tpl_id)
        await db.commit()
        return {"message": "已删除"}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/{tpl_id}/toggle", response_model=ProductTemplateOut)
@limiter.limit("30/minute")
async def toggle_active(
    request: Request,
    tpl_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        template = await product_template_service.toggle_active(db, tpl_id)
        await db.commit()
        return template
    except ValueError as exc:
        raise HTTPException(404, str(exc))
