from typing import Optional, List, Dict, Any
from app.core.postgres import PostgreSQL
from app.core.config import Config


def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'


def _fila_a_dict(fila) -> Optional[Dict[str, Any]]:
    if not fila:
        return None

    return {
        "id_proveedor": fila[0],
        "razon_social": fila[1],
        "nit": fila[2],
        "telefono": fila[3],
        "correo": fila[4],
        "direccion": fila[5],
        "contacto": fila[6],
        "estado": fila[7]
    }


def listar_proveedores(
    busqueda: Optional[str] = None,
    solo_activos: bool = False
) -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()

    try:
        schema = _get_schema()

        query = f"""
            SELECT
                id_proveedor,
                razon_social,
                nit,
                telefono,
                correo,
                direccion,
                contacto,
                estado
            FROM {schema}.t_proveedor
            WHERE 1=1
        """

        params = []

        if solo_activos:
            query += " AND estado = TRUE"

        if busqueda:
            query += """
                AND (
                    razon_social ILIKE %s
                    OR nit ILIKE %s
                    OR contacto ILIKE %s
                )
            """

            patron = f"%{busqueda}%"
            params.extend([patron, patron, patron])

        query += """
            ORDER BY id_proveedor DESC
        """

        filas = db.execute_query(
            query,
            tuple(params),
            fetchall=True
        )

        return [
            _fila_a_dict(fila)
            for fila in filas
        ]

    finally:
        db.close_connection()


def obtener_proveedor_por_id(
    id_proveedor: int
) -> Optional[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()

    try:
        schema = _get_schema()

        query = f"""
            SELECT
                id_proveedor,
                razon_social,
                nit,
                telefono,
                correo,
                direccion,
                contacto,
                estado
            FROM {schema}.t_proveedor
            WHERE id_proveedor = %s
        """

        fila = db.execute_query(
            query,
            (id_proveedor,),
            fetchone=True
        )

        return _fila_a_dict(fila)

    finally:
        db.close_connection()


def verificar_nit_duplicado(
    nit: str,
    id_proveedor: Optional[int] = None
) -> bool:
    db = PostgreSQL()
    db.create_connection()

    try:
        schema = _get_schema()

        query = f"""
            SELECT 1
            FROM {schema}.t_proveedor
            WHERE nit = %s
        """

        params = [nit]

        if id_proveedor is not None:
            query += """
                AND id_proveedor <> %s
            """
            params.append(id_proveedor)

        fila = db.execute_query(
            query,
            tuple(params),
            fetchone=True
        )

        return fila is not None

    finally:
        db.close_connection()


def crear_proveedor(
    razon_social: str,
    nit: str,
    telefono: str,
    correo: str,
    direccion: str,
    contacto: str
) -> Optional[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()

    try:
        schema = _get_schema()

        query = f"""
            INSERT INTO {schema}.t_proveedor (
                razon_social,
                nit,
                telefono,
                correo,
                direccion,
                contacto,
                estado
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                TRUE
            )
            RETURNING
                id_proveedor,
                razon_social,
                nit,
                telefono,
                correo,
                direccion,
                contacto,
                estado
        """

        fila = db.execute_query(
            query,
            (
                razon_social,
                nit,
                telefono,
                correo,
                direccion,
                contacto
            ),
            fetchone=True,
            commit=True
        )

        return _fila_a_dict(fila)

    finally:
        db.close_connection()


def actualizar_proveedor(
    id_proveedor: int,
    razon_social: str,
    nit: str,
    telefono: str,
    correo: str,
    direccion: str,
    contacto: str
) -> Optional[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()

    try:
        schema = _get_schema()

        query = f"""
            UPDATE {schema}.t_proveedor
            SET
                razon_social = %s,
                nit = %s,
                telefono = %s,
                correo = %s,
                direccion = %s,
                contacto = %s
            WHERE id_proveedor = %s
            RETURNING
                id_proveedor,
                razon_social,
                nit,
                telefono,
                correo,
                direccion,
                contacto,
                estado
        """

        fila = db.execute_query(
            query,
            (
                razon_social,
                nit,
                telefono,
                correo,
                direccion,
                contacto,
                id_proveedor
            ),
            fetchone=True,
            commit=True
        )

        return _fila_a_dict(fila)

    finally:
        db.close_connection()


def cambiar_estado_proveedor(
    id_proveedor: int,
    estado: bool
) -> Optional[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()

    try:
        schema = _get_schema()

        query = f"""
            UPDATE {schema}.t_proveedor
            SET estado = %s
            WHERE id_proveedor = %s
            RETURNING
                id_proveedor,
                razon_social,
                nit,
                telefono,
                correo,
                direccion,
                contacto,
                estado
        """

        fila = db.execute_query(
            query,
            (
                estado,
                id_proveedor
            ),
            fetchone=True,
            commit=True
        )

        return _fila_a_dict(fila)

    finally:
        db.close_connection()