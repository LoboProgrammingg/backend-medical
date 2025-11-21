"""Modelo de Gem (IA Especializada)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Gem(Base):
    """Modelo de Gem - IA especializada para conteúdo médico específico."""

    __tablename__ = "gems"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Informações básicas
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Instruções personalizadas para a IA
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relacionamentos
    user: Mapped["User"] = relationship("User", back_populates="gems")
    documents: Mapped[list["GemDocument"]] = relationship(
        "GemDocument", back_populates="gem", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Representação string."""
        return f"<Gem(id={self.id}, name={self.name})>"


class GemDocument(Base):
    """Modelo de documento PDF associado a uma Gem."""

    __tablename__ = "gem_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    gem_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("gems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Informações do arquivo
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)  # em bytes
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relacionamentos
    gem: Mapped["Gem"] = relationship("Gem", back_populates="documents")
    embedding: Mapped["GemDocumentEmbedding"] = relationship(
        "GemDocumentEmbedding",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Representação string."""
        return f"<GemDocument(id={self.id}, filename={self.filename})>"


class GemDocumentEmbedding(Base):
    """Modelo de embedding vetorial de documento da Gem para RAG."""

    __tablename__ = "gem_document_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("gem_documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Embedding vetorial (pgvector)
    embedding: Mapped[Vector] = mapped_column(
        Vector(768),  # text-embedding-004 gera vetores de 768 dimensões
        nullable=False,
    )
    embedding_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="models/text-embedding-004"
    )
    
    # Texto do documento (chunk)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)  # Índice do chunk no documento
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relacionamento
    document: Mapped["GemDocument"] = relationship(
        "GemDocument", back_populates="embedding"
    )

    def __repr__(self) -> str:
        """Representação string."""
        return f"<GemDocumentEmbedding(id={self.id}, document_id={self.document_id})>"

