#!/bin/bash
# ╔══════════════════════════════════════════╗
# ║   STOP - WhatsApp Bot + Bridge          ║
# ║   Para todos os serviços                ║
# ╚══════════════════════════════════════════╝

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}🛑 Parando serviços...${NC}"
echo ""

# Para Python server
echo -n "   Parando Python server... "
if pkill -f "python3 bot.py" 2>/dev/null; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${YELLOW}⚠️  Não encontrado${NC}"
fi

# Para WhatsApp bridge
echo -n "   Parando WhatsApp bridge... "
if pkill -f "node index.js" 2>/dev/null; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${YELLOW}⚠️  Não encontrado${NC}"
fi

# Espera processos terminarem
sleep 2

# Verifica se ainda há processos
echo ""
echo -e "${BLUE}📊 Status:${NC}"

PYTHON_RUNNING=$(pgrep -f "python3 bot.py" > /dev/null 2>&1 && echo "sim" || echo "não")
NODE_RUNNING=$(pgrep -f "node index.js" > /dev/null 2>&1 && echo "sim" || echo "não")

if [ "$PYTHON_RUNNING" = "não" ] && [ "$NODE_RUNNING" = "não" ]; then
    echo -e "   • Python server: ${GREEN}Parado${NC}"
    echo -e "   • WhatsApp bridge: ${GREEN}Parado${NC}"
    echo ""
    echo -e "${GREEN}✅ Todos os serviços foram parados${NC}"
else
    echo -e "   • Python server: ${RED}Ainda rodando${NC}"
    echo -e "   • WhatsApp bridge: ${RED}Ainda rodando${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Alguns serviços ainda estão rodando${NC}"
    echo -e "${YELLOW}   Tente: pkill -f 'python3 bot.py' && pkill -f 'node index.js'${NC}"
fi

echo ""
