# 💝 Amorinha Backend

Sistema de auxílio médico com IA para estudantes de medicina.

## 🚀 Stack Tecnológico

- **FastAPI** - Framework web assíncrono
- **PostgreSQL** - Banco de dados relacional
- **pgvector** - Extensão para embeddings vetoriais
- **LangGraph** - Orquestração de agentes de IA
- **Gemini 2.5 Flash** - Modelo de linguagem
- **SQLAlchemy** - ORM assíncrono
- **Poetry** - Gerenciamento de dependências

## 📋 Pré-requisitos

- Python 3.11+
- Poetry
- Docker e Docker Compose
- PostgreSQL 15+ (via Docker)

## ⚙️ Setup Local

### 1. Instalar dependências

```bash
poetry install
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

### 3. Iniciar banco de dados

```bash
docker-compose up -d
```

### 4. Executar migrações

```bash
poetry run alembic upgrade head
```

### 5. Iniciar servidor de desenvolvimento

```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 Documentação da API

Acesse http://localhost:8000/docs para a documentação interativa (Swagger UI).

## 🧪 Testes

```bash
poetry run pytest
```

## 📁 Estrutura do Projeto

```
backend/
├── app/
│   ├── main.py              # Entry point
│   ├── config/              # Configurações
│   ├── core/                # Auth, security, dependencies
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── api/                 # Rotas da API
│   ├── services/            # Lógica de negócio
│   ├── agents/              # Agentes LangGraph
│   ├── rag/                 # Sistema RAG
│   └── utils/               # Utilitários
├── alembic/                 # Migrações de banco
├── tests/                   # Testes
└── storage/                 # Arquivos uploadados
```

## 🔒 Segurança

- Senhas hasheadas com bcrypt
- Autenticação JWT
- Validação de entrada com Pydantic
- CORS configurado
- Rate limiting

## 📝 Convenções de Código

- Formatação: Black
- Linting: Ruff
- Type hints obrigatórios
- Docstrings em todas as funções públicas
- Async/await para operações I/O

---

Desenvolvido com ❤️

