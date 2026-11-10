import re
import unicodedata

# Palabras de relleno conversacionales a ignorar
STOPWORDS = [
    "por favor", "porfa", "dame", "dar", "quiero", "necesito",
    "muestrame", "muestra", "mostrar", "generar", "genera", "generame",
    "sacar", "sacame", "consultar", "consulta", "traer", "traeme",
    "reporte", "informe", "resumen", "listado", "lista",
    "un", "una", "unos", "unas", "el", "la", "los", "las",
    "de", "del", "al", "a", "en", "para", "con", "sobre"
]

def eliminar_tildes(texto: str) -> str:
    """Elimina acentos y diacríticos preservando los caracteres ASCII base."""
    texto_norm = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in texto_norm if unicodedata.category(c) != 'Mn')

def normalizar_texto(texto: str, remover_stopwords: bool = True) -> str:
    """
    Normaliza el texto de entrada:
    1. Convierte a minúsculas.
    2. Elimina acentos/tildes.
    3. Reemplaza signos de puntuación por espacios.
    4. Opcionalmente elimina palabras de relleno conversacionales.
    5. Colapsa espacios múltiples.
    """
    if not texto:
        return ""

    # Minúsculas y eliminación de tildes
    t = eliminar_tildes(texto.lower().strip())

    # Remover signos de puntuación innecesarios
    t = re.sub(r'[^\w\s-]', ' ', t)

    if remover_stopwords:
        # Reemplazar frases stopwords de varias palabras primero
        for sw in sorted(STOPWORDS, key=lambda x: len(x), reverse=True):
            patron = r'\b' + re.escape(sw) + r'\b'
            t = re.sub(patron, ' ', t)

    # Colapsar espacios múltiples
    t = re.sub(r'\s+', ' ', t).strip()
    return t
