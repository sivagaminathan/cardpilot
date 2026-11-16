"""initial empty migration

Revision ID: f5f1d05a3578
Revises:
Create Date: 2026-11-15 21:39:42.203494

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "f5f1d05a3578"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
