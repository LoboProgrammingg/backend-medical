"""Entry point da aplicação FastAPI."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.database import close_db, init_db
from app.config.settings import settings
from app.utils.errors import AppError, AuthenticationError, ValidationError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Gerencia o ciclo de vida da aplicação.

    Inicializa recursos no startup e limpa no shutdown.
    """
    # Startup
    settings.create_storage_dirs()
    await init_db()
    yield
    # Shutdown
    await close_db()


def create_application() -> FastAPI:
    """Factory para criar a aplicação FastAPI."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Configurar CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Registrar rotas
    register_routes(app)

    return app


def register_routes(app: FastAPI) -> None:
    """Registra todas as rotas da aplicação."""
    
    # Importar rotas
    from app.api.routes import agents, auth, calendar, conversations, documents, gems, notes, rag, official_sources
    
    # Registrar routers
    app.include_router(auth.router)
    app.include_router(notes.router)
    app.include_router(rag.router)
    app.include_router(documents.router)
    app.include_router(agents.router)
    app.include_router(conversations.router)
    app.include_router(official_sources.router)
    app.include_router(calendar.router)
    app.include_router(gems.router)

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """
        Health check endpoint.

        Returns:
            dict: Status da aplicação.
        """
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
        }

    @app.get("/", tags=["Root"])
    async def root() -> dict:
        """
        Endpoint raiz.

        Returns:
            dict: Mensagem de boas-vindas.
        """
        return {
            "message": f"Bem-vinda ao {settings.app_name}! 💝",
            "docs": "/docs" if settings.debug else "Documentação disponível apenas em modo debug",
        }

    # Exception handlers
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Handler para erros customizados da aplicação."""
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handler global de exceções."""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Erro interno do servidor",
                "detail": str(exc) if settings.debug else None,
            },
        )


# Criar aplicação
app = create_application()
