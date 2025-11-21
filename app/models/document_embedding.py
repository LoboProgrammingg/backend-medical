"""Model de embedding de documento."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base


class DocumentEmbedding(Base):
    """Model de embedding de documento PDF."""

    __tablename__ = "document_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    content_preview: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Primeiros 500 caracteres para referência
    embedding: Mapped[list[float]] = mapped_column(
        Vector(768), nullable=False
    )  # Dimensão do text-embedding-004
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relacionamentos
    document: Mapped["Document"] = relationship(
        "Document", back_populates="embedding"
    )

    def __repr__(self) -> str:
        """Representação string do embedding."""
        return f"<DocumentEmbedding(id={self.id}, document_id={self.document_id})>"

