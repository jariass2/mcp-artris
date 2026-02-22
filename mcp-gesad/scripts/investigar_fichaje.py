import asyncio
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Agregar el directorio parent al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gesad_client import gesad_client
from cache_manager import cache_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def investigar_fichaje(fichaje_id: int, dias_buscar: int = 7):
    """Investigar los campos GPS de un fichaje específico"""

    # Buscar en los últimos N días
    fecha_actual = datetime.now()

    for i in range(dias_buscar):
        fecha = fecha_actual - timedelta(days=i)
        fecha_str = fecha.strftime('%d-%m-%Y')

        # Obtener fichajes del día
        logger.info(f"Buscando fichaje {fichaje_id} en día {fecha_str}...")
        result = await gesad_client.get_fichajes_dia(fecha_str)

        if "error" in result or not isinstance(result, list):
            logger.warning(f"Error obteniendo fichajes del {fecha_str}: {result}")
            continue

        # Buscar el fichaje específico
        fichaje_buscado = None
        for fichaje in result:
            fichaje_id_api = fichaje.get('Fichaje_Id') or fichaje.get('FichajeId') or fichaje.get('Fichaje')
            if fichaje_id_api == fichaje_id:
                fichaje_buscado = fichaje
                break

        if fichaje_buscado:
            logger.info(f"\n{'='*80}")
            logger.info(f"FICHAJE {fichaje_id} ENCONTRADO - Fecha: {fecha_str}")
            logger.info(f"{'='*80}\n")

            # Mostrar todos los campos del fichaje relacionados con GPS
            logger.info("CAMPOS GPS DEL FICHAJE:")
            logger.info("-" * 80)
            for key in sorted(fichaje_buscado.keys()):
                if 'gps' in key.lower() or 'lat' in key.lower() or 'lon' in key.lower():
                    value = fichaje_buscado.get(key)
                    logger.info(f"  {key}: {value}")

            # Mostrar otros campos importantes
            logger.info("\nOTROS CAMPOS IMPORTANTES:")
            logger.info("-" * 80)
            for key in ['Fichaje_Id', 'Usuario_Id', 'Trabajador_Id', 'Hora_Ent_Fichaje',
                        'Hora_Sal_Fichaje', 'Hora_Ent_Prevista', 'Hora_Sal_Prevista',
                        'Metodo_Fichaje_Ent', 'Metodo_Fichaje_Salida']:
                value = fichaje_buscado.get(key)
                logger.info(f"  {key}: {value}")

            # Buscar el usuario y trabajador
            usuario_id = fichaje_buscado.get('Usuario_Id') or fichaje_buscado.get('UsuarioId')
            trabajador_id = fichaje_buscado.get('Trabajador_Id') or fichaje_buscado.get('TrabajadorId')

            logger.info(f"\nUsuario ID: {usuario_id}")
            logger.info(f"Trabajador ID: {trabajador_id}\n")

            # Obtener usuario del caché
            usuario = await cache_manager.get_usuario(usuario_id)
            if not usuario:
                logger.error(f"Usuario {usuario_id} no encontrado en caché")
                return

            logger.info(f"{'='*80}")
            logger.info(f"DATOS DEL USUARIO")
            logger.info(f"{'='*80}\n")

            # Mostrar campos GPS del usuario
            logger.info("CAMPOS GPS DEL USUARIO:")
            logger.info("-" * 80)
            for key in ['Gis_Latitud', 'Gis_Longitud', 'Latitud', 'Longitud', 'Direccion']:
                value = usuario.get(key)
                logger.info(f"  {key}: {value}")

            # Calcular distancia con la función actual
            from webhook_manager import webhook_manager

            logger.info(f"\n{'='*80}")
            logger.info(f"CÁLCULO DE DISTANCIA")
            logger.info(f"{'='*80}\n")

            ubicacion = webhook_manager._calcular_distancia(usuario, fichaje_buscado)

            logger.info("RESULTADO:")
            logger.info("-" * 80)
            for key, value in ubicacion.items():
                if isinstance(value, dict):
                    logger.info(f"  {key}:")
                    for k2, v2 in value.items():
                        logger.info(f"    {k2}: {v2}")
                else:
                    logger.info(f"  {key}: {value}")

            logger.info(f"\n{'='*80}")
            logger.info("RESUMEN")
            logger.info(f"{'='*80}")

            gps_fichaje_lat = fichaje_buscado.get('Fichaje_Ent_Gps_Lat') or fichaje_buscado.get('Fichaje_Sal_Gps_Lat')
            gps_fichaje_lon = fichaje_buscado.get('Fichaje_Ent_Gps_Lon') or fichaje_buscado.get('Fichaje_Sal_Gps_Lon')
            usuario_lat = usuario.get('Gis_Latitud')
            usuario_lon = usuario.get('Gis_Longitud')

            logger.info(f"GPS Fichaje: {gps_fichaje_lat}, {gps_fichaje_lon}")
            logger.info(f"GPS Usuario: {usuario_lat}, {usuario_lon}")
            logger.info(f"Distancia calculada: {ubicacion.get('distancia_metros')} metros")

            return

    logger.error(f"Fichaje {fichaje_id} no encontrado en los últimos {dias_buscar} días")


if __name__ == "__main__":
    fichaje_id = int(sys.argv[1]) if len(sys.argv) > 1 else 10679998
    dias = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    asyncio.run(investigar_fichaje(fichaje_id, dias))
