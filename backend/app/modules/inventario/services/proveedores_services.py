from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from app.modules.inventario.repos import proveedores_repos
from app.modules.admin.services import bitacora_services
import re
def _validar_correo(correo: str) -> bool:
    patron = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
    return re.match(patron, correo) is not None


def listar_proveedores_service(
    busqueda: Optional[str] = None,
    solo_activos: bool = False
) -> List[Dict[str, Any]]:
    return proveedores_repos.listar_proveedores(
        busqueda=busqueda,
        solo_activos=solo_activos
    )


def obtener_proveedor_service(
    id_proveedor: int
) -> Dict[str, Any]:
    proveedor = proveedores_repos.obtener_proveedor_por_id(id_proveedor)

    if not proveedor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor no existe"
        )

    return proveedor


def crear_proveedor_service(
    razon_social: str,
    nit: str,
    telefono: str,
    correo: str,
    direccion: str,
    contacto: str,
    usuario_id: Optional[int] = None
) -> Dict[str, Any]:

    razon_social = razon_social.strip()
    nit = nit.strip()
    telefono = telefono.strip()
    correo = correo.strip()
    direccion = direccion.strip()
    contacto = contacto.strip()

    if not razon_social:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La razón social es obligatoria"
        )

    if not nit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El NIT es obligatorio"
        )

    if not correo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo es obligatorio"
        )

    if not _validar_correo(correo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico no es válido"
        )

    if proveedores_repos.verificar_nit_duplicado(nit):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un proveedor registrado con ese NIT"
        )

    proveedor = proveedores_repos.crear_proveedor(
        razon_social=razon_social,
        nit=nit,
        telefono=telefono,
        correo=correo,
        direccion=direccion,
        contacto=contacto
    )

    if not proveedor:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar el proveedor"
        )

    if usuario_id:
        bitacora_services.registrar_accion(
            usuario_id=usuario_id,
            accion="CREAR",
            tabla="t_proveedor",
            registro_id=proveedor["id_proveedor"],
            detalle=f"Se registró el proveedor {proveedor['razon_social']}"
        )

    return proveedor


def actualizar_proveedor_service(
    id_proveedor: int,
    razon_social: str,
    nit: str,
    telefono: str,
    correo: str,
    direccion: str,
    contacto: str,
    usuario_id: Optional[int] = None
) -> Dict[str, Any]:

    proveedor_actual = proveedores_repos.obtener_proveedor_por_id(
        id_proveedor
    )

    if not proveedor_actual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor no existe"
        )

    razon_social = razon_social.strip()
    nit = nit.strip()
    telefono = telefono.strip()
    correo = correo.strip()
    direccion = direccion.strip()
    contacto = contacto.strip()

    if not razon_social:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La razón social es obligatoria"
        )

    if not nit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El NIT es obligatorio"
        )

    if not correo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo es obligatorio"
        )

    if not _validar_correo(correo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico no es válido"
        )

    if proveedores_repos.verificar_nit_duplicado(
        nit,
        id_proveedor
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe otro proveedor registrado con ese NIT"
        )

    proveedor = proveedores_repos.actualizar_proveedor(
        id_proveedor=id_proveedor,
        razon_social=razon_social,
        nit=nit,
        telefono=telefono,
        correo=correo,
        direccion=direccion,
        contacto=contacto
    )

    if not proveedor:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo actualizar el proveedor"
        )

    if usuario_id:
        bitacora_services.registrar_accion(
            usuario_id=usuario_id,
            accion="ACTUALIZAR",
            tabla="t_proveedor",
            registro_id=id_proveedor,
            detalle=f"Se actualizó el proveedor {proveedor['razon_social']}"
        )

    return proveedor


def cambiar_estado_proveedor_service(
    id_proveedor: int,
    estado: bool,
    usuario_id: Optional[int] = None
) -> Dict[str, Any]:

    proveedor = proveedores_repos.obtener_proveedor_por_id(
        id_proveedor
    )

    if not proveedor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor no existe"
        )

    if proveedor["estado"] == estado:
        estado_texto = "activo" if estado else "inactivo"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El proveedor ya se encuentra {estado_texto}"
        )

    proveedor_actualizado = proveedores_repos.cambiar_estado_proveedor(
        id_proveedor=id_proveedor,
        estado=estado
    )

    if not proveedor_actualizado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo cambiar el estado del proveedor"
        )

    accion = "ACTIVAR" if estado else "DESACTIVAR"
    estado_texto = "activo" if estado else "inactivo"

    if usuario_id:
        bitacora_services.registrar_accion(
            usuario_id=usuario_id,
            accion=accion,
            tabla="t_proveedor",
            registro_id=id_proveedor,
            detalle=f"El proveedor {proveedor['razon_social']} fue marcado como {estado_texto}"
        )

    return proveedor_actualizado