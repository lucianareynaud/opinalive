#!/bin/bash

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para imprimir mensagens com cor
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Verifica se estamos no diretório correto
if [ ! -f "requirements.txt" ]; then
    print_error "Este script deve ser executado do diretório raiz do projeto"
    exit 1
fi

# Ativa o ambiente virtual
if [ ! -d ".venv" ]; then
    print_status "Criando ambiente virtual..."
    python3 -m venv .venv
fi

# Ativa o ambiente virtual
source .venv/bin/activate

# Verifica se a ativação funcionou
if [ $? -ne 0 ]; then
    print_error "Falha ao ativar ambiente virtual"
    exit 1
fi

print_status "Ambiente virtual ativado"

# Instala/atualiza dependências se necessário
if [ ! -f ".venv/.dependencies-installed" ]; then
    print_status "Instalando dependências..."
    pip install -r requirements.txt
    touch .venv/.dependencies-installed
else
    print_warning "Dependências já instaladas. Use 'update-deps' para atualizar se necessário"
fi

# Carrega variáveis de ambiente
if [ -f ".env" ]; then
    source .env
    print_status "Variáveis de ambiente carregadas de .env"
elif [ -f "config-local.env" ]; then
    source config-local.env
    print_status "Variáveis de ambiente carregadas de config-local.env"
else
    print_error "Arquivo .env não encontrado"
    exit 1
fi

# Cria aliases úteis
alias run="python -m uvicorn app.main:app --reload"
alias test="python -m pytest"
alias update-deps="pip install -r requirements.txt && touch .venv/.dependencies-installed"

print_status "Ambiente de desenvolvimento pronto!"
print_status "Comandos disponíveis:"
echo "  run         -> Inicia o servidor de desenvolvimento"
echo "  test        -> Roda os testes"
echo "  update-deps -> Atualiza dependências"

# Mantém o shell ativo
exec $SHELL 