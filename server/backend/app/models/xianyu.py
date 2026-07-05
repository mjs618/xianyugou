"""闲鱼账号与同步日志模型（第二阶段：闲鱼对接 & 订单同步）"""
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Float, Integer, String, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON

from ..database import Base


class XianyuAccount(Base):
    """闲鱼账号（手动粘贴 Cookie）。cookies 为原始字符串，敏感，存储时加密。"""
    __tablename__ = "xianyu_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    # 闲鱼用户 ID（从 Cookie 的 unb 字段提取），用于区分账号
    unb: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    # 原始 Cookie 字符串（加密存储）
    cookies: Mapped[str] = mapped_column(Text, nullable=False)
    # online / invalid / disabled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="online", index=True)
    # 备注（如：账号对应的代理信息）
    proxy_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class XianyuOrder(Base):
    """闲鱼订单镜像：保存平台订单快照，交易表只作为后续投影。"""
    __tablename__ = "xianyu_orders"
    __table_args__ = (
        UniqueConstraint("account_id", "order_no", name="uq_xianyu_orders_account_order_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("xianyu_accounts.id"), nullable=False, index=True)
    order_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    order_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    buyer_nick: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sale_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trade_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    raw_order: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    projected_transaction_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class XianyuSyncLog(Base):
    """订单同步日志：记录每次同步拉取/新增/跳过的数量"""
    __tablename__ = "xianyu_sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("xianyu_accounts.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success/failed
    fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 拉取到的订单数
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 新建交易数
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 跳过(已存在)数
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
