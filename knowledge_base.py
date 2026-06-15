"""
╔══════════════════════════════════════════╗
║   KNOWLEDGE BASE — Busca Inteligente   ║
║   RAG via TF-IDF + Similaridade        ║
╚══════════════════════════════════════════╝

Como funciona:
1. Cada pergunta da FAQ vira um "documento" vetorizado
2. Quando chega uma pergunta nova, busca os mais parecidos
3. Retorna APENAS os trechos relevantes pra IA

Vantagens sobre mandar a FAQ inteira:
✅ MUITO menos tokens (só o relevante)
✅ Mais rápido
✅ Respostas mais precisas
✅ 100% local, sem API, sem download de modelo
"""

import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import numpy as np

# ──────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────

PASTA_ATUAL = Path(__file__).parent
CAMINHO_FAQ = PASTA_ATUAL / "knowledge" / "faq.json"

# Quantos trechos retornar na busca
QTD_RESULTADOS = 3

# ──────────────────────────────────────────
# EXTRAIR TEXTO DA FAQ
# ──────────────────────────────────────────

def carregar_faq() -> dict:
    """Carrega a FAQ do arquivo JSON."""
    try:
        with open(CAMINHO_FAQ, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️  FAQ não encontrada: {CAMINHO_FAQ}")
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️  FAQ com erro de JSON: {e}")
        return {}


def extrair_documentos() -> list[dict]:
    """
    Transforma cada pergunta da FAQ em um "documento" buscável.
    
    Cada documento tem:
    - texto: o conteúdo que será vetorizado (pergunta + palavras-chave + resposta)
    - pergunta: a pergunta original
    - resposta: a resposta
    - categoria: a categoria
    - id: identificador único
    """
    faq = carregar_faq()
    documentos = []

    if not faq or "categorias" not in faq:
        return documentos

    # 1. Cada pergunta da FAQ vira um documento
    for cat_id, cat_dados in faq["categorias"].items():
        cat_label = cat_dados.get("label", cat_id)
        for pergunta in cat_dados.get("perguntas", []):
            # O texto buscável = pergunta + palavras-chave + resposta
            texto_busca = " ".join([
                pergunta.get("pergunta", ""),
                " ".join(pergunta.get("palavras_chave", [])),
                pergunta.get("resposta", "")[:200]  # só início da resposta
            ])
            
            documentos.append({
                "id": pergunta.get("id", f"{cat_id}_sem_id"),
                "categoria": cat_label,
                "pergunta": pergunta.get("pergunta", ""),
                "palavras_chave": pergunta.get("palavras_chave", []),
                "resposta": pergunta.get("resposta", ""),
                "texto_busca": texto_busca,
            })

    # 2. Adiciona um documento com a descrição geral do evento/empresa
    empresa = faq.get("empresa", {})
    evento = faq.get("evento", {})
    if empresa or evento:
        texto_geral = (
            f"{empresa.get('nome', '')} - {empresa.get('descricao', '')}. "
            f"Evento: {evento.get('nome', '')}. {evento.get('descricao', '')}. "
            f"Local: {evento.get('local', '')}. Classificação: {evento.get('classificacao', '')}."
        )
        documentos.append({
            "id": "info_geral",
            "categoria": "Geral",
            "pergunta": "Informações gerais do evento",
            "resposta": "",
            "texto_busca": texto_geral,
        })

    return documentos


# ──────────────────────────────────────────
# VETORIZADOR TF-IDF
# ──────────────────────────────────────────

class BuscadorRAG:
    """
    Buscador que usa TF-IDF pra encontrar os trechos mais relevantes.
    
    Uso:
        buscador = BuscadorRAG()
        buscador.carregar_documentos()
        resultados = buscador.buscar("Tem estacionamento?")
    """

    def __init__(self):
        self.documentos = []
        self.vectorizer = TfidfVectorizer(
            max_features=1000,     # máximo de palavras no vocabulário
            stop_words=None,        # não remove stopwords (português)
            ngram_range=(1, 2),     # considera palavras isoladas E pares
            lowercase=True,
            strip_accents="unicode",  # lida com acentos
            max_df=0.8,             # ignora palavras muito comuns
            min_df=1,               # mínimo de docs que a palavra aparece
        )
        self.vetores = None
        self.pronto = False

    def carregar_documentos(self):
        """Carrega os documentos da FAQ e gera os vetores TF-IDF."""
        self.documentos = extrair_documentos()

        if not self.documentos:
            print("⚠️  Nenhum documento carregado!")
            self.pronto = False
            return

        # Pega só os textos pra vetorizar
        textos = [doc["texto_busca"] for doc in self.documentos]
        
        # Gera os vetores TF-IDF
        self.vetores = self.vectorizer.fit_transform(textos)
        self.pronto = True
        
        print(f"📚 RAG carregado: {len(self.documentos)} documentos na base")

    def buscar(self, pergunta: str, top_k: int = QTD_RESULTADOS) -> list[dict]:
        """
        Busca os documentos mais relevantes para a pergunta.
        
        Args:
            pergunta: texto da pergunta do usuário
            top_k: quantos resultados retornar
            
        Returns:
            Lista de dicts com os documentos mais relevantes
        """
        if not self.pronto:
            return []

        # Vetoriza a pergunta
        pergunta_vetor = self.vectorizer.transform([pergunta])

        # Calcula similaridade com todos os documentos
        similaridades = cosine_similarity(pergunta_vetor, self.vetores)[0]

        # Pega os índices dos mais similares
        indices_top = similaridades.argsort()[-top_k:][::-1]

        resultados = []
        for idx in indices_top:
            score = float(similaridades[idx])
            # Só retorna se tiver similaridade mínima
            if score > 0.05:
                doc = self.documentos[idx].copy()
                doc["score"] = score
                resultados.append(doc)

        return resultados

    def obter_contexto_para_ia(self, pergunta: str) -> str:
        """
        Monta o contexto pra enviar pra IA, só com os trechos relevantes.
        
        Em vez de mandar a FAQ INTEIRA, manda só os TOP trechos
        que combinam com a pergunta.
        """
        resultados = self.buscar(pergunta)

        if not resultados:
            return ""

        # Monta o contexto compacto
        contexto = "📋 INFORMAÇÕES RELEVANTES:\n\n"

        for i, doc in enumerate(resultados, 1):
            if doc["resposta"]:
                # É uma pergunta da FAQ
                contexto += f"[{i}] {doc['pergunta']}\n"
                contexto += f"Resposta: {doc['resposta']}\n\n"
            else:
                # É o documento geral
                contexto += f"[{i}] {doc['texto_busca']}\n\n"

        contexto += "⚠️ Use APENAS essas informações para responder. "
        contexto += "Se não encontrar a resposta aqui, informe que não sabe."

        return contexto


# ──────────────────────────────────────────
# INSTÂNCIA GLOBAL (singleton)
# ──────────────────────────────────────────

# Cria e carrega uma instância global
# O carregamento acontece na primeira importação
buscador = BuscadorRAG()
buscador.carregar_documentos()


# ──────────────────────────────────────────
# TESTE RÁPIDO (se executado diretamente)
# ──────────────────────────────────────────

if __name__ == "__main__":
    print("🧪 Testando Knowledge Base RAG...\n")

    perguntas_teste = [
        "Qual o horário do evento?",
        "Tem estacionamento?",
        "Quanto custa o ingresso?",
        "Pode levar comida?",
        "Qual o instagram?",
        "Aceita cartão?"
    ]

    for pergunta in perguntas_teste:
        print(f"📩 Pergunta: {pergunta}")
        resultados = buscador.buscar(pergunta)
        print(f"📊 Total de resultados: {len(resultados)}")
        for doc in resultados:
            print(f"   → [{doc['score']:.3f}] {doc['pergunta'][:60]}...")
        print()

    print("📄 Contexto completo pra IA:")
    contexto = buscador.obter_contexto_para_ia("Tem estacionamento?")
    print(contexto)
