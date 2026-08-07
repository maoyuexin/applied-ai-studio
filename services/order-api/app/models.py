from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(400))
    category: Mapped[str] = mapped_column(String(80))
    price_cents: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(default=True)

    inventory: Mapped["Inventory"] = relationship(back_populates="product")

    @property
    def quantity_available(self) -> int:
        return self.inventory.quantity_available - self.inventory.quantity_reserved


class Inventory(Base):
    __tablename__ = "inventory"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(String(30), default="SEA-01")
    quantity_available: Mapped[int] = mapped_column(Integer)
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[Product] = relationship(back_populates="inventory")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), index=True)
    address_line: Mapped[str] = mapped_column(String(240))
    city: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(80))
    postal_code: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted','address_validated','payment_cleared','allocated','packed','shipped','delivered','cancelled')",
            name="ck_orders_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    display_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="submitted", index=True)
    scenario: Mapped[str] = mapped_column(String(60), default="happy-path")
    subtotal_cents: Mapped[int] = mapped_column(Integer)
    shipping_cents: Mapped[int] = mapped_column(Integer)
    total_cents: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    customer: Mapped[Customer] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["WorkflowEvent"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="WorkflowEvent.sequence",
    )
    decisions: Mapped[list["OrderDecision"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderDecision.created_at",
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("order_id", "product_id", name="uq_order_product"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_cents: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (UniqueConstraint("order_id", "sequence", name="uq_order_event_sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    stage: Mapped[str] = mapped_column(String(50))
    actor: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(String(300))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    order: Mapped[Order] = relationship(back_populates="events")


class OrderDecision(Base):
    __tablename__ = "order_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    decision_type: Mapped[str] = mapped_column(String(80), index=True)
    method: Mapped[str] = mapped_column(String(50))
    recommendation: Mapped[str] = mapped_column(String(120))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="applied")
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    impact: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    algorithm_profile: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    decided_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    order: Mapped[Order] = relationship(back_populates="decisions")
