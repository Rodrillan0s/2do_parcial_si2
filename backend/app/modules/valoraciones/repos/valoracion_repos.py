"""
Repositorio para el Sistema de Valoraciones de Calidad y Servicio.
Gestiona la persistencia en t_valoracion y asegura compras verificadas multi-tenant.
"""
from typing import Optional, Dict, Any, List
import logging
from app.core.postgres import PostgreSQL
from app.core.config import Config

logger = logging.getLogger(__name__)


def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'


def validar_elegibilidad_compra(
    id_cliente: int,
    id_producto: Optional[int] = None,
    id_pedido: Optional[int] = None,
    id_venta: Optional[int] = None,
    id_reserva: Optional[int] = None
) -> Dict[str, Any]:
    """
    Verifica que el cliente efectivamente haya adquirido el producto o realizado el servicio.
    Retorna el contexto de negocio (id_empresa, id_sucursal, id_venta).
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # 1. Caso Pedido Online
        if id_pedido:
            q_ped = f"""
                SELECT p.id_pedido, p.id_empresa, p.id_sucursal, p.id_venta, p.estado
                FROM {schema}.t_pedido p
                WHERE p.id_pedido = %s AND p.id_cliente = %s;
            """
            ped_row = db.execute_query(q_ped, (id_pedido, id_cliente), fetchone=True)
            if not ped_row:
                raise ValueError("No se encontró el pedido o no pertenece al cliente.")

            id_emp = ped_row[1]
            id_suc = ped_row[2]
            id_vta = ped_row[3]
            estado = ped_row[4]

            if estado not in ('PAGADO', 'ENTREGADO', 'EN_CAMINO', 'COMPLETADO'):
                raise ValueError(f"El pedido no está en un estado elegible para valoración (Estado actual: {estado}).")

            # Si se valora un producto específico, verificar que esté en el pedido
            if id_producto:
                q_item = f"""
                    SELECT 1
                    FROM {schema}.t_detalle_pedido dp
                    JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = dp.id_variante
                    WHERE dp.id_pedido = %s AND ptc.id_producto = %s
                    LIMIT 1;
                """
                item_row = db.execute_query(q_item, (id_pedido, id_producto), fetchone=True)
                if not item_row:
                    raise ValueError("El producto especificado no forma parte de este pedido.")

            return {
                "id_empresa": id_emp,
                "id_sucursal": id_suc,
                "id_venta": id_vta,
                "id_pedido": id_pedido
            }

        # 2. Caso Venta Directa / POS
        if id_venta:
            q_vta = f"""
                SELECT v.id_venta, v.id_empresa, v.id_sucursal, v.estado
                FROM {schema}.t_venta v
                WHERE v.id_venta = %s AND v.id_cliente = %s;
            """
            vta_row = db.execute_query(q_vta, (id_venta, id_cliente), fetchone=True)
            if not vta_row:
                raise ValueError("No se encontró la venta o no pertenece al cliente.")

            id_emp = vta_row[1]
            id_suc = vta_row[2]

            if id_producto:
                q_vta_item = f"""
                    SELECT 1
                    FROM {schema}.t_detalle_venta dv
                    JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = dv.id_variante
                    WHERE dv.id_venta = %s AND ptc.id_producto = %s
                    LIMIT 1;
                """
                item_vta_row = db.execute_query(q_vta_item, (id_venta, id_producto), fetchone=True)
                if not item_vta_row:
                    raise ValueError("El producto especificado no forma parte de esta venta.")

            return {
                "id_empresa": id_emp,
                "id_sucursal": id_suc,
                "id_venta": id_venta,
                "id_pedido": None
            }

        # 3. Caso Cita de Vestidor / Reserva
        if id_reserva:
            q_res = f"""
                SELECT r.id_reserva, r.id_empresa, r.id_sucursal, r.estado
                FROM {schema}.t_reserva r
                WHERE r.id_reserva = %s AND r.id_cliente = %s;
            """
            res_row = db.execute_query(q_res, (id_reserva, id_cliente), fetchone=True)
            if not res_row:
                raise ValueError("No se encontró la reserva o no pertenece al cliente.")

            id_emp = res_row[1]
            id_suc = res_row[2]
            estado_res = res_row[3]

            if estado_res not in ('ATENDIDA', 'COMPLETADA', 'CONFIRMADA'):
                raise ValueError(f"La reserva no está en estado atendida para valorar (Estado actual: {estado_res}).")

            return {
                "id_empresa": id_emp,
                "id_sucursal": id_suc,
                "id_venta": None,
                "id_pedido": None,
                "id_reserva": id_reserva
            }

        raise ValueError("Debe proporcionar al menos un identificador de compra o servicio (id_pedido, id_venta o id_reserva).")
    finally:
        db.close_connection()


def verificar_valoracion_existente(
    id_cliente: int,
    id_producto: Optional[int] = None,
    id_pedido: Optional[int] = None,
    id_venta: Optional[int] = None,
    id_reserva: Optional[int] = None
) -> bool:
    """Verifica si ya existe una calificación previa para evitar duplicados."""
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        if id_reserva:
            q = f"SELECT 1 FROM {schema}.t_valoracion WHERE id_cliente = %s AND id_reserva = %s LIMIT 1;"
            return bool(db.execute_query(q, (id_cliente, id_reserva), fetchone=True))

        if id_pedido and id_producto:
            q = f"SELECT 1 FROM {schema}.t_valoracion WHERE id_cliente = %s AND id_pedido = %s AND id_producto = %s LIMIT 1;"
            return bool(db.execute_query(q, (id_cliente, id_pedido, id_producto), fetchone=True))

        if id_venta and id_producto:
            q = f"SELECT 1 FROM {schema}.t_valoracion WHERE id_cliente = %s AND id_venta = %s AND id_producto = %s LIMIT 1;"
            return bool(db.execute_query(q, (id_cliente, id_venta, id_producto), fetchone=True))

        if id_pedido and not id_producto:
            q = f"SELECT 1 FROM {schema}.t_valoracion WHERE id_cliente = %s AND id_pedido = %s AND id_producto IS NULL LIMIT 1;"
            return bool(db.execute_query(q, (id_cliente, id_pedido), fetchone=True))

        if id_venta and not id_producto:
            q = f"SELECT 1 FROM {schema}.t_valoracion WHERE id_cliente = %s AND id_venta = %s AND id_producto IS NULL LIMIT 1;"
            return bool(db.execute_query(q, (id_cliente, id_venta), fetchone=True))

        return False
    finally:
        db.close_connection()


def registrar_valoracion(
    id_empresa: int,
    id_sucursal: Optional[int],
    id_cliente: int,
    puntuacion: int,
    id_producto: Optional[int] = None,
    id_pedido: Optional[int] = None,
    id_venta: Optional[int] = None,
    id_reserva: Optional[int] = None,
    comentario: Optional[str] = None,
    motivo_negativo: Optional[str] = None
) -> Dict[str, Any]:
    """
    Inserta la valoración en t_valoracion.
    Si puntuación == 1, activa requiere_revision = TRUE para revisión administrativa.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        es_critica = (puntuacion == 1)

        q = f"""
            INSERT INTO {schema}.t_valoracion (
                id_empresa, id_sucursal, id_cliente, id_producto,
                id_venta, id_pedido, id_reserva, puntuacion,
                comentario, motivo_negativo, requiere_revision, atendido
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, FALSE
            )
            RETURNING id_valoracion, id_empresa, id_sucursal, id_cliente,
                      id_producto, id_venta, id_pedido, id_reserva,
                      puntuacion, comentario, motivo_negativo, requiere_revision,
                      atendido, fecha_creacion;
        """
        row = db.execute_query(
            q,
            (
                id_empresa, id_sucursal, id_cliente, id_producto,
                id_venta, id_pedido, id_reserva, puntuacion,
                comentario, motivo_negativo, es_critica
            ),
            fetchone=True
        )

        return {
            "id_valoracion": row[0],
            "id_empresa": row[1],
            "id_sucursal": row[2],
            "id_cliente": row[3],
            "id_producto": row[4],
            "id_venta": row[5],
            "id_pedido": row[6],
            "id_reserva": row[7],
            "puntuacion": row[8],
            "comentario": row[9],
            "motivo_negativo": row[10],
            "requiere_revision": row[11],
            "atendido": row[12],
            "fecha_creacion": row[13].isoformat() if row[13] else None
        }
    finally:
        db.close_connection()


def obtener_resumen_producto(id_producto: int, limite_opiniones: int = 10) -> Dict[str, Any]:
    """
    Calcula el promedio, total de opiniones y desglose por estrellas para un producto.
    Incluye las reseñas más recientes con nombre del comprador verificado anonimizado.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        q_stats = f"""
            SELECT 
                COALESCE(ROUND(AVG(puntuacion), 2), 0.0) AS promedio,
                COUNT(*) AS total
            FROM {schema}.t_valoracion
            WHERE id_producto = %s;
        """
        stats_row = db.execute_query(q_stats, (id_producto,), fetchone=True)
        promedio = float(stats_row[0]) if stats_row and stats_row[0] is not None else 0.0
        total = int(stats_row[1]) if stats_row else 0

        # Conteo por estrellas
        q_dist = f"""
            SELECT puntuacion, COUNT(*)
            FROM {schema}.t_valoracion
            WHERE id_producto = %s
            GROUP BY puntuacion;
        """
        dist_rows = db.execute_query(q_dist, (id_producto,), fetchall=True) or []
        distribucion = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for r in dist_rows:
            distribucion[int(r[0])] = int(r[1])

        # Últimas opiniones
        q_reviews = f"""
            SELECT 
                v.id_valoracion,
                v.puntuacion,
                v.comentario,
                v.fecha_creacion,
                COALESCE(u.nombre, 'Cliente') AS nombre_usuario,
                COALESCE(u.apellido, '') AS apellido_usuario
            FROM {schema}.t_valoracion v
            JOIN {schema}.t_cliente c ON c.id_cliente = v.id_cliente
            JOIN {schema}.t_usuario u ON u.id_usuario = c.id_usuario
            WHERE v.id_producto = %s
            ORDER BY v.fecha_creacion DESC
            LIMIT %s;
        """
        review_rows = db.execute_query(q_reviews, (id_producto, limite_opiniones), fetchall=True) or []
        opiniones = []
        for r in review_rows:
            nombre = r[4]
            apellido = r[5]
            nombre_mostrado = f"{nombre} {apellido[0]}." if apellido else nombre
            opiniones.append({
                "id_valoracion": r[0],
                "puntuacion": r[1],
                "comentario": r[2],
                "fecha_creacion": r[3].isoformat() if r[3] else None,
                "nombre_cliente": nombre_mostrado,
                "compra_verificada": True
            })

        return {
            "id_producto": id_producto,
            "promedio": promedio,
            "total": total,
            "distribucion": distribucion,
            "ultimas_opiniones": opiniones
        }
    finally:
        db.close_connection()


def obtener_compras_pendientes_cliente(id_cliente: int, limite: int = 15) -> List[Dict[str, Any]]:
    """
    Retorna pedidos y prendas elegibles que el cliente todavía no ha calificado.
    Permite mostrar en 'Mis Pedidos' la opción de calificar sin registros previos.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        # Pedidos pagados o entregados
        q = f"""
            SELECT 
                p.id_pedido,
                p.codigo_pedido,
                p.fecha_pedido,
                p.estado,
                p.modalidad_compra,
                s.nombre AS nombre_sucursal,
                dp.id_variante,
                ptc.id_producto,
                pr.nombre AS nombre_producto,
                pr.imagen_principal
            FROM {schema}.t_pedido p
            JOIN {schema}.t_sucursal s ON s.id_sucursal = p.id_sucursal
            JOIN {schema}.t_detalle_pedido dp ON dp.id_pedido = p.id_pedido
            JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = dp.id_variante
            JOIN {schema}.t_producto pr ON pr.id_producto = ptc.id_producto
            LEFT JOIN {schema}.t_valoracion val 
                ON val.id_cliente = p.id_cliente 
               AND val.id_pedido = p.id_pedido 
               AND val.id_producto = ptc.id_producto
            WHERE p.id_cliente = %s 
              AND p.estado IN ('PAGADO', 'ENTREGADO', 'COMPLETADO')
              AND val.id_valoracion IS NULL
            ORDER BY p.fecha_pedido DESC
            LIMIT %s;
        """
        rows = db.execute_query(q, (id_cliente, limite), fetchall=True) or []
        pendientes = []
        for r in rows:
            pendientes.append({
                "id_pedido": r[0],
                "codigo_pedido": r[1],
                "fecha_pedido": r[2].isoformat() if r[2] else None,
                "estado": r[3],
                "modalidad_compra": r[4],
                "nombre_sucursal": r[5],
                "id_variante": r[6],
                "id_producto": r[7],
                "nombre_producto": r[8],
                "imagen_producto": r[9]
            })
        return pendientes
    finally:
        db.close_connection()


def listar_valoraciones_admin(
    id_empresa: int,
    id_sucursal: Optional[int] = None,
    solo_criticas: bool = False,
    atendido: Optional[bool] = None,
    limite: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Listado administrativo de valoraciones para supervisión, análisis de satisfacción y alertas.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()

        filtros = [f"v.id_empresa = %s"]
        params = [id_empresa]

        if id_sucursal:
            filtros.append("v.id_sucursal = %s")
            params.append(id_sucursal)

        if solo_criticas:
            filtros.append("(v.requiere_revision = TRUE OR v.puntuacion = 1)")

        if atendido is not None:
            filtros.append("v.atendido = %s")
            params.append(atendido)

        where_clause = " AND ".join(filtros)

        q = f"""
            SELECT 
                v.id_valoracion,
                v.id_empresa,
                v.id_sucursal,
                s.nombre AS nombre_sucursal,
                v.id_cliente,
                COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), 'Cliente') AS nombre_cliente,
                v.id_producto,
                pr.nombre AS nombre_producto,
                v.id_pedido,
                ped.codigo_pedido,
                v.id_venta,
                v.id_reserva,
                v.puntuacion,
                v.comentario,
                v.motivo_negativo,
                v.requiere_revision,
                v.atendido,
                v.notas_admin,
                v.fecha_creacion
            FROM {schema}.t_valoracion v
            LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
            LEFT JOIN {schema}.t_cliente c ON c.id_cliente = v.id_cliente
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = c.id_usuario
            LEFT JOIN {schema}.t_producto pr ON pr.id_producto = v.id_producto
            LEFT JOIN {schema}.t_pedido ped ON ped.id_pedido = v.id_pedido
            WHERE {where_clause}
            ORDER BY v.fecha_creacion DESC
            LIMIT %s OFFSET %s;
        """
        params.extend([limite, offset])
        rows = db.execute_query(q, tuple(params), fetchall=True) or []

        resultado = []
        for r in rows:
            resultado.append({
                "id_valoracion": r[0],
                "id_empresa": r[1],
                "id_sucursal": r[2],
                "nombre_sucursal": r[3],
                "id_cliente": r[4],
                "nombre_cliente": r[5],
                "id_producto": r[6],
                "nombre_producto": r[7],
                "id_pedido": r[8],
                "codigo_pedido": r[9],
                "id_venta": r[10],
                "id_reserva": r[11],
                "puntuacion": r[12],
                "comentario": r[13],
                "motivo_negativo": r[14],
                "requiere_revision": r[15],
                "atendido": r[16],
                "notas_admin": r[17],
                "fecha_creacion": r[18].isoformat() if r[18] else None
            })
        return resultado
    finally:
        db.close_connection()


def resolver_valoracion_admin(
    id_valoracion: int,
    id_empresa: int,
    notas_admin: str,
    atendido: bool = True
) -> bool:
    """Registra la atención administrativa dada a una valoración crítica."""
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        q = f"""
            UPDATE {schema}.t_valoracion
            SET atendido = %s,
                notas_admin = %s,
                requiere_revision = FALSE
            WHERE id_valoracion = %s AND id_empresa = %s;
        """
        db.execute_query(q, (atendido, notas_admin, id_valoracion, id_empresa))
        return True
    finally:
        db.close_connection()
