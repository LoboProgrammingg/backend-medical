#!/bin/bash
# Script de inicialização para Railway
# Este script é executado automaticamente após o deploy

set -e

echo "🚀 Inicializando banco de dados no Railway..."

# Converter DATABASE_URL do Railway (postgresql://) para asyncpg (postgresql+asyncpg://)
if [ -n "$DATABASE_URL" ]; then
    # Railway fornece postgresql://, mas precisamos postgresql+asyncpg://
    if [[ "$DATABASE_URL" == postgresql://* ]]; then
        export DATABASE_URL="${DATABASE_URL/postgresql:\/\//postgresql+asyncpg:\/\/}"
        echo "✅ DATABASE_URL convertida para asyncpg"
    fi
fi

# Executar migrações
echo "📦 Executando migrações do banco de dados..."
alembic upgrade head

# Criar extensões necessárias (se não existirem)
echo "🔧 Criando extensões PostgreSQL..."
python -c "
import asyncio
from sqlalchemy import text
from app.config.database import engine

async def create_extensions():
    async with engine.begin() as conn:
        # Criar extensão pgvector
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        # Criar extensão uuid-ossp
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"'))
        print('✅ Extensões criadas com sucesso')

asyncio.run(create_extensions())
"

echo "✅ Inicialização concluída!"

