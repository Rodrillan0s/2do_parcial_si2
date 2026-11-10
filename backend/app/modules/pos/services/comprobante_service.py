import io
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from app.core.postgres import PostgreSQL
from app.core.config import Config

logger = logging.getLogger(__name__)

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

def obtener_datos_venta_comprobante(id_venta: int) -> Optional[Dict[str, Any]]:
    """
    Recupera los datos completos de una venta, sus ítems, cliente, pago y sucursal.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        # 1. Cabecera de venta
        q_vta = f"""
            SELECT 
                v.id_venta,
                v.numero_venta,
                v.tipo_venta,
                v.fecha_venta,
                v.subtotal,
                v.descuento,
                v.total,
                v.estado,
                v.observacion,
                COALESCE(v.nit_ci, '0') AS nit_ci,
                COALESCE(v.razon_social, 'Sin Nombre') AS razon_social,
                COALESCE(v.tipo_documento, 'COMPROBANTE') AS tipo_documento,
                COALESCE(s.nombre, 'Sucursal Principal') AS sucursal_nombre,
                COALESCE(s.direccion, 'Calle Principal') AS sucursal_direccion,
                COALESCE(s.telefono, '') AS sucursal_telefono,
                COALESCE(emp.nombre_empresa, 'AURA Atelier') AS empresa_nombre,
                COALESCE(emp.nit, '1020304050') AS empresa_nit,
                COALESCE(v.razon_social, u.nombre, 'Cliente') AS cliente_nombre,
                COALESCE(u.apellido, '') AS cliente_apellido,
                COALESCE(v.correo_facturacion, u.correo, '') AS cliente_correo,
                COALESCE(u.telefono, '') AS cliente_telefono,
                p.codigo_pedido,
                pg.codigo_transaccion,
                mp.nombre AS metodo_pago_nombre
            FROM {schema}.t_venta v
            LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
            LEFT JOIN {schema}.empresa emp ON emp.id_empresa = s.id_empresa OR emp.id_empresa = v.id_empresa
            LEFT JOIN {schema}.t_cliente c ON c.id_cliente = v.id_cliente
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = v.id_usuario OR u.id_usuario = c.id_usuario
            LEFT JOIN {schema}.t_pedido p ON p.id_venta = v.id_venta
            LEFT JOIN {schema}.t_pago pg ON pg.id_venta = v.id_venta
            LEFT JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = pg.id_metodo_pago
            WHERE v.id_venta = %s
            ORDER BY pg.id_pago DESC
            LIMIT 1;
        """
        row = db.execute_query(q_vta, (id_venta,), fetchone=True)
        if not row:
            return None

        # 2. Ítems del detalle de venta
        q_det = f"""
            SELECT 
                dv.id_variante,
                dv.cantidad,
                dv.precio_unitario,
                dv.subtotal,
                p.nombre AS producto_nombre,
                v.sku,
                t.nombre AS talla_nombre,
                col.nombre AS color_nombre
            FROM {schema}.t_detalle_venta dv
            JOIN {schema}.t_producto_talla_color v ON v.id_variante = dv.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
            JOIN {schema}.t_talla t ON t.id_talla = v.id_talla
            JOIN {schema}.t_color col ON col.id_color = v.id_color
            WHERE dv.id_venta = %s
            ORDER BY dv.id_detalle_venta ASC;
        """
        det_rows = db.execute_query(q_det, (id_venta,), fetchall=True) or []

        items = []
        for d in det_rows:
            items.append({
                "id_variante": d[0],
                "cantidad": d[1],
                "precio_unitario": float(d[2]),
                "subtotal": float(d[3]),
                "producto_nombre": d[4],
                "sku": d[5],
                "talla": d[6],
                "color": d[7]
            })

        nombre_completo = f"{row[17]} {row[18]}".strip() or "Consumidor Final"

        return {
            "id_venta": row[0],
            "numero_venta": row[1],
            "tipo_venta": row[2],
            "fecha_venta": row[3] or datetime.now(),
            "subtotal": float(row[4] or 0.0),
            "descuento": float(row[5] or 0.0),
            "total": float(row[6] or 0.0),
            "estado": row[7],
            "observacion": row[8] or "",
            "nit_ci": row[9],
            "razon_social": row[10],
            "tipo_documento": row[11],
            "sucursal_nombre": row[12],
            "sucursal_direccion": row[13],
            "sucursal_telefono": row[14],
            "empresa_nombre": row[15],
            "empresa_nit": row[16],
            "cliente_nombre": nombre_completo,
            "cliente_correo": row[19],
            "cliente_telefono": row[20],
            "codigo_pedido": row[21] or f"VTA-{row[0]}",
            "codigo_transaccion": row[22] or "TXN-MANUAL",
            "metodo_pago": row[23] or "Pago Electrónico",
            "items": items
        }
    finally:
        db.close_connection()

def generar_pdf_venta(id_venta: int) -> bytes:
    """
    Genera el comprobante de venta o factura electrónica en formato PDF.
    Diseño visual premium para la cadena de moda AURA Atelier.
    """
    datos = obtener_datos_venta_comprobante(id_venta)
    if not datos:
        raise ValueError(f"No se encontró la venta con ID {id_venta}.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Estilos tipográficos
    style_brand = ParagraphStyle(
        'BrandTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E1B4B') # Indigo oscuro
    )

    style_sub = ParagraphStyle(
        'BrandSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#6B7280')
    )

    style_doc_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#4338CA')
    )

    style_doc_num = ParagraphStyle(
        'DocNum',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#111827')
    )

    style_cell = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1F2937')
    )

    style_cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#111827')
    )

    style_cell_right = ParagraphStyle(
        'CellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#1F2937')
    )

    story = []

    # 1. Cabecera (Empresa vs Documento)
    tipo_doc_titulo = "FACTURA ELECTRÓNICA" if datos["tipo_documento"] == "FACTURA" else "COMPROBANTE DE VENTA"
    fecha_str = datos["fecha_venta"].strftime('%d/%m/%Y %H:%M') if isinstance(datos["fecha_venta"], datetime) else str(datos["fecha_venta"])

    header_left = [
        Paragraph(f"<b>AURORA — {datos['empresa_nombre'].upper()}</b>", style_brand),
        Paragraph("Boutique Oficial & Alta Costura", style_sub),
        Paragraph(f"NIT: {datos['empresa_nit']} · Sucursal: {datos['sucursal_nombre']}", style_sub),
        Paragraph(f"{datos['sucursal_direccion']}", style_sub),
        Paragraph(f"Tel: {datos['sucursal_telefono']}", style_sub)
    ]

    header_right = [
        Paragraph(f"<b>{tipo_doc_titulo}</b>", style_doc_title),
        Paragraph(f"N° {datos['numero_venta']}", style_doc_num),
        Spacer(1, 4),
        Paragraph(f"<b>Fecha:</b> {fecha_str}", style_cell_right),
        Paragraph(f"<b>Pedido:</b> {datos['codigo_pedido']}", style_cell_right),
        Paragraph(f"<b>Pago:</b> {datos['metodo_pago']}", style_cell_right),
        Paragraph(f"<b>Transacción:</b> {datos['codigo_transaccion'][:20]}", style_cell_right)
    ]

    header_table = Table(
        [[header_left, header_right]],
        colWidths=[3.8 * inch, 3.7 * inch]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E5E7EB'), spaceBefore=6, spaceAfter=10))

    # 2. Datos del Cliente / Facturación
    razon = datos['razon_social'] if datos['razon_social'] != 'Sin Nombre' else datos['cliente_nombre']
    nit = datos['nit_ci'] if datos['nit_ci'] != '0' else 'Sin NIT'

    client_info = [
        [
            Paragraph("<b>Señor(es):</b> " + razon, style_cell),
            Paragraph("<b>NIT / CI:</b> " + nit, style_cell)
        ],
        [
            Paragraph("<b>Cliente:</b> " + datos['cliente_nombre'], style_cell),
            Paragraph("<b>Correo:</b> " + datos['cliente_correo'], style_cell)
        ]
    ]
    client_table = Table(client_info, colWidths=[4.5 * inch, 3.0 * inch])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F9FAFB')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#F3F4F6')),
        ('PADDING', (0, 0), (-1, -1), 6)
    ]))
    story.append(client_table)
    story.append(Spacer(1, 12))

    # 3. Tabla de Productos
    table_data = [
        [
            Paragraph("<b>#</b>", style_cell_bold),
            Paragraph("<b>Prenda / Variante</b>", style_cell_bold),
            Paragraph("<b>SKU</b>", style_cell_bold),
            Paragraph("<b>Talla / Color</b>", style_cell_bold),
            Paragraph("<b>Cant.</b>", style_cell_bold),
            Paragraph("<b>Precio (Bs.)</b>", style_cell_bold),
            Paragraph("<b>Subtotal (Bs.)</b>", style_cell_bold)
        ]
    ]

    for idx, itm in enumerate(datos["items"], start=1):
        table_data.append([
            Paragraph(str(idx), style_cell),
            Paragraph(itm["producto_nombre"], style_cell),
            Paragraph(itm["sku"], style_cell),
            Paragraph(f"{itm['talla']} · {itm['color']}", style_cell),
            Paragraph(str(itm["cantidad"]), style_cell_right),
            Paragraph(f"{itm['precio_unitario']:.2f}", style_cell_right),
            Paragraph(f"{itm['subtotal']:.2f}", style_cell_right)
        ])

    items_table = Table(
        table_data,
        colWidths=[0.3 * inch, 2.7 * inch, 1.1 * inch, 1.2 * inch, 0.5 * inch, 0.8 * inch, 0.9 * inch]
    )
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEF2FF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#3730A3')),
        ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0E7FF')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 10))

    # 4. Resumen Financiero de Totales
    totals_data = [
        [Paragraph("Subtotal:", style_cell_right), Paragraph(f"Bs. {datos['subtotal']:.2f}", style_cell_right)],
        [Paragraph("Descuento:", style_cell_right), Paragraph(f"Bs. {datos['descuento']:.2f}", style_cell_right)],
        [Paragraph("<b>TOTAL A PAGAR:</b>", style_cell_right), Paragraph(f"<b>Bs. {datos['total']:.2f}</b>", style_cell_right)]
    ]
    totals_table = Table(totals_data, colWidths=[6.0 * inch, 1.5 * inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 1), (-1, 1), 1, colors.HexColor('#D1D5DB')),
        ('LINEBELOW', (0, 2), (-1, 2), 1.5, colors.HexColor('#4338CA'))
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 16))

    # 5. Pie de página legal y de control
    leyenda_fiscal = (
        "«ESTE DOCUMENTO ES LA EMISIÓN DE UN COMPROBANTE OFICIAL DE VENTA POR COMERCIO ELECTRÓNICO»"
        if datos["tipo_documento"] == "COMPROBANTE" else
        "«ESTA FACTURA CONTRIBUYE AL DESARROLLO DEL PAÍS, EL USO ILÍCITO SERÁ SANCIONADO DE ACUERDO A LEY»"
    )

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E5E7EB'), spaceBefore=6, spaceAfter=8))
    story.append(Paragraph(f"<b>Estado de Transacción:</b> {datos['estado']} | Pago acreditado vía {datos['metodo_pago']}", style_sub))
    story.append(Spacer(1, 4))
    story.append(Paragraph(leyenda_fiscal, ParagraphStyle('Leg', parent=styles['Normal'], fontSize=7, alignment=TA_CENTER, textColor=colors.HexColor('#9CA3AF'))))
    story.append(Paragraph("AURA Atelier © 2026 — Plataforma Multi-Tenant de Moda", ParagraphStyle('Leg2', parent=styles['Normal'], fontSize=6, alignment=TA_CENTER, textColor=colors.HexColor('#9CA3AF'))))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def generar_pdf_reserva(id_reserva: int) -> bytes:
    """
    Genera el comprobante de reserva en tienda en formato PDF.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q_res = f"""
            SELECT 
                r.id_reserva,
                r.codigo_reserva,
                r.fecha_reserva,
                r.fecha_hora_visita,
                r.estado,
                r.observaciones,
                s.nombre AS sucursal_nombre,
                s.direccion AS sucursal_direccion,
                s.telefono AS sucursal_telefono,
                emp.nombre_empresa AS empresa_nombre,
                COALESCE(u.nombre, 'Cliente') AS cliente_nombre,
                COALESCE(u.apellido, '') AS cliente_apellido,
                COALESCE(u.correo, '') AS cliente_correo,
                COALESCE(u.telefono, '') AS cliente_telefono,
                COALESCE(r.con_pago, false) AS con_pago,
                COALESCE(r.monto_pagado, 0.0) AS monto_pagado,
                COALESCE(r.estado_pago, 'SIN_PAGO') AS estado_pago
            FROM {schema}.t_reserva r
            JOIN {schema}.t_sucursal s ON s.id_sucursal = r.id_sucursal
            LEFT JOIN {schema}.empresa emp ON emp.id_empresa = s.id_empresa
            JOIN {schema}.t_cliente c ON c.id_cliente = r.id_cliente
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = c.id_usuario
            WHERE r.id_reserva = %s;
        """
        row = db.execute_query(q_res, (id_reserva,), fetchone=True)
        if not row:
            raise ValueError(f"No se encontró la reserva con ID {id_reserva}.")

        q_det = f"""
            SELECT 
                dr.id_variante,
                dr.cantidad,
                p.nombre AS producto_nombre,
                v.sku,
                t.nombre AS talla_nombre,
                col.nombre AS color_nombre,
                COALESCE(v.precio, p.precio, 0.0) AS precio
            FROM {schema}.t_detalle_reserva dr
            JOIN {schema}.t_producto_talla_color v ON v.id_variante = dr.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
            JOIN {schema}.t_talla t ON t.id_talla = v.id_talla
            JOIN {schema}.t_color col ON col.id_color = v.id_color
            WHERE dr.id_reserva = %s;
        """
        det_rows = db.execute_query(q_det, (id_reserva,), fetchall=True) or []
    finally:
        db.close_connection()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    empresa_label = (row[9] or 'Tienda').strip()
    brand_title = f"AURORA — {empresa_label.upper()}"
    es_pagado = bool(row[14])
    monto_p = float(row[15] or 0.0)
    modalidad_txt = f"PAGADA ONLINE (Abonado: Bs. {monto_p:.2f})" if es_pagado else "RESERVA GRATUITA (Pago en Tienda al Probarse)"

    story = [
        Paragraph(f"<b>{brand_title}</b>", ParagraphStyle('B1', fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor('#1E1B4B'))),
        Paragraph("COMPROBANTE OFICIAL DE RESERVA EN TIENDA", ParagraphStyle('B2', fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#D97706'))),
        Paragraph(f"Código: <b>{row[1]}</b> | Fecha: {row[2].strftime('%d/%m/%Y') if row[2] else 'Hoy'} | Modalidad: <b>{modalidad_txt}</b>", ParagraphStyle('B3', fontSize=9, textColor=colors.HexColor('#4B5563'))),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E5E7EB'), spaceBefore=6, spaceAfter=8),
        Paragraph(f"<b>Cliente:</b> {row[10]} {row[11]} ({row[12]})", ParagraphStyle('C1', fontSize=9)),
        Paragraph(f"<b>Sucursal de Visita:</b> {row[6]} — {row[7]}", ParagraphStyle('C2', fontSize=9)),
        Paragraph(f"<b>Fecha/Hora de Prueba Estimada:</b> {row[3].strftime('%d/%m/%Y %H:%M') if row[3] else 'Horario Comercial'}", ParagraphStyle('C3', fontSize=9)),
        Spacer(1, 10)
    ]

    table_data = [[
        Paragraph("<b>#</b>", styles['Normal']),
        Paragraph("<b>Prenda</b>", styles['Normal']),
        Paragraph("<b>SKU</b>", styles['Normal']),
        Paragraph("<b>Talla / Color</b>", styles['Normal']),
        Paragraph("<b>Cant.</b>", styles['Normal']),
        Paragraph("<b>Ref. Precio (Bs.)</b>", styles['Normal'])
    ]]
    for idx, d in enumerate(det_rows, 1):
        table_data.append([
            Paragraph(str(idx), styles['Normal']),
            Paragraph(d[2], styles['Normal']),
            Paragraph(d[3], styles['Normal']),
            Paragraph(f"{d[4]} / {d[5]}", styles['Normal']),
            Paragraph(str(d[1]), styles['Normal']),
            Paragraph(f"{float(d[6]):.2f}", styles['Normal'])
        ])

    t = Table(table_data, colWidths=[0.4 * inch, 3.1 * inch, 1.2 * inch, 1.3 * inch, 0.5 * inch, 1.0 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FEF3C7')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FDE68A')),
        ('PADDING', (0, 0), (-1, -1), 5)
    ]))
    story.append(t)
    story.append(Spacer(1, 16))
    story.append(Paragraph("✦ Presenta este comprobante o tu código de reserva en el probador de la sucursal.", ParagraphStyle('Foot', fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor('#6B7280'))))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
