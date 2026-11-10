from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional

from app.core.security import verificar_token
from app.modules.inventario.services import proveedores_services
router = APIRouter(
    prefix="/api/proveedores",
    tags=["Gestión de Proveedores"]
)


@router.get(
    "",
    summary="Listar proveedores"
)
def listar_proveedores(
    busqueda: Optional[str] = Query(None),
    solo_activos: bool = Query(False),
    token_data: dict = Depends(verificar_token)
):
    proveedores = proveedores_services.listar_proveedores_service(
        busqueda=busqueda,
        solo_activos=solo_activos
    )

    return {
        "success": True,
        "message": "Proveedores obtenidos correctamente",
        "data": proveedores
    }


@router.get(
    "/{id_proveedor}",
    summary="Obtener proveedor por ID"
)
def obtener_proveedor(
    id_proveedor: int,
    token_data: dict = Depends(verificar_token)
):
    proveedor = proveedores_services.obtener_proveedor_service(
        id_proveedor=id_proveedor
    )

    return {
        "success": True,
        "message": "Proveedor obtenido correctamente",
        "data": proveedor
    }


@router.post(
    "",
    summary="Registrar proveedor"
)
def crear_proveedor(
    datos: dict,
    token_data: dict = Depends(verificar_token)
):
    usuario_id = token_data.get("nro_usuario")

    proveedor = proveedores_services.crear_proveedor_service(
        razon_social=datos.get("razon_social", ""),
        nit=datos.get("nit", ""),
        telefono=datos.get("telefono", ""),
        correo=datos.get("correo", ""),
        direccion=datos.get("direccion", ""),
        contacto=datos.get("contacto", ""),
        usuario_id=usuario_id
    )

    return {
        "success": True,
        "message": "Proveedor registrado correctamente",
        "data": proveedor
    }


@router.put(
    "/{id_proveedor}",
    summary="Actualizar proveedor"
)
def actualizar_proveedor(
    id_proveedor: int,
    datos: dict,
    token_data: dict = Depends(verificar_token)
):
    usuario_id = token_data.get("nro_usuario")

    proveedor = proveedores_services.actualizar_proveedor_service(
        id_proveedor=id_proveedor,
        razon_social=datos.get("razon_social", ""),
        nit=datos.get("nit", ""),
        telefono=datos.get("telefono", ""),
        correo=datos.get("correo", ""),
        direccion=datos.get("direccion", ""),
        contacto=datos.get("contacto", ""),
        usuario_id=usuario_id
    )

    return {
        "success": True,
        "message": "Proveedor actualizado correctamente",
        "data": proveedor
    }


@router.put(
    "/{id_proveedor}/estado",
    summary="Cambiar estado del proveedor"
)
def cambiar_estado_proveedor(
    id_proveedor: int,
    datos: dict,
    token_data: dict = Depends(verificar_token)
):
    usuario_id = token_data.get("nro_usuario")

    estado = datos.get("estado")

    if not isinstance(estado, bool):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El campo estado debe ser booleano"
        )

    proveedor = proveedores_services.cambiar_estado_proveedor_service(
        id_proveedor=id_proveedor,
        estado=estado,
        usuario_id=usuario_id
    )

    mensaje = (
        "Proveedor activado correctamente"
        if estado
        else "Proveedor desactivado correctamente"
    )

    return {
        "success": True,
        "message": mensaje,
        "data": proveedor
    }