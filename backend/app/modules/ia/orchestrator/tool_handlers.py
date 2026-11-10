"""
Implementación de manejadores de herramientas de negocio y Ejecutor Seguro (ToolExecutor)
para Aurora Advisor.
"""

import time
import json
import logging
import psycopg2
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from app.core.config import Config
from app.modules.ia.orchestrator.security_guard import (
    AssistantSecurityContext,
    verify_branch_access,
    sanitize_untrusted_db_content
)
from app.modules.ia.orchestrator.tool_registry import (
    ToolRegistry,
    ToolDefinition,
    FORBIDDEN_WRITE_TOOLS
)
from app.modules.ia.orchestrator.nlp_understanding import resolve_relative_period
from app.modules.ia.ai.exceptions.ai_exceptions import (
    AISecurityViolationError,
    AIToolExecutionError,
    AIDatabaseError
)

logger = logging.getLogger(__name__)


def get_db_connection():
    try:
        return psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            dbname=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            connect_timeout=10
        )
    except Exception as e:
        logger.error(f"Error de conexión a PostgreSQL en herramienta IA: {e}")
        raise AIDatabaseError("No fue posible conectar con la base de datos de Aurora Store.")


def _enrich_product_variants(cur, id_producto: int) -> Tuple[List[str], List[str]]:
    cur.execute("""
        SELECT DISTINCT t.nombre, col.nombre
        FROM comercio.t_producto_talla_color ptc
        LEFT JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
        LEFT JOIN comercio.t_color col ON ptc.id_color = col.id_color
        WHERE ptc.id_producto = %s
    """, (id_producto,))
    vars_data = cur.fetchall()
    tallas = sorted(list({str(v[0]) for v in vars_data if v[0]}))
    colores = sorted(list({str(v[1]) for v in vars_data if v[1]}))
    return tallas, colores


# =====================================================================
# HERRAMIENTAS DE CLIENTE Y CATÁLOGO
# =====================================================================

def handle_buscar_prendas_avanzada(args: Dict[str, Any], ctx: AssistantSecurityContext, max_results: int = 10) -> Dict[str, Any]:
    termino = str(args.get("termino") or "").strip()
    categoria = str(args.get("categoria") or "").strip()
    talla = str(args.get("talla") or "").strip()
    color = str(args.get("color") or "").strip()
    colores_excluidos = [str(c).strip().lower() for c in (args.get("colores_excluidos") or []) if c]
    precio_min = args.get("precio_min")
    precio_max = args.get("precio_max")
    sucursal = str(args.get("sucursal") or "").strip()
    genero = str(args.get("genero") or "").strip()

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
        params: List[Any] = [ctx.id_empresa]

        if termino:
            sql += " AND (p.nombre ILIKE %s OR p.descripcion ILIKE %s OR p.codigo_producto ILIKE %s OR c.nombre ILIKE %s)"
            t_pat = f"%{termino}%"
            params.extend([t_pat, t_pat, t_pat, t_pat])

        if categoria:
            sql += " AND (c.nombre ILIKE %s OR p.nombre ILIKE %s)"
            params.extend([f"%{categoria}%", f"%{categoria}%"])

        if genero:
            sql += " AND (p.genero ILIKE %s OR p.genero ILIKE 'Unisex')"
            params.append(f"%{genero}%")

        if talla:
            sql += " AND t.nombre ILIKE %s"
            params.append(f"%{talla}%")

        if color and color.lower() not in ("colores claros", "colores oscuros", "claro", "oscuro"):
            sql += " AND col.nombre ILIKE %s"
            params.append(f"%{color}%")

        if precio_min is not None:
            sql += " AND p.precio >= %s"
            params.append(float(precio_min))

        if precio_max is not None:
            sql += " AND p.precio <= %s"
            params.append(float(precio_max))

        if sucursal:
            sql += " AND s.nombre ILIKE %s AND COALESCE(inv.stock_disponible, 0) > 0"
            params.append(f"%{sucursal}%")

        sql += """
            GROUP BY p.id_producto, p.nombre, p.codigo_producto, p.precio, c.nombre, p.genero, p.imagen_url, p.descripcion
            ORDER BY stock_total DESC, p.id_producto DESC
            LIMIT %s
        """
        params.append(max_results * 2)

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        # Si el filtro estricto de sucursal o color dejó 0 resultados, relajar ligeramente mantendo empresa y precio
        if not rows and (sucursal or color or talla):
            sql_fallback = """
                SELECT
                    p.id_producto, p.nombre, p.codigo_producto, COALESCE(p.precio, 0) as precio,
                    COALESCE(c.nombre, 'Moda') as categoria, COALESCE(p.genero, 'Unisex') as genero,
                    p.imagen_url, p.descripcion, COALESCE(SUM(inv.stock_disponible), 0) as stock_total
                FROM comercio.t_producto p
                LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
                LEFT JOIN comercio.t_producto_talla_color ptc ON p.id_producto = ptc.id_producto
                LEFT JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
                WHERE p.id_empresa = %s AND p.activo = true
            """
            fb_params: List[Any] = [ctx.id_empresa]
            if categoria:
                sql_fallback += " AND (c.nombre ILIKE %s OR p.nombre ILIKE %s)"
                fb_params.extend([f"%{categoria}%", f"%{categoria}%"])
            elif termino:
                sql_fallback += " AND (p.nombre ILIKE %s OR p.descripcion ILIKE %s)"
                fb_params.extend([f"%{termino}%", f"%{termino}%"])
            if precio_max is not None:
                sql_fallback += " AND p.precio <= %s"
                fb_params.append(float(precio_max))
            sql_fallback += " GROUP BY p.id_producto, p.nombre, p.codigo_producto, p.precio, c.nombre, p.genero, p.imagen_url, p.descripcion ORDER BY stock_total DESC LIMIT %s"
            fb_params.append(max_results)
            cur.execute(sql_fallback, tuple(fb_params))
            rows = cur.fetchall()

        productos = []
        for r in rows:
            tallas_list, colores_list = _enrich_product_variants(cur, r[0])
            if colores_excluidos:
                # Filtrar colores excluidos de la vista o descartar si solo existe en el color excluido
                colores_permitidos = [c for c in colores_list if not any(ex in c.lower() for ex in colores_excluidos)]
                if colores_list and not colores_permitidos:
                    continue
                colores_list = colores_permitidos

            productos.append({
                "id_producto": r[0],
                "nombre": r[1],
                "codigo_producto": r[2],
                "codigo": r[2],
                "precio": float(r[3]),
                "categoria": r[4],
                "genero": r[5],
                "imagen_url": r[6] or "assets/images/default-fashion.jpg",
                "descripcion": r[7] or "",
                "stock_disponible": int(r[8]),
                "tallas": tallas_list,
                "colores": colores_list,
                "sucursal_consultada": sucursal or None,
                "enlace_producto": f"/catalogo/{r[0]}"
            })
            if len(productos) >= max_results:
                break

        return {
            "total_encontrados": len(productos),
            "filtros_aplicados": {
                "termino": termino or None,
                "categoria": categoria or None,
                "talla": talla or None,
                "color": color or None,
                "colores_excluidos": colores_excluidos or None,
                "precio_max": precio_max,
                "sucursal": sucursal or None
            },
            "productos": productos
        }
    finally:
        conn.close()


def handle_comparar_productos(args: Dict[str, Any], ctx: AssistantSecurityContext, max_results: int = 5) -> Dict[str, Any]:
    ids_productos = args.get("ids_productos") or []
    nombres_productos = args.get("nombres_productos") or []
    categoria = str(args.get("categoria") or "").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        rows = []
        if ids_productos:
            clean_ids = [int(i) for i in ids_productos if str(i).isdigit()][:max_results]
            if clean_ids:
                placeholders = ",".join(["%s"] * len(clean_ids))
                cur.execute(f"""
                    SELECT p.id_producto, p.nombre, p.codigo_producto, COALESCE(p.precio, 0),
                           COALESCE(c.nombre, 'Moda'), COALESCE(p.genero, 'Unisex'), p.imagen_url, p.descripcion,
                           COALESCE(SUM(inv.stock_disponible), 0)
                    FROM comercio.t_producto p
                    LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
                    LEFT JOIN comercio.t_producto_talla_color ptc ON p.id_producto = ptc.id_producto
                    LEFT JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
                    WHERE p.id_empresa = %s AND p.id_producto IN ({placeholders})
                    GROUP BY p.id_producto, p.nombre, p.codigo_producto, p.precio, c.nombre, p.genero, p.imagen_url, p.descripcion
                """, tuple([ctx.id_empresa] + clean_ids))
                rows = cur.fetchall()

        if not rows and nombres_productos:
            for nom in nombres_productos[:max_results]:
                cur.execute("""
                    SELECT p.id_producto, p.nombre, p.codigo_producto, COALESCE(p.precio, 0),
                           COALESCE(c.nombre, 'Moda'), COALESCE(p.genero, 'Unisex'), p.imagen_url, p.descripcion,
                           COALESCE(SUM(inv.stock_disponible), 0)
                    FROM comercio.t_producto p
                    LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
                    LEFT JOIN comercio.t_producto_talla_color ptc ON p.id_producto = ptc.id_producto
                    LEFT JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
                    WHERE p.id_empresa = %s AND p.activo = true AND p.nombre ILIKE %s
                    GROUP BY p.id_producto, p.nombre, p.codigo_producto, p.precio, c.nombre, p.genero, p.imagen_url, p.descripcion
                    LIMIT 2
                """, (ctx.id_empresa, f"%{nom}%"))
                rows.extend(cur.fetchall())

        if not rows:
            sql_cat = """
                SELECT p.id_producto, p.nombre, p.codigo_producto, COALESCE(p.precio, 0),
                       COALESCE(c.nombre, 'Moda'), COALESCE(p.genero, 'Unisex'), p.imagen_url, p.descripcion,
                       COALESCE(SUM(inv.stock_disponible), 0)
                FROM comercio.t_producto p
                LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
                LEFT JOIN comercio.t_producto_talla_color ptc ON p.id_producto = ptc.id_producto
                LEFT JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
                WHERE p.id_empresa = %s AND p.activo = true
            """
            p_cat: List[Any] = [ctx.id_empresa]
            if categoria:
                sql_cat += " AND c.nombre ILIKE %s"
                p_cat.append(f"%{categoria}%")
            sql_cat += " GROUP BY p.id_producto, p.nombre, p.codigo_producto, p.precio, c.nombre, p.genero, p.imagen_url, p.descripcion ORDER BY p.precio ASC LIMIT 3"
            cur.execute(sql_cat, tuple(p_cat))
            rows = cur.fetchall()

        comparativa = []
        for r in rows[:max_results]:
            tallas, colores = _enrich_product_variants(cur, r[0])
            comparativa.append({
                "id_producto": r[0],
                "nombre": r[1],
                "codigo_producto": r[2],
                "precio": float(r[3]),
                "categoria": r[4],
                "genero": r[5],
                "imagen_url": r[6] or "assets/images/default-fashion.jpg",
                "descripcion": r[7] or "",
                "stock_disponible": int(r[8]),
                "tallas": tallas,
                "colores": colores
            })

        comparativa.sort(key=lambda x: x["precio"])
        mas_economico = comparativa[0] if comparativa else None
        mayor_stock = max(comparativa, key=lambda x: x["stock_disponible"]) if comparativa else None

        return {
            "total_comparados": len(comparativa),
            "productos_comparados": comparativa,
            "productos": comparativa,
            "items": comparativa,
            "mas_economico": mas_economico,
            "mayor_disponibilidad": mayor_stock
        }
    finally:
        conn.close()


def handle_buscar_productos_similares(args: Dict[str, Any], ctx: AssistantSecurityContext, max_results: int = 6) -> Dict[str, Any]:
    id_ref = args.get("id_producto_referencia")
    nom_ref = str(args.get("nombre_referencia") or "").strip()
    mas_economico = bool(args.get("mas_economico", False))
    precio_max = args.get("precio_max")
    talla = str(args.get("talla") or "").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        ref_row = None
        if id_ref:
            cur.execute("""
                SELECT id_producto, nombre, id_categoria, COALESCE(precio, 0), genero
                FROM comercio.t_producto
                WHERE id_producto = %s AND id_empresa = %s LIMIT 1
            """, (int(id_ref), ctx.id_empresa))
            ref_row = cur.fetchone()
        elif nom_ref:
            cur.execute("""
                SELECT id_producto, nombre, id_categoria, COALESCE(precio, 0), genero
                FROM comercio.t_producto
                WHERE nombre ILIKE %s AND id_empresa = %s LIMIT 1
            """, (f"%{nom_ref}%", ctx.id_empresa))
            ref_row = cur.fetchone()

        sql = """
            SELECT
                p.id_producto, p.nombre, p.codigo_producto, COALESCE(p.precio, 0) as precio,
                COALESCE(c.nombre, 'Moda') as categoria, COALESCE(p.genero, 'Unisex') as genero,
                p.imagen_url, p.descripcion, COALESCE(SUM(inv.stock_disponible), 0) as stock_total
            FROM comercio.t_producto p
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            LEFT JOIN comercio.t_producto_talla_color ptc ON p.id_producto = ptc.id_producto
            LEFT JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
            LEFT JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
            WHERE p.id_empresa = %s AND p.activo = true
        """
        params: List[Any] = [ctx.id_empresa]

        ref_info = None
        if ref_row:
            ref_id, ref_nom, ref_cat_id, ref_precio, ref_gen = ref_row
            ref_info = {"id_producto": ref_id, "nombre": ref_nom, "precio": float(ref_precio)}
            sql += " AND p.id_producto != %s"
            params.append(ref_id)
            if ref_cat_id:
                sql += " AND p.id_categoria = %s"
                params.append(ref_cat_id)
            if mas_economico and not precio_max:
                precio_max = float(ref_precio)

        if precio_max is not None:
            sql += " AND p.precio <= %s"
            params.append(float(precio_max))

        if talla:
            sql += " AND t.nombre ILIKE %s"
            params.append(f"%{talla}%")

        sql += """
            GROUP BY p.id_producto, p.nombre, p.codigo_producto, p.precio, c.nombre, p.genero, p.imagen_url, p.descripcion
            ORDER BY p.precio ASC, stock_total DESC
            LIMIT %s
        """
        params.append(max_results)

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        # Si filtrar por la misma categoría con menor precio no arrojó resultados, ampliar a otras categorías dentro del precio
        if not rows and ref_row:
            cur.execute("""
                SELECT
                    p.id_producto, p.nombre, p.codigo_producto, COALESCE(p.precio, 0) as precio,
                    COALESCE(c.nombre, 'Moda') as categoria, COALESCE(p.genero, 'Unisex') as genero,
                    p.imagen_url, p.descripcion, COALESCE(SUM(inv.stock_disponible), 0) as stock_total
                FROM comercio.t_producto p
                LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
                LEFT JOIN comercio.t_producto_talla_color ptc ON p.id_producto = ptc.id_producto
                LEFT JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
                WHERE p.id_empresa = %s AND p.activo = true AND p.id_producto != %s
                GROUP BY p.id_producto, p.nombre, p.codigo_producto, p.precio, c.nombre, p.genero, p.imagen_url, p.descripcion
                ORDER BY precio ASC
                LIMIT %s
            """, (ctx.id_empresa, ref_row[0], max_results))
            rows = cur.fetchall()

        similares = []
        for r in rows:
            tallas_l, colores_l = _enrich_product_variants(cur, r[0])
            similares.append({
                "id_producto": r[0],
                "nombre": r[1],
                "codigo_producto": r[2],
                "precio": float(r[3]),
                "categoria": r[4],
                "genero": r[5],
                "imagen_url": r[6] or "assets/images/default-fashion.jpg",
                "descripcion": r[7] or "",
                "stock_disponible": int(r[8]),
                "tallas": tallas_l,
                "colores": colores_l
            })

        return {
            "producto_referencia": ref_info,
            "mas_economico_solicitado": mas_economico,
            "total_encontrados": len(similares),
            "productos": similares
        }
    finally:
        conn.close()


def handle_recomendar_outfit_avanzado(args: Dict[str, Any], ctx: AssistantSecurityContext) -> Dict[str, Any]:
    ocasion = str(args.get("ocasion") or "evento especial").strip().lower()
    genero = str(args.get("genero") or "").strip()
    estilo = str(args.get("estilo_preferido") or "elegante y refinado").strip()
    talla = str(args.get("talla") or "").strip()
    colores_pref = [str(c).strip().lower() for c in (args.get("colores_preferidos") or []) if c]
    colores_excl = [str(c).strip().lower() for c in (args.get("colores_excluidos") or []) if c]
    presupuesto_max = args.get("presupuesto_max")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT
                p.id_producto,
                p.nombre,
                COALESCE(p.precio, 0) as precio,
                COALESCE(c.nombre, 'Moda') as categoria,
                p.imagen_url,
                p.descripcion,
                COALESCE(SUM(inv.stock_disponible), 0) as stock_total
            FROM comercio.t_producto p
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            LEFT JOIN comercio.t_producto_talla_color ptc ON p.id_producto = ptc.id_producto
            LEFT JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
            WHERE p.id_empresa = %s AND p.activo = true
        """
        params: List[Any] = [ctx.id_empresa]
        if genero:
            sql += " AND (p.genero ILIKE %s OR p.genero = 'Unisex')"
            params.append(f"%{genero}%")

        sql += " GROUP BY p.id_producto, p.nombre, p.precio, c.nombre, p.imagen_url, p.descripcion ORDER BY stock_total DESC, precio ASC LIMIT 30"
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        piezas_principales = []
        complementos = []

        kw_principal = ["vestido", "traje", "blazer", "conjunto", "blusa", "camisa", "pantalon", "falda"]
        if any(w in ocasion for w in ["boda", "gala", "cena", "coctel", "fiesta"]):
            kw_principal = ["vestido", "traje", "blazer", "blusa", "falda", "pantalon"]

        presupuesto_acumulado = 0.0
        limite_presupuesto = float(presupuesto_max) if presupuesto_max else 999999.0

        for r in rows:
            p_id, p_nom, p_prec_raw, p_cat, p_img, p_desc, p_stk = r
            p_prec = float(p_prec_raw or 0)
            tallas_l, colores_l = _enrich_product_variants(cur, p_id)

            # Respetar restricción de colores excluidos (ej. 'prefiero no usar negro')
            if colores_excl:
                colores_limpios = [c for c in colores_l if not any(ex in c.lower() for ex in colores_excl)]
                if colores_l and not colores_limpios:
                    continue
                if any(ex in p_nom.lower() for ex in colores_excl):
                    continue
                colores_l = colores_limpios

            if talla and tallas_l and not any(t.upper() == talla.upper() for t in tallas_l):
                continue

            item = {
                "id_producto": p_id,
                "nombre": p_nom,
                "precio": p_prec,
                "categoria": p_cat,
                "imagen_url": p_img or "assets/images/default-fashion.jpg",
                "descripcion": p_desc or "",
                "stock_disponible": int(p_stk or 0),
                "tallas": tallas_l,
                "colores": colores_l
            }

            nom_l = p_nom.lower()
            cat_l = p_cat.lower()
            es_accesorio = any(k in nom_l or k in cat_l for k in ["accesorio", "cartera", "bolso", "cinturon", "calzado", "zapato", "tacones"])

            if es_accesorio:
                if len(complementos) < 2 and (presupuesto_acumulado + p_prec) <= limite_presupuesto:
                    complementos.append(item)
                    presupuesto_acumulado += p_prec
            elif any(k in nom_l or k in cat_l for k in kw_principal):
                if len(piezas_principales) < 2 and (presupuesto_acumulado + p_prec) <= limite_presupuesto:
                    piezas_principales.append(item)
                    presupuesto_acumulado += p_prec

        if not piezas_principales and rows:
            for r in rows:
                p_prec = float(r[2] or 0)
                if p_prec <= limite_presupuesto:
                    tallas_l, colores_l = _enrich_product_variants(cur, r[0])
                    piezas_principales.append({
                        "id_producto": r[0], "nombre": r[1], "precio": p_prec,
                        "categoria": r[3], "imagen_url": r[4] or "assets/images/default-fashion.jpg",
                        "descripcion": r[5] or "", "stock_disponible": int(r[6] or 0),
                        "tallas": tallas_l, "colores": colores_l
                    })
                    presupuesto_acumulado += p_prec
                    if len(piezas_principales) >= 2:
                        break

        todos_items = piezas_principales + complementos
        total_look = round(sum(i["precio"] for i in todos_items), 2)

        consejo = (
            f"Para una ocasión de {ocasion}, seleccionamos piezas reales en existencia que equilibran silueta y textura"
            + (f", evitando tonos {', '.join(colores_excl)}" if colores_excl else "")
            + (f" y respetando tu tope presupuestario de Bs. {presupuesto_max}." if presupuesto_max else ".")
        )

        return {
            "ocasion": ocasion.capitalize(),
            "estilo": estilo.capitalize(),
            "colores_excluidos": colores_excl,
            "presupuesto_max_bs": presupuesto_max,
            "presupuesto_estimado_bs": total_look,
            "piezas_principales": piezas_principales,
            "complementos_accesorios": complementos,
            "consejo_estilismo": consejo,
            "productos": todos_items
        }
    finally:
        conn.close()


def handle_consultar_disponibilidad_sucursal(args: Dict[str, Any], ctx: AssistantSecurityContext) -> Dict[str, Any]:
    id_prod = args.get("id_producto")
    nom_prenda = str(args.get("nombre_prenda") or "").strip()
    talla = str(args.get("talla") or "").strip()
    sucursal = str(args.get("sucursal") or "").strip()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT 
                s.nombre as sucursal,
                p.id_producto,
                p.nombre as prenda,
                t.nombre as talla,
                col.nombre as color,
                COALESCE(inv.stock_disponible, 0) as stock_disponible,
                COALESCE(p.precio, 0) as precio
            FROM comercio.t_inventario inv
            JOIN comercio.t_sucursal s ON inv.id_sucursal = s.id_sucursal
            JOIN comercio.t_producto_talla_color ptc ON inv.id_variante = ptc.id_variante
            JOIN comercio.t_producto p ON ptc.id_producto = p.id_producto
            LEFT JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
            LEFT JOIN comercio.t_color col ON ptc.id_color = col.id_color
            WHERE p.id_empresa = %s AND s.id_empresa = %s AND p.activo = true AND s.activo = true
              AND COALESCE(inv.stock_disponible, 0) > 0
        """
        params: List[Any] = [ctx.id_empresa, ctx.id_empresa]

        if id_prod:
            sql += " AND p.id_producto = %s"
            params.append(int(id_prod))
        elif nom_prenda:
            sql += " AND (p.nombre ILIKE %s OR p.codigo_producto ILIKE %s)"
            params.extend([f"%{nom_prenda}%", f"%{nom_prenda}%"])

        if talla:
            sql += " AND t.nombre ILIKE %s"
            params.append(f"%{talla}%")

        if sucursal:
            sql += " AND s.nombre ILIKE %s"
            params.append(f"%{sucursal}%")

        sql += " ORDER BY inv.stock_disponible DESC, s.nombre ASC LIMIT 12"
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        disponibilidad = []
        resumen_sucursales: Dict[str, int] = {}
        for r in rows:
            stk = int(r[5] or 0)
            resumen_sucursales[r[0]] = resumen_sucursales.get(r[0], 0) + stk
            disponibilidad.append({
                "sucursal": r[0],
                "id_producto": r[1],
                "prenda": r[2],
                "talla": r[3] or "Única",
                "color": r[4] or "Estándar",
                "stock_disponible": stk,
                "precio": float(r[6] or 0)
            })

        sucursal_mayor = max(resumen_sucursales.items(), key=lambda x: x[1])[0] if resumen_sucursales else None

        return {
            "total_variantes_con_stock": len(disponibilidad),
            "sucursal_con_mas_opciones": sucursal_mayor,
            "resumen_por_sucursal": resumen_sucursales,
            "items": disponibilidad
        }
    finally:
        conn.close()


def handle_consultar_promociones(args: Dict[str, Any], ctx: AssistantSecurityContext) -> Dict[str, Any]:
    categoria = str(args.get("categoria") or "").strip()
    presupuesto_max = args.get("presupuesto_max")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT
                p.id_producto, p.nombre, p.codigo_producto, COALESCE(p.precio, 0) as precio,
                COALESCE(c.nombre, 'Colección') as categoria, COALESCE(p.temporada, 'Temporada Actual') as temporada,
                p.imagen_url, p.descripcion, COALESCE(SUM(inv.stock_disponible), 0) as stock_total
            FROM comercio.t_producto p
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            LEFT JOIN comercio.t_producto_talla_color ptc ON p.id_producto = ptc.id_producto
            LEFT JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
            WHERE p.id_empresa = %s AND p.activo = true
        """
        params: List[Any] = [ctx.id_empresa]
        if categoria:
            sql += " AND c.nombre ILIKE %s"
            params.append(f"%{categoria}%")
        if presupuesto_max:
            sql += " AND p.precio <= %s"
            params.append(float(presupuesto_max))

        sql += """
            GROUP BY p.id_producto, p.nombre, p.codigo_producto, p.precio, c.nombre, p.temporada, p.imagen_url, p.descripcion
            HAVING COALESCE(SUM(inv.stock_disponible), 0) > 0
            ORDER BY precio ASC
            LIMIT 6
        """
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        promos = []
        for r in rows:
            tallas_l, colores_l = _enrich_product_variants(cur, r[0])
            promos.append({
                "id_producto": r[0],
                "nombre": r[1],
                "codigo_producto": r[2],
                "precio": float(r[3]),
                "categoria": r[4],
                "temporada": r[5],
                "imagen_url": r[6] or "assets/images/default-fashion.jpg",
                "descripcion": r[7] or "",
                "stock_disponible": int(r[8]),
                "tallas": tallas_l,
                "colores": colores_l,
                "beneficio": "Envío gratis en compras mayores a Bs. 600 y reserva gratuita por 48h en boutique."
            })
        return {
            "total_oportunidades": len(promos),
            "politica_beneficios": "Envío express sin costo desde Bs. 600 y cita en probador privado sin pago anticipado.",
            "productos": promos
        }
    finally:
        conn.close()


# =====================================================================
# HERRAMIENTAS ADMINISTRATIVAS Y DE INTELIGENCIA COMERCIAL (CU20W-CU23W)
# =====================================================================

def handle_consultar_ventas_por_periodo(args: Dict[str, Any], ctx: AssistantSecurityContext) -> Dict[str, Any]:
    p_actual_str = str(args.get("periodo_actual") or "este_mes")
    p_comp_str = str(args.get("periodo_comparacion") or "mes_pasado")
    sucursal_req = verify_branch_access(ctx, args.get("sucursal"))

    f_ini_1, f_fin_1, label_1 = resolve_relative_period(p_actual_str)
    f_ini_2, f_fin_2, label_2 = resolve_relative_period(p_comp_str)

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        def _query_periodo(d_ini: date, d_fin: date) -> Dict[str, Any]:
            sql = """
                SELECT 
                    COUNT(v.id_venta),
                    COALESCE(SUM(v.total), 0),
                    COALESCE(AVG(v.total), 0)
                FROM comercio.t_venta v
                LEFT JOIN comercio.t_sucursal s ON v.id_sucursal = s.id_sucursal
                WHERE v.id_empresa = %s
                  AND v.fecha_venta >= %s
                  AND v.fecha_venta < %s
                  AND UPPER(COALESCE(v.estado, '')) NOT IN ('CANCELADA', 'ANULADA', 'PENDIENTE_PAGO')
            """
            p: List[Any] = [ctx.id_empresa, d_ini, d_fin + timedelta(days=1)]
            if sucursal_req:
                sql += " AND s.nombre ILIKE %s"
                p.append(f"%{sucursal_req}%")
            cur.execute(sql, tuple(p))
            r = cur.fetchone()
            return {
                "transacciones": int(r[0] or 0) if r else 0,
                "ingresos_bs": round(float(r[1] or 0.0), 2) if r else 0.0,
                "ticket_promedio_bs": round(float(r[2] or 0.0), 2) if r else 0.0
            }

        m_actual = _query_periodo(f_ini_1, f_fin_1)
        m_anterior = _query_periodo(f_ini_2, f_fin_2)

        ing_1 = m_actual["ingresos_bs"]
        ing_2 = m_anterior["ingresos_bs"]
        diff_bs = round(ing_1 - ing_2, 2)
        if ing_2 > 0:
            var_pct = round(((ing_1 - ing_2) / ing_2) * 100.0, 2)
        else:
            var_pct = 100.0 if ing_1 > 0 else 0.0

        tendencia = "CRECIMIENTO" if diff_bs > 0 else ("CONTRACCIÓN" if diff_bs < 0 else "ESTABLE")

        return {
            "sucursal": sucursal_req or "Todas las sucursales",
            "periodo_actual": {
                "nombre": label_1,
                "desde": f_ini_1.strftime("%d/%m/%Y"),
                "hasta": f_fin_1.strftime("%d/%m/%Y"),
                **m_actual
            },
            "periodo_comparacion": {
                "nombre": label_2,
                "desde": f_ini_2.strftime("%d/%m/%Y"),
                "hasta": f_fin_2.strftime("%d/%m/%Y"),
                **m_anterior
            },
            "diferencia_bs": diff_bs,
            "variacion_porcentual": var_pct,
            "tendencia": tendencia
        }
    finally:
        conn.close()


def handle_consultar_productos_mas_vendidos(args: Dict[str, Any], ctx: AssistantSecurityContext) -> Dict[str, Any]:
    periodo_str = str(args.get("periodo") or "ultimos_30_dias")
    sucursal_req = verify_branch_access(ctx, args.get("sucursal"))
    limite = min(int(args.get("limite") or 8), 12)

    f_ini, f_fin, label = resolve_relative_period(periodo_str)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT 
                p.id_producto,
                p.nombre as prenda,
                COALESCE(c.nombre, 'Moda') as categoria,
                SUM(dv.cantidad) as unidades_vendidas,
                SUM(dv.subtotal) as ingresos_bs,
                COALESCE((
                    SELECT SUM(inv.stock_disponible)
                    FROM comercio.t_producto_talla_color ptc2
                    JOIN comercio.t_inventario inv ON ptc2.id_variante = inv.id_variante
                    WHERE ptc2.id_producto = p.id_producto
                ), 0) as stock_disponible
            FROM comercio.t_detalle_venta dv
            JOIN comercio.t_venta v ON dv.id_venta = v.id_venta
            LEFT JOIN comercio.t_sucursal s ON v.id_sucursal = s.id_sucursal
            JOIN comercio.t_producto_talla_color ptc ON dv.id_variante = ptc.id_variante
            JOIN comercio.t_producto p ON ptc.id_producto = p.id_producto
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            WHERE v.id_empresa = %s
              AND v.fecha_venta >= %s
              AND v.fecha_venta < %s
              AND UPPER(COALESCE(v.estado, '')) NOT IN ('CANCELADA', 'ANULADA', 'PENDIENTE_PAGO')
        """
        params: List[Any] = [ctx.id_empresa, f_ini, f_fin + timedelta(days=1)]
        if sucursal_req:
            sql += " AND s.nombre ILIKE %s"
            params.append(f"%{sucursal_req}%")

        sql += """
            GROUP BY p.id_producto, p.nombre, c.nombre
            ORDER BY unidades_vendidas DESC, ingresos_bs DESC
            LIMIT %s
        """
        params.append(limite)

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        ranking = []
        for idx, r in enumerate(rows, start=1):
            uds = int(r[3] or 0)
            stk = int(r[5] or 0)
            alerta_rotacion = "ALTA DEMANDA / STOCK CRÍTICO" if stk <= 3 else "ROTACIÓN SALUDABLE"
            ranking.append({
                "posicion": idx,
                "id_producto": r[0],
                "prenda": r[1],
                "categoria": r[2],
                "unidades_vendidas": uds,
                "total_bs": round(float(r[4] or 0.0), 2),
                "stock_disponible": stk,
                "estado_comercial": alerta_rotacion
            })

        return {
            "periodo": label,
            "sucursal": sucursal_req or "Todas",
            "total_productos": len(ranking),
            "items": ranking
        }
    finally:
        conn.close()


def handle_consultar_productos_sin_rotacion(args: Dict[str, Any], ctx: AssistantSecurityContext) -> Dict[str, Any]:
    sucursal_req = verify_branch_access(ctx, args.get("sucursal"))
    limite = min(int(args.get("limite") or 8), 12)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT 
                p.id_producto,
                p.nombre as prenda,
                COALESCE(c.nombre, 'Moda') as categoria,
                s.nombre as sucursal,
                COALESCE(SUM(inv.stock_disponible), 0) as stock_estancado,
                COALESCE(p.precio, 0) as precio_unitario,
                COALESCE(SUM(inv.stock_disponible) * p.precio, 0) as capital_retenido_bs,
                COALESCE((
                    SELECT COUNT(dv.id_detalle_venta)
                    FROM comercio.t_detalle_venta dv
                    JOIN comercio.t_venta v ON dv.id_venta = v.id_venta
                    JOIN comercio.t_producto_talla_color ptc2 ON dv.id_variante = ptc2.id_variante
                    WHERE ptc2.id_producto = p.id_producto
                      AND v.id_empresa = %s
                      AND v.fecha_venta >= CURRENT_DATE - 30
                      AND UPPER(COALESCE(v.estado, '')) NOT IN ('CANCELADA', 'ANULADA')
                ), 0) as ventas_30d
            FROM comercio.t_inventario inv
            JOIN comercio.t_sucursal s ON inv.id_sucursal = s.id_sucursal
            JOIN comercio.t_producto_talla_color ptc ON inv.id_variante = ptc.id_variante
            JOIN comercio.t_producto p ON ptc.id_producto = p.id_producto
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            WHERE p.id_empresa = %s AND p.activo = true AND COALESCE(inv.stock_disponible, 0) > 0
        """
        params: List[Any] = [ctx.id_empresa, ctx.id_empresa]
        if sucursal_req:
            sql += " AND s.nombre ILIKE %s"
            params.append(f"%{sucursal_req}%")

        sql += """
            GROUP BY p.id_producto, p.nombre, c.nombre, s.nombre, p.precio
            ORDER BY ventas_30d ASC, capital_retenido_bs DESC
            LIMIT %s
        """
        params.append(limite)

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        inmovilizados = []
        for r in rows:
            v30 = int(r[7] or 0)
            stk = int(r[4] or 0)
            cap = round(float(r[6] or 0.0), 2)
            recomendacion = (
                "Evaluar exhibición destacada en vitrina o traslado inter-sucursal"
                if v30 == 0 else "Rotación lenta: acompañar en sugerencias de outfits"
            )
            inmovilizados.append({
                "id_producto": r[0],
                "prenda": r[1],
                "categoria": r[2],
                "sucursal": r[3],
                "stock_disponible": stk,
                "ventas_ultimos_30d": v30,
                "total_bs": cap,
                "capital_retenido_bs": cap,
                "accion_sugerida": recomendacion
            })

        return {
            "sucursal": sucursal_req or "Todas",
            "total_detectados": len(inmovilizados),
            "items": inmovilizados
        }
    finally:
        conn.close()


def handle_consultar_reposicion_cu23w(args: Dict[str, Any], ctx: AssistantSecurityContext) -> Dict[str, Any]:
    """Consume el servicio oficial CU23W (calcular_recomendaciones_reposicion_db)."""
    from app.modules.ia.services.demanda_forecast_services import calcular_recomendaciones_reposicion_db

    sucursal_req = verify_branch_access(ctx, args.get("sucursal"))
    categoria = str(args.get("categoria") or "").strip().lower()
    lead_time = max(1, min(int(args.get("lead_time_dias") or 7), 60))

    id_sucursal_target = None
    if ctx.alcance == "SUCURSAL" and ctx.sucursales_autorizadas:
        id_sucursal_target = ctx.sucursales_autorizadas[0]

    recs = calcular_recomendaciones_reposicion_db(
        id_empresa=ctx.id_empresa,
        id_sucursal=id_sucursal_target,
        lead_time_dias=lead_time
    )

    if sucursal_req:
        recs = [r for r in recs if sucursal_req.lower() in str(r.get("sucursal", "")).lower()]
    if categoria:
        recs = [r for r in recs if categoria in str(r.get("categoria", "")).lower() or categoria in str(r.get("producto", "")).lower()]

    top_recs = recs[:10]
    formatted_items = []
    for r in top_recs:
        formatted_items.append({
            "prenda": r["producto"],
            "categoria": r["categoria"],
            "talla": r["talla"],
            "color": r["color"],
            "sucursal": r["sucursal"],
            "stock_actual": r["stock_disponible"],
            "stock_disponible": r["stock_disponible"],
            "stock_minimo": r["stock_minimo"],
            "ritmo_diario": r["ritmo_diario_estimado"],
            "dias_cobertura": r["dias_cobertura"],
            "sugerencia_reposicion_unidades": r["reposicion_sugerida"],
            "prioridad": r["riesgo_rotura"],
            "inversion_estimada_bs": r["inversion_estimada_bs"],
            "explicacion": r["explicacion"]
        })

    return {
        "lead_time_dias": lead_time,
        "total_alertas_reposicion": len(formatted_items),
        "inversion_total_sugerida_bs": round(sum(i["inversion_estimada_bs"] for i in formatted_items), 2),
        "recomendaciones": formatted_items,
        "items": formatted_items
    }


def handle_consultar_demanda_proyectada_cu23w(args: Dict[str, Any], ctx: AssistantSecurityContext) -> Dict[str, Any]:
    """Consume el servicio oficial CU23W de predicción de series temporales e intervalos de confianza."""
    from app.modules.ia.services.demanda_forecast_services import (
        obtener_serie_temporal_ventas,
        predecir_demanda_serie,
        evaluar_backtesting_modelo
    )

    dias_proy = max(3, min(int(args.get("dias_proyeccion") or 14), 60))
    dias_hist = max(14, min(int(args.get("dias_historia") or 60), 180))
    id_prod = args.get("id_producto")
    verify_branch_access(ctx, args.get("sucursal"))

    id_sucursal_target = None
    if ctx.alcance == "SUCURSAL" and ctx.sucursales_autorizadas:
        id_sucursal_target = ctx.sucursales_autorizadas[0]

    serie = obtener_serie_temporal_ventas(
        id_empresa=ctx.id_empresa,
        id_sucursal=id_sucursal_target,
        id_producto=int(id_prod) if id_prod else None,
        dias_historia=dias_hist
    )
    forecast = predecir_demanda_serie(serie, dias_proyeccion=dias_proy)
    backtest = evaluar_backtesting_modelo(serie, dias_test=min(14, dias_proy))

    unidades_proyectadas = round(sum(p["prediccion"] for p in forecast["proyecciones"]), 1)

    return {
        "dias_analizados": dias_hist,
        "dias_proyectados": dias_proy,
        "tendencia": forecast["tendencia"],
        "tasa_crecimiento_diario": forecast["tasa_crecimiento_diario"],
        "unidades_totales_proyectadas": unidades_proyectadas,
        "precision_modelo_pct": backtest["precision_pct"],
        "mae": backtest["mae"],
        "rmse": backtest["rmse"],
        "mape": backtest["mape"],
        "proyecciones": forecast["proyecciones"][:14]
    }


def handle_consultar_riesgo_agotamiento_cu23w(args: Dict[str, Any], ctx: AssistantSecurityContext) -> Dict[str, Any]:
    res = handle_consultar_reposicion_cu23w(args, ctx)
    criticos = [
        item for item in res.get("recomendaciones", [])
        if item.get("prioridad") in ("CRITICO", "ALTO")
    ]
    return {
        "lead_time_dias": res.get("lead_time_dias", 7),
        "total_riesgo_quiebre": len(criticos),
        "alertas_criticas": criticos,
        "items": criticos
    }


class ToolExecutor:
    """
    Ejecutor controlado de herramientas con:
    - Verificación en lista blanca.
    - Bloqueo de herramientas de escritura.
    - Autorización RBAC y de alcance independiente del modelo.
    - Detección de ciclos de llamadas repetidas.
    - Límite de herramientas por interacción.
    - Sanitización de resultados contra Prompt Injection indirecto.
    """
    MAX_TOOLS_PER_TURN = 4

    def __init__(self, ctx: AssistantSecurityContext, session_slots: Optional[Dict[str, Any]] = None):
        self.ctx = ctx
        self.session_slots = session_slots or {}
        self.executed_signatures: set = set()
        self.execution_log: List[Dict[str, Any]] = []

    def execute(self, tool_name: str, raw_args: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], str]:
        t0 = time.perf_counter()
        clean_name = str(tool_name or "").strip()
        args = dict(raw_args) if isinstance(raw_args, dict) else {}

        # 1. Bloquear operaciones de escritura o destructivas
        if clean_name.lower() in FORBIDDEN_WRITE_TOOLS or any(
             clean_name.lower().startswith(p) for p in ("eliminar_", "borrar_", "modificar_", "actualizar_", "anular_")
        ):
            raise AISecurityViolationError(
                f"Operación denegada: La herramienta '{clean_name}' intenta realizar una escritura no permitida.",
                status_code=403,
                code="WRITE_TOOL_FORBIDDEN"
            )

        # 2. Verificar existencia en lista blanca (ToolRegistry)
        tool_def = ToolRegistry.get_tool(clean_name)
        if not tool_def:
            raise AIToolExecutionError(
                f"La herramienta solicitada '{clean_name}' no existe en el registro oficial.",
                tool_name=clean_name,
                code="UNKNOWN_TOOL"
            )

        # 3. Verificación RBAC y de alcance independiente del LLM
        if not ToolRegistry.is_authorized(tool_def, self.ctx):
            logger.warning(
                f"Intento no autorizado de ejecutar '{clean_name}' por usuario={self.ctx.id_usuario} "
                f"alcance={self.ctx.alcance} roles={self.ctx.roles}"
            )
            raise AISecurityViolationError(
                f"Acceso denegado: Su rol ({self.ctx.alcance}) no tiene permisos para ejecutar '{clean_name}'.",
                status_code=403,
                code="UNAUTHORIZED_TOOL_CALL"
            )

        # 4. Control de límite de herramientas por turno
        if len(self.execution_log) >= self.MAX_TOOLS_PER_TURN:
            return {
                "aviso": "Se alcanzó el límite máximo de herramientas por consulta.",
                "items": []
            }, "texto"

        # 5. Detección de ciclos (evitar ejecutar la misma herramienta con idénticos argumentos)
        canonical_sig = f"{clean_name}:{json.dumps(args, sort_keys=True, default=str)}"
        if canonical_sig in self.executed_signatures:
            return {
                "aviso": f"La consulta '{clean_name}' ya fue ejecutada en este turno.",
                "items": []
            }, tool_def.widget_type
        self.executed_signatures.add(canonical_sig)

        # 6. Validar acceso a sucursal en herramientas administrativas
        if tool_def.is_admin_tool:
            suc_arg = args.get("sucursal")
            effective_suc = verify_branch_access(self.ctx, suc_arg)
            if effective_suc:
                args["sucursal"] = effective_suc

        # 7. Despacho hacia los manejadores verificados
        if clean_name == "buscar_prendas_avanzada":
            result = handle_buscar_prendas_avanzada(args, self.ctx, max_results=tool_def.max_results)
            w_type = "productos"
        elif clean_name == "comparar_productos":
            result = handle_comparar_productos(args, self.ctx, max_results=tool_def.max_results)
            w_type = "comparacion"
        elif clean_name == "buscar_productos_similares":
            result = handle_buscar_productos_similares(args, self.ctx, max_results=tool_def.max_results)
            w_type = "productos"
        elif clean_name == "recomendar_outfit_estilo":
            result = handle_recomendar_outfit_avanzado(args, self.ctx)
            w_type = "outfit"
        elif clean_name == "consultar_disponibilidad_sucursal":
            result = handle_consultar_disponibilidad_sucursal(args, self.ctx)
            w_type = "tabla"
        elif clean_name == "consultar_promociones":
            result = handle_consultar_promociones(args, self.ctx)
            w_type = "productos"
        elif clean_name == "consultar_mis_recomendaciones_personalizadas":
            from app.modules.ia.services.ml_preferencias_services import obtener_recomendaciones_cliente
            lim = min(int(args.get("limite") or 4), tool_def.max_results)
            merged_prefs = dict(self.session_slots)
            for k in ("categoria", "talla", "precio_max"):
                if args.get(k):
                    merged_prefs[k] = args[k]
            recs = obtener_recomendaciones_cliente(
                self.ctx.id_usuario,
                self.ctx.id_empresa,
                limite=lim,
                preferencias_sesion=merged_prefs
            )
            result = {"recomendaciones": recs, "total": len(recs), "productos": recs}
            w_type = "recomendaciones"
        elif clean_name == "consultar_ventas_por_periodo":
            result = handle_consultar_ventas_por_periodo(args, self.ctx)
            w_type = "comparacion"
        elif clean_name == "consultar_productos_mas_vendidos":
            result = handle_consultar_productos_mas_vendidos(args, self.ctx)
            w_type = "tabla"
        elif clean_name == "consultar_productos_sin_rotacion":
            result = handle_consultar_productos_sin_rotacion(args, self.ctx)
            w_type = "alertas"
        elif clean_name == "consultar_recomendaciones_reposicion_stock":
            result = handle_consultar_reposicion_cu23w(args, self.ctx)
            w_type = "recomendaciones"
        elif clean_name == "consultar_demanda_proyectada":
            result = handle_consultar_demanda_proyectada_cu23w(args, self.ctx)
            w_type = "predicciones"
        elif clean_name == "consultar_riesgo_agotamiento":
            result = handle_consultar_riesgo_agotamiento_cu23w(args, self.ctx)
            w_type = "alertas"
        else:
            # Delegar en las herramientas base existentes en asistente_services
            from app.modules.ia.services import asistente_services
            effective_token = self.ctx.token_data or {
                "id_usuario": self.ctx.id_usuario,
                "id_empresa": self.ctx.id_empresa,
                "roles": self.ctx.roles,
                "alcance": self.ctx.alcance
            }
            tool_lookup = "consultar_indicadores_kpi_generales" if clean_name == "consultar_kpis_empresa" else clean_name
            result, w_type = asistente_services.despachar_herramienta(
                tool_lookup, args, effective_token, self.ctx.id_empresa
            )
            if clean_name == "consultar_mis_pedidos":
                w_type = "seguimiento_pedido"
            elif clean_name == "consultar_inventario_alertas":
                w_type = "alertas"

        # 8. Sanitizar contenido recuperado de la BD (prevenir Indirect Prompt Injection) y truncar excesos
        sanitized_result = sanitize_untrusted_db_content(result)
        for list_key in ("productos", "items", "pedidos", "reservas", "recomendaciones", "sucursales"):
            if isinstance(sanitized_result, dict) and isinstance(sanitized_result.get(list_key), list):
                sanitized_result[list_key] = sanitized_result[list_key][: tool_def.max_results]

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        self.execution_log.append({
            "tool": clean_name,
            "latency_ms": elapsed_ms,
            "widget_type": w_type
        })

        return sanitized_result, w_type
