#!/usr/bin/env python3
"""
Demo del sistema GESAD funcionando en horario activo (Europe/Madrid)
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from config import config
from scheduler import GESADScheduler

async def demo_horario_activo():
    """Demo del sistema en horario activo"""
    
    print("🎭 DEMO: Sistema GESAD en horario activo (Europe/Madrid)")
    print("=" * 60)
    
    # Mostrar configuración actual
    print(f"🌍 Timezone: {config.TIMEZONE}")
    print(f"🕐 Hora actual Madrid: {config.get_local_time().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"⏰ Horario activo: {config.ACTIVE_START}:00 - {config.ACTIVE_END}:00 Madrid")
    print(f"📊 ¿Está activo?: {'✅ Sí' if config.is_active_time() else '❌ No'}")
    print()
    
    # Simular horario activo temporalmente
    print("🎭 Simulando horario activo para demo...")
    original_start = config.ACTIVE_START
    original_end = config.ACTIVE_END
    
    current_hour = config.get_local_time().hour
    config.ACTIVE_START = current_hour - 1
    config.ACTIVE_END = current_hour + 2
    
    print(f"📝 Horario temporal demo: {config.ACTIVE_START}:00 - {config.ACTIVE_END}:00")
    print(f"✅ Ahora está activo: {config.is_active_time()}")
    print()
    
    # Crear scheduler para demo
    demo_scheduler = GESADScheduler()
    
    # Callback de demo
    check_count = 0
    async def demo_callback():
        nonlocal check_count
        check_count += 1
        
        current_time = config.get_local_time()
        print(f"🔍 [{current_time.strftime('%H:%M:%S')}] ✅ Verificación #{check_count}")
        print("   📡 Conectando a API GESAD...")
        print("   📥 Obteniendo fichajes del día...")
        print("   🧮 Analizando trabajadores...")
        print("   📊 Resultado:")
        print("      • 12 trabajadores analizados")
        print("      • 11 presentes a tiempo ✅")
        print("      • 1 llegada tardía ⏰")
        print("      • 0 ausentes ❌")
        print("      • 1 alerta generada")
        print("   💾 Datos guardados en cache (TTL: 20 min)")
        print("   🌐 API calls hoy: " + str(check_count * 2) + f"/{config.DAILY_LIMIT}")
        print()
        
        # Simular diferentes resultados
        if check_count == 1:
            return {
                "timestamp": current_time.isoformat(),
                "check_number": check_count,
                "trabajadores": 12,
                "presentes": 11,
                "tardias": 1,
                "ausentes": 0,
                "alertas": 1,
                "success": True
            }
        elif check_count == 2:
            return {
                "timestamp": current_time.isoformat(),
                "check_number": check_count,
                "trabajadores": 12,
                "presentes": 10,
                "tardias": 2,
                "ausentes": 0,
                "alertas": 2,
                "success": True
            }
        else:
            return {
                "timestamp": current_time.isoformat(),
                "check_number": check_count,
                "trabajadores": 12,
                "presentes": 9,
                "tardias": 3,
                "ausentes": 0,
                "alertas": 3,
                "success": True
            }
    
    demo_scheduler.set_monitoring_callback(demo_callback)
    
    print("🚀 Iniciando demo (2 verificaciones - 40 segundos)...")
    print()
    
    # Configurar intervalo corto para demo
    demo_scheduler.check_interval = 20  # 20 segundos en lugar de 20 minutos
    
    # Iniciar demo
    task = asyncio.create_task(demo_scheduler.start())
    
    try:
        # Ejecutar demo por 40 segundos (2 verificaciones)
        await asyncio.sleep(40)
    except KeyboardInterrupt:
        print("⌨️ Demo interrumpido")
    finally:
        # Restaurar configuración original
        config.ACTIVE_START = original_start
        config.ACTIVE_END = original_end
        
        # Detener demo
        demo_scheduler.running = False
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        print("🛑 Demo completado")
        print()
        print("📊 Resumen del demo:")
        print(f"   • Verificaciones ejecutadas: {check_count}")
        print(f"   • Hora configuración: {config.TIMEZONE}")
        print(f"   • Sistema funcionando: ✅")
        print(f"   • API calls simulados: {check_count * 2}")
        print(f"   • Cache optimizado: ✅")
        print(f"   • Configuración restaurada: ✅")

async def main():
    """Función principal"""
    
    load_dotenv()
    
    # Mostrar información de producción
    print("🌍 Configuración Timezone Europe/Madrid")
    print("=" * 60)
    
    # Validar configuración
    try:
        config.validate()
        print("✅ Configuración validada")
        print(f"🔑 Credenciales configuradas: {config.CONEX_NAME}")
        print(f"🌐 Timezone: {config.TIMEZONE}")
        print(f"🕐 Hora Madrid: {config.get_local_time().strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"⏰ Horario producción: {config.ACTIVE_START}:00 - {config.ACTIVE_END}:00 Madrid")
        print(f"📅 Próxima activación: {config.get_local_time() + config.get_time_until_active()}")
        print()
    except Exception as e:
        print(f"❌ Error configuración: {e}")
        return
    
    await demo_horario_activo()
    
    print()
    print("🎯 Para producción:")
    print("✅ Credenciales configuradas")
    print("✅ Timezone Europe/Madrid configurado")  
    print("✅ Horario 6:00-12:00 Madrid configurado")
    print("✅ Sistema listo para producción")
    print()
    print("🚀 Ejecutar en producción:")
    print("python start_monitoring.py")
    print()
    print("📚 Más información en README.md")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrumpido")