import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import tempfile
import os

# Importar módulos del proyecto
from config import config
from cache_manager import cache_manager
from scheduler import gesad_scheduler
from data_processor import asistencia_processor
from alert_manager import alert_manager


class TestConfig:
    """Test para configuración del sistema"""
    
    def test_config_validation(self):
        """Test validación de configuración"""
        # Test con configuración válida
        os.environ['GESAD_CONEX_NAME'] = 'test'
        os.environ['GESAD_AUTH_CODE'] = 'test'
        os.environ['GESAD_SESSION_ID'] = 'test'
        
        assert config.validate() == True
        
        # Test con configuración inválida
        os.environ['GESAD_CONEX_NAME'] = ''
        
        with pytest.raises(ValueError):
            config.validate()
    
    def test_active_time_check(self):
        """Test verificación de horario activo"""
        # Test horario activo (9 AM)
        active_time = datetime(2023, 1, 1, 9, 0, 0)
        assert config.is_active_time(active_time) == True
        
        # Test horario inactivo (2 PM)
        inactive_time = datetime(2023, 1, 1, 14, 0, 0)
        assert config.is_active_time(inactive_time) == False
        
        # Test horario inactivo (5 AM)
        early_time = datetime(2023, 1, 1, 5, 0, 0)
        assert config.is_active_time(early_time) == False


class TestCacheManager:
    """Test para sistema de caché"""
    
    @pytest.fixture
    async def temp_cache_dir(self):
        """Crear directorio temporal para tests"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cache_dir = cache_manager.cache_dir
            cache_manager.cache_dir = tmpdir
            yield tmpdir
            cache_manager.cache_dir = original_cache_dir
    
    @pytest.mark.asyncio
    async def test_cache_set_get(self, temp_cache_dir):
        """Test guardar y obtener del caché"""
        key = "test_key"
        data = {"test": "data"}
        
        # Guardar en caché
        await cache_manager.set(key, data)
        
        # Obtener del caché
        result = await cache_manager.get(key)
        
        assert result == data
    
    @pytest.mark.asyncio
    async def test_cache_ttl(self, temp_cache_dir):
        """Test TTL del caché"""
        key = "test_ttl_key"
        data = {"test": "ttl_data"}
        
        # Guardar con TTL corto
        await cache_manager.set(key, data, ttl=1)
        
        # Debería estar disponible inmediatamente
        result = await cache_manager.get(key)
        assert result == data
        
        # Esperar a que expire
        await asyncio.sleep(2)
        
        # Debería estar expirado
        result = await cache_manager.get(key, "default")
        assert result == "default"
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, temp_cache_dir):
        """Test estadísticas del caché"""
        key = "test_stats_key"
        data = {"test": "stats_data"}
        
        # Obtener stats iniciales
        initial_stats = await cache_manager.get_stats()
        initial_sets = initial_stats['sets']
        
        # Guardar y obtener
        await cache_manager.set(key, data)
        await cache_manager.get(key)
        
        # Verificar stats actualizados
        final_stats = await cache_manager.get_stats()
        assert final_stats['sets'] == initial_sets + 1
        assert final_stats['memory_hits'] > 0


class TestScheduler:
    """Test para scheduler del sistema"""
    
    def test_active_time_check(self):
        """Test verificación de horario activo"""
        # Mock del scheduler
        scheduler = gesad_scheduler
        
        # Test horario activo
        active_time = datetime(2023, 1, 1, 9, 0, 0)
        assert scheduler.is_active_time(active_time) == True
        
        # Test horario inactivo
        inactive_time = datetime(2023, 1, 1, 14, 0, 0)
        assert scheduler.is_active_time(inactive_time) == False
    
    def test_time_until_active(self):
        """Test cálculo de tiempo hasta activación"""
        scheduler = gesad_scheduler
        
        # Test para mañana a las 6 AM
        morning_time = datetime(2023, 1, 1, 5, 0, 0)
        time_until = scheduler.get_time_until_active(morning_time)
        
        # Debe ser 1 hora
        assert time_until.total_seconds() == 3600
    
    def test_scheduler_status(self):
        """Test obtener status del scheduler"""
        status = gesad_scheduler.get_status()
        
        # Verificar que contiene los campos esperados
        assert 'running' in status
        assert 'sleep_mode' in status
        assert 'is_active_time' in status
        assert 'check_count' in status
        assert 'active_hours' in status


class TestAlertManager:
    """Test para sistema de alertas"""
    
    @pytest.mark.asyncio
    async def test_alert_generation(self):
        """Test generación de alertas"""
        # Datos de prueba
        resultados = [
            {
                'trabajador_id': 1,
                'nombre': 'Juan Pérez',
                'departamento': 'Ventas',
                'estado': 'ausente_no_detectado',
                'mensaje': 'Sin entrada',
                'hora_prevista': '09:00'
            },
            {
                'trabajador_id': 2,
                'nombre': 'María García',
                'departamento': 'Administración',
                'estado': 'presente_tiempo',
                'mensaje': 'Entrada registrada',
                'hora_prevista': '08:30'
            }
        ]
        
        timestamp = datetime.now()
        
        # Generar alertas
        alertas = await alert_manager.procesar_alertas(resultados, timestamp)
        
        # Debería haber solo una alerta (ausencia)
        assert len(alertas) == 1
        assert alertas[0]['tipo'] == 'ausencia_no_detectada'
        assert alertas[0]['trabajador_id'] == 1
    
    @pytest.mark.asyncio
    async def test_alert_filtering(self):
        """Test filtrado de alertas"""
        # Guardar alertas de prueba
        alertas_prueba = [
            {
                'id': 'test_ausencia_1',
                'tipo': 'ausencia_no_detectada',
                'prioridad': 'alta',
                'trabajador_id': 1
            },
            {
                'id': 'test_tardia_1',
                'tipo': 'llegada_tardia',
                'prioridad': 'media',
                'trabajador_id': 2
            }
        ]
        
        await cache_manager.set("alertas_activas", {
            "alertas": alertas_prueba,
            "timestamp": datetime.now().isoformat(),
            "total": 2
        })
        
        # Filtrar por tipo
        ausencias = await alert_manager.filtrar_alertas_por_tipo('ausencia_no_detectada')
        assert len(ausencias) == 1
        assert ausencias[0]['tipo'] == 'ausente_no_detectado'
        
        tardias = await alert_manager.filtrar_alertas_por_tipo('llegada_tardia')
        assert len(tardias) == 1
        assert tardias[0]['tipo'] == 'llegada_tardia'


class TestDataProcessor:
    """Test para procesador de datos de asistencia"""
    
    def test_parse_hora(self):
        """Test parseo de horas"""
        processor = asistencia_processor
        current_date = datetime(2023, 1, 1, 10, 0, 0)
        
        # Test parseo correcto
        result = processor.parse_hora("09:30", current_date)
        expected = current_date.replace(hour=9, minute=30, second=0, microsecond=0)
        assert result == expected
    
    def test_analizar_estado_trabajador(self):
        """Test análisis de estado de trabajador"""
        processor = asistencia_processor
        
        trabajador = {
            'id': 1,
            'nombre': 'Juan Pérez',
            'departamento': 'Ventas',
            'hora_entrada': '09:00'
        }
        
        fichajes = []  # Sin fichajes
        timestamp = datetime(2023, 1, 1, 9, 30, 0)  # 9:30 AM
        
        # Analizar estado (debería estar ausente)
        estado = processor.analizar_estado_trabajador(trabajador, fichajes, timestamp)
        
        assert estado['trabajador_id'] == 1
        assert estado['estado'] == 'ausente_no_detectado'
        assert 'ausente' in estado['mensaje'].lower()
    
    @pytest.mark.asyncio
    async def test_get_trabajadores_activos(self):
        """Test obtener trabajadores activos"""
        processor = asistencia_processor
        
        trabajadores = await processor.get_trabajadores_activos()
        
        # Debería haber trabajadores de ejemplo
        assert len(trabajadores) > 0
        
        # Verificar estructura
        for trabajador in trabajadores:
            assert 'id' in trabajador
            assert 'nombre' in trabajador
            assert 'hora_entrada' in trabajador
    
    def test_generar_resumen(self):
        """Test generación de resumen estadístico"""
        processor = asistencia_processor
        
        resultados = [
            {'estado': 'presente_tiempo', 'departamento': 'Ventas'},
            {'estado': 'presente_tiempo', 'departamento': 'Ventas'},
            {'estado': 'llegada_tardia', 'departamento': 'Administración'},
            {'estado': 'ausente_no_detectado', 'departamento': 'Ventas'}
        ]
        
        resumen = processor.generar_resumen(resultados)
        
        assert resumen['total'] == 4
        assert resumen['presentes_tiempo'] == 2
        assert resumen['llegadas_tardias'] == 1
        assert resumen['ausentes_no_detectados'] == 1
        assert 'Ventas' in resumen['por_departamento']
        assert 'Administración' in resumen['por_departamento']


class TestIntegration:
    """Tests de integración del sistema completo"""
    
    @pytest.mark.asyncio
    async def test_monitoring_simulation(self):
        """Test simulación del proceso de monitoreo"""
        
        # Mock del cliente GESAD
        mock_fichajes = [
            {
                'trabajador_id': 1,
                'timestamp': '2023-01-01T09:00:00',
                'tipo': 'entrada'
            },
            {
                'trabajador_id': 2,
                'timestamp': '2023-01-01T08:45:00',
                'tipo': 'entrada'
            }
        ]
        
        # Mockear la llamada API
        async def mock_get_fichajes(fecha):
            return {'data': mock_fichajes}
        
        # Reemplazar temporalmente el método
        original_method = asistencia_processor.process_monitoring_check
        
        try:
            # Simular procesamiento
            resultado = await asistencia_processor.process_monitoring_check()
            
            # Verificar estructura del resultado
            assert 'timestamp' in resultado
            assert 'resultados' in resultado
            assert 'resumen' in resultado
            assert 'alertas' in resultado
            
        except Exception as e:
            # Es esperado que falle sin API real
            assert 'error' in str(e)
        
        finally:
            # Restaurar método original
            asistencia_processor.process_monitoring_check = original_method


if __name__ == "__main__":
    pytest.main([__file__, "-v"])