"""
╔══════════════════════════════════════════╗
║   SERVIDOR PRINCIPAL - Chatbot WhatsApp ║
║   FastAPI + AI Engine                   ║
╚══════════════════════════════════════════╝

Este servidor:
- Recebe mensagens via API (HTTP)
- Processa com o AI Engine
- Retorna a resposta

Depois o WhatsApp Bridge (Node.js) vai se conectar aqui.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

# ──────────────────────────────────────────
# Importa nosso AI Engine
# ──────────────────────────────────────────

# Adiciona a pasta atual ao path (pra importar o ai_engine)
PASTA_ATUAL = Path(__file__).parent
sys.path.insert(0, str(PASTA_ATUAL))

from ai_engine import processar_mensagem

# ──────────────────────────────────────────
# CONFIGURAÇÃO DE LOG
# ──────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
logger = logging.getLogger("whatsapp-bot")

# ──────────────────────────────────────────
# CRIA O SERVIDOR FASTAPI
# ──────────────────────────────────────────

app = FastAPI(
    title="🤖 TechSolutions Bot",
    description="Chatbot com IA para WhatsApp",
    version="1.0.0",
)

# Libera acesso de qualquer lugar (necessário pro WhatsApp Bridge)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────
# MODELOS DE DADOS (schemas)
# ──────────────────────────────────────────

class MensagemRequest(BaseModel):
    """
    Formato da mensagem que chega do WhatsApp.

    Exemplo:
    {
        "de": "5511999998888",
        "mensagem": "Qual o horário de funcionamento?",
        "nome": "João Silva"  # opcional
    }
    """
    de: str = Field(..., description="Número do WhatsApp do usuário")
    mensagem: str = Field(..., description="Texto da mensagem")
    nome: Optional[str] = Field(None, description="Nome do contato (opcional)")


class MensagemResponse(BaseModel):
    """
    Formato da resposta que volta pro WhatsApp.
    """
    para: str
    resposta: str
    timestamp: str
    metodo: str  # "faq" ou "ia"


# ──────────────────────────────────────────
# ENDPOINTS (rotas da API)
# ──────────────────────────────────────────

@app.get("/")
async def root():
    """Página inicial — mostra que o bot está online."""
    return {
        "status": "online",
        "bot": "TechSolutions WhatsApp Bot",
        "versao": "1.0.0",
    }


@app.get("/health")
async def health():
    """Health check (verifica se o servidor está saudável)."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/webhook", response_model=MensagemResponse)
async def webhook(dados: MensagemRequest):
    """
    📩 ENDPOINT PRINCIPAL
    Recebe a mensagem do WhatsApp e retorna a resposta.

    Chamado pelo WhatsApp Bridge (Node.js) a cada mensagem.
    """
    numero = dados.de
    mensagem = dados.mensagem
    nome = dados.nome or "Cliente"

    logger.info(f"📩 Mensagem de {nome} ({numero}): {mensagem[:50]}...")

    try:
        # Processa a mensagem com nosso AI Engine
        resposta = await processar_mensagem(mensagem)

        logger.info(f"✅ Resposta enviada para {numero}")

        # Descobre se veio da FAQ ou da IA (pelo tamanho/tipo)
        # FAQ tem respostas mais curtas e diretas
        metodo = "faq" if len(resposta) < 500 else "ia"

        return MensagemResponse(
            para=numero,
            resposta=resposta,
            timestamp=datetime.now().isoformat(),
            metodo=metodo,
        )

    except Exception as erro:
        logger.error(f"❌ Erro ao processar mensagem: {erro}")
        raise HTTPException(status_code=500, detail=str(erro))


# ──────────────────────────────────────────
# PONTO DE ENTRADA
# ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print("""
    ╔══════════════════════════════════════╗
    ║   🤖 TechSolutions Bot              ║
    ║   Rodando em http://localhost:8000   ║
    ║                                      ║
    ║   📄 Docs: http://localhost:8000/docs║
    ╚══════════════════════════════════════╝
    """)

    uvicorn.run(
        "bot:app",
        host="0.0.0.0",  # Aceita conexões de qualquer lugar na rede local
        port=8000,
        reload=True,     # Auto-reload quando editar o código
    )
