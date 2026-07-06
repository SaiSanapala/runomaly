"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-05
"""

from __future__ import annotations

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from backend.app.db.base import Base
    from backend.app.models import entities  # noqa: F401

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from backend.app.db.base import Base
    from backend.app.models import entities  # noqa: F401

    Base.metadata.drop_all(bind=bind)
