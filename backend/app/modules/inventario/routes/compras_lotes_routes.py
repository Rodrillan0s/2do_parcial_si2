from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.core.security import require_permission
from app.core.tenant_guard import resolver_tenant_operacion, resolver_sucursal_autorizada
from app.modules.inventario.services import compras_lotes_services
router = APIRouter(tags=["Gestión de Compras, Lotes e Importación Masiva"])

# --- Modelos Pydantic ---
class ConfirmarImportacionIn(BaseModel):
    id_sucursal: int = Field(..., description="ID de la sucursal donde ingresará la mercadería")
    id_empresa: Optional[int] = Field(None, description="Empresa seleccionada para administradores globales")
    filas: List[Dict[str, Any]] = Field(..., description="Listado de filas validadas para importar")
    generar_orden_compra: bool = Field(True, description="Si genera automáticamente registro de Orden de Compra")
    id_proveedor: Optional[int] = Field(None, description="ID del proveedor opcional")
    numero_lote: Optional[str] = Field(None, description="Código de lote (auto si es nulo)")
    guia_remision: Optional[str] = Field(None, description="Número de guía de remisión o factura del proveedor")
    observaciones: Optional[str] = Field(None, description="Notas de la recepción")

class RechazoOrdenIn(BaseModel):
    motivo: str = Field(..., description="Motivo de rechazo de la orden de compra")

class RecepcionOrdenIn(BaseModel):
    numero_lote: Optional[str] = Field(None, description="Código del lote recibido")
    guia_remision: Optional[str] = Field(None, description="Guía de remisión del despacho")
    observaciones: Optional[str] = Field(None, description="Notas adicionales del ingreso")

class ItemOrdenCompraIn(BaseModel):
    id_producto: Optional[int] = Field(None, description="ID del producto existente si aplica")
    id_variante: Optional[int] = Field(None, description="ID de la variante si aplica")
    codigo_producto: str = Field(..., description="Código o SKU de referencia")
    nombre_producto: str = Field(..., description="Nombre del producto o prenda")
    talla: Optional[str] = Field("Única", description="Talla de la prenda")
    color: Optional[str] = Field("Estándar", description="Color de la prenda")
    sku: Optional[str] = Field(None, description="SKU específico")
    cantidad_solicitada: int = Field(..., gt=0, description="Cantidad solicitada")
    costo_unitario: float = Field(..., ge=0, description="Costo unitario estimado de compra")

class CrearOrdenCompraIn(BaseModel):
    id_sucursal: int = Field(..., description="ID de la sucursal de destino asignada a la orden")
    id_empresa: Optional[int] = Field(None, description="Empresa seleccionada para administradores globales")
    id_proveedor: Optional[int] = Field(None, description="ID del proveedor seleccionado")
    fecha_entrega_esperada: Optional[str] = Field(None, description="Fecha esperada de entrega (YYYY-MM-DD)")
    observaciones: Optional[str] = Field(None, description="Observaciones o términos de la orden")
    items: List[ItemOrdenCompraIn] = Field(..., min_length=1, description="Listado de prendas requeridas")


# ==============================================================================
# 1. PLANTILLA Y CARGA MASIVA DE PRENDAS
# ==============================================================================

@router.get("/api/inventario/importacion/plantilla")
def descargar_plantilla_excel(
    id_empresa: Optional[int] = Query(None, description="Empresa seleccionada para administradores globales"),
    token_data: dict = Depends(require_permission('compras.ver'))
):
    """
    Descarga la plantilla fija y oficial de Excel (.xlsx) para importación de prendas por lote.
    Incluye formato predefinido, validaciones y catálogo de categorías, tallas y colores.
    """
    try:
        empresa_efectiva = resolver_tenant_operacion(token_data, id_empresa, permitir_global=False)
        buf = compras_lotes_services.generar_plantilla_excel_lotes(empresa_efectiva)
        filename = "plantilla_importacion_prendas_lote.xlsx"
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando plantilla Excel: {str(e)}"
        )


@router.post("/api/inventario/importacion/preview")
async def previsualizar_archivo_excel(
    archivo: UploadFile = File(...),
    id_sucursal: Optional[int] = Form(None),
    id_empresa: Optional[int] = Form(None),
    token_data: dict = Depends(require_permission('compras.crear'))
):
    """
    Lee y valida en memoria el archivo Excel subido (Dry-Run / Preview).
    Retorna la clasificación por fila (nuevo producto vs existente) y totales sin modificar la BD.
    """
    try:
        empresa_efectiva = resolver_tenant_operacion(token_data, id_empresa, permitir_global=False)
        id_sucursal = resolver_sucursal_autorizada(token_data, id_sucursal)
        content = await archivo.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo enviado está vacío.")

        resumen = compras_lotes_services.analizar_y_previsualizar_excel(content, empresa_efectiva, id_sucursal)
        return {
            "success": True,
            "data": resumen
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando archivo Excel: {str(e)}"
        )


@router.post("/api/inventario/importacion/confirmar")
def confirmar_importacion_lote(
    payload: ConfirmarImportacionIn,
    token_data: dict = Depends(require_permission('compras.crear'))
):
    """
    Aplica transaccionalmente la importación masiva:
    Crea productos/variantes nuevos, afecta el inventario físico disponible en la sucursal
    y genera los registros de auditoría y lote.
    """
    try:
        datos = payload.model_dump()
        datos['id_empresa'] = resolver_tenant_operacion(
            token_data,
            datos.get('id_empresa'),
            permitir_global=False
        )
        resolver_sucursal_autorizada(token_data, datos.get('id_sucursal'))
        resultado = compras_lotes_services.confirmar_e_importar_lote_db(
            datos,
            token_data
        )
        return resultado
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al confirmar importación del lote: {str(e)}"
        )


# ==============================================================================
# 2. CICLO DE VIDA DE ÓRDENES DE COMPRA (COMPRAS & PROCUREMENT)
# ==============================================================================

@router.get("/api/compras/ordenes")
def listar_ordenes_compra(
    id_sucursal: Optional[int] = Query(None, description="Filtrar por sucursal"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    id_empresa: Optional[int] = Query(None, description="Empresa seleccionada para administradores globales"),
    token_data: dict = Depends(require_permission('compras.ver'))
):
    """Retorna las órdenes de compra activas para la empresa y opcionalmente por sucursal."""
    try:
        empresa_efectiva = resolver_tenant_operacion(token_data, id_empresa, permitir_global=False)
        id_sucursal = resolver_sucursal_autorizada(token_data, id_sucursal)
        ordenes = compras_lotes_services.listar_ordenes_compra_db(empresa_efectiva, id_sucursal, estado)
        return {
            "success": True,
            "ordenes": ordenes,
            "total": len(ordenes)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/api/compras/ordenes", status_code=status.HTTP_201_CREATED)
def crear_orden_compra(
    payload: CrearOrdenCompraIn,
    token_data: dict = Depends(require_permission('compras.crear'))
):
    """
    Crea una nueva orden de compra asignada a una sucursal específica
    con estado inicial PENDIENTE_APROBACION.
    """
    try:
        datos = payload.model_dump()
        datos['id_empresa'] = resolver_tenant_operacion(
            token_data,
            datos.get('id_empresa'),
            permitir_global=False
        )
        datos['id_sucursal'] = resolver_sucursal_autorizada(token_data, datos.get('id_sucursal'))
        nueva_oc = compras_lotes_services.crear_orden_compra_db(datos, token_data)
        return {
            "success": True,
            "mensaje": f"Orden de compra {nueva_oc['numero_orden']} emitida con éxito para la sucursal {nueva_oc['sucursal']}.",
            "orden": nueva_oc
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creando orden de compra: {str(e)}")


@router.get("/api/compras/ordenes/{id_orden}")
def obtener_detalle_orden_compra(
    id_orden: int,
    id_empresa: Optional[int] = Query(None, description="Empresa seleccionada para administradores globales"),
    token_data: dict = Depends(require_permission('compras.ver'))
):
    """Retorna la cabecera y el detalle de prendas de una orden de compra."""
    try:
        empresa_efectiva = resolver_tenant_operacion(token_data, id_empresa, permitir_global=False)
        detalle = compras_lotes_services.obtener_detalle_orden_compra_db(id_orden, empresa_efectiva)
        return {
            "success": True,
            "orden": detalle
        }
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/api/compras/ordenes/{id_orden}/aprobar")
def aprobar_orden_compra(
    id_orden: int,
    token_data: dict = Depends(require_permission('compras.crear'))
):
    """Aprueba una orden de compra pendiente para permitir su despacho y recepción."""
    try:
        resultado = compras_lotes_services.aprobar_orden_compra_db(id_orden, token_data)
        return resultado
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/api/compras/ordenes/{id_orden}/rechazar")
def rechazar_orden_compra(
    id_orden: int,
    payload: RechazoOrdenIn,
    token_data: dict = Depends(require_permission('compras.crear'))
):
    """Rechaza una orden de compra pendiente justificando el motivo."""
    try:
        resultado = compras_lotes_services.rechazar_orden_compra_db(id_orden, payload.motivo, token_data)
        return resultado
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/api/compras/ordenes/{id_orden}/recibir")
def recibir_orden_compra(
    id_orden: int,
    payload: RecepcionOrdenIn,
    token_data: dict = Depends(require_permission('compras.crear'))
):
    """
    Confirma la recepción física de mercadería de una orden aprobada.
    Genera el lote en t_lote, actualiza el stock en t_inventario y finaliza la orden.
    """
    try:
        resultado = compras_lotes_services.recibir_mercaderia_orden_db(
            id_orden,
            payload.model_dump(),
            token_data
        )
        return resultado
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/api/compras/lotes")
def listar_lotes_ingresados(
    id_sucursal: Optional[int] = Query(None, description="Filtrar por sucursal"),
    id_empresa: Optional[int] = Query(None, description="Empresa seleccionada para administradores globales"),
    token_data: dict = Depends(require_permission('compras.ver'))
):
    """Lista todos los lotes de mercadería ingresados a la empresa."""
    try:
        empresa_efectiva = resolver_tenant_operacion(token_data, id_empresa, permitir_global=False)
        id_sucursal = resolver_sucursal_autorizada(token_data, id_sucursal)
        lotes = compras_lotes_services.listar_lotes_db(empresa_efectiva, id_sucursal)
        return {
            "success": True,
            "lotes": lotes,
            "total": len(lotes)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
