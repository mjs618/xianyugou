"""设置 + 商品模板 + 财务 + 审计 + 迁移路由"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import (
    SettingsUpdate, SettingsOut,
    ProductTemplateCreate, ProductTemplateUpdate, ProductTemplateOut,
    OperatingExpenseCreate, OperatingExpenseUpdate, OperatingExpenseOut,
    OperationLogOut, LogListResponse,
    MigrateImportResponse,
)
from ..services import settings_service, product_template_service, audit_service, migrate_service, expense_service
from ..services.settings_service import SettingsError


# ==================== 设置 ====================
settings_router = APIRouter(prefix="/api/settings", tags=["settings"])


@settings_router.get("", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    data = await settings_service.get_settings_plain(db)
    await db.commit()
    return data


@settings_router.put("", response_model=SettingsOut)
async def update_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    try:
        await settings_service.update_settings(db, payload.model_dump(exclude_unset=True))
        await db.commit()
        data = await settings_service.get_settings_plain(db)
        await db.commit()
        return data
    except SettingsError as e:
        raise HTTPException(400, str(e))


# ==================== 商品模板 ====================
templates_router = APIRouter(prefix="/api/product-templates", tags=["product-templates"])


@templates_router.get("", response_model=list[ProductTemplateOut])
async def list_templates(active_only: bool = Query(False), db: AsyncSession = Depends(get_db)):
    if active_only:
        items = await product_template_service.list_active_templates(db)
    else:
        items = await product_template_service.list_templates(db)
    await db.commit()
    return items


@templates_router.post("", response_model=ProductTemplateOut)
async def create_template(payload: ProductTemplateCreate, db: AsyncSession = Depends(get_db)):
    t = await product_template_service.create_template(db, **payload.model_dump())
    await db.commit()
    return t


@templates_router.patch("/{tpl_id}", response_model=ProductTemplateOut)
async def update_template(tpl_id: int, payload: ProductTemplateUpdate, db: AsyncSession = Depends(get_db)):
    try:
        t = await product_template_service.update_template(db, tpl_id, payload.model_dump(exclude_unset=True))
        await db.commit()
        return t
    except ValueError as e:
        raise HTTPException(404, str(e))


@templates_router.delete("/{tpl_id}")
async def delete_template(tpl_id: int, db: AsyncSession = Depends(get_db)):
    await product_template_service.delete_template(db, tpl_id)
    await db.commit()
    return {"message": "已删除"}


@templates_router.post("/{tpl_id}/toggle", response_model=ProductTemplateOut)
async def toggle_active(tpl_id: int, db: AsyncSession = Depends(get_db)):
    try:
        t = await product_template_service.toggle_active(db, tpl_id)
        await db.commit()
        return t
    except ValueError as e:
        raise HTTPException(404, str(e))


# ==================== 财务 ====================
from ..services import finance_service

finance_router = APIRouter(prefix="/api/finance", tags=["finance"])


@finance_router.get("/overview")
async def finance_overview(db: AsyncSession = Depends(get_db)):
    data = await finance_service.get_finance_overview(db)
    await db.commit()
    return data


@finance_router.get("/products")
async def product_profit_stats(
    start: Optional[str] = Query(None), end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    from ..utils.helpers import parse_date
    s = parse_date(start) if start else None
    e = parse_date(end) if end else None
    data = await finance_service.get_product_profit_stats(db, s, e)
    await db.commit()
    return data


@finance_router.get("/customers")
async def customer_value_stats(limit: int = Query(100), db: AsyncSession = Depends(get_db)):
    data = await finance_service.get_customer_value_stats(db, limit)
    await db.commit()
    return data


@finance_router.get("/overview-by-range")
async def finance_overview_by_range(
    start: str = Query(...), end: str = Query(...), db: AsyncSession = Depends(get_db),
):
    from ..utils.helpers import parse_date
    s, e = parse_date(start), parse_date(end)
    data = await finance_service.get_finance_overview_by_range(db, s, e)
    await db.commit()
    return data


@finance_router.get("/trend")
async def trend(days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db)):
    data = await finance_service.get_trend(db, days)
    await db.commit()
    return data


@finance_router.get("/monthly-comparison")
async def monthly_comparison(months: int = Query(6, ge=1, le=24), db: AsyncSession = Depends(get_db)):
    data = await finance_service.get_monthly_comparison(db, months)
    await db.commit()
    return data


@finance_router.get("/new-customer-count")
async def new_customer_count(
    start: Optional[str] = Query(None), end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    from ..utils.helpers import parse_date
    if start and end:
        cnt = await finance_service.get_new_customer_count_by_range(db, parse_date(start), parse_date(end))
    else:
        cnt = await finance_service.get_new_customer_count(db)
    await db.commit()
    return {"count": cnt}


# ==================== 运营支出 ====================
expenses_router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@expenses_router.get("", response_model=list[OperatingExpenseOut])
async def list_expenses(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    from ..utils.helpers import parse_date
    s = parse_date(start) if start else None
    e = parse_date(end) if end else None
    data = await expense_service.list_expenses(db, s, e)
    await db.commit()
    return data


@expenses_router.post("", response_model=OperatingExpenseOut)
async def create_expense(payload: OperatingExpenseCreate, db: AsyncSession = Depends(get_db)):
    data = await expense_service.create_expense(db, **payload.model_dump())
    await db.commit()
    return data


@expenses_router.patch("/{expense_id}", response_model=OperatingExpenseOut)
async def update_expense(expense_id: int, payload: OperatingExpenseUpdate, db: AsyncSession = Depends(get_db)):
    try:
        data = await expense_service.update_expense(db, expense_id, payload.model_dump(exclude_unset=True))
        await db.commit()
        return data
    except ValueError as e:
        raise HTTPException(404, str(e))


@expenses_router.delete("/{expense_id}")
async def delete_expense(expense_id: int, db: AsyncSession = Depends(get_db)):
    try:
        await expense_service.delete_expense(db, expense_id)
        await db.commit()
        return {"message": "已删除"}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ==================== 审计日志 ====================
audit_router = APIRouter(prefix="/api/operation-logs", tags=["audit"])


@audit_router.get("", response_model=LogListResponse)
async def list_logs(
    module: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    items, total = await audit_service.list_logs(db, module=module, limit=page_size, offset=(page - 1) * page_size)
    await db.commit()
    return {"items": items, "total": total}


@audit_router.delete("")
async def clear_logs(db: AsyncSession = Depends(get_db)):
    await audit_service.clear_logs(db)
    await db.commit()
    return {"message": "日志已清空"}


# ==================== 迁移 ====================
migrate_router = APIRouter(prefix="/api/migrate", tags=["migrate"])


@migrate_router.post("/import", response_model=MigrateImportResponse)
async def import_backup(backup: dict, db: AsyncSession = Depends(get_db)):
    try:
        counts = await migrate_service.import_backup(db, backup)
        await db.commit()
        return MigrateImportResponse(counts=counts, message="导入成功")
    except ValueError as e:
        raise HTTPException(400, str(e))


@migrate_router.get("/export")
async def export_backup(db: AsyncSession = Depends(get_db)):
    data = await migrate_service.export_backup(db)
    await db.commit()
    return data
