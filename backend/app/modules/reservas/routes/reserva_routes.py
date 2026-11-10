from typing import Optional, List
from datetime import datetime
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from pydantic import BaseModel, Field
from app.core.security import verificar_token
from app.modules.reservas.repos import reserva_repos
from app.modules.catalogo.repos import catalogo_repos
from app.core.postgres import PostgreSQL
from app.core.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reservas", tags=["Reservas y Citas en Sucursal"])

class ItemReservaDTO(BaseModel):
    id_variante: int = Field(..., gt=0, description="ID de la variante (talla + color)")
    cantidad: int = Field(1, gt=0, description="Cantidad de prendas a apartar")

class CrearReservaDTO(BaseModel):
    id_sucursal: int = Field(..., gt=0, description="ID de la sucursal física seleccionada")
    fecha_hora_visita: str = Field(..., min_length=10, description="Fecha y hora de visita programada (YYYY-MM-DD HH:MM)")
    observaciones: Optional[str] = Field(None, max_length=500, description="Observaciones o notas para el asesor de tienda")
    items: List[ItemReservaDTO] = Field(..., min_length=1, description="Listado de prendas y variantes a reservar")
    id_empresa: Optional[int] = Field(None, description="Parámetro opcional; el backend valida y resuelve el Tenant real")
    con_pago: Optional[bool] = Field(False, description="True si el cliente decidió pagar online anticipadamente")
    monto_pagado: Optional[float] = Field(0.0, ge=0.0, description="Monto abonado online")

class CancelarReservaDTO(BaseModel):
    motivo: Optional[str] = Field("Cancelación solicitada por el cliente.", max_length=300, description="Motivo de la cancelación")

def _enviar_correo_reserva_background(id_reserva: int):
    """
    Tarea en background para generar el PDF de reserva y enviarlo al correo del cliente.
    """
    try:
        from app.modules.pos.services import comprobante_service
        from app.shared.email_service import enviar_correo_reserva

        db = PostgreSQL()
        db.create_connection()
        schema = Config.SCHEMA or 'comercio'
        try:
            q_res = f"""
                SELECT 
                    r.codigo_reserva,
                    s.nombre AS sucursal_nombre,
                    s.direccion AS sucursal_direccion,
                    r.fecha_hora_visita,
                    COALESCE(emp.nombre_empresa, 'Tienda Oficial') AS empresa_nombre,
                    COALESCE(u.nombre, 'Cliente') AS cliente_nombre,
                    COALESCE(u.apellido, '') AS cliente_apellido,
                    COALESCE(u.correo, '') AS cliente_correo,
                    COALESCE(r.con_pago, false) AS con_pago,
                    COALESCE(r.monto_pagado, 0.0) AS monto_pagado
                FROM {schema}.t_reserva r
                JOIN {schema}.t_sucursal s ON s.id_sucursal = r.id_sucursal
                LEFT JOIN {schema}.empresa emp ON emp.id_empresa = s.id_empresa
                JOIN {schema}.t_cliente c ON c.id_cliente = r.id_cliente
                LEFT JOIN {schema}.t_usuario u ON u.id_usuario = c.id_usuario
                WHERE r.id_reserva = %s;
            """
            row = db.execute_query(q_res, (id_reserva,), fetchone=True)
            if not row or not row[7] or '@' not in row[7]:
                return

            q_items = f"""
                SELECT p.nombre, t.nombre, col.nombre, dr.cantidad
                FROM {schema}.t_detalle_reserva dr
                JOIN {schema}.t_producto_talla_color v ON v.id_variante = dr.id_variante
                JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
                JOIN {schema}.t_talla t ON t.id_talla = v.id_talla
                JOIN {schema}.t_color col ON col.id_color = v.id_color
                WHERE dr.id_reserva = %s;
            """
            items_raw = db.execute_query(q_items, (id_reserva,), fetchall=True) or []
            prendas = [{"producto_nombre": it[0], "talla_nombre": it[1], "color_nombre": it[2], "cantidad": it[3]} for it in items_raw]

            fecha_str = row[3].strftime('%d/%m/%Y %H:%M') if isinstance(row[3], datetime) else str(row[3])
            pdf_bytes = comprobante_service.generar_pdf_reserva(id_reserva)

            enviar_correo_reserva(
                destinatario_email=row[7],
                destinatario_nombre=f"{row[5]} {row[6]}".strip(),
                codigo_reserva=row[0],
                nombre_tienda=row[4],
                nombre_sucursal=row[1],
                direccion_sucursal=row[2],
                fecha_hora_visita=fecha_str,
                con_pago=bool(row[8]),
                monto_pagado=float(row[9]),
                prendas=prendas,
                pdf_bytes=pdf_bytes,
                nombre_archivo=f"Reserva_{row[0]}.pdf"
            )
        finally:
            db.close_connection()
    except Exception as e:
        logger.error(f"[RESERVA BACKGROUND EMAIL ERROR] {e}")

def _resolver_empresa_de_sucursal(id_sucursal: int) -> Optional[int]:
    """Obtiene el ID de la empresa dueña de la sucursal física."""
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        cur = db.conn.cursor()
        cur.execute(f"SELECT id_empresa FROM {schema}.t_sucursal WHERE id_sucursal = %s;", (id_sucursal,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        db.close_connection()

def _resolver_id_empresa_segura(token_data: dict, id_empresa_param: Optional[int] = None, id_sucursal: Optional[int] = None) -> int:
    """
    Resuelve y valida el Tenant sin confiar ciegamente en id_empresa enviado por el frontend.
    1. Si se proporciona id_sucursal, la empresa se determina directamente de la sucursal en BD.
    2. Si no hay sucursal, se valida id_empresa_param o el token claim.
    3. Fallback para clientes globales al tenant público activo.
    """
    from app.core.commerce_tenant import resolver_empresa_compra
    empresa_sucursal = _resolver_empresa_de_sucursal(id_sucursal) if id_sucursal else None
    if id_sucursal and empresa_sucursal is None:
        raise HTTPException(404, detail='Sucursal inexistente.')
    return resolver_empresa_compra(token_data, id_empresa_param, empresa_sucursal, id_sucursal)

@router.post('', status_code=status.HTTP_201_CREATED, summary="Crear una reserva de prendas para visita en sucursal")
@router.post('/', status_code=status.HTTP_201_CREATED, summary="Crear una reserva de prendas para visita en sucursal")
def crear_reserva(
    body: CrearReservaDTO,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        if not id_usuario:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no válida o usuario no identificado.")

        # Seguridad de pagos: Deshabilitado temporalmente pago online anticipado
        if body.con_pago or (body.monto_pagado and body.monto_pagado > 0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El pago anticipado online de reservas no se encuentra habilitado por el momento. Las prendas apartadas deben abonarse directamente en el mostrador tras probárselas."
            )

        empresa_id = _resolver_id_empresa_segura(token_data, body.id_empresa, body.id_sucursal)

        from app.modules.saas.services.saas_services import exigir_vigencia
        exigir_vigencia(empresa_id)
        datos = body.model_dump()
        reserva = reserva_repos.crear_reserva(
            id_usuario=id_usuario,
            id_empresa=empresa_id,
            datos=datos
        )

        # Enviar correo de confirmación de cita en background
        if reserva.get("id_reserva"):
            background_tasks.add_task(_enviar_correo_reserva_background, reserva["id_reserva"])

        return {
            "success": True,
            "message": f"Reserva {reserva['codigo_reserva']} generada exitosamente. Tu prenda ha sido apartada.",
            "data": reserva
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al generar la reserva: {str(e)}"
        )

@router.get('/mis-reservas', summary="Listar las reservas del cliente autenticado")
def obtener_mis_reservas(
    id_empresa: Optional[int] = Query(None, description="Opcional: ID de la empresa"),
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        if not id_usuario:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autenticado.")

        reservas = reserva_repos.obtener_mis_reservas(id_usuario, id_empresa)

        return {
            "success": True,
            "data": reservas
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener tus reservas: {str(e)}"
        )

@router.get('/{id_reserva}', summary="Consultar detalle de una reserva específica")
def consultar_detalle_reserva(
    id_reserva: int,
    id_empresa: Optional[int] = Query(None, description="Opcional: ID de la empresa"),
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        rol = (token_data.get('nombre_rol') or '').upper()
        es_admin = rol in ('ADMINISTRADOR', 'ADMINISTRADOR_TIENDA', 'ENCARGADO_SUCURSAL')

        empresa_id = _resolver_id_empresa_segura(token_data, id_empresa)
        reserva = reserva_repos.obtener_detalle_reserva(id_reserva, id_usuario, empresa_id, es_admin)

        if not reserva:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La reserva solicitada no existe, no pertenece a tu cuenta o corresponde a otra tienda."
            )

        return {
            "success": True,
            "data": reserva
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar el detalle de la reserva: {str(e)}"
        )

@router.post('/{id_reserva}/cancelar', summary="Cancelar una reserva activa y liberar su inventario")
def cancelar_reserva(
    id_reserva: int,
    body: Optional[CancelarReservaDTO] = None,
    id_empresa: Optional[int] = Query(None, description="Opcional: ID de la empresa"),
    token_data: dict = Depends(verificar_token)
):
    try:
        id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
        rol = (token_data.get('nombre_rol') or '').upper()
        es_admin = rol in ('ADMINISTRADOR', 'ADMINISTRADOR_TIENDA', 'ENCARGADO_SUCURSAL')

        empresa_id = _resolver_id_empresa_segura(token_data, id_empresa)
        motivo = body.motivo if body and body.motivo else "Cancelación solicitada por el cliente."

        resultado = reserva_repos.cancelar_reserva(
            id_reserva=id_reserva,
            id_usuario=id_usuario,
            id_empresa=empresa_id,
            motivo=motivo,
            es_admin=es_admin
        )

        return {
            "success": True,
            "data": resultado
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cancelar la reserva: {str(e)}"
        )

@router.post('/expirar-vencidas', summary="Expira reservas vencidas y libera inventario al stock disponible")
def expirar_reservas_vencidas_endpoint(
    tolerancia_horas: int = Query(12, ge=1, le=168, description="Ventana de retención en boutique (horas)"),
    tolerancia_llegada_minutos: int = Query(60, ge=15, le=240, description="Minutos de cortesía para llegada a la cita"),
    id_empresa: Optional[int] = Query(None, description="Opcional: ID de la empresa a filtrar"),
    token_data: dict = Depends(verificar_token)
):
    try:
        empresa_id = _resolver_id_empresa_segura(token_data, id_empresa) if id_empresa else None
        res = reserva_repos.expirar_reservas_vencidas(
            id_empresa=empresa_id,
            tolerancia_horas=tolerancia_horas,
            tolerancia_llegada_minutos=tolerancia_llegada_minutos
        )
        return {
            "success": True,
            "message": f"Se procesaron {res['reservas_expiradas']} reservas vencidas y se liberaron {res['prendas_liberadas']} prendas al inventario disponible.",
            "data": res
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al ejecutar expiración automática de reservas: {str(e)}"
        )
