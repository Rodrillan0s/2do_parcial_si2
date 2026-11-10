import json
import logging
import re
import requests
from decimal import Decimal
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
import psycopg2
from app.core.config import Config

logger = logging.getLogger(__name__)

def get_db_connection():
    return psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        connect_timeout=10
    )


# =====================================================================
# HERRAMIENTAS DISPONIBLES (OPENAI / DEEPSEEK FUNCTION CALLING SPEC)
# =====================================================================

CLIENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_prendas_catalogo",
            "description": "Busca prendas y artículos en el catálogo de Aurora Store por término, categoría, género (Damas, Caballeros, Unisex) o precio máximo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "termino": {"type": "string", "description": "Término de búsqueda (ej. 'vestido', 'camisa', 'pantalón slim', 'seda')"},
                    "categoria": {"type": "string", "description": "Nombre de la categoría (ej. 'Vestidos', 'Camisas', 'Pantalones')"},
                    "genero": {"type": "string", "enum": ["Damas", "Caballeros", "Unisex", "Niños"], "description": "Género o sección"},
                    "precio_max": {"type": "number", "description": "Precio máximo en Bolivianos (Bs.)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recomendar_outfit_estilo",
            "description": "Asesora y sugiere combinaciones exclusivas de prendas (outfits) para ocasiones específicas (gala, cóctel, oficina, casual, cena romántica, temporada otoño-invierno, etc.), combinando prendas, colores y accesorios a juego.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ocasion": {"type": "string", "description": "Ocasión del evento (ej. 'gala', 'casual', 'oficina', 'coctel', 'boda', 'invierno', 'cena')"},
                    "genero": {"type": "string", "enum": ["Damas", "Caballeros", "Unisex"], "description": "Género del destinatario"},
                    "estilo_preferido": {"type": "string", "description": "Estilo preferido (ej. 'elegante', 'minimalista', 'moderno', 'vanguardista', 'clasico')"},
                    "presupuesto_max": {"type": "number", "description": "Presupuesto máximo aproximado en Bolivianos (Bs.)"}
                },
                "required": ["ocasion"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_politicas_devolucion",
            "description": "Consulta las políticas de compras, cambios de talla, garantías por fallas de fábrica, duración de reservas en tienda física (48 horas), métodos de pago y tiempos de entrega de Aurora Store en Bolivia.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tema": {
                        "type": "string",
                        "enum": ["cambios_talla", "garantias_devoluciones", "reservas_vigencia", "envios_tiempos", "cuidados_prendas", "metodos_pago", "general"],
                        "description": "Tema específico de la consulta sobre políticas o servicios"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_prendas_avanzada",
            "description": "Búsqueda avanzada y detallada en catálogo filtrando por talla, color, rango de precios, sucursal disponible o temporada.",
            "parameters": {
                "type": "object",
                "properties": {
                    "termino": {"type": "string", "description": "Palabra clave o modelo"},
                    "categoria": {"type": "string", "description": "Categoría de la prenda"},
                    "talla": {"type": "string", "description": "Talla buscada (ej. XS, S, M, L, XL)"},
                    "color": {"type": "string", "description": "Color deseado (ej. Negro, Blanco, Beige, Terracota)"},
                    "precio_min": {"type": "number", "description": "Precio mínimo en Bs."},
                    "precio_max": {"type": "number", "description": "Precio máximo en Bs."},
                    "sucursal": {"type": "string", "description": "Nombre de la sucursal preferida"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_detalle_prenda",
            "description": "Obtiene la información detallada de una prenda: precio, tallas disponibles, colores y existencias en tiendas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id_producto": {"type": "integer", "description": "ID numérico del producto si se conoce"},
                    "nombre_prenda": {"type": "string", "description": "Nombre aproximado o código de la prenda"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_sucursales_tiendas",
            "description": "Lista las sucursales y tiendas físicas activas de Aurora Store con sus direcciones, horarios y teléfonos.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_mis_pedidos",
            "description": "Consulta el historial de pedidos y compras realizados por el cliente autenticado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limite": {"type": "integer", "description": "Cantidad de pedidos a consultar (por defecto 5)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_mis_reservas",
            "description": "Consulta las reservas activas de prendas del cliente autenticado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limite": {"type": "integer", "description": "Cantidad de reservas a consultar (por defecto 5)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_mis_recomendaciones_personalizadas",
            "description": "Obtiene las recomendaciones de prendas personalizadas por Machine Learning basadas en las compras anteriores, gustos, tallas habituales y paleta cromática del cliente autenticado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limite": {"type": "integer", "description": "Cantidad de recomendaciones a devolver (por defecto 4)"}
                }
            }
        }
    }
]

ADMIN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_ventas_empresa",
            "description": "Consulta las ventas, facturación total, ticket promedio y cantidad de transacciones de la empresa en un periodo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "periodo": {
                        "type": "string", 
                        "enum": ["hoy", "ayer", "esta_semana", "este_mes", "ultimos_30_dias"],
                        "description": "Periodo temporal a consultar"
                    },
                    "sucursal": {"type": "string", "description": "Nombre o fragmento de la sucursal (opcional)"}
                },
                "required": ["periodo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_inventario_alertas",
            "description": "Consulta el estado del inventario físico, prendas agotadas o con stock bajo respecto al mínimo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filtro": {
                        "type": "string", 
                        "enum": ["agotados", "bajo_stock", "todos"],
                        "description": "Condición del stock a filtrar"
                    },
                    "sucursal": {"type": "string", "description": "Nombre o fragmento de la sucursal (opcional)"}
                },
                "required": ["filtro"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_devoluciones_reclamos",
            "description": "Audita y resume las devoluciones y reclamos de clientes en tiendas u online en un periodo determinado, detallando motivos y montos reembolsados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "periodo": {
                        "type": "string",
                        "enum": ["hoy", "esta_semana", "este_mes", "ultimos_30_dias", "todos"],
                        "description": "Periodo a evaluar"
                    },
                    "sucursal": {"type": "string", "description": "Nombre o fragmento de la sucursal (opcional)"},
                    "motivo": {"type": "string", "description": "Motivo particular de la devolución (opcional)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_recomendaciones_reposicion_stock",
            "description": "Genera recomendaciones inteligentes de reabastecimiento para prendas críticas con alta rotación de ventas y bajo inventario en tiendas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sucursal": {"type": "string", "description": "Nombre o fragmento de la sucursal (opcional)"},
                    "categoria": {"type": "string", "description": "Filtrar por categoría (opcional)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_reporte_motor_analitico",
            "description": "Ejecuta cualquier reporte canónico o consulta en lenguaje natural a través del Motor Canónico de Reportes (ventas, rentabilidad, rendimiento de cajeros, stock inmovilizado, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "comando_o_reporte": {
                        "type": "string",
                        "description": "Consulta analítica (ej. 'rentabilidad del mes por producto', 'rendimiento de cajeros hoy', 'stock inmovilizado con mayor capital')"
                    }
                },
                "required": ["comando_o_reporte"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_ventas_pendientes",
            "description": "Consulta las ventas y pedidos pendientes de pago, con clientes deudores, total por cobrar y días de antigüedad.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sucursal": {"type": "string", "description": "Nombre de la sucursal (opcional)"},
                    "canal": {"type": "string", "enum": ["todos", "pos", "online"], "description": "Canal de venta"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_reservas_prendas_empresa",
            "description": "Consulta prendas apartadas/reservadas en tiendas físicas, fechas de visita y vigencia para cobranza o liberación de stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sucursal": {"type": "string", "description": "Nombre de la sucursal (opcional)"},
                    "vigencia": {"type": "string", "enum": ["vigente", "vencida", "todas"], "description": "Estado de vigencia"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_auditoria_pos_errores",
            "description": "Auditoría de ventas en mostrador/caja POS para encontrar errores, ventas sin pago registrado o descuadres de cajeros.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sucursal": {"type": "string", "description": "Nombre de la sucursal (opcional)"},
                    "solo_alertas": {"type": "boolean", "description": "Si es True, devuelve solo ventas con advertencias o no cobradas"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_indicadores_kpi_generales",
            "description": "Obtiene los principales indicadores de rendimiento (KPIs) del negocio: ingresos totales, margen, productos activos y pedidos.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generar_reporte_directo",
            "description": "Genera o resume un reporte formal de ventas, inventario, pagos, caja, devoluciones o rentabilidad.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo_reporte": {
                        "type": "string",
                        "enum": ["ventas", "inventario", "pagos", "caja", "devoluciones", "rentabilidad", "rendimiento_personal", "stock_inmovilizado"],
                        "description": "Tipo de reporte solicitado"
                    },
                    "periodo": {"type": "string", "description": "Periodo o rango de fechas (ej. 'este_mes', 'hoy', 'ano_pasado')"}
                },
                "required": ["tipo_reporte"]
            }
        }
    }
]


# =====================================================================
# EJECUCIÓN PARAMETRIZADA DE HERRAMIENTAS (POSTGRESQL MULTI-TENANT)
# =====================================================================

def _ejecutar_buscar_prendas(args: dict, id_empresa: int) -> dict:
    termino = str(args.get("termino") or "").strip()
    categoria = str(args.get("categoria") or "").strip()
    genero = str(args.get("genero") or "").strip()
    precio_max = args.get("precio_max")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT
                p.id_producto,
                p.nombre,
                p.codigo_producto,
                COALESCE(p.precio, 0) as precio,
                COALESCE(c.nombre, 'Moda') as categoria,
                COALESCE(p.genero, 'Unisex') as genero,
                p.imagen_url,
                p.descripcion,
                COALESCE(SUM(inv.stock_disponible), 0) as stock_total
            FROM comercio.t_producto p
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            LEFT JOIN comercio.t_producto_talla_color ptc ON p.id_producto = ptc.id_producto
            LEFT JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
            WHERE p.id_empresa = %s AND p.activo = true
        """
        params: List[Any] = [id_empresa]

        if termino:
            sql += " AND (p.nombre ILIKE %s OR p.descripcion ILIKE %s OR p.codigo_producto ILIKE %s)"
            t_pattern = f"%{termino}%"
            params.extend([t_pattern, t_pattern, t_pattern])

        if categoria:
            sql += " AND c.nombre ILIKE %s"
            params.append(f"%{categoria}%")

        if genero:
            sql += " AND p.genero ILIKE %s"
            params.append(f"%{genero}%")

        if precio_max:
            sql += " AND p.precio <= %s"
            params.append(float(precio_max))

        sql += """
            GROUP BY p.id_producto, p.nombre, p.codigo_producto, p.precio, c.nombre, p.genero, p.imagen_url, p.descripcion
            ORDER BY p.id_producto DESC
            LIMIT 8
        """

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        productos = []
        for r in rows:
            cur.execute("""
                SELECT DISTINCT t.nombre as talla, col.nombre as color
                FROM comercio.t_producto_talla_color ptc
                LEFT JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
                LEFT JOIN comercio.t_color col ON ptc.id_color = col.id_color
                WHERE ptc.id_producto = %s
            """, (r[0],))
            vars_data = cur.fetchall()
            tallas = sorted(list({v[0] for v in vars_data if v[0]}))
            colores = sorted(list({v[1] for v in vars_data if v[1]}))

            productos.append({
                "id_producto": r[0],
                "nombre": r[1],
                "codigo": r[2],
                "precio": float(r[3]),
                "categoria": r[4],
                "genero": r[5],
                "imagen_url": r[6] or "assets/images/default-fashion.jpg",
                "descripcion": r[7] or "",
                "stock_disponible": int(r[8]),
                "tallas": tallas,
                "colores": colores
            })

        return {
            "total_encontrados": len(productos),
            "productos": productos
        }
    finally:
        conn.close()


def _ejecutar_recomendar_outfit(args: dict, id_empresa: int) -> dict:
    ocasion = str(args.get("ocasion") or "evento especial").strip().lower()
    genero = str(args.get("genero") or "").strip()
    estilo = str(args.get("estilo_preferido") or "elegante y refinado").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        kw_principal = ["vestido", "traje", "blazer", "conjunto"]
        if any(w in ocasion for w in ["casual", "diario", "paseo", "fin de semana"]):
            kw_principal = ["blusa", "pantalon", "falda", "camisa", "sueter"]
        elif any(w in ocasion for w in ["oficina", "trabajo", "ejecutivo", "reunion"]):
            kw_principal = ["blazer", "traje", "camisa", "pantalon vestir"]
        elif any(w in ocasion for w in ["invierno", "frio", "otono"]):
            kw_principal = ["abrigo", "chaqueta", "sueter", "blazer"]

        sql_base = """
            SELECT DISTINCT
                p.id_producto,
                p.nombre,
                COALESCE(p.precio, 0) as precio,
                COALESCE(c.nombre, 'Moda') as categoria,
                p.imagen_url,
                p.descripcion
            FROM comercio.t_producto p
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            WHERE p.id_empresa = %s AND p.activo = true
        """
        params_base: List[Any] = [id_empresa]

        if genero:
            sql_base += " AND (p.genero ILIKE %s OR p.genero = 'Unisex')"
            params_base.append(f"%{genero}%")

        cur.execute(sql_base + " ORDER BY p.id_producto DESC LIMIT 20", tuple(params_base))
        todas_las_prendas = cur.fetchall()

        prendas_outfit = []
        prendas_accesorios = []

        for p_row in todas_las_prendas:
            p_id, p_nom, p_prec, p_cat, p_img, p_desc = p_row
            item = {
                "id_producto": p_id,
                "nombre": p_nom,
                "precio": float(p_prec),
                "categoria": p_cat,
                "imagen_url": p_img or "assets/images/default-fashion.jpg",
                "descripcion": p_desc or ""
            }
            nom_lower = p_nom.lower()
            cat_lower = p_cat.lower()

            if any(k in nom_lower or k in cat_lower for k in ["accesorio", "cartera", "bolso", "cinturon", "calzado", "zapato"]):
                if len(prendas_accesorios) < 2:
                    prendas_accesorios.append(item)
            elif any(k in nom_lower or k in cat_lower for k in kw_principal):
                if len(prendas_outfit) < 3:
                    prendas_outfit.append(item)

        if not prendas_outfit:
            prendas_outfit = [{
                "id_producto": p[0], "nombre": p[1], "precio": float(p[2]),
                "categoria": p[3], "imagen_url": p[4] or "assets/images/default-fashion.jpg",
                "descripcion": p[5] or ""
            } for p in todas_las_prendas[:3]]

        total_look = sum(item["precio"] for item in prendas_outfit + prendas_accesorios)

        consejos = {
            "gala": "Te sugerimos siluetas fluidas o estructuradas con caída limpia, complementadas con joyas sobrias que estilicen la figura sin restar protagonismo al diseño.",
            "oficina": "Opta por sastrería fina combinando un blazer estructurado con piezas livianas para proyectar liderazgo, sofisticación y comodidad durante el día.",
            "coctel": "Un balance perfecto entre modernidad y etiqueta. Los tonos como borgoña, zafiro o negro noche acompañados de un bolso de mano causan gran distinción.",
            "casual": "Elegancia relajada: fibras nobles como algodón o seda suave en cortes holgados, armonizados con calzado y accesorios en tonos tierra o marfil.",
            "invierno": "Layering o superposición estratégica: un abrigo de paño o chaqueta entallada sobre prendas de punto fino para abrigarte con un porte impecable."
        }
        consejo_texto = next((c for k, c in consejos.items() if k in ocasion), "Prioriza el equilibrio de texturas y una paleta cromática sobria para un acabado estilístico pulcro.")

        return {
            "ocasion": ocasion.capitalize(),
            "estilo": estilo.capitalize(),
            "piezas_principales": prendas_outfit,
            "complementos_accesorios": prendas_accesorios,
            "presupuesto_estimado_bs": round(total_look, 2),
            "consejo_estilismo": consejo_texto,
            "productos": prendas_outfit + prendas_accesorios
        }
    finally:
        conn.close()


def _ejecutar_consultar_politicas(args: dict) -> dict:
    tema = (args.get("tema") or "general").strip().lower()

    politicas = {
        "cambios_talla": {
            "titulo": "Política de Cambios de Talla y Modelo",
            "plazo": "15 días calendario a partir de la entrega o compra en tienda.",
            "condiciones": [
                "Prenda sin uso, sin lavar y con etiquetas originales adheridas.",
                "Presentación de la factura física, ticket electrónico o código de reserva.",
                "El cambio puede realizarse en cualquiera de nuestras sucursales a nivel nacional."
            ]
        },
        "garantias_devoluciones": {
            "titulo": "Garantía de Calidad y Devoluciones",
            "plazo": "30 días calendario por fallas o defectos de confección/fábrica.",
            "condiciones": [
                "Evaluación técnica inmediata en sucursal o mediante fotografía con atención al cliente.",
                "Opción de cambio inmediato por prenda idéntica, nota de crédito sin vencimiento o reembolso.",
                "No cubre desgaste natural por uso indebido o lavado contrario a la etiqueta de cuidado."
            ]
        },
        "reservas_vigencia": {
            "titulo": "Vigencia de Reservas en Tienda Física",
            "plazo": "48 horas continuas de reserva exclusiva garantizada.",
            "condiciones": [
                "Sin costo por adelantado; probador privado asignado en la sucursal seleccionada.",
                "Recibirás recordatorio por SMS/WhatsApp antes de que el stock reservado sea liberado.",
                "Posibilidad de extender la reserva 24h adicionales notificando a la tienda."
            ]
        },
        "envios_tiempos": {
            "titulo": "Tiempos y Métodos de Entrega en Bolivia",
            "plazo": "Santa Cruz: 24 horas. La Paz y Cochabamba: 24 a 48 horas hábiles.",
            "condiciones": [
                "Empaque de alta costura con estuche protector rígido antipolvo.",
                "Seguimiento en tiempo real con número de guía vía transporte expreso.",
                "Envío gratuito en compras superiores a Bs. 600."
            ]
        },
        "cuidados_prendas": {
            "titulo": "Guía de Cuidado de Prendas de Alta Costura",
            "plazo": "Recomendaciones permanentes para preservar texturas y colores.",
            "condiciones": [
                "Prendas de lino, lana virgen o seda: Limpieza en seco recomendada en tintorería especializada.",
                "Planchado al vapor a baja temperatura con paño intermedio para evitar brillos en el tejido.",
                "Guardar en perchas anchas acolchadas para mantener la estructura original del hombro."
            ]
        },
        "metodos_pago": {
            "titulo": "Métodos de Pago Aceptados",
            "plazo": "Acreditación inmediata y segura.",
            "condiciones": [
                "Tarjetas de Débito y Crédito (Visa, Mastercard, Red Enlace).",
                "Pago mediante código QR Simple (Banco Unión, BCP, BNB, Mercantil Santa Cruz, etc.).",
                "Efectivo en Bolivianos (Bs.) o Dólares (al tipo de cambio oficial) en sucursales físicas."
            ]
        }
    }

    if tema in politicas:
        return politicas[tema]

    return {
        "titulo": "Políticas Generales y Compromiso de Servicio Aurora Store",
        "resumen": "En Aurora Store nos distinguimos por un estándar de excelencia en alta costura y satisfacción garantizada.",
        "puntos_clave": [
            "Cambios de talla hasta 15 días continuos en cualquier sucursal del país.",
            "Garantía de 30 días contra cualquier defecto de costura o material.",
            "Reservas en probador privado vigentes por 48 horas sin compromiso.",
            "Envíos express nacionales con empaque de lujo en 24 a 48 horas.",
            "Múltiples métodos de pago: QR Simple, Tarjetas y Efectivo."
        ]
    }


def _ejecutar_buscar_prendas_avanzada(args: dict, id_empresa: int) -> dict:
    termino = str(args.get("termino") or "").strip()
    categoria = str(args.get("categoria") or "").strip()
    talla = str(args.get("talla") or "").strip()
    color = str(args.get("color") or "").strip()
    precio_min = args.get("precio_min")
    precio_max = args.get("precio_max")
    sucursal = str(args.get("sucursal") or "").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT
                p.id_producto,
                p.nombre,
                p.codigo_producto,
                COALESCE(p.precio, 0) as precio,
                COALESCE(c.nombre, 'Moda') as categoria,
                COALESCE(p.genero, 'Unisex') as genero,
                p.imagen_url,
                p.descripcion,
                COALESCE(SUM(inv.stock_disponible), 0) as stock_total
            FROM comercio.t_producto p
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            LEFT JOIN comercio.t_producto_talla_color ptc ON p.id_producto = ptc.id_producto
            LEFT JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
            LEFT JOIN comercio.t_color col ON ptc.id_color = col.id_color
            LEFT JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
            LEFT JOIN comercio.t_sucursal s ON inv.id_sucursal = s.id_sucursal
            WHERE p.id_empresa = %s AND p.activo = true
        """
        params: List[Any] = [id_empresa]

        if termino:
            sql += " AND (p.nombre ILIKE %s OR p.descripcion ILIKE %s OR p.codigo_producto ILIKE %s)"
            t_pat = f"%{termino}%"
            params.extend([t_pat, t_pat, t_pat])

        if categoria:
            sql += " AND c.nombre ILIKE %s"
            params.append(f"%{categoria}%")

        if talla:
            sql += " AND t.nombre ILIKE %s"
            params.append(f"%{talla}%")

        if color:
            sql += " AND col.nombre ILIKE %s"
            params.append(f"%{color}%")

        if precio_min:
            sql += " AND p.precio >= %s"
            params.append(float(precio_min))

        if precio_max:
            sql += " AND p.precio <= %s"
            params.append(float(precio_max))

        if sucursal:
            sql += " AND s.nombre ILIKE %s"
            params.append(f"%{sucursal}%")

        sql += """
            GROUP BY p.id_producto, p.nombre, p.codigo_producto, p.precio, c.nombre, p.genero, p.imagen_url, p.descripcion
            ORDER BY p.id_producto DESC
            LIMIT 10
        """

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        productos = []
        for r in rows:
            cur.execute("""
                SELECT DISTINCT t.nombre, col.nombre
                FROM comercio.t_producto_talla_color ptc
                LEFT JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
                LEFT JOIN comercio.t_color col ON ptc.id_color = col.id_color
                WHERE ptc.id_producto = %s
            """, (r[0],))
            vars_data = cur.fetchall()
            tallas_list = sorted(list({v[0] for v in vars_data if v[0]}))
            colores_list = sorted(list({v[1] for v in vars_data if v[1]}))

            productos.append({
                "id_producto": r[0],
                "nombre": r[1],
                "codigo": r[2],
                "precio": float(r[3]),
                "categoria": r[4],
                "genero": r[5],
                "imagen_url": r[6] or "assets/images/default-fashion.jpg",
                "descripcion": r[7] or "",
                "stock_disponible": int(r[8]),
                "tallas": tallas_list,
                "colores": colores_list
            })

        return {
            "total_encontrados": len(productos),
            "filtros_aplicados": {"termino": termino, "categoria": categoria, "talla": talla, "color": color, "sucursal": sucursal},
            "productos": productos
        }
    finally:
        conn.close()


def _ejecutar_detalle_prenda(args: dict, id_empresa: int) -> dict:
    id_prod = args.get("id_producto")
    nom_prenda = str(args.get("nombre_prenda") or "").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if id_prod:
            sql = "SELECT id_producto, nombre, codigo_producto, precio, imagen_url, descripcion FROM comercio.t_producto WHERE id_producto = %s AND id_empresa = %s"
            cur.execute(sql, (id_prod, id_empresa))
        else:
            sql = "SELECT id_producto, nombre, codigo_producto, precio, imagen_url, descripcion FROM comercio.t_producto WHERE (nombre ILIKE %s OR codigo_producto ILIKE %s) AND id_empresa = %s LIMIT 1"
            p = f"%{nom_prenda}%"
            cur.execute(sql, (p, p, id_empresa))

        prod = cur.fetchone()
        if not prod:
            return {"mensaje": "No se encontró la prenda con los datos provistos."}

        cur.execute("""
            SELECT 
                s.nombre as sucursal,
                t.nombre as talla,
                col.nombre as color,
                COALESCE(inv.stock_disponible, 0) as stock
            FROM comercio.t_producto_talla_color ptc
            JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
            JOIN comercio.t_color col ON ptc.id_color = col.id_color
            JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
            JOIN comercio.t_sucursal s ON inv.id_sucursal = s.id_sucursal
            WHERE ptc.id_producto = %s AND s.id_empresa = %s
            ORDER BY s.nombre, t.nombre
        """, (prod[0], id_empresa))

        rows_stock = cur.fetchall()
        stock_list = []
        for s in rows_stock:
            stock_list.append({
                "sucursal": s[0],
                "talla": s[1],
                "color": s[2],
                "stock": int(s[3])
            })

        return {
            "id_producto": prod[0],
            "nombre": prod[1],
            "codigo": prod[2],
            "precio": float(prod[3]),
            "imagen_url": prod[4] or "assets/images/default-fashion.jpg",
            "descripcion": prod[5] or "",
            "variantes_stock": stock_list
        }
    finally:
        conn.close()


def _ejecutar_consultar_sucursales(id_empresa: int) -> dict:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id_sucursal, s.nombre, COALESCE(s.direccion, 'Centro Comercial'), COALESCE(s.telefono, '70000000'), COALESCE(c.nombre, 'Bolivia')
            FROM comercio.t_sucursal s
            LEFT JOIN comercio.t_ciudad c ON s.id_ciudad = c.id_ciudad
            WHERE s.id_empresa = %s AND s.activo = true
            ORDER BY s.id_sucursal ASC
        """, (id_empresa,))
        rows = cur.fetchall()
        sucursales = []
        for r in rows:
            sucursales.append({
                "id_sucursal": r[0],
                "nombre": r[1],
                "direccion": r[2],
                "telefono": r[3],
                "ciudad": r[4]
            })
        return {"sucursales": sucursales}
    finally:
        conn.close()


def _ejecutar_consultar_mis_pedidos(id_usuario: Optional[int], limite: int = 5) -> dict:
    if not id_usuario:
        return {"mensaje": "Debes iniciar sesión con tu cuenta para consultar tus pedidos."}

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id_cliente FROM comercio.t_cliente WHERE id_usuario = %s LIMIT 1", (id_usuario,))
        row_cli = cur.fetchone()
        if not row_cli:
            return {"pedidos": [], "mensaje": "No se encontró perfil de cliente asociado a tu cuenta."}
        id_cliente = row_cli[0]

        cur.execute("""
            SELECT id_pedido, codigo_pedido, fecha_pedido, total, estado, COALESCE(estado_pago, 'PENDIENTE')
            FROM comercio.t_pedido
            WHERE id_cliente = %s
            ORDER BY fecha_pedido DESC
            LIMIT %s
        """, (id_cliente, limite or 5))
        rows = cur.fetchall()
        pedidos = []
        for r in rows:
            pedidos.append({
                "id_pedido": r[0],
                "numero": r[1],
                "fecha": r[2].strftime("%d/%m/%Y") if r[2] else "",
                "total": float(r[3]),
                "estado": r[4],
                "metodo_pago": r[5]
            })
        return {"pedidos": pedidos}
    finally:
        conn.close()


def _ejecutar_consultar_mis_reservas(id_usuario: Optional[int], limite: int = 5) -> dict:
    if not id_usuario:
        return {"mensaje": "Debes iniciar sesión con tu cuenta para consultar tus reservas."}

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id_cliente FROM comercio.t_cliente WHERE id_usuario = %s LIMIT 1", (id_usuario,))
        row_cli = cur.fetchone()
        if not row_cli:
            return {"reservas": [], "mensaje": "No se encontró perfil de cliente asociado a tu cuenta."}
        id_cliente = row_cli[0]

        cur.execute("""
            SELECT r.id_reserva, r.codigo_reserva, r.fecha_reserva, r.fecha_hora_visita, r.estado, 
                   COALESCE(s.nombre, 'Tienda Central') as sucursal,
                   COALESCE(p.nombre, 'Prenda exclusiva') as prenda,
                   COALESCE(dr.cantidad, 1) as cantidad
            FROM comercio.t_reserva r
            LEFT JOIN comercio.t_sucursal s ON r.id_sucursal = s.id_sucursal
            LEFT JOIN comercio.t_detalle_reserva dr ON r.id_reserva = dr.id_reserva
            LEFT JOIN comercio.t_producto_talla_color ptc ON dr.id_variante = ptc.id_variante
            LEFT JOIN comercio.t_producto p ON ptc.id_producto = p.id_producto
            WHERE r.id_cliente = %s
            ORDER BY r.fecha_reserva DESC
            LIMIT %s
        """, (id_cliente, limite or 5))
        rows = cur.fetchall()
        reservas = []
        for r in rows:
            reservas.append({
                "id_reserva": r[0],
                "codigo": r[1],
                "fecha": r[2].strftime("%d/%m/%Y") if r[2] else "",
                "expira": r[3].strftime("%d/%m/%Y %H:%M") if r[3] else "",
                "estado": r[4],
                "sucursal": r[5] or "Tienda Central",
                "prenda": r[6],
                "cantidad": r[7]
            })
        return {"reservas": reservas}
    finally:
        conn.close()


def _ejecutar_consultar_ventas(args: dict, id_empresa: int) -> dict:
    periodo = str(args.get("periodo") or "hoy").strip()
    sucursal = str(args.get("sucursal") or "").strip()

    hoy = date.today()
    if periodo == "hoy":
        f_desde = hoy
        f_hasta = hoy
    elif periodo == "ayer":
        f_desde = hoy - timedelta(days=1)
        f_hasta = f_desde
    elif periodo == "esta_semana":
        f_desde = hoy - timedelta(days=hoy.weekday())
        f_hasta = hoy
    elif periodo == "este_mes":
        f_desde = hoy.replace(day=1)
        f_hasta = hoy
    else:
        f_desde = hoy - timedelta(days=30)
        f_hasta = hoy

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT 
                COUNT(v.id_venta) as total_ventas,
                COALESCE(SUM(v.total), 0) as recaudacion_total,
                COALESCE(AVG(v.total), 0) as ticket_promedio
            FROM comercio.t_venta v
            LEFT JOIN comercio.t_sucursal s ON v.id_sucursal = s.id_sucursal
            WHERE v.id_empresa = %s
              AND v.fecha_venta >= %s
              AND v.fecha_venta < %s
              AND v.estado != 'CANCELADA'
        """
        params = [id_empresa, f_desde, f_hasta + timedelta(days=1)]

        if sucursal:
            sql += " AND s.nombre ILIKE %s"
            params.append(f"%{sucursal}%")

        cur.execute(sql, tuple(params))
        row = cur.fetchone()

        cur.execute("""
            SELECT p.nombre, SUM(dv.cantidad) as total_prendas, SUM(dv.subtotal) as subtotal_bs
            FROM comercio.t_detalle_venta dv
            JOIN comercio.t_venta v ON dv.id_venta = v.id_venta
            JOIN comercio.t_producto_talla_color ptc ON dv.id_variante = ptc.id_variante
            JOIN comercio.t_producto p ON ptc.id_producto = p.id_producto
            WHERE v.id_empresa = %s AND v.fecha_venta >= %s AND v.fecha_venta < %s AND v.estado != 'CANCELADA'
            GROUP BY p.nombre
            ORDER BY total_prendas DESC
            LIMIT 3
        """, (id_empresa, f_desde, f_hasta + timedelta(days=1)))
        top_prendas = [{"prenda": r[0], "unidades": int(r[1]), "recaudado": float(r[2])} for r in cur.fetchall()]

        return {
            "periodo": periodo,
            "desde": f_desde.strftime("%d/%m/%Y"),
            "hasta": f_hasta.strftime("%d/%m/%Y"),
            "sucursal_filtrada": sucursal or "Todas",
            "transacciones": int(row[0]) if row else 0,
            "ingresos_totales_bs": float(row[1]) if row else 0.0,
            "ticket_promedio_bs": round(float(row[2]), 2) if row else 0.0,
            "prendas_top": top_prendas
        }
    finally:
        conn.close()


def _ejecutar_consultar_inventario_alertas(args: dict, id_empresa: int) -> dict:
    filtro = str(args.get("filtro") or "bajo_stock").strip()
    sucursal = str(args.get("sucursal") or "").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT 
                p.nombre as prenda,
                t.nombre as talla,
                col.nombre as color,
                s.nombre as sucursal,
                inv.stock_disponible,
                COALESCE(inv.stock_minimo, 3) as stock_minimo
            FROM comercio.t_inventario inv
            JOIN comercio.t_producto_talla_color ptc ON inv.id_variante = ptc.id_variante
            JOIN comercio.t_producto p ON ptc.id_producto = p.id_producto
            JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
            JOIN comercio.t_color col ON ptc.id_color = col.id_color
            JOIN comercio.t_sucursal s ON inv.id_sucursal = s.id_sucursal
            WHERE p.id_empresa = %s AND p.activo = true
        """
        params = [id_empresa]

        if sucursal:
            sql += " AND s.nombre ILIKE %s"
            params.append(f"%{sucursal}%")

        if filtro == "agotados":
            sql += " AND inv.stock_disponible <= 0"
        elif filtro == "bajo_stock":
            sql += " AND inv.stock_disponible <= COALESCE(inv.stock_minimo, 3)"

        sql += " ORDER BY inv.stock_disponible ASC LIMIT 12"

        cur.execute(sql, tuple(params))
        items = []
        for r in cur.fetchall():
            items.append({
                "prenda": r[0],
                "talla": r[1],
                "color": r[2],
                "sucursal": r[3],
                "stock": int(r[4]),
                "minimo": int(r[5]),
                "alerta": "AGOTADO" if r[4] <= 0 else "STOCK CRÍTICO"
            })

        return {
            "filtro_aplicado": filtro,
            "alertas_encontradas": len(items),
            "items": items
        }
    finally:
        conn.close()


def _ejecutar_consultar_devoluciones(args: dict, id_empresa: int) -> dict:
    periodo = args.get("periodo", "este_mes")
    sucursal = (args.get("sucursal") or "").strip()
    motivo = (args.get("motivo") or "").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM information_schema.views WHERE table_schema = 'comercio' AND table_name = 'vw_devoluciones_reporte' LIMIT 1")
        if not cur.fetchone():
            return {
                "periodo": periodo,
                "total_devoluciones": 0,
                "total_prendas_afectadas": 0,
                "monto_total_reembolsado_bs": 0.0,
                "motivos_principales": {},
                "items": []
            }

        sql = """
            SELECT 
                codigo_devolucion,
                fecha,
                sucursal,
                cliente,
                numero_venta,
                motivo_general,
                total_articulos,
                monto_total_devolucion,
                estado
            FROM comercio.vw_devoluciones_reporte
            WHERE id_empresa = %s
        """
        params: List[Any] = [id_empresa]

        if sucursal:
            sql += " AND sucursal ILIKE %s"
            params.append(f"%{sucursal}%")

        if motivo:
            sql += " AND motivo_general ILIKE %s"
            params.append(f"%{motivo}%")

        sql += " ORDER BY fecha DESC LIMIT 10"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        devoluciones = []
        total_monto = 0.0
        total_prendas = 0
        motivos_conteo: Dict[str, int] = {}

        for r in rows:
            m = r[5] or "Sin motivo especificado"
            motivos_conteo[m] = motivos_conteo.get(m, 0) + 1
            monto_dev = float(r[7] or 0.0)
            articulos = int(r[6] or 0)
            total_monto += monto_dev
            total_prendas += articulos

            devoluciones.append({
                "codigo": r[0],
                "fecha": str(r[1]),
                "sucursal": r[2],
                "cliente": r[3] or "Cliente Tienda",
                "venta": r[4],
                "motivo": m,
                "articulos": articulos,
                "monto_bs": monto_dev,
                "estado": r[8]
            })

        return {
            "periodo": periodo,
            "total_devoluciones": len(devoluciones),
            "total_prendas_afectadas": total_prendas,
            "monto_total_reembolsado_bs": round(total_monto, 2),
            "motivos_principales": motivos_conteo,
            "items": devoluciones
        }
    except Exception as e:
        logger.warning(f"Error consultando vista devoluciones: {e}")
        return {"total_devoluciones": 0, "monto_total_reembolsado_bs": 0.0, "items": []}
    finally:
        conn.close()


def _ejecutar_recomendaciones_reposicion(args: dict, id_empresa: int) -> dict:
    sucursal = (args.get("sucursal") or "").strip()
    categoria = (args.get("categoria") or "").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT 
                p.nombre as prenda,
                c.nombre as categoria,
                t.nombre as talla,
                col.nombre as color,
                s.nombre as sucursal,
                inv.stock_disponible,
                COALESCE(inv.stock_minimo, 3) as stock_minimo,
                p.precio
            FROM comercio.t_inventario inv
            JOIN comercio.t_producto_talla_color ptc ON inv.id_variante = ptc.id_variante
            JOIN comercio.t_producto p ON ptc.id_producto = p.id_producto
            JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
            JOIN comercio.t_color col ON ptc.id_color = col.id_color
            JOIN comercio.t_sucursal s ON inv.id_sucursal = s.id_sucursal
            WHERE p.id_empresa = %s AND p.activo = true AND inv.stock_disponible <= COALESCE(inv.stock_minimo, 3) + 2
        """
        params: List[Any] = [id_empresa]

        if sucursal:
            sql += " AND s.nombre ILIKE %s"
            params.append(f"%{sucursal}%")
        if categoria:
            sql += " AND c.nombre ILIKE %s"
            params.append(f"%{categoria}%")

        sql += " ORDER BY inv.stock_disponible ASC LIMIT 10"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        recomendaciones = []
        for r in rows:
            stk_actual = int(r[5])
            stk_min = int(r[6])
            sug_pedido = max((stk_min * 2) - stk_actual, 5)

            prioridad = "ALTA" if stk_actual <= 1 else "MEDIA"
            recomendaciones.append({
                "prenda": r[0],
                "categoria": r[1],
                "talla": r[2],
                "color": r[3],
                "sucursal": r[4],
                "stock_actual": stk_actual,
                "stock_minimo": stk_min,
                "sugerencia_reposicion_unidades": sug_pedido,
                "prioridad": prioridad
            })

        return {
            "total_alertas_reposicion": len(recomendaciones),
            "recomendaciones": recomendaciones,
            "items": recomendaciones
        }
    finally:
        conn.close()


def _ejecutar_motor_reportes(args: dict, id_empresa: int, token_data: Optional[dict]) -> dict:
    from app.modules.pedidos.services.reports.parser.command_parser import parsear_comando_voz
    from app.modules.pedidos.services.reports.engine.report_engine import ejecutar_reporte_dinamico

    comando = args.get("comando_o_reporte", "ventas de este mes")
    parsed = parsear_comando_voz(comando, id_empresa)
    report_req = parsed.get("report_request") or {}

    t_data = token_data or {
        "id_empresa": id_empresa,
        "id_rol": 1,
        "roles": ["ADMINISTRADOR"],
        "id_usuario": 1,
        "nombre": "Administrador"
    }

    try:
        resultado = ejecutar_reporte_dinamico(report_req, t_data)
        return {
            "resumen_interpretacion": parsed.get("resumen_interpretacion", "Reporte ejecutado"),
            "reporte": report_req.get("reporte"),
            "total_registros": resultado.get("resumen", {}).get("total_registros", 0),
            "monto_total_bs": float(resultado.get("resumen", {}).get("total_monto", 0.0)),
            "columnas": [c.get("titulo") for c in resultado.get("columnas", [])],
            "filas": resultado.get("filas", [])[:10],
            "items": resultado.get("filas", [])[:10]
        }
    except Exception as e:
        logger.error(f"Error ejecutando reporte analítico en asistente: {e}")
        return {
            "error": str(e),
            "resumen_interpretacion": parsed.get("resumen_interpretacion", "Error en motor de reportes"),
            "items": []
        }


def _ejecutar_consultar_ventas_pendientes(args: dict, id_empresa: int) -> dict:
    sucursal = str(args.get("sucursal") or "").strip()
    canal = str(args.get("canal") or "todos").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT 
                numero_documento,
                fecha,
                sucursal,
                cliente,
                canal,
                total,
                dias_pendiente,
                CASE
                    WHEN COALESCE(dias_pendiente, 0) >= 7 THEN 'CRÍTICA'
                    WHEN COALESCE(dias_pendiente, 0) >= 3 THEN 'ATENCIÓN'
                    ELSE 'NORMAL'
                END AS alerta_antiguedad
            FROM comercio.vw_ventas_pendientes_reporte
            WHERE id_empresa = %s
        """
        params = [id_empresa]

        if sucursal:
            sql += " AND sucursal ILIKE %s"
            params.append(f"%{sucursal}%")

        if canal and canal.lower() != "todos":
            sql += " AND canal ILIKE %s"
            params.append(f"%{canal}%")

        sql += " ORDER BY dias_pendiente DESC LIMIT 10"

        cur.execute(sql, tuple(params))
        ventas = []
        for r in cur.fetchall():
            ventas.append({
                "numero_venta": r[0],
                "fecha": str(r[1]),
                "sucursal": r[2],
                "cliente": r[3] or "Cliente sin registrar",
                "canal": r[4],
                "monto_total": float(r[5] or 0.0),
                "dias_antiguedad": r[6] or 0,
                "alerta": r[7] or "NORMAL"
            })
        return {
            "total_encontradas": len(ventas),
            "ventas_pendientes": ventas,
            "items": ventas
        }
    finally:
        conn.close()


def _ejecutar_consultar_reservas_empresa(args: dict, id_empresa: int) -> dict:
    sucursal = str(args.get("sucursal") or "").strip()
    vigencia = str(args.get("vigencia") or "todas").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT 
                codigo_reserva,
                fecha_reserva,
                sucursal,
                cliente,
                prenda,
                cantidad,
                subtotal_estimado,
                vigencia
            FROM comercio.vw_reservas_reporte
            WHERE id_empresa = %s
        """
        params = [id_empresa]

        if sucursal:
            sql += " AND sucursal ILIKE %s"
            params.append(f"%{sucursal}%")

        if vigencia == "vigente":
            sql += " AND vigencia = 'VIGENTE'"
        elif vigencia == "vencida":
            sql += " AND vigencia = 'VENCIDA'"

        sql += " ORDER BY fecha_reserva DESC LIMIT 10"

        cur.execute(sql, tuple(params))
        reservas = []
        for r in cur.fetchall():
            reservas.append({
                "codigo": r[0],
                "fecha": str(r[1]),
                "sucursal": r[2],
                "cliente": r[3] or "Cliente Tienda",
                "prenda": r[4] or "Prenda exclusiva",
                "cantidad": r[5] or 1,
                "monto_bs": float(r[6] or 0.0),
                "vigencia": r[7] or "VIGENTE"
            })
        return {
            "total_reservas": len(reservas),
            "reservas": reservas,
            "items": reservas
        }
    finally:
        conn.close()


def _ejecutar_consultar_auditoria_pos(args: dict, id_empresa: int) -> dict:
    sucursal = str(args.get("sucursal") or "").strip()
    solo_alertas = bool(args.get("solo_alertas", False))

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT 
                numero_venta,
                fecha,
                cajero,
                sucursal,
                caja,
                total,
                metodo_pago,
                alerta_auditoria
            FROM comercio.vw_pos_reporte
            WHERE id_empresa = %s
        """
        params = [id_empresa]

        if sucursal:
            sql += " AND sucursal ILIKE %s"
            params.append(f"%{sucursal}%")

        if solo_alertas:
            sql += " AND alerta_auditoria != 'OK'"

        sql += " ORDER BY fecha_venta DESC LIMIT 10"

        cur.execute(sql, tuple(params))
        auditorias = []
        for r in cur.fetchall():
            auditorias.append({
                "venta": r[0],
                "fecha": str(r[1]),
                "cajero": r[2] or "Cajero",
                "sucursal": r[3],
                "caja": r[4] or "Caja Principal",
                "total_venta": float(r[5] or 0.0),
                "total_cobrado": float(r[5] or 0.0),
                "alerta": r[7] or "OK"
            })
        return {
            "total_registros": len(auditorias),
            "auditoria_pos": auditorias,
            "items": auditorias
        }
    finally:
        conn.close()


def _ejecutar_consultar_indicadores_kpi(id_empresa: int) -> dict:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                COALESCE(SUM(total), 0) as total_facturado,
                COUNT(id_venta) as total_ventas
            FROM comercio.t_venta
            WHERE id_empresa = %s AND estado != 'CANCELADA'
        """, (id_empresa,))
        row_ventas = cur.fetchone()

        cur.execute("SELECT COUNT(id_producto) FROM comercio.t_producto WHERE id_empresa = %s AND activo = true", (id_empresa,))
        row_prod = cur.fetchone()

        cur.execute("SELECT COUNT(id_pedido) FROM comercio.t_pedido WHERE id_empresa = %s", (id_empresa,))
        row_ped = cur.fetchone()

        cur.execute("SELECT COUNT(id_sucursal) FROM comercio.t_sucursal WHERE id_empresa = %s AND activo = true", (id_empresa,))
        row_suc = cur.fetchone()

        return {
            "ingresos_totales_bs": float(row_ventas[0]) if row_ventas else 0.0,
            "ventas_realizadas": int(row_ventas[1]) if row_ventas else 0,
            "prendas_activas_catalogo": int(row_prod[0]) if row_prod else 0,
            "pedidos_online": int(row_ped[0]) if row_ped else 0,
            "sucursales_activas": int(row_suc[0]) if row_suc else 0
        }
    finally:
        conn.close()


def despachar_herramienta(tool_name: str, tool_args: dict, token_data: Optional[dict], id_empresa: int) -> tuple[dict, str]:
    id_usuario = token_data.get("id_usuario") if token_data else None

    if tool_name == "buscar_prendas_catalogo":
        res = _ejecutar_buscar_prendas(tool_args, id_empresa)
        return res, "productos"

    elif tool_name == "recomendar_outfit_estilo":
        res = _ejecutar_recomendar_outfit(tool_args, id_empresa)
        return res, "productos"

    elif tool_name == "consultar_politicas_devolucion":
        res = _ejecutar_consultar_politicas(tool_args)
        return res, "tabla"

    elif tool_name == "buscar_prendas_avanzada":
        res = _ejecutar_buscar_prendas_avanzada(tool_args, id_empresa)
        return res, "productos"

    elif tool_name == "consultar_detalle_prenda":
        res = _ejecutar_detalle_prenda(tool_args, id_empresa)
        return res, "productos"

    elif tool_name == "consultar_sucursales_tiendas":
        res = _ejecutar_consultar_sucursales(id_empresa)
        return res, "tabla"

    elif tool_name == "consultar_mis_pedidos":
        res = _ejecutar_consultar_mis_pedidos(id_usuario, tool_args.get("limite", 5))
        return res, "tabla"

    elif tool_name == "consultar_mis_reservas":
        res = _ejecutar_consultar_mis_reservas(id_usuario, tool_args.get("limite", 5))
        return res, "tabla"

    elif tool_name == "consultar_mis_recomendaciones_personalizadas":
        from app.modules.ia.services.ml_preferencias_services import obtener_recomendaciones_cliente
        lim = tool_args.get("limite", 4)
        recs = obtener_recomendaciones_cliente(id_usuario, id_empresa, limite=lim)
        return {"recomendaciones": recs, "total": len(recs), "productos": recs}, "productos"

    elif tool_name == "consultar_ventas_empresa":
        res = _ejecutar_consultar_ventas(tool_args, id_empresa)
        return res, "indicadores"

    elif tool_name == "consultar_inventario_alertas":
        res = _ejecutar_consultar_inventario_alertas(tool_args, id_empresa)
        return res, "tabla"

    elif tool_name == "consultar_devoluciones_reclamos":
        res = _ejecutar_consultar_devoluciones(tool_args, id_empresa)
        return res, "tabla"

    elif tool_name == "consultar_recomendaciones_reposicion_stock":
        res = _ejecutar_recomendaciones_reposicion(tool_args, id_empresa)
        return res, "tabla"

    elif tool_name == "consultar_reporte_motor_analitico":
        res = _ejecutar_motor_reportes(tool_args, id_empresa, token_data)
        return res, "reporte"

    elif tool_name == "consultar_ventas_pendientes":
        res = _ejecutar_consultar_ventas_pendientes(tool_args, id_empresa)
        return res, "tabla"

    elif tool_name == "consultar_reservas_prendas_empresa":
        res = _ejecutar_consultar_reservas_empresa(tool_args, id_empresa)
        return res, "tabla"

    elif tool_name == "consultar_auditoria_pos_errores":
        res = _ejecutar_consultar_auditoria_pos(tool_args, id_empresa)
        return res, "tabla"

    elif tool_name == "consultar_indicadores_kpi_generales":
        res = _ejecutar_consultar_indicadores_kpi(id_empresa)
        return res, "indicadores"

    elif tool_name == "generar_reporte_directo":
        tipo = tool_args.get("tipo_reporte", "ventas")
        if tipo == "ventas":
            res = _ejecutar_consultar_ventas({"periodo": "este_mes"}, id_empresa)
        elif tipo == "inventario":
            res = _ejecutar_consultar_inventario_alertas({"filtro": "todos"}, id_empresa)
        elif tipo == "devoluciones":
            res = _ejecutar_consultar_devoluciones({}, id_empresa)
        elif tipo in ["rentabilidad", "rendimiento_personal", "stock_inmovilizado"]:
            res = _ejecutar_motor_reportes({"comando_o_reporte": tipo}, id_empresa, token_data)
        elif tipo == "ventas_pendientes":
            res = _ejecutar_consultar_ventas_pendientes({}, id_empresa)
        elif tipo == "reservas":
            res = _ejecutar_consultar_reservas_empresa({}, id_empresa)
        elif tipo == "pos":
            res = _ejecutar_consultar_auditoria_pos({}, id_empresa)
        else:
            res = _ejecutar_consultar_indicadores_kpi(id_empresa)
        return res, "reporte"

    return {"error": f"Herramienta '{tool_name}' desconocida."}, "texto"


# =====================================================================
# SÍNTESIS CONVERSACIONAL NATURAL & FALLBACK RESILIENTE
# =====================================================================

def _formatear_respuesta_natural(tool_name: str, tool_result: dict, nombre_usuario: str = "estimado cliente") -> str:
    """
    Genera redacción fluida, cálida y natural de asesora de alta costura
    a partir de los datos retornados por cada herramienta.
    """
    if tool_name == "recomendar_outfit_estilo":
        ocasion = tool_result.get("ocasion", "tu evento")
        estilo = tool_result.get("estilo", "elegante")
        presupuesto = tool_result.get("presupuesto_estimado_bs", 0.0)
        consejo = tool_result.get("consejo_estilismo", "")
        piezas = tool_result.get("piezas_principales", [])
        accesorios = tool_result.get("complementos_accesorios", [])
        
        texto = f"Con el mayor de los gustos, {nombre_usuario}. Para una ocasión de **{ocasion}** con estilo **{estilo}**, he seleccionado una combinación sublime que proyecta distinción y armonía.\n\n"
        if piezas:
            texto += "**Piezas Principales del Look:**\n"
            for p in piezas:
                p_nom = p.get("nombre", "Prenda")
                p_prec = p.get("precio", 0.0)
                texto += f"• **{p_nom}** — Bs. {p_prec:.2f}\n"
        if accesorios:
            texto += "\n**Complementos y Accesorios Recomendados:**\n"
            for a in accesorios:
                a_nom = a.get("nombre", "Accesorio")
                a_prec = a.get("precio", 0.0)
                texto += f"• **{a_nom}** — Bs. {a_prec:.2f}\n"
        if presupuesto > 0:
            texto += f"\n*Inversión total estimada del atuendo: **Bs. {presupuesto:.2f}**.*\n"
        if consejo:
            texto += f"\n💡 **Consejo de estilo:** {consejo}"
        return texto

    elif tool_name == "consultar_mis_recomendaciones_personalizadas":
        recs = tool_result.get("recomendaciones", [])
        if not recs:
            return "Actualmente estamos analizando tus preferencias de compra para generar recomendaciones a tu medida. Mientras tanto, te sugiero explorar nuestras colecciones destacadas."
        resp = f"Basándome en tus compras anteriores y en tu afinidad de estilo aprendida por nuestro sistema, he seleccionado estas piezas para ti, {nombre_usuario}:\n\n"
        for r in recs[:4]:
            p_nom = r.get("nombre", "Prenda")
            p_cat = r.get("categoria", "Alta Costura")
            p_prec = r.get("precio", 0.0)
            p_afin = r.get("afinidad_porcentaje", 85)
            p_mot = r.get("motivo", "")
            resp += f"• **{p_nom}** ({p_cat}) — Bs. {p_prec:.2f} [{p_afin}% afinidad]\n  *{p_mot}*\n"
        resp += "\n*¿Te gustaría apartar alguna de estas piezas en probador privado en tu sucursal más cercana?*"
        return resp

    elif tool_name in ["buscar_prendas_catalogo", "buscar_prendas_avanzada"]:
        total = tool_result.get("total_encontrados", 0)
        if total == 0:
            return "Actualmente no disponemos de piezas con esas características específicas en el catálogo, pero podemos coordinar una reserva personalizada o recomendarte alternativas similares."
        return f"He seleccionado **{total} prendas exclusivas** que combinan a la perfección con tu búsqueda. Puedes consultar sus detalles, tallas y probador en nuestras tiendas a continuación:"

    elif tool_name == "consultar_politicas_devolucion":
        titulo = tool_result.get("titulo", "Políticas de Aurora Store")
        plazo = tool_result.get("plazo", "")
        condiciones = tool_result.get("condiciones", [])
        puntos = tool_result.get("puntos_clave", [])
        
        resp = f"**{titulo}**\n\n"
        if plazo:
            resp += f"⏱️ **Plazo garantizado:** {plazo}\n\n"
        if condiciones:
            resp += "**Condiciones del servicio:**\n"
            for c in condiciones:
                resp += f"• {c}\n"
        elif puntos:
            for p in puntos:
                resp += f"• {p}\n"
        resp += "\n*En Aurora Store tu satisfacción y confianza son nuestro mayor compromiso.*"
        return resp

    elif tool_name == "consultar_ventas_empresa":
        recaudado = tool_result.get("ingresos_totales_bs", 0.0)
        trx = tool_result.get("transacciones", 0)
        ticket = tool_result.get("ticket_promedio_bs", 0.0)
        periodo = tool_result.get("periodo", "").replace("_", " ")
        top = tool_result.get("prendas_top", [])

        resp = f"Aquí tienes el balance comercial de **{periodo.upper()}**:\n\n"
        resp += f"• **Recaudación Total:** Bs. {recaudado:,.2f}\n"
        resp += f"• **Operaciones Realizadas:** {trx} transacciones\n"
        resp += f"• **Ticket Promedio:** Bs. {ticket:,.2f}\n"
        if top:
            resp += "\n**Prendas con mayor demanda:**\n"
            for t in top:
                resp += f"• {t['prenda']}: {t['unidades']} unidades (Bs. {t['recaudado']:,.2f})\n"
        return resp

    elif tool_name == "consultar_devoluciones_reclamos":
        total = tool_result.get("total_devoluciones", 0)
        monto = tool_result.get("monto_total_reembolsado_bs", 0.0)
        motivos = tool_result.get("motivos_principales", {})
        
        resp = "Informe de Devoluciones y Garantías:\n\n"
        resp += f"Se registraron **{total} solicitudes** con un impacto económico de **Bs. {monto:,.2f}**.\n"
        if motivos:
            resp += "\n**Principales causas registradas:**\n"
            for m, count in motivos.items():
                resp += f"• {m}: {count} caso(s)\n"
        return resp

    elif tool_name == "consultar_recomendaciones_reposicion_stock":
        recs = tool_result.get("recomendaciones", [])
        if not recs:
            return "El estado de inventario se encuentra óptimo; no se registran prendas críticas por debajo del stock de seguridad."
        resp = f"He identificado **{len(recs)} artículos con reposición sugerida** para evitar quiebres de inventario:\n\n"
        for r in recs[:5]:
            resp += f"• **{r['prenda']}** ({r['talla']}, {r['color']}) en *{r['sucursal']}*: Stock actual **{r['stock_actual']}** (Mín: {r['stock_minimo']}) → **Sugerido pedir: +{r['sugerencia_reposicion_unidades']} uds** [{r['prioridad']}]\n"
        return resp

    elif tool_name in ["consultar_reporte_motor_analitico", "generar_reporte_directo"]:
        resumen = tool_result.get("resumen_interpretacion", "Reporte analítico generado")
        total_reg = tool_result.get("total_registros", 0)
        monto = tool_result.get("monto_total_bs", 0.0)
        resp = f"**{resumen}**\n\n"
        resp += f"Consolidación analítica completada: **{total_reg} registros evaluados**"
        if monto > 0:
            resp += f" con un volumen total de **Bs. {monto:,.2f}**"
        resp += ".\nPresento los datos procesados en la vista adjunta:"
        return resp

    elif tool_name == "consultar_sucursales_tiendas":
        sucs = tool_result.get("sucursales", [])
        resp = "Nuestras boutiques exclusivas están a tu disposición en las siguientes ubicaciones:\n\n"
        for s in sucs:
            resp += f"• **{s['nombre']}** ({s['ciudad']}): {s['direccion']} — Tel: {s['telefono']}\n"
        resp += "\n*Te invitamos a visitarnos para disfrutar de nuestra experiencia de probador privado.*"
        return resp

    return "Aquí tienes los datos procesados correspondientes a tu solicitud."


def _procesar_intencion_local(mensaje: str, token_data: Optional[dict], id_empresa: int, es_admin: bool) -> dict:
    """
    Motor local de reconocimiento de intenciones y fallbacks elegantes
    cuando el servicio externo de LLM no está disponible o la consulta es directa.
    """
    msg = (mensaje or "").lower().strip()
    nombre = token_data.get("nombre") if token_data else "estimado cliente"

    # 1. Saludos cordiales
    if re.search(r'\b(hola|buen[ao]s?\s*(dias|tardes|noches)?|saludos|que\s+tal)\b', msg) and len(msg.split()) <= 4:
        saludo = f"¡Hola! Es un placer saludarte, {nombre}. Soy **Aurora Advisor**, tu asesora de imagen y asistente inteligente de Aurora Store.\n\nPuedo ayudarte con:\n"
        saludo += "✨ **Recomendación de atuendos y estilismo** para cualquier evento u ocasión.\n"
        saludo += "👗 **Búsqueda exclusiva de prendas** por modelo, talla, color o temporada.\n"
        saludo += "📍 **Ubicaciones y horarios** de nuestras tiendas en Santa Cruz, La Paz y Cochabamba.\n"
        saludo += "📦 **Políticas de compra, envíos rápidos y garantías** de cambio.\n"
        if es_admin:
            saludo += "📊 **Motor de reportes comerciales y analítica en tiempo real** (ventas, devoluciones, rentabilidad, stock inmovilizado).\n"
        saludo += "\n¿En qué podemos inspirarte hoy?"
        return {"respuesta": saludo, "tipo": "texto", "datos": None}

    # 1.1 Recomendaciones basadas en compras históricas / preferencias ML
    if any(k in msg for k in ["segun mis compras", "segun lo que compre", "mis recomendaciones", "que me recomiendas comprar", "ropa para mi", "mis gustos"]):
        res, tipo = despachar_herramienta("consultar_mis_recomendaciones_personalizadas", {}, token_data, id_empresa)
        comentario = _formatear_respuesta_natural("consultar_mis_recomendaciones_personalizadas", res, nombre)
        return {"respuesta": comentario, "tipo": tipo, "datos": res.get("productos", [])}

    # 2. Recomendación de Outfit / Estilo
    if any(k in msg for k in ["outfit", "recomendar", "look", "combinar", "que me pongo", "gala", "coctel", "boda", "fiesta", "asesoria", "estilo"]):
        ocasion = "gala" if "gala" in msg else ("coctel" if "coctel" in msg else ("casual" if "casual" in msg else ("oficina" if "oficina" in msg else "evento especial")))
        genero = "Caballeros" if any(w in msg for w in ["hombre", "caballero", "masculino"]) else ("Damas" if any(w in msg for w in ["dama", "mujer", "femenino"]) else "")
        args = {"ocasion": ocasion, "genero": genero, "estilo_preferido": "elegante"}
        res, tipo = despachar_herramienta("recomendar_outfit_estilo", args, token_data, id_empresa)
        comentario = _formatear_respuesta_natural("recomendar_outfit_estilo", res, nombre)
        return {"respuesta": comentario, "tipo": tipo, "datos": res.get("productos", [])}

    # 3. Políticas, cambios y devoluciones del cliente
    if any(k in msg for k in ["politica", "cambio", "devolucion", "garantia", "reserva", "tiempo de reserva", "envio", "entrega", "pago"]):
        tema = "cambios_talla" if "cambio" in msg or "talla" in msg else ("reservas_vigencia" if "reserva" in msg else ("envios_tiempos" if "envio" in msg or "entrega" in msg else ("garantias_devoluciones" if "garantia" in msg or "devolucion" in msg else "general")))
        res, tipo = despachar_herramienta("consultar_politicas_devolucion", {"tema": tema}, token_data, id_empresa)
        comentario = _formatear_respuesta_natural("consultar_politicas_devolucion", res, nombre)
        return {"respuesta": comentario, "tipo": "texto", "datos": res}

    # 4. Sucursales y ubicaciones
    if any(k in msg for k in ["sucursal", "tienda", "donde estan", "ubicacion", "direccion", "telefono", "horario"]):
        res, tipo = despachar_herramienta("consultar_sucursales_tiendas", {}, token_data, id_empresa)
        comentario = _formatear_respuesta_natural("consultar_sucursales_tiendas", res, nombre)
        return {"respuesta": comentario, "tipo": tipo, "datos": res.get("sucursales", [])}

    # 5. Comandos analíticos / reportes (para administración)
    if es_admin and any(k in msg for k in ["reporte", "ventas", "margen", "rentabilidad", "cajeros", "inmovilizado", "devoluciones", "kpi", "arqueo"]):
        res, tipo = despachar_herramienta("consultar_reporte_motor_analitico", {"comando_o_reporte": msg}, token_data, id_empresa)
        comentario = _formatear_respuesta_natural("consultar_reporte_motor_analitico", res, nombre)
        return {"respuesta": comentario, "tipo": tipo, "datos": res}

    # 6. Búsqueda de prendas en catálogo
    res, tipo = despachar_herramienta("buscar_prendas_catalogo", {"termino": msg}, token_data, id_empresa)
    if res.get("total_encontrados", 0) > 0:
        comentario = _formatear_respuesta_natural("buscar_prendas_catalogo", res, nombre)
        return {"respuesta": comentario, "tipo": tipo, "datos": res.get("productos", [])}

    default_text = f"He tomado nota de tu consulta, {nombre}. Como asesora de Aurora Store, puedo orientarte sobre nuestro catálogo de alta costura, asesorarte en combinación de prendas o asistirte con datos y operaciones de la tienda. ¿Deseas ver alguna prenda o consultar disponibilidad en sucursal?"
    return {"respuesta": default_text, "tipo": "texto", "datos": None}


# =====================================================================
# SERVICIO PRINCIPAL DE CHAT CON ORQUESTADOR MULTIMODELO + RBAC + MEMORIA
# =====================================================================

def procesar_mensaje_chat(
    mensaje: str,
    historial: Optional[List[dict]] = None,
    token_data: Optional[dict] = None,
    conversation_id: Optional[str] = None,
    slug_tienda: Optional[str] = None,
    id_empresa_solicitado: Optional[int] = None,
    rate_limit_key: Optional[str] = None,
    orchestrator: Optional[Any] = None,
    modelo: Optional[str] = None,
) -> dict:
    """
    Punto de entrada principal de Aurora Advisor (Iteraciones 2/3 modernizadas).
    Delega en ConversationalOrchestrator aplicando:
    - Aislamiento multitenant estricto y verificación RBAC desde PostgreSQL
    - Anti-prompt injection y sanitización de historial/salidas
    - Memoria conversacional con extracción de preferencias y referencias anafóricas
    - Orquestación multi-herramienta agnóstica al proveedor (DeepSeek, OpenAI, Gemini)
    - Integración con CU23W (proyección de demanda y reposición de stock)
    - Fallback inteligente multi-intención cuando el proveedor externo no está disponible
    """
    from app.modules.ia.orchestrator.conversational_orchestrator import GLOBAL_ORCHESTRATOR

    if not mensaje or not str(mensaje).strip():
        return {
            "success": False,
            "conversation_id": conversation_id or "empty",
            "mensaje": "Por favor escribe tu consulta o requerimiento para poder asistirte.",
            "respuesta": "Por favor escribe tu consulta o requerimiento para poder asistirte.",
            "tipo": "texto",
            "datos": None,
            "herramientas_usadas": [],
            "metadata": {},
        }

    active_orchestrator = orchestrator or GLOBAL_ORCHESTRATOR
    return active_orchestrator.process_turn(
        mensaje=mensaje,
        token_data=token_data,
        historial=historial,
        conversation_id=conversation_id,
        slug_tienda=slug_tienda,
        id_empresa_solicitado=id_empresa_solicitado,
        rate_limit_key=rate_limit_key,
        modelo=modelo,
    )

