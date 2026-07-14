"""D2 测试补充：customer_tag_service.delete_tag 级联清理。

验证 P1-4 批量化改造后的 delete_tag 正确级联清理：
1. delete_tag 删除标签定义
2. delete_tag 删除 CustomerTagRelation 关联关系
3. delete_tag 从客户的 tags 数组中移除标签名
4. delete_tag 不存在的标签幂等返回
5. delete_tag 客户不存在时不报错
6. delete_tag 批量清理多个客户的 tags（验证批量化不丢数据）
7. set_customer_tags 自动建标签 + 重建关联
"""
import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Customer, CustomerTag, CustomerTagRelation
from app.services.customer_tag_service import (
    create_tag,
    delete_tag,
    get_customer_tags,
    set_customer_tags,
)


class CustomerTagServiceTests(unittest.IsolatedAsyncioTestCase):
    """customer_tag_service 级联清理与 set_customer_tags 流程。"""

    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def _create_customer(self, db, nickname: str, customer_id: int) -> Customer:
        """创建客户并指定 id（测试用）。"""
        c = Customer(id=customer_id, xianyu_nickname=nickname)
        db.add(c)
        await db.flush()
        return c

    async def test_delete_tag_removes_tag_definition(self):
        """delete_tag 删除标签定义。"""
        async with self.Session() as db:
            tag = await create_tag(db, "vip客户", color="gold")
            tag_id = tag.id
            await db.commit()

        async with self.Session() as db:
            await delete_tag(db, tag_id)
            await db.commit()

        async with self.Session() as db:
            result = await db.get(CustomerTag, tag_id)
            self.assertIsNone(result)

    async def test_delete_tag_removes_relations(self):
        """delete_tag 删除关联关系。"""
        async with self.Session() as db:
            await self._create_customer(db, "客户A", 1)
            tag = await create_tag(db, "vip")
            await db.commit()
            await set_customer_tags(db, customer_id=1, tag_names=["vip"])
            await db.commit()
            # 确认关联存在
            relations = (await db.execute(
                __import__("sqlalchemy").select(CustomerTagRelation).where(
                    CustomerTagRelation.tag_id == tag.id
                )
            )).scalars().all()
            self.assertEqual(len(relations), 1)

        async with self.Session() as db:
            await delete_tag(db, tag.id)
            await db.commit()

        async with self.Session() as db:
            relations = (await db.execute(
                __import__("sqlalchemy").select(CustomerTagRelation).where(
                    CustomerTagRelation.tag_id == tag.id
                )
            )).scalars().all()
            self.assertEqual(len(relations), 0)

    async def test_delete_tag_removes_from_customer_tags_array(self):
        """delete_tag 从客户的 tags 数组中移除标签名。"""
        async with self.Session() as db:
            await self._create_customer(db, "客户A", 1)
            tag = await create_tag(db, "vip")
            await db.commit()
            await set_customer_tags(db, customer_id=1, tag_names=["vip", "高消费"])
            await db.commit()

        # 验证 tags 数组
        async with self.Session() as db:
            c = await db.get(Customer, 1)
            self.assertEqual(sorted(c.tags), ["vip", "高消费"])

        # 删除 vip 标签
        async with self.Session() as db:
            await delete_tag(db, tag.id)
            await db.commit()

        # 验证 tags 数组中不再有 vip
        async with self.Session() as db:
            c = await db.get(Customer, 1)
            self.assertEqual(c.tags, ["高消费"])

    async def test_delete_nonexistent_tag_is_idempotent(self):
        """删除不存在的标签幂等返回（不报错）。"""
        async with self.Session() as db:
            # 不存在的 tag_id：不应抛异常
            await delete_tag(db, 99999)

    async def test_delete_tag_handles_missing_customer_gracefully(self):
        """delete_tag 遇到关联但客户不存在的孤儿 relation 时不报错。

        验证批量化改造后，customers_map.get() 返回 None 时正确跳过。
        """
        async with self.Session() as db:
            # 创建标签 + 孤儿 relation（customer 不存在）
            tag = CustomerTag(name="孤儿标签", is_system=False)
            db.add(tag)
            await db.flush()
            db.add(CustomerTagRelation(customer_id=99999, tag_id=tag.id))
            await db.commit()

        async with self.Session() as db:
            # 不应抛异常
            await delete_tag(db, tag.id)
            await db.commit()

        async with self.Session() as db:
            result = await db.get(CustomerTag, tag.id)
            self.assertIsNone(result)

    async def test_delete_tag_batch_cleans_multiple_customers(self):
        """delete_tag 批量清理多个客户的 tags 数组（验证批量化不丢数据）。"""
        async with self.Session() as db:
            # 3 个客户都贴了同一标签
            await self._create_customer(db, "客户A", 1)
            await self._create_customer(db, "客户B", 2)
            await self._create_customer(db, "客户C", 3)
            tag = await create_tag(db, "vip")
            await db.commit()
            for cid in [1, 2, 3]:
                await set_customer_tags(db, customer_id=cid, tag_names=["vip"])
            await db.commit()

        # 删除 vip 标签
        async with self.Session() as db:
            await delete_tag(db, tag.id)
            await db.commit()

        # 验证 3 个客户的 tags 数组都清空
        async with self.Session() as db:
            for cid in [1, 2, 3]:
                c = await db.get(Customer, cid)
                self.assertEqual(c.tags, [], f"客户 {cid} 的 tags 应被清空")

    async def test_set_customer_tags_auto_creates_missing_tags(self):
        """set_customer_tags 自动建缺失的标签。"""
        async with self.Session() as db:
            await self._create_customer(db, "客户A", 1)
            await db.commit()
            # vip 已存在，高消费自动创建
            await create_tag(db, "vip")
            await db.commit()
            await set_customer_tags(db, customer_id=1, tag_names=["vip", "高消费"])
            await db.commit()

        async with self.Session() as db:
            tags = await get_customer_tags(db, customer_id=1)
            tag_names = sorted(t.name for t in tags)
            self.assertEqual(tag_names, ["vip", "高消费"])

    async def test_set_customer_tags_replaces_existing(self):
        """set_customer_tags 替换（而非追加）客户标签。"""
        async with self.Session() as db:
            await self._create_customer(db, "客户A", 1)
            await db.commit()
            # 第一次贴 vip + 高消费
            await set_customer_tags(db, customer_id=1, tag_names=["vip", "高消费"])
            await db.commit()
            # 第二次只贴 core
            await set_customer_tags(db, customer_id=1, tag_names=["core"])
            await db.commit()

        async with self.Session() as db:
            tags = await get_customer_tags(db, customer_id=1)
            tag_names = sorted(t.name for t in tags)
            self.assertEqual(tag_names, ["core"])
            # 客户的 tags 数组也应是 ["core"]
            c = await db.get(Customer, 1)
            self.assertEqual(c.tags, ["core"])

    async def test_set_customer_tags_skips_empty_names(self):
        """set_customer_tags 跳过空字符串与空白标签名。"""
        async with self.Session() as db:
            await self._create_customer(db, "客户A", 1)
            await db.commit()
            await set_customer_tags(db, customer_id=1, tag_names=["vip", "", "  ", "高消费"])
            await db.commit()

        async with self.Session() as db:
            tags = await get_customer_tags(db, customer_id=1)
            tag_names = sorted(t.name for t in tags)
            self.assertEqual(tag_names, ["vip", "高消费"])

    async def test_set_customer_tags_rejects_deleted_customer(self):
        """set_customer_tags 拒绝已删除的客户。"""
        async with self.Session() as db:
            from datetime import datetime
            c = Customer(id=1, xianyu_nickname="已删除", deleted_at=datetime(2026, 7, 1))
            db.add(c)
            await db.commit()

        async with self.Session() as db:
            from app.services.customer_tag_service import TagError
            with self.assertRaises(TagError):
                await set_customer_tags(db, customer_id=1, tag_names=["vip"])


if __name__ == "__main__":
    unittest.main()
