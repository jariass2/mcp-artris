# GESAD MCP - Solución Integral de Gestión de Asistencias Domiciliarias

---

## 🚀 Transformación Digital de tu Servicio de Atención Domiciliaria

**GESAD MCP** es la plataforma definitiva para digitalizar y automatizar el control de asistencia de tus profesionales en servicios domiciliarios. Con tecnología de inteligencia artificial integrada, reduce costes, mejora la eficiencia y garantiza el cumplimiento normativo.

---

## Problema

Los servicios de atención domiciliaria (SAD) enfrentan desafíos críticos:

| Desafío | Impacto |
|---------|---------|
| **Control manual de asistencia** | Errores humanos, pérdida de tiempo |
| **Ausencias no detectadas** | Interrupción del servicio a personas vulnerables |
| **Fichajes fuera del domicilio** | Riesgo de fraude laboral |
| **Falta de reporting** | Decisiones basadas en datos incompletos |
| **Tardanzas no documentadas** | Incumplimiento de horas contratadas |

---

## Solución: GESAD MCP

Una plataforma integral que combina:

- 🤖 **Inteligencia Artificial** (Model Context Protocol)
- 📡 **Integración nativa** con API GESAD
- 📊 **Reporting automático** en PDF
- 🔔 **Alertas en tiempo real** vía webhooks
- 🗄️ **Base de datos histórica** PostgreSQL
- 💬 **Chat NLP** para consultas en lenguaje natural

---

## Funcionalidades

### ✅ Funcionalidades Incluidas

| Módulo | Descripción |
|--------|-------------|
| **Fase 0: Análisis** | Estudio de API, requisitos, propuesta técnica |
| **Monitoreo Automático** | Verificación cada 20 minutos (6:00-12:00) |
| **Detección de Ausencias** | Alerta 20 min después de hora prevista |
| **Control GPS** | Verifica que el trabajador fiche en el domicilio |
| **Fichaje Manual** | Detecta ficajes sin GPS/QR válido |
| **Alertas por Email** | Notificaciones en tiempo real por correo |
| **Cache Inteligente** | Optimización de llamadas API (3.6% del límite) |

### 🚧 Funcionalidades Futuras (Fase 2-4)

| Módulo | Descripción |
|--------|-------------|
| **WhatsApp Business** | Alertas por WhatsApp (futuro) |
| **Histórico PostgreSQL** | Almacenamiento de todos los fichajes |
|--------|-------------|
| **Histórico PostgreSQL** | Almacenamiento de todos los fichajes |
| **Reporting Automático** | PDF semanal para coordinadores y gerencia |
| **Categorización IA** | Clasificación automática de trabajadores (A/B/C) |
| **Nivel de Servicio** | % cumplimiento por usuario |
| **Chat NLP** | Consultas en lenguaje natural (OpenWebUI + OpenRouter) |

---

## Planificación Progresiva de Despliegue

### Fase 0: Análisis y Prueba (Semanas 1-2)
**Objetivo:** Validar viabilidad técnica y definir requisitos exactos

```
┌─────────────────────────────────────────────┐
│  FASE 0: ANÁLISIS Y PRUEBA                 │
├─────────────────────────────────────────────┤
│  ✓ Análisis detallado de API GESAD          │
│  ✓ Mapeo de campos y estructura de datos   │
│  ✓ Prueba de conexión y autenticación      │
│  ✓ Identificación de casos edge            │
│  ✓ Documentación de endpoints útiles       │
│  ✓ Entrevista con coordinadores            │
│  ✓ Definición de requisitos exactos        │
│  ✓ Propuesta técnica personalizada         │
│                                              │
│  Complejidad: BAJA                          │
│  Inversión: MEDIA                           │
│  Impacto: CRÍTICO (valida todo el proyecto)│
└─────────────────────────────────────────────┘
```

**Entregables:**
- Informe técnico de la API
- Documentación de campos disponibles
- Lista de requisitos funcionales
- Propuesta técnica ajustada
- Presupuesto detallado

**Coste estimado:** 500-1.000 €

**Infraestructura requerida (preparación):**
```bash
# Acceso a credenciales API GESAD
# Acceso a documentación/endpoints de la API
# Reunión con coordinadores para requisitos
```

**Nota:** Esta fase es fundamental para evitar surpresas en fases posteriores. Permite validar que la API proporciona los datos necesarios y ajustar el alcance del proyecto.

---

### Fase 1: Fundamentos (Semanas 3-4)
**Objetivo:** Implementación básica funcional

```
┌─────────────────────────────────────────────┐
│  FASE 1: FUNDAMENTOS                        │
├─────────────────────────────────────────────┤
│  ✓ Conexión API GESAD                       │
│  ✓ Monitorización automática                │
│  ✓ Detección de ausencias                 │
│  ✓ Alertas por email                       │
│                                              │
│  Complejidad: BAJA                          │
│  Inversión: MEDIA                           │
│  Impacto: INMEDIATO                        │
└─────────────────────────────────────────────┘
```

**Entregables:**
- Sistema funcionando 24/7
- Notificaciones de ausencias por email

**Coste estimado:** 1.500-2.500 € (tras Fase 0)

**Infraestructura requerida:**
```bash
# VPS con Ubuntu 22.04 (mínimo 2CPU, 4GB RAM)
# Instalar Python 3.12+
# Instalar dependencias: pip install -r requirements.txt
# Configurar email en .env:
#   SMTP_HOST=smtp.gmail.com
#   SMTP_PORT=587
#   SMTP_USER=tu_email@empresa.com
#   SMTP_PASSWORD=tu_password
#   ALERT_EMAIL=coordinador@empresa.com
# Ejecutar: python server.py
```

---

### Fase 2: Control y Seguridad (Semanas 5-6)
**Objetivo:** Validación de ubicación y calidad de ficajes

```
┌─────────────────────────────────────────────┐
│  FASE 2: CONTROL Y SEGURIDAD                │
├─────────────────────────────────────────────┤
│  ✓ Verificación GPS por domicilio           │
│  ✓ Detección de ficajes manuales           │
│  ✓ Control de retardos (+20 min)           │
│  ✓ Control de salidas tempranas            │
│  ✓ Alertas por email                      │
│  ✓ [FUTURO: WhatsApp Business API]        │
│                                              │
│  Complejidad: MEDIA                         │
│  Inversión: MEDIA                           │
│  Impacto: ALTO                              │
└─────────────────────────────────────────────┘
```

**Entregables:**
- Registro de incidencias
- Notificaciones por email

**Coste estimado:** 2.500-4.000 € (acumulado)

**Infraestructura requerida:**
```bash
# Continúa con la infraestructura de Fase 1
# Las alertas ya están configuradas por email
# [FUTURO]: Integración con WhatsApp Business API
```

**Entregables:**
- Mapa de ubicaciones
- Registro de incidents
- Notificaciones multi-canal

**Coste estimado:** 2.500-4.000 € (acumulado)

**Infraestructura requerida:**
```bash
# Continúa con la infraestructura de Fase 1
# Añadir: npm install -g n8n (o Docker)
# Configurar webhook en n8n para alertas
```

---

### Fase 3: Datos y Reporting (Semanas 7-10)
**Objetivo:** Almacenamiento histórico y análisis

```
┌─────────────────────────────────────────────┐
│  FASE 3: DATOS Y REPORTING                 │
├─────────────────────────────────────────────┤
│  ✓ Base de datos PostgreSQL                │
│  ✓ Histórico de ficajes                    │
│  ✓ Reporte semanal PDF (Coordinadores)     │
│  ✓ Reporte semanal PDF (Gerencia)          │
│  ✓ Categorización automática (A/B/C)       │
│  ✓ Nivel de servicio por usuario           │
│                                              │
│  Complejidad: ALTA                          │
│  Inversión: ALTA                            │
│  Impacto: ESTRATÉGICO                      │
└─────────────────────────────────────────────┘
```

**Entregables:**
- Base de datos operativa
- 2 tipos de reportes semanales
- Dashboard histórico

**Coste estimado:** 5.000-8.000 € (acumulado)

**Infraestructura requerida:**
```bash
# Añadir PostgreSQL (Docker):
docker run -d --name gesad-postgres \
  -e POSTGRES_DB=gesad \
  -e POSTGRES_USER=gesad \
  -e POSTGRES_PASSWORD=tu_password \
  -v postgres_data:/var/lib/postgresql/data \
  -p 5432:5432 postgres:15

# Configurar variables en .env:
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# POSTGRES_DB=gesad
# POSTGRES_USER=gesad
# POSTGRES_PASSWORD=tu_password
```

---

### Fase 4: Inteligencia Artificial (Semanas 11-14)
**Objetivo:** Consultas en lenguaje natural

```
┌─────────────────────────────────────────────┐
│  FASE 4: INTELIGENCIA ARTIFICIAL           │
├─────────────────────────────────────────────┤
│  ✓ Integración OpenWebUI                   │
│  ✓ Conexión OpenRouter (GLM-4.7/Kimi)      │
│  ✓ Chat NLP para consultas                 │
│  ✓ Análisis predictivo                     │
│  ✓ Alertas predictivas                     │
│                                              │
│  Complejidad: MUY ALTA                     │
│  Inversión: MEDIA (opex)                    │
│  Impacto: TRANSFORMADOR                    │
└─────────────────────────────────────────────┘
```

**Entregables:**
- Chat conversacional
- Consultas en español
- Informes automatizados

**Coste estimado:** 8.000-12.000 € (acumulado)
**Coste mensual IA:** 5-15 €/mes (OpenRouter)

**Infraestructura requerida:**
```bash
# Docker Compose para OpenWebUI + MCPO:

# 1. Obtener API Key de OpenRouter: https://openrouter.ai
# 2. Crear docker-compose.yml:

version: '3.8'
services:
  openwebui:
    image: openwebui/open-webui:main
    ports:
      - "8080:8080"
    environment:
      - OPENAI_API_KEY=${OPENROUTER_API_KEY}
      - OPENAI_API_BASE_URL=https://openrouter.ai/v1

  mcpo:
    image: openwebui/mcpo:latest
    ports:
      - "8000:8000"
    command: --port 8000 mcp-gesad:9999
    depends_on:
      - mcp-gesad

  mcp-gesad:
    build: .
    ports:
      - "9999:9999"

# 3. Ejecutar: docker-compose up -d
# 4. Acceder a http://tu-servidor:8080
```

---

## Comparativa: Antes vs Después

| Aspecto | Antes | Después |
|---------|-------|---------|
| **Detección de ausencias** | Manual (horas) | Automático (20 min) |
| **Verificación GPS** | No disponible | Automático |
| **Reporting** | Hojas de cálculo | PDF automático |
| **Consultas de datos** | Tedioso | Chat NLP |
| **Horas de gestión/semana** | 15-20h | 2-3h |
| **Tasa de error** | 5-10% | <1% |

---

## ROI Esperado

### Ahorro Directo
| Concepto | Estimación |
|----------|------------|
| Reducción absentismo | 15-25% |
| Eliminación fraude GPS | 100% |
| Tiempo de gestión | -80% |
| Llamadas de verificación | -70% |

### Beneficios Intangibles
- Mayor calidad de servicio al usuario
- Cumplimiento normativo garantizado
- Decisiones basadas en datos
- Satisfacción del trabajador
- Imagen profesional

---

## Tech Stack Recomendado

```
┌─────────────────────────────────────────────┐
│               ARQUITECTURA                   │
├─────────────────────────────────────────────┤
│                                             │
│   ┌─────────┐    ┌─────────┐    ┌────────┐ │
│   │ Claude  │    │  n8n    │    │  VPS   │ │
│   │ Desktop │    │(Webhook)│    │ Easy   │ │
│   └────┬────┘    └────┬────┘    │ Panel  │ │
│        │               │         └───┬────┘ │
│        │               │             │       │
│   ┌────┴───────────────┴─────────────┴─┐   │
│   │         MCP GESAD Server            │   │
│   │            (Puerto 9999)            │   │
│   └────────────────┬───────────────────┘   │
│                    │                         │
│   ┌────────────────┴───────────────────┐   │
│   │         PostgreSQL                  │   │
│   │    (Histórico + Reporting)          │   │
│   └────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

### Infraestructura
| Fase | Componente | Especificación |
|------|------------|----------------|
| 0-1 | VPS | Ubuntu 22.04, 2CPU, 4GB RAM |
| 1 | Python | 3.12+ con pip |
| 2 | n8n | Docker o npm (para webhooks) |
| 3 | PostgreSQL | Docker (para histórico) |
| 4 | OpenWebUI + OpenRouter | Docker + API Key |

**Coste servidor:** 20-40 €/mes (VPS básico)

**Instalación completa recomendada (EasyPanel):**
```bash
# 1. VPS con Ubuntu 22.04
# 2. Instalar EasyPanel: curl -sSL https://get.easypanel.io | sh
# 3. Crear apps desde EasyPanel:
#    - PostgreSQL (puerto 5432)
#    - n8n (puerto 5678)
#    - MCP GESAD (puerto 9999)
# 4. Configurar SSL automático
```

---

## Modelo de Licencia

### Opción A: Desarrollo + Implementación
| Fase | Precio | Notas |
|------|--------|-------|
| Fase 0 | 500-1.000 € | Análisis y Prueba |
| Fase 1 | 1.500-2.500 € | Fundamentos |
| Fase 2 | 1.000-1.500 € | Control GPS |
| Fase 3 | 3.000-4.000 € | Reporting |
| Fase 4 | 2.500-3.000 € | IA Chat |
| **Total** | **8.500-12.000 €** | Todo incluido |

### Opción B: Mantenimiento Mensual
| Servicio | Precio |
|----------|--------|
| Hosting (VPS) | 25 €/mes |
| Mantenimiento | 150 €/mes |
| Soporte | Incluido |
| OpenRouter (IA) | 5-15 €/mes |

---

## Próximos Pasos

1. **Demo gratuita** (1 hora)
   - Presentación del sistema
   - Configuración personalizada
   - Responder preguntas

2. **Piloto** (2 semanas)
   - Implementación Fase 1
   - Evaluación de resultados
   - Ajuste de parámetros

3. **Implementación completa**
   - Despliegue por fases
   - Formación equipo
   - Soporte continuo

---

## Contacto

**Desarrollador:** Jordi Arias  
**Email:** jariass2@gmail.com
**GitHub:** github.com/jariass2/MCP_Artris

---


