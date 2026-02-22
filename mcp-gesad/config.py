import os
import logging
import pytz
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class Config:
    """Configuración centralizada del MCP server GESAD"""
    
    # Timezone Configuration
    TIMEZONE = os.getenv("GESAD_TIMEZONE", "Europe/Madrid")
    TZ = pytz.timezone(TIMEZONE)
    
    # API Configuration
    CONEX_NAME: str = os.getenv("GESAD_CONEX_NAME", "CLOUD01")
    AUTH_CODE: str = os.getenv("GESAD_AUTH_CODE", "")
    BASIC_AUTH: str = os.getenv("GESAD_BASIC_AUTH", "dXNlcndzX2FydHJpczpKZk4yM1BiI1FCJjFKejY=")  # userws_artris:JfN23Pb#QB&1Jz6
    API_CODE: str = os.getenv("GESAD_API_CODE", "ARTRIS_4Jk#pL%1@")
    SESSION_ID: str = os.getenv("GESAD_SESSION_ID", "R0_F5FB07C4-0E63-4A7A-BA8A-43108D19224B")
    BASE_URL: str = os.getenv("GESAD_BASE_URL", "https://data-bi.ayudadomiciliaria.com/api")
    
    # Schedule Configuration
    ACTIVE_START: int = int(os.getenv("GESAD_ACTIVE_START", "6"))
    ACTIVE_END: int = int(os.getenv("GESAD_ACTIVE_END", "24"))  # Medianoche (24:00)
    CHECK_INTERVAL: int = int(os.getenv("GESAD_CHECK_INTERVAL", "20"))
    
    # Umbrales de tiempo (en minutos) - Configurables desde .env
    UMBRAL_LLEGADA_ADELANTADA = int(os.getenv("GESAD_UMBRAL_LLEGADA_ADELANTADA", "20"))  # Minutos antes del inicio
    UMBRAL_RETRASO_AUSENCIA = int(os.getenv("GESAD_UMBRAL_RETRASO_AUSENCIA", "20"))  # Minutos después del inicio
    UMBRAL_SALIDA_ADELANTADA = int(os.getenv("GESAD_UMBRAL_SALIDA_ADELANTADA", "10"))  # Minutos antes del fin
    UMBRAL_SALIDA_TARDE = int(os.getenv("GESAD_UMBRAL_SALIDA_TARDE", "10"))  # Minutos después del fin
    
    # Umbral de distancia GPS (en metros) - Configurable desde .env
    # Valor por defecto: 50 metros
    UMBRAL_DISTANCIA_UBICACION = int(os.getenv("GESAD_UMBRAL_DISTANCIA_UBICACION", "50"))
    
    # Valor que identifica servicios de acompañamiento
    SERVICIO_ACOMPANAMIENTO = "BASE"  # Valor del campo Servicio_Origen
    
    # Cache Configuration
    CACHE_DIR: str = os.getenv("GESAD_CACHE_DIR", "./cache")
    CACHE_PERSISTENT_DAYS: int = int(os.getenv("GESAD_CACHE_PERSISTENT_DAYS", "7"))
    
    # API Limits
    DAILY_LIMIT: int = int(os.getenv("GESAD_DAILY_LIMIT", "500"))
    EMERGENCY_BUFFER: int = int(os.getenv("GESAD_EMERGENCY_BUFFER", "50"))
    
    # Performance Settings
    REQUEST_TIMEOUT: int = int(os.getenv("GESAD_REQUEST_TIMEOUT", "30"))
    BATCH_SIZE: int = int(os.getenv("GESAD_BATCH_SIZE", "20"))
    RETRY_ATTEMPTS: int = int(os.getenv("GESAD_RETRY_ATTEMPTS", "3"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("GESAD_LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> bool:
        """Validar configuración requerida"""
        
        if not cls.CONEX_NAME:
            raise ValueError("GESAD_CONEX_NAME es requerido")
        
        if not cls.BASIC_AUTH:
            raise ValueError("GESAD_BASIC_AUTH es requerido")
        
        if not cls.API_CODE:
            raise ValueError("GESAD_API_CODE es requerido")
        
        if not cls.SESSION_ID:
            raise ValueError("GESAD_SESSION_ID es requerido")
        
        return True
    
    @classmethod
    def get_local_time(cls, utc_time: Optional[datetime] = None) -> datetime:
        """Convertir UTC a hora local (Europe/Madrid)"""
        if utc_time is None:
            utc_time = datetime.now(timezone.utc)
        elif utc_time.tzinfo is None:
            utc_time = utc_time.replace(tzinfo=timezone.utc)
        
        return utc_time.astimezone(cls.TZ)
    
    @classmethod
    def is_active_time(cls, current_time: Optional[datetime] = None) -> bool:
        """Verificar si estamos en horario activo (6:00 AM - 12:00 PM Madrid)"""
        if current_time is None:
            current_time = cls.get_local_time()
        elif current_time.tzinfo is None:
            current_time = cls.get_local_time(current_time)
        
        return cls.ACTIVE_START <= current_time.hour < cls.ACTIVE_END
    
    @classmethod
    def get_check_interval_seconds(cls) -> int:
        """Obtener intervalo de verificación en segundos"""
        return cls.CHECK_INTERVAL * 60  # Convertir minutos a segundos
    
    @classmethod
    def get_next_active_time(cls) -> datetime:
        """Obtener próxima fecha y hora de activación en horario Madrid"""
        now = cls.get_local_time()
        
        if now.hour < cls.ACTIVE_START:
            # Hoy aún no ha comenzado el horario activo
            next_active = now.replace(hour=cls.ACTIVE_START, minute=0, second=0, microsecond=0)
        elif now.hour >= cls.ACTIVE_END:
            # Ya pasó el horario activo hoy, activar mañana
            next_active = now.replace(hour=cls.ACTIVE_START, minute=0, second=0, microsecond=0)
            next_active += timedelta(days=1)
        else:
            # Estamos en horario activo
            next_active = now + timedelta(minutes=cls.CHECK_INTERVAL)
        
        return next_active
    
    @classmethod
    def get_time_until_active(cls) -> timedelta:
        """Obtener tiempo hasta próxima activación (en horario Madrid)"""
        now = cls.get_local_time()
        next_active = cls.get_next_active_time()
        return next_active - now
    
    @classmethod
    def get_endpoints(cls) -> dict:
        """Obtener endpoints configurados"""
        return {
            'fichajes': f'/ControlPresencia/Fichajes/{cls.SESSION_ID}',
            'trabajador': f'/Trabajadores/Expedientes/{cls.SESSION_ID}/ID',
            'usuario': f'/Usuarios/Expedientes/{cls.SESSION_ID}/ID'
        }
    
    # Webhook Configuration
    WEBHOOK_URL: str = os.getenv("GESAD_WEBHOOK_URL", "")
    WEBHOOK_ENABLED: bool = os.getenv("GESAD_WEBHOOK_ENABLED", "false").lower() == "true"
    WEBHOOK_TIMEOUT: int = int(os.getenv("GESAD_WEBHOOK_TIMEOUT", "30"))
    WEBHOOK_EVENTS: str = os.getenv("GESAD_WEBHOOK_EVENTS", "ausencia,cambio_estado,llegada_tarde,fichaje_manual,retraso_confirmado,salida_adelantada,salida_tarde,ubicacion_fuera_rango")
    
    @classmethod
    def get_webhook_events(cls) -> list:
        """Obtener lista de eventos de webhook habilitados"""
        return [e.strip() for e in cls.WEBHOOK_EVENTS.split(",") if e.strip()]
    
    @classmethod
    def is_webhook_event_enabled(cls, event: str) -> bool:
        """Verificar si un evento específico está habilitado"""
        return event in cls.get_webhook_events()
    
    @classmethod
    def reload_from_env(cls):
        """Recargar variables de entorno desde el archivo .env"""
        import os
        logger.info("🔄 Recargando configuración desde .env")
        
        cls.SESSION_ID = os.getenv("GESAD_SESSION_ID", "")
        cls.TIMEZONE = os.getenv("GESAD_TIMEZONE", "Europe/Madrid")
        cls.ACTIVE_START = int(os.getenv("GESAD_ACTIVE_START", "6"))
        cls.ACTIVE_END = int(os.getenv("GESAD_ACTIVE_END", "24"))
        cls.CHECK_INTERVAL = int(os.getenv("GESAD_CHECK_INTERVAL", "20"))
        cls.WEBHOOK_URL = os.getenv("GESAD_WEBHOOK_URL", "")
        cls.WEBHOOK_ENABLED = os.getenv("GESAD_WEBHOOK_ENABLED", "false").lower() == "true"
        cls.WEBHOOK_TIMEOUT = int(os.getenv("GESAD_WEBHOOK_TIMEOUT", "30"))
        cls.WEBHOOK_EVENTS = os.getenv("GESAD_WEBHOOK_EVENTS", "ausencia,cambio_estado,llegada_tarde,resumen_diario")
        
        logger.info(f"   ✅ WEBHOOK_URL: {cls.WEBHOOK_URL}")
        logger.info(f"   ✅ WEBHOOK_ENABLED: {cls.WEBHOOK_ENABLED}")
        logger.info(f"   ✅ WEBHOOK_EVENTS: {cls.WEBHOOK_EVENTS}")
        logger.info("✅ Configuración recargada")



# Configuración global
config = Config()