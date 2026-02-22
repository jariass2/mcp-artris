#!/bin/bash

echo "🔧 Configurando credenciales GESAD"
echo "================================"
echo ""

# Mostrar el archivo actual
echo "📋 Archivo .env actual:"
echo ""
cat .env | head -4
echo ""

echo "❗ Necesitas editar las líneas 2 y 3 del archivo .env:"
echo ""
echo "📍 Ubicación del archivo:"
echo "   $(pwd)/.env"
echo ""

echo "📝 Valores a configurar:"
echo ""
echo "Línea 2: GESAD_CONEX_NAME=nombre_centro_trabajo"
echo "   → Debe ser tu nombre de centro de trabajo real"
echo ""

echo "Línea 3: GESAD_AUTH_CODE=tu_auth_code_aqui"  
echo "   → Debe ser tu código de autorización real"
echo ""

echo "💡 Ejemplo:"
echo "   GESAD_CONEX_NAME=Madrid-Centro"
echo "   GESAD_AUTH_CODE=JfN23Pb#QB&1Jz6"
echo ""

echo "🔨 Opciones para editar:"
echo "1️⃣ Editor de texto: nano .env"
echo "2️⃣ Editor VS Code: code .env" 
echo "3️⃣ Editor de Mac: open -e .env"
echo ""

echo "⚠️ Después de editar, ejecuta:"
echo "   python server.py"
echo ""

echo "🎯 SESSION_ID ya está configurado correctamente:"
echo "   R0_F5FB07C4-0E63-4A7A-BA8A-43108D19224B"
echo ""

read -p "¿Quieres abrir el editor ahora? (s/n): " choice
if [[ $choice == "s" || $choice == "S" ]]; then
    echo "📝 Abriendo editor..."
    nano .env
fi