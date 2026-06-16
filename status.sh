#!/bin/bash
# ╔══════════════════════════════════════════╗
# ║   STATUS - WhatsApp Bot + Bridge        ║
# ║   Verifica status dos serviços          ║
# ╚══════════════════════════════════════════╝

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   📊 Status dos Serviços               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# Verifica Python server
echo -n "   Python server (porta 8000): "
if curl -s "http://localhost:8000/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Rodando${NC}"
    
    # Mostra estatísticas
    echo ""
    echo -e "${BLUE}   📊 Estatísticas:${NC}"
    curl -s "http://localhost:8000/estatisticas" 2>/dev/null | python3 -m json.tool 2>/dev/null | sed 's/^/      /'
else
    echo -e "${RED}❌ Parado${NC}"
fi

echo ""

# Verifica WhatsApp bridge
echo -n "   WhatsApp bridge: "
if pgrep -f "node index.js" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Rodando${NC}"
    
    # Mostra PID
    PID=$(pgrep -f "node index.js" | head -1)
    echo -e "      PID: $PID"
else
    echo -e "${RED}❌ Parado${NC}"
fi

echo ""

# Verifica logs recentes
echo -e "${BLUE}📋 Logs recentes:${NC}"
echo ""

if [ -f "/tmp/whatsapp-bot-python.log" ]; then
    echo -e "   ${YELLOW}Python server (últimas 5 linhas):${NC}"
    tail -5 /tmp/whatsapp-bot-python.log 2>/dev/null | sed 's/^/      /'
else
    echo -e "   ${YELLOW}Python server: Sem logs${NC}"
fi

echo ""

echo -e "   ${YELLOW}WhatsApp bridge: Output direto no terminal${NC}"
echo -e "   ${YELLOW}   (QR code aparece ao iniciar com ./start.sh)${NC}"

echo ""

# Comandos úteis
echo -e "${BLUE}📋 Comandos úteis:${NC}"
echo -e "   • Iniciar: ${YELLOW}./start.sh${NC}"
echo -e "   • Parar: ${YELLOW}./stop.sh${NC}"
echo -e "   • Ver logs: ${YELLOW}tail -f /tmp/whatsapp-bot-*.log${NC}"
echo ""
