/**
 * ╔══════════════════════════════════════════╗
 * ║   WHATSAPP BRIDGE (via Baileys v7)     ║
 * ║   Conecta WhatsApp → Python FastAPI    ║
 * ╚══════════════════════════════════════════╝
 *
 * Versão com proteção contra ban:
 * - Rate limiting de QR Code (máx 5, depois espera 5min)
 * - Backoff exponencial entre reconexões
 * - Tratamento correto de disconnect reasons
 * - Persistência de sessão
 */

const {
    makeWASocket,
    DisconnectReason,
    useMultiFileAuthState,
    fetchLatestBaileysVersion,
    makeCacheableSignalKeyStore
} = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const pino = require('pino');
const fs = require('fs');
const path = require('path');

// ==========================================
// CONFIGURAÇÃO
// ==========================================

const PYTHON_SERVER = process.env.BOT_SERVER || 'http://localhost:8000';

// Configurações de proteção contra ban
const CONFIG = {
    MAX_QR_CODES: 5,           // Máximo de QR codes antes de pausar
    QR_PAUSE_MS: 5 * 60 * 1000, // 5 minutos de pausa após max QR codes
    RECONNECT_BASE_MS: 5000,    // 5 segundos base para reconexão
    RECONNECT_MAX_MS: 60000,    // Máximo 1 minuto entre reconexões
    QR_EXPIRY_MS: 20000,        // QR code válido por ~20 segundos
};

// Logger mostrando warnings
const logger = pino({
    level: 'warn',
    transport: {
        target: 'pino-pretty',
        options: { colorize: true }
    }
});

// Estado global
let qrCodeCount = 0;
let lastQrTime = 0;
let isPaused = false;
let reconnectAttempts = 0;

// ==========================================
// FUNÇÕES AUXILIARES
// ==========================================

function formatarNumero(jid) {
    return jid.replace(/@s\.whatsapp\.net$/, '').replace(/@g\.us$/, '');
}

function pegarNome(msg) {
    return msg.pushName || 'Cliente';
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function getBackoffDelay() {
    // Backoff exponencial com jitter
    const base = CONFIG.RECONNECT_BASE_MS * Math.pow(2, reconnectAttempts);
    const jitter = Math.random() * 1000; // 0-1s de jitter
    return Math.min(base + jitter, CONFIG.RECONNECT_MAX_MS);
}

// ==========================================
// VERIFICAÇÃO DE SESSÃO
// ==========================================

function verificarSessao(authDir) {
    const credsPath = path.join(authDir, 'creds.json');
    
    if (!fs.existsSync(credsPath)) {
        return { existe: false, motivo: 'Arquivo creds.json não encontrado' };
    }
    
    try {
        const creds = JSON.parse(fs.readFileSync(credsPath, 'utf8'));
        
        // Verifica se tem credenciais básicas
        if (!creds.noiseKey || !creds.signedIdentityKey) {
            return { existe: false, motivo: 'Credenciais incompletas' };
        }
        
        return { existe: true, motivo: 'Sessão válida encontrada' };
    } catch (erro) {
        return { existe: false, motivo: `Erro ao ler creds: ${erro.message}` };
    }
}

// ==========================================
// CONECTA NO WHATSAPP
// ==========================================

async function iniciarBot() {
    console.log('\n🤖 WhatsApp Bridge (Baileys) iniciando...\n');
    console.log(`🔗 Servidor Python: ${PYTHON_SERVER}\n`);

    // Verifica se está pausado por excesso de QR codes
    if (isPaused) {
        console.log(`⏸️  PAUSADO: Muitos QR codes gerados (${qrCodeCount})`);
        console.log(`⏰ Aguardando ${CONFIG.QR_PAUSE_MS / 1000 / 60} minutos antes de tentar novamente...\n`);
        await sleep(CONFIG.QR_PAUSE_MS);
        isPaused = false;
        qrCodeCount = 0;
        console.log('🔄 Retomando conexão...\n');
    }

    // Garante que a pasta de auth existe
    const authDir = path.join(__dirname, 'whatsapp-auth');
    if (!fs.existsSync(authDir)) {
        fs.mkdirSync(authDir, { recursive: true });
    }

    // Verifica se tem sessão salva
    const sessao = verificarSessao(authDir);
    console.log(`📱 ${sessao.motivo}\n`);

    // Carrega estado de autenticação
    const { state, saveCreds } = await useMultiFileAuthState(authDir);

    // Cria o socket
    const sock = makeWASocket({
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, pino({ level: 'silent' })),
        },
        logger: logger,
        browser: ['Chrome', 'Windows', '120.0.0.0'], // Browser mais realista
        markOnlineOnConnect: false, // Não mostra online imediatamente
        // Configuração de QR code
        qrTimeout: CONFIG.QR_EXPIRY_MS,
    });

    // Salva credenciais automaticamente
    sock.ev.on('creds.update', saveCreds);

    // ========== CONEXÃO ==========
    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        // QR Code
        if (qr) {
            const now = Date.now();
            const timeSinceLastQr = now - lastQrTime;
            
            // Rate limiting: não gera QR muito rápido
            if (timeSinceLastQr < CONFIG.QR_EXPIRY_MS) {
                console.log(`⏳ Aguardando QR code anterior expirar...`);
                return;
            }
            
            qrCodeCount++;
            lastQrTime = now;
            
            console.log(`\n📱 QR Code ${qrCodeCount}/${CONFIG.MAX_QR_CODES}`);
            console.log('━'.repeat(40));
            qrcode.generate(qr, { small: true });
            console.log('━'.repeat(40));
            console.log('⚠️  WhatsApp → Dispositivos → Escanear QR');
            console.log(`⏰ Válido por ~${CONFIG.QR_EXPIRY_MS / 1000} segundos\n`);

            // Se atingiu o limite, pausa
            if (qrCodeCount >= CONFIG.MAX_QR_CODES) {
                console.log(`\n🛑 LIMITE DE QR CODES ATINGIDO (${CONFIG.MAX_QR_CODES})`);
                console.log(`⏸️  Pausando por ${CONFIG.QR_PAUSE_MS / 1000 / 60} minutos para evitar ban...`);
                console.log('💡 Dica: Escaneie o QR code rapidamente!\n');
                isPaused = true;
                
                // Fecha a conexão atual
                sock.end();
                return;
            }
        }

        if (connection === 'open') {
            console.log('\n✅ CONECTADO! Aguardando mensagens...\n');
            qrCodeCount = 0; // Reseta contador de QR codes
            reconnectAttempts = 0; // Reseta tentativas de reconexão
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const errorMessage = lastDisconnect?.error?.message || 'Desconhecido';
            
            console.log(`\n⚠️  Desconectado`);
            console.log(`   Código: ${statusCode}`);
            console.log(`   Motivo: ${errorMessage}\n`);

            // Trata diferentes motivos de desconexão
            switch (statusCode) {
                case DisconnectReason.loggedOut:
                    console.log('❌ LOGGED OUT: Sessão expirada ou logout manual');
                    console.log('💡 Solução: Delete ./whatsapp-auth e reinicie');
                    console.log('⚠️  NÃO reconectando automaticamente\n');
                    // Não reconecta - precisa de novo pareamento
                    process.exit(0);
                    break;

                case DisconnectReason.badSession:
                    console.log('❌ BAD SESSION: Sessão corrompida');
                    console.log('💡 Solução: Delete ./whatsapp-auth e reinicie\n');
                    process.exit(1);
                    break;

                case DisconnectReason.connectionClosed:
                    console.log('🔄 Conexão fechada. Reconectando...');
                    reconectarComBackoff();
                    break;

                case DisconnectReason.connectionLost:
                    console.log('🔄 Conexão perdida. Reconectando...');
                    reconectarComBackoff();
                    break;

                case DisconnectReason.connectionReplaced:
                    console.log('⚠️  CONEXÃO SUBSTITUÍDA: Outro dispositivo conectou');
                    console.log('💡 Isso acontece se você abrir o WhatsApp Web em outro lugar');
                    console.log('🔄 Reconectando...\n');
                    reconectarComBackoff();
                    break;

                case DisconnectReason.timedOut:
                    console.log('⏰ Timeout. Reconectando...');
                    reconectarComBackoff();
                    break;

                case 403:
                    console.log('🚫 ACESSO NEGADO (403)');
                    console.log('💡 Possível ban temporário. Aguarde 6 horas.');
                    console.log('⏸️  Não reconectando.\n');
                    isPaused = true;
                    break;

                default:
                    console.log(`🔄 Desconexão desconhecida (${statusCode}). Reconectando...`);
                    reconectarComBackoff();
                    break;
            }
        }
    });

    // ========== MENSAGENS ==========
    sock.ev.on('messages.upsert', async (m) => {
        const msg = m.messages[0];
        if (!msg || !msg.message) return;
        if (msg.key.fromMe) return;
        if (msg.key.remoteJid?.includes('@g.us')) return;

        const texto = msg.message.conversation
            || msg.message.extendedTextMessage?.text
            || msg.message.imageMessage?.caption
            || '';

        if (!texto) return;

        const numero = formatarNumero(msg.key.remoteJid);
        const nome = pegarNome(msg);

        console.log(`📩 ${nome} (${numero}): "${texto.substring(0, 60)}"`);

        try {
            const resposta = await axios.post(`${PYTHON_SERVER}/webhook`, {
                de: numero, mensagem: texto, nome: nome
            }, { timeout: 30000 });

            console.log(`✅ Resposta: "${resposta.data.resposta.substring(0, 60)}"\n`);
            await sock.sendMessage(msg.key.remoteJid, { text: resposta.data.resposta });

        } catch (erro) {
            console.error(`❌ ${erro.code === 'ECONNREFUSED' ? 'Servidor Python offline!' : erro.message}`);
            await sock.sendMessage(msg.key.remoteJid, {
                text: erro.code === 'ECONNREFUSED'
                    ? '❌ Bot temporariamente offline. Tente novamente.'
                    : '❌ Erro ao processar. Tente novamente.'
            });
        }
    });

    return sock;
}

// ==========================================
// RECONEXÃO COM BACKOFF
// ==========================================

async function reconectarComBackoff() {
    reconnectAttempts++;
    const delay = getBackoffDelay();
    
    console.log(`🔄 Reconexão ${reconnectAttempts} em ${(delay / 1000).toFixed(1)}s...`);
    
    await sleep(delay);
    
    try {
        await iniciarBot();
    } catch (erro) {
        console.error(`❌ Erro na reconexão: ${erro.message}`);
        // Tenta novamente com backoff maior
        reconectarComBackoff();
    }
}

// ==========================================
// INICIAR
// ==========================================

console.log('╔══════════════════════════════════════════╗');
console.log('║   🤖 WhatsApp Bridge v2.0               ║');
console.log('║   Proteção contra ban ativada           ║');
console.log('╚══════════════════════════════════════════╝');
console.log('');
console.log('📋 Configurações:');
console.log(`   • Máximo de QR codes: ${CONFIG.MAX_QR_CODES}`);
console.log(`   • Pausa após limite: ${CONFIG.QR_PAUSE_MS / 1000 / 60} minutos`);
console.log(`   • Backoff base: ${CONFIG.RECONNECT_BASE_MS / 1000}s`);
console.log(`   • Backoff máximo: ${CONFIG.RECONNECT_MAX_MS / 1000}s`);
console.log('');

iniciarBot().catch(erro => {
    console.error('❌ Erro fatal:', erro);
    process.exit(1);
});
