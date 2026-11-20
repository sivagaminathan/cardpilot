"""add unique constraint on profile_cards

Revision ID: b88bb3c71071
Revises: 460ae59a41d3
Create Date: 2026-11-19 19:02:22.395665

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b88bb3c71071"
down_revision: str | Sequence[str] | None = "460ae59a41d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT_NAME = "uq_profile_cards_profile_product_nickname"


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    dup_count = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM ("
            "  SELECT profile_id, card_product_id, nickname "
            "  FROM profile_cards "
            "  GROUP BY profile_id, card_product_id, nickname "
            "  HAVING COUNT(*) > 1"
            ") AS dups"
        )
    ).scalar_one()
    if dup_count > 0:
        raise RuntimeError(
            "Cannot apply uq_profile_cards_profile_product_nickname: "
            f"found {dup_count} duplicate (profile_id, card_product_id, nickname) group(s)."
        )

    op.create_unique_constraint(
        _CONSTRAINT_NAME,
        "profile_cards",
        ["profile_id", "card_product_id", "nickname"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(_CONSTRAINT_NAME, "profile_cards", type_="unique")
