#!/usr/bin/env python3
"""
Script para verificar fichajes específicos sin entrada
"""

import asyncio
from gesad_client import gesad_client
from data_processor_optimized import gesad_optimized_processor
from cache_manager import cache_manager
from config import config

# Lista de fichajes específicos a verificar
FICHAJES_A_VERIFICAR = [
    '10678199',
    '10673690', 
    '10673288',
    '10671313',
    '10673675',
    '10674955',
    '10673306',
    '10674922',
    '10678019'
]

async def verificar_fichajes_especificos():
    print('🔍 VERIFICACIÓN DE FICHAJES ESPECÍFICOS')
    print('=' * 70)
    print(f'Fichajes a verificar: {len(FICHAJES_A_VERIFICAR)}')
    print()
    
    # Obtener fichajes del día
    result = await gesad_client.get_fichajes_dia('12-02-2026')
    
    if not isinstance(result, list):
        print(f'❌ Error obteniendo fichajes: {result}')
        return
    
    print(f'📊 Total fichajes en API: {len(result)}')
    print()
    
    # Buscar los fichajes específicos
    fichajes_encontrados = []
    
    for fichaje in result:
        if isinstance(fichaje, dict):
            codigo = str(fichaje.get('Codigo', ''))
            
            if codigo in FICHAJES_A_VERIFICAR:
                fichajes_encontrados.append(fichaje)
                
                print(f'🎯 FICHAJE ENCONTRADO: {codigo}')
                print(f'   👤 Trabajador ID: {fichaje.get("Trabajador_Id", "N/A")}')
                print(f'   👥 Usuario ID: {fichaje.get("Usuario_Id", "N/A")}')
                print(f'   🕐 Hora Entrada: {fichaje.get("Hora_Ent_Fichaje", "None")}')
                print(f'   🕐 Hora Salida: {fichaje.get("Hora_Sal_Fichaje", "None")}')
                print(f'   🔧 Servicio: {fichaje.get("Servicio_Activo", "N/A")}')
                print(f'   📍 Ubicación: {fichaje.get("Ubicacion", "N/A")}')
                
                # Verificar si tiene entrada
                hora_entrada = fichaje.get('Hora_Ent_Fichaje')
                if hora_entrada is None or hora_entrada == '':
                    print(f'   ⚠️  ESTADO: ❌ SIN ENTRADA (Ausencia)')
                else:
                    print(f'   ✅ ESTADO: Con entrada ({hora_entrada})')
                
                print()
    
    print(f'📈 RESUMEN:')
    print(f'   Fichajes buscados: {len(FICHAJES_A_VERIFICAR)}')
    print(f'   Fichajes encontrados: {len(fichajes_encontrados)}')
    
    sin_entrada = sum(1 for f in fichajes_encontrados 
                     if f.get('Hora_Ent_Fichaje') is None or f.get('Hora_Ent_Fichaje') == '')
    
    print(f'   Sin entrada (ausencias): {sin_entrada}')
    print(f'   Con entrada: {len(fichajes_encontrados) - sin_entrada}')
    print()
    
    # Verificar en el sistema de procesados
    print('📝 ESTADO EN SISTEMA DE PROCESADOS:')
    lista_procesados = await cache_manager.get_lista_procesados_detalle("sin_fichaje")
    
    for fichaje in fichajes_encontrados:
        codigo = str(fichaje.get('Codigo', ''))
        esta_procesado = await cache_manager.is_fichaje_procesado(codigo, "sin_fichaje")
        
        if esta_procesado:
            print(f'   ✅ {codigo}: Ya procesado (no se detectará de nuevo)')
        else:
            print(f'   ⏳ {codigo}: Pendiente de procesar')
    
    print()
    print('💡 Para forzar reprocesamiento:')
    print('   POST /admin/reset-procesados?tipo=sin_fichaje')

if __name__ == "__main__":
    asyncio.run(verificar_fichajes_especificos())