import unittest

from httpx import ASGITransport, AsyncClient

from app.main import app


class HealthRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_preserves_service_name_and_scheduler_state(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["service"], "xianyu-backend")
        self.assertIsInstance(payload["scheduler_running"], bool)


if __name__ == "__main__":
    unittest.main()
