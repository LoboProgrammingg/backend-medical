"""Modelo de Calendário e Eventos."""

from datetime import date, datetime, time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Time, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Calendar(Base):
    """Modelo de calendário do usuário."""

    __tablename__ = "calendars"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Informações do usuário no calendário
    group_number: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Ex: 7
    name_in_calendar: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Ex: Tatiana Minakami
    position_in_list: Mapped[str | None] = mapped_column(String(10), nullable=True)  # Ex: A1
    
    # Período do calendário
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Metadata
    source_file: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Nome do PDF original
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="calendars")
    events: Mapped[list["CalendarEvent"]] = relationship(
        "CalendarEvent", back_populates="calendar", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Representação string."""
        return f"<Calendar {self.title} ({self.start_date} - {self.end_date})>"


class CalendarEvent(Base):
    """Modelo de evento do calendário (trabalho normal ou plantão)."""

    __tablename__ = "calendar_events"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    calendar_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("calendars.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Tipo de evento
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'work' (trabalho normal) ou 'on_call' (plantão)
    
    # Data e horário
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_of_week: Mapped[str | None] = mapped_column(String(10), nullable=True)  # Seg, Ter, Qua, etc.
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    
    # Detalhes
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Ex: UPA1, UPA2
    shift_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Ex: Sala Vermelha, Global, Plantão Cinderela, Plantão Diurno
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    preceptor: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Preceptor responsável da semana
    
    # Semana de referência (opcional)
    week_number: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Semana 1, 2, 3, etc.
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    calendar: Mapped["Calendar"] = relationship("Calendar", back_populates="events")

    def __repr__(self) -> str:
        """Representação string."""
        return f"<CalendarEvent {self.event_type} on {self.event_date}>"

