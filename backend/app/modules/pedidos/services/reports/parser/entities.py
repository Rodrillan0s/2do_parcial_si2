import re
from typing import Dict, Any, List, Optional
from app.core.postgres import PostgreSQL
from app.core.config import Config
from app.modules.pedidos.services.reports.parser.normalizer import eliminar_tildes

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

def buscar_sucursal_por_termino(termino: str, id_empresa: int) -> List[Dict[str, Any]]:
    """Busca sucursales activas en la empresa cuyo nombre coincida parcialmente."""
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT s.id_sucursal, s.nombre, COALESCE(c.nombre, '') as ciudad
            FROM {schema}.t_sucursal s
            LEFT JOIN {schema}.t_ciudad c ON c.id_ciudad = s.id_ciudad
            WHERE s.id_empresa = %s AND s.activo = TRUE
              AND LOWER(s.nombre) LIKE LOWER(%s)
            LIMIT 5;
        """
        rows = db.execute_query(q, (id_empresa, f"%{termino}%"), fetchall=True) or []
        return [{
            "tipo": "sucursal",
            "id": r[0],
            "nombre": r[1],
            "detalle": r[2]
        } for r in rows]
    finally:
        db.close_connection()


def buscar_categoria_por_termino(termino: str) -> List[Dict[str, Any]]:
    """Busca categorías activas cuyo nombre coincida parcialmente."""
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT id_categoria, nombre
            FROM {schema}.t_categoria
            WHERE estado = TRUE AND LOWER(nombre) LIKE LOWER(%s)
            LIMIT 5;
        """
        rows = db.execute_query(q, (f"%{termino}%",), fetchall=True) or []
        return [{
            "tipo": "categoria",
            "id": r[0],
            "nombre": r[1],
            "detalle": "Categoría de Prendas"
        } for r in rows]
    finally:
        db.close_connection()


def buscar_producto_por_termino(termino: str, id_empresa: Optional[int] = None) -> List[Dict[str, Any]]:
    """Busca prendas/productos en catálogo cuyo nombre o código coincida."""
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        where = ["p.activo = TRUE", "(LOWER(p.nombre) LIKE LOWER(%s) OR LOWER(p.codigo_producto) LIKE LOWER(%s))"]
        params = [f"%{termino}%", f"%{termino}%"]
        if id_empresa:
            where.append("(p.id_empresa = %s OR p.id_empresa IS NULL)")
            params.append(id_empresa)

        where_sql = " AND ".join(where)
        q = f"""
            SELECT p.id_producto, p.nombre, COALESCE(c.nombre, 'Sin Categoría') as cat
            FROM {schema}.t_producto p
            LEFT JOIN {schema}.t_categoria c ON c.id_categoria = p.id_categoria
            WHERE {where_sql}
            LIMIT 5;
        """
        rows = db.execute_query(q, tuple(params), fetchall=True) or []
        return [{
            "tipo": "producto",
            "id": r[0],
            "nombre": r[1],
            "detalle": f"Modelo: {r[2]}"
        } for r in rows]
    finally:
        db.close_connection()


def buscar_metodo_pago_por_termino(termino: str) -> Optional[Dict[str, Any]]:
    """Identifica métodos de pago por nombre (efectivo, tarjeta, qr, paypal, etc.)."""
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            SELECT id_metodo_pago, nombre
            FROM {schema}.t_metodo_pago
            WHERE estado = TRUE AND LOWER(nombre) LIKE LOWER(%s)
            LIMIT 1;
        """
        row = db.execute_query(q, (f"%{termino}%",), fetchone=True)
        if row:
            return {"tipo": "metodo_pago", "id": row[0], "nombre": row[1]}
        return None
    finally:
        db.close_connection()


def resolver_entidades_en_texto(texto: str, id_empresa: int):
    """
    Analiza las palabras y frases del texto contra PostgreSQL para resolver entidades.
    Detecta sucursales, categorías, productos, estados y métodos de pago.
    Si una entidad es ambigua (coincide en múltiples categorías o con producto y categoría),
    construye un objeto de ambigüedad para que el usuario elija.
    """
    t = eliminar_tildes(texto.lower().strip())
    
    entidades_resueltas = {
        "sucursal_id": None,
        "sucursal_nombre": None,
        "categoria_id": None,
        "categoria_nombre": None,
        "producto_id": None,
        "producto_nombre": None,
        "metodo_pago_id": None,
        "metodo_pago_nombre": None,
        "estado_venta": None,
        "estado_stock": None
    }
    
    ambiguedades = []
    texto_consumido = t

    # 1. Detección de estados fijos
    if re.search(r'\b(agotad[oa]s?|sin stock|cero stock)\b', t):
        entidades_resueltas["estado_stock"] = "agotado"
        texto_consumido = re.sub(r'\b(agotad[oa]s?|sin stock|cero stock)\b', ' ', texto_consumido)
    elif re.search(r'\b(bajo stock|poc[oa] stock|escas[oa]s?|minimo)\b', t):
        entidades_resueltas["estado_stock"] = "bajo"
        texto_consumido = re.sub(r'\b(bajo stock|poc[oa] stock|escas[oa]s?|minimo)\b', ' ', texto_consumido)
        
    if re.search(r'\b(anulad[oa]s?|cancelad[oa]s?)\b', t):
        entidades_resueltas["estado_venta"] = "ANULADA"
        texto_consumido = re.sub(r'\b(anulad[oa]s?|cancelad[oa]s?)\b', ' ', texto_consumido)
    elif re.search(r'\b(completad[oa]s?|pagad[oa]s?|exitos[oa]s?)\b', t):
        entidades_resueltas["estado_venta"] = "COMPLETADA"
        texto_consumido = re.sub(r'\b(completad[oa]s?|pagad[oa]s?|exitos[oa]s?)\b', ' ', texto_consumido)
    elif re.search(r'\b(pendientes?|en espera)\b', t):
        entidades_resueltas["estado_venta"] = "PENDIENTE"
        texto_consumido = re.sub(r'\b(pendientes?|en espera)\b', ' ', texto_consumido)

    # 2. Extracción de posibles nombres tras palabras clave:
    # "sucursal <nombre>", "tienda <nombre>", "sede <nombre>"
    match_suc = re.search(r'\b(?:sucursal|tienda|sede)\s+([a-z0-9\s]+?)(?:\s+(?:por|de|en|del|con)\b|$)', t)
    termino_sucursal = match_suc.group(1).strip() if match_suc else None
    
    if termino_sucursal and len(termino_sucursal) >= 3:
        coincidencias = buscar_sucursal_por_termino(termino_sucursal, id_empresa)
        if len(coincidencias) == 1:
            entidades_resueltas["sucursal_id"] = coincidencias[0]["id"]
            entidades_resueltas["sucursal_nombre"] = coincidencias[0]["nombre"]
            texto_consumido = texto_consumido.replace(termino_sucursal, ' ')
        elif len(coincidencias) > 1:
            ambiguedades.append({
                "pregunta": f"¿A qué sucursal te refieres con '{termino_sucursal}'?",
                "termino": termino_sucursal,
                "opciones": coincidencias
            })

    # Si no hubo palabra clave explícita de sucursal, verificar palabras del texto contra sucursales conocidas
    if not entidades_resueltas["sucursal_id"] and not ambiguedades:
        palabras = [p for p in texto_consumido.split() if len(p) >= 4]
        for p in palabras:
            coincidencias_suc = buscar_sucursal_por_termino(p, id_empresa)
            if len(coincidencias_suc) == 1:
                entidades_resueltas["sucursal_id"] = coincidencias_suc[0]["id"]
                entidades_resueltas["sucursal_nombre"] = coincidencias_suc[0]["nombre"]
                texto_consumido = texto_consumido.replace(p, ' ')
                break

    # 3. Métodos de pago
    for mp_term in ["efectivo", "tarjeta", "qr", "transferencia", "paypal"]:
        if re.search(r'\b' + mp_term + r'\b', t):
            mp_res = buscar_metodo_pago_por_termino(mp_term)
            if mp_res:
                entidades_resueltas["metodo_pago_id"] = mp_res["id"]
                entidades_resueltas["metodo_pago_nombre"] = mp_res["nombre"]
                texto_consumido = re.sub(r'\b' + mp_term + r'\b', ' ', texto_consumido)
                break

    # 4. Detección de Categoría / Producto y Ambigüedades
    # Extraer términos significativos restantes
    palabras_restantes = [p for p in texto_consumido.split() if len(p) >= 4 and p not in ["ventas", "venta", "inventario", "stock", "productos", "sucursal", "sucursales"]]
    
    for termino in palabras_restantes:
        cats = buscar_categoria_por_termino(termino)
        prods = buscar_producto_por_termino(termino, id_empresa)
        
        opciones_combinadas = cats + prods
        if len(opciones_combinadas) == 1:
            if opciones_combinadas[0]["tipo"] == "categoria":
                entidades_resueltas["categoria_id"] = opciones_combinadas[0]["id"]
                entidades_resueltas["categoria_nombre"] = opciones_combinadas[0]["nombre"]
            else:
                entidades_resueltas["producto_id"] = opciones_combinadas[0]["id"]
                entidades_resueltas["producto_nombre"] = opciones_combinadas[0]["nombre"]
            texto_consumido = texto_consumido.replace(termino, ' ')
        elif len(opciones_combinadas) > 1:
            ambiguedades.append({
                "pregunta": f"¿A qué te refieres con '{termino}'?",
                "termino": termino,
                "opciones": opciones_combinadas
            })

    return entidades_resueltas, ambiguedades, re.sub(r'\s+', ' ', texto_consumido).strip()
