#!/bin/bash
# Script de instalación y configuración para GESAD MCP + API n8n

set -e

echo "🚀 Instalando GESAD MCP con API para n8n"
echo "================================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funciones de ayuda
log_info() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 1. Verificar Python y pip
echo "📦 Verificando dependencias base..."
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 no encontrado. Por favor instala Python 3.8+"
    exit 1
fi

if ! command -v pip &> /dev/null; then
    log_error "pip no encontrado. Por favor instala pip"
    exit 1
fi

log_info "Python 3 y pip encontrados"

# 2. Crear directorio de trabajo
WORK_DIR="/opt/gesad-api"
echo "📁 Creando directorio en $WORK_DIR..."
sudo mkdir -p $WORK_DIR
sudo chown $USER:$USER $WORK_DIR

# Copiar archivos al directorio de trabajo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📋 Copiando archivos desde $SCRIPT_DIR a $WORK_DIR..."
cp -r $SCRIPT_DIR/* $WORK_DIR/
cd $WORK_DIR

# 3. Crear entorno virtual
echo "🐍 Creando entorno virtual..."
python3 -m venv venv
source venv/bin/activate

# 4. Instalar dependencias
echo "📦 Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Configurar archivo .env
if [ ! -f .env ]; then
    echo "⚙️ Creando archivo .env de configuración..."
    cat > .env << EOF
# GESAD API Configuration
GESAD_API_USER=userws_artris
GESAD_API_PASSWORD=JFN23Pb#QB&1Jz6
GESAD_API_CODE=ARTRIS_4Jk#pL%1@
GESAD_SESSION_ID=R0_F5FB07C4-0E63-4A7A-BA8A-43108D19224B
GESAD_CONEX_NAME=CLOUD01
GESAD_BASE_URL=https://data-bi.ayudadomiciliaria.com/api

# System Configuration
ACTIVE_START=06:00
ACTIVE_END=24:00
TIMEZONE=Europe/Madrid
MONITORING_INTERVAL=1200
DAILY_LIMIT=500
CACHE_DIR=./cache
LOG_LEVEL=INFO

# API Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
EOF
    log_info "Archivo .env creado"
else
    log_warn "Archivo .env ya existe, manteniendo configuración actual"
fi

# 6. Crear directorio de cache
echo "💾 Creando directorio de cache..."
mkdir -p cache

# 7. Verificar configuración
echo "🔍 Verificando configuración..."
python -c "
from config import config
try:
    config.validate()
    print('✅ Configuración válida')
except Exception as e:
    print(f'❌ Error configuración: {e}')
    exit(1)
"

# 8. Crear servicio systemd
echo "🔧 Creando servicio systemd..."
sudo tee /etc/systemd/system/gesad-api.service > /dev/null << EOF
[Unit]
Description=GESAD MCP API for n8n
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR
Environment=PATH=$WORK_DIR/venv/bin
EnvironmentFile=$WORK_DIR/.env
ExecStart=$WORK_DIR/venv/bin/python api_server.py --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 9. Configurar firewall
echo "🔥 Configurando firewall..."
sudo ufw --force enable
sudo ufw allow 8000/tcp
sudo ufw reload

# 10. Iniciar y habilitar servicio
echo "🚀 Iniciando servicio GESAD API..."
sudo systemctl daemon-reload
sudo systemctl enable gesad-api.service
sudo systemctl start gesad-api.service

# 11. Esperar y verificar
echo "⏳ Esperando inicio del servicio..."
sleep 10

# Verificar estado
if sudo systemctl is-active --quiet gesad-api.service; then
    log_info "Servicio GESAD API iniciado correctamente"
else
    log_error "Error al iniciar el servicio"
    sudo journalctl -u gesad-api.service --no-pager -l
    exit 1
fi

# 12. Probar API
echo "🧪 Probando endpoints de la API..."

# Obtener IP del servidor
SERVER_IP=$(curl -s ifconfig.me || echo "localhost")
API_URL="http://$SERVER_IP:8000"

echo "🌐 URL de la API: $API_URL"

# Health check
if curl -f -s "$API_URL/health" > /dev/null; then
    log_info "Health check exitoso"
else
    log_error "Health check falló"
    exit 1
fi

# Probar endpoint principal
echo "📊 Probando endpoint de datos..."
RESPONSE=$(curl -s "$API_URL/datos-cruzados")
if echo "$RESPONSE" | grep -q '"success": true'; then
    log_info "Endpoint de datos funcionando"
else
    log_warn "Endpoint de datos pudo tener problemas"
fi

# 13. Mostrar información final
echo ""
echo "🎉 INSTALACIÓN COMPLETADA"
echo "==========================="
echo ""
echo "📍 Información del Sistema:"
echo "   🌐 API URL: $API_URL"
echo "   📚 Documentación: $API_URL/docs"
echo "   🔍 Health Check: $API_URL/health"
echo ""
echo "🔧 Comandos útiles:"
echo "   📊 Ver estado: sudo systemctl status gesad-api.service"
echo "   📋 Ver logs: sudo journalctl -u gesad-api.service -f"
echo "   🔄 Reiniciar: sudo systemctl restart gesad-api.service"
echo "   ⏹️  Detener: sudo systemctl stop gesad-api.service"
echo ""
echo "📗 Endpoints para n8n:"
echo "   📊 Datos cruzados: GET $API_URL/datos-cruzados"
echo "   📋 Informes ausencias: GET $API_URL/informes/ausencias?tipo=sin_fichaje"
echo "   👥 Resumen usuarios: GET $API_URL/resumen/usuarios"
echo "   📈 Estadísticas: GET $API_URL/estadisticas"
echo "   🖥️ Dashboard: GET $API_URL/dashboard"
echo "   ⚡ Forzar verificación: POST $API_URL/monitoring/force-check"
echo ""
echo "📖 Documentación completa:"
echo "   cat $WORK_DIR/N8N_INTEGRATION.md"
echo ""
log_info "¡Sistema GESAD MCP + API n8n listo para usar!"