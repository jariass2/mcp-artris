import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from gesad_client import gesad_client
from cache_manager import cache_manager
from config import config

logger = logging.getLogger(__name__)


class AsistenciaProcessor:
    """Procesador principal de datos de asistencia GESAD"""
    
    def __init__(self):
        self.tolerance_minutes = 20  # Ventana de tolerancia para fichar
        self.check_window_hours = None  # Se calculará dinámicamente según intervalo de verificación

        # Datos de ejemplo de trabajadores (en producción vendrían de API/DB)
        # NOTA: Esto es código legacy - usar data_processor_optimized.py en producción
        self.trabajadores_ejemplo = {
            9434: {
                "id": 9434,
                "nombre": "Juan Pérez",
                "departamento": "Ventas",
                "hora_entrada": "09:00",
                "email": "juan.perez@empresa.com"
            },
            1234: {
                "id": 1234,
                "nombre": "María García",
                "departamento": "Administración",
                "hora_entrada": "08:30",
                "email": "maria.garcia@empresa.com"
            },
            5678: {
                "id": 5678,
                "nombre": "Carlos López",
                "departamento": "Ventas",
                "hora_entrada": "09:15",
                "email": "carlos.lopez@empresa.com"
            }
        }
    
    def filtrar_fichajes_por_periodo(self, fichajes: List[Dict[str, Any]], timestamp_actual: datetime) -> tuple:
        """Filtrar fichajes por el periodo actual basándose en la hora prevista de entrada
        
        La ventana se adapta dinámicamente al intervalo de verificación configurado
        
        Returns:
            tuple: (fichajes_filtrados, hora_limite_superior)
        """
        
        fichajes_filtrados = []
        
        if timestamp_actual.tzinfo is None:
            timestamp_actual = config.TZ.localize(timestamp_actual)
        
        check_interval_seconds = config.get_check_interval_seconds()
        hora_limite_superior = timestamp_actual + timedelta(seconds=check_interval_seconds)
        
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
                
                if timestamp_actual <= hora_prevista_dt <= hora_limite_superior:
                    fichajes_filtrados.append(fichaje)
                    
            except Exception as e:
                logger.warning(f"Error parseando hora prevista para fichaje: {e}")
                continue
        
        minutos_ventana = check_interval_seconds / 60
        logger.info(f"🕐 Fichajes filtrados por periodo: {len(fichajes_filtrados)}/{len(fichajes)} (ventana: {timestamp_actual.strftime('%H:%M')} - {hora_limite_superior.strftime('%H:%M')} | {minutos_ventana:.0f} min)")

        return fichajes_filtrados, hora_limite_superior
    
    def parse_hora(self, hora_str: str, current_date: Optional[datetime] = None) -> datetime:
        """Convertir string de hora a datetime del día actual"""
        if not current_date:
            current_date = datetime.now()
        
        try:
            hora, minuto = map(int, hora_str.split(':'))
            return current_date.replace(hour=hora, minute=minuto, second=0, microsecond=0)
        except Exception as e:
            logger.error(f"Error parseando hora '{hora_str}': {e}")
            return current_date
    
    def buscar_fichaje_entrada(self, fichajes: List[Dict[str, Any]], trabajador_id: int) -> Optional[Dict[str, Any]]:
        """Buscar primer fichaje de entrada del día para un trabajador"""
        
        for fichaje in fichajes:
            if fichaje.get('Trabajador_Id') == trabajador_id:
                # Revisar si hay fichaje de entrada
                if fichaje.get('Hora_Ent_Fichaje') or fichaje.get('Hora_Sal_Fichaje'):
                    return fichaje
        
        return None
    
    async def get_datos_cruzados(self, timestamp_actual: datetime) -> Dict[str, Any]:
        """Obtener datos cruzados: fichajes + usuarios + trabajadores cacheados"""
        
        from cache_manager import cache_manager
        
        try:
            fecha_actual = timestamp_actual.strftime('%Y-%m-%d')
            
            # 1. Obtener fichajes del día (con cache)
            cache_key_fichajes = f"fichajes_hoy_{fecha_actual}"
            fichajes_hoy = await cache_manager.get(cache_key_fichajes)
            
            if not fichajes_hoy:
                logger.info("Obteniendo fichajes desde API...")
                
                # Convertir fecha a formato dd-MM-yyyy
                fecha_obj = datetime.strptime(fecha_actual, '%Y-%m-%d')
                fecha_inicio = fecha_obj.strftime('%d-%m-%Y')
                fecha_fin = (fecha_obj + timedelta(days=1)).strftime('%d-%m-%Y')
                
                from gesad_client import gesad_client
                api_result = await gesad_client.get_fichajes_rango(fecha_inicio, fecha_fin)
                
                if isinstance(api_result, list):
                    fichajes_hoy = api_result
                    await cache_manager.set(cache_key_fichajes, fichajes_hoy, ttl=300)  # 5 min
                elif "error" in api_result:
                    return {"error": f"Error obteniendo fichajes: {api_result['error']}"}
            
            # 2. Obtener usuarios cacheados
            usuarios_cache = await cache_manager.get("usuarios_lista_completa", [])
            usuarios_map = {usuario.get('Usuario_Id', ''): usuario for usuario in usuarios_cache if usuario.get('Usuario_Id')}
            
            # 3. Obtener trabajadores cacheados
            trabajadores_cache = await cache_manager.get("trabajadores_lista_completa", [])
            trabajadores_map = {trabajador.get('Trabajador_Id', ''): trabajador for trabajador in trabajadores_cache if trabajador.get('Trabajador_Id')}
            
            # 4. Filtrar fichajes por periodo actual
            fichajes_periodo_actual, hora_limite_superior = self.filtrar_fichajes_por_periodo(fichajes_hoy, timestamp_actual)
            
            # 5. Cruzar datos y generar informes detallados
            informes_ausencias = []
            informes_parciales = []
            informes_presentes = []
            
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
                
                # Analizar tipo de ausencia
                informe = {
                    'fichaje': fichaje,
                    'trabajador': trabajador,
                    'usuario': usuario,
                    'tipo_ausencia': self.clasificar_tipo_ausencia(fichaje, timestamp_actual),
                    'detalles': self.generar_detalles_informe(fichaje, trabajador, usuario)
                }
                
                # Clasificar por tipo
                if informe['tipo_ausencia'] == 'sin_fichaje':
                    informes_ausencias.append(informe)
                elif informe['tipo_ausencia'] == 'fichaje_parcial':
                    informes_parciales.append(informe)
                elif informe['tipo_ausencia'] == 'completo':
                    informes_presentes.append(informe)
            
            # 6. Generar resumen
            resumen = {
                'fecha': fecha_actual,
                'timestamp': timestamp_actual.isoformat(),
                'total_fichajes_dia': len(fichajes_hoy),
                'total_fichajes_periodo': len(fichajes_periodo_actual),
                'periodo_ventana': {
                    'inicio': timestamp_actual.strftime('%H:%M'),
                    'fin': hora_limite_superior.strftime('%H:%M')
                },
                'total_usuarios_cache': len(usuarios_map),
                'total_trabajadores_cache': len(trabajadores_map),
                'ausencias_detectadas': len(informes_ausencias),
                'fichajes_parciales': len(informes_parciales),
                'fichajes_completos': len(informes_presentes),
                'informes_ausencias': informes_ausencias,
                'informes_parciales': informes_parciales,
                'informes_presentes': informes_presentes,
                'api_calls_today': gesad_client.get_usage_stats()['daily_calls']
            }
            
            # Guardar resultado en cache (TTL más largo para datos cruzados)
            await cache_manager.set("datos_cruzados_resumen", resumen, ttl=600)  # 10 min
            
            logger.info(f"📊 Datos cruzados generados: {len(informes_ausencias)} ausencias, {len(informes_parciales)} parciales, {len(informes_presentes)} completos")
            
            return resumen
            
        except Exception as e:
            logger.error(f"Error generando datos cruzados: {e}")
            return {"error": f"Error en datos cruzados: {str(e)}", "timestamp": timestamp_actual.isoformat()}
    
    def clasificar_tipo_ausencia(self, fichaje: Dict[str, Any], timestamp_actual: datetime) -> str:
        """Clasificar tipo de ausencia según la situación del fichaje"""
        
        # Analizar fichajes de entrada y salida
        hora_entrada = fichaje.get('Hora_Ent_Fichaje')
        hora_salida = fichaje.get('Hora_Sal_Fichaje')
        
        if not hora_entrada and not hora_salida:
            return 'sin_fichaje'  # No tiene ni entrada ni salida
        elif not hora_entrada and hora_salida:
            return 'fichaje_parcial'  # Solo tiene salida (sin entrada)
        elif hora_entrada and not hora_salida:
            return 'fichaje_parcial'  # Solo tiene entrada (sin salida)
        else:
            return 'completo'  # Tiene ambos fichajes
    
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
        """Analizar estado individual con lógica simple: ausente si no fichó o fichó 20+ min tarde"""
        
        trabajador_id = trabajador['id']
        hora_entrada_str = trabajador['hora_entrada']  # Ej: "06:45"
        
        # Parsear hora de entrada prevista
        try:
            hora_parts = hora_entrada_str.split(':')
            hora_entrada_prevista = timestamp_actual.replace(
                hour=int(hora_parts[0]), 
                minute=int(hora_parts[1]), 
                second=0, 
                microsecond=0
            )
            hora_limite = hora_entrada_prevista + timedelta(minutes=20)  # Tolerancia de 20 min
        except:
            # Error parseando hora, asumir ausente
            return {
                'trabajador_id': trabajador_id,
                'nombre': trabajador.get('nombre', 'N/A'),
                'departamento': trabajador.get('departamento', 'N/A'),
                'estado': 'ausente',
                'mensaje': f"❌ Ausente (hora entrada inválida: {hora_entrada_str})",
                'icono': "❌"
            }
        
        # Buscar si tiene fichaje de entrada hoy
        fichaje_entrada = self.buscar_fichaje_entrada(fichajes_hoy, trabajador_id)
        
        if not fichaje_entrada:
            # No tiene ningún fichaje de entrada hoy = AUSENTE
            return {
                'trabajador_id': trabajador_id,
                'nombre': trabajador.get('nombre', 'N/A'),
                'departamento': trabajador.get('departamento', 'N/A'),
                'estado': 'ausente',
                'mensaje': f"❌ Ausente sin fichaje (prevista: {hora_entrada_str})",
                'icono': "❌"
            }
        
        # Tiene fichaje, analizar si está a tiempo o tarde
        hora_entrada_str = fichaje_entrada.get('Hora_Ent_Fichaje', '')
        
        if not hora_entrada_str or hora_entrada_str == 'None':
            # Tiene fichaje pero sin hora de entrada = PARCIAL
            return {
                'trabajador_id': trabajador_id,
                'nombre': trabajador.get('nombre', 'N/A'),
                'departamento': trabajador.get('departamento', 'N/A'),
                'estado': 'parcial',
                'mensaje': f"📝 Fichaje sin hora de entrada registrada",
                'icono': "📝"
            }
        
        # Parsear hora de fichaje
        try:
            # Formato de API: "2026-02-12T06:43:00.000"
            if 'T' in hora_entrada_str:
                hora_entrada_real = datetime.fromisoformat(hora_entrada_str.replace('Z', '+00:00'))
            else:
                # Formato simple "HH:MM"
                hora_parts = hora_entrada_str.split(':')
                hora_entrada_real = timestamp_actual.replace(
                    hour=int(hora_parts[0]),
                    minute=int(hora_parts[1]),
                    second=0,
                    microsecond=0
                )
            
            # Comparar con hora límite
            if hora_entrada_real <= hora_limite:
                # A tiempo
                minutos_previstos = int((hora_limite - hora_entrada_real).total_seconds() / 60)
                return {
                    'trabajador_id': trabajador_id,
                    'nombre': trabajador.get('nombre', 'N/A'),
                    'departamento': trabajador.get('departamento', 'N/A'),
                    'estado': 'presente',
                    'mensaje': f"✅ Presente (fichó {minutos_previstos} min antes del límite)",
                    'icono': "✅"
                }
            else:
                # Llegada tardía = AUSENTE (según tu criterio: si excede 20 min es ausente)
                minutos_tarde = int((hora_entrada_real - hora_limite).total_seconds() / 60)
                return {
                    'trabajador_id': trabajador_id,
                    'nombre': trabajador.get('nombre', 'N/A'),
                    'departamento': trabajador.get('departamento', 'N/A'),
                    'estado': 'ausente_tarde',
                    'mensaje': f"❌ Ausente por tardanza ({minutos_tarde} min tarde, límite: {hora_limite.strftime('%H:%M')})",
                    'icono': "❌"
                }
                
        except Exception as e:
            # Error parseando hora del fichaje
            return {
                'trabajador_id': trabajador_id,
                'nombre': trabajador.get('nombre', 'N/A'),
                'departamento': trabajador.get('departamento', 'N/A'),
                'estado': 'error',
                'mensaje': f"⚠️ Error analizando fichaje: {str(e)}",
                'icono': "⚠️"
            }
    
    async def get_trabajadores_activos(self) -> List[Dict[str, Any]]:
        """Obtener lista de trabajadores activos con cache"""
        
        # En producción, esto vendría de la API de GESAD
        # Por ahora usamos datos de ejemplo con cache
        cache_key = "trabajadores_activos_lista"
        cached_data = await cache_manager.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Simular datos de trabajadores
        trabajadores = list(self.trabajadores_ejemplo.values())
        
        # Cache por 24 horas
        await cache_manager.set(cache_key, trabajadores, ttl=24 * 3600)
        
        return trabajadores
    
    async def process_monitoring_check(self) -> Dict[str, Any]:
        """Procesar una verificación completa de monitoreo"""
        
        timestamp_actual = datetime.now()
        fecha_actual = timestamp_actual.strftime('%Y-%m-%d')
        
        logger.info(f"🔍 Procesando verificación de asistencia para {fecha_actual}")
        
        try:
            # 1. Obtener fichajes del día (1 llamada API)
            cache_key_fichajes = f"fichajes_hoy_{fecha_actual}"
            fichajes_hoy = await cache_manager.get(cache_key_fichajes)
            
            if not fichajes_hoy:
                logger.info("Obteniendo fichajes desde API...")
                
                # Convertir fecha de YYYY-MM-DD a dd-MM-yyyy para API GESAD
                fecha_obj = datetime.strptime(fecha_actual, '%Y-%m-%d')
                fecha_fin = fecha_obj.strftime('%d-%m-%Y')  # Hoy
                
                # Para rango, usar día anterior como fecha inicio (ayer - hoy)
                from datetime import timedelta
                fecha_inicio = (fecha_obj - timedelta(days=1)).strftime('%d-%m-%Y')  # Ayer
                
                api_result = await gesad_client.get_fichajes_rango(fecha_inicio, fecha_fin)
                
                if isinstance(api_result, list):
                    # API devuelve lista directamente
                    fichajes_hoy = api_result
                elif "error" in api_result:
                    return {
                        "error": f"Error obteniendo fichajes: {api_result['error']}",
                        "timestamp": timestamp_actual.isoformat()
                    }
                else:
                    # API devuelve diccionario con 'data'
                    fichajes_hoy = api_result.get('data', [])
                
                # Cache por 5 minutos para datos del día
                await cache_manager.set(cache_key_fichajes, fichajes_hoy, ttl=300)
            else:
                logger.info(f"Usando fichajes cacheados: {len(fichajes_hoy)} registros")
            
            # 2. Obtener lista de trabajadores
            trabajadores = await self.get_trabajadores_activos()
            
            # 3. Analizar estado de cada trabajador
            resultados = []
            for trabajador in trabajadores:
                estado = self.analizar_trabajador_con_fichajes(trabajador, fichajes_hoy, timestamp_actual)
                resultados.append(estado)
            
            # 4. Generar resumen y estadísticas
            resumen = self.generar_resumen_simple(resultados)
            
            # 5. Generar alertas (ausencias y llegadas tardías)
            from alert_manager import alert_manager
            alertas = await alert_manager.procesar_alertas(resultados, timestamp_actual)
            
            # 6. Guardar resultado completo en cache
            monitoring_result = {
                'timestamp': timestamp_actual.isoformat(),
                'fecha': fecha_actual,
                'trabajadores_analizados': len(resultados),
                'resultados': resultados,
                'resumen': resumen,
                'alertas': alertas,
                'api_calls_made': gesad_client.get_usage_stats()['daily_calls']
            }
            
            # Cache por 20 minutos (intervalo de verificación)
            await cache_manager.set("monitoring_result", monitoring_result, ttl=1200)
            
            logger.info(f"✅ Verificación completada: {len(resultados)} trabajadores, {len(alertas)} alertas")
            
            return monitoring_result
            
        except Exception as e:
            logger.error(f"Error en procesamiento de monitoreo: {e}")
            return {
                "error": str(e),
                "timestamp": timestamp_actual.isoformat()
            }
    
    def generar_resumen_simple(self, resultados: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generar resumen estadístico de resultados con lógica simple"""
        
        if not resultados:
            return {
                'total': 0,
                'presentes': 0,
                'ausentes': 0,
                'ausentes_tarde': 0,
                'parciales': 0,
                'errores': 0
            }
        
        # Contar por estado simple
        counts = {}
        for resultado in resultados:
            estado = resultado.get('estado', 'desconocido')
            counts[estado] = counts.get(estado, 0) + 1
        
        # Agrupar por departamento
        por_departamento = {}
        for resultado in resultados:
            depto = resultado.get('departamento', 'No especificado')
            if depto not in por_departamento:
                por_departamento[depto] = {
                    'total': 0,
                    'presentes': 0,
                    'ausentes': 0,
                    'ausentes_tarde': 0,
                    'parciales': 0,
                    'errores': 0
                }
            
            por_departamento[depto]['total'] += 1
            estado_actual = resultado.get('estado', 'desconocido')
            por_departamento[depto][estado_actual] = por_departamento[depto].get(estado_actual, 0) + 1
        
        return {
            'total': len(resultados),
            'presentes': counts.get('presente', 0),
            'ausentes': counts.get('ausente', 0),
            'ausentes_tarde': counts.get('ausente_tarde', 0),
            'parciales': counts.get('parcial', 0),
            'errores': counts.get('error', 0),
            'por_departamento': por_departamento,
            'timestamp': datetime.now().isoformat()
        }
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Obtener datos actuales para dashboard"""
        
        # Intentar obtener último resultado de monitoreo
        monitoring_result = await cache_manager.get("monitoring_result")
        
        if not monitoring_result:
            return {
                "error": "No hay datos de monitoreo disponibles",
                "timestamp": datetime.now().isoformat()
            }
        
        # Añadir estado del sistema
        from scheduler import gesad_scheduler
        
        dashboard_data = {
            **monitoring_result,
            'sistema': {
                'activo': gesad_scheduler.is_active_time(),
                'scheduler_running': gesad_scheduler.running,
                'sleep_mode': gesad_scheduler.sleep_mode,
                'ultima_verificacion': gesad_scheduler.last_check_time.isoformat() if gesad_scheduler.last_check_time else None,
                'proxima_verificacion': (gesad_scheduler.last_check_time + timedelta(seconds=config.get_check_interval_seconds())).isoformat() if gesad_scheduler.last_check_time else None
            },
            'api_usage': gesad_client.get_usage_stats(),
            'cache_stats': await cache_manager.get_stats()
        }
        
        return dashboard_data
    
    def analizar_trabajador_con_fichajes(self, trabajador: Dict[str, Any], fichajes_hoy: List, timestamp_actual: datetime) -> Dict[str, Any]:
        """Analizar estado de un trabajador basado en sus fichajes del día"""
        
        try:
            trabajador_id = str(trabajador.get('Trabajador_Id', ''))
            
            # Buscar fichajes del trabajador
            fichajes_trabajador = []
            for fichaje in fichajes_hoy:
                if isinstance(fichaje, dict) and str(fichaje.get('Trabajador_Id', '')) == trabajador_id:
                    fichajes_trabajador.append(fichaje)
            
            # Clasificar estado
            if not fichajes_trabajador:
                return {
                    'trabajador_id': trabajador_id,
                    'nombre': trabajador.get('Nombre', 'N/A'),
                    'estado': 'ausente',
                    'fichajes': [],
                    'mensaje': 'Sin registros de fichaje hoy'
                }
            
            # Analizar fichajes encontrados
            estado_actual = 'presente'
            mensaje = 'Con fichajes registrados'
            
            for fichaje in fichajes_trabajador:
                hora_entrada = fichaje.get('Hora_Ent_Fichaje')
                hora_salida = fichaje.get('Hora_Sal_Fichaje')
                
                if not hora_entrada and not hora_salida:
                    estado_actual = 'ausente'
                    mensaje = 'Fichaje sin entrada ni salida'
                    break
                elif not hora_entrada:
                    estado_actual = 'parcial'
                    mensaje = 'Fichaje sin entrada'
                    break
            
            return {
                'trabajador_id': trabajador_id,
                'nombre': trabajador.get('Nombre', 'N/A'),
                'estado': estado_actual,
                'fichajes': fichajes_trabajador,
                'mensaje': mensaje,
                'timestamp': timestamp_actual.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analizando trabajador {trabajador.get('Trabajador_Id', 'N/A')}: {e}")
            return {
                'trabajador_id': trabajador.get('Trabajador_Id', 'N/A'),
                'nombre': trabajador.get('Nombre', 'N/A'),
                'estado': 'error',
                'fichajes': [],
                'mensaje': f'Error en análisis: {str(e)}'
            }


# Processor global
asistencia_processor = AsistenciaProcessor()