"""Rotas para Calendário e Plantões."""

from datetime import date, datetime, time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, Form, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.calendar_organizer import CalendarOrganizerAgent
from app.config.database import get_db
from app.core.dependencies import get_current_user
from app.models.calendar import Calendar, CalendarEvent
from app.models.user import User
from app.schemas.calendar import (
    CalendarCreate,
    CalendarResponse,
    CalendarListResponse,
    CalendarUploadRequest,
    CalendarEventResponse,
    CalendarEventCreate,
)
from app.utils.pdf_processor import PDFProcessor
from pathlib import Path
import tempfile

router = APIRouter(prefix="/calendar", tags=["Calendário"])


@router.post(
    "/upload",
    response_model=CalendarResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload e processamento de calendário PDF",
    description="Faz upload de um PDF de calendário e extrai os dados com precisão.",
)
async def upload_calendar(
    file: UploadFile = File(...),
    group_number: int = Form(...),
    name: str = Form(...),
    position: str = Form(...),
    title: str = Form(None),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> CalendarResponse:
    """
    Faz upload de um PDF ou Excel de calendário e extrai dados com precisão.
    
    Args:
        file: Arquivo PDF ou Excel (.xlsx, .xls) do calendário
        group_number: Número do grupo (ex: 7)
        name: Nome completo (ex: Tatiana Minakami)
        position: Posição na lista (ex: A1)
        title: Título do calendário (opcional)
        current_user: Usuário autenticado
        db: Sessão do banco
    
    Returns:
        CalendarResponse com calendário criado e eventos extraídos
    """
    print(f"[CALENDAR-UPLOAD] Iniciando upload: {file.filename}")
    print(f"[CALENDAR-UPLOAD] Grupo: {group_number}, Nome: {name}, Posição: {position}")
    
    # Validar tipo de arquivo (PDF ou Excel)
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in [".pdf", ".xlsx", ".xls"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apenas arquivos PDF ou Excel (.xlsx, .xls) são permitidos"
        )
    
    # Salvar arquivo temporariamente
    temp_dir = Path("./storage/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = temp_dir / file.filename
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        print(f"[CALENDAR-UPLOAD] Arquivo salvo. Extraindo texto...")
        
        # Extrair texto do arquivo (PDF ou Excel)
        print(f"[CALENDAR-UPLOAD] Iniciando extração de texto do arquivo ({file_ext})...")
        import asyncio
        loop = asyncio.get_event_loop()
        
        try:
            if file_ext == ".pdf":
                # Usar extração ESTRUTURADA para calendários PDF (melhor para tabelas)
                calendar_text = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, 
                        PDFProcessor.extract_structured_calendar_text, 
                        file_path
                    ),
                    timeout=60.0  # 60 segundos para extrair PDF estruturado
                )
                print(f"[CALENDAR-UPLOAD] ✅ Texto estruturado (PDF) extraído: {len(calendar_text)} caracteres")
            elif file_ext in [".xlsx", ".xls"]:
                # Usar extração ESTRUTURADA para calendários Excel
                calendar_text = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, 
                        PDFProcessor.extract_structured_calendar_from_excel, 
                        file_path
                    ),
                    timeout=60.0  # 60 segundos para extrair Excel estruturado
                )
                print(f"[CALENDAR-UPLOAD] ✅ Texto estruturado (Excel) extraído: {len(calendar_text)} caracteres")
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Formato de arquivo não suportado: {file_ext}"
                )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="Timeout ao extrair texto do arquivo. O arquivo pode estar muito grande ou corrompido."
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        if not calendar_text or len(calendar_text) < 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não foi possível extrair texto suficiente do arquivo. Verifique se o arquivo está correto."
            )
        
        # Usar CalendarOrganizerAgent para extrair dados
        print(f"[CALENDAR-UPLOAD] Iniciando extração de dados com IA...")
        agent = CalendarOrganizerAgent()
        
        try:
            calendar_data = await asyncio.wait_for(
                agent.extract_calendar_from_pdf(
                    pdf_text=calendar_text,
                    group_number=group_number,
                    name=name,
                    position=position,
                ),
                timeout=220.0  # 180 segundos (3 minutos) para processar com IA
            )
            print(f"[CALENDAR-UPLOAD] ✅ Dados extraídos pela IA")
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="Timeout ao processar calendário com IA. O arquivo pode estar muito grande. Tente novamente ou use um arquivo menor."
            )
        except Exception as e:
            print(f"[CALENDAR-UPLOAD] ❌ Erro na extração: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao processar calendário com IA: {str(e)}"
            )
        
        print(f"[CALENDAR-UPLOAD] Dados extraídos: {len(calendar_data.get('work_days', []))} dias de trabalho, {len(calendar_data.get('on_call_shifts', []))} plantões")
        
        # Criar calendário no banco
        calendar_title = title or f"Calendário {name} - Grupo {group_number}"
        calendar = Calendar(
            user_id=current_user.id,
            title=calendar_title,
            group_number=calendar_data.get("group_number", group_number),
            name_in_calendar=calendar_data.get("name", name),
            position_in_list=calendar_data.get("position", position),
            start_date=datetime.strptime(calendar_data["start_date"], "%Y-%m-%d").date(),
            end_date=datetime.strptime(calendar_data["end_date"], "%Y-%m-%d").date(),
            source_file=file.filename,
        )
        db.add(calendar)
        await db.flush()  # Para obter o ID
        
        # Função auxiliar para converter DD/MM para YYYY-MM-DD e validar dia da semana
        def parse_date_with_year(date_str: str, day_of_week: str, calendar_start: date, calendar_end: date) -> date:
            """Converte DD/MM para YYYY-MM-DD validando o dia da semana."""
            from datetime import timedelta
            
            try:
                # Tentar primeiro como DD/MM
                day, month = map(int, date_str.split("/"))
                
                # Mapear dias da semana
                day_map = {
                    'Seg': 0, 'Segunda': 0,
                    'Ter': 1, 'Terça': 1,
                    'Qua': 2, 'Quarta': 2,
                    'Qui': 3, 'Quinta': 3,
                    'Sex': 4, 'Sexta': 4,
                    'Sáb': 5, 'Sábado': 5,
                    'Dom': 6, 'Domingo': 6,
                }
                
                expected_weekday = day_map.get(day_of_week) if day_of_week else None
                
                # Tentar com o ano do período do calendário
                year = calendar_start.year
                event_date = date(year, month, day)
                
                # Se a data estiver antes do início, pode ser do próximo ano
                if event_date < calendar_start:
                    event_date = date(year + 1, month, day)
                
                # Se a data estiver depois do fim, pode ser do ano anterior
                if event_date > calendar_end:
                    event_date = date(year - 1, month, day)
                
                # Validar dia da semana se fornecido
                if expected_weekday is not None:
                    actual_weekday = event_date.weekday()
                    if actual_weekday != expected_weekday:
                        # Ajustar a data para corresponder ao dia da semana correto
                        days_diff = expected_weekday - actual_weekday
                        # Se a diferença for grande, pode ser que esteja no mês/ano errado
                        if abs(days_diff) > 3:
                            # Tentar ajustar para o próximo período de 7 dias
                            if days_diff < 0:
                                days_diff += 7
                            event_date += timedelta(days=days_diff)
                        else:
                            event_date += timedelta(days=days_diff)
                        
                        # Verificar se ainda está no período
                        if event_date < calendar_start or event_date > calendar_end:
                            # Se não estiver, tentar o próximo mês
                            if month == 12:
                                event_date = date(year + 1, 1, day)
                            else:
                                event_date = date(year, month + 1, day)
                        
                        print(f"✅ [CALENDAR] Ajustada data {date_str} de {actual_weekday} para {expected_weekday}: {event_date}")
                
                # Validar que a data está dentro do período do calendário
                if event_date < calendar_start or event_date > calendar_end:
                    print(f"⚠️ [CALENDAR] Data {event_date} ainda fora do período {calendar_start} - {calendar_end}")
                
                return event_date
            except (ValueError, AttributeError) as e:
                # Se falhar, tentar como YYYY-MM-DD (compatibilidade)
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    raise ValueError(f"Formato de data inválido: {date_str} - {str(e)}")
        
        # Criar eventos em batch (muito mais rápido)
        events_to_add = []
        
        # Processar dias de trabalho
        for work_day in calendar_data.get("work_days", []):
            event_date = parse_date_with_year(
                work_day["date"], 
                work_day.get("day_of_week"),
                calendar.start_date, 
                calendar.end_date
            )
            start_time_obj = None
            end_time_obj = None
            
            if work_day.get("start_time"):
                start_time_obj = datetime.strptime(work_day["start_time"], "%H:%M").time()
            if work_day.get("end_time"):
                end_time_obj = datetime.strptime(work_day["end_time"], "%H:%M").time()
            
            events_to_add.append(CalendarEvent(
                calendar_id=calendar.id,
                event_type="work",
                event_date=event_date,
                day_of_week=work_day.get("day_of_week"),
                start_time=start_time_obj,
                end_time=end_time_obj,
                location=work_day.get("location"),
                shift_type=work_day.get("shift_type"),
                preceptor=work_day.get("preceptor"),
                week_number=work_day.get("week"),
            ))
        
        # Processar plantões
        for shift in calendar_data.get("on_call_shifts", []):
            event_date = parse_date_with_year(
                shift["date"],
                shift.get("day_of_week"),
                calendar.start_date,
                calendar.end_date
            )
            start_time_obj = None
            end_time_obj = None
            
            if shift.get("start_time"):
                start_time_obj = datetime.strptime(shift["start_time"], "%H:%M").time()
            if shift.get("end_time"):
                end_time_obj = datetime.strptime(shift["end_time"], "%H:%M").time()
            
            events_to_add.append(CalendarEvent(
                calendar_id=calendar.id,
                event_type="on_call",
                event_date=event_date,
                day_of_week=shift.get("day_of_week"),
                start_time=start_time_obj,
                end_time=end_time_obj,
                location=shift.get("location"),
                shift_type=shift.get("shift_type"),
                preceptor=shift.get("preceptor"),
                week_number=shift.get("week"),
            ))
        
        # Adicionar todos os eventos de uma vez (batch insert)
        db.add_all(events_to_add)
        await db.commit()
        await db.refresh(calendar)
        
        # Eventos já foram adicionados, recarregar com relacionamento
        from sqlalchemy.orm import selectinload
        await db.refresh(calendar, ["events"])
        events = calendar.events
        
        print(f"[CALENDAR-UPLOAD] ✅ Calendário criado: {calendar.id} com {len(events)} eventos")
        
        return CalendarResponse(
            id=calendar.id,
            title=calendar.title,
            description=calendar.description,
            group_number=calendar.group_number,
            name_in_calendar=calendar.name_in_calendar,
            position_in_list=calendar.position_in_list,
            start_date=calendar.start_date,
            end_date=calendar.end_date,
            source_file=calendar.source_file,
            events=[
                CalendarEventResponse(
                    id=e.id,
                    event_type=e.event_type,
                    event_date=e.event_date,
                    day_of_week=e.day_of_week,
                    start_time=e.start_time,
                    end_time=e.end_time,
                    location=e.location,
                    shift_type=e.shift_type,
                    notes=e.notes,
                    preceptor=e.preceptor,
                    week_number=e.week_number,
                )
                for e in events
            ],
            created_at=calendar.created_at.isoformat(),
            updated_at=calendar.updated_at.isoformat(),
        )
        
    except Exception as e:
        print(f"[CALENDAR-UPLOAD] ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar calendário: {str(e)}"
        )
    finally:
        # Remover arquivo temporário
        if file_path.exists():
            file_path.unlink()


@router.get(
    "/",
    response_model=CalendarListResponse,
    summary="Listar calendários",
    description="Lista todos os calendários do usuário.",
)
async def list_calendars(
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> CalendarListResponse:
    """Lista todos os calendários do usuário."""
    from sqlalchemy.orm import selectinload
    
    # Usar selectinload para evitar N+1 queries (carrega todos os eventos de uma vez)
    query = (
        select(Calendar)
        .where(Calendar.user_id == current_user.id)
        .order_by(Calendar.created_at.desc())
        .options(selectinload(Calendar.events))
    )
    result = await db.execute(query)
    calendars = result.scalars().unique().all()
    
    # Agora os eventos já estão carregados (sem queries adicionais)
    calendar_responses = []
    for calendar in calendars:
        events = calendar.events  # Já carregado pelo selectinload
        
        calendar_responses.append(
            CalendarResponse(
                id=calendar.id,
                title=calendar.title,
                description=calendar.description,
                group_number=calendar.group_number,
                name_in_calendar=calendar.name_in_calendar,
                position_in_list=calendar.position_in_list,
                start_date=calendar.start_date,
                end_date=calendar.end_date,
                source_file=calendar.source_file,
                events=[
                    CalendarEventResponse(
                        id=e.id,
                        event_type=e.event_type,
                        event_date=e.event_date,
                        day_of_week=e.day_of_week,
                        start_time=e.start_time,
                        end_time=e.end_time,
                        location=e.location,
                        shift_type=e.shift_type,
                        notes=e.notes,
                        preceptor=e.preceptor,
                        week_number=e.week_number,
                    )
                    for e in events
                ],
                created_at=calendar.created_at.isoformat(),
                updated_at=calendar.updated_at.isoformat(),
            )
        )
    
    return CalendarListResponse(calendars=calendar_responses, total=len(calendar_responses))


@router.get(
    "/{calendar_id}",
    response_model=CalendarResponse,
    summary="Obter calendário",
    description="Obtém um calendário específico com todos os eventos.",
)
async def get_calendar(
    calendar_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> CalendarResponse:
    """Obtém um calendário específico."""
    from sqlalchemy.orm import selectinload
    
    # Usar selectinload para carregar eventos junto (evita query extra)
    query = (
        select(Calendar)
        .where(
            Calendar.id == calendar_id,
            Calendar.user_id == current_user.id,
        )
        .options(selectinload(Calendar.events))
    )
    result = await db.execute(query)
    calendar = result.scalar_one_or_none()
    
    if not calendar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendário não encontrado"
        )
    
    # Eventos já estão carregados
    events = calendar.events
    
    return CalendarResponse(
        id=calendar.id,
        title=calendar.title,
        description=calendar.description,
        group_number=calendar.group_number,
        name_in_calendar=calendar.name_in_calendar,
        position_in_list=calendar.position_in_list,
        start_date=calendar.start_date,
        end_date=calendar.end_date,
        source_file=calendar.source_file,
        events=[
            CalendarEventResponse(
                id=e.id,
                event_type=e.event_type,
                event_date=e.event_date,
                day_of_week=e.day_of_week,
                start_time=e.start_time,
                end_time=e.end_time,
                location=e.location,
                shift_type=e.shift_type,
                notes=e.notes,
                preceptor=e.preceptor,
                week_number=e.week_number,
            )
            for e in events
        ],
        created_at=calendar.created_at.isoformat(),
        updated_at=calendar.updated_at.isoformat(),
    )


@router.post(
    "/{calendar_id}/events",
    response_model=CalendarEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar evento personalizado",
    description="Adiciona um evento personalizado ao calendário.",
)
async def create_event(
    calendar_id: UUID,
    event_data: CalendarEventCreate,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> CalendarEventResponse:
    """Cria um evento personalizado no calendário."""
    # Verificar se o calendário existe e pertence ao usuário
    query = select(Calendar).where(
        Calendar.id == calendar_id,
        Calendar.user_id == current_user.id,
    )
    result = await db.execute(query)
    calendar = result.scalar_one_or_none()
    
    if not calendar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendário não encontrado"
        )
    
    # Verificar se a data está dentro do período do calendário
    if event_data.event_date < calendar.start_date or event_data.event_date > calendar.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A data do evento deve estar entre {calendar.start_date} e {calendar.end_date}"
        )
    
    # Criar evento
    event = CalendarEvent(
        calendar_id=calendar.id,
        event_type=event_data.event_type,
        event_date=event_data.event_date,
        day_of_week=event_data.day_of_week,
        start_time=event_data.start_time,
        end_time=event_data.end_time,
        location=event_data.location,
        shift_type=event_data.shift_type,
        notes=event_data.notes,
        preceptor=event_data.preceptor,
        week_number=event_data.week_number,
    )
    
    db.add(event)
    await db.commit()
    await db.refresh(event)
    
    return CalendarEventResponse(
        id=event.id,
        event_type=event.event_type,
        event_date=event.event_date,
        day_of_week=event.day_of_week,
        start_time=event.start_time,
        end_time=event.end_time,
        location=event.location,
        shift_type=event.shift_type,
        notes=event.notes,
        preceptor=event.preceptor,
        week_number=event.week_number,
    )


@router.delete(
    "/{calendar_id}",
    status_code=status.HTTP_200_OK,
    summary="Deletar calendário",
    description="Deleta um calendário e todos os seus eventos.",
)
async def delete_calendar(
    calendar_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Deleta um calendário."""
    query = select(Calendar).where(
        Calendar.id == calendar_id,
        Calendar.user_id == current_user.id,
    )
    result = await db.execute(query)
    calendar = result.scalar_one_or_none()
    
    if not calendar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendário não encontrado"
        )
    
    await db.delete(calendar)
    await db.commit()
    
    return {"message": "Calendário deletado com sucesso"}

