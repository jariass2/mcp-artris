# Plan de Implementación: Reporting Automatizado con PostgreSQL

**Fecha de creación:** 14/02/2026  
**Estado:** Pendiente de implementación

---

## Objetivo

Integrar el sistema MCP GESAD con una base de datos PostgreSQL para:
1. Almacenar todos los fichajes (con y sin incidencia)
2. Generar reportes automáticos semanales en PDF
3. Permitir análisis con lenguaje natural de datos históricos

---

## 1. Estructura de Base de Datos (Schema SQL)

### 1.1 Tablas Principales

```sql
-- Tabla principal de fichajes
CREATE TABLE fichajes (
    id SERIAL PRIMARY KEY,
    ficha_id VARCHAR(50) UNIQUE NOT NULL,
    fecha DATE NOT NULL,
    usuario_id VARCHAR(20) NOT NULL,
    trabajador_id VARCHAR(20) NOT NULL,
    servicio_origen VARCHAR(100),
    
    -- Horarios
    hora_entrada_prevista TIME,
    hora_salida_prevista TIME,
    hora_entrada_fichaje TIME,
    hora_salida_fichaje TIME,
    
    -- GPS
    gps_entrada_lat DECIMAL(10, 8),
    gps_entrada_lon DECIMAL(11, 8),
    gps_salida_lat DECIMAL(10, 8),
    gps_salida_lon DECIMAL(11, 8),
    gps_domicilio_lat DECIMAL(10, 8),
    gps_domicilio_lon DECIMAL(11, 8),
    
    -- Distancias
    distancia_entrada_metros DECIMAL(10, 2),
    distancia_salida_metros DECIMAL(10, 2),
    
    -- Método
    metodo_entrada VARCHAR(20),
    metodo_salida VARCHAR(20),
    
    -- Incidencia
    tipo_incidencia VARCHAR(50),
    minutos_diferencia INTEGER,
    descripcion_incidencia TEXT,
    
    -- Metadata
    procesado_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_fecha (fecha),
    INDEX idx_trabajador (trabajador_id),
    INDEX idx_usuario (usuario_id),
    INDEX idx_incidencia (tipo_incidencia)
);

-- Tabla de trabajadores (cache)
CREATE TABLE trabajadores (
    id VARCHAR(20) PRIMARY KEY,
    nombre VARCHAR(200),
    centro_trabajo VARCHAR(200),
    categoria VARCHAR(10),  -- A, B, C
    fecha_alta DATE,
    INDEX idx_categoria (categoria)
);

-- Tabla de usuarios (cache)
CREATE TABLE usuarios (
    id VARCHAR(20) PRIMARY KEY,
    nombre VARCHAR(200),
    direccion VARCHAR(500),
    zona VARCHAR(100),
    tipo_servicio VARCHAR(100),
    INDEX idx_zona (zona)
);

-- Tabla de niveles de servicio por usuario
CREATE TABLE niveles_servicio (
    id SERIAL PRIMARY KEY,
    usuario_id VARCHAR(20) REFERENCES usuarios(id),
    fecha DATE NOT NULL,
    horas_contratadas DECIMAL(5, 2),
    horas_realizadas DECIMAL(5, 2),
    cumplimiento_porcentaje DECIMAL(5, 2),
    incidencias_count INTEGER DEFAULT 0,
    INDEX idx_usuario_fecha (usuario_id, fecha)
);

-- Tabla de reportes generados
CREATE TABLE reportes (
    id SERIAL PRIMARY KEY,
    tipo_reporte VARCHAR(20) NOT NULL,  -- coordinadores, gerencia
    periodo_semana DATE NOT NULL,
    generado_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ruta_fichero VARCHAR(500),
    INDEX idx_tipo_periodo (tipo_reporte, periodo_semana)
);

-- Tabla de tipos de incidencia
CREATE TABLE tipos_incidencia (
    codigo VARCHAR(50) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    severidad VARCHAR(20),  -- alta, media, baja
    requiere_accion BOOLEAN DEFAULT FALSE
);
```

### 1.2 Datos Iniciales

```sql
-- Insertar tipos de incidencia
INSERT INTO tipos_incidencia (codigo, nombre, descripcion, severidad, requiere_accion) VALUES
('sin_incidencia', 'Sin Incidencia', 'Fichaje dentro de parámetros normales', 'baja', false),
('ausencia', 'Ausencia', 'No se ha producido fichaje', 'alta', true),
('fichaje_adelantado', 'Fichaje Adelantado', 'Llegada 20+ min antes', 'media', false),
('retraso_confirmado', 'Retraso Confirmado', 'Llegada 20+ min después', 'alta', true),
('salida_adelantada', 'Salida Adelantada', 'Salida 10+ min antes', 'media', true),
('salida_tarde', 'Salida Tarde', 'Salida 10+ min después', 'alta', true),
('ubicacion_fuera_rango', 'Ubicación Fuera de Rango', 'GPS a 50m+ del domicilio', 'media', true),
('fichaje_manual_sin_gps', 'Fichaje Manual sin GPS', 'Fichaje manual sin coordenadas', 'alta', true);
```

---

## 2. Configuración (.env)

```env
# === POSTGRESQL ===
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=gesad_reporting
POSTGRES_USER=gesad_user
POSTGRES_PASSWORD=tu_password

# === REPORTING AUTOMÁTICO ===
REPORTING_ENABLED=true
REPORTING_DAY_OF_WEEK=5  # Viernes = 5
REPORTING_HOUR=8  # 8:00 AM
REPORTING_FORMAT=pdf

# Coordinadores
REPORT_COORDINADORES_ENABLED=true
REPORT_COORDINADORES_EMAIL=coordinadores@empresa.com

# Gerencia
REPORT_GERENCIA_ENABLED=true
REPORT_GERENCIA_EMAIL=gerencia@empresa.com

# PDF
PDF_PAGE_SIZE=A4
PDF_FONT=Helvetica
```

---

## 3. Indicadores por Tipo de Reporte

### 3.1 REPORTE COORDINADORES (Operativo)

| # | Indicador | Descripción |
|---|-----------|-------------|
| 1 | Total servicios día | Fichajes procesados |
| 2 | Incidencias totales | Conteo por tipo |
| 3 | Ausencias detectadas | Sin entrada |
| 4 | Retrasos confirmados | >20 min tarde |
| 5 | Fichajes manuales sin GPS | Requiere refichaje |
| 6 | GPS fuera de rango | Distancia >50m |
| 7 | Incidencias por trabajador | Detalle individual |
| 8 | Incidencias por zona | Distribución geográfica |
| 9 | Servicios sin cerrar | Sin salida registrada |
| 10 | TOP 5 trabajadores con más incidencias | Ranking semanal |
| 11 | Servicios completados a tiempo | % con entrada y salida en rango |
| 12 | Distancia media GPS | Media de distancia al domicilio |

### 3.2 REPORTE GERENCIA (Estratégico)

| # | Indicador | Descripción |
|---|-----------|-------------|
| 1 | % Cumplimiento global | Fichajes a tiempo vs total |
| 2 | Índice de absentismo | Ausencias / total servicios |
| 3 | Trabajadores por categoría | Distribución A/B/C |
| 4 | Evolución semanal | Comparativa vs semana anterior |
| 5 | Tendencia de incidencias | Gráfico histórico 4 semanas |
| 6 | Nivel de servicio por usuario | % horas contratadas |
| 7 | Productividad por zona | Servicios/hora-trabajador |
| 8 | Coste estimado incidencias | (horas extra, reemplazos) |
| 9 | Ratio GPS válidos | % con coordenadas |
| 10 | Satisfacción estimada | Basado en incidencias |
| 11 | Distribución por tipo de servicio | SAD vs Acompañamiento |
| 12 | Tendencia 12 meses | Evolución anual |

---

## 4. Módulos a Implementar

```
mcp-gesad/
├── db_manager.py              # Conexión PostgreSQL + CRUD
├── report_queries.py          # Consultas SQL para indicadores
├── report_builder.py          # Generación PDF con indicadores
├── report_scheduler.py        # Programación semanal
├── email_sender.py           # Envío por email
├── nlp_queries.py             # Consultas en lenguaje natural (opcional)
└── config.py                  # Actualizar con nuevos parámetros
```

---

## 5. Flujo de Funcionamiento

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUJO DE REPORTING                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ Scheduler   │───▶│ Report Builder   │───▶│ PDF Generator │  │
│  │ (Friday 8am)│    │ (SQL Queries)    │    │ (ReportLab)   │  │
│  └─────────────┘    └──────────────────┘    └───────┬───────┘  │
│                                                      │          │
│                                                      ▼          │
│                                            ┌───────────────┐   │
│                                            │ Email Sender  │   │
│                                            │ (SMTP)        │   │
│                                            └───────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Dependencias a Instalar

```txt
# requirements.txt - añadir:
asyncpg>=0.29.0          # PostgreSQL async
reportlab>=4.0.0         # Generación PDF
aiofiles>=23.0.0         # Escritura async
jinja2>=3.1.0            # Plantillas HTML
langchain>=0.1.0         # NLP (opcional)
langchain-openai>=0.0.1 # OpenAI para NLP
```

---

## 7. Orden de Implementación

### Fase 1: Base de Datos
1. [ ] Crear base de datos PostgreSQL
2. [ ] Ejecutar schema SQL (sección 1.1)
3. [ ] Insertar datos iniciales (sección 1.2)

### Fase 2: Integración Core
4. [ ] Añadir variables .env
5. [ ] Implementar `db_manager.py`
6. [ ] Integrar guardado de fichajes en processor existente

### Fase 3: Reporting
7. [ ] Implementar `report_queries.py`
8. [ ] Implementar `report_builder.py`
9. [ ] Implementar `report_scheduler.py`
10. [ ] Implementar `email_sender.py`

### Fase 4: NLP (Opcional)
11. [ ] Implementar `nlp_queries.py` para consultas en lenguaje natural

---

## 8. Categorización de Trabajadores

### Criterios de Clasificación

| Categoría | Criterios |
|-----------|-----------|
| **A (Excelente)** | ≥95% cumplimiento, ≤1 incidencia/mes |
| **B (Bueno)** | 80-94% cumplimiento, ≤3 incidencias/mes |
| **C (Necesita mejora)** | <80% cumplimiento o >3 incidencias/mes |

### Actualización
- Se recalcula semanalmente tras generar reportes
- Se guarda en tabla `trabajadores.categoria`

---

## 9. Nivel de Servicio por Usuario

### Métricas

```
Nivel de Servicio = (Horas Realizadas / Horas Contratadas) × 100
```

| Nivel | Rango |
|-------|-------|
| Óptimo | ≥95% |
| Adecuado | 80-94% |
| Deficiente | <80% |

### Guardado
- Se calcula diariamente en `niveles_servicio`
- Promedio semanal en reportes

---

## 10. Notas

- El usuario creará la base de datos PostgreSQL manualmente
- Los reportes se generan cada viernes a las 8:00 AM
- Dos tipos de reporte: coordinadores (operativo) y gerencia (estratégico)
- Formato PDF con tabla de indicadores

---

## 11. Chat NLP con OpenWebUI + OpenRouter

### 11.1 Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                    STACK COMPLETO NLP                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────────┐                                         │
│   │   OpenWebUI      │ ◀── Interfaz de chat (Docker)          │
│   │   (Docker)       │                                          │
│   └────────┬─────────┘                                         │
│            │                                                   │
│            │ OpenAI-compatible API                             │
│            ▼                                                   │
│   ┌──────────────────┐                                         │
│   │   OpenRouter     │ ◀── Gateway (1 key = 300+ modelos)      │
│   │   (API Key)     │     GLM-4.7 / Kimi K2 / MiniMax         │
│   └────────┬─────────┘                                         │
│            │                                                   │
│     ┌─────┴─────┬──────────────┐                              │
│     ▼           ▼              ▼                               │
│  GLM-4.7    Kimi K2      MiniMax M2                          │
│  $0.60/M    $0.60/M      $0.30/M                            │
│                                                                  │
│   ┌──────────────────┐                                         │
│   │   MCPO Proxy     │ ◀── Convierte MCP a OpenAPI            │
│   │   (Docker)       │                                          │
│   └────────┬─────────┘                                         │
│            │                                                   │
│            ▼                                                   │
│   ┌──────────────────┐                                         │
│   │   MCP GESAD      │ ◀── Herramientas para PostgreSQL       │
│   │   (Puerto 9999) │                                          │
│   └────────┬─────────┘                                         │
│            │                                                   │
│            ▼                                                   │
│   ┌──────────────────┐                                         │
│   │   PostgreSQL     │ ◀── Datos históricos                   │
│   └──────────────────┘                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 11.2 Componentes

| Componente | Tecnología | Función |
|------------|------------|---------|
| **Interfaz** | OpenWebUI | Chat web, historial, documentos |
| **Gateway LLM** | OpenRouter | Acceso a 300+ modelos |
| **Modelos** | GLM-4.7 / Kimi K2 | LLM para consultas SQL + NLP |
| **Proxy MCP** | MCPO | Traduce MCP a OpenAPI |
| **Datos** | PostgreSQL | Almacenamiento |

### 11.3 Modelos Recomendados (via OpenRouter)

| Modelo | Input/1M | Output/1M | Mejor para |
|--------|----------|-----------|------------|
| **GLM-4.7** | $0.60 | $2.20 | Código, SQL |
| **Kimi K2** | $0.60 | $2.50 | Español, reasoning |
| **MiniMax M2** | $0.35 | $1.40 | Económico |
| **Claude 3.5 Haiku** | $1.00 | $5.00 | Mejor calidad |

### 11.4 Coste Estimado

| Uso | Consultas/mes | Coste estimado |
|-----|---------------|----------------|
| Bajo | 500 | **3-5 €/mes** |
| Medio | 1,000 | **5-10 €/mes** |
| Alto | 2,000 | **10-15 €/mes** |

### 11.5 Configuración

```yaml
# docker-compose.yml
version: '3.8'

services:
  openwebui:
    image: openwebui/open-webui:main
    ports:
      - "8080:8080"
    environment:
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
      - OPENAI_API_KEY=${OPENROUTER_API_KEY}
      - OPENAI_API_BASE_URL=https://openrouter.ai/v1

  mcpo:
    image: openwebui/mcpo:latest
    ports:
      - "8000:8000"
    command: --port 8000 mcp-gesad:9999

  mcp-gesad:
    build: .
    ports:
      - "9999:9999"
    environment:
      - POSTGRES_HOST=postgres
```

### 11.6 Ejemplos de Preguntas

Una vez configurado, puedes preguntar a OpenWebUI:

- "¿Cuántas ausencias tuvimos esta semana?"
- "¿Qué trabajador tiene más retrasos en enero?"
- "¿Cuál es el porcentaje de cumplimiento por zona?"
- "¿Cuántas horas de servicio se realizaron?"
- "¿Dame un resumen de incidencias por categoría A?"

### 11.7 Alternativa: Claude Desktop

Si prefieres usar Claude Desktop directamente:

1. MCP GESAD ya está configurado para conectar con PostgreSQL
2. Las preguntas se hacen directamente en Claude Desktop
3. No necesitas OpenWebUI
4. Coste: Incluido en suscripción de Claude

```bash
# Configurar MCP en Claude Desktop
# File > Settings > MCP > Add new server
# Server: mcp-gesad (puerto 9999)
```

---

### 11.8 Configuración de MCP GESAD en OpenWebUI

Hay dos formas de conectar MCP GESAD con OpenWebUI:

#### Opción A: MCPO (Recomendada)

MCPO es un proxy que convierte cualquier servidor MCP en una API compatible con OpenAI.

```bash
# 1. Obtener API Key de OpenRouter: https://openrouter.ai
# 2. Crear docker-compose.yml:

version: '3.8'

services:
  openwebui:
    image: openwebui/open-webui:main
    container_name: openwebui
    ports:
      - "3000:8080"
    environment:
      - OPENAI_API_KEY=${OPENROUTER_API_KEY}
      - OPENAI_API_BASE_URL=https://openrouter.ai/v1
    volumes:
      - openwebui_data:/app/backend/data

  mcpo:
    image: openwebui/mcpo:latest
    container_name: mcpo
    ports:
      - "8000:8000"
    command: --port 8000 --host 0.0.0.0 python /path/to/server.py
    environment:
      - GESAD_CONEX_NAME=${GESAD_CONEX_NAME}
      - GESAD_AUTH_CODE=${GESAD_AUTH_CODE}
      - GESAD_SESSION_ID=${GESAD_SESSION_ID}

volumes:
  openwebui_data:
```

```bash
# 3. Crear archivo .env:
OPENROUTER_API_KEY=sk-or-v1-xxxxx
GESAD_CONEX_NAME=tu_centro
GESAD_AUTH_CODE=tu_auth_code
GESAD_SESSION_ID=tu_session_id

# 4. Ejecutar:
docker-compose up -d

# 5. Acceder a http://tu-servidor:3000
```

#### Opción B: Conexión Directa (HTTP Streaming)

A partir de OpenWebUI v0.6.31, puedes conectar directamente a un servidor MCP que exponga HTTP streaming.

```bash
# 1. Asegúrate de que MCP GESAD esté ejecutándose:
python server.py
# Servidor disponible en http://localhost:9999

# 2. En OpenWebUI:
#    Admin Panel > Settings > Tools > External Tools

# 3. Añadir nuevo tool server:
#    URL: http://tu-servidor:9999/mcp (si soporta streamable HTTP)
#    O usar MCPO como proxy
```

#### Configuración de Herramientas en OpenWebUI

Una vez conectado, las herramientas de MCP GESAD aparecerán automáticamente:

```
Tools disponibles:
- get_estado_asistencia_actual() - Estado actual del monitoreo
- get_alertas_activas() - Alertas activas del sistema
- get_system_status() - Estado completo del sistema
- force_verification() - Forzar verificación manual
```

#### Uso en Chat

```
1. Iniciar sesión en OpenWebUI
2. Seleccionar modelo (GLM-4.7, Kimi, etc.)
3. Habilitar herramientas en la conversación
4. Preguntar: "¿Cuáles son las alertas activas hoy?"
```

#### Solución de Problemas

| Problema | Solución |
|----------|----------|
| No aparecen herramientas | Verificar que MCPO está funcionando |
| Error de conexión | Comprobar puertos y firewall |
| Error de autenticación | Verificar credenciales GESAD en .env |
| Timeout | Aumentar timeout en configuración |
