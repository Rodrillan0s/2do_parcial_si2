import re
from datetime import datetime, timedelta
import calendar
from typing import Tuple, Optional
from app.modules.pedidos.services.reports.parser.normalizer import eliminar_tildes

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

def interpretar_fechas(texto: str) -> Tuple[Optional[str], Optional[str], str]:
    """
    Identifica expresiones de fecha en el texto mediante reglas deterministas.
    Retorna: (fecha_desde_str, fecha_hasta_str, texto_restante)
    Las fechas están en formato 'YYYY-MM-DD'.
    """
    t = eliminar_tildes(texto.lower().strip())
    ahora = datetime.now()
    hoy_str = ahora.strftime('%Y-%m-%d')
    
    fecha_desde = None
    fecha_hasta = None
    texto_restante = t

    # 1. "hoy"
    if re.search(r'\bhoy\b', t):
        fecha_desde = hoy_str
        fecha_hasta = hoy_str
        texto_restante = re.sub(r'\bhoy\b', ' ', texto_restante)

    # 2. "ayer"
    elif re.search(r'\bayer\b', t):
        ayer = (ahora - timedelta(days=1)).strftime('%Y-%m-%d')
        fecha_desde = ayer
        fecha_hasta = ayer
        texto_restante = re.sub(r'\bayer\b', ' ', texto_restante)

    # 3. "ultimos (\d+) dias"
    elif re.search(r'\bultimos?\s+(\d+)\s+dias?\b', t):
        m = re.search(r'\bultimos?\s+(\d+)\s+dias?\b', t)
        dias = int(m.group(1))
        d_desde = (ahora - timedelta(days=dias)).strftime('%Y-%m-%d')
        fecha_desde = d_desde
        fecha_hasta = hoy_str
        texto_restante = re.sub(r'\bultimos?\s+(\d+)\s+dias?\b', ' ', texto_restante)

    # 4. "esta semana"
    elif re.search(r'\besta\s+semana\b', t):
        inicio_semana = ahora - timedelta(days=ahora.weekday())
        fecha_desde = inicio_semana.strftime('%Y-%m-%d')
        fecha_hasta = hoy_str
        texto_restante = re.sub(r'\besta\s+semana\b', ' ', texto_restante)

    # 5. "semana pasada"
    elif re.search(r'\bsemana\s+pasada\b', t):
        lunes_esta = ahora - timedelta(days=ahora.weekday())
        domingo_pasada = lunes_esta - timedelta(days=1)
        lunes_pasada = domingo_pasada - timedelta(days=6)
        fecha_desde = lunes_pasada.strftime('%Y-%m-%d')
        fecha_hasta = domingo_pasada.strftime('%Y-%m-%d')
        texto_restante = re.sub(r'\bsemana\s+pasada\b', ' ', texto_restante)

    # 6. "este mes"
    elif re.search(r'\beste\s+mes\b', t):
        inicio_mes = ahora.replace(day=1)
        fecha_desde = inicio_mes.strftime('%Y-%m-%d')
        fecha_hasta = hoy_str
        texto_restante = re.sub(r'\beste\s+mes\b', ' ', texto_restante)

    # 7. "mes pasado"
    elif re.search(r'\bmes\s+pasado\b', t):
        primer_dia_este_mes = ahora.replace(day=1)
        ultimo_dia_mes_pasado = primer_dia_este_mes - timedelta(days=1)
        primer_dia_mes_pasado = ultimo_dia_mes_pasado.replace(day=1)
        fecha_desde = primer_dia_mes_pasado.strftime('%Y-%m-%d')
        fecha_hasta = ultimo_dia_mes_pasado.strftime('%Y-%m-%d')
        texto_restante = re.sub(r'\bmes\s+pasado\b', ' ', texto_restante)

    # 8. "este ano" / "ano en curso"
    elif re.search(r'\b(?:este\s+a[nñ]o|a[nñ]o\s+en\s+curso)\b', t):
        fecha_desde = f"{ahora.year}-01-01"
        fecha_hasta = hoy_str
        texto_restante = re.sub(r'\b(?:este\s+a[nñ]o|a[nñ]o\s+en\s+curso)\b', ' ', texto_restante)

    # 9. "ano pasado"
    elif re.search(r'\ba[nñ]o\s+pasado\b', t):
        anio_prev = ahora.year - 1
        fecha_desde = f"{anio_prev}-01-01"
        fecha_hasta = f"{anio_prev}-12-31"
        texto_restante = re.sub(r'\ba[nñ]o\s+pasado\b', ' ', texto_restante)

    # 10. Trimestres (Q1, Q2, Q3, Q4)
    elif re.search(r'\b(?:primer\s+trimestre|1er\s+trimestre|q1)\b', t):
        fecha_desde = f"{ahora.year}-01-01"
        fecha_hasta = f"{ahora.year}-03-31"
        texto_restante = re.sub(r'\b(?:primer\s+trimestre|1er\s+trimestre|q1)\b', ' ', texto_restante)
    elif re.search(r'\b(?:segundo\s+trimestre|2do\s+trimestre|q2)\b', t):
        fecha_desde = f"{ahora.year}-04-01"
        fecha_hasta = f"{ahora.year}-06-30"
        texto_restante = re.sub(r'\b(?:segundo\s+trimestre|2do\s+trimestre|q2)\b', ' ', texto_restante)
    elif re.search(r'\b(?:tercer\s+trimestre|3er\s+trimestre|q3)\b', t):
        fecha_desde = f"{ahora.year}-07-01"
        fecha_hasta = f"{ahora.year}-09-30"
        texto_restante = re.sub(r'\b(?:tercer\s+trimestre|3er\s+trimestre|q3)\b', ' ', texto_restante)
    elif re.search(r'\b(?:cuarto\s+trimestre|4to\s+trimestre|q4)\b', t):
        fecha_desde = f"{ahora.year}-10-01"
        fecha_hasta = f"{ahora.year}-12-31"
        texto_restante = re.sub(r'\b(?:cuarto\s+trimestre|4to\s+trimestre|q4)\b', ' ', texto_restante)
    elif re.search(r'\b(?:ultimo\s+trimestre|ultimos\s+3\s+meses)\b', t):
        fecha_desde = (ahora - timedelta(days=90)).strftime('%Y-%m-%d')
        fecha_hasta = hoy_str
        texto_restante = re.sub(r'\b(?:ultimo\s+trimestre|ultimos\s+3\s+meses)\b', ' ', texto_restante)

    # 11. "en [mes] [de anio]" o "del mes de [mes]"
    match_mes = re.search(r'\b(?:en\s+|de\s+|del\s+mes\s+de\s+)([a-z]+)(?:\s+de\s+(\d{4}))?\b', t)
    if match_mes and match_mes.group(1) in MESES:
        m_num = MESES[match_mes.group(1)]
        y_val = int(match_mes.group(2)) if match_mes.group(2) else ahora.year
        _, last_day = calendar.monthrange(y_val, m_num)
        fecha_desde = f"{y_val:04d}-{m_num:02d}-01"
        fecha_hasta = f"{y_val:04d}-{m_num:02d}-{last_day:02d}"
        texto_restante = texto_restante.replace(match_mes.group(0), ' ')

    # 12. Rangos explícitos: "del 1 al 15 [de mes] [de año]"
    match_rango_dias = re.search(r'\b(?:del|desde)\s+(\d{1,2})\s+(?:al|hasta)\s+(\d{1,2})(?:\s+de\s+([a-z]+))?(?:\s+de\s+(\d{4}))?\b', t)
    if match_rango_dias:
        d1 = int(match_rango_dias.group(1))
        d2 = int(match_rango_dias.group(2))
        mes_nom = match_rango_dias.group(3)
        anio_str = match_rango_dias.group(4)
        
        mes = MESES.get(mes_nom, ahora.month) if mes_nom else ahora.month
        anio = int(anio_str) if anio_str else ahora.year
        
        try:
            f1 = datetime(anio, mes, d1).strftime('%Y-%m-%d')
            f2 = datetime(anio, mes, d2).strftime('%Y-%m-%d')
            fecha_desde = f1
            fecha_hasta = f2
            texto_restante = texto_restante.replace(match_rango_dias.group(0), ' ')
        except Exception:
            pass

    # 13. Fechas ISO explícitas: YYYY-MM-DD
    fechas_iso = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', t)
    if len(fechas_iso) >= 2:
        fecha_desde = fechas_iso[0]
        fecha_hasta = fechas_iso[1]
        for f in fechas_iso[:2]:
            texto_restante = texto_restante.replace(f, ' ')
    elif len(fechas_iso) == 1:
        fecha_desde = fechas_iso[0]
        fecha_hasta = fechas_iso[0]
        texto_restante = texto_restante.replace(fechas_iso[0], ' ')

    texto_restante = re.sub(r'\s+', ' ', texto_restante).strip()
    return fecha_desde, fecha_hasta, texto_restante
