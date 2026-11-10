import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import verificar_token, tiene_permiso
from app.modules.pos.repos import caja_pago_repos
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/caja/pagos", tags=["W28 - Procesar Pago en Caja"])

class DatosFacturacionSnapshotDTO(BaseModel):
    razon_social: Optional[str] = Field(None, max_length=150)
    nit_ci: Optional[str] = Field(None, max_length=50)
    correo_facturacion: Optional[str] = Field(None, max_length=150)
    tipo_documento: Optional[str] = Field("COMPROBANTE", max_length=30)

class ProcesarPagoCajaDTO(BaseModel):
    id_venta: int = Field(..., gt=0, description="ID de la venta creada por W24")
    id_metodo_pago: int = Field(..., gt=0, description="ID de t_metodo_pago (Efectivo, Tarjeta, QR)")
    monto_recibido: Optional[float] = Field(None, ge=0.0, description="Monto entregado en efectivo por el comprador")
    referencia_transaccion: Optional[str] = Field(None, max_length=100, description="Código de comprobante POS o voucher")
    referencia_externa: Optional[str] = Field(None, max_length=100, description="Alias para referencia de voucher")
    razon_social: Optional[str] = Field(None, max_length=150)
    nit_ci: Optional[str] = Field(None, max_length=50)
    correo_facturacion: Optional[str] = Field(None, max_length=150)
    tipo_documento: Optional[str] = Field(None, max_length=30)
    datos_facturacion: Optional[DatosFacturacionSnapshotDTO] = Field(None, description="Datos opcionales para facturación de la venta")
    id_sucursal: Optional[int] = Field(None, gt=0)
    desglose_recibido: Optional[List[Dict[str, Any]]] = Field(None, description="Desglose de billetes y monedas entregados por el comprador")
    desglose_cambio: Optional[List[Dict[str, Any]]] = Field(None, description="Desglose de billetes y monedas entregados como cambio")

def _verificar_acceso_caja_pago(token_data: dict) -> None:
    if any(tiene_permiso(token_data, codigo) for codigo in ("pos.cobrar", "pos.vender", "caja.abrir", "caja.ver")):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acceso restringido. No tienes permisos para cobrar ventas en caja."
    )

@router.get('/metodos', summary="W28: Listar métodos de pago habilitados para cobro en caja")
def listar_metodos_pago(token_data: dict = Depends(verificar_token)):
    _verificar_acceso_caja_pago(token_data)
    try:
        metodos = caja_pago_repos.obtener_metodos_pago_activos()
        return {
            "success": True,
            "metodos": metodos,
            "data": metodos
        }
    except Exception as e:
        logger.error(f"[METODOS PAGO ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get('/venta/{id_venta}', summary="W28: Validar y consultar venta para cobro en caja")
def validar_venta_cobro(
    id_venta: int,
    id_sucursal: Optional[int] = Query(None),
    token_data: dict = Depends(verificar_token)
):
    _verificar_acceso_caja_pago(token_data)
    try:
        id_usuario = token_data.get("nro_usuario") or token_data.get("id_usuario")
        id_empresa = token_data.get("id_empresa")
        sucursales = token_data.get("sucursales", [])
        id_suc_efectiva = id_sucursal or (sucursales[0] if sucursales else None)

        venta = caja_pago_repos.validar_venta_para_pago_caja(
            id_venta=id_venta,
            id_usuario=id_usuario,
            id_sucursal=id_suc_efectiva,
            id_empresa=id_empresa
        )
        return {
            "success": True,
            "venta": venta,
            "data": venta
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"[VENTA PARA PAGO ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post('/procesar', summary="W28: Registrar pago en caja y actualizar venta a PAGADO")
def procesar_pago_caja(
    body: ProcesarPagoCajaDTO,
    token_data: dict = Depends(verificar_token)
):
    _verificar_acceso_caja_pago(token_data)
    try:
        id_usuario = token_data.get("nro_usuario") or token_data.get("id_usuario")
        id_empresa = token_data.get("id_empresa")
        sucursales = token_data.get("sucursales", [])
        id_suc_efectiva = body.id_sucursal or (sucursales[0] if sucursales else None)

        datos_fac_dict = {}
        if body.datos_facturacion:
            datos_fac_dict.update({k: v for k, v in body.datos_facturacion.dict().items() if v is not None})
        if body.razon_social is not None:
            datos_fac_dict["razon_social"] = body.razon_social
        if body.nit_ci is not None:
            datos_fac_dict["nit_ci"] = body.nit_ci
        if body.correo_facturacion is not None:
            datos_fac_dict["correo_facturacion"] = body.correo_facturacion
        if body.tipo_documento is not None:
            datos_fac_dict["tipo_documento"] = body.tipo_documento

        ref_efectiva = body.referencia_externa or body.referencia_transaccion

        resultado = caja_pago_repos.ejecutar_pago_caja(
            id_venta=body.id_venta,
            id_usuario=id_usuario,
            id_metodo_pago=body.id_metodo_pago,
            monto_recibido=body.monto_recibido,
            referencia_transaccion=ref_efectiva,
            referencia_externa=ref_efectiva,
            datos_facturacion=datos_fac_dict,
            id_sucursal=id_suc_efectiva,
            id_empresa=id_empresa,
            desglose_recibido=body.desglose_recibido,
            desglose_cambio=body.desglose_cambio
        )

        resp_dict = {
            "success": True,
            "message": "Pago registrado correctamente en t_pago. Venta marcada como PAGADA.",
            "pago": resultado,
            "data": resultado
        }
        resp_dict.update(resultado)
        return resp_dict
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"[PROCESAR PAGO CAJA ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
