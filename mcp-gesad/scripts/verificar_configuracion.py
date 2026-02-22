#!/usr/bin/env python3
"""
Script para verificar la configuración del sistema GESAD MCP.
Verifica que las variables de entorno estén configuradas correctamente.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from colorama import Fore, Style, init

# Inicializar colorama
init()

def print_success(message):
    print(f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}")

def print_error(message):
    print(f"{Fore.RED}❌ {message}{Style.RESET_ALL}")

def print_warning(message):
    print(f"{Fore.YELLOW}⚠️  {message}{Style.RESET_ALL}")

def print_info(message):
    print(f"{Fore.CYAN}ℹ️  {message}{Style.RESET_ALL}")

def main():
    print(f"\n{Fore.CYAN}{'=' * 70}")
    print(f"🔍 VERIFICACIÓN DE CONFIGURACIÓN GESAD MCP")
    print(f"{'=' * 70}{Style.RESET_ALL}\n")
    
    all_good = True
    
    # 1. Verificar que el archivo .env existe
    print(f"{Fore.YELLOW}1. Verificando archivo .env...{Style.RESET_ALL}")
    env_path = Path('.env')
    if env_path.exists():
        print_success(f"Archivo .env encontrado en: {env_path.absolute()}")
    else:
        print_error("Archivo .env NO encontrado en el directorio actual")
        all_good = False
        return all_good
    
    # 2. Cargar variables de entorno
    print(f"\n{Fore.YELLOW}2. Cargando variables de entorno...{Style.RESET_ALL}")
    load_dotenv()
    print_success("Variables de entorno cargadas desde .env")
    
    # 3. Verificar variables de conexión API
    print(f"\n{Fore.YELLOW}3. Verificando variables de conexión API...{Style.RESET_ALL}")
    api_vars = {
        'GESAD_CONEX_NAME': 'Nombre de conexión',
        'GESAD_AUTH_CODE': 'Código de autorización',
        'GESAD_BASIC_AUTH': 'Autenticación básica',
        'GESAD_API_CODE': 'Código API',
        'GESAD_SESSION_ID': 'ID de sesión',
        'GESAD_BASE_URL': 'URL base de la API'
    }
    
    for var, desc in api_vars.items():
        value = os.getenv(var)
        if value:
            if var == 'GESAD_BASIC_AUTH':
                masked = value[:10] + '...' if len(value) > 10 else '***'
                print_success(f"{desc}: {masked}")
            else:
                print_success(f"{desc}: {value}")
        else:
            print_error(f"{desc} ({var}) NO está configurada")
            all_good = False
    
    # 4. Verificar variables de horarios
    print(f"\n{Fore.YELLOW}4. Verificando configuración de horarios...{Style.RESET_ALL}")
    schedule_vars = {
        'GESAD_TIMEZONE': 'Zona horaria',
        'GESAD_ACTIVE_START': 'Hora inicio (6)',
        'GESAD_ACTIVE_END': 'Hora fin (24)',
        'GESAD_CHECK_INTERVAL': 'Intervalo de verificación (20 min)'
    }
    
    for var, desc in schedule_vars.items():
        value = os.getenv(var)
        if value:
            print_success(f"{desc}: {value}")
        else:
            print_error(f"{desc} ({var}) NO está configurada")
            all_good = False
    
    # 5. Verificar variables de webhook
    print(f"\n{Fore.YELLOW}5. Verificando configuración de Webhook...{Style.RESET_ALL}")
    
    webhook_url = os.getenv('GESAD_WEBHOOK_URL')
    if webhook_url:
        print_success(f"URL del Webhook: {webhook_url}")
    else:
        print_error("GESAD_WEBHOOK_URL NO está configurada")
        all_good = False
    
    webhook_enabled = os.getenv('GESAD_WEBHOOK_ENABLED')
    if webhook_enabled:
        if webhook_enabled.lower() in ['true', '1', 'yes']:
            print_success(f"Webhook habilitado: {webhook_enabled}")
        else:
            print_warning(f"Webhook deshabilitado: {webhook_enabled}")
            print_info("Para habilitar el webhook, establece GESAD_WEBHOOK_ENABLED=true en .env")
    else:
        print_error("GESAD_WEBHOOK_ENABLED NO está configurada")
        all_good = False
    
    webhook_events = os.getenv('GESAD_WEBHOOK_EVENTS')
    if webhook_events:
        events = webhook_events.split(',')
        print_success(f"Eventos a notificar ({len(events)}): {', '.join(events)}")
    else:
        print_warning("GESAD_WEBHOOK_EVENTS NO está configurada (usará eventos por defecto)")
    
    # 6. Verificar umbrales
    print(f"\n{Fore.YELLOW}6. Verificando umbrales de alertas...{Style.RESET_ALL}")
    threshold_vars = {
        'GESAD_UMBRAL_LLEGADA_ADELANTADA': 'Llegada adelantada (20 min)',
        'GESAD_UMBRAL_RETRASO_AUSENCIA': 'Retraso ausencia (20 min)',
        'GESAD_UMBRAL_SALIDA_ADELANTADA': 'Salida adelantada (10 min)',
        'GESAD_UMBRAL_SALIDA_TARDE': 'Salida tarde (10 min)',
        'GESAD_UMBRAL_DISTANCIA_UBICACION': 'Distancia ubicación (50m)'
    }
    
    for var, desc in threshold_vars.items():
        value = os.getenv(var)
        if value:
            print_success(f"{desc}: {value}")
        else:
            print_warning(f"{desc} ({var}) NO está configurada (usará valor por defecto)")
    
    # 7. Resumen
    print(f"\n{Fore.CYAN}{'=' * 70}")
    if all_good:
        print(f"{Fore.GREEN}✅ CONFIGURACIÓN COMPLETA - SISTEMA LISTO PARA PRODUCCIÓN")
        print(f"{Fore.GREEN}🚀 Puedes ejecutar: python start_monitoring.py --standalone{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ CONFIGURACIÓN INCOMPLETA - REVISAR ERRORES ARRIBA{Style.RESET_ALL}")
    print(f"{'=' * 70}\n")
    
    return all_good

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
