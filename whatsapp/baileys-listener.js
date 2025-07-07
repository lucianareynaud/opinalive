import { Boom } from '@hapi/boom';
import P from 'pino';
import { fileURLToPath } from 'url';
import path from 'path';
import axios from 'axios';
import baileys from '@whiskeysockets/baileys';
import qrcode from 'qrcode-terminal';
import fs from 'fs';

const { default: makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion, DisconnectReason, makeCacheableSignalKeyStore } = baileys;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configure structured logging
const logger = P({
    level: 'info',
    transport: {
        target: 'pino-pretty',
        options: {
            colorize: true
        }
    }
});

// Create auth directory if it doesn't exist
const AUTH_DIR = path.join(__dirname, '..', 'auth');
if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
}

// Cleanup function to keep only recent auth files
const MAX_AUTH_FILES = 2; // Reduzido para 2 pre-keys
const CLEANUP_INTERVAL = 1000 * 60 * 5; // Run cleanup every 5 minutes

function cleanupAuthFiles() {
    try {
        const files = fs.readdirSync(AUTH_DIR);
        
        // Separate pre-keys from other auth files
        const preKeys = files.filter(f => f.startsWith('pre-key-'));
        const otherFiles = files.filter(f => !f.startsWith('pre-key-'));
        
        // Sort pre-keys by number
        const sortedPreKeys = preKeys.sort((a, b) => {
            const numA = parseInt(a.replace('pre-key-', '').replace('.json', ''));
            const numB = parseInt(b.replace('pre-key-', '').replace('.json', ''));
            return numB - numA; // Sort descending
        });
        
        // Keep only MAX_AUTH_FILES most recent pre-keys
        const keysToDelete = sortedPreKeys.slice(MAX_AUTH_FILES);
        
        // Delete old pre-keys
        for (const key of keysToDelete) {
            fs.unlinkSync(path.join(AUTH_DIR, key));
            logger.info('auth_file_cleaned', { file: key });
        }
        
        logger.info('auth_cleanup_completed', {
            files_removed: keysToDelete.length,
            files_kept: sortedPreKeys.length - keysToDelete.length + otherFiles.length
        });
    } catch (error) {
        logger.error('auth_cleanup_failed', {
            error: error.message,
            error_type: error.name
        });
    }
}

// Run cleanup periodically
setInterval(cleanupAuthFiles, CLEANUP_INTERVAL);

// Run initial cleanup
cleanupAuthFiles();

const FASTAPI_URL = process.env.FASTAPI_URL || 'http://localhost:8000';

let sock = null;
let reconnectCount = 0;
const MAX_RECONNECTS = 5;
const RECONNECT_INTERVAL = 5000;

// Função para atualizar status no monitoramento
async function updateMonitoringStatus(status, extraInfo = {}) {
    try {
        await axios.post(`${FASTAPI_URL}/monitoring/whatsapp/status`, {
            status,
            ...extraInfo
        });
    } catch (error) {
        logger.error('monitoring_update_failed', {
            error: error.message,
            status,
            extra_info: extraInfo
        });
    }
}

// Função para iniciar a conexão
async function startSock() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
        version,
        printQRInTerminal: true,
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, logger)
        },
        logger,
        generateHighQualityLinkPreview: true,
        browser: ['Opina', 'Chrome', '96.0.4664.110']
    });

    sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
        const statusCode = (lastDisconnect?.error instanceof Boom)?.output?.statusCode;

        logger.info('connection_update', {
            status: connection,
            disconnect_reason: statusCode ? DisconnectReason[statusCode] : null,
            reconnect_count: reconnectCount,
            qr_received: !!qr
        });

        // Handle QR code
        if (qr) {
            // Generate QR in terminal
            qrcode.generate(qr, { small: true });
            
            // Update monitoring with QR
            await updateMonitoringStatus('qr_code', { qr });
            
            logger.info('qr_code_generated', {
                timestamp: new Date().toISOString()
            });
        }

        if (connection === 'close') {
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            
            await updateMonitoringStatus('disconnected', {
                reason: statusCode ? DisconnectReason[statusCode] : null,
                reconnect_count: reconnectCount
            });
            
            if (shouldReconnect && reconnectCount < MAX_RECONNECTS) {
                reconnectCount++;
                logger.info('reconnecting', {
                    attempt: reconnectCount,
                    max_attempts: MAX_RECONNECTS,
                    next_attempt_ms: RECONNECT_INTERVAL
                });
                
                setTimeout(startSock, RECONNECT_INTERVAL);
            } else if (reconnectCount >= MAX_RECONNECTS) {
                logger.error('max_reconnects_reached', {
                    max_attempts: MAX_RECONNECTS,
                    final_status: connection,
                    final_error: statusCode ? DisconnectReason[statusCode] : null
                });
                process.exit(1);
            }
        } else if (connection === 'open') {
            reconnectCount = 0;
            await updateMonitoringStatus('connected', {
                phone: sock.user?.id,
                version
            });
            
            logger.info('connection_established', {
                version: version,
                phone: sock.user?.id
            });
        }
    });

    sock.ev.on('messages.upsert', async ({ messages }) => {
        const msg = messages[0];
        if (!msg.message || msg.key.fromMe) return;

        const sender = msg.key.remoteJid;
        const audio = msg.message.audioMessage;

        // Atualizar monitoramento para qualquer mensagem
        await updateMonitoringStatus('message_received', {
            message_type: audio ? 'audio' : 'other'
        });

        if (audio) {
            const context = {
                message_id: msg.key.id,
                from: sender.replace('@s.whatsapp.net', ''),
                timestamp: new Date(msg.messageTimestamp * 1000).toISOString(),
                media_type: 'audio'
            };

            const startTime = Date.now();

            try {
                logger.info('processing_audio', context);
                
                const buffer = await sock.downloadMediaMessage(msg);
                
                await axios.post(`${FASTAPI_URL}/webhooks/process-audio`, {
                    from: context.from,
                    message_id: context.message_id,
                    audio: buffer.toString('base64')
                }, {
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const duration = (Date.now() - startTime) / 1000;
                
                logger.info('audio_processed', {
                    ...context,
                    status: 'success',
                    duration
                });
                
                // Atualizar métricas de processamento
                await axios.post(`${FASTAPI_URL}/monitoring/audio/processed`, {
                    success: true,
                    duration
                });
                
            } catch (error) {
                const duration = (Date.now() - startTime) / 1000;
                
                logger.error('audio_processing_failed', {
                    ...context,
                    error: error.message,
                    error_type: error.name,
                    status: 'failed',
                    duration
                });
                
                // Atualizar métricas de erro
                await axios.post(`${FASTAPI_URL}/monitoring/audio/processed`, {
                    success: false,
                    duration,
                    error: error.message
                });
            }
        }
    });

    sock.ev.on('creds.update', () => {
        saveCreds();
        cleanupAuthFiles(); // Limpa arquivos após cada atualização de credenciais
    });
}

// Iniciar conexão
startSock();

// Processar comandos da entrada padrão
process.stdin.on('data', async (data) => {
    try {
        const command = JSON.parse(data.toString());
        
        if (command.type === 'send_message' && sock) {
            logger.info('sending_message', {
                to: command.to,
                type: 'text'
            });
            
            await sock.sendMessage(command.to, { text: command.message });
            
            logger.info('message_sent', {
                to: command.to,
                type: 'text',
                status: 'success'
            });
        }
    } catch (error) {
        logger.error('command_processing_failed', {
            error: error.message,
            error_type: error.name,
            raw_command: data.toString()
        });
    }
}); 