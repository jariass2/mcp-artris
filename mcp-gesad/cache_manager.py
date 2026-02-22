import os
import json
import time
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List
from pathlib import Path
import aiofiles

from config import config

logger = logging.getLogger(__name__)


class CacheManager:
    """Sistema de caché multinivel para MCP GESAD"""
    
    def __init__(self):
        self.cache_dir = Path(config.CACHE_DIR)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Cache en memoria para datos frecuentes
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        
        # TTL configurations
        self.ttl_config = {
            'usuarios_lista_completa': {'ttl': 24 * 3600, 'priority': 'persistent'},  # 24 horas
            'trabajadores_lista_completa': {'ttl': 24 * 3600, 'priority': 'persistent'},  # 24 horas
            'trabajador_info': {'ttl': 7 * 24 * 3600, 'priority': 'persistent'},     # 7 días
            'usuario_info': {'ttl': 3 * 24 * 3600, 'priority': 'persistent'},        # 3 días
            'fichajes_hoy': {'ttl': 300, 'priority': 'temporal'},                    # 5 min
            'dashboard_estado': {'ttl': 1200, 'priority': 'temporal'},              # 20 min
            'alertas_activas': {'ttl': 3600, 'priority': 'temporal'},               # 1 hora
            'estadisticas_dia': {'ttl': 3600, 'priority': 'temporal'},             # 1 hora
            'monitoring_result': {'ttl': 1200, 'priority': 'temporal'}              # 20 min
        }
        
        # Estadísticas
        self.stats = {
            'memory_hits': 0,
            'disk_hits': 0,
            'misses': 0,
            'sets': 0
        }
    
    def _get_cache_file(self, key: str) -> Path:
        """Obtener path de archivo de caché"""
        # Sanitizar key para filename
        safe_key = key.replace('/', '_').replace(':', '_')
        return self.cache_dir / f"{safe_key}.json"
    
    def _is_expired(self, cache_entry: Dict[str, Any], ttl: int) -> bool:
        """Verificar si entrada de caché está expirada"""
        timestamp = cache_entry.get('timestamp', 0)
        return (time.time() - timestamp) > ttl
    
    def _get_ttl_for_key(self, key: str) -> int:
        """Obtener TTL para una key específica"""
        for pattern, config in self.ttl_config.items():
            if pattern in key:
                return config['ttl']
        return 300  # Default 5 min
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Obtener valor del caché (memoria o disco)"""
        
        # Primero intentar memoria cache
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            ttl = self._get_ttl_for_key(key)
            
            if not self._is_expired(entry, ttl):
                self.stats['memory_hits'] += 1
                logger.debug(f"Memory cache hit: {key}")
                return entry['data']
            else:
                # Limpiar de memoria cache si está expirado
                del self.memory_cache[key]
        
        # Intentar disco cache
        cache_file = self._get_cache_file(key)
        if cache_file.exists():
            try:
                async with aiofiles.open(cache_file, 'r') as f:
                    content = await f.read()
                    entry = json.loads(content)
                
                ttl = self._get_ttl_for_key(key)
                if not self._is_expired(entry, ttl):
                    # Cargar a memoria cache
                    self.memory_cache[key] = entry
                    self.stats['disk_hits'] += 1
                    logger.debug(f"Disk cache hit: {key}")
                    return entry['data']
                else:
                    # Eliminar archivo expirado
                    cache_file.unlink()
                    
            except Exception as e:
                logger.warning(f"Error reading cache file {cache_file}: {e}")
        
        self.stats['misses'] += 1
        logger.debug(f"Cache miss: {key}")
        return default
    
    async def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """Guardar valor en caché (memoria y disco)"""
        
        ttl = ttl or self._get_ttl_for_key(key)
        cache_entry = {
            'data': data,
            'timestamp': time.time(),
            'ttl': ttl
        }
        
        # Guardar en memoria cache
        self.memory_cache[key] = cache_entry
        
        # Guardar en disco cache para datos persistentes
        ttl_config = None
        for pattern, config in self.ttl_config.items():
            if pattern in key:
                ttl_config = config
                break
        
        if ttl_config and ttl_config['priority'] == 'persistent':
            cache_file = self._get_cache_file(key)
            try:
                async with aiofiles.open(cache_file, 'w') as f:
                    await f.write(json.dumps(cache_entry, indent=2))
            except Exception as e:
                logger.warning(f"Error writing cache file {cache_file}: {e}")
        
        self.stats['sets'] += 1
        logger.debug(f"Cache set: {key}")
    
    async def delete(self, key: str) -> None:
        """Eliminar key del caché"""
        
        # Eliminar de memoria
        if key in self.memory_cache:
            del self.memory_cache[key]
        
        # Eliminar de disco
        cache_file = self._get_cache_file(key)
        if cache_file.exists():
            try:
                cache_file.unlink()
            except Exception as e:
                logger.warning(f"Error deleting cache file {cache_file}: {e}")
    
    async def clear_expired(self) -> int:
        """Limpiar entradas expiradas del caché"""
        
        cleared_count = 0
        
        # Limpiar memoria cache
        expired_keys = []
        for key, entry in self.memory_cache.items():
            ttl = self._get_ttl_for_key(key)
            if self._is_expired(entry, ttl):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.memory_cache[key]
            cleared_count += 1
        
        # Limpiar disco cache
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                async with aiofiles.open(cache_file, 'r') as f:
                    content = await f.read()
                    entry = json.loads(content)
                
                # Extraer key del filename
                key = cache_file.stem.replace('_', '/')
                ttl = self._get_ttl_for_key(key)
                
                if self._is_expired(entry, ttl):
                    cache_file.unlink()
                    cleared_count += 1
                    
            except Exception as e:
                logger.warning(f"Error checking cache file {cache_file}: {e}")
                try:
                    cache_file.unlink()  # Eliminar archivos corruptos
                    cleared_count += 1
                except:
                    pass
        
        logger.info(f"Cleared {cleared_count} expired cache entries")
        return cleared_count
    
    async def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del caché"""
        
        total_requests = self.stats['memory_hits'] + self.stats['disk_hits'] + self.stats['misses']
        hit_rate = 0
        if total_requests > 0:
            hit_rate = ((self.stats['memory_hits'] + self.stats['disk_hits']) / total_requests) * 100
        
        return {
            'memory_hits': self.stats['memory_hits'],
            'disk_hits': self.stats['disk_hits'],
            'misses': self.stats['misses'],
            'sets': self.stats['sets'],
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2),
            'memory_cache_size': len(self.memory_cache),
            'disk_cache_files': len(list(self.cache_dir.glob("*.json")))
        }
    
    async def preload_trabajadores(self, trabajador_ids: List[int], fetch_func) -> Dict[int, Any]:
        """Pre-cargar datos de trabajadores en caché"""
        
        results = {}
        missing_ids = []
        
        # Verificar qué trabajadores ya están en caché
        for worker_id in trabajador_ids:
            cache_key = f"trabajador_info_{worker_id}"
            cached_data = await self.get(cache_key)
            
            if cached_data and "error" not in cached_data:
                results[worker_id] = cached_data
            else:
                missing_ids.append(worker_id)
        
        # Obtener datos faltantes
        if missing_ids:
            logger.info(f"Fetching {len(missing_ids)} missing workers from API")
            fresh_data = await fetch_func(missing_ids)
            
            for worker_id, data in fresh_data.items():
                if "error" not in data:
                    cache_key = f"trabajador_info_{worker_id}"
                    await self.set(cache_key, data)
                    results[worker_id] = data
        
        logger.info(f"Preloaded {len(results)} trabajadores en caché")
        return results
    
    async def mark_fichaje_procesado(self, fichaje_id: str, tipo_ausencia: str = 'ausente') -> bool:
        """Marcar un fichaje como procesado para evitar duplicados
        
        Args:
            fichaje_id: ID único del fichaje
            tipo_ausencia: Tipo de ausencia ('ausente', 'parcial', 'tarde')
            
        Returns:
            True si se marcó correctamente, False si ya existía
        """
        try:
            cache_key = "ausencias_procesadas"
            ausencias_procesadas = await self.get(cache_key, {})
            
            # Usar una estructura anidada: {tipo_ausencia: {fichaje_id: timestamp}}
            if tipo_ausencia not in ausencias_procesadas:
                ausencias_procesadas[tipo_ausencia] = {}
            
            if fichaje_id in ausencias_procesadas[tipo_ausencia]:
                # Ya fue procesado
                return False
            
            # Marcar como procesado
            ausencias_procesadas[tipo_ausencia][fichaje_id] = datetime.now().isoformat()
            
            # Guardar con TTL de 24 horas para limpiar automáticamente
            await self.set(cache_key, ausencias_procesadas, ttl=24*3600)
            
            logger.info(f"📝 Fichaje {fichaje_id} marcado como procesado (tipo: {tipo_ausencia})")
            return True
            
        except Exception as e:
            logger.error(f"Error marcando fichaje {fichaje_id} como procesado: {e}")
            return False
    
    async def is_fichaje_procesado(self, fichaje_id: str, tipo_ausencia: str = 'ausente') -> bool:
        """Verificar si un fichaje ya fue procesado anteriormente
        
        Args:
            fichaje_id: ID único del fichaje
            tipo_ausencia: Tipo de ausencia a verificar
            
        Returns:
            True si ya fue procesado, False si no
        """
        try:
            cache_key = "ausencias_procesadas"
            ausencias_procesadas = await self.get(cache_key, {})
            
            if tipo_ausencia not in ausencias_procesadas:
                return False
                
            return fichaje_id in ausencias_procesadas[tipo_ausencia]
            
        except Exception as e:
            logger.error(f"Error verificando si fichaje {fichaje_id} fue procesado: {e}")
            return False
    
    async def get_fichajes_procesados_hoy(self) -> Dict[str, int]:
        """Obtener estadísticas de fichajes procesados hoy por tipo
        
        Returns:
            Dict con conteo de fichajes procesados por tipo
        """
        try:
            cache_key = "ausencias_procesadas"
            ausencias_procesadas = await self.get(cache_key, {})
            
            stats = {}
            hoy = datetime.now().strftime('%Y-%m-%d')
            
            for tipo_ausencia, fichajes in ausencias_procesadas.items():
                stats[tipo_ausencia] = 0
                for fichaje_id, timestamp in fichajes.items():
                    # Contar solo los procesados hoy
                    if timestamp.startswith(hoy):
                        stats[tipo_ausencia] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de fichajes procesados: {e}")
            return {}
    
    async def reset_fichajes_procesados_hoy(self, tipo_ausencia: str = "todos") -> bool:
        """Resetear fichajes procesados del día
        
        Args:
            tipo_ausencia: Tipo específico a resetear (None para todos)
            
        Returns:
            True si se reseteó correctamente
        """
        try:
            cache_key = "ausencias_procesadas"
            ausencias_procesadas = await self.get(cache_key, {})
            
            if tipo_ausencia:
                # Resetear solo un tipo específico
                if tipo_ausencia in ausencias_procesadas:
                    count = len(ausencias_procesadas[tipo_ausencia])
                    ausencias_procesadas[tipo_ausencia] = {}
                    logger.info(f"🔄 Reseteados {count} fichajes procesados del tipo: {tipo_ausencia}")
            else:
                # Resetear todos
                total_count = sum(len(fichajes) for fichajes in ausencias_procesadas.values())
                ausencias_procesadas = {}
                logger.info(f"🔄 Reseteados {total_count} fichajes procesados de todos los tipos")
            
            # Guardar cambios
            await self.set(cache_key, ausencias_procesadas, ttl=24*3600)
            return True
            
        except Exception as e:
            logger.error(f"Error reseteando fichajes procesados: {e}")
            return False
    
    async def get_lista_procesados_detalle(self, tipo_ausencia: str = "todos") -> Dict[str, Dict[str, str]]:
        """Obtener lista detallada de fichajes procesados
        
        Returns:
            Dict con {fichaje_id: timestamp} para cada tipo
        """
        try:
            cache_key = "ausencias_procesadas"
            ausencias_procesadas = await self.get(cache_key, {})
            
            if tipo_ausencia:
                return {tipo_ausencia: ausencias_procesadas.get(tipo_ausencia, {})}
            else:
                return ausencias_procesadas
                
        except Exception as e:
            logger.error(f"Error obteniendo lista detallada de procesados: {e}")
            return {}
    
    async def remove_fichaje_procesado(self, fichaje_id: str, tipo_ausencia: str = "sin_fichaje") -> bool:
        """Remover un fichaje específico de la lista de procesados
        
        Args:
            fichaje_id: ID del fichaje a remover
            tipo_ausencia: Tipo de ausencia
            
        Returns:
            True si se removió correctamente
        """
        try:
            cache_key = "ausencias_procesadas"
            ausencias_procesadas = await self.get(cache_key, {})
            
            if tipo_ausencia in ausencias_procesadas:
                if fichaje_id in ausencias_procesadas[tipo_ausencia]:
                    del ausencias_procesadas[tipo_ausencia][fichaje_id]
                    await self.set(cache_key, ausencias_procesadas, ttl=24*3600)
                    logger.info(f"🗑️ Fichaje {fichaje_id} removido de procesados (tipo: {tipo_ausencia})")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removiendo fichaje procesado {fichaje_id}: {e}")
            return False
    
    async def get_historial_estados_fichaje(self, fichaje_id: str) -> list:
        """Obtener historial de estados de un fichaje específico
        
        Args:
            fichaje_id: ID del fichaje
            
        Returns:
            Lista de estados ordenados cronológicamente
        """
        try:
            cache_key = "fichajes_historial_estados"
            historial = await self.get(cache_key, {})
            
            return historial.get(fichaje_id, [])
            
        except Exception as e:
            logger.error(f"Error obteniendo historial de estados para {fichaje_id}: {e}")
            return []
    
    async def add_estado_fichaje_historial(self, fichaje_id: str, tipo_estado: str, 
                                           timestamp: str, cambio_estado: bool = False) -> bool:
        """Añadir un estado al historial de un fichaje
        
        Args:
            fichaje_id: ID del fichaje
            tipo_estado: Tipo de estado (sin_fichaje, fichaje_parcial, completo)
            timestamp: Timestamp del cambio
            cambio_estado: True si hubo cambio de estado respecto al anterior
            
        Returns:
            True si se añadió correctamente
        """
        try:
            cache_key = "fichajes_historial_estados"
            historial = await self.get(cache_key, {})
            
            if fichaje_id not in historial:
                historial[fichaje_id] = []
            
            # Añadir nuevo estado
            historial[fichaje_id].append({
                'tipo': tipo_estado,
                'timestamp': timestamp,
                'cambio_estado': cambio_estado
            })
            
            # Mantener solo los últimos 10 estados para no crecer indefinidamente
            if len(historial[fichaje_id]) > 10:
                historial[fichaje_id] = historial[fichaje_id][-10:]
            
            await self.set(cache_key, historial, ttl=48*3600)  # 48 horas de retención
            
            if cambio_estado:
                logger.info(f"📊 Historial actualizado: {fichaje_id} → {tipo_estado} (CAMBIO DE ESTADO)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error añadiendo estado al historial para {fichaje_id}: {e}")
            return False
    
    async def get_webhooks_enviados_hoy(self, fecha_actual: str) -> set:
        """Obtener lista de fichajes ya notificados hoy
        
        Args:
            fecha_actual: Fecha en formato 'YYYY-MM-DD'
            
        Returns:
            Set con los fichaje_id ya notificados hoy
        """
        cache_key = f"webhooks_enviados_{fecha_actual}"
        notificados = await self.get(cache_key, set())
        return notificados
    
    async def marcar_webhook_enviado(self, fichaje_id: str, fecha_actual: str) -> bool:
        """Marcar un fichaje como notificado hoy
        
        Args:
            fichaje_id: ID del fichaje notificado
            fecha_actual: Fecha en formato 'YYYY-MM-DD'
            
        Returns:
            True si se guardó correctamente, False si no
        """
        try:
            cache_key = f"webhooks_enviados_{fecha_actual}"
            notificados = await self.get(cache_key, set())
            notificados.add(fichaje_id)
            await self.set(cache_key, notificados, ttl=24*3600)  # 24 horas
            return True
        except Exception as e:
            logger.error(f"Error marcando webhook como enviado: {e}")
            return False
    
    async def limpiar_notificaciones_antiguas(self, fecha_actual: str):
        """Limpiar notificaciones de días anteriores
        
        Args:
            fecha_actual: Fecha actual en formato 'YYYY-MM-DD'
        """
        try:
            # Listar todos los archivos de cache que empiecen con webhooks_enviados_
            cache_files = list(self.cache_dir.glob("webhooks_enviados_*.json"))
            
            for cache_file in cache_files:
                # Extraer fecha del nombre del archivo
                file_date = cache_file.stem.replace("webhooks_enviados_", "")
                
                # Si es una fecha anterior a hoy, eliminar el archivo
                if file_date and file_date != fecha_actual:
                    try:
                        cache_file.unlink()
                        logger.debug(f"Limpiado archivo de notificaciones: {file_date}")
                    except Exception as e:
                        logger.warning(f"Error limpiando archivo {file_date}: {e}")
            
        except Exception as e:
            logger.error(f"Error limpiando notificaciones antiguas: {e}")


# Cache manager global
cache_manager = CacheManager()