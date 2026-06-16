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
from extractor import event_extractor
from database import db_manager

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

        # Descobre se veio do ChromaDB ou da IA (pelo tamanho/tipo)
        # ChromaDB tem respostas mais curtas e diretas
        metodo = "chromadb" if len(resposta) < 500 else "ia"

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
# ENDPOINTS DE EXTRAÇÃO DE EVENTOS
# ──────────────────────────────────────────

class ExtrairRequest(BaseModel):
    """Requisição para extrair evento de uma URL."""
    url: str = Field(..., description="URL do evento na bilheteria")


class ExtrairResponse(BaseModel):
    """Resposta da extração de evento."""
    success: bool
    evento_id: Optional[str] = None
    nome: Optional[str] = None
    data: Optional[str] = None
    local: Optional[str] = None
    message: str


@app.post("/extrair", response_model=ExtrairResponse)
async def extrair_evento(dados: ExtrairRequest):
    """
    🎯 EXTRATOR DE EVENTOS
    Extrai dados de um evento a partir da URL da bilheteria.

    Suporta: BaladAPP, Meu Bilhete, Ticket360, GuicheLive, IngressoLive, Q2 Ingressos
    """
    url = dados.url

    logger.info(f"🔍 Extraindo evento de: {url}")

    try:
        evento_id = await event_extractor.extrair_e_salvar(url)

        if evento_id:
            # Busca o evento no banco para retornar os dados
            eventos = db_manager.listar_eventos()
            evento = next((e for e in eventos if e["id"] == evento_id), None)

            if evento:
                return ExtrairResponse(
                    success=True,
                    evento_id=evento_id,
                    nome=evento["metadata"].get("nome"),
                    data=evento["metadata"].get("data"),
                    local=evento["metadata"].get("local"),
                    message=f"✅ Evento extraído com sucesso!"
                )

        return ExtrairResponse(
            success=False,
            message="❌ Não foi possível extrair dados do evento"
        )

    except Exception as erro:
        logger.error(f"❌ Erro ao extrair evento: {erro}")
        return ExtrairResponse(
            success=False,
            message=f"❌ Erro: {str(erro)}"
        )


@app.get("/eventos")
async def listar_eventos():
    """
    📋 LISTA EVENTOS
    Retorna todos os eventos armazenados no banco.
    """
    eventos = db_manager.listar_eventos()
    return {
        "total": len(eventos),
        "eventos": eventos
    }


@app.delete("/eventos/{evento_id}")
async def remover_evento(evento_id: str):
    """
    🗑️ REMOVE EVENTO
    Remove um evento do banco pelo ID.
    """
    success = db_manager.remover_evento(evento_id)
    return {"success": success, "evento_id": evento_id}


@app.get("/estatisticas")
async def obter_estatisticas():
    """
    📊 ESTATÍSTICAS
    Retorna estatísticas do banco de dados.
    """
    return db_manager.obter_estatisticas()


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
