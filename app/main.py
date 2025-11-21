"""Entry point da aplicação FastAPI."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.database import close_db, init_db
from app.config.settings import settings
from app.utils.errors import AppError, AuthenticationError, ValidationError


# Flag global para indicar se a aplicação está pronta
_app_ready = False

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Gerencia o ciclo de vida da aplicação.

    Inicializa recursos no startup e limpa no shutdown.
    """
    global _app_ready
    _app_ready = False
    
    # Startup
    settings.create_storage_dirs()
    
    # Tentar inicializar banco com retry
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            await init_db()
            print("✅ Banco de dados inicializado com sucesso")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Erro ao inicializar banco (tentativa {attempt + 1}/{max_retries}): {e}")
                print(f"🔄 Tentando novamente em {retry_delay} segundos...")
                import asyncio
                await asyncio.sleep(retry_delay)
            else:
                print(f"❌ Erro ao inicializar banco após {max_retries} tentativas: {e}")
                print("⚠️ Aplicação continuará sem inicializar banco (pode causar erros)")
    
    # Marcar aplicação como pronta
    _app_ready = True
    import os
    port = os.getenv("PORT", "8001")
    print(f"✅ Aplicação pronta para receber requisições na porta {port}")
    print(f"✅ Health check disponível em: http://0.0.0.0:{port}/health")
    print(f"✅ Root endpoint disponível em: http://0.0.0.0:{port}/")
    
    yield
    # Shutdown
    _app_ready = False
    await close_db()


def create_application() -> FastAPI:
    """Factory para criar a aplicação FastAPI."""
    # Habilitar docs sempre (útil para documentação da API)
    # Em produção, pode ser desabilitado definindo ENABLE_DOCS=false
    import os
    enable_docs = os.getenv("ENABLE_DOCS", "true").lower() == "true"
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
    )

    # Middleware de logging para debug
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Middleware para logar todas as requisições."""
        print(f"🌐 [MIDDLEWARE] {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}")
        response = await call_next(request)
        print(f"✅ [MIDDLEWARE] {request.method} {request.url.path} - Status: {response.status_code}")
        return response

    # Configurar CORS
    allowed_origins = settings.allowed_origins_list
    print(f"🌐 [CORS] Origens permitidas: {allowed_origins}")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Registrar rotas
    register_routes(app)

    return app


def register_routes(app: FastAPI) -> None:
    """Registra todas as rotas da aplicação."""
    
    # IMPORTANTE: Registrar endpoints raiz ANTES dos routers
    # para garantir que sejam encontrados primeiro
    
    @app.get("/", tags=["Root"])
    async def root() -> dict:
        """
        Endpoint raiz da aplicação.
        
        Retorna status 200 quando a aplicação está pronta, 503 se ainda estiver iniciando.
        """
        global _app_ready
        print(f"🔍 [ROOT] Endpoint '/' chamado - _app_ready: {_app_ready}")
        
        if not _app_ready:
            print("⚠️ [ROOT] Retornando 503 - app ainda iniciando")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "starting",
                    "message": "Aplicação ainda está iniciando"
                }
            )
        
        print("✅ [ROOT] Retornando 200 - app pronta")
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
            "message": "Backend Amorinha está funcionando!"
        }

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """
        Health check endpoint para Railway.
        
        Retorna status 200 quando a aplicação está pronta, 503 se ainda estiver iniciando.

        Returns:
            dict ou JSONResponse: Status da aplicação.
        """
        global _app_ready
        print(f"🔍 [HEALTH] Endpoint '/health' chamado - _app_ready: {_app_ready}")
        
        if not _app_ready:
            print("⚠️ [HEALTH] Retornando 503 - app ainda iniciando")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "starting",
                    "message": "Aplicação ainda está iniciando"
                }
            )
        
        print("✅ [HEALTH] Retornando 200 - app pronta")
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
        }
    
    # Importar rotas
    from app.api.routes import agents, auth, calendar, conversations, documents, gems, notes, rag, official_sources
    
    # Registrar routers (depois dos endpoints raiz)
    app.include_router(auth.router)
    app.include_router(notes.router)
    app.include_router(rag.router)
    app.include_router(documents.router)
    app.include_router(agents.router)
    app.include_router(conversations.router)
    app.include_router(official_sources.router)
    app.include_router(calendar.router)
    app.include_router(gems.router)
    
    print("✅ Todas as rotas registradas")

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
