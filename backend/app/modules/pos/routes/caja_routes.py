import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import verificar_token, tiene_permiso
from app.modules.pos.repos import caja_repos
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/caja", tags=["W24 - Control de Caja y Arqueo"])

# --- DTOs ---

class ConteoDenominacionItemDTO(BaseModel):
    id_denominacion: int = Field(..., gt=0)
    cantidad: int = Field(..., ge=0)

class AbrirCajaDTO(BaseModel):
    id_caja: Optional[int] = Field(None, gt=0, description="ID de la caja física opcional")
    id_sucursal: Optional[int] = Field(None, gt=0, description="Sucursal donde opera el cajero")
    id_empresa: Optional[int] = Field(None, gt=0, description="Empresa de la caja")
    conteo: Optional[List[ConteoDenominacionItemDTO]] = Field(None, description="Conteo físico de billetes y monedas")
    conteo_items: Optional[List[ConteoDenominacionItemDTO]] = Field(None, description="Alias conteo_items")
    observacion: Optional[str] = Field(None, max_length=300)
    observaciones: Optional[str] = Field(None, max_length=300)

class CerrarCajaDTO(BaseModel):
    id_sesion_caja: Optional[int] = Field(None, gt=0)
    conteo: Optional[List[ConteoDenominacionItemDTO]] = Field(None, description="Conteo de efectivo para el arqueo")
    conteo_items: Optional[List[ConteoDenominacionItemDTO]] = Field(None, description="Alias conteo_items")
    observacion: Optional[str] = Field(None, max_length=300)
    observaciones: Optional[str] = Field(None, max_length=300)

class CrearCajaDTO(BaseModel):
    id_sucursal: int = Field(..., gt=0, description="Sucursal donde se ubica la caja")
    id_empresa: Optional[int] = Field(None, gt=0, description="Empresa de la caja")
    nombre: str = Field(..., min_length=2, max_length=150, description="Nombre descriptivo de la caja")
    codigo_caja: Optional[str] = Field(None, max_length=50, description="Código de caja opcional")


def _verificar_permiso_cajero(token_data: dict) -> None:
    """
    Verifica que el usuario tenga rol de Cajero, Administrador o Encargado de Sucursal,
    o posea el permiso explícito caja.ver / caja.abrir.
    """
    if any(tiene_permiso(token_data, codigo) for codigo in ("caja.ver", "caja.abrir", "pos.vender")):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acceso restringido. No tienes permisos para operar la caja registradora."
    )


def _verificar_permiso_supervisor(token_data: dict) -> None:
    """
    Verifica que el usuario sea Administrador General, Administrador de Tienda,
    Encargado de Sucursal o cuente con permisos de monitoreo/reportes.
    """
    id_rol = token_data.get("id_rol")
    roles = [str(r).upper() for r in token_data.get("roles", [])]
    alcance = token_data.get("alcance")

    es_supervisor = (
        any(r in ('ADMINISTRADOR', 'SUPERADMIN', 'ADMINISTRADOR_TIENDA', 'ENCARGADO', 'ENCARGADO_SUCURSAL') for r in roles) or
        alcance in ('PLATAFORMA', 'EMPRESA') or
        any(tiene_permiso(token_data, codigo) for codigo in ('caja.ver', 'reportes.ver', 'ventas.ver', 'admin.acceder'))
    )

    if not es_supervisor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido. Solo Administradores y Encargados pueden supervisar las cajas."
        )


def _obtener_empresa_efectiva(token_data: dict, id_empresa_solicitada: Optional[int] = None) -> int:
    from app.core.tenant_guard import resolver_tenant_operacion
    return resolver_tenant_operacion(token_data, id_empresa_solicitada)


def _obtener_sucursal_efectiva(token_data: dict, id_sucursal_solicitada: Optional[int] = None, id_empresa: Optional[int] = None) -> int:
    from app.modules.pos.routes.pos_routes import _obtener_sucursal_contexto
    return _obtener_sucursal_contexto(token_data, id_sucursal_solicitada, id_empresa)


def _contexto_supervision(token_data, empresa, sucursal):
    from app.core.tenant_guard import resolver_tenant_operacion, resolver_sucursal_autorizada
    empresa = resolver_tenant_operacion(token_data, empresa, permitir_global=True)
    sucursal = resolver_sucursal_autorizada(token_data, sucursal)
    if sucursal is not None:
        from app.modules.inventario.repos.sucursales_repos import obtener_sucursal_por_id
        branch = obtener_sucursal_por_id(sucursal)
        if not branch or (empresa is not None and branch['id_empresa'] != empresa):
            raise HTTPException(403, detail='Sucursal fuera de la empresa seleccionada.')
    return empresa, sucursal


# --- ENDPOINTS ---

@router.get('/denominaciones', summary="W24: Obtener catálogo de denominaciones monetarias")
def listar_denominaciones(token_data: dict = Depends(verificar_token)):
    _verificar_permiso_cajero(token_data)
    try:
        data = caja_repos.obtener_denominaciones_activas()
        return {
            "success": True,
            "denominaciones": data,
            "data": data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DENOMINACIONES ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get('/estado', summary="W24: Consultar estado de la caja del cajero")
def obtener_estado_caja(
    id_sucursal: Optional[int] = Query(None, description="Sucursal a consultar"),
    id_empresa: Optional[int] = Query(None, description="Empresa a consultar"),
    token_data: dict = Depends(verificar_token)
):
    _verificar_permiso_cajero(token_data)
    try:
        id_usuario = token_data.get("nro_usuario") or token_data.get("id_usuario")
        id_emp = _obtener_empresa_efectiva(token_data, id_empresa)
        id_suc = _obtener_sucursal_efectiva(token_data, id_sucursal, id_emp)

        caja_asig = caja_repos.obtener_caja_disponible_sucursal(id_suc, id_emp)
        sesion_activa = caja_repos.obtener_sesion_activa_usuario(id_usuario, id_suc)

        if not sesion_activa:
            return {
                "success": True,
                "abierta": False,
                "tiene_sesion_activa": False,
                "caja_asignada": caja_asig,
                "sesion_activa": None,
                "id_sucursal": id_suc,
                "id_empresa": id_emp,
                "message": "No existe una caja abierta para tu usuario en esta sucursal.",
                "data": None
            }

        # Calcular resumen financiero en vivo de la sesión
        resumen = caja_repos.calcular_resumen_caja(sesion_activa["id_sesion_caja"])
        sesion_activa["resumen"] = resumen

        return {
            "success": True,
            "abierta": True,
            "tiene_sesion_activa": True,
            "caja_asignada": caja_asig,
            "sesion_activa": sesion_activa,
            "id_sucursal": id_suc,
            "id_empresa": id_emp,
            "message": "Caja abierta activa encontrada.",
            "data": sesion_activa
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ESTADO CAJA ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post('/abrir', summary="W24: Apertura de caja registradora mediante conteo físico")
def abrir_caja(
    body: AbrirCajaDTO,
    token_data: dict = Depends(verificar_token)
):
    _verificar_permiso_cajero(token_data)
    try:
        id_usuario = token_data.get("nro_usuario") or token_data.get("id_usuario")
        id_emp = _obtener_empresa_efectiva(token_data, body.id_empresa)
        id_suc = _obtener_sucursal_efectiva(token_data, body.id_sucursal, id_emp)

        # Si no se pasó id_caja, obtener o crear la caja por defecto de la sucursal
        id_caja = body.id_caja
        if not id_caja:
            caja_info = caja_repos.obtener_caja_disponible_sucursal(id_suc, id_emp)
            id_caja = caja_info["id_caja"]

        conteo_raw = body.conteo or body.conteo_items or []
        if not conteo_raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe ingresar el conteo físico de billetes y monedas.")

        conteo_dicts = [item.dict() for item in conteo_raw]
        obs = body.observacion or body.observaciones
        sesion = caja_repos.abrir_caja_sesion(
            id_usuario=id_usuario,
            id_sucursal=id_suc,
            id_empresa=id_emp,
            id_caja=id_caja,
            conteo_items=conteo_dicts,
            observacion=obs
        )

        return {
            "success": True,
            "message": f"Caja abierta exitosamente con un fondo inicial de Bs. {sesion['monto_inicial']:.2f}.",
            "sesion": sesion,
            "data": sesion
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ABRIR CAJA ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get('/resumen', summary="W24: Resumen financiero en vivo de la caja del turno")
def obtener_resumen_caja(
    id_sesion_caja: Optional[int] = Query(None, description="ID de sesión de caja opcional"),
    token_data: dict = Depends(verificar_token)
):
    _verificar_permiso_cajero(token_data)
    try:
        id_usuario = token_data.get("nro_usuario") or token_data.get("id_usuario")
        id_emp = _obtener_empresa_efectiva(token_data)
        if not id_sesion_caja:
            sesion = caja_repos.obtener_sesion_activa_usuario(id_usuario)
            if not sesion:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tienes una sesión de caja abierta.")
            id_sesion_caja = sesion["id_sesion_caja"]
        else:
            sesion = caja_repos.obtener_sesion_caja_por_id(id_sesion_caja)
            if not sesion:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión de caja no encontrada.")
            from app.core.tenant_guard import validar_acceso_recurso_tenant, obtener_sucursales_autorizadas
            validar_acceso_recurso_tenant(token_data, sesion.get("id_empresa"), "sesión de caja")
            sucursales_auth = obtener_sucursales_autorizadas(token_data)
            if sucursales_auth is not None and sesion.get("id_sucursal") not in sucursales_auth:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos sobre la sucursal de esta sesión de caja.")

        resumen = caja_repos.calcular_resumen_caja(id_sesion_caja, id_empresa=id_emp)
        return {
            "success": True,
            "resumen": resumen,
            "data": resumen
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RESUMEN CAJA ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post('/cerrar', summary="W24: Cierre de caja registradora mediante conteo y arqueo")
def cerrar_caja(
    body: CerrarCajaDTO,
    token_data: dict = Depends(verificar_token)
):
    _verificar_permiso_cajero(token_data)
    try:
        id_usuario = token_data.get("nro_usuario") or token_data.get("id_usuario")
        id_emp = _obtener_empresa_efectiva(token_data)
        id_sesion = body.id_sesion_caja
        if not id_sesion:
            sesion = caja_repos.obtener_sesion_activa_usuario(id_usuario)
            if not sesion:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tienes una sesión de caja abierta para cerrar.")
            id_sesion = sesion["id_sesion_caja"]
        else:
            sesion = caja_repos.obtener_sesion_caja_por_id(id_sesion)
            if not sesion:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión de caja no encontrada.")
            from app.core.tenant_guard import validar_acceso_recurso_tenant, obtener_sucursales_autorizadas
            validar_acceso_recurso_tenant(token_data, sesion.get("id_empresa"), "sesión de caja")
            sucursales_auth = obtener_sucursales_autorizadas(token_data)
            if sucursales_auth is not None and sesion.get("id_sucursal") not in sucursales_auth:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos sobre la sucursal de esta sesión de caja.")

        conteo_raw = body.conteo or body.conteo_items or []
        if not conteo_raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe ingresar el conteo físico de billetes y monedas.")

        conteo_dicts = [item.dict() for item in conteo_raw]
        obs = body.observacion or body.observaciones
        cierre = caja_repos.cerrar_caja_sesion(
            id_sesion_caja=id_sesion,
            id_usuario=id_usuario,
            conteo_items=conteo_dicts,
            observacion=obs,
            id_empresa=id_emp
        )

        dif = cierre["diferencia"]
        estado_dif = cierre["estado_diferencia"]
        mensaje = f"Caja cerrada exitosamente. Arqueo: {estado_dif} (Bs. {abs(dif):.2f})."

        return {
            "success": True,
            "message": mensaje,
            "cierre": cierre,
            "data": cierre
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CERRAR CAJA ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get('/monitoreo', summary="Supervisión en vivo de cajas registradoras por tienda y sucursales")
def monitorear_cajas(
    id_empresa: Optional[int] = Query(None, description="Filtrar por empresa"),
    id_sucursal: Optional[int] = Query(None, description="Filtrar por sucursal"),
    estado: Optional[str] = Query(None, description="Filtrar por estado: TODAS, ABIERTA, CERRADA"),
    token_data: dict = Depends(verificar_token)
):
    _verificar_permiso_supervisor(token_data)
    try:
        empresa_efectiva, sucursal_efectiva = _contexto_supervision(token_data, id_empresa, id_sucursal)

        data = caja_repos.monitorear_cajas_tienda_sucursal(
            id_empresa=empresa_efectiva,
            id_sucursal=sucursal_efectiva,
            estado_filtro=estado
        )
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MONITOREO CAJAS ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get('/sesiones-historial', summary="Historial de turnos y arqueos de caja")
def listar_historial_sesiones(
    id_empresa: Optional[int] = Query(None),
    id_sucursal: Optional[int] = Query(None),
    id_caja: Optional[int] = Query(None),
    limite: int = Query(50, ge=1, le=200),
    token_data: dict = Depends(verificar_token)
):
    _verificar_permiso_supervisor(token_data)
    try:
        empresa_efectiva, sucursal_efectiva = _contexto_supervision(token_data, id_empresa, id_sucursal)

        sesiones = caja_repos.listar_todas_sesiones_caja(
            id_empresa=empresa_efectiva,
            id_sucursal=sucursal_efectiva,
            id_caja=id_caja,
            limite=limite
        )
        return {
            "success": True,
            "sesiones": sesiones,
            "total": len(sesiones)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HISTORIAL SESIONES ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post('/crear', summary="Registrar una nueva caja física para una sucursal")
def registrar_caja(
    body: CrearCajaDTO,
    token_data: dict = Depends(verificar_token)
):
    _verificar_permiso_supervisor(token_data)
    try:
        id_emp = _obtener_empresa_efectiva(token_data, body.id_empresa)
        id_suc = _obtener_sucursal_efectiva(token_data, body.id_sucursal, id_emp)

        nueva_caja = caja_repos.crear_nueva_caja(
            id_sucursal=id_suc,
            id_empresa=id_emp,
            nombre=body.nombre,
            codigo_caja=body.codigo_caja
        )
        return {
            "success": True,
            "message": f"Caja '{nueva_caja['nombre']}' registrada exitosamente con código {nueva_caja['codigo_caja']}.",
            "caja": nueva_caja,
            "data": nueva_caja
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CREAR CAJA ERROR] {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
