from app.modules.auth.repos import roles_repos
from fastapi import Request
from app.modules.admin.services import bitacora_services
def is_global_admin(payload: dict) -> bool:
    from app.core.tenant_guard import es_administrador_global
    return es_administrador_global(payload)


def listar_roles(payload: dict):
    roles = roles_repos.obtener_todos_los_roles()
    
    if not is_global_admin(payload):
        # Filtrar roles globales (como ADMINISTRADOR) para usuarios de tienda
        roles = [r for r in roles if r.get('nombre_rol', '').upper() != 'ADMINISTRADOR' and r.get('id_rol') != 1]
        
    return {
        "success": True,
        "message": "Roles recuperados exitosamente",
        "data": roles
    }

def registrar_rol(data: dict, payload: dict, request: Request = None):
    nombre_rol = data.get('nombre_rol')
    descripcion = data.get('descripcion')
    
    if not nombre_rol or len(nombre_rol.strip()) == 0:
        raise ValueError("El campo 'nombre_rol' es obligatorio.")

    # Guardamos el nombre del rol siempre en mayúsculas (ej. ADMINISTRADOR, MECANICO)
    nuevo_id = roles_repos.crear_rol_db(nombre_rol.upper(), descripcion)

    bitacora_services.registrar_accion(
        modulo="ROLES", accion="ROL_CREADO", nivel="INFO", resultado="EXITO",
        payload_jwt=payload, entidad="Rol", id_entidad=str(nuevo_id),
        descripcion=f"Rol creado: {nombre_rol.upper()}",
        datos_nuevos={"nombre_rol": nombre_rol.upper(), "descripcion": descripcion},
        request=request
    )

    return {
        "success": True,
        "message": "Rol registrado exitosamente",
        "id_rol": nuevo_id
    }

def actualizar_rol(id_rol: int, data: dict, payload: dict, request: Request = None):
    nro_rol = id_rol
    if nro_rol <= 0:
        raise ValueError("ID de rol no válido.")
        
    nombre_rol = data.get('nombre_rol')
    descripcion = data.get('descripcion')
    
    if not nombre_rol or len(nombre_rol.strip()) == 0:
        raise ValueError("El campo 'nombre_rol' es obligatorio.")

    # Get previous state for audit log if needed
    rol_db = None
    try:
        from app.core.postgres import PostgreSQL
        db = PostgreSQL()
        db.create_connection()
        r = db.execute_query(f"SELECT id_rol, nombre, descripcion FROM comercio.t_rol WHERE id_rol = %s", (nro_rol,), fetchone=True)
        if r:
            rol_db = {"id_rol": r[0], "nombre_rol": r[1], "descripcion": r[2]}
        db.close_connection()
    except Exception:
        pass

    exito = roles_repos.actualizar_rol_db(nro_rol, nombre_rol.upper(), descripcion)

    if not exito:
        raise ValueError(f"No se pudo actualizar. El rol con ID {nro_rol} no existe.")

    if exito:
        bitacora_services.registrar_accion(
            modulo="ROLES", accion="ROL_EDITADO", nivel="INFO", resultado="EXITO",
            payload_jwt=payload, entidad="Rol", id_entidad=str(nro_rol),
            descripcion=f"Rol editado: {nombre_rol.upper()}",
            datos_anteriores=rol_db,
            datos_nuevos={"nombre_rol": nombre_rol.upper(), "descripcion": descripcion},
            request=request
        )

    return {
        "success": True,
        "message": "Rol actualizado exitosamente"
    }

def borrar_rol(id_rol: int, payload: dict, request: Request = None):
    nro_rol = id_rol
    if nro_rol <= 0:
        raise ValueError("ID de rol no válido.")
        
    exito = roles_repos.eliminar_rol_db(nro_rol)
    
    if not exito:
        raise ValueError(f"No se pudo eliminar. El rol con ID {nro_rol} no existe.")
    
    bitacora_services.registrar_accion(
        modulo="ROLES", accion="ROL_ELIMINADO", nivel="WARNING", resultado="EXITO",
        payload_jwt=payload, entidad="Rol", id_entidad=str(nro_rol),
        descripcion=f"Rol eliminado",
        request=request
    )
    
    return {
        "success": True,
        "message": "Rol eliminado correctamente."
    }