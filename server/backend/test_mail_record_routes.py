"""D5 测试补充：mail_record 路由加密往返测试。

验证敏感字段（gpt_password / email_password）的加密写入 + 解密读取往返：
1. POST 带明文密码 → DB 中存的是加密值
2. GET 列表 → 返回明文密码（解密）
3. POST 不带密码字段 → 空字符串存储，GET 返回空
4. POST 带 sent_at 字符串 → 正确解析为 datetime
5. DELETE 单条 → 删除成功
6. DELETE 清空 → 全部删除
7. 加密值不等于明文（防泄漏）
"""
import unittest
from datetime import datetime

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import MailRecord
from app.utils.crypto import is_encrypted


class MailRecordRouteTests(unittest.IsolatedAsyncioTestCase):
    """mail_record 路由：敏感字段加密往返。"""

    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(bind=self.engine, expire_on_commit=False)

        async def override_get_db():
            async with self.Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

    async def asyncTearDown(self):
        app.dependency_overrides.pop(get_db, None)
        await self.engine.dispose()

    async def test_post_encrypts_passwords_db_stores_ciphertext(self):
        """POST 带明文密码 → DB 中存的是加密值。"""
        payload = {
            "to": "customer@example.com",
            "customer_name": "测试客户",
            "email_account": "shop@qq.com",
            "gpt_password": "gpt_secret_123",
            "token_url": "https://example.com/token",
            "email_password": "smtp_pass_456",
            "subject": "发货通知",
            "status": "success",
            "sent_at": "2026-07-13T10:00:00",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/mail-records", json=payload)
            self.assertEqual(response.status_code, 200)
            rid = response.json()["id"]

        # 验证 DB 中存的是加密值
        async with self.Session() as db:
            record = await db.get(MailRecord, rid)
            self.assertIsNotNone(record)
            self.assertTrue(is_encrypted(record.gpt_password))
            self.assertTrue(is_encrypted(record.email_password))
            # 加密值不等于明文（防泄漏）
            self.assertNotEqual(record.gpt_password, "gpt_secret_123")
            self.assertNotEqual(record.email_password, "smtp_pass_456")

    async def test_get_returns_decrypted_passwords(self):
        """GET 列表 → 返回明文密码（解密）。"""
        payload = {
            "to": "customer@example.com",
            "email_account": "shop@qq.com",
            "gpt_password": "my_gpt_password",
            "token_url": "https://example.com/token",
            "email_password": "my_smtp_password",
            "subject": "发货通知",
            "status": "success",
            "sent_at": "2026-07-13T10:00:00",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/api/mail-records", json=payload)
            response = await client.get("/api/mail-records")
            self.assertEqual(response.status_code, 200)
            items = response.json()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["gpt_password"], "my_gpt_password")
            self.assertEqual(items[0]["email_password"], "my_smtp_password")

    async def test_post_without_passwords_stores_empty(self):
        """POST 不带密码字段 → 空字符串存储，GET 返回空。"""
        payload = {
            "to": "customer@example.com",
            "email_account": "shop@qq.com",
            "gpt_password": "",
            "token_url": "https://example.com/token",
            "email_password": "",
            "subject": "发货通知",
            "status": "success",
            "sent_at": "2026-07-13T10:00:00",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/mail-records", json=payload)
            self.assertEqual(response.status_code, 200)
            rid = response.json()["id"]

            get_response = await client.get("/api/mail-records")
            items = get_response.json()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["gpt_password"], "")
            self.assertEqual(items[0]["email_password"], "")

        # 验证 DB 中也是空字符串
        async with self.Session() as db:
            record = await db.get(MailRecord, rid)
            self.assertEqual(record.gpt_password, "")
            self.assertEqual(record.email_password, "")

    async def test_post_parses_sent_at_string(self):
        """POST 带 sent_at 字符串 → 正确解析为 datetime。"""
        payload = {
            "to": "customer@example.com",
            "email_account": "shop@qq.com",
            "gpt_password": "",
            "token_url": "https://example.com/token",
            "email_password": "",
            "subject": "发货通知",
            "status": "success",
            "sent_at": "2026-07-13T15:30:00",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/mail-records", json=payload)
            self.assertEqual(response.status_code, 200)
            rid = response.json()["id"]

        # 验证 DB 中 sent_at 是 datetime
        async with self.Session() as db:
            record = await db.get(MailRecord, rid)
            self.assertIsInstance(record.sent_at, datetime)
            self.assertEqual(record.sent_at.year, 2026)
            self.assertEqual(record.sent_at.month, 7)
            self.assertEqual(record.sent_at.day, 13)
            self.assertEqual(record.sent_at.hour, 15)
            self.assertEqual(record.sent_at.minute, 30)

    async def test_delete_single_record(self):
        """DELETE 单条 → 删除成功。"""
        payload = {
            "to": "customer@example.com",
            "email_account": "shop@qq.com",
            "gpt_password": "p1",
            "token_url": "url",
            "email_password": "p2",
            "subject": "s",
            "status": "success",
            "sent_at": "2026-07-13T10:00:00",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            post_resp = await client.post("/api/mail-records", json=payload)
            rid = post_resp.json()["id"]
            delete_resp = await client.delete(f"/api/mail-records/{rid}")
            self.assertEqual(delete_resp.status_code, 200)
            self.assertTrue(delete_resp.json()["ok"])

            # 验证已删除
            get_resp = await client.get("/api/mail-records")
            self.assertEqual(len(get_resp.json()), 0)

    async def test_clear_all_records(self):
        """DELETE 清空 → 全部删除。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 创建 3 条记录
            for i in range(3):
                payload = {
                    "to": f"customer{i}@example.com",
                    "email_account": "shop@qq.com",
                    "gpt_password": f"p{i}",
                    "token_url": "url",
                    "email_password": "ep",
                    "subject": "s",
                    "status": "success",
                    "sent_at": "2026-07-13T10:00:00",
                }
                await client.post("/api/mail-records", json=payload)

            # 清空
            clear_resp = await client.delete("/api/mail-records")
            self.assertEqual(clear_resp.status_code, 200)
            self.assertTrue(clear_resp.json()["ok"])

            # 验证全部删除
            get_resp = await client.get("/api/mail-records")
            self.assertEqual(len(get_resp.json()), 0)

    async def test_encrypted_password_roundtrip_multiple_records(self):
        """多条记录的加密往返：每条独立加密，互不干扰。"""
        passwords = ["pwd_a", "pwd_b", "pwd_c"]
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for pwd in passwords:
                payload = {
                    "to": f"{pwd}@example.com",
                    "email_account": "shop@qq.com",
                    "gpt_password": pwd,
                    "token_url": "url",
                    "email_password": pwd,
                    "subject": "s",
                    "status": "success",
                    "sent_at": "2026-07-13T10:00:00",
                }
                await client.post("/api/mail-records", json=payload)

            get_resp = await client.get("/api/mail-records")
            items = get_resp.json()
            self.assertEqual(len(items), 3)
            returned_passwords = {item["gpt_password"] for item in items}
            self.assertEqual(returned_passwords, set(passwords))

        # 验证 DB 中每条都独立加密（nonce 不同）
        async with self.Session() as db:
            records = (await db.execute(select(MailRecord))).scalars().all()
            self.assertEqual(len(records), 3)
            ciphertexts = {r.gpt_password for r in records}
            self.assertEqual(len(ciphertexts), 3, "每条记录的密文应不同（nonce 随机）")
            for r in records:
                self.assertTrue(is_encrypted(r.gpt_password))

    async def test_delete_nonexistent_record_returns_404(self):
        """DELETE 不存在的 id 应返回 404（与 expenses 路由行为一致）。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.delete("/api/mail-records/9999")
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
