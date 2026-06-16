"""
╔══════════════════════════════════════════╗
║   GERADOR DE FAQ                        ║
║   Extrai URLs → Gera faq.json           ║
╚══════════════════════════════════════════╝

Uso:
    python gerador_faq.py https://baladapp.com.br/... https://...
    python gerador_faq.py --urls urls.txt
"""

import json
import sys
import re
import unicodedata
from pathlib import Path

from extrator import extrair_de_texto, extrair_de_url, extrair_de_cache, EventoData


PASTA_ATUAL = Path(__file__).parent
CAMINHO_FAQ = PASTA_ATUAL / "knowledge" / "faq.json"


def normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def slug(texto: str) -> str:
    norm = normalizar(texto)
    return re.sub(r"[^a-z0-9]+", "_", norm).strip("_")[:40]


# ════════════════════════════════════════
# GERAR PERGUNTAS POR CATEGORIA
# ════════════════════════════════════════

def gerar_datas(ev: EventoData, idx: int) -> list[dict]:
    perguntas = []
    if ev.data or ev.horario:
        data_str = f"{ev.data}" if ev.data else ""
        horario_str = f" às {ev.horario}" if ev.horario else ""
        local_str = f"\n📍 Local: {ev.local}, {ev.cidade}" if ev.cidade else ""

        perguntas.append({
            "id": f"evento_{idx}_data",
            "palavras_chave": [
                "data", "quando", "dia", "acontece",
                normalizar(ev.artista), normalizar(ev.nome.split("-")[0].strip())[:20],
            ],
            "pergunta": f"Quando vai ser {ev.artista or ev.nome}?",
            "resposta": f"📅 **{ev.nome}**\nData: {data_str}{horario_str}{local_str}",
        })

    if ev.local:
        perguntas.append({
            "id": f"evento_{idx}_local",
            "palavras_chave": [
                "onde", "local", "lugar", "endereco", normalizar(ev.cidade.split("/")[0]),
            ],
            "pergunta": f"Onde vai ser {ev.artista or ev.nome}?",
            "resposta": f"📍 **{ev.local or ev.nome}** — {ev.cidade}",
        })

    return perguntas


def gerar_ingressos(ev: EventoData, idx: int) -> list[dict]:
    perguntas = []

    if ev.setores:
        setores_texto = ""
        for s in ev.setores:
            preco = f" — {s['preco']}" if s.get("preco") else ""
            setores_texto += f"\n🎟️ **{s['nome']}**{preco}"

        perguntas.append({
            "id": f"evento_{idx}_setores",
            "palavras_chave": [
                "setor", "ingresso", "tipo", "opcao", normalizar(ev.artista),
            ],
            "pergunta": f"Quais os setores/ingressos de {ev.artista or ev.nome}?",
            "resposta": f"Setores disponíveis:{setores_texto}",
        })

    if ev.meia_entrada:
        perguntas.append({
            "id": f"evento_{idx}_meia",
            "palavras_chave": [
                "meia", "solidaria", "desconto", "alimento", normalizar(ev.artista),
            ],
            "pergunta": f"Tem meia-entrada para {ev.artista or ev.nome}?",
            "resposta": f"🎫 **Meia-entrada:** {ev.meia_entrada}",
        })

    return perguntas


def gerar_regras(ev: EventoData, idx: int) -> list[dict]:
    perguntas = []

    if ev.classificacao:
        perguntas.append({
            "id": f"evento_{idx}_classif",
            "palavras_chave": [
                "idade", "classificacao", "menor", normalizar(ev.artista),
            ],
            "pergunta": f"Qual a classificação de {ev.artista or ev.nome}?",
            "resposta": f"🔞 Classificação: **{ev.classificacao}**",
        })

    if ev.itens_proibidos:
        itens = ", ".join(ev.itens_proibidos[:6])
        perguntas.append({
            "id": f"evento_{idx}_proibido",
            "palavras_chave": ["proibido", "levar", "pode levar", normalizar(ev.artista)],
            "pergunta": f"O que é proibido levar em {ev.artista or ev.nome}?",
            "resposta": f"🚫 **Itens proibidos:** {itens}. Consulte o regulamento completo do evento.",
        })

    if ev.politica_cancelamento:
        perguntas.append({
            "id": f"evento_{idx}_cancel",
            "palavras_chave": [
                "cancelar", "reembolso", "cancelamento", normalizar(ev.artista),
            ],
            "pergunta": f"Posso cancelar o ingresso de {ev.artista or ev.nome}?",
            "resposta": f"✅ **Cancelamento:** {ev.politica_cancelamento}",
        })

    return perguntas


def gerar_contato(ev: EventoData, idx: int) -> list[dict]:
    perguntas = []
    if not ev.contato:
        return perguntas

    partes = []
    if ev.contato.get("instagram"):
        partes.append(f"📱 Instagram: **{ev.contato['instagram']}**")
    if ev.contato.get("telefone"):
        partes.append(f"📞 Telefone: **{ev.contato['telefone']}**")
    if ev.contato.get("email"):
        partes.append(f"📧 E-mail: **{ev.contato['email']}**")

    if partes:
        perguntas.append({
            "id": f"evento_{idx}_contato",
            "palavras_chave": ["contato", "instagram", "telefone", normalizar(ev.artista)],
            "pergunta": f"Como falar com {ev.artista or ev.nome}?",
            "resposta": "\n".join(partes),
        })

    return perguntas


def gerar_info_geral(ev: EventoData, idx: int) -> list[dict]:
    """Gera uma pergunta-resumo do evento."""
    if not ev.nome and not ev.artista:
        return []

    resposta_partes = [f"🎉 **{ev.nome}**"]
    if ev.artista and ev.artista != ev.nome:
        resposta_partes.append(f"🎤 Artista: {ev.artista}")
    if ev.data:
        resposta_partes.append(f"📅 Data: {ev.data}" + (f" às {ev.horario}" if ev.horario else ""))
    if ev.cidade:
        resposta_partes.append(f"📍 Local: {ev.local or ev.nome} — {ev.cidade}")
    if ev.classificacao:
        resposta_partes.append(f"🔞 Classificação: {ev.classificacao}")
    if ev.plataforma:
        resposta_partes.append(f"🎫 Plataforma: {ev.plataforma}")
    if ev.url:
        resposta_partes.append(f"🔗 {ev.url}")

    return [{
        "id": f"evento_{idx}_geral",
        "palavras_chave": [
            normalizar(ev.artista) if ev.artista else "",
            normalizar(ev.nome.split("-")[0].strip())[:15],
            "evento", "show",
        ],
        "pergunta": f"Me fale sobre {ev.artista or ev.nome}",
        "resposta": "\n".join(resposta_partes),
    }]


# ════════════════════════════════════════
# EVENTO → CATEGORIAS FAQ
# ════════════════════════════════════════

def evento_para_faq(ev: EventoData, idx: int) -> dict:
    """Converte um EventoData em categorias do faq.json."""
    categorias = {}

    def add_categoria(cat_id, label, perguntas):
        if perguntas:
            categorias[cat_id] = {"label": label, "perguntas": perguntas}

    nome_short = slug(ev.artista or ev.nome)

    add_categoria(f"datas_{nome_short}", f"📅 {ev.artista or ev.nome} — Datas",
                  gerar_datas(ev, idx))
    add_categoria(f"ingressos_{nome_short}", f"🎟️ {ev.artista or ev.nome} — Ingressos",
                  gerar_ingressos(ev, idx))
    add_categoria(f"regras_{nome_short}", f"🚫 {ev.artista or ev.nome} — Regras",
                  gerar_regras(ev, idx))
    add_categoria(f"contato_{nome_short}", f"📞 {ev.artista or ev.nome} — Contato",
                  gerar_contato(ev, idx))
    add_categoria(f"geral_{nome_short}", f"🎉 {ev.artista or ev.nome} — Info Geral",
                  gerar_info_geral(ev, idx))

    return categorias


# ════════════════════════════════════════
# MERGE COM FAQ EXISTENTE
# ════════════════════════════════════════

def carregar_faq_existente() -> dict:
    try:
        with open(CAMINHO_FAQ, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"empresa": {}, "evento": {}, "categorias": {}}


def merge_faqs(faq_atual: dict, novas_categorias: dict) -> dict:
    """Adiciona novas categorias sem sobrescrever as existentes."""
    faq = faq_atual.copy()
    faq["categorias"] = faq.get("categorias", {})
    faq["categorias"].update(novas_categorias)
    return faq


def salvar_faq(faq: dict):
    with open(CAMINHO_FAQ, "w", encoding="utf-8") as f:
        json.dump(faq, f, ensure_ascii=False, indent=2)
    print(f"✅ FAQ salva em: {CAMINHO_FAQ}")


# ════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ════════════════════════════════════════

def gerar_faq_de_urls(urls: list[str], merge: bool = True) -> dict:
    """
    Pipeline completo: URLs → Extração → FAQ JSON.

    Args:
        urls: Lista de URLs de eventos
        merge: Se True, preserva FAQ existente. Se False, sobrescreve.

    Returns:
        Dicionário faq.json atualizado
    """
    faq = carregar_faq_existente() if merge else {"empresa": {}, "evento": {}, "categorias": {}}
    novas_categorias = {}

    for i, url in enumerate(urls, 1):
        print(f"\n{'='*50}")
        print(f"🔍 [{i}/{len(urls)}] Extraindo: {url[:60]}...")
        print(f"{'='*50}")

        evento = extrair_de_url(url)
        if not evento:
            print("   📂 Tentando cache local...")
            evento = extrair_de_cache(url)
        if not evento:
            print(f"⚠️  Falhou ao extrair: {url}")
            continue

        cats = evento_para_faq(evento, i)
        novas_categorias.update(cats)

        # Mostra resumo
        print(f"   ✅ {evento.nome}")
        print(f"   📅 {evento.data} {'às ' + evento.horario if evento.horario else ''}")
        print(f"   📍 {evento.local} — {evento.cidade}")
        print(f"   🎟️ Setores: {len(evento.setores)} | Perguntas geradas: {sum(len(c['perguntas']) for c in cats.values())}")

    faq = merge_faqs(faq, novas_categorias)
    return faq


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python gerador_faq.py URL1 URL2 ...")
        print("     python gerador_faq.py --urls urls.txt")
        sys.exit(1)

    if sys.argv[1] == "--urls":
        with open(sys.argv[2]) as f:
            urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    else:
        urls = sys.argv[1:]

    faq = gerar_faq_de_urls(urls, merge=True)
    salvar_faq(faq)
