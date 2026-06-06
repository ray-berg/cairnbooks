"""init

Revision ID: 0001
Revises:
Create Date: 2026-06-06 00:00:00.000000

Empty baseline migration.  All subsequent migrations will build on top of
this revision.  Add ``op.*`` calls here when the first database tables are
introduced.
"""

from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401

from alembic import op  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply schema changes — empty baseline."""
    pass


def downgrade() -> None:
    """Revert schema changes — empty baseline."""
    pass
