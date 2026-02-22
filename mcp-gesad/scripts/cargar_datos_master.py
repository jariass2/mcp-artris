#!/usr/bin/env python3
"""
Script para cargar datos de usuarios y trabajadores en el cache
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from config import config
from gesad_client import gesad_client
from cache_manager import cache_manager

async def cargar_datos_master():
    """Cargar usuarios y trabajadores en el cache"""
    
    print("\n" + "="*80)
    print("📦 CARGAR DATOS MASTER EN CACHE")
    print("="*80 + "\n")
    
    # 1. Cargar usuarios (con paginación)
    print("📥 Cargando usuarios (con paginación)...")
    cache_key_usuarios = "usuarios_lista_completa"
    usuarios_cache = await cache_manager.get(cache_key_usuarios)
    
    if not usuarios_cache:
        print("   📡 Obteniendo usuarios desde API...")
        todos_usuarios = []
        pagina = 1
        max_paginas = 50  # Safety limit
        
        while pagina <= max_paginas:
            print(f"      📄 Página {pagina}...")
            usuarios_result = await gesad_client.get_usuarios_expedientes_pagina(pagina, 1000)
            
            if isinstance(usuarios_result, list) and len(usuarios_result) > 0:
                todos_usuarios.extend(usuarios_result)
                print(f"         ✅ {len(usuarios_result)} usuarios (total: {len(todos_usuarios)})")
                pagina += 1
                
                # Si tenemos menos de 1000, es la última página
                if len(usuarios_result) < 1000:
                    break
            else:
                print(f"         ⚠️ No más usuarios en página {pagina}")
                break
        
        if len(todos_usuarios) > 0:
            await cache_manager.set(cache_key_usuarios, todos_usuarios, ttl=24 * 3600)
            print(f"   ✅ {len(todos_usuarios)} usuarios cacheados por 24 horas")
        else:
            print(f"   ⚠️ Error: No se pudieron obtener usuarios")
    else:
        print(f"   📦 {len(usuarios_cache)} usuarios ya estaban cacheados")
    
    # 2. Cargar trabajadores (con paginación)
    print("\n👥 Cargando trabajadores (con paginación)...")
    cache_key_trabajadores = "trabajadores_lista_completa"
    trabajadores_cache = await cache_manager.get(cache_key_trabajadores)
    
    if not trabajadores_cache:
        print("   📡 Obteniendo trabajadores desde API...")
        todos_trabajadores = []
        pagina = 1
        max_paginas = 50  # Safety limit
        
        while pagina <= max_paginas:
            print(f"      📄 Página {pagina}...")
            trabajadores_result = await gesad_client.get_trabajadores_expedientes_pagina(pagina, 1000)
            
            if isinstance(trabajadores_result, list) and len(trabajadores_result) > 0:
                todos_trabajadores.extend(trabajadores_result)
                print(f"         ✅ {len(trabajadores_result)} trabajadores (total: {len(todos_trabajadores)})")
                pagina += 1
                
                if len(trabajadores_result) < 1000:
                    break
            else:
                print(f"         ⚠️ No más trabajadores en página {pagina}")
                break
        
        if len(todos_trabajadores) > 0:
            await cache_manager.set(cache_key_trabajadores, todos_trabajadores, ttl=24 * 3600)
            print(f"   ✅ {len(todos_trabajadores)} trabajadores cacheados por 24 horas")
        else:
            print(f"   ⚠️ Error: No se pudieron obtener trabajadores")
    else:
        print(f"   📦 {len(trabajadores_cache)} trabajadores ya estaban cacheados")
    
    # 3. Verificar carga
    print("\n" + "="*80)
    print("📊 RESUMEN DE CARGA")
    print("="*80)
    
    usuarios_final = await cache_manager.get(cache_key_usuarios, [])
    trabajadores_final = await cache_manager.get(cache_key_trabajadores, [])
    
    print(f"\n✅ Usuarios en cache: {len(usuarios_final)}")
    print(f"✅ Trabajadores en cache: {len(trabajadores_final)}")
    
    if usuarios_final:
        print(f"\n📋 Ejemplo de usuario:")
        usuario = usuarios_final[0]
        print(f"   - ID: {usuario.get('Usuario_Id', 'N/A')}")
        print(f"   - Nombre: {usuario.get('Nombre', 'N/A')} {usuario.get('Apellidos', '')}")
        print(f"   - Email: {usuario.get('Email', 'N/A')}")
        print(f"   - Dirección: {usuario.get('Direccion', 'N/A')}")
    
    if trabajadores_final:
        print(f"\n👥 Ejemplo de trabajador:")
        trabajador = trabajadores_final[0]
        print(f"   - ID: {trabajador.get('Trabajador_Id', 'N/A')}")
        print(f"   - Nombre: {trabajador.get('Nombre', 'N/A')} {trabajador.get('Apellidos', '')}")
        print(f"   - Departamento: {trabajador.get('Departamento', 'N/A')}")
        print(f"   - Teléfono: {trabajador.get('Telefono1', 'N/A')}")
    
    print("\n" + "="*80)
    print("✅ Carga completada")
    print("="*80 + "\n")

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(cargar_datos_master())
