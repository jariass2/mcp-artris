import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any

from config import config
from cache_manager import cache_manager
from gesad_client import gesad_client

logger = logging.getLogger(__name__)


class GESADScheduler:
    """Scheduler con horario restringido para monitoreo GESAD"""
    
    def __init__(self):
        self.active_hours = (config.ACTIVE_START, config.ACTIVE_END)  # 6 AM a 12 PM
        self.check_interval = config.get_check_interval_seconds()  # 20 minutos en segundos
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.last_check_time: Optional[datetime] = None
        self.check_count = 0
        self.sleep_mode = False
        
        # Callback para ejecutar en cada verificación
        self.monitoring_callback: Optional[Callable] = None
    
    def is_active_time(self, current_time: Optional[datetime] = None) -> bool:
        """Verificar si estamos en horario activo (6:00 AM - 12:00 PM Madrid)"""
        return config.is_active_time(current_time)
    
    def get_time_until_active(self) -> timedelta:
        """Obtener tiempo hasta próxima activación (6:00 AM Madrid)"""
        return config.get_time_until_active()
    
    def get_time_until_sleep(self) -> timedelta:
        """Obtener tiempo hasta modo sleep (12:00 PM)"""
        now = datetime.now()
        
        if now.hour < self.active_hours[1]:
            # Todavía es antes de 12 PM
            sleep_time = now.replace(hour=self.active_hours[1], minute=0, second=0, microsecond=0)
            return sleep_time - now
        else:
            # Ya es después de 12 PM
            return timedelta(0)
    
    async def sleep_until_active(self):
        """Dormir hasta próxima activación (6:00 AM Madrid)"""
        wait_time = config.get_time_until_active()
        wait_seconds = int(wait_time.total_seconds())
        
        logger.info(f"💤 Sistema entrando en modo sleep por {wait_seconds} segundos")
        logger.info(f"📅 Próxima activación: {config.get_local_time() + wait_time}")
        
        self.sleep_mode = True
        
        # Guardar estado de sleep en cache
        await cache_manager.set("system_sleep_mode", {
            "active": True,
            "wakeup_time": (config.get_local_time() + wait_time).isoformat(),
            "sleep_start": config.get_local_time().isoformat(),
            "timezone": config.TIMEZONE
        }, ttl=24 * 3600)  # 24 horas
        
        await asyncio.sleep(wait_seconds)
        
        self.sleep_mode = False
        logger.info("☀️ Sistema activando - iniciando monitoreo")
        
        # Limpiar estado de sleep
        await cache_manager.delete("system_sleep_mode")
    
    async def sleep_until_next_check(self):
        """Dormir hasta próxima verificación (solo en horario activo)"""
        await asyncio.sleep(self.check_interval)
    
    async def execute_monitoring_check(self):
        """Ejecutar una verificación de monitoreo"""
        
        self.check_count += 1
        self.last_check_time = datetime.now()
        
        logger.info(f"🔍 Ejecutando verificación #{self.check_count} a las {self.last_check_time.strftime('%H:%M:%S')}")
        
        try:
            if self.monitoring_callback:
                result = await self.monitoring_callback()
                
                # Guardar resultado en cache
                await cache_manager.set("last_monitoring_result", {
                    "timestamp": self.last_check_time.isoformat(),
                    "check_number": self.check_count,
                    "result": result,
                    "success": True
                }, ttl=config.get_check_interval_seconds() + 60)  # TTL un poco más largo que intervalo
                
                return result
            
        except Exception as e:
            logger.error(f"Error en verificación de monitoreo: {e}")
            
            # Guardar error en cache
            await cache_manager.set("last_monitoring_result", {
                "timestamp": self.last_check_time.isoformat(),
                "check_number": self.check_count,
                "error": str(e),
                "success": False
            }, ttl=config.get_check_interval_seconds())
            
            return {"error": str(e)}
    
    async def monitoring_loop(self):
        """Loop principal de monitoreo con precarga optimizada"""
        
        logger.info("🚀 Iniciando loop de monitoreo GESAD")
        logger.info(f"⏰ Horario activo: {self.active_hours[0]:02d}:00 - {self.active_hours[1]:02d}:00")
        logger.info(f"🔄 Intervalo de verificación: {config.CHECK_INTERVAL} minutos")
        
        # Precargar listas de usuarios y trabajadores al iniciar
        await self.precargar_datos_maestros()
        
        while self.running:
            try:
                if self.is_active_time():
                    # Horario activo - ejecutar verificación con datos cacheados
                    await self.execute_monitoring_check()
                    
                    # Verificar si queda tiempo en horario activo
                    if self.is_active_time():
                        await self.sleep_until_next_check()
                    else:
                        logger.info("🌙 Finalizando horario activo - entrando en modo sleep")
                        await self.sleep_until_active()
                else:
                    # Horario inactivo - dormir hasta activación
                    await self.sleep_until_active()
                    
            except asyncio.CancelledError:
                logger.info("🛑 Loop de monitoreo cancelado")
                break
            except Exception as e:
                logger.error(f"Error inesperado en loop de monitoreo: {e}")
                await asyncio.sleep(60)  # Esperar 1 minuto antes de reintentar
    
    async def precargar_datos_maestros(self):
        """Precargar usuarios y trabajadores en cache al inicio del día"""
        
        from gesad_client import gesad_client
        from cache_manager import cache_manager
        
        try:
            logger.info("📥 Precargando datos maestros (usuarios y trabajadores)...")
            
            # Precargar lista de usuarios
            cache_key_usuarios = "usuarios_lista_completa"
            usuarios_cache = await cache_manager.get(cache_key_usuarios)
            
            if not usuarios_cache:
                logger.info("📥 Obteniendo lista completa de usuarios...")
                usuarios_result = await self.obtener_usuarios_completos()
                
                if usuarios_result and "error" not in usuarios_result:
                    await cache_manager.set(cache_key_usuarios, usuarios_result, ttl=24 * 3600)  # 24 horas
                    logger.info(f"✅ {len(usuarios_result)} usuarios cacheados")
                else:
                    logger.warning(f"❌ Error obteniendo usuarios: {usuarios_result.get('error', 'Unknown')}")
            
            # Precargar lista de trabajadores
            cache_key_trabajadores = "trabajadores_lista_completa"
            trabajadores_cache = await cache_manager.get(cache_key_trabajadores)
            
            if not trabajadores_cache:
                logger.info("👥 Obteniendo lista completa de trabajadores...")
                trabajadores_result = await self.obtener_trabajadores_completos()
                
                if trabajadores_result and "error" not in trabajadores_result:
                    await cache_manager.set(cache_key_trabajadores, trabajadores_result, ttl=24 * 3600)  # 24 horas
                    logger.info(f"✅ {len(trabajadores_result)} trabajadores cacheados")
                else:
                    logger.warning(f"❌ Error obteniendo trabajadores: {trabajadores_result.get('error', 'Unknown')}")
            
            logger.info("📦 Precarga de datos maestros completada")
            logger.info("🔗 Los datos estarán disponibles para cruzar con fichajes durante el día")
            
        except Exception as e:
            logger.error(f"❌ Error en precarga de datos maestros: {e}")
    
    async def obtener_usuarios_completos(self):
        """Obtener lista completa de usuarios con paginación y fallback de año"""

        fecha_actual = config.get_local_time().strftime('%d-%m-%Y')
        url = f"{config.BASE_URL}/Usuarios/Expedientes/{config.SESSION_ID}"
        año_actual = config.get_local_time().year

        for años_atras in range(6):
            fecha_inicio = f'01-01-{año_actual - años_atras}'
            all_usuarios = []
            pagina = 1
            tiene_mas = True

            while tiene_mas:
                params = {
                    'fecha_Inicio': fecha_inicio,
                    'fecha_Fin': fecha_actual,
                    'numero_Pagina': pagina,
                    'registros_Pagina': 1000
                }
                result = await gesad_client._make_request_with_retry("GET", url, params=params)

                if result and "error" not in result and isinstance(result, list):
                    all_usuarios.extend(result)
                    if len(result) < 1000:
                        tiene_mas = False
                    else:
                        pagina += 1
                        await asyncio.sleep(0.5)
                else:
                    tiene_mas = False
                    logger.warning(f"Error obteniendo usuarios página {pagina}: {result}")

            if all_usuarios:
                if años_atras > 0:
                    logger.info(f"✅ Usuarios encontrados con fecha_Inicio={fecha_inicio} ({años_atras} año(s) atrás)")
                return all_usuarios

            logger.info(f"Sin usuarios desde {fecha_inicio}, retrocediendo un año...")

        logger.error("No se encontraron usuarios en los últimos 6 años")
        return []
    
    async def obtener_trabajadores_completos(self):
        """Obtener lista completa de trabajadores con paginación y fallback de año"""

        fecha_actual = config.get_local_time().strftime('%d-%m-%Y')
        url = f"{config.BASE_URL}/Trabajadores/Expedientes/{config.SESSION_ID}"
        año_actual = config.get_local_time().year

        for años_atras in range(6):
            fecha_inicio = f'01-01-{año_actual - años_atras}'
            all_trabajadores = []
            pagina = 1
            tiene_mas = True

            while tiene_mas:
                params = {
                    'fecha_Inicio': fecha_inicio,
                    'fecha_Fin': fecha_actual,
                    'numero_Pagina': pagina,
                    'registros_Pagina': 1000
                }
                result = await gesad_client._make_request_with_retry("GET", url, params=params)

                if result and "error" not in result and isinstance(result, list):
                    all_trabajadores.extend(result)
                    if len(result) < 1000:
                        tiene_mas = False
                    else:
                        pagina += 1
                        await asyncio.sleep(0.5)
                else:
                    tiene_mas = False
                    logger.warning(f"Error obteniendo trabajadores página {pagina}: {result}")

            if all_trabajadores:
                if años_atras > 0:
                    logger.info(f"✅ Trabajadores encontrados con fecha_Inicio={fecha_inicio} ({años_atras} año(s) atrás)")
                return all_trabajadores

            logger.info(f"Sin trabajadores desde {fecha_inicio}, retrocediendo un año...")

        logger.error("No se encontraron trabajadores en los últimos 6 años")
        return []
    
    def set_monitoring_callback(self, callback: Callable):
        """Establecer callback para ejecutar en cada verificación"""
        self.monitoring_callback = callback
    
    async def start(self):
        """Iniciar scheduler"""
        if self.running:
            logger.warning("Scheduler ya está corriendo")
            return
        
        self.running = True
        self.check_count = 0
        
        # Limpiar estados anteriores
        await cache_manager.delete("system_sleep_mode")
        
        # Iniciar loop
        self.monitor_task = asyncio.create_task(self.monitoring_loop())
        
        logger.info("✅ Scheduler GESAD iniciado exitosamente")
    
    async def stop(self):
        """Detener scheduler"""
        if not self.running:
            logger.warning("Scheduler no está corriendo")
            return
        
        self.running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 Scheduler GESAD detenido")
    
    async def force_check(self) -> Dict[str, Any]:
        """Forzar una verificación manual"""
        logger.info("🔨 Forzando verificación manual de monitoreo")
        
        if not self.monitoring_callback:
            return {"error": "No monitoring callback configured"}
        
        result = await self.execute_monitoring_check()
        return result or {"error": "Check failed"}
    
    def get_status(self) -> Dict[str, Any]:
        """Obtener estado actual del scheduler"""
        
        return {
            "running": self.running,
            "sleep_mode": self.sleep_mode,
            "is_active_time": self.is_active_time(),
            "check_count": self.check_count,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "check_interval_seconds": config.get_check_interval_seconds(),
            "active_hours": f"{self.active_hours[0]:02d}:00 - {self.active_hours[1]:02d}:00",
            "timezone": config.TIMEZONE,
            "current_time_madrid": config.get_local_time().isoformat(),
            "time_until_active": str(config.get_time_until_active()) if not self.is_active_time() else None
        }


# Scheduler global
gesad_scheduler = GESADScheduler()