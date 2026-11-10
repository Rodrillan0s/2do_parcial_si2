from app.core.postgres import PostgreSQL
from app.core.config import Config

# --- COMPROBAR UNICIDAD DE NIT ---
def existe_nit_db(nit: str, exclude_id_empresa: int = None) -> bool:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        if exclude_id_empresa:
            query = f"SELECT 1 FROM {schema}.empresa WHERE LOWER(nit) = LOWER(%s) AND id_empresa != %s LIMIT 1;"
            res = db.execute_query(query, (str(nit).strip(), exclude_id_empresa), fetchone=True)
        else:
            query = f"SELECT 1 FROM {schema}.empresa WHERE LOWER(nit) = LOWER(%s) LIMIT 1;"
            res = db.execute_query(query, (str(nit).strip(),), fetchone=True)
        return bool(res)
    finally:
        db.close_connection()

# --- LEER TODAS LAS EMPRESAS / TENANTS ---
def obtener_todas_las_empresas():
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT 
                id_empresa, 
                nombre_empresa, 
                COALESCE(razon_social, nombre_empresa) AS razon_social,
                COALESCE(nit, '') AS nit, 
                COALESCE(correo, '') AS correo,
                COALESCE(telefono, '') AS telefono,
                COALESCE(direccion_fiscal, '') AS direccion_fiscal,
                COALESCE(ciudad, 'Santa Cruz') AS ciudad,
                COALESCE(logo, '') AS logo,
                COALESCE(estado, 'ACTIVO') AS estado,
                TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS updated_at,
                COALESCE(slug, LOWER(REGEXP_REPLACE(TRIM(nombre_empresa), '[^a-zA-Z0-9]+', '-', 'g'))) AS slug
            FROM {schema}.empresa 
            ORDER BY id_empresa ASC;
        """
        resultados = db.execute_query(query, fetchall=True)
        
        empresas = []
        if resultados:
            for r in resultados:
                empresas.append({
                    "id_empresa": r[0],
                    "nombre_empresa": r[1],
                    "razon_social": r[2],
                    "nit": r[3],
                    "correo": r[4],
                    "telefono": r[5],
                    "direccion_fiscal": r[6],
                    "ciudad": r[7],
                    "logo": r[8],
                    "estado": r[9],
                    "created_at": r[10],
                    "updated_at": r[11],
                    "slug": r[12]
                })
        return empresas
    finally:
        db.close_connection()

# --- LEER EMPRESA POR ID ---
def obtener_empresa_por_id_db(id_empresa: int):
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            SELECT 
                id_empresa, 
                nombre_empresa, 
                COALESCE(razon_social, nombre_empresa) AS razon_social,
                COALESCE(nit, '') AS nit, 
                COALESCE(correo, '') AS correo,
                COALESCE(telefono, '') AS telefono,
                COALESCE(direccion_fiscal, '') AS direccion_fiscal,
                COALESCE(ciudad, 'Santa Cruz') AS ciudad,
                COALESCE(logo, '') AS logo,
                COALESCE(estado, 'ACTIVO') AS estado,
                TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS updated_at
            FROM {schema}.empresa 
            WHERE id_empresa = %s;
        """
        r = db.execute_query(query, (id_empresa,), fetchone=True)
        if not r:
            return None
        return {
            "id_empresa": r[0],
            "nombre_empresa": r[1],
            "razon_social": r[2],
            "nit": r[3],
            "correo": r[4],
            "telefono": r[5],
            "direccion_fiscal": r[6],
            "ciudad": r[7],
            "logo": r[8],
            "estado": r[9],
            "created_at": r[10],
            "updated_at": r[11]
        }
    finally:
        db.close_connection()

# --- CREAR EMPRESA / TENANT ---
def crear_empresa_db(datos: dict):
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            INSERT INTO {schema}.empresa (
                nombre_empresa, razon_social, nit, correo, telefono, 
                direccion_fiscal, ciudad, logo, estado, created_at, updated_at
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) 
            RETURNING id_empresa;
        """
        params = (
            datos.get('nombre_empresa', '').strip().upper(),
            (datos.get('razon_social') or datos.get('nombre_empresa', '')).strip().upper(),
            datos.get('nit', '').strip(),
            datos.get('correo', '').strip(),
            datos.get('telefono', '').strip(),
            datos.get('direccion_fiscal', '').strip(),
            datos.get('ciudad', '').strip(),
            datos.get('logo', '').strip() if datos.get('logo') else None,
            datos.get('estado', 'ACTIVO').strip().upper()
        )
        resultado = db.execute_query(query, params, fetchone=True, commit=True)
        return resultado[0] if resultado else None
    finally:
        db.close_connection()

# --- ACTUALIZAR EMPRESA / TENANT ---
def actualizar_empresa_db(id_empresa: int, datos: dict):
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"""
            UPDATE {schema}.empresa 
            SET 
                nombre_empresa = %s, 
                razon_social = %s,
                nit = %s, 
                correo = %s,
                telefono = %s,
                direccion_fiscal = %s,
                ciudad = %s,
                logo = %s,
                estado = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id_empresa = %s;
        """
        params = (
            datos.get('nombre_empresa', '').strip().upper(),
            (datos.get('razon_social') or datos.get('nombre_empresa', '')).strip().upper(),
            datos.get('nit', '').strip(),
            datos.get('correo', '').strip(),
            datos.get('telefono', '').strip(),
            datos.get('direccion_fiscal', '').strip(),
            datos.get('ciudad', '').strip(),
            datos.get('logo', '').strip() if datos.get('logo') else None,
            datos.get('estado', 'ACTIVO').strip().upper(),
            id_empresa
        )
        filas_afectadas = db.execute_query(query, params, commit=True)
        return filas_afectadas > 0
    finally:
        db.close_connection()

# --- ELIMINAR EMPRESA ---
def eliminar_empresa_db(id_empresa: int):
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        query = f"UPDATE {schema}.empresa SET estado='INACTIVO', updated_at=CURRENT_TIMESTAMP WHERE id_empresa = %s;"
        filas_afectadas = db.execute_query(query, (id_empresa,), commit=True)
        return filas_afectadas > 0
    finally:
        db.close_connection()