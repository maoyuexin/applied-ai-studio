import asyncio
from tempfile import TemporaryDirectory

from httpx import ASGITransport, AsyncClient

from app.main import create_app


def test_health_checks_database_connection() -> None:
    async def run() -> None:
        with TemporaryDirectory() as directory:
            app = create_app(f"sqlite:///{directory}/orders.db")
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/health")

            assert response.status_code == 200
            assert response.json() == {
                "status": "ok",
                "service": "order-api",
                "database": "ok",
            }

    asyncio.run(run())
