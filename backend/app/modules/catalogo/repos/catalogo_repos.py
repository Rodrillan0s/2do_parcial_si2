from typing import Optional, List, Dict, Any
from app.core.postgres import PostgreSQL
from app.core.config import Config

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

# ==============================================================================
# TENANTS PÚBLICOS
# ==============================================================================

def _normalizar_publico(valor: Optional[str]) -> str:
    if not valor:
        return "Unisex"
    v = valor.strip().lower()
    if v in ("mujer", "damas", "dama", "femenino", "women"):
        return "Mujer"
    if v in ("hombre", "caballeros", "caballero", "masculino", "men"):
        return "Hombre"
    if v in ("unisex", "ambos", "mixto"):
        return "Unisex"
    if v in ("niños", "ninos", "niño", "nino", "infantil", "boys"):
        return "Niños"
    if v in ("niñas", "ninas", "niña", "nina", "girls"):
        return "Niñas"
    if v in ("bebés", "bebes", "bebé", "bebe", "baby"):
        return "Bebés"
    return valor.strip().title()


def _normalizar_config_storefront(raw_cfg: Any, nombre_empresa: str = "") -> Dict[str, Any]:
    cfg = dict(raw_cfg) if isinstance(raw_cfg, dict) else {}
    default_secciones = [
        {"codigo": "banner", "visible": True, "orden": 1},
        {"codigo": "publicos", "visible": True, "orden": 2},
        {"codigo": "categorias", "visible": True, "orden": 3},
        {"codigo": "colecciones", "visible": True, "orden": 4},
        {"codigo": "destacados", "visible": True, "orden": 5},
        {"codigo": "novedades", "visible": True, "orden": 6},
        {"codigo": "recomendaciones", "visible": True, "orden": 7},
    ]
    return {
        "nombre_comercial": cfg.get("nombre_comercial") or nombre_empresa or "Tienda Oficial",
        "eslogan": cfg.get("eslogan") or "Moda y estilo para cada ocasión",
        "color_primario": cfg.get("color_primario") or "#18181b",
        "color_secundario": cfg.get("color_secundario") or "#c2410c",
        "tipografia": cfg.get("tipografia") if cfg.get("tipografia") in ("editorial", "moderna", "clasica", "minimal") else "editorial",
        "estilo_tarjetas": cfg.get("estilo_tarjetas") if cfg.get("estilo_tarjetas") in ("editorial", "minimal", "borde_suave") else "editorial",
        "banner_titulo": cfg.get("banner_titulo") or f"Colección Oficial {nombre_empresa or ''}".strip(),
        "banner_subtitulo": cfg.get("banner_subtitulo") or "Explora nuestro catálogo actualizado con disponibilidad real por sucursal.",
        "banner_imagen_url": cfg.get("banner_imagen_url") or "",
        "banner_cta_texto": cfg.get("banner_cta_texto") or "Explorar catálogo",
        "publicos_habilitados": cfg.get("publicos_habilitados") if isinstance(cfg.get("publicos_habilitados"), list) else [],
        "colecciones_destacadas": cfg.get("colecciones_destacadas") if isinstance(cfg.get("colecciones_destacadas"), list) else [],
        "secciones": cfg.get("secciones") if isinstance(cfg.get("secciones"), list) and len(cfg.get("secciones")) > 0 else default_secciones,
        "onboarding_completado": bool(cfg.get("onboarding_completado", False)),
    }


def obtener_tenants_publicos() -> List[Dict[str, Any]]:
    """
    Retorna la lista de tiendas / empresas activas disponibles para consulta pública.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        query = f"""
            SELECT 
                id_empresa, 
                nombre_empresa, 
                razon_social, 
                logo, 
                ciudad, 
                correo, 
                telefono, 
                direccion_fiscal,
                COALESCE(slug, LOWER(REGEXP_REPLACE(TRIM(nombre_empresa), '[^a-zA-Z0-9]+', '-', 'g'))) AS slug,
                COALESCE(configuracion_storefront, '{{}}'::jsonb) AS configuracion_storefront
            FROM {schema}.empresa
            WHERE estado = 'ACTIVO'
            ORDER BY id_empresa ASC;
        """
        filas = db.execute_query(query, fetchall=True) or []
        resultado = []
        for r in filas:
            resultado.append({
                "id_empresa": r[0],
                "nombre_empresa": r[1],
                "razon_social": r[2],
                "logo": r[3],
                "ciudad": r[4],
                "correo": r[5],
                "telefono": r[6],
                "direccion_fiscal": r[7],
                "slug": r[8],
                "configuracion_storefront": _normalizar_config_storefront(r[9], r[1])
            })
        return resultado
    finally:
        db.close_connection()

def obtener_info_tenant(id_empresa: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene los datos públicos de un Tenant específico.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        query = f"""
            SELECT 
                id_empresa, 
                nombre_empresa, 
                razon_social, 
                logo, 
                ciudad, 
                correo, 
                telefono, 
                direccion_fiscal,
                COALESCE(slug, LOWER(REGEXP_REPLACE(TRIM(nombre_empresa), '[^a-zA-Z0-9]+', '-', 'g'))) AS slug,
                COALESCE(configuracion_storefront, '{{}}'::jsonb) AS configuracion_storefront
            FROM {schema}.empresa
            WHERE id_empresa = %s AND estado = 'ACTIVO'
            LIMIT 1;
        """
        r = db.execute_query(query, (id_empresa,), fetchone=True)
        if not r:
            return None
        return {
            "id_empresa": r[0],
            "nombre_empresa": r[1],
            "razon_social": r[2],
            "logo": r[3],
            "ciudad": r[4],
            "correo": r[5],
            "telefono": r[6],
            "direccion_fiscal": r[7],
            "slug": r[8],
            "configuracion_storefront": _normalizar_config_storefront(r[9], r[1])
        }
    finally:
        db.close_connection()


def obtener_info_tenant_por_slug(slug: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene los datos públicos de un Tenant activo por su slug único.
    """
    if not slug or not slug.strip():
        return None
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        slug_norm = slug.strip().lower()
        query = f"""
            SELECT 
                id_empresa, 
                nombre_empresa, 
                razon_social, 
                logo, 
                ciudad, 
                correo, 
                telefono, 
                direccion_fiscal,
                COALESCE(slug, LOWER(REGEXP_REPLACE(TRIM(nombre_empresa), '[^a-zA-Z0-9]+', '-', 'g'))) AS slug,
                COALESCE(configuracion_storefront, '{{}}'::jsonb) AS configuracion_storefront
            FROM {schema}.empresa
            WHERE LOWER(COALESCE(slug, LOWER(REGEXP_REPLACE(TRIM(nombre_empresa), '[^a-zA-Z0-9]+', '-', 'g')))) = %s
              AND estado = 'ACTIVO'
            LIMIT 1;
        """
        r = db.execute_query(query, (slug_norm,), fetchone=True)
        if not r:
            return None
        return {
            "id_empresa": r[0],
            "nombre_empresa": r[1],
            "razon_social": r[2],
            "logo": r[3],
            "ciudad": r[4],
            "correo": r[5],
            "telefono": r[6],
            "direccion_fiscal": r[7],
            "slug": r[8],
            "configuracion_storefront": _normalizar_config_storefront(r[9], r[1])
        }
    finally:
        db.close_connection()

# ==============================================================================
# FILTROS DINÁMICOS DISPONIBLES
# ==============================================================================

def obtener_filtros_disponibles(id_empresa: int) -> Dict[str, Any]:
    """
    Retorna dinámicamente las categorías, tallas, colores, temporadas y colecciones
    disponibles para productos visibles del Tenant actual.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # Condición de visibilidad para clientes:
        # - Temporada actual
        # - PERMANENTE
        # - Fuera de temporada con promoción vigente
        condicion_visibilidad = f"""
            (
                UPPER(
                    TRIM(
                        COALESCE(
                            NULLIF(p.temporada, ''),
                            'PERMANENTE'
                        )
                    )
                ) =
                CASE
                    WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (12, 1, 2)
                        THEN 'VERANO'
                    WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (3, 4, 5)
                        THEN 'OTOÑO'
                    WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (6, 7, 8)
                        THEN 'INVIERNO'
                    WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (9, 10, 11)
                        THEN 'PRIMAVERA'
                END

                OR UPPER(
                    TRIM(
                        COALESCE(
                            NULLIF(p.temporada, ''),
                            'PERMANENTE'
                        )
                    )
                ) = 'PERMANENTE'

                OR EXISTS (
                    SELECT 1
                    FROM {schema}.t_promocion_producto pp_temp
                    INNER JOIN {schema}.t_promocion pr_temp
                        ON pr_temp.id_promocion = pp_temp.id_promocion
                    WHERE pp_temp.id_producto = p.id_producto
                      AND pr_temp.estado = TRUE
                      AND CURRENT_DATE >= pr_temp.fecha_inicio
                      AND CURRENT_DATE <= pr_temp.fecha_fin
                )
            )
        """

        # 1. Categorías con productos visibles
        q_cats = f"""
            SELECT DISTINCT 
                c.id_categoria, 
                c.nombre, 
                c.imagen_url,
                COUNT(p.id_producto) AS total_prendas
            FROM {schema}.t_categoria c
            JOIN {schema}.t_producto p 
                ON p.id_categoria = c.id_categoria
            WHERE p.id_empresa = %s
              AND p.activo = TRUE
              AND c.activo = TRUE
              AND {condicion_visibilidad}
            GROUP BY c.id_categoria, c.nombre, c.imagen_url
            ORDER BY c.nombre ASC;
        """

        cats_res = db.execute_query(
            q_cats,
            (id_empresa,),
            fetchall=True
        ) or []

        categorias = [
            {
                "id_categoria": r[0],
                "nombre": r[1],
                "imagen_url": r[2],
                "total_prendas": r[3]
            }
            for r in cats_res
        ]

        # 2. Tallas activas con variantes disponibles de productos visibles
        q_tallas = f"""
            SELECT DISTINCT 
                t.id_talla, 
                t.nombre
            FROM {schema}.t_talla t
            JOIN {schema}.t_producto_talla_color v 
                ON v.id_talla = t.id_talla
            JOIN {schema}.t_producto p 
                ON p.id_producto = v.id_producto
            WHERE p.id_empresa = %s
              AND p.activo = TRUE
              AND v.activo = TRUE
              AND t.activo = TRUE
              AND {condicion_visibilidad}
            ORDER BY t.id_talla ASC;
        """

        tallas_res = db.execute_query(
            q_tallas,
            (id_empresa,),
            fetchall=True
        ) or []

        tallas = [
            {
                "id_talla": r[0],
                "nombre": r[1]
            }
            for r in tallas_res
        ]

        # 3. Colores activos con variantes disponibles de productos visibles
        q_colores = f"""
            SELECT DISTINCT 
                col.id_color, 
                col.nombre, 
                col.codigo_hex
            FROM {schema}.t_color col
            JOIN {schema}.t_producto_talla_color v 
                ON v.id_color = col.id_color
            JOIN {schema}.t_producto p 
                ON p.id_producto = v.id_producto
            WHERE p.id_empresa = %s
              AND p.activo = TRUE
              AND v.activo = TRUE
              AND col.activo = TRUE
              AND {condicion_visibilidad}
            ORDER BY col.nombre ASC;
        """

        colores_res = db.execute_query(
            q_colores,
            (id_empresa,),
            fetchall=True
        ) or []

        colores = [
            {
                "id_color": r[0],
                "nombre": r[1],
                "codigo_hex": r[2]
            }
            for r in colores_res
        ]

        # 4. Temporadas de productos visibles
        q_temps = f"""
            SELECT DISTINCT 
                TRIM(p.temporada)
            FROM {schema}.t_producto p
            WHERE p.id_empresa = %s
              AND p.activo = TRUE
              AND p.temporada IS NOT NULL
              AND TRIM(p.temporada) <> ''
              AND {condicion_visibilidad}
            ORDER BY 1 ASC;
        """

        temps_res = db.execute_query(
            q_temps,
            (id_empresa,),
            fetchall=True
        ) or []

        temporadas = [
            r[0]
            for r in temps_res
            if r[0]
        ]

        # 5. Colecciones de productos visibles
        q_cols = f"""
            SELECT DISTINCT 
                TRIM(p.coleccion)
            FROM {schema}.t_producto p
            WHERE p.id_empresa = %s
              AND p.activo = TRUE
              AND p.coleccion IS NOT NULL
              AND TRIM(p.coleccion) <> ''
              AND {condicion_visibilidad}
            ORDER BY 1 ASC;
        """

        cols_res = db.execute_query(
            q_cols,
            (id_empresa,),
            fetchall=True
        ) or []

        colecciones = [
            r[0]
            for r in cols_res
            if r[0]
        ]

        # 6. Rango de precios de productos visibles
        q_prices = f"""
            SELECT 
                COALESCE(MIN(p.precio), 0) AS min_precio,
                COALESCE(MAX(p.precio), 0) AS max_precio
            FROM {schema}.t_producto p
            WHERE p.id_empresa = %s
              AND p.activo = TRUE
              AND {condicion_visibilidad};
        """

        p_res = db.execute_query(
            q_prices,
            (id_empresa,),
            fetchone=True
        )

        precio_min_posible = (
            float(p_res[0])
            if p_res and p_res[0] is not None
            else 0.0
        )

        precio_max_posible = (
            float(p_res[1])
            if p_res and p_res[1] is not None
            else 0.0
        )

        # 7. Públicos objetivo (genero) con productos visibles en la tienda
        q_publicos = f"""
            SELECT 
                COALESCE(NULLIF(TRIM(p.genero), ''), 'Unisex') AS genero_raw,
                COUNT(p.id_producto) AS total_prendas
            FROM {schema}.t_producto p
            WHERE p.id_empresa = %s
              AND p.activo = TRUE
              AND {condicion_visibilidad}
            GROUP BY 1
            ORDER BY total_prendas DESC;
        """
        pub_res = db.execute_query(q_publicos, (id_empresa,), fetchall=True) or []
        publicos_map: Dict[str, int] = {}
        for r in pub_res:
            norm = _normalizar_publico(r[0])
            publicos_map[norm] = publicos_map.get(norm, 0) + int(r[1] or 0)
        publicos = [
            {"nombre": k, "total_prendas": v}
            for k, v in publicos_map.items()
            if v > 0
        ]

        # 8. Sucursales activas de la empresa
        q_sucs = f"""
            SELECT 
                s.id_sucursal,
                s.nombre,
                COALESCE(s.direccion, '') AS direccion,
                COALESCE(c.nombre, '') AS ciudad,
                COALESCE(s.telefono, '') AS telefono,
                COALESCE(TO_CHAR(s.horario_apertura, 'HH24:MI'), '') AS apertura,
                COALESCE(TO_CHAR(s.horario_cierre, 'HH24:MI'), '') AS cierre
            FROM {schema}.t_sucursal s
            LEFT JOIN {schema}.t_ciudad c ON c.id_ciudad = s.id_ciudad
            WHERE s.id_empresa = %s AND COALESCE(s.activo, s.estado, FALSE) = TRUE
            ORDER BY s.id_sucursal ASC;
        """
        sucs_res = db.execute_query(q_sucs, (id_empresa,), fetchall=True) or []
        sucursales = [
            {
                "id_sucursal": r[0],
                "nombre": r[1],
                "direccion": r[2],
                "ciudad": r[3],
                "telefono": r[4],
                "horario": f"{r[5]} - {r[6]}".strip(" -") if (r[5] or r[6]) else ""
            }
            for r in sucs_res
        ]

        return {
            "categorias": categorias,
            "publicos": publicos,
            "sucursales": sucursales,
            "tallas": tallas,
            "colores": colores,
            "temporadas": temporadas,
            "colecciones": colecciones,
            "precio_min": precio_min_posible,
            "precio_max": precio_max_posible
        }

    finally:
        db.close_connection()
# ==============================================================================
# CONSULTA PÚBLICA DE PRODUCTOS (CATÁLOGO)
# ==============================================================================
def listar_catalogo_publico(
    id_empresa: int,
    busqueda: Optional[str] = None,
    id_categoria: Optional[int] = None,
    publico: Optional[str] = None,
    id_sucursal: Optional[int] = None,
    id_talla: Optional[int] = None,
    id_color: Optional[int] = None,
    temporada: Optional[str] = None,
    coleccion: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    orden: Optional[str] = "destacados",
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Consulta productos activos del Tenant con filtros combinados y ordenamiento.
    Retorna total y lista formateada con variantes resumidas, fotos y promoción vigente.

    La visibilidad pública depende de la temporada actual:
    - Productos de la temporada actual: visibles.
    - Productos PERMANENTE: visibles.
    - Productos fuera de temporada con promoción vigente: visibles.
    - Productos fuera de temporada sin promoción vigente: no visibles.
    """
    db = PostgreSQL()
    db.create_connection()

    try:
        schema = _get_schema()

        condiciones = [
            "p.id_empresa = %s",
            "p.activo = TRUE",

            # Visibilidad según temporada actual o promoción vigente
            f"""
            (
                UPPER(TRIM(COALESCE(NULLIF(p.temporada, ''), 'PERMANENTE'))) =
                CASE
                    WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (12, 1, 2)
                        THEN 'VERANO'
                    WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (3, 4, 5)
                        THEN 'OTOÑO'
                    WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (6, 7, 8)
                        THEN 'INVIERNO'
                    WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (9, 10, 11)
                        THEN 'PRIMAVERA'
                END

                OR

                UPPER(TRIM(COALESCE(NULLIF(p.temporada, ''), 'PERMANENTE'))) = 'PERMANENTE'

                OR

                EXISTS (
                    SELECT 1
                    FROM {schema}.t_promocion_producto pp_temp
                    INNER JOIN {schema}.t_promocion pr_temp
                        ON pr_temp.id_promocion = pp_temp.id_promocion
                    WHERE pp_temp.id_producto = p.id_producto
                      AND pr_temp.estado = TRUE
                      AND CURRENT_DATE >= pr_temp.fecha_inicio
                      AND CURRENT_DATE <= pr_temp.fecha_fin
                )
            )
            """,

            # El catálogo público solo muestra productos con disponibilidad real.
            f"""
            EXISTS (
                SELECT 1
                FROM {schema}.t_inventario inv_visible
                INNER JOIN {schema}.t_producto_talla_color var_visible
                    ON var_visible.id_variante = inv_visible.id_variante
                INNER JOIN {schema}.t_sucursal suc_visible
                    ON suc_visible.id_sucursal = inv_visible.id_sucursal
                WHERE var_visible.id_producto = p.id_producto
                  AND var_visible.activo = TRUE
                  AND suc_visible.id_empresa = p.id_empresa
                  AND suc_visible.activo = TRUE
                  AND COALESCE(inv_visible.stock_disponible, 0) > 0
            )
            """
        ]

        params: List[Any] = [id_empresa]

        # Filtro de categoría activa
        if id_categoria:
            condiciones.append("p.id_categoria = %s")
            condiciones.append("c.activo = TRUE")
            params.append(id_categoria)

        # Filtro de búsqueda textual
        if busqueda and busqueda.strip():
            term = f"%{busqueda.strip()}%"
            condiciones.append(
                "(p.nombre ILIKE %s OR p.descripcion ILIKE %s "
                "OR p.marca ILIKE %s OR p.codigo_producto ILIKE %s)"
            )
            params.extend([term, term, term, term])

        # Filtro por talla
        if id_talla:
            condiciones.append(f"""
                EXISTS (
                    SELECT 1
                    FROM {schema}.t_producto_talla_color v
                    JOIN {schema}.t_talla t
                        ON t.id_talla = v.id_talla
                    WHERE v.id_producto = p.id_producto
                      AND v.id_talla = %s
                      AND v.activo = TRUE
                      AND t.activo = TRUE
                )
            """)
            params.append(id_talla)

        # Filtro por color
        if id_color:
            condiciones.append(f"""
                EXISTS (
                    SELECT 1
                    FROM {schema}.t_producto_talla_color v
                    JOIN {schema}.t_color col
                        ON col.id_color = v.id_color
                    WHERE v.id_producto = p.id_producto
                      AND v.id_color = %s
                      AND v.activo = TRUE
                      AND col.activo = TRUE
                )
            """)
            params.append(id_color)

        # Filtro por temporada
        if temporada and temporada.strip() and temporada.lower() != 'todas':
            condiciones.append("p.temporada ILIKE %s")
            params.append(f"%{temporada.strip()}%")

        # Filtro por colección
        if coleccion and coleccion.strip() and coleccion.lower() != 'todas':
            condiciones.append("p.coleccion ILIKE %s")
            params.append(f"%{coleccion.strip()}%")

        # Filtro por público objetivo (genero)
        if publico and publico.strip() and publico.lower() != 'todos':
            pub_norm = _normalizar_publico(publico)
            if pub_norm == "Mujer":
                condiciones.append("UPPER(TRIM(COALESCE(p.genero, ''))) IN ('MUJER', 'DAMAS', 'DAMA', 'FEMENINO', 'WOMEN')")
            elif pub_norm == "Hombre":
                condiciones.append("UPPER(TRIM(COALESCE(p.genero, ''))) IN ('HOMBRE', 'CABALLEROS', 'CABALLERO', 'MASCULINO', 'MEN')")
            elif pub_norm == "Unisex":
                condiciones.append("UPPER(TRIM(COALESCE(p.genero, 'UNISEX'))) IN ('UNISEX', 'AMBOS', 'MIXTO', '')")
            elif pub_norm == "Niños":
                condiciones.append("UPPER(TRIM(COALESCE(p.genero, ''))) IN ('NIÑOS', 'NINOS', 'NIÑO', 'NINO', 'INFANTIL', 'BOYS')")
            elif pub_norm == "Niñas":
                condiciones.append("UPPER(TRIM(COALESCE(p.genero, ''))) IN ('NIÑAS', 'NINAS', 'NIÑA', 'NINA', 'GIRLS')")
            elif pub_norm == "Bebés":
                condiciones.append("UPPER(TRIM(COALESCE(p.genero, ''))) IN ('BEBÉS', 'BEBES', 'BEBÉ', 'BEBE', 'BABY')")
            else:
                condiciones.append("p.genero ILIKE %s")
                params.append(f"%{publico.strip()}%")

        # Filtro por disponibilidad en sucursal específica
        if id_sucursal and id_sucursal > 0:
            condiciones.append(f"""
                EXISTS (
                    SELECT 1
                    FROM {schema}.t_inventario inv_suc
                    INNER JOIN {schema}.t_producto_talla_color var_suc
                        ON var_suc.id_variante = inv_suc.id_variante
                    INNER JOIN {schema}.t_sucursal suc_f
                        ON suc_f.id_sucursal = inv_suc.id_sucursal
                    WHERE var_suc.id_producto = p.id_producto
                      AND var_suc.activo = TRUE
                      AND suc_f.id_sucursal = %s
                      AND suc_f.id_empresa = p.id_empresa
                      AND COALESCE(suc_f.activo, suc_f.estado, FALSE) = TRUE
                      AND COALESCE(inv_suc.stock_disponible, 0) > 0
                )
            """)
            params.append(id_sucursal)

        # Filtro por rango de precio
        if precio_min is not None and precio_min >= 0:
            condiciones.append("p.precio >= %s")
            params.append(precio_min)

        if precio_max is not None and precio_max >= 0:
            condiciones.append("p.precio <= %s")
            params.append(precio_max)

        where_sql = f"WHERE {' AND '.join(condiciones)}"

        # 1. Total de registros para paginación
        count_query = f"""
            SELECT COUNT(p.id_producto)
            FROM {schema}.t_producto p
            LEFT JOIN {schema}.t_categoria c
                ON c.id_categoria = p.id_categoria
            {where_sql};
        """

        total_res = db.execute_query(
            count_query,
            tuple(params),
            fetchone=True
        )

        total = total_res[0] if total_res else 0

        # 2. Cláusula de ordenamiento
        order_clause = "p.id_producto DESC"

        if orden == "precio_asc":
            order_clause = "p.precio ASC, p.id_producto DESC"
        elif orden == "precio_desc":
            order_clause = "p.precio DESC, p.id_producto DESC"
        elif orden == "nombre_asc":
            order_clause = "p.nombre ASC, p.id_producto DESC"
        elif orden == "nombre_desc":
            order_clause = "p.nombre DESC, p.id_producto DESC"
        elif orden == "recientes":
            order_clause = "p.fecha_registro DESC NULLS LAST, p.id_producto DESC"
        else:
            order_clause = "p.fecha_registro DESC NULLS LAST, p.id_producto DESC"

        # 3. Consulta principal de productos
        query = f"""
            SELECT
                p.id_producto,
                p.id_empresa,
                p.id_categoria,
                c.nombre AS categoria_nombre,
                p.codigo_producto,
                p.nombre,
                p.descripcion,
                p.marca,
                p.genero,
                p.precio,
                p.temporada,
                p.coleccion,
                p.fecha_registro,

                (
                    SELECT img.imagen_url
                    FROM {schema}.t_producto_imagen img
                    WHERE img.id_producto = p.id_producto
                    ORDER BY
                        img.es_principal DESC,
                        img.orden ASC,
                        img.id_imagen ASC
                    LIMIT 1
                ) AS imagen_portada,

                (
                    SELECT COUNT(img.id_imagen)
                    FROM {schema}.t_producto_imagen img
                    WHERE img.id_producto = p.id_producto
                ) AS total_imagenes,

                (
                    SELECT COUNT(v.id_variante)
                    FROM {schema}.t_producto_talla_color v
                    WHERE v.id_producto = p.id_producto
                      AND v.activo = TRUE
                ) AS total_variantes,

                (
                    SELECT json_build_object(
                        'id_promocion', pr.id_promocion,
                        'nombre', pr.nombre,
                        'descripcion', pr.descripcion,
                        'porcentaje_descuento', pp.porcentaje_descuento,
                        'fecha_inicio', pr.fecha_inicio,
                        'fecha_fin', pr.fecha_fin,
                        'precio_promocional',
                            ROUND(
                                p.precio * (
                                    1 - pp.porcentaje_descuento / 100
                                ),
                                2
                            )
                    )
                    FROM {schema}.t_promocion_producto pp
                    INNER JOIN {schema}.t_promocion pr
                        ON pr.id_promocion = pp.id_promocion
                    WHERE pp.id_producto = p.id_producto
                      AND pr.estado = TRUE
                      AND CURRENT_DATE >= pr.fecha_inicio
                      AND CURRENT_DATE <= pr.fecha_fin
                    ORDER BY pr.fecha_inicio DESC
                    LIMIT 1
                ) AS promocion,

                COALESCE((
                    SELECT SUM(inv.stock_disponible)
                    FROM {schema}.t_inventario inv
                    INNER JOIN {schema}.t_sucursal suc
                        ON suc.id_sucursal = inv.id_sucursal
                    INNER JOIN {schema}.t_producto_talla_color var
                        ON var.id_variante = inv.id_variante
                    WHERE var.id_producto = p.id_producto
                      AND var.activo = TRUE
                      AND suc.id_empresa = p.id_empresa
                      AND suc.activo = TRUE
                ), 0) AS stock_disponible_catalogo,
                COALESCE((
                    SELECT MIN(v.precio)
                    FROM {schema}.t_producto_talla_color v
                    WHERE v.id_producto = p.id_producto AND v.activo = TRUE AND v.precio > 0
                ), p.precio) AS precio_min,
                COALESCE((
                    SELECT MAX(v.precio)
                    FROM {schema}.t_producto_talla_color v
                    WHERE v.id_producto = p.id_producto AND v.activo = TRUE AND v.precio > 0
                ), p.precio) AS precio_max

            FROM {schema}.t_producto p
            LEFT JOIN {schema}.t_categoria c
                ON c.id_categoria = p.id_categoria

            {where_sql}

            ORDER BY {order_clause}
            LIMIT %s OFFSET %s;
        """

        exec_params = params + [limit, offset]

        filas = db.execute_query(
            query,
            tuple(exec_params),
            fetchall=True
        ) or []

        productos = []

        ids_productos = [r[0] for r in filas]

        # 4. Cargar variantes resumidas
        variantes_por_prod: Dict[int, Dict[str, Any]] = {
            pid: {
                "tallas": [],
                "colores": []
            }
            for pid in ids_productos
        }

        if ids_productos:
            q_var_summary = f"""
                SELECT DISTINCT
                    v.id_producto,
                    t.id_talla,
                    t.nombre AS talla_nombre,
                    col.id_color,
                    col.nombre AS color_nombre,
                    col.codigo_hex,
                    COALESCE(v.precio, 0) AS precio_variante
                FROM {schema}.t_producto_talla_color v
                JOIN {schema}.t_talla t
                    ON t.id_talla = v.id_talla
                   AND t.activo = TRUE
                JOIN {schema}.t_color col
                    ON col.id_color = v.id_color
                   AND col.activo = TRUE
                WHERE v.id_producto = ANY(%s)
                  AND v.activo = TRUE
                ORDER BY t.id_talla ASC, col.nombre ASC;
            """

            v_rows = db.execute_query(
                q_var_summary,
                (ids_productos,),
                fetchall=True
            ) or []

            for vr in v_rows:
                pid, tid, tnom, cid, cnom, chex = vr[0], vr[1], vr[2], vr[3], vr[4], vr[5]
                pvar = float(vr[6]) if len(vr) > 6 and vr[6] is not None else 0.0

                v_dict = variantes_por_prod[pid]

                if not any(
                    t["id_talla"] == tid
                    for t in v_dict["tallas"]
                ):
                    v_dict["tallas"].append({
                        "id_talla": tid,
                        "nombre": tnom,
                        "precio": pvar
                    })

                if not any(
                    c["id_color"] == cid
                    for c in v_dict["colores"]
                ):
                    v_dict["colores"].append({
                        "id_color": cid,
                        "nombre": cnom,
                        "codigo_hex": chex
                    })

        # 5. Formatear productos
        for r in filas:
            pid = r[0]

            prod_vars = variantes_por_prod.get(
                pid,
                {
                    "tallas": [],
                    "colores": []
                }
            )

            productos.append({
                "id_producto": pid,
                "id_empresa": r[1],
                "id_categoria": r[2],
                "categoria_nombre": r[3] or "Sin Categoría",
                "codigo_producto": r[4],
                "nombre": r[5],
                "descripcion": r[6] or "",
                "marca": r[7] or "Aurora Atelier",
                "genero": r[8] or "Unisex",
                "precio": float(r[9]) if r[9] is not None else 0.0,
                "precio_min": float(r[18]) if len(r) > 18 and r[18] is not None else (float(r[9]) if r[9] is not None else 0.0),
                "precio_max": float(r[19]) if len(r) > 19 and r[19] is not None else (float(r[9]) if r[9] is not None else 0.0),
                "temporada": r[10] or "Atemporal",
                "coleccion": r[11] or "Esenciales",
                "fecha_registro": (
                    r[12].strftime("%Y-%m-%d %H:%M")
                    if r[12] else None
                ),
                "imagen_principal": r[13],
                "total_imagenes": r[14],
                "total_variantes": r[15],
                "promocion": r[16],
                "stock_disponible_catalogo": int(r[17] or 0),
                "estado_stock": (
                    "AGOTADO" if (r[17] or 0) <= 0
                    else "POCAS" if (r[17] or 0) < 3
                    else "DISPONIBLE"
                ),
                "tallas_disponibles": prod_vars["tallas"],
                "colores_disponibles": prod_vars["colores"]
            })

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "productos": productos
        }

    finally:
        db.close_connection()
# ==============================================================================
# DETALLE PÚBLICO DE PRODUCTO CON VARIANTES Y STOCK POR SUCURSAL
# ==============================================================================
def obtener_detalle_producto_publico(id_producto: int, id_empresa: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Obtiene el detalle completo de un producto activo, su galería de fotos,
    sus variantes activas de talla/color y la disponibilidad por sucursal vigente.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # 1. Consulta datos de la prenda
        cond_empresa = "AND p.id_empresa = %s" if id_empresa else ""
        params_base: List[Any] = [id_producto]
        if id_empresa:
            params_base.append(id_empresa)

        q_prod = f"""
            SELECT 
                p.id_producto,
                p.id_empresa,
                e.nombre_empresa,
                p.id_categoria,
                c.nombre AS categoria_nombre,
                p.codigo_producto,
                p.nombre,
                p.descripcion,
                p.marca,
                p.genero,
                p.precio,
                p.temporada,
                p.coleccion,
                p.fecha_registro,
                p.updated_at,
                COALESCE(p.tiene_ra, FALSE) AS tiene_ra,
                p.modelo_2d_url,
                p.tipo_prenda_ra
            FROM {schema}.t_producto p
            LEFT JOIN {schema}.empresa e 
                ON e.id_empresa = p.id_empresa
            LEFT JOIN {schema}.t_categoria c 
                ON c.id_categoria = p.id_categoria
            WHERE p.id_producto = %s
              AND p.activo = TRUE
              {cond_empresa}
              AND (
                  -- Producto de la temporada actual
                  UPPER(
                      TRIM(
                          COALESCE(
                              NULLIF(p.temporada, ''),
                              'PERMANENTE'
                          )
                      )
                  ) =
                  CASE
                      WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (12, 1, 2)
                          THEN 'VERANO'
                      WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (3, 4, 5)
                          THEN 'OTOÑO'
                      WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (6, 7, 8)
                          THEN 'INVIERNO'
                      WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (9, 10, 11)
                          THEN 'PRIMAVERA'
                  END

                  -- Producto permanente
                  OR UPPER(
                      TRIM(
                          COALESCE(
                              NULLIF(p.temporada, ''),
                              'PERMANENTE'
                          )
                      )
                  ) = 'PERMANENTE'

                  -- Producto fuera de temporada con promoción vigente
                  OR EXISTS (
                      SELECT 1
                      FROM {schema}.t_promocion_producto pp_temp
                      INNER JOIN {schema}.t_promocion pr_temp
                          ON pr_temp.id_promocion = pp_temp.id_promocion
                      WHERE pp_temp.id_producto = p.id_producto
                        AND pr_temp.estado = TRUE
                        AND CURRENT_DATE >= pr_temp.fecha_inicio
                        AND CURRENT_DATE <= pr_temp.fecha_fin
                  )
              )
            LIMIT 1;
        """

        p_row = db.execute_query(
            q_prod,
            tuple(params_base),
            fetchone=True
        )

        if not p_row:
            return None

        id_empresa_prod = p_row[1]

        # 2. Promoción vigente del producto
        q_promocion = f"""
            SELECT
                pr.id_promocion,
                pr.nombre,
                pr.descripcion,
                pr.fecha_inicio,
                pr.fecha_fin,
                pp.porcentaje_descuento,
                ROUND(
                    p.precio * (
                        1 - pp.porcentaje_descuento / 100
                    ),
                    2
                ) AS precio_promocional
            FROM {schema}.t_promocion_producto pp
            INNER JOIN {schema}.t_promocion pr
                ON pr.id_promocion = pp.id_promocion
            INNER JOIN {schema}.t_producto p
                ON p.id_producto = pp.id_producto
            WHERE pp.id_producto = %s
              AND pr.estado = TRUE
              AND CURRENT_DATE >= pr.fecha_inicio
              AND CURRENT_DATE <= pr.fecha_fin
            ORDER BY pr.fecha_inicio DESC
            LIMIT 1;
        """

        promocion_row = db.execute_query(
            q_promocion,
            (id_producto,),
            fetchone=True
        )

        promocion = None

        if promocion_row:
            promocion = {
                "id_promocion": promocion_row[0],
                "nombre": promocion_row[1],
                "descripcion": promocion_row[2] or "",
                "fecha_inicio": (
                    promocion_row[3].isoformat()
                    if promocion_row[3] else None
                ),
                "fecha_fin": (
                    promocion_row[4].isoformat()
                    if promocion_row[4] else None
                ),
                "porcentaje_descuento": float(promocion_row[5]),
                "precio_promocional": float(promocion_row[6])
            }

        # 3. Galería de imágenes completa
        q_imgs = f"""
            SELECT 
                id_imagen, 
                imagen_url, 
                public_id, 
                es_principal, 
                orden
            FROM {schema}.t_producto_imagen
            WHERE id_producto = %s
            ORDER BY es_principal DESC, orden ASC, id_imagen ASC;
        """

        imgs_res = db.execute_query(
            q_imgs,
            (id_producto,),
            fetchall=True
        ) or []

        imagenes = [
            {
                "id_imagen": r[0],
                "imagen_url": r[1],
                "public_id": r[2],
                "es_principal": r[3],
                "orden": r[4]
            }
            for r in imgs_res
        ]

        # 4. Variantes activas de talla y color
        q_vars = f"""
            SELECT 
                v.id_variante,
                v.id_talla,
                t.nombre AS talla_nombre,
                v.id_color,
                col.nombre AS color_nombre,
                col.codigo_hex,
                v.sku,
                v.precio,
                v.modelo_ra_url
            FROM {schema}.t_producto_talla_color v
            JOIN {schema}.t_talla t 
                ON t.id_talla = v.id_talla 
                AND t.activo = TRUE
            JOIN {schema}.t_color col 
                ON col.id_color = v.id_color 
                AND col.activo = TRUE
            WHERE v.id_producto = %s 
              AND v.activo = TRUE
            ORDER BY t.id_talla ASC, col.nombre ASC;
        """

        vars_res = db.execute_query(
            q_vars,
            (id_producto,),
            fetchall=True
        ) or []

        variantes = []
        ids_variantes = []
        tiene_modelo_ra = False

        for vr in vars_res:
            ids_variantes.append(vr[0])

            if vr[8]:
                tiene_modelo_ra = True

            variantes.append({
                "id_variante": vr[0],
                "id_talla": vr[1],
                "talla_nombre": vr[2],
                "id_color": vr[3],
                "color_nombre": vr[4],
                "codigo_hex": vr[5],
                "sku": vr[6],
                "precio": (
                    float(vr[7])
                    if vr[7] is not None
                    else float(p_row[10] or 0.0)
                ),
                "modelo_ra_url": vr[8]
            })

        # 5. Revisar si tiene modelo 3D en t_prenda_ra
        q_ra = f"""
            SELECT modelo_3d_url, modelo_ar_url 
            FROM {schema}.t_prenda_ra 
            WHERE id_producto = %s 
              AND estado = TRUE 
            LIMIT 1;
        """

        ra_res = db.execute_query(
            q_ra,
            (id_producto,),
            fetchone=True
        )

        modelo_3d_global = ra_res[0] if ra_res else None
        modelo_ar_global = ra_res[1] if ra_res else None

        if modelo_3d_global or modelo_ar_global:
            tiene_modelo_ra = True

        # 6. Disponibilidad por Sucursal en tiempo real desde t_inventario
        # Consultar todas las sucursales activas del Tenant
        q_sucs = f"""
            SELECT 
                s.id_sucursal,
                s.nombre,
                s.codigo_sucursal,
                s.direccion,
                s.telefono,
                s.correo,
                s.horario_apertura,
                s.horario_cierre,
                ci.nombre AS ciudad_nombre
            FROM {schema}.t_sucursal s
            LEFT JOIN {schema}.t_ciudad ci 
                ON ci.id_ciudad = s.id_ciudad
            WHERE s.id_empresa = %s 
              AND s.activo = TRUE
            ORDER BY s.nombre ASC;
        """

        sucs_res = db.execute_query(
            q_sucs,
            (id_empresa_prod,),
            fetchall=True
        ) or []

        # Consultar stock por sucursal y variante
        stock_map: Dict[int, Dict[int, int]] = {}

        if ids_variantes and sucs_res:
            q_inv = f"""
                SELECT 
                    inv.id_sucursal,
                    inv.id_variante,
                    GREATEST(
                        0,
                        COALESCE(inv.stock_disponible, 0)
                    ) AS stock_disponible
                FROM {schema}.t_inventario inv
                WHERE inv.id_variante = ANY(%s) 
                  AND inv.estado = TRUE;
            """

            inv_res = db.execute_query(
                q_inv,
                (ids_variantes,),
                fetchall=True
            ) or []

            for ir in inv_res:
                suc_id, var_id, stk = ir

                if suc_id not in stock_map:
                    stock_map[suc_id] = {}

                stock_map[suc_id][var_id] = int(stk)

        sucursales_stock = []
        stock_total_general = 0

        for s in sucs_res:
            suc_id = s[0]
            var_stock_dict = stock_map.get(suc_id, {})

            # Total de unidades de esta prenda en la sucursal
            # sumando todas sus variantes
            total_suc = sum(
                var_stock_dict.get(vid, 0)
                for vid in ids_variantes
            )

            stock_total_general += total_suc

            sucursales_stock.append({
                "id_sucursal": suc_id,
                "nombre": s[1],
                "codigo_sucursal": s[2],
                "direccion": s[3] or "Dirección no especificada",
                "telefono": s[4] or "",
                "horario": f"{s[6] or '09:00'} - {s[7] or '20:00'}",
                "ciudad": s[8] or "",
                "stock_total_sucursal": total_suc,
                "disponible": total_suc > 0,
                "stock_por_variante": var_stock_dict
            })

        # Listas agrupadas de tallas y colores para navegación ágil
        tallas_unicas = []
        colores_unicos = []

        for v in variantes:
            if not any(
                t["id_talla"] == v["id_talla"]
                for t in tallas_unicas
            ):
                tallas_unicas.append({
                    "id_talla": v["id_talla"],
                    "nombre": v["talla_nombre"]
                })

            if not any(
                c["id_color"] == v["id_color"]
                for c in colores_unicos
            ):
                colores_unicos.append({
                    "id_color": v["id_color"],
                    "nombre": v["color_nombre"],
                    "codigo_hex": v["codigo_hex"]
                })

        return {
            "id_producto": p_row[0],
            "id_empresa": id_empresa_prod,
            "empresa_nombre": p_row[2],
            "id_categoria": p_row[3],
            "categoria_nombre": p_row[4] or "Colección General",
            "codigo_producto": p_row[5],
            "nombre": p_row[6],
            "descripcion": p_row[7] or "",
            "marca": p_row[8] or "Aurora Atelier",
            "genero": p_row[9] or "Unisex",

            "precio": (
                float(p_row[10])
                if p_row[10] is not None
                else 0.0
            ),

            "promocion": promocion,

            "temporada": p_row[11] or "Atemporal",
            "coleccion": p_row[12] or "Esenciales",
            "fecha_registro": (
                p_row[13].strftime("%Y-%m-%d %H:%M")
                if p_row[13]
                else None
            ),

            "imagenes": imagenes,
            "imagen_principal": (
                imagenes[0]["imagen_url"]
                if imagenes
                else None
            ),

            "variantes": variantes,
            "tallas": tallas_unicas,
            "colores": colores_unicos,

            "sucursales_stock": sucursales_stock,
            "stock_total_general": stock_total_general,
            "hay_stock_disponible": stock_total_general > 0,

            # M14: Vestidor Virtual en Realidad Aumentada
            "tiene_ra": bool(p_row[15]),
            "modelo_2d_url": p_row[16],
            "tipo_prenda_ra": p_row[17] or "TOP",
            "permite_reserva": True,
            "permite_compra": True,
            "permite_vestidor_ra": (
                bool(p_row[15]) or tiene_modelo_ra
            ),

            "recursos_ra": {
                "modelo_2d_url": p_row[16],
                "tipo_prenda_ra": p_row[17] or "TOP",
                "modelo_3d_url": modelo_3d_global,
                "modelo_ar_url": modelo_ar_global
            }
        }

    finally:
        db.close_connection()
# ==============================================================================
# M14 - VESTIDOR VIRTUAL REALIDAD AUMENTADA
# ==============================================================================

ORDEN_TALLAS = {'XXS': 0, 'XS': 1, 'S': 2, 'M': 3, 'L': 4, 'XL': 5, 'XXL': 6, '2XL': 6, '3XL': 7}

def _ordenar_tallas(tallas: Optional[List[str]]) -> List[str]:
    if not tallas:
        return ['S', 'M', 'L']
    def key_fn(t):
        t_str = str(t).strip().upper()
        if t_str in ORDEN_TALLAS:
            return (0, ORDEN_TALLAS[t_str], t_str)
        if t_str.isdigit():
            return (1, int(t_str), t_str)
        return (2, 0, t_str)
    return sorted(list(set(str(t).strip() for t in tallas if t)), key=key_fn)

def _resolver_modelo_3d(custom_url: Optional[str], tipo_prenda: Optional[str]) -> str:
    if custom_url and custom_url.strip():
        return custom_url.strip()
    tipo = (tipo_prenda or "TOP").upper()
    if tipo in ("DRESS", "VESTIDO"):
        return "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/Corset/glTF-Binary/Corset.glb"
    elif tipo in ("PANT", "PANTS", "PANTALON", "CALZADO", "ZAPATO"):
        return "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/MaterialsVariantsShoe/glTF-Binary/MaterialsVariantsShoe.glb"
    return "https://raw.githubusercontent.com/adrianhajdin/project_threejs_ai/main/client/public/shirt_baked.glb"

def obtener_prendas_vestidor_ra(id_empresa: Optional[int] = None, tipo_prenda: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retorna la lista de prendas activas compatibles con el Vestidor Virtual (M14),
    incluyendo modelos 3D volumétricos y tallas disponibles según inventario / variantes activas.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        conds = ["p.activo = TRUE", "p.tiene_ra = TRUE"]
        params: List[Any] = []

        if id_empresa:
            conds.append("p.id_empresa = %s")
            params.append(id_empresa)

        if tipo_prenda and tipo_prenda.upper() != 'TODAS':
            conds.append("UPPER(p.tipo_prenda_ra) = %s")
            params.append(tipo_prenda.upper())

        where_clause = " AND ".join(conds)
        q = f"""
            SELECT 
                p.id_producto,
                p.nombre,
                p.precio,
                p.modelo_2d_url,
                p.tipo_prenda_ra,
                img.imagen_url AS imagen_preview,
                COALESCE(
                    (
                        SELECT array_agg(DISTINCT t.nombre)
                        FROM {schema}.t_producto_talla_color ptc
                        JOIN {schema}.t_talla t ON ptc.id_talla = t.id_talla
                        WHERE ptc.id_producto = p.id_producto AND ptc.activo = TRUE
                    ),
                    ARRAY['S', 'M', 'L']::varchar[]
                ) AS tallas_disponibles,
                ra.modelo_3d_url
            FROM {schema}.t_producto p
            LEFT JOIN LATERAL (
                SELECT imagen_url 
                FROM {schema}.t_producto_imagen 
                WHERE id_producto = p.id_producto 
                ORDER BY es_principal DESC, orden ASC, id_imagen ASC 
                LIMIT 1
            ) img ON TRUE
            LEFT JOIN {schema}.t_prenda_ra ra ON ra.id_producto = p.id_producto AND ra.estado = TRUE
            WHERE {where_clause}
            ORDER BY p.id_producto ASC;
        """
        rows = db.execute_query(q, tuple(params) if params else None, fetchall=True) or []
        resultado = []
        for r in rows:
            tipo_ra = r[4] or "TOP"
            resultado.append({
                "id_producto": r[0],
                "nombre": r[1],
                "precio": float(r[2]) if r[2] is not None else 0.0,
                "modelo_2d_url": r[3] or r[5],
                "tipo_prenda_ra": tipo_ra,
                "imagen_preview": r[5] or r[3],
                "tallas_disponibles": _ordenar_tallas(r[6]),
                "modelo_3d_url": _resolver_modelo_3d(r[7], tipo_ra)
            })
        return resultado
    finally:
        db.close_connection()

def obtener_config_vestidor_producto(id_producto: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene la configuración de vestidor virtual para una prenda específica,
    incluyendo modelo 3D y tallas disponibles.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT 
                p.id_producto,
                p.nombre,
                p.precio,
                COALESCE(p.tiene_ra, FALSE) AS tiene_ra,
                p.modelo_2d_url,
                p.tipo_prenda_ra,
                COALESCE(
                    (
                        SELECT array_agg(DISTINCT t.nombre)
                        FROM {schema}.t_producto_talla_color ptc
                        JOIN {schema}.t_talla t ON ptc.id_talla = t.id_talla
                        WHERE ptc.id_producto = p.id_producto AND ptc.activo = TRUE
                    ),
                    ARRAY['S', 'M', 'L']::varchar[]
                ) AS tallas_disponibles,
                ra.modelo_3d_url
            FROM {schema}.t_producto p
            LEFT JOIN {schema}.t_prenda_ra ra ON ra.id_producto = p.id_producto AND ra.estado = TRUE
            WHERE p.id_producto = %s AND p.activo = TRUE
            LIMIT 1;
        """
        r = db.execute_query(q, (id_producto,), fetchone=True)
        if not r:
            return None
        tipo_ra = r[5] or "TOP"
        return {
            "id_producto": r[0],
            "nombre": r[1],
            "precio": float(r[2]) if r[2] is not None else 0.0,
            "tiene_ra": bool(r[3]),
            "modelo_2d_url": r[4],
            "tipo_prenda_ra": tipo_ra,
            "tallas_disponibles": _ordenar_tallas(r[6]),
            "modelo_3d_url": _resolver_modelo_3d(r[7], tipo_ra)
        }
    finally:
        db.close_connection()

# ==============================================================================
# DISPONIBILIDAD DE VARIANTE POR SUCURSAL EN TIEMPO REAL
# ==============================================================================

def obtener_disponibilidad_variante_sucursales(
    id_variante: int,
    id_empresa: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Consulta en tiempo real la disponibilidad y existencias de una variante específica
    en todas las sucursales activas del Tenant al que pertenece.
    Garantiza aislamiento estricto por empresa y evita cantidades negativas.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # 1. Obtener datos de la variante y su producto/empresa
        q_var = f"""
            SELECT 
                v.id_variante,
                v.id_producto,
                p.nombre AS producto_nombre,
                p.id_empresa,
                e.nombre_empresa,
                t.id_talla,
                t.nombre AS talla_nombre,
                col.id_color,
                col.nombre AS color_nombre,
                col.codigo_hex,
                v.sku,
                COALESCE(v.precio, p.precio) AS precio,
                p.activo AS producto_activo,
                v.activo AS variante_activa,

                -- Verificar si el producto pertenece a la temporada actual,
                -- es permanente o tiene una promoción vigente
                (
                    UPPER(
                        TRIM(
                            COALESCE(
                                NULLIF(p.temporada, ''),
                                'PERMANENTE'
                            )
                        )
                    ) =
                    CASE
                        WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (12, 1, 2)
                            THEN 'VERANO'
                        WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (3, 4, 5)
                            THEN 'OTOÑO'
                        WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (6, 7, 8)
                            THEN 'INVIERNO'
                        WHEN EXTRACT(MONTH FROM CURRENT_DATE) IN (9, 10, 11)
                            THEN 'PRIMAVERA'
                    END

                    OR UPPER(
                        TRIM(
                            COALESCE(
                                NULLIF(p.temporada, ''),
                                'PERMANENTE'
                            )
                        )
                    ) = 'PERMANENTE'

                    OR EXISTS (
                        SELECT 1
                        FROM {schema}.t_promocion_producto pp_temp
                        INNER JOIN {schema}.t_promocion pr_temp
                            ON pr_temp.id_promocion = pp_temp.id_promocion
                        WHERE pp_temp.id_producto = p.id_producto
                          AND pr_temp.estado = TRUE
                          AND CURRENT_DATE >= pr_temp.fecha_inicio
                          AND CURRENT_DATE <= pr_temp.fecha_fin
                    )
                ) AS producto_visible,

                (
                    SELECT json_build_object(
                        'id_promocion', pr.id_promocion,
                        'nombre', pr.nombre,
                        'descripcion', pr.descripcion,
                        'porcentaje_descuento', pp.porcentaje_descuento,
                        'fecha_inicio', pr.fecha_inicio,
                        'fecha_fin', pr.fecha_fin,
                        'precio_promocional',
                            ROUND(
                                COALESCE(v.precio, p.precio) *
                                (1 - pp.porcentaje_descuento / 100),
                                2
                            )
                    )
                    FROM {schema}.t_promocion_producto pp
                    INNER JOIN {schema}.t_promocion pr
                        ON pr.id_promocion = pp.id_promocion
                    WHERE pp.id_producto = p.id_producto
                      AND pr.estado = TRUE
                      AND CURRENT_DATE >= pr.fecha_inicio
                      AND CURRENT_DATE <= pr.fecha_fin
                    ORDER BY pr.fecha_inicio DESC
                    LIMIT 1
                ) AS promocion

            FROM {schema}.t_producto_talla_color v

            JOIN {schema}.t_producto p 
                ON p.id_producto = v.id_producto

            JOIN {schema}.empresa e 
                ON e.id_empresa = p.id_empresa

            JOIN {schema}.t_talla t 
                ON t.id_talla = v.id_talla 
                AND t.activo = TRUE

            JOIN {schema}.t_color col 
                ON col.id_color = v.id_color 
                AND col.activo = TRUE

            WHERE v.id_variante = %s
            LIMIT 1;
        """

        var_row = db.execute_query(
            q_var,
            (id_variante,),
            fetchone=True
        )

        if not var_row:
            return None

        tenant_id = var_row[3]

        if id_empresa and tenant_id != id_empresa:
            return None  # Aislamiento multi-tenant

        # Producto y variante deben estar activos
        if not var_row[12] or not var_row[13]:
            return None

        # Producto debe estar visible para clientes
        if not var_row[14]:
            return None

        # 2. Consultar sucursales activas del Tenant con inventario vigente
        q_sucs = f"""
            SELECT 
                s.id_sucursal,
                s.nombre,
                s.codigo_sucursal,
                s.direccion,
                s.telefono,
                s.correo,
                s.horario_apertura,
                s.horario_cierre,
                ci.nombre AS ciudad_nombre,
                GREATEST(
                    0,
                    COALESCE(inv.stock_disponible, 0)
                ) AS stock_disponible
            FROM {schema}.t_sucursal s
            LEFT JOIN {schema}.t_ciudad ci 
                ON ci.id_ciudad = s.id_ciudad
            LEFT JOIN {schema}.t_inventario inv 
                ON inv.id_sucursal = s.id_sucursal 
                AND inv.id_variante = %s 
                AND inv.estado = TRUE
            WHERE s.id_empresa = %s 
              AND s.activo = TRUE
            ORDER BY s.nombre ASC;
        """

        filas_sucs = db.execute_query(
            q_sucs,
            (id_variante, tenant_id),
            fetchall=True
        ) or []

        sucursales = []
        stock_total = 0

        for s in filas_sucs:
            stock = int(s[9])
            stock_total += stock

            sucursales.append({
                "id_sucursal": s[0],
                "nombre": s[1],
                "codigo_sucursal": s[2],
                "direccion": s[3] or "Dirección no especificada",
                "telefono": s[4] or "",
                "correo": s[5] or "",
                "horario": f"{s[6] or '09:00'} - {s[7] or '20:00'}",
                "ciudad": s[8] or "",
                "stock_disponible": stock,
                "disponible": stock > 0,
                "permite_reserva": True,
                "permite_compra": stock > 0
            })

        return {
            "variante": {
                "id_variante": var_row[0],
                "id_producto": var_row[1],
                "producto_nombre": var_row[2],
                "id_empresa": tenant_id,
                "empresa_nombre": var_row[4],
                "id_talla": var_row[5],
                "talla_nombre": var_row[6],
                "id_color": var_row[7],
                "color_nombre": var_row[8],
                "codigo_hex": var_row[9],
                "sku": var_row[10],
                "precio": (
                    float(var_row[11])
                    if var_row[11] is not None
                    else 0.0
                ),
                "promocion": var_row[15]
            },
            "stock_total": stock_total,
            "hay_disponibilidad": stock_total > 0,
            "sucursales": sucursales
        }

    finally:
        db.close_connection()


def obtener_delta_catalogo(
    id_empresa: Optional[int] = None,
    updated_since: Optional[str] = None,
    id_sucursal: Optional[int] = None,
    limit: int = 200
) -> Dict[str, Any]:
    """
    Recupera el conjunto incremental de productos y variantes modificados desde 'updated_since'.
    Garantiza una sincronización ligera y eficiente para clientes offline (PWA / POS).
    """
    from datetime import datetime, timezone
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        cursor_nuevo = datetime.now(timezone.utc).isoformat()
        
        condiciones = ["1=1"]
        params = []
        if id_empresa:
            condiciones.append("p.id_empresa = %s")
            params.append(id_empresa)
            
        if updated_since:
            condiciones.append("(p.updated_at >= %s OR p.fecha_registro >= %s)")
            params.extend([updated_since, updated_since])
            
        cond_sql = " AND ".join(condiciones)
        
        q_modificados = f"""
            SELECT 
                p.id_producto,
                p.id_empresa,
                p.nombre,
                p.codigo_producto,
                p.precio,
                p.imagen_url,
                p.activo,
                p.updated_at,
                c.nombre AS categoria_nombre
            FROM {schema}.t_producto p
            LEFT JOIN {schema}.t_categoria c ON c.id_categoria = p.id_categoria
            WHERE {cond_sql}
            ORDER BY p.updated_at DESC
            LIMIT %s;
        """
        params.append(limit)
        rows = db.execute_query(q_modificados, tuple(params), fetchall=True) or []
        
        items = []
        for r in rows:
            prod_id = r[0]
            suc_clause = "AND i.id_sucursal = %s" if id_sucursal else ""
            q_vars = f"""
                SELECT 
                    ptc.id_variante,
                    ptc.sku,
                    COALESCE(ptc.precio, %s) AS precio,
                    t.nombre AS talla,
                    col.nombre AS color,
                    COALESCE(SUM(i.stock_disponible), 0) AS stock_disponible
                FROM {schema}.t_producto_talla_color ptc
                LEFT JOIN {schema}.t_talla t ON t.id_talla = ptc.id_talla
                LEFT JOIN {schema}.t_color col ON col.id_color = ptc.id_color
                LEFT JOIN {schema}.t_inventario i ON i.id_variante = ptc.id_variante {suc_clause}
                WHERE ptc.id_producto = %s AND ptc.activo = TRUE
                GROUP BY ptc.id_variante, ptc.sku, ptc.precio, t.nombre, col.nombre;
            """
            v_params = [r[4]]
            if id_sucursal:
                v_params.append(id_sucursal)
            v_params.append(prod_id)
            var_rows = db.execute_query(q_vars, tuple(v_params), fetchall=True) or []
            
            variantes = [{
                "id_variante": vr[0],
                "sku": vr[1],
                "precio": float(vr[2] or 0),
                "talla": vr[3] or "",
                "color": vr[4] or "",
                "stock_disponible": int(vr[5] or 0)
            } for vr in var_rows]
            
            items.append({
                "id_producto": r[0],
                "id_empresa": r[1],
                "nombre": r[2],
                "codigo_producto": r[3],
                "precio": float(r[4] or 0),
                "imagen_url": r[5] or "",
                "activo": bool(r[6]),
                "updated_at": r[7].isoformat() if r[7] else None,
                "categoria": r[8] or "",
                "variantes": variantes
            })
            
        eliminados = []
        if updated_since:
            emp_clause = "AND id_empresa = %s" if id_empresa else ""
            q_del = f"""
                SELECT id_producto 
                FROM {schema}.t_producto 
                WHERE activo = FALSE AND updated_at >= %s {emp_clause};
            """
            d_params = [updated_since]
            if id_empresa:
                d_params.append(id_empresa)
            del_rows = db.execute_query(q_del, tuple(d_params), fetchall=True) or []
            eliminados = [dr[0] for dr in del_rows]
            
        return {
            "cursor": cursor_nuevo,
            "total_modificados": len(items),
            "modificados": items,
            "eliminados_ids": eliminados
        }
    finally:
        db.close_connection()
