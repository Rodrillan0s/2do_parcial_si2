import re
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from app.modules.catalogo.repos import tallas_colores_repos
from app.modules.admin.services import bitacora_services
from app.core.tenant_guard import (
    es_administrador_global,
    resolver_tenant_operacion,
    validar_acceso_recurso_tenant
)

def is_global_admin(payload: dict) -> bool:
    return es_administrador_global(payload)

def validar_codigo_hex(hex_code: str) -> str:
    if not hex_code or not str(hex_code).strip():
        raise ValueError("El código HEX del color es obligatorio.")
    codigo = str(hex_code).strip().upper()
    if not codigo.startswith('#'):
        codigo = f"#{codigo}"
    if not re.match(r'^#(?:[0-9A-F]{3}){1,2}$', codigo):
        raise ValueError("El código HEX debe tener un formato válido (ej. #FFFFFF o #FFF).")
    return codigo


# ==============================================================================
# SERVICIOS DE TALLAS
# ==============================================================================

def listar_tallas(
    payload: dict,
    solo_activas: bool = False,
    busqueda: Optional[str] = None,
    id_empresa: Optional[int] = None
) -> Dict[str, Any]:
    empresa_id = resolver_tenant_operacion(payload, id_empresa, permitir_global=True)
    tallas = tallas_colores_repos.obtener_tallas(
        id_empresa=empresa_id,
        solo_activas=solo_activas,
        busqueda=busqueda
    )
    return {
        "success": True,
        "message": "Tallas recuperadas exitosamente",
        "data": tallas,
        "total": len(tallas)
    }

def obtener_talla(id_talla: int, payload: dict) -> Dict[str, Any]:
    if id_talla <= 0:
        raise HTTPException(status_code=400, detail="ID de talla no válido.")

    talla = tallas_colores_repos.obtener_talla_por_id(id_talla)
    if not talla:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    validar_acceso_recurso_tenant(payload, talla.get('id_empresa'), "talla")

    return {
        "success": True,
        "data": talla
    }

def registrar_talla(data: dict, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    nombre = data.get('nombre')
    descripcion = data.get('descripcion', '')
    activo = data.get('activo', True)
    if isinstance(activo, str):
        activo = activo.lower() in ('true', '1', 'yes', 't')

    if not nombre or not str(nombre).strip():
        raise HTTPException(status_code=400, detail="El nombre de la talla es obligatorio.")
    nombre = str(nombre).strip()

    id_empresa_solicitado = data.get('id_empresa')
    if id_empresa_solicitado in (0, '0', '', None):
        id_empresa_solicitado = None
    else:
        id_empresa_solicitado = int(id_empresa_solicitado)

    empresa_id = resolver_tenant_operacion(payload, id_empresa_solicitado, permitir_global=False)

    if tallas_colores_repos.verificar_nombre_talla_duplicado(nombre, empresa_id):
        raise HTTPException(status_code=400, detail=f"Ya existe una talla con el nombre '{nombre}' en esta empresa.")

    nuevo_id = tallas_colores_repos.crear_talla_db(
        nombre=nombre,
        descripcion=descripcion.strip() if descripcion else "",
        id_empresa=empresa_id,
        activo=bool(activo)
    )

    if not nuevo_id:
        raise HTTPException(status_code=500, detail="No se pudo registrar la talla en la base de datos.")

    try:
        bitacora_services.registrar_accion(
            modulo="TALLAS",
            accion="CREAR_TALLA",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Talla",
            id_entidad=str(nuevo_id),
            descripcion=f"Talla registrada: '{nombre}' (Tenant #{empresa_id})",
            datos_nuevos={"nombre": nombre, "descripcion": descripcion, "id_empresa": empresa_id, "activo": activo},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar bitácora talla: {e}")

    return {
        "success": True,
        "message": f"Talla '{nombre}' registrada exitosamente",
        "id_talla": nuevo_id
    }

def actualizar_talla(id_talla: int, data: dict, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    if id_talla <= 0:
        raise HTTPException(status_code=400, detail="ID de talla no válido.")

    talla_db = tallas_colores_repos.obtener_talla_por_id(id_talla)
    if not talla_db:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    validar_acceso_recurso_tenant(payload, talla_db.get('id_empresa'), "talla")

    nombre = data.get('nombre')
    if not nombre or not str(nombre).strip():
        raise HTTPException(status_code=400, detail="El nombre de la talla es obligatorio.")
    nombre = str(nombre).strip()

    descripcion = data.get('descripcion', talla_db.get('descripcion', ''))
    empresa_id = talla_db.get('id_empresa')

    if tallas_colores_repos.verificar_nombre_talla_duplicado(nombre, empresa_id, id_talla_excluir=id_talla):
        raise ValueError(f"Ya existe otra talla con el nombre '{nombre}' en esta empresa.")

    activo = data.get('activo', talla_db.get('activo', True))
    if isinstance(activo, str):
        activo = activo.lower() in ('true', '1', 'yes', 't')

    exito = tallas_colores_repos.actualizar_talla_db(
        id_talla=id_talla,
        nombre=nombre,
        descripcion=descripcion.strip() if descripcion else "",
        id_empresa=empresa_id,
        activo=bool(activo)
    )

    if not exito:
        raise ValueError("No se pudo actualizar la talla.")

    try:
        bitacora_services.registrar_accion(
            modulo="TALLAS",
            accion="ACTUALIZAR_TALLA",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Talla",
            id_entidad=str(id_talla),
            descripcion=f"Talla actualizada: '{nombre}' (ID #{id_talla})",
            datos_anteriores=talla_db,
            datos_nuevos={"nombre": nombre, "descripcion": descripcion, "activo": activo},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar bitácora talla: {e}")

    return {
        "success": True,
        "message": f"Talla '{nombre}' actualizada exitosamente"
    }

def cambiar_estado_talla(id_talla: int, activo: bool, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    if id_talla <= 0:
        raise HTTPException(status_code=400, detail="ID de talla no válido.")

    talla_db = tallas_colores_repos.obtener_talla_por_id(id_talla)
    if not talla_db:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    validar_acceso_recurso_tenant(payload, talla_db.get('id_empresa'), "talla")

    exito = tallas_colores_repos.cambiar_estado_talla_db(id_talla, bool(activo))
    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo cambiar el estado de la talla.")

    try:
        bitacora_services.registrar_accion(
            modulo="TALLAS",
            accion="CAMBIAR_ESTADO_TALLA",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Talla",
            id_entidad=str(id_talla),
            descripcion=f"Talla '{talla_db.get('nombre')}' {'activada' if activo else 'desactivada'}",
            datos_anteriores={"activo": talla_db.get("activo")},
            datos_nuevos={"activo": activo},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar cambio de estado talla: {e}")

    return {
        "success": True,
        "message": f"Talla '{talla_db.get('nombre')}' {'activada' if activo else 'desactivada'} correctamente",
        "activo": activo
    }

def eliminar_talla(id_talla: int, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    if id_talla <= 0:
        raise HTTPException(status_code=400, detail="ID de talla no válido.")

    talla_db = tallas_colores_repos.obtener_talla_por_id(id_talla)
    if not talla_db:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    validar_acceso_recurso_tenant(payload, talla_db.get('id_empresa'), "talla")

    variantes_vinculadas = tallas_colores_repos.contar_variantes_por_talla(id_talla)
    if variantes_vinculadas > 0:
        tallas_colores_repos.cambiar_estado_talla_db(id_talla, False)
        try:
            bitacora_services.registrar_accion(
                modulo="TALLAS",
                accion="DESACTIVAR_TALLA_POR_PRODUCTOS",
                nivel="WARN",
                resultado="EXITO",
                payload_jwt=payload,
                entidad="Talla",
                id_entidad=str(id_talla),
                descripcion=f"Intento de eliminación: Talla '{talla_db.get('nombre')}' desactivada preventivamente al tener {variantes_vinculadas} variantes de producto vinculadas.",
                datos_anteriores={"activo": talla_db.get("activo")},
                datos_nuevos={"activo": False, "variantes_asociadas": variantes_vinculadas},
                request=request
            )
        except Exception as e:
            print(f"[BITACORA] Error al registrar bitácora desactivación talla: {e}")

        return {
            "success": True,
            "eliminado_fisico": False,
            "message": f"La talla cuenta con {variantes_vinculadas} variante(s) de producto vinculadas. Por integridad del catálogo de la tienda no se permite eliminación física; la talla fue desactivada automáticamente."
        }

    exito = tallas_colores_repos.eliminar_talla_fisico_db(id_talla)
    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo eliminar la talla de la base de datos.")

    try:
        bitacora_services.registrar_accion(
            modulo="TALLAS",
            accion="ELIMINAR_TALLA",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Talla",
            id_entidad=str(id_talla),
            descripcion=f"Talla eliminada físicamente: '{talla_db.get('nombre')}'",
            datos_anteriores=talla_db,
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar bitácora eliminación física talla: {e}")

    return {
        "success": True,
        "eliminado_fisico": True,
        "message": f"Talla '{talla_db.get('nombre')}' eliminada exitosamente."
    }


# ==============================================================================
# SERVICIOS DE COLORES
# ==============================================================================

def listar_colores(
    payload: dict,
    solo_activos: bool = False,
    busqueda: Optional[str] = None,
    id_empresa: Optional[int] = None
) -> Dict[str, Any]:
    empresa_id = resolver_tenant_operacion(payload, id_empresa, permitir_global=True)
    colores = tallas_colores_repos.obtener_colores(
        id_empresa=empresa_id,
        solo_activos=solo_activos,
        busqueda=busqueda
    )
    return {
        "success": True,
        "message": "Colores recuperados exitosamente",
        "data": colores,
        "total": len(colores)
    }

def obtener_color(id_color: int, payload: dict) -> Dict[str, Any]:
    if id_color <= 0:
        raise HTTPException(status_code=400, detail="ID de color no válido.")

    color = tallas_colores_repos.obtener_color_por_id(id_color)
    if not color:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    validar_acceso_recurso_tenant(payload, color.get('id_empresa'), "color")

    return {
        "success": True,
        "data": color
    }

def registrar_color(data: dict, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    nombre = data.get('nombre')
    codigo_hex = data.get('codigo_hex')
    activo = data.get('activo', True)
    if isinstance(activo, str):
        activo = activo.lower() in ('true', '1', 'yes', 't')

    if not nombre or not str(nombre).strip():
        raise HTTPException(status_code=400, detail="El nombre del color es obligatorio.")
    nombre = str(nombre).strip()

    hex_validado = validar_codigo_hex(codigo_hex)

    id_empresa_solicitado = data.get('id_empresa')
    if id_empresa_solicitado in (0, '0', '', None):
        id_empresa_solicitado = None
    else:
        id_empresa_solicitado = int(id_empresa_solicitado)

    empresa_id = resolver_tenant_operacion(payload, id_empresa_solicitado, permitir_global=False)

    if tallas_colores_repos.verificar_nombre_color_duplicado(nombre, empresa_id):
        raise HTTPException(status_code=400, detail=f"Ya existe un color con el nombre '{nombre}' en esta empresa.")

    nuevo_id = tallas_colores_repos.crear_color_db(
        nombre=nombre,
        codigo_hex=hex_validado,
        id_empresa=empresa_id,
        activo=bool(activo)
    )

    if not nuevo_id:
        raise HTTPException(status_code=500, detail="No se pudo registrar el color en la base de datos.")

    try:
        bitacora_services.registrar_accion(
            modulo="COLORES",
            accion="CREAR_COLOR",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Color",
            id_entidad=str(nuevo_id),
            descripcion=f"Color registrado: '{nombre}' ({hex_validado}, Tenant #{empresa_id})",
            datos_nuevos={"nombre": nombre, "codigo_hex": hex_validado, "id_empresa": empresa_id, "activo": activo},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar bitácora color: {e}")

    return {
        "success": True,
        "message": f"Color '{nombre}' registrado exitosamente",
        "id_color": nuevo_id
    }

def actualizar_color(id_color: int, data: dict, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    if id_color <= 0:
        raise HTTPException(status_code=400, detail="ID de color no válido.")

    color_db = tallas_colores_repos.obtener_color_por_id(id_color)
    if not color_db:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    validar_acceso_recurso_tenant(payload, color_db.get('id_empresa'), "color")

    nombre = data.get('nombre')
    if not nombre or not str(nombre).strip():
        raise HTTPException(status_code=400, detail="El nombre del color es obligatorio.")
    nombre = str(nombre).strip()

    codigo_hex = data.get('codigo_hex', color_db.get('codigo_hex'))
    hex_validado = validar_codigo_hex(codigo_hex)
    empresa_id = color_db.get('id_empresa')

    if tallas_colores_repos.verificar_nombre_color_duplicado(nombre, empresa_id, id_color_excluir=id_color):
        raise HTTPException(status_code=400, detail=f"Ya existe otro color con el nombre '{nombre}' en esta empresa.")

    activo = data.get('activo', color_db.get('activo', True))
    if isinstance(activo, str):
        activo = activo.lower() in ('true', '1', 'yes', 't')

    exito = tallas_colores_repos.actualizar_color_db(
        id_color=id_color,
        nombre=nombre,
        codigo_hex=hex_validado,
        id_empresa=empresa_id,
        activo=bool(activo)
    )

    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo actualizar el color.")

    try:
        bitacora_services.registrar_accion(
            modulo="COLORES",
            accion="ACTUALIZAR_COLOR",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Color",
            id_entidad=str(id_color),
            descripcion=f"Color actualizado: '{nombre}' ({hex_validado}, ID #{id_color})",
            datos_anteriores=color_db,
            datos_nuevos={"nombre": nombre, "codigo_hex": hex_validado, "activo": activo},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar bitácora color: {e}")

    return {
        "success": True,
        "message": f"Color '{nombre}' actualizado exitosamente"
    }

def cambiar_estado_color(id_color: int, activo: bool, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    if id_color <= 0:
        raise HTTPException(status_code=400, detail="ID de color no válido.")

    color_db = tallas_colores_repos.obtener_color_por_id(id_color)
    if not color_db:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    validar_acceso_recurso_tenant(payload, color_db.get('id_empresa'), "color")

    exito = tallas_colores_repos.cambiar_estado_color_db(id_color, bool(activo))
    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo cambiar el estado del color.")

    try:
        bitacora_services.registrar_accion(
            modulo="COLORES",
            accion="CAMBIAR_ESTADO_COLOR",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Color",
            id_entidad=str(id_color),
            descripcion=f"Color '{color_db.get('nombre')}' {'activado' if activo else 'desactivado'}",
            datos_anteriores={"activo": color_db.get("activo")},
            datos_nuevos={"activo": activo},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar cambio de estado color: {e}")

    return {
        "success": True,
        "message": f"Color '{color_db.get('nombre')}' {'activado' if activo else 'desactivado'} correctamente",
        "activo": activo
    }

def eliminar_color(id_color: int, payload: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    if id_color <= 0:
        raise HTTPException(status_code=400, detail="ID de color no válido.")

    color_db = tallas_colores_repos.obtener_color_por_id(id_color)
    if not color_db:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    validar_acceso_recurso_tenant(payload, color_db.get('id_empresa'), "color")

    variantes_vinculadas = tallas_colores_repos.contar_variantes_por_color(id_color)
    if variantes_vinculadas > 0:
        tallas_colores_repos.cambiar_estado_color_db(id_color, False)
        try:
            bitacora_services.registrar_accion(
                modulo="COLORES",
                accion="DESACTIVAR_COLOR_POR_PRODUCTOS",
                nivel="WARN",
                resultado="EXITO",
                payload_jwt=payload,
                entidad="Color",
                id_entidad=str(id_color),
                descripcion=f"Intento de eliminación: Color '{color_db.get('nombre')}' desactivado preventivamente al tener {variantes_vinculadas} variantes vinculadas.",
                datos_anteriores={"activo": color_db.get("activo")},
                datos_nuevos={"activo": False, "variantes_asociadas": variantes_vinculadas},
                request=request
            )
        except Exception as e:
            print(f"[BITACORA] Error al registrar bitácora desactivación color: {e}")

        return {
            "success": True,
            "eliminado_fisico": False,
            "message": f"El color cuenta con {variantes_vinculadas} variante(s) de producto vinculadas. Por integridad del catálogo de la tienda no se permite eliminación física; el color fue desactivado automáticamente."
        }

    exito = tallas_colores_repos.eliminar_color_fisico_db(id_color)
    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo eliminar el color de la base de datos.")

    try:
        bitacora_services.registrar_accion(
            modulo="COLORES",
            accion="ELIMINAR_COLOR",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Color",
            id_entidad=str(id_color),
            descripcion=f"Color eliminado físicamente: '{color_db.get('nombre')}'",
            datos_anteriores=color_db,
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar bitácora eliminación física color: {e}")

    return {
        "success": True,
        "eliminado_fisico": True,
        "message": f"Color '{color_db.get('nombre')}' eliminado exitosamente."
    }
