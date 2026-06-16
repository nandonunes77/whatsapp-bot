"""
╔══════════════════════════════════════════╗
║   EXTRATOR DE EVENTOS                   ║
║   URL → Dados estruturados              ║
╚══════════════════════════════════════════╝

Uso:
    from extrator import extrair_de_url
    evento = extrair_de_url("https://baladapp.com.br/...")
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EventoData:
    """Dados extraídos de um evento."""
    nome: str = ""
    artista: str = ""
    data: str = ""
    horario: str = ""
    local: str = ""
    cidade: str = ""
    classificacao: str = ""
    descricao: str = ""
    plataforma: str = ""
    url: str = ""
    setores: list[dict] = field(default_factory=list)
    meia_entrada: str = ""
    itens_proibidos: list[str] = field(default_factory=list)
    politica_cancelamento: str = ""
    politica_transferencia: str = ""
    contato: dict = field(default_factory=dict)
    regras: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v}


def normalizar(texto: str) -> str:
    """Remove acentos, lowercase, strip."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _extrair_plataforma(url: str) -> str:
    """Identifica a plataforma pelo domínio."""
    dominios = {
        "baladapp.com": "BaladAPP",
        "ticket360.com": "Ticket360",
        "meubilhete.com": "MeuBilhete",
        "guichelive.com": "Guichê Live",
        "sympla.com": "Sympla",
        "eventim.com": "Eventim",
        "ticketmaster": "Ticketmaster",
    }
    url_lower = url.lower()
    for dominio, nome in dominios.items():
        if dominio in url_lower:
            return nome
    return "Outro"


def _extrair_data(texto: str) -> tuple[str, str]:
    """Tenta extrair data (DD/MM/AAAA) e horário do texto."""
    meses = {
        "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
        "abril": "04", "maio": "05", "junho": "06",
        "julho": "07", "agosto": "08", "setembro": "09",
        "outubro": "10", "novembro": "11", "dezembro": "12",
        "january": "01", "february": "02", "march": "03",
        "april": "04", "may": "05", "june": "06",
        "july": "07", "august": "08", "september": "09",
        "october": "10", "november": "11", "december": "12",
    }

    # Padrão: DD/MM/AAAA
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", texto)
    if match:
        data = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
    else:
        # Padrão PT-BR: "DD de MES de AAAA" ou "DD de MES"
        padrao_pt = r"(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?"
        match = re.search(padrao_pt, texto, re.IGNORECASE)
        if match:
            dia = match.group(1).zfill(2)
            mes_nome = match.group(2)
            mes = meses.get(normalizar(mes_nome), "??")
            ano = match.group(3) or ""
            data = f"{dia}/{mes}/{ano}" if ano else f"{dia}/{mes}"
        else:
            # Padrão EN: "Month DD, YYYY" ou "Month DD YYYY"
            padrao_en = r"(\w+)\s+(\d{1,2}),?\s+(\d{4})"
            match = re.search(padrao_en, texto, re.IGNORECASE)
            if match:
                mes_nome = match.group(1)
                mes = meses.get(normalizar(mes_nome), "??")
                dia = match.group(2).zfill(2)
                ano = match.group(3)
                data = f"{dia}/{mes}/{ano}" if mes != "??" else ""
            else:
                data = ""

    # Horário: HH:MM ou HHh ou HHhMM
    horario_match = re.search(r"(\d{1,2})[h:](\d{2})?h?", texto)
    horario = ""
    if horario_match:
        h = horario_match.group(1).zfill(2)
        m = (horario_match.group(2) or "00").zfill(2)
        horario = f"{h}:{m}"

    return data, horario


def _extrair_cidade_local(texto: str) -> tuple[str, str]:
    """Tenta extrair local e cidade do texto."""
    # Limpa markdown do texto antes de buscar
    texto_limpo = re.sub(r"\*\*", "", texto)
    texto_limpo = re.sub(r"#+\s*", "", texto_limpo)
    
    UFS_VALIDOS = {
        "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
        "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"
    }

    # Padrão: "Cidade/UF" (com UF válido)
    for match in re.finditer(r"([\w\s]+?)\s*/\s*([A-Z]{2})", texto_limpo):
        uf = match.group(2)
        if uf in UFS_VALIDOS:
            cidade = match.group(1).strip()
            # Limpa lixo markdown/texto que sobrou
            cidade = re.sub(r"[^\w\s]", "", cidade).strip()
            return "", f"{cidade}/{uf}"

    # Padrão: "Cidade - UF" ou ", Cidade - UF"
    for match in re.finditer(r"[-,]\s*([\w\s]+?)\s*-\s*([A-Z]{2})\b", texto_limpo):
        uf = match.group(2)
        if uf in UFS_VALIDOS:
            cidade = match.group(1).strip()
            cidade = re.sub(r"[^\w\s]", "", cidade).strip()
            return "", f"{cidade}/{uf}"

    # Fallback: cidades conhecidas
    cidades_comuns = [
        "uberlândia", "uberlandia", "montes claros", "araguari",
        "goiânia", "belo horizonte", "são paulo", "rio de janeiro",
    ]
    texto_lower = texto.lower()
    for cidade in cidades_comuns:
        if cidade in texto_lower:
            match_uf = re.search(
                re.escape(cidade) + r"\s*[-/,]?\s*([A-Z]{2})",
                texto, re.IGNORECASE,
            )
            if match_uf and match_uf.group(1) in UFS_VALIDOS:
                return "", f"{cidade.title()}/{match_uf.group(1)}"
            return "", cidade.title()

    return "", ""


def _extrair_setores(texto: str) -> list[dict]:
    """Identifica setores mencionados no texto."""
    setores_encontrados = []

    setores_conhecidos = [
        ("bistrô", "Bistrô"), ("bistro", "Bistrô"),
        ("frontstage", "Frontstage"), ("pista premium", "Pista Premium"),
        ("área vip", "Área VIP"), ("vip", "Área VIP"),
        ("camarote", "Camarote"), ("mesa diamante", "Mesa Diamante"),
        ("mesa ouro", "Mesa Ouro"), ("mesa prata", "Mesa Prata"),
        ("lounge", "Lounge"), ("pista", "Pista"),
        ("plateia", "Plateia"), ("arquibancada", "Arquibancada"),
    ]

    texto_lower = normalizar(texto)
    vistos = set()

    for chave, nome in setores_conhecidos:
        chave_norm = normalizar(chave)
        if chave_norm in texto_lower and nome not in vistos:
            vistos.add(nome)

            # Tenta extrair preço associado
            padrao_preco = re.compile(
                rf"{re.escape(chave)}.*?R\$\s*(\d+[.,]\d{{2}})",
                re.IGNORECASE,
            )
            preco_match = padrao_preco.search(texto)
            preco = f"R$ {preco_match.group(1)}" if preco_match else ""

            setores_encontrados.append({"nome": nome, "preco": preco})

    return setores_encontrados


def extrair_de_texto(texto: str, url: str = "") -> EventoData:
    """
    Extrai dados de um evento a partir de texto estruturado.

    Args:
        texto: Conteúdo markdown/texto do evento
        url: URL original do evento

    Returns:
        EventoData com todos os campos extraídos
    """
    ev = EventoData(url=url, plataforma=_extrair_plataforma(url))

    linhas = [l.strip() for l in texto.split("\n") if l.strip()]

    # ── Título ──
    for linha in linhas:
        if linha.startswith("# "):
            nome = linha.lstrip("# ").strip()
            # Remove sufixos de plataformas (web_extract adiciona isso)
            for sufixo in [" - Event Summary", " | Comprehensive Summary",
                           "Event Summary", "Comprehensive Summary",
                           " - Guiche Web", " - BaladAPP"]:
                nome = nome.replace(sufixo, "").strip()
            # Remove " - Cidade/UF" se presente no título (já capturado separadamente)
            nome = re.sub(r"\s*-\s*[A-Z][a-z]+\s*[-/]\s*[A-Z]{2}$", "", nome).strip()
            # Remove artefatos markdown (asteriscos, underscores)
            nome = re.sub(r"[\*]{2,}", "", nome).strip()
            nome = re.sub(r"_{2,}", "", nome).strip()
            ev.nome = nome
            break

    # ── Artista ──
    artistas = [
        "ana carolina", "victor e leo", "victor & leo", "capital inicial",
        "ralf", "geriatricus",
    ]
    texto_lower = texto.lower()
    for nome_artista in artistas:
        if nome_artista in texto_lower:
            ev.artista = nome_artista.title()
            break

    # ── Descrição (primeiro parágrafo após título) ──
    capturar = False
    descricao_linhas = []
    for linha in linhas:
        if linha.startswith("# "):
            capturar = True
            continue
        if capturar and not linha.startswith("#") and not linha.startswith("-"):
            descricao_linhas.append(linha)
        elif capturar and (linha.startswith("#") or linha.startswith("-")):
            break
    ev.descricao = " ".join(descricao_linhas[:2])[:300]

    # ── Data e horário ──
    ev.data, ev.horario = _extrair_data(texto)

    # ── Local e cidade ──
    local, cidade = _extrair_cidade_local(texto)
    ev.local = local or ev.local
    ev.cidade = cidade or ev.cidade

    # ── Classificação ──
    match_class = re.search(r"[+]\s*(\d+)", texto)
    if match_class:
        ev.classificacao = f"+{match_class.group(1)}"

    # ── Meia entrada ──
    if "solid" in texto_lower and "alimento" in texto_lower:
        match_kg = re.search(r"(\d+)\s*kg", texto_lower)
        kg = match_kg.group(1) if match_kg else "1"
        ev.meia_entrada = f"Solidária: doação de {kg}kg de alimento não perecível"

    # ── Setores ──
    ev.setores = _extrair_setores(texto)

    # ── Itens proibidos ──
    itens = [
        "drogas", "armas", "vidro", "perfumes", "animais",
        "fogos", "capacete", "alimentos", "bebidas",
        "máscaras", "roupas pontiagudas",
    ]
    for item in itens:
        if item in texto_lower:
            ev.itens_proibidos.append(item)

    # ── Política de cancelamento ──
    if "7 dias" in texto and ("cancelamento" in texto_lower or "reembolso" in texto_lower):
        ev.politica_cancelamento = "Até 7 dias após a compra, sem ultrapassar 48h antes do evento"

    # ── Contato ──
    instagram_match = re.search(r"@([\w.]+)", texto)
    if instagram_match:
        ev.contato["instagram"] = f"@{instagram_match.group(1)}"

    telefone_match = re.search(r"\(\d{2}\)\s*\d", texto)
    if telefone_match:
        tel = re.search(r"\(\d{2}\)\s*[\d\s.-]+", texto)
        if tel:
            ev.contato["telefone"] = tel.group().strip()

    email_match = re.search(r"[\w.-]+@[\w.-]+\.\w+", texto)
    if email_match:
        ev.contato["email"] = email_match.group()

    return ev


def extrair_de_url(url: str) -> Optional[EventoData]:
    """
    Busca conteúdo de uma URL e extrai dados do evento.

    Args:
        url: URL do evento

    Returns:
        EventoData ou None se falhar
    """
    try:
        from hermes_tools import web_extract
        resultado = web_extract([url])
        resultados = resultado.get("results", [])
        if not resultados or resultados[0].get("error"):
            print(f"❌ Erro ao extrair URL: {resultados[0].get('error') if resultados else 'vazio'}")
            return None
        conteudo = resultados[0].get("content", "")
        return extrair_de_texto(conteudo, url)
    except ImportError:
        print("⚠️  web_extract não disponível. Use extrair_de_texto() diretamente.")
        return None


def extrair_de_cache(url: str, cache_path: str = ".extracao_cache.json") -> Optional[EventoData]:
    """
    Lê conteúdo de uma URL a partir de um cache JSON local.
    Útil quando web_extract já foi chamado antes e os dados foram salvos.
    """
    import json as _json
    from pathlib import Path as _Path

    caminho = _Path(__file__).parent / cache_path
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            cache = _json.load(f)
        for item in cache:
            if item.get("url") == url and item.get("content"):
                return extrair_de_texto(item["content"], url)
    except Exception as e:
        print(f"⚠️  Erro ao ler cache: {e}")
    return None
