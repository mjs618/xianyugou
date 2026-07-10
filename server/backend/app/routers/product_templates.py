"""Product template routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import (
    ProductTemplateCreate,
    ProductTemplateOut,
    ProductTemplateUpdate,
)
from ..services import product_template_service


router = APIRouter(
    prefix="/api/product-templates",
    tags=["product-templates"],
)


@router.get("", response_model=list[ProductTemplateOut])
async def list_templates(
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
async def create_template(
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
async def update_template(
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
async def delete_template(
    tpl_id: int,
    db: AsyncSession = Depends(get_db),
):
    await product_template_service.delete_template(db, tpl_id)
    await db.commit()
    return {"message": "已删除"}


@router.post("/{tpl_id}/toggle", response_model=ProductTemplateOut)
async def toggle_active(
    tpl_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        template = await product_template_service.toggle_active(db, tpl_id)
        await db.commit()
        return template
    except ValueError as exc:
        raise HTTPException(404, str(exc))
