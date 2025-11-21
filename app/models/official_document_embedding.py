"""Modelo para embeddings de documentos oficiais."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.config.database import Base


class OfficialDocumentEmbedding(Base):
    """Embeddings de documentos oficiais para busca semântica."""

    __tablename__ = "official_document_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("official_documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    content_preview: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Preview do conteúdo
    embedding: Mapped[Vector] = mapped_column(
        Vector(768), nullable=False
    )  # Google text-embedding-004 gera 768 dimensões
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relacionamento
    document: Mapped["OfficialDocument"] = relationship(
        "OfficialDocument", back_populates="embedding"
    )

    def __repr__(self) -> str:
        """Representação string do embedding."""
        return f"<OfficialDocumentEmbedding(id={self.id}, document_id={self.document_id})>"

