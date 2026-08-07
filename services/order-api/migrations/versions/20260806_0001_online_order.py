"""Create the Online Order Operations schema.

Revision ID: 20260806_0001
Revises:
Create Date: 2026-08-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260806_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("address_line", sa.String(length=240), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("region", sa.String(length=80), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_email", "customers", ["email"])
    op.create_table(
        "inventory",
        sa.Column("product_id", sa.String(length=40), nullable=False),
        sa.Column("warehouse_code", sa.String(length=30), nullable=False),
        sa.Column("quantity_available", sa.Integer(), nullable=False),
        sa.Column("quantity_reserved", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("product_id"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("display_id", sa.String(length=20), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("scenario", sa.String(length=60), nullable=False),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("shipping_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('submitted','address_validated','payment_cleared','allocated','packed','shipped','delivered','cancelled')",
            name="ck_orders_status",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_display_id", "orders", ["display_id"], unique=True)
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "product_id", name="uq_order_product"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "sequence", name="uq_order_event_sequence"),
    )
    op.create_index("ix_workflow_events_event_type", "workflow_events", ["event_type"])
    op.create_index("ix_workflow_events_order_id", "workflow_events", ["order_id"])
    op.create_table(
        "order_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("decision_type", sa.String(length=80), nullable=False),
        sa.Column("method", sa.String(length=50), nullable=False),
        sa.Column("recommendation", sa.String(length=120), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("decided_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_decisions_decision_type", "order_decisions", ["decision_type"])
    op.create_index("ix_order_decisions_order_id", "order_decisions", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_decisions_order_id", table_name="order_decisions")
    op.drop_index("ix_order_decisions_decision_type", table_name="order_decisions")
    op.drop_table("order_decisions")
    op.drop_index("ix_workflow_events_order_id", table_name="workflow_events")
    op.drop_index("ix_workflow_events_event_type", table_name="workflow_events")
    op.drop_table("workflow_events")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_display_id", table_name="orders")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_table("orders")
    op.drop_table("inventory")
    op.drop_index("ix_customers_email", table_name="customers")
    op.drop_table("customers")
    op.drop_table("products")
