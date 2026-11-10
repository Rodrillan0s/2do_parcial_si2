"""
AuroraStore Iteración 3 — Servicios de Devoluciones (CU24W / CU25W)
Lógica de negocio, orquestación de permisos, auditoría en t_bitacora y multitenant.
"""
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from app.core.tenant_guard import resolver_tenant_operacion, obtener_sucursales_autorizadas, obtener_alcance_usuario, es_administrador_global
from app.core.security import tiene_permiso
from app.modules.admin.repos.bitacora_repos import registrar_evento_db
from app.modules.pedidos.repos import devoluciones_repos
from app.core.postgres import atomic


def _es_personal(token_data):
    roles = {str(role).upper() for role in token_data.get('roles', [])}
    return roles != {'CLIENTE'} and obtener_alcance_usuario(token_data) in ('PLATAFORMA','EMPRESA','SUCURSAL') and tiene_permiso(token_data, 'devoluciones.ver')


def _require_permission(token_data, permission):
    if not tiene_permiso(token_data, permission):
        raise HTTPException(403, f'Permiso requerido: {permission}')


def _authorize_return(id_devolucion, datos, token_data, permission):
    _require_permission(token_data, permission)
    tenant, branch, sale_branch = devoluciones_repos.contexto_devolucion(id_devolucion)
    if es_administrador_global(token_data):
        return tenant
    effective = resolver_tenant_operacion(token_data, datos.get('id_empresa') or tenant)
    if effective != tenant:
        raise HTTPException(403, 'Devolución ajena al tenant autorizado.')
    branches = obtener_sucursales_autorizadas(token_data)
    if branches is not None and (branch not in branches or sale_branch not in branches):
        raise HTTPException(403, 'Devolución fuera de las sucursales autorizadas.')
    return tenant


def _critical_audit(**kwargs):
    result = registrar_evento_db(**kwargs)
    if not result:
        raise HTTPException(503, 'No pudo persistirse la auditoría; operación revertida.')
    return result

def consultar_elegibilidad_venta(
    id_venta: int,
    token_data: dict,
    id_empresa_solicitado: Optional[int] = None
) -> Dict[str, Any]:
    """
    Verifica si una venta es elegible para devolución y calcula el saldo disponible por ítem.
    Distingue automáticamente entre vista de cliente y vista de personal administrativo.
    """
    alcance = obtener_alcance_usuario(token_data)
    es_personal = _es_personal(token_data)
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')

    if es_personal:
        id_empresa = resolver_tenant_operacion(token_data, id_empresa_solicitado)
        sucursales = obtener_sucursales_autorizadas(token_data)
    else:
        id_empresa = id_empresa_solicitado
        sucursales = None

    return devoluciones_repos.consultar_venta_elegible(
        id_venta=id_venta,
        id_usuario=id_usuario,
        id_empresa=id_empresa,
        es_personal=es_personal,
        sucursales_autorizadas=sucursales
    )

def buscar_ventas_presencial(
    criterio: str,
    token_data: dict,
    id_empresa_solicitado: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Búsqueda rápida y flexible de ventas en mostrador/POS para iniciar devoluciones.
    Aplica filtro multitenant estricto por empresa.
    """
    id_empresa = resolver_tenant_operacion(token_data, id_empresa_solicitado)
    sucursales = obtener_sucursales_autorizadas(token_data)
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')

    return devoluciones_repos.buscar_ventas_presencial(
        criterio=criterio,
        id_empresa=id_empresa,
        id_usuario=id_usuario,
        sucursales_autorizadas=sucursales
    )

@atomic
def solicitar_devolucion_cliente(
    datos: dict,
    token_data: dict
) -> Dict[str, Any]:
    """
    CU25W: Procesa la solicitud de devolución iniciada por un cliente online.
    """
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
    # This customer action is authorized by the account of the original sale.
    id_empresa = datos.get('id_empresa')

    id_venta = datos.get("id_venta")
    motivo = (datos.get("motivo") or "").strip()
    descripcion = datos.get("descripcion")
    evidencia_url = datos.get("evidencia_url")
    items = datos.get("items") or []
    tipo_resolucion = (datos.get("tipo_resolucion") or "REEMBOLSO_DINERO").strip().upper()

    if not id_venta or id_venta <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de venta inválido.")

    if not motivo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe especificar el motivo de la devolución.")

    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe seleccionar al menos una prenda a devolver.")

    res = devoluciones_repos.crear_solicitud_cliente(
        id_venta=id_venta,
        id_usuario=id_usuario,
        id_empresa=id_empresa,
        motivo=motivo,
        descripcion=descripcion,
        evidencia_url=evidencia_url,
        items_solicitados=items,
        tipo_resolucion=tipo_resolucion
    )

    if res.get('idempotent_replay'):
        return res
    id_empresa = res['id_empresa']

    # Registro en auditoría
    _critical_audit(
        id_usuario=id_usuario,
        usuario_nombre=token_data.get('username') or 'Cliente',
        usuario_email=token_data.get('correo') or token_data.get('sub'),
        id_empresa=id_empresa,
        id_sucursal=None,
        modulo="devoluciones",
        accion="SOLICITAR_DEVOLUCION_ONLINE",
        entidad="t_devolucion",
        id_entidad=str(res["id_devolucion"]),
        descripcion=f"Cliente solicita devolución {res['codigo_devolucion']} para venta #{id_venta} por monto Bs. {res['monto_reembolso']}.",
        resultado="EXITO",
        nivel="INFO",
        ip=None,
        user_agent=None,
        datos_anteriores=None,
        datos_nuevos=res,
        metadatos={"motivo": motivo, "id_venta": id_venta},
        request_id=None
    )

    return res

@atomic
def registrar_devolucion_presencial_mostrador(
    datos: dict,
    token_data: dict
) -> Dict[str, Any]:
    """
    CU24W: Cajero o Encargado registra una devolución directa en mostrador físico.
    """
    _require_permission(token_data,'devoluciones.crear_presencial')
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
    id_empresa = resolver_tenant_operacion(token_data, datos.get("id_empresa"))
    sucursales_aut = obtener_sucursales_autorizadas(token_data)

    id_sucursal = datos.get("id_sucursal")
    if not id_sucursal:
        id_sucursal = (token_data.get('sucursales') or [None])[0]

    if not id_sucursal:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe indicar la sucursal de recepción.")

    if sucursales_aut is not None and id_sucursal not in sucursales_aut:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos sobre la sucursal indicada.")

    id_venta = datos.get("id_venta")
    motivo = (datos.get("motivo") or "").strip()
    observaciones = datos.get("observaciones")
    items = datos.get("items") or []
    reembolso_inmediato = bool(datos.get("registrar_reembolso_inmediato", False))
    metodo_reembolso = datos.get("metodo_reembolso")
    referencia_reembolso = datos.get("referencia_reembolso")
    tipo_resolucion = (datos.get("tipo_resolucion") or "REEMBOLSO_DINERO").strip().upper()
    id_sesion_caja = datos.get("id_sesion_caja")
    items_cambio = datos.get("items_cambio")

    if not id_venta or id_venta <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de venta inválido.")

    if not motivo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe indicar el motivo de la devolución.")

    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe indicar los artículos a devolver.")

    devoluciones_repos.consultar_venta_elegible(id_venta,id_usuario,id_empresa,True,sucursales_aut)
    if reembolso_inmediato:
        _require_permission(token_data,'devoluciones.reembolsar')
    res = devoluciones_repos.registrar_devolucion_presencial(
        id_venta=id_venta,
        id_usuario_cajero=id_usuario,
        id_empresa=id_empresa,
        id_sucursal=id_sucursal,
        motivo=motivo,
        observaciones=observaciones,
        items_recibidos=items,
        registrar_reembolso_inmediato=reembolso_inmediato,
        metodo_reembolso=metodo_reembolso,
        referencia_reembolso=referencia_reembolso,
        tipo_resolucion=tipo_resolucion,
        id_sesion_caja=id_sesion_caja,
        items_cambio=items_cambio
    )

    if res.get('idempotent_replay'):
        return res
    _critical_audit(
        id_usuario=id_usuario,
        usuario_nombre=token_data.get('username') or 'Personal',
        usuario_email=token_data.get('correo') or token_data.get('sub'),
        id_empresa=id_empresa,
        id_sucursal=id_sucursal,
        modulo="devoluciones",
        accion="REGISTRAR_DEVOLUCION_PRESENCIAL",
        entidad="t_devolucion",
        id_entidad=str(res["id_devolucion"]),
        descripcion=f"Personal registra devolución presencial {res['codigo_devolucion']} en sucursal {id_sucursal} (Monto Bs. {res['monto_reembolso']}).",
        resultado="EXITO",
        nivel="INFO",
        ip=None,
        user_agent=None,
        datos_anteriores=None,
        datos_nuevos=res,
        metadatos={"id_venta": id_venta, "id_sucursal": id_sucursal},
        request_id=None
    )

    return res

def listar_mis_devoluciones(
    token_data: dict,
    limit: int = 10,
    offset: int = 0,
    id_empresa_solicitado: Optional[int] = None
) -> Dict[str, Any]:
    """
    CU25W: Consulta el historial de solicitudes de devolución del cliente autenticado.
    """
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
    id_empresa = id_empresa_solicitado

    return devoluciones_repos.listar_devoluciones_cliente(
        id_usuario=id_usuario,
        id_empresa=id_empresa,
        limit=limit,
        offset=offset
    )

def listar_bandeja_personal(
    token_data: dict,
    estado: Optional[str] = None,
    id_sucursal: Optional[int] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    busqueda: Optional[str] = None,
    limit: int = 15,
    offset: int = 0,
    id_empresa_solicitado: Optional[int] = None
) -> Dict[str, Any]:
    """
    CU24W: Consulta la bandeja administrativa de devoluciones para personal autorizado.
    """
    id_empresa = resolver_tenant_operacion(token_data, id_empresa_solicitado)
    sucursales_aut = obtener_sucursales_autorizadas(token_data)

    return devoluciones_repos.listar_devoluciones_personal(
        id_empresa=id_empresa,
        sucursales_autorizadas=sucursales_aut,
        estado=estado,
        id_sucursal=id_sucursal,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        busqueda=busqueda,
        limit=limit,
        offset=offset
    )

def consultar_detalle_devolucion(
    id_devolucion: int,
    token_data: dict,
    id_empresa_solicitado: Optional[int] = None
) -> Dict[str, Any]:
    """
    Retorna el detalle completo de una devolución comprobando autorizaciones.
    """
    alcance = obtener_alcance_usuario(token_data)
    es_personal = _es_personal(token_data)
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')

    if es_personal:
        if es_administrador_global(token_data):
            tenant, _, _ = devoluciones_repos.contexto_devolucion(id_devolucion)
            id_empresa = tenant
            sucursales = None
        else:
            id_empresa = resolver_tenant_operacion(token_data, id_empresa_solicitado)
            sucursales = obtener_sucursales_autorizadas(token_data)
    else:
        id_empresa = id_empresa_solicitado
        sucursales = None

    return devoluciones_repos.obtener_detalle_devolucion(
        id_devolucion=id_devolucion,
        id_usuario=id_usuario,
        id_empresa=id_empresa,
        es_personal=es_personal,
        sucursales_autorizadas=sucursales
    )

@atomic
def resolver_solicitud(
    id_devolucion: int,
    datos: dict,
    token_data: dict
) -> Dict[str, Any]:
    """
    CU24W: Dictamen formal de una solicitud (Aprobar / Rechazar).
    """
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
    id_empresa = _authorize_return(id_devolucion,datos,token_data,"devoluciones.aprobar_rechazar")

    accion = (datos.get("accion") or "").strip().upper()
    observaciones = (datos.get("observaciones") or "").strip()

    if accion not in ("APROBAR", "RECHAZAR", "EN_REVISION"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Acción inválida. Debe ser APROBAR, RECHAZAR o EN_REVISION.")

    if not observaciones:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe ingresar las observaciones y justificación del dictamen.")

    nuevo_estado = {"APROBAR":"APROBADA","RECHAZAR":"RECHAZADA","EN_REVISION":"EN_REVISION"}[accion]
    tipo_resolucion = datos.get("tipo_resolucion")

    res = devoluciones_repos.resolver_solicitud_devolucion(
        id_devolucion=id_devolucion,
        id_usuario_revisor=id_usuario,
        id_empresa=id_empresa,
        nuevo_estado=nuevo_estado,
        observaciones=observaciones,
        tipo_resolucion=tipo_resolucion
    )

    _critical_audit(
        id_usuario=id_usuario,
        usuario_nombre=token_data.get('username') or 'Personal',
        usuario_email=token_data.get('correo') or token_data.get('sub'),
        id_empresa=id_empresa,
        id_sucursal=None,
        modulo="devoluciones",
        accion=f"RESOLVER_SOLICITUD_{nuevo_estado}",
        entidad="t_devolucion",
        id_entidad=str(id_devolucion),
        descripcion=f"Personal dictamina devolución #{id_devolucion} con resultado '{nuevo_estado}'. Observaciones: {observaciones}",
        resultado="EXITO",
        nivel="INFO",
        ip=None,
        user_agent=None,
        datos_anteriores={"estado": res["estado_anterior"]},
        datos_nuevos={"estado": res["nuevo_estado"]},
        metadatos={"accion": accion, "id_devolucion": id_devolucion},
        request_id=None
    )

    return res

@atomic
def registrar_recepcion(
    id_devolucion: int,
    datos: dict,
    token_data: dict
) -> Dict[str, Any]:
    """
    CU24W: Registra la recepción física de prendas de una devolución aprobada y actualiza stock.
    """
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
    id_empresa = _authorize_return(id_devolucion,datos,token_data,"devoluciones.recibir")
    sucursales_aut = obtener_sucursales_autorizadas(token_data)

    id_sucursal = datos.get("id_sucursal")
    if not id_sucursal:
        id_sucursal = (token_data.get('sucursales') or [None])[0]

    if not id_sucursal:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe indicar la sucursal de recepción física.")

    if sucursales_aut is not None and id_sucursal not in sucursales_aut:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos sobre la sucursal de recepción indicada.")

    items = datos.get("items") or []
    observaciones = datos.get("observaciones")

    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe detallar los artículos recibidos.")

    res = devoluciones_repos.registrar_recepcion_prendas(
        id_devolucion=id_devolucion,
        id_usuario_receptor=id_usuario,
        id_empresa=id_empresa,
        id_sucursal_recepcion=id_sucursal,
        observaciones=observaciones,
        items_inspeccionados=items
    )

    if res.get('idempotent_replay'):
        return res
    _critical_audit(
        id_usuario=id_usuario,
        usuario_nombre=token_data.get('username') or 'Personal',
        usuario_email=token_data.get('correo') or token_data.get('sub'),
        id_empresa=id_empresa,
        id_sucursal=id_sucursal,
        modulo="devoluciones",
        accion="RECEPCION_PRENDAS_DEVOLUCION",
        entidad="t_devolucion",
        id_entidad=str(id_devolucion),
        descripcion=f"Recepción física completada para devolución #{id_devolucion} en sucursal {id_sucursal}.",
        resultado="EXITO",
        nivel="INFO",
        ip=None,
        user_agent=None,
        datos_anteriores=None,
        datos_nuevos=res,
        metadatos={"id_devolucion": id_devolucion, "id_sucursal": id_sucursal},
        request_id=None
    )

    return res

@atomic
def liquidar_reembolso(
    id_devolucion: int,
    datos: dict,
    token_data: dict
) -> Dict[str, Any]:
    """
    CU24W: Registra la liquidación económica del reembolso al cliente.
    """
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
    id_empresa = _authorize_return(id_devolucion,datos,token_data,"devoluciones.reembolsar")

    metodo = (datos.get("metodo_reembolso") or "").strip()
    referencia = (datos.get("referencia_reembolso") or "").strip()
    observaciones = datos.get("observaciones")
    tipo_resolucion = datos.get("tipo_resolucion")
    id_sesion_caja = datos.get("id_sesion_caja")

    res = devoluciones_repos.registrar_reembolso_financiero(
        id_devolucion=id_devolucion,
        id_usuario_responsable=id_usuario,
        id_empresa=id_empresa,
        metodo_reembolso=metodo,
        referencia_reembolso=referencia,
        observaciones=observaciones,
        tipo_resolucion=tipo_resolucion,
        id_sesion_caja=id_sesion_caja
    )

    _critical_audit(
        id_usuario=id_usuario,
        usuario_nombre=token_data.get('username') or 'Personal',
        usuario_email=token_data.get('correo') or token_data.get('sub'),
        id_empresa=id_empresa,
        id_sucursal=None,
        modulo="devoluciones",
        accion="LIQUIDAR_REEMBOLSO_DEVOLUCION",
        entidad="t_devolucion",
        id_entidad=str(id_devolucion),
        descripcion=f"Resolución liquidada para devolución #{id_devolucion} como {res['tipo_resolucion']}. Monto: Bs. {res['monto_reembolsado']}, Método: {res['metodo_reembolso']}, Ref: {res['referencia_reembolso']}.",
        resultado="EXITO",
        nivel="INFO",
        ip=None,
        user_agent=None,
        datos_anteriores=None,
        datos_nuevos=res,
        metadatos={"id_devolucion": id_devolucion},
        request_id=None
    )

    return res

def consultar_politicas_tienda(id_empresa: int) -> Dict[str, Any]:
    """
    Retorna la política de devoluciones activa de una empresa.
    """
    return devoluciones_repos.obtener_politica_devolucion(id_empresa)

def actualizar_politicas_tienda(datos: dict, token_data: dict) -> Dict[str, Any]:
    """
    Actualiza la configuración de políticas de devolución del tenant (requiere permisos).
    """
    _require_permission(token_data, "devoluciones.politicas")
    id_empresa = resolver_tenant_operacion(token_data, datos.get("id_empresa"))
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')

    politica_actualizada = devoluciones_repos.guardar_politica_devolucion(id_empresa, datos.get("politica", {}))

    _critical_audit(
        id_usuario=id_usuario,
        usuario_nombre=token_data.get('username') or 'Administrador',
        usuario_email=token_data.get('correo') or token_data.get('sub'),
        id_empresa=id_empresa,
        id_sucursal=None,
        modulo="devoluciones",
        accion="ACTUALIZAR_POLITICAS_DEVOLUCION",
        entidad="empresa",
        id_entidad=str(id_empresa),
        descripcion="Actualización de plazos y reglas de devolución y garantía Ley 453.",
        resultado="EXITO",
        nivel="INFO",
        ip=None,
        user_agent=None,
        datos_anteriores=None,
        datos_nuevos=politica_actualizada,
        metadatos={"id_empresa": id_empresa},
        request_id=None
    )

    return {"success": True, "politica": politica_actualizada}

def listar_mis_creditos_cliente(token_data: dict, id_empresa: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Lista el saldo a favor y créditos del cliente autenticado.
    """
    id_usuario = token_data.get('nro_usuario') or token_data.get('id_usuario')
    return devoluciones_repos.listar_creditos_cliente(id_usuario, id_empresa)

def verificar_credito_cliente(codigo_credito: str, id_empresa: int) -> Dict[str, Any]:
    """
    Verifica la validez y saldo disponible de un crédito de tienda para canje en checkout o mostrador.
    """
    return devoluciones_repos.verificar_saldo_credito(codigo_credito, id_empresa)

