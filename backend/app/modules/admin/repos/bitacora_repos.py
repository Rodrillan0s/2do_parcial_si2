from app.core.postgres import PostgreSQL
from app.core.config import Config
import json

def registrar_evento_db(
    id_usuario: int | None,
    usuario_nombre: str | None,
    usuario_email: str | None,
    id_empresa: int | None,
    id_sucursal: int | None,
    modulo: str,
    accion: str,
    entidad: str | None,
    id_entidad: str | None,
    descripcion: str | None,
    resultado: str,
    nivel: str,
    ip: str | None,
    user_agent: str | None,
    datos_anteriores: dict | None,
    datos_nuevos: dict | None,
    metadatos: dict | None,
    request_id: str | None
) -> int | None:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.t_bitacora (
                id_usuario, usuario_nombre, usuario_email, id_empresa, id_sucursal,
                modulo, accion, entidad, id_entidad, descripcion, resultado, nivel,
                ip, user_agent, datos_anteriores, datos_nuevos, metadatos, request_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id_bitacora;
        """
        
        # Helper to convert dict to JSON string if present
        def to_json(d):
            return json.dumps(d) if d is not None else None

        params = (
            id_usuario, usuario_nombre, usuario_email, id_empresa, id_sucursal,
            modulo, accion, entidad, id_entidad, descripcion, resultado, nivel,
            ip, user_agent, to_json(datos_anteriores), to_json(datos_nuevos), to_json(metadatos), request_id
        )
        
        res = db.execute_query(query, params, fetchone=True, commit=True)
        return res[0] if res else None
    finally:
        db.close_connection()

def obtener_eventos_db(
    id_empresa_filtro: int | None,
    id_sucursal_filtro: int | None,
    filtros: dict,
    limit: int = 25,
    offset: int = 0
):
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        
        # Base queries
        where_clauses = ["1=1"]
        params = []
        
        # Scopes enforcement
        if id_empresa_filtro is not None:
            where_clauses.append("id_empresa = %s")
            params.append(id_empresa_filtro)
        
        if id_sucursal_filtro is not None:
            where_clauses.append("id_sucursal = %s")
            params.append(id_sucursal_filtro)
            
        if '_sucursales_autorizadas' in filtros:
            where_clauses.append('id_sucursal = ANY(%s)')
            params.append(filtros['_sucursales_autorizadas'])

        # Optional filters
        if filtros.get('modulo'):
            where_clauses.append("modulo = %s")
            params.append(filtros['modulo'])
            
        if filtros.get('accion'):
            where_clauses.append("accion = %s")
            params.append(filtros['accion'])
            
        if filtros.get('resultado'):
            where_clauses.append("resultado = %s")
            params.append(filtros['resultado'])
            
        if filtros.get('nivel'):
            where_clauses.append("nivel = %s")
            params.append(filtros['nivel'])
            
        if filtros.get('id_usuario'):
            where_clauses.append("id_usuario = %s")
            params.append(filtros['id_usuario'])
            
        if filtros.get('fecha_desde'):
            where_clauses.append("fecha_hora >= %s")
            params.append(filtros['fecha_desde'])
            
        if filtros.get('fecha_hasta'):
            where_clauses.append("fecha_hora <= %s")
            params.append(filtros['fecha_hasta'])
            
        if filtros.get('search'):
            search_term = f"%{filtros['search']}%"
            where_clauses.append("""
                (usuario_nombre ILIKE %s OR usuario_email ILIKE %s OR 
                 accion ILIKE %s OR entidad ILIKE %s OR descripcion ILIKE %s)
            """)
            # Repeat search term for each ILIKE
            params.extend([search_term] * 5)
            
        where_str = " AND ".join(where_clauses)

        # Query única de datos con COUNT(*) OVER() para reducir latencia remota a la mitad
        query = f"""
            SELECT 
                id_bitacora, fecha_hora, id_usuario, usuario_nombre, usuario_email,
                id_empresa, id_sucursal, modulo, accion, entidad, id_entidad,
                descripcion, resultado, nivel,
                COUNT(*) OVER() AS full_count
            FROM {schema}.t_bitacora
            WHERE {where_str}
            ORDER BY fecha_hora DESC
            LIMIT %s OFFSET %s
        """
        
        query_params = list(params)
        query_params.append(limit)
        query_params.append(offset)
        
        resultados = db.execute_query(query, tuple(query_params), fetchall=True)
        
        total_items = 0
        items = []
        if resultados:
            total_items = resultados[0][14]
            for r in resultados:
                items.append({
                    "id_bitacora": r[0],
                    "fecha_hora": r[1].isoformat() if r[1] else None,
                    "id_usuario": r[2],
                    "usuario_nombre": r[3],
                    "usuario_email": r[4],
                    "id_empresa": r[5],
                    "id_sucursal": r[6],
                    "modulo": r[7],
                    "accion": r[8],
                    "entidad": r[9],
                    "id_entidad": r[10],
                    "descripcion": r[11],
                    "resultado": r[12],
                    "nivel": r[13]
                })
        elif offset > 0:
            # Si offset > total_items, consultar conteo exacto
            count_query = f"SELECT COUNT(*) FROM {schema}.t_bitacora WHERE {where_str}"
            total_res = db.execute_query(count_query, tuple(params), fetchone=True)
            total_items = total_res[0] if total_res else 0
                
        return {
            "total": total_items,
            "items": items
        }
    finally:
        db.close_connection()

def obtener_detalle_evento_db(id_bitacora: int):
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT 
                id_bitacora, fecha_hora, id_usuario, usuario_nombre, usuario_email,
                id_empresa, id_sucursal, modulo, accion, entidad, id_entidad,
                descripcion, resultado, nivel, ip, user_agent, request_id,
                datos_anteriores, datos_nuevos, metadatos
            FROM {schema}.t_bitacora
            WHERE id_bitacora = %s
        """
        r = db.execute_query(query, (id_bitacora,), fetchone=True)
        if not r:
            return None
            
        return {
            "id_bitacora": r[0],
            "fecha_hora": r[1].isoformat() if r[1] else None,
            "id_usuario": r[2],
            "usuario_nombre": r[3],
            "usuario_email": r[4],
            "id_empresa": r[5],
            "id_sucursal": r[6],
            "modulo": r[7],
            "accion": r[8],
            "entidad": r[9],
            "id_entidad": r[10],
            "descripcion": r[11],
            "resultado": r[12],
            "nivel": r[13],
            "ip": r[14],
            "user_agent": r[15],
            "request_id": r[16],
            "datos_anteriores": r[17] if isinstance(r[17], dict) else (json.loads(r[17]) if r[17] else None),
            "datos_nuevos": r[18] if isinstance(r[18], dict) else (json.loads(r[18]) if r[18] else None),
            "metadatos": r[19] if isinstance(r[19], dict) else (json.loads(r[19]) if r[19] else None)
        }
    finally:
        db.close_connection()
