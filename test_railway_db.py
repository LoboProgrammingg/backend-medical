#!/usr/bin/env python3
"""
Script para testar conexão com PostgreSQL no Railway.
Execute: railway run python test_railway_db.py
"""

import asyncio
import os
from sqlalchemy import text
from app.config.database import engine, get_database_url

async def test_connection():
    """Testa conexão com o banco de dados."""
    print("🔍 Testando conexão com PostgreSQL...")
    print(f"📋 DATABASE_URL: {get_database_url()[:50]}...")  # Mostrar apenas início
    
    try:
        async with engine.begin() as conn:
            # Teste 1: Versão do PostgreSQL
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ Conexão OK!")
            print(f"📦 PostgreSQL: {version.split(',')[0]}")
            
            # Teste 2: Verificar extensões
            result = await conn.execute(text("""
                SELECT extname, extversion 
                FROM pg_extension 
                WHERE extname IN ('vector', 'uuid-ossp')
            """))
            extensions = result.fetchall()
            
            if extensions:
                print("\n✅ Extensões instaladas:")
                for ext_name, ext_version in extensions:
                    print(f"   • {ext_name} (v{ext_version})")
            else:
                print("\n⚠️ Nenhuma extensão encontrada (serão criadas automaticamente)")
            
            # Teste 3: Verificar se pode criar extensões
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
                print("\n✅ Extensões criadas/verificadas com sucesso!")
            except Exception as e:
                print(f"\n⚠️ Aviso ao criar extensões: {e}")
            
            # Teste 4: Listar databases
            result = await conn.execute(text("SELECT current_database()"))
            db_name = result.scalar()
            print(f"\n📊 Database atual: {db_name}")
            
            print("\n✅ Todos os testes passaram!")
            return True
            
    except Exception as e:
        print(f"\n❌ Erro de conexão: {e}")
        print("\n🔧 Verifique:")
        print("   1. DATABASE_URL está configurada no Railway")
        print("   2. PostgreSQL está rodando")
        print("   3. Credenciais estão corretas")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    exit(0 if success else 1)

