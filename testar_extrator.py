#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║   TESTE DO EXTRATOR DE EVENTOS          ║
╚══════════════════════════════════════════╝

Script para testar a extração de eventos de bilheterias.

Uso:
    python testar_extrator.py <url_do_evento>

Exemplo:
    python testar_extrator.py https://baladapp.com.br/evento/arena-triangulo-uberlandia/8797
"""

import asyncio
import sys
from pathlib import Path

# Adiciona o diretório pai ao path
PASTA_ATUAL = Path(__file__).parent
sys.path.insert(0, str(PASTA_ATUAL))

from extractor import event_extractor
from database import db_manager


async def testar_extracao(url: str):
    """Testa a extração de um evento."""
    
    print("=" * 60)
    print("🧪 TESTE DO EXTRATOR DE EVENTOS")
    print("=" * 60)
    print(f"\n🔗 URL: {url}\n")
    
    # Extrai e salva o evento
    evento_id = await event_extractor.extrair_e_salvar(url)
    
    if evento_id:
        print("\n" + "=" * 60)
        print("✅ EVENTO EXTRAÍDO COM SUCESSO!")
        print("=" * 60)
        
        # Busca o evento no banco
        eventos = db_manager.listar_eventos()
        evento = next((e for e in eventos if e["id"] == evento_id), None)
        
        if evento:
            meta = evento["metadata"]
            print(f"\n📋 DADOS DO EVENTO:")
            print(f"   ID: {evento['id']}")
            print(f"   Nome: {meta.get('nome', 'N/A')}")
            print(f"   Data: {meta.get('data', 'N/A')}")
            print(f"   Horário: {meta.get('horario', 'N/A')}")
            print(f"   Local: {meta.get('local', 'N/A')}")
            print(f"   Classificação: {meta.get('classificacao', 'N/A')}")
            print(f"   Plataforma: {meta.get('plataforma', 'N/A')}")
            print(f"   URL Original: {meta.get('url_original', 'N/A')}")
        
        # Mostra estatísticas
        stats = db_manager.obter_estatisticas()
        print(f"\n📊 ESTATÍSTICAS DO BANCO:")
        print(f"   Total de eventos: {stats['eventos']}")
        print(f"   Total de documentos: {stats['total_documentos']}")
        
    else:
        print("\n❌ FALHA NA EXTRAÇÃO")
        print("   Não foi possível extrair dados do evento.")
        print("   Verifique se a URL está correta e tente novamente.")
    
    print("\n" + "=" * 60)


async def listar_todos_eventos():
    """Lista todos os eventos no banco."""
    
    print("\n📋 TODOS OS EVENTOS NO BANCO:")
    print("-" * 60)
    
    eventos = db_manager.listar_eventos()
    
    if not eventos:
        print("   Nenhum evento encontrado.")
        return
    
    for i, evento in enumerate(eventos, 1):
        meta = evento["metadata"]
        print(f"\n{i}. {meta.get('nome', 'Sem nome')}")
        print(f"   ID: {evento['id']}")
        print(f"   Data: {meta.get('data', 'N/A')}")
        print(f"   Local: {meta.get('local', 'N/A')}")
    
    print("-" * 60)
    print(f"Total: {len(eventos)} eventos\n")


async def main():
    """Função principal."""
    
    if len(sys.argv) < 2:
        print("Uso: python testar_extrator.py <url_do_evento>")
        print("\nExemplo:")
        print("  python testar_extrator.py https://baladapp.com.br/evento/xxx")
        print("\nOu para listar todos os eventos:")
        print("  python testar_extrator.py --listar")
        sys.exit(1)
    
    arg = sys.argv[1]
    
    if arg == "--listar":
        await listar_todos_eventos()
    else:
        await testar_extracao(arg)


if __name__ == "__main__":
    asyncio.run(main())
