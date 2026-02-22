#!/usr/bin/env python3
"""
Demo de optimización de caché para minimizar llamadas API
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from config import config
from gesad_client import gesad_client
from cache_manager import cache_manager
from data_processor_optimized import gesad_optimized_processor

async def demo_optimizacion_cache():
    """Demostrar optimización de caché con datos reales"""
    
    print("🚀 DEMO: Optimización de Caché para Minimizar Llamadas API")
    print("=" * 60)
    
    print("📊 Estadísticas Actuales:")
    
    # Obtener estadísticas actuales
    stats_cache = await cache_manager.get_stats()
    stats_api = gesad_client.get_usage_stats()
    
    print(f"   • Cache hit rate: {stats_cache.get('hit_rate_percent', 0):.1f}%")
    print(f"   • Llamadas API hoy: {stats_api.get('daily_calls', 0)}/{stats_api.get('daily_limit', 500)}")
    print(f"   • Uso API: {stats_api.get('usage_percentage', 0):.1f}%")
    print(f"   • Archivos cache: {stats_cache.get('disk_cache_files', 0)}")
    print()
    
    # Demostrar precarga de datos
    print("📥 DEMO 1: Precarga de Datos Maestros")
    print("-" * 40)
    
    # Simular precarga de usuarios
    print("📥 Obteniendo lista de usuarios (1a vez en el día)...")
    
    # Usar el método real para obtener usuarios
    cache_key_usuarios = "usuarios_lista_completa"
    usuarios_cache = await cache_manager.get(cache_key_usuarios)
    
    if not usuarios_cache:
        print("   📡 Realizando llamada a API para obtener usuarios...")
        # Usar el endpoint correcto de usuarios
        usuarios_result = await gesad_client.get_usuarios_expedientes()
        
        if isinstance(usuarios_result, list) and len(usuarios_result) > 0:
            usuarios_cache = list(usuarios_result)  # Usar todos los usuarios disponibles
            await cache_manager.set(cache_key_usuarios, usuarios_cache, ttl=24 * 3600)
            print(f"   ✅ {len(usuarios_cache)} usuarios cacheados por 24 horas")
        else:
            print(f"   ⚠️ Creando 50 usuarios de ejemplo para demo")
            usuarios_cache = [
                {"Usuario_Id": f"USER{i:03d}", "Nombre": f"Usuario{i}", "Apellidos": f"Apellido{i}", "Email": f"usuario{i}@ejemplo.com"}
                for i in range(1, 51)
            ]
            await cache_manager.set(cache_key_usuarios, usuarios_cache, ttl=24 * 3600)
    else:
        print(f"   📦 {len(usuarios_cache)} usuarios ya cacheados")
    
    # Simular precarga de trabajadores
    print("\n👥 Obteniendo lista de trabajadores (1a vez en el día)...")
    
    cache_key_trabajadores = "trabajadores_lista_completa"
    trabajadores_cache = await cache_manager.get(cache_key_trabajadores)
    
    if not trabajadores_cache:
        print("   📡 Realizando llamada a API para obtener trabajadores...")
        # Usar el endpoint correcto de trabajadores
        trabajadores_result = await gesad_client.get_trabajadores_expedientes()
        
        if isinstance(trabajadores_result, list) and len(trabajadores_result) > 0:
            trabajadores_cache = list(trabajadores_result)  # Usar todos los trabajadores disponibles
            await cache_manager.set(cache_key_trabajadores, trabajadores_cache, ttl=24 * 3600)
            print(f"   ✅ {len(trabajadores_cache)} trabajadores cacheados por 24 horas")
        else:
            print(f"   ⚠️ Creando 50 trabajadores de ejemplo para demo")
            trabajadores_cache = [
                {"Trabajador_Id": f"TRAB{i:03d}", "Nombre": f"Trabajador{i}", "Apellidos": f"Apellido{i}", "Departamento": f"Dept{i}", "Telefono1": f"60000000{i}"}
                for i in range(1, 51)
            ]
            await cache_manager.set(cache_key_trabajadores, trabajadores_cache, ttl=24 * 3600)
    else:
        print(f"   📦 {len(trabajadores_cache)} trabajadores ya cacheados")
    
    print()
    print("🔍 DEMO 2: Monitoreo con Datos Cacheados")
    print("-" * 40)
    
    # Simular monitoreo
    timestamp_actual = config.get_local_time()
    print(f"🕐 Hora actual: {timestamp_actual.strftime('%H:%M:%S')} ({config.TIMEZONE})")
    
    # Generar datos cruzados optimizados
    print("📊 Generando datos cruzados con cache optimizado...")
    datos_cruzados = await gesad_optimized_processor.get_datos_cruzados(timestamp_actual)
    
    if "error" in datos_cruzados:
        print(f"   ❌ Error: {datos_cruzados['error']}")
    else:
        print(f"   ✅ Datos cruzados generados exitosamente")
        print(f"   📋 Total fichajes analizados: {datos_cruzados['total_fichajes']}")
        print(f"   👥 Usuarios cacheados: {datos_cruzados['total_usuarios_cache']}")
        print(f"   👤 Trabajadores cacheados: {datos_cruzados['total_trabajadores_cache']}")
        print(f"   ❌ Ausencias detectadas: {datos_cruzados['ausencias_detectadas']}")
        print(f"   ⚠️ Fichajes parciales: {datos_cruzados['fichajes_parciales']}")
        print(f"   ✅ Fichajes completos: {datos_cruzados['fichajes_completos']}")
        print(f"   🌐 Llamadas API hoy: {datos_cruzados['api_calls_today']}")
        print(f"   📈 Cache hit rate: {datos_cruzados['cache_hit_rate']:.1f}%")
    
    print()
    print("🔗 DEMO 3: Informes Detallados")
    print("-" * 40)
    
    # Mostrar informes de ausencias
    informes_ausencias = await gesad_optimized_processor.get_informes_ausencias('sin_fichaje')
    
    if informes_ausencias and 'informes' in informes_ausencias:
        print(f"📋 Informes de ausencias sin fichaje: {len(informes_ausencias['informes'])}")
        
        # Mostrar primeros 3 informes
        for i, informe in enumerate(informes_ausencias['informes'][:3], 1):
            print(f"\n📄 Informe #{i}:")
            print(f"   💾 ID Fichaje: {informe['fichaje'].get('odigo', 'N/A')}")
            print(f"   👤 Trabajador: {informe['trabajador'].get('Nombre', 'N/A')} {informe['trabajador'].get('Apellidos', '')}")
            print(f"   👤 Usuario: {informe['usuario'].get('Nombre', 'N/A')} {informe['usuario'].get('Apellidos', '')}")
            print(f"   📧 Email: {informe['usuario'].get('Email', 'N/A')}")
            print(f"   📞 Teléfono: {informe['trabajador'].get('Telefono1', 'N/A')}")
            
            # Detalles del fichaje
            fichaje = informe['fichaje']
            print(f"   🕐 Entrada: {fichaje.get('Hora_Ent_Fichaje', 'N/A')}")
            print(f"   🕐 Salida: {fichaje.get('Hora_Sal_Fichaje', 'N/A')}")
            print(f"   🔧 Servicio: {fichaje.get('Servicio_Activo', 'N/A')} (ID: {fichaje.get('Servicio_Id', 'N/A')})")
    
    # Mostrar resumen de usuarios afectados
    resumen_usuarios = await gesad_optimized_processor.get_resumen_usuarios_ausentes()
    
    if resumen_usuarios and 'usuarios_con_ausencias' in resumen_usuarios:
        print(f"\n👥 Resumen por Usuario:")
        print(f"   Total usuarios con ausencias: {resumen_usuarios['total_usuarios_afectados']}")
        print(f"   Total ausencias: {resumen_usuarios['total_ausencias']}")
        
        for usuario_id, info in list(resumen_usuarios['usuarios_con_ausencias'].items())[:3]:
            usuario = info['usuario']
            print(f"\n👤 Usuario: {usuario.get('Nombre', 'N/A')} {usuario.get('Apellidos', '')}")
            print(f"   📧 Email: {usuario.get('Email', 'N/A')}")
            print(f"   💼 Coordinador: {usuario.get('Coordinador', 'N/A')}")
            print(f"   📊 Ausencias: {len(info['ausencias'])}")
            
            # Mostrar sus ausencias
            for j, ausencia in enumerate(info['ausencias'][:2], 1):
                trabajador = ausencia['trabajador']
                print(f"     {j}. 👤 {trabajador.get('Nombre', 'N/A')} - {trabajador.get('Departamento', 'N/A')}")
    
    print()
    print("🎯 DEMO 4: Estadísticas de Optimización")
    print("-" * 40)
    
    stats_opt = await gesad_optimized_processor.get_estadisticas_optimizacion()
    
    if "error" not in stats_opt:
        print("📊 Métricas de rendimiento:")
        print(f"   📦 Usuarios cacheados: {stats_opt['usuarios_cacheados']}")
        print(f"   👤 Trabajadores cacheados: {stats_opt['trabajadores_cacheados']}")
        print(f"   🔗 Llamadas evitadas: {stats_opt['llamadas_evitadas']}")
        print(f"   📈 Porcentaje de uso API: {stats_opt['porcentaje_uso_api']:.1f}%")
        print(f"   💾 Cache efficiency: {stats_opt['eficiencia_cache']:.1f}%")
        print(f"   💰 Ahorro estimado: {stats_opt.get('ahorro_estimado', 'N/A')}")
        print(f"   ⏱️ Tiempo guardado: {stats_opt.get('tiempo_guardado', 'N/A')}")
        
        print("\n🎯 Beneficios de la optimización:")
        print("   ✅ Minimizar llamadas API (máximo 500/día)")
        print("   ✅ Respuestas instantáneas (cache)")
        print("   ✅ Información completa cruzada")
        print("   ✅ Identificar responsable de cada ausencia")
        print("   ✅ Datos de contacto para notificaciones")
        print("   ✅ Optimización de costos y recursos")
    
    print()
    print("🎉 OPTIMIZACIÓN IMPLEMENTADA CON ÉXITO!")
    print("=" * 60)
    print("🔥 El sistema ahora:")
    print("   1. Precarga usuarios y trabajadores a las 6:00 AM")
    print("   2. Usa datos cacheados para cruces con fichajes")
    print("   3. Solo 1 llamada API cada 20 minutos (para fichajes)")
    print("   4. Identifica ausencias con responsables asignados")
    print("   5. Genera informes detallados con datos de contacto")
    print("   6. Minimiza costos y maximiza eficiencia")
    
    print(f"\n🚀 Para producción, ejecuta:")
    print("python start_monitoring.py --standalone")

async def main():
    """Función principal del demo"""
    
    load_dotenv()
    
    # Validar configuración
    try:
        config.validate()
        print("✅ Configuración validada")
    except Exception as e:
        print(f"❌ Error configuración: {e}")
        return
    
    await demo_optimizacion_cache()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrumpido")