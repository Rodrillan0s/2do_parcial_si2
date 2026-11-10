from typing import Optional, Dict, Any, List
from fastapi import Request, UploadFile, HTTPException, status
from app.modules.catalogo.repos import categorias_repos
from app.modules.admin.services import bitacora_services
from app.shared.cloudinary_service import subir_imagen_cloudinary, eliminar_imagen_cloudinary
from app.core.tenant_guard import (
    es_administrador_global,
    resolver_tenant_operacion,
    validar_acceso_recurso_tenant
)

def is_global_admin(payload: dict) -> bool:
    return es_administrador_global(payload)

def listar_categorias(
    payload: dict,
    solo_activas: bool = False,
    busqueda: Optional[str] = None,
    id_empresa: Optional[int] = None
) -> Dict[str, Any]:
    empresa_id = resolver_tenant_operacion(payload, id_empresa, permitir_global=True)
    categorias = categorias_repos.obtener_categorias(
        id_empresa=empresa_id,
        solo_activas=solo_activas,
        busqueda=busqueda
    )
    return {
        "success": True,
        "message": "Categorías obtenidas exitosamente",
        "data": categorias,
        "total": len(categorias)
    }

def obtener_categoria(id_categoria: int, payload: dict) -> Dict[str, Any]:
    if id_categoria <= 0:
        raise HTTPException(status_code=400, detail="ID de categoría no válido.")

    categoria = categorias_repos.obtener_categoria_por_id(id_categoria)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    validar_acceso_recurso_tenant(payload, categoria.get('id_empresa'), "categoría")

    return {
        "success": True,
        "data": categoria
    }

def registrar_categoria(
    data: dict,
    payload: dict,
    request: Optional[Request] = None,
    imagen_file: Optional[UploadFile] = None
) -> Dict[str, Any]:
    nombre = data.get('nombre')
    descripcion = data.get('descripcion', '')
    id_padre = data.get('id_padre')
    id_empresa = data.get('id_empresa')
    activo = data.get('activo', True)
    if isinstance(activo, str):
        activo = activo.lower() in ('true', '1', 'yes', 't')

    if not nombre or not str(nombre).strip():
        raise ValueError("El nombre de la categoría es obligatorio.")
    nombre = str(nombre).strip()

    # Validar Tenant
    id_empresa_solicitado = data.get('id_empresa')
    if id_empresa_solicitado in (0, '0', '', None):
        id_empresa_solicitado = None
    else:
        id_empresa_solicitado = int(id_empresa_solicitado)

    empresa_id = resolver_tenant_operacion(payload, id_empresa_solicitado, permitir_global=False)

    # Validar Unicidad de Nombre en el Tenant
    if categorias_repos.verificar_nombre_duplicado(nombre, empresa_id):
        raise HTTPException(status_code=400, detail=f"Ya existe una categoría con el nombre '{nombre}' en esta empresa.")

    # Validar Categoría Padre si se proporciona
    if id_padre:
        try:
            id_padre = int(id_padre)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="El ID de la categoría padre debe ser un número entero.")

        padre_db = categorias_repos.obtener_categoria_por_id(id_padre)
        if not padre_db:
            raise HTTPException(status_code=400, detail="La categoría padre seleccionada no existe.")

        # Validar mismo Tenant
        if empresa_id and padre_db.get('id_empresa') and int(padre_db['id_empresa']) != int(empresa_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La categoría padre debe pertenecer al mismo Tenant.")

    imagen_url = data.get('imagen_url')
    imagen_public_id = data.get('imagen_public_id')

    # Subida a Cloudinary si se adjunta archivo
    if imagen_file and imagen_file.filename:
        try:
            res_cloud = subir_imagen_cloudinary(imagen_file.file, folder="aurora_store/categorias")
            imagen_url = res_cloud.get("url")
            imagen_public_id = res_cloud.get("public_id")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al subir imagen a Cloudinary: {str(e)}")

    nuevo_id = categorias_repos.crear_categoria_db(
        nombre=nombre,
        descripcion=descripcion,
        id_padre=id_padre,
        id_empresa=empresa_id,
        imagen_url=imagen_url,
        imagen_public_id=imagen_public_id,
        activo=bool(activo)
    )

    if not nuevo_id:
        raise HTTPException(status_code=500, detail="No se pudo registrar la categoría en la base de datos.")

    # Bitácora de Auditoría
    try:
        bitacora_services.registrar_accion(
            modulo="CATEGORIAS",
            accion="CREAR_CATEGORIA",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Categoria",
            id_entidad=str(nuevo_id),
            descripcion=f"Categoría creada: '{nombre}' (Tenant #{empresa_id})",
            datos_nuevos={
                "nombre": nombre,
                "descripcion": descripcion,
                "id_padre": id_padre,
                "id_empresa": empresa_id,
                "imagen_url": imagen_url,
                "activo": activo
            },
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar bitácora categoría: {e}")

    return {
        "success": True,
        "message": f"Categoría '{nombre}' registrada exitosamente",
        "id_categoria": nuevo_id
    }

def actualizar_categoria(
    id_categoria: int,
    data: dict,
    payload: dict,
    request: Optional[Request] = None,
    imagen_file: Optional[UploadFile] = None
) -> Dict[str, Any]:
    if id_categoria <= 0:
        raise HTTPException(status_code=400, detail="ID de categoría no válido.")

    categoria_db = categorias_repos.obtener_categoria_por_id(id_categoria)
    if not categoria_db:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    # Tenant check
    validar_acceso_recurso_tenant(payload, categoria_db.get('id_empresa'), "categoría")

    nombre = data.get('nombre')
    if not nombre or not str(nombre).strip():
        raise HTTPException(status_code=400, detail="El nombre de la categoría es obligatorio.")
    nombre = str(nombre).strip()

    descripcion = data.get('descripcion', categoria_db.get('descripcion', ''))
    id_padre = data.get('id_padre')
    empresa_id = categoria_db.get('id_empresa')

    # Parsear id_padre
    if id_padre is not None and str(id_padre).strip() != '' and str(id_padre).lower() != 'null':
        try:
            id_padre = int(id_padre)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="El ID de categoría padre debe ser un número entero.")
    else:
        id_padre = None

    # Validar que una categoría no sea su propia categoría padre
    if id_padre is not None:
        if id_padre == id_categoria:
            raise HTTPException(status_code=400, detail="Una categoría no puede ser su propia categoría padre.")

        # Validar que no se generen ciclos jerárquicos
        if categorias_repos.es_ancestro_o_ciclo(id_categoria, id_padre):
            raise HTTPException(status_code=400, detail="No se puede seleccionar una subcategoría descendiente como categoría padre (evitar ciclos).")

        padre_db = categorias_repos.obtener_categoria_por_id(id_padre)
        if not padre_db:
            raise HTTPException(status_code=400, detail="La categoría padre especificada no existe.")
        if empresa_id and padre_db.get('id_empresa') and int(padre_db['id_empresa']) != int(empresa_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La categoría padre debe pertenecer al mismo Tenant.")

    # Validar unicidad de nombre excluyendo la actual
    if categorias_repos.verificar_nombre_duplicado(nombre, empresa_id, id_categoria_excluir=id_categoria):
        raise HTTPException(status_code=400, detail=f"Ya existe otra categoría con el nombre '{nombre}' en esta empresa.")

    activo = data.get('activo', categoria_db.get('activo', True))
    if isinstance(activo, str):
        activo = activo.lower() in ('true', '1', 'yes', 't')

    imagen_url = data.get('imagen_url')
    imagen_public_id = data.get('imagen_public_id')

    # Subir nueva imagen si se proporciona archivo
    if imagen_file and imagen_file.filename:
        try:
            old_pub_id = categoria_db.get('imagen_public_id')
            if old_pub_id:
                try:
                    eliminar_imagen_cloudinary(old_pub_id)
                except Exception as ex_del:
                    print(f"[CLOUDINARY] Advertencia al eliminar imagen previa: {ex_del}")

            res_cloud = subir_imagen_cloudinary(imagen_file.file, folder="aurora_store/categorias")
            imagen_url = res_cloud.get("url")
            imagen_public_id = res_cloud.get("public_id")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al subir imagen a Cloudinary: {str(e)}")

    exito = categorias_repos.actualizar_categoria_db(
        id_categoria=id_categoria,
        nombre=nombre,
        descripcion=descripcion,
        id_padre=id_padre,
        id_empresa=empresa_id,
        imagen_url=imagen_url,
        imagen_public_id=imagen_public_id,
        activo=bool(activo)
    )

    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo actualizar la categoría.")

    # Auditoría
    try:
        bitacora_services.registrar_accion(
            modulo="CATEGORIAS",
            accion="ACTUALIZAR_CATEGORIA",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Categoria",
            id_entidad=str(id_categoria),
            descripcion=f"Categoría actualizada: '{nombre}' (ID #{id_categoria})",
            datos_anteriores=categoria_db,
            datos_nuevos={
                "nombre": nombre,
                "descripcion": descripcion,
                "id_padre": id_padre,
                "activo": activo,
                "imagen_url": imagen_url
            },
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar bitácora categoría: {e}")

    return {
        "success": True,
        "message": f"Categoría '{nombre}' actualizada exitosamente"
    }

def cambiar_estado_categoria(
    id_categoria: int,
    activo: bool,
    payload: dict,
    request: Optional[Request] = None
) -> Dict[str, Any]:
    if id_categoria <= 0:
        raise HTTPException(status_code=400, detail="ID de categoría no válido.")

    categoria_db = categorias_repos.obtener_categoria_por_id(id_categoria)
    if not categoria_db:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    validar_acceso_recurso_tenant(payload, categoria_db.get('id_empresa'), "categoría")

    exito = categorias_repos.cambiar_estado_categoria_db(id_categoria, bool(activo))
    if not exito:
        raise HTTPException(status_code=500, detail="No se pudo cambiar el estado de la categoría.")

    # Auditoría
    try:
        bitacora_services.registrar_accion(
            modulo="CATEGORIAS",
            accion="CAMBIAR_ESTADO_CATEGORIA",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Categoria",
            id_entidad=str(id_categoria),
            descripcion=f"Categoría '{categoria_db.get('nombre')}' {'activada' if activo else 'desactivada'}",
            datos_anteriores={"activo": categoria_db.get("activo")},
            datos_nuevos={"activo": activo},
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar cambio de estado categoría: {e}")

    return {
        "success": True,
        "message": f"Categoría '{categoria_db.get('nombre')}' {'activada' if activo else 'desactivada'} correctamente",
        "activo": activo
    }

def eliminar_categoria(
    id_categoria: int,
    payload: dict,
    request: Optional[Request] = None
) -> Dict[str, Any]:
    if id_categoria <= 0:
        raise HTTPException(status_code=400, detail="ID de categoría no válido.")

    categoria_db = categorias_repos.obtener_categoria_por_id(id_categoria)
    if not categoria_db:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    validar_acceso_recurso_tenant(payload, categoria_db.get('id_empresa'), "categoría")

    # Regla de integridad: No eliminar físicamente si tiene productos asociados
    productos_vinculados = categorias_repos.contar_productos_por_categoria(id_categoria)
    if productos_vinculados > 0:
        # Desactivar en su lugar
        categorias_repos.cambiar_estado_categoria_db(id_categoria, False)

        try:
            bitacora_services.registrar_accion(
                modulo="CATEGORIAS",
                accion="DESACTIVAR_CATEGORIA_POR_PRODUCTOS",
                nivel="WARN",
                resultado="EXITO",
                payload_jwt=payload,
                entidad="Categoria",
                id_entidad=str(id_categoria),
                descripcion=f"Intento de eliminación: Categoría '{categoria_db.get('nombre')}' desactivada automáticamente porque contiene {productos_vinculados} productos asociados.",
                datos_anteriores={"activo": categoria_db.get("activo")},
                datos_nuevos={"activo": False, "productos_asociados": productos_vinculados},
                request=request
            )
        except Exception as e:
            print(f"[BITACORA] Error al registrar bitácora desactivación: {e}")

        return {
            "success": True,
            "eliminado_fisico": False,
            "message": f"La categoría cuenta con {productos_vinculados} producto(s) vinculado(s). Por integridad del catálogo de la tienda no se permite eliminación física; la categoría fue desactivada automáticamente."
        }

    # Si no tiene productos, eliminar imagen de Cloudinary si existe y eliminar físicamente
    old_pub_id = categoria_db.get('imagen_public_id')
    if old_pub_id:
        try:
            eliminar_imagen_cloudinary(old_pub_id)
        except Exception as ex_cloud:
            print(f"[CLOUDINARY] No se pudo eliminar imagen en Cloudinary: {ex_cloud}")

    exito = categorias_repos.eliminar_categoria_fisico_db(id_categoria)
    if not exito:
        raise ValueError("No se pudo eliminar la categoría de la base de datos.")

    try:
        bitacora_services.registrar_accion(
            modulo="CATEGORIAS",
            accion="ELIMINAR_CATEGORIA",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="Categoria",
            id_entidad=str(id_categoria),
            descripcion=f"Categoría eliminada físicamente: '{categoria_db.get('nombre')}'",
            datos_anteriores=categoria_db,
            request=request
        )
    except Exception as e:
        print(f"[BITACORA] Error al registrar bitácora eliminación física: {e}")

    return {
        "success": True,
        "eliminado_fisico": True,
        "message": f"Categoría '{categoria_db.get('nombre')}' eliminada exitosamente."
    }
