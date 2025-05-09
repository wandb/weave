"""create_configurations_table

Revision ID: f634ba358539
Revises:
Create Date: 2025-05-09 11:24:49.660234

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f634ba358539"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "configurations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_configurations_id"), "configurations", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_configurations_project_id"),
        "configurations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_configurations_type"), "configurations", ["type"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_configurations_type"), table_name="configurations")
    op.drop_index(op.f("ix_configurations_project_id"), table_name="configurations")
    op.drop_index(op.f("ix_configurations_id"), table_name="configurations")
    op.drop_table("configurations")
