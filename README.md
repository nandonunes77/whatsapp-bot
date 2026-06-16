# 🤖 Triângulo Entretenimento — Chatbot WhatsApp

Chatbot com IA para WhatsApp do evento **Arena Triângulo** (Uberlândia/MG).

Sistema avançado com **ChromaDB (banco vetorial)** + **DeepSeek API** para respostas inteligentes e contextuais.

## 📦 Estrutura do Projeto

```
whatsapp-bot/
│
├── 🐍 bot.py                  # Servidor FastAPI (porta 8000)
├── 🧠 ai_engine.py            # Motor: ChromaDB + DeepSeek
│
├── 📦 database/
│   └── __init__.py            # ChromaManager (banco vetorial)
│
├── 🔍 extractor/
│   └── __init__.py            # Extrator de eventos (6 bilheterias)
│
├── 📚 knowledge/
│   └── bot_soul.md            # Personalidade do bot
│
├── 💾 data/
│   └── chromadb/              # Banco vetorial persistente
│
├── 📱 whatsapp-bridge/
│   ├── index.js               # Conexão WhatsApp (Baileys v7)
│   └── package.json           # Dependências Node.js
│
├── 📦 requirements.txt        # Dependências Python
├── 🔑 .env                    # Chave DeepSeek (não versionar!)
├── 🧪 testar_extrator.py      # Script de teste do extrator
└── 📖 README.md               # Esta documentação
```

## ⚡ Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    GERENCIADOR DE EVENTOS                │
│                                                         │
│  POST /extrair?url=baladapp.com.br/evento/xxx           │
│         │                                               │
│         ▼                                               │
│  ┌──────────────────┐                                   │
│  │  EXTRACTOR ENGINE │                                   │
│  │                   │                                   │
│  │  ① JSON-LD ──────┼──→ Encontrou? → Estruturado      │
│  │  ② HTML Parser ──┼──→ Encontrou? → Estruturado      │
│  │  ③ IA DeepSeek ──┼──→ Fallback  → tokens            │
│  └────────┬─────────┘                                   │
│           │                                             │
│           ▼                                             │
│  ┌──────────────────┐                                   │
│  │   CHROMADB        │                                   │
│  │                   │                                   │
│  │  📦 Eventos       │ (embeddings dos eventos)         │
│  │  🤖 Bot SOUL      │ (personalidade fixa)             │
│  │  📚 Info fixas    │ (dados permanentes)              │
│  └────────┬─────────┘                                   │
│           │                                             │
└───────────┼─────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────┐
│                   WHATSAPP BOT                          │
│                                                         │
│  Usuário pergunta: "Quando é o evento X?"               │
│         │                                               │
│         ▼                                               │
│  RAG consulta ChromaDB                                  │
│         │                                               │
│         ▼                                               │
│  DeepSeek responde com contexto                         │
└─────────────────────────────────────────────────────────┘
```

## 🎯 Bilheterias Suportadas

| Plataforma | Status | Método | Observação |
|------------|--------|--------|------------|
| GuicheLive | ✅ **FUNCIONANDO** | JSON-LD | Extração perfeita |
| Ticket360 | ✅ **FUNCIONANDO** | JSON-LD | Extração perfeita |
| BaladAPP | ⚠️ **INTERMITENTE** | cloudscraper | Cloudflare bloqueia às vezes |
| Meu Bilhete | ❌ **SPA** | - | Precisa de browser headless |
| IngressoLive | ⏳ **PENDENTE** | - | Não testado |
| Q2 Ingressos | ⏳ **PENDENTE** | - | Não testado |

### ⚠️ Limitações Conhecidas

**BaladAPP** e **Meu Bilhete** são **Single Page Applications (SPAs)** que carregam conteúdo via JavaScript. Sem um browser headless (Chrome/Playwright), não é possível extrair dados desses sites de forma confiável.

**Soluções futuras:**
1. Instalar Chrome/Playwright no servidor
2. Usar um serviço de proxy (ScrapingBee, Browserless)
3. Encontrar APIs internas dos sites

### 🤖 Fallback Inteligente

O extrator usa IA (DeepSeek) como fallback quando faltam campos cruciais (data, local). Se a extração inicial não encontrar esses campos, a IA tenta extrair apenas o que falta, economizando tokens.

## 📊 Dados Extraídos por Evento

- Nome do evento
- Data e horário
- Local e endereço
- Artistas/atrações
- Tipos de ingresso (tipo, preço, lote)
- Classificação etária
- Descrição do evento
- Se é coberto ou não
- Onde comprar (plataforma + WhatsApp)

## 🚀 Como Rodar

### Opção 1: Script automático (recomendado)

```bash
cd whatsapp-bot

# Iniciar tudo (Python + WhatsApp)
./start.sh

# Ver status
./status.sh

# Parar tudo
./stop.sh
```

### Opção 2: Manual

#### 1. Servidor Python

```bash
cd whatsapp-bot
source venv/bin/activate
python bot.py
```

#### 2. Conexão WhatsApp

```bash
cd whatsapp-bridge
node index.js
```

Na primeira vez, **escaneie o QR Code** com seu WhatsApp.

### 3. Testar sem o WhatsApp

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"de":"5511999998888","mensagem":"Qual o horário do evento?"}'
```
# Via API (com servidor rodando)
curl -X POST http://localhost:8000/extrair \
  -H "Content-Type: application/json" \
  -d '{"url": "https://baladapp.com.br/evento/xxx"}'
```

## 🔧 Endpoints da API

### Webhook WhatsApp
```
POST /webhook
{
  "de": "5511999998888",
  "mensagem": "Qual o horário do evento?",
  "nome": "João Silva"
}
```

### Extrair Evento
```
POST /extrair
{
  "url": "https://baladapp.com.br/evento/xxx"
}
```

### Listar Eventos
```
GET /eventos
```

### Remover Evento
```
DELETE /eventos/{evento_id}
```

### Estatísticas
```
GET /estatisticas
```

### Health Check
```
GET /health
```

## 🧠 Bot SOUL (Personalidade)

O bot possui uma personalidade configurável em `knowledge/bot_soul.md`:

- **Tom:** Amigável e profissional
- **Formato:** Respostas curtas e diretas
- **Emojis:** Usa com moderação
- **Idioma:** Português do Brasil

Para alterar a personalidade, edite o arquivo `knowledge/bot_soul.md` e reinicie o servidor.

## 📚 Banco Vetorial (ChromaDB)

O sistema usa **ChromaDB** para armazenar e buscar informações:

- **Coleção `events`:** Eventos extraídos das bilheterias
- **Coleção `bot_soul`:** Personalidade do bot
- **Coleção `fixed_info`:** Informações fixas e permanentes

Os dados são persistidos em `data/chromadb/`.

## 🔧 Dependências

**Python** (requirements.txt):
- `fastapi` + `uvicorn` — servidor web
- `httpx` — chamadas HTTP pra DeepSeek
- `python-dotenv` — variáveis de ambiente
- `chromadb` — banco vetorial
- `beautifulsoup4` + `lxml` — parsing HTML
- `pypdf2` + `markdown` — leitura de documentos

**Node.js** (whatsapp-bridge/package.json):
- `@whiskeysockets/baileys` v7.0.0-rc13 — conexão WhatsApp
- `qrcode-terminal` — QR Code no terminal
- `axios` — chamadas pro servidor Python

## 📝 Próximos Passos

- [ ] Implementar extração via IA (DeepSeek) para páginas sem JSON-LD
- [ ] Adicionar suporte a mais bilheterias
- [ ] Dashboard de estatísticas
- [ ] Filtro de contatos (whitelist)
- [ ] Suporte a documentos PDF

---

Projeto: **Triângulo Entretenimento** — Arena Triângulo  
Stack: Python FastAPI + Baileys + DeepSeek + ChromaDB  
Idioma: 🇧🇷 Português do Brasil
