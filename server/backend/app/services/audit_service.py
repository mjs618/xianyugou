"""审计日志服务"""
from typing import Optional
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import OperationLog


async def log_operation(
    db: AsyncSession,
    module: str,
    action: str,
    *,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """写审计日志。失败不影响主流程。"""
    log = OperationLog(
        module=module,
        action=action,
        target_id=target_id,
        target_name=target_name,
        detail=detail,
    )
    db.add(log)
    await db.flush()


async def list_logs(
    db: AsyncSession,
    *,
    module: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[OperationLog], int]:
    """分页查询日志 + 总数"""
    base = select(OperationLog)
    count_base = select(func.count(OperationLog.id))
    if module:
        base = base.where(OperationLog.module == module)
        count_base = count_base.where(OperationLog.module == module)
    total = (await db.execute(count_base)).scalar_one()
    rows = (
        await db.execute(
            base.order_by(OperationLog.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return list(rows), total


async def clear_logs(db: AsyncSession) -> None:
    await db.execute(delete(OperationLog))
