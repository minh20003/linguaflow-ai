"""Keep explicit assistant mentions private to their requester.

Revision ID: b2f8d4c1a903
Revises: a7d6c2b8e4f1
"""

from alembic import op
import sqlalchemy as sa


revision = "b2f8d4c1a903"
down_revision = "a7d6c2b8e4f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "visible_to_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_messages_conversation_visible_created_at",
        "messages",
        ["conversation_id", "visible_to_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_visible_created_at", table_name="messages")
    op.drop_column("messages", "visible_to_user_id")
