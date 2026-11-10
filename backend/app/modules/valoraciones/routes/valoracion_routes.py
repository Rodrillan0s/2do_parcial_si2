"""
Rutas API para el Sistema de Valoraciones de Calidad y Servicio.
Endpoints protegidos con autenticación JWT, compras verificadas y aislamiento multitenant.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.security import verificar_token
from app.modules.valoraciones.schemas.valoracion_schemas import (
    CrearValoracionDTO,
    AtenderValoracionDTO
)
from app.modules.valoraciones.services import valoracion_services

router = APIRouter(prefix="/api/valoraciones", tags=["Valoraciones"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar valoración de calidad y servicio (Cliente autenticado con compra verificada)"
)
@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar valoración de calidad y servicio"
)
def crear_valoracion(
    dto: CrearValoracionDTO,
    token_data: dict = Depends(verificar_token)
):
    try:
        return valoracion_services.registrar_valoracion_cliente(dto, token_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar la valoración: {str(e)}"
        )


@router.get(
    "/pendientes",
    summary="Listar compras y prendas elegibles pendientes de valoración para el cliente en sesión"
)
def obtener_pendientes(
    token_data: dict = Depends(verificar_token)
):
    try:
        return valoracion_services.obtener_pendientes_cliente(token_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar pendientes: {str(e)}"
        )


@router.get(
    "/producto/{id_producto}",
    summary="Consultar promedio, desglose de estrellas y últimas opiniones verificadas de un producto"
)
def consultar_valoraciones_producto(
    id_producto: int
):
    try:
        return valoracion_services.obtener_resumen_producto(id_producto)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar valoraciones del producto: {str(e)}"
        )


@router.get(
    "/admin",
    summary="Listar valoraciones de la empresa para auditoría, satisfacción de clientes y seguimiento"
)
def listar_valoraciones_admin(
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    id_sucursal: Optional[int] = Query(None, description="Filtrar por sucursal"),
    solo_criticas: bool = Query(False, description="Filtrar solo 1 estrella o que requieran revisión"),
    atendido: Optional[bool] = Query(None, description="Filtrar por estado de atención"),
    limite: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    token_data: dict = Depends(verificar_token)
):
    try:
        return valoracion_services.listar_valoraciones_admin(
            token_data=token_data,
            id_empresa_param=id_empresa,
            id_sucursal=id_sucursal,
            solo_criticas=solo_criticas,
            atendido=atendido,
            limite=limite,
            offset=offset
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar valoraciones: {str(e)}"
        )


@router.patch(
    "/admin/{id_valoracion}/atender",
    summary="Marcar como atendida una valoración crítica y registrar nota de seguimiento"
)
def atender_valoracion_admin(
    id_valoracion: int,
    dto: AtenderValoracionDTO,
    id_empresa: Optional[int] = Query(None, description="ID del Tenant"),
    token_data: dict = Depends(verificar_token)
):
    try:
        return valoracion_services.atender_valoracion_admin(
            id_valoracion=id_valoracion,
            dto=dto,
            token_data=token_data,
            id_empresa_param=id_empresa
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al atender valoración: {str(e)}"
        )
