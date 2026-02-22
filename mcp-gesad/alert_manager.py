import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from cache_manager import cache_manager

logger = logging.getLogger(__name__)


class AlertManager:
    """Sistema de alertas para ausencias y llegadas tardías"""
    
    def __init__(self):
        self.alertas_enviadas_hoy = set()  # Evitar duplicados por día
        self.tipos_alerta = {
            'ausencia_no_detectada': {
                'prioridad': 'alta',
                'categoria': 'asistencia',
                'mensaje_template': "❗ Ausencia detectada: {nombre} no ha fichado entrada (prevista: {hora})"
            },
            'llegada_tardia': {
                'prioridad': 'media',
                'categoria': 'asistencia',
                'mensaje_template': "⏰ Llegada tardía: {nombre} llegó tarde"
            }
        }
    
    async def procesar_alertas(self, resultados: List[Dict[str, Any]], timestamp_actual: datetime) -> List[Dict[str, Any]]:
        """Procesar resultados y generar alertas correspondientes"""
        
        alertas = []
        fecha_actual = timestamp_actual.strftime('%Y-%m-%d')
        
        # Resetear registro de alertas enviadas si es nuevo día
        alertas_fecha = await cache_manager.get("alertas_fecha_actual")
        if alertas_fecha != fecha_actual:
            self.alertas_enviadas_hoy.clear()
            await cache_manager.set("alertas_fecha_actual", fecha_actual, ttl=24 * 3600)
        
        for resultado in resultados:
            alerta = self.procesar_trabajador_alerta(resultado, timestamp_actual)
            if alerta:
                # Evitar duplicados para ausencias
                if alerta['tipo'] == 'ausencia_no_detectada':
                    alerta_id = f"{resultado['trabajador_id']}_{fecha_actual}"
                    
                    if alerta_id in self.alertas_enviadas_hoy:
                        continue  # Ya se alertó hoy
                    
                    self.alertas_enviadas_hoy.add(alerta_id)
                
                alertas.append(alerta)
        
        # Guardar alertas actuales en cache
        await cache_manager.set("alertas_activas", {
            "alertas": alertas,
            "timestamp": timestamp_actual.isoformat(),
            "total": len(alertas)
        }, ttl=3600)  # 1 hora
        
        logger.info(f"🚨 Generadas {len(alertas)} alertas")
        return alertas
    
    def procesar_trabajador_alerta(self, resultado: Dict[str, Any], timestamp_actual: datetime) -> Optional[Dict[str, Any]]:
        """Procesar resultado individual y generar alerta si corresponde"""
        
        estado = resultado['estado']
        
        # Solo generar alertas para ciertos estados
        if estado not in ['ausente_no_detectado', 'llegada_tardia']:
            return None
        
        # Obtener configuración del tipo de alerta
        if estado == 'ausente_no_detectado':
            tipo_alerta = 'ausencia_no_detectada'
            requiere_accion = True
        elif estado == 'llegada_tardia':
            tipo_alerta = 'llegada_tardia'
            requiere_accion = False
        else:
            return None
        
        config_alerta = self.tipos_alerta.get(tipo_alerta, {})
        
        # Generar mensaje personalizado
        mensaje = self.generar_mensaje_alerta(resultado, config_alerta)
        
        # Crear alerta
        alerta = {
            'id': f"{tipo_alerta}_{resultado['trabajador_id']}_{int(timestamp_actual.timestamp())}",
            'tipo': tipo_alerta,
            'prioridad': config_alerta.get('prioridad', 'media'),
            'categoria': config_alerta.get('categoria', 'general'),
            'trabajador_id': resultado['trabajador_id'],
            'trabajador_nombre': resultado['nombre'],
            'departamento': resultado['departamento'],
            'mensaje': mensaje,
            'detalle': resultado['mensaje'],
            'hora_prevista': resultado['hora_prevista'],
            'timestamp': timestamp_actual.isoformat(),
            'requiere_accion': requiere_accion,
            'estado_trabajador': estado
        }
        
        return alerta
    
    def generar_mensaje_alerta(self, resultado: Dict[str, Any], config_alerta: Dict[str, Any]) -> str:
        """Generar mensaje de alerta personalizado"""
        
        template = config_alerta.get('mensaje_template', '{nombre} requiere atención')
        
        mensaje = template.format(
            nombre=resultado['nombre'],
            hora=resultado['hora_prevista'],
            departamento=resultado['departamento']
        )
        
        return mensaje
    
    async def get_alertas_activas(self) -> Dict[str, Any]:
        """Obtener alertas activas desde cache"""
        
        cached_alertas = await cache_manager.get("alertas_activas")
        
        if not cached_alertas:
            return {
                "alertas": [],
                "timestamp": datetime.now().isoformat(),
                "total": 0
            }
        
        return cached_alertas
    
    async def filtrar_alertas_por_tipo(self, tipo: str) -> List[Dict[str, Any]]:
        """Obtener alertas filtradas por tipo"""
        
        alertas_data = await self.get_alertas_activas()
        alertas = alertas_data.get('alertas', [])
        
        filtradas = [alerta for alerta in alertas if alerta.get('tipo') == tipo]
        
        return filtradas
    
    async def filtrar_alertas_por_prioridad(self, prioridad: str) -> List[Dict[str, Any]]:
        """Obtener alertas filtradas por prioridad"""
        
        alertas_data = await self.get_alertas_activas()
        alertas = alertas_data.get('alertas', [])
        
        filtradas = [alerta for alerta in alertas if alerta.get('prioridad') == prioridad]
        
        return filtradas
    
    async def get_resumen_alertas(self) -> Dict[str, Any]:
        """Obtener resumen estadístico de alertas"""
        
        alertas_data = await self.get_alertas_activas()
        alertas = alertas_data.get('alertas', [])
        
        # Contar por tipo
        por_tipo = {}
        por_prioridad = {}
        por_departamento = {}
        
        for alerta in alertas:
            # Por tipo
            tipo = alerta.get('tipo', 'desconocido')
            por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
            
            # Por prioridad
            prioridad = alerta.get('prioridad', 'media')
            por_prioridad[prioridad] = por_prioridad.get(prioridad, 0) + 1
            
            # Por departamento
            depto = alerta.get('departamento', 'No especificado')
            por_departamento[depto] = por_departamento.get(depto, 0) + 1
        
        return {
            'total': len(alertas),
            'por_tipo': por_tipo,
            'por_prioridad': por_prioridad,
            'por_departamento': por_departamento,
            'requieren_accion': len([a for a in alertas if a.get('requiere_accion', False)]),
            'timestamp': datetime.now().isoformat()
        }
    
    async def marcar_alerta_resuelta(self, alerta_id: str, resolucion: str = "Manual") -> Dict[str, Any]:
        """Marcar una alerta como resuelta"""
        
        alertas_data = await self.get_alertas_activas()
        alertas = alertas_data.get('alertas', [])
        
        # Buscar la alerta
        alerta_encontrada = None
        for i, alerta in enumerate(alertas):
            if alerta.get('id') == alerta_id:
                alerta_encontrada = alerta
                alerta['resolucion'] = resolucion
                alerta['timestamp_resolucion'] = datetime.now().isoformat()
                alerta['estado'] = 'resuelta'
                break
        
        if not alerta_encontrada:
            return {"error": f"Alerta {alerta_id} no encontrada"}
        
        # Actualizar cache
        await cache_manager.set("alertas_activas", {
            "alertas": alertas,
            "timestamp": datetime.now().isoformat(),
            "total": len(alertas)
        }, ttl=3600)
        
        # Guardar historial de resoluciones
        historial = await cache_manager.get("alertas_resueltas", [])
        historial.append(alerta_encontrada)
        await cache_manager.set("alertas_resueltas", historial, ttl=7 * 24 * 3600)  # 7 días
        
        logger.info(f"✅ Alerta {alerta_id} marcada como resuelta: {resolucion}")
        
        return {"success": True, "alerta": alerta_encontrada}
    
    async def get_historial_resueltas(self, dias: int = 7) -> List[Dict[str, Any]]:
        """Obtener historial de alertas resueltas"""
        
        historial = await cache_manager.get("alertas_resueltas", [])
        
        # Filtrar por fecha
        fecha_limite = datetime.now() - timedelta(days=dias)
        filtrada = []
        
        for alerta in historial:
            timestamp = datetime.fromisoformat(alerta.get('timestamp_resolucion', ''))
            if timestamp >= fecha_limite:
                filtrada.append(alerta)
        
        # Ordenar por fecha descendente
        filtrada.sort(key=lambda x: x.get('timestamp_resolucion', ''), reverse=True)
        
        return filtrada


# Alert manager global
alert_manager = AlertManager()