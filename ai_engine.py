"""
╔══════════════════════════════════════════╗
║   AI ENGINE - Motor de Respostas        ║
║   Chatbot WhatsApp Triângulo            ║
╚══════════════════════════════════════════╝

Como funciona:
1. Busca no ChromaDB (eventos extraídos)
2. Se não achar, usa a DeepSeek API com contexto do ChromaDB
3. A IA responde APENAS com base nos dados fornecidos
"""

import os
from typing import Optional

import httpx
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# Importa o gerenciador do banco de dados
from database import db_manager

# ──────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────

# Chave da API DeepSeek (vem do .env)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MODELO_IA = "deepseek-chat"


# ──────────────────────────────────────────
# BUSCA NO CHROMADB
# ──────────────────────────────────────────

def buscar_no_chromadb(mensagem: str) -> Optional[str]:
    """
    Busca eventos no ChromaDB usando similaridade vetorial.
    Retorna o contexto encontrado ou None se não achar.
    """
    try:
        # Busca eventos similares no ChromaDB
        resultados = db_manager.buscar_eventos(mensagem, n_results=3)
        
        if not resultados:
            return None
        
        # Monta o contexto com os eventos encontrados
        contexto_parts = []
        
        for evento in resultados:
            meta = evento.get("metadata", {})
            nome = meta.get("nome", "Evento")
            data = meta.get("data", "")
            local = meta.get("local", "")
            horario = meta.get("horario", "")
            
            if nome:
                linha = f"📅 {nome}"
                if data:
                    linha += f" — Data: {data}"
                if horario:
                    linha += f" às {horario}"
                if local:
                    linha += f" — Local: {local}"
                contexto_parts.append(linha)
        
        if contexto_parts:
            return "\n".join(contexto_parts)
        
        return None
        
    except Exception as e:
        print(f"⚠️  Erro ao buscar no ChromaDB: {e}")
        return None


# ──────────────────────────────────────────
# IA - DEEPSEEK
# ──────────────────────────────────────────

async def perguntar_ia(mensagem: str) -> str:
    """
    Envia a pergunta para a DeepSeek API com CONTEXTO do ChromaDB.
    
    Busca eventos relevantes no ChromaDB e usa como contexto para a IA.
    """
    if not DEEPSEEK_API_KEY:
        return ("⚠️  Ainda não configurei a chave da IA!\n\n"
                "Peça ao admin para configurar a DEEPSEEK_API_KEY no arquivo .env")

    # 🔍 Busca contexto no ChromaDB
    contexto = buscar_no_chromadb(mensagem)
    
    if not contexto:
        contexto = "Nenhum evento encontrado na base de dados."
    
    # Estatística de economia
    tokens_approx = len(contexto) // 4
    print(f"📊 RAG: {tokens_approx} tokens enviados pra IA")

    # Monta o prompt com sistema + contexto
    prompt_sistema = f"""Você é o assistente virtual da Triângulo Entretenimento, 
produtora de eventos em Uberlândia/MG.

REGRAS:
- Responda APENAS com base nas informações abaixo
- Se não encontrar a resposta, diga que não sabe e sugira contato humano
- Responda em português do Brasil
- Seja educado, profissional e use emojis com moderação
- Mantenha respostas curtas e diretas

EVENTOS DISPONÍVEIS:
{contexto}"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    corpo = {
        "model": MODELO_IA,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": mensagem}
        ],
        "temperature": 0.3,
        "max_tokens": 500,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resposta = await client.post(DEEPSEEK_URL, json=corpo, headers=headers)
            resposta.raise_for_status()
            dados = resposta.json()
            return dados["choices"][0]["message"]["content"]

    except httpx.TimeoutException:
        return "❌ Desculpe, a IA demorou muito pra responder. Tente de novo!"
    except httpx.HTTPStatusError as erro:
        print(f"⚠️  Erro na API DeepSeek: {erro.response.status_code} - {erro.response.text}")
        return "❌ Erro ao consultar a IA. O suporte técnico foi avisado."
    except Exception as erro:
        print(f"⚠️  Erro inesperado: {erro}")
        return "❌ Ocorreu um erro inesperado. Tente novamente mais tarde."


# ──────────────────────────────────────────
# FUNÇÃO PRINCIPAL
# ──────────────────────────────────────────

async def processar_mensagem(mensagem: str) -> str:
    """
    Processa a mensagem do usuário e retorna a melhor resposta.

    Fluxo:
    1. Busca no ChromaDB (eventos extraídos)
    2. Se não achar, pergunta pra IA (DeepSeek com contexto)
    3. Retorna a resposta
    """
    if not mensagem or not mensagem.strip():
        return "Olá! Como posso ajudar? 😊"

    print(f"📩 Mensagem recebida: {mensagem}")

    # PASSO 1: Busca no ChromaDB
    print("🔍 Buscando no ChromaDB...")
    resposta_chromadb = buscar_no_chromadb(mensagem)
    if resposta_chromadb:
        print("✅ Resposta encontrada no ChromaDB")
        return resposta_chromadb

    # PASSO 2: Se não achou, pergunta pra IA
    print("🤔 Não achei na base. Perguntando pra IA...")
    resposta_ia = await perguntar_ia(mensagem)
    return resposta_ia
