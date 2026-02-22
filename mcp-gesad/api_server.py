#!/usr/bin/env python3
"""
Servidor HTTP API para integrar MCP GESAD con n8n
Expone las funciones del MCP como endpoints REST
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Importaciones del sistema MCP
from config import config
from data_processor_optimized import gesad_optimized_processor
from cache_manager import cache_manager
from gesad_client import gesad_client
from scheduler import gesad_scheduler

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title="GESAD MCP API for n8n",
    description="API HTTP para integrar sistema GESAD con n8n workflows",
    version="1.0.0"
)

# Configurar CORS para n8n
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios de n8n
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Modelos Pydantic para requests
class MonitoringRequest(BaseModel):
    force_check: bool = False

class AlertRequest(BaseModel):
    tipo: str = "todos"  # 'sin_fichaje', 'fichaje_parcial', 'todos'

# Endpoints principales
@app.get("/")
async def root():
    """Endpoint raíz con información del sistema"""
    return {
        "sistema": "GESAD MCP API for n8n",
        "estado": "operativo",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "datos_cruzados": "/datos-cruzados",
            "informes_ausencias": "/informes/ausencias",
            "resumen_usuarios": "/resumen/usuarios",
            "estadisticas": "/estadisticas",
            "estado_sistema": "/estado/sistema",
            "forzar_verificacion": "/monitoring/force-check",
            "alertas": "/alertas",
            "dashboard": "/dashboard"
        }
    }

@app.get("/datos-cruzados")
async def get_datos_cruzados():
    """Obtener datos cruzados optimizados"""
    try:
        timestamp = config.get_local_time()
        result = await gesad_optimized_processor.get_datos_cruzados(timestamp)
        
        return {
            "success": True,
            "data": result,
            "timestamp": timestamp.isoformat()
        }
    except Exception as e:
        logger.error(f"Error en /datos-cruzados: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/informes/ausencias")
async def get_informes_ausencias(tipo: str = "sin_fichaje"):
    """Obtener informes de ausencias"""
    try:
        result = await gesad_optimized_processor.get_informes_ausencias(tipo)
        
        return {
            "success": True,
            "data": result,
            "tipo_filtro": tipo,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error en /informes/ausencias: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/resumen/usuarios")
async def get_resumen_usuarios():
    """Obtener resumen de usuarios con ausencias"""
    try:
        result = await gesad_optimized_processor.get_resumen_usuarios_ausentes()
        
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error en /resumen/usuarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/estadisticas")
async def get_estadisticas():
    """Obtener estadísticas de optimización"""
    try:
        result = await gesad_optimized_processor.get_estadisticas_optimizacion()
        
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error en /estadisticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/estado/sistema")
async def get_estado_sistema():
    """Obtener estado completo del sistema"""
    try:
        # Estado del scheduler
        scheduler_status = gesad_scheduler.get_status()
        
        # Estadísticas API
        api_stats = gesad_client.get_usage_stats()
        
        # Estadísticas cache
        cache_stats = await cache_manager.get_stats()
        
        # Fichajes procesados hoy
        procesados_hoy = await cache_manager.get_fichajes_procesados_hoy()
        
        return {
            "success": True,
            "data": {
                "scheduler": scheduler_status,
                "api_usage": api_stats,
                "cache_stats": cache_stats,
                "fichajes_procesados_hoy": procesados_hoy,
                "timestamp": datetime.now().isoformat(),
                "timezone": config.TIMEZONE
            }
        }
    except Exception as e:
        logger.error(f"Error en /estado/sistema: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/monitoring/force-check")
async def force_monitoring_check(background_tasks: BackgroundTasks, request: MonitoringRequest):
    """Forzar una verificación manual de asistencia"""
    try:
        # Ejecutar en background para no bloquear
        background_tasks.add_task(
            gesad_scheduler.force_check
        )
        
        return {
            "success": True,
            "message": "Verificación forzada iniciada",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error en /monitoring/force-check: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alertas")
async def get_alertas(tipo: str = "todos"):
    """Obtener alertas activas"""
    try:
        from alert_manager import alert_manager
        
        if tipo:
            alertas = await alert_manager.filtrar_alertas_por_tipo(tipo)
        else:
            alertas_data = await alert_manager.get_alertas_activas()
            alertas = alertas_data.get("alertas", [])
        
        resumen = await alert_manager.get_resumen_alertas()
        
        return {
            "success": True,
            "data": {
                "alertas": alertas,
                "total": len(alertas),
                "resumen": resumen
            },
            "tipo_filtro": tipo,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error en /alertas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard")
async def get_dashboard():
    """Obtener datos para dashboard"""
    try:
        timestamp = config.get_local_time()
        result = await gesad_optimized_processor.get_datos_cruzados(timestamp)
        
        if "error" in result:
            return {
                "success": False,
                "error": result["error"],
                "timestamp": timestamp.isoformat()
            }
        
        # Crear dashboard amigable
        dashboard = {
            "titulo": f"Dashboard GESAD - {timestamp.strftime('%d/%m/%Y %H:%M')}",
            "resumen": {
                "total_fichajes": result.get("total_fichajes", 0),
                "ausencias_detectadas": result.get("ausencias_detectadas", 0),
                "fichajes_parciales": result.get("fichajes_parciales", 0),
                "fichajes_completos": result.get("fichajes_completos", 0),
                "usuarios_cacheados": result.get("total_usuarios_cache", 0),
                "trabajadores_cacheados": result.get("total_trabajadores_cache", 0)
            },
            "eficiencia": {
                "api_calls_today": result.get("api_calls_today", 0),
                "cache_hit_rate": result.get("cache_hit_rate", 0),
                "porcentaje_uso_api": (result.get("api_calls_today", 0) / 500) * 100
            },
            "timestamp": timestamp.isoformat()
        }
        
        return {
            "success": True,
            "data": dashboard
        }
    except Exception as e:
        logger.error(f"Error en /dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/fichajes-procesados")
async def get_fichajes_procesados(tipo: str = "todos"):
    """Obtener lista de fichajes procesados (para administración)
    
    Args:
        tipo: Tipo de ausencia ('sin_fichaje', 'fichaje_parcial', 'todos')
    """
    try:
        lista_procesados = await cache_manager.get_lista_procesados_detalle(tipo)
        stats = await cache_manager.get_fichajes_procesados_hoy()
        
        return {
            "success": True,
            "data": {
                "lista_procesados": lista_procesados,
                "estadisticas": stats
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error en /admin/fichajes-procesados: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/reset-procesados")
async def reset_fichajes_procesados(tipo: str = "todos"):
    """Resetear fichajes procesados
    
    Args:
        tipo: Tipo de ausencia a resetear ('sin_fichaje', 'fichaje_parcial', 'todos')
    """
    try:
        resultado = await cache_manager.reset_fichajes_procesados_hoy(tipo)
        
        return {
            "success": resultado,
            "message": f"Fichajes procesados reseteados (tipo: {tipo})",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error en /admin/reset-procesados: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/fichaje-procesado/{fichaje_id}")
async def remove_fichaje_procesado(fichaje_id: str, tipo: str = "sin_fichaje"):
    """Remover un fichaje específico de la lista de procesados
    
    Args:
        fichaje_id: ID del fichaje a remover
        tipo: Tipo de ausencia
    """
    try:
        resultado = await cache_manager.remove_fichaje_procesado(fichaje_id, tipo)
        
        return {
            "success": resultado,
            "message": f"Fichaje {fichaje_id} removido de procesados" if resultado else f"Fichaje {fichaje_id} no encontrado",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error en /admin/fichaje-procesado/{fichaje_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check para monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "GESAD MCP API"
    }

# Iniciar servidor
def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Iniciar el servidor HTTP API"""
    
    logger.info(f"🚀 Iniciando GESAD MCP API en http://{host}:{port}")
    logger.info("📚 Documentación disponible en: http://localhost:8000/docs")
    logger.info("🔗 Endpoints para n8n configurados con CORS")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GESAD MCP API Server for n8n")
    parser.add_argument("--host", default="0.0.0.0", help="Host del servidor (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Puerto del servidor (default: 8000)")
    
    args = parser.parse_args()
    
    # Cargar configuración
    try:
        config.validate()
        logger.info("✅ Configuración validada")
    except Exception as e:
        logger.error(f"❌ Error configuración: {e}")
        exit(1)
    
    # Iniciar servidor
    start_server(args.host, args.port)