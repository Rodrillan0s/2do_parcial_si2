import io
import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfgen import canvas

from app.core.postgres import PostgreSQL
from app.modules.pedidos.services.reports.engine.catalog import CATALOGO_REPORTES, resolver_alias_reporte
from app.modules.pedidos.services.reports.engine.query_builder import construir_consulta_reporte
from app.modules.pedidos.repos import reportes_repos
# ==============================================================================
# ESTILOS REPORTLAB PARA MOTOR DINÁMICO
# ==============================================================================

class NumberedCanvas(canvas.Canvas):
    """Agrega pie de página corporativo con numeración 'Página X de Y'."""
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
        
        # Línea divisoria pie de página
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 30, self._pagesize[0] - 36, 30)
        
        # Textos pie de página
        self.drawString(36, 18, "Aurora Store — Sistema de Gestión Comercial Multi-Tenant • Motor de Reportes Dinámico")
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(self._pagesize[0] - 36, 18, page_str)
        self.restoreState()


def _obtener_estilos_motor():
    styles = getSampleStyleSheet()
    azul_primario = colors.HexColor("#1E1B4B")
    gris_oscuro = colors.HexColor("#1E293B")
    gris_medio = colors.HexColor("#64748B")

    return {
        "title": ParagraphStyle(
            'MRepTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=15,
            leading=19,
            textColor=azul_primario,
            alignment=TA_LEFT
        ),
        "subtitle": ParagraphStyle(
            'MRepSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11,
            textColor=gris_medio,
            alignment=TA_LEFT
        ),
        "meta_label": ParagraphStyle(
            'MMetaLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=azul_primario
        ),
        "meta_val": ParagraphStyle(
            'MMetaVal',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=gris_oscuro
        ),
        "th": ParagraphStyle(
            'MTh',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            alignment=TA_CENTER
        ),
        "tb": ParagraphStyle(
            'MTb',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9.5,
            textColor=gris_oscuro,
            alignment=TA_LEFT
        ),
        "tb_center": ParagraphStyle(
            'MTbCenter',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9.5,
            textColor=gris_oscuro,
            alignment=TA_CENTER
        ),
        "tb_right": ParagraphStyle(
            'MTbRight',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9.5,
            textColor=gris_oscuro,
            alignment=TA_RIGHT
        ),
        "sum_label": ParagraphStyle(
            'MSumLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=azul_primario,
            alignment=TA_RIGHT
        ),
        "sum_val": ParagraphStyle(
            'MSumVal',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#0D9488"),
            alignment=TA_RIGHT
        )
    }


def _resolver_contexto_tenant(token_data: Dict[str, Any]) -> Tuple[int, Optional[List[int]]]:
    """Extrae el id_empresa inviolable del token y calcula restricciones de sucursal."""
    from app.core.tenant_guard import resolver_tenant_operacion, obtener_alcance_usuario, obtener_sucursales_autorizadas
    id_empresa = resolver_tenant_operacion(token_data, token_data.get('_empresa_reporte'))
    sucursales = obtener_sucursales_autorizadas(token_data) if obtener_alcance_usuario(token_data) == 'SUCURSAL' else None
    return id_empresa, sucursales


def _serializar_valor(val: Any) -> Any:
    """Convierte tipos no nativos de JSON como Decimals y Fechas a formatos estándar."""
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    return val


# ==============================================================================
# MOTOR DE EJECUCIÓN DINÁMICA
# ==============================================================================

def ejecutar_reporte_dinamico(
    request: Dict[str, Any],
    token_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Ejecuta una solicitud canónica de reporte (ReportRequest) contra las vistas PostgreSQL.
    Aplica multi-tenancy, permisos y calcula resúmenes numéricos.
    """
    tipo_reporte = request.get("tipo_reporte") or request.get("reporte")
    tipo_reporte = resolver_alias_reporte(tipo_reporte)
    if not tipo_reporte or tipo_reporte not in CATALOGO_REPORTES:
        raise ValueError(f"Tipo de reporte '{tipo_reporte}' no reconocido en el catálogo.")

    definicion = CATALOGO_REPORTES[tipo_reporte]
    id_empresa, sucursales_permitidas = _resolver_contexto_tenant(token_data)

    sql, params, columnas_meta = construir_consulta_reporte(
        definicion=definicion,
        request=request,
        id_empresa=id_empresa,
        sucursales_permitidas=sucursales_permitidas
    )

    db = PostgreSQL()
    db.create_connection()
    try:
        raw_rows = db.execute_query(sql, params, fetchall=True) or []
        col_names = [desc[0] for desc in db.cur.description] if db.cur and db.cur.description else []
    finally:
        db.close_connection()

    # Limpiar y normalizar filas
    filas = []
    campo_monto = definicion.get("campo_monto", "total")
    monto_acumulado = Decimal("0.0")
    tiene_montos = False

    # En caso de agrupamiento, el campo_monto agrupado se llama 'total_monto'
    if request.get("groupBy"):
        campo_monto = "total_monto"

    for r in raw_rows:
        fila_dict = {}
        if isinstance(r, dict):
            items_iter = r.items()
        else:
            items_iter = [(col_names[i], r[i]) for i in range(min(len(col_names), len(r)))]

        for k, v in items_iter:
            fila_dict[k] = _serializar_valor(v)
            if k == campo_monto and v is not None:
                try:
                    monto_acumulado += Decimal(str(v))
                    tiene_montos = True
                except:
                    pass
        filas.append(fila_dict)

    total_registros = len(filas)
    total_monto_float = float(monto_acumulado) if tiene_montos else 0.0
    promedio_float = round(total_monto_float / total_registros, 2) if total_registros > 0 else 0.0

    resumen = {
        "total_registros": total_registros,
        "total_monto": total_monto_float,
        "promedio_monto": promedio_float,
        "campo_monto_usado": campo_monto
    }

    return {
        "tipo_reporte": tipo_reporte,
        "codigo": definicion["codigo"],
        "nombre": definicion["nombre"],
        "descripcion": definicion["descripcion"],
        "columnas": columnas_meta,
        "items": filas,
        "resumen": resumen,
        "filtros_aplicados": request.get("filtros") or {},
        "groupBy": request.get("groupBy"),
        "orderBy": request.get("orderBy"),
        "orderDirection": request.get("orderDirection", "DESC")
    }


# ==============================================================================
# GENERACIÓN DE PDF DINÁMICO
# ==============================================================================

def generar_pdf_reporte_dinamico(
    datos_reporte: Dict[str, Any],
    token_data: Dict[str, Any]
) -> io.BytesIO:
    """
    Genera un archivo PDF profesional en base a cualquier reporte dinámico del motor.
    Ajusta dinámicamente orientación horizontal (landscape) y anchos de columnas.
    """
    id_empresa, _ = _resolver_contexto_tenant(token_data)
    empresa_info = reportes_repos.obtener_info_empresa_para_reporte_db(id_empresa)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=44
    )

    estilos = _obtener_estilos_motor()
    story = []

    # 1. Cabecera Corporativa
    emp_nombre = empresa_info.get("nombre", "Aurora Store S.R.L.")
    emp_nit = empresa_info.get("nit", "1028492031")
    emp_dir = empresa_info.get("direccion", "Santa Cruz, Bolivia")
    emp_tel = empresa_info.get("telefono", "+591 3 3456789")

    usuario_nombre = f"{token_data.get('nombre', 'Administrador')} {token_data.get('apellido', '')}".strip()
    fecha_emision = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Tabla Header
    header_data = [
        [
            Paragraph(f"<b>{emp_nombre}</b><br/>NIT: {emp_nit}<br/>{emp_dir}<br/>Tel: {emp_tel}", estilos["subtitle"]),
            Paragraph(
                f"<b>{datos_reporte.get('nombre', 'Reporte')}</b><br/>"
                f"<font color='#64748B'>{datos_reporte.get('descripcion', '')}</font>",
                estilos["title"]
            ),
            Paragraph(
                f"<b>Fecha de emisión:</b><br/>{fecha_emision}<br/>"
                f"<b>Generado por:</b><br/>{usuario_nombre}",
                estilos["meta_val"]
            )
        ]
    ]

    header_table = Table(header_data, colWidths=[200, 360, 160])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(header_table)

    # 2. Resumen de Filtros Aplicados
    filtros_aplicados = datos_reporte.get("filtros_aplicados", {})
    filtros_txt_list = []
    if filtros_aplicados.get("fechaDesde") and filtros_aplicados.get("fechaHasta"):
        filtros_txt_list.append(f"Período: {filtros_aplicados['fechaDesde']} al {filtros_aplicados['fechaHasta']}")
    elif filtros_aplicados.get("fechaDesde"):
        filtros_txt_list.append(f"Desde: {filtros_aplicados['fechaDesde']}")
    elif filtros_aplicados.get("fechaHasta"):
        filtros_txt_list.append(f"Hasta: {filtros_aplicados['fechaHasta']}")

    if filtros_aplicados.get("sucursalId"):
        filtros_txt_list.append(f"Sucursal ID: {filtros_aplicados['sucursalId']}")
    if filtros_aplicados.get("categoriaId"):
        filtros_txt_list.append(f"Categoría ID: {filtros_aplicados['categoriaId']}")
    if filtros_aplicados.get("estado"):
        filtros_txt_list.append(f"Estado: {filtros_aplicados['estado']}")
    if datos_reporte.get("groupBy"):
        filtros_txt_list.append(f"Agrupado por: {datos_reporte['groupBy'].capitalize()}")

    filtros_badge_txt = " • ".join(filtros_txt_list) if filtros_txt_list else "Todos los registros (sin filtros restrictivos)"

    filtro_table = Table([[Paragraph(f"<b>Parámetros de consulta:</b> {filtros_badge_txt}", estilos["subtitle"])]], colWidths=[720])
    filtro_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
    ]))
    story.append(filtro_table)
    story.append(Spacer(1, 10))

    # 3. Tabla de Datos
    columnas = datos_reporte.get("columnas", [])
    items = datos_reporte.get("items", [])
    num_cols = len(columnas) if columnas else 1

    # Distribución equitativa o inteligente de ancho para página horizontal (720 pt útiles)
    ancho_disponible = 720
    ancho_por_col = max(ancho_disponible / num_cols, 45)
    col_widths = [ancho_por_col] * num_cols

    # Headers
    table_data = [[Paragraph(f"<b>{c.get('titulo', c['campo'])}</b>", estilos["th"]) for c in columnas]]

    for it in items:
        row = []
        for c in columnas:
            k = c["campo"]
            tipo = c.get("tipo", "string")
            val = it.get(k, "")
            
            if val is None:
                val_str = "-"
            elif tipo == "currency":
                try:
                    val_str = f"Bs. {float(val):,.2f}"
                except:
                    val_str = str(val)
            elif tipo == "number":
                try:
                    val_str = f"{int(val):,}" if float(val).is_integer() else f"{float(val):,.2f}"
                except:
                    val_str = str(val)
            else:
                val_str = str(val)

            # Estilo según tipo
            if tipo == "currency" or tipo == "number":
                row.append(Paragraph(val_str, estilos["tb_right"]))
            elif tipo in ["date", "badge"]:
                row.append(Paragraph(val_str, estilos["tb_center"]))
            else:
                row.append(Paragraph(val_str[:30], estilos["tb"]))
        table_data.append(row)

    if not items:
        # Fila vacía
        table_data.append([Paragraph("<i>No se encontraron registros para los filtros seleccionados.</i>", estilos["tb_center"])] * num_cols)

    t_reporte = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_reporte.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E1B4B")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_reporte)
    story.append(Spacer(1, 10))

    # 4. Cuadro Resumen al pie
    resumen = datos_reporte.get("resumen", {})
    tot_reg = resumen.get("total_registros", len(items))
    tot_monto = resumen.get("total_monto", 0.0)
    prom_monto = resumen.get("promedio_monto", 0.0)

    resumen_data = [
        [
            Paragraph(f"<b>Total Filas / Registros:</b> {tot_reg}", estilos["sum_label"]),
            Paragraph(f"<b>Monto Total Consolidado:</b> Bs. {tot_monto:,.2f}", estilos["sum_val"]),
            Paragraph(f"<b>Promedio:</b> Bs. {prom_monto:,.2f}", estilos["sum_label"]),
        ]
    ]
    t_resumen = Table(resumen_data, colWidths=[240, 240, 240])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_resumen)

    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


def generar_csv_reporte_dinamico(datos_reporte: Dict[str, Any]) -> io.BytesIO:
    """Exporta el reporte dinámico a CSV con codificación UTF-8 BOM."""
    from app.modules.pedidos.services.reports.export_utils import exportar_a_csv
    columnas = datos_reporte.get("columnas", [])
    headers = [c.get("titulo", c.get("campo", "")) for c in columnas]
    keys = [c.get("campo", "") for c in columnas]
    filas = datos_reporte.get("filas", [])
    return exportar_a_csv(headers, keys, filas)


def generar_xlsx_reporte_dinamico(datos_reporte: Dict[str, Any]) -> io.BytesIO:
    """Exporta el reporte dinámico a XLSX con formato institucional y resumen."""
    from app.modules.pedidos.services.reports.export_utils import exportar_a_xlsx
    columnas = datos_reporte.get("columnas", [])
    headers = [c.get("titulo", c.get("campo", "")) for c in columnas]
    keys = [c.get("campo", "") for c in columnas]
    tipos = [c.get("tipo", "string") for c in columnas]
    filas = datos_reporte.get("filas", [])
    resumen = datos_reporte.get("resumen", {})
    reporte_nombre = datos_reporte.get("reporte", {}).get("nombre", "Reporte Dinámico")
    return exportar_a_xlsx(reporte_nombre, headers, keys, tipos, filas, resumen)

