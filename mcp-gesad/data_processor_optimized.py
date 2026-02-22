import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from cache_manager import cache_manager
from gesad_client import gesad_client
from config import config
from webhook_manager import webhook_manager

logger = logging.getLogger(__name__)


class GESADOptimizedProcessor:
    """Procesador optimizado con cruce de datos y caché inteligente"""
    
    def __init__(self):
        self.tolerance_minutes = 20  # Tolerancia para detección de ausencias
        self.check_window_hours = None  # Se calculará dinámicamente según intervalo de verificación
    
    def _tiene_gps_entrada(self, fichaje: Dict[str, Any]) -> bool:
        """Verificar si el fichaje tiene datos GPS de entrada"""
        return bool(
            fichaje.get('Fichaje_Ent_Gps_Lat') is not None and 
            fichaje.get('Fichaje_Ent_Gps_Lon') is not None
        )
    
    def _tiene_qr_entrada(self, fichaje: Dict[str, Any]) -> bool:
        """Verificar si el fichaje se hizo con QR"""
        metodo = fichaje.get('Metodo_Fichaje_Ent')
        return metodo == "QR"  # Case-sensitive, solo valor exacto "QR"
    
    def _tiene_gps_salida(self, fichaje: Dict[str, Any]) -> bool:
        """Verificar si el fichaje tiene datos GPS de salida"""
        return bool(
            fichaje.get('Fichaje_Sal_Gps_Lat') is not None and 
            fichaje.get('Fichaje_Sal_Gps_Lon') is not None
        )
    
    def _tiene_qr_salida(self, fichaje: Dict[str, Any]) -> bool:
        """Verificar si el fichaje de salida se hizo con QR"""
        metodo = fichaje.get('Metodo_Fichaje_Salida')
        return metodo == "QR"
    
    def _calcular_distancia_gps(self, fichaje: Dict[str, Any], usuario: Dict[str, Any]) -> float:
        """Calcular distancia entre GPS del fichaje y domicilio del usuario (en metros)"""
        from math import radians, cos, sin, asin, sqrt
        
        fichaje_lat = float(fichaje.get('Fichaje_Ent_Gps_Lat', 0)) if fichaje.get('Fichaje_Ent_Gps_Lat') else 0
        fichaje_lon = float(fichaje.get('Fichaje_Ent_Gps_Lon', 0)) if fichaje.get('Fichaje_Ent_Gps_Lon') else 0
        usuario_lat = float(usuario.get('Gis_Latitud', 0)) if usuario.get('Gis_Latitud') else 0
        usuario_lon = float(usuario.get('Gis_Longitud', 0)) if usuario.get('Gis_Longitud') else 0
        
        if not fichaje_lat or not fichaje_lon or not usuario_lat or not usuario_lon:
            return None
        
        try:
            lat1, lon1, lat2, lon2 = map(radians, [fichaje_lat, fichaje_lon, usuario_lat, usuario_lon])
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            
            return c * 6371000  # Radio de la Tierra en metros
        except:
            return None
    
    def _verificar_presencia_domicilio(self, fichaje: Dict[str, Any], usuario: Dict[str, Any]) -> Dict[str, Any]:
        """Verificar si el trabajador está en el domicilio del usuario"""
        
        distancia = self._calcular_distancia_gps(fichaje, usuario)
        dentro_rango = False
        distancia_metros = None
        
        if distancia is not None:
            dentro_rango = distancia <= config.UMBRAL_DISTANCIA_UBICACION
            distancia_metros = round(distancia, 2)
        
        return {
            'distancia_metros': distancia_metros,
            'dentro_rango': dentro_rango,
            'umbral_configurado': config.UMBRAL_DISTANCIA_UBICACION
        }
    
    def _verificar_ubicacion_gps(self, fichaje: Dict[str, Any], usuario: Dict[str, Any]) -> Dict[str, Any]:
        """Verificar si la ubicación GPS del fichaje está dentro del rango del domicilio (Supuesto 2)
        
        EXCLUYE servicios de acompañamiento (Servicio_Origen == "BASE")
        
        Returns:
            Dict con: tiene_gps, distancia, dentro_rango, requiere_alerta, motivo
        """
        
        # VERIFICAR SI ES SERVICIO DE ACOMPAÑAMIENTO - EXCLUIR VERIFICACIÓN
        servicio_origen = fichaje.get('Servicio_Origen', '')
        es_acompanamiento = servicio_origen == config.SERVICIO_ACOMPANAMIENTO
        
        if es_acompanamiento:
            return {
                'tiene_gps': False,
                'distancia_metros': None,
                'dentro_rango': None,
                'requiere_alerta': False,
                'motivo': f'Servicio de acompañamiento ({config.SERVICIO_ACOMPANAMIENTO}) - Verificación excluida',
                'servicio_origen': servicio_origen
            }
        
        # Verificar si el fichaje tiene GPS de entrada
        tiene_gps = self._tiene_gps_entrada(fichaje)
        
        if not tiene_gps:
            return {
                'tiene_gps': False,
                'distancia_metros': None,
                'dentro_rango': False,
                'requiere_alerta': False,
                'motivo': 'Sin datos GPS',
                'servicio_origen': servicio_origen
            }
        
        # Calcular distancia
        distancia = self._calcular_distancia_gps(fichaje, usuario)
        
        # Si no hay distancia válida, no generar alerta
        if distancia is None:
            return {
                'tiene_gps': True,
                'distancia_metros': None,
                'dentro_rango': None,
                'requiere_alerta': False,
                'umbral_configurado': config.UMBRAL_DISTANCIA_UBICACION,
                'motivo': 'No se pudo calcular distancia (GPS inválido)',
                'servicio_origen': servicio_origen
            }
        
        # Verificar si está dentro del rango permitido
        dentro_rango = distancia <= config.UMBRAL_DISTANCIA_UBICACION
        requiere_alerta = not dentro_rango
        
        return {
            'tiene_gps': True,
            'distancia_metros': round(distancia, 2),
            'dentro_rango': dentro_rango,
            'requiere_alerta': requiere_alerta,
            'umbral_configurado': config.UMBRAL_DISTANCIA_UBICACION,
            'motivo': 'ubicacion_fuera_rango' if requiere_alerta else 'ubicacion_valida',
            'servicio_origen': servicio_origen
        }
    
    def _parsear_hora_prevista(self, hora_prevista: str, timestamp_actual: datetime) -> Optional[datetime]:
        """Parsear hora prevista y ajustarla a la fecha actual"""
        try:
            hora_prevista_str = str(hora_prevista)
            hora_prevista_dt = datetime.fromisoformat(
                hora_prevista_str.replace('Z', '+00:00') if 'Z' in hora_prevista_str else hora_prevista_str
            )
            
            hora_prevista_dt = hora_prevista_dt.replace(
                year=timestamp_actual.year,
                month=timestamp_actual.month,
                day=timestamp_actual.day
            )
            
            if hora_prevista_dt.tzinfo is None:
                hora_prevista_dt = config.TZ.localize(hora_prevista_dt)
                
            return hora_prevista_dt
        except Exception as e:
            logger.warning(f"Error parseando hora prevista: {e}")
            return None
    
    def filtrar_fichajes_por_periodo(self, fichajes: List[Dict[str, Any]], timestamp_actual: datetime) -> tuple:
        """Filtrar fichajes por el periodo actual basándose en la hora prevista de entrada
        
        La ventana es simétrica: desde (actual - intervalo/2) hasta (actual + intervalo/2)
        Esto permite detectar ausencias que ya pasaron su hora prevista
        
        Returns:
            tuple: (fichajes_filtrados, hora_limite_superior, hora_limite_inferior)
        """
        
        fichajes_filtrados = []
        
        if timestamp_actual.tzinfo is None:
            timestamp_actual = config.TZ.localize(timestamp_actual)
        
        check_interval_seconds = config.get_check_interval_seconds()
        half_interval = check_interval_seconds / 2
        hora_limite_superior = timestamp_actual + timedelta(seconds=half_interval)
        hora_limite_inferior = timestamp_actual - timedelta(seconds=half_interval)
        
        for fichaje in fichajes:
            if not isinstance(fichaje, dict):
                continue
            
            hora_prevista = fichaje.get('Hora_Ent_Prevista')
            
            if not hora_prevista or hora_prevista == '':
                continue
            
            try:
                hora_prevista_str = str(hora_prevista)
                
                if 'T' in hora_prevista_str:
                    hora_prevista_dt = datetime.fromisoformat(
                        hora_prevista_str.replace('Z', '+00:00') if 'Z' in hora_prevista_str else hora_prevista_str
                    )
                else:
                    continue
                
                hora_prevista_dt = hora_prevista_dt.replace(
                    year=timestamp_actual.year,
                    month=timestamp_actual.month,
                    day=timestamp_actual.day
                )
                
                if hora_prevista_dt.tzinfo is None:
                    hora_prevista_dt = config.TZ.localize(hora_prevista_dt)
                
                # Ventana simétrica: hora_prevista debe estar entre (actual - intervalo/2) y (actual + intervalo/2)
                if hora_limite_inferior <= hora_prevista_dt <= hora_limite_superior:
                    fichajes_filtrados.append(fichaje)
                    
            except Exception as e:
                logger.warning(f"Error parseando hora prevista para fichaje: {e}")
                continue
        
        minutos_ventana = check_interval_seconds / 60
        logger.info(f"🕐 Fichajes filtrados por periodo: {len(fichajes_filtrados)}/{len(fichajes)} (ventana: {hora_limite_inferior.strftime('%H:%M')} - {hora_limite_superior.strftime('%H:%M')} | {minutos_ventana:.0f} min)")
        
        return fichajes_filtrados, hora_limite_superior, hora_limite_inferior
    
    async def _asegurar_datos_precargados(self):
        """Asegurar que los datos de usuarios y trabajadores estén en caché"""
        
        usuarios_cache = await cache_manager.get("usuarios_lista_completa", [])
        trabajadores_cache = await cache_manager.get("trabajadores_lista_completa", [])
        
        # Si no hay datos, cargarlos usando paginación
        if len(usuarios_cache) < 100:
            logger.warning("⚠️  Datos de usuarios no encontrados en caché, precargando...")
            # Cargar con paginación
            todos_usuarios = []
            pagina = 1
            while True:
                usuarios_pagina = await gesad_client.get_usuarios_expedientes_pagina(pagina, 1000)
                if not usuarios_pagina or len(usuarios_pagina) == 0:
                    break
                todos_usuarios.extend(usuarios_pagina)
                logger.info(f"   📄 Página {pagina}: {len(usuarios_pagina)} usuarios")
                if len(usuarios_pagina) < 1000:
                    break
                pagina += 1
            
            if todos_usuarios:
                await cache_manager.set("usuarios_lista_completa", todos_usuarios, ttl=24*3600)
                logger.info(f"   ✅ {len(todos_usuarios)} usuarios guardados en caché")
            usuarios_cache = await cache_manager.get("usuarios_lista_completa", [])
        
        if len(trabajadores_cache) < 100:
            logger.warning("⚠️  Datos de trabajadores no encontrados en caché, precargando...")
            # Cargar con paginación
            todos_trabajadores = []
            pagina = 1
            while True:
                trabajadores_pagina = await gesad_client.get_trabajadores_expedientes_pagina(pagina, 1000)
                if not trabajadores_pagina or len(trabajadores_pagina) == 0:
                    break
                todos_trabajadores.extend(trabajadores_pagina)
                logger.info(f"   📄 Página {pagina}: {len(trabajadores_pagina)} trabajadores")
                if len(trabajadores_pagina) < 1000:
                    break
                pagina += 1
            
            if todos_trabajadores:
                await cache_manager.set("trabajadores_lista_completa", todos_trabajadores, ttl=24*3600)
                logger.info(f"   ✅ {len(todos_trabajadores)} trabajadores guardados en caché")
            trabajadores_cache = await cache_manager.get("trabajadores_lista_completa", [])
        
        logger.info(f"✅ Datos precargados: {len(usuarios_cache)} usuarios, {len(trabajadores_cache)} trabajadores")
    
    async def get_datos_cruzados(self, timestamp_actual: datetime) -> Dict[str, Any]:
        """Obtener datos cruzados: fichajes + usuarios + trabajadores cacheados"""
        
        try:
            # Asegurar que los datos maestros estén precargados
            await self._asegurar_datos_precargados()
            
            fecha_actual = timestamp_actual.strftime('%Y-%m-%d')
            
            # 1. Obtener fichajes del día (con cache)
            cache_key_fichajes = f"fichajes_hoy_{fecha_actual}"
            fichajes_hoy = await cache_manager.get(cache_key_fichajes)
            
            if not fichajes_hoy:
                logger.info("Obteniendo fichajes desde API...")
                
                # Convertir fecha a formato dd-MM-yyyy
                fecha_obj = datetime.strptime(fecha_actual, '%Y-%m-%d')
                fecha_inicio = (fecha_obj - timedelta(days=1)).strftime('%d-%m-%Y')  # Ayer
                fecha_fin = fecha_obj.strftime('%d-%m-%Y')  # Hoy
                
                api_result = await gesad_client.get_fichajes_rango(fecha_inicio, fecha_fin)
                
                if isinstance(api_result, list):
                    fichajes_hoy = api_result
                    await cache_manager.set(cache_key_fichajes, fichajes_hoy, ttl=300)  # 5 min
                elif "error" in api_result:
                    return {"error": f"Error obteniendo fichajes: {api_result['error']}"}
            
            # 2. Obtener usuarios cacheados
            usuarios_cache = await cache_manager.get("usuarios_lista_completa", [])
            usuarios_map = {}
            for usuario in usuarios_cache:
                if isinstance(usuario, dict) and usuario.get('Usuario_Id'):
                    usuarios_map[str(usuario['Usuario_Id'])] = usuario
            
            # 3. Obtener trabajadores cacheados
            trabajadores_cache = await cache_manager.get("trabajadores_lista_completa", [])
            trabajadores_map = {}
            for trabajador in trabajadores_cache:
                if isinstance(trabajador, dict) and trabajador.get('Trabajador_Id'):
                    trabajadores_map[str(trabajador['Trabajador_Id'])] = trabajador
            
            # 4. Filtrar fichajes por periodo actual
            fichajes_periodo_actual, hora_limite_superior, hora_limite_inferior = self.filtrar_fichajes_por_periodo(fichajes_hoy, timestamp_actual)
            
            # 4.5 Limpiar notificaciones antiguas y obtener lista de hoy
            fecha_actual_str = timestamp_actual.strftime('%Y-%m-%d')
            await cache_manager.limpiar_notificaciones_antiguas(fecha_actual_str)
            webhooks_enviados_hoy = await cache_manager.get_webhooks_enviados_hoy(fecha_actual_str)
            
            # 5. Cruzar datos y generar informes detallados
            informes_ausencias = []
            informes_parciales = []
            informes_adelantados = []
            informes_presentes = []
            informes_fichajes_manuales = []
            informes_retrasos_confirmados = []
            informes_salidas_adelantadas = []
            informes_salidas_tardes = []
            informes_fichajes_adelantados_validar = []
            informes_ubicaciones_fuera_rango = []
            
            for fichaje in fichajes_periodo_actual:
                # Validar que fichaje es un diccionario
                if not isinstance(fichaje, dict):
                    continue
                    
                trabajador_id = fichaje.get('Trabajador_Id')
                usuario_id = fichaje.get('Usuario_Id')
                
                if not trabajador_id:
                    continue  # Skip fichajes sin trabajador
                
                # Cruzar con datos de trabajador
                trabajador = trabajadores_map.get(str(trabajador_id), {})
                usuario = usuarios_map.get(str(usuario_id), {})
                
                # SUPUESTO 2: Verificar ubicación GPS del fichaje
                ubicacion_info = None
                hora_entrada = fichaje.get('Hora_Ent_Fichaje')
                
                if hora_entrada:
                    ubicacion_info = self._verificar_ubicacion_gps(fichaje, usuario)
                    
                    if ubicacion_info.get('requiere_alerta'):
                        logger.info(f"📍 ALERTA UBICACIÓN: {trabajador_id} a {ubicacion_info['distancia_metros']}m del domicilio (umbral: {ubicacion_info['umbral_configurado']}m)")
                
                # Analizar tipo de ausencia
                tipo_ausencia_actual = self.clasificar_tipo_ausencia(fichaje, timestamp_actual)
                
                # Obtener ID único del fichaje
                fichaje_id = fichaje.get('Codigo', '') or str(fichaje.get('Trabajador_Id', '')) + '_' + timestamp_actual.strftime('%Y-%m-%d')
                
                # Verificar estado previo en cache
                estados_previos = await cache_manager.get_historial_estados_fichaje(fichaje_id)
                estado_anterior = estados_previos[-1] if estados_previos else None
                
                # Determinar tipo_cache basado en estado actual
                if tipo_ausencia_actual == 'sin_fichaje':
                    tipo_cache_actual = 'sin_fichaje'
                elif tipo_ausencia_actual == 'fichaje_parcial':
                    tipo_cache_actual = 'fichaje_parcial'
                elif tipo_ausencia_actual == 'fichaje_adelantado':
                    tipo_cache_actual = 'fichaje_adelantado'
                else:
                    tipo_cache_actual = 'completo'
                
                # Lógica de procesamiento inteligente
                debe_procesar = False
                cambio_estado = False
                
                if tipo_ausencia_actual in ['sin_fichaje', 'fichaje_parcial', 'fichaje_adelantado']:
                    if not estado_anterior:
                        # Primera vez que se ve este fichaje
                        debe_procesar = True
                        logger.info(f"🆕 Fichaje {fichaje_id}: Primera detección ({tipo_ausencia_actual})")
                    elif estado_anterior['tipo'] == 'sin_fichaje' and tipo_ausencia_actual in ['fichaje_parcial', 'fichaje_adelantado']:
                        # ¡Cambio importante! Antes era ausencia, ahora tiene entrada (tarde o adelantada)
                        debe_procesar = True
                        cambio_estado = True
                        logger.info(f"🔄 Fichaje {fichaje_id}: CAMBIO DE ESTADO - De 'sin_fichaje' a '{tipo_ausencia_actual}'")
                        # Remover del estado anterior para poder reprocesar
                        await cache_manager.remove_fichaje_procesado(fichaje_id, 'sin_fichaje')
                    elif estado_anterior['tipo'] == tipo_cache_actual:
                        # Mismo estado, ya fue procesado
                        logger.info(f"⏭️ Fichaje {fichaje_id}: Ya procesado como {tipo_cache_actual}, omitiendo...")
                        continue
                    else:
                        # Otro cambio de estado o primera vez en este estado
                        debe_procesar = True
                
                if debe_procesar:
                    # Marcar con el estado actual
                    await cache_manager.mark_fichaje_procesado(fichaje_id, tipo_cache_actual)
                    
                    # Guardar historial de estados
                    await cache_manager.add_estado_fichaje_historial(
                        fichaje_id, 
                        tipo_cache_actual, 
                        timestamp_actual.isoformat(),
                        cambio_estado
                    )
                
                informe = {
                    'fichaje': fichaje,
                    'fichaje_id': fichaje_id,
                    'trabajador': trabajador,
                    'usuario': usuario,
                    'tipo_ausencia': tipo_ausencia_actual,
                    'detalles': self.generar_detalles_informe(fichaje, trabajador, usuario),
                    'procesado_timestamp': timestamp_actual.isoformat(),
                    'cambio_estado': cambio_estado,
                    'estado_anterior': estado_anterior['tipo'] if estado_anterior else None,
                    'ubicacion_info': ubicacion_info  # NUEVO: Información de ubicación GPS
                }
                
                # Clasificar por tipo
                if tipo_ausencia_actual == 'sin_fichaje':
                    informes_ausencias.append(informe)
                    
                    # Verificar si ya se envió webhook hoy
                    ya_notificado = fichaje_id in webhooks_enviados_hoy
                    
                    # Enviar webhook de ausencia (si no se envió hoy)
                    if config.is_webhook_event_enabled('ausencia') and not ya_notificado:
                        await webhook_manager.notificar_ausencia(
                            fichaje_id=fichaje_id,
                            trabajador=trabajador,
                            usuario=usuario,
                            hora_prevista=fichaje.get('Hora_Ent_Prevista', 'No especificada'),
                            hora_prevista_salida=fichaje.get('Hora_Sal_Prevista', 'No especificada'),
                            fichaje=fichaje
                        )
                        # Marcar como notificado
                        await cache_manager.marcar_webhook_enviado(fichaje_id, fecha_actual_str)
                        
                elif tipo_ausencia_actual == 'fichaje_manual_sin_gps_qr':
                    informes_fichajes_manuales.append(informe)
                    
                    ya_notificado = fichaje_id in webhooks_enviados_hoy
                    
                    if config.is_webhook_event_enabled('fichaje_manual') and not ya_notificado:
                        hora_fichaje = fichaje.get('Hora_Ent_Fichaje', 'No especificada')
                        await webhook_manager.notificar_fichaje_manual_sin_gps_qr(
                            fichaje_id=fichaje_id,
                            trabajador=trabajador,
                            usuario=usuario,
                            hora_fichaje=hora_fichaje,
                            fichaje=fichaje
                        )
                        await cache_manager.marcar_webhook_enviado(fichaje_id, fecha_actual_str)

                elif tipo_ausencia_actual == 'retraso_confirmado':
                    informes_retrasos_confirmados.append(informe)
                    
                    ya_notificado = fichaje_id in webhooks_enviados_hoy
                    
                    if config.is_webhook_event_enabled('retraso_confirmado') and not ya_notificado:
                        hora_prevista = fichaje.get('Hora_Ent_Prevista', 'No especificada')
                        hora_prevista_dt = self._parsear_hora_prevista(hora_prevista, timestamp_actual)
                        
                        if hora_prevista_dt:
                            minutos_retraso = int((timestamp_actual - hora_prevista_dt).total_seconds() / 60)
                        else:
                            minutos_retraso = config.UMBRAL_RETRASO_AUSENCIA
                        
                        await webhook_manager.notificar_retraso_confirmado(
                            fichaje_id=fichaje_id,
                            trabajador=trabajador,
                            usuario=usuario,
                            hora_prevista=hora_prevista,
                            minutos_retraso=minutos_retraso,
                            fichaje=fichaje
                        )
                        await cache_manager.marcar_webhook_enviado(fichaje_id, fecha_actual_str)

                elif tipo_ausencia_actual == 'salida_adelantada':
                    informes_salidas_adelantadas.append(informe)
                    
                    ya_notificado = fichaje_id in webhooks_enviados_hoy
                    
                    if config.is_webhook_event_enabled('salida_adelantada') and not ya_notificado:
                        hora_prevista_fin = fichaje.get('Hora_Sal_Prevista', 'No especificada')
                        hora_real_salida = fichaje.get('Hora_Sal_Fichaje', 'No especificada')
                        
                        try:
                            if hora_prevista_fin:
                                hora_prevista_str = str(hora_prevista_fin)
                                hora_prevista_dt = datetime.fromisoformat(hora_prevista_str.replace('Z', '+00:00') if 'Z' in hora_prevista_str else hora_prevista_str)
                                hora_salida_str = str(hora_real_salida)
                                hora_salida_dt = datetime.fromisoformat(hora_salida_str.replace('Z', '+00:00') if 'Z' in hora_salida_str else hora_salida_str)
                                minutos_antes = int((hora_prevista_dt - hora_salida_dt).total_seconds() / 60)
                            else:
                                minutos_antes = config.UMBRAL_SALIDA_ADELANTADA
                        except:
                            minutos_antes = config.UMBRAL_SALIDA_ADELANTADA
                        
                        await webhook_manager.notificar_salida_adelantada(
                            fichaje_id=fichaje_id,
                            trabajador=trabajador,
                            usuario=usuario,
                            hora_prevista_fin=hora_prevista_fin,
                            hora_real_salida=hora_real_salida,
                            minutos_antes=minutos_antes,
                            fichaje=fichaje
                        )
                        await cache_manager.marcar_webhook_enviado(fichaje_id, fecha_actual_str)

                elif tipo_ausencia_actual == 'salida_tarde':
                    informes_salidas_tardes.append(informe)
                    
                    ya_notificado = fichaje_id in webhooks_enviados_hoy
                    
                    if config.is_webhook_event_enabled('salida_tarde') and not ya_notificado:
                        hora_prevista_fin = fichaje.get('Hora_Sal_Prevista', 'No especificada')
                        hora_real_salida = fichaje.get('Hora_Sal_Fichaje', 'No especificada')
                        
                        try:
                            if hora_prevista_fin:
                                hora_prevista_str = str(hora_prevista_fin)
                                hora_prevista_dt = datetime.fromisoformat(hora_prevista_str.replace('Z', '+00:00') if 'Z' in hora_prevista_str else hora_prevista_str)
                                minutos_despues = int((timestamp_actual - hora_prevista_dt).total_seconds() / 60)
                            else:
                                minutos_despues = config.UMBRAL_SALIDA_TARDE
                        except:
                            minutos_despues = config.UMBRAL_SALIDA_TARDE
                        
                        await webhook_manager.notificar_salida_tarde(
                            fichaje_id=fichaje_id,
                            trabajador=trabajador,
                            usuario=usuario,
                            hora_prevista_fin=hora_prevista_fin,
                            hora_real_salida=hora_real_salida,
                            minutos_despues=minutos_despues,
                            fichaje=fichaje
                        )
                        await cache_manager.marcar_webhook_enviado(fichaje_id, fecha_actual_str)

                elif tipo_ausencia_actual == 'fichaje_adelantado':
                    informes_adelantados.append(informe)
                    
                    ya_notificado = fichaje_id in webhooks_enviados_hoy
                    
                    if config.is_webhook_event_enabled('fichaje_adelantado') and not ya_notificado:
                        hora_prevista = fichaje.get('Hora_Ent_Prevista', 'No especificada')
                        hora_entrada = fichaje.get('Hora_Ent_Fichaje', '')
                        
                        if hora_entrada and hora_prevista:
                            hora_prevista_dt = self._parsear_hora_prevista(hora_prevista, timestamp_actual)
                            
                            if hora_prevista_dt:
                                minutos_antes = int((hora_prevista_dt - timestamp_actual).total_seconds() / 60)
                            else:
                                minutos_antes = config.UMBRAL_LLEGADA_ADELANTADA
                            
                            ubicacion = self._verificar_presencia_domicilio(fichaje, usuario)
                            
                            await webhook_manager.notificar_fichaje_adelantado(
                                fichaje_id=fichaje_id,
                                trabajador=trabajador,
                                usuario=usuario,
                                hora_prevista=hora_prevista,
                                minutos_antes=minutos_antes,
                                tiene_gps=False,
                                tiene_qr=False,
                                ubicacion=ubicacion,
                                fichaje=fichaje
                            )
                            await cache_manager.marcar_webhook_enviado(fichaje_id, fecha_actual_str)
                
                elif tipo_ausencia_actual == 'fichaje_adelantado_validar':
                    informes_fichajes_adelantados_validar.append(informe)
                    
                    ya_notificado = fichaje_id in webhooks_enviados_hoy
                    
                    hora_prevista = fichaje.get('Hora_Ent_Prevista', 'No especificada')
                    
                    if hora_entrada and hora_prevista:
                        try:
                            h_real = datetime.fromisoformat(str(hora_entrada).replace('Z', '+00:00'))
                            h_prev = datetime.fromisoformat(str(hora_prevista).replace('Z', '+00:00'))
                            minutos_tarde = int((h_real - h_prev).total_seconds() / 60)
                            
                            if minutos_tarde > 0 and not ya_notificado:
                                await webhook_manager.notificar_llegada_tarde(
                                    fichaje_id=fichaje_id,
                                    trabajador=trabajador,
                                    hora_entrada=str(hora_entrada),
                                    hora_prevista=str(hora_prevista),
                                    minutos_tarde=minutos_tarde,
                                    usuario=usuario,
                                    fichaje=fichaje
                                )
                                await cache_manager.marcar_webhook_enviado(fichaje_id, fecha_actual_str)
                        except:
                            pass
                        
                elif tipo_ausencia_actual == 'fichaje_adelantado':
                    informes_adelantados.append(informe)
                    
                    # Enviar webhook de cambio de estado (si aplica)
                    if cambio_estado and config.is_webhook_event_enabled('cambio_estado'):
                        await webhook_manager.notificar_cambio_estado(
                            fichaje_id=fichaje_id,
                            estado_anterior=estado_anterior['tipo'] if estado_anterior else 'desconocido',
                            estado_nuevo='fichaje_adelantado',
                            trabajador=trabajador,
                            usuario=usuario
                        )
                        
                elif tipo_ausencia_actual == 'completo':
                    informes_presentes.append(informe)
                
                # SUPUESTO 2: Verificar ubicación GPS (independiente del tipo de ausencia)
                if ubicacion_info and ubicacion_info.get('requiere_alerta'):
                    informes_ubicaciones_fuera_rango.append(informe)
                    
                    ya_notificado = f"{fichaje_id}_ubicacion" in webhooks_enviados_hoy
                    
                    if config.is_webhook_event_enabled('ubicacion_fuera_rango') and not ya_notificado:
                        await webhook_manager.notificar_ubicacion_fuera_rango(
                            fichaje_id=fichaje_id,
                            trabajador=trabajador,
                            usuario=usuario,
                            ubicacion_info=ubicacion_info,
                            fichaje=fichaje
                        )
                        await cache_manager.marcar_webhook_enviado(f"{fichaje_id}_ubicacion", fecha_actual_str)
            
            # 6. Obtener estadísticas de fichajes procesados hoy
            stats_procesados_hoy = await cache_manager.get_fichajes_procesados_hoy()
            
            # 7. Generar resumen
            resumen = {
                'fecha': fecha_actual,
                'timestamp': timestamp_actual.isoformat(),
                'total_fichajes_dia': len(fichajes_hoy),
                'total_fichajes_periodo': len(fichajes_periodo_actual),
                'periodo_ventana': {
                    'inicio': hora_limite_inferior.strftime('%H:%M'),
                    'fin': hora_limite_superior.strftime('%H:%M')
                },
                'total_usuarios_cache': len(usuarios_map),
                'total_trabajadores_cache': len(trabajadores_map),
                'ausencias_detectadas': len(informes_ausencias),
                'fichajes_parciales': len(informes_parciales),
                'fichajes_adelantados': len(informes_adelantados),
                'fichajes_completos': len(informes_presentes),
                'fichajes_manuales_sin_gps_qr': len(informes_fichajes_manuales),
                'retrasos_confirmados': len(informes_retrasos_confirmados),
                'salidas_adelantadas': len(informes_salidas_adelantadas),
                'salidas_tardes': len(informes_salidas_tardes),
                'fichajes_adelantados_validar': len(informes_fichajes_adelantados_validar),
                'ubicaciones_fuera_rango': len(informes_ubicaciones_fuera_rango),
                'informes_ausencias': informes_ausencias,
                'informes_parciales': informes_parciales,
                'informes_adelantados': informes_adelantados,
                'informes_presentes': informes_presentes,
                'informes_fichajes_manuales': informes_fichajes_manuales,
                'informes_retrasos_confirmados': informes_retrasos_confirmados,
                'informes_salidas_adelantadas': informes_salidas_adelantadas,
                'informes_salidas_tardes': informes_salidas_tardes,
                'informes_fichajes_adelantados_validar': informes_fichajes_adelantados_validar,
                'informes_ubicaciones_fuera_rango': informes_ubicaciones_fuera_rango,
                'api_calls_today': gesad_client.get_usage_stats()['daily_calls'],
                'cache_hit_rate': (await cache_manager.get_stats()).get('hit_rate_percent', 0),
                'fichajes_procesados_hoy': stats_procesados_hoy,
                'nuevas_ausencias': max(0, len(informes_ausencias) - stats_procesados_hoy.get('sin_fichaje', 0)),
                'nuevos_parciales': max(0, len(informes_parciales) - stats_procesados_hoy.get('fichaje_parcial', 0)),
                'nuevos_adelantados': max(0, len(informes_adelantados) - stats_procesados_hoy.get('fichaje_adelantado', 0))
            }
            
            # Guardar resultado en cache (TTL más largo para datos cruzados)
            await cache_manager.set("datos_cruzados_resumen", resumen, ttl=600)  # 10 min
            
            # Calcular total de fichajes clasificados (excluyendo ubicaciones fuera rango que son alertas)
            total_clasificados = (
                len(informes_ausencias) +
                len(informes_parciales) +
                len(informes_adelantados) +
                len(informes_presentes) +
                len(informes_fichajes_manuales) +
                len(informes_retrasos_confirmados) +
                len(informes_salidas_adelantadas) +
                len(informes_salidas_tardes) +
                len(informes_fichajes_adelantados_validar)
            )
            
            logger.info(f"📊 Datos cruzados generados: {len(informes_ausencias)} ausencias, {len(informes_parciales)} parciales, {len(informes_adelantados)} adelantados, {len(informes_presentes)} completos")
            logger.info(f"   - Fichajes manuales: {len(informes_fichajes_manuales)}, Retrasos: {len(informes_retrasos_confirmados)}")
            logger.info(f"   - Salidas (adelantadas/tardes): {len(informes_salidas_adelantadas)}/{len(informes_salidas_tardes)}, Adelantados validar: {len(informes_fichajes_adelantados_validar)}")
            logger.info(f"   - Ubicaciones fuera rango: {len(informes_ubicaciones_fuera_rango)}")
            logger.info(f"✅ Total clasificados: {total_clasificados}/{len(fichajes_periodo_actual)}")
            
            return resumen
            
        except Exception as e:
            logger.error(f"Error generando datos cruzados: {e}")
            return {"error": f"Error en datos cruzados: {str(e)}", "timestamp": timestamp_actual.isoformat()}
    
    def clasificar_tipo_ausencia(self, fichaje: Dict[str, Any], timestamp_actual: datetime) -> str:
        """Clasificar tipo de ausencia según la situación del fichaje"""
        
        # Analizar fichajes de entrada y salida
        hora_entrada = fichaje.get('Hora_Ent_Fichaje')
        hora_salida = fichaje.get('Hora_Sal_Fichaje')
        hora_entrada_prevista = fichaje.get('Hora_Ent_Prevista')
        
        fichaje_id = fichaje.get('Codigo', '') or str(fichaje.get('Trabajador_Id', ''))
        logger.debug(f"🔍 Clasificando fichaje {fichaje_id}: entrada={hora_entrada}, salida={hora_salida}, prevista={hora_entrada_prevista}")
        
        # SUPUESTO 4: Si no tiene entrada ni salida, verificar si han pasado 20+ min
        if not hora_entrada and not hora_salida:
            logger.debug(f"  → Sin entrada ni salida")
            if hora_entrada_prevista:
                hora_prevista_dt = self._parsear_hora_prevista(hora_entrada_prevista, timestamp_actual)
                if hora_prevista_dt:
                    tiempo_transcurrido = (timestamp_actual - hora_prevista_dt).total_seconds() / 60
                    logger.debug(f"  → Tiempo transcurrido: {tiempo_transcurrido:.1f} min")
                
                    if tiempo_transcurrido >= config.UMBRAL_RETRASO_AUSENCIA:
                        logger.debug(f"  → Clasificado: retraso_confirmado")
                        return 'retraso_confirmado'
        
            logger.debug(f"  → Clasificado: sin_fichaje")
            return 'sin_fichaje'
        
        # Si tiene entrada, verificar condiciones
        if hora_entrada and hora_entrada_prevista:
            logger.debug(f"  → Tiene entrada y hora prevista")
            try:
                hora_actual = datetime.fromisoformat(
                    hora_entrada.replace('Z', '+00:00') if 'Z' in str(hora_entrada) else str(hora_entrada)
                )
                hora_prevista = datetime.fromisoformat(
                    hora_entrada_prevista.replace('Z', '+00:00') if 'Z' in str(hora_entrada_prevista) else str(hora_entrada_prevista)
                )
                
                diferencia_minutos = (hora_prevista - hora_actual).total_seconds() / 60
                logger.debug(f"  → Diferencia: {diferencia_minutos:.1f} min (positivo=adelantado, negativo=tarde)")
            
                # SUPUESTO 1: Llegada adelantada (+20 min antes)
                if diferencia_minutos >= 20:
                    tiene_gps = self._tiene_gps_entrada(fichaje)
                    tiene_qr = self._tiene_qr_entrada(fichaje)
                    logger.debug(f"  → GPS={tiene_gps}, QR={tiene_qr}")
                
                    if not tiene_gps and not tiene_qr:
                        logger.debug(f"  → Clasificado: fichaje_adelantado_validar")
                        return 'fichaje_adelantado_validar'
                
                    logger.debug(f"  → Clasificado: fichaje_adelantado")
                    return 'fichaje_adelantado'
            
                # Si llegó después de la hora prevista
                if diferencia_minutos < 0:
                    if not hora_salida:
                        logger.debug(f"  → Clasificado: fichaje_parcial (sin salida)")
                        return 'fichaje_parcial'
                    else:
                        logger.debug(f"  → Clasificado: completo")
                        return 'completo'
                else:
                    logger.debug(f"  → A tiempo (dentro de 20 min), continuando...")
                    
            except Exception as e:
                logger.warning(f"Error calculando diferencia de horas para fichaje {fichaje_id}: {e}")
        
        # SUPUESTO 3: Fichaje manual sin GPS/QR
        if hora_entrada:
            metodo_entrada = fichaje.get('Metodo_Fichaje_Ent')
            logger.debug(f"  → Método de entrada: {metodo_entrada}")
        
            if metodo_entrada == "MANUAL":
                tiene_gps = self._tiene_gps_entrada(fichaje)
                if not tiene_gps:
                    logger.debug(f"  → Clasificado: fichaje_manual_sin_gps_qr")
                    return 'fichaje_manual_sin_gps_qr'
        
        # SUPUESTOS 6 Y 7: Análisis de hora de salida
        if hora_salida:
            logger.debug(f"  → Tiene salida")
            hora_salida_prevista = fichaje.get('Hora_Sal_Prevista')
        
            if hora_salida_prevista:
                logger.debug(f"  → Tiene hora de salida prevista")
                try:
                    hora_prevista_str = str(hora_salida_prevista)
                    hora_prevista_dt = datetime.fromisoformat(
                        hora_prevista_str.replace('Z', '+00:00') if 'Z' in hora_prevista_str else hora_prevista_str
                    )
                
                    if hora_prevista_dt.tzinfo is None:
                        hora_prevista_dt = config.TZ.localize(hora_prevista_dt)
                
                    hora_salida_str = str(hora_salida)
                    hora_salida_dt = datetime.fromisoformat(
                        hora_salida_str.replace('Z', '+00:00') if 'Z' in hora_salida_str else hora_salida_str
                    )
                
                    if hora_salida_dt.tzinfo is None:
                        hora_salida_dt = config.TZ.localize(hora_salida_dt)
                
                    diferencia_minutos = (hora_prevista_dt - hora_salida_dt).total_seconds() / 60
                    logger.debug(f"  → Diferencia salida: {diferencia_minutos:.1f} min")
                
                    # SUPUESTO 6: Salida adelantada (10+ min antes)
                    if diferencia_minutos >= config.UMBRAL_SALIDA_ADELANTADA:
                        logger.debug(f"  → Clasificado: salida_adelantada")
                        return 'salida_adelantada'
                
                    # SUPUESTO 7: Salida tarde (10+ min después)
                    if diferencia_minutos < -config.UMBRAL_SALIDA_TARDE:
                        logger.debug(f"  → Clasificado: salida_tarde")
                        return 'salida_tarde'
                        
                except Exception as e:
                    logger.warning(f"Error calculando diferencia de salida para fichaje {fichaje_id}: {e}")
        
        # Clasificación estándar
        logger.debug(f"  → Clasificación estándar")
        if not hora_entrada and hora_salida:
            logger.debug(f"  → Clasificado: fichaje_parcial (sin entrada)")
            return 'fichaje_parcial'
        elif hora_entrada and not hora_salida:
            logger.debug(f"  → Clasificado: fichaje_parcial (sin salida)")
            return 'fichaje_parcial'
        else:
            logger.debug(f"  → Clasificado: completo (default)")
            return 'completo'
    
    def generar_detalles_informe(self, fichaje: Dict[str, Any], trabajador: Dict[str, Any], usuario: Dict[str, Any]) -> str:
        """Generar descripción detallada para informe de ausencia"""
        
        detalles = []
        
        # Información del trabajador
        if trabajador:
            detalles.append(f"👤 Trabajador: {trabajador.get('Nombre', 'N/A')} {trabajador.get('Apellidos', '')}")
            detalles.append(f"🏢 Departamento: {trabajador.get('Departamento', 'N/A')}")
            detalles.append(f"📞 Teléfono: {trabajador.get('Telefono1', 'N/A')}")
        
        # Información del usuario asignado
        if usuario:
            detalles.append(f"👤 Usuario asignado: {usuario.get('Nombre', 'N/A')} {usuario.get('Apellidos', '')}")
            detalles.append(f"📧 Email: {usuario.get('Email', 'N/A')}")
            detalles.append(f"💼 Coordinador: {usuario.get('Coordinador', 'N/A')}")
        
        # Detalles del fichaje
        hora_entrada = fichaje.get('Hora_Ent_Fichaje', 'N/A')
        hora_salida = fichaje.get('Hora_Sal_Fichaje', 'N/A')
        servicio_id = fichaje.get('Servicio_Id', 'N/A')
        servicio = fichaje.get('Servicio_Activo', 'N/A')
        
        detalles.append(f"🕐 Fichaje entrada: {hora_entrada}")
        detalles.append(f"🕐 Fichaje salida: {hora_salida}")
        detalles.append(f"🔧 Servicio: {servicio} (ID: {servicio_id})")
        
        # Duración del servicio
        duracion = fichaje.get('Servicio_Duracion_Min')
        if duracion and duracion > 0:
            detalles.append(f"⏱️ Duración: {duracion} minutos")
        
        return " | ".join(detalles)
    
    async def get_informes_ausencias(self, tipo: Optional[str] = None) -> Dict[str, Any]:
        """Obtener informes de ausencias filtrados por tipo"""
        
        resumen = await cache_manager.get("datos_cruzados_resumen")
        
        if not resumen or "error" in resumen:
            return {"error": "No hay datos de ausencias disponibles", "informes": []}
        
        informes = resumen.get('informes_ausencias', [])
        
        if tipo:
            informes = [inf for inf in informes if inf.get('tipo_ausencia') == tipo]
        
        return {
            "informes": informes,
            "total": len(informes),
            "timestamp": resumen.get('timestamp'),
            "tipo_filtro": tipo,
            "resumen_general": resumen
        }
    
    async def get_usuarios_por_fichaje_sin_entrada(self) -> List[Dict[str, Any]]:
        """Obtener lista de usuarios asociados a fichajes sin entrada"""
        
        informes = await self.get_informes_ausencias('sin_fichaje')
        usuarios_sin_entrada = []
        
        for informe in informes.get('informes', []):
            usuario = informe.get('usuario', {})
            if usuario and usuario not in usuarios_sin_entrada:
                usuarios_sin_entrada.append(usuario)
        
        return usuarios_sin_entrada
    
    async def get_resumen_usuarios_ausentes(self) -> Dict[str, Any]:
        """Generar resumen agrupado por usuarios con ausencias"""
        
        informes = await self.get_informes_ausencias()
        usuarios_con_ausencias = {}
        
        for informe in informes.get('informes', []):
            usuario = informe.get('usuario', {})
            usuario_id = usuario.get('Usuario_Id', 'Unknown')
            
            if usuario_id not in usuarios_con_ausencias:
                usuarios_con_ausencias[usuario_id] = {
                    'usuario': usuario,
                    'trabajador': informe.get('trabajador', {}),
                    'ausencias': [],
                    'detalles': []
                }
            
            usuarios_con_ausencias[usuario_id]['ausencias'].append(informe)
            usuarios_con_ausencias[usuario_id]['detalles'].append(informe['detalles'])
        
        return {
            'usuarios_con_ausencias': usuarios_con_ausencias,
            'total_usuarios_afectados': len(usuarios_con_ausencias),
            'total_ausencias': sum(len(ua['ausencias']) for ua in usuarios_con_ausencias.values()),
            'timestamp': informes.get('timestamp')
        }
    
    async def get_api_calls_hoy(self) -> int:
        """Obtener número de llamadas API hoy"""
        from gesad_client import gesad_client
        return gesad_client.get_usage_stats().get('daily_calls', 0)
    
    async def get_cache_hit_rate(self) -> float:
        """Obtener tasa de aciertos de caché"""
        stats = await cache_manager.get_stats()
        return stats.get('hit_rate_percent', 0.0)
    
    async def get_estadisticas_optimizacion(self) -> Dict[str, Any]:
        """Obtener estadísticas de la optimización de caché"""
        
        stats_cache = await cache_manager.get_stats()
        stats_api = await self.get_api_calls_hoy()
        
        # Estimar ahorro de llamadas API
        usuarios_cacheados = len(await cache_manager.get("usuarios_lista_completa", []))
        trabajadores_cacheados = len(await cache_manager.get("trabajadores_lista_completa", []))
        
        # Si no tuviéramos caché, haríamos llamadas adicionales
        llamadas_evitadas = usuarios_cacheados + trabajadores_cacheados
        limite_diario = config.DAILY_LIMIT
        porcentaje_uso = (stats_api / limite_diario) * 100 if limite_diario > 0 else 0
        
        return {
            'cache_stats': stats_cache,
            'api_calls_today': stats_api,
            'usuarios_cacheados': usuarios_cacheados,
            'trabajadores_cacheados': trabajadores_cacheados,
            'llamadas_evitadas': llamadas_evitadas,
            'porcentaje_uso_api': round(porcentaje_uso, 2),
            'ahorro_optimizacion': f"Evitadas {llamadas_evitadas} llamadas API gracias al caché",
            'eficiencia_cache': stats_cache.get('hit_rate_percent', 0)
        }
    
    async def process_monitoring_check(self) -> Dict[str, Any]:
        """Procesar una verificación completa de monitoreo (compatible con scheduler)"""
        
        timestamp_actual = config.get_local_time()
        
        try:
            # Obtener datos cruzados (procesa todos los fichajes)
            datos_cruzados = await self.get_datos_cruzados(timestamp_actual)
            
            if "error" in datos_cruzados:
                return {
                    "success": False,
                    "error": datos_cruzados["error"],
                    "timestamp": timestamp_actual.isoformat()
                }
            
            # Generar alertas basadas en los datos cruzados
            # Convertir informes a formato compatible con alert_manager
            resultados_para_alertas = []
            
            # Agregar ausencias
            for informe in datos_cruzados.get("informes_ausencias", []):
                resultados_para_alertas.append({
                    "trabajador_id": informe.get("fichaje", {}).get("Trabajador_Id"),
                    "nombre": informe.get("trabajador", {}).get("Nombre", "N/A"),
                    "departamento": informe.get("trabajador", {}).get("Departamento", "N/A"),
                    "estado": "ausente_no_detectado",
                    "hora_prevista": informe.get("fichaje", {}).get("Hora_Ent_Prevista"),
                    "mensaje": f"Trabajador sin fichaje de entrada",
                    "fichaje": informe.get("fichaje", {}),
                    "tipo_ausencia": "sin_fichaje"
                })
            
            # Agregar parciales (llegadas tarde)
            for informe in datos_cruzados.get("informes_parciales", []):
                resultados_para_alertas.append({
                    "trabajador_id": informe.get("fichaje", {}).get("Trabajador_Id"),
                    "nombre": informe.get("trabajador", {}).get("Nombre", "N/A"),
                    "departamento": informe.get("trabajador", {}).get("Departamento", "N/A"),
                    "estado": "llegada_tardia",
                    "hora_prevista": informe.get("fichaje", {}).get("Hora_Ent_Prevista"),
                    "mensaje": f"Llegada tarde detectada",
                    "fichaje": informe.get("fichaje", {}),
                    "tipo_ausencia": "fichaje_parcial"
                })
            
            # Generar alertas
            from alert_manager import alert_manager
            alertas = await alert_manager.procesar_alertas(resultados_para_alertas, timestamp_actual)
            
            # Preparar resultado compatible con el formato esperado
            resultado = {
                "success": True,
                "timestamp": timestamp_actual.isoformat(),
                "fecha": timestamp_actual.strftime('%Y-%m-%d'),
                "trabajadores_analizados": datos_cruzados.get("total_fichajes_periodo", 0),
                "total_fichajes_dia": datos_cruzados.get("total_fichajes_dia", 0),
                "periodo_ventana": datos_cruzados.get("periodo_ventana", {}),
                "ausencias_detectadas": datos_cruzados.get("ausencias_detectadas", 0),
                "fichajes_parciales": datos_cruzados.get("fichajes_parciales", 0),
                "fichajes_adelantados": datos_cruzados.get("fichajes_adelantados", 0),
                "fichajes_completos": datos_cruzados.get("fichajes_completos", 0),
                "fichajes_manuales_sin_gps_qr": datos_cruzados.get("fichajes_manuales_sin_gps_qr", 0),
                "retrasos_confirmados": datos_cruzados.get("retrasos_confirmados", 0),
                "salidas_adelantadas": datos_cruzados.get("salidas_adelantadas", 0),
                "salidas_tardes": datos_cruzados.get("salidas_tardes", 0),
                "fichajes_adelantados_validar": datos_cruzados.get("fichajes_adelantados_validar", 0),
                "ubicaciones_fuera_rango": datos_cruzados.get("ubicaciones_fuera_rango", 0),
                "resumen": {
                    "total": datos_cruzados.get("total_fichajes_periodo", 0),
                    "ausencias": datos_cruzados.get("ausencias_detectadas", 0),
                    "parciales": datos_cruzados.get("fichajes_parciales", 0),
                    "adelantados": datos_cruzados.get("fichajes_adelantados", 0),
                    "completos": datos_cruzados.get("fichajes_completos", 0),
                    "fichajes_manuales": datos_cruzados.get("fichajes_manuales_sin_gps_qr", 0),
                    "retrasos": datos_cruzados.get("retrasos_confirmados", 0),
                    "salidas_antes": datos_cruzados.get("salidas_adelantadas", 0),
                    "salidas_despues": datos_cruzados.get("salidas_tardes", 0),
                    "adelantados_validar": datos_cruzados.get("fichajes_adelantados_validar", 0),
                    "ubicaciones_fuera": datos_cruzados.get("ubicaciones_fuera_rango", 0)
                },
                "alertas": alertas,
                "api_calls_made": datos_cruzados.get("api_calls_today", 0),
                "cache_hit_rate": datos_cruzados.get("cache_hit_rate", 0)
            }
            
            logger.info(f"✅ Verificación completada: {resultado['trabajadores_analizados']} fichajes, {len(alertas)} alertas")
            
            return resultado
            
        except Exception as e:
            logger.error(f"Error en process_monitoring_check: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": timestamp_actual.isoformat()
            }


# Procesador optimizado global
gesad_optimized_processor = GESADOptimizedProcessor()