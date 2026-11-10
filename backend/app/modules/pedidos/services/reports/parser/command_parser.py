import re
from typing import Dict, Any, Tuple, List, Optional
from app.modules.pedidos.services.reports.parser.normalizer import normalizar_texto, eliminar_tildes
from app.modules.pedidos.services.reports.parser.dates import interpretar_fechas
from app.modules.pedidos.services.reports.parser.entities import resolver_entidades_en_texto

DICCIONARIO_REPORTES = {
    "devoluciones": [
        "devoluciones y reclamos", "devoluciones", "devolucion", "reclamos", "reclamo",
        "cambios de prenda", "prendas devueltas", "mercancia devuelta",
        "fallas de fabrica", "garantias", "motivos de devolucion", "cambio de producto"
    ],
    "rentabilidad": [
        "rentabilidad y margen", "margen de ganancia", "rentabilidad", "margen bruto",
        "utilidad neta", "utilidad", "margen", "ganancia", "ganancias", "utilidades",
        "costos y margen", "rentabilidad por producto", "margen de utilidad"
    ],
    "rendimiento_personal": [
        "rendimiento de cajeros y personal", "rendimiento de cajeros", "rendimiento de personal",
        "rendimiento personal", "desempeno de cajeros", "ventas por cajero", "ventas por vendedor",
        "cajeros", "vendedores", "ranking de vendedores", "eficiencia de cajeros", "comisiones de venta",
        "desempeno de vendedores", "rendimiento vendedores"
    ],
    "stock_inmovilizado": [
        "stock inmovilizado", "stock estancado", "prendas estancadas", "baja rotacion",
        "prendas sin movimiento", "productos estancados", "ropa sin vender", "stock sin rotacion",
        "inventario estancado", "mercaderia inmovilizada", "capital estancado", "sin rotacion"
    ],
    "ventas_pendientes": [
        "ventas pendientes", "venta pendiente", "prendas por pagar", "pedidos por pagar",
        "pendientes de pago", "pendiente de pago", "por cobrar", "cuentas por cobrar",
        "pedidos pendientes", "saldo pendiente", "ventas por cobrar", "pedidos por cobrar"
    ],
    "reservas": [
        "reservas", "reserva", "prendas apartadas", "prenda apartada",
        "reservaciones", "prendas reservadas", "apartados", "apartado"
    ],
    "pos_auditoria": [
        "auditoria pos", "ventas pos", "venta pos", "punto de venta", "transacciones pos",
        "caja pos", "mostrador pos", "errores pos", "descuadres pos", "auditoria de caja",
        "caja mostrador", "pos"
    ],
    "productos_vendidos": [
        "productos mas vendidos", "producto mas vendido", "prendas mas vendidas",
        "prenda mas vendida", "mas vendido", "mas vendidos", "rotacion de prendas",
        "rotacion de productos", "lo mas vendido", "articulos mas vendidos"
    ],
    "ventas": [
        "ventas", "venta", "vendido", "vendidos", "facturacion",
        "factura", "facturas", "ingresos por ventas", "transacciones de venta",
        "ventas totales", "recaudacion"
    ],
    "inventario": [
        "inventario", "stock", "existencia", "existencias",
        "productos disponibles", "prendas disponibles", "almacen"
    ],
    "pagos": [
        "pagos", "pago", "cobros", "cobro", "transacciones de pago",
        "metodos de pago"
    ],
    "caja": [
        "caja", "cajas", "arqueo", "arqueos", "sesion de caja",
        "sesiones de caja", "cierre de caja", "apertura de caja"
    ],
    "sucursales": [
        "comparativa sucursales", "sucursales", "sucursal",
        "rendimiento por sucursal", "rendimiento sucursales"
    ],
    "valoraciones": [
        "valoraciones", "valoracion", "calificaciones", "calificacion", "estrellas",
        "satisfaccion", "satisfaccion del cliente", "opiniones", "resenas", "quejas",
        "alertas de calidad", "csat", "calidad de prendas", "evaluaciones", "evaluacion",
        "calidad del servicio"
    ]
}

def parsear_comando_voz(comando_crudo: str, id_empresa: int = 1) -> Dict[str, Any]:
    """
    Parser determinista de lenguaje natural / comandos de voz (SIN IA NI TOKENS).
    Transforma texto transcrito o ingresado manualmente en un ReportRequest canónico.
    """
    if not comando_crudo or not comando_crudo.strip():
        return {
            "valido": False,
            "mensaje": "Comando vacío o no recibido.",
            "report_request": None,
            "ambiguities": []
        }

    # 1. Normalización inicial
    texto_limpio = normalizar_texto(comando_crudo, remover_stopwords=False)
    
    # 2. Extracción de agrupaciones (GROUP BY)
    group_by = None
    if re.search(r'\bpor\s+(?:sucursal|tienda|sede)\b', texto_limpio):
        group_by = "sucursal"
        texto_limpio = re.sub(r'\bpor\s+(?:sucursal|tienda|sede)\b', ' ', texto_limpio)
    elif re.search(r'\bpor\s+(?:metodo\s+de\s+pago|forma\s+de\s+pago|metodo)\b', texto_limpio):
        group_by = "metodo_pago"
        texto_limpio = re.sub(r'\bpor\s+(?:metodo\s+de\s+pago|forma\s+de\s+pago|metodo)\b', ' ', texto_limpio)
    elif re.search(r'\bpor\s+(?:categoria|tipo\s+de\s+prenda)\b', texto_limpio):
        group_by = "categoria"
        texto_limpio = re.sub(r'\bpor\s+(?:categoria|tipo\s+de\s+prenda)\b', ' ', texto_limpio)
    elif re.search(r'\bpor\s+(?:cajero|vendedor|personal|usuario)\b', texto_limpio):
        group_by = "cajero"
        texto_limpio = re.sub(r'\bpor\s+(?:cajero|vendedor|personal|usuario)\b', ' ', texto_limpio)
    elif re.search(r'\bpor\s+(?:motivo|razon)\b', texto_limpio):
        group_by = "motivo"
        texto_limpio = re.sub(r'\bpor\s+(?:motivo|razon)\b', ' ', texto_limpio)
    elif re.search(r'\bpor\s+(?:producto|prenda|modelo)\b', texto_limpio):
        group_by = "producto"
        texto_limpio = re.sub(r'\bpor\s+(?:producto|prenda|modelo)\b', ' ', texto_limpio)
    elif re.search(r'\bpor\s+(?:dia|fecha)\b', texto_limpio):
        group_by = "dia"
        texto_limpio = re.sub(r'\bpor\s+(?:dia|fecha)\b', ' ', texto_limpio)
    elif re.search(r'\bpor\s+(?:puntuacion|estrellas|calificacion|satisfaccion)\b', texto_limpio):
        group_by = "puntuacion"
        texto_limpio = re.sub(r'\bpor\s+(?:puntuacion|estrellas|calificacion|satisfaccion)\b', ' ', texto_limpio)
    elif re.search(r'\bpor\s+(?:mes)\b', texto_limpio):
        group_by = "mes"
        texto_limpio = re.sub(r'\bpor\s+(?:mes)\b', ' ', texto_limpio)

    # 3. Extracción de ordenamiento (ORDER BY)
    order_by = None
    order_dir = "DESC"
    if re.search(r'\b(?:mas\s+vendidos?|mayor\s+venta|top)\b', texto_limpio):
        order_by = "unidades_vendidas"
        order_dir = "DESC"
    elif re.search(r'\b(?:menos\s+stock|menor\s+stock|criticos?)\b', texto_limpio):
        order_by = "stock_disponible"
        order_dir = "ASC"
    elif re.search(r'\b(?:mayor\s+rentabilidad|mas\s+rentable|mayor\s+margen)\b', texto_limpio):
        order_by = "margen_porcentual"
        order_dir = "DESC"
    elif re.search(r'\b(?:mayor\s+ganancia|mas\s+ganancia|mayor\s+utilidad)\b', texto_limpio):
        order_by = "utilidad_neta_bs"
        order_dir = "DESC"
    elif re.search(r'\b(?:mas\s+estancado|mayor\s+capital\s+estancado|sin\s+rotacion)\b', texto_limpio):
        order_by = "capital_estancado_bs"
        order_dir = "DESC"
    elif re.search(r'\b(?:mas\s+devoluciones|mayor\s+reclamos?)\b', texto_limpio):
        order_by = "total_devoluciones"
        order_dir = "DESC"

    # 4. Extracción determinista de fechas
    fecha_desde, fecha_hasta, texto_sin_fechas = interpretar_fechas(texto_limpio)

    # 5. Resolución de entidades contra PostgreSQL
    entidades, ambiguedades, texto_residual = resolver_entidades_en_texto(texto_sin_fechas, id_empresa)

    # 6. Detección del tipo de reporte mediante diccionario de sinónimos
    reporte_detectado = None
    texto_norm_final = normalizar_texto(texto_residual, remover_stopwords=True)

    # Buscar primero frases compuestas en el texto limpio (para detectar con prioridad frases como "ventas pendientes")
    for rep_key, terminos in DICCIONARIO_REPORTES.items():
        for t in sorted(terminos, key=lambda x: len(x), reverse=True):
            if re.search(r'\b' + re.escape(t) + r'\b', texto_limpio):
                reporte_detectado = rep_key
                break
        if reporte_detectado:
            break

    # Si no se detectó aún, buscar en texto_norm_final
    if not reporte_detectado:
        for rep_key, terminos in DICCIONARIO_REPORTES.items():
            for t in sorted(terminos, key=lambda x: len(x), reverse=True):
                if re.search(r'\b' + re.escape(t) + r'\b', texto_norm_final):
                    reporte_detectado = rep_key
                    break
            if reporte_detectado:
                break

    # Si no se detectó explícitamente pero hay filtros claros:
    if not reporte_detectado:
        if entidades["estado_stock"] or re.search(r'\b(stock|existencias|prendas)\b', texto_limpio):
            reporte_detectado = "inventario"
        elif entidades["metodo_pago_id"] or re.search(r'\b(pago|pagos|cobro)\b', texto_limpio):
            reporte_detectado = "pagos"
        elif re.search(r'\b(caja|arqueo|sesion)\b', texto_limpio):
            reporte_detectado = "caja"
        elif group_by == "sucursal" and not (entidades["estado_stock"]):
            reporte_detectado = "ventas"
        else:
            # Reporte por defecto más común
            reporte_detectado = "ventas"

    # Si el reporte es 'sucursales', forzar group_by = 'sucursal' si aplica
    if reporte_detectado == "sucursales":
        reporte_detectado = "ventas"
        group_by = "sucursal"

    # 7. Construcción de ReportRequest
    filtros: Dict[str, Any] = {}
    if fecha_desde:
        filtros["fechaDesde"] = fecha_desde
    if fecha_hasta:
        filtros["fechaHasta"] = fecha_hasta
    if entidades["sucursal_id"]:
        filtros["sucursalId"] = entidades["sucursal_id"]
    if entidades["categoria_id"]:
        filtros["categoriaId"] = entidades["categoria_id"]
    if entidades["producto_id"]:
        filtros["productoId"] = entidades["producto_id"]
    if entidades["metodo_pago_id"]:
        filtros["metodoPagoId"] = entidades["metodo_pago_id"]
    if entidades["estado_venta"] and reporte_detectado != "ventas_pendientes":
        filtros["estado"] = entidades["estado_venta"]
    if entidades["estado_stock"]:
        filtros["estadoStock"] = entidades["estado_stock"]

    report_request = {
        "reporte": reporte_detectado,
        "tipo_reporte": reporte_detectado,
        "id_empresa": id_empresa,
        "filtros": {**filtros, **({"id_empresa": id_empresa} if id_empresa else {})},
        "groupBy": group_by,
        "orderBy": order_by,
        "orderDirection": order_dir,
        "formato": "screen"
    }

    # Resumen legible para el usuario
    partes_resumen = [f"Reporte de **{reporte_detectado.upper().replace('_', ' ')}**"]
    if fecha_desde and fecha_hasta:
        if fecha_desde == fecha_hasta:
            partes_resumen.append(f"Fecha: **{fecha_desde}**")
        else:
            partes_resumen.append(f"Período: **{fecha_desde} al {fecha_hasta}**")
    if entidades["sucursal_nombre"]:
        partes_resumen.append(f"Sucursal: **{entidades['sucursal_nombre']}**")
    if entidades["categoria_nombre"]:
        partes_resumen.append(f"Categoría: **{entidades['categoria_nombre']}**")
    if entidades["producto_nombre"]:
        partes_resumen.append(f"Producto: **{entidades['producto_nombre']}**")
    if group_by:
        partes_resumen.append(f"Agrupado por: **{group_by}**")
    if order_by:
        partes_resumen.append(f"Orden: **{order_by} ({order_dir})**")
    if entidades["estado_stock"]:
        partes_resumen.append(f"Filtro Stock: **{entidades['estado_stock'].upper()}**")

    resumen_humano = " • ".join(partes_resumen)

    return {
        "valido": True,
        "comando_original": comando_crudo,
        "resumen_interpretacion": resumen_humano,
        "report_request": report_request,
        "reportRequest": report_request,
        "ambiguities": ambiguedades
    }

interpretar_comando_reporte = parsear_comando_voz
