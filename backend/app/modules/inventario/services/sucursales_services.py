
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException
from app.modules.inventario.repos import sucursales_repos
from app.modules.inventario.repos import ciudades_repos
from app.modules.admin.services import bitacora_services
from app.core.tenant_guard import (
    es_administrador_global,
    resolver_tenant_operacion,
    validar_acceso_recurso_tenant,
    validar_relaciones_tenant, obtener_sucursales_autorizadas, obtener_alcance_usuario, resolver_sucursal_autorizada
)


def is_global_admin(payload: dict) -> bool:
    return es_administrador_global(payload)


def listar_sucursales(
    id_empresa: Optional[int] = None,
    payload: dict = None
) -> Dict[str, Any]:

    empresa_efectiva = resolver_tenant_operacion(
        payload,
        id_empresa,
        permitir_global=True
    )

    sucursales = sucursales_repos.obtener_sucursales_por_empresa(
        empresa_efectiva
    )

    if obtener_alcance_usuario(payload) == 'SUCURSAL':
        permitidas = set(obtener_sucursales_autorizadas(payload))
        sucursales = [s for s in sucursales if s['id_sucursal'] in permitidas]

    return {
        "success": True,
        "message": "Sucursales recuperadas exitosamente",
        "data": sucursales
    }


def obtener_sucursal_detalle(
    id_sucursal: int,
    payload: dict
) -> Dict[str, Any]:

    if id_sucursal <= 0:
        raise HTTPException(
            status_code=400,
            detail="ID de sucursal no válido."
        )

    sucursal = sucursales_repos.obtener_sucursal_por_id(id_sucursal)

    if not sucursal:
        raise HTTPException(
            status_code=404,
            detail="Sucursal no encontrada."
        )

    resolver_sucursal_autorizada(payload, id_sucursal)
    validar_acceso_recurso_tenant(
        payload,
        sucursal.get('id_empresa'),
        "sucursal"
    )

    return {
        "success": True,
        "data": sucursal
    }


def registrar_sucursal(
    data: dict,
    payload: dict,
    request: Optional[Request] = None
) -> Dict[str, Any]:

    if obtener_alcance_usuario(payload) not in ('PLATAFORMA', 'EMPRESA'):
        raise HTTPException(403, detail='Solo administracion de empresa puede crear sucursales.')
    nombre = data.get('nombre') or data.get('nombre_sucursal')
    direccion = data.get('direccion') or data.get('direccion_sucursal')
    telefono = data.get('telefono') or data.get('telefono_sucursal')

    id_ciudad = data.get('id_ciudad')
    ciudad_nombre = data.get('ciudad')
    departamento = data.get('departamento')
    activo = data.get('activo', True)

    # Coordenadas geográficas
    latitud = data.get('latitud')
    longitud = data.get('longitud')

    # Validaciones de obligatoriedad
    if not nombre or not str(nombre).strip():
        raise HTTPException(
            status_code=400,
            detail="El nombre de la sucursal es obligatorio."
        )

    if not direccion or not str(direccion).strip():
        raise HTTPException(
            status_code=400,
            detail="La dirección física de la sucursal es obligatoria."
        )

    if not telefono or not str(telefono).strip():
        raise HTTPException(
            status_code=400,
            detail="El teléfono de contacto de la sucursal es obligatorio."
        )

    # Validación de coordenadas
    if latitud is not None:
        try:
            latitud = float(latitud)

            if latitud < -90 or latitud > 90:
                raise ValueError("La latitud debe estar entre -90 y 90.")

        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="La latitud proporcionada no es válida."
            )

    if longitud is not None:
        try:
            longitud = float(longitud)

            if longitud < -180 or longitud > 180:
                raise ValueError("La longitud debe estar entre -180 y 180.")

        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="La longitud proporcionada no es válida."
            )

    # Aislamiento y Resolución Multi-Tenant
    id_empresa_solicitado = data.get('id_empresa')

    if id_empresa_solicitado in (0, '0', '', None):
        id_empresa_solicitado = None
    else:
        id_empresa_solicitado = int(id_empresa_solicitado)

    id_empresa = resolver_tenant_operacion(
        payload,
        id_empresa_solicitado,
        permitir_global=False
    )

    # Coordenadas por defecto según departamento / ciudad
    DEPARTAMENTO_COORDS = {
        'santa cruz': (-17.7833, -63.1821),
        'la paz': (-16.5000, -68.1500),
        'cochabamba': (-17.3895, -66.1568),
        'chuquisaca': (-19.0333, -65.2627),
        'sucre': (-19.0333, -65.2627),
        'oruro': (-17.9833, -67.1500),
        'potosí': (-19.5836, -65.7531),
        'potosi': (-19.5836, -65.7531),
        'tarija': (-21.5355, -64.7296),
        'beni': (-14.8333, -64.9000),
        'trinidad': (-14.8333, -64.9000),
        'pando': (-11.0267, -68.7692),
        'cobija': (-11.0267, -68.7692),
    }

    # Resolución de Ciudad
    ciudad_existente = None
    if not id_ciudad:

        if (
            ciudad_nombre
            and str(ciudad_nombre).strip()
            and departamento
            and str(departamento).strip()
        ):
            id_ciudad = ciudades_repos.obtener_o_crear_ciudad_db(
                str(ciudad_nombre).strip(),
                str(departamento).strip()
            )

        else:
            raise ValueError(
                "Debe seleccionar o indicar una ciudad y departamento para la sucursal."
            )

    else:

        ciudad_existente = ciudades_repos.obtener_ciudad_por_id_db(id_ciudad)

        if not ciudad_existente:
            raise ValueError("La ciudad seleccionada no es válida.")

    # Si no se suministraron coordenadas o son None, asignar por defecto
    if latitud is None or longitud is None:
        dep_key = (departamento or '').strip().lower()
        if not dep_key and ciudad_existente and isinstance(ciudad_existente, dict):
            dep_key = (ciudad_existente.get('departamento') or '').strip().lower()
        coords_def = DEPARTAMENTO_COORDS.get(dep_key, (-17.7833, -63.1821))
        if latitud is None:
            latitud = coords_def[0]
        if longitud is None:
            longitud = coords_def[1]

    nuevo_id = sucursales_repos.crear_sucursal_db(
        nombre=str(nombre).strip(),
        direccion=str(direccion).strip(),
        telefono=str(telefono).strip(),
        id_ciudad=id_ciudad,
        id_empresa=id_empresa,
        activo=bool(activo),
        latitud=latitud,
        longitud=longitud,
        codigo_sucursal=data.get('codigo_sucursal')
    )

    # Auditoría
    try:
        bitacora_services.registrar_accion(
            modulo="SUCURSALES",
            accion="REGISTRAR_SUCURSAL",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Sucursal",
            id_entidad=str(nuevo_id),
            descripcion=f"Sucursal registrada: {nombre} (Tenant #{id_empresa})",
            datos_nuevos={
                "nombre": nombre,
                "direccion": direccion,
                "telefono": telefono,
                "id_empresa": id_empresa,
                "id_ciudad": id_ciudad,
                "activo": activo,
                "latitud": latitud,
                "longitud": longitud
            },
            request=request
        )

    except Exception as e:
        print(f"[BITACORA] Error al registrar sucursal: {e}")

    return {
        "success": True,
        "message": f"Sucursal '{nombre}' registrada exitosamente",
        "id_sucursal": nuevo_id
    }


def actualizar_sucursal(
    id_sucursal: int,
    data: dict,
    payload: dict,
    request: Optional[Request] = None
) -> Dict[str, Any]:

    if id_sucursal <= 0:
        raise ValueError("ID de sucursal no válido.")

    nombre = data.get('nombre')
    direccion = data.get('direccion')
    telefono = data.get('telefono')
    id_empresa = data.get('id_empresa')
    id_ciudad = data.get('id_ciudad')
    ciudad_nombre = data.get('ciudad')
    departamento = data.get('departamento')
    activo = data.get('activo')

    # Coordenadas geográficas
    latitud = data.get('latitud')
    longitud = data.get('longitud')

    if not nombre or not str(nombre).strip():
        raise ValueError("El nombre de la sucursal es obligatorio.")

    if not direccion or not str(direccion).strip():
        raise ValueError("La dirección de la sucursal es obligatoria.")

    if not telefono or not str(telefono).strip():
        raise ValueError("El teléfono de la sucursal es obligatorio.")

    if activo is None:
        activo = True

    # Validación de coordenadas
    if latitud is not None:
        try:
            latitud = float(latitud)

            if latitud < -90 or latitud > 90:
                raise ValueError("La latitud debe estar entre -90 y 90.")

        except (TypeError, ValueError):
            raise ValueError("La latitud proporcionada no es válida.")

    if longitud is not None:
        try:
            longitud = float(longitud)

            if longitud < -180 or longitud > 180:
                raise ValueError("La longitud debe estar entre -180 y 180.")

        except (TypeError, ValueError):
            raise ValueError("La longitud proporcionada no es válida.")

    sucursal_db = sucursales_repos.obtener_sucursal_por_id(id_sucursal)

    if not sucursal_db:
        raise HTTPException(
            status_code=404,
            detail="Sucursal no encontrada."
        )

    resolver_sucursal_autorizada(payload, id_sucursal)
    validar_acceso_recurso_tenant(
        payload,
        sucursal_db.get('id_empresa'),
        "sucursal"
    )

    if not is_global_admin(payload):

        id_empresa = payload.get('id_empresa')

    else:

        if not id_empresa or not isinstance(id_empresa, int):
            id_empresa = sucursal_db.get('id_empresa')

    if id_empresa != sucursal_db.get('id_empresa'):
        raise HTTPException(409, detail='No se permite trasladar sucursales entre empresas.')

    # Resolución de Ciudad
    if not id_ciudad:

        if (
            ciudad_nombre
            and str(ciudad_nombre).strip()
            and departamento
            and str(departamento).strip()
        ):

            id_ciudad = ciudades_repos.obtener_o_crear_ciudad_db(
                str(ciudad_nombre).strip(),
                str(departamento).strip()
            )

        else:

            id_ciudad = sucursal_db.get('id_ciudad')

    exito = sucursales_repos.actualizar_sucursal_db(
        id_sucursal=id_sucursal,
        nombre=str(nombre).strip(),
        direccion=str(direccion).strip(),
        telefono=str(telefono).strip(),
        id_ciudad=id_ciudad,
        id_empresa=id_empresa,
        activo=bool(activo),
        latitud=latitud,
        longitud=longitud
    )

    if exito:

        try:
            bitacora_services.registrar_accion(
                modulo="SUCURSALES",
                accion="ACTUALIZAR_SUCURSAL",
                nivel="INFO",
                resultado="EXITO",
                payload_jwt=payload,
                entidad="Sucursal",
                id_entidad=str(id_sucursal),
                descripcion=f"Sucursal actualizada: {nombre}",
                datos_anteriores=sucursal_db,
                datos_nuevos={
                    "nombre": nombre,
                    "direccion": direccion,
                    "telefono": telefono,
                    "id_empresa": id_empresa,
                    "id_ciudad": id_ciudad,
                    "activo": activo,
                    "latitud": latitud,
                    "longitud": longitud
                },
                request=request
            )

        except Exception as e:
            print(f"[BITACORA] Error al registrar actualización de sucursal: {e}")

    return {
        "success": True,
        "message": f"Sucursal '{nombre}' actualizada correctamente"
    }


def cambiar_estado_sucursal(
    id_sucursal: int,
    data: dict,
    payload: dict,
    request: Optional[Request] = None
) -> Dict[str, Any]:

    if id_sucursal <= 0:
        raise HTTPException(
            status_code=400,
            detail="ID de sucursal no válido."
        )

    sucursal_db = sucursales_repos.obtener_sucursal_por_id(id_sucursal)

    if not sucursal_db:
        raise HTTPException(
            status_code=404,
            detail="Sucursal no encontrada."
        )

    resolver_sucursal_autorizada(payload, id_sucursal)
    validar_acceso_recurso_tenant(
        payload,
        sucursal_db.get('id_empresa'),
        "sucursal"
    )

    nuevo_activo = bool(data.get('activo', False))

    exito = sucursales_repos.cambiar_estado_sucursal_db(
        id_sucursal,
        nuevo_activo
    )

    if not exito:
        raise HTTPException(
            status_code=500,
            detail="No se pudo actualizar el estado de la sucursal."
        )

    try:
        bitacora_services.registrar_accion(
            modulo="SUCURSALES",
            accion="CAMBIAR_ESTADO_SUCURSAL",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Sucursal",
            id_entidad=str(id_sucursal),
            descripcion=f"Estado de sucursal {sucursal_db.get('nombre')} cambiado a {'ACTIVA' if nuevo_activo else 'INACTIVA'}",
            datos_anteriores={
                "activo": sucursal_db.get("activo")
            },
            datos_nuevos={
                "activo": nuevo_activo
            },
            request=request
        )

    except Exception as e:
        print(f"[BITACORA] Error al registrar cambio de estado de sucursal: {e}")

    return {
        "success": True,
        "message": f"Sucursal {'activada' if nuevo_activo else 'desactivada'} correctamente"
    }


def borrar_sucursal(
    id_sucursal: int,
    payload: dict,
    request: Optional[Request] = None
) -> Dict[str, Any]:

    return cambiar_estado_sucursal(
        id_sucursal,
        {"activo": False},
        payload,
        request
    )