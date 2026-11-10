from app.modules.auth.repos import rbac_repos
# --- LEER ROLES ---
def obtener_todos_los_roles():
    roles = rbac_repos.obtener_todos_los_roles()
    res = []
    for r in roles:
        res.append({
            "nro_rol": r["id_rol"],
            "id_rol": r["id_rol"],
            "nombre_rol": r["nombre"],
            "nombre": r["nombre"],
            "descripcion": r["descripcion"],
            "activo": r.get("activo", True),
            "fecha_registro": r.get("created_at")
        })
    return res

# --- CREAR ROL ---
def crear_rol_db(nombre_rol, descripcion):
    return rbac_repos.crear_rol(nombre_rol, descripcion)

# --- ACTUALIZAR ROL ---
def actualizar_rol_db(nro_rol, nombre_rol, descripcion):
    return rbac_repos.actualizar_rol(nro_rol, nombre_rol, descripcion, True)

# --- ELIMINAR ROL (Desactivación Lógica) ---
def eliminar_rol_db(nro_rol: int):
    return rbac_repos.desactivar_rol(nro_rol)