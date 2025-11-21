"""Configuração do banco de dados PostgreSQL com SQLAlchemy."""

from typing import AsyncGenerator
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .settings import settings


def get_database_url() -> str:
    """
    Obtém a URL do banco de dados, convertendo se necessário.
    
    Railway fornece DATABASE_URL no formato postgresql://
    mas precisamos postgresql+asyncpg:// para asyncpg.
    
    Prioridade:
    1. DATABASE_URL (URL privada do Railway - SEM custos de egress)
    2. DATABASE_PUBLIC_URL (URL pública - pode gerar custos)
    3. settings.database_url (fallback)
    
    NOTA: Preferimos DATABASE_URL (privada) para evitar custos de egress.
    """
    import os
    
    # Debug: verificar todas as variáveis de ambiente relacionadas
    print("🔍 Verificando variáveis de ambiente...")
    
    # Listar TODAS as variáveis de ambiente que contêm "DATABASE" ou "POSTGRES"
    all_env_vars = {k: v for k, v in os.environ.items() if "DATABASE" in k.upper() or "POSTGRES" in k.upper()}
    print(f"   📋 Variáveis relacionadas encontradas: {len(all_env_vars)}")
    for key, value in all_env_vars.items():
        print(f"      {key}: {value[:60]}...")
    
    db_url_env = os.getenv("DATABASE_URL")
    db_public_url_env = os.getenv("DATABASE_PUBLIC_URL")
    
    # Tentar também variáveis alternativas do Railway
    railway_db_url = os.getenv("RAILWAY_DATABASE_URL") or os.getenv("POSTGRES_URL")
    
    print(f"   DATABASE_URL presente: {'✅ SIM' if db_url_env else '❌ NÃO'}")
    if db_url_env:
        print(f"   DATABASE_URL valor: {db_url_env[:60]}...")
    
    print(f"   DATABASE_PUBLIC_URL presente: {'✅ SIM' if db_public_url_env else '❌ NÃO'}")
    if db_public_url_env:
        print(f"   DATABASE_PUBLIC_URL valor: {db_public_url_env[:60]}...")
    
    if railway_db_url:
        print(f"   ⚠️ RAILWAY_DATABASE_URL ou POSTGRES_URL encontrada: {railway_db_url[:60]}...")
    
    # Railway fornece DATABASE_URL (privada, sem custos) e DATABASE_PUBLIC_URL (pública, com custos)
    # Preferimos DATABASE_URL (privada) para evitar custos de egress
    # Também tentamos variáveis alternativas do Railway
    db_url = db_url_env or db_public_url_env or railway_db_url
    
    # Se não encontrou nas variáveis de ambiente, usar settings
    if not db_url:
        db_url = settings.database_url
        print("⚠️ Usando DATABASE_URL do settings (variável de ambiente não encontrada)")
        print("💡 Verifique se DATABASE_URL está configurada no Railway (Backend → Variables)")
    else:
        if db_url_env:
            print("✅ DATABASE_URL (privada) encontrada - sem custos de egress")
        else:
            print("⚠️ Usando DATABASE_PUBLIC_URL (pública) - pode gerar custos de egress")
            print("💡 Considere usar DATABASE_URL (privada) para evitar custos")
    
    # Se for do Railway (postgresql://), converter para asyncpg
    if db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        print("✅ URL convertida para asyncpg")
    
    return db_url


# Engine assíncrono do SQLAlchemy
engine = create_async_engine(
    get_database_url(),
    echo=settings.debug,
    future=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory assíncrona
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Classe base para todos os models SQLAlchemy."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para obter sessão do banco de dados.

    Yields:
        AsyncSession: Sessão do banco de dados.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Inicializa o banco de dados criando todas as tabelas e extensões."""
    from sqlalchemy import text
    
    db_url = get_database_url()
    print(f"🔍 Tentando conectar ao banco...")
    print(f"📋 DATABASE_URL: {db_url[:60]}...")  # Mostrar início da URL (sem senha)
    
    # Verificar conexão primeiro
    try:
        async with engine.begin() as conn:
            # Testar conexão
            result = await conn.execute(text("SELECT 1"))
            print("✅ Conexão com banco de dados estabelecida")
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Erro ao conectar ao banco: {error_msg}")
        
        # Verificar se é problema de URL
        if "postgresql" not in db_url.lower():
            print("⚠️ DATABASE_URL não parece ser uma URL PostgreSQL válida")
        
        # Verificar se é problema de conexão
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            print("⚠️ Verifique se o PostgreSQL está rodando e acessível")
        
        raise
    
    # Criar extensões e tabelas
    try:
        async with engine.begin() as conn:
            # Criar extensões necessárias
            try:
                await conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
                await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
                print("✅ Extensões PostgreSQL criadas")
            except Exception as e:
                ext_error = str(e)
                if "does not exist" in ext_error.lower():
                    print(f"⚠️ Extensão não disponível (pgvector pode não estar instalado): {ext_error}")
                else:
                    print(f"⚠️ Aviso ao criar extensões: {ext_error}")
            
            # Criar tabelas
            await conn.run_sync(Base.metadata.create_all)
            print("✅ Tabelas criadas")
    except Exception as e:
        print(f"❌ Erro ao inicializar banco: {e}")
        raise


async def close_db() -> None:
    """Fecha as conexões do banco de dados."""
    await engine.dispose()
