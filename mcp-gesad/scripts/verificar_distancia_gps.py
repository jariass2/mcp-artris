import asyncio
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Agregar el directorio parent al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gesad_client import gesad_client
from cache_manager import cache_manager
from webhook_manager import webhook_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def buscar_fichajes_con_gps():
    """Buscar fichajes recientes con GPS y verificar cálculo de distancia"""

    fecha_actual = datetime.now()
    fecha_str = fecha_actual.strftime('%d-%m-%Y')

    # Obtener fichajes del día
    logger.info(f"Obteniendo fichajes del día {fecha_str}...")
    result = await gesad_client.get_fichajes_dia(fecha_str)

    if "error" in result or not isinstance(result, list):
        logger.error(f"Error obteniendo fichajes: {result}")
        return

    logger.info(f"Se obtuvieron {len(result)} fichajes\n")

    # Buscar fichajes con GPS del fichaje
    fichajes_con_gps = []
    fichajes_con_gps_usuario = []

    for fichaje in result:
        fichaje_id = fichaje.get('Fichaje_Id') or fichaje.get('FichajeId')
        fichaje_lat = fichaje.get('Fichaje_Ent_Gps_Lat') or fichaje.get('Fichaje_Sal_Gps_Lat')
        fichaje_lon = fichaje.get('Fichaje_Ent_Gps_Lon') or fichaje.get('Fichaje_Sal_Gps_Lon')

        if fichaje_lat and fichaje_lon:
            fichajes_con_gps.append(fichaje)

    logger.info(f"Fichajes con GPS del trabajador: {len(fichajes_con_gps)}")

    if not fichajes_con_gps:
        logger.info("No se encontraron fichajes con GPS del trabajador")
        return

    # Analizar los primeros 3 fichajes con GPS
    for i, fichaje in enumerate(fichajes_con_gps[:3]):
        fichaje_id = fichaje.get('Fichaje_Id') or fichaje.get('FichajeId')
        usuario_id = fichaje.get('Usuario_Id') or fichaje.get('UsuarioId')

        logger.info(f"\n{'='*80}")
        logger.info(f"FICHAJE #{i+1}: {fichaje_id}")
        logger.info(f"{'='*80}\n")

        # Mostrar campos GPS del fichaje
        logger.info("CAMPOS GPS DEL FICHAJE:")
        logger.info("-" * 80)
        for key in ['Fichaje_Ent_Gps_Lat', 'Fichaje_Ent_Gps_Lon', 'Fichaje_Sal_Gps_Lat', 'Fichaje_Sal_Gps_Lon']:
            value = fichaje.get(key)
            logger.info(f"  {key}: {value}")

        # Obtener usuario
        if not usuario_id:
            logger.warning("No se encontró usuario_id")
            continue

        # Obtener usuarios cacheados y buscar el específico
        usuarios_cache = await cache_manager.get("usuarios_lista_completa", [])
        usuarios_map = {}
        for usuario in usuarios_cache:
            if isinstance(usuario, dict) and usuario.get('Usuario_Id'):
                usuarios_map[str(usuario['Usuario_Id'])] = usuario

        usuario = usuarios_map.get(str(usuario_id), {})
        if not usuario:
            logger.warning(f"Usuario {usuario_id} no encontrado en caché")
            continue

        # Mostrar campos GPS del usuario
        logger.info("\nCAMPOS GPS DEL USUARIO:")
        logger.info("-" * 80)
        for key in ['Gis_Latitud', 'Gis_Longitud', 'Latitud', 'Longitud']:
            value = usuario.get(key)
            logger.info(f"  {key}: {value}")

        # Calcular distancia
        logger.info("\nCÁLCULO DE DISTANCIA:")
        logger.info("-" * 80)
        ubicacion = webhook_manager._calcular_distancia(usuario, fichaje)

        logger.info("RESULTADO:")
        logger.info("-" * 80)
        for key, value in ubicacion.items():
            if isinstance(value, dict):
                logger.info(f"  {key}:")
                for k2, v2 in value.items():
                    logger.info(f"    {k2}: {v2}")
            else:
                logger.info(f"  {key}: {value}")

        # Resumen
        logger.info("\nRESUMEN:")
        logger.info("-" * 80)
        logger.info(f"  GPS Fichaje: {fichaje.get('Fichaje_Ent_Gps_Lat') or fichaje.get('Fichaje_Sal_Gps_Lat')}, {fichaje.get('Fichaje_Ent_Gps_Lon') or fichaje.get('Fichaje_Sal_Gps_Lon')}")
        logger.info(f"  GPS Usuario: {usuario.get('Gis_Latitud')}, {usuario.get('Gis_Longitud')}")
        logger.info(f"  Distancia: {ubicacion.get('distancia_metros')} metros")
        logger.info(f"  Tiene GPS: {ubicacion.get('tiene_gps')}")

        # Verificar valores nulos
        if ubicacion.get('distancia_metros') is None:
            logger.warning("\n⚠️ DISTANCIA ES NULL - DETALLES:")

            gps_fichaje_lat = fichaje.get('Fichaje_Ent_Gps_Lat') or fichaje.get('Fichaje_Sal_Gps_Lat')
            gps_fichaje_lon = fichaje.get('Fichaje_Ent_Gps_Lon') or fichaje.get('Fichaje_Sal_Gps_Lon')
            usuario_lat = usuario.get('Gis_Latitud')
            usuario_lon = usuario.get('Gis_Longitud')

            logger.warning(f"  GPS Fichaje Lat: {gps_fichaje_lat} (type: {type(gps_fichaje_lat)})")
            logger.warning(f"  GPS Fichaje Lon: {gps_fichaje_lon} (type: {type(gps_fichaje_lon)})")
            logger.warning(f"  GPS Usuario Lat: {usuario_lat} (type: {type(usuario_lat)})")
            logger.warning(f"  GPS Usuario Lon: {usuario_lon} (type: {type(usuario_lon)})")

            # Verificar si son strings vacíos
            if gps_fichaje_lat == '' or gps_fichaje_lat == '0' or gps_fichaje_lat == 0:
                logger.warning(f"  → GPS Fichaje Lat está vacío o es 0")
            if usuario_lat == '' or usuario_lat == '0' or usuario_lat == 0:
                logger.warning(f"  → GPS Usuario Lat está vacío o es 0")


if __name__ == "__main__":
    asyncio.run(buscar_fichajes_con_gps())
