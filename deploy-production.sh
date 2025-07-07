#!/bin/bash

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 DEPLOY OPINA.LIVE PARA PRODUÇÃO${NC}\n"

# Verifica se está no diretório correto
if [ ! -f "cloudbuild.yaml" ] || [ ! -f "app/main.py" ]; then
    echo -e "${RED}❌ Execute este script do diretório raiz do projeto${NC}"
    exit 1
fi

# Verifica se gcloud está instalado
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ Google Cloud CLI não está instalado${NC}"
    echo -e "${YELLOW}📝 Instale em: https://cloud.google.com/sdk/docs/install${NC}"
    exit 1
fi

# Define variáveis
PROJECT_ID="opina-app"  # Projeto existente no Google Cloud
REGION="us-central1"    # Região que suporta domain mappings
SERVICE_NAME="opina-app"

echo -e "${YELLOW}📋 Configurações do Deploy:${NC}"
echo -e "   Project ID: ${PROJECT_ID}"
echo -e "   Região: ${REGION}"
echo -e "   Serviço: ${SERVICE_NAME}"
echo ""

# Confirma se quer continuar
read -p "Deseja continuar com o deploy? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏹️  Deploy cancelado${NC}"
    exit 0
fi

# 1. Verifica autenticação
echo -e "${BLUE}🔐 Verificando autenticação...${NC}"
if ! gcloud auth list --filter="status:ACTIVE" --format="value(account)" | grep -q .; then
    echo -e "${RED}❌ Não está logado no gcloud${NC}"
    echo -e "${YELLOW}💡 Execute: gcloud auth login${NC}"
    exit 1
fi

# 2. Define projeto
echo -e "${BLUE}🎯 Definindo projeto...${NC}"
gcloud config set project $PROJECT_ID

# 3. Habilita APIs necessárias
echo -e "${BLUE}🔧 Habilitando APIs necessárias...${NC}"
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# 4. Verifica se env.yaml existe e tem as configurações corretas
echo -e "${BLUE}🔍 Validando variáveis críticas...${NC}"
if [ ! -f "env.yaml" ]; then
    echo -e "${RED}❌ Arquivo env.yaml não encontrado${NC}"
    exit 1
fi

# Verifica se ENVIRONMENT é production
ENV_CHECK=$(grep "ENVIRONMENT:" env.yaml | grep "production")
if [ -z "$ENV_CHECK" ]; then
    echo -e "${RED}❌ ENVIRONMENT deve ser 'production' no env.yaml${NC}"
    exit 1
fi

# Verifica se DATABASE_URL existe
DB_CHECK=$(grep "DATABASE_URL:" env.yaml)
if [ -z "$DB_CHECK" ]; then
    echo -e "${RED}❌ DATABASE_URL não encontrado no env.yaml${NC}"
    exit 1
fi

# Verifica se OPENAI_API_KEY existe
OPENAI_CHECK=$(grep "OPENAI_API_KEY:" env.yaml)
if [ -z "$OPENAI_CHECK" ]; then
    echo -e "${RED}❌ OPENAI_API_KEY não encontrado no env.yaml${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Todas as validações passaram!${NC}\n"

# 7. Build e deploy usando Cloud Build
echo -e "${BLUE}🏗️  Iniciando build e deploy...${NC}"
gcloud builds submit --config cloudbuild.yaml .

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ Build concluído com sucesso!${NC}"
    
    echo -e "${BLUE}🚀 Fazendo deploy no Cloud Run...${NC}"
    
    # Deploy no Cloud Run
    gcloud run deploy $SERVICE_NAME \
        --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
        --region $REGION \
        --platform managed \
        --env-vars-file env.yaml \
        --allow-unauthenticated \
        --port 8080 \
        --memory 512Mi \
        --cpu 1 \
        --min-instances 0 \
        --max-instances 10 \
        --timeout 300
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}\n🎉 DEPLOY REALIZADO COM SUCESSO!${NC}"
        echo -e "${GREEN}📱 URL da aplicação: https://$SERVICE_NAME-915022096211.$REGION.run.app${NC}"
        echo -e "${YELLOW}📝 Configure os redirect URIs no Google OAuth Console${NC}"
        echo -e "${YELLOW}📝 Configure os webhooks no Stripe Dashboard${NC}"
    else
        echo -e "${RED}❌ Erro no deploy do Cloud Run${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Erro no build da aplicação${NC}"
    exit 1
fi 