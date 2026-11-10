from typing import Optional, List, Dict, Any
from app.core.postgres import PostgreSQL
from app.core.config import Config


# --- LEER SUCURSALES POR EMPRESA ---
def obtener_sucursales_por_empresa(
    id_empresa: Optional[int] = None
) -> List[Dict[str, Any]]:

    db = PostgreSQL()
    db.create_connection()

    try:
        schema = Config.SCHEMA or 'comercio'

        condiciones = []
        params = []

        if id_empresa:
            condiciones.append("s.id_empresa = %s")
            params.append(id_empresa)

        where_clause = (
            "WHERE " + " AND ".join(condiciones)
            if condiciones
            else ""
        )

        query = f"""
            SELECT 
                s.id_sucursal, 
                s.nombre, 
                s.direccion, 
                s.telefono,
                s.activo, 
                s.estado,
                s.id_empresa,
                e.nombre_empresa,
                s.id_ciudad,
                c.nombre AS ciudad,
                c.departamento,
                s.created_at,
                s.latitud,
                s.longitud,
                s.codigo_sucursal
            FROM {schema}.t_sucursal s
            LEFT JOIN {schema}.t_ciudad c 
                ON s.id_ciudad = c.id_ciudad
            LEFT JOIN {schema}.empresa e 
                ON s.id_empresa = e.id_empresa
            {where_clause}
            ORDER BY s.id_sucursal ASC;
        """

        resultados = db.execute_query(
            query,
            tuple(params) if params else None,
            fetchall=True
        )

        sucursales = []

        if resultados:
            for r in resultados:
                sucursales.append({
                    "id_sucursal": r[0],
                    "nombre": r[1],
                    "direccion": r[2],
                    "telefono": r[3] or "",
                    "activo": bool(
                        r[4] if r[4] is not None else r[5]
                    ),
                    "estado": (
                        "ACTIVO"
                        if (r[4] if r[4] is not None else r[5])
                        else "INACTIVO"
                    ),
                    "id_empresa": r[6],
                    "empresa_nombre": r[7] or "Sin Empresa",
                    "id_ciudad": r[8],
                    "ciudad": r[9] or "No asignada",
                    "departamento": r[10] or "Bolivia",
                    "created_at": (
                        r[11].isoformat()
                        if r[11]
                        else None
                    ),
                    "latitud": float(r[12]) if r[12] is not None else None,
                    "longitud": float(r[13]) if r[13] is not None else None,
                    "codigo_sucursal": r[14] or f"SUC-{r[0]:02d}"
                })

        return sucursales

    finally:
        db.close_connection()


# --- CREAR SUCURSAL ---
def crear_sucursal_db(
    nombre: str,
    direccion: str,
    telefono: str,
    id_ciudad: Optional[int],
    id_empresa: int,
    activo: bool = True,
    latitud: Optional[float] = None,
    longitud: Optional[float] = None,
    codigo_sucursal: Optional[str] = None
) -> Optional[int]:

    db = PostgreSQL()
    db.create_connection()

    try:
        schema = Config.SCHEMA or 'comercio'

        # Generar código correlativo legible si no viene provisto
        if not codigo_sucursal:
            row_count = db.execute_query(
                f"SELECT COUNT(*) FROM {schema}.t_sucursal WHERE id_empresa = %s;",
                (id_empresa,),
                fetchone=True
            )
            seq_num = (row_count[0] + 1) if row_count else 1
            codigo_sucursal = f"SUC-E{id_empresa}-{seq_num:02d}"

        query = f"""
            INSERT INTO {schema}.t_sucursal (
                nombre,
                codigo_sucursal,
                direccion,
                telefono,
                id_ciudad,
                id_empresa,
                activo,
                estado,
                latitud,
                longitud
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING id_sucursal;
        """

        resultado = db.execute_query(
            query,
            (
                nombre.strip(),
                codigo_sucursal,
                direccion.strip(),
                (telefono or "").strip(),
                id_ciudad,
                id_empresa,
                activo,
                activo,
                latitud,
                longitud
            ),
            fetchone=True
        )

        if not resultado:
            return None

        id_sucursal_creada = resultado[0]

        # Crear automáticamente una caja registradora activa en la nueva sucursal
        caja_exist = db.execute_query(
            f"SELECT id_caja FROM {schema}.t_caja WHERE id_sucursal = %s LIMIT 1;",
            (id_sucursal_creada,),
            fetchone=True
        )
        if not caja_exist:
            db.execute_query(
                f"""
                    INSERT INTO {schema}.t_caja (id_sucursal, id_empresa, codigo_caja, nombre, estado)
                    VALUES (%s, %s, %s, %s, 'ACTIVA');
                """,
                (
                    id_sucursal_creada,
                    id_empresa,
                    f"CAJA-SUC-{id_sucursal_creada}-01",
                    f"Caja 01 - {nombre.strip()}"
                )
            )

        db.conn.commit()
        return id_sucursal_creada

    except Exception as e:
        if db.conn:
            db.conn.rollback()
        raise e
    finally:
        db.close_connection()


# --- LEER SUCURSAL POR ID ---
def obtener_sucursal_por_id(
    id_sucursal: int
) -> Optional[Dict[str, Any]]:

    db = PostgreSQL()
    db.create_connection()

    try:
        schema = Config.SCHEMA or 'comercio'

        query = f"""
            SELECT 
                s.id_sucursal, 
                s.nombre, 
                s.direccion, 
                s.telefono,
                s.activo, 
                s.estado,
                s.id_empresa,
                e.nombre_empresa,
                s.id_ciudad,
                c.nombre AS ciudad,
                c.departamento,
                s.created_at,
                s.latitud,
                s.longitud,
                s.codigo_sucursal
            FROM {schema}.t_sucursal s
            LEFT JOIN {schema}.t_ciudad c 
                ON s.id_ciudad = c.id_ciudad
            LEFT JOIN {schema}.empresa e 
                ON s.id_empresa = e.id_empresa
            WHERE s.id_sucursal = %s;
        """

        r = db.execute_query(query, (id_sucursal,), fetchone=True)

        if not r:
            return None

        return {
            "id_sucursal": r[0],
            "nombre": r[1],
            "direccion": r[2],
            "telefono": r[3] or "",
            "activo": bool(
                r[4] if r[4] is not None else r[5]
            ),
            "estado": (
                "ACTIVO"
                if (r[4] if r[4] is not None else r[5])
                else "INACTIVO"
            ),
            "id_empresa": r[6],
            "empresa_nombre": r[7] or "Sin Empresa",
            "id_ciudad": r[8],
            "ciudad": r[9] or "No asignada",
            "departamento": r[10] or "Bolivia",
            "created_at": (
                r[11].isoformat()
                if r[11]
                else None
            ),
            "latitud": float(r[12]) if r[12] is not None else None,
            "longitud": float(r[13]) if r[13] is not None else None,
            "codigo_sucursal": r[14] or f"SUC-{r[0]:02d}"
        }

    finally:
        db.close_connection()


# --- ACTUALIZAR SUCURSAL ---
def actualizar_sucursal_db(
    id_sucursal: int,
    nombre: str,
    direccion: str,
    telefono: str,
    id_ciudad: Optional[int],
    id_empresa: int,
    activo: bool,
    latitud: Optional[float] = None,
    longitud: Optional[float] = None
) -> bool:

    db = PostgreSQL()
    db.create_connection()

    try:
        schema = Config.SCHEMA or 'comercio'

        query = f"""
            UPDATE {schema}.t_sucursal
            SET 
                nombre = %s,
                direccion = %s,
                telefono = %s,
                id_ciudad = %s,
                id_empresa = %s,
                activo = %s,
                estado = %s,
                latitud = %s,
                longitud = %s
            WHERE id_sucursal = %s;
        """

        filas_afectadas = db.execute_query(
            query,
            (
                nombre.strip(),
                direccion.strip(),
                (telefono or "").strip(),
                id_ciudad,
                id_empresa,
                activo,
                activo,
                latitud,
                longitud,
                id_sucursal
            ),
            commit=True
        )

        return (filas_afectadas or 0) > 0

    finally:
        db.close_connection()


# --- CAMBIAR ESTADO DE SUCURSAL ---
def cambiar_estado_sucursal_db(
    id_sucursal: int,
    activo: bool
) -> bool:

    db = PostgreSQL()
    db.create_connection()

    try:
        schema = Config.SCHEMA or 'comercio'

        query = f"""
            UPDATE {schema}.t_sucursal
            SET activo = %s, estado = %s
            WHERE id_sucursal = %s;
        """

        filas_afectadas = db.execute_query(
            query,
            (activo, activo, id_sucursal),
            commit=True
        )

        return (filas_afectadas or 0) > 0

    finally:
        db.close_connection()


# --- ELIMINAR SUCURSAL ---
def eliminar_sucursal_db(
    id_sucursal: int
) -> bool:

    db = PostgreSQL()
    db.create_connection()

    try:
        schema = Config.SCHEMA or 'comercio'

        query = f"""
            DELETE FROM {schema}.t_sucursal
            WHERE id_sucursal = %s;
        """

        filas_afectadas = db.execute_query(
            query,
            (id_sucursal,),
            commit=True
        )

        return (filas_afectadas or 0) > 0

    finally:
        db.close_connection()