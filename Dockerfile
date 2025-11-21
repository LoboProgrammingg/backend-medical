# ==============================================
# BACKEND DOCKERFILE - PRODUÇÃO
# ==============================================

FROM python:3.11-slim

# Definir variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry
RUN pip install poetry==1.7.1

# Copiar arquivos de dependências
COPY pyproject.toml poetry.lock ./

# Configurar Poetry e instalar dependências
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

# Copiar código da aplicação
COPY . .

# Criar diretórios necessários
RUN mkdir -p storage/temp storage/documents storage/exports

# Expor porta (Railway usa variável $PORT)
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8001}/health || exit 1

# Comando para iniciar a aplicação (Railway define $PORT)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}

