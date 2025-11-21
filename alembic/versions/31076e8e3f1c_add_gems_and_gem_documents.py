"""add_gems_and_gem_documents

Revision ID: 31076e8e3f1c
Revises: cfd74c38ad07
Create Date: 2025-11-21 11:47:04.745534

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31076e8e3f1c'
down_revision: Union[str, None] = 'cfd74c38ad07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Verificar se as tabelas já existem
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Criar tabela gems
    if 'gems' not in existing_tables:
        op.create_table(
            'gems',
            sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('instructions', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        )
        op.create_index(op.f('ix_gems_user_id'), 'gems', ['user_id'], unique=False)
    
    # Criar tabela gem_documents
    if 'gem_documents' not in existing_tables:
        op.create_table(
            'gem_documents',
            sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('gem_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('filename', sa.String(255), nullable=False),
            sa.Column('file_path', sa.String(500), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['gem_id'], ['gems.id'], ondelete='CASCADE'),
        )
        op.create_index(op.f('ix_gem_documents_gem_id'), 'gem_documents', ['gem_id'], unique=False)
    
    # Criar tabela gem_document_embeddings
    if 'gem_document_embeddings' not in existing_tables:
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
        # Criar coluna como vector diretamente
        op.execute("""
            CREATE TABLE gem_document_embeddings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID NOT NULL UNIQUE REFERENCES gem_documents(id) ON DELETE CASCADE,
                embedding vector(768) NOT NULL,
                embedding_model VARCHAR(100) NOT NULL DEFAULT 'models/text-embedding-004',
                chunk_text TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        op.create_index('ix_gem_document_embeddings_document_id', 'gem_document_embeddings', ['document_id'], unique=True)


def downgrade() -> None:
    op.drop_table('gem_document_embeddings')
    op.drop_table('gem_documents')
    op.drop_table('gems')


