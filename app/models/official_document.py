"""Modelo para documentos oficiais (PCDT, Sociedades Médicas)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base


class OfficialDocument(Base):
    """Documentos oficiais para RAG (PCDT, SBC, SBOC, AMIB, SBP)."""

    __tablename__ = "official_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'pcdt', 'sbc', 'sboc', 'amib', 'sbp'
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    priority: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )  # 1 = mais alta
    specialty: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )  # 'cardiologia', 'pediatria', etc.
    last_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relacionamento
    embedding: Mapped["OfficialDocumentEmbedding"] = relationship(
        "OfficialDocumentEmbedding",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Representação string do documento oficial."""
        return f"<OfficialDocument(id={self.id}, source='{self.source}', title='{self.title}')>"

