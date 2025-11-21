"""Schemas para Calendário."""

from datetime import date, time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CalendarEventCreate(BaseModel):
    """Schema para criar evento de calendário."""

    event_type: str = Field(..., description="Tipo: 'work' ou 'on_call'")
    event_date: date
    day_of_week: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = None
    shift_type: Optional[str] = None
    notes: Optional[str] = None
    preceptor: Optional[str] = None
    week_number: Optional[int] = None


class CalendarCreate(BaseModel):
    """Schema para criar calendário."""

    title: str
    description: Optional[str] = None
    group_number: Optional[int] = None
    name_in_calendar: Optional[str] = None
    position_in_list: Optional[str] = None
    start_date: date
    end_date: date
    source_file: Optional[str] = None
    events: List[CalendarEventCreate] = []


class CalendarEventResponse(BaseModel):
    """Schema de resposta de evento."""

    id: UUID
    event_type: str
    event_date: date
    day_of_week: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = None
    shift_type: Optional[str] = None
    notes: Optional[str] = None
    preceptor: Optional[str] = None
    week_number: Optional[int] = None

    class Config:
        from_attributes = True


class CalendarResponse(BaseModel):
    """Schema de resposta de calendário."""

    id: UUID
    title: str
    description: Optional[str] = None
    group_number: Optional[int] = None
    name_in_calendar: Optional[str] = None
    position_in_list: Optional[str] = None
    start_date: date
    end_date: date
    source_file: Optional[str] = None
    events: List[CalendarEventResponse] = []
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CalendarUploadRequest(BaseModel):
    """Schema para upload de calendário PDF."""

    group_number: int = Field(..., description="Número do grupo (ex: 7)")
    name: str = Field(..., description="Nome completo (ex: Tatiana Minakami)")
    position: str = Field(..., description="Posição na lista (ex: A1)")
    title: Optional[str] = Field(None, description="Título do calendário (opcional)")


class CalendarListResponse(BaseModel):
    """Schema de resposta de lista de calendários."""

    calendars: List[CalendarResponse]
    total: int

