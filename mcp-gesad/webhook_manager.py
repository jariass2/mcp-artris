import logging
import asyncio
import httpx
from typing import Dict, Any, Optional
from datetime import datetime
from config import config

logger = logging.getLogger(__name__)


class WebhookManager:
    """Gestor de webhooks para enviar notificaciones a URLs externas"""
    
    def __init__(self):
        # Leer configuración directamente del sistema (si no está disponible, usar valores por defecto)
        import os
        from dotenv import load_dotenv
        
        # Cargar variables de entorno primero
        load_dotenv()
        
        self.webhook_url = os.getenv("GESAD_WEBHOOK_URL", "")
        self.webhook_enabled = os.getenv("GESAD_WEBHOOK_ENABLED", "false").lower() == "true"
        self.webhook_timeout = int(os.getenv("GESAD_WEBHOOK_TIMEOUT", "30"))
    
    def _formatear_timestamp(self) -> Dict[str, str]:
        """Formatear timestamp de manera legible para humanos"""
        now = datetime.now()
        
        # Días de la semana en español
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        
        dia_semana = dias_semana[now.weekday()]
        dia = now.day
        mes = meses[now.month - 1]
        anio = now.year
        hora = now.strftime('%H:%M')
        
        return {
            "iso": now.isoformat(),
            "legible": f"{dia_semana}, {dia} de {mes} de {anio} a las {hora}",
            "fecha": f"{dia:02d}/{now.month:02d}/{anio}",
            "hora": hora,
            "dia_semana": dia_semana
        }
    
    def _formatear_fecha_iso_a_legible(self, fecha_str) -> Optional[str]:
        """Transformar fecha ISO a formato legible español"""
        if not fecha_str:
            return None
        
        try:
            if isinstance(fecha_str, str):
                # Parsear fecha ISO
                if 'T' in fecha_str:
                    fecha_dt = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
                    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
                    return f"{fecha_dt.day} de {meses[fecha_dt.month - 1]} de {fecha_dt.year}"
            return fecha_str
        except:
            return fecha_str
    
    def _transformar_fechas_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transformar campos de fecha en un diccionario a formato legible"""
        if not isinstance(data, dict):
            return data
        
        # Campos de fecha comunes en la API de GESAD
        campos_fecha = [
            'Fecha_Nacimiento', 'Fecha_Antiguedad', 'Fecha_Alta', 'Fecha_Ultmodi',
            'Fecha_Inicio', 'Fecha_Baja_Definitiva', 'F_Ult_Factura_Privada',
            'Inicio_Baja', 'Hora_Ent_Prevista', 'Hora_Ent_Fichaje', 
            'Hora_Sal_Prevista', 'Hora_Sal_Fichaje'
        ]
        
        resultado = data.copy()
        for campo in campos_fecha:
            if campo in resultado:
                valor = resultado[campo]
                if valor:
                    resultado[f"{campo}_legible"] = self._formatear_fecha_iso_a_legible(valor)
        
        return resultado
    
    async def enviar_notificacion(self, tipo: str, datos: Dict[str, Any]) -> bool:
        """Enviar notificación webhook
        
        Args:
            tipo: Tipo de notificación (ausencia, parcial, cambio_estado, etc.)
            datos: Datos a enviar en el webhook
            
        Returns:
            True si se envió correctamente, False si no
        """
        if not self.webhook_enabled or not self.webhook_url:
            logger.debug("Webhook no configurado o deshabilitado")
            return False
        
        try:
            # Formatear timestamp legible
            timestamp_data = self._formatear_timestamp()
            
            # Extraer información del trabajador para el log
            trabajador_nombre = datos.get('trabajador', {}).get('nombre_completo', 'N/A')
            usuario = datos.get('usuario', {})
            
            # Intentar obtener nombre_completo del usuario
            if isinstance(usuario, dict):
                usuario_nombre = usuario.get('nombre_completo') or \
                                f"{usuario.get('Nombre', '')} {usuario.get('Apellidos', '')}".strip() or 'N/A'
            else:
                usuario_nombre = 'N/A'
            
            fichaje_id = datos.get('fichaje_id', 'N/A')
            
            # Transformar fechas a formato legible
            datos_transformados = datos.copy()
            if 'trabajador' in datos_transformados and isinstance(datos_transformados['trabajador'], dict):
                datos_transformados['trabajador'] = self._transformar_fechas_dict(datos_transformados['trabajador'])
            if 'usuario' in datos_transformados and isinstance(datos_transformados['usuario'], dict):
                datos_transformados['usuario'] = self._transformar_fechas_dict(datos_transformados['usuario'])
            
            # Preparar payload
            payload = {
                "timestamp": timestamp_data,
                "tipo": tipo,
                "sistema": "GESAD-MCP",
                "datos": datos_transformados
            }
            
            # Enviar webhook
            logger.info(f"📤 Enviando webhook: {tipo} - {trabajador_nombre} ({fichaje_id})")
            if usuario_nombre != 'N/A':
                logger.info(f"   👤 Usuario: {usuario_nombre}")
            else:
                logger.warning(f"   ⚠️  Usuario NO encontrado (objeto usuario vacío)")
            
            async with httpx.AsyncClient(timeout=self.webhook_timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "GESAD-MCP-Webhook/1.0"
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Webhook enviado correctamente: {tipo}")
                    return True
                else:
                    logger.error(f"❌ Webhook falló: HTTP {response.status_code} - {response.text}")
                    return False
                    
        except httpx.TimeoutException as e:
            logger.error(f"❌ Timeout: No se pudo conectar en {self.webhook_timeout}s")
            return False
        except Exception as e:
            logger.error(f"❌ Error enviando webhook: {e}")
            return False
    
    def _calcular_distancia(self, usuario: Dict, fichaje: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calcular distancia entre usuario y fichaje del trabajador
        
        Usa únicamente GPS del fichaje (Fichaje_Ent_Gps_Lat/Lon)
        Si no hay GPS del fichaje, la distancia es null
        """
        
        # Base: ubicación sin GPS disponible
        ubicacion = {
            "tiene_gps": False,
            "distancia_metros": None,
            "descripcion": "No hay coordenadas GPS disponibles",
            "gps_fichaje": {
                "latitud": None,
                "longitud": None
            },
            "gps_domicilio": {
                "latitud": usuario.get('Gis_Latitud') if usuario else None,
                "longitud": usuario.get('Gis_Longitud') if usuario else None
            }
        }
        
        if not fichaje or not usuario:
            logger.debug(f"Distancia no calculable: fichaje={bool(fichaje)}, usuario={bool(usuario)}")
            return ubicacion
        
        # Intentar obtener GPS del fichaje (prioridad: entrada, luego salida)
        fichaje_lat = fichaje.get('Fichaje_Ent_Gps_Lat') or fichaje.get('Fichaje_Sal_Gps_Lat')
        fichaje_lon = fichaje.get('Fichaje_Ent_Gps_Lon') or fichaje.get('Fichaje_Sal_Gps_Lon')
        
        # Buscar GPS del usuario
        usuario_lat = usuario.get('Gis_Latitud')
        usuario_lon = usuario.get('Gis_Longitud')
        
        # Actualizar datos GPS disponibles
        ubicacion["gps_fichaje"]["latitud"] = fichaje_lat
        ubicacion["gps_fichaje"]["longitud"] = fichaje_lon
        ubicacion["gps_domicilio"]["latitud"] = usuario_lat
        ubicacion["gps_domicilio"]["longitud"] = usuario_lon
        
        if not fichaje_lat or not fichaje_lon or not usuario_lat or not usuario_lon:
            razones_faltantes = []
            if not fichaje_lat or not fichaje_lon:
                razones_faltantes.append("sin GPS del fichaje")
            if not usuario_lat or not usuario_lon:
                razones_faltantes.append("sin GPS del domicilio")
            ubicacion["descripcion"] = f"No se puede calcular: {', '.join(razones_faltantes)}"
            logger.debug(f"Distancia no calculable: {ubicacion['descripcion']}")
            return ubicacion
        
        try:
            from math import radians, cos, sin, asin, sqrt
            
            fichaje_lat_float = float(fichaje_lat)
            fichaje_lon_float = float(fichaje_lon)
            usuario_lat_float = float(usuario_lat)
            usuario_lon_float = float(usuario_lon)
            
            lat1, lon1, lat2, lon2 = map(radians, [fichaje_lat_float, fichaje_lon_float, usuario_lat_float, usuario_lon_float])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            distancia = c * 6371000
            
            if distancia >= 1000:
                mensaje_distancia = f"{round(distancia/1000, 1)} km del domicilio"
            else:
                mensaje_distancia = f"{round(distancia, 1)} metros del domicilio"
            
            ubicacion = {
                "tiene_gps": True,
                "distancia_metros": round(distancia, 1),
                "descripcion": mensaje_distancia,
                "gps_fichaje": {
                    "latitud": str(fichaje_lat),
                    "longitud": str(fichaje_lon)
                },
                "gps_domicilio": {
                    "latitud": str(usuario_lat),
                    "longitud": str(usuario_lon)
                }
            }
        except Exception as e:
            logger.warning(f"Error calculando distancia: {e}")
            ubicacion["descripcion"] = f"Error al calcular distancia: {str(e)}"
        
        return ubicacion
    
    async def notificar_ausencia(self, fichaje_id: str, trabajador: Dict, 
                                  usuario: Dict, hora_prevista: str,
                                  hora_prevista_salida: str = 'No especificada',
                                  fichaje: Optional[Dict[str, Any]] = None) -> bool:
        """Notificar nueva ausencia detectada"""
        
        trabajador_nombre = f"{trabajador.get('Nombre', '')} {trabajador.get('Apellidos', '')}".strip()
        
        # Calcular distancia entre usuario y fichaje
        ubicacion = self._calcular_distancia(usuario, fichaje)
        
        # Obtener tipo de fichaje del API
        tipo_fichaje = fichaje.get('Metodo_Fichaje_Ent') or fichaje.get('Metodo_Fichaje_Salida') or 'NINGUNO'
        
        # Formatear horas si están en formato ISO
        hora_prevista_legible = hora_prevista
        if hora_prevista and 'T' in hora_prevista:
            try:
                hora_dt = datetime.fromisoformat(hora_prevista.replace('Z', '+00:00'))
                hora_prevista_legible = hora_dt.strftime('%H:%M')
            except:
                pass
        
        hora_prevista_salida_legible = hora_prevista_salida
        if hora_prevista_salida and 'T' in hora_prevista_salida:
            try:
                hora_dt = datetime.fromisoformat(hora_prevista_salida.replace('Z', '+00:00'))
                hora_prevista_salida_legible = hora_dt.strftime('%H:%M')
            except:
                pass
        
        # Obtener horas del fichaje si está disponible
        hora_fichaje_entrada = 'No registrada'
        hora_fichaje_salida = 'No registrada'
        if fichaje:
            if fichaje.get('Hora_Ent_Fichaje'):
                hora_fichaje_entrada = fichaje.get('Hora_Ent_Fichaje')
                if 'T' in hora_fichaje_entrada:
                    try:
                        hora_dt = datetime.fromisoformat(hora_fichaje_entrada.replace('Z', '+00:00'))
                        hora_fichaje_entrada = hora_dt.strftime('%H:%M')
                    except:
                        pass
            if fichaje.get('Hora_Sal_Fichaje'):
                hora_fichaje_salida = fichaje.get('Hora_Sal_Fichaje')
                if 'T' in hora_fichaje_salida:
                    try:
                        hora_dt = datetime.fromisoformat(hora_fichaje_salida.replace('Z', '+00:00'))
                        hora_fichaje_salida = hora_dt.strftime('%H:%M')
                    except:
                        pass
        
        return await self.enviar_notificacion("ausencia_detectada", {
            "fichaje_id": fichaje_id,
            "tipo_fichaje": tipo_fichaje,
            "trabajador": trabajador,
            "usuario": usuario,
            "gps_fichaje": {
                "entrada": {
                    "latitud": fichaje.get('Fichaje_Ent_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Ent_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None},
                "salida": {
                    "latitud": fichaje.get('Fichaje_Sal_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Sal_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None}
            },
            "horarios": {
                "hora_prevista_entrada": hora_prevista_legible,
                "hora_prevista_salida": hora_prevista_salida_legible,
                "hora_fichaje_entrada": hora_fichaje_entrada,
                "hora_fichaje_salida": hora_fichaje_salida
            },
            "ubicacion": ubicacion,
            "mensaje": f"🚨 AUSENCIA DETECTADA: {trabajador_nombre} no ha fichado entrada",
            "severidad": "alta",
            "accion_requerida": "Contactar al trabajador y/o usuario asignado"
        })
    
    async def notificar_cambio_estado(self, fichaje_id: str, estado_anterior: str,
                                       estado_nuevo: str, trabajador: Dict, usuario: Optional[Dict] = None) -> bool:
        """Notificar cambio de estado (ej: ausencia → parcial)"""
        
        trabajador_nombre = f"{trabajador.get('Nombre', '')} {trabajador.get('Apellidos', '')}".strip()
        
        datos = {
            "fichaje_id": fichaje_id,
            "trabajador": {
                "id": trabajador.get('Trabajador_Id', 'N/A'),
                "nombre_completo": trabajador_nombre,
                "telefono": trabajador.get('Telefono1') or trabajador.get('Telefono2') or 'No disponible'
            },
            "cambio": {
                "de": estado_anterior,
                "a": estado_nuevo
            },
            "mensaje": f"🔄 CAMBIO DE ESTADO: De '{estado_anterior}' a '{estado_nuevo}'",
            "severidad": "media",
            "accion_requerida": "Revisar situación del trabajador"
        }
        
        # Agregar datos del usuario si está disponible
        if usuario:
            usuario_nombre = f"{usuario.get('Nombre', '')} {usuario.get('Apellidos', '')}".strip()
            usuario_direccion = usuario.get('Direccion', 'No disponible')
            usuario_codigo_postal = usuario.get('Codigo_Postal') or usuario.get('CP') or 'No disponible'
            usuario_provincia = usuario.get('Provincia', 'No disponible')
            usuario_localidad = usuario.get('Localidad', 'No disponible')
            usuario_gis_latitud = usuario.get('Gis_Latitud') or usuario.get('Latitud') or 'No disponible'
            usuario_gis_longitud = usuario.get('Gis_Longitud') or usuario.get('Longitud') or 'No disponible'
            usuario_coordinador = usuario.get('Coordinador', 'N/A')
            
            datos["usuario"] = {
                "id": usuario.get('Usuario_Id', 'N/A'),
                "nombre_completo": usuario_nombre,
                "telefono": usuario.get('Telefono1') or usuario.get('Movil') or 'No disponible',
                "email": usuario.get('Email', 'No disponible'),
                "direccion": usuario_direccion,
                "codigo_postal": usuario_codigo_postal,
                "provincia": usuario_provincia,
                "localidad": usuario_localidad,
                "gis_latitud": usuario_gis_latitud,
                "gis_longitud": usuario_gis_longitud,
                "coordinador": usuario_coordinador
            }
        
        return await self.enviar_notificacion("cambio_estado", datos)
    
    async def notificar_llegada_tarde(self, fichaje_id: str, trabajador: Dict,
                                       usuario: Optional[Dict] = None, hora_entrada: str = '',
                                       hora_prevista: str = '', minutos_tarde: int = 0,
                                       fichaje: Optional[Dict[str, Any]] = None) -> bool:
        """Notificar llegada tarde"""
        
        trabajador_nombre = f"{trabajador.get('Nombre', '')} {trabajador.get('Apellidos', '')}".strip()
        
        # Calcular distancia entre usuario y fichaje
        if usuario:
            ubicacion = self._calcular_distancia(usuario, fichaje)
        else:
            ubicacion = {
                "tiene_gps": False,
                "descripcion": "No hay información de usuario"
            }
        
        # Obtener tipo de fichaje del API
        tipo_fichaje = fichaje.get('Metodo_Fichaje_Ent') or fichaje.get('Metodo_Fichaje_Salida') or 'NINGUNO'
        
        # Formatear horas si están en formato ISO
        hora_prevista_legible = hora_prevista
        if hora_prevista and 'T' in hora_prevista:
            try:
                hora_dt = datetime.fromisoformat(hora_prevista.replace('Z', '+00:00'))
                hora_prevista_legible = hora_dt.strftime('%H:%M')
            except:
                pass
        
        hora_fichaje_entrada_legible = hora_entrada
        if hora_entrada and 'T' in hora_entrada:
            try:
                hora_dt = datetime.fromisoformat(hora_entrada.replace('Z', '+00:00'))
                hora_fichaje_entrada_legible = hora_dt.strftime('%H:%M')
            except:
                pass
        
        # Obtener horas adicionales del fichaje
        hora_prevista_salida = 'No especificada'
        hora_fichaje_salida = 'No registrada'
        if fichaje:
            if fichaje.get('Hora_Sal_Prevista'):
                hora_prevista_salida = fichaje.get('Hora_Sal_Prevista')
                if 'T' in hora_prevista_salida:
                    try:
                        hora_dt = datetime.fromisoformat(hora_prevista_salida.replace('Z', '+00:00'))
                        hora_prevista_salida = hora_dt.strftime('%H:%M')
                    except:
                        pass
            if fichaje.get('Hora_Sal_Fichaje'):
                hora_fichaje_salida = fichaje.get('Hora_Sal_Fichaje')
                if 'T' in hora_fichaje_salida:
                    try:
                        hora_dt = datetime.fromisoformat(hora_fichaje_salida.replace('Z', '+00:00'))
                        hora_fichaje_salida = hora_dt.strftime('%H:%M')
                    except:
                        pass
        
        datos = {
            "fichaje_id": fichaje_id,
            "tipo_fichaje": tipo_fichaje,
            "trabajador": trabajador,
            "gps_fichaje": {
                "entrada": {
                    "latitud": fichaje.get('Fichaje_Ent_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Ent_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None},
                "salida": {
                    "latitud": fichaje.get('Fichaje_Sal_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Sal_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None}
            },
            "horarios": {
                "hora_prevista_entrada": hora_prevista_legible,
                "hora_prevista_salida": hora_prevista_salida,
                "hora_fichaje_entrada": hora_fichaje_entrada_legible,
                "hora_fichaje_salida": hora_fichaje_salida,
                "minutos_tarde": minutos_tarde
            },
            "ubicacion": ubicacion,
            "mensaje": f"⏰ LLEGADA TARDE: {trabajador_nombre} llegó {minutos_tarde} minutos tarde",
            "severidad": "media",
            "accion_requerida": "Registrar incidencia"
        }
        
        if usuario:
            datos["usuario"] = usuario
        
        return await self.enviar_notificacion("llegada_tarde", datos)
    
    async def notificar_resumen_diario(self, estadisticas: Dict[str, Any]) -> bool:
        """Enviar resumen diario al final del día"""
        
        datos = {
            "fecha": datetime.now().strftime('%Y-%m-%d'),
            "resumen": estadisticas,
            "mensaje": f"📊 RESUMEN DIARIO: {estadisticas.get('total_fichajes', 0)} fichajes procesados",
            "severidad": "info",
            "accion_requerida": None
        }
        
        return await self.enviar_notificacion("resumen_diario", datos)
    
    async def notificar_fichaje_adelantado(self, fichaje_id: str, trabajador: Dict,
                                       usuario: Dict, hora_prevista: str,
                                       minutos_antes: int, tiene_gps: bool = False,
                                       tiene_qr: bool = False,
                                       ubicacion: Optional[Dict[str, Any]] = None,
                                       fichaje: Optional[Dict[str, Any]] = None) -> bool:
        """Notificar fichaje adelantado (+20 min antes) con validación de GPS/QR"""
        
        trabajador_nombre = f"{trabajador.get('Nombre', '')} {trabajador.get('Apellidos', '')}".strip()
        
        motivo = "Con GPS y/o QR válido" if (tiene_gps or tiene_qr) else "SIN GPS ni QR"
        
        # Obtener tipo de fichaje del API
        tipo_fichaje = fichaje.get('Metodo_Fichaje_Ent') or fichaje.get('Metodo_Fichaje_Salida') or 'NINGUNO'
        
        # Calcular ubicación si no se proporcionó
        if not ubicacion:
            ubicacion = self._calcular_distancia(usuario, fichaje)
        
        # Formatear hora_prevista si está en formato ISO
        hora_prevista_legible = hora_prevista
        if hora_prevista and 'T' in hora_prevista:
            try:
                hora_dt = datetime.fromisoformat(hora_prevista.replace('Z', '+00:00'))
                hora_prevista_legible = hora_dt.strftime('%H:%M')
            except:
                pass
        
        # Obtener horas del fichaje
        hora_fichaje_entrada = 'No registrada'
        hora_prevista_salida = 'No especificada'
        hora_fichaje_salida = 'No registrada'
        if fichaje:
            if fichaje.get('Hora_Ent_Fichaje'):
                hora_fichaje_entrada = fichaje.get('Hora_Ent_Fichaje')
                if 'T' in hora_fichaje_entrada:
                    try:
                        hora_dt = datetime.fromisoformat(hora_fichaje_entrada.replace('Z', '+00:00'))
                        hora_fichaje_entrada = hora_dt.strftime('%H:%M')
                    except:
                        pass
            if fichaje.get('Hora_Sal_Prevista'):
                hora_prevista_salida = fichaje.get('Hora_Sal_Prevista')
                if 'T' in hora_prevista_salida:
                    try:
                        hora_dt = datetime.fromisoformat(hora_prevista_salida.replace('Z', '+00:00'))
                        hora_prevista_salida = hora_dt.strftime('%H:%M')
                    except:
                        pass
            if fichaje.get('Hora_Sal_Fichaje'):
                hora_fichaje_salida = fichaje.get('Hora_Sal_Fichaje')
                if 'T' in hora_fichaje_salida:
                    try:
                        hora_dt = datetime.fromisoformat(hora_fichaje_salida.replace('Z', '+00:00'))
                        hora_fichaje_salida = hora_dt.strftime('%H:%M')
                    except:
                        pass
        
        datos = {
            "fichaje_id": fichaje_id,
            "tipo_fichaje": tipo_fichaje,
            "trabajador": trabajador,
            "usuario": usuario,
            "gps_fichaje": {
                "entrada": {
                    "latitud": fichaje.get('Fichaje_Ent_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Ent_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None},
                "salida": {
                    "latitud": fichaje.get('Fichaje_Sal_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Sal_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None}
            },
            "horarios": {
                "hora_prevista_entrada": hora_prevista_legible,
                "hora_prevista_salida": hora_prevista_salida,
                "hora_fichaje_entrada": hora_fichaje_entrada,
                "hora_fichaje_salida": hora_fichaje_salida,
                "minutos_antes": minutos_antes
            },
            "validacion": {
                "tiene_gps": tiene_gps,
                "tiene_qr": tiene_qr,
                "motivo": motivo
            },
            "ubicacion": ubicacion,
            "mensaje": f"⏰ SUPUESTO 1 - FICHAJE ADELANTADO: {trabajador_nombre} fichó {minutos_antes} min antes",
            "severidad": "media" if (tiene_gps or tiene_qr) else "alta",
            "accion_requerida": "Validar fichaje con coordinación" if not (tiene_gps or tiene_qr) else None
        }
        
        return await self.enviar_notificacion("fichaje_adelantado", datos)
    
    async def notificar_fichaje_manual_sin_gps_qr(self, fichaje_id: str, trabajador: Dict,
                                                usuario: Dict, hora_fichaje: str,
                                                fichaje: Optional[Dict[str, Any]] = None) -> bool:
        """Notificar fichaje manual sin GPS/QR (Supuesto3)"""
        
        trabajador_nombre = f"{trabajador.get('Nombre', '')} {trabajador.get('Nombre', '')}".strip()
        
        # Calcular ubicación entre usuario y fichaje
        ubicacion = self._calcular_distancia(usuario, fichaje)
        
        # Obtener tipo de fichaje del API
        tipo_fichaje = fichaje.get('Metodo_Fichaje_Ent') or fichaje.get('Metodo_Fichaje_Salida') or 'NINGUNO'
        
        # Formatear hora_fichaje si está en formato ISO
        hora_fichaje_legible = hora_fichaje
        if hora_fichaje and 'T' in hora_fichaje:
            try:
                hora_dt = datetime.fromisoformat(hora_fichaje.replace('Z', '+00:00'))
                hora_fichaje_legible = hora_dt.strftime('%H:%M')
            except:
                pass
        
        # Obtener horas previstas del fichaje
        hora_prevista_entrada = 'No especificada'
        hora_prevista_salida = 'No especificada'
        hora_fichaje_salida = 'No registrada'
        if fichaje:
            if fichaje.get('Hora_Ent_Prevista'):
                hora_prevista_entrada = fichaje.get('Hora_Ent_Prevista')
                if 'T' in hora_prevista_entrada:
                    try:
                        hora_dt = datetime.fromisoformat(hora_prevista_entrada.replace('Z', '+00:00'))
                        hora_prevista_entrada = hora_dt.strftime('%H:%M')
                    except:
                        pass
            if fichaje.get('Hora_Sal_Prevista'):
                hora_prevista_salida = fichaje.get('Hora_Sal_Prevista')
                if 'T' in hora_prevista_salida:
                    try:
                        hora_dt = datetime.fromisoformat(hora_prevista_salida.replace('Z', '+00:00'))
                        hora_prevista_salida = hora_dt.strftime('%H:%M')
                    except:
                        pass
            if fichaje.get('Hora_Sal_Fichaje'):
                hora_fichaje_salida = fichaje.get('Hora_Sal_Fichaje')
                if 'T' in hora_fichaje_salida:
                    try:
                        hora_dt = datetime.fromisoformat(hora_fichaje_salida.replace('Z', '+00:00'))
                        hora_fichaje_salida = hora_dt.strftime('%H:%M')
                    except:
                        pass
        
        datos = {
            "fichaje_id": fichaje_id,
            "tipo_fichaje": tipo_fichaje,
            "trabajador": trabajador,
            "usuario": usuario,
            "gps_fichaje": {
                "entrada": {
                    "latitud": fichaje.get('Fichaje_Ent_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Ent_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None},
                "salida": {
                    "latitud": fichaje.get('Fichaje_Sal_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Sal_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None}
            },
            "horarios": {
                "hora_prevista_entrada": hora_prevista_entrada,
                "hora_prevista_salida": hora_prevista_salida,
                "hora_fichaje_entrada": hora_fichaje_legible,
                "hora_fichaje_salida": hora_fichaje_salida
            },
            "ubicacion": ubicacion,
            "mensaje": "⚠️ SUPUESTO 3 - FICHAJE MANUAL: Sin datos GPS ni código QR",
            "severidad": "alta",
            "accion_requerida": "Solicitar refichaje o validar con coordinador"
        }
        
        return await self.enviar_notificacion("fichaje_manual_sin_gps_qr", datos)
    
    async def notificar_retraso_confirmado(self, fichaje_id: str, trabajador: Dict,
                                       usuario: Dict, hora_prevista: str,
                                       minutos_retraso: int,
                                       fichaje: Optional[Dict[str, Any]] = None) -> bool:
        """Notificar retraso confirmado (+20 min después de hora prevista)"""
        
        trabajador_nombre = f"{trabajador.get('Nombre', '')} {trabajador.get('Apellidos', '')}".strip()
        
        # Calcular ubicación entre usuario y fichaje
        ubicacion = self._calcular_distancia(usuario, fichaje)
        
        # Obtener tipo de fichaje del API
        tipo_fichaje = fichaje.get('Metodo_Fichaje_Ent') or fichaje.get('Metodo_Fichaje_Salida') or 'NINGUNO'
        
        # Formatear hora_prevista si está en formato ISO
        hora_prevista_legible = hora_prevista
        if hora_prevista and 'T' in hora_prevista:
            try:
                hora_dt = datetime.fromisoformat(hora_prevista.replace('Z', '+00:00'))
                hora_prevista_legible = hora_dt.strftime('%H:%M')
            except:
                pass
        
        # Obtener horas del fichaje
        hora_fichaje_entrada = 'No registrada'
        hora_prevista_salida = 'No especificada'
        hora_fichaje_salida = 'No registrada'
        if fichaje:
            if fichaje.get('Hora_Ent_Fichaje'):
                hora_fichaje_entrada = fichaje.get('Hora_Ent_Fichaje')
                if 'T' in hora_fichaje_entrada:
                    try:
                        hora_dt = datetime.fromisoformat(hora_fichaje_entrada.replace('Z', '+00:00'))
                        hora_fichaje_entrada = hora_dt.strftime('%H:%M')
                    except:
                        pass
            if fichaje.get('Hora_Sal_Prevista'):
                hora_prevista_salida = fichaje.get('Hora_Sal_Prevista')
                if 'T' in hora_prevista_salida:
                    try:
                        hora_dt = datetime.fromisoformat(hora_prevista_salida.replace('Z', '+00:00'))
                        hora_prevista_salida = hora_dt.strftime('%H:%M')
                    except:
                        pass
            if fichaje.get('Hora_Sal_Fichaje'):
                hora_fichaje_salida = fichaje.get('Hora_Sal_Fichaje')
                if 'T' in hora_fichaje_salida:
                    try:
                        hora_dt = datetime.fromisoformat(hora_fichaje_salida.replace('Z', '+00:00'))
                        hora_fichaje_salida = hora_dt.strftime('%H:%M')
                    except:
                        pass
        
        datos = {
            "fichaje_id": fichaje_id,
            "tipo_fichaje": tipo_fichaje,
            "trabajador": trabajador,
            "usuario": usuario,
            "gps_fichaje": {
                "entrada": {
                    "latitud": fichaje.get('Fichaje_Ent_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Ent_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None},
                "salida": {
                    "latitud": fichaje.get('Fichaje_Sal_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Sal_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None}
            },
            "horarios": {
                "hora_prevista_entrada": hora_prevista_legible,
                "hora_prevista_salida": hora_prevista_salida,
                "hora_fichaje_entrada": hora_fichaje_entrada,
                "hora_fichaje_salida": hora_fichaje_salida,
                "minutos_retraso": minutos_retraso
            },
            "ubicacion": ubicacion,
            "mensaje": f"❌ SUPUESTO 4 - RETRASO CONFIRMADO: {trabajador_nombre} con {minutos_retraso} min de retraso",
            "severidad": "alta",
            "accion_recarada": "Contactar al trabajador para clasificar motivo"
        }
        
        return await self.enviar_notificacion("retraso_confirmado", datos)
    
    async def notificar_salida_adelantada(self, fichaje_id: str, trabajador: Dict,
                                       usuario: Dict, hora_prevista_fin: str,
                                       hora_real_salida: str, minutos_antes: int,
                                       fichaje: Optional[Dict[str, Any]] = None) -> bool:
        """Notificar salida adelantada (-10 min antes del fin)"""
        
        trabajador_nombre = f"{trabajador.get('Nombre', '')} {trabajador.get('Apellidos', '')}".strip()
        
        # Calcular ubicación entre usuario y fichaje
        ubicacion = self._calcular_distancia(usuario, fichaje)
        
        # Obtener tipo de fichaje del API
        tipo_fichaje = fichaje.get('Metodo_Fichaje_Ent') or fichaje.get('Metodo_Fichaje_Salida') or 'NINGUNO'
        
        # Formatear horas si están en formato ISO
        hora_prevista_fin_legible = hora_prevista_fin
        if hora_prevista_fin and 'T' in hora_prevista_fin:
            try:
                hora_dt = datetime.fromisoformat(hora_prevista_fin.replace('Z', '+00:00'))
                hora_prevista_fin_legible = hora_dt.strftime('%H:%M')
            except:
                pass
        
        hora_real_salida_legible = hora_real_salida
        if hora_real_salida and 'T' in hora_real_salida:
            try:
                hora_dt = datetime.fromisoformat(hora_real_salida.replace('Z', '+00:00'))
                hora_real_salida_legible = hora_dt.strftime('%H:%M')
            except:
                pass
        
        datos = {
            "fichaje_id": fichaje_id,
            "tipo_fichaje": tipo_fichaje,
            "trabajador": trabajador,
            "usuario": usuario,
            "gps_fichaje": {
                "entrada": {
                    "latitud": fichaje.get('Fichaje_Ent_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Ent_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None},
                "salida": {
                    "latitud": fichaje.get('Fichaje_Sal_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Sal_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None}
            },
            "horarios": {
                "hora_prevista_entrada": "No especificada",
                "hora_prevista_salida": hora_prevista_fin_legible,
                "hora_fichaje_entrada": "No registrada",
                "hora_fichaje_salida": hora_real_salida_legible,
                "minutos_antes": minutos_antes
            },
            "ubicacion": ubicacion,
            "mensaje": f"⏰ SUPUESTO 5 - SALIDA ADELANTADA: {trabajador_nombre} salió {minutos_antes} min antes",
            "severidad": "media",
            "accion_requerida": "Verificar finalización del servicio"
        }
        
        return await self.enviar_notificacion("salida_adelantada", datos)
    
    async def notificar_salida_tarde(self, fichaje_id: str, trabajador: Dict,
                                     usuario: Dict, hora_prevista_fin: str,
                                     hora_real_salida: str, 
                                     minutos_despues: int,
                                     fichaje: Optional[Dict[str, Any]] = None) -> bool:
        """Notificar salida tardía (+10 min después del fin)"""
        
        trabajador_nombre = f"{trabajador.get('Nombre', '')} {trabajador.get('Apellidos', '')}".strip()
        
        # Calcular ubicación entre usuario y fichaje
        ubicacion = self._calcular_distancia(usuario, fichaje)
        
        # Obtener tipo de fichaje del API
        tipo_fichaje = fichaje.get('Metodo_Fichaje_Ent') or fichaje.get('Metodo_Fichaje_Salida') or 'NINGUNO'
        
        # Formatear horas si están en formato ISO
        hora_prevista_fin_legible = hora_prevista_fin
        if hora_prevista_fin and 'T' in hora_prevista_fin:
            try:
                hora_dt = datetime.fromisoformat(hora_prevista_fin.replace('Z', '+00:00'))
                hora_prevista_fin_legible = hora_dt.strftime('%H:%M')
            except:
                pass
        
        hora_real_salida_legible = hora_real_salida
        if hora_real_salida and 'T' in hora_real_salida:
            try:
                hora_dt = datetime.fromisoformat(hora_real_salida.replace('Z', '+00:00'))
                hora_real_salida_legible = hora_dt.strftime('%H:%M')
            except:
                pass
        
        datos = {
            "fichaje_id": fichaje_id,
            "tipo_fichaje": tipo_fichaje,
            "trabajador": trabajador,
            "usuario": usuario,
            "gps_fichaje": {
                "entrada": {
                    "latitud": fichaje.get('Fichaje_Ent_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Ent_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None},
                "salida": {
                    "latitud": fichaje.get('Fichaje_Sal_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Sal_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None}
            },
            "horarios": {
                "hora_prevista_entrada": "No especificada",
                "hora_prevista_salida": hora_prevista_fin_legible,
                "hora_fichaje_entrada": "No registrada",
                "hora_fichaje_salida": hora_real_salida_legible,
                "minutos_despues": minutos_despues
            },
            "ubicacion": ubicacion,
            "mensaje": f"⏰ SUPUESTO 6 - SALIDA TARDE: {trabajador_nombre} salió {minutos_despues} min después",
            "severidad": "alta",
            "accion_requerida": "Llamada urgente a coordinación"
        }
        
        return await self.enviar_notificacion("salida_tarde", datos)
    
    async def notificar_ubicacion_fuera_rango(self, fichaje_id: str, trabajador: Dict,
                                          usuario: Dict, ubicacion_info: Dict[str, Any],
                                          fichaje: Optional[Dict[str, Any]] = None) -> bool:
        """Notificar ubicación GPS fuera de rango del domicilio (Supuesto 2)"""
        
        trabajador_nombre = f"{trabajador.get('Nombre', '')} {trabajador.get('Apellidos', '')}".strip()
        
        distancia = ubicacion_info.get('distancia_metros', 0)
        umbral = ubicacion_info.get('umbral_configurado', 50)
        servicio_origen = ubicacion_info.get('servicio_origen', 'N/A')
        es_acompanamiento = servicio_origen == "BASE"
        
        # Obtener tipo de fichaje del API
        tipo_fichaje = fichaje.get('Metodo_Fichaje_Ent') or fichaje.get('Metodo_Fichaje_Salida') or 'NINGUNO'
        
        if distancia >= 1000:
            mensaje_distancia = f"{round(distancia/1000, 1)} km del domicilio"
        else:
            mensaje_distancia = f"{round(distancia, 0)} metros del domicilio"
        
        # Construir ubicación con datos completos
        ubicacion_datos = {
            "distancia_metros": distancia,
            "umbral_configurado_metros": umbral,
            "descripcion": mensaje_distancia,
            "dentro_rango": ubicacion_info.get('dentro_rango', False),
            "gps_fichaje": {
                "latitud": ubicacion_info.get('gps_fichaje', {}).get('latitud', 'N/A'),
                "longitud": ubicacion_info.get('gps_fichaje', {}).get('longitud', 'N/A')
            },
            "gps_domicilio": {
                "latitud": ubicacion_info.get('gps_domicilio', {}).get('latitud', 'N/A'),
                "longitud": ubicacion_info.get('gps_domicilio', {}).get('longitud', 'N/A')
            }
        }
        
        # Obtener horas del fichaje
        hora_prevista_entrada = 'No especificada'
        hora_prevista_salida = 'No especificada'
        hora_fichaje_entrada = 'No registrada'
        hora_fichaje_salida = 'No registrada'
        if fichaje:
            if fichaje.get('Hora_Ent_Prevista'):
                hora_prevista_entrada = fichaje.get('Hora_Ent_Prevista')
                if 'T' in hora_prevista_entrada:
                    try:
                        hora_dt = datetime.fromisoformat(hora_prevista_entrada.replace('Z', '+00:00'))
                        hora_prevista_entrada = hora_dt.strftime('%H:%M')
                    except:
                        pass
            if fichaje.get('Hora_Sal_Prevista'):
                hora_prevista_salida = fichaje.get('Hora_Sal_Prevista')
                if 'T' in hora_prevista_salida:
                    try:
                        hora_dt = datetime.fromisoformat(hora_prevista_salida.replace('Z', '+00:00'))
                        hora_prevista_salida = hora_dt.strftime('%H:%M')
                    except:
                        pass
            if fichaje.get('Hora_Ent_Fichaje'):
                hora_fichaje_entrada = fichaje.get('Hora_Ent_Fichaje')
                if 'T' in hora_fichaje_entrada:
                    try:
                        hora_dt = datetime.fromisoformat(hora_fichaje_entrada.replace('Z', '+00:00'))
                        hora_fichaje_entrada = hora_dt.strftime('%H:%M')
                    except:
                        pass
            if fichaje.get('Hora_Sal_Fichaje'):
                hora_fichaje_salida = fichaje.get('Hora_Sal_Fichaje')
                if 'T' in hora_fichaje_salida:
                    try:
                        hora_dt = datetime.fromisoformat(hora_fichaje_salida.replace('Z', '+00:00'))
                        hora_fichaje_salida = hora_dt.strftime('%H:%M')
                    except:
                        pass
        
        datos = {
            "fichaje_id": fichaje_id,
            "tipo_fichaje": tipo_fichaje,
            "trabajador": trabajador,
            "usuario": usuario,
            "gps_fichaje": {
                "entrada": {
                    "latitud": fichaje.get('Fichaje_Ent_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Ent_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None},
                "salida": {
                    "latitud": fichaje.get('Fichaje_Sal_Gps_Lat'),
                    "longitud": fichaje.get('Fichaje_Sal_Gps_Lon')
                } if fichaje else {"latitud": None, "longitud": None}
            },
            "horarios": {
                "hora_prevista_entrada": hora_prevista_entrada,
                "hora_prevista_salida": hora_prevista_salida,
                "hora_fichaje_entrada": hora_fichaje_entrada,
                "hora_fichaje_salida": hora_fichaje_salida
            },
            "ubicacion": ubicacion_datos,
            "servicio": {
                "origen": servicio_origen,
                "descripcion": "Servicio de atención domiciliaria"
            },
            "mensaje": f"📍 SUPUESTO 2 - UBICACIÓN FUERA DE RANGO: {trabajador_nombre} está a {mensaje_distancia} del domicilio (umbral: {umbral}m)",
            "severidad": "media",
            "accion_requerida": "Contactar al trabajador para verificar su ubicación"
        }
        
        return await self.enviar_notificacion("ubicacion_fuera_rango", datos)


# Instancia global
webhook_manager = WebhookManager()