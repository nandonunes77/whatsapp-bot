"""
╔══════════════════════════════════════════╗
║   CHROMADB MANAGER                      ║
║   Camada de dados vetorial              ║
╚══════════════════════════════════════════╝

Módulo para gerenciar o banco vetorial do Chatbot WhatsApp.

Coleções:
- events: Eventos extraídos das bilheterias
- bot_soul: Personalidade e regras do bot
- fixed_info: Informações fixas e permanentes
"""

import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import Optional, Dict, List, Any
import json
import hashlib
from datetime import datetime

# Configurações
PASTA_ATUAL = Path(__file__).parent
PASTA_PROJETO = PASTA_ATUAL.parent
PASTA_DADOS = PASTA_PROJETO / "data" / "chromadb"

# Caminhos para dados fixos
CAMINHO_BOT_SOUL = PASTA_PROJETO / "knowledge" / "bot_soul.md"


class ChromaManager:
    """
    Gerenciador do banco vetorial ChromaDB.
    
    Responsável por:
    - Inicializar e gerenciar coleções
    - Armazenar eventos extraídos
    - Gerenciar personalidade do bot (SOUL)
    - Consultar dados para o RAG
    """
    
    def __init__(self, persist_directory: Optional[str] = None):
        """
        Inicializa o ChromaDB.
        
        Args:
            persist_directory: Diretório para persistir dados (padrão: data/chromadb)
        """
        self.persist_directory = persist_directory or str(PASTA_DADOS)
        
        # Garante que o diretório existe
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
        
        # Inicializa o cliente ChromaDB
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
        # Inicializa as coleções
        self._init_collections()
        
        print(f"✅ ChromaDB inicializado em: {self.persist_directory}")
    
    def _init_collections(self):
        """Inicializa as coleções padrão do ChromaDB."""
        
        # Coleção de eventos
        self.events = self.client.get_or_create_collection(
            name="events",
            metadata={"description": "Eventos extraídos das bilheterias"}
        )
        
        # Coleção da personalidade do bot
        self.bot_soul = self.client.get_or_create_collection(
            name="bot_soul",
            metadata={"description": "Personalidade e regras do bot"}
        )
        
        # Coleção de informações fixas
        self.fixed_info = self.client.get_or_create_collection(
            name="fixed_info",
            metadata={"description": "Informações fixas e permanentes"}
        )
        
        print(f"📚 Coleções inicializadas: events, bot_soul, fixed_info")
    
    def _generate_id(self, text: str) -> str:
        """Gera um ID único baseado no texto."""
        return hashlib.md5(text.encode()).hexdigest()[:12]
    
    # ==================================================
    # EVENTOS
    # ==================================================
    
    def adicionar_evento(self, dados_evento: Dict[str, Any]) -> str:
        """
        Adiciona um evento ao banco de dados.
        
        Args:
            dados_evento: Dicionário com os dados do evento
                {
                    "nome": "Nome do Evento",
                    "data": "2024-06-15",
                    "horario": "22:00",
                    "local": "Nome do Local",
                    "endereco": "Endereço completo",
                    "artistas": ["Artista 1", "Artista 2"],
                    "ingressos": [
                        {"tipo": "Pista", "preco": 100.00, "lote": "1º lote"},
                        {"tipo": "VIP", "preco": 200.00, "lote": "1º lote"}
                    ],
                    "classificacao": "18+",
                    "descricao": "Descrição do evento",
                    "coberto": true,
                    "onde_comprar": {
                        "plataforma": "BaladAPP",
                        "url": "https://...",
                        "whatsapp": "+5511999999999"
                    },
                    "url_original": "https://..."
                }
        
        Returns:
            ID do evento criado
        """
        # Gera ID único baseado na URL ou nome
        evento_id = self._generate_id(
            dados_evento.get("url_original") or dados_evento.get("nome", "")
        )
        
        # Monta o texto para busca
        texto_busca = self._montar_texto_evento(dados_evento)
        
        # Metadados para filtragem
        metadata = {
            "nome": dados_evento.get("nome", ""),
            "data": dados_evento.get("data", ""),
            "horario": dados_evento.get("horario", ""),
            "local": dados_evento.get("local", ""),
            "classificacao": dados_evento.get("classificacao", ""),
            "coberto": dados_evento.get("coberto", False),
            "plataforma": dados_evento.get("onde_comprar", {}).get("plataforma", ""),
            "url_original": dados_evento.get("url_original", ""),
            "data_extracao": datetime.now().isoformat(),
        }
        
        # Armazena no ChromaDB
        self.events.upsert(
            ids=[evento_id],
            documents=[texto_busca],
            metadatas=[metadata]
        )
        
        print(f"✅ Evento adicionado: {dados_evento.get('nome')} (ID: {evento_id})")
        return evento_id
    
    def _montar_texto_evento(self, dados: Dict[str, Any]) -> str:
        """Monta o texto do evento para busca vetorial."""
        partes = []
        
        if dados.get("nome"):
            partes.append(f"Evento: {dados['nome']}")
        
        if dados.get("data"):
            partes.append(f"Data: {dados['data']}")
        
        if dados.get("horario"):
            partes.append(f"Horário: {dados['horario']}")
        
        if dados.get("local"):
            partes.append(f"Local: {dados['local']}")
        
        if dados.get("endereco"):
            partes.append(f"Endereço: {dados['endereco']}")
        
        if dados.get("artistas"):
            artistas = ", ".join(dados["artistas"])
            partes.append(f"Artistas: {artistas}")
        
        if dados.get("ingressos"):
            for ing in dados["ingressos"]:
                partes.append(
                    f"Ingresso {ing.get('tipo', '')}: "
                    f"R${ing.get('preco', 0):.2f} ({ing.get('lote', '')})"
                )
        
        if dados.get("classificacao"):
            partes.append(f"Classificação: {dados['classificacao']}")
        
        if dados.get("descricao"):
            partes.append(f"Descrição: {dados['descricao']}")
        
        if dados.get("coberto") is not None:
            partes.append(f"Coberto: {'Sim' if dados['coberto'] else 'Não'}")
        
        if dados.get("onde_comprar"):
            comp = dados["onde_comprar"]
            if comp.get("plataforma"):
                partes.append(f"Comprar em: {comp['plataforma']}")
            if comp.get("url"):
                partes.append(f"Link: {comp['url']}")
            if comp.get("whatsapp"):
                partes.append(f"WhatsApp: {comp['whatsapp']}")
        
        return "\n".join(partes)
    
    def listar_eventos(self) -> List[Dict[str, Any]]:
        """Lista todos os eventos armazenados."""
        resultados = self.events.get()
        
        eventos = []
        metadatas = resultados.get("metadatas") or []
        documents = resultados.get("documents") or []
        
        for i, metadata in enumerate(metadatas):
            eventos.append({
                "id": resultados["ids"][i],
                "metadata": metadata,
                "documento": documents[i] if i < len(documents) else ""
            })
        
        return eventos
    
    def buscar_eventos(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Busca eventos por similaridade.
        
        Args:
            query: Texto da busca
            n_results: Número de resultados
            
        Returns:
            Lista de eventos encontrados
        """
        resultados = self.events.query(
            query_texts=[query],
            n_results=n_results
        )
        
        eventos = []
        ids = resultados.get("ids") or [[]]
        metadatas = resultados.get("metadatas") or [[]]
        documents = resultados.get("documents") or [[]]
        distances = resultados.get("distances") or [[]]
        
        for i in range(len(ids[0])):
            eventos.append({
                "id": ids[0][i],
                "metadata": metadatas[0][i] if i < len(metadatas[0]) else {},
                "documento": documents[0][i] if i < len(documents[0]) else "",
                "distancia": distances[0][i] if i < len(distances[0]) else 0.0
            })
        
        return eventos
    
    def remover_evento(self, evento_id: str) -> bool:
        """Remove um evento pelo ID."""
        try:
            self.events.delete(ids=[evento_id])
            print(f"✅ Evento removido: {evento_id}")
            return True
        except Exception as e:
            print(f"❌ Erro ao remover evento: {e}")
            return False
    
    # ==================================================
    # BOT SOUL (Personalidade)
    # ==================================================
    
    def carregar_bot_soul(self) -> bool:
        """
        Carrega a personalidade do bot do arquivo bot_soul.md.
        
        Returns:
            True se carregou com sucesso
        """
        if not CAMINHO_BOT_SOUL.exists():
            print(f"⚠️  Arquivo bot_soul.md não encontrado em: {CAMINHO_BOT_SOUL}")
            return False
        
        try:
            conteudo = CAMINHO_BOT_SOUL.read_text(encoding="utf-8")
            
            # Remove o bot soul existente e adiciona o novo
            self.bot_soul.upsert(
                ids=["bot_soul"],
                documents=[conteudo],
                metadatas=[{
                    "tipo": "personalidade",
                    "data_atualizacao": datetime.now().isoformat()
                }]
            )
            
            print(f"✅ Bot SOUL carregado: {len(conteudo)} caracteres")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao carregar bot SOUL: {e}")
            return False
    
    def obter_bot_soul(self) -> str:
        """Retorna a personalidade do bot."""
        resultados = self.bot_soul.get(ids=["bot_soul"])
        
        if resultados["documents"]:
            return resultados["documents"][0]
        
        return ""
    
    # ==================================================
    # INFORMAÇÕES FIXAS
    # ==================================================
    
    def adicionar_info_fixa(self, chave: str, conteudo: str, metadata: Optional[Dict] = None) -> str:
        """
        Adiciona uma informação fixa ao banco.
        
        Args:
            chave: Identificador único (ex: "regras_gerais", "contato_suporte")
            conteudo: Texto da informação
            metadata: Metadados opcionais
            
        Returns:
            ID do registro
        """
        info_id = f"fixed_{chave}"
        
        meta = metadata or {}
        meta["chave"] = chave
        meta["data_atualizacao"] = datetime.now().isoformat()
        
        self.fixed_info.upsert(
            ids=[info_id],
            documents=[conteudo],
            metadatas=[meta]
        )
        
        print(f"✅ Info fixa adicionada: {chave}")
        return info_id
    
    def obter_info_fixa(self, chave: str) -> str:
        """Retorna uma informação fixa pela chave."""
        info_id = f"fixed_{chave}"
        resultados = self.fixed_info.get(ids=[info_id])
        
        if resultados["documents"]:
            return resultados["documents"][0]
        
        return ""
    
    def listar_info_fixa(self) -> List[Dict[str, Any]]:
        """Lista todas as informações fixas."""
        resultados = self.fixed_info.get()
        
        infos = []
        metadatas = resultados.get("metadatas") or []
        
        for i, metadata in enumerate(metadatas):
            infos.append({
                "id": resultados["ids"][i],
                "chave": metadata.get("chave", ""),
                "metadata": metadata
            })
        
        return infos
    
    # ==================================================
    # CONSULTA PARA RAG
    # ==================================================
    
    def obter_contexto_para_ia(self, pergunta: str) -> str:
        """
        Monta o contexto para enviar à IA baseado na pergunta.
        
        Busca:
        1. Eventos relevantes
        2. Informações fixas relevantes
        3. Bot SOUL (sempre incluído)
        
        Args:
            pergunta: Pergunta do usuário
            
        Returns:
            Contexto formatado para a IA
        """
        partes = []
        
        # 1. Bot SOUL (sempre incluir)
        bot_soul = self.obter_bot_soul()
        if bot_soul:
            partes.append("═══ PERSONALIDADE DO BOT ═══")
            partes.append(bot_soul)
            partes.append("")
        
        # 2. Eventos relevantes
        eventos = self.buscar_eventos(pergunta, n_results=3)
        if eventos:
            partes.append("═══ EVENTOS RELACIONADOS ═══")
            for evento in eventos:
                partes.append(f"📅 {evento['metadata'].get('nome', 'Evento')}")
                partes.append(f"   Data: {evento['metadata'].get('data', 'N/A')}")
                partes.append(f"   Local: {evento['metadata'].get('local', 'N/A')}")
                partes.append(f"   {evento['documento']}")
                partes.append("")
        
        # 3. Informações fixas relevantes (busca por similaridade)
        # TODO: Implementar busca por similaridade em fixed_info se necessário
        
        if not partes:
            return ""
        
        return "\n".join(partes)
    
    # ==================================================
    # ESTATÍSTICAS
    # ==================================================
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """Retorna estatísticas do banco de dados."""
        return {
            "eventos": self.events.count(),
            "bot_soul": self.bot_soul.count(),
            "info_fixa": self.fixed_info.count(),
            "total_documentos": (
                self.events.count() + 
                self.bot_soul.count() + 
                self.fixed_info.count()
            )
        }


# ==================================================
# INSTÂNCIA GLOBAL (Singleton)
# ==================================================

# Cria uma instância global do gerenciador
db_manager = ChromaManager()


# ==================================================
# TESTE RÁPIDO
# ==================================================

if __name__ == "__main__":
    print("\n🧪 Testando ChromaDB Manager...\n")
    
    # Testa a instância
    stats = db_manager.obter_estatisticas()
    print(f"📊 Estatísticas:")
    print(f"   Eventos: {stats['eventos']}")
    print(f"   Bot SOUL: {stats['bot_soul']}")
    print(f"   Info Fixa: {stats['info_fixa']}")
    print(f"   Total: {stats['total_documentos']}")
    
    # Testa o bot SOUL
    print("\n🤖 Carregando Bot SOUL...")
    db_manager.carregar_bot_soul()
    
    bot_soul = db_manager.obter_bot_soul()
    if bot_soul:
        print(f"   Bot SOUL: {len(bot_soul)} caracteres")
        print(f"   Primeiros 100 chars: {bot_soul[:100]}...")
    else:
        print("   ⚠️  Bot SOUL não encontrado")
    
    print("\n✅ Testes concluídos!")
