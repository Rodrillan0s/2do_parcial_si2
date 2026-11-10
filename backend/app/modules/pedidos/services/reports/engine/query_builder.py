from typing import Dict, Any, Tuple, List, Optional
from app.core.config import Config

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

def construir_consulta_reporte(
    definicion: Dict[str, Any],
    request: Dict[str, Any],
    id_empresa: int,
    sucursales_permitidas: Optional[List[int]] = None
) -> Tuple[str, Tuple, List[Dict[str, Any]]]:
    """
    Construye una consulta SQL estrictamente parametrizada (%s) sobre las vistas.
    Garantiza el aislamiento multi-tenant forzando 'id_empresa = %s'
    y nunca concatena texto ingresado por el usuario en la sentencia SQL.
    """
    schema = _get_schema()
    vista = f"{schema}.{definicion['vista']}"
    filtros = request.get("filtros") or {}
    group_by = request.get("groupBy")
    order_by = request.get("orderBy")

    # Normalización de sinónimos entre command_parser y catálogo de vistas
    synonyms_group = {
        "cajero": "empleado_nombre" if definicion.get("codigo") == "rendimiento_personal" else "cajero",
        "motivo": "motivo_general",
        "tienda": "sucursal",
        "sede": "sucursal",
        "forma_pago": "metodo_pago",
        "caja": "caja_nombre" if definicion.get("codigo") == "caja" else "caja",
    }
    synonyms_order = {
        "margen_porcentual": "margen_porcentaje",
        "utilidad_neta_bs": "margen_bruto_bs",
        "total_devoluciones": "monto_total_devolucion",
        "capital_estancado": "capital_estancado_bs",
    }
    if group_by in synonyms_group:
        group_by = synonyms_group[group_by]
    if order_by in synonyms_order:
        order_by = synonyms_order[order_by]

    order_dir = "DESC" if str(request.get("orderDirection", "DESC")).upper() == "DESC" else "ASC"

    where_clauses = ["id_empresa = %s"]
    params = [id_empresa]

    filtros_permitidos = set(definicion.get("filtros_permitidos", []))

    # Restricción de sucursal por usuario de Nivel 4/5 (Encargado/Cajero)
    if sucursales_permitidas == []:
        where_clauses.append('FALSE')
    if sucursales_permitidas and len(sucursales_permitidas) > 0:
        placeholders = ', '.join(['%s'] * len(sucursales_permitidas))
        where_clauses.append(f"id_sucursal IN ({placeholders})")
        params.extend(sucursales_permitidas)

    # 1. Filtros de Fecha (Inclusivos) — solo si el reporte lo permite
    if "fechaDesde" in filtros_permitidos:
        if filtros.get("fechaDesde"):
            where_clauses.append("fecha >= %s")
            params.append(filtros["fechaDesde"])
        if filtros.get("fechaHasta"):
            where_clauses.append("fecha <= %s")
            params.append(filtros["fechaHasta"])

    # 2. Filtros de Entidades
    if filtros.get("sucursalId") and "sucursalId" in filtros_permitidos:
        where_clauses.append("id_sucursal = %s")
        params.append(filtros["sucursalId"])

    if filtros.get("categoriaId") and "categoriaId" in filtros_permitidos:
        where_clauses.append("id_categoria = %s")
        params.append(filtros["categoriaId"])

    if filtros.get("productoId") and "productoId" in filtros_permitidos:
        where_clauses.append("id_producto = %s")
        params.append(filtros["productoId"])

    if filtros.get("metodoPagoId") and "metodoPagoId" in filtros_permitidos:
        where_clauses.append("id_metodo_pago = %s")
        params.append(filtros["metodoPagoId"])

    if filtros.get("clienteId") and "clienteId" in filtros_permitidos:
        where_clauses.append("id_cliente = %s")
        params.append(filtros["clienteId"])

    if filtros.get("usuarioId") and "usuarioId" in filtros_permitidos:
        where_clauses.append("id_usuario = %s")
        params.append(filtros["usuarioId"])

    if filtros.get("cajaId") and "cajaId" in filtros_permitidos:
        where_clauses.append("id_caja = %s")
        params.append(filtros["cajaId"])

    # Filtro de Estado adaptativo
    estado_val = filtros.get("estado") or filtros.get("estadoVenta")
    if estado_val and str(estado_val).upper() != "TODOS":
        # En ventas_pendientes, la vista ya contiene exclusivamente pendientes
        if definicion.get("codigo") == "ventas_pendientes" and str(estado_val).upper() in ("PENDIENTE", "PENDIENTES", "PENDIENTE_PAGO"):
            pass
        elif "estado" in filtros_permitidos or "estadoVenta" in filtros_permitidos:
            campos_vista = [c["campo"] for c in definicion.get("columnas", [])]
            col_estado = "estado"
            if "estado" in campos_vista:
                col_estado = "estado"
            elif "estado_pago" in campos_vista:
                col_estado = "estado_pago"
            elif "estado_venta" in campos_vista:
                col_estado = "estado_venta"
            where_clauses.append(f"UPPER({col_estado}) = %s")
            params.append(str(estado_val).upper())

    if filtros.get("estadoStock") and filtros.get("estadoStock") != "todos" and "estadoStock" in filtros_permitidos:
        where_clauses.append("LOWER(estado_stock) = %s")
        params.append(str(filtros["estadoStock"]).lower())

    if filtros.get("canal") and "canal" in filtros_permitidos:
        where_clauses.append("UPPER(canal) = %s")
        params.append(str(filtros["canal"]).upper())

    if filtros.get("vigencia") and "vigencia" in filtros_permitidos:
        where_clauses.append("UPPER(vigencia) = %s")
        params.append(str(filtros["vigencia"]).upper())

    if filtros.get("motivoGeneral") and "motivoGeneral" in filtros_permitidos:
        where_clauses.append("UPPER(motivo_general) = %s")
        params.append(str(filtros["motivoGeneral"]).upper())

    if filtros.get("reembolsoEstado") and "reembolsoEstado" in filtros_permitidos:
        where_clauses.append("UPPER(reembolso_estado) = %s")
        params.append(str(filtros["reembolsoEstado"]).upper())

    if filtros.get("alerta") and "alerta" in filtros_permitidos:
        where_clauses.append("alerta_auditoria = %s")
        params.append(filtros["alerta"])

    if filtros.get("ciudad") and "ciudad" in filtros_permitidos:
        where_clauses.append("LOWER(ciudad) LIKE LOWER(%s)")
        params.append(f"%{filtros['ciudad']}%")

    if filtros.get("puntuacion") and "puntuacion" in filtros_permitidos:
        where_clauses.append("puntuacion = %s")
        params.append(int(filtros["puntuacion"]))

    if filtros.get("requiereRevision") is not None and "requiereRevision" in filtros_permitidos:
        where_clauses.append("requiere_revision = %s")
        params.append(bool(filtros["requiereRevision"]))

    where_sql = " AND ".join(where_clauses)

    # =========================================================================
    # RAMA A: CONSULTA CON AGRUPACIÓN (GROUP BY)
    # =========================================================================
    if group_by and group_by in definicion.get("agrupaciones_permitidas", []):
        columna_grupo = group_by
        
        # Adaptaciones de nombres de columna en vista
        if columna_grupo == "dia":
            col_expr = "fecha"
            col_alias = "dia"
        else:
            col_expr = columna_grupo
            col_alias = columna_grupo

        campo_monto = definicion.get("campo_monto", "total")
        is_score = campo_monto == "puntuacion"
        
        sql = f"""
            SELECT 
                {col_expr} AS {col_alias},
                COUNT(*) AS cantidad_registros,
                COALESCE(SUM({campo_monto}), 0) AS total_monto,
                ROUND(COALESCE(AVG({campo_monto}), 0), 2) AS promedio_monto
            FROM {vista}
            WHERE {where_sql}
            GROUP BY {col_expr}
            ORDER BY total_monto {order_dir};
        """
        
        columnas_meta = [
            {"campo": col_alias, "titulo": col_alias.replace('_', ' ').capitalize(), "tipo": "string"},
            {"campo": "cantidad_registros", "titulo": "Opiniones / Registros" if is_score else "Registros / Transacciones", "tipo": "number"},
            {"campo": "total_monto", "titulo": "Puntos Acumulados" if is_score else "Monto Total (Bs.)", "tipo": "number" if is_score else "currency"},
            {"campo": "promedio_monto", "titulo": "Promedio (★)" if is_score else "Promedio (Bs.)", "tipo": "number" if is_score else "currency"}
        ]
        return sql, tuple(params), columnas_meta

    # =========================================================================
    # RAMA B: CONSULTA DE DETALLE ESTÁNDAR
    # =========================================================================
    columnas_meta = definicion["columnas"]
    campos_sql = [c["campo"] for c in columnas_meta]
    select_sql = ", ".join(campos_sql)

    # Ordenamiento seguro verificado contra campos permitidos
    campo_orden = order_by if (order_by and any(c["campo"] == order_by for c in columnas_meta)) else campos_sql[0]
    
    # Si el reporte tiene columna 'fecha' o 'total', preferirlas para orden lógico
    if not order_by:
        if "fecha" in campos_sql:
            campo_orden = "fecha"
            order_dir = "DESC"
        elif "total" in campos_sql:
            campo_orden = "total"
            order_dir = "DESC"
        elif "stock_disponible" in campos_sql:
            campo_orden = "stock_disponible"
            order_dir = "ASC"

    sql = f"""
        SELECT {select_sql}
        FROM {vista}
        WHERE {where_sql}
        ORDER BY {campo_orden} {order_dir}
        LIMIT 500;
    """

    return sql, tuple(params), columnas_meta
