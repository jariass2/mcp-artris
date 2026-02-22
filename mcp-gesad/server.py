import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from config import config
from gesad_client import gesad_client
from cache_manager import cache_manager
from scheduler import gesad_scheduler
from data_processor import asistencia_processor
from data_processor_optimized import gesad_optimized_processor
from alert_manager import alert_manager

logger = logging.getLogger(__name__)

# Intentar importar MCP
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("gesad-asistencia-server")
    MCP_AVAILABLE = True
except ImportError:
    logger.warning("FastMCP no disponible. Algunas funciones no estarán disponibles.")
    mcp = None
    MCP_AVAILABLE = False


# =============================================================================
# MCP TOOLS - Definir siempre, decorar solo si MCP está disponible
# =============================================================================

async def get_estado_asistencia_actual() -> Dict[str, Any]:
    """Obtener estado actual de asistencia del monitoreo más reciente"""
    
    try:
        monitoring_result = await cache_manager.get("monitoring_result")
        
        if not monitoring_result:
            return {
                "error": "No hay datos de monitoreo disponibles",
                "mensaje": "El sistema no ha realizado ninguna verificación todavía",
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "timestamp": monitoring_result.get("timestamp"),
            "fecha": monitoring_result.get("fecha"),
            "total_trabajadores": monitoring_result.get("trabajadores_analizados", 0),
            "resumen": monitoring_result.get("resumen", {}),
            "alertas_count": len(monitoring_result.get("alertas", [])),
            "ultima_verificacion": monitoring_result.get("timestamp"),
            "api_calls": monitoring_result.get("api_calls_made", 0)
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado asistencia: {e}")
        return {"error": str(e), "timestamp": datetime.now().isoformat()}

    async def get_alertas_activas(tipo: Optional[str] = None) -> Dict[str, Any]:
        """Obtener alertas activas de ausencias y llegadas tardías
        
        Args:
            tipo: Filtrar por tipo de alerta ('ausencia_no_detectada', 'llegada_tardia')
        """
        
        try:
            if tipo:
                alertas = await alert_manager.filtrar_alertas_por_tipo(tipo)
            else:
                alertas_data = await alert_manager.get_alertas_activas()
                alertas = alertas_data.get("alertas", [])
            
            resumen = await alert_manager.get_resumen_alertas()
            
            return {
                "alertas": alertas,
                "total": len(alertas),
                "timestamp": datetime.now().isoformat(),
                "resumen": resumen,
                "filtros": {"tipo": tipo} if tipo else None
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo alertas activas: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    @mcp.tool()
    async def get_system_status() -> Dict[str, Any]:
        """Obtener estado completo del sistema de monitoreo"""
        
        try:
            scheduler_status = gesad_scheduler.get_status()
            api_usage = gesad_client.get_usage_stats()
            cache_stats = await cache_manager.get_stats()
            last_monitoring = await cache_manager.get("last_monitoring_result")
            alertas_resumen = await alert_manager.get_resumen_alertas()
            
            return {
                "scheduler": scheduler_status,
                "api_usage": api_usage,
                "cache_stats": cache_stats,
                "last_monitoring": last_monitoring,
                "alertas": alertas_resumen,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo system status: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    @mcp.tool()
    async def force_verification() -> Dict[str, Any]:
        """Forzar una verificación manual de asistencia"""
        
        try:
            result = await gesad_scheduler.force_check()
            return result
            
        except Exception as e:
            logger.error(f"Error en verificación forzada: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    @mcp.tool()
    async def get_datos_cruzados_optimizados() -> Dict[str, Any]:
        """Obtener datos cruzados optimizados con caché inteligente
        
        Retorna fichajes del día cruzados con información completa de usuarios y trabajadores,
        minimizando llamadas API mediante caché.
        """
        
        try:
            timestamp_actual = config.get_local_time()
            datos_cruzados = await gesad_optimized_processor.get_datos_cruzados(timestamp_actual)
            
            if "error" in datos_cruzados:
                return datos_cruzados
                
            return {
                "datos_cruzados": datos_cruzados,
                "timestamp": timestamp_actual.isoformat(),
                "optimization": {
                    "cache_hit_rate": datos_cruzados.get('cache_hit_rate', 0),
                    "api_calls_saved": datos_cruzados.get('total_usuarios_cache', 0) + datos_cruzados.get('total_trabajadores_cache', 0),
                    "efficiency": f"{datos_cruzados.get('cache_hit_rate', 0):.1f}%"
                }
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo datos cruzados optimizados: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    @mcp.tool()
    async def get_informes_ausencias_detallados(tipo: str = "sin_fichaje") -> Dict[str, Any]:
        """Obtener informes detallados de ausencias con datos de contacto
        
        Args:
            tipo: Tipo de ausencia ('sin_fichaje', 'fichaje_parcial', 'todos')
        """
        
        try:
            informes = await gesad_optimized_processor.get_informes_ausencias(tipo)
            
            return {
                "informes": informes,
                "tipo_filtro": tipo,
                "total_informes": len(informes.get('informes', [])) if isinstance(informes, dict) else 0,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo informes de ausencias: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    @mcp.tool()
    async def get_resumen_usuarios_ausencias() -> Dict[str, Any]:
        """Obtener resumen de usuarios con ausencias y datos de contacto"""
        
        try:
            resumen = await gesad_optimized_processor.get_resumen_usuarios_ausentes()
            
            return {
                "resumen": resumen,
                "total_usuarios_afectados": resumen.get('total_usuarios_afectados', 0) if isinstance(resumen, dict) else 0,
                "total_ausencias": resumen.get('total_ausencias', 0) if isinstance(resumen, dict) else 0,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo resumen usuarios ausencias: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    @mcp.tool()
    async def get_estadisticas_optimizacion() -> Dict[str, Any]:
        """Obtener estadísticas detalladas de optimización y rendimiento"""
        
        try:
            stats = await gesad_optimized_processor.get_estadisticas_optimizacion()
            
            return {
                "estadisticas": stats,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de optimización: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    # =============================================================================
    # MCP RESOURCES - Solo si MCP está disponible
    # =============================================================================

    @mcp.resource("gesad://monitoring/live-dashboard")
    async def live_dashboard() -> str:
        """Dashboard en tiempo real del estado de asistencia"""
        
        try:
            dashboard_data = await asistencia_processor.get_dashboard_data()
            
            if "error" in dashboard_data:
                return f"❌ Error: {dashboard_data['error']}"
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            dashboard = f"""
📊 DASHBOARD DE ASISTENCIA GESAD - {timestamp}

🖥️ ESTADO DEL SISTEMA:
{'🟢 ACTIVO' if dashboard_data.get('sistema', {}).get('activo') else '🔴 INACTIVO'}
• Scheduler: {'✅ Corriendo' if dashboard_data.get('sistema', {}).get('scheduler_running') else '❌ Detenido'}
• Modo Sleep: {'😴 Activo' if dashboard_data.get('sistema', {}).get('sleep_mode') else '🏃 Despierto'}

👥 ESTADO GENERAL DE ASISTENCIA:
• Total trabajadores: {dashboard_data.get('resumen', {}).get('total', 0)}
• Presentes a tiempo: {dashboard_data.get('resumen', {}).get('presentes_tiempo', 0)} ✅
• Con llegada tardía: {dashboard_data.get('resumen', {}).get('llegadas_tardias', 0)} ⏰
• Ausentes no detectados: {dashboard_data.get('resumen', {}).get('ausentes_no_detectados', 0)} ❌
• Pendientes de fichar: {dashboard_data.get('resumen', {}).get('pendientes_fichar', 0)} ⏳

📊 USO API:
• Llamadas hoy: {dashboard_data.get('api_usage', {}).get('daily_calls', 0)}
• Límite diario: {dashboard_data.get('api_usage', {}).get('daily_limit', 500)}
• Uso: {dashboard_data.get('api_usage', {}).get('usage_percentage', 0):.1f}%

🚨 ALERTAS ACTIVAS:
{len(dashboard_data.get('alertas', []))} alertas activas

💾 CACHE PERFORMANCE:
• Hit rate: {dashboard_data.get('cache_stats', {}).get('hit_rate_percent', 0):.1f}%
"""
            return dashboard.strip()
            
        except Exception as e:
            logger.error(f"Error generando dashboard: {e}")
            return f"❌ Error generando dashboard: {str(e)}"

    @mcp.resource("gesad://monitoring/system-status")
    async def system_status_resource() -> str:
        """Estado del sistema formateado para IA"""
        
        try:
            status = await get_system_status()
            
            if "error" in status:
                return f"❌ Error: {status['error']}"
            
            scheduler = status.get('scheduler', {})
            api = status.get('api_usage', {})
            cache = status.get('cache_stats', {})
            
            output = f"""
🖥️ ESTADO COMPLETO DEL SISTEMA GESAD
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚡ SCHEDULER:
• Corriendo: {'✅ Sí' if scheduler.get('running') else '❌ No'}
• Horario activo: {'✅ Sí' if scheduler.get('is_active_time') else '❌ No'}
• Modo sleep: {'😴 Sí' if scheduler.get('sleep_mode') else '🏃 No'}
• Verificaciones hoy: {scheduler.get('check_count', 0)}

🌐 API CLIENT:
• Llamadas hoy: {api.get('daily_calls', 0)} / {api.get('daily_limit', 500)}
• Uso porcentaje: {api.get('usage_percentage', 0):.1f}%

💾 CACHE SYSTEM:
• Hit rate: {cache.get('hit_rate_percent', 0):.1f}%
• Memory hits: {cache.get('memory_hits', 0)}
• Disk hits: {cache.get('disk_hits', 0)}

📊 MONITORING:
• Alertas activas: {status.get('alertas', {}).get('total', 0)}
• Requieren acción: {status.get('alertas', {}).get('requieren_accion', 0)}
"""
            return output.strip()
            
        except Exception as e:
            logger.error(f"Error generando system status: {e}")
            return f"❌ Error obteniendo estado del sistema: {str(e)}"


# =============================================================================
# Funciones principales del sistema
# =============================================================================

async def initialize_server():
    """Inicializar el MCP server con el scheduler"""
    
    # Precargar datos maestros al inicio (sin importar la hora)
    await gesad_scheduler.precargar_datos_maestros()
    
    # Configurar callback del scheduler
    gesad_scheduler.set_monitoring_callback(asistencia_processor.process_monitoring_check)
    
    # Iniciar scheduler
    await gesad_scheduler.start()
    
    logger.info("🚀 MCP Server GESAD inicializado exitosamente")


async def main():
    """Función principal para ejecutar el MCP server"""
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Configurar logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Validar configuración
    config.validate()
    
    # Inicializar servidor
    await initialize_server()
    
# Iniciar MCP server solo si está disponible
    if MCP_AVAILABLE and mcp:
        logger.info("🚀 Iniciando MCP Server con transport: stdio")
        
        # Intentar usar nest_asyncio para permitir loops anidados
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            logger.warning("nest_asyncio no está instalado. Si hay problemas con el loop de eventos, por favor instálelo: pip install nest_asyncio")
        
        await mcp.run_stdio_async()
    else:
        logger.warning("⚠️ MCP no disponible. El sistema seguirá funcionando en modo standalone.")
        logger.info("🔄 El scheduler seguirá ejecutando el monitoreo automático.")
        
        # Mantener el sistema corriendo
        try:
            while True:
                await asyncio.sleep(60)  # Verificar cada minuto
        except KeyboardInterrupt:
            logger.info("🛑 Sistema detenido por usuario")
        finally:
            await gesad_scheduler.stop()


if __name__ == "__main__":
    asyncio.run(main())