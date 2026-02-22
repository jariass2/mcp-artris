#!/usr/bin/env python3
"""
Demo del sistema GESAD funcionando en modo activo para testing
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from config import config
from scheduler import GESADScheduler

async def demo_activo():
    """Demo del sistema en modo activo"""
    
    print("🎭 DEMO: Sistema GESAD en modo activo")
    print("=" * 50)
    
    # Temporalmente cambiar configuración para demo
    original_start = config.ACTIVE_START
    original_end = config.ACTIVE_END
    
    # Configurar horario activo actual para demo
    current_hour = datetime.now().hour
    config.ACTIVE_START = current_hour - 1
    config.ACTIVE_END = current_hour + 2
    
    print(f"🕐 Horario demo activo: {config.ACTIVE_START}:00 - {config.ACTIVE_END}:00")
    print(f"📅 Hora actual: {datetime.now().strftime('%H:%M')}")
    print()
    
    # Crear scheduler demo
    demo_scheduler = GESADScheduler()
    
    # Callback de demo
    async def demo_callback():
        print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Verificación de asistencia ejecutada!")
        print("   ✅ Fichajes obtenidos desde API")
        print("   📊 3 trabajadores analizados")  
        print("   🚨 1 alerta generada (Ausencia detectada)")
        print("   💾 Datos guardados en cache")
        print()
        return {"success": True, "workers": 3, "alerts": 1}
    
    demo_scheduler.set_monitoring_callback(demo_callback)
    
    print("🚀 Iniciando demo de monitoreo (30 segundos)...")
    print()
    
    # Iniciar con timeout de 30 segundos
    task = asyncio.create_task(demo_scheduler.start())
    
    try:
        # Ejecutar por 30 segundos
        await asyncio.wait_for(asyncio.sleep(30), timeout=30)
    except asyncio.TimeoutError:
        print("⏰ Demo completado (30 segundos)")
    except KeyboardInterrupt:
        print("⌨️ Demo interrumpido")
    finally:
        # Restaurar configuración original
        config.ACTIVE_START = original_start
        config.ACTIVE_END = original_end
        
        # Detener scheduler
        demo_scheduler.running = False
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        print("🛑 Demo detenido")
        print()
        print("📊 Resumen del demo:")
        print(f"   • Verificaciones ejecutadas: {demo_scheduler.check_count}")
        print(f"   • Sistema iniciado: ✅")
        print(f"   • Callback funcionando: ✅")
        print(f"   • Configuración restaurada: ✅")

async def main():
    """Función principal"""
    
    load_dotenv()
    
    print("🎭 Sistema de Monitoreo GESAD - DEMO")
    print("=" * 50)
    
    # Validar configuración
    try:
        config.validate()
        print("✅ Configuración validada")
    except Exception as e:
        print(f"❌ Error configuración: {e}")
        return
    
    print()
    await demo_activo()
    
    print()
    print("🎯 Para producción:")
    print("1. Configura tus credenciales reales en .env")
    print("2. Ejecuta: python start_monitoring.py")
    print("3. Sistema operará 6:00 AM - 12:00 PM automáticamente")
    print()
    print("📚 Más información en README.md")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrumpido")