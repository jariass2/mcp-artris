# Despliegue en VPS con EasyPanel

## Requisitos previos

- VPS con EasyPanel instalado
- Acceso al panel en `https://<tu-dominio-easypanel>`
- Cuenta GitHub con acceso al repositorio `jariass2/mcp-artris`
- GitHub Personal Access Token configurado en EasyPanel (Settings → GitHub Token)

---

## Paso 1 — Crear el proyecto

En EasyPanel → **New Project** → nombre: `gesad` (o el que prefieras).

> Si EasyPanel tiene límite de proyectos, usa uno existente.

---

## Paso 2 — Crear el servicio App

Dentro del proyecto → **Create Service** → **App**.

| Campo | Valor |
|---|---|
| Service Name | `gesad-monitoring` |
| Source | GitHub |
| Repository | `jariass2/mcp-artris` |
| Branch | `master` |
| Root Directory | `/mcp-gesad` |
| Build | Nixpacks (auto-detectado) |

> El `Procfile` define el comando de inicio: `python start_monitoring.py --standalone`

---

## Paso 3 — Variables de entorno

En la pestaña **Environment**, añadir las siguientes variables.

> ⚠️ Valores con caracteres especiales (`#`, `@`, `%`) deben ir **entre comillas dobles**.

```env
GESAD_CONEX_NAME=CLOUD01
GESAD_AUTH_CODE=R0_F5FB07C4-0E63-4A7A-BA8A-43108D19224B
GESAD_BASIC_AUTH=dXNlcndzX2FydHJpczpKZk4yM1BiI1FCJjFKejY=
GESAD_API_CODE="ARTRIS_4Jk#pL%1@"
GESAD_SESSION_ID=R0_F5FB07C4-0E63-4A7A-BA8A-43108D19224B
GESAD_BASE_URL=https://data-bi.ayudadomiciliaria.com/api
GESAD_TIMEZONE=Europe/Madrid
GESAD_ACTIVE_START=6
GESAD_ACTIVE_END=24
GESAD_CHECK_INTERVAL=20
GESAD_CACHE_DIR=./cache
GESAD_CACHE_PERSISTENT_DAYS=7
GESAD_DAILY_LIMIT=500
GESAD_EMERGENCY_BUFFER=50
GESAD_REQUEST_TIMEOUT=30
GESAD_BATCH_SIZE=20
GESAD_RETRY_ATTEMPTS=3
GESAD_LOG_LEVEL=INFO
GESAD_WEBHOOK_URL=https://n8n.multiplai.org/webhook/fichaje
GESAD_WEBHOOK_ENABLED=true
GESAD_WEBHOOK_TIMEOUT=30
GESAD_WEBHOOK_EVENTS=ausencia,fichaje_manual,retraso_confirmado,salida_adelantada,salida_tarde,fichaje_adelantado,ubicacion_fuera_rango
GESAD_UMBRAL_LLEGADA_ADELANTADA=20
GESAD_UMBRAL_RETRASO_AUSENCIA=20
GESAD_UMBRAL_SALIDA_ADELANTADA=10
GESAD_UMBRAL_SALIDA_TARDE=10
GESAD_UMBRAL_DISTANCIA_UBICACION=50
```

---

## Paso 4 — Deploy

Click en **Deploy**. EasyPanel clonará el repo, ejecutará Nixpacks y levantará el contenedor.

El build tarda ~2-3 minutos. Al finalizar, el servicio aparece como `Running`.

---

## Verificación

En los logs del servicio deberías ver:

```
✅ Configuración validada
✅ 2199 usuarios cacheados
✅ 269 trabajadores cacheados
🔍 Ejecutando verificación #1 ...
✅ Webhook enviado correctamente
```

---

## Deploy automático desde GitHub

Para que cada `git push` redesplegue automáticamente:

1. En el servicio → **Settings** → activar **Auto Deploy**
2. EasyPanel añadirá un webhook en el repositorio de GitHub

---

## Problemas conocidos

### `api_Code no válido` (HTTP 409)
El valor de `GESAD_API_CODE` contiene `#` que se interpreta como comentario en formato `.env`.
**Solución:** el valor debe ir entre comillas dobles: `GESAD_API_CODE="ARTRIS_4Jk#pL%1@"`

### Conflicto de dependencias en build
`fastapi==0.104.1` (anyio<4) es incompatible con `mcp>=1.0.0` (anyio>=4.5).
**Solución:** `requirements.txt` ya no incluye fastapi/uvicorn. No añadirlos.

### Servicio deshabilitado tras build fallido
EasyPanel deshabilita el servicio automáticamente si el build falla.
**Solución:** corregir el error y hacer deploy de nuevo desde el panel o via webhook.
