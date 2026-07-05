"""MTOP 客户端 - 闲鱼 H5 API 调用封装。

参考 xianyu-auto-reply 项目 common/services/xianyu_mtop.py + xianyu_utils.py 重写：
- 签名算法：MD5('{token}&{timestamp}&{appKey}&{data}')，appKey 固定 34839810
- 端点：https://h5api.m.goofish.com/h5/{api}/{version}/
- Token 过期处理：FAIL_SYS_TOKEN_EXOIRED → 从响应 Set-Cookie 取新 _m_h5_tk 重签重试

注意：闲鱼私有协议可能随时变更，此处只实现订单拉取所需的最小能力。
"""
import hashlib
import time
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from ...config import settings
from .cookie_utils import parse_cookie_string, get_token, cookies_to_header

# 闲鱼网页版 H5 固定 appKey（逆向得到，参考项目同值）
APP_KEY = settings.xianyu_app_key
MTOP_ENDPOINT = settings.xianyu_mtop_endpoint
ORIGIN = settings.xianyu_origin

# Token 过期标记（含闲鱼历史拼写错误 EXOIRED，代码兼容）
TOKEN_EXPIRED_CODES = {"FAIL_SYS_TOKEN_EXOIRED", "FAIL_SYS_TOKEN_EXPIRED", "FAIL_SYS_TOKEN_EMPTY"}
# 风控标记
RISK_CODES = {"FAIL_SYS_USER_VALIDATE", "RGV587", "FAIL_BIZ_WUA_IS_MACHINE"}
# Session/Cookie 失效标记（需用户重新登录复制 Cookie）
AUTH_FAIL_CODES = {
    "FAIL_SYS_SESSION_EXPIRED", "FAIL_SYS_USER_VALIDATE",
    "-1:session expired", "FAIL_BIZ_USER_VALIDATE",
}


def generate_sign(token: str, timestamp: str, data: str) -> str:
    """MTOP 签名：MD5('{token}&{timestamp}&{appKey}&{data}')"""
    msg = f"{token}&{timestamp}&{APP_KEY}&{data}"
    return hashlib.md5(msg.encode("utf-8")).hexdigest()


class MtopError(Exception):
    """MTOP 调用异常"""

    def __init__(self, code: str, message: str, *, risk: bool = False, auth_fail: bool = False):
        self.code = code
        self.message = message
        self.risk = risk
        # auth_fail: Cookie/Session 失效（需用户重新登录复制 Cookie）
        self.auth_fail = auth_fail
        super().__init__(f"[{code}] {message}")


class MtopClient:
    """单个闲鱼账号的 MTOP 客户端。

    持有 Cookie 与 token，自动处理 Token 过期重签。
    """

    def __init__(self, cookie_str: str, *, timeout: float = 15.0):
        self.cookie_str = cookie_str
        self.cookies = parse_cookie_string(cookie_str)
        self.token = get_token(self.cookies) or ""
        self.unb = self.cookies.get("unb")
        self._timeout = timeout

    def _build_params(self, api: str, data: str, timestamp: str) -> dict:
        """构造 MTOP 请求 query 参数。"""
        sign = generate_sign(self.token, timestamp, data)
        return {
            "jsv": "2.7.2",
            "appKey": APP_KEY,
            "t": timestamp,
            "sign": sign,
            "api": api,
            "v": "1.0",
            "type": "originaljson",
            "dataType": "json",
            "timeout": "20000",
            "data": data,
        }

    def _headers(self) -> dict:
        return {
            "Origin": ORIGIN,
            "Referer": ORIGIN + "/",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Cookie": cookies_to_header(self.cookies),
        }

    def _refresh_token_from_response(self, response: httpx.Response) -> bool:
        """从响应的 Set-Cookie 提取新的 _m_h5_tk，更新 token。返回是否刷新成功。"""
        new_tk = None
        for header_val in response.headers.get_list("set-cookie"):
            # 格式: _m_h5_tk=token_timestamp; ...
            for part in header_val.split(";"):
                part = part.strip()
                if part.startswith("_m_h5_tk="):
                    new_tk = part[len("_m_h5_tk="):]
                    break
            if new_tk:
                break
        if new_tk and "_" in new_tk:
            self.token = new_tk.split("_")[0]
            self.cookies["_m_h5_tk"] = new_tk
            return True
        return False

    async def request(
        self,
        api: str,
        data: dict[str, Any],
        *,
        version: str = "1.0",
        retry_on_token_expired: bool = True,
    ) -> dict[str, Any]:
        """发起一次 MTOP 请求。自动处理 Token 过期重试一次。"""
        import json
        data_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        timestamp = str(int(time.time() * 1000))
        params = self._build_params(api, data_str, timestamp)
        url = MTOP_ENDPOINT.format(api=api, version=version)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, params=params, headers=self._headers(), data=urlencode({":": ""}))

        try:
            body = resp.json()
        except Exception:
            raise MtopError("PARSE_ERROR", "闲鱼接口响应格式异常，未记录原始响应")

        ret = body.get("ret", [])
        ret_str = "; ".join(ret) if isinstance(ret, list) else str(ret)

        # 风控拦截
        if any(code in ret_str for code in RISK_CODES):
            raise MtopError("RISK", "触发闲鱼风控（验证码/滑块），请稍后重试或更新 Cookie", risk=True)

        # Session/Cookie 失效：账号登录态已过期，需用户重新登录复制 Cookie
        if any(code in ret_str for code in AUTH_FAIL_CODES):
            raise MtopError("AUTH_FAIL", "闲鱼登录态已失效（Session过期），请重新登录闲鱼并更新 Cookie", auth_fail=True)

        # Token 过期：尝试刷新重试一次
        if any(code in ret_str for code in TOKEN_EXPIRED_CODES) and retry_on_token_expired:
            if self._refresh_token_from_response(resp):
                return await self.request(api, data, version=version, retry_on_token_expired=False)
            raise MtopError("TOKEN_EXPIRED", "Token 过期且无法自动刷新，请重新登录闲鱼复制新 Cookie", auth_fail=True)

        # 业务失败
        if not ret or "SUCCESS" not in ret_str.upper():
            raise MtopError("BIZ_FAIL", ret_str or "未知业务错误")

        return body.get("data", {})
