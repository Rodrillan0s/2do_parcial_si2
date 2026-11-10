from typing import Dict, Any

CATALOGO_REPORTES: Dict[str, Any] = {
    "ventas": {
        "codigo": "ventas",
        "nombre": "Reporte de Ventas",
        "descripcion": "Detalle transaccional de ventas, facturación y medios de cobro.",
        "vista": "vw_ventas_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "fechaDesde", "fechaHasta", "sucursalId", "clienteId", "estado", "metodoPagoId"
        ],
        "agrupaciones_permitidas": [
            "sucursal", "metodo_pago", "dia", "estado", "ciudad"
        ],
        "columnas": [
            {"campo": "numero_venta", "titulo": "N° Venta", "tipo": "string"},
            {"campo": "fecha", "titulo": "Fecha", "tipo": "date"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "cliente", "titulo": "Cliente", "tipo": "string"},
            {"campo": "metodo_pago", "titulo": "Método Pago", "tipo": "string"},
            {"campo": "subtotal", "titulo": "Subtotal (Bs.)", "tipo": "currency"},
            {"campo": "descuento", "titulo": "Descuento (Bs.)", "tipo": "currency"},
            {"campo": "total", "titulo": "Total (Bs.)", "tipo": "currency"},
            {"campo": "estado", "titulo": "Estado", "tipo": "badge"}
        ],
        "campo_monto": "total"
    },

    "inventario": {
        "codigo": "inventario",
        "nombre": "Reporte de Inventario y Stock",
        "descripcion": "Disponibilidad física de prendas por sucursal y alertas de reposición.",
        "vista": "vw_inventario_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "sucursalId", "categoriaId", "productoId", "estadoStock"
        ],
        "agrupaciones_permitidas": [
            "sucursal", "categoria", "estado_stock"
        ],
        "columnas": [
            {"campo": "producto", "titulo": "Prenda / Modelo", "tipo": "string"},
            {"campo": "sku", "titulo": "SKU", "tipo": "string"},
            {"campo": "categoria", "titulo": "Categoría", "tipo": "string"},
            {"campo": "talla", "titulo": "Talla", "tipo": "string"},
            {"campo": "color", "titulo": "Color", "tipo": "string"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "stock_actual", "titulo": "Stock Actual", "tipo": "number"},
            {"campo": "stock_disponible", "titulo": "Disponible", "tipo": "number"},
            {"campo": "stock_minimo", "titulo": "Mínimo", "tipo": "number"},
            {"campo": "estado_stock", "titulo": "Estado", "tipo": "badge"}
        ],
        "campo_monto": "stock_disponible"
    },

    "productos_vendidos": {
        "codigo": "productos_vendidos",
        "nombre": "Reporte de Productos Más Vendidos",
        "descripcion": "Volumen de prendas comercializadas y recaudación acumulada por modelo.",
        "vista": "vw_productos_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "fechaDesde", "fechaHasta", "sucursalId", "categoriaId", "productoId"
        ],
        "agrupaciones_permitidas": [
            "producto", "categoria", "sucursal"
        ],
        "columnas": [
            {"campo": "producto", "titulo": "Prenda / Modelo", "tipo": "string"},
            {"campo": "sku", "titulo": "SKU", "tipo": "string"},
            {"campo": "categoria", "titulo": "Categoría", "tipo": "string"},
            {"campo": "talla", "titulo": "Talla", "tipo": "string"},
            {"campo": "color", "titulo": "Color", "tipo": "string"},
            {"campo": "cantidad", "titulo": "Unidades", "tipo": "number"},
            {"campo": "precio_unitario", "titulo": "Precio Unitario (Bs.)", "tipo": "currency"},
            {"campo": "subtotal_ingresos", "titulo": "Recaudación (Bs.)", "tipo": "currency"}
        ],
        "campo_monto": "subtotal_ingresos"
    },

    "pagos": {
        "codigo": "pagos",
        "nombre": "Reporte de Pagos",
        "descripcion": "Trazabilidad de pagos recibidos, códigos de transacción y pasarelas.",
        "vista": "vw_pagos_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "fechaDesde", "fechaHasta", "sucursalId", "metodoPagoId", "estado"
        ],
        "agrupaciones_permitidas": [
            "metodo_pago", "sucursal", "dia", "estado"
        ],
        "columnas": [
            {"campo": "numero_venta", "titulo": "N° Venta", "tipo": "string"},
            {"campo": "fecha", "titulo": "Fecha", "tipo": "date"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "metodo_pago", "titulo": "Método de Pago", "tipo": "string"},
            {"campo": "codigo_transaccion", "titulo": "Transacción / Ref", "tipo": "string"},
            {"campo": "monto", "titulo": "Monto (Bs.)", "tipo": "currency"},
            {"campo": "estado", "titulo": "Estado", "tipo": "badge"}
        ],
        "campo_monto": "monto"
    },

    "caja": {
        "codigo": "caja",
        "nombre": "Reporte de Sesiones de Caja",
        "descripcion": "Arqueos de mostrador POS, diferencias de efectivo y cierres de turno.",
        "vista": "vw_caja_reporte",
        "permiso": "caja.ver",
        "activo": True,
        "filtros_permitidos": [
            "fechaDesde", "fechaHasta", "sucursalId", "estado"
        ],
        "agrupaciones_permitidas": [
            "sucursal", "caja_nombre", "estado", "dia"
        ],
        "columnas": [
            {"campo": "caja_nombre", "titulo": "Caja", "tipo": "string"},
            {"campo": "codigo_caja", "titulo": "Código", "tipo": "string"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "cajero_nombre", "titulo": "Cajero", "tipo": "string"},
            {"campo": "fecha_apertura", "titulo": "Apertura", "tipo": "date"},
            {"campo": "monto_inicial", "titulo": "Monto Inicial (Bs.)", "tipo": "currency"},
            {"campo": "efectivo_esperado", "titulo": "Esperado (Bs.)", "tipo": "currency"},
            {"campo": "efectivo_contado", "titulo": "Contado (Bs.)", "tipo": "currency"},
            {"campo": "diferencia", "titulo": "Diferencia (Bs.)", "tipo": "currency"},
            {"campo": "estado", "titulo": "Estado", "tipo": "badge"}
        ],
        "campo_monto": "efectivo_contado"
    },

    "ventas_pendientes": {
        "codigo": "ventas_pendientes",
        "nombre": "Reporte de Ventas y Cobros Pendientes",
        "descripcion": "Control de ventas presenciales y pedidos online con cobro pendiente o prendas por liquidar.",
        "vista": "vw_ventas_pendientes_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "fechaDesde", "fechaHasta", "sucursalId", "clienteId", "canal", "estado"
        ],
        "agrupaciones_permitidas": [
            "sucursal", "canal", "estado_pago", "ciudad", "dia"
        ],
        "columnas": [
            {"campo": "numero_documento", "titulo": "N° Documento", "tipo": "string"},
            {"campo": "fecha", "titulo": "Fecha", "tipo": "date"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "cliente", "titulo": "Cliente", "tipo": "string"},
            {"campo": "telefono", "titulo": "Teléfono", "tipo": "string"},
            {"campo": "canal", "titulo": "Canal", "tipo": "string"},
            {"campo": "total", "titulo": "Total Pendiente (Bs.)", "tipo": "currency"},
            {"campo": "dias_pendiente", "titulo": "Días Pendiente", "tipo": "number"},
            {"campo": "estado_pago", "titulo": "Estado", "tipo": "badge"}
        ],
        "campo_monto": "total"
    },

    "reservas": {
        "codigo": "reservas",
        "nombre": "Reporte de Reservas de Prendas",
        "descripcion": "Seguimiento de prendas apartadas por clientes, fechas límite de visita y vigencia.",
        "vista": "vw_reservas_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "fechaDesde", "fechaHasta", "sucursalId", "clienteId", "vigencia"
        ],
        "agrupaciones_permitidas": [
            "sucursal", "vigencia", "prenda", "dia"
        ],
        "columnas": [
            {"campo": "codigo_reserva", "titulo": "Cód. Reserva", "tipo": "string"},
            {"campo": "fecha", "titulo": "Fecha Reserva", "tipo": "date"},
            {"campo": "fecha_vencimiento", "titulo": "Fecha Límite", "tipo": "date"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "cliente", "titulo": "Cliente", "tipo": "string"},
            {"campo": "telefono", "titulo": "Teléfono", "tipo": "string"},
            {"campo": "prenda", "titulo": "Prenda", "tipo": "string"},
            {"campo": "talla", "titulo": "Talla", "tipo": "string"},
            {"campo": "color", "titulo": "Color", "tipo": "string"},
            {"campo": "cantidad", "titulo": "Cant.", "tipo": "number"},
            {"campo": "precio_unitario", "titulo": "Precio (Bs.)", "tipo": "currency"},
            {"campo": "subtotal_estimado", "titulo": "Subtotal (Bs.)", "tipo": "currency"},
            {"campo": "vigencia", "titulo": "Vigencia", "tipo": "badge"}
        ],
        "campo_monto": "subtotal_estimado"
    },

    "pos_auditoria": {
        "codigo": "pos_auditoria",
        "nombre": "Reporte de Auditoría y Ventas POS",
        "descripcion": "Trazabilidad de ventas de mostrador POS, control de cajeros, conciliación de pagos y detección de anomalías.",
        "vista": "vw_pos_reporte",
        "permiso": "caja.ver",
        "activo": True,
        "filtros_permitidos": [
            "fechaDesde", "fechaHasta", "sucursalId", "cajaId", "usuarioId", "estadoVenta", "alerta"
        ],
        "agrupaciones_permitidas": [
            "sucursal", "caja", "cajero", "metodo_pago", "estado_venta", "alerta_auditoria", "dia"
        ],
        "columnas": [
            {"campo": "numero_venta", "titulo": "N° Venta", "tipo": "string"},
            {"campo": "fecha", "titulo": "Fecha", "tipo": "date"},
            {"campo": "hora", "titulo": "Hora", "tipo": "string"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "caja", "titulo": "Caja", "tipo": "string"},
            {"campo": "cajero", "titulo": "Cajero", "tipo": "string"},
            {"campo": "cliente", "titulo": "Cliente", "tipo": "string"},
            {"campo": "metodo_pago", "titulo": "Método Pago", "tipo": "string"},
            {"campo": "total", "titulo": "Total (Bs.)", "tipo": "currency"},
            {"campo": "estado_venta", "titulo": "Estado Venta", "tipo": "badge"},
            {"campo": "estado_sesion", "titulo": "Caja Sesión", "tipo": "badge"},
            {"campo": "alerta_auditoria", "titulo": "Auditoría", "tipo": "badge"}
        ],
        "campo_monto": "total"
    },

    "sucursales": {
        "codigo": "sucursales",
        "nombre": "Reporte Comparativo de Sucursales",
        "descripcion": "Rendimiento consolidado, facturación total, cantidad de ventas y ticket promedio por sede.",
        "vista": "vw_sucursales_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "sucursalId", "ciudad"
        ],
        "agrupaciones_permitidas": [
            "ciudad", "sucursal"
        ],
        "columnas": [
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "ciudad", "titulo": "Ciudad", "tipo": "string"},
            {"campo": "telefono", "titulo": "Teléfono", "tipo": "string"},
            {"campo": "cantidad_ventas", "titulo": "N° Ventas", "tipo": "number"},
            {"campo": "total_ingresos", "titulo": "Total Ingresos (Bs.)", "tipo": "currency"},
            {"campo": "ticket_promedio", "titulo": "Ticket Promedio (Bs.)", "tipo": "currency"}
        ],
        "campo_monto": "total_ingresos"
    },
"devoluciones": {
        "codigo": "devoluciones",
        "nombre": "Reporte de Devoluciones y Reclamos",
        "descripcion": "Control de solicitudes de devolución, motivos de reclamo, estado de reembolsos y montos devueltos.",
        "vista": "vw_devoluciones_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "fechaDesde", "fechaHasta", "sucursalId", "clienteId", "estado", "motivoGeneral", "reembolsoEstado"
        ],
        "agrupaciones_permitidas": [
            "sucursal", "motivo_general", "estado", "reembolso_metodo", "dia"
        ],
        "columnas": [
            {"campo": "codigo_devolucion", "titulo": "Cód. Devolución", "tipo": "string"},
            {"campo": "fecha", "titulo": "Fecha", "tipo": "date"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "cliente", "titulo": "Cliente", "tipo": "string"},
            {"campo": "numero_venta", "titulo": "N° Venta", "tipo": "string"},
            {"campo": "motivo_general", "titulo": "Motivo", "tipo": "badge"},
            {"campo": "total_articulos", "titulo": "Prendas", "tipo": "number"},
            {"campo": "monto_total_devolucion", "titulo": "Total Devolución (Bs.)", "tipo": "currency"},
            {"campo": "estado", "titulo": "Estado", "tipo": "badge"},
            {"campo": "reembolso_estado", "titulo": "Reembolso", "tipo": "badge"}
        ],
        "campo_monto": "monto_total_devolucion"
    },

    "rentabilidad": {
        "codigo": "rentabilidad",
        "nombre": "Reporte de Rentabilidad y Margen",
        "descripcion": "Análisis de ingresos brutos, costo estimado y margen de utilidad por modelo, categoría y sucursal.",
        "vista": "vw_rentabilidad_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "fechaDesde", "fechaHasta", "sucursalId", "categoriaId", "productoId"
        ],
        "agrupaciones_permitidas": [
            "categoria", "producto", "sucursal", "dia"
        ],
        "columnas": [
            {"campo": "producto", "titulo": "Prenda / Modelo", "tipo": "string"},
            {"campo": "categoria", "titulo": "Categoría", "tipo": "string"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "transacciones", "titulo": "Ventas", "tipo": "number"},
            {"campo": "unidades_vendidas", "titulo": "Unidades", "tipo": "number"},
            {"campo": "ingresos_totales", "titulo": "Ingresos (Bs.)", "tipo": "currency"},
            {"campo": "costo_estimado", "titulo": "Costo Est. (Bs.)", "tipo": "currency"},
            {"campo": "margen_bruto_bs", "titulo": "Margen Bruto (Bs.)", "tipo": "currency"},
            {"campo": "margen_porcentaje", "titulo": "Margen %", "tipo": "badge"}
        ],
        "campo_monto": "margen_bruto_bs"
    },

    "rendimiento_personal": {
        "codigo": "rendimiento_personal",
        "nombre": "Reporte de Rendimiento de Cajeros y Personal",
        "descripcion": "Métricas de productividad, volumen de facturación y promedio por transacción por empleado.",
        "vista": "vw_rendimiento_personal_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "fechaDesde", "fechaHasta", "sucursalId", "usuarioId"
        ],
        "agrupaciones_permitidas": [
            "empleado_nombre", "sucursal", "rol", "dia"
        ],
        "columnas": [
            {"campo": "empleado_nombre", "titulo": "Colaborador", "tipo": "string"},
            {"campo": "rol", "titulo": "Rol", "tipo": "badge"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "fecha", "titulo": "Fecha", "tipo": "date"},
            {"campo": "total_ventas", "titulo": "Total Tickets", "tipo": "number"},
            {"campo": "total_recaudado", "titulo": "Recaudación (Bs.)", "tipo": "currency"},
            {"campo": "ticket_promedio", "titulo": "Ticket Promedio (Bs.)", "tipo": "currency"}
        ],
        "campo_monto": "total_recaudado"
    },

    "stock_inmovilizado": {
        "codigo": "stock_inmovilizado",
        "nombre": "Reporte de Stock Inmovilizado / Baja Rotación",
        "descripcion": "Prendas disponibles en tiendas físicas sin rotación reciente, recomendadas para ofertas o rebajas.",
        "vista": "vw_stock_inmovilizado_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "sucursalId", "categoriaId", "productoId"
        ],
        "agrupaciones_permitidas": [
            "sucursal", "categoria", "producto"
        ],
        "columnas": [
            {"campo": "producto", "titulo": "Prenda / Modelo", "tipo": "string"},
            {"campo": "codigo_producto", "titulo": "Código", "tipo": "string"},
            {"campo": "categoria", "titulo": "Categoría", "tipo": "string"},
            {"campo": "talla", "titulo": "Talla", "tipo": "string"},
            {"campo": "color", "titulo": "Color", "tipo": "string"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "stock_disponible", "titulo": "Stock Disponible", "tipo": "number"},
            {"campo": "precio", "titulo": "Precio Unit. (Bs.)", "tipo": "currency"},
            {"campo": "capital_estancado_bs", "titulo": "Capital Estancado (Bs.)", "tipo": "currency"},
            {"campo": "ultima_venta", "titulo": "Última Actividad", "tipo": "date"}
        ],
        "campo_monto": "capital_estancado_bs"
    },

    "valoraciones": {
        "codigo": "valoraciones",
        "nombre": "Reporte de Valoraciones y Satisfacción",
        "descripcion": "Auditoría de satisfacción de clientes, calidad de prendas, estrellas CSAT y alertas críticas de servicio.",
        "vista": "vw_valoraciones_reporte",
        "permiso": "reportes.ver",
        "activo": True,
        "filtros_permitidos": [
            "fechaDesde", "fechaHasta", "sucursalId", "productoId", "categoriaId", "clienteId", "puntuacion", "estado", "requiereRevision"
        ],
        "agrupaciones_permitidas": [
            "sucursal", "producto", "categoria", "puntuacion", "estado_satisfaccion", "dia"
        ],
        "columnas": [
            {"campo": "fecha", "titulo": "Fecha", "tipo": "date"},
            {"campo": "cliente", "titulo": "Cliente", "tipo": "string"},
            {"campo": "producto", "titulo": "Prenda / Concepto", "tipo": "string"},
            {"campo": "categoria", "titulo": "Categoría", "tipo": "string"},
            {"campo": "sucursal", "titulo": "Sucursal", "tipo": "string"},
            {"campo": "puntuacion", "titulo": "Estrellas (1-5)", "tipo": "number"},
            {"campo": "codigo_referencia", "titulo": "N° Ref / Pedido", "tipo": "string"},
            {"campo": "motivo_negativo", "titulo": "Motivo Observación", "tipo": "string"},
            {"campo": "comentario", "titulo": "Comentario del Cliente", "tipo": "string"},
            {"campo": "estado_satisfaccion", "titulo": "Satisfacción", "tipo": "badge"}
        ],
        "campo_monto": "puntuacion"
    }
}

ALIASES_REPORTES: Dict[str, str] = {
    "productos": "productos_vendidos",
    "producto": "productos_vendidos",
    "venta": "ventas",
    "sucursal": "sucursales",
    "cajas": "caja",
    "pago": "pagos",
    "reserva": "reservas",
    "pos": "pos_auditoria",
    "devolucion": "devoluciones",
    "reclamo": "devoluciones",
    "reclamos": "devoluciones",
    "margen": "rentabilidad",
    "utilidad": "rentabilidad",
    "ganancia": "rentabilidad",
    "cajeros": "rendimiento_personal",
    "vendedores": "rendimiento_personal",
    "personal": "rendimiento_personal",
    "inmovilizado": "stock_inmovilizado",
    "estancado": "stock_inmovilizado",
    "rotacion_lenta": "stock_inmovilizado",
    "valoracion": "valoraciones",
    "calificacion": "valoraciones",
    "calificaciones": "valoraciones",
    "satisfaccion": "valoraciones",
    "opiniones": "valoraciones",
    "resenas": "valoraciones",
    "csat": "valoraciones",
    "quejas": "valoraciones",
}


def resolver_alias_reporte(codigo: str) -> str:
    cod = (codigo or '').lower().strip()
    return ALIASES_REPORTES.get(cod, cod)

def obtener_definicion_reporte(codigo_reporte: str) -> Dict[str, Any]:
    """Recupera la especificación de un reporte del catálogo."""
    cod = resolver_alias_reporte(codigo_reporte)
    if cod not in CATALOGO_REPORTES:
        raise ValueError(f"El reporte '{codigo_reporte}' no está registrado en el catálogo del sistema.")
    rep = CATALOGO_REPORTES[cod]
    if not rep.get("activo", False):
        raise ValueError(f"El reporte '{rep['nombre']}' se encuentra temporalmente inactivo.")
    return rep
