"""
╔══════════════════════════════════════════╗
║   EXTRACTOR ENGINE                      ║
║   Extrai dados de eventos de bilheterias║
╚══════════════════════════════════════════╝

Estratégias de extração (em ordem de prioridade):
1. JSON-LD (Structured Data) - 0 tokens
2. HTML Parsing - 0 tokens
3. IA (DeepSeek) - fallback com tokens

Uso:
    from extractor import EventExtractor
    
    extractor = EventExtractor()
    evento = await extractor.extrair("https://baladapp.com.br/evento/xxx")
"""

import json
import re
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import hashlib

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import cloudscraper

# Adiciona o diretório pai ao path para importar módulos locais
PASTA_ATUAL = Path(__file__).parent
PASTA_PROJETO = PASTA_ATUAL.parent
sys.path.insert(0, str(PASTA_PROJETO))

# Carrega variáveis de ambiente
load_dotenv()

# Importa o gerenciador do banco de dados
from database import db_manager

# Configuração DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MODELO_IA = "deepseek-chat"


class EventExtractor:
    """
    Extrai dados de eventos de diferentes plataformas de bilheteria.
    
    Suporta:
    - BaladAPP
    - Meu Bilhete
    - Ticket360
    - GuicheLive
    - IngressoLive
    - Q2 Ingressos
    """
    
    def __init__(self):
        """Inicializa o extrator."""
        self.platforms = {
            "baladapp.com.br": self._extract_baladapp,
            "meubilhete.com.br": self._extract_meubilhete,
            "ticket360.com.br": self._extract_ticket360,
            "guichelive.com.br": self._extract_guichelive,
            "ingressolive.com": self._extract_ingressolive,
            "q2ingressos.com.br": self._extract_q2ingressos,
        }
        
        # Headers para requisições HTTP
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    
    async def extrair(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extrai dados de um evento a partir da URL.
        
        Args:
            url: URL do evento na bilheteria
            
        Returns:
            Dicionário com os dados do evento ou None se falhar
        """
        print(f"🔍 Extraindo dados de: {url}")
        
        # Identifica a plataforma
        plataforma = self._identificar_plataforma(url)
        if not plataforma:
            print(f"❌ Plataforma não suportada: {url}")
            return None
        
        print(f"📱 Plataforma identificada: {plataforma}")
        
        try:
            # Faz a requisição HTTP (usa cloudscraper para bypassar Cloudflare)
            # Tenta até 3 vezes com delay crescente
            html = None
            
            for tentativa in range(3):
                try:
                    # Cria um novo scraper a cada tentativa (evita bloqueio)
                    scraper = cloudscraper.create_scraper(
                        browser={
                            'browser': 'chrome',
                            'platform': 'windows',
                            'desktop': True
                        }
                    )
                    response = scraper.get(url, timeout=30)
                    response.raise_for_status()
                    html = response.text
                    break
                except Exception as e:
                    if tentativa < 2:
                        delay = (tentativa + 1) * 3  # 3s, 6s
                        print(f"⚠️  Tentativa {tentativa + 1} falhou: {e}")
                        import time
                        time.sleep(delay)
                    else:
                        raise e
            
            if not html:
                print("❌ Não foi possível obter o HTML após 3 tentativas")
                return None
            
            print(f"✅ HTML obtido: {len(html)} caracteres")
            
            dados = None
            
            # Tenta extrair com a estratégia específica da plataforma
            extractor_func = self.platforms.get(plataforma)
            if extractor_func:
                dados = await extractor_func(url, html)
            
            # Fallback: tenta JSON-LD genérico
            if not dados:
                print("🔄 Tentando JSON-LD genérico...")
                dados = self._extract_jsonld(html)
            
            # Fallback: tenta HTML parsing genérico
            if not dados:
                print("🔄 Tentando HTML parsing genérico...")
                dados = self._extract_html_generico(url, html)
            
            # Se encontrou dados, verifica se faltam campos cruciais
            if dados:
                campos_faltando = self._verificar_campos_faltando(dados)
                
                if campos_faltando:
                    print(f"🤖 IA: preenchendo campos faltando: {campos_faltando}")
                    dados = await self._completar_campos_com_ia(url, html, dados, campos_faltando)
                
                print(f"✅ Dados extraídos com sucesso!")
                return dados
            
            # Último fallback: tenta extrair tudo via IA
            print("🤖 Tentando extração completa via IA...")
            dados = await self._extract_via_ia(url, html)
            if dados:
                print(f"✅ Dados extraídos via IA!")
                return dados
            
            print("❌ Não foi possível extrair dados do evento")
            return None
            
        except httpx.HTTPError as e:
            print(f"❌ Erro HTTP: {e}")
            return None
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            return None
    
    def _verificar_campos_faltando(self, dados: Dict[str, Any]) -> List[str]:
        """Verifica quais campos cruciais estão faltando."""
        campos_faltando = []
        
        # Campos cruciais
        if not dados.get("data"):
            campos_faltando.append("data")
        if not dados.get("local"):
            campos_faltando.append("local")
        
        return campos_faltando
    
    async def _completar_campos_com_ia(self, url: str, html: str, dados: Dict[str, Any], campos_faltando: List[str]) -> Dict[str, Any]:
        """
        Usa IA para preencher campos faltando nos dados extraídos.
        """
        if not DEEPSEEK_API_KEY:
            print("⚠️  DeepSeek API key não configurada")
            return dados
        
        # Limpa o HTML para obter texto limpo
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove scripts, styles e outros elementos desnecessários
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        # Obtém o texto limpo
        texto = soup.get_text(separator='\n', strip=True)
        
        # Limita o tamanho do texto para economizar tokens
        texto = texto[:2000]  # Máximo 2000 caracteres
        
        # Monta o prompt para a IA
        campos_str = ", ".join(campos_faltando)
        
        prompt_sistema = f"""Você é um extrator de dados de eventos. 
        
Extraia APENAS os seguintes campos do texto fornecido: {campos_str}

Retorne APENAS um JSON válido com os campos solicitados.
Se não encontrar uma informação, use "".

Exemplo de resposta:
{{
    "data": "DD/MM/AAAA",
    "local": "Nome do local"
}}

REGRAS:
- Para data, tente converter para formato DD/MM/AAAA
- Para local, extraia apenas o nome do local (sem endereço completo)
- Retorne APENAS o JSON, sem texto adicional"""

        prompt_usuario = f"Extraia os campos {campos_str} do evento deste texto:\n\n{texto}"
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        
        corpo = {
            "model": MODELO_IA,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            "temperature": 0.1,
            "max_tokens": 500,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resposta = await client.post(DEEPSEEK_URL, json=corpo, headers=headers)
                resposta.raise_for_status()
                dados_api = resposta.json()
                
                # Extrai o JSON da resposta
                conteudo = dados_api["choices"][0]["message"]["content"]
                
                print(f"🤖 Resposta da IA: {conteudo[:200]}...")
                
                # Tenta parsear o JSON
                try:
                    # Remove possíveis marcadores de código
                    conteudo = conteudo.strip()
                    if conteudo.startswith("```json"):
                        conteudo = conteudo[7:]
                    if conteudo.endswith("```"):
                        conteudo = conteudo[:-3]
                    conteudo = conteudo.strip()
                    
                    resultado = json.loads(conteudo)
                    
                    # Atualiza apenas os campos que foram solicitados
                    for campo in campos_faltando:
                        if campo in resultado and resultado[campo]:
                            dados[campo] = resultado[campo]
                            print(f"   ✅ {campo}: {resultado[campo]}")
                    
                    return dados
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️  Erro ao parsear resposta da IA: {e}")
                    return dados
                    
        except httpx.TimeoutException:
            print("⚠️  Timeout na requisição à IA")
            return dados
        except httpx.HTTPStatusError as e:
            print(f"⚠️  Erro HTTP na IA: {e.response.status_code}")
            return dados
        except Exception as e:
            print(f"⚠️  Erro inesperado na IA: {e}")
            return dados
    
    def _identificar_plataforma(self, url: str) -> Optional[str]:
        """Identifica a plataforma da URL."""
        url_lower = url.lower()
        
        for plataforma in self.platforms.keys():
            if plataforma in url_lower:
                return plataforma
        
        return None
    
    # ==================================================
    # ESTRATÉGIAS DE EXTRAÇÃO
    # ==================================================
    
    def _extract_jsonld(self, html: str) -> Optional[Dict[str, Any]]:
        """
        Extrai dados de JSON-LD (Structured Data).
        Método mais rápido e confiável (0 tokens).
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Procura por script type="application/ld+json"
        scripts = soup.find_all('script', type='application/ld+json')
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                
                # Verifica se é um Event (ou variações como MusicEvent)
                if isinstance(data, dict):
                    event_type = data.get('@type', '')
                    if event_type in ['Event', 'MusicEvent', 'TheaterEvent', 'Festival']:
                        return self._parse_jsonld_event(data)
                    # Pode ser um array de eventos
                    elif isinstance(data.get('@graph'), list):
                        for item in data['@graph']:
                            if isinstance(item, dict) and item.get('@type', '') in ['Event', 'MusicEvent', 'TheaterEvent', 'Festival']:
                                return self._parse_jsonld_event(item)
                
                # Pode ser uma lista
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type', '') in ['Event', 'MusicEvent', 'TheaterEvent', 'Festival']:
                            return self._parse_jsonld_event(item)
                            
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _parse_jsonld_event(self, data: Dict) -> Optional[Dict[str, Any]]:
        """Converte JSON-LD Event para nosso formato."""
        try:
            # Extrai data e horário
            start_date = data.get('startDate', '')
            data_evento = ''
            horario = ''
            
            if start_date:
                # Formato ISO: 2024-06-15T22:00:00
                parts = start_date.split('T')
                if len(parts) >= 1:
                    data_evento = parts[0]
                if len(parts) >= 2:
                    horario = parts[1][:5]  # HH:MM
            
            # Extrai local
            location = data.get('location', {})
            local = ''
            endereco = ''
            
            if isinstance(location, dict):
                local = location.get('name', '')
                address = location.get('address', {})
                if isinstance(address, dict):
                    endereco = address.get('streetAddress', '')
            
            # Extrai artistas/performers
            performers = data.get('performer', [])
            artistas = []
            
            if isinstance(performers, list):
                for p in performers:
                    if isinstance(p, dict):
                        artistas.append(p.get('name', ''))
                    elif isinstance(p, str):
                        artistas.append(p)
            elif isinstance(performers, dict):
                artistas.append(performers.get('name', ''))
            
            # Monta o dicionário de dados
            dados = {
                "nome": data.get('name', ''),
                "data": data_evento,
                "horario": horario,
                "local": local,
                "endereco": endereco,
                "artistas": artistas,
                "descricao": data.get('description', ''),
                "classificacao": data.get('typicalAgeRange', ''),
                "url_original": data.get('url', ''),
            }
            
            # Tenta extrair preço
            offers = data.get('offers', {})
            if isinstance(offers, dict):
                preco = offers.get('price', '')
                if preco:
                    dados["ingressos"] = [{
                        "tipo": "Geral",
                        "preco": float(preco) if preco.replace('.', '').isdigit() else 0,
                        "lote": ""
                    }]
            
            return dados
            
        except Exception as e:
            print(f"⚠️  Erro ao parsear JSON-LD: {e}")
            return None
    
    def _extract_html_generico(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """
        Extrai dados via parsing HTML genérico.
        Método fallback (0 tokens).
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        dados = {
            "nome": "",
            "data": "",
            "horario": "",
            "local": "",
            "endereco": "",
            "artistas": [],
            "descricao": "",
            "classificacao": "",
            "url_original": url,
        }
        
        # Tenta encontrar o título do evento
        titulo = soup.find('h1') or soup.find('title')
        if titulo:
            dados["nome"] = titulo.get_text(strip=True)[:100]
        
        # Tenta encontrar meta tags
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            dados["descricao"] = meta_desc.get('content', '')[:500]
        
        # Tenta encontrar datas (heurística simples)
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}',
            r'\d{1,2}\s+de\s+\w+',
            r'\w+-feira|\sábado|\domingo',
        ]
        
        text_content = soup.get_text()
        for pattern in date_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                dados["data"] = match.group(0)
                break
        
        # Tenta encontrar horário (HH:MM ou HHh)
        horario_patterns = [
            r'\b(\d{1,2}:\d{2})\b',  # 22:00, 14:30
            r'\b(\d{1,2}h)\b',        # 22h, 14h30
            r'abertura[:\s]*(\d{1,2}[h:]\d{0,2})',
        ]
        for pattern in horario_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                dados["horario"] = match.group(1)
                break
        
        # Tenta encontrar local (heurística)
        local_keywords = ['castelli', 'hall', 'arena', 'teatro', 'cinema', 'clube', 'bar', 'balada', 'casa', 'espaço', 'centro', 'pavilhão', 'ginásio']
        
        # Procura por elementos que contenham palavras-chave de local
        # Prioriza tags menores (p, span) sobre divs
        for tag_name in ['p', 'span', 'h2', 'h3', 'div']:
            for elem in soup.find_all(tag_name):
                text = elem.get_text(strip=True)
                text_lower = text.lower()
                
                # Verifica se o elemento contém uma palavra-chave de local
                if any(palavra in text_lower for palavra in local_keywords):
                    # Limita o texto para não pegar texto demais
                    if len(text) < 100:  # Locais geralmente são curtos
                        # Remove "Local:" do início se presente
                        local_text = re.sub(r'^Local[:\s]*', '', text, flags=re.IGNORECASE)
                        dados["local"] = local_text.strip()
                        break
            if dados["local"]:
                break
        
        # Se não encontrou local nos elementos, tenta extrair do texto completo
        if not dados["local"]:
            # Procura por padrão "Local:" seguido do nome do local
            # Formato com quebras de linha: "Local:\nPica Pau Country Clube - Araguari / MG\nAbertura"
            local_pattern = r'Local[:\s]*\n?([^\n]{5,80}?)(?:\n|Abertura|Data|Classificação|$)'
            match = re.search(local_pattern, text_content, re.IGNORECASE)
            if match:
                local_text = match.group(1).strip()
                # Limpa o texto (remove "Local:" se estiver no início)
                local_text = re.sub(r'^Local[:\s]*', '', local_text, flags=re.IGNORECASE)
                # Remove caracteres extras no final
                local_text = local_text.rstrip(' -')
                dados["local"] = local_text
        
        # Só retorna se encontrou pelo menos o nome
        if dados["nome"]:
            return dados
        
        return None
    
    async def _extract_via_ia(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """
        Extrai dados via IA (DeepSeek).
        Método mais completo, gasta tokens.
        """
        if not DEEPSEEK_API_KEY:
            print("⚠️  DeepSeek API key não configurada")
            return None
        
        # Limpa o HTML para obter texto limpo
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove scripts, styles e outros elementos desnecessários
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        # Obtém o texto limpo
        texto = soup.get_text(separator='\n', strip=True)
        
        # Limita o tamanho do texto para economizar tokens
        texto = texto[:3000]  # Máximo 3000 caracteres
        
        # Monta o prompt para a IA
        prompt_sistema = """Você é um extrator de dados de eventos. 
        
Extraia APENAS as informações solicitadas do texto fornecido.

Retorne APENAS um JSON válido com a seguinte estrutura:
{
    "nome": "Nome do evento",
    "data": "Data no formato DD/MM/AAAA",
    "horario": "Horário no formato HH:MM",
    "local": "Nome do local",
    "endereco": "Endereço completo",
    "artistas": ["Artista 1", "Artista 2"],
    "descricao": "Descrição breve",
    "classificacao": "Classificação etária (ex: +18)",
    "ingressos": [
        {"tipo": "Nome do tipo", "preco": 100.00, "lote": "1º lote"}
    ],
    "coberto": true,
    "onde_comprar": {
        "plataforma": "Nome da plataforma",
        "url": "URL de compra"
    }
}

REGRAS:
- Se não encontrar uma informação, use "" ou []
- Para data, tente converter para formato DD/MM/AAAA
- Para horário, extraia no formato HH:MM
- Para preço, extraia apenas números (ex: 100.00)
- Retorne APENAS o JSON, sem texto adicional"""

        prompt_usuario = f"Extraia os dados do evento deste texto:\n\n{texto}"
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        
        corpo = {
            "model": MODELO_IA,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            "temperature": 0.1,
            "max_tokens": 1000,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resposta = await client.post(DEEPSEEK_URL, json=corpo, headers=headers)
                resposta.raise_for_status()
                dados = resposta.json()
                
                # Extrai o JSON da resposta
                conteudo = dados["choices"][0]["message"]["content"]
                
                print(f"🤖 Resposta da IA (primeiros 300 chars): {conteudo[:300]}...")
                
                # Tenta parsear o JSON
                try:
                    # Remove possíveis marcadores de código
                    conteudo = conteudo.strip()
                    if conteudo.startswith("```json"):
                        conteudo = conteudo[7:]
                    if conteudo.endswith("```"):
                        conteudo = conteudo[:-3]
                    conteudo = conteudo.strip()
                    
                    resultado = json.loads(conteudo)
                    
                    # Adiciona URL original
                    resultado["url_original"] = url
                    
                    return resultado
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️  Erro ao parsear resposta da IA: {e}")
                    print(f"   Resposta completa: {conteudo}")
                    return None
                    
        except httpx.TimeoutException:
            print("⚠️  Timeout na requisição à IA")
            return None
        except httpx.HTTPStatusError as e:
            print(f"⚠️  Erro HTTP na IA: {e.response.status_code}")
            return None
        except Exception as e:
            print(f"⚠️  Erro inesperado na IA: {e}")
            return None
    
    # ==================================================
    # EXTRATORES ESPECÍFICOS POR PLATAFORMA
    # ==================================================
    
    async def _extract_baladapp(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """Extrai dados específicos da BaladAPP."""
        # Tenta JSON-LD primeiro
        dados = self._extract_jsonld(html)
        if dados:
            dados["url_original"] = url
            dados["onde_comprar"] = {
                "plataforma": "BaladAPP",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Tenta HTML parsing genérico
        dados = self._extract_html_generico(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "BaladAPP",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Fallback: IA
        print("🤖 BaladAPP: tentando IA...")
        dados = await self._extract_via_ia(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "BaladAPP",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        return None
    
    async def _extract_meubilhete(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """Extrai dados específicos do Meu Bilhete."""
        # Tenta JSON-LD primeiro
        dados = self._extract_jsonld(html)
        if dados:
            dados["url_original"] = url
            dados["onde_comprar"] = {
                "plataforma": "Meu Bilhete",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Tenta HTML parsing genérico
        dados = self._extract_html_generico(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "Meu Bilhete",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Fallback: IA
        print("🤖 Meu Bilhete: tentando IA...")
        dados = await self._extract_via_ia(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "Meu Bilhete",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        return None
    
    async def _extract_ticket360(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """Extrai dados específicos da Ticket360."""
        # Tenta JSON-LD primeiro (Ticket360 geralmente tem)
        dados = self._extract_jsonld(html)
        if dados:
            dados["url_original"] = url
            dados["onde_comprar"] = {
                "plataforma": "Ticket360",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Tenta HTML parsing genérico
        dados = self._extract_html_generico(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "Ticket360",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Fallback: IA
        print("🤖 Ticket360: tentando IA...")
        dados = await self._extract_via_ia(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "Ticket360",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        return None
    
    async def _extract_guichelive(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """Extrai dados específicos do GuicheLive."""
        # Tenta JSON-LD primeiro
        dados = self._extract_jsonld(html)
        if dados:
            dados["url_original"] = url
            dados["onde_comprar"] = {
                "plataforma": "GuicheLive",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Tenta HTML parsing genérico
        dados = self._extract_html_generico(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "GuicheLive",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Fallback: IA
        print("🤖 GuicheLive: tentando IA...")
        dados = await self._extract_via_ia(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "GuicheLive",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        return None
    
    async def _extract_ingressolive(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """Extrai dados específicos do IngressoLive."""
        # Tenta JSON-LD primeiro
        dados = self._extract_jsonld(html)
        if dados:
            dados["url_original"] = url
            dados["onde_comprar"] = {
                "plataforma": "IngressoLive",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Tenta HTML parsing genérico
        dados = self._extract_html_generico(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "IngressoLive",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Fallback: IA
        print("🤖 IngressoLive: tentando IA...")
        dados = await self._extract_via_ia(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "IngressoLive",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        return None
    
    async def _extract_q2ingressos(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """Extrai dados específicos do Q2 Ingressos."""
        # Tenta JSON-LD primeiro
        dados = self._extract_jsonld(html)
        if dados:
            dados["url_original"] = url
            dados["onde_comprar"] = {
                "plataforma": "Q2 Ingressos",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Tenta HTML parsing genérico
        dados = self._extract_html_generico(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "Q2 Ingressos",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        # Fallback: IA
        print("🤖 Q2 Ingressos: tentando IA...")
        dados = await self._extract_via_ia(url, html)
        if dados:
            dados["onde_comprar"] = {
                "plataforma": "Q2 Ingressos",
                "url": url,
                "whatsapp": ""
            }
            return dados
        
        return None
    
    # ==================================================
    # PERSISTÊNCIA NO BANCO
    # ==================================================
    
    async def extrair_e_salvar(self, url: str) -> Optional[str]:
        """
        Extrai dados de um evento e salva no ChromaDB.
        
        Args:
            url: URL do evento
            
        Returns:
            ID do evento no banco ou None se falhar
        """
        # Extrai os dados
        dados = await self.extrair(url)
        
        if not dados:
            return None
        
        # Salva no banco
        evento_id = db_manager.adicionar_evento(dados)
        
        print(f"✅ Evento salvo no banco: {evento_id}")
        print(f"   Nome: {dados.get('nome')}")
        print(f"   Data: {dados.get('data')}")
        print(f"   Local: {dados.get('local')}")
        
        return evento_id


# ==================================================
# INSTÂNCIA GLOBAL (Singleton)
# ==================================================

# Cria uma instância global do extrator
event_extractor = EventExtractor()


# ==================================================
# TESTE RÁPIDO
# ==================================================

if __name__ == "__main__":
    import asyncio
    
    async def testar():
        print("\n🧪 Testando Event Extractor...\n")
        
        # Testa identificação de plataforma
        urls_teste = [
            "https://baladapp.com.br/evento/teste",
            "https://meubilhete.com.br/evento/teste",
            "https://ticket360.com.br/evento/teste",
            "https://sitequalquer.com.br/evento",
        ]
        
        extractor = EventExtractor()
        
        for url in urls_teste:
            plataforma = extractor._identificar_plataforma(url)
            print(f"URL: {url}")
            print(f"  Plataforma: {plataforma or 'Não suportada'}")
            print()
        
        print("✅ Testes concluídos!")
    
    asyncio.run(testar())
