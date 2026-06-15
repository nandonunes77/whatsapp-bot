# 🤖 Triângulo Entretenimento — Chatbot WhatsApp

Chatbot com IA para WhatsApp do evento **Arena Triângulo** (Uberlândia/MG).
Responde perguntas sobre datas, ingressos, atrações e regras usando **FAQ + RAG + DeepSeek**.

## 📦 Estrutura do Projeto

```
whatsapp-bot/
│
├── 🐍 bot.py                  # Servidor FastAPI (porta 8000)
├── 🧠 ai_engine.py            # Motor: FAQ keyword → RAG → DeepSeek
├── 📚 knowledge_base.py       # Busca vetorial TF-IDF (RAG leve)
│
├── 📋 knowledge/
│   ├── faq.json               # Perguntas e respostas do evento
│   └── documentos/            # PDFs, TXTs, MDs (futuro)
│
├── 📱 whatsapp-bridge/
│   ├── index.js               # Conexão WhatsApp (Baileys v7)
│   └── package.json           # Dependências Node.js
│
├── 📦 requirements.txt        # Dependências Python
├── 🔑 .env                    # Chave DeepSeek (não versionar!)
├── 📖 README.md               # Esta documentação
└── 📁 venv/                   # Ambiente virtual Python
```

## ⚡ Fluxo de Resposta

```
Usuário envia mensagem no WhatsApp
    │
    ▼
📱 Bridge (Node.js / Baileys)
    │ HTTP POST → /webhook
    ▼
🐍 Servidor Python (bot.py)
    │
    ▼
🧠 AI Engine (ai_engine.py)
    │
    ├── 1️⃣ Keyword match na FAQ?
    │       ├── ✅ SIM → Resposta direta (0 tokens gastos)
    │       └── ❌ NÃO →
    │               │
    │               ▼
    │         2️⃣ RAG (TF-IDF + cosseno)
    │               ├── Busca SÓ os trechos relevantes
    │               └── Manda ~50-200 tokens pra IA
    │                      │
    │                      ▼
    │                🤖 DeepSeek API
    │                      │
    │                      ▼
    └── ✅ Resposta volta pro WhatsApp
```

## 💰 Economia com RAG

| Métrica | Sem RAG | Com RAG |
|---------|---------|---------|
| Tokens por consulta | ~2.000 (FAQ inteira) | ~50-200 (só relevante) |
| Custo por 1.000 consultas | ~$0.30 | ~$0.02-0.03 |
| Economia | — | **~90%** 🎉 |

## 🚀 Como Rodar

### 1. Servidor Python

```bash
cd whatsapp-bot
source venv/bin/activate
python bot.py
```

### 2. Conexão WhatsApp

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

## 🔧 Arquivos em Detalhe

### `bot.py` — Servidor FastAPI
- Endpoint `POST /webhook` — recebe mensagens do WhatsApp
- Endpoint `GET /health` — health check
- Executa com `uvicorn` em `0.0.0.0:8000`

### `ai_engine.py` — Motor de IA
- `buscar_na_faq()` — match por palavras-chave (rápido, sem API)
- `perguntar_ia()` — fallback com RAG + DeepSeek
- `remover_acentos()` — normalização pra comparação

### `knowledge_base.py` — Busca Vetorial (RAG)
- `BuscadorRAG` — classe principal
- Usa `TfidfVectorizer` do scikit-learn
- `obter_contexto_para_ia()` — monta contexto só com trechos relevantes
- 21 documentos indexados da FAQ

### `whatsapp-bridge/index.js` — Conexão WhatsApp
- Usa `@whiskeysockets/baileys` v7 (⚠️ v6 NÃO funciona)
- Reconexão automática se cair
- Salva sessão (QR só na primeira vez)

## 📝 FAQ — Como Editar

Arquivo: `knowledge/faq.json`

```json
{
  "empresa": { "nome": "Triângulo Entretenimento" },
  "evento": { "nome": "Arena Triângulo", "local": "Castelli Eventos" },
  "categorias": {
    "minha_categoria": {
      "label": "Minha Categoria",
      "perguntas": [
        {
          "id": "exemplo_1",
          "palavras_chave": ["keyword1", "keyword2"],
          "pergunta": "O que o usuário pergunta?",
          "resposta": "O que o bot responde"
        }
      ]
    }
  }
}
```

> ⚠️ **Dica:** Depois de editar a FAQ, reinicie o servidor Python pra recarregar o RAG

## 📱 Comandos do WhatsApp

O bot entende perguntas como:

| Categoria | Exemplos |
|-----------|----------|
| 📅 Datas | "Quando vai ser?" "Que horas abre?" |
| 🎟️ Ingressos | "Quanto custa?" "Onde compra?" "Tem meia?" |
| 🎵 Atrações | "Quem vai tocar?" "Quais bandas?" |
| 🚫 Regras | "O que não pode levar?" "Precisa de documento?" |
| 📞 Contato | "Qual o Instagram?" "Telefone pra contato?" |

## 🔐 Dependências

**Python** (requirements.txt):
- `fastapi` + `uvicorn` — servidor web
- `httpx` — chamadas HTTP pra DeepSeek
- `python-dotenv` — variáveis de ambiente
- `scikit-learn` — TF-IDF (RAG leve)
- `pypdf2` + `markdown` — leitura de documentos (futuro)

**Node.js** (whatsapp-bridge/package.json):
- `@whiskeysockets/baileys` v7.0.0-rc13 — conexão WhatsApp
- `qrcode-terminal` — QR Code no terminal
- `axios` — chamadas pro servidor Python

## 🔮 Próximos Passos

- [ ] Migrar de TF-IDF pra **ChromaDB + embeddings** (mais preciso)
- [ ] Adicionar suporte a **documentos PDF** (descritivo do evento)
- [ ] Dashboard de **estatísticas** (quantas perguntas, quais as mais frequentes)
- [ ] **Filtro de contatos** (whitelist pra não responder amigos)

---

Projeto: **Triângulo Entretenimento** — Arena Triângulo  
Stack: Python FastAPI + Baileys + DeepSeek + TF-IDF RAG  
Idioma: 🇧🇷 Português do Brasil
