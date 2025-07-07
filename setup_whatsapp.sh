#!/bin/bash

# Script para configurar o listener do WhatsApp com Baileys
# Execute: chmod +x setup_whatsapp.sh && ./setup_whatsapp.sh

echo "🚀 Configurando WhatsApp listener com Baileys..."

# Verifica se o Node.js está instalado
if ! command -v node &> /dev/null; then
    echo "❌ Node.js não encontrado. Por favor, instale o Node.js v18 ou superior."
    exit 1
fi

# Verifica versão do Node.js
NODE_VERSION=$(node -v | cut -d. -f1 | tr -d 'v')
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js v18 ou superior é necessário. Versão atual: $(node -v)"
    exit 1
fi

# Cria diretórios necessários
mkdir -p whatsapp/auth whatsapp/audios

# Entra no diretório do WhatsApp
cd whatsapp

# Instala dependências
echo "📦 Instalando dependências..."
npm install

echo "✅ Configuração concluída!"
echo ""
echo "Para iniciar o WhatsApp listener:"
echo "1. Execute o servidor FastAPI normalmente"
echo "2. O listener será iniciado automaticamente"
echo "3. Escaneie o QR code que aparecerá no terminal"
echo ""
echo "⚠️  Importante:"
echo "- Mantenha o celular conectado à internet"
echo "- Não desconecte o WhatsApp Web"
echo "- O QR code será exibido apenas na primeira vez" 