# MCP Server GESAD - Sistema de Monitoreo de Asistencia

## 📋 Descripción

Sistema completo de monitoreo de asistencia para GESAD con Model Context Protocol (MCP) que permite:

- **Monitoreo automático**: Cada 20 minutos durante horario 6:00 AM - 12:00 PM
- **Detección de ausencias**: Ventana de 20 minutos post-hora prevista
- **Alertas automáticas**: Para ausencias y llegadas tardías
- **Dashboard en tiempo real**: Estado actual del sistema
- **Consumo optimizado**: Solo 18 llamadas API diarias (3.6% del límite de 500)

## 📚 Documentación Completa

Toda la documentación está consolidada en un solo archivo:

**[📘 DOCUMENTACIÓN COMPLETA](docs/DOCUMENTACION_COMPLETA.md)**

Incluye:
- Descripción del sistema
- Instalación y configuración
- Lógica del sistema y supuestos implementados
- Configuración de webhooks
- Integración con n8n
- Scripts de utilidad
- Variables de entorno
- Mensajes configurados

## 🚀 Instalación y Configuración

### 1. Instalar Dependencias
```bash
cd mcp-gesad
pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno
```bash
cp .env.example .env
# Editar .env con tus credenciales de GESAD
```

### 3. Configurar Credenciales
```env
GESAD_CONEX_NAME=nombre_centro_trabajo
GESAD_AUTH_CODE=tu_auth_code_aqui
GESAD_SESSION_ID=R0_F5FB07C4-0E63-4A7A-BA8A-43108D19224B
```

## 🏃‍♂️ Ejecución

### Modo MCP Server (Con Claude Desktop)
```bash
python server.py
```

### Modo Standalone (Solo monitoreo)
```bash
# El sistema funcionará aunque MCP no esté disponible
python server.py
```

## 📊 Funcionalidades Principales

### MCP Tools (Operaciones)
- `get_estado_asistencia_actual()` - Estado actual del monitoreo
- `get_alertas_activas()` - Alertas activas del sistema
- `get_system_status()` - Estado completo del sistema
- `force_verification()` - Forzar verificación manual

### MCP Resources (Datos Formateados)
- `gesad://monitoring/live-dashboard` - Dashboard en tiempo real
- `gesad://monitoring/system-status` - Estado del sistema para IA
- `gesad://trabajador/{id}` - Perfil individual de trabajador
- `gesad://equipo/resumen/{depto}` - Resumen por departamento

### Sistema Automático
- **Scheduler**: Control de horarios 6:00 AM - 12:00 PM
- **Caché Inteligente**: Datos de trabajadores 7 días, fichajes 5 min
- **Rate Limiting**: Máximo 18 llamadas API diarias
- **Alertas**: Ausencias con 20 min tolerancia, llegadas tardías

## 📈 Uso con Claude Desktop

### Configuración
Editar `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gesad-asistencia": {
      "command": "python",
      "args": ["/ruta/absoluta/al/mcp-gesad/server.py"],
      "env": {
        "GESAD_CONEX_NAME": "nombre_centro_trabajo",
        "GESAD_AUTH_CODE": "tu_auth_code",
        "GESAD_SESSION_ID": "R0_F5FB07C4-0E63-4A7A-BA8A-43108D19224B"
      }
    }
  }
}
```

### Ejemplos de Consultas
- "Muéstrame el dashboard actual de asistencia"
- "¿Quiénes no han fichado hoy?"
- "Resumen de alertas activas"
- "Estado del sistema de monitoreo"
- "Forzar verificación manual"

## 🏗️ Arquitectura

### Componentes
- **server.py** - MCP server principal con tools y resources
- **gesad_client.py** - Cliente HTTP para API GESAD
- **scheduler.py** - Sistema de horarios y monitoreo
- **cache_manager.py** - Caché multinivel persistente
- **data_processor.py** - Procesamiento y análisis de asistencia
- **alert_manager.py** - Sistema de alertas automático
- **config.py** - Configuración centralizada

### Flujo de Monitoreo
```
Cada 20 min (6:00-12:00):
1. Scheduler activa verificación
2. Cliente API obtiene fichajes del día (1 llamada)
3. Data processor analiza estado trabajadores
4. Alert manager genera alertas si corresponde
5. Results se guardan en cache (20 min TTL)
6. MCP tools/resources acceden datos cacheados
```

## 📊 Performance y Optimización

### Consumo API
- **Llamadas diarias**: 18 (cada 20 min, 6 horas activas)
- **Uso del límite**: 3.6% (18/500 llamadas disponibles)
- **Cache hit rate**: >90% (datos trabajadores cacheados)
- **Response time**: <2 segundos (datos cacheados)

### Estrategias de Caché
- **Trabajadores**: 7 días (cambian poco)
- **Fichajes del día**: 5 min (datos en tiempo real)
- **Dashboard**: 20 min (intervalo de verificación)
- **Alertas**: 1 hora (estado actual)

## 🧪 Testing

### Ejecutar Tests
```bash
python -m pytest tests/ -v
```

### Tests Disponibles
- Configuración del sistema
- Sistema de caché
- Scheduler y horarios
- Generación de alertas
- Procesamiento de datos
- Integración completa

## 🔧 Configuración Avanzada

### Variables de Entorno
```env
# Horarios (6 AM - 12 PM)
GESAD_ACTIVE_START=6
GESAD_ACTIVE_END=12
GESAD_CHECK_INTERVAL=20

# Cache
GESAD_CACHE_DIR=./cache
GESAD_CACHE_PERSISTENT_DAYS=7

# Límites API
GESAD_DAILY_LIMIT=500
GESAD_EMERGENCY_BUFFER=50

# Performance
GESAD_REQUEST_TIMEOUT=30
GESAD_BATCH_SIZE=20
GESAD_RETRY_ATTEMPTS=3
```

### Monitoreo y Logs
```bash
# Ver logs del sistema
tail -f logs/gesad_monitoring.log

# Estadísticas de caché
curl "http://localhost:8080/api/cache-stats"

# Estado del sistema
curl "http://localhost:8080/api/system-status"
```

## 🚨 Gestión de Alertas

### Tipos de Alertas
- **Ausencia no detectada**: Alta prioridad, requiere acción
- **Llegada tardía**: Media prioridad, informativa

### Canales de Notificación
- Email (para ausencias)
- Slack/Teams (opcional)
- Dashboard en tiempo real

### Manejo de Alertas
```python
# Ver alertas activas
await get_alertas_activas()

# Filtrar por tipo
await get_alertas_activas(tipo='ausencia_no_detectada')

# Marcar como resuelta
await alert_manager.marcar_alerta_resuelta(alerta_id, "Contactado por teléfono")
```

## 📈 Métricas y KPIs

### Indicadores Clave
- **Tasa de asistencia**: % de trabajadores presentes
- **Tasa de puntualidad**: % de llegadas a tiempo
- **Promedio de tardanzas**: Minutos promedio de retraso
- **Hit rate de caché**: Eficiencia del sistema
- **Uso de API**: Consumo del límite diario

### Reportes Automáticos
- **Diario**: Resumen de asistencia del día
- **Semanal**: Tendencias y patrones
- **Mensual**: Estadísticas consolidadas

## 🆘 Troubleshooting

### Problemas Comunes

#### El scheduler no se inicia
```bash
# Verificar configuración de horarios
python -c "from config import config; print(config.is_active_time())"

# Revisar logs de errores
tail -f logs/gesad_monitoring.log
```

#### No se obtienen datos de la API
```bash
# Probar conexión manual
python -c "
import asyncio
from gesad_client import gesad_client
result = asyncio.run(gesad_client.get_fichajes_dia('2023-01-01'))
print(result)
"
```

#### Caché no funciona
```bash
# Limpiar caché
rm -rf cache/*

# Verificar permisos
ls -la cache/
```

### Logs y Debug
```python
# Nivel de log DEBUG
GESAD_LOG_LEVEL=DEBUG python server.py

# Ver estadísticas en tiempo real
python -c "
import asyncio
from cache_manager import cache_manager
stats = asyncio.run(cache_manager.get_stats())
print(stats)
"
```

## 📞 Soporte

Para soporte técnico:
1. Verificar logs del sistema
2. Revisar configuración de API
3. Validar credenciales de GESAD
4. Comprobar límites de rate limiting

---

## ☁️ Despliegue en Producción

### Requisitos de Infraestructura

| Componente | Tecnología | Notas |
|------------|------------|-------|
| **Servidor** | VPS (Ubuntu 22.04) | Mínimo 2CPU, 4GB RAM |
| **Panel** | EasyPanel | Gestión de contenedores |
| **n8n** | Docker | Orquestación de webhooks |
| **PostgreSQL** | Docker | Almacenamiento de datos |
| **MCP GESAD** | Docker | Puerto 9999 |

### Puertos

| Puerto | Servicio |
|--------|----------|
| 80/443 | EasyPanel + n8n |
| 5678 | n8n (opcional) |
| 5432 | PostgreSQL |
| 9999 | MCP GESAD |

### Chat NLP con OpenWebUI + OpenRouter (Opcional)

Para consultas en lenguaje natural sobre los datos:

```
OpenWebUI → OpenRouter (GLM-4.7/Kimi) → MCPO → MCP GESAD → PostgreSQL
```

Coste: ~5-15€/mes via OpenRouter

Ver docs/PLAN_REPORTING_POSTGRESQL.md para más detalles.

### Configuración Rápida OpenWebUI

```bash
# 1. Obtener API Key de OpenRouter: https://openrouter.ai

# 2. Docker Compose:
version: '3.8'
services:
  openwebui:
    image: openwebui/open-webui:main
    ports:
      - "3000:8080"
    environment:
      - OPENAI_API_KEY=${OPENROUTER_API_KEY}
      - OPENAI_API_BASE_URL=https://openrouter.ai/v1

  mcpo:
    image: openwebui/mcpo:latest
    ports:
      - "8000:8000"
    command: --port 8000 python /path/to/server.py

# 3. Acceder a http://localhost:3000
```

### Herramientas Disponibles en OpenWebUI

- `get_estado_asistencia_actual()` - Estado actual del monitoreo
- `get_alertas_activas()` - Alertas activas del sistema
- `get_system_status()` - Estado completo del sistema
- `force_verification()` - Forzar verificación manual

## 📄 Licencia

Este proyecto está licenciado bajo los términos de licencia de la empresa.

---

**MCP GESAD Asistencia Server** - Sistema completo de monitoreo con inteligencia artificial integrada.