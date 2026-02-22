# GESAD MCP - Documentación Completa

Sistema de monitoreo de fichajes para Servicios de Atención Domiciliaria (SAD) con integración MCP y notificaciones vía webhooks.

---

## 📋 Índice

1. [Descripción del Sistema](#1-descripción-del-sistema)
2. [Instalación y Configuración](#2-instalación-y-configuración)
3. [Lógica del Sistema](#3-lógica-del-sistema)
4. [Configuración de Webhooks](#4-configuración-de-webhooks)
5. [Integración con n8n](#5-integración-con-n8n)
6. [Scripts de Utilidad](#6-scripts-de-utilidad)
7. [Variables de Entorno](#7-variables-de-entorno)
8. [Mensajes Configurados](#8-mensajes-configurados)
9. [Sistema de Caché y Carga de Datos](#9-sistema-de-caché-y-carga-de-datos)
10. [Soporte](#10-soporte)
11. [Requisitos de Despliegue](#10-requisitos-de-despliegue)

---

## 1. Descripción del Sistema

Sistema completo de monitoreo de asistencia para GESAD con Model Context Protocol (MCP) que permite:

- **Monitoreo automático**: Cada 20 minutos durante horario 6:00 AM - 12:00 PM
- **Detección de ausencias**: Ventana de 20 minutos post-hora prevista
- **Alertas automáticas**: Para ausencias y llegadas tardías
- **Dashboard en tiempo real**: Estado actual del sistema
- **Consumo optimizado**: Solo 18 llamadas API diarias (3.6% del límite de 500)

### Supuestos Implementados

| # | Tipo de Alerta | Condición | Umbral |
|---|---------------|-----------|---------|
| 1 | `fichaje_adelantado` | Llegada 20+ min antes | 20 min |
| 2 | `ubicacion_fuera_rango` | GPS fuera del domicilio | 50 metros |
| 3 | `fichaje_manual_sin_gps_qr` | Fichaje manual sin ubicación | - |
| 4 | `retraso_confirmado` | 20+ min después de hora prevista | 20 min |
| 5 | `salida_adelantada` | Salida 10+ min antes | 10 min |
| 6 | `salida_tarde` | Salida 10+ min después | 10 min |

---

## 2. Instalación y Configuración

### 2.1 Requisitos Previos

- Python 3.12 o superior
- Credenciales de API de GESAD
- n8n instalado (opcional, para webhooks)

### 2.2 Instalación

```bash
# Clonar el repositorio
git clone https://github.com/jariass2/MCP_Artris.git
cd MCP_Artris/mcp-gesad

# Instalar dependencias
pip install -r requirements.txt
```

### 2.3 Configuración

```bash
# Copiar plantilla de variables de entorno
cp .env.example .env

# Editar .env con tus credenciales
nano .env
```

### 2.4 Verificar Configuración

```bash
python scripts/verificar_configuracion.py
```

### 2.5 Ejecución

```bash
# Modo MCP Server (Con Claude Desktop)
python server.py

# Modo Standalone (Solo monitoreo)
python start_monitoring.py --standalone

# Cargar datos maestros
python scripts/cargar_datos_master.py
```

---

## 3. Lógica del Sistema

### 3.1 Estados de Fichajes

El sistema clasifica cada fichaje en uno de los siguientes estados:

#### 1. **Sin Fichaje (Ausencia)**
```
❌ Entrada: (vacío)
❌ Salida: (vacío)
📊 Estado: SIN FICHAJE (Ausencia)
```

#### 2. **Fichaje Parcial (Llegada Tarde)**
```
✅ Entrada: 08:25
❌ Salida: (vacío)
📊 Estado: PARCIAL (Sin salida)
```

#### 3. **Fichaje Adelantado**
```
⏰ Hora prevista: 08:00
🕐 Entrada real: 07:35
📊 Estado: ADELANTADO (25 min antes)
```

#### 4. **Fichaje Completo**
```
⏰ Hora prevista: 08:00
🕐 Entrada real: 07:58
✅ Salida: 16:02
📊 Estado: COMPLETO (A tiempo)
```

### 3.2 Caché de Datos

El sistema utiliza un sistema de caché multinivel:

- **Caché en memoria**: Datos frecuentes (usuarios, trabajadores)
- **Caché en disco**: Datos persistentes con TTL configurado
- **Precarga al inicio**: 2198 usuarios y 268 trabajadores cargados al arranque

### 3.3 Procesamiento de Fichajes

1. **Filtrar por período**: Solo fichajes en ventana de 40 minutos (±20 min de hora actual)
2. **Cruzar datos**: Asociar con usuario y trabajador
3. **Validar ubicación GPS**: Verificar si fichaje está dentro del domicilio (umbral: 50m)
4. **Clasificar estado**: Determinar tipo de ausencia/fichaje
5. **Generar alertas**: Enviar webhooks según configuración
6. **Actualizar caché**: Marcar fichajes como procesados

---

## 4. Configuración de Webhooks

### 4.1 Habilitar Webhooks

En el archivo `.env`:

```env
GESAD_WEBHOOK_ENABLED=true
GESAD_WEBHOOK_URL=https://n8n.multiplai.org/webhook/fichaje
GESAD_WEBHOOK_TIMEOUT=30
GESAD_WEBHOOK_EVENTS=ausencia,fichaje_manual,retraso_confirmado,salida_adelantada,salida_tarde,fichaje_adelantado,ubicacion_fuera_rango
```

### 4.2 Distancia GPS en Webhooks

Todos los webhooks incluyen un campo `ubicacion` con la siguiente estructura:

```json
{
  "ubicacion": {
    "tiene_gps": true/false,
    "distancia_metros": 45.6,
    "descripcion": "45.6 metros del domicilio",
    "gps_fichaje": {
      "latitud": "41.674202",
      "longitud": "2.7879543"
    },
    "gps_domicilio": {
      "latitud": "41.6733853",
      "longitud": "2.7879543"
    }
  }
}
```

**Tipos de GPS:**

| Tipo | Origen | Campos GPS | Uso |
|------|---------|-------------|-----|
| **GPS del Fichaje (trabajador)** | `Fichaje_Ent_Gps_Lat`, `Fichaje_Ent_Gps_Lon` | Entrada/salida del trabajador - Valida si estaba en domicilio |
| **GPS del Usuario (domicilio)** | `usuario['Gis_Latitud']`, `usuario['Gis_Longitud']` | Domicilio del usuario - Usado como referencia cuando NO hay GPS del fichaje |

**Lógica de cálculo:**

```
SI el fichaje tiene GPS del trabajador (Fichaje_Ent_Gps_Lat/Lon):
    distancia = distancia(GPS_fichaje, GPS_domicilio)
    calcula y muestra la distancia en metros o km

SI el fichaje NO tiene GPS del trabajador:
    distancia = null
    motivo = "sin GPS del fichaje" o "sin GPS del domicilio"
    descripcion = "No se puede calcular: sin GPS del fichaje"
```

**Casos de distancia null:**

| Caso | GPS Fichaje | GPS Domicilio | Resultado |
|------|-------------|---------------|-----------|
| 1 | ✅ Disponible | ✅ Disponible | Calcula distancia |
| 2 | ❌ No disponible | ✅ Disponible | null (sin GPS del fichaje) |
| 3 | ✅ Disponible | ❌ No disponible | null (sin GPS del domicilio) |
| 4 | ❌ No disponible | ❌ No disponible | null (sin GPS del fichaje, sin GPS del domicilio) |

**Mensajes de ubicación por tipo de evento:**

| Evento | Mensaje |
|--------|---------|
| `ubicacion_fuera_rango` | 📍 SUPUESTO 2 - UBICACIÓN FUERA DE RANGO: {nombre_trabajador} está a {distancia} del domicilio (umbral: 50m) |
| `salida_adelantada` | ⏰ SUPUESTO 5 - SALIDA ADELANTADA: {nombre_trabajador} salió {minutos} min antes (Ubicación: {descripcion}) |
| `salida_tarde` | ⏰ SUPUESTO 6 - SALIDA TARDE: {nombre_trabajador} salió {minutos} min después (Ubicación: {descripcion}) |
| `fichaje_adelantado` | ⏰ SUPUESTO 1 - FICHAJE ADELANTADO: {nombre_trabajador} fichó {minutos} min antes (Ubicación: {descripcion}) |
| `fichaje_manual_sin_gps_qr` | ⚠️ SUPUESTO 3 - FICHAJE MANUAL: Sin datos GPS ni código QR (Ubicación: No hay GPS disponible) |

---

### 4.3 Estructura del Payload

Todos los webhooks incluyen:

```json
{
  "timestamp": {
    "iso": "2026-02-14T10:30:00.123456",
    "legible": "Sábado, 14 de Febrero de 2026 a las 10:30",
    "fecha": "14/02/2026",
    "hora": "10:30",
    "dia_semana": "Sábado"
  },
  "tipo": "ausencia_detectada",
  "sistema": "GESAD-MCP",
  "datos": {
    "fichaje_id": "10687853",
    "tipo_fichaje": "NINGUNO",
    "trabajador": { ... },
    "usuario": { ... },
    "gps_fichaje": {
      "entrada": {
        "latitud": "41.67420211352",
        "longitud": "2.786167629444"
      },
      "salida": {
        "latitud": "41.68285026332",
        "longitud": "2.792237130645"
      }
    },
    "horarios": {
      "hora_prevista_entrada": "10:00",
      "hora_prevista_salida": "12:00",
      "hora_fichaje_entrada": "09:30",
      "hora_fichaje_salida": "No registrada"
    },
    "ubicacion": { ... },
    "mensaje": "🚨 AUSENCIA DETECTADA: {nombre_trabajador} no ha fichado entrada",
    "severidad": "alta",
    "accion_requerida": "Contactar al trabajador y/o usuario asignado"
  }
}
```

**Campos del payload:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `fichaje_id` | string | ID único del fichaje |
| `tipo_fichaje` | string | Método de fichaje: `QR`, `MANUAL`, `NINGUNO` |
| `trabajador` | object | Datos completos del trabajador |
| `usuario` | object | Datos completos del usuario |
| `gps_fichaje` | object | Coordenadas GPS del fichaje (entrada y salida) |
| `gps_fichaje.entrada.latitud` | string | Latitud donde el trabajador fichó entrada |
| `gps_fichaje.entrada.longitud` | string | Longitud donde el trabajador fichó entrada |
| `gps_fichaje.salida.latitud` | string | Latitud donde el trabajador fichó salida |
| `gps_fichaje.salida.longitud` | string | Longitud donde el trabajador fichó salida |
| `horarios` | object | Horas previstas y reales del servicio |
| `ubicacion` | object | Distancia calculada entre GPS del fichaje y domicilio |
| `ubicacion.distancia_metros` | number/null | Distancia en metros (null si no hay GPS) |
| `ubicacion.tiene_gps` | boolean | Indica si se pudo calcular la distancia |
| `mensaje` | string | Mensaje descriptivo del evento |
| `severidad` | string | Nivel de severidad: `alta`, `media`, `info` |
| `accion_requerida` | string/null | Acción recomendada para resolver el evento |

En el archivo `.env`:

```env
GESAD_WEBHOOK_ENABLED=true
GESAD_WEBHOOK_URL=https://n8n.multiplai.org/webhook/fichaje
GESAD_WEBHOOK_TIMEOUT=30
GESAD_WEBHOOK_EVENTS=ausencia,fichaje_manual,retraso_confirmado,salida_adelantada,salida_tarde,fichaje_adelantado,ubicacion_fuera_rango
```

### 4.4 Eventos Disponibles

- `ausencia` - Ausencia detectada
- `fichaje_manual` - Fichaje manual sin GPS/QR
- `retraso_confirmado` - Retraso confirmado (+20 min)
- `salida_adelantada` - Salida adelantada (-10 min)
- `salida_tarde` - Salida tarde (+10 min)
- `fichaje_adelantado` - Fichaje adelantado (-20 min)
- `ubicacion_fuera_rango` - Ubación GPS fuera del domicilio

### 4.4 Formato de Fechas

El sistema transforma las fechas ISO a formato legible español:

- **ISO**: `1982-07-30T00:00:00`
- **Legible**: `30 de Julio de 1982`
- **Hora**: `10:00`

Todos los campos de fecha incluyen tanto el valor original ISO como el formato legible en un campo `_legible`.

---

## 5. Integración con n8n

### 5.1 Instalar n8n

```bash
# Usar script de instalación
./scripts/install_n8n.sh
```

### 5.2 Crear Webhook en n8n

1. Abrir n8n en `http://localhost:5678`
2. Crear nuevo workflow
3. Añadir nodo "Webhook"
4. Configurar:
   - **Método**: POST
   - **Path**: `/webhook/fichaje`
   - **Authentication**: None (o configurar token)

### 5.3 Workflow de Ejemplo

```javascript
// Nodo Webhook → Switch (por tipo) → Notificaciones correspondientes

// 1. AUSENCIA DETECTADA
if (tipo === 'ausencia_detectada') {
  // Enviar mensaje a Slack/Teams
  // Llamar al trabajador
  // Notificar coordinador
}

// 2. FICHAJE MANUAL SIN GPS/QR
if (tipo === 'fichaje_manual_sin_gps_qr') {
  // Solicitar refichaje
  // Validar con coordinador
}

// 3. RETRASO CONFIRMADO
if (tipo === 'retraso_confirmado') {
  // Clasificar motivo del retraso
  // Documentar incidencia
}
```

### 5.4 Variables de Entorno para n8n

```env
N8N_HOST=127.0.0.1
N8N_PORT=5678
N8N_PATH=/n8n
```

---

## 6. Scripts de Utilidad

### 6.1 Verificar Configuración

```bash
python scripts/verificar_configuracion.py
```

Verifica que todas las variables de entorno estén configuradas correctamente.

### 6.2 Cargar Datos Maestros

```bash
python scripts/cargar_datos_master.py
```

Precarga usuarios y trabajadores en caché para mejorar rendimiento.

### 6.3 Verificar Fichajes

```bash
python scripts/verificar_fichajes.py
```

Verifica el estado de los fichajes y detecta anomalías.

### 6.4 Demo

```bash
python scripts/demo.py
```

Demostración del sistema con datos de ejemplo.

### 6.5 Investigar Fichaje

```bash
python scripts/investigar_fichaje.py <fichaje_id> [dias]
```

Investiga los campos GPS de un fichaje específico y calcula la distancia al domicilio.

**Parámetros:**
- `fichaje_id` - ID del fichaje a investigar (por defecto: 10679998)
- `dias` - Días hacia atrás a buscar (por defecto: 7)

### 6.6 Verificar Distancia GPS

```bash
python scripts/verificar_distancia_gps.py
```

Busca fichajes recientes con GPS y verifica el cálculo de distancia al domicilio.

### 6.7 Instalación

```bash
./scripts/install.sh
```

Instala todas las dependencias del sistema.

---

## 7. Variables de Entorno

### 7.1 Conexión API

```env
GESAD_CONEX_NAME=nombre_centro_trabajo
GESAD_AUTH_CODE=tu_auth_code_aqui
GESAD_BASIC_AUTH=your_basic_auth_here
GESAD_API_CODE=your_api_code
GESAD_SESSION_ID=R0_F5FB07C4-0E63-4A7A-BA8A-43108D19224B
GESAD_BASE_URL=https://data-bi.ayudadomiciliaria.com/api
```

### 7.2 Horario y Monitoreo

```env
GESAD_TIMEZONE=Europe/Madrid
GESAD_ACTIVE_START=6
GESAD_ACTIVE_END=24
GESAD_CHECK_INTERVAL=20
```

### 7.3 Webhooks

```env
GESAD_WEBHOOK_URL=https://n8n.multiplai.org/webhook/fichaje
GESAD_WEBHOOK_ENABLED=true
GESAD_WEBHOOK_TIMEOUT=30
GESAD_WEBHOOK_EVENTS=ausencia,fichaje_manual,retraso_confirmado,salida_adelantada,salida_tarde,fichaje_adelantado,ubicacion_fuera_rango
```

### 7.4 Umbrales de Alertas

```env
GESAD_UMBRAL_LLEGADA_ADELANTADA=20
GESAD_UMBRAL_RETRASO_AUSENCIA=20
GESAD_UMBRAL_SALIDA_ADELANTADA=10
GESAD_UMBRAL_SALIDA_TARDE=10
GESAD_UMBRAL_DISTANCIA_UBICACION=50
```

---

## 8. Mensajes Configurados

| # | Tipo de Notificación | Mensaje | Severidad | Acción Requerida |
|---|----------------------|---------|-----------|-------------------|
| 1 | **ausencia_detectada** | 🚨 AUSENCIA DETECTADA: {nombre_trabajador} no ha fichado entrada | alta | Contactar al trabajador y/o usuario asignado |
| 2 | **fichaje_adelantado** | ⏰ SUPUESTO 1 - FICHAJE ADELANTADO: {trabajador_nombre} fichó {minutos} min antes | media/alta* | Validar fichaje con coordinación* |
| 3 | **ubicacion_fuera_rango** | 📍 SUPUESTO 2 - UBICACIÓN FUERA DE RANGO: {trabajador_nombre} está a {distancia} del domicilio (umbral: 50m) | media | Contactar al trabajador para verificar su ubicación |
| 4 | **fichaje_manual_sin_gps_qr** | ⚠️ SUPUESTO 3 - FICHAJE MANUAL: Sin datos GPS ni código QR | alta | Solicitar refichaje o validar con coordinador |
| 5 | **retraso_confirmado** | ❌ SUPUESTO 4 - RETRASO CONFIRMADO: {trabajador_nombre} con {minutos} min de retraso | alta | Contactar al trabajador para clasificar motivo |
| 6 | **salida_adelantada** | ⏰ SUPUESTO 5 - SALIDA ADELANTADA: {nombre_trabajador} salió {minutos} min antes | media | Verificar finalización del servicio |
| 7 | **salida_tarde** | ⏰ SUPUESTO 6 - SALIDA TARDE: {nombre_trabajador} salió {minutos} min después | alta | Llamada urgente a coordinación |

\* Para `fichaje_adelantado`:
- **Severidad media**: Si tiene GPS y/o QR válido
- **Severidad alta**: Si NO tiene GPS ni QR
- **Acción requerida**: Solo si NO tiene GPS ni QR

---

## 9. Sistema de Caché y Carga de Datos

### 9.1 Datos Maestros

El sistema utiliza un sistema de caché multinivel para optimizar las llamadas a la API de GESAD:

| Tipo de dato | TTL (Tiempo de vida) | Descripción |
|--------------|---------------------|-------------|
| **Usuarios** | 24 horas | Lista completa de usuarios (2198+) |
| **Trabajadores** | 24 horas | Lista completa de trabajadores (735+) |
| **Fichajes del día** | 5 minutos | Fichajes del día actual |
| **Resultado monitoreo** | 20 minutos | Último resultado de verificación |

### 9.2 Momentos de Carga de Datos

Los datos de usuarios y trabajadores se cargan automáticamente en estos momentos:

```
┌─────────────────────────────────────────────────────────────────┐
│                    MOMENTOS DE CARGA DE DATOS                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Al iniciar el servidor                                     │
│     python start_monitoring.py --standalone                     │
│     → Precarga: 2198 usuarios + 735 trabajadores               │
│                                                                  │
│  2. Al inicio del ciclo diario (6:00 AM)                       │
│     → Verifica y recarga si es necesario                       │
│                                                                  │
│  3. Antes de cada verificación                                  │
│     → Método _asegurar_datos_precargados()                     │
│     → Recarga automáticamente si faltan datos                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 9.3 Carga Manual de Datos

Si necesitas forzar la carga de datos manualmente:

```bash
# Ejecutar script de carga
python scripts/cargar_datos_master.py

# Salida esperada:
# ✅ 2198 usuarios cacheados por 24 horas
# ✅ 735 trabajadores cacheados por 24 horas
```

### 9.4 Verificar Datos en Caché

```bash
# Ver contenido del caché
ls -la cache/

# Limpiar caché (si hay problemas)
rm -rf cache/*
python scripts/cargar_datos_master.py
```

---

## 10. Soporte

Para más información o problemas, visite:
- **Repositorio**: https://github.com/jariass2/MCP_Artris
- **Issues**: https://github.com/jariass2/MCP_Artris/issues

---

## 10. Requisitos de Despliegue

### 10.1 Infraestructura Necesaria

| Componente | Tecnología | Descripción |
|------------|------------|-------------|
| **Servidor** | VPS | Ubuntu 22.04 LTS (mínimo 2CPU, 4GB RAM) |
| **Panel** | EasyPanel | Gestión de contenedores y aplicaciones |
| **n8n** | Docker/Contenedor | Orquestación de webhooks |
| **Base de datos** | PostgreSQL | Almacenamiento de datos |
| **MCP GESAD** | Docker/Contenedor | Aplicación principal |

### 10.2 Diagrama de Arquitectura

```
┌─────────────────────────────────────────┐
│              VPS (Ubuntu)                │
│  ┌───────────────────────────────────┐  │
│  │          EasyPanel                 │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────┐ │  │
│  │  │  n8n    │ │ PostgreSQL│ │MCP  │ │  │
│  │  │Container│ │ Container│ │Gesad│ │  │
│  │  └─────────┘ └─────────┘ └─────┘ │  │
│  │           │        │        │      │  │
│  │           └────────┴────────┘      │  │
│  │         Docker Compose              │  │
│  └───────────────────────────────────┘  │
│              │        │                  │
│              ▼        ▼                  │
│         ┌────────┐ ┌────────┐           │
│         │  SSL   │ │ Backup │           │
│         │(Let's  │ │ Daily  │           │
│         │Encrypt)│ │ Dump   │           │
│         └────────┘ └────────┘           │
└─────────────────────────────────────────┘
```

### 10.3 Puertos Necesarios

| Puerto | Servicio | Notas |
|--------|----------|-------|
| 80/443 | EasyPanel + n8n | HTTP/HTTPS |
| 5678 | n8n | Opcional (si no usa proxy) |
| 5432 | PostgreSQL | Solo localhost |
| 9999 | MCP GESAD | Aplicación principal |

### 10.4 Componentes Adicionales Recomendados

- **Docker Compose**: Orquestación de contenedores
- **Proxy inverso**: Caddy o Traefik (si se expone a internet)
- **SSL/HTTPS**: Let's Encrypt (vía EasyPanel)
- **Backup PostgreSQL**: Daily dumps automáticos
- **Dominio/DNS**: Para acceso externo

### 10.5 Instalación Recomendada

```bash
# 1. VPS con Ubuntu 22.04
# 2. Instalar EasyPanel
# 3. Crear contenedores desde EasyPanel:
#    - PostgreSQL (持久化卷)
#    - n8n
#    - MCP GESAD (puerto 9999)
# 4. Configurar SSL automático
# 5. Configurar backup PostgreSQL
```
