"""闲鱼账号与同步日志模型（第二阶段：闲鱼对接 & 订单同步）"""
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Float, Integer, String, Boolean, ForeignKey, Text, UniqueConstraint, func
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
    # online / invalid / disabled / paused（paused=熔断暂停，需人工恢复）
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="online", index=True)
    # 备注（如：账号对应的代理信息）
    proxy_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # P3 安全调度字段
    auto_sync_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    auto_sync_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=120, server_default="120"
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # P2-3 软删除：账号删除时不物理删除，保留关联数据可追溯
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
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


class XianyuItem(Base):
    """闲鱼商品镜像：按账号隔离保存平台商品摘要。"""
    __tablename__ = "xianyu_items"
    __table_args__ = (
        UniqueConstraint("account_id", "item_id", name="uq_xianyu_items_account_item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("xianyu_accounts.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    item_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_item: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    projected_template_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class XianyuSyncLog(Base):
    """同步日志：记录每次同步拉取/新增/跳过的数量（订单或商品）"""
    __tablename__ = "xianyu_sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("xianyu_accounts.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success/failed
    fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 拉取到的订单/商品数
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 新建交易/镜像数
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 跳过(已存在)数
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sync_type: Mapped[str] = mapped_column(String(10), nullable=False, default="order")  # order/item
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
