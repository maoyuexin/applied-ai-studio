# Online Order Operations API

FastAPI domain service for the executable Online Order workflow.

## Responsibilities

- Own products, inventory, customers, orders, line items, decisions, and events.
- Advance the happy-path state machine one persisted transition at a time.
- Publish order events through server-sent events for synchronized browser views.
- Seed deterministic synthetic products and inventory.
- Apply Alembic migrations before serving requests.
- Persist structured AI impact: model identity, signal contributions, output,
  thresholds, selected branch, process and business effects, counterfactual, and
  human authority.
- Persist algorithm profiles for address rules, payment classification,
  fulfillment optimization, and delivery prediction. Profiles define features,
  data sources, training or configuration, split strategy, metrics, testing,
  monitoring, and limitations.

## Local setup

From the `applied-ai-studio` root:

```bash
python3.11 -m venv .venv
npm run setup:orders
npm run dev:orders
```

The service listens on <http://127.0.0.1:4330> through the npm fallback. Aspire
uses service discovery and may map a different host port.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Verify service and database connectivity |
| `GET` | `/api/orders/products` | List synthetic products and available inventory |
| `POST` | `/api/orders` | Submit and persist an order |
| `GET` | `/api/orders` | List current orders |
| `GET` | `/api/orders/{id}` | Read one complete order aggregate |
| `POST` | `/api/orders/{id}/advance` | Run one state transition |
| `GET` | `/api/orders/{id}/events/stream` | Stream new workflow events |

Payment screening records a synthetic fraud-classification probability. Shipment
dispatch records a synthetic late-delivery prediction. Both influence explicit
workflow branches rather than controlling the state machine directly.

The local database is ignored at `services/order-api/data/orders.db`. Test runs
use temporary migrated databases.
