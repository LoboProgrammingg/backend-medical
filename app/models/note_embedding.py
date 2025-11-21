"""Model de embedding de anotação."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base


class NoteEmbedding(Base):
    """Model de embedding vetorial de anotação para RAG."""

    __tablename__ = "note_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    embedding: Mapped[Vector] = mapped_column(
        Vector(768),  # text-embedding-004 gera vetores de 768 dimensões
        nullable=False,
    )
    embedding_model: Mapped[str] = mapped_column(
        nullable=False,
        default="models/text-embedding-004",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relacionamento
    note: Mapped["Note"] = relationship("Note", back_populates="embedding")

    def __repr__(self) -> str:
        """Representação string do embedding."""
        return f"<NoteEmbedding(id={self.id}, note_id={self.note_id})>"

