# 📱 WhatsApp Bridge

Bridge entre WhatsApp Web e o servidor Python FastAPI (via Baileys).

## ⚠️ Proteção contra Ban

Esta versão inclui proteções contra banimento temporário do WhatsApp:

### Problemas que causam ban:
1. **QR codes gerados muito rápido** — Cada QR = tentativa de pareamento
2. **Reconexão sem delay** — Comportamento suspeito
3. **Múltiplas sessões** — Vários dispositivos conectados

### Soluções implementadas:

| Proteção | Configuração | Descrição |
|----------|--------------|-----------|
| Rate limiting de QR | `MAX_QR_CODES=1` | Apenas 1 QR code, depois pausa 5min |
| Backoff exponencial | `RECONNECT_BASE_MS=5000` | Espera mais tempo entre reconexões |
| Verificação de sessão | Automático | Verifica se já tem sessão válida |
| Tratamento de disconnect | Automático | Não reconecta em logout |

## 🚀 Como Usar

### 1. Instalar dependências

```bash
cd whatsapp-bridge
npm install
```

### 2. Configurar (opcional)

```bash
cp .env.example .env
# Edite .env se necessário
```

### 3. Iniciar

```bash
node index.js
```

### 4. Primeira vez

1. O QR code será exibido no terminal
2. Abra o WhatsApp no celular
3. Vá em **Dispositivos conectados** → **Conectar dispositivo**
4. Escaneie o QR code **dentro de 20 segundos**

### 5. Sessão persistente

Após o primeiro pareamento:
- A sessão é salva em `./whatsapp-auth/`
- **Não precisa escanear novamente** ao reiniciar o servidor
- A sessão persiste entre restarts

## 🔧 Configurações

Edite o arquivo `.env`:

```bash
# Servidor Python
BOT_SERVER=http://localhost:8000

# Proteção contra ban
MAX_QR_CODES=5           # Máximo de QR codes antes de pausar
QR_PAUSE_MINUTES=5       # Minutos de pausa após limite
RECONNECT_BASE_SECONDS=5 # Delay base para reconexão
RECONNECT_MAX_SECONDS=60 # Delay máximo para reconexão
```

## ⚠️ Códigos de Desconexão

| Código | Significado | Ação |
|--------|-------------|------|
| 401 | Logged out | Delete `./whatsapp-auth` e reinicie |
| 403 | Forbidden (possível ban) | Aguarde 6 horas |
| 408 | Timeout | Reconecta automaticamente |
| 428 | Conexão fechada | Reconecta automaticamente |
| 440 | Conexão substituída | Cuidado com múltiplos acessos |

## 🛡️ Dicas para Evitar Ban

1. **Escaneie o QR code rapidamente** (dentro de 20s)
2. **Não abra WhatsApp Web em outro lugar** enquanto o bot está rodando
3. **Não delete a pasta `whatsapp-auth`** desnecessariamente
4. **Aguarde 6 horas** se receber erro 403
5. **Não faça deploy em múltiplos servidores** com o mesmo número

## 📊 Logs

O bot mostra informações úteis:

```
📱 QR Code 1/5          → Escaneie este QR
✅ CONECTADO!            → Bot funcionando
⚠️ Desconectado (408)   → Reconectando automaticamente
🛑 LIMITE DE QR CODES   → Pausando para evitar ban
❌ LOGGED OUT            → Precisa de novo pareamento
```

## 🔍 Troubleshooting

### "QR code aparece muito rápido"
- Normal na primeira vez
- Se continuar, verifique se a sessão está sendo salva

### "Erro 403 - Forbidden"
- Possível ban temporário
- Aguarde 6 horas antes de tentar novamente

### "Logged out"
- Delete a pasta `./whatsapp-auth/`
- Reinicie o bot
- Escaneie o QR code novamente

### "Conexão substituída"
- Você abriu WhatsApp Web em outro lugar
- Feche o WhatsApp Web no navegador
- O bot vai reconectar automaticamente

---

**Versão:** 2.0  
**Última atualização:** 2026-06-16
