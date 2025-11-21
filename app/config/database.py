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
    1. DATABASE_PUBLIC_URL (se disponível, para acesso externo)
    2. DATABASE_URL (URL interna do Railway)
    3. settings.database_url (fallback)
    """
    import os
    
    # Railway fornece DATABASE_PUBLIC_URL para acesso externo
    # e DATABASE_URL para acesso interno
    # Preferimos DATABASE_PUBLIC_URL se disponível
    db_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL") or settings.database_url
    
    # Se for do Railway (postgresql://), converter para asyncpg
    if db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
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
