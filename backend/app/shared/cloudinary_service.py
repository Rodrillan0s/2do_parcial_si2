import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv
from app.core.config import Config
from typing import Dict, Any, Optional

def inicializar_cloudinary():
    """
    Inicializa la configuración de Cloudinary usando las variables de entorno más recientes.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(base_dir, '.env'), override=True)
    load_dotenv(os.path.join(os.path.dirname(base_dir), '.env'), override=True)
    
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME") or getattr(Config, 'CLOUDINARY_CLOUD_NAME', None) or "dljz1f6ns"
    api_key = os.getenv("CLOUDINARY_API_KEY") or getattr(Config, 'CLOUDINARY_API_KEY', None) or "638117962672329"
    api_secret = os.getenv("CLOUDINARY_API_SECRET") or getattr(Config, 'CLOUDINARY_API_SECRET', None) or "cA7cmDDU-CDW8DkFaZ-Ym0P30KY"

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )

def probar_conexion_cloudinary() -> Dict[str, Any]:
    """
    Verifica la conectividad y validez de las credenciales con Cloudinary.
    """
    try:
        inicializar_cloudinary()
        # Intentamos obtener información de uso / ping
        ping_res = cloudinary.api.ping()
        usage_res = cloudinary.api.usage()
        cloud_name = cloudinary.config().cloud_name
        api_key = cloudinary.config().api_key
        return {
            "success": True,
            "message": "Conexión a Cloudinary establecida exitosamente.",
            "cloud_name": cloud_name,
            "api_key": api_key,
            "plan": usage_res.get('plan', 'Free'),
            "ping": ping_res.get('status', 'ok')
        }
    except Exception as e:
        error_msg = str(e)
        cloud_name = getattr(cloudinary.config(), 'cloud_name', None) or Config.CLOUDINARY_CLOUD_NAME
        api_key = getattr(cloudinary.config(), 'api_key', None) or Config.CLOUDINARY_API_KEY
        return {
            "success": False,
            "message": f"Error al conectar con Cloudinary: {error_msg}",
            "error_detail": error_msg,
            "cloud_name_usado": cloud_name,
            "api_key_usada": api_key
        }

# Límite máximo de peso permitido antes de procesamiento (en Megabytes)
MAX_FILE_SIZE_MB = 10.0

def _obtener_tamano_archivo(archivo) -> int:
    """
    Calcula el tamaño en bytes del archivo recibido en diferentes formatos
    (bytes, bytearray, file-like object o ruta en disco).
    """
    if isinstance(archivo, (bytes, bytearray)):
        return len(archivo)
    elif hasattr(archivo, 'seek') and hasattr(archivo, 'tell'):
        pos_actual = archivo.tell()
        archivo.seek(0, os.SEEK_END)
        tamano = archivo.tell()
        archivo.seek(pos_actual)
        return tamano
    elif isinstance(archivo, str) and os.path.exists(archivo):
        return os.path.getsize(archivo)
    return 0

def _validar_formato_imagen(archivo) -> bool:
    """
    Verifica los magic bytes iniciales para asegurar que el archivo sea una imagen válida.
    """
    header = b""
    if isinstance(archivo, (bytes, bytearray)):
        header = archivo[:32]
    elif hasattr(archivo, 'seek') and hasattr(archivo, 'read'):
        pos_actual = archivo.tell()
        header = archivo.read(32)
        archivo.seek(pos_actual)
    elif isinstance(archivo, str) and os.path.exists(archivo):
        try:
            with open(archivo, 'rb') as f:
                header = f.read(32)
        except Exception:
            return True

    if not header:
        return True

    # JPEG: \xff\xd8\xff
    if header.startswith(b'\xff\xd8\xff'):
        return True
    # PNG: \x89PNG\r\n\x1a\n
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return True
    # GIF: GIF87a / GIF89a
    if header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
        return True
    # WEBP: RIFF....WEBP
    if header.startswith(b'RIFF') and b'WEBP' in header[:16]:
        return True
    # SVG o XML
    if b'<svg' in header.lower() or b'<?xml' in header.lower():
        return True
    # BMP: BM
    if header.startswith(b'BM'):
        return True

    return False

def subir_imagen_cloudinary(
    archivo, 
    folder: str = "aurora_store/general", 
    public_id: Optional[str] = None,
    max_size_mb: float = MAX_FILE_SIZE_MB,
    max_dimension: int = 1920,
    calidad: str = "auto:good"
) -> Dict[str, Any]:
    """
    Sube un archivo de imagen a Cloudinary con las siguientes garantías:
    1. Control de peso: Rechaza archivos que superen el límite máximo (por defecto 10 MB).
    2. Validación de formato: Verifica magic bytes para admitir solo imágenes válidas.
    3. Redimensionamiento prudente (crop: 'limit'): Si la imagen excede 'max_dimension' (ej. 1920px),
       se reduce proporcionalmente conservando el 100% de la relación de aspecto (ancho/alto)
       sin deformar, estirar ni recortar la prenda. Si la imagen es menor, no se altera.
    4. Compresión visualmente sin pérdidas ('quality': 'auto:good'): Aplica algoritmos de
       percepción humana para aligerar significativamente los KB sin perder nitidez en alta costura.
    """
    inicializar_cloudinary()

    # 1. Validación de tamaño máximo
    tamano_bytes = _obtener_tamano_archivo(archivo)
    limite_bytes = int(max_size_mb * 1024 * 1024)
    if tamano_bytes > limite_bytes:
        tamano_mb = round(tamano_bytes / (1024 * 1024), 2)
        raise ValueError(
            f"El archivo es demasiado pesado ({tamano_mb} MB). El tamaño máximo permitido es de {max_size_mb} MB."
        )

    # 2. Validación de formato de imagen
    if not _validar_formato_imagen(archivo):
        raise ValueError(
            "El archivo proporcionado no es una imagen válida. Formatos admitidos: JPG, PNG, WEBP, GIF, SVG."
        )

    # 3. Configuración de subida y transformaciones inteligentes
    opciones = {
        "folder": folder,
        "resource_type": "image",
        "overwrite": True,
        "transformation": [
            # Redimensiona solo si supera el ancho/alto máximo, manteniendo estrictamente el ratio
            {"width": max_dimension, "height": max_dimension, "crop": "limit"},
            # Optimización inteligente de peso sin pérdida de calidad perceptible
            {"quality": calidad},
            # Formato de entrega óptimo según el dispositivo
            {"fetch_format": "auto"}
        ]
    }
    if public_id:
        opciones["public_id"] = public_id

    resultado = cloudinary.uploader.upload(archivo, **opciones)
    bytes_finales = resultado.get("bytes", 0)

    return {
        "url": resultado.get("secure_url") or resultado.get("url"),
        "secure_url": resultado.get("secure_url") or resultado.get("url"),
        "public_id": resultado.get("public_id"),
        "formato": resultado.get("format"),
        "ancho": resultado.get("width"),
        "alto": resultado.get("height"),
        "bytes": bytes_finales,
        "bytes_originales": tamano_bytes if tamano_bytes > 0 else bytes_finales,
        "ahorro_peso_porcentaje": round(
            (1 - (bytes_finales / tamano_bytes)) * 100, 1
        ) if tamano_bytes > bytes_finales and tamano_bytes > 0 else 0
    }

def eliminar_imagen_cloudinary(public_id: str) -> Dict[str, Any]:
    """
    Elimina una imagen de Cloudinary por su public_id.
    """
    inicializar_cloudinary()
    return cloudinary.uploader.destroy(public_id)
