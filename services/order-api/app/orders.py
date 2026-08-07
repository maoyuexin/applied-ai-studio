from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .algorithm_profiles import algorithm_profile
from .models import Customer, Inventory, Order, OrderDecision, OrderItem, Product, WorkflowEvent
from .schemas import OrderCreate, ProductRead


ORDER_LOAD = (
    selectinload(Order.customer),
    selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.inventory),
    selectinload(Order.events),
    selectinload(Order.decisions),
)


def list_products(session: Session) -> list[ProductRead]:
    products = session.scalars(
        select(Product)
        .where(Product.active.is_(True))
        .options(selectinload(Product.inventory))
        .order_by(Product.name)
    ).all()
    return [
        ProductRead(
            id=product.id,
            name=product.name,
            description=product.description,
            category=product.category,
            price_cents=product.price_cents,
            image_url=product.image_url,
            quantity_available=product.inventory.quantity_available
            - product.inventory.quantity_reserved,
        )
        for product in products
    ]


def get_order(session: Session, order_id: str) -> Order:
    order = session.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(*ORDER_LOAD)
        .execution_options(populate_existing=True)
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order


def list_orders(session: Session) -> list[Order]:
    return list(
        session.scalars(select(Order).options(*ORDER_LOAD).order_by(Order.created_at.desc())).all()
    )


def _next_sequence(session: Session, order_id: str) -> int:
    current = session.scalar(
        select(func.coalesce(func.max(WorkflowEvent.sequence), 0)).where(
            WorkflowEvent.order_id == order_id
        )
    )
    return int(current or 0) + 1


def _add_event(
    session: Session,
    order: Order,
    *,
    event_type: str,
    stage: str,
    actor: str,
    summary: str,
    details: dict[str, object] | None = None,
) -> None:
    session.add(
        WorkflowEvent(
            order_id=order.id,
            sequence=_next_sequence(session, order.id),
            event_type=event_type,
            stage=stage,
            actor=actor,
            summary=summary,
            details=details or {},
        )
    )


def create_order(session: Session, payload: OrderCreate) -> Order:
    product_ids = {item.product_id for item in payload.items}
    products = {
        product.id: product
        for product in session.scalars(
            select(Product)
            .where(Product.id.in_(product_ids), Product.active.is_(True))
            .options(selectinload(Product.inventory))
        ).all()
    }
    if len(products) != len(product_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown product.")

    subtotal = 0
    for item in payload.items:
        product = products[item.product_id]
        available = product.inventory.quantity_available - product.inventory.quantity_reserved
        if item.quantity > available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only {available} units of {product.name} are available.",
            )
        subtotal += product.price_cents * item.quantity

    shipping = 0 if subtotal >= 10_000 else 800
    customer = Customer(
        name=payload.customer_name,
        email=str(payload.customer_email),
        address_line=payload.address_line,
        city=payload.city,
        region=payload.region,
        postal_code=payload.postal_code,
    )
    order = Order(
        display_id=f"ORD-{uuid4().hex[:8].upper()}",
        customer=customer,
        scenario=payload.scenario,
        subtotal_cents=subtotal,
        shipping_cents=shipping,
        total_cents=subtotal + shipping,
    )
    for item in payload.items:
        product = products[item.product_id]
        order.items.append(
            OrderItem(
                product_id=product.id,
                quantity=item.quantity,
                unit_price_cents=product.price_cents,
            )
        )
    session.add(order)
    session.flush()
    _add_event(
        session,
        order,
        event_type="order.submitted",
        stage="input",
        actor="Customer",
        summary="Order submitted from the customer storefront.",
        details={"scenario": payload.scenario, "item_count": sum(i.quantity for i in payload.items)},
    )
    session.commit()
    return get_order(session, order.id)


@dataclass(frozen=True)
class Transition:
    next_status: str
    event_type: str
    stage: str
    actor: str
    summary: str
    apply: Callable[[Session, Order], None] | None = None


def _validate_address(session: Session, order: Order) -> None:
    session.add(
        OrderDecision(
            order_id=order.id,
            decision_type="address_validation",
            method="rule",
            recommendation="deliverable",
            status="applied",
            evidence=["Postal code format valid", "Service region supported"],
            algorithm_profile=algorithm_profile("address_validation"),
            decided_by="Commerce system",
        )
    )


def _screen_payment(session: Session, order: Order) -> None:
    baseline = 0.18
    order_value_effect = min(order.total_cents / 200_000, 0.08)
    region_effect = -0.03
    device_effect = -0.02
    score = round(baseline + order_value_effect + region_effect + device_effect, 2)
    session.add(
        OrderDecision(
            order_id=order.id,
            decision_type="payment_screening",
            method="ai-classification",
            recommendation="approve",
            score=score,
            status="applied",
            evidence=["Known delivery region", "Order value within normal range", "No device mismatch"],
            impact={
                "question": "Should this payment continue automatically or pause for fraud review?",
                "model_name": "Synthetic Payment Risk Classifier",
                "model_version": "baseline-v1",
                "model_kind": "binary classification",
                "output_name": "Fraud probability",
                "output_value": round(score * 100, 2),
                "output_unit": "%",
                "output_label": "Low risk",
                "thresholds": [
                    {"label": "Approve", "range": "0-34%", "outcome": "Clear payment and begin allocation"},
                    {"label": "Review", "range": "35-69%", "outcome": "Pause order in the fraud review queue"},
                    {"label": "Decline", "range": "70-100%", "outcome": "Block fulfillment and require analyst disposition"},
                ],
                "selected_branch": "Approve automatically",
                "process_effect": "Payment cleared; the order advanced directly to inventory and carrier allocation.",
                "business_effect": "Avoided an estimated four-minute manual review while preserving the policy threshold.",
                "human_boundary": "A fraud analyst owns every review or decline outcome and can override model evidence.",
                "counterfactual": "At 35% or higher, this order would stop before allocation and enter manual fraud review.",
                "input_signals": [
                    {
                        "label": "Portfolio baseline",
                        "value": "18%",
                        "influence": "neutral",
                        "contribution": "+18 pts",
                        "explanation": "Synthetic starting risk before order-specific signals.",
                    },
                    {
                        "label": "Order value",
                        "value": f"${order.total_cents / 100:,.2f}",
                        "influence": "raises",
                        "contribution": f"+{round(order_value_effect * 100)} pts",
                        "explanation": "Higher value modestly increases exposure in this synthetic model.",
                    },
                    {
                        "label": "Delivery region",
                        "value": "Known service area",
                        "influence": "lowers",
                        "contribution": "-3 pts",
                        "explanation": "The destination matches a supported, previously observed region.",
                    },
                    {
                        "label": "Device consistency",
                        "value": "No mismatch",
                        "influence": "lowers",
                        "contribution": "-2 pts",
                        "explanation": "No synthetic device anomaly was present for this order.",
                    },
                ],
            },
            algorithm_profile=algorithm_profile("payment_screening"),
            decided_by="Synthetic fraud scorer",
        )
    )


def _allocate_inventory(session: Session, order: Order) -> None:
    for item in order.items:
        inventory = session.get(Inventory, item.product_id)
        if not inventory:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Inventory unavailable.")
        available = inventory.quantity_available - inventory.quantity_reserved
        if available < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Inventory changed before allocation for {item.product.name}.",
            )
        inventory.quantity_reserved += item.quantity
    session.add(
        OrderDecision(
            order_id=order.id,
            decision_type="fulfillment_allocation",
            method="optimization",
            recommendation="SEA-01 / Northline Ground",
            status="applied",
            evidence=["All items available in one warehouse", "Delivery window feasible"],
            algorithm_profile=algorithm_profile("fulfillment_allocation"),
            decided_by="Allocation engine",
        )
    )


def _predict_delivery_risk(session: Session, order: Order) -> None:
    item_units = sum(item.quantity for item in order.items)
    item_complexity_effect = min(item_units * 0.02, 0.08)
    score = round(0.12 + item_complexity_effect, 2)
    expected_delay_hours = round(score * 12, 1)
    session.add(
        OrderDecision(
            order_id=order.id,
            decision_type="delivery_risk_prediction",
            method="ai-prediction",
            recommendation="keep original promise",
            score=score,
            status="applied",
            evidence=[
                "Single-warehouse fulfillment",
                "No active route disruption",
                f"{item_units} units in the shipment",
            ],
            impact={
                "question": "Is this shipment likely to miss its promised delivery window?",
                "model_name": "Synthetic Delivery Risk Predictor",
                "model_version": "baseline-v1",
                "model_kind": "probability prediction",
                "output_name": "Late-delivery probability",
                "output_value": round(score * 100, 2),
                "output_unit": "%",
                "output_label": "On track",
                "thresholds": [
                    {"label": "On track", "range": "0-39%", "outcome": "Keep the promise and continue delivery"},
                    {"label": "Monitor", "range": "40-64%", "outcome": "Recalculate ETA and watch route events"},
                    {"label": "Intervene", "range": "65-100%", "outcome": "Route to support and review the customer promise"},
                ],
                "selected_branch": "Dispatch on the original promise",
                "process_effect": "Shipment continued without a delivery exception or proactive support case.",
                "business_effect": f"Retained the original promise; estimated delay exposure is {expected_delay_hours} hours.",
                "human_boundary": "A fulfillment manager owns promise changes, carrier escalation, and customer compensation.",
                "counterfactual": "At 40% risk the shipment would enter monitoring; at 65% it would trigger support intervention.",
                "input_signals": [
                    {
                        "label": "Route baseline",
                        "value": "12%",
                        "influence": "neutral",
                        "contribution": "+12 pts",
                        "explanation": "Synthetic baseline for the selected warehouse and ground carrier lane.",
                    },
                    {
                        "label": "Shipment complexity",
                        "value": f"{item_units} units",
                        "influence": "raises",
                        "contribution": f"+{round(item_complexity_effect * 100)} pts",
                        "explanation": "More units add handling and transfer exposure in the simulation.",
                    },
                    {
                        "label": "Fulfillment source",
                        "value": "One warehouse",
                        "influence": "lowers",
                        "contribution": "0 pts",
                        "explanation": "No split shipment or inter-warehouse transfer is required.",
                    },
                    {
                        "label": "Active disruptions",
                        "value": "None",
                        "influence": "lowers",
                        "contribution": "0 pts",
                        "explanation": "No weather, capacity, or carrier exception is active in the happy path.",
                    },
                ],
            },
            algorithm_profile=algorithm_profile("delivery_risk_prediction"),
            decided_by="Synthetic delivery predictor",
        )
    )


TRANSITIONS = {
    "submitted": Transition(
        "address_validated",
        "address.validated",
        "decision",
        "Commerce system",
        "Delivery address passed deterministic service-area checks.",
        _validate_address,
    ),
    "address_validated": Transition(
        "payment_cleared",
        "payment.screened",
        "decision",
        "Synthetic fraud scorer",
        "Payment was classified as low risk and cleared.",
        _screen_payment,
    ),
    "payment_cleared": Transition(
        "allocated",
        "inventory.allocated",
        "decision",
        "Allocation engine",
        "Inventory and carrier capacity were assigned.",
        _allocate_inventory,
    ),
    "allocated": Transition(
        "packed",
        "shipment.packed",
        "action",
        "Warehouse",
        "Warehouse completed picking and packing.",
    ),
    "packed": Transition(
        "shipped",
        "shipment.dispatched",
        "action",
        "Carrier",
        "Carrier accepted the parcel and began delivery.",
        _predict_delivery_risk,
    ),
    "shipped": Transition(
        "delivered",
        "order.delivered",
        "outcome",
        "Carrier",
        "Order was delivered and the customer retained it.",
    ),
}


def advance_order(session: Session, order_id: str) -> Order:
    order = get_order(session, order_id)
    transition = TRANSITIONS.get(order.status)
    if not transition:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order has no remaining happy-path transition.",
        )
    if transition.apply:
        transition.apply(session, order)
    order.status = transition.next_status
    order.version += 1
    _add_event(
        session,
        order,
        event_type=transition.event_type,
        stage=transition.stage,
        actor=transition.actor,
        summary=transition.summary,
        details={"status": transition.next_status},
    )
    session.commit()
    return get_order(session, order.id)
