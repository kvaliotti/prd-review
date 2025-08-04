"""add_page_type_column_only

Revision ID: 6d1a43a8aa4b
Revises: 16a2e296ae74
Create Date: 2025-08-03 22:01:23.922820

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d1a43a8aa4b'
down_revision = '16a2e296ae74'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add page_type column to notion_chunks for PGVector filtering
    op.add_column('notion_chunks', sa.Column('page_type', sa.Enum('prd', 'research', 'analytics', name='pagetype'), nullable=True))
    
    # Populate page_type from related notion_pages
    op.execute("""
        UPDATE notion_chunks 
        SET page_type = notion_pages.page_type 
        FROM notion_pages 
        WHERE notion_chunks.page_id = notion_pages.id
    """)


def downgrade() -> None:
    # Remove page_type column
    op.drop_column('notion_chunks', 'page_type') 