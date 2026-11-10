import csv
import io
from typing import List, Dict, Any, Optional
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def exportar_a_csv(headers: List[str], keys: List[str], filas: List[Dict[str, Any]]) -> io.BytesIO:
    """
    Genera un archivo CSV codificado con UTF-8 BOM (utf-8-sig) para compatibilidad
    nativa con Microsoft Excel, Google Sheets y software contable.
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for fila in filas:
        row_vals = []
        for k in keys:
            val = fila.get(k, '')
            if val is None:
                val = ''
            elif isinstance(val, (float, Decimal)):
                val = f"{float(val):.2f}"
            row_vals.append(str(val))
        writer.writerow(row_vals)
    
    bytes_io = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    bytes_io.seek(0)
    return bytes_io

def exportar_a_xlsx(
    titulo: str,
    headers: List[str],
    keys: List[str],
    tipos: List[str],
    filas: List[Dict[str, Any]],
    resumen: Optional[Dict[str, Any]] = None
) -> io.BytesIO:
    """
    Genera un libro XLSX con diseño corporativo elegante: cabecera oscura institucional,
    celdas tipadas, zebra-striping y anchos automáticos.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = (titulo[:28] if titulo else "Reporte").replace("/", "-")
    ws.views.sheetView[0].showGridLines = True

    # 1. Título corporativo en la primera fila
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title_cell = ws.cell(row=1, column=1, value=f"AURORASTORE • {titulo.upper()}")
    title_cell.font = Font(name="Calibri", size=14, bold=True, color="1E1B4B")
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    # 2. Encabezados de columnas
    header_fill = PatternFill(start_color="1E1B4B", end_color="1E1B4B", fill_type="solid")
    header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    ws.row_dimensions[3].height = 24
    for col_idx, header_text in enumerate(headers, start=1):
        cell = ws.cell(row=3, column=col_idx, value=header_text)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # 3. Filas de datos
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    data_font = Font(name="Calibri", size=10, color="1E293B")

    current_row = 4
    for r_idx, fila in enumerate(filas):
        fill_to_use = zebra_fill if (r_idx % 2 == 1) else white_fill
        ws.row_dimensions[current_row].height = 20

        for c_idx, key in enumerate(keys, start=1):
            tipo = tipos[c_idx - 1] if c_idx - 1 < len(tipos) else "string"
            val = fila.get(key)
            cell = ws.cell(row=current_row, column=c_idx)
            cell.font = data_font
            cell.fill = fill_to_use
            cell.border = thin_border

            if val is None:
                cell.value = ""
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif tipo == "currency":
                try:
                    cell.value = float(val)
                    cell.number_format = '"Bs. "#,##0.00'
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                except (ValueError, TypeError):
                    cell.value = str(val)
                    cell.alignment = Alignment(horizontal="right", vertical="center")
            elif tipo == "number":
                try:
                    cell.value = float(val) if '.' in str(val) else int(val)
                    cell.number_format = '#,##0'
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                except (ValueError, TypeError):
                    cell.value = str(val)
                    cell.alignment = Alignment(horizontal="right", vertical="center")
            elif tipo == "date":
                cell.value = str(val)
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif tipo == "badge":
                cell.value = str(val)
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.value = str(val)
                cell.alignment = Alignment(horizontal="left", vertical="center")

        current_row += 1

    # 4. Resumen al pie si está disponible
    if resumen:
        current_row += 1
        ws.row_dimensions[current_row].height = 22
        summary_font = Font(name="Calibri", size=10, bold=True, color="1E1B4B")
        summary_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        
        col_offset = 1
        for k, v in resumen.items():
            if col_offset <= len(headers):
                c = ws.cell(row=current_row, column=col_offset, value=f"{k.replace('_', ' ').capitalize()}: {v}")
                c.font = summary_font
                c.fill = summary_fill
                c.border = thin_border
                col_offset += 1

    # 5. Ajuste dinámico de anchos de columna
    for col_idx in range(1, len(headers) + 1):
        col_letter = get_column_letter(col_idx)
        max_len = len(str(headers[col_idx - 1]))
        for row in range(4, min(current_row, 100)):
            cell_val = ws.cell(row=row, column=col_idx).value
            if cell_val is not None:
                max_len = max(max_len, len(str(cell_val)))
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 40)

    bytes_io = io.BytesIO()
    wb.save(bytes_io)
    bytes_io.seek(0)
    return bytes_io
