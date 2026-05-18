"""semantic embeddings

Revision ID: 20260518_0015
Revises: 20260518_0014
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260518_0015"
down_revision: Union[str, None] = "20260518_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_table VARCHAR(100) NOT NULL,
            source_id UUID NOT NULL,
            owner_type VARCHAR(100) NOT NULL,
            owner_id UUID,
            content TEXT NOT NULL,
            content_hash VARCHAR(128) NOT NULL,
            embedding vector(1536) NOT NULL,
            embedding_metadata JSONB,
            model VARCHAR(255) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_semantic_embedding_source UNIQUE (source_table, source_id, content_hash)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_semantic_embeddings_source ON semantic_embeddings (source_table, source_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_semantic_embeddings_owner ON semantic_embeddings (owner_type, owner_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_semantic_embeddings_vector ON semantic_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS semantic_embeddings")
