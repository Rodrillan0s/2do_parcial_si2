from typing import Optional, List, Dict, Any, Tuple
from app.core.postgres import PostgreSQL, atomic
from app.core.config import Config

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

def obtener_url_miniatura(url: Optional[str], width: int = 120, height: int = 140) -> str:
    if not url or "res.cloudinary.com" not in url or "/upload/" not in url:
        return url or ""
    if "/upload/f_auto,q_auto" in url:
        return url
    return url.replace("/upload/", f"/upload/f_auto,q_auto,w_{width},h_{height},c_fill/")

# ==============================================================================
# LECTURA DE PRODUCTOS
# ==============================================================================

def listar_productos(
    id_empresa: Optional[int] = None,
    solo_activos: bool = False,
    id_categoria: Optional[int] = None,
    busqueda: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    activo: Optional[bool] = None,
    temporada: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Lista productos con categoría, Tenant, portada principal,
    conteos de variantes/fotos y promoción vigente.
    Usa CTE paginada + LEFT JOIN LATERAL para agregar imágenes y variantes
    únicamente sobre las filas de la página solicitada.
    """
    db = PostgreSQL()
    db.create_connection()

    try:
        schema = _get_schema()
        condiciones = []
        params: List[Any] = []

        if id_empresa:
            condiciones.append("p.id_empresa = %s")
            params.append(id_empresa)

        if activo is not None:
            condiciones.append("p.activo = %s")
            params.append(bool(activo))
        elif solo_activos:
            condiciones.append("p.activo = TRUE")

        if id_categoria:
            condiciones.append("p.id_categoria = %s")
            params.append(id_categoria)

        if temporada and temporada.strip() and temporada.strip().upper() != "TODAS":
            condiciones.append("p.temporada = %s")
            params.append(temporada.strip())

        if busqueda and busqueda.strip():
            term = f"%{busqueda.strip()}%"
            condiciones.append(
                "(p.nombre ILIKE %s OR p.descripcion ILIKE %s "
                "OR p.codigo_producto ILIKE %s OR c.nombre ILIKE %s)"
            )
            params.extend([term, term, term, term])

        where_clause = (
            f"WHERE {' AND '.join(condiciones)}"
            if condiciones else ""
        )

        query = f"""
            WITH productos_paginados AS (
                SELECT
                    p.id_producto,
                    p.id_empresa,
                    e.nombre_empresa AS empresa_nombre,
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
                    p.activo,
                    p.estado,
                    p.fecha_registro,
                    p.updated_at,
                    p.imagen_url,
                    COALESCE(p.tiene_ra, FALSE) AS tiene_ra,
                    p.tipo_prenda_ra,
                    p.modelo_2d_url,
                    COUNT(*) OVER() AS total_registros
                FROM {schema}.t_producto p
                LEFT JOIN {schema}.t_categoria c ON p.id_categoria = c.id_categoria
                LEFT JOIN {schema}.empresa e ON p.id_empresa = e.id_empresa
                {where_clause}
                ORDER BY p.id_producto DESC
                LIMIT %s OFFSET %s
            )
            SELECT
                pp.id_producto,
                pp.id_empresa,
                pp.empresa_nombre,
                pp.id_categoria,
                pp.categoria_nombre,
                pp.codigo_producto,
                pp.nombre,
                pp.descripcion,
                pp.marca,
                pp.genero,
                pp.precio,
                pp.temporada,
                pp.coleccion,
                pp.activo,
                pp.estado,
                pp.fecha_registro,
                pp.updated_at,
                COALESCE(img_agg.imagen_principal, pp.imagen_url, '') AS imagen_principal,
                COALESCE(img_agg.total_imagenes, 0) AS total_imagenes,
                COALESCE(var_agg.total_variantes, 0) AS total_variantes,
                pp.tiene_ra,
                pp.tipo_prenda_ra,
                pp.modelo_2d_url,
                promo.promocion_json AS promocion,
                pp.total_registros
            FROM productos_paginados pp
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*)::int AS total_imagenes,
                    (
                        ARRAY_AGG(pi.imagen_url ORDER BY pi.es_principal DESC, pi.orden ASC, pi.id_imagen ASC)
                    )[1] AS imagen_principal
                FROM {schema}.t_producto_imagen pi
                WHERE pi.id_producto = pp.id_producto
            ) img_agg ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*)::int AS total_variantes
                FROM {schema}.t_producto_talla_color ptc
                WHERE ptc.id_producto = pp.id_producto AND ptc.activo = TRUE
            ) var_agg ON TRUE
            LEFT JOIN LATERAL (
                SELECT json_build_object(
                    'id_promocion', pr.id_promocion,
                    'nombre', pr.nombre,
                    'descripcion', pr.descripcion,
                    'porcentaje_descuento', ppr.porcentaje_descuento,
                    'fecha_inicio', pr.fecha_inicio,
                    'fecha_fin', pr.fecha_fin,
                    'precio_promocional', ROUND(pp.precio * (1 - ppr.porcentaje_descuento / 100), 2)
                ) AS promocion_json
                FROM {schema}.t_promocion_producto ppr
                INNER JOIN {schema}.t_promocion pr ON pr.id_promocion = ppr.id_promocion
                WHERE ppr.id_producto = pp.id_producto
                  AND pr.estado = TRUE
                  AND CURRENT_DATE >= pr.fecha_inicio
                  AND CURRENT_DATE <= pr.fecha_fin
                ORDER BY pr.fecha_inicio DESC
                LIMIT 1
            ) promo ON TRUE
            ORDER BY pp.id_producto DESC;
        """

        params.extend([limit, offset])

        filas = db.execute_query(
            query,
            tuple(params),
            fetchall=True
        ) or []

        resultado = []

        for r in filas:
            img_url = r[17] or ""
            resultado.append({
                "id_producto": r[0],
                "id_empresa": r[1],
                "empresa_nombre": r[2] or "Sin Tenant",
                "id_categoria": r[3],
                "categoria_nombre": r[4] or "Sin Categoría",
                "codigo_producto": r[5] or f"PRD-{r[0]}",
                "nombre": r[6],
                "descripcion": r[7] or "",
                "marca": r[8] or "Aurora Atelier",
                "genero": r[9] or "Femenino",
                "precio": float(r[10]) if r[10] is not None else 0.0,
                "temporada": r[11] or "",
                "coleccion": r[12] or "",
                "activo": bool(r[13]),
                "estado": bool(r[14]),
                "fecha_registro": r[15].isoformat() if r[15] else None,
                "updated_at": r[16].isoformat() if r[16] else None,
                "imagen_principal": img_url,
                "imagen_thumbnail": obtener_url_miniatura(img_url),
                "total_imagenes": int(r[18]),
                "total_variantes": int(r[19]),
                "tiene_ra": bool(r[20]),
                "tipo_prenda_ra": r[21],
                "modelo_2d_url": r[22],
                "promocion": r[23],
                "_total_registros": int(r[24]) if len(r) > 24 and r[24] is not None else 0
            })

        return resultado

    finally:
        db.close_connection()

def obtener_producto_por_id(id_producto: int, id_empresa: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Obtiene el detalle completo de un producto con su galería de imágenes,
    variantes (talla x color) y promoción vigente.
    """
    db = PostgreSQL()
    db.create_connection()

    try:
        schema = _get_schema()
        condiciones = ["p.id_producto = %s"]
        params: List[Any] = [id_producto]

        if id_empresa:
            condiciones.append("p.id_empresa = %s")
            params.append(id_empresa)

        query = f"""
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
                p.activo,
                p.estado,
                p.fecha_registro,
                p.updated_at,
                p.imagen_url,
                COALESCE(p.tiene_ra, FALSE) AS tiene_ra,
                p.tipo_prenda_ra,
                p.modelo_2d_url
            FROM {schema}.t_producto p
            LEFT JOIN {schema}.t_categoria c
                ON p.id_categoria = c.id_categoria
            LEFT JOIN {schema}.empresa e
                ON p.id_empresa = e.id_empresa
            WHERE {' AND '.join(condiciones)};
        """

        r = db.execute_query(
            query,
            tuple(params),
            fetchone=True
        )

        if not r:
            return None

        # 1. Obtener promoción vigente
        query_promocion = f"""
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

        r_promocion = db.execute_query(
            query_promocion,
            (id_producto,),
            fetchone=True
        )

        promocion = None

        if r_promocion:
            promocion = {
                "id_promocion": r_promocion[0],
                "nombre": r_promocion[1],
                "descripcion": r_promocion[2] or "",
                "fecha_inicio": (
                    r_promocion[3].isoformat()
                    if r_promocion[3] else None
                ),
                "fecha_fin": (
                    r_promocion[4].isoformat()
                    if r_promocion[4] else None
                ),
                "porcentaje_descuento": float(r_promocion[5]),
                "precio_promocional": float(r_promocion[6])
            }

        # 2. Obtener galería de fotos
        query_imgs = f"""
            SELECT
                id_imagen,
                imagen_url,
                public_id,
                es_principal,
                orden,
                created_at
            FROM {schema}.t_producto_imagen
            WHERE id_producto = %s
            ORDER BY es_principal DESC, orden ASC, id_imagen ASC;
        """

        filas_imgs = db.execute_query(
            query_imgs,
            (id_producto,),
            fetchall=True
        ) or []

        imagenes = []

        for img in filas_imgs:
            imagenes.append({
                "id_imagen": img[0],
                "imagen_url": img[1],
                "public_id": img[2],
                "es_principal": bool(img[3]),
                "orden": img[4],
                "created_at": img[5].isoformat() if img[5] else None
            })

        # 3. Obtener variantes (Tallas x Colores)
        query_vars = f"""
            SELECT
                ptc.id_variante,
                ptc.id_talla,
                t.nombre AS talla_nombre,
                ptc.id_color,
                col.nombre AS color_nombre,
                col.codigo_hex,
                ptc.sku,
                ptc.precio,
                ptc.activo,
                ptc.estado,
                (
                    SELECT COUNT(*)
                    FROM {schema}.t_inventario inv
                    WHERE inv.id_variante = ptc.id_variante
                      AND (
                          inv.stock_actual > 0
                          OR inv.stock_reservado > 0
                      )
                ) AS tiene_stock,
                (
                    SELECT COUNT(*)
                    FROM {schema}.t_movimiento_inventario mov
                    JOIN {schema}.t_inventario inv2
                        ON mov.id_inventario = inv2.id_inventario
                    WHERE inv2.id_variante = ptc.id_variante
                ) AS total_movimientos
            FROM {schema}.t_producto_talla_color ptc
            JOIN {schema}.t_talla t
                ON ptc.id_talla = t.id_talla
            JOIN {schema}.t_color col
                ON ptc.id_color = col.id_color
            WHERE ptc.id_producto = %s
            ORDER BY t.id_talla ASC, col.nombre ASC;
        """

        filas_vars = db.execute_query(
            query_vars,
            (id_producto,),
            fetchall=True
        ) or []

        variantes = []

        for v in filas_vars:
            variantes.append({
                "id_variante": v[0],
                "id_talla": v[1],
                "talla_nombre": v[2],
                "id_color": v[3],
                "color_nombre": v[4],
                "codigo_hex": v[5],
                "sku": v[6] or "",
                "precio": (
                    float(v[7])
                    if v[7] is not None
                    else float(r[10] or 0.0)
                ),
                "activo": bool(v[8]),
                "estado": bool(v[9]),
                "tiene_stock": int(v[10]) > 0,
                "total_movimientos": int(v[11])
            })

        # Imagen de portada resuelta
        portada = next(
            (
                img["imagen_url"]
                for img in imagenes
                if img["es_principal"]
            ),
            None
        )

        if not portada and imagenes:
            portada = imagenes[0]["imagen_url"]

        if not portada:
            portada = r[17] or ""

        return {
            "id_producto": r[0],
            "id_empresa": r[1],
            "empresa_nombre": r[2] or "Sin Tenant",
            "id_categoria": r[3],
            "categoria_nombre": r[4] or "Sin Categoría",
            "codigo_producto": r[5] or f"PRD-{r[0]}",
            "nombre": r[6],
            "descripcion": r[7] or "",
            "marca": r[8] or "Aurora Atelier",
            "genero": r[9] or "Femenino",
            "precio": float(r[10]) if r[10] is not None else 0.0,
            "temporada": r[11] or "",
            "coleccion": r[12] or "",
            "activo": bool(r[13]),
            "estado": bool(r[14]),
            "fecha_registro": r[15].isoformat() if r[15] else None,
            "updated_at": r[16].isoformat() if r[16] else None,
            "imagen_principal": portada,
            "imagenes": imagenes,
            "variantes": variantes,
            "tiene_ra": bool(r[18]),
            "tipo_prenda_ra": r[19],
            "modelo_2d_url": r[20],
            "promocion": promocion
        }

    finally:
        db.close_connection()

def verificar_nombre_duplicado(nombre: str, id_empresa: Optional[int], id_producto_actual: Optional[int] = None) -> bool:
    """
    Verifica si ya existe un producto con el mismo nombre dentro del Tenant.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        query = f"""
            SELECT COUNT(*) 
            FROM {schema}.t_producto 
            WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) 
              AND COALESCE(id_empresa, 0) = COALESCE(%s, 0)
        """
        params = [nombre, id_empresa]
        if id_producto_actual:
            query += " AND id_producto != %s"
            params.append(id_producto_actual)

        res = db.execute_query(query, tuple(params), fetchone=True)
        return (res[0] > 0) if res else False
    finally:
        db.close_connection()

# ==============================================================================
# ESCRITURA Y MUTACIONES
# ==============================================================================

@atomic
def crear_producto(
    id_empresa: int,
    id_categoria: int,
    nombre: str,
    precio: float,
    descripcion: str = "",
    codigo_producto: Optional[str] = None,
    temporada: Optional[str] = None,
    coleccion: Optional[str] = None,
    marca: str = "Aurora Atelier",
    genero: str = "Femenino",
    activo: bool = True,
    tiene_ra: bool = False,
    tipo_prenda_ra: Optional[str] = None,
    modelo_2d_url: Optional[str] = None
) -> int:
    """
    Crea el producto base en t_producto y retorna su id_producto.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        from app.core.tenant_guard import validar_relaciones_tenant
        db.execute_query('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                         (f'catalog-sku:{schema}:{id_empresa}',))
        validar_relaciones_tenant(id_empresa, id_categoria=id_categoria)
        query = f"""
            INSERT INTO {schema}.t_producto (
                id_empresa, id_categoria, nombre, descripcion, precio,
                codigo_producto, temporada, coleccion, marca, genero,
                activo, estado, tiene_ra, tipo_prenda_ra, modelo_2d_url,
                fecha_registro, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING id_producto;
        """
        params = (
            id_empresa, id_categoria, nombre.strip(), descripcion.strip(), precio,
            codigo_producto, temporada.strip() if temporada else None,
            coleccion.strip() if coleccion else None, marca, genero,
            activo, activo, bool(tiene_ra), tipo_prenda_ra, modelo_2d_url
        )
        res = db.execute_query(query, params, fetchone=True, commit=True)
        id_prod = res[0]

        # Si no se pasó código_producto, generamos uno limpio con el ID
        if not codigo_producto:
            codigo_gen = f"AUR-{id_empresa:02d}-{id_prod:04d}"
            db.execute_query(
                f"UPDATE {schema}.t_producto SET codigo_producto = %s WHERE id_producto = %s;",
                (codigo_gen, id_prod),
                commit=True
            )

        return id_prod
    finally:
        db.close_connection()

@atomic
def actualizar_producto(
    id_producto: int,
    id_categoria: int,
    nombre: str,
    precio: float,
    descripcion: str = "",
    codigo_producto: Optional[str] = None,
    temporada: Optional[str] = None,
    coleccion: Optional[str] = None,
    marca: str = "Aurora Atelier",
    genero: str = "Femenino",
    activo: bool = True,
    tiene_ra: bool = False,
    tipo_prenda_ra: Optional[str] = None,
    modelo_2d_url: Optional[str] = None
) -> bool:
    """
    Actualiza la información general del producto.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        from app.core.tenant_guard import validar_relaciones_tenant
        owner = db.execute_query(f'SELECT id_empresa FROM {schema}.t_producto WHERE id_producto=%s', (id_producto,), fetchone=True)
        if not owner:
            from fastapi import HTTPException
            raise HTTPException(404, 'Producto no encontrado.')
        db.execute_query('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                         (f'catalog-sku:{schema}:{owner[0]}',))
        db.execute_query(f'SELECT id_producto FROM {schema}.t_producto WHERE id_producto=%s FOR UPDATE', (id_producto,), fetchone=True)
        validar_relaciones_tenant(owner[0], id_categoria=id_categoria)
        query = f"""
            UPDATE {schema}.t_producto 
            SET 
                id_categoria = %s,
                nombre = %s,
                descripcion = %s,
                precio = %s,
                codigo_producto = COALESCE(%s, codigo_producto),
                temporada = %s,
                coleccion = %s,
                marca = %s,
                genero = %s,
                activo = %s,
                estado = %s,
                tiene_ra = %s,
                tipo_prenda_ra = %s,
                modelo_2d_url = %s,
                updated_at = NOW()
            WHERE id_producto = %s;
        """
        params = (
            id_categoria, nombre.strip(), descripcion.strip(), precio,
            codigo_producto, temporada.strip() if temporada else None,
            coleccion.strip() if coleccion else None, marca, genero,
            activo, activo, bool(tiene_ra), tipo_prenda_ra, modelo_2d_url,
            id_producto
        )
        filas = db.execute_query(query, params, commit=True)
        return filas > 0
    finally:
        db.close_connection()

def cambiar_estado_producto(id_producto: int, activo: bool) -> bool:
    """
    Alterna el estado Activo / Inactivo del producto.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        query = f"""
            UPDATE {schema}.t_producto 
            SET activo = %s, estado = %s, updated_at = NOW() 
            WHERE id_producto = %s;
        """
        filas = db.execute_query(query, (activo, activo, id_producto), commit=True)
        return filas > 0
    finally:
        db.close_connection()

# ==============================================================================
# GESTIÓN DE VARIANTES (TALLA x COLOR)
# ==============================================================================

@atomic
def sincronizar_variantes_producto(
    id_producto: int,
    tallas_ids: List[int],
    colores_ids: List[int],
    precio_base: float,
    precios_por_talla: Optional[Dict[Any, float]] = None,
    precios_variantes: Optional[Dict[Any, float]] = None
) -> Dict[str, Any]:
    """
    Genera y sincroniza la matriz cartesiana (Tallas x Colores) para el producto.
    - Reactiva variantes existentes y actualiza precios específicos por talla/variante.
    - Inserta nuevas variantes con su precio específico por talla (o precio_base).
    - Para variantes no seleccionadas:
        - Si tienen inventario/movimientos -> las desactiva (activo = FALSE) para conservar historial.
        - Si no tienen inventario -> las elimina físicamente.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # Normalizar mapas de precios por talla y por variante
        mapa_precios_talla: Dict[int, float] = {}
        if precios_por_talla and isinstance(precios_por_talla, dict):
            for k, v in precios_por_talla.items():
                try:
                    if v is not None and float(v) > 0:
                        mapa_precios_talla[int(k)] = float(v)
                except (ValueError, TypeError):
                    pass

        mapa_precios_var: Dict[int, float] = {}
        if precios_variantes and isinstance(precios_variantes, dict):
            for k, v in precios_variantes.items():
                try:
                    if v is not None and float(v) > 0:
                        mapa_precios_var[int(k)] = float(v)
                except (ValueError, TypeError):
                    pass

        # Obtener datos del producto para SKU
        prod_row = db.execute_query(
            f"SELECT codigo_producto, id_empresa FROM {schema}.t_producto WHERE id_producto = %s;",
            (id_producto,),
            fetchone=True
        )
        if not prod_row:
            from fastapi import HTTPException
            raise HTTPException(404, 'Producto no encontrado.')
        from app.core.tenant_guard import validar_relaciones_tenant
        validar_relaciones_tenant(prod_row[1], tallas_ids=tallas_ids, colores_ids=colores_ids)
        # Serialize every generated SKU within its real tenant, including absent variants.
        db.execute_query('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                         (f'catalog-sku:{schema}:{prod_row[1]}',))
        db.execute_query(f'SELECT id_producto FROM {schema}.t_producto WHERE id_producto=%s FOR UPDATE', (id_producto,), fetchone=True)
        codigo_prod = prod_row[0] if prod_row and prod_row[0] else f"PRD-{id_producto}"

        # 1. Combinaciones deseadas: set de tuplas (id_talla, id_color)
        combinaciones_deseadas = set()
        for t_id in tallas_ids:
            for c_id in colores_ids:
                combinaciones_deseadas.add((int(t_id), int(c_id)))

        # 2. Consultar variantes existentes en la BD
        query_existentes = f"""
            SELECT id_variante, id_talla, id_color, activo 
            FROM {schema}.t_producto_talla_color 
            WHERE id_producto = %s;
        """
        filas_existentes = db.execute_query(query_existentes, (id_producto,), fetchall=True) or []
        variantes_bd = {}
        for row in filas_existentes:
            # key: (id_talla, id_color) -> (id_variante, activo)
            variantes_bd[(row[1], row[2])] = {"id_variante": row[0], "activo": bool(row[3])}

        creadas = 0
        reactivadas = 0
        desactivadas = 0
        eliminadas = 0

        # Precargar nombres de tallas y colores en lote para evitar N+1
        tallas_unicas = sorted({t_id for (t_id, _) in combinaciones_deseadas})
        colores_unicos = sorted({c_id for (_, c_id) in combinaciones_deseadas})
        mapa_tallas: Dict[int, str] = {}
        mapa_colores: Dict[int, str] = {}

        if tallas_unicas:
            rows_t = db.execute_query(
                f"SELECT id_talla, nombre FROM {schema}.t_talla WHERE id_talla = ANY(%s);",
                (tallas_unicas,),
                fetchall=True
            ) or []
            mapa_tallas = {int(r[0]): (r[1] or "") for r in rows_t}

        if colores_unicos:
            rows_c = db.execute_query(
                f"SELECT id_color, nombre FROM {schema}.t_color WHERE id_color = ANY(%s);",
                (colores_unicos,),
                fetchall=True
            ) or []
            mapa_colores = {int(r[0]): (r[1] or "") for r in rows_c}

        # 3. Procesar combinaciones deseadas
        for (t_id, c_id) in combinaciones_deseadas:
            p_especifico = float(mapa_precios_talla.get(int(t_id), precio_base))
            if (t_id, c_id) in variantes_bd:
                info = variantes_bd[(t_id, c_id)]
                vid = int(info["id_variante"])
                p_final = float(mapa_precios_var.get(vid, p_especifico))
                db.execute_query(
                    f"UPDATE {schema}.t_producto_talla_color SET precio = %s, activo = TRUE, estado = TRUE WHERE id_variante = %s;",
                    (p_final, vid),
                    commit=True
                )
                if not info["activo"]:
                    reactivadas += 1
            else:
                t_raw = mapa_tallas.get(t_id, str(t_id))
                c_raw = mapa_colores.get(c_id, str(c_id))
                t_str = t_raw.replace(" ", "").upper()[:4] if t_raw else str(t_id)
                c_str = c_raw.replace(" ", "").upper()[:4] if c_raw else str(c_id)
                sku = f"{codigo_prod}-{t_str}-{c_str}"

                collision = db.execute_query(f"""SELECT v.id_variante FROM {schema}.t_producto_talla_color v
                    JOIN {schema}.t_producto p ON p.id_producto=v.id_producto
                    WHERE p.id_empresa=%s AND lower(trim(v.sku))=lower(trim(%s)) LIMIT 1""",
                    (prod_row[1], sku), fetchone=True)
                if collision:
                    from fastapi import HTTPException
                    raise HTTPException(409, 'SKU_COLLISION: el codigo generado coincide con otra variante; no se modificaron SKU historicos.')
                db.execute_query(f"""
                    INSERT INTO {schema}.t_producto_talla_color (
                        id_producto, id_talla, id_color, sku, precio, activo, estado, created_at
                    ) VALUES (%s, %s, %s, %s, %s, TRUE, TRUE, NOW())
                """, (id_producto, t_id, c_id, sku, p_especifico), commit=True)
                creadas += 1

        # 4. Procesar variantes que estaban antes pero ya NO están en las seleccionadas (en lote)
        ids_candidatas_baja = [
            int(info["id_variante"])
            for (t_id, c_id), info in variantes_bd.items()
            if (t_id, c_id) not in combinaciones_deseadas and info["activo"]
        ]
        if ids_candidatas_baja:
            uso_rows = db.execute_query(f"""
                SELECT
                    inv.id_variante,
                    COALESCE(SUM(COALESCE(inv.stock_actual, 0) + COALESCE(inv.stock_reservado, 0)), 0) AS stock_total,
                    COUNT(mov.id_movimiento) AS mov_count
                FROM {schema}.t_inventario inv
                LEFT JOIN {schema}.t_movimiento_inventario mov ON mov.id_inventario = inv.id_inventario
                WHERE inv.id_variante = ANY(%s)
                GROUP BY inv.id_variante;
            """, (ids_candidatas_baja,), fetchall=True) or []
            variantes_con_historial = {
                int(r[0]) for r in uso_rows if (r[1] or 0) > 0 or (r[2] or 0) > 0
            }
            ids_desactivar = [vid for vid in ids_candidatas_baja if vid in variantes_con_historial]
            ids_eliminar = [vid for vid in ids_candidatas_baja if vid not in variantes_con_historial]

            if ids_desactivar:
                db.execute_query(
                    f"UPDATE {schema}.t_producto_talla_color SET activo = FALSE, estado = FALSE WHERE id_variante = ANY(%s);",
                    (ids_desactivar,),
                    commit=True
                )
                desactivadas = len(ids_desactivar)
            if ids_eliminar:
                db.execute_query(
                    f"DELETE FROM {schema}.t_producto_talla_color WHERE id_variante = ANY(%s);",
                    (ids_eliminar,),
                    commit=True
                )
                eliminadas = len(ids_eliminar)

        return {
            "total_combinaciones": len(combinaciones_deseadas),
            "creadas": creadas,
            "reactivadas": reactivadas,
            "desactivadas": desactivadas,
            "eliminadas": eliminadas
        }
    finally:
        db.close_connection()


@atomic
def actualizar_precios_variantes_producto(
    id_producto: int,
    precios_por_talla: Optional[Dict[Any, float]] = None,
    precios_por_variante: Optional[Dict[Any, float]] = None
) -> int:
    """
    Actualiza el precio de las variantes activas de un producto según id_talla o id_variante.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        actualizadas = 0
        if precios_por_talla and isinstance(precios_por_talla, dict):
            for tid, precio in precios_por_talla.items():
                try:
                    tid_int = int(tid)
                    p_val = float(precio)
                    if p_val > 0:
                        db.execute_query(
                            f"UPDATE {schema}.t_producto_talla_color SET precio = %s WHERE id_producto = %s AND id_talla = %s AND activo = TRUE;",
                            (p_val, id_producto, tid_int),
                            commit=True
                        )
                        actualizadas += 1
                except (ValueError, TypeError):
                    continue
        if precios_por_variante and isinstance(precios_por_variante, dict):
            for vid, precio in precios_por_variante.items():
                try:
                    vid_int = int(vid)
                    p_val = float(precio)
                    if p_val > 0:
                        db.execute_query(
                            f"UPDATE {schema}.t_producto_talla_color SET precio = %s WHERE id_variante = %s AND id_producto = %s;",
                            (p_val, vid_int, id_producto),
                            commit=True
                        )
                        actualizadas += 1
                except (ValueError, TypeError):
                    continue
        return actualizadas
    finally:
        db.close_connection()

# ==============================================================================
# GESTIÓN DE IMÁGENES MULTIMEDIA (CLOUDINARY)
# ==============================================================================

def agregar_imagen_producto(
    id_producto: int,
    imagen_url: str,
    public_id: str,
    es_principal: bool = False
) -> int:
    """
    Agrega una imagen a t_producto_imagen y sincroniza la portada en t_producto.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # Si es la primera imagen o es_principal es True, asegurar bandera
        conteo_imgs = db.execute_query(
            f"SELECT COUNT(*) FROM {schema}.t_producto_imagen WHERE id_producto = %s;",
            (id_producto,),
            fetchone=True
        )[0]
        if conteo_imgs == 0:
            es_principal = True

        if es_principal:
            # Desmarcar anteriores
            db.execute_query(
                f"UPDATE {schema}.t_producto_imagen SET es_principal = FALSE WHERE id_producto = %s;",
                (id_producto,),
                commit=True
            )

        query = f"""
            INSERT INTO {schema}.t_producto_imagen (
                id_producto, imagen_url, public_id, es_principal, orden, created_at
            ) VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id_imagen;
        """
        res = db.execute_query(query, (id_producto, imagen_url, public_id, es_principal, conteo_imgs), fetchone=True, commit=True)
        id_img = res[0]

        if es_principal:
            db.execute_query(
                f"UPDATE {schema}.t_producto SET imagen_url = %s, updated_at = NOW() WHERE id_producto = %s;",
                (imagen_url, id_producto),
                commit=True
            )

        return id_img
    finally:
        db.close_connection()

def marcar_imagen_principal(id_imagen: int, id_producto: int) -> bool:
    """
    Establece una imagen como la principal de la prenda.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        # Verificar que la imagen pertenezca al producto
        img_row = db.execute_query(
            f"SELECT imagen_url FROM {schema}.t_producto_imagen WHERE id_imagen = %s AND id_producto = %s;",
            (id_imagen, id_producto),
            fetchone=True
        )
        if not img_row:
            return False

        url = img_row[0]
        db.execute_query(
            f"UPDATE {schema}.t_producto_imagen SET es_principal = FALSE WHERE id_producto = %s;",
            (id_producto,),
            commit=True
        )
        db.execute_query(
            f"UPDATE {schema}.t_producto_imagen SET es_principal = TRUE WHERE id_imagen = %s;",
            (id_imagen,),
            commit=True
        )
        db.execute_query(
            f"UPDATE {schema}.t_producto SET imagen_url = %s, updated_at = NOW() WHERE id_producto = %s;",
            (url, id_producto),
            commit=True
        )
        return True
    finally:
        db.close_connection()

def eliminar_imagen_producto(id_imagen: int, id_producto: int) -> Optional[str]:
    """
    Elimina la imagen de la BD y retorna su public_id para borrarla en Cloudinary.
    Si era la principal, promueve otra imagen automáticamente.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        img_row = db.execute_query(
            f"SELECT public_id, es_principal FROM {schema}.t_producto_imagen WHERE id_imagen = %s AND id_producto = %s;",
            (id_imagen, id_producto),
            fetchone=True
        )
        if not img_row:
            return None

        public_id, era_principal = img_row[0], bool(img_row[1])

        db.execute_query(
            f"DELETE FROM {schema}.t_producto_imagen WHERE id_imagen = %s;",
            (id_imagen,),
            commit=True
        )

        # Si era principal, promover la siguiente disponible
        if era_principal:
            siguiente = db.execute_query(
                f"SELECT id_imagen, imagen_url FROM {schema}.t_producto_imagen WHERE id_producto = %s ORDER BY id_imagen ASC LIMIT 1;",
                (id_producto,),
                fetchone=True
            )
            if siguiente:
                db.execute_query(
                    f"UPDATE {schema}.t_producto_imagen SET es_principal = TRUE WHERE id_imagen = %s;",
                    (siguiente[0],),
                    commit=True
                )
                db.execute_query(
                    f"UPDATE {schema}.t_producto SET imagen_url = %s, updated_at = NOW() WHERE id_producto = %s;",
                    (siguiente[1], id_producto),
                    commit=True
                )
            else:
                db.execute_query(
                    f"UPDATE {schema}.t_producto SET imagen_url = NULL, updated_at = NOW() WHERE id_producto = %s;",
                    (id_producto,),
                    commit=True
                )

        return public_id
    finally:
        db.close_connection()

# ==============================================================================
# ELIMINACIÓN INTELIGENTE DE PRODUCTO
# ==============================================================================

def eliminar_producto_seguro(id_producto: int) -> Tuple[str, List[str]]:
    """
    Evalúa si el producto tiene historial o dependencias:
    - Si tiene movimientos de inventario, stock > 0 o ventas -> Desactiva suavemente ('DESACTIVADO', []).
    - Si no tiene historial -> Borra físicamente ('ELIMINADO', [public_ids de fotos para Cloudinary]).
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # 1. Comprobar stock o movimientos en sus variantes
        check_inventario = db.execute_query(f"""
            SELECT 
                COALESCE(SUM(inv.stock_actual), 0),
                COALESCE(SUM(inv.stock_reservado), 0)
            FROM {schema}.t_inventario inv
            JOIN {schema}.t_producto_talla_color ptc ON inv.id_variante = ptc.id_variante
            WHERE ptc.id_producto = %s;
        """, (id_producto,), fetchone=True)
        stock_total = (check_inventario[0] + check_inventario[1]) if check_inventario else 0

        check_movs = db.execute_query(f"""
            SELECT COUNT(*) 
            FROM {schema}.t_movimiento_inventario mov
            JOIN {schema}.t_inventario inv ON mov.id_inventario = inv.id_inventario
            JOIN {schema}.t_producto_talla_color ptc ON inv.id_variante = ptc.id_variante
            WHERE ptc.id_producto = %s;
        """, (id_producto,), fetchone=True)[0]

        # 2. Comprobar detalles de venta
        check_ventas = 0
        ventas_table_exists = db.execute_query(f"""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = '{schema}' AND table_name = 't_detalle_venta';
        """, fetchone=True)[0]
        if ventas_table_exists > 0:
            check_ventas = db.execute_query(f"""
                SELECT COUNT(*) FROM {schema}.t_detalle_venta dv
                JOIN {schema}.t_producto_talla_color ptc ON dv.id_variante = ptc.id_variante
                WHERE ptc.id_producto = %s;
            """, (id_producto,), fetchone=True)[0]

        if stock_total > 0 or check_movs > 0 or check_ventas > 0:
            # Desactivación preventiva
            db.execute_query(
                f"UPDATE {schema}.t_producto SET activo = FALSE, estado = FALSE, updated_at = NOW() WHERE id_producto = %s;",
                (id_producto,),
                commit=True
            )
            db.execute_query(
                f"UPDATE {schema}.t_producto_talla_color SET activo = FALSE, estado = FALSE WHERE id_producto = %s;",
                (id_producto,),
                commit=True
            )
            return ("DESACTIVADO", [])

        # 3. No tiene historial: recolectar public_ids de fotos para Cloudinary
        filas_imgs = db.execute_query(
            f"SELECT public_id FROM {schema}.t_producto_imagen WHERE id_producto = %s;",
            (id_producto,),
            fetchall=True
        ) or []
        public_ids = [r[0] for r in filas_imgs if r[0]]

        # Borrar registros en cascada
        db.execute_query(f"DELETE FROM {schema}.t_producto_imagen WHERE id_producto = %s;", (id_producto,), commit=True)
        db.execute_query(f"DELETE FROM {schema}.t_producto_talla_color WHERE id_producto = %s;", (id_producto,), commit=True)
        db.execute_query(f"DELETE FROM {schema}.t_producto WHERE id_producto = %s;", (id_producto,), commit=True)

        return ("ELIMINADO", public_ids)
    finally:
        db.close_connection()

# ==============================================================================
# GESTIÓN DE PROMOCIONES
# ==============================================================================

def listar_promociones(
    solo_activas: bool = False
) -> List[Dict[str, Any]]:
    """
    Lista las promociones registradas.
    Si solo_activas=True, devuelve únicamente promociones habilitadas.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        condiciones = []
        params: List[Any] = []

        if solo_activas:
            condiciones.append("pr.estado = TRUE")

        where_clause = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

        query = f"""
            SELECT
                pr.id_promocion,
                pr.nombre,
                pr.descripcion,
                pr.fecha_inicio,
                pr.fecha_fin,
                pr.estado,
                CASE
                    WHEN pr.estado = TRUE
                     AND CURRENT_DATE BETWEEN pr.fecha_inicio AND pr.fecha_fin
                    THEN TRUE
                    ELSE FALSE
                END AS vigente
            FROM {schema}.t_promocion pr
            {where_clause}
            ORDER BY pr.id_promocion DESC;
        """

        filas = db.execute_query(query, tuple(params), fetchall=True) or []

        return [
            {
                "id_promocion": r[0],
                "nombre": r[1] or "",
                "descripcion": r[2] or "",
                "fecha_inicio": r[3].isoformat() if r[3] else None,
                "fecha_fin": r[4].isoformat() if r[4] else None,
                "estado": bool(r[5]),
                "vigente": bool(r[6])
            }
            for r in filas
        ]

    finally:
        db.close_connection()


def crear_promocion(
    nombre: str,
    descripcion: Optional[str],
    fecha_inicio,
    fecha_fin,
    estado: bool = True
) -> int:
    """
    Crea una nueva promoción.
    """
    if not nombre or not nombre.strip():
        raise ValueError("El nombre de la promoción es obligatorio.")

    if fecha_inicio > fecha_fin:
        raise ValueError("La fecha de inicio no puede ser posterior a la fecha de fin.")

    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        query = f"""
            INSERT INTO {schema}.t_promocion (
                nombre,
                descripcion,
                fecha_inicio,
                fecha_fin,
                estado
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id_promocion;
        """

        res = db.execute_query(
            query,
            (
                nombre.strip(),
                descripcion.strip() if descripcion else None,
                fecha_inicio,
                fecha_fin,
                estado
            ),
            fetchone=True,
            commit=True
        )

        return res[0]

    finally:
        db.close_connection()


def asignar_promocion_producto(
    id_promocion: int,
    id_producto: int,
    porcentaje_descuento: float
) -> int:
    """
    Asocia un producto a una promoción indicando su porcentaje de descuento.
    No permite promociones con períodos de fechas superpuestos
    para el mismo producto.
    """

    if porcentaje_descuento <= 0 or porcentaje_descuento > 100:
        raise ValueError(
            "El porcentaje de descuento debe estar entre 0.01 y 100."
        )

    db = PostgreSQL()
    db.create_connection()

    try:
        schema = _get_schema()

        # Verificar que la promoción exista y esté activa
        promocion = db.execute_query(
            f"""
                SELECT
                    id_promocion,
                    fecha_inicio,
                    fecha_fin
                FROM {schema}.t_promocion
                WHERE id_promocion = %s
                  AND estado = TRUE
                LIMIT 1;
            """,
            (id_promocion,),
            fetchone=True
        )

        if not promocion:
            raise ValueError(
                "La promoción no existe o está inactiva."
            )

        fecha_inicio_promocion = promocion[1]
        fecha_fin_promocion = promocion[2]

        # Verificar que el producto exista
        producto = db.execute_query(
            f"""
                SELECT id_producto
                FROM {schema}.t_producto
                WHERE id_producto = %s
                LIMIT 1;
            """,
            (id_producto,),
            fetchone=True
        )

        if not producto:
            raise ValueError("El producto no existe.")

        # Verificar si ya está asociado
        existente = db.execute_query(
            f"""
                SELECT id_promocion_producto
                FROM {schema}.t_promocion_producto
                WHERE id_promocion = %s
                  AND id_producto = %s
                LIMIT 1;
            """,
            (id_promocion, id_producto),
            fetchone=True
        )

        # Verificar si existe otra promoción con fechas superpuestas
        promocion_superpuesta = db.execute_query(
            f"""
                SELECT
                    pp.id_promocion,
                    pr.nombre,
                    pr.fecha_inicio,
                    pr.fecha_fin
                FROM {schema}.t_promocion_producto pp
                INNER JOIN {schema}.t_promocion pr
                    ON pr.id_promocion = pp.id_promocion
                WHERE pp.id_producto = %s
                  AND pp.id_promocion <> %s
                  AND pr.estado = TRUE
                  AND pr.fecha_inicio <= %s
                  AND pr.fecha_fin >= %s
                LIMIT 1;
            """,
            (
                id_producto,
                id_promocion,
                fecha_fin_promocion,
                fecha_inicio_promocion
            ),
            fetchone=True
        )

        if promocion_superpuesta:
            raise ValueError(
                f"El producto ya tiene la promoción "
                f"'{promocion_superpuesta[1]}' programada para un "
                f"período que se superpone con la nueva promoción."
            )

        # Si ya está asociado, actualizar el porcentaje
        if existente:
            db.execute_query(
                f"""
                    UPDATE {schema}.t_promocion_producto
                    SET porcentaje_descuento = %s
                    WHERE id_promocion_producto = %s;
                """,
                (
                    porcentaje_descuento,
                    existente[0]
                ),
                commit=True
            )

            return existente[0]

        # Crear nueva asociación
        query = f"""
            INSERT INTO {schema}.t_promocion_producto (
                id_promocion,
                id_producto,
                porcentaje_descuento
            )
            VALUES (%s, %s, %s)
            RETURNING id_promocion_producto;
        """

        res = db.execute_query(
            query,
            (
                id_promocion,
                id_producto,
                porcentaje_descuento
            ),
            fetchone=True,
            commit=True
        )

        return res[0]

    finally:
        db.close_connection()


def obtener_promocion_producto(
    id_producto: int
) -> Optional[Dict[str, Any]]:
    """
    Obtiene la promoción actualmente vigente para un producto.
    Si no existe, retorna None.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        query = f"""
            SELECT
                pr.id_promocion,
                pr.nombre,
                pr.descripcion,
                pr.fecha_inicio,
                pr.fecha_fin,
                pp.porcentaje_descuento
            FROM {schema}.t_promocion_producto pp
            JOIN {schema}.t_promocion pr
                ON pr.id_promocion = pp.id_promocion
            WHERE pp.id_producto = %s
              AND pr.estado = TRUE
              AND CURRENT_DATE BETWEEN pr.fecha_inicio AND pr.fecha_fin
            ORDER BY pr.fecha_inicio DESC
            LIMIT 1;
        """

        r = db.execute_query(
            query,
            (id_producto,),
            fetchone=True
        )

        if not r:
            return None

        return {
            "id_promocion": r[0],
            "nombre": r[1],
            "descripcion": r[2] or "",
            "fecha_inicio": r[3].isoformat() if r[3] else None,
            "fecha_fin": r[4].isoformat() if r[4] else None,
            "porcentaje_descuento": float(r[5])
        }

    finally:
        db.close_connection()

def listar_promociones_producto(
    id_producto: int
) -> List[Dict[str, Any]]:
    """
    Lista todas las promociones asociadas a un producto,
    incluyendo promociones vigentes y finalizadas.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        query = f"""
            SELECT
                pp.id_promocion_producto,
                pr.id_promocion,
                pr.nombre,
                pr.descripcion,
                pr.fecha_inicio,
                pr.fecha_fin,
                pr.estado,
                pp.porcentaje_descuento,
                CASE
                    WHEN pr.estado = TRUE
                     AND CURRENT_DATE BETWEEN pr.fecha_inicio AND pr.fecha_fin
                    THEN TRUE
                    ELSE FALSE
                END AS vigente
            FROM {schema}.t_promocion_producto pp
            INNER JOIN {schema}.t_promocion pr
                ON pr.id_promocion = pp.id_promocion
            WHERE pp.id_producto = %s
            ORDER BY pr.fecha_inicio DESC, pp.id_promocion_producto DESC;
        """

        filas = db.execute_query(
            query,
            (id_producto,),
            fetchall=True
        ) or []

        return [
            {
                "id_promocion_producto": r[0],
                "id_promocion": r[1],
                "nombre": r[2] or "",
                "descripcion": r[3] or "",
                "fecha_inicio": r[4].isoformat() if r[4] else None,
                "fecha_fin": r[5].isoformat() if r[5] else None,
                "estado": bool(r[6]),
                "porcentaje_descuento": float(r[7]),
                "vigente": bool(r[8])
            }
            for r in filas
        ]

    finally:
        db.close_connection()        

def eliminar_promocion_producto(
    id_promocion_producto: int,
    id_producto: int
) -> bool:
    """
    Elimina la asociación entre una promoción y un producto.
    No elimina la promoción.
    """

    db = PostgreSQL()
    db.create_connection()

    try:
        schema = _get_schema()

        existente = db.execute_query(
            f"""
                SELECT id_promocion_producto
                FROM {schema}.t_promocion_producto
                WHERE id_promocion_producto = %s
                  AND id_producto = %s
                LIMIT 1;
            """,
            (
                id_promocion_producto,
                id_producto
            ),
            fetchone=True
        )

        if not existente:
            raise ValueError(
                "La promoción no está asociada al producto."
            )

        db.execute_query(
            f"""
                DELETE FROM {schema}.t_promocion_producto
                WHERE id_promocion_producto = %s
                  AND id_producto = %s;
            """,
            (
                id_promocion_producto,
                id_producto
            ),
            commit=True
        )

        return True

    finally:
        db.close_connection()
