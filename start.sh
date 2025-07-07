#!/bin/bash

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Iniciando setup do Opina...${NC}\n"

# Verifica se Python 3.11 está instalado
if ! command -v python3.11 &> /dev/null; then
    echo -e "${RED}❌ Python 3.11 não encontrado. Por favor, instale o Python 3.11${NC}"
    exit 1
fi

# Verifica se estamos no diretório correto (deve ter app/ e requirements.txt)
if [ ! -d "app" ] || [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ Execute este script do diretório raiz do projeto${NC}"
    exit 1
fi

# Verifica se .env existe
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Arquivo .env não encontrado${NC}"
    echo -e "${YELLOW}ℹ️  Crie o arquivo .env baseado no env.template${NC}"
    exit 1
fi

# Cria ambiente virtual se não existir
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}🔨 Criando ambiente virtual...${NC}"
    python3.11 -m venv .venv
fi

# Ativa o ambiente virtual
echo -e "${YELLOW}🔨 Ativando ambiente virtual...${NC}"
source .venv/bin/activate

# Atualiza pip
echo -e "${YELLOW}🔨 Atualizando pip...${NC}"
python -m pip install --upgrade pip

# Instala/atualiza dependências
echo -e "${YELLOW}🔨 Instalando/atualizando dependências...${NC}"
pip install -r requirements.txt

# Verifica se todas as variáveis de ambiente necessárias estão definidas
echo -e "${YELLOW}🔍 Verificando variáveis de ambiente...${NC}"
required_vars=(
    "DATABASE_URL"
    "OPENAI_API_KEY"
    "JWT_SECRET"
)

missing_vars=0
for var in "${required_vars[@]}"; do
    if ! grep -q "^${var}=" .env || [ -z "$(grep "^${var}=" .env | cut -d'=' -f2)" ]; then
        echo -e "${RED}❌ Variável $var não encontrada ou vazia no .env${NC}"
        missing_vars=1
    fi
done

if [ $missing_vars -eq 1 ]; then
    echo -e "${RED}❌ Configure todas as variáveis de ambiente necessárias no .env${NC}"
    exit 1
fi

# Inicia a aplicação
echo -e "\n${GREEN}✅ Setup completo! Iniciando a aplicação...${NC}\n"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload 