#!/usr/bin/env python3
"""
Script para testar o sistema de autenticação Google OAuth
"""
import asyncio
import sys
import os
from pathlib import Path

# Adiciona o diretório app ao Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import get_db, init_db
from app.config import settings
from app.services.auth import GoogleOAuthService, AuthService
from app.models import User
from sqlalchemy import text

async def test_database_connection():
    """Testa conexão com o banco de dados"""
    print("🔍 Testando conexão com banco de dados...")
    
    try:
        # Inicializa o banco
        await init_db()
        
        # Testa query simples
        async for db in get_db():
            result = await db.execute(text("SELECT 1"))
            row = result.fetchone()
            if row and row[0] == 1:
                print("✅ Conexão com banco de dados OK")
                return True
            else:
                print("❌ Erro na query de teste")
                return False
                
    except Exception as e:
        print(f"❌ Erro na conexão com banco: {e}")
        return False

async def test_google_oauth_config():
    """Testa configuração do Google OAuth"""
    print("\n🔍 Testando configuração Google OAuth...")
    
    oauth_service = GoogleOAuthService()
    
    # Verifica se as configurações estão definidas
    if not oauth_service.client_id:
        print("❌ GOOGLE_CLIENT_ID não configurado")
        return False
    
    if not oauth_service.client_secret:
        print("❌ GOOGLE_CLIENT_SECRET não configurado")
        return False
    
    # Testa geração de URL de autorização
    try:
        auth_url = oauth_service.get_authorization_url()
        if "accounts.google.com" in auth_url:
            print("✅ URL de autorização Google gerada corretamente")
            print(f"   URL: {auth_url[:100]}...")
            return True
        else:
            print("❌ URL de autorização inválida")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao gerar URL de autorização: {e}")
        return False

async def test_user_model():
    """Testa criação de usuário"""
    print("\n🔍 Testando modelo de usuário...")
    
    try:
        async for db in get_db():
            # Verifica se tabela users existe
            result = await db.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'users'
                )
            """))
            
            exists = result.fetchone()[0]
            
            if exists:
                print("✅ Tabela 'users' existe no banco")
                
                # Testa contagem de usuários
                result = await db.execute(text("SELECT COUNT(*) FROM users"))
                count = result.fetchone()[0]
                print(f"✅ Total de usuários: {count}")
                
                return True
            else:
                print("❌ Tabela 'users' não encontrada")
                return False
                
    except Exception as e:
        print(f"❌ Erro ao testar modelo de usuário: {e}")
        return False

async def test_auth_service():
    """Testa serviço de autenticação"""
    print("\n🔍 Testando serviço de autenticação...")
    
    try:
        auth_service = AuthService()
        
        # Testa se o serviço foi criado corretamente
        if hasattr(auth_service, 'google_oauth'):
            print("✅ AuthService criado corretamente")
            
            # Testa criação de token JWT (mock)
            test_user_data = {
                "id": 1,
                "email": "test@example.com",
                "plan_type": "free"
            }
            
            # Simula um objeto User
            class MockUser:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)
            
            mock_user = MockUser(test_user_data)
            token = auth_service.google_oauth.create_jwt_token(mock_user)
            
            if token and len(token) > 0:
                print("✅ Token JWT criado corretamente")
                print(f"   Token: {token[:50]}...")
                return True
            else:
                print("❌ Erro ao criar token JWT")
                return False
                
        else:
            print("❌ AuthService não configurado corretamente")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar serviço de autenticação: {e}")
        return False

async def test_environment():
    """Testa variáveis de ambiente"""
    print("\n🔍 Testando variáveis de ambiente...")
    
    required_vars = [
        "DATABASE_URL",
        "SECRET_KEY",
        "SESSION_SECRET_KEY",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET"
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = getattr(settings, var, None)
        if not value or value in ["", "your-secret-key-here", "your-session-secret-key-here", "your-google-client-id-here", "your-google-client-secret-here"]:
            missing_vars.append(var)
        else:
            print(f"✅ {var} configurado")
    
    if missing_vars:
        print(f"❌ Variáveis não configuradas: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ Todas as variáveis obrigatórias estão configuradas")
        return True

async def main():
    """Função principal de teste"""
    print("🧪 TESTE DO SISTEMA DE AUTENTICAÇÃO OPINA")
    print("=" * 50)
    
    results = []
    
    # Testa variáveis de ambiente
    results.append(await test_environment())
    
    # Testa conexão com banco
    results.append(await test_database_connection())
    
    # Testa configuração OAuth
    results.append(await test_google_oauth_config())
    
    # Testa modelo de usuário
    results.append(await test_user_model())
    
    # Testa serviço de autenticação
    results.append(await test_auth_service())
    
    # Resultados finais
    print("\n" + "=" * 50)
    print("📊 RESULTADOS DO TESTE")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Testes aprovados: {passed}/{total}")
    print(f"❌ Testes falharam: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("👍 Sistema de autenticação está pronto para uso")
        print("\n📝 Próximos passos:")
        print("   1. Configure o Google OAuth no Google Cloud Console")
        print("   2. Execute: python -m uvicorn app.main:app --reload")
        print("   3. Acesse: http://localhost:8000")
    else:
        print("\n⚠️  ALGUNS TESTES FALHARAM")
        print("🔧 Verifique as configurações mencionadas acima")
        print("📖 Consulte o arquivo config-local.env para ajuda")

if __name__ == "__main__":
    asyncio.run(main()) 