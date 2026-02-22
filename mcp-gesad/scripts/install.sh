#!/bin/bash

# Script de instalación y configuración del MCP Server GESAD

echo "🚀 Instalando MCP Server GESAD..."

# 1. Crear entorno virtual
echo "📦 Creando entorno virtual..."
python3 -m venv venv
source venv/bin/activate

# 2. Instalar dependencias
echo "📥 Instalando dependencias..."
pip install -r requirements.txt

# 3. Crear directorio de cache
echo "📁 Creando directorios necesarios..."
mkdir -p cache
mkdir -p logs

# 4. Configurar archivo .env
if [ ! -f .env ]; then
    echo "⚙️ Configurando archivo .env..."
    cp .env.example .env
    echo "✅ Archivo .env creado. Por favor edita con tus credenciales:"
    echo "   - GESAD_CONEX_NAME: Tu nombre de centro de trabajo"
    echo "   - GESAD_AUTH_CODE: Tu código de autorización"
    echo "   - GESAD_SESSION_ID: ID de sesión (por defecto ya configurado)"
fi

# 5. Ejecutar tests básicos
echo "🧪 Ejecutando tests de validación..."
python -m pytest tests/ -v --tb=short

# 6. Verificar configuración
echo "🔍 Verificando configuración..."
python -c "
try:
    from config import config
    config.validate()
    print('✅ Configuración válida')
except ValueError as e:
    print(f'❌ Error en configuración: {e}')
    print('Por favor edita el archivo .env con tus credenciales')
"

echo ""
echo "🎉 Instalación completada!"
echo ""
echo "📋 Próximos pasos:"
echo "1. Edita el archivo .env con tus credenciales de GESAD"
echo "2. Ejecuta: python server.py"
echo "3. Configura Claude Desktop si es necesario"
echo ""
echo "📖 Consulta README.md para más información"