#!/usr/bin/env python3
"""
Script de inicio simplificado que evita problemas de asyncio loop
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from config import config
from gesad_client import gesad_client
from cache_manager import cache_manager
from scheduler import gesad_scheduler
from data_processor_optimized import gesad_optimized_processor
from alert_manager import alert_manager

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class GESADMonitoringServer:
    """Servidor de monitoreo simplificado"""
    
    def __init__(self):
        self.running = False
        self.scheduler_task = None
    
    async def start(self):
        """Iniciar el servidor de monitoreo"""
        logger.info("🚀 Iniciando servidor de monitoreo GESAD")
        
        # Validar configuración
        try:
            config.validate()
            logger.info("✅ Configuración validada")
        except Exception as e:
            logger.error(f"❌ Error en configuración: {e}")
            return False
        
        # Inicializar scheduler con procesador optimizado
        gesad_scheduler.set_monitoring_callback(gesad_optimized_processor.process_monitoring_check)
        
        # Iniciar monitoreo
        await gesad_scheduler.start()
        self.running = True
        
        logger.info("✅ Servidor de monitoreo iniciado exitosamente")
        return True
    
    async def stop(self):
        """Detener el servidor"""
        logger.info("🛑 Deteniendo servidor de monitoreo")
        
        self.running = False
        
        if gesad_scheduler.running:
            await gesad_scheduler.stop()
        
        logger.info("✅ Servidor detenido")
    
    async def run_forever(self):
        """Mantener el servidor corriendo"""
        if not await self.start():
            return
        
        try:
            while self.running:
                await asyncio.sleep(60)
                
                # Mostrar estado cada hora
                import time
                if int(time.time()) % 3600 < 60:  # Aproximadamente cada hora
                    status = gesad_scheduler.get_status()
                    logger.info(f"📊 Estado: {status['check_count']} verificaciones, API: {gesad_client.get_usage_stats()['daily_calls']} llamadas")
        
        except KeyboardInterrupt:
            logger.info("⌨️ Interrupción por usuario")
        except Exception as e:
            logger.error(f"❌ Error inesperado: {e}")
        finally:
            await self.stop()
    
    async def run_with_mcp(self):
        """Ejecutar con MCP si está disponible"""
        try:
            from mcp.server.fastmcp import FastMCP
            mcp = FastMCP("gesad-asistencia-server")
            
            # Añadir tools básicas
            @mcp.tool()
            async def get_system_status():
                return gesad_scheduler.get_status()
            
            @mcp.tool() 
            async def force_verification():
                return await gesad_scheduler.force_check()
            
            # Iniciar scheduler primero
            await self.start()
            
            # Luego iniciar MCP
            logger.info("🚀 Iniciando MCP Server")
            
            # Usar run_stdio_async para evitar el problema de loop
            import nest_asyncio
            nest_asyncio.apply()
            
            await mcp.run_stdio_async()
            
        except ImportError:
            logger.warning("⚠️ MCP no disponible, ejecutando en modo standalone")
            await self.run_forever()
        except Exception as e:
            logger.error(f"❌ Error MCP: {e}")
            logger.info("🔄 Cambiando a modo standalone")
            await self.run_forever()

# Manejo de señales
def signal_handler(signum, frame):
    print(f"\n🛑 Señal {signum} recibida, deteniendo servidor...")
    sys.exit(0)

async def main():
    """Función principal"""
    # Configurar manejo de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Cargar variables de entorno
    print("🔧 Cargando variables de entorno...")
    load_dotenv()
    
    # Recargar configuración para asegurar que las variables de entorno estén cargadas
    print("🔄 Recargando configuración...")
    config.reload_from_env()
    
    print("🔧 Configuración final:")
    print(f"   WEBHOOK_URL: {config.WEBHOOK_URL}")
    print(f"   WEBHOOK_ENABLED: {config.WEBHOOK_ENABLED}")
    print(f"   WEBHOOK_EVENTS: {config.WEBHOOK_EVENTS}")
    print()
    
    # Crear servidor
    server = GESADMonitoringServer()
    
    # Determinar modo de ejecución
    if len(sys.argv) > 1 and sys.argv[1] == "--standalone":
        logger.info("🔧 Modo standalone")
        await server.run_forever()
    else:
        logger.info("🤖 Modo MCP (con fallback a standalone)")
        await server.run_with_mcp()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Programa detenido por usuario")
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        sys.exit(1)