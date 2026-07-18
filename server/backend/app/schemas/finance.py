"""财务相关 schema。

POST /api/finance/backfill-cost 响应：一次性回填历史 cost_price=0 交易的成本价。
"""
from pydantic import BaseModel, Field


class BackfillCostResponse(BaseModel):
    """POST /api/finance/backfill-cost 响应。

    只回填 cost_price=0 的交易，不覆盖用户已手动设置的成本价。
    通过 xianyu_orders 镜像 raw_order.itemId 反查
    product_templates.source_xianyu_item_id 匹配模板。

    字段：
    - matched: 找到匹配模板的交易数（含模板成本仍为 0 的）
    - backfilled: 实际回填了成本（模板 default_cost > 0）的交易数
    - skipped_no_template: 无镜像 / 无 itemId / 无匹配模板的交易数
    - skipped_zero_cost_template: 匹配到模板但模板成本仍为 0 的交易数
    """

    matched: int = Field(0, ge=0, description="找到匹配模板的交易数（含模板成本仍为 0 的）")
    backfilled: int = Field(0, ge=0, description="实际回填了成本（模板 default_cost > 0）的交易数")
    skipped_no_template: int = Field(0, ge=0, description="无镜像 / 无 itemId / 无匹配模板的交易数")
    skipped_zero_cost_template: int = Field(0, ge=0, description="匹配到模板但模板成本仍为 0 的交易数")
