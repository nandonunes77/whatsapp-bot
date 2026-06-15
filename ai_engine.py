"""
╔══════════════════════════════════════════╗
║   AI ENGINE - Motor de Respostas        ║
║   Chatbot WhatsApp TechSolutions        ║
╚══════════════════════════════════════════╝

Como funciona:
1. Tenta encontrar a pergunta na FAQ (match por palavras-chave)
2. Se não achar, usa a DeepSeek API com o contexto da FAQ
3. A IA responde APENAS com base nos dados fornecidos
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# Importa o buscador RAG (só os trechos relevantes, não a FAQ inteira)
from knowledge_base import buscador

# ──────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────

# Caminho até a pasta onde este arquivo está
PASTA_ATUAL = Path(__file__).parent
CAMINHO_FAQ = PASTA_ATUAL / "knowledge" / "faq.json"

# Chave da API DeepSeek (vem do .env)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MODELO_IA = "deepseek-chat"


# ──────────────────────────────────────────
# CARREGAR FAQ
# ──────────────────────────────────────────

def carregar_faq() -> dict:
    """Carrega o arquivo FAQ e retorna como dicionário."""
    try:
        with open(CAMINHO_FAQ, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except FileNotFoundError:
        print(f"⚠️  Arquivo FAQ não encontrado em: {CAMINHO_FAQ}")
        return {"categorias": {}}
    except json.JSONDecodeError as erro:
        print(f"⚠️  Erro ao ler FAQ (JSON inválido): {erro}")
        return {"categorias": {}}


def listar_todas_perguntas() -> list[dict]:
    """Retorna uma lista com TODAS as perguntas do FAQ."""
    faq = carregar_faq()
    todas = []
    for categoria, dados in faq.get("categorias", {}).items():
        for pergunta in dados.get("perguntas", []):
            pergunta["categoria"] = dados.get("label", categoria)
            todas.append(pergunta)
    return todas


# ──────────────────────────────────────────
# BUSCA NA FAQ (MÉTODO 1: Palavras-chave)
# ──────────────────────────────────────────

def buscar_na_faq(mensagem: str) -> Optional[str]:
    """
    Procura a mensagem na FAQ usando palavras-chave.
    Retorna a resposta se encontrar um match bom, ou None se não achar.
    """
    perguntas = listar_todas_perguntas()
    mensagem_lower = mensagem.lower()

    # Remove acentos pra comparação ficar mais precisa
    mensagem_limpa = remover_acentos(mensagem_lower)

    melhor_match = None
    maior_pontuacao = 0

    for pergunta in perguntas:
        pontuacao = 0

        # Verifica cada palavra-chave
        for palavra in pergunta.get("palavras_chave", []):
            palavra_limpa = remover_acentos(palavra.lower())
            if palavra_limpa in mensagem_limpa:
                pontuacao += 1

        # Se todas as palavras-chave aparecerem, é match perfeito
        total_palavras = len(pergunta.get("palavras_chave", []))
        if total_palavras > 0 and pontuacao == total_palavras:
            return pergunta["resposta"]

        # Guarda o melhor match parcial
        if pontuacao > maior_pontuacao:
            maior_pontuacao = pontuacao
            melhor_match = pergunta

    # Se tiver pelo menos 1 palavra-chave match, retorna a resposta
    if maior_pontuacao >= 1:
        return melhor_match["resposta"]

    return None


def remover_acentos(texto: str) -> str:
    """Remove acentos de uma string para comparação."""
    acentos = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c',
        'ñ': 'n',
    }
    for com_acento, sem_acento in acentos.items():
        texto = texto.replace(com_acento, sem_acento)
    return texto


# ──────────────────────────────────────────
# IA - DEEPSEEK (MÉTODO 2: RAG + Inteligência)
# ──────────────────────────────────────────

async def perguntar_ia(mensagem: str) -> str:
    """
    Envia a pergunta para a DeepSeek API com CONTEXTO OTIMIZADO (RAG).
    
    Em vez de mandar a FAQ INTEIRA (~2.000 tokens), a gente:
    1. Busca SÓ os trechos relevantes pra pergunta (TF-IDF)
    2. Manda APENAS esses trechos pra IA (~50-200 tokens)
    
    Economia: ~90% menos tokens por consulta! 🎉
    """
    if not DEEPSEEK_API_KEY:
        return ("⚠️  Ainda não configurei a chave da IA!\n\n"
                "Peça ao admin para configurar a DEEPSEEK_API_KEY no arquivo .env")

    # 🔍 PASSO 1: Busca SÓ os trechos relevantes (RAG)
    contexto = buscador.obter_contexto_para_ia(mensagem)

    if not contexto:
        # Nenhum trecho relevante encontrado
        return ("Não encontrei essa informação nos meus dados. "
                "Vou transferir para um atendente humano.")

    # Estatística de economia
    tokens_approx = len(contexto) // 4
    print(f"📊 RAG: {tokens_approx} tokens enviados pra IA (vs ~2000 sem RAG)")

    # 📋 PASSO 2: Monta o prompt com sistema + contexto pequeno
    prompt_sistema = f"""Você é o assistente virtual da Triângulo Entretenimento, 
produtora do evento Arena Triângulo em Uberlândia/MG.

REGRAS:
- Responda APENAS com base nas informações abaixo
- Se não encontrar a resposta, diga que não sabe e sugira contato humano
- Responda em português do Brasil
- Seja educado, profissional e use emojis com moderação
- Mantenha respostas curtas e diretas

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
    1. Tenta achar na FAQ (match por palavras-chave)
    2. Se não achar, pergunta pra IA (DeepSeek)
    3. Retorna a resposta
    """
    if not mensagem or not mensagem.strip():
        return "Olá! Como posso ajudar? 😊"

    print(f"📩 Mensagem recebida: {mensagem}")

    # PASSO 1: Tenta encontrar na FAQ
    resposta_faq = buscar_na_faq(mensagem)
    if resposta_faq:
        print("✅ Resposta encontrada na FAQ")
        return resposta_faq

    # PASSO 2: Se não achou, pergunta pra IA
    print("🤔 Não achei na FAQ. Perguntando pra IA...")
    resposta_ia = await perguntar_ia(mensagem)
    return resposta_ia
