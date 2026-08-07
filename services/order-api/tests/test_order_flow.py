import asyncio
from tempfile import TemporaryDirectory

from httpx import ASGITransport, AsyncClient

from app.main import create_app


ORDER = {
    "customer_name": "Maya Chen",
    "customer_email": "maya@example.com",
    "address_line": "451 Cedar Avenue",
    "city": "Seattle",
    "region": "WA",
    "postal_code": "98101",
    "items": [
        {"product_id": "trail-pack", "quantity": 1},
        {"product_id": "steel-bottle", "quantity": 1},
    ],
}


def test_happy_path_persists_events_and_decisions() -> None:
    async def run() -> None:
        with TemporaryDirectory() as directory:
            app = create_app(f"sqlite:///{directory}/orders.db")
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                products = await client.get("/api/orders/products")
                assert products.status_code == 200
                assert len(products.json()) == 6
                openapi = await client.get("/openapi.json")
                assert "/api/orders/{order_id}/events/stream" in openapi.json()["paths"]

                submitted = await client.post("/api/orders", json=ORDER)
                assert submitted.status_code == 201
                order = submitted.json()
                assert order["status"] == "submitted"
                assert [event["event_type"] for event in order["events"]] == ["order.submitted"]

                statuses = [
                    "address_validated",
                    "payment_cleared",
                    "allocated",
                    "packed",
                    "shipped",
                    "delivered",
                ]
                for expected in statuses:
                    advanced = await client.post(f"/api/orders/{order['id']}/advance")
                    assert advanced.status_code == 200
                    order = advanced.json()
                    assert order["status"] == expected

                assert [decision["method"] for decision in order["decisions"]] == [
                    "rule",
                    "ai-classification",
                    "optimization",
                    "ai-prediction",
                ]
                assert [decision["algorithm_profile"]["training_required"] for decision in order["decisions"]] == [
                    False,
                    True,
                    False,
                    True,
                ]
                assert order["decisions"][0]["algorithm_profile"]["category"] == "Deterministic rule system"
                assert order["decisions"][1]["algorithm_profile"]["features"][0]["name"] == "Order amount"
                assert order["decisions"][2]["algorithm_profile"]["metrics"][0]["name"] == "Feasibility rate"
                assert order["decisions"][3]["algorithm_profile"]["split_strategy"].startswith("Time-ordered")
                payment = order["decisions"][1]
                assert payment["impact"]["output_name"] == "Fraud probability"
                assert payment["impact"]["output_value"] == 19.0
                assert payment["impact"]["selected_branch"] == "Approve automatically"
                assert "manual fraud review" in payment["impact"]["counterfactual"]
                delivery = order["decisions"][3]
                assert delivery["impact"]["output_name"] == "Late-delivery probability"
                assert delivery["impact"]["output_value"] == 16.0
                assert delivery["impact"]["selected_branch"] == "Dispatch on the original promise"
                assert delivery["impact"]["input_signals"][1]["label"] == "Shipment complexity"
                assert len(order["events"]) == 7
                assert order["events"][-1]["event_type"] == "order.delivered"
                completed = await client.post(f"/api/orders/{order['id']}/advance")
                assert completed.status_code == 409

    asyncio.run(run())