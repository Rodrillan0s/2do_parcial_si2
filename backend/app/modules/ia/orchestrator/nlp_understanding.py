"""
Motor de Comprensión Avanzada del Lenguaje Natural (NLP Understanding) para Aurora Advisor.
Procesa consultas en español (incluyendo variantes regionales de Bolivia, errores tipográficos,
expresiones coloquiales, múltiples restricciones, fechas relativas y referencias anafóricas).
"""

import re
import unicodedata
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from app.modules.ia.orchestrator.context_manager import ConversationSession

# Zona horaria oficial de Bolivia (UTC-4)
BOLIVIA_TZ = timezone(timedelta(hours=-4))


def get_bolivia_today() -> date:
    return datetime.now(BOLIVIA_TZ).date()


# Correcciones ortográficas y variantes regionales frecuentes
_TYPO_MAP = {
    r"\bbestidos?\b": "vestido",
    r"\bbentas?\b": "ventas",
    r"\binbentario\b": "inventario",
    r"\bdebolucion(es)?\b": "devolucion",
    r"\brebolso\b": "reembolso",
    r"\bsucurzal(es)?\b": "sucursal",
    r"\bpresios?\b": "precio",
    r"\bpoleras?\b": "blusa camisa",
    r"\bremeras?\b": "blusa camisa",
    r"\bchompas?\b": "sueter abrigo chaqueta",
    r"\bpulover\b": "sueter",
    r"\bpolleras?\b": "falda",
    r"\blevas?\b": "blazer traje",
    r"\bbaratito\b": "barato economico",
    r"\bplatita\b": "presupuesto",
    r"\blukas\b": "bolivianos",
    r"\bbs\.?\b": "bolivianos",
}

_CATEGORY_SYNONYMS = {
    "Vestidos": ["vestido", "vestidos", "solera", "gala", "vestido de noche", "vestido largo", "vestido corto"],
    "Blusas": ["blusa", "blusas", "top", "tops", "camisola", "polera de dama"],
    "Camisas": ["camisa", "camisas", "camisa formal", "camisa slim"],
    "Pantalones": ["pantalon", "pantalones", "jean", "jeans", "vaquero", "palazzo", "pantalon de vestir"],
    "Chaquetas": ["chaqueta", "chaquetas", "blazer", "blazers", "abrigo", "abrigos", "saco", "chompa", "sueter", "cardigan"],
    "Faldas": ["falda", "faldas", "pollera", "minifalda", "falda midi"],
    "Accesorios": ["accesorio", "accesorios", "cinturon", "cinturones", "cartera", "bolso", "bufanda", "pañuelo", "joyeria"],
    "Calzado": ["calzado", "zapato", "zapatos", "tacones", "sandalias", "botines", "mocasines"],
    "Trajes": ["traje", "trajes", "terno", "conjunto sastre", "smoking"],
}

_COLOR_LIST = [
    "negro", "blanco", "azul", "rojo", "verde", "amarillo", "rosa", "rosado",
    "beige", "marfil", "crema", "gris", "plateado", "dorado", "cafe", "marron",
    "celeste", "turquesa", "lila", "morado", "violeta", "vino", "borgona",
    "terracota", "coral", "naranja", "camel", "arena", "perla"
]

_LIGHT_COLORS = ["Blanco", "Beige", "Marfil", "Crema", "Rosa", "Celeste", "Perla", "Arena"]
_DARK_COLORS = ["Negro", "Azul", "Gris", "Vino", "Borgoña", "Café", "Marrón"]


def normalize_spanish_text(text: str) -> str:
    """Normaliza tildes, minúsculas, signos y corrige errores tipográficos comunes."""
    if not text:
        return ""
    lowered = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    for pattern, replacement in _TYPO_MAP.items():
        ascii_text = re.sub(pattern, replacement, ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def resolve_relative_period(text: str) -> Tuple[date, date, str]:
    """
    Resuelve expresiones temporales relativas en el backend usando la zona horaria de Bolivia.
    Nunca delega al LLM la invención de fechas.
    """
    hoy = get_bolivia_today()
    norm = normalize_spanish_text(text)

    if "ayer" in norm:
        ayer = hoy - timedelta(days=1)
        return ayer, ayer, "ayer"
    if "hoy" in norm or "dia de hoy" in norm:
        return hoy, hoy, "hoy"
    if "semana pasada" in norm or "ultima semana" in norm or "ultimos 7 dias" in norm:
        fin = hoy
        ini = hoy - timedelta(days=7)
        return ini, fin, "ultimos_7_dias"
    if "esta semana" in norm or "semana actual" in norm:
        ini = hoy - timedelta(days=hoy.weekday())
        return ini, hoy, "esta_semana"
    if "mes anterior" in norm or "mes pasado" in norm:
        primer_dia_este_mes = hoy.replace(day=1)
        ultimo_dia_mes_ant = primer_dia_este_mes - timedelta(days=1)
        primer_dia_mes_ant = ultimo_dia_mes_ant.replace(day=1)
        return primer_dia_mes_ant, ultimo_dia_mes_ant, "mes_pasado"
    if "ultimos 30 dias" in norm or "ultimo mes" in norm:
        return hoy - timedelta(days=30), hoy, "ultimos_30_dias"
    if "primer trimestre" in norm or "q1" in norm:
        return date(hoy.year, 1, 1), date(hoy.year, 3, 31), "primer_trimestre"
    if "segundo trimestre" in norm or "q2" in norm:
        return date(hoy.year, 4, 1), date(hoy.year, 6, 30), "segundo_trimestre"
    if "tercer trimestre" in norm or "q3" in norm:
        return date(hoy.year, 7, 1), date(hoy.year, 9, 30), "tercer_trimestre"
    if "cuarto trimestre" in norm or "q4" in norm:
        return date(hoy.year, 10, 1), date(hoy.year, 12, 31), "cuarto_trimestre"
    if "principios de ano" in norm or "este ano" in norm or "ano actual" in norm:
        return date(hoy.year, 1, 1), hoy, "este_anio"
    if "ano pasado" in norm or "ano anterior" in norm:
        y = hoy.year - 1
        return date(y, 1, 1), date(y, 12, 31), "anio_pasado"

    # Por defecto: este mes
    return hoy.replace(day=1), hoy, "este_mes"


def extract_query_constraints(text: str, session: Optional[ConversationSession] = None) -> Dict[str, Any]:
    """
    Extrae múltiples restricciones e intenciones de una consulta en lenguaje natural:
    - Categoría / prenda
    - Ocasión (boda, gala, cena formal, oficina, fiesta, casual, invierno)
    - Talla (XS, S, M, L, XL, XXL o numérica)
    - Colores preferidos (incluyendo 'colores claros' o 'colores oscuros')
    - Colores excluidos (ej. 'no quiero usar negro', 'sin rojo')
    - Rango de presupuesto (precio_min, precio_max en Bs.)
    - Sucursal mencionada
    - Género / público objetivo
    """
    norm = normalize_spanish_text(text)
    constraints: Dict[str, Any] = {
        "categoria": None,
        "termino": None,
        "ocasion": None,
        "talla": None,
        "colores": [],
        "colores_excluidos": [],
        "precio_min": None,
        "precio_max": None,
        "sucursal": None,
        "genero": None,
        "intenciones": [],
        "es_ambigua": False,
        "pregunta_aclaracion": None,
        "referencia_contextual": None
    }

    # 1. Detectar categoría
    for cat_canonical, keywords in _CATEGORY_SYNONYMS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", norm):
                constraints["categoria"] = cat_canonical
                constraints["termino"] = kw.rstrip("s") if len(kw) > 4 else kw
                break
        if constraints["categoria"]:
            break

    # 2. Detectar ocasión
    ocasiones_map = {
        "boda": ["boda", "matrimonio", "casamiento", "novia", "madrina"],
        "gala": ["gala", "alfombra roja", "evento de etiqueta", "graduacion", "recepcion"],
        "cena formal": ["cena formal", "cena elegante", "cena romantica", "aniversario", "velada"],
        "coctel": ["coctel", "cocktail", "brindis", "inauguracion"],
        "oficina": ["oficina", "trabajo", "ejecutivo", "ejecutiva", "reunion de negocios", "corporativo", "entrevista"],
        "fiesta": ["fiesta", "cumpleanos", "celebracion", "evento social"],
        "casual": ["casual", "diario", "fin de semana", "paseo", "universidad", "relajado"],
        "invierno": ["invierno", "frio", "otono", "abrigado"],
        "verano": ["verano", "calor", "primavera", "fresco", "playa"]
    }
    for oc_key, oc_words in ocasiones_map.items():
        if any(w in norm for w in oc_words):
            constraints["ocasion"] = oc_key
            break

    # 3. Detectar talla (ej. 'talla M', 'en M', 'usa talla L', 'talle S')
    m_talla = re.search(r"\b(?:talla|talle|size|en)\s+(xs|s|m|l|xl|xxl|36|38|40|42|44)\b", norm)
    if not m_talla:
        m_talla = re.search(r"\b(xs|xxl|xl)\b", norm)
    if m_talla:
        constraints["talla"] = m_talla.group(1).upper()

    # 4. Detectar colores excluidos (ej. 'no quiero usar negro', 'sin negro', 'menos negro', 'que no sea negro/negra')
    for col in _COLOR_LIST:
        col_stem = re.sub(r"o$", "[oa]", col)
        pat_excl = rf"\b(?:no\s+(?:quiero\s+)?(?:usar\s+|en\s+)?|sin\s+(?:color\s+)?|que\s+no\s+sea(?:n)?\s+|excepto\s+|menos\s+|no\s+){col_stem}s?\b"
        if re.search(pat_excl, norm):
            constraints["colores_excluidos"].append(col.capitalize())

    # 5. Detectar colores preferidos o gamas ('colores claros', 'tonos pastel', 'colores oscuros')
    if any(p in norm for p in ["colores claros", "tonos claros", "color claro", "tonos suaves", "tonos pastel"]):
        constraints["colores"].extend(_LIGHT_COLORS)
    elif any(p in norm for p in ["colores oscuros", "tonos oscuros", "color oscuro"]):
        constraints["colores"].extend(_DARK_COLORS)

    for col in _COLOR_LIST:
        if col.capitalize() in constraints["colores_excluidos"]:
            continue
        col_stem = re.sub(r"o$", "[oa]", col)
        if re.search(rf"\b{col_stem}s?\b", norm):
            c_cap = col.capitalize()
            if c_cap not in constraints["colores"]:
                constraints["colores"].append(c_cap)

    # 6. Detectar presupuesto / precios en Bolivianos
    # Rango: 'entre 150 y 400'
    m_range = re.search(r"\bentre\s+(\d+(?:[.,]\d+)?)\s*(?:y|a|-)\s*(\d+(?:[.,]\d+)?)", norm)
    if m_range:
        constraints["precio_min"] = float(m_range.group(1).replace(",", "."))
        constraints["precio_max"] = float(m_range.group(2).replace(",", "."))
    else:
        # Máximo: 'no quiero gastar mas de 500', 'menos de 500', 'presupuesto de 700', 'hasta 400', 'maximo 300'
        m_max = re.search(
            r"(?:no\s+(?:quiero\s+)?gastar\s+mas\s+de|menos\s+de|maximo|hasta|presupuesto\s+(?:de\s+|maximo\s+de\s+)?|tope\s+de|por\s+debajo\s+de)\s*(?:bs\.?|bolivianos)?\s*(\d+(?:[.,]\d+)?)",
            norm
        )
        if not m_max:
            m_max = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:bolivianos|bs)\s*(?:maximo|como\s+maximo|o\s+menos)?", norm)
        if m_max:
            constraints["precio_max"] = float(m_max.group(1).replace(",", "."))

        m_min = re.search(r"(?:mas\s+de|minimo|desde|arriba\s+de)\s*(?:bs\.?|bolivianos)?\s*(\d+(?:[.,]\d+)?)", norm)
        if m_min:
            constraints["precio_min"] = float(m_min.group(1).replace(",", "."))

    # 7. Detectar sucursal
    suc_patterns = [
        ("Equipetrol", ["equipetrol", "central equipetrol"]),
        ("Central", ["sucursal del centro", "sucursal central", "tienda del centro", "centro"]),
        ("Calacoto", ["calacoto", "la paz", "zona sur"]),
        ("Cochabamba", ["cochabamba", "jardin", "recoleta"]),
        ("Cristo Redentor", ["cristo redentor", "redentor"]),
    ]
    for suc_name, s_words in suc_patterns:
        if any(sw in norm for sw in s_words):
            constraints["sucursal"] = suc_name
            break

    # 8. Detectar género
    if any(w in norm for w in ["mujer", "dama", "damas", "femenino", "femenina", "novia", "vestido", "blusa", "falda"]):
        constraints["genero"] = "Damas"
    elif any(w in norm for w in ["hombre", "caballero", "caballeros", "masculino", "varon", "terno"]):
        constraints["genero"] = "Caballeros"
    elif any(w in norm for w in ["nino", "nina", "infantil", "bebe"]):
        constraints["genero"] = "Niños"

    # 9. Heredar slots de sesión si el usuario hace una consulta de seguimiento corta
    if session and session.slots:
        is_followup = any(w in norm for w in [
            "tambien", "y en", "que tal", "esos", "esas", "anteriores",
            "mas barato", "mas caro", "el primero", "el segundo", "parecido",
            "similar", "otra sucursal", "haz lo mismo"
        ])
        if is_followup:
            if not constraints["talla"] and session.slots.get("talla"):
                constraints["talla"] = session.slots["talla"]
            if not constraints["precio_max"] and session.slots.get("presupuesto_max"):
                constraints["precio_max"] = session.slots["presupuesto_max"]
            if not constraints["categoria"] and session.slots.get("categoria"):
                constraints["categoria"] = session.slots["categoria"]

    # 10. Detectar referencias contextuales a productos anteriores
    if session and session.last_products:
        ref = resolve_contextual_reference(norm, session.last_products)
        if ref:
            constraints["referencia_contextual"] = ref

    # 11. Detectar intenciones múltiples
    intenciones = detect_multiple_intents(norm, constraints)
    constraints["intenciones"] = intenciones

    # 12. Detectar ambigüedad cuando falta información crítica
    if norm in ("busca ropa para una fiesta", "quiero ropa para una fiesta", "ropa para fiesta", "busco ropa", "que tienes"):
        constraints["es_ambigua"] = True
        constraints["pregunta_aclaracion"] = (
            "Para recomendarte las piezas ideales para la fiesta, ¿me comentarías si buscas un estilo "
            "**de gala/noche**, **cóctel elegante** o **casual**, y si prefieres sección de **Damas** o **Caballeros**?"
        )

    return constraints


def resolve_contextual_reference(norm_text: str, last_products: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Resuelve referencias como 'el más barato', 'el más caro', 'el primero', 'el segundo',
    'ese', 'algo parecido a esta pero no tan cara'.
    """
    if not last_products:
        return None

    # ¿Cuál es el más barato?
    if any(p in norm_text for p in ["mas barato", "mas economico", "menor precio", "cual cuesta menos"]):
        sorted_by_price = sorted(last_products, key=lambda x: float(x.get("precio") or 999999))
        cheapest = sorted_by_price[0]
        return {
            "type": "cheapest",
            "target_product": cheapest,
            "all_compared": sorted_by_price
        }

    # ¿Cuál es el más caro?
    if any(p in norm_text for p in ["mas caro", "mayor precio", "mas exclusivo", "cual cuesta mas"]):
        sorted_by_price = sorted(last_products, key=lambda x: float(x.get("precio") or 0), reverse=True)
        most_exp = sorted_by_price[0]
        return {
            "type": "most_expensive",
            "target_product": most_exp,
            "all_compared": sorted_by_price
        }

    # Comparación de los productos anteriores
    if any(p in norm_text for p in ["comparalos", "compara esos", "compara los dos", "diferencia entre", "comparar"]):
        return {
            "type": "compare_previous",
            "products": last_products[:3]
        }

    # Posicionales: 'el primero', 'el segundo', 'el tercero'
    if re.search(r"\b(el\s+primero|la\s+primera|opcion\s+1)\b", norm_text):
        return {"type": "positional", "index": 0, "target_product": last_products[0]}
    if re.search(r"\b(el\s+segundo|la\s+segunda|opcion\s+2)\b", norm_text) and len(last_products) >= 2:
        return {"type": "positional", "index": 1, "target_product": last_products[1]}
    if re.search(r"\b(el\s+tercero|la\s+tercera|opcion\s+3)\b", norm_text) and len(last_products) >= 3:
        return {"type": "positional", "index": 2, "target_product": last_products[2]}

    # Similares más baratos: 'prendas parecidas a esta, pero que no sean tan caras' / 'algo parecido'
    if any(p in norm_text for p in ["parecida", "parecido", "similar", "similares", "como ese", "como esta"]):
        ref_prod = last_products[0]
        cheaper = any(w in norm_text for w in ["no sean tan caras", "no tan caro", "mas barato", "mas economico", "menor precio"])
        return {
            "type": "similar",
            "target_product": ref_prod,
            "cheaper_only": cheaper
        }

    # Disponibilidad por sucursal de la prenda en foco: '¿qué sucursal tiene más opciones de este vestido?'
    if any(p in norm_text for p in ["este vestido", "esta prenda", "ese vestido", "esa prenda", "ese producto"]) and "sucursal" in norm_text:
        return {
            "type": "branch_availability",
            "target_product": last_products[0]
        }

    return None


def detect_multiple_intents(norm_text: str, constraints: Dict[str, Any]) -> List[str]:
    """
    Identifica si una consulta del usuario combina varias operaciones de negocio en una misma frase.
    Ejemplo: '¿Qué productos se venden más y cuáles están por agotarse?'
    """
    intents: List[str] = []

    # Intenciones administrativas
    if any(k in norm_text for k in ["venden mas", "mas vendidos", "mayor rotacion", "top ventas", "productos estrella"]):
        intents.append("consultar_productos_mas_vendidos")
    if any(k in norm_text for k in ["venden menos", "baja rotacion", "sin rotacion", "inmovilizado", "estancado", "menos de lo esperado"]):
        intents.append("consultar_productos_sin_rotacion")
    if any(k in norm_text for k in ["por agotarse", "agotados", "stock bajo", "alerta de stock", "quiebre", "stock critico"]):
        intents.append("consultar_inventario_alertas")
    if any(k in norm_text for k in ["reponer primero", "deberia reponer", "reposicion", "reabastecer"]):
        intents.append("consultar_recomendaciones_reposicion_stock")
    if any(k in norm_text for k in ["demanda proyectada", "pronostico", "prediccion", "proyeccion de demanda"]):
        intents.append("consultar_demanda_proyectada")
    if any(k in norm_text for k in ["compara las ventas", "comparar ventas", "ventas de este mes con", "paso con las ventas"]):
        intents.append("consultar_ventas_por_periodo")
    elif any(k in norm_text for k in ["cuanto vendimos", "ventas de hoy", "ventas de la tienda", "facturacion", "ingresos"]):
        intents.append("consultar_ventas_empresa")

    # Intenciones de cliente
    if any(k in norm_text for k in ["conjunto", "outfit", "combinar", "cena formal", "para una boda", "para una gala", "que me pongo"]):
        if "recomendar_outfit_estilo" not in intents:
            intents.append("recomendar_outfit_estilo")
    if any(k in norm_text for k in ["sucursal tiene", "disponible en la sucursal", "stock por sucursal", "en que tienda hay"]):
        intents.append("consultar_disponibilidad_sucursal")
    if any(k in norm_text for k in ["parecidas", "parecido", "similares", "alternativas"]):
        intents.append("buscar_productos_similares")
    if any(k in norm_text for k in ["compara", "comparar", "diferencia entre"]) and "consultar_ventas_por_periodo" not in intents:
        intents.append("comparar_productos")
    if any(k in norm_text for k in ["promociones", "descuentos", "ofertas", "rebajas"]):
        intents.append("consultar_promociones")
    if any(k in norm_text for k in ["politica", "devolucion", "garantia", "cambio de talla", "envio", "metodos de pago"]):
        intents.append("consultar_politicas_devolucion")
    if any(k in norm_text for k in ["donde quedan", "ubicacion", "horarios de atencion", "direcciones de tiendas"]):
        intents.append("consultar_sucursales_tiendas")
    if any(k in norm_text for k in ["mis pedidos", "mis compras", "estado de mi pedido"]):
        intents.append("consultar_mis_pedidos")
    if any(k in norm_text for k in ["mis reservas", "mis apartados", "cita de probador"]):
        intents.append("consultar_mis_reservas")
    if any(k in norm_text for k in ["mis recomendaciones", "segun mis gustos", "segun mis compras", "para mi estilo"]):
        intents.append("consultar_mis_recomendaciones_personalizadas")

    # Si hay filtros de prenda (categoría, talla, color, precio, sucursal) y aún no hay búsqueda avanzada
    has_advanced_filters = any([
        constraints.get("talla"),
        constraints.get("colores"),
        constraints.get("colores_excluidos"),
        constraints.get("precio_max"),
        constraints.get("precio_min"),
        constraints.get("sucursal")
    ])
    if (constraints.get("categoria") or has_advanced_filters) and not intents:
        intents.append("buscar_prendas_avanzada")

    return intents
