"""邮件发送记录请求 schema。"""
from typing import Optional

from pydantic import BaseModel


class MailRecordCreate(BaseModel):
    """创建邮件发送记录。
    gpt_password / email_password 为敏感字段，路由层加密后落库。
    sent_at 接受字符串，路由层 parse_date 转 datetime（兼容多种日期格式）。
    """
    model_config = {"extra": "allow"}

    to: str
    customer_name: Optional[str] = None
    email_account: str
    gpt_password: Optional[str] = None
    token_url: str
    email_password: Optional[str] = None
    subject: str
    status: str = "success"
    error: Optional[str] = None
    message_id: Optional[str] = None
    sent_at: Optional[str] = None
