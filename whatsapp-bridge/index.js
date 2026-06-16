/**
 * ╔══════════════════════════════════════════╗
 * ║   WHATSAPP BRIDGE (via Baileys v7)     ║
 * ║   Conecta WhatsApp → Python FastAPI    ║
 * ╚══════════════════════════════════════════╝
 *
 * Versão depurada — testa QR Code mais diretamente
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

// ==========================================
// CONFIGURAÇÃO
// ==========================================

const PYTHON_SERVER = process.env.BOT_SERVER || 'http://localhost:8000';

// Logger mostrando warnings
const logger = pino({
    level: 'warn',
    transport: {
        target: 'pino-pretty',
        options: { colorize: true }
    }
});

// ==========================================
// FUNÇÕES AUXILIARES
// ==========================================

function formatarNumero(jid) {
    return jid.replace(/@s\.whatsapp\.net$/, '').replace(/@g\.us$/, '');
}

function pegarNome(msg) {
    return msg.pushName || 'Cliente';
}

// ==========================================
// CONECTA NO WHATSAPP
// ==========================================

async function iniciarBot() {
    console.log('🤖 WhatsApp Bridge (Baileys) iniciando...\n');
    console.log(`🔗 Servidor Python: ${PYTHON_SERVER}\n`);

    // Garante que a pasta de auth existe
    const authDir = './whatsapp-auth';
    if (!fs.existsSync(authDir)) {
        fs.mkdirSync(authDir, { recursive: true });
    }

    // Carrega estado de autenticação
    const { state, saveCreds } = await useMultiFileAuthState(authDir);

    // Mostra se tem credenciais salvas
    const temCreds = state.creds && state.creds.me;
    console.log(temCreds ? '📱 Sessão anterior encontrada!' : '📱 Nova sessão — QR Code será gerado');

    // Cria o socket
    const sock = makeWASocket({
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, pino({ level: 'silent' })),
        },
        logger: logger,
        browser: ['Bot', 'Chrome', '1.0.0'],
        markOnlineOnConnect: true,
    });

    // Salva credenciais automaticamente
    sock.ev.on('creds.update', saveCreds);

    // ========== CONEXÃO ==========
    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        // QR Code manual (caso o printQRInTerminal não funcione)
        if (qr) {
            console.log('\n📱 ESCANEIE O QR CODE:\n');
            qrcode.generate(qr, { small: true });
            console.log('\n⚠️  WhatsApp → Dispositivos → Escanear QR\n');
        }

        if (connection === 'open') {
            console.log('\n✅ CONECTADO! Aguardando mensagens...\n');
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            console.log(`\n⚠️  Desconectado (código: ${statusCode})`);

            if (statusCode !== DisconnectReason.loggedOut) {
                console.log('🔄 Reconectando em 3s...');
                setTimeout(() => iniciarBot(), 3000);
            } else {
                console.log('❌ Logged out. Delete ./whatsapp-auth e reinicie.');
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

iniciarBot().catch(erro => {
    console.error('❌ Erro fatal:', erro);
    process.exit(1);
});
