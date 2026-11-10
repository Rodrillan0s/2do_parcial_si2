"""
Mini Machine Learning - Preference Learning & Content-Based Recommendation Engine
Módulo: IA & Catálogo de Aurora Store
Tablas PostgreSQL: comercio.t_preferencia_cliente, comercio.t_recomendacion
"""

import math
import logging
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import psycopg2
from app.core.config import Config

logger = logging.getLogger(__name__)


def _get_db_connection():
    return psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        connect_timeout=10
    )


class MiniMLPreferenceEngine:
    """
    Mini Machine Learning Engine basado en extracción de perfiles de usuario
    y afinidad vectorial (Content-Based Feature Weighting Recommender).
    
    Pesos del modelo de afinidad:
    - w_categoria: 0.40 (Afinidad por silueta o tipo de prenda)
    - w_talla:     0.25 (Fit anatómico / talla habitual del cliente)
    - w_color:     0.20 (Preferencia estética de paleta cromática)
    - w_precio:    0.15 (Afinidad al rango de inversión histórico)
    """

    WEIGHT_CATEGORY = 0.40
    WEIGHT_SIZE = 0.25
    WEIGHT_COLOR = 0.20
    WEIGHT_PRICE = 0.15

    @classmethod
    def extraer_vector_cliente(cls, cur, id_cliente: int, id_empresa: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Extrae y pondera el vector de preferencias del cliente a partir de su
        historial transaccional en ventas presenciales (POS) y pedidos online en el tenant.
        Aplica decaimiento temporal y frecuencias acumuladas.
        """
        if id_empresa:
            filtro_v = "v.id_cliente = %s AND v.estado NOT IN ('CANCELADA', 'ANULADA') AND v.id_empresa = %s"
            filtro_ped = "ped.id_cliente = %s AND ped.estado_pago = 'PAGADO' AND ped.id_empresa = %s"
            params_compras = (id_cliente, id_empresa, id_cliente, id_empresa)
        else:
            filtro_v = "v.id_cliente = %s AND v.estado NOT IN ('CANCELADA', 'ANULADA')"
            filtro_ped = "ped.id_cliente = %s AND ped.estado_pago = 'PAGADO'"
            params_compras = (id_cliente, id_cliente)

        # 1. Ventas presenciales y pedidos confirmados
        cur.execute(f"""
            SELECT 
                p.id_producto,
                p.id_categoria,
                COALESCE(c.nombre, 'General') as categoria,
                ptc.id_talla,
                COALESCE(t.nombre, 'U') as talla,
                ptc.id_color,
                COALESCE(col.nombre, 'Neutro') as color,
                COALESCE(dv.precio_unitario, p.precio, 0) as precio,
                dv.cantidad,
                v.fecha_venta
            FROM comercio.t_detalle_venta dv
            JOIN comercio.t_venta v ON dv.id_venta = v.id_venta
            JOIN comercio.t_producto_talla_color ptc ON dv.id_variante = ptc.id_variante
            JOIN comercio.t_producto p ON ptc.id_producto = p.id_producto
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            LEFT JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
            LEFT JOIN comercio.t_color col ON ptc.id_color = col.id_color
            WHERE {filtro_v}

            UNION ALL

            SELECT 
                p.id_producto,
                p.id_categoria,
                COALESCE(c.nombre, 'General') as categoria,
                ptc.id_talla,
                COALESCE(t.nombre, 'U') as talla,
                ptc.id_color,
                COALESCE(col.nombre, 'Neutro') as color,
                COALESCE(dp.precio_unitario, p.precio, 0) as precio,
                dp.cantidad,
                ped.fecha_pedido as fecha_venta
            FROM comercio.t_detalle_pedido dp
            JOIN comercio.t_pedido ped ON dp.id_pedido = ped.id_pedido
            JOIN comercio.t_producto_talla_color ptc ON dp.id_variante = ptc.id_variante
            JOIN comercio.t_producto p ON ptc.id_producto = p.id_producto
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            LEFT JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
            LEFT JOIN comercio.t_color col ON ptc.id_color = col.id_color
            WHERE {filtro_ped};
        """, params_compras)

        compras = cur.fetchall()
        if not compras:
            return None

        cat_counts: Dict[int, float] = {}
        cat_names: Dict[int, str] = {}
        talla_counts: Dict[int, float] = {}
        talla_names: Dict[int, str] = {}
        color_counts: Dict[int, float] = {}
        color_names: Dict[int, str] = {}
        precios: List[float] = []
        productos_comprados: set = set()

        total_peso = 0.0
        now = datetime.now()

        for row in compras:
            id_prod, id_cat, nom_cat, id_tal, nom_tal, id_col, nom_col, prec, cant, f_venta = row
            productos_comprados.add(id_prod)
            cant_float = float(cant or 1)

            # Factor de recencia (decaimiento exponencial suave)
            if f_venta:
                f_naive = f_venta.replace(tzinfo=None) if hasattr(f_venta, 'tzinfo') and f_venta.tzinfo else f_venta
                dias_antiguedad = max((now - f_naive).days, 0)
            else:
                dias_antiguedad = 30
            peso_tiempo = math.exp(-dias_antiguedad / 180.0) # Vida media de 6 meses
            peso_item = cant_float * peso_tiempo
            total_peso += peso_item

            # Categoría
            if id_cat:
                cat_counts[id_cat] = cat_counts.get(id_cat, 0.0) + peso_item
                cat_names[id_cat] = nom_cat

            # Talla
            if id_tal:
                talla_counts[id_tal] = talla_counts.get(id_tal, 0.0) + peso_item
                talla_names[id_tal] = nom_tal

            # Color
            if id_col:
                color_counts[id_col] = color_counts.get(id_col, 0.0) + peso_item
                color_names[id_col] = nom_col

            precios.append(float(prec))

        if total_peso <= 0:
            total_peso = 1.0

        # Normalizar probabilidades/pesos
        cat_dist = {k: v / total_peso for k, v in cat_counts.items()}
        talla_dist = {k: v / total_peso for k, v in talla_counts.items()}
        color_dist = {k: v / total_peso for k, v in color_counts.items()}

        top_cats = sorted(cat_dist.items(), key=lambda x: x[1], reverse=True)
        top_tallas = sorted(talla_dist.items(), key=lambda x: x[1], reverse=True)
        top_colores = sorted(color_dist.items(), key=lambda x: x[1], reverse=True)

        avg_price = sum(precios) / len(precios) if precios else 500.0

        return {
            "id_cliente": id_cliente,
            "total_compras": len(compras),
            "top_categoria": (top_cats[0][0], cat_names[top_cats[0][0]]) if top_cats else (None, None),
            "top_talla": (top_tallas[0][0], talla_names[top_tallas[0][0]]) if top_tallas else (None, None),
            "top_color": (top_colores[0][0], color_names[top_colores[0][0]]) if top_colores else (None, None),
            "cat_dist": cat_dist,
            "cat_names": cat_names,
            "talla_dist": talla_dist,
            "talla_names": talla_names,
            "color_dist": color_dist,
            "color_names": color_names,
            "precio_promedio": avg_price,
            "productos_comprados": list(productos_comprados)
        }

    @classmethod
    def actualizar_tabla_preferencias(cls, cur, perfil: Dict[str, Any]):
        """
        Persiste los patrones aprendidos en la tabla oficial comercio.t_preferencia_cliente.
        """
        id_cliente = perfil["id_cliente"]
        # Limpiar preferencias previas del cliente para mantener el perfil consolidado
        cur.execute("DELETE FROM comercio.t_preferencia_cliente WHERE id_cliente = %s", (id_cliente,))

        top_cat_id = perfil["top_categoria"][0]
        top_tal_id = perfil["top_talla"][0]
        top_col_id = perfil["top_color"][0]

        # 1. Preferencia dominante absoluta
        if top_cat_id or top_tal_id or top_col_id:
            cur.execute("""
                INSERT INTO comercio.t_preferencia_cliente (
                    id_cliente, id_categoria, id_talla, id_color, tipo_preferencia
                ) VALUES (%s, %s, %s, %s, %s);
            """, (id_cliente, top_cat_id, top_tal_id, top_col_id, 'COMPRA_FRECUENTE'))

        # 2. Preferencias secundarias cruzadas (hasta 3 patrones representativos)
        cats = sorted(perfil["cat_dist"].items(), key=lambda x: x[1], reverse=True)[:2]
        cols = sorted(perfil["color_dist"].items(), key=lambda x: x[1], reverse=True)[:2]

        for cat_id, cat_weight in cats:
            for col_id, col_weight in cols:
                if (cat_id == top_cat_id and col_id == top_col_id):
                    continue  # Ya insertada
                cur.execute("""
                    INSERT INTO comercio.t_preferencia_cliente (
                        id_cliente, id_categoria, id_talla, id_color, tipo_preferencia
                    ) VALUES (%s, %s, %s, %s, %s);
                """, (id_cliente, cat_id, top_tal_id, col_id, 'AFINIDAD_ESTILO'))

    @classmethod
    def generar_recomendaciones(cls, cur, perfil: Dict[str, Any], id_empresa: int = 1, top_k: int = 8) -> List[Dict[str, Any]]:
        """
        Ejecuta el modelo de afinidad (Content-Based Feature Weighting)
        contra todos los productos activos y genera la lista ordenada de recomendaciones.
        """
        id_cliente = perfil["id_cliente"]
        cat_dist = perfil["cat_dist"]
        talla_dist = perfil["talla_dist"]
        color_dist = perfil["color_dist"]
        precio_prom = perfil["precio_promedio"]
        comprados = set(perfil["productos_comprados"])

        # Consultar catálogo activo con sus variantes
        cur.execute("""
            SELECT 
                p.id_producto,
                p.nombre,
                p.id_categoria,
                COALESCE(c.nombre, 'Moda') as categoria_nombre,
                COALESCE(p.precio, 0) as precio,
                p.imagen_url,
                p.descripcion
            FROM comercio.t_producto p
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            WHERE p.id_empresa = %s AND p.activo = true
        """, (id_empresa,))
        candidatos = cur.fetchall()

        recomendaciones_candidatas = []

        # Pre-cargar todas las variantes de productos en una sola consulta para máximo rendimiento
        cur.execute("""
            SELECT ptc.id_producto, ptc.id_talla, ptc.id_color
            FROM comercio.t_producto_talla_color ptc
        """)
        vars_map: Dict[int, Tuple[set, set]] = {}
        for row_v in cur.fetchall():
            pid, tid, cid = row_v
            if pid not in vars_map:
                vars_map[pid] = (set(), set())
            if tid:
                vars_map[pid][0].add(tid)
            if cid:
                vars_map[pid][1].add(cid)

        for prod in candidatos:
            id_p, nombre, id_cat, nom_cat, precio, img_url, desc = prod
            precio_flt = float(precio)

            tallas_prod, colores_prod = vars_map.get(id_p, (set(), set()))

            # 1. Afinidad por Categoría
            score_cat = cat_dist.get(id_cat, 0.0)

            # 2. Afinidad por Talla (máxima coincidencia disponible en el producto)
            score_talla = max([talla_dist.get(t, 0.0) for t in tallas_prod], default=0.0)

            # 3. Afinidad por Color (máxima coincidencia en la paleta)
            score_color = max([color_dist.get(c, 0.0) for c in colores_prod], default=0.0)

            # 4. Afinidad por Precio (función gaussiana normalizada)
            dif_precio_rel = abs(precio_flt - precio_prom) / max(precio_prom, 100.0)
            score_precio = math.exp(-dif_precio_rel * 1.5)

            # Puntuación Final Combinada
            score_raw = (
                cls.WEIGHT_CATEGORY * score_cat +
                cls.WEIGHT_SIZE * score_talla +
                cls.WEIGHT_COLOR * score_color +
                cls.WEIGHT_PRICE * score_precio
            )

            # Bonus de diversidad para prendas no compradas aún
            if id_p not in comprados:
                score_raw *= 1.15
            else:
                score_raw *= 0.85  # Menor prioridad si ya la compró

            # Escalar a un score legible [0.55 - 0.98]
            score_final = min(max(0.50 + (score_raw * 0.48), 0.55), 0.98)

            # Construcción de explicabilidad (motivo generado por IA/ML)
            motivo_partes = []
            if score_cat > 0.2:
                motivo_partes.append(f"alta afinidad con tu preferencia en {nom_cat}")
            if score_talla > 0.2 and perfil["top_talla"][1]:
                motivo_partes.append(f"disponible en tu talla habitual ({perfil['top_talla'][1]})")
            if score_color > 0.2 and perfil["top_color"][1]:
                motivo_partes.append(f"tono armónico con tu paleta ({perfil['top_color'][1]})")

            if motivo_partes:
                motivo_humano = "Recomendado por " + ", ".join(motivo_partes) + "."
            else:
                motivo_humano = f"Prenda destacada de la colección seleccionada para tu estilo en {nom_cat}."

            recomendaciones_candidatas.append({
                "id_producto": id_p,
                "nombre": nombre,
                "categoria": nom_cat,
                "precio": precio_flt,
                "imagen_url": img_url or "assets/images/default-fashion.jpg",
                "descripcion": desc or "",
                "puntuacion": round(score_final, 3),
                "motivo": motivo_humano
            })

        # Ordenar por mayor puntuación
        recomendaciones_candidatas.sort(key=lambda x: x["puntuacion"], reverse=True)
        top_recomendaciones = recomendaciones_candidatas[:top_k]

        # Guardar en comercio.t_recomendacion
        cur.execute("DELETE FROM comercio.t_recomendacion WHERE id_cliente = %s", (id_cliente,))
        for rec in top_recomendaciones:
            cur.execute("""
                INSERT INTO comercio.t_recomendacion (
                    id_cliente, id_producto, puntuacion, motivo, fecha_recomendacion
                ) VALUES (%s, %s, %s, %s, %s);
            """, (id_cliente, rec["id_producto"], Decimal(str(rec["puntuacion"])), rec["motivo"], datetime.now()))

        return top_recomendaciones


# =====================================================================
# FUNCIONES DE SERVICIO / INTERFAZ PÚBLICA DEL MOTOR DE PREFERENCIAS
# =====================================================================

def aprender_preferencias_cliente(id_cliente: int, id_empresa: int = 1) -> Dict[str, Any]:
    """
    Ejecuta el aprendizaje automático de preferencias para un cliente específico.
    Lee su historial de compras en el tenant, actualiza t_preferencia_cliente y recalcula t_recomendacion.
    """
    conn = _get_db_connection()
    try:
        cur = conn.cursor()
        perfil = MiniMLPreferenceEngine.extraer_vector_cliente(cur, id_cliente, id_empresa=id_empresa)
        if not perfil:
            conn.close()
            return {
                "success": False,
                "id_cliente": id_cliente,
                "mensaje": "El cliente no cuenta con compras registradas en esta tienda para inferir preferencias."
            }

        # 1. Actualizar preferencias aprendidas
        MiniMLPreferenceEngine.actualizar_tabla_preferencias(cur, perfil)

        # 2. Generar recomendaciones
        recs = MiniMLPreferenceEngine.generar_recomendaciones(cur, perfil, id_empresa=id_empresa)
        conn.commit()

        return {
            "success": True,
            "id_cliente": id_cliente,
            "preferencias_aprendidas": {
                "top_categoria": perfil["top_categoria"][1],
                "top_talla": perfil["top_talla"][1],
                "top_color": perfil["top_color"][1],
                "precio_promedio_bs": round(perfil["precio_promedio"], 2),
                "total_compras_analizadas": perfil["total_compras"]
            },
            "recomendaciones_generadas": recs
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"Error aprendiendo preferencias para cliente {id_cliente}: {e}")
        raise
    finally:
        conn.close()


def entrenar_modelo_todos_los_clientes(id_empresa: int = 1) -> Dict[str, Any]:
    """
    Entrena el modelo de Machine Learning en lote para los clientes del tenant
    que han realizado compras en tiendas físicas u online.
    """
    conn = _get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT id_cliente 
            FROM comercio.t_venta 
            WHERE id_cliente IS NOT NULL AND id_empresa = %s
            UNION
            SELECT DISTINCT id_cliente
            FROM comercio.t_pedido
            WHERE id_cliente IS NOT NULL AND id_empresa = %s;
        """, (id_empresa, id_empresa))
        clientes = [r[0] for r in cur.fetchall()]

        procesados = 0
        total_recs = 0

        for id_cli in clientes:
            try:
                perfil = MiniMLPreferenceEngine.extraer_vector_cliente(cur, id_cli, id_empresa=id_empresa)
                if perfil:
                    MiniMLPreferenceEngine.actualizar_tabla_preferencias(cur, perfil)
                    recs = MiniMLPreferenceEngine.generar_recomendaciones(cur, perfil, id_empresa=id_empresa)
                    procesados += 1
                    total_recs += len(recs)
            except Exception as ex_cli:
                logger.warning(f"Error procesando cliente {id_cli}: {ex_cli}")

        conn.commit()
        return {
            "success": True,
            "clientes_entrenados": procesados,
            "recomendaciones_totales_almacenadas": total_recs,
            "mensaje": f"Entrenamiento completado: {procesados} perfiles de cliente actualizados."
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"Error en entrenamiento global de preferencias: {e}")
        raise
    finally:
        conn.close()


def obtener_recomendaciones_cliente(
    id_usuario: Optional[int],
    id_empresa: int = 1,
    limite: int = 6,
    preferencias_sesion: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Recupera las prendas recomendadas para el usuario actual combinando:
    1. Historial de compras y afinidad vectorial (si el cliente tiene historial).
    2. Señales de carrito activo y reservas recientes del cliente.
    3. Preferencias expresadas durante la conversación actual (categoría, talla, colores, presupuesto).
    4. Disponibilidad real de stock y popularidad verificable en la tienda (para inicio en frío honesto,
       sin inventar porcentajes fijos de afinidad como si fueran predicciones reales).
    """
    conn = _get_db_connection()
    try:
        cur = conn.cursor()
        id_cliente = None
        if id_usuario:
            cur.execute("SELECT id_cliente FROM comercio.t_cliente WHERE id_usuario = %s LIMIT 1", (id_usuario,))
            row_cli = cur.fetchone()
            if row_cli:
                id_cliente = row_cli[0]

        prefs = preferencias_sesion or {}
        cat_pref = (prefs.get("categoria") or "").strip()
        talla_pref = (prefs.get("talla") or "").strip()
        colores_pref = [c.lower() for c in (prefs.get("colores") or []) if c]
        colores_excl = [c.lower() for c in (prefs.get("colores_excluidos") or []) if c]
        precio_max = prefs.get("precio_max") or prefs.get("presupuesto_max")

        # Si el usuario expresó restricciones en la sesión actual, priorizar el ranking contextual híbrido
        tiene_contexto_conversacional = bool(cat_pref or talla_pref or colores_pref or colores_excl or precio_max)

        # 1. Si hay cliente identificado y no pidió algo radicalmente distinto en la sesión, revisar perfil histórico
        if id_cliente and not tiene_contexto_conversacional:
            cur.execute("""
                SELECT 
                    r.id_producto,
                    p.nombre,
                    COALESCE(c.nombre, 'Alta Costura') as categoria,
                    COALESCE(p.precio, 0) as precio,
                    p.imagen_url,
                    r.puntuacion,
                    r.motivo,
                    p.descripcion
                FROM comercio.t_recomendacion r
                JOIN comercio.t_producto p ON r.id_producto = p.id_producto
                LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
                WHERE r.id_cliente = %s AND p.id_empresa = %s AND p.activo = true
                ORDER BY r.puntuacion DESC
                LIMIT %s;
            """, (id_cliente, id_empresa, limite))
            rows = cur.fetchall()

            if rows:
                return _formatear_recomendaciones(cur, rows, es_inicio_frio=False)

            perfil = MiniMLPreferenceEngine.extraer_vector_cliente(cur, id_cliente, id_empresa=id_empresa)
            if perfil:
                MiniMLPreferenceEngine.actualizar_tabla_preferencias(cur, perfil)
                MiniMLPreferenceEngine.generar_recomendaciones(cur, perfil, id_empresa=id_empresa, top_k=limite)
                conn.commit()
                cur.execute("""
                    SELECT 
                        r.id_producto,
                        p.nombre,
                        COALESCE(c.nombre, 'Alta Costura') as categoria,
                        COALESCE(p.precio, 0) as precio,
                        p.imagen_url,
                        r.puntuacion,
                        r.motivo,
                        p.descripcion
                    FROM comercio.t_recomendacion r
                    JOIN comercio.t_producto p ON r.id_producto = p.id_producto
                    LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
                    WHERE r.id_cliente = %s AND p.id_empresa = %s AND p.activo = true
                    ORDER BY r.puntuacion DESC
                    LIMIT %s;
                """, (id_cliente, id_empresa, limite))
                return _formatear_recomendaciones(cur, cur.fetchall(), es_inicio_frio=False)

        # 2. Ranking multicriterio verificable (combina popularidad real, disponibilidad, reservas/carrito y preferencias de sesión)
        # Obtener popularidad real de ventas en la empresa
        cur.execute("""
            SELECT ptc.id_producto, COALESCE(SUM(dv.cantidad), 0) as vendidos
            FROM comercio.t_detalle_venta dv
            JOIN comercio.t_venta v ON dv.id_venta = v.id_venta
            JOIN comercio.t_producto_talla_color ptc ON dv.id_variante = ptc.id_variante
            WHERE v.id_empresa = %s AND UPPER(COALESCE(v.estado, '')) NOT IN ('CANCELADA', 'ANULADA')
            GROUP BY ptc.id_producto;
        """, (id_empresa,))
        pop_map = {r[0]: int(r[1] or 0) for r in cur.fetchall()}
        max_pop = max(pop_map.values(), default=1) or 1

        # Señales de carrito y reservas del cliente (si está autenticado)
        cats_interes_reciente = set()
        if id_cliente:
            cur.execute("""
                SELECT DISTINCT p.id_categoria
                FROM comercio.t_reserva r
                JOIN comercio.t_detalle_reserva dr ON r.id_reserva = dr.id_reserva
                JOIN comercio.t_producto_talla_color ptc ON dr.id_variante = ptc.id_variante
                JOIN comercio.t_producto p ON ptc.id_producto = p.id_producto
                WHERE r.id_cliente = %s AND p.id_empresa = %s
            """, (id_cliente, id_empresa))
            for rc in cur.fetchall():
                if rc[0]:
                    cats_interes_reciente.add(rc[0])

        cur.execute("""
            SELECT 
                p.id_producto,
                p.nombre,
                COALESCE(c.nombre, 'Colección') as categoria,
                COALESCE(p.precio, 0) as precio,
                p.imagen_url,
                p.descripcion,
                p.id_categoria,
                COALESCE(SUM(inv.stock_disponible), 0) as stock_total
            FROM comercio.t_producto p
            LEFT JOIN comercio.t_categoria c ON p.id_categoria = c.id_categoria
            LEFT JOIN comercio.t_producto_talla_color ptc ON p.id_producto = ptc.id_producto
            LEFT JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
            WHERE p.id_empresa = %s AND p.activo = true
            GROUP BY p.id_producto, p.nombre, c.nombre, p.precio, p.imagen_url, p.descripcion, p.id_categoria
            ORDER BY stock_total DESC, p.id_producto DESC
            LIMIT 40;
        """, (id_empresa,))
        candidatos = cur.fetchall()

        scored_rows = []
        for cand in candidatos:
            id_p, nom, cat_nom, precio_raw, img, desc, id_cat, stock_tot = cand
            precio_f = float(precio_raw or 0)
            stock_int = int(stock_tot or 0)

            # Respetar filtro duro de presupuesto máximo si fue indicado
            if precio_max and precio_f > float(precio_max):
                continue

            cur.execute("""
                SELECT DISTINCT t.nombre, col.nombre
                FROM comercio.t_producto_talla_color ptc
                LEFT JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
                LEFT JOIN comercio.t_color col ON ptc.id_color = col.id_color
                WHERE ptc.id_producto = %s
            """, (id_p,))
            vars_data = cur.fetchall()
            tallas_p = [str(v[0]) for v in vars_data if v[0]]
            colores_p = [str(v[1]) for v in vars_data if v[1]]
            colores_p_lower = [c.lower() for c in colores_p]

            # Si todos los colores del producto están excluidos, omitir
            if colores_excl and colores_p_lower and all(any(ex in cl for ex in colores_excl) for cl in colores_p_lower):
                continue

            # Calcular score de ranking verificable
            score_rank = 0.40
            razones = []

            if stock_int > 0:
                score_rank += 0.15
            else:
                score_rank -= 0.25

            unidades_vend = pop_map.get(id_p, 0)
            if unidades_vend > 0:
                score_rank += 0.15 * min(1.0, unidades_vend / max_pop)
                razones.append(f"alta demanda en tienda ({unidades_vend} uds. vendidas)")

            if cat_pref and cat_pref.lower() in cat_nom.lower():
                score_rank += 0.20
                razones.append(f"coincide con tu búsqueda en {cat_nom}")
            elif id_cat in cats_interes_reciente:
                score_rank += 0.15
                razones.append(f"relacionado con tus reservas recientes en {cat_nom}")

            if talla_pref and any(t.upper() == talla_pref.upper() for t in tallas_p):
                score_rank += 0.15
                razones.append(f"disponible en talla {talla_pref.upper()}")

            if colores_pref and any(any(cp in cl for cp in colores_pref) for cl in colores_p_lower):
                score_rank += 0.15
                razones.append("tono acorde a tu preferencia cromática")

            if precio_max:
                razones.append(f"dentro de tu presupuesto (Bs. {precio_f:.2f})")

            if not razones:
                razones.append(f"destacado de la colección {cat_nom} con disponibilidad en tienda")

            motivo_final = "Seleccionado por " + ", ".join(razones[:3]) + "."
            scored_rows.append((
                id_p, nom, cat_nom, precio_f, img,
                round(min(0.96, max(0.50, score_rank)), 3),
                motivo_final, desc, tallas_p, colores_p, stock_int
            ))

        scored_rows.sort(key=lambda x: x[5], reverse=True)
        resultado = []
        for sr in scored_rows[:limite]:
            id_p, nom, cat, precio_f, img, punt, motivo, desc, tallas, colores, stock_int = sr
            resultado.append({
                "id_producto": id_p,
                "nombre": nom,
                "categoria": cat,
                "precio": float(precio_f),
                "imagen_url": img or "assets/images/default-fashion.jpg",
                "puntuacion": float(punt),
                "puntuacion_ranking": float(punt),
                "afinidad_porcentaje": None if not id_cliente else int(float(punt) * 100),
                "es_inicio_frio": not bool(id_cliente),
                "motivo": motivo,
                "descripcion": desc or "",
                "tallas": sorted(list(set(tallas))),
                "colores": sorted(list(set(colores))),
                "stock_disponible": stock_int
            })
        return resultado
    finally:
        conn.close()


def _formatear_recomendaciones(cur, rows, es_inicio_frio: bool = False) -> List[Dict[str, Any]]:
    resultado = []
    for r in rows:
        id_p, nom, cat, precio, img, punt, motivo, desc = r
        cur.execute("""
            SELECT DISTINCT t.nombre, col.nombre
            FROM comercio.t_producto_talla_color ptc
            LEFT JOIN comercio.t_talla t ON ptc.id_talla = t.id_talla
            LEFT JOIN comercio.t_color col ON ptc.id_color = col.id_color
            WHERE ptc.id_producto = %s
        """, (id_p,))
        vars_data = cur.fetchall()
        tallas = sorted(list({v[0] for v in vars_data if v[0]}))
        colores = sorted(list({v[1] for v in vars_data if v[1]}))

        cur.execute("""
            SELECT COALESCE(SUM(inv.stock_disponible), 0)
            FROM comercio.t_producto_talla_color ptc
            JOIN comercio.t_inventario inv ON ptc.id_variante = inv.id_variante
            WHERE ptc.id_producto = %s
        """, (id_p,))
        row_stk = cur.fetchone()
        stock_disp = int(row_stk[0] or 0) if row_stk else 0

        resultado.append({
            "id_producto": id_p,
            "nombre": nom,
            "categoria": cat,
            "precio": float(precio),
            "imagen_url": img or "assets/images/default-fashion.jpg",
            "puntuacion": float(punt),
            "puntuacion_ranking": float(punt),
            "afinidad_porcentaje": None if es_inicio_frio else int(float(punt) * 100),
            "es_inicio_frio": es_inicio_frio,
            "motivo": motivo,
            "descripcion": desc or "",
            "tallas": tallas,
            "colores": colores,
            "stock_disponible": stock_disp
        })
    return resultado
