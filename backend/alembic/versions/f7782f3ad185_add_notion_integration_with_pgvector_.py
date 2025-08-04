"""Add Notion integration with pgvector support

Revision ID: f7782f3ad185
Revises: 20231201_120000
Create Date: 2025-08-02 17:32:16.993744

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f7782f3ad185'
down_revision = '20231201_120000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Note: pgvector extension will be added later when available
    # For now, we'll use regular ARRAY(Float) for embeddings
    
    # Create enum type for page types if it doesn't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE pagetype AS ENUM ('prd', 'research', 'analytics');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    page_type_enum = postgresql.ENUM('prd', 'research', 'analytics', name='pagetype')
    
    # Create notion_settings table
    op.create_table(
        'notion_settings',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notion_token', sa.Text(), nullable=True),
        sa.Column('prd_database_id', sa.String(255), nullable=True),
        sa.Column('research_database_id', sa.String(255), nullable=True),
        sa.Column('analytics_database_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_notion_settings_id', 'notion_settings', ['id'])
    
    # Create trigger for updating updated_at on notion_settings
    op.execute("""
        CREATE TRIGGER update_notion_settings_updated_at
        BEFORE UPDATE ON notion_settings
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # Create notion_pages table
    op.create_table(
        'notion_pages',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notion_page_id', sa.String(255), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('page_type', page_type_enum, nullable=False),
        sa.Column('notion_url', sa.String(1000), nullable=True),
        sa.Column('parent_page_id', sa.String(255), nullable=True),
        sa.Column('last_edited_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('notion_page_id')
    )
    op.create_index('ix_notion_pages_id', 'notion_pages', ['id'])
    op.create_index('ix_notion_pages_notion_page_id', 'notion_pages', ['notion_page_id'])
    op.create_index('ix_notion_pages_user_id', 'notion_pages', ['user_id'])
    op.create_index('ix_notion_pages_page_type', 'notion_pages', ['page_type'])
    
    # Create trigger for updating updated_at on notion_pages
    op.execute("""
        CREATE TRIGGER update_notion_pages_updated_at
        BEFORE UPDATE ON notion_pages
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # Create notion_chunks table
    op.create_table(
        'notion_chunks',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('page_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['page_id'], ['notion_pages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notion_chunks_id', 'notion_chunks', ['id'])
    op.create_index('ix_notion_chunks_page_id', 'notion_chunks', ['page_id'])
    
    # Create notion_comments table
    op.create_table(
        'notion_comments',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('page_id', sa.Integer(), nullable=False),
        sa.Column('notion_comment_id', sa.String(255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('author', sa.String(255), nullable=True),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['page_id'], ['notion_pages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('notion_comment_id')
    )
    op.create_index('ix_notion_comments_id', 'notion_comments', ['id'])
    op.create_index('ix_notion_comments_notion_comment_id', 'notion_comments', ['notion_comment_id'])
    op.create_index('ix_notion_comments_page_id', 'notion_comments', ['page_id'])


def downgrade() -> None:
    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('notion_comments')
    op.drop_table('notion_chunks')
    
    # Drop trigger before dropping notion_pages table
    op.execute("DROP TRIGGER IF EXISTS update_notion_pages_updated_at ON notion_pages;")
    op.drop_table('notion_pages')
    
    # Drop trigger before dropping notion_settings table
    op.execute("DROP TRIGGER IF EXISTS update_notion_settings_updated_at ON notion_settings;")
    op.drop_table('notion_settings')
    
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS pagetype;")
    
    # Drop pgvector extension (optional, might want to keep it)
    # op.execute("DROP EXTENSION IF EXISTS vector;") 