import asyncio
import json

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import Settings, settings
from .algorithm_profiles import backfill_algorithm_profiles
from .database import Database, get_session
from .migrations import upgrade_database
from .models import WorkflowEvent
from .orders import advance_order, create_order, get_order, list_orders, list_products
from .schemas import OrderCreate, OrderList, OrderRead, ProductRead, WorkflowEventRead
from .seed import seed_products


def create_app(database_url: str | None = None) -> FastAPI:
    app_settings = Settings(database_url=database_url) if database_url else settings
    database = Database(app_settings.database_url)
    upgrade_database(database.url)
    with database.session() as session:
        seed_products(session)
        backfill_algorithm_profiles(session)

    application = FastAPI(title="Online Order Operations API", version="0.1.0")
    application.state.database = database
    application.state.settings = app_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )

    @application.get("/health")
    def health(request: Request) -> dict[str, str]:
        app_database: Database = request.app.state.database
        with app_database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "service": app_settings.service_name, "database": "ok"}

    @application.get("/api/orders/products", response_model=list[ProductRead])
    def products(session: Session = Depends(get_session)) -> list[ProductRead]:
        return list_products(session)

    @application.post("/api/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
    def submit_order(payload: OrderCreate, session: Session = Depends(get_session)) -> OrderRead:
        return OrderRead.model_validate(create_order(session, payload))

    @application.get("/api/orders", response_model=OrderList)
    def orders(session: Session = Depends(get_session)) -> OrderList:
        items = [OrderRead.model_validate(order) for order in list_orders(session)]
        return OrderList(items=items, total=len(items))

    @application.get("/api/orders/{order_id}", response_model=OrderRead)
    def order(order_id: str, session: Session = Depends(get_session)) -> OrderRead:
        return OrderRead.model_validate(get_order(session, order_id))

    @application.post("/api/orders/{order_id}/advance", response_model=OrderRead)
    def advance(order_id: str, session: Session = Depends(get_session)) -> OrderRead:
        return OrderRead.model_validate(advance_order(session, order_id))

    @application.get("/api/orders/{order_id}/events/stream")
    async def stream_order_events(
        request: Request,
        order_id: str,
        after: int = 0,
    ) -> StreamingResponse:
        with database.session() as session:
            get_order(session, order_id)

        async def event_stream():
            cursor = after

            def load_events() -> tuple[list[dict[str, object]], str]:
                with database.session() as session:
                    order = get_order(session, order_id)
                    events = session.scalars(
                        select(WorkflowEvent)
                        .where(
                            WorkflowEvent.order_id == order_id,
                            WorkflowEvent.id > cursor,
                        )
                        .order_by(WorkflowEvent.id)
                    ).all()
                    payloads = [
                        WorkflowEventRead.model_validate(event).model_dump(mode="json")
                        for event in events
                    ]
                    return payloads, order.status

            while not await request.is_disconnected():
                payloads, order_status = await asyncio.to_thread(load_events)
                if payloads:
                    for payload in payloads:
                        cursor = int(payload["id"])
                        yield f"id: {cursor}\ndata: {json.dumps(payload)}\n\n"
                else:
                    yield ": keepalive\n\n"
                if order_status in {"delivered", "cancelled"}:
                    return
                await asyncio.sleep(0.75)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return application


app = create_app()
