"""add pgvector embedding column"""

from alembic import op
from sqlalchemy import text

revision = "0002_pgvector"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    op.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(384)"))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding"))
