"""系统设置服务 - 单例(id=1)，smtp_pass 加密存储。

复刻前端 settingsService.ts：
- getSettings 返回明文（解密 smtp_pass）
- updateSettings 校验阈值合理性 + 加密 smtp_pass，并在等级/返利规则变更后触发重算
"""
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Settings as SettingsModel
from ..utils.crypto import encrypt_field, decrypt_field, is_encrypted
from ..utils.helpers import DEFAULT_SETTINGS
from .audit_service import log_operation


class SettingsError(ValueError):
    pass


async def get_settings(db: AsyncSession, *, decrypt: bool = True) -> SettingsModel:
    """获取单例设置。decrypt=False 时 smtp_pass 保持密文（导出场景）。"""
    s = (await db.execute(select(SettingsModel).where(SettingsModel.id == 1))).scalar_one_or_none()
    if s is None:
        # 首次初始化默认设置
        s = SettingsModel(**DEFAULT_SETTINGS)
        db.add(s)
        await db.flush()
        return s
    return s


async def get_settings_plain(db: AsyncSession) -> dict:
    """返回明文 dict（smtp_pass 解密），用于导出 / 返回前端。"""
    s = await get_settings(db)
    data = {c.name: getattr(s, c.name) for c in s.__table__.columns}
    if data.get("smtp_pass"):
        data["smtp_pass"] = decrypt_field(data["smtp_pass"])
    return data


async def update_settings(db: AsyncSession, patch: dict[str, Any]) -> SettingsModel:
    """更新设置，自动校验 + 加密 + 触发级联重算。"""
    # 边界校验
    if "rebate_rate" in patch and patch["rebate_rate"] is not None:
        if not (0 <= patch["rebate_rate"] <= 1):
            raise SettingsError("返利比例必须在 0~1 之间")
    if "warranty_days" in patch and patch["warranty_days"] is not None and patch["warranty_days"] < 0:
        raise SettingsError("质保天数不能为负数")
    for k in ("vip_threshold", "core_threshold", "vip_trade_count", "core_trade_count"):
        if k in patch and patch[k] is not None and patch[k] < 0:
            raise SettingsError(f"{k} 不能为负数")

    s = await get_settings(db)
    # 合并校验阈值合理性
    merged_vip = patch.get("vip_threshold", s.vip_threshold)
    merged_core = patch.get("core_threshold", s.core_threshold)
    merged_vip_cnt = patch.get("vip_trade_count", s.vip_trade_count)
    merged_core_cnt = patch.get("core_trade_count", s.core_trade_count)
    if merged_vip > merged_core:
        raise SettingsError("VIP 阈值不能高于核心客户阈值")
    if merged_vip_cnt > merged_core_cnt:
        raise SettingsError("VIP 交易笔数阈值不能高于核心客户交易笔数阈值")

    # 应用 patch
    level_keys = ("vip_threshold", "core_threshold", "vip_trade_count", "core_trade_count")
    rate_changed = "rebate_rate" in patch or "rebate_base" in patch
    level_changed = any(k in patch for k in level_keys)

    for k, v in patch.items():
        if k == "smtp_pass" and v and not is_encrypted(v):
            v = encrypt_field(v)
        if hasattr(s, k):
            setattr(s, k, v)

    await db.flush()

    # 触发级联重算（设置变更后存量数据需要同步）
    changed_keys = list(patch.keys())
    await log_operation(db, "settings", "update", detail=f"修改字段: {', '.join(changed_keys)}")

    # 延迟导入避免循环依赖
    if level_changed:
        from .customer_service import recalc_all_customers_stats
        await recalc_all_customers_stats(db)
    if rate_changed:
        from .rebate_service import recalc_pending_rebates
        await recalc_pending_rebates(db)

    return s


async def migrate_encrypt_settings(db: AsyncSession) -> bool:
    """存量明文 smtp_pass 自动加密，返回是否发生迁移。"""
    s = await get_settings(db, decrypt=False)
    if s.smtp_pass and not is_encrypted(s.smtp_pass):
        s.smtp_pass = encrypt_field(s.smtp_pass)
        await db.flush()
        await log_operation(db, "system", "migrate", detail="SMTP 授权码已自动加密")
        return True
    return False
