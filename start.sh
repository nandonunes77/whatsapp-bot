#!/bin/bash
# ╔══════════════════════════════════════════╗
# ║   STARTUP - WhatsApp Bot + Bridge       ║
# ║   Inicia todos os serviços              ║
# ╚══════════════════════════════════════════╝

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Diretório do projeto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Função para limpar processos ao sair
cleanup() {
    echo -e "\n${YELLOW}🛑 Parando serviços...${NC}"
    
    # Mata processos filhos
    if [ ! -z "$PYTHON_PID" ]; then
        kill $PYTHON_PID 2>/dev/null
        echo -e "${RED}   Python server parado${NC}"
    fi
    
    if [ ! -z "$NODE_PID" ]; then
        kill $NODE_PID 2>/dev/null
        echo -e "${RED}   WhatsApp bridge parada${NC}"
    fi
    
    # Mata processos por nome (caso tenha escapado)
    pkill -f "python3 bot.py" 2>/dev/null
    pkill -f "node index.js" 2>/dev/null
    
    echo -e "${GREEN}✅ Serviços parados${NC}"
    exit 0
}

# Captura Ctrl+C
trap cleanup SIGINT SIGTERM

# Função para verificar se porta está em uso
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0
    else
        return 1
    fi
}

# Função para esperar serviço ficar pronto
wait_for_service() {
    local name=$1
    local url=$2
    local max_attempts=30
    local attempt=1
    
    echo -n "   Aguardando $name"
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}✅${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    echo -e " ${RED}❌${NC}"
    return 1
}

# Banner
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   🤖 WhatsApp Bot - Triângulo           ║${NC}"
echo -e "${BLUE}║   Iniciando serviços...                 ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# Verifica se porta 8000 já está em uso
if check_port 8000; then
    echo -e "${YELLOW}⚠️  Porta 8000 já em uso. Matando processo...${NC}"
    pkill -f "python3 bot.py" 2>/dev/null
    sleep 2
fi

# ========== PYTHON SERVER ==========
echo -e "${BLUE}📦 Iniciando Python server...${NC}"
cd "$PROJECT_DIR"

# Ativa venv e inicia servidor
source venv/bin/activate
python3 bot.py > /tmp/whatsapp-bot-python.log 2>&1 &
PYTHON_PID=$!

# Espera servidor ficar pronto
if wait_for_service "Python server" "http://localhost:8000/health"; then
    echo -e "${GREEN}   ✅ Python server rodando (PID: $PYTHON_PID)${NC}"
else
    echo -e "${RED}   ❌ Falha ao iniciar Python server${NC}"
    echo -e "${YELLOW}   📋 Log: /tmp/whatsapp-bot-python.log${NC}"
    cleanup
fi

# ========== WHATSAPP BRIDGE ==========
echo -e "${BLUE}📱 Iniciando WhatsApp bridge...${NC}"
cd "$PROJECT_DIR/whatsapp-bridge"

# Verifica se node_modules existe
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}   ⚠️  node_modules não encontrado. Instalando...${NC}"
    npm install
fi

# Inicia bridge
node index.js > /tmp/whatsapp-bot-bridge.log 2>&1 &
NODE_PID=$!

sleep 2

# Verifica se bridge está rodando
if kill -0 $NODE_PID 2>/dev/null; then
    echo -e "${GREEN}   ✅ WhatsApp bridge rodando (PID: $NODE_PID)${NC}"
else
    echo -e "${RED}   ❌ Falha ao iniciar WhatsApp bridge${NC}"
    echo -e "${YELLOW}   📋 Log: /tmp/whatsapp-bot-bridge.log${NC}"
    cleanup
fi

# ========== STATUS ==========
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ Serviços iniciados com sucesso!    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📊 Status:${NC}"
echo -e "   • Python server: ${GREEN}http://localhost:8000${NC}"
echo -e "   • WhatsApp bridge: ${GREEN}Rodando${NC}"
echo -e "   • Health check: ${GREEN}http://localhost:8000/health${NC}"
echo ""
echo -e "${BLUE}📋 Comandos úteis:${NC}"
echo -e "   • Ver logs Python: ${YELLOW}tail -f /tmp/whatsapp-bot-python.log${NC}"
echo -e "   • Ver logs Bridge: ${YELLOW}tail -f /tmp/whatsapp-bot-bridge.log${NC}"
echo -e "   • Parar serviços: ${YELLOW}Ctrl+C${NC}"
echo ""
echo -e "${BLUE}🔍 QR Code:${NC}"
echo -e "   • Se precisar escanear QR code, veja o log da bridge"
echo -e "   • O QR code é válido por ~20 segundos"
echo -e "   • Se não escanear, espera 5 minutos e tenta de novo"
echo ""

# Mantém script rodando e mostra logs
echo -e "${YELLOW}📋 Logs em tempo real (Ctrl+C para sair):${NC}"
echo ""

# Mostra logs em tempo real
tail -f /tmp/whatsapp-bot-python.log /tmp/whatsapp-bot-bridge.log 2>/dev/null &
TAIL_PID=$!

# Espera indefinidamente
wait $TAIL_PID
