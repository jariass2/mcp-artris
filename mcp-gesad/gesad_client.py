import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import httpx
from config import config

logger = logging.getLogger(__name__)


class GESADClient:
    """Cliente HTTP optimizado para API GESAD"""
    
    def __init__(self):
        self.base_url = config.BASE_URL
        self.conex_name = config.CONEX_NAME
        self.auth_code = config.AUTH_CODE
        self.basic_auth = config.BASIC_AUTH
        self.api_code = config.API_CODE
        self.session_id = config.SESSION_ID
        self.timeout = config.REQUEST_TIMEOUT
        self.retry_attempts = config.RETRY_ATTEMPTS
        self.endpoints = config.get_endpoints()
        
        # Estadísticas de uso
        self.daily_calls = 0
        self.last_reset = datetime.now().date()
        
    def _get_headers(self) -> Dict[str, str]:
        """Obtener headers para requests con autenticación correcta"""
        return {
            'accept': 'text/plain',
            'Authorization': f'Basic {self.basic_auth}',
            'api_Code': self.api_code,
            'conex_Name': self.conex_name,
            'User-Agent': f'MCP-GESAD-Server/1.0 ({self.conex_name})'
        }
    
    async def _check_daily_limit(self) -> bool:
        """Verificar límite diario de llamadas"""
        today = datetime.now().date()
        
        # Resetear contador cada día
        if today != self.last_reset:
            self.daily_calls = 0
            self.last_reset = today
        
        if self.daily_calls >= config.DAILY_LIMIT:
            logger.warning(f"Límite diario alcanzado: {self.daily_calls}/{config.DAILY_LIMIT}")
            return False
        
        return True
    
    async def _make_request_with_retry(self, method: str, url: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Realizar request con retry y rate limiting"""
        
        if not await self._check_daily_limit():
            return {"error": "Daily API limit reached"}
        
        for attempt in range(self.retry_attempts):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    self.daily_calls += 1
                    
                    if method == "GET":
                        response = await client.get(url, headers=self._get_headers(), **kwargs)
                    else:
                        raise ValueError(f"Método {method} no soportado")
                    
                    if response.status_code == 200:
                        # Parsear respuesta (text/plain a JSON si es necesario)
                        content = response.text.strip()
                        if content.startswith('{') or content.startswith('['):
                            return response.json()
                        else:
                            # Intentar parsear si es texto plano con estructura
                            return {"data": content, "format": "text"}
                    
                    else:
                        logger.warning(f"HTTP {response.status_code}: {response.text}")
                        if attempt == self.retry_attempts - 1:
                            return {"error": f"HTTP {response.status_code}: {response.text}"}
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        
            except httpx.TimeoutException:
                logger.error(f"Timeout en llamada a {url}")
                if attempt == self.retry_attempts - 1:
                    return {"error": "Request timeout"}
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error(f"Error en llamada a {url}: {str(e)}")
                if attempt == self.retry_attempts - 1:
                    return {"error": f"Request failed: {str(e)}"}
                await asyncio.sleep(2 ** attempt)
        
        return None
    
    async def get_fichajes_rango(self, fecha_inicio: str, fecha_fin: str) -> Dict[str, Any]:
        """Obtener fichajes en un rango de fechas
        
        Args:
            fecha_inicio: Fecha en formato dd-MM-yyyy
            fecha_fin: Fecha en formato dd-MM-yyyy
        """
        
        url = f"{self.base_url}{self.endpoints['fichajes']}"
        params = {
            'numero_Pagina': 1,
            'registros_Pagina': 1000,
            'fecha_Inicio': fecha_inicio,
            'fecha_Fin': fecha_fin
        }
        
        logger.info(f"Obteniendo fichajes del rango {fecha_inicio} a {fecha_fin}")
        result = await self._make_request_with_retry("GET", url, params=params)
        
        if result and "error" not in result:
            logger.info(f"Fichajes obtenidos exitosamente: {len(result) if isinstance(result, list) else 'N/A'}")
        
        return result or {"error": "Failed to get fichajes"}
    
    async def get_fichajes_dia(self, fecha: str) -> Dict[str, Any]:
        """Obtener fichajes del día específico
        
        Args:
            fecha: Fecha en formato dd-MM-yyyy
        """
        
        # Convertir fecha a objeto para manipular
        from datetime import datetime, timedelta
        fecha_obj = datetime.strptime(fecha, '%d-%m-%Y')
        
        # Para obtener fichajes del día, usar rango: día anterior al día siguiente
        # Esto evita el error de "fecha inicio debe ser anterior a fecha fin"
        fecha_inicio = (fecha_obj - timedelta(days=1)).strftime('%d-%m-%Y')  # Día anterior
        fecha_fin = (fecha_obj + timedelta(days=1)).strftime('%d-%m-%Y')      # Día siguiente
        
        url = f"{self.base_url}{self.endpoints['fichajes']}"
        params = {
            'numero_Pagina': 1,
            'registros_Pagina': 1000,
            'fecha_Inicio': fecha_inicio,  # Día anterior
            'fecha_Fin': fecha_fin         # Día siguiente
        }
        
        logger.info(f"Obteniendo fichajes del rango {fecha_inicio} a {fecha_fin} (para día {fecha})")
        result = await self._make_request_with_retry("GET", url, params=params)
        
        if result and "error" not in result:
            if isinstance(result, list):
                logger.info(f"Fichajes obtenidos exitosamente: {len(result)}")
            else:
                logger.info(f"Fichajes obtenidos exitosamente: {len(result.get('data', []))}")
        
        return result or {"error": "Failed to get fichajes"}
    
    async def get_trabajadores_expedientes(self, fecha_fin: str = "today") -> Dict[str, Any]:
        """Obtener lista completa de trabajadores
        
        Args:
            fecha_fin: Fecha final en formato dd-MM-yyyy (default: hoy)
        """
        
        if fecha_fin == "today":
            fecha_fin = config.get_local_time().strftime('%d-%m-%Y')
            
        url = f"{self.base_url}/Trabajadores/Expedientes/{self.session_id}"
        params = {
            'numero_Pagina': 1,
            'registros_Pagina': 1000,
            'fecha_Inicio': '01-01-2020',
            'fecha_Fin': fecha_fin
        }
        
        logger.info(f"Obteniendo trabajadores hasta {fecha_fin}")
        result = await self._make_request_with_retry("GET", url, params=params)
        
        if result and "error" not in result:
            logger.info(f"Trabajadores obtenidos exitosamente: {len(result) if isinstance(result, list) else 0}")
        
        return result or {"error": "Failed to get trabajadores"}
    
    async def get_usuarios_expedientes_pagina(self, pagina: int = 1, registros: int = 1000) -> List[Dict]:
        """Obtener usuarios de una página específica
        
        Args:
            pagina: Número de página (1-indexed)
            registros: Registros por página
        """
        
        fecha_fin = config.get_local_time().strftime('%d-%m-%Y')
        
        url = f"{self.base_url}/Usuarios/Expedientes/{self.session_id}"
        params = {
            'fecha_Inicio': '01-01-2024',
            'fecha_Fin': fecha_fin,
            'numero_Pagina': pagina,
            'registros_Pagina': registros
        }
        
        result = await self._make_request_with_retry("GET", url, params=params)
        
        if result and isinstance(result, list):
            return result
        return []
    
    async def get_trabajadores_expedientes_pagina(self, pagina: int = 1, registros: int = 1000) -> List[Dict]:
        """Obtener trabajadores de una página específica
        
        Args:
            pagina: Número de página (1-indexed)
            registros: Registros por página
        """
        
        url = f"{self.base_url}/Trabajadores/Expedientes/{self.session_id}"
        params = {
            'numero_Pagina': pagina,
            'registros_Pagina': registros
        }
        
        result = await self._make_request_with_retry("GET", url, params=params)
        
        if result and isinstance(result, list):
            return result
        return []

    async def get_usuarios_expedientes(self, fecha_fin: str = "today") -> Dict[str, Any]:
        """Obtener lista completa de usuarios
        
        Args:
            fecha_fin: Fecha final en formato dd-MM-yyyy (default: hoy)
        """
        
        if fecha_fin == "today":
            fecha_fin = config.get_local_time().strftime('%d-%m-%Y')
            
        url = f"{self.base_url}/Usuarios/Expedientes/{self.session_id}"
        params = {
            'fecha_Inicio': '01-01-2024',
            'fecha_Fin': fecha_fin,
            'numero_Pagina': 1,
            'registros_Pagina': 1000
        }
        
        logger.info(f"Obteniendo usuarios hasta {fecha_fin}")
        result = await self._make_request_with_retry("GET", url, params=params)
        
        if result and "error" not in result:
            logger.info(f"Usuarios obtenidos exitosamente: {len(result) if isinstance(result, list) else 0}")
        
        return result or {"error": "Failed to get usuarios"}
    
    async def test_connection(self) -> Dict[str, Any]:
        """Probar conexión con el endpoint de usuarios que sabemos funciona"""
        
        return await self.get_usuarios_expedientes()
    
    async def get_multiple_trabajadores(self, trabajador_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Obtener información de múltiples trabajadores en batch"""
        
        results = {}
        
        # Procesar en batches para optimizar llamadas
        for i in range(0, len(trabajador_ids), config.BATCH_SIZE):
            batch = trabajador_ids[i:i + config.BATCH_SIZE]
            
            # Ejecutar llamadas en paralelo
            # tasks = [self.get_trabajador_info(worker_id) for worker_id in batch]  # Comentado temporalmente
            tasks = []  # Método no disponible temporalmente
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for worker_id, result in zip(batch, batch_results):
                if isinstance(result, dict) and "error" not in result:
                    results[worker_id] = result
                else:
                    logger.warning(f"Error obteniendo trabajador {worker_id}: {result}")
                    results[worker_id] = {"error": str(result)}
        
        logger.info(f"Obtenidos {len(results)} de {len(trabajador_ids)} trabajadores")
        return results
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de uso de la API"""
        return {
            "daily_calls": self.daily_calls,
            "daily_limit": config.DAILY_LIMIT,
            "remaining_calls": max(0, config.DAILY_LIMIT - self.daily_calls),
            "usage_percentage": (self.daily_calls / config.DAILY_LIMIT) * 100,
            "last_reset": self.last_reset.isoformat()
        }


# Cliente global
gesad_client = GESADClient()