import io
from datetime import datetime
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfgen import canvas

from app.modules.pedidos.repos import reportes_repos
from app.modules.auth.services.rbac_services import obtener_nivel_actor
from app.modules.pedidos.services.kpis_services import _resolver_contexto_tenant, _normalizar_fechas


# ==============================================================================
# CANVAS CON NUMERACIÓN DE PÁGINAS "PÁGINA X DE Y"
# ==============================================================================

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Pie de página institucional
        texto_pie = f"AURA Atelier • Sistema de Información y Reportería Empresarial • Página {self._pageNumber} de {page_count}"
        self.drawRightString(self._pagesize[0] - 36, 25, texto_pie)
        
        # Línea sutil superior de pie de página
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 38, self._pagesize[0] - 36, 38)
        self.restoreState()


# ==============================================================================
# ESTILOS CORPORATIVOS REPORTLAB
# ==============================================================================

def _obtener_estilos_reporte():
    styles = getSampleStyleSheet()
    
    azul_primario = colors.HexColor("#1E1B4B")
    gris_oscuro = colors.HexColor("#1E293B")
    gris_medio = colors.HexColor("#64748B")
    
    title_style = ParagraphStyle(
        'RepTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=azul_primario,
        alignment=TA_LEFT
    )
    
    subtitle_style = ParagraphStyle(
        'RepSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=gris_medio,
        alignment=TA_LEFT
    )
    
    meta_label = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=azul_primario
    )
    
    meta_val = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=gris_oscuro
    )
    
    th_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=TA_CENTER
    )
    
    tb_style = ParagraphStyle(
        'TableBody',
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=gris_oscuro,
        alignment=TA_LEFT
    )
    
    tb_center = ParagraphStyle(
        'TableBodyCenter',
        parent=tb_style,
        alignment=TA_CENTER
    )
    
    tb_right = ParagraphStyle(
        'TableBodyRight',
        parent=tb_style,
        alignment=TA_RIGHT
    )
    
    summary_label = ParagraphStyle(
        'SumLabel',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=azul_primario
    )
    
    summary_val = ParagraphStyle(
        'SumVal',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=gris_oscuro,
        alignment=TA_RIGHT
    )
    
    return {
        "title": title_style,
        "subtitle": subtitle_style,
        "meta_label": meta_label,
        "meta_val": meta_val,
        "th": th_style,
        "tb": tb_style,
        "tb_center": tb_center,
        "tb_right": tb_right,
        "sum_label": summary_label,
        "sum_val": summary_val
    }


def _generar_encabezado_reporte(story, empresa_info: dict, titulo_reporte: str, filtros_aplicados: str, usuario_nombre: str, estilos: dict):
    """
    Construye el bloque de membrete oficial de AURA Atelier y la empresa tenant.
    """
    nom_emp = empresa_info.get("nombre_empresa", "AURA Atelier")
    nit = empresa_info.get("nit", "4045127018")
    dir_emp = empresa_info.get("direccion", "Av. San Martín #450")
    tel_emp = empresa_info.get("telefono", "70011223")
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")

    col_izq = [
        Paragraph(f"<b>{nom_emp.upper()}</b>", estilos["title"]),
        Paragraph(f"NIT: {nit} • Tel: {tel_emp}", estilos["subtitle"]),
        Paragraph(f"{dir_emp}", estilos["subtitle"]),
    ]

    col_der = [
        Paragraph(f"<b>{titulo_reporte.upper()}</b>", ParagraphStyle('TitDer', parent=estilos["title"], fontSize=13, alignment=TA_RIGHT)),
        Paragraph(f"<b>Fecha Emisión:</b> {fecha_emision}", ParagraphStyle('SubDer', parent=estilos["subtitle"], alignment=TA_RIGHT)),
        Paragraph(f"<b>Emitido por:</b> {usuario_nombre}", ParagraphStyle('SubDer2', parent=estilos["subtitle"], alignment=TA_RIGHT)),
        Paragraph(f"<b>Filtros:</b> {filtros_aplicados}", ParagraphStyle('SubDer3', parent=estilos["subtitle"], alignment=TA_RIGHT, textColor=colors.HexColor("#4338CA"))),
    ]

    tabla_head = Table([[col_izq, col_der]], colWidths=[280, 260])
    tabla_head.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    
    story.append(tabla_head)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E1B4B"), spaceAfter=14, spaceBefore=4))


# ==============================================================================
# SERVICIOS DE OBTENCIÓN DE DATOS (JSON)
# ==============================================================================

def generar_reporte_ventas(token_data: dict, id_sucursal: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, estado: Optional[str] = None, id_metodo_pago: Optional[int] = None, id_empresa: Optional[int] = None):
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    
    data = reportes_repos.obtener_reporte_ventas_db(id_empresa_final, id_sucursal_final, f_ini, f_fin, estado, id_metodo_pago)
    return {
        "success": True,
        "message": "Reporte de ventas generado exitosamente.",
        "data": data
    }


def generar_reporte_inventario(token_data: dict, id_sucursal: Optional[int] = None, id_categoria: Optional[int] = None, estado_stock: Optional[str] = None, id_empresa: Optional[int] = None):
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    
    data = reportes_repos.obtener_reporte_inventario_db(id_empresa_final, id_sucursal_final, id_categoria, estado_stock)
    return {
        "success": True,
        "message": "Reporte de inventario generado exitosamente.",
        "data": data
    }


def generar_reporte_productos_vendidos(token_data: dict, id_sucursal: Optional[int] = None, id_categoria: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, id_empresa: Optional[int] = None):
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    
    data = reportes_repos.obtener_reporte_productos_vendidos_db(id_empresa_final, id_sucursal_final, id_categoria, f_ini, f_fin)
    return {
        "success": True,
        "message": "Reporte de productos vendidos generado exitosamente.",
        "data": data
    }


def generar_reporte_sucursales(token_data: dict, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, id_empresa: Optional[int] = None):
    id_empresa_final, _ = _resolver_contexto_tenant(token_data, None, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    
    data = reportes_repos.obtener_reporte_sucursales_db(id_empresa_final, f_ini, f_fin)
    return {
        "success": True,
        "message": "Reporte comparativo por sucursal generado exitosamente.",
        "data": data
    }


def generar_reporte_valoraciones(token_data: dict, id_sucursal: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, puntuacion: Optional[int] = None, requiere_revision: Optional[bool] = None, id_empresa: Optional[int] = None):
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    
    data = reportes_repos.obtener_reporte_valoraciones_db(id_empresa_final, id_sucursal_final, f_ini, f_fin, puntuacion, requiere_revision)
    return {
        "success": True,
        "message": "Reporte de valoraciones generado exitosamente.",
        "data": data
    }



# ==============================================================================
# GENERADOR OFICIAL DE PDFs REPORTLAB
# ==============================================================================

def generar_pdf_reporte_ventas(token_data: dict, id_sucursal: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, estado: Optional[str] = None, id_metodo_pago: Optional[int] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    
    datos = reportes_repos.obtener_reporte_ventas_db(id_empresa_final, id_sucursal_final, f_ini, f_fin, estado, id_metodo_pago)
    empresa_info = reportes_repos.obtener_info_empresa_para_reporte_db(id_empresa_final)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=48
    )
    
    estilos = _obtener_estilos_reporte()
    story = []
    
    # Filtros para encabezado
    filtros = []
    if fecha_inicio and fecha_fin:
        filtros.append(f"{fecha_inicio} al {fecha_fin}")
    elif fecha_inicio:
        filtros.append(f"Desde {fecha_inicio}")
    elif fecha_fin:
        filtros.append(f"Hasta {fecha_fin}")
    else:
        filtros.append("Histórico Completo")
    if id_sucursal_final:
        filtros.append(f"Sucursal #{id_sucursal_final}")
    if estado:
        filtros.append(f"Estado: {estado}")
    filtros_txt = " • ".join(filtros)
    
    usuario_nombre = f"{token_data.get('nombre', 'Administrador')} {token_data.get('apellido', '')}".strip()
    
    _generar_encabezado_reporte(story, empresa_info, "Reporte Oficial de Ventas", filtros_txt, usuario_nombre, estilos)
    
    # Tabla de Ventas
    headers = [
        Paragraph("<b>N° Venta</b>", estilos["th"]),
        Paragraph("<b>Fecha</b>", estilos["th"]),
        Paragraph("<b>Sucursal</b>", estilos["th"]),
        Paragraph("<b>Cliente</b>", estilos["th"]),
        Paragraph("<b>Método</b>", estilos["th"]),
        Paragraph("<b>Total (Bs.)</b>", estilos["th"]),
        Paragraph("<b>Estado</b>", estilos["th"]),
    ]
    
    table_data = [headers]
    for it in datos["items"]:
        table_data.append([
            Paragraph(str(it["numero_venta"]), estilos["tb_center"]),
            Paragraph(str(it["fecha"]), estilos["tb_center"]),
            Paragraph(str(it["sucursal"][:18]), estilos["tb"]),
            Paragraph(str(it["cliente"][:20]), estilos["tb"]),
            Paragraph(str(it["metodo_pago"]), estilos["tb_center"]),
            Paragraph(f"Bs. {it['total']:,.2f}", estilos["tb_right"]),
            Paragraph(str(it["estado"]), estilos["tb_center"]),
        ])
        
    t_ventas = Table(table_data, colWidths=[70, 75, 100, 110, 75, 65, 45], repeatRows=1)
    t_ventas.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E1B4B")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_ventas)
    story.append(Spacer(1, 14))
    
    # Cuadro de Resumen
    res = datos["resumen"]
    resumen_data = [
        [
            Paragraph(f"<b>Cantidad de Ventas:</b> {res['cantidad_ventas']}", estilos["sum_label"]),
            Paragraph(f"<b>Ticket Promedio:</b> Bs. {res['ticket_promedio']:,.2f}", estilos["sum_label"]),
            Paragraph(f"<b>Total Recaudado:</b> Bs. {res['total_recaudado']:,.2f}", ParagraphStyle('TotG', parent=estilos["sum_val"], fontSize=10, textColor=colors.HexColor("#1E1B4B")))
        ]
    ]
    t_res = Table(resumen_data, colWidths=[180, 180, 180])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EEF2FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#C7D2FE")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(KeepTogether([t_res]))
    
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


def generar_pdf_reporte_inventario(token_data: dict, id_sucursal: Optional[int] = None, id_categoria: Optional[int] = None, estado_stock: Optional[str] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    datos = reportes_repos.obtener_reporte_inventario_db(id_empresa_final, id_sucursal_final, id_categoria, estado_stock)
    empresa_info = reportes_repos.obtener_info_empresa_para_reporte_db(id_empresa_final)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=48
    )
    
    estilos = _obtener_estilos_reporte()
    story = []
    
    filtros = []
    if id_sucursal_final:
        filtros.append(f"Sucursal #{id_sucursal_final}")
    if estado_stock:
        filtros.append(f"Filtro Stock: {estado_stock.upper()}")
    else:
        filtros.append("Todas las Existencias")
    filtros_txt = " • ".join(filtros)
    
    usuario_nombre = f"{token_data.get('nombre', 'Administrador')} {token_data.get('apellido', '')}".strip()
    _generar_encabezado_reporte(story, empresa_info, "Reporte de Inventario y Existencias", filtros_txt, usuario_nombre, estilos)
    
    headers = [
        Paragraph("<b>Producto / Prenda</b>", estilos["th"]),
        Paragraph("<b>SKU</b>", estilos["th"]),
        Paragraph("<b>Categoría</b>", estilos["th"]),
        Paragraph("<b>Talla</b>", estilos["th"]),
        Paragraph("<b>Color</b>", estilos["th"]),
        Paragraph("<b>Sucursal</b>", estilos["th"]),
        Paragraph("<b>Actual</b>", estilos["th"]),
        Paragraph("<b>Disponible</b>", estilos["th"]),
        Paragraph("<b>Mínimo</b>", estilos["th"]),
        Paragraph("<b>Estado</b>", estilos["th"]),
    ]
    
    table_data = [headers]
    for it in datos["items"]:
        estado_color = "#10B981" if it["estado_alerta"] == "ÓPTIMO" else ("#EF4444" if it["estado_alerta"] == "AGOTADO" else "#F59E0B")
        table_data.append([
            Paragraph(str(it["producto"][:26]), estilos["tb"]),
            Paragraph(str(it["sku"]), estilos["tb_center"]),
            Paragraph(str(it["categoria"]), estilos["tb"]),
            Paragraph(str(it["talla"]), estilos["tb_center"]),
            Paragraph(str(it["color"]), estilos["tb"]),
            Paragraph(str(it["sucursal"][:20]), estilos["tb"]),
            Paragraph(str(it["stock_actual"]), estilos["tb_center"]),
            Paragraph(str(it["stock_disponible"]), estilos["tb_center"]),
            Paragraph(str(it["stock_minimo"]), estilos["tb_center"]),
            Paragraph(f"<font color='{estado_color}'><b>{it['estado_alerta']}</b></font>", estilos["tb_center"]),
        ])
        
    t_inv = Table(table_data, colWidths=[150, 95, 95, 40, 60, 110, 45, 50, 45, 50], repeatRows=1)
    t_inv.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E1B4B")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_inv)
    story.append(Spacer(1, 14))
    
    res = datos["resumen"]
    resumen_data = [
        [
            Paragraph(f"<b>Variantes Registradas:</b> {res['total_items_registrados']}", estilos["sum_label"]),
            Paragraph(f"<b>Stock Total Unidades:</b> {res['stock_total_unidades']}", estilos["sum_label"]),
            Paragraph(f"<b>Disponibles:</b> {res['stock_disponible_unidades']}", estilos["sum_label"]),
            Paragraph(f"<b>Bajo Stock:</b> {res['items_bajo_stock']}", ParagraphStyle('SB', parent=estilos["sum_label"], textColor=colors.HexColor("#D97706"))),
            Paragraph(f"<b>Agotados:</b> {res['items_agotados']}", ParagraphStyle('AG', parent=estilos["sum_val"], textColor=colors.HexColor("#DC2626"))),
        ]
    ]
    t_res = Table(resumen_data, colWidths=[150, 150, 150, 140, 150])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EEF2FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#C7D2FE")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(KeepTogether([t_res]))
    
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


def generar_pdf_reporte_productos_vendidos(token_data: dict, id_sucursal: Optional[int] = None, id_categoria: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    
    datos = reportes_repos.obtener_reporte_productos_vendidos_db(id_empresa_final, id_sucursal_final, id_categoria, f_ini, f_fin)
    empresa_info = reportes_repos.obtener_info_empresa_para_reporte_db(id_empresa_final)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=48
    )
    
    estilos = _obtener_estilos_reporte()
    story = []
    
    filtros = []
    if fecha_inicio and fecha_fin:
        filtros.append(f"{fecha_inicio} al {fecha_fin}")
    else:
        filtros.append("Histórico Completo")
    if id_sucursal_final:
        filtros.append(f"Sucursal #{id_sucursal_final}")
    filtros_txt = " • ".join(filtros)
    
    usuario_nombre = f"{token_data.get('nombre', 'Administrador')} {token_data.get('apellido', '')}".strip()
    _generar_encabezado_reporte(story, empresa_info, "Reporte de Productos Vendidos", filtros_txt, usuario_nombre, estilos)
    
    headers = [
        Paragraph("<b>Producto</b>", estilos["th"]),
        Paragraph("<b>SKU</b>", estilos["th"]),
        Paragraph("<b>Categoría</b>", estilos["th"]),
        Paragraph("<b>Talla/Color</b>", estilos["th"]),
        Paragraph("<b>Unidades</b>", estilos["th"]),
        Paragraph("<b>Precio Prom.</b>", estilos["th"]),
        Paragraph("<b>Subtotal (Bs.)</b>", estilos["th"]),
        Paragraph("<b>Part. %</b>", estilos["th"]),
    ]
    
    table_data = [headers]
    for it in datos["items"]:
        table_data.append([
            Paragraph(str(it["producto"][:24]), estilos["tb"]),
            Paragraph(str(it["sku"]), estilos["tb_center"]),
            Paragraph(str(it["categoria"]), estilos["tb"]),
            Paragraph(f"{it['talla']} - {it['color']}", estilos["tb_center"]),
            Paragraph(str(it["unidades_vendidas"]), estilos["tb_center"]),
            Paragraph(f"Bs. {it['precio_promedio']:,.2f}", estilos["tb_right"]),
            Paragraph(f"Bs. {it['total_ingresos']:,.2f}", estilos["tb_right"]),
            Paragraph(f"{it['participacion_pct']}%", estilos["tb_center"]),
        ])
        
    t_prods = Table(table_data, colWidths=[120, 80, 85, 75, 45, 60, 75, 40], repeatRows=1)
    t_prods.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E1B4B")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_prods)
    story.append(Spacer(1, 14))
    
    res = datos["resumen"]
    resumen_data = [
        [
            Paragraph(f"<b>Modelos Vendidos:</b> {res['total_productos_distintos']}", estilos["sum_label"]),
            Paragraph(f"<b>Unidades Totales:</b> {res['total_unidades_vendidas']}", estilos["sum_label"]),
            Paragraph(f"<b>Total Recaudado:</b> Bs. {res['total_ingresos']:,.2f}", ParagraphStyle('TotIng', parent=estilos["sum_val"], fontSize=10, textColor=colors.HexColor("#1E1B4B")))
        ]
    ]
    t_res = Table(resumen_data, colWidths=[180, 180, 180])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EEF2FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#C7D2FE")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(KeepTogether([t_res]))
    
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


def generar_pdf_reporte_sucursales(token_data: dict, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, _ = _resolver_contexto_tenant(token_data, None, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    
    datos = reportes_repos.obtener_reporte_sucursales_db(id_empresa_final, f_ini, f_fin)
    empresa_info = reportes_repos.obtener_info_empresa_para_reporte_db(id_empresa_final)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=48
    )
    
    estilos = _obtener_estilos_reporte()
    story = []
    
    filtros = []
    if fecha_inicio and fecha_fin:
        filtros.append(f"{fecha_inicio} al {fecha_fin}")
    else:
        filtros.append("Histórico Completo")
    filtros_txt = " • ".join(filtros)
    
    usuario_nombre = f"{token_data.get('nombre', 'Administrador')} {token_data.get('apellido', '')}".strip()
    _generar_encabezado_reporte(story, empresa_info, "Reporte Comparativo de Sucursales", filtros_txt, usuario_nombre, estilos)
    
    headers = [
        Paragraph("<b>Sucursal / Sede</b>", estilos["th"]),
        Paragraph("<b>Ciudad</b>", estilos["th"]),
        Paragraph("<b>Transacciones</b>", estilos["th"]),
        Paragraph("<b>Prendas Vendidas</b>", estilos["th"]),
        Paragraph("<b>Ticket Promedio</b>", estilos["th"]),
        Paragraph("<b>Total Ingresos (Bs.)</b>", estilos["th"]),
        Paragraph("<b>Part. %</b>", estilos["th"]),
    ]
    
    table_data = [headers]
    for it in datos["items"]:
        table_data.append([
            Paragraph(str(it["sucursal"]), estilos["tb"]),
            Paragraph(str(it["ciudad"]), estilos["tb_center"]),
            Paragraph(str(it["cantidad_ventas"]), estilos["tb_center"]),
            Paragraph(str(it["unidades_vendidas"]), estilos["tb_center"]),
            Paragraph(f"Bs. {it['ticket_promedio']:,.2f}", estilos["tb_right"]),
            Paragraph(f"Bs. {it['total_ingresos']:,.2f}", estilos["tb_right"]),
            Paragraph(f"{it['participacion_ingresos_pct']}%", estilos["tb_center"]),
        ])
        
    t_suc = Table(table_data, colWidths=[130, 80, 70, 70, 75, 75, 40], repeatRows=1)
    t_suc.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E1B4B")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_suc)
    story.append(Spacer(1, 14))
    
    res = datos["resumen"]
    resumen_data = [
        [
            Paragraph(f"<b>Sucursales Activas:</b> {res['total_sucursales']}", estilos["sum_label"]),
            Paragraph(f"<b>Ventas Totales:</b> {res['total_ventas']}", estilos["sum_label"]),
            Paragraph(f"<b>Prendas:</b> {res['total_unidades_vendidas']}", estilos["sum_label"]),
            Paragraph(f"<b>Total Recaudado:</b> Bs. {res['total_ingresos']:,.2f}", ParagraphStyle('TotIng', parent=estilos["sum_val"], fontSize=10, textColor=colors.HexColor("#1E1B4B")))
        ]
    ]
    t_res = Table(resumen_data, colWidths=[135, 135, 135, 135])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EEF2FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#C7D2FE")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(KeepTogether([t_res]))
    
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


# ==============================================================================
# EXPORTADORES CSV Y XLSX (CU21W)
# ==============================================================================

from app.modules.pedidos.services.reports.export_utils import exportar_a_csv, exportar_a_xlsx

def generar_csv_reporte_ventas(token_data: dict, id_sucursal: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, estado: Optional[str] = None, id_metodo_pago: Optional[int] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    datos = reportes_repos.obtener_reporte_ventas_db(id_empresa_final, id_sucursal_final, f_ini, f_fin, estado, id_metodo_pago)
    headers = ["N° Venta", "Fecha", "Sucursal", "Cliente", "NIT/CI", "Método Pago", "Subtotal (Bs.)", "Descuento (Bs.)", "Total (Bs.)", "Estado"]
    keys = ["numero_venta", "fecha_formateada", "sucursal_nombre", "cliente_nombre", "nit_ci", "metodo_pago", "subtotal", "descuento", "total", "estado"]
    return exportar_a_csv(headers, keys, datos.get("items", []))

def generar_xlsx_reporte_ventas(token_data: dict, id_sucursal: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, estado: Optional[str] = None, id_metodo_pago: Optional[int] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    datos = reportes_repos.obtener_reporte_ventas_db(id_empresa_final, id_sucursal_final, f_ini, f_fin, estado, id_metodo_pago)
    headers = ["N° Venta", "Fecha", "Sucursal", "Cliente", "NIT/CI", "Método Pago", "Subtotal (Bs.)", "Descuento (Bs.)", "Total (Bs.)", "Estado"]
    keys = ["numero_venta", "fecha_formateada", "sucursal_nombre", "cliente_nombre", "nit_ci", "metodo_pago", "subtotal", "descuento", "total", "estado"]
    tipos = ["string", "date", "string", "string", "string", "string", "currency", "currency", "currency", "badge"]
    return exportar_a_xlsx("Reporte de Ventas", headers, keys, tipos, datos.get("items", []), datos.get("resumen"))

def generar_csv_reporte_inventario(token_data: dict, id_sucursal: Optional[int] = None, id_categoria: Optional[int] = None, estado_stock: Optional[str] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    datos = reportes_repos.obtener_reporte_inventario_db(id_empresa_final, id_sucursal_final, id_categoria, estado_stock)
    headers = ["Prenda / Modelo", "SKU", "Categoría", "Talla", "Color", "Sucursal", "Stock Físico", "Reservado", "Disponible", "Mínimo", "Estado"]
    keys = ["producto", "sku", "categoria", "talla", "color", "sucursal", "stock_actual", "stock_reservado", "stock_disponible", "stock_minimo", "estado_alerta"]
    return exportar_a_csv(headers, keys, datos.get("items", []))

def generar_xlsx_reporte_inventario(token_data: dict, id_sucursal: Optional[int] = None, id_categoria: Optional[int] = None, estado_stock: Optional[str] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    datos = reportes_repos.obtener_reporte_inventario_db(id_empresa_final, id_sucursal_final, id_categoria, estado_stock)
    headers = ["Prenda / Modelo", "SKU", "Categoría", "Talla", "Color", "Sucursal", "Stock Físico", "Reservado", "Disponible", "Mínimo", "Estado"]
    keys = ["producto", "sku", "categoria", "talla", "color", "sucursal", "stock_actual", "stock_reservado", "stock_disponible", "stock_minimo", "estado_alerta"]
    tipos = ["string", "string", "string", "string", "string", "string", "number", "number", "number", "number", "badge"]
    return exportar_a_xlsx("Reporte de Inventario y Stock", headers, keys, tipos, datos.get("items", []), datos.get("resumen"))

def generar_csv_reporte_productos_vendidos(token_data: dict, id_sucursal: Optional[int] = None, id_categoria: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    datos = reportes_repos.obtener_reporte_productos_vendidos_db(id_empresa_final, id_sucursal_final, id_categoria, f_ini, f_fin)
    headers = ["Prenda / Modelo", "SKU", "Categoría", "Talla", "Color", "Sucursal", "Unidades", "Precio (Bs.)", "Recaudación (Bs.)", "Part. %"]
    keys = ["producto", "sku", "categoria", "talla", "color", "sucursal", "unidades_vendidas", "precio_unitario", "subtotal_ingresos", "participacion_ingresos_pct"]
    return exportar_a_csv(headers, keys, datos.get("items", []))

def generar_xlsx_reporte_productos_vendidos(token_data: dict, id_sucursal: Optional[int] = None, id_categoria: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    datos = reportes_repos.obtener_reporte_productos_vendidos_db(id_empresa_final, id_sucursal_final, id_categoria, f_ini, f_fin)
    headers = ["Prenda / Modelo", "SKU", "Categoría", "Talla", "Color", "Sucursal", "Unidades", "Precio (Bs.)", "Recaudación (Bs.)", "Part. %"]
    keys = ["producto", "sku", "categoria", "talla", "color", "sucursal", "unidades_vendidas", "precio_unitario", "subtotal_ingresos", "participacion_ingresos_pct"]
    tipos = ["string", "string", "string", "string", "string", "string", "number", "currency", "currency", "string"]
    return exportar_a_xlsx("Reporte de Productos Vendidos", headers, keys, tipos, datos.get("items", []), datos.get("resumen"))

def generar_csv_reporte_sucursales(token_data: dict, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, _ = _resolver_contexto_tenant(token_data, None, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    datos = reportes_repos.obtener_reporte_sucursales_db(id_empresa_final, f_ini, f_fin)
    headers = ["Sucursal", "Ciudad", "Transacciones", "Prendas", "Ticket Promedio (Bs.)", "Total Ingresos (Bs.)", "Part. %"]
    keys = ["sucursal", "ciudad", "cantidad_ventas", "unidades_vendidas", "ticket_promedio", "total_ingresos", "participacion_ingresos_pct"]
    return exportar_a_csv(headers, keys, datos.get("items", []))

def generar_xlsx_reporte_sucursales(token_data: dict, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, _ = _resolver_contexto_tenant(token_data, None, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    datos = reportes_repos.obtener_reporte_sucursales_db(id_empresa_final, f_ini, f_fin)
    headers = ["Sucursal", "Ciudad", "Transacciones", "Prendas", "Ticket Promedio (Bs.)", "Total Ingresos (Bs.)", "Part. %"]
    keys = ["sucursal", "ciudad", "cantidad_ventas", "unidades_vendidas", "ticket_promedio", "total_ingresos", "participacion_ingresos_pct"]
    tipos = ["string", "string", "number", "number", "currency", "currency", "string"]
    return exportar_a_xlsx("Reporte Comparativo de Sucursales", headers, keys, tipos, datos.get("items", []), datos.get("resumen"))


def generar_pdf_reporte_valoraciones(token_data: dict, id_sucursal: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, puntuacion: Optional[int] = None, requiere_revision: Optional[bool] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    from app.modules.pedidos.services.reports.engine.report_engine import ejecutar_reporte_dinamico, generar_pdf_reporte_dinamico
    req = {
        "tipo_reporte": "valoraciones",
        "filtros": {
            "sucursalId": id_sucursal,
            "fechaDesde": fecha_inicio,
            "fechaHasta": fecha_fin,
            "puntuacion": puntuacion,
            "requiereRevision": requiere_revision
        }
    }
    token_mod = {**token_data, '_empresa_reporte': id_empresa} if id_empresa else token_data
    datos = ejecutar_reporte_dinamico(req, token_mod)
    return generar_pdf_reporte_dinamico(datos, token_mod)


def generar_csv_reporte_valoraciones(token_data: dict, id_sucursal: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, puntuacion: Optional[int] = None, requiere_revision: Optional[bool] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    datos = reportes_repos.obtener_reporte_valoraciones_db(id_empresa_final, id_sucursal_final, f_ini, f_fin, puntuacion, requiere_revision)
    headers = ["Fecha", "Cliente", "Prenda / Concepto", "Categoría", "Sucursal", "Estrellas (1-5)", "N° Referencia", "Motivo Observación", "Comentario", "Satisfacción"]
    keys = ["fecha", "cliente", "producto", "categoria", "sucursal", "puntuacion", "codigo_referencia", "motivo_negativo", "comentario", "estado_satisfaccion"]
    return exportar_a_csv(headers, keys, datos.get("items", []))


def generar_xlsx_reporte_valoraciones(token_data: dict, id_sucursal: Optional[int] = None, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, puntuacion: Optional[int] = None, requiere_revision: Optional[bool] = None, id_empresa: Optional[int] = None) -> io.BytesIO:
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    datos = reportes_repos.obtener_reporte_valoraciones_db(id_empresa_final, id_sucursal_final, f_ini, f_fin, puntuacion, requiere_revision)
    headers = ["Fecha", "Cliente", "Prenda / Concepto", "Categoría", "Sucursal", "Estrellas (1-5)", "N° Referencia", "Motivo Observación", "Comentario", "Satisfacción"]
    keys = ["fecha", "cliente", "producto", "categoria", "sucursal", "puntuacion", "codigo_referencia", "motivo_negativo", "comentario", "estado_satisfaccion"]
    tipos = ["date", "string", "string", "string", "string", "number", "string", "string", "string", "badge"]
    return exportar_a_xlsx("Reporte de Valoraciones y Calidad", headers, keys, tipos, datos.get("items", []), datos.get("resumen"))


