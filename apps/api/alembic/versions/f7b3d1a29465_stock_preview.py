"""Persist the one-stock preview binding.

Revision ID: f7b3d1a29465
Revises: e6a2c9f08314
"""
from alembic import op
import sqlalchemy as sa

revision = "f7b3d1a29465"
down_revision = "e6a2c9f08314"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("advanced_preview_code", sa.String(16)))


def downgrade() -> None:
    op.drop_column("users", "advanced_preview_code")
