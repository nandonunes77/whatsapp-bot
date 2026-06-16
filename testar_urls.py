#!/usr/bin/env python3
"""Testa extração de múltiplos eventos reais."""
import asyncio
import sys
from pathlib import Path

PASTA_ATUAL = Path(__file__).parent
sys.path.insert(0, str(PASTA_ATUAL))

from extractor import event_extractor
from database import db_manager


async def testar_urls(urls):
    for url in urls:
        print("\n" + "=" * 70)
        print(f"🔍 TESTANDO: {url}")
        print("=" * 70)

        evento_id = await event_extractor.extrair_e_salvar(url)

        if evento_id:
            eventos = db_manager.listar_eventos()
            evento = next((e for e in eventos if e["id"] == evento_id), None)
            if evento:
                meta = evento["metadata"]
                print(f"\n✅ Resultado:")
                print(f"   Nome: {meta.get('nome', 'N/A')}")
                print(f"   Data: {meta.get('data', 'N/A')}")
                print(f"   Horário: {meta.get('horario', 'N/A')}")
                print(f"   Local: {meta.get('local', 'N/A')}")
                print(f"   Plataforma: {meta.get('plataforma', 'N/A')}")
        else:
            print("❌ Falhou")

    print("\n" + "=" * 70)
    stats = db_manager.obter_estatisticas()
    print(f"\n📊 Total de eventos no banco: {stats['eventos']}")


async def main():
    urls = [
        "https://www.guichelive.com.br/geriatricus-montes-claros_51842",
        "https://baladapp.com.br/pt-BR/eventos/ralf-40-anos-de-sucesso/8622",
        "https://baladapp.com.br/pt-BR/eventos/capital-inicial-em-uberlandia/8395",
        "https://www.ticket360.com.br/evento/33224/ingressos-para-victor-e-leo-turne-essencia",
        "https://www.meubilhete.com.br/turne-25-anos-ana-carolina",
    ]
    await testar_urls(urls)


if __name__ == "__main__":
    asyncio.run(main())
