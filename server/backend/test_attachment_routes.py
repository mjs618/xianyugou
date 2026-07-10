import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app


class AttachmentRouteTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_upload_batch_content_and_delete(self):
        content = b"fake-png-content"
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            uploaded = await client.post(
                "/api/attachments",
                files={"file": ("sample.png", content, "image/png")},
            )
            self.assertEqual(uploaded.status_code, 200)
            metadata = uploaded.json()
            self.assertEqual(metadata["name"], "sample.png")
            self.assertEqual(metadata["size"], len(content))

            batch = await client.post(
                "/api/attachments/batch",
                json={"ids": [metadata["id"], 9999]},
            )
            self.assertEqual([item["id"] for item in batch.json()], [metadata["id"]])

            downloaded = await client.get(
                f"/api/attachments/{metadata['id']}/content"
            )
            self.assertEqual(downloaded.status_code, 200)
            self.assertEqual(downloaded.content, content)
            self.assertEqual(downloaded.headers["content-type"], "image/png")

            deleted = await client.delete(f"/api/attachments/{metadata['id']}")
            self.assertEqual(deleted.status_code, 200)
            missing = await client.get(
                f"/api/attachments/{metadata['id']}/content"
            )
            self.assertEqual(missing.status_code, 404)

    async def test_upload_rejects_disallowed_mime(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/attachments",
                files={"file": ("notes.txt", b"text", "text/plain")},
            )
        self.assertEqual(response.status_code, 400)

    async def test_upload_rejects_empty_and_oversized_files(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            empty = await client.post(
                "/api/attachments",
                files={"file": ("empty.png", b"", "image/png")},
            )
            oversized = await client.post(
                "/api/attachments",
                files={
                    "file": (
                        "large.png",
                        b"x" * (5 * 1024 * 1024 + 1),
                        "image/png",
                    )
                },
            )
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(oversized.status_code, 413)


if __name__ == "__main__":
    unittest.main()
