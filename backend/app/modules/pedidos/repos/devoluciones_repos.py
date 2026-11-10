"""
AuroraStore Iteración 3 — Repositorio de Devoluciones (CU24W / CU25W)
Garantiza aislamiento multitenant, verificación de sucursales, concurrencia segura
mediante bloqueos FOR UPDATE y registro de movimientos de inventario.
"""
from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime, timezone
import json
from fastapi import HTTPException, status
from app.core.postgres import PostgreSQL, atomic
from app.core.inventory_integrity import lock_items, lock_position
from app.modules.pedidos.repos.devolucion_importes import line_entitlements, partial_amount, cents
from decimal import Decimal
from app.core.config import Config

DEFAULT_POLITICA = {
    "dias_limite_cambio": 15,
    "dias_limite_defecto": 90,
    "permite_cambio": True,
    "permite_saldo_favor": True,
    "permite_reembolso": True,
    "permite_inter_sucursal": True,
    "requiere_etiqueta_cambio": True,
    "requiere_empaque_original": False,
    "descripcion_politica": "Cambios de talla y modelo permitidos dentro de los 15 días posteriores a la compra con etiquetas intactas. Defectos de fabricación amparados legalmente hasta 90 días conforme a la Ley 453 de Defensa del Consumidor sin requerir etiquetas originales."
}

MOTIVOS_LEY_453 = {'DEFECTO_FABRICA', 'PRODUCTO_DEFECTUOSO', 'PRODUCTO_EQUIVOCADO', 'DANADO_TRANSPORTE', 'ERROR_DESCRIPCION'}
MOTIVOS_PREFERENCIA = {'TALLA_INCORRECTA', 'COLOR_DISTINTO', 'NO_GUSTO', 'COMPRA_DUPLICADA', 'OTRO'}

def obtener_politica_devolucion(id_empresa: int) -> Dict[str, Any]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        row = db.execute_query(f"SELECT politica_devolucion FROM {schema}.empresa WHERE id_empresa = %s", (id_empresa,), fetchone=True)
        if row and row[0]:
            pol = row[0]
            if isinstance(pol, str):
                pol = json.loads(pol)
            merged = dict(DEFAULT_POLITICA)
            merged.update(pol)
            return merged
        return dict(DEFAULT_POLITICA)
    finally:
        db.close_connection()

def guardar_politica_devolucion(id_empresa: int, politica: Dict[str, Any]) -> Dict[str, Any]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        merged = dict(DEFAULT_POLITICA)
        merged.update(politica)
        db.execute_query(f"UPDATE {schema}.empresa SET politica_devolucion = %s WHERE id_empresa = %s", (json.dumps(merged), id_empresa), commit=True)
        return merged
    finally:
        db.close_connection()

def listar_creditos_cliente(id_usuario: int, id_empresa: Optional[int] = None) -> List[Dict[str, Any]]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        sql = f"""
            SELECT c.id_credito, c.id_cliente, c.id_empresa, emp.nombre_empresa, c.codigo_credito,
                   c.monto_inicial, c.saldo_disponible, c.fecha_emision, c.fecha_expiracion, c.estado
            FROM {schema}.t_credito_cliente c
            JOIN {schema}.t_cliente cli ON cli.id_cliente = c.id_cliente
            LEFT JOIN {schema}.empresa emp ON emp.id_empresa = c.id_empresa
            WHERE cli.id_usuario = %s AND (%s IS NULL OR c.id_empresa = %s)
            ORDER BY c.id_credito DESC;
        """
        rows = db.execute_query(sql, (id_usuario, id_empresa, id_empresa), fetchall=True) or []
        res = []
        for r in rows:
            res.append({
                "id_credito": r[0],
                "id_cliente": r[1],
                "id_empresa": r[2],
                "nombre_empresa": r[3],
                "codigo_credito": r[4],
                "monto_inicial": float(r[5] or 0),
                "saldo_disponible": float(r[6] or 0),
                "fecha_emision": r[7].isoformat() if hasattr(r[7], 'isoformat') and r[7] else str(r[7]),
                "fecha_expiracion": r[8].isoformat() if hasattr(r[8], 'isoformat') and r[8] else None,
                "estado": r[9]
            })
        return res
    finally:
        db.close_connection()

def verificar_saldo_credito(codigo_credito: str, id_empresa: int) -> Dict[str, Any]:
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        sql = f"""
            SELECT c.id_credito, c.id_cliente, c.id_empresa, c.codigo_credito,
                   c.monto_inicial, c.saldo_disponible, c.fecha_expiracion, c.estado
            FROM {schema}.t_credito_cliente c
            WHERE UPPER(TRIM(c.codigo_credito)) = %s AND c.id_empresa = %s;
        """
        row = db.execute_query(sql, (codigo_credito.strip().upper(), id_empresa), fetchone=True)
        if not row:
            raise HTTPException(404, "Código de crédito no encontrado para esta empresa.")
        if row[7] != 'ACTIVO' or float(row[5] or 0) <= 0:
            raise HTTPException(400, "El crédito se encuentra agotado o inactivo.")
        if row[6] and row[6] < datetime.now():
            raise HTTPException(400, "El crédito de tienda ha expirado.")
        return {
            "valido": True,
            "id_credito": row[0],
            "codigo_credito": row[3],
            "saldo_disponible": float(row[5]),
            "fecha_expiracion": row[6].isoformat() if hasattr(row[6], 'isoformat') and row[6] else None
        }
    finally:
        db.close_connection()

def _registrar_movimiento_no_vendible(
    db: PostgreSQL,
    schema: str,
    id_sucursal: int,
    id_variante: int,
    cantidad: int,
    id_usuario: int,
    tipo_movimiento: str,
    motivo_log: str
) -> None:
    sql_inv = f"SELECT id_inventario, stock_actual FROM {schema}.t_inventario WHERE id_sucursal = %s AND id_variante = %s FOR SHARE"
    inv_row = db.execute_query(sql_inv, (id_sucursal, id_variante), fetchone=True)
    if inv_row:
        id_inv, stock_act = inv_row
        sql_mov = f"""
            INSERT INTO {schema}.t_movimiento_inventario (
                id_inventario, id_usuario, tipo_movimiento, cantidad,
                stock_anterior, stock_nuevo, motivo, fecha_movimiento
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            );
        """
        db.execute_query(sql_mov, (id_inv, id_usuario, tipo_movimiento, cantidad, stock_act, stock_act, motivo_log))

def _unique_items(items, key):
    ids = [int(item.get(key, 0)) for item in items]
    if not ids or any(value <= 0 for value in ids) or len(ids) != len(set(ids)):
        raise HTTPException(400, 'Debe indicar artículos válidos, sin detalles repetidos.')


def _check_sync(db, schema, sale, tenant):
    # Receipts store data.id_venta. Missing infrastructure must not fail open.
    if not db.execute_query('SELECT to_regclass(%s)', (f'{schema}.t_sync_operacion',), fetchone=True)[0]:
        raise HTTPException(503, 'No está disponible la verificación persistente de operaciones.')
    ready = db.execute_query('''SELECT EXISTS(SELECT 1 FROM information_schema.columns
        WHERE table_schema=%s AND table_name='t_sync_operacion' AND column_name='request_hash')''',
        (schema,), fetchone=True)
    if not ready or not ready[0]:
        raise HTTPException(503, 'Falta la infraestructura de huellas persistentes de operaciones.')
    rows = db.execute_query(f'''SELECT status,conflict_code,request_hash,response_json,
        operation_id::text,id_usuario,id_empresa FROM {schema}.t_sync_operacion
        WHERE id_empresa=%s AND COALESCE(response_json->'data'->>'id_venta',response_json->>'id_venta')=%s''',
        (tenant, str(sale)), fetchall=True) or []
    for row in rows:
        if row[0] != 'synced':
            return row[:2]
        receipt = row[3] if isinstance(row[3],dict) else {}
        expected = dict(operation_id=row[4],id_usuario=row[5],id_empresa=row[6],request_hash=row[2])
        if not row[2] or receipt.get('confirmation_verified') is not True or receipt.get('confirmation') != expected:
            return ('reconciliation_required','UNVERIFIED_SYNC_RECEIPT')
    return None


def _require_structure(db, schema):
    row = db.execute_query('''SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema=%s AND ((table_name='t_devolucion' AND column_name='codigo_devolucion')
        OR (table_name='t_detalle_devolucion' AND column_name='id_detalle_venta'))''', (schema,), fetchone=True)
    if not row or row[0] != 2:
        raise HTTPException(503, 'RETURNS_SCHEMA_NOT_READY: migración de devoluciones pendiente de aprobación; no se escribió la base.')


def _validate_branch(db, schema, branch, tenant):
    row = db.execute_query(f'SELECT id_empresa FROM {schema}.t_sucursal WHERE id_sucursal=%s FOR SHARE', (branch,), fetchone=True)
    if not row or row[0] != tenant:
        raise HTTPException(403, 'Sucursal ajena a la empresa de la venta.')


def contexto_devolucion(id_devolucion):
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        _require_structure(db,schema)
        row = db.execute_query(f'''SELECT d.id_empresa,d.id_sucursal,v.id_empresa,v.id_sucursal,s.id_empresa,src.id_empresa
            FROM {schema}.t_devolucion d JOIN {schema}.t_venta v ON v.id_venta=d.id_venta
            JOIN {schema}.t_sucursal s ON s.id_sucursal=d.id_sucursal
            JOIN {schema}.t_sucursal src ON src.id_sucursal=v.id_sucursal
            WHERE d.id_devolucion=%s''', (id_devolucion,), fetchone=True)
        if not row:
            raise HTTPException(404, 'Devolución no encontrada.')
        if row[0] != row[2] or row[0] != row[4] or row[0] != row[5]:
            raise HTTPException(409, 'RETURN_RECONCILIATION_REQUIRED: pertenencia inconsistente.')
        return row[0], row[1], row[3]
    finally:
        db.close_connection()


def _request_replay(db, schema, sale, user, kind, reason, description, evidence, items, branch=None):
    """Conservative replay: identical intent on a sale returns its persistent request.

    The locked sale serializes lookup/insert. An identical second intentional
    request needs a distinct description until explicit action keys are approved.
    """
    rows = db.execute_query(f'''SELECT id_devolucion,codigo_devolucion,estado,monto_reembolso,fecha_devolucion
        FROM {schema}.t_devolucion WHERE id_venta=%s AND id_usuario=%s AND tipo_devolucion=%s
        AND motivo=%s AND descripcion_cliente IS NOT DISTINCT FROM %s AND evidencia_url IS NOT DISTINCT FROM %s
        AND estado IS DISTINCT FROM 'RECHAZADA' AND (%s IS NULL OR id_sucursal=%s)
        ORDER BY id_devolucion''', (sale,user,kind,reason,description,evidence,branch,branch), fetchall=True) or []
    requested = sorted((int(i['id_detalle_venta']),int(i['cantidad']),i.get('condicion','REVENDIBLE').upper()) for i in items)
    for row in rows:
        details = db.execute_query(f'''SELECT id_detalle_venta,cantidad,COALESCE(condicion,'REVENDIBLE')
            FROM {schema}.t_detalle_devolucion WHERE id_devolucion=%s''', (row[0],), fetchall=True) or []
        if sorted(details) == requested:
            return dict(success=True,id_devolucion=row[0],codigo_devolucion=row[1],estado=row[2],
                        monto_reembolso=float(row[3]),fecha_devolucion=row[4].isoformat(),idempotent_replay=True)
    return None


def _check_money_cap(db,schema,sale,entitlements,details):
    rows = db.execute_query(f'''SELECT dd.id_detalle_venta,SUM(dd.monto_reembolso)
        FROM {schema}.t_detalle_devolucion dd JOIN {schema}.t_devolucion d ON d.id_devolucion=dd.id_devolucion
        WHERE d.id_venta=%s AND d.estado IS DISTINCT FROM 'RECHAZADA' GROUP BY dd.id_detalle_venta''', (sale,), fetchall=True) or []
    previous = {row[0]: cents(row[1]) for row in rows}
    for detail in details:
        key = detail['id_detalle_venta']
        if previous.get(key,0) + cents(detail['monto_reembolso']) > entitlements[key]:
            raise HTTPException(409, 'REFUND_RECONCILIATION_REQUIRED: importe acumulado superior al neto vendido.')

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

def _generar_codigo_devolucion() -> str:
    fecha_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    sufijo = uuid.uuid4().hex[:6].upper()
    return f"DEV-{fecha_str}-{sufijo}"

def buscar_ventas_presencial(
    criterio: str,
    id_empresa: Optional[int],
    id_usuario: int,
    sucursales_autorizadas: Optional[List[int]] = None
) -> List[Dict[str, Any]]:
    """
    Búsqueda rápida y flexible de ventas en mostrador/POS para iniciar devoluciones.
    Permite buscar por número de venta (VTA-...), código de pedido (PED-...),
    nombre o apellido del cliente, razón social, NIT/CI, o escaneo de QR/barras.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        _require_structure(db, schema)

        criterio_limpio = (criterio or "").strip()
        if not criterio_limpio:
            return []

        # Soporte para escaneo de QR con JSON {"id_venta": 141} o URLs tipo .../comprobante/VTA-...
        if criterio_limpio.startswith("{") and criterio_limpio.endswith("}"):
            try:
                parsed_qr = json.loads(criterio_limpio)
                criterio_limpio = str(parsed_qr.get("numero_venta") or parsed_qr.get("id_venta") or parsed_qr.get("codigo") or criterio_limpio)
            except Exception:
                pass
        elif "/" in criterio_limpio and ("http" in criterio_limpio or "comprobante" in criterio_limpio):
            criterio_limpio = criterio_limpio.split("/")[-1].split("?")[0]

        patron = f"%{criterio_limpio}%"
        es_numero = criterio_limpio.isdigit()
        id_venta_num = int(criterio_limpio) if es_numero else -1

        sql = f"""
            SELECT 
                v.id_venta,
                v.numero_venta,
                v.fecha_venta,
                v.subtotal,
                v.descuento,
                v.total,
                v.estado,
                v.tipo_venta,
                v.id_empresa,
                v.id_sucursal,
                v.id_cliente,
                COALESCE(
                    NULLIF(TRIM(v.razon_social), ''),
                    NULLIF(TRIM(CONCAT(u.nombre, ' ', COALESCE(u.apellido, ''))), ''),
                    NULLIF(TRIM(ped.nombre_contacto), ''),
                    'Sin cliente registrado'
                ) AS cliente_nombre,
                COALESCE(
                    NULLIF(TRIM(v.nit_ci), ''),
                    NULLIF(TRIM(c.ci), ''),
                    '-'
                ) AS cliente_documento,
                ped.codigo_pedido,
                s.nombre AS nombre_sucursal,
                COALESCE(mp.nombre, p_lat.tipo, 'Efectivo / Caja') AS metodo_pago,
                (
                    SELECT COALESCE(SUM(dv.cantidad), 0)
                    FROM {schema}.t_detalle_venta dv
                    WHERE dv.id_venta = v.id_venta
                ) AS total_articulos_adquiridos,
                (
                    SELECT COALESCE(SUM(dd.cantidad), 0)
                    FROM {schema}.t_detalle_devolucion dd
                    JOIN {schema}.t_devolucion d ON d.id_devolucion = dd.id_devolucion
                    WHERE d.id_venta = v.id_venta AND d.estado IS DISTINCT FROM 'RECHAZADA'
                ) AS total_articulos_devueltos
            FROM {schema}.t_venta v
            LEFT JOIN {schema}.t_cliente c ON c.id_cliente = v.id_cliente
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = c.id_usuario
            LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
            LEFT JOIN {schema}.t_pedido ped ON ped.id_venta = v.id_venta
            LEFT JOIN LATERAL (
                SELECT p.id_pago, p.id_metodo_pago, mp.tipo
                FROM {schema}.t_pago p
                LEFT JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p.id_metodo_pago
                WHERE p.id_venta = v.id_venta AND p.estado = 'APROBADO'
                ORDER BY p.id_pago DESC
                LIMIT 1
            ) p_lat ON true
            LEFT JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p_lat.id_metodo_pago
            WHERE (%s IS NULL OR v.id_empresa = %s)
              AND (
                  v.numero_venta ILIKE %s
                  OR ped.codigo_pedido ILIKE %s
                  OR v.nit_ci ILIKE %s
                  OR c.ci ILIKE %s
                  OR v.razon_social ILIKE %s
                  OR CONCAT(u.nombre, ' ', COALESCE(u.apellido, '')) ILIKE %s
                  OR ped.nombre_contacto ILIKE %s
                  OR (v.id_venta = %s)
              )
            ORDER BY v.fecha_venta DESC
            LIMIT 15;
        """
        rows = db.execute_query(sql, (
            id_empresa, id_empresa,
            patron, patron, patron, patron, patron, patron, patron, id_venta_num
        ), fetchall=True) or []

        resultados = []
        for r in rows:
            cant_adquirida = int(r[16] or 0)
            cant_devuelta = int(r[17] or 0)
            cant_disponible = max(0, cant_adquirida - cant_devuelta)

            es_otra_suc = False
            if sucursales_autorizadas is not None and r[9] not in sucursales_autorizadas:
                es_otra_suc = True

            estado_norm = (r[6] or "").strip().upper()
            es_valida_estado = estado_norm in ('COMPLETADA', 'PAGADO', 'ENTREGADO')

            resultados.append({
                "id_venta": r[0],
                "numero_venta": r[1],
                "fecha_venta": r[2].isoformat() if hasattr(r[2], 'isoformat') else str(r[2]),
                "subtotal": float(r[3] or 0),
                "descuento": float(r[4] or 0),
                "total": float(r[5] or 0),
                "estado": r[6],
                "tipo_venta": r[7],
                "id_empresa": r[8],
                "id_sucursal": r[9],
                "id_cliente": r[10],
                "cliente_nombre": r[11],
                "cliente_documento": r[12],
                "codigo_pedido": r[13],
                "nombre_sucursal": r[14],
                "metodo_pago": r[15],
                "total_articulos_adquiridos": cant_adquirida,
                "total_articulos_devueltos": cant_devuelta,
                "total_articulos_disponibles": cant_disponible,
                "es_otra_sucursal": es_otra_suc,
                "es_elegible": es_valida_estado and cant_disponible > 0
            })

        return resultados
    finally:
        db.close_connection()

def consultar_venta_elegible(
    id_venta: int,
    id_usuario: int,
    id_empresa: Optional[int] = None,
    es_personal: bool = False,
    sucursales_autorizadas: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Consulta los datos de una venta y calcula los ítems y cantidades elegibles para devolución.
    Resta devoluciones previas que no hayan sido rechazadas.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        _require_structure(db,schema)

        # 1. Cabecera de la venta con datos de cliente, pedido y método de pago
        sql_venta = f"""
            SELECT 
                v.id_venta,
                v.numero_venta,
                v.fecha_venta,
                v.subtotal,
                v.descuento,
                v.total,
                v.estado,
                v.tipo_venta,
                v.id_empresa,
                v.id_sucursal,
                v.id_cliente,
                c.id_usuario AS id_usuario_cliente,
                s.nombre AS nombre_sucursal,
                emp.nombre_empresa,
                COALESCE(
                    NULLIF(TRIM(v.razon_social), ''),
                    NULLIF(TRIM(CONCAT(u.nombre, ' ', COALESCE(u.apellido, ''))), ''),
                    NULLIF(TRIM(ped.nombre_contacto), ''),
                    'Sin cliente registrado'
                ) AS cliente_nombre,
                COALESCE(
                    NULLIF(TRIM(v.nit_ci), ''),
                    NULLIF(TRIM(c.ci), ''),
                    '-'
                ) AS cliente_documento,
                ped.codigo_pedido,
                COALESCE(mp.nombre, p_lateral.tipo, 'Efectivo / Caja') AS metodo_pago_nombre
            FROM {schema}.t_venta v
            LEFT JOIN {schema}.t_cliente c ON c.id_cliente = v.id_cliente
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = c.id_usuario
            LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
            LEFT JOIN {schema}.empresa emp ON emp.id_empresa = v.id_empresa
            LEFT JOIN {schema}.t_pedido ped ON ped.id_venta = v.id_venta
            LEFT JOIN LATERAL (
                SELECT p.id_pago, p.id_metodo_pago, mp.tipo
                FROM {schema}.t_pago p
                LEFT JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p.id_metodo_pago
                WHERE p.id_venta = v.id_venta AND p.estado = 'APROBADO'
                ORDER BY p.id_pago DESC
                LIMIT 1
            ) p_lateral ON true
            LEFT JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p_lateral.id_metodo_pago
            WHERE v.id_venta = %s
            LIMIT 1;
        """
        row_v = db.execute_query(sql_venta, (id_venta,), fetchone=True)
        if not row_v:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")

        v_id, v_num, v_fecha, v_sub, v_desc, v_tot, v_estado, v_tipo, v_emp, v_suc, v_cli, v_uid_cli, v_suc_nom, v_emp_nom, v_cli_nom, v_cli_doc, v_cod_ped, v_metodo_pago = row_v

        # 2. Validaciones de Autorización y Multitenant
        if id_empresa and v_emp != id_empresa:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene autorización para acceder a ventas de otra empresa.")

        # Obtener política de devolución configurada para la empresa
        row_pol = db.execute_query(f"SELECT politica_devolucion FROM {schema}.empresa WHERE id_empresa = %s", (v_emp,), fetchone=True)
        politica_emp = dict(DEFAULT_POLITICA)
        if row_pol and row_pol[0]:
            pol_raw = row_pol[0]
            if isinstance(pol_raw, str):
                pol_raw = json.loads(pol_raw)
            politica_emp.update(pol_raw)

        if not es_personal:
            # Cliente autenticado: debe ser el dueño de la venta
            if v_uid_cli != id_usuario:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene autorización para consultar esta venta.")
        else:
            # Personal: validar si sucursal autorizada o inter-sucursal permitida
            if sucursales_autorizadas is not None and v_suc not in sucursales_autorizadas:
                permite_inter = bool(politica_emp.get("permite_inter_sucursal", True))
                if not permite_inter:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No tiene permisos sobre la sucursal de origen ({v_suc_nom}) y la empresa no admite devoluciones inter-sucursal.")

        _validate_branch(db,schema,v_suc,v_emp)
        # 3. Comprobar si la venta está completada/pagada
        estado_normalizado = (v_estado or "").strip().upper()
        es_elegible_estado = estado_normalizado in ('COMPLETADA', 'PAGADO', 'ENTREGADO')
        motivo_bloqueo = None
        if not es_elegible_estado:
            motivo_bloqueo = f"La venta se encuentra en estado '{v_estado}'. Solo pueden devolverse ventas completadas o pagadas."

        # 4. Comprobar si la venta está bajo conciliación o sin sincronizar en t_sync_operacion
        sync_row = _check_sync(db,schema,id_venta,v_emp)
        if sync_row:
            es_elegible_estado = False
            motivo_bloqueo = f'Venta pendiente de conciliacion central ({sync_row[1] or sync_row[0]}).'

        # Cálculo de días transcurridos desde la compra
        if hasattr(v_fecha, 'replace'):
            fecha_naive = v_fecha.replace(tzinfo=None)
        else:
            fecha_naive = datetime.fromisoformat(str(v_fecha)).replace(tzinfo=None)
        dias_transcurridos = max(0, (datetime.now() - fecha_naive).days)

        dias_limite_cambio = int(politica_emp.get("dias_limite_cambio", 15))
        dias_limite_defecto = int(politica_emp.get("dias_limite_defecto", 90))

        aviso_politica = None
        if dias_transcurridos > dias_limite_defecto:
            es_elegible_estado = False
            motivo_bloqueo = f"El plazo de garantía legal y comercial para esta compra ({dias_limite_defecto} días) ha vencido (transcurrieron {dias_transcurridos} días)."
        elif dias_transcurridos > dias_limite_cambio and es_elegible_estado:
            aviso_politica = f"Han transcurrido {dias_transcurridos} días desde la compra. El plazo de política de tienda para cambios o preferencias ({dias_limite_cambio} días) ha finalizado. Únicamente se admiten reclamaciones por defectos de fabricación amparados por la Ley 453 (hasta {dias_limite_defecto} días)."

        # Pago original para identificar si fue PayPal u otro
        sql_pago_orig = f"""
            SELECT p.id_pago, p.codigo_transaccion, mp.tipo, p.monto
            FROM {schema}.t_pago p
            JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p.id_metodo_pago
            WHERE p.id_venta = %s AND p.estado = 'APROBADO'
            ORDER BY p.id_pago DESC LIMIT 1;
        """
        row_pago = db.execute_query(sql_pago_orig, (id_venta,), fetchone=True)
        pago_origen = None
        if row_pago:
            pago_origen = {
                "id_pago": row_pago[0],
                "codigo_transaccion": row_pago[1],
                "tipo_metodo": row_pago[2],
                "es_paypal": (row_pago[2] or '').upper() == 'PAYPAL' or 'CAPTURE-' in (row_pago[1] or ''),
                "monto_pagado": float(row_pago[3] or 0)
            }

        # 5. Obtener los ítems originales de la venta
        sql_items = f"""
            SELECT 
                dv.id_detalle_venta,
                dv.id_variante,
                dv.cantidad,
                dv.precio_unitario,
                dv.descuento,
                dv.subtotal,
                p.nombre AS producto_nombre,
                v.sku,
                t.nombre AS talla_nombre,
                col.nombre AS color_nombre,
                (
                    SELECT img.imagen_url 
                    FROM {schema}.t_producto_imagen img 
                    WHERE img.id_producto = p.id_producto 
                    ORDER BY img.es_principal DESC, img.orden ASC, img.id_imagen ASC 
                    LIMIT 1
                ) AS imagen_url,
                p.id_producto
            FROM {schema}.t_detalle_venta dv
            JOIN {schema}.t_producto_talla_color v ON v.id_variante = dv.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
            JOIN {schema}.t_talla t ON t.id_talla = v.id_talla
            JOIN {schema}.t_color col ON col.id_color = v.id_color
            WHERE dv.id_venta = %s
            ORDER BY dv.id_detalle_venta ASC;
        """
        rows_items = db.execute_query(sql_items, (id_venta,), fetchall=True) or []

        # 5.1 Cargar variantes alternativas de los productos (para cambio de talla) en 1 sola consulta
        prod_ids = list({it[11] for it in rows_items if len(it) > 11 and it[11]})
        mapa_variantes = {}
        if prod_ids:
            placeholders = ','.join(['%s'] * len(prod_ids))
            sql_vars = f"""
                SELECT v2.id_producto, v2.id_variante, t2.nombre AS talla, col2.nombre AS color, v2.precio,
                       COALESCE(inv.stock_disponible, 0) AS stock
                FROM {schema}.t_producto_talla_color v2
                JOIN {schema}.t_talla t2 ON t2.id_talla = v2.id_talla
                JOIN {schema}.t_color col2 ON col2.id_color = v2.id_color
                LEFT JOIN {schema}.t_inventario inv ON inv.id_variante = v2.id_variante AND inv.id_sucursal = %s
                WHERE v2.id_producto IN ({placeholders}) AND v2.activo = true AND v2.estado = true
                ORDER BY t2.id_talla;
            """
            rows_v = db.execute_query(sql_vars, (v_suc, *prod_ids), fetchall=True) or []
            for rv in rows_v:
                pid, var_id, var_talla, var_col, var_precio, var_stock = rv
                mapa_variantes.setdefault(pid, []).append({
                    "id_variante": var_id,
                    "talla": var_talla,
                    "color": var_col,
                    "precio": float(var_precio or 0),
                    "stock_disponible": int(var_stock or 0)
                })

        # 6. Calcular devoluciones activas o completadas para cada detalle de venta
        sql_dev_cant = f"""
            SELECT 
                dd.id_detalle_venta,
                COALESCE(SUM(dd.cantidad), 0) AS cant_devuelta
            FROM {schema}.t_detalle_devolucion dd
            JOIN {schema}.t_devolucion d ON d.id_devolucion = dd.id_devolucion
            WHERE d.id_venta = %s 
              AND d.estado IS DISTINCT FROM 'RECHAZADA'
            GROUP BY dd.id_detalle_venta;
        """
        rows_dev = db.execute_query(sql_dev_cant, (id_venta,), fetchall=True) or []
        mapa_devueltos = {r[0]: int(r[1]) for r in rows_dev}

        entitlements = line_entitlements(rows_items,v_sub,v_desc,v_tot)
        items_resultado = []
        total_elegible_general = 0

        for it in rows_items:
            id_det_v = it[0]
            cant_original = int(it[2])
            cant_devuelta = mapa_devueltos.get(id_det_v, 0)
            cant_elegible = max(0, cant_original - cant_devuelta)
            
            # Cálculo de precio neto unitario proporcional a los descuentos aplicados
            subtotal_det = float(it[5])
            precio_neto_unitario = float(Decimal(entitlements[id_det_v]) / Decimal(100) / cant_original)

            total_elegible_general += cant_elegible

            items_resultado.append({
                "id_detalle_venta": id_det_v,
                "id_variante": it[1],
                "cantidad_original": cant_original,
                "cantidad_devuelta": cant_devuelta,
                "cantidad_elegible": cant_elegible,
                "precio_unitario": float(it[3]),
                "descuento_unitario": float(it[4]),
                "subtotal": subtotal_det,
                "precio_neto_unitario": precio_neto_unitario,
                "producto_nombre": it[6],
                "sku": it[7],
                "talla": it[8],
                "color": it[9],
                "imagen_url": it[10],
                "id_producto": it[11] if len(it) > 11 else None,
                "variantes_disponibles": mapa_variantes.get(it[11], []) if len(it) > 11 else []
            })

        if total_elegible_general == 0 and not motivo_bloqueo:
            es_elegible_estado = False
            motivo_bloqueo = "Todos los artículos de esta venta ya han sido devueltos o están en proceso de solicitud."

        return {
            "venta": {
                "id_venta": v_id,
                "numero_venta": v_num,
                "fecha_venta": v_fecha.isoformat() if hasattr(v_fecha, 'isoformat') else str(v_fecha),
                "subtotal": float(v_sub or 0),
                "descuento": float(v_desc or 0),
                "total": float(v_tot or 0),
                "estado": v_estado,
                "tipo_venta": v_tipo,
                "id_empresa": v_emp,
                "nombre_empresa": v_emp_nom,
                "id_sucursal": v_suc,
                "nombre_sucursal": v_suc_nom,
                "cliente_nombre": v_cli_nom or "Sin cliente registrado",
                "cliente_documento": v_cli_doc or "-",
                "codigo_pedido": v_cod_ped,
                "metodo_pago": v_metodo_pago or "Efectivo / Caja",
                "total_articulos_adquiridos": sum(it["cantidad_original"] for it in items_resultado),
                "total_articulos_devueltos": sum(it["cantidad_devuelta"] for it in items_resultado),
                "total_articulos_disponibles": total_elegible_general,
                "dias_transcurridos": dias_transcurridos,
                "es_otra_sucursal": bool(sucursales_autorizadas is not None and v_suc not in sucursales_autorizadas)
            },
            "es_elegible": es_elegible_estado,
            "motivo_bloqueo": motivo_bloqueo,
            "aviso_politica": aviso_politica,
            "politica": {
                "dias_transcurridos": dias_transcurridos,
                "dias_limite_cambio": dias_limite_cambio,
                "dias_limite_defecto": dias_limite_defecto,
                "permite_cambio": bool(politica_emp.get("permite_cambio", True)),
                "permite_saldo_favor": bool(politica_emp.get("permite_saldo_favor", True)),
                "permite_reembolso": bool(politica_emp.get("permite_reembolso", True)),
                "requiere_etiqueta_cambio": bool(politica_emp.get("requiere_etiqueta_cambio", True)),
                "requiere_empaque_original": bool(politica_emp.get("requiere_empaque_original", False)),
                "descripcion_politica": politica_emp.get("descripcion_politica", "")
            },
            "pago_origen": pago_origen,
            "items": items_resultado
        }
    finally:
        db.close_connection()

@atomic
def crear_solicitud_cliente(
    id_venta: int,
    id_usuario: int,
    id_empresa: int,
    motivo: str,
    descripcion: Optional[str],
    evidencia_url: Optional[str],
    items_solicitados: List[Dict[str, Any]],
    tipo_resolucion: str = "REEMBOLSO_DINERO"
) -> Dict[str, Any]:
    """
    CU25W: Crea atómicamente una solicitud de devolución online en estado 'SOLICITADA'.
    Usa transacciones con bloqueos FOR UPDATE para evitar condiciones de carrera.
    Aplica validación de políticas de tienda y Ley 453 Bolivia.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        _require_structure(db,schema)
        _unique_items(items_solicitados,"id_detalle_venta")
        
        # Iniciar transacción

        # Bloqueo y verificación de la venta
        sql_v = f"""
            SELECT id_venta, id_cliente, id_empresa, id_sucursal, estado, total, subtotal, descuento, fecha_venta
            FROM {schema}.t_venta
            WHERE id_venta = %s
            FOR UPDATE;
        """
        row_v = db.execute_query(sql_v, (id_venta,), fetchone=True)
        if not row_v:
            db.rollback()
            raise HTTPException(status_code=404, detail="Venta no encontrada.")

        v_id, v_cli, v_emp, v_suc, v_estado, v_tot, v_sub, v_desc, v_fec = row_v

        # Validar pertenencia del cliente
        owner = db.execute_query(f'SELECT id_usuario FROM {schema}.t_cliente WHERE id_cliente=%s', (v_cli,), fetchone=True)
        if not owner or owner[0] != id_usuario:
            db.rollback()
            raise HTTPException(status_code=403, detail="No tiene autorización para solicitar devoluciones sobre compras ajenas.")

        if id_empresa is not None and v_emp != id_empresa:
            db.rollback()
            raise HTTPException(status_code=403, detail="La venta no pertenece a la empresa actual.")

        id_empresa = v_emp
        _validate_branch(db,schema,v_suc,v_emp)
        if _check_sync(db,schema,id_venta,v_emp):
            raise HTTPException(409,'Venta pendiente de conciliacion central.')

        # Validar política y plazos (Ley 453 Bolivia vs comercial)
        row_pol = db.execute_query(f"SELECT politica_devolucion FROM {schema}.empresa WHERE id_empresa = %s", (v_emp,), fetchone=True)
        politica_emp = dict(DEFAULT_POLITICA)
        if row_pol and row_pol[0]:
            pol_raw = row_pol[0]
            if isinstance(pol_raw, str):
                pol_raw = json.loads(pol_raw)
            politica_emp.update(pol_raw)

        if hasattr(v_fec, 'replace'):
            fecha_naive = v_fec.replace(tzinfo=None)
        else:
            fecha_naive = datetime.fromisoformat(str(v_fec)).replace(tzinfo=None)
        dias_transcurridos = max(0, (datetime.now() - fecha_naive).days)

        motivo_norm = (motivo or "").strip().upper()
        tipo_res_norm = (tipo_resolucion or "REEMBOLSO_DINERO").strip().upper()
        if tipo_res_norm not in ('CAMBIO_PRENDA', 'SALDO_A_FAVOR', 'REEMBOLSO_DINERO'):
            tipo_res_norm = 'REEMBOLSO_DINERO'

        es_defecto = any(m in motivo_norm for m in ('DEFECTO', 'DANADO', 'DANO', 'EQUIVOCADO', 'ERROR')) or motivo_norm in MOTIVOS_LEY_453
        dias_max = int(politica_emp.get("dias_limite_defecto", 90)) if es_defecto else int(politica_emp.get("dias_limite_cambio", 15))

        if dias_transcurridos > dias_max:
            db.rollback()
            if not es_defecto:
                raise HTTPException(
                    status_code=400,
                    detail=f"El plazo de tienda para cambios o devoluciones por preferencia ({dias_max} días) ha expirado (han pasado {dias_transcurridos} días). Las reclamaciones por defecto de fabricación cuentan con garantía legal de hasta {politica_emp.get('dias_limite_defecto', 90)} días conforme a la Ley 453."
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"El plazo de garantía legal ({dias_max} días) para esta compra ha vencido."
                )

        if not es_defecto and tipo_res_norm == 'REEMBOLSO_DINERO' and not politica_emp.get("permite_reembolso", True):
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="La política comercial de esta tienda no admite reembolso en dinero para devoluciones por preferencia; elija cambio de prenda o saldo a favor."
            )

        replay = _request_replay(db,schema,id_venta,id_usuario,'SOLICITUD_CLIENTE',motivo,descripcion,evidencia_url,items_solicitados)
        if replay:
            return replay

        estado_norm = (v_estado or "").strip().upper()
        if estado_norm not in ('COMPLETADA', 'PAGADO', 'ENTREGADO'):
            db.rollback()
            raise HTTPException(status_code=400, detail=f"No se pueden devolver ventas en estado '{v_estado}'.")

        # Bloqueo de los detalles de la venta
        sql_dv = f"""
            SELECT id_detalle_venta, id_variante, cantidad, precio_unitario, descuento, subtotal
            FROM {schema}.t_detalle_venta
            WHERE id_venta = %s
            FOR UPDATE;
        """
        rows_dv = db.execute_query(sql_dv, (id_venta,), fetchall=True) or []
        mapa_dv = {r[0]: r for r in rows_dv}
        entitlements = line_entitlements(rows_dv,v_sub,v_desc,v_tot)

        # Calcular cantidades devueltas previamente no rechazadas
        sql_dev = f"""
            SELECT dd.id_detalle_venta, COALESCE(SUM(dd.cantidad), 0)
            FROM {schema}.t_detalle_devolucion dd
            JOIN {schema}.t_devolucion d ON d.id_devolucion = dd.id_devolucion
            WHERE d.id_venta = %s AND d.estado IS DISTINCT FROM 'RECHAZADA'
            GROUP BY dd.id_detalle_venta;
        """
        rows_dev = db.execute_query(sql_dev, (id_venta,), fetchall=True) or []
        mapa_devueltas = {r[0]: int(r[1]) for r in rows_dev}

        # Validar ítems solicitados
        if not items_solicitados:
            db.rollback()
            raise HTTPException(status_code=400, detail="Debe seleccionar al menos un artículo para devolver.")

        monto_total_reembolso = Decimal('0.00')
        detalles_a_insertar = []

        for req in items_solicitados:
            id_det_v = req.get("id_detalle_venta")
            cant_req = int(req.get("cantidad", 0))

            if cant_req <= 0:
                db.rollback()
                raise HTTPException(status_code=400, detail="La cantidad a devolver debe ser mayor a 0.")

            if id_det_v not in mapa_dv:
                db.rollback()
                raise HTTPException(status_code=400, detail=f"El detalle de venta {id_det_v} no pertenece a esta venta.")

            dv_row = mapa_dv[id_det_v]
            cant_original = int(dv_row[2])
            subtotal_orig = dv_row[5]
            cant_ya_dev = mapa_devueltas.get(id_det_v, 0)
            cant_disp = cant_original - cant_ya_dev

            if cant_req > cant_disp:
                db.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"La cantidad solicitada ({cant_req}) supera la cantidad elegible disponible ({cant_disp}) para el artículo."
                )

            # Cálculo de reembolso unitario neto
            subtotal_item_reembolso = partial_amount(entitlements[id_det_v],cant_original,cant_ya_dev,cant_req)
            monto_total_reembolso += subtotal_item_reembolso

            # Resolver variante de cambio si la resolución es cambio de talla
            id_var_cambio = req.get("id_variante_cambio")
            talla_deseada = (req.get("talla_deseada") or "").strip()
            if not id_var_cambio and talla_deseada and tipo_res_norm == 'CAMBIO_PRENDA':
                var_orig = dv_row[1]
                row_target = db.execute_query(f"""
                    SELECT v2.id_variante
                    FROM {schema}.t_producto_talla_color v_orig
                    JOIN {schema}.t_producto_talla_color v2 ON v2.id_producto = v_orig.id_producto
                    JOIN {schema}.t_talla t2 ON t2.id_talla = v2.id_talla
                    WHERE v_orig.id_variante = %s AND UPPER(TRIM(t2.nombre)) = UPPER(TRIM(%s)) AND v2.activo = true
                    LIMIT 1;
                """, (var_orig, talla_deseada), fetchone=True)
                if row_target:
                    id_var_cambio = row_target[0]

            detalles_a_insertar.append({
                "id_detalle_venta": id_det_v,
                "cantidad": cant_req,
                "precio_unitario": dv_row[3],
                "descuento_unitario": dv_row[4],
                "monto_reembolso": subtotal_item_reembolso,
                "estado_item": "SOLICITADO",
                "id_variante_cambio": id_var_cambio,
                "cantidad_cambio": cant_req if tipo_res_norm == 'CAMBIO_PRENDA' else 0,
                "precio_unitario_cambio": dv_row[3] if tipo_res_norm == 'CAMBIO_PRENDA' else Decimal('0.00'),
                "talla_deseada": talla_deseada
            })

        _check_money_cap(db,schema,id_venta,entitlements,detalles_a_insertar)
        # Generar código de referencia
        codigo_dev = _generar_codigo_devolucion()

        # Enriquecer descripción si se especificó cambio de talla
        tallas_req = [d["talla_deseada"] for d in detalles_a_insertar if d.get("talla_deseada")]
        descripcion_final = descripcion
        if tallas_req and tipo_res_norm == 'CAMBIO_PRENDA':
            nota_talla = f"[Cambio solicitado por talla: {', '.join(tallas_req)}]"
            descripcion_final = f"{descripcion or ''} {nota_talla}".strip()

        # Insertar cabecera t_devolucion
        sql_ins_dev = f"""
            INSERT INTO {schema}.t_devolucion (
                id_venta, id_usuario, id_empresa, id_sucursal, codigo_devolucion,
                tipo_devolucion, motivo, descripcion_cliente, evidencia_url,
                monto_reembolso, estado, tipo_resolucion, dias_desde_compra,
                cumple_politica, excepcion_ley_453, fecha_devolucion
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            ) RETURNING id_devolucion, fecha_devolucion;
        """
        params_ins_dev = (
            id_venta, id_usuario, id_empresa, v_suc, codigo_dev,
            'SOLICITUD_CLIENTE', motivo, descripcion_final, evidencia_url,
            monto_total_reembolso, 'SOLICITADA', tipo_res_norm,
            dias_transcurridos, True, es_defecto
        )
        row_dev = db.execute_query(sql_ins_dev, params_ins_dev, fetchone=True)
        id_devolucion, fecha_dev = row_dev

        # Insertar detalles en t_detalle_devolucion
        sql_ins_det = f"""
            INSERT INTO {schema}.t_detalle_devolucion (
                id_devolucion, id_detalle_venta, cantidad, precio_unitario,
                descuento_unitario, monto_reembolso, estado_item,
                id_variante_cambio, cantidad_cambio, precio_unitario_cambio
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            );
        """
        for d in detalles_a_insertar:
            db.execute_query(sql_ins_det, (
                id_devolucion, d["id_detalle_venta"], d["cantidad"],
                d["precio_unitario"], d["descuento_unitario"],
                d["monto_reembolso"], d["estado_item"],
                d["id_variante_cambio"], d["cantidad_cambio"],
                d["precio_unitario_cambio"]
            ))

        db.commit()

        return {
            "success": True,
            "id_devolucion": id_devolucion,
            "codigo_devolucion": codigo_dev,
            "estado": "SOLICITADA",
            "tipo_resolucion": tipo_res_norm,
            "dias_desde_compra": dias_transcurridos,
            "excepcion_ley_453": es_defecto,
            "monto_reembolso": float(monto_total_reembolso),
            "id_empresa": v_emp,
            "id_sucursal": v_suc,
            "fecha_devolucion": fecha_dev.isoformat() if hasattr(fecha_dev, 'isoformat') else str(fecha_dev)
        }
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close_connection()

@atomic
def registrar_devolucion_presencial(
    id_venta: int,
    id_usuario_cajero: int,
    id_empresa: int,
    id_sucursal: int,
    motivo: str,
    observaciones: Optional[str],
    items_recibidos: List[Dict[str, Any]],
    registrar_reembolso_inmediato: bool = False,
    metodo_reembolso: Optional[str] = None,
    referencia_reembolso: Optional[str] = None,
    tipo_resolucion: str = "REEMBOLSO_DINERO",
    id_sesion_caja: Optional[int] = None,
    items_cambio: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    CU24W: Registra una devolución presencial directa en mostrador/caja.
    Ajusta inventario de forma atómica para unidades 'REVENDIBLE'.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        _require_structure(db,schema)
        _unique_items(items_recibidos,"id_detalle_venta")

        # Bloqueo y verificación de venta
        sql_v = f"""
            SELECT id_venta, id_empresa, id_sucursal, estado, total, id_cliente, subtotal, descuento, fecha_venta
            FROM {schema}.t_venta
            WHERE id_venta = %s
            FOR UPDATE;
        """
        row_v = db.execute_query(sql_v, (id_venta,), fetchone=True)
        if not row_v:
            db.rollback()
            raise HTTPException(status_code=404, detail="Venta no encontrada.")

        v_id, v_emp, v_suc, v_estado, v_tot, v_cli, v_sub, v_desc, v_fec = row_v

        if v_emp != id_empresa:
            db.rollback()
            raise HTTPException(status_code=403, detail="La venta no pertenece a la empresa actual.")

        _validate_branch(db,schema,id_sucursal,v_emp)
        if _check_sync(db,schema,id_venta,v_emp):
            raise HTTPException(409,'Venta pendiente de conciliacion central.')

        if hasattr(v_fec, 'replace'):
            fecha_naive = v_fec.replace(tzinfo=None)
        else:
            fecha_naive = datetime.fromisoformat(str(v_fec)).replace(tzinfo=None)
        dias_transcurridos = max(0, (datetime.now() - fecha_naive).days)

        motivo_norm = (motivo or "").strip().upper()
        tipo_res_norm = (tipo_resolucion or "REEMBOLSO_DINERO").strip().upper()
        if tipo_res_norm not in ('CAMBIO_PRENDA', 'SALDO_A_FAVOR', 'REEMBOLSO_DINERO'):
            tipo_res_norm = 'REEMBOLSO_DINERO'

        es_defecto = any(m in motivo_norm for m in ('DEFECTO', 'DANADO', 'DANO', 'EQUIVOCADO', 'ERROR')) or motivo_norm in MOTIVOS_LEY_453

        if registrar_reembolso_inmediato and tipo_res_norm == 'REEMBOLSO_DINERO':
            if not metodo_reembolso:
                metodo_reembolso = 'EFECTIVO'
            if not referencia_reembolso:
                referencia_reembolso = f"REC-POS-{id_sucursal}-{uuid.uuid4().hex[:6].upper()}"
        replay = _request_replay(db,schema,id_venta,id_usuario_cajero,'PRESENCIAL_MOSTRADOR',motivo,None,None,items_recibidos,id_sucursal)
        if replay:
            return replay

        estado_norm = (v_estado or "").strip().upper()
        if estado_norm not in ('COMPLETADA', 'PAGADO', 'ENTREGADO'):
            db.rollback()
            raise HTTPException(status_code=400, detail=f"No se pueden devolver ventas en estado '{v_estado}'.")

        # Bloqueo de detalles de la venta
        sql_dv = f"""
            SELECT dv.id_detalle_venta, dv.id_variante, dv.cantidad, dv.precio_unitario, dv.descuento, dv.subtotal
            FROM {schema}.t_detalle_venta dv
            WHERE dv.id_venta = %s
            FOR UPDATE;
        """
        rows_dv = db.execute_query(sql_dv, (id_venta,), fetchall=True) or []
        mapa_dv = {r[0]: r for r in rows_dv}
        entitlements = line_entitlements(rows_dv,v_sub,v_desc,v_tot)

        # Calcular devueltas previas
        sql_dev = f"""
            SELECT dd.id_detalle_venta, COALESCE(SUM(dd.cantidad), 0)
            FROM {schema}.t_detalle_devolucion dd
            JOIN {schema}.t_devolucion d ON d.id_devolucion = dd.id_devolucion
            WHERE d.id_venta = %s AND d.estado IS DISTINCT FROM 'RECHAZADA'
            GROUP BY dd.id_detalle_venta;
        """
        rows_dev = db.execute_query(sql_dev, (id_venta,), fetchall=True) or []
        mapa_devueltas = {r[0]: int(r[1]) for r in rows_dev}

        if not items_recibidos:
            db.rollback()
            raise HTTPException(status_code=400, detail="Debe especificar al menos una prenda a devolver.")

        monto_total_reembolso = Decimal('0.00')
        detalles_a_procesar = []

        for req in items_recibidos:
            id_det_v = req.get("id_detalle_venta")
            cant_req = int(req.get("cantidad", 0))
            condicion = (req.get("condicion") or "REVENDIBLE").strip().upper()
            if condicion not in ('REVENDIBLE','DEFECTUOSO','NO_REVENDIBLE'):
                raise HTTPException(400,'Condicion de prenda invalida.')

            if cant_req <= 0:
                db.rollback()
                raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0.")

            if id_det_v not in mapa_dv:
                db.rollback()
                raise HTTPException(status_code=400, detail=f"El ítem {id_det_v} no pertenece a la venta.")

            dv_row = mapa_dv[id_det_v]
            id_variante = dv_row[1]
            cant_orig = int(dv_row[2])
            subtotal_orig = dv_row[5]
            cant_ya_dev = mapa_devueltas.get(id_det_v, 0)
            cant_disp = cant_orig - cant_ya_dev

            if cant_req > cant_disp:
                db.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"La cantidad ({cant_req}) supera el saldo elegible ({cant_disp}) para el ítem {id_det_v}."
                )

            subtotal_item_reembolso = partial_amount(entitlements[id_det_v],cant_orig,cant_ya_dev,cant_req)
            monto_total_reembolso += subtotal_item_reembolso

            detalles_a_procesar.append({
                "id_detalle_venta": id_det_v,
                "id_variante": id_variante,
                "cantidad": cant_req,
                "condicion": condicion,
                "precio_unitario": dv_row[3],
                "descuento_unitario": dv_row[4],
                "monto_reembolso": subtotal_item_reembolso
            })

        _check_money_cap(db,schema,id_venta,entitlements,detalles_a_procesar)
        lock_items(db,schema,id_sucursal,detalles_a_procesar,id_empresa,allow_missing=True)
        # Cálculo de diferencia en caso de CAMBIO DE PRENDA
        diferencia_cambio = Decimal('0.00')
        if tipo_res_norm == 'CAMBIO_PRENDA' and items_cambio:
            total_cambio_nuevo = Decimal('0.00')
            for ic in items_cambio:
                cant_c = int(ic.get('cantidad', 1))
                pr_c = Decimal(str(ic.get('precio_unitario', 0)))
                total_cambio_nuevo += cant_c * pr_c
                id_var_nuevo = ic.get('id_variante')
                if id_var_nuevo:
                    sql_desct = f"""
                        UPDATE {schema}.t_inventario
                        SET stock_actual = stock_actual - %s,
                            stock_disponible = stock_disponible - %s,
                            fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE id_sucursal = %s AND id_variante = %s AND stock_disponible >= %s;
                    """
                    db.execute_query(sql_desct, (cant_c, cant_c, id_sucursal, id_var_nuevo, cant_c))
                    sql_mov_sal = f"""
                        INSERT INTO {schema}.t_movimiento_inventario (
                            id_inventario, id_usuario, tipo_movimiento, cantidad,
                            motivo, fecha_movimiento
                        ) SELECT id_inventario, %s, 'SALIDA_CAMBIO_PRENDA', %s, 'Entrega en cambio de prenda', CURRENT_TIMESTAMP
                        FROM {schema}.t_inventario WHERE id_sucursal = %s AND id_variante = %s;
                    """
                    db.execute_query(sql_mov_sal, (id_usuario_cajero, cant_c, id_sucursal, id_var_nuevo))
            diferencia_cambio = total_cambio_nuevo - monto_total_reembolso

        # Emisión de Crédito Inmediato si SALDO_A_FAVOR
        if registrar_reembolso_inmediato and tipo_res_norm == 'SALDO_A_FAVOR':
            cod_cred = f"CRED-{id_empresa}-{uuid.uuid4().hex[:8].upper()}"
            id_cli_target = v_cli
            if not id_cli_target:
                row_cli_ins = db.execute_query(f"INSERT INTO {schema}.t_cliente (id_usuario, fecha_registro) VALUES (%s, CURRENT_TIMESTAMP) RETURNING id_cliente", (id_usuario_cajero,), fetchone=True)
                id_cli_target = row_cli_ins[0]
            sql_ins_cr = f"""
                INSERT INTO {schema}.t_credito_cliente (
                    id_cliente, id_empresa, codigo_credito, monto_inicial, saldo_disponible,
                    fecha_expiracion, estado
                ) VALUES (
                    %s, %s, %s, %s, %s, CURRENT_TIMESTAMP + interval '180 days', 'ACTIVO'
                ) RETURNING id_credito;
            """
            row_cr = db.execute_query(sql_ins_cr, (id_cli_target, id_empresa, cod_cred, float(monto_total_reembolso), float(monto_total_reembolso)), fetchone=True)
            if row_cr:
                db.execute_query(f"""
                    INSERT INTO {schema}.t_movimiento_credito (
                        id_credito, tipo_movimiento, monto, saldo_anterior, saldo_nuevo, id_usuario, motivo
                    ) VALUES (%s, 'EMISION', %s, 0, %s, %s, 'Crédito presencial en mostrador');
                """, (row_cr[0], float(monto_total_reembolso), float(monto_total_reembolso), id_usuario_cajero))
            metodo_reembolso = 'SALDO_A_FAVOR'
            referencia_reembolso = cod_cred

        # Determinar estado
        estado_final = "COMPLETADA" if registrar_reembolso_inmediato else "PENDIENTE_REEMBOLSO"
        codigo_dev = _generar_codigo_devolucion()

        # Insertar cabecera t_devolucion
        sql_ins_dev = f"""
            INSERT INTO {schema}.t_devolucion (
                id_venta, id_usuario, id_empresa, id_sucursal, codigo_devolucion,
                tipo_devolucion, motivo, observaciones_resolucion,
                monto_reembolso, estado, id_usuario_revisor, fecha_resolucion,
                metodo_reembolso, referencia_reembolso, fecha_reembolso, fecha_devolucion,
                tipo_resolucion, id_sesion_caja, diferencia_cambio, dias_desde_compra,
                cumple_politica, excepcion_ley_453
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s,
                {"CURRENT_TIMESTAMP" if registrar_reembolso_inmediato else "NULL"}, CURRENT_TIMESTAMP,
                %s, %s, %s, %s, %s, %s
            ) RETURNING id_devolucion, fecha_devolucion;
        """
        params_ins_dev = (
            id_venta, id_usuario_cajero, id_empresa, id_sucursal, codigo_dev,
            'PRESENCIAL_MOSTRADOR', motivo, observaciones,
            monto_total_reembolso, estado_final, id_usuario_cajero,
            metodo_reembolso if registrar_reembolso_inmediato else None,
            referencia_reembolso if registrar_reembolso_inmediato else None,
            tipo_res_norm, id_sesion_caja, float(diferencia_cambio),
            dias_transcurridos, True, es_defecto
        )
        row_dev = db.execute_query(sql_ins_dev, params_ins_dev, fetchone=True)
        id_devolucion, fecha_dev = row_dev

        # Insertar detalles y ajustar stock
        sql_ins_det = f"""
            INSERT INTO {schema}.t_detalle_devolucion (
                id_devolucion, id_detalle_venta, cantidad, condicion,
                precio_unitario, descuento_unitario, monto_reembolso, estado_item,
                destino_inventario
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, 'RECIBIDO', %s
            );
        """

        for d in detalles_a_procesar:
            c_norm = d["condicion"]
            if c_norm in ("REVENDIBLE", "NUEVO"):
                dest = "STOCK_DISPONIBLE"
                _reincorporar_stock_inventario(
                    db=db,
                    schema=schema,
                    id_sucursal=id_sucursal,
                    id_variante=d["id_variante"],
                    cantidad=d["cantidad"],
                    id_usuario=id_usuario_cajero,
                    motivo_log=f"Devolución presencial {codigo_dev}"
                )
            elif c_norm in ("DEFECTUOSO", "CON_DEFECTO"):
                dest = "CUARENTENA_DEFECTO"
                _registrar_movimiento_no_vendible(
                    db=db,
                    schema=schema,
                    id_sucursal=id_sucursal,
                    id_variante=d["id_variante"],
                    cantidad=d["cantidad"],
                    id_usuario=id_usuario_cajero,
                    tipo_movimiento="CUARENTENA_DEFECTO",
                    motivo_log=f"Prenda retenida por defecto {codigo_dev}"
                )
            else:
                dest = "MERMA_DANO"
                _registrar_movimiento_no_vendible(
                    db=db,
                    schema=schema,
                    id_sucursal=id_sucursal,
                    id_variante=d["id_variante"],
                    cantidad=d["cantidad"],
                    id_usuario=id_usuario_cajero,
                    tipo_movimiento="MERMA_DEVOLUCION",
                    motivo_log=f"Prenda dañada presencial {codigo_dev}"
                )

            db.execute_query(sql_ins_det, (
                id_devolucion, d["id_detalle_venta"], d["cantidad"], d["condicion"],
                d["precio_unitario"], d["descuento_unitario"], d["monto_reembolso"], dest
            ))

        db.commit()

        return {
            "success": True,
            "id_devolucion": id_devolucion,
            "codigo_devolucion": codigo_dev,
            "estado": estado_final,
            "tipo_resolucion": tipo_res_norm,
            "diferencia_cambio": float(diferencia_cambio),
            "monto_reembolso": float(monto_total_reembolso),
            "id_empresa": v_emp,
            "id_sucursal": id_sucursal,
            "recepcion": items_recibidos,
            "fecha_devolucion": fecha_dev.isoformat() if hasattr(fecha_dev, 'isoformat') else str(fecha_dev)
        }
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close_connection()

def _reincorporar_stock_inventario(
    db: PostgreSQL,
    schema: str,
    id_sucursal: int,
    id_variante: int,
    cantidad: int,
    id_usuario: int,
    motivo_log: str
) -> None:
    """
    Función interna que actualiza t_inventario y t_movimiento_inventario bajo la misma transacción.
    """
    lock_position(db,schema,id_sucursal,id_variante,allow_missing=True)
    # 1. Obtener o crear inventario para la variante en la sucursal
    sql_inv = f"""
        SELECT id_inventario, stock_actual, stock_disponible
        FROM {schema}.t_inventario
        WHERE id_sucursal = %s AND id_variante = %s
        FOR UPDATE;
    """
    inv_row = db.execute_query(sql_inv, (id_sucursal, id_variante), fetchone=True)
    if not inv_row:
        # Crear registro de inventario base si no existía en esta sucursal
        sql_crear_inv = f"""
            INSERT INTO {schema}.t_inventario (
                id_sucursal, id_variante, stock_actual, stock_reservado, stock_disponible, estado
            ) VALUES (
                %s, %s, %s, 0, %s, true
            ) RETURNING id_inventario;
        """
        nuevo_inv = db.execute_query(sql_crear_inv, (id_sucursal, id_variante, cantidad, cantidad), fetchone=True)
        id_inv = nuevo_inv[0]
        stock_ant = 0
        stock_nuevo = cantidad
    else:
        id_inv, stock_act, stock_disp = inv_row
        stock_ant = stock_act
        stock_nuevo = stock_act + cantidad
        stock_disp_nuevo = stock_disp + cantidad

        sql_upd_inv = f"""
            UPDATE {schema}.t_inventario
            SET stock_actual = %s,
                stock_disponible = %s,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_inventario = %s;
        """
        db.execute_query(sql_upd_inv, (stock_nuevo, stock_disp_nuevo, id_inv))

    # 2. Registrar movimiento de inventario para trazabilidad completa
    sql_mov = f"""
        INSERT INTO {schema}.t_movimiento_inventario (
            id_inventario, id_usuario, tipo_movimiento, cantidad,
            stock_anterior, stock_nuevo, motivo, fecha_movimiento
        ) VALUES (
            %s, %s, 'ENTRADA', %s, %s, %s, %s, CURRENT_TIMESTAMP
        );
    """
    db.execute_query(sql_mov, (id_inv, id_usuario, cantidad, stock_ant, stock_nuevo, motivo_log))

    lock_position(db,schema,id_sucursal,id_variante)

def listar_devoluciones_cliente(
    id_usuario: int,
    id_empresa: Optional[int] = None,
    limit: int = 10,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Lista las solicitudes de devolución del cliente autenticado con paginación.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        _require_structure(db,schema)

        condiciones = ["d.id_usuario = %s"]
        params: List[Any] = [id_usuario]

        if id_empresa and id_empresa > 0:
            condiciones.append("d.id_empresa = %s")
            params.append(id_empresa)

        where_cl = " AND ".join(condiciones)

        sql_total = f"SELECT COUNT(*) FROM {schema}.t_devolucion d WHERE {where_cl};"
        total = db.execute_query(sql_total, tuple(params), fetchone=True)[0]

        sql_data = f"""
            SELECT 
                d.id_devolucion,
                d.codigo_devolucion,
                d.id_venta,
                v.numero_venta,
                d.tipo_devolucion,
                d.motivo,
                d.descripcion_cliente,
                d.monto_reembolso,
                d.estado,
                d.fecha_devolucion,
                d.fecha_resolucion,
                d.observaciones_resolucion,
                s.nombre AS nombre_sucursal,
                (
                    SELECT COUNT(*) 
                    FROM {schema}.t_detalle_devolucion dd 
                    WHERE dd.id_devolucion = d.id_devolucion
                ) AS total_prendas,
                d.id_empresa
            FROM {schema}.t_devolucion d
            LEFT JOIN {schema}.t_venta v ON v.id_venta = d.id_venta
            LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = d.id_sucursal
            WHERE {where_cl}
            ORDER BY d.fecha_devolucion DESC
            LIMIT %s OFFSET %s;
        """
        params_data = tuple(params + [limit, offset])
        rows = db.execute_query(sql_data, params_data, fetchall=True) or []

        resultado = []
        for r in rows:
            resultado.append({
                "id_devolucion": r[0],
                "codigo_devolucion": r[1] or f"DEV-{r[0]}",
                "id_venta": r[2],
                "numero_venta": r[3],
                "tipo_devolucion": r[4],
                "motivo": r[5],
                "descripcion_cliente": r[6],
                "monto_reembolso": float(r[7] or 0),
                "estado": r[8],
                "fecha_devolucion": r[9].isoformat() if hasattr(r[9], 'isoformat') else str(r[9]),
                "fecha_resolucion": r[10].isoformat() if r[10] and hasattr(r[10], 'isoformat') else str(r[10]) if r[10] else None,
                "observaciones_resolucion": r[11],
                "nombre_sucursal": r[12],
                "total_prendas": int(r[13] or 0)
            })

        return {
            "total": total,
            "data": resultado
        }
    finally:
        db.close_connection()

def listar_devoluciones_personal(
    id_empresa: int,
    sucursales_autorizadas: Optional[List[int]] = None,
    estado: Optional[str] = None,
    id_sucursal: Optional[int] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    busqueda: Optional[str] = None,
    limit: int = 15,
    offset: int = 0
) -> Dict[str, Any]:
    """
    CU24W: Lista devoluciones para personal administrativo filtrando por tenant y sucursales.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        _require_structure(db,schema)

        condiciones = ["d.id_empresa = %s"]
        params: List[Any] = [id_empresa]

        # Restricción estricta de sucursales para cajero / encargado
        if sucursales_autorizadas is not None:
            if not sucursales_autorizadas:
                return {"total": 0, "data": []}
            condiciones.append("d.id_sucursal = ANY(%s)")
            params.append(sucursales_autorizadas)

        if id_sucursal and id_sucursal > 0:
            condiciones.append("d.id_sucursal = %s")
            params.append(id_sucursal)

        if estado and estado.strip() and estado.strip().upper() != 'TODOS':
            condiciones.append("d.estado = %s")
            params.append(estado.strip().upper())

        if fecha_inicio and fecha_inicio.strip():
            condiciones.append("d.fecha_devolucion >= %s")
            params.append(fecha_inicio.strip())

        if fecha_fin and fecha_fin.strip():
            condiciones.append("d.fecha_devolucion <= %s")
            params.append(fecha_fin.strip() + " 23:59:59")

        if busqueda and busqueda.strip():
            b = f"%{busqueda.strip()}%"
            condiciones.append("(d.codigo_devolucion ILIKE %s OR v.numero_venta ILIKE %s OR u.nombre ILIKE %s OR u.apellido ILIKE %s OR u.correo ILIKE %s)")
            params.extend([b, b, b, b, b])

        where_cl = " AND ".join(condiciones)

        sql_tot = f"""
            SELECT COUNT(*) 
            FROM {schema}.t_devolucion d
            LEFT JOIN {schema}.t_venta v ON v.id_venta = d.id_venta
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = d.id_usuario
            WHERE {where_cl};
        """
        total = db.execute_query(sql_tot, tuple(params), fetchone=True)[0]

        sql_data = f"""
            SELECT 
                d.id_devolucion,
                d.codigo_devolucion,
                d.id_venta,
                v.numero_venta,
                d.tipo_devolucion,
                d.motivo,
                d.monto_reembolso,
                d.estado,
                d.fecha_devolucion,
                d.fecha_resolucion,
                d.id_sucursal,
                s.nombre AS nombre_sucursal,
                u.nombre AS cliente_nombre,
                u.apellido AS cliente_apellido,
                u.correo AS cliente_correo,
                rev.nombre AS revisor_nombre,
                rev.apellido AS revisor_apellido,
                (
                    SELECT COUNT(*) 
                    FROM {schema}.t_detalle_devolucion dd 
                    WHERE dd.id_devolucion = d.id_devolucion
                ) AS total_prendas,
                d.id_empresa
            FROM {schema}.t_devolucion d
            LEFT JOIN {schema}.t_venta v ON v.id_venta = d.id_venta
            LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = d.id_sucursal
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = d.id_usuario
            LEFT JOIN {schema}.t_usuario rev ON rev.id_usuario = d.id_usuario_revisor
            WHERE {where_cl}
            ORDER BY d.fecha_devolucion DESC
            LIMIT %s OFFSET %s;
        """
        params_data = tuple(params + [limit, offset])
        rows = db.execute_query(sql_data, params_data, fetchall=True) or []

        resultado = []
        for r in rows:
            cliente_nom = f"{r[12] or ''} {r[13] or ''}".strip() or "Cliente Mostrador"
            revisor_nom = f"{r[15] or ''} {r[16] or ''}".strip() if r[15] else None

            resultado.append({
                "id_devolucion": r[0],
                "codigo_devolucion": r[1] or f"DEV-{r[0]}",
                "id_venta": r[2],
                "numero_venta": r[3],
                "tipo_devolucion": r[4],
                "motivo": r[5],
                "monto_reembolso": float(r[6] or 0),
                "estado": r[7],
                "fecha_devolucion": r[8].isoformat() if hasattr(r[8], 'isoformat') else str(r[8]),
                "fecha_resolucion": r[9].isoformat() if r[9] and hasattr(r[9], 'isoformat') else str(r[9]) if r[9] else None,
                "id_sucursal": r[10],
                "nombre_sucursal": r[11],
                "cliente_nombre": cliente_nom,
                "cliente_correo": r[14],
                "revisor_nombre": revisor_nom,
                "total_prendas": int(r[17] or 0),
                "id_empresa": r[18]
            })

        return {
            "total": total,
            "data": resultado
        }
    finally:
        db.close_connection()

def obtener_detalle_devolucion(
    id_devolucion: int,
    id_usuario: int,
    id_empresa: Optional[int] = None,
    es_personal: bool = False,
    sucursales_autorizadas: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Retorna el detalle completo de una devolución (cabecera, venta, prendas, resolución y reembolso).
    Verifica pertenencia y aislamiento multitenant.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        _require_structure(db,schema)

        sql_head = f"""
            SELECT 
                d.id_devolucion,
                d.codigo_devolucion,
                d.id_venta,
                v.numero_venta,
                v.total AS total_venta,
                v.fecha_venta,
                v.tipo_venta,
                d.id_empresa,
                d.id_sucursal,
                s.nombre AS nombre_sucursal,
                d.id_usuario,
                u.nombre AS cliente_nombre,
                u.apellido AS cliente_apellido,
                u.correo AS cliente_correo,
                d.tipo_devolucion,
                d.motivo,
                d.descripcion_cliente,
                d.evidencia_url,
                d.monto_reembolso,
                d.estado,
                d.id_usuario_revisor,
                rev.nombre AS revisor_nombre,
                rev.apellido AS revisor_apellido,
                d.fecha_resolucion,
                d.observaciones_resolucion,
                d.metodo_reembolso,
                d.referencia_reembolso,
                d.fecha_reembolso,
                d.fecha_devolucion,
                COALESCE(d.tipo_resolucion, 'REEMBOLSO_DINERO') AS tipo_resolucion,
                d.id_sesion_caja,
                COALESCE(d.diferencia_cambio, 0.00) AS diferencia_cambio,
                d.dias_desde_compra,
                COALESCE(d.cumple_politica, true) AS cumple_politica,
                COALESCE(d.excepcion_ley_453, false) AS excepcion_ley_453
            FROM {schema}.t_devolucion d
            LEFT JOIN {schema}.t_venta v ON v.id_venta = d.id_venta
            LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = d.id_sucursal
            LEFT JOIN {schema}.t_usuario u ON u.id_usuario = d.id_usuario
            LEFT JOIN {schema}.t_usuario rev ON rev.id_usuario = d.id_usuario_revisor
            WHERE d.id_devolucion = %s
            LIMIT 1;
        """
        row = db.execute_query(sql_head, (id_devolucion,), fetchone=True)
        if not row:
            raise HTTPException(status_code=404, detail="Devolución no encontrada.")

        # Validar permisos
        v_emp = row[7]
        v_suc = row[8]
        v_uid = row[10]

        if id_empresa and v_emp != id_empresa:
            raise HTTPException(status_code=403, detail="No tiene autorización sobre devoluciones de otra empresa.")

        if not es_personal:
            if v_uid != id_usuario:
                raise HTTPException(status_code=403, detail="No tiene autorización para consultar devoluciones ajenas.")
        else:
            if sucursales_autorizadas is not None and v_suc not in sucursales_autorizadas:
                raise HTTPException(status_code=403, detail="No tiene autorización sobre la sucursal de esta devolución.")

        # Obtener información del pago original de la venta
        id_venta_orig = row[2]
        sql_pago_orig = f"""
            SELECT p.id_pago, p.codigo_transaccion, mp.tipo, p.monto
            FROM {schema}.t_pago p
            JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p.id_metodo_pago
            WHERE p.id_venta = %s AND p.estado = 'APROBADO'
            ORDER BY p.id_pago DESC LIMIT 1;
        """
        pago_row = db.execute_query(sql_pago_orig, (id_venta_orig,), fetchone=True)
        pago_info = None
        if pago_row:
            pago_info = {
                "id_pago": pago_row[0],
                "codigo_transaccion": pago_row[1],
                "tipo_metodo": pago_row[2],
                "es_paypal": (pago_row[2] or '').upper() == 'PAYPAL' or 'CAPTURE-' in (pago_row[1] or ''),
                "monto_pagado": float(pago_row[3] or 0)
            }

        # Obtener prendas de la devolución
        sql_items = f"""
            SELECT 
                dd.id_detalle_devolucion,
                dd.id_detalle_venta,
                dd.cantidad,
                COALESCE(dd.condicion, 'REVENDIBLE') AS condicion,
                dd.precio_unitario,
                dd.descuento_unitario,
                dd.monto_reembolso,
                COALESCE(dd.estado_item, 'SOLICITADO') AS estado_item,
                p.nombre AS producto_nombre,
                v.sku,
                t.nombre AS talla_nombre,
                col.nombre AS color_nombre,
                (
                    SELECT img.imagen_url 
                    FROM {schema}.t_producto_imagen img 
                    WHERE img.id_producto = p.id_producto 
                    ORDER BY img.es_principal DESC, img.orden ASC, img.id_imagen ASC 
                    LIMIT 1
                ) AS imagen_url,
                dd.id_variante_cambio,
                dd.cantidad_cambio,
                dd.precio_unitario_cambio,
                COALESCE(dd.destino_inventario, 'STOCK_DISPONIBLE') AS destino_inventario,
                tc.nombre AS talla_cambio,
                vc.sku AS sku_cambio
            FROM {schema}.t_detalle_devolucion dd
            JOIN {schema}.t_detalle_venta dv ON dv.id_detalle_venta = dd.id_detalle_venta
            JOIN {schema}.t_producto_talla_color v ON v.id_variante = dv.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
            JOIN {schema}.t_talla t ON t.id_talla = v.id_talla
            JOIN {schema}.t_color col ON col.id_color = v.id_color
            LEFT JOIN {schema}.t_producto_talla_color vc ON vc.id_variante = dd.id_variante_cambio
            LEFT JOIN {schema}.t_talla tc ON tc.id_talla = vc.id_talla
            WHERE dd.id_devolucion = %s
            ORDER BY dd.id_detalle_devolucion ASC;
        """
        rows_it = db.execute_query(sql_items, (id_devolucion,), fetchall=True) or []
        items = []
        for it in rows_it:
            items.append({
                "id_detalle_devolucion": it[0],
                "id_detalle_venta": it[1],
                "cantidad": it[2],
                "condicion": it[3],
                "precio_unitario": float(it[4] or 0),
                "descuento_unitario": float(it[5] or 0),
                "monto_reembolso": float(it[6] or 0),
                "estado_item": it[7],
                "producto_nombre": it[8],
                "sku": it[9],
                "talla": it[10],
                "color": it[11],
                "imagen_url": it[12],
                "id_variante_cambio": it[13],
                "cantidad_cambio": it[14],
                "precio_unitario_cambio": float(it[15] or 0),
                "destino_inventario": it[16],
                "talla_cambio": it[17] if len(it) > 17 else None,
                "sku_cambio": it[18] if len(it) > 18 else None
            })

        cliente_nom = f"{row[11] or ''} {row[12] or ''}".strip() or "Cliente"
        revisor_nom = f"{row[21] or ''} {row[22] or ''}".strip() if row[21] else None

        return {
            "id_devolucion": row[0],
            "codigo_devolucion": row[1] or f"DEV-{row[0]}",
            "id_venta": row[2],
            "numero_venta": row[3],
            "total_venta": float(row[4] or 0),
            "fecha_venta": row[5].isoformat() if hasattr(row[5], 'isoformat') else str(row[5]),
            "tipo_venta": row[6],
            "id_empresa": row[7],
            "id_sucursal": row[8],
            "nombre_sucursal": row[9],
            "id_usuario_cliente": row[10],
            "cliente_nombre": cliente_nom,
            "cliente_correo": row[13],
            "tipo_devolucion": row[14],
            "motivo": row[15],
            "descripcion_cliente": row[16],
            "evidencia_url": row[17],
            "monto_reembolso": float(row[18] or 0),
            "estado": row[19],
            "id_usuario_revisor": row[20],
            "revisor_nombre": revisor_nom,
            "fecha_resolucion": row[23].isoformat() if row[23] and hasattr(row[23], 'isoformat') else str(row[23]) if row[23] else None,
            "observaciones_resolucion": row[24],
            "metodo_reembolso": row[25],
            "referencia_reembolso": row[26],
            "fecha_reembolso": row[27].isoformat() if row[27] and hasattr(row[27], 'isoformat') else str(row[27]) if row[27] else None,
            "fecha_devolucion": row[28].isoformat() if hasattr(row[28], 'isoformat') else str(row[28]),
            "tipo_resolucion": row[29],
            "id_sesion_caja": row[30],
            "diferencia_cambio": float(row[31] or 0),
            "dias_desde_compra": row[32],
            "cumple_politica": bool(row[33]),
            "excepcion_ley_453": bool(row[34]),
            "pago_origen": pago_info,
            "total_prendas": len(items),
            "items": items
        }
    finally:
        db.close_connection()

@atomic
def resolver_solicitud_devolucion(
    id_devolucion: int,
    id_usuario_revisor: int,
    id_empresa: int,
    nuevo_estado: str,
    observaciones: str,
    tipo_resolucion: Optional[str] = None
) -> Dict[str, Any]:
    """
    CU24W: Aprueba o rechaza una solicitud de devolución.
    Transiciones válidas:
      - SOLICITADA -> EN_REVISION, APROBADA, RECHAZADA
      - EN_REVISION -> APROBADA, RECHAZADA
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        _require_structure(db,schema)

        sql_dev = f"""
            SELECT id_devolucion, id_empresa, estado
            FROM {schema}.t_devolucion
            WHERE id_devolucion = %s
            FOR UPDATE;
        """
        row = db.execute_query(sql_dev, (id_devolucion,), fetchone=True)
        if not row:
            db.rollback()
            raise HTTPException(status_code=404, detail="Devolución no encontrada.")

        v_id, v_emp, v_est_act = row
        if v_emp != id_empresa:
            db.rollback()
            raise HTTPException(status_code=403, detail="No tiene autorización sobre la empresa de esta devolución.")

        estado_act = (v_est_act or "").strip().upper()
        estado_dest = (nuevo_estado or "").strip().upper()

        transiciones_validas = {
            "SOLICITADA": ["EN_REVISION", "APROBADA", "RECHAZADA"],
            "EN_REVISION": ["APROBADA", "RECHAZADA"]
        }

        if estado_dest not in transiciones_validas.get(estado_act, []):
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Transición inválida: no se puede pasar de '{estado_act}' a '{estado_dest}'."
            )

        # Si es aprobada, pasa a PENDIENTE_RECEPCION
        estado_asignar = "PENDIENTE_RECEPCION" if estado_dest == "APROBADA" else estado_dest

        sql_upd = f"""
            UPDATE {schema}.t_devolucion
            SET estado = %s,
                id_usuario_revisor = %s,
                observaciones_resolucion = %s,
                tipo_resolucion = COALESCE(%s, tipo_resolucion),
                fecha_resolucion = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id_devolucion = %s;
        """
        db.execute_query(sql_upd, (estado_asignar, id_usuario_revisor, observaciones, tipo_resolucion, id_devolucion))
        db.commit()

        return {
            "success": True,
            "id_devolucion": id_devolucion,
            "estado_anterior": estado_act,
            "nuevo_estado": estado_asignar,
            "tipo_resolucion": tipo_resolucion,
            "observaciones": observaciones
        }
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close_connection()

@atomic
def registrar_recepcion_prendas(
    id_devolucion: int,
    id_usuario_receptor: int,
    id_empresa: int,
    id_sucursal_recepcion: int,
    observaciones: Optional[str],
    items_inspeccionados: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    CU24W: Registra la recepción física de las prendas inspeccionadas.
    Ajusta el inventario vendible solo para unidades marcadas como REVENDIBLE.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        _require_structure(db,schema)

        sql_dev = f"""
            SELECT id_devolucion, id_empresa, id_sucursal, codigo_devolucion, estado, tipo_resolucion, id_venta, id_usuario, monto_reembolso
            FROM {schema}.t_devolucion
            WHERE id_devolucion = %s
            FOR UPDATE;
        """
        row = db.execute_query(sql_dev, (id_devolucion,), fetchone=True)
        if not row:
            db.rollback()
            raise HTTPException(status_code=404, detail="Devolución no encontrada.")

        d_id, d_emp, d_suc_orig, d_cod, d_estado, d_tipo_res, d_venta, d_usuario, d_monto = row
        tipo_res_act = (d_tipo_res or 'REEMBOLSO_DINERO').strip().upper()
        if d_emp != id_empresa:
            db.rollback()
            raise HTTPException(status_code=403, detail="No tiene permisos sobre la empresa de esta devolución.")

        estado_act = (d_estado or "").strip().upper()
        sucursal_destino = id_sucursal_recepcion or d_suc_orig
        _validate_branch(db,schema,sucursal_destino,d_emp)

        # Obtener detalles de la devolución con sus variantes
        sql_det = f"""
            SELECT dd.id_detalle_devolucion, dd.id_detalle_venta, dd.cantidad, dv.id_variante,dd.condicion,dd.estado_item,dv.id_venta
            FROM {schema}.t_detalle_devolucion dd
            JOIN {schema}.t_detalle_venta dv ON dv.id_detalle_venta = dd.id_detalle_venta
            WHERE dd.id_devolucion = %s
            FOR UPDATE;
        """
        rows_det = db.execute_query(sql_det, (id_devolucion,), fetchall=True) or []
        mapa_det = {r[0]: r for r in rows_det}

        if not items_inspeccionados:
            db.rollback()
            raise HTTPException(status_code=400, detail="Debe detallar los artículos inspeccionados.")

        _unique_items(items_inspeccionados,'id_detalle_devolucion')
        if set(mapa_det) != {int(it['id_detalle_devolucion']) for it in items_inspeccionados}:
            raise HTTPException(409,'PARTIAL_RECEIPT_REQUIRES_MIGRATION: debe recibir todas las lineas completas.')
        sale = db.execute_query(f'SELECT id_venta FROM {schema}.t_devolucion WHERE id_devolucion=%s', (id_devolucion,), fetchone=True)[0]
        for it in items_inspeccionados:
            stored = mapa_det[int(it['id_detalle_devolucion'])]
            if stored[6] != sale:
                raise HTTPException(409,'RETURN_RECONCILIATION_REQUIRED: detalle de venta ajeno.')
            if int(it.get('cantidad_recibida',0)) != int(stored[2]):
                raise HTTPException(409,'PARTIAL_RECEIPT_REQUIRES_MIGRATION: cantidad parcial no persistible en 005.')
            condicion_chk = it.get('condicion','REVENDIBLE').upper()
            condiciones_validas = ('REVENDIBLE','NUEVO','DEFECTUOSO','CON_DEFECTO','DAÑADO','DANADO','NO_REVENDIBLE','EN_INSPECCION')
            if condicion_chk not in condiciones_validas:
                raise HTTPException(400, f"Condicion invalida '{condicion_chk}'.")
        if estado_act in ('PENDIENTE_REEMBOLSO', 'RECIBIDA', 'PENDIENTE_ENTREGA', 'COMPLETADA'):
            evidence = db.execute_query(f'''SELECT datos_nuevos FROM {schema}.t_bitacora WHERE entidad='t_devolucion' AND id_entidad=%s AND accion='RECEPCION_PRENDAS_DEVOLUCION' ORDER BY id_bitacora DESC LIMIT 1''', (str(id_devolucion),), fetchone=True)
            received = evidence[0] if evidence else {}
            def canonical(items):
                return sorted((int(i['id_detalle_devolucion']),int(i['cantidad_recibida']),i.get('condicion','REVENDIBLE').upper()) for i in items)
            if received.get('id_sucursal') == sucursal_destino and canonical(received.get('items_recibidos',[])) == canonical(items_inspeccionados):
                return dict(success=True,id_devolucion=id_devolucion,nuevo_estado=estado_act,idempotent_replay=True)
            raise HTTPException(409,'Recepcion ya registrada; concilie la evidencia existente.')
        if estado_act not in ('APROBADA', 'PENDIENTE_RECEPCION'):
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"No se pueden recibir prendas de una devolución en estado '{estado_act}' (debe estar APROBADA o PENDIENTE_RECEPCION)."
            )

        lock_items(db,schema,sucursal_destino,[dict(id_variante=r[3],cantidad=r[2]) for r in rows_det],id_empresa,allow_missing=True)

        for item in items_inspeccionados:
            id_det_dev = item.get("id_detalle_devolucion")
            cant_rec = int(item.get("cantidad_recibida", 0))
            condicion = (item.get("condicion") or "REVENDIBLE").strip().upper()

            if id_det_dev not in mapa_det:
                db.rollback()
                raise HTTPException(status_code=400, detail=f"Detalle {id_det_dev} no pertenece a esta devolución.")

            det_info = mapa_det[id_det_dev]
            cant_solicitada = int(det_info[2])
            id_variante = det_info[3]

            if cant_rec <= 0 or cant_rec > cant_solicitada:
                db.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"Cantidad recibida ({cant_rec}) inválida para ítem {id_det_dev} (solicitadas: {cant_solicitada})."
                )

            if condicion in ("REVENDIBLE", "NUEVO"):
                destino_inv = "STOCK_DISPONIBLE"
                _reincorporar_stock_inventario(
                    db=db,
                    schema=schema,
                    id_sucursal=sucursal_destino,
                    id_variante=id_variante,
                    cantidad=cant_rec,
                    id_usuario=id_usuario_receptor,
                    motivo_log=f"Recepción devolución {d_cod}"
                )
            elif condicion in ("DEFECTUOSO", "CON_DEFECTO"):
                destino_inv = "CUARENTENA_DEFECTO"
                _registrar_movimiento_no_vendible(
                    db=db,
                    schema=schema,
                    id_sucursal=sucursal_destino,
                    id_variante=id_variante,
                    cantidad=cant_rec,
                    id_usuario=id_usuario_receptor,
                    tipo_movimiento="CUARENTENA_DEFECTO",
                    motivo_log=f"Prenda retenida por defecto en devolución {d_cod}"
                )
            elif condicion in ("DAÑADO", "DANADO", "NO_REVENDIBLE"):
                destino_inv = "MERMA_DANO"
                _registrar_movimiento_no_vendible(
                    db=db,
                    schema=schema,
                    id_sucursal=sucursal_destino,
                    id_variante=id_variante,
                    cantidad=cant_rec,
                    id_usuario=id_usuario_receptor,
                    tipo_movimiento="MERMA_DEVOLUCION",
                    motivo_log=f"Baja por daño en devolución {d_cod}"
                )
            else:
                destino_inv = "EN_INSPECCION"

            # Actualizar detalle de devolución con condicion y destino_inventario
            sql_upd_det = f"""
                UPDATE {schema}.t_detalle_devolucion
                SET condicion = %s,
                    destino_inventario = %s,
                    estado_item = 'RECIBIDO'
                WHERE id_detalle_devolucion = %s;
            """
            db.execute_query(sql_upd_det, (condicion, destino_inv, id_det_dev))

        # Determinar nuevo estado y mensaje según tipo de resolución
        if tipo_res_act == 'CAMBIO_PRENDA':
            nuevo_estado = 'PENDIENTE_ENTREGA'
            mensaje_res = "Prendas recibidas e inspeccionadas. Pendiente entrega de prenda de cambio."
        elif tipo_res_act == 'SALDO_A_FAVOR':
            monto_float = float(d_monto or 0.0)
            row_cli = db.execute_query(f"SELECT id_cliente FROM {schema}.t_venta WHERE id_venta = %s", (d_venta,), fetchone=True)
            id_cliente = row_cli[0] if (row_cli and row_cli[0]) else None
            if not id_cliente:
                row_cli2 = db.execute_query(f"SELECT id_cliente FROM {schema}.t_cliente WHERE id_usuario = %s ORDER BY id_cliente LIMIT 1", (d_usuario,), fetchone=True)
                id_cliente = row_cli2[0] if (row_cli2 and row_cli2[0]) else None
            if not id_cliente:
                row_ins_cli = db.execute_query(f"INSERT INTO {schema}.t_cliente (id_usuario, fecha_registro) VALUES (%s, CURRENT_TIMESTAMP) RETURNING id_cliente", (d_usuario,), fetchone=True)
                id_cliente = row_ins_cli[0]

            cod_credito = f"CRED-{id_empresa}-{uuid.uuid4().hex[:8].upper()}"
            sql_ins_cred = f"""
                INSERT INTO {schema}.t_credito_cliente (
                    id_cliente, id_empresa, id_devolucion, codigo_credito,
                    monto_inicial, saldo_disponible, fecha_expiracion, estado
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP + interval '180 days', 'ACTIVO'
                ) RETURNING id_credito;
            """
            row_cred = db.execute_query(sql_ins_cred, (id_cliente, id_empresa, id_devolucion, cod_credito, monto_float, monto_float), fetchone=True)
            if row_cred:
                id_cred = row_cred[0]
                sql_mov = f"""
                    INSERT INTO {schema}.t_movimiento_credito (
                        id_credito, tipo_movimiento, monto, saldo_anterior, saldo_nuevo, id_usuario, motivo
                    ) VALUES (
                        %s, 'EMISION', %s, 0.00, %s, %s, %s
                    );
                """
                db.execute_query(sql_mov, (id_cred, monto_float, monto_float, id_usuario_receptor, f"Crédito emitido por devolución {d_cod}"))

            nuevo_estado = 'COMPLETADA'
            mensaje_res = f"Prendas recibidas. Crédito en tienda emitido exitosamente ({cod_credito})."
            db.execute_query(f"""
                UPDATE {schema}.t_devolucion
                SET metodo_reembolso = 'SALDO_A_FAVOR',
                    referencia_reembolso = %s,
                    fecha_reembolso = CURRENT_TIMESTAMP
                WHERE id_devolucion = %s;
            """, (cod_credito, id_devolucion))
        else:
            nuevo_estado = 'PENDIENTE_REEMBOLSO'
            mensaje_res = "Prendas recibidas e inspeccionadas. Pendiente liquidación de reembolso."

        # Actualizar estado de la devolución
        sql_upd_dev = f"""
            UPDATE {schema}.t_devolucion
            SET estado = %s,
                observaciones_resolucion = COALESCE(observaciones_resolucion, '') || ' | ' || %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id_devolucion = %s;
        """
        db.execute_query(sql_upd_dev, (nuevo_estado, observaciones or mensaje_res, id_devolucion))
        db.commit()

        return {
            "success": True,
            "id_devolucion": id_devolucion,
            "nuevo_estado": nuevo_estado,
            "tipo_resolucion": tipo_res_act,
            "items_recibidos": items_inspeccionados,
            "id_usuario_receptor": id_usuario_receptor,
            "id_sucursal": sucursal_destino,
            "mensaje": mensaje_res
        }
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close_connection()

@atomic
def registrar_reembolso_financiero(
    id_devolucion: int,
    id_usuario_responsable: int,
    id_empresa: int,
    metodo_reembolso: str,
    referencia_reembolso: str,
    observaciones: Optional[str] = None,
    tipo_resolucion: Optional[str] = None,
    id_sesion_caja: Optional[int] = None
) -> Dict[str, Any]:
    """
    CU24W: Registra formalmente la liquidación de la devolución al cliente.
    Soporta los tres resultados:
      1. REEMBOLSO_DINERO: Pasarela PayPal (llamada a API REST), Transferencia bancaria o Efectivo de caja.
      2. SALDO_A_FAVOR: Emisión de crédito en tienda (t_credito_cliente) con saldo acumulable.
      3. CAMBIO_PRENDA: Confirmación del cambio de prenda y cierre financiero.
    Actualiza la devolución a estado 'COMPLETADA'.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        _require_structure(db,schema)

        sql_dev = f"""
            SELECT id_devolucion, id_empresa, monto_reembolso, estado, codigo_devolucion, id_venta, id_usuario, tipo_resolucion
            FROM {schema}.t_devolucion
            WHERE id_devolucion = %s
            FOR UPDATE;
        """
        row = db.execute_query(sql_dev, (id_devolucion,), fetchone=True)
        if not row:
            db.rollback()
            raise HTTPException(status_code=404, detail="Devolución no encontrada.")

        d_id, d_emp, d_monto, d_estado, d_cod, d_venta, d_usuario, d_tipo_res = row
        if d_emp != id_empresa:
            db.rollback()
            raise HTTPException(status_code=403, detail="No tiene permisos sobre la empresa de esta devolución.")

        estado_act = (d_estado or "").strip().upper()
        if estado_act not in ('PENDIENTE_REEMBOLSO', 'RECIBIDA', 'PENDIENTE_ENTREGA'):
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"La devolución debe encontrarse en estado 'PENDIENTE_REEMBOLSO', 'PENDIENTE_ENTREGA' o 'RECIBIDA' (estado actual: '{estado_act}')."
            )

        resolucion_final = (tipo_resolucion or d_tipo_res or 'REEMBOLSO_DINERO').strip().upper()
        monto_float = float(d_monto or 0.0)

        # ---------------------------------------------------------------------
        # 1. RESOLUCIÓN: SALDO A FAVOR / CRÉDITO EN TIENDA
        # ---------------------------------------------------------------------
        if resolucion_final == 'SALDO_A_FAVOR':
            row_cli = db.execute_query(f"SELECT id_cliente FROM {schema}.t_venta WHERE id_venta = %s", (d_venta,), fetchone=True)
            id_cliente = row_cli[0] if (row_cli and row_cli[0]) else None
            if not id_cliente:
                row_cli2 = db.execute_query(f"SELECT id_cliente FROM {schema}.t_cliente WHERE id_usuario = %s ORDER BY id_cliente LIMIT 1", (d_usuario,), fetchone=True)
                id_cliente = row_cli2[0] if (row_cli2 and row_cli2[0]) else None

            if not id_cliente:
                row_ins_cli = db.execute_query(f"INSERT INTO {schema}.t_cliente (id_usuario, fecha_registro) VALUES (%s, CURRENT_TIMESTAMP) RETURNING id_cliente", (d_usuario,), fetchone=True)
                id_cliente = row_ins_cli[0]

            cod_credito = f"CRED-{id_empresa}-{uuid.uuid4().hex[:8].upper()}"
            sql_ins_cred = f"""
                INSERT INTO {schema}.t_credito_cliente (
                    id_cliente, id_empresa, id_devolucion, codigo_credito,
                    monto_inicial, saldo_disponible, fecha_expiracion, estado
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP + interval '180 days', 'ACTIVO'
                ) RETURNING id_credito;
            """
            row_cred = db.execute_query(sql_ins_cred, (id_cliente, id_empresa, id_devolucion, cod_credito, monto_float, monto_float), fetchone=True)
            if row_cred:
                id_cred = row_cred[0]
                sql_mov = f"""
                    INSERT INTO {schema}.t_movimiento_credito (
                        id_credito, tipo_movimiento, monto, saldo_anterior, saldo_nuevo, id_usuario, motivo
                    ) VALUES (
                        %s, 'EMISION', %s, 0.00, %s, %s, %s
                    );
                """
                db.execute_query(sql_mov, (id_cred, monto_float, monto_float, id_usuario_responsable, f"Crédito emitido por devolución {d_cod}"))

            metodo_reembolso = 'SALDO_A_FAVOR'
            referencia_reembolso = cod_credito

        # ---------------------------------------------------------------------
        # 2. RESOLUCIÓN: REEMBOLSO MONETARIO DIRECTO
        # ---------------------------------------------------------------------
        elif resolucion_final == 'REEMBOLSO_DINERO':
            if not metodo_reembolso or not referencia_reembolso:
                db.rollback()
                raise HTTPException(status_code=400, detail="Debe proporcionar el método de pago y número de comprobante/referencia del reembolso.")

            metodo_norm = (metodo_reembolso or "").strip().upper()
            if metodo_norm == 'PAYPAL':
                # Buscar transacción original de PayPal
                sql_pago_pp = f"""
                    SELECT p.codigo_transaccion, p.monto
                    FROM {schema}.t_pago p
                    JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p.id_metodo_pago
                    WHERE p.id_venta = %s AND (mp.tipo = %s OR p.codigo_transaccion LIKE %s OR p.codigo_transaccion LIKE %s)
                    ORDER BY p.id_pago DESC LIMIT 1;
                """
                p_row = db.execute_query(sql_pago_pp, (d_venta, 'PAYPAL', 'CAPTURE-%', 'ORD-%'), fetchone=True)
                if p_row and p_row[0]:
                    capture_id = p_row[0]
                    try:
                        from app.modules.ecommerce.services.paypal_service import reembolsar_captura_paypal, TASA_CAMBIO_BOB_USD
                        monto_usd = round(monto_float / TASA_CAMBIO_BOB_USD, 2)
                        res_pp = reembolsar_captura_paypal(capture_id=capture_id, monto_usd=monto_usd, nota=f"Reembolso devolución {d_cod}")
                        if res_pp and res_pp.get("success"):
                            ref_pp = res_pp.get("refund_id") or res_pp.get("id") or capture_id
                            referencia_reembolso = f"PAYPAL-REFUND-{ref_pp}"
                        else:
                            referencia_reembolso = referencia_reembolso or f"PAYPAL-SIM-{capture_id}"
                    except Exception as pe:
                        # Si es entorno sandbox local o captura simulada, persistir referencia estructurada
                        referencia_reembolso = referencia_reembolso or f"PAYPAL-SIM-{capture_id}"
                else:
                    referencia_reembolso = referencia_reembolso or f"PAYPAL-DIRECTO-{uuid.uuid4().hex[:8].upper()}"

        # ---------------------------------------------------------------------
        # 3. RESOLUCIÓN: CAMBIO DE PRENDA
        # ---------------------------------------------------------------------
        elif resolucion_final == 'CAMBIO_PRENDA':
            metodo_reembolso = metodo_reembolso or 'ENTREGA_PRENDA_CAMBIO'
            referencia_reembolso = referencia_reembolso or f"CAMBIO-{d_cod}"

            # Descontar stock de la prenda o talla de reemplazo
            sql_det_cambio = f"""
                SELECT dd.id_variante_cambio, COALESCE(dd.cantidad_cambio, dd.cantidad, 1)
                FROM {schema}.t_detalle_devolucion dd
                WHERE dd.id_devolucion = %s AND dd.id_variante_cambio IS NOT NULL;
            """
            rows_cambio = db.execute_query(sql_det_cambio, (id_devolucion,), fetchall=True) or []
            row_suc = db.execute_query(f"SELECT id_sucursal FROM {schema}.t_devolucion WHERE id_devolucion = %s", (id_devolucion,), fetchone=True)
            dev_suc = row_suc[0] if row_suc else 1

            for rc in rows_cambio:
                var_cambio_id = rc[0]
                cant_cambio = int(rc[1] or 1)
                if var_cambio_id and cant_cambio > 0:
                    sql_stock_desc = f"""
                        UPDATE {schema}.t_inventario
                        SET stock_actual = stock_actual - %s,
                            stock_disponible = stock_disponible - %s,
                            fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE id_sucursal = %s AND id_variante = %s AND stock_disponible >= %s;
                    """
                    db.execute_query(sql_stock_desc, (cant_cambio, cant_cambio, dev_suc, var_cambio_id, cant_cambio))
                    sql_mov = f"""
                        INSERT INTO {schema}.t_movimiento_inventario (
                            id_inventario, id_usuario, tipo_movimiento, cantidad, motivo, fecha_movimiento
                        ) SELECT id_inventario, %s, 'SALIDA_CAMBIO_PRENDA', %s, 'Entrega de prenda en cambio de talla', CURRENT_TIMESTAMP
                        FROM {schema}.t_inventario WHERE id_sucursal = %s AND id_variante = %s;
                    """
                    db.execute_query(sql_mov, (id_usuario_responsable, cant_cambio, dev_suc, var_cambio_id))

        # ---------------------------------------------------------------------
        # 4. ACTUALIZACIÓN FINAL EN t_devolucion
        # ---------------------------------------------------------------------
        sql_upd = f"""
            UPDATE {schema}.t_devolucion
            SET estado = 'COMPLETADA',
                fecha_reembolso = CURRENT_TIMESTAMP,
                metodo_reembolso = %s,
                referencia_reembolso = %s,
                id_sesion_caja = %s,
                tipo_resolucion = %s,
                observaciones_resolucion = COALESCE(observaciones_resolucion, '') || ' | ' || %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id_devolucion = %s;
        """
        db.execute_query(sql_upd, (
            metodo_reembolso or 'EFECTIVO',
            referencia_reembolso or 'REF-DIRECTA',
            id_sesion_caja,
            resolucion_final,
            observaciones or f"Liquidación completada exitosamente como {resolucion_final}.",
            id_devolucion
        ))
        db.commit()

        return {
            "success": True,
            "id_devolucion": id_devolucion,
            "codigo_devolucion": d_cod,
            "monto_reembolsado": monto_float,
            "nuevo_estado": "COMPLETADA",
            "tipo_resolucion": resolucion_final,
            "metodo_reembolso": metodo_reembolso,
            "referencia_reembolso": referencia_reembolso,
            "id_sesion_caja": id_sesion_caja,
            "fecha_reembolso": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close_connection()
