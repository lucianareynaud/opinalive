# Build stage
FROM nikolaik/python-nodejs:python3.11-nodejs20 as builder

WORKDIR /app

# Copiar apenas os arquivos necessários para instalar dependências
COPY requirements.txt ./
COPY whatsapp/package.json whatsapp/package-lock.json ./whatsapp/

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt && \
    cd whatsapp && npm install --production && cd ..

# Runtime stage
FROM nikolaik/python-nodejs:python3.11-nodejs20-slim

WORKDIR /app

# Copiar código da aplicação e arquivos de dependências
COPY requirements.txt ./
COPY . .

# Instalar dependências Python no ambiente final
RUN pip install --no-cache-dir -r requirements.txt && \
    mkdir -p /data/whatsapp && \
    chown -R nobody:nogroup /data

# Copiar node_modules do estágio de build
COPY --from=builder /app/whatsapp/node_modules /app/whatsapp/node_modules

# Configurar variáveis de ambiente
ENV HOST=0.0.0.0
ENV ENVIRONMENT=production

# Usar usuário não-root
USER nobody

# Expor porta (será sobrescrita pelo Cloud Run)
EXPOSE 8080

# Comando para iniciar usando a variável PORT do Cloud Run
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
