from typing import Optional, Dict, Any
from fastapi import Request
from app.modules.inventario.repos import ciudades_repos
from app.modules.admin.services import bitacora_services
DEPARTAMENTOS_BOLIVIA = [
    "Santa Cruz", "La Paz", "Cochabamba", "Chuquisaca", "Oruro", 
    "Potosí", "Tarija", "Beni", "Pando"
]

def listar_ciudades(solo_activas: bool = False, busqueda: Optional[str] = None) -> Dict[str, Any]:
    ciudades = ciudades_repos.obtener_todas_ciudades_db(solo_activas=solo_activas, busqueda=busqueda)
    return {
        "success": True,
        "message": "Ciudades recuperadas exitosamente",
        "data": ciudades
    }

def registrar_ciudad(data: dict, payload_jwt: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    nombre = data.get("nombre")
    departamento = data.get("departamento")
    estado = data.get("estado", True)

    if not nombre or not str(nombre).strip():
        raise ValueError("El nombre de la ciudad es obligatorio.")

    if not departamento or not str(departamento).strip():
        raise ValueError("El departamento es obligatorio.")

    nombre_limpio = str(nombre).strip()
    depto_limpio = str(departamento).strip()

    if ciudades_repos.existe_ciudad_db(nombre_limpio, depto_limpio):
        raise ValueError(f"Ya existe la ciudad '{nombre_limpio}' en el departamento de {depto_limpio}.")

    id_ciudad = ciudades_repos.crear_ciudad_db(nombre_limpio, depto_limpio, bool(estado))

    # Registro en Bitácora
    try:
        bitacora_services.registrar_accion(
            modulo="CIUDADES",
            accion="REGISTRAR_CIUDAD",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload_jwt,
            entidad="Ciudad",
            id_entidad=str(id_ciudad),
            descripcion=f"Registro de ciudad: {nombre_limpio} ({depto_limpio})",
            datos_nuevos={"nombre": nombre_limpio, "departamento": depto_limpio, "estado": estado},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar auditoría de ciudad: {e}")

    return {
        "success": True,
        "message": f"Ciudad '{nombre_limpio}' registrada exitosamente",
        "id_ciudad": id_ciudad
    }

def actualizar_ciudad(id_ciudad: int, data: dict, payload_jwt: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    if id_ciudad <= 0:
        raise ValueError("ID de ciudad inválido.")

    ciudad_existente = ciudades_repos.obtener_ciudad_por_id_db(id_ciudad)
    if not ciudad_existente:
        raise ValueError("La ciudad no existe.")

    nombre = data.get("nombre")
    departamento = data.get("departamento")
    estado = data.get("estado", ciudad_existente.get("estado"))

    if not nombre or not str(nombre).strip():
        raise ValueError("El nombre de la ciudad es obligatorio.")

    if not departamento or not str(departamento).strip():
        raise ValueError("El departamento es obligatorio.")

    nombre_limpio = str(nombre).strip()
    depto_limpio = str(departamento).strip()

    if ciudades_repos.existe_ciudad_db(nombre_limpio, depto_limpio, exclude_id=id_ciudad):
        raise ValueError(f"Ya existe otra ciudad con el nombre '{nombre_limpio}' en {depto_limpio}.")

    exito = ciudades_repos.actualizar_ciudad_db(id_ciudad, nombre_limpio, depto_limpio, bool(estado))
    if not exito:
        raise ValueError("No se pudo actualizar la ciudad en la base de datos.")

    try:
        bitacora_services.registrar_accion(
            modulo="CIUDADES",
            accion="ACTUALIZAR_CIUDAD",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload_jwt,
            entidad="Ciudad",
            id_entidad=str(id_ciudad),
            descripcion=f"Actualización de ciudad: {nombre_limpio} ({depto_limpio})",
            datos_anteriores=ciudad_existente,
            datos_nuevos={"nombre": nombre_limpio, "departamento": depto_limpio, "estado": estado},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar auditoría de ciudad: {e}")

    return {
        "success": True,
        "message": f"Ciudad '{nombre_limpio}' actualizada correctamente"
    }

def cambiar_estado_ciudad(id_ciudad: int, data: dict, payload_jwt: dict, request: Optional[Request] = None) -> Dict[str, Any]:
    if id_ciudad <= 0:
        raise ValueError("ID de ciudad inválido.")

    ciudad_existente = ciudades_repos.obtener_ciudad_por_id_db(id_ciudad)
    if not ciudad_existente:
        raise ValueError("La ciudad no existe.")

    nuevo_estado = bool(data.get("estado", False))
    exito = ciudades_repos.cambiar_estado_ciudad_db(id_ciudad, nuevo_estado)
    if not exito:
        raise ValueError("No se pudo cambiar el estado de la ciudad.")

    try:
        bitacora_services.registrar_accion(
            modulo="CIUDADES",
            accion="CAMBIAR_ESTADO_CIUDAD",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload_jwt,
            entidad="Ciudad",
            id_entidad=str(id_ciudad),
            descripcion=f"Cambio de estado de ciudad: {ciudad_existente.get('nombre')} -> {'ACTIVO' if nuevo_estado else 'INACTIVO'}",
            datos_anteriores={"estado": ciudad_existente.get("estado")},
            datos_nuevos={"estado": nuevo_estado},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar auditoría de ciudad: {e}")

    return {
        "success": True,
        "message": f"Estado de la ciudad actualizado a {'ACTIVA' if nuevo_estado else 'INACTIVA'}"
    }
