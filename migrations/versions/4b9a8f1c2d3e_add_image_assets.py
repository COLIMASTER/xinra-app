"""add image assets table

Revision ID: 4b9a8f1c2d3e
Revises: 0fcedfa35f5a
Create Date: 2026-01-08 20:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "4b9a8f1c2d3e"
down_revision = "0fcedfa35f5a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "image_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("image_assets")
