from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from app.modules.catalogo.repos import productos_repos
from app.modules.admin.services import bitacora_services
from app.shared import cloudinary_service
from app.core.postgres import PostgreSQL, atomic
from app.core.config import Config

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'

# ==============================================================================
# VALIDACIONES DE NEGOCIO
# ==============================================================================

def _validar_categoria_activa(id_categoria: int, id_empresa: Optional[int]):
    """Verifica que la categoría exista, pertenezca al Tenant y esté activa."""
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        query = f"""
            SELECT activo, estado, id_empresa, nombre 
            FROM {schema}.t_categoria 
            WHERE id_categoria = %s;
        """
        cat = db.execute_query(query, (id_categoria,), fetchone=True)
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La categoría seleccionada no existe."
            )
        activo = bool(cat[0] and cat[1])
        if not activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La categoría '{cat[3]}' se encuentra inactiva y no puede ser utilizada para nuevos productos."
            )
        # Si el usuario tiene Tenant, comprobar pertenencia
        if id_empresa and cat[2] is not None and cat[2] != id_empresa:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La categoría seleccionada pertenece a otra empresa o Tenant."
            )
    finally:
        db.close_connection()

def _validar_tallas_activas(tallas_ids: List[int], id_empresa: Optional[int]):
    """Verifica que todas las tallas seleccionadas existan y estén activas en el Tenant (en 1 sola consulta)."""
    if not tallas_ids:
        return
    tallas_unicas = list(dict.fromkeys(int(t) for t in tallas_ids if t is not None))
    if not tallas_unicas:
        return
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        rows = db.execute_query(
            f"SELECT id_talla, activo, estado, nombre, id_empresa FROM {schema}.t_talla WHERE id_talla = ANY(%s);",
            (tallas_unicas,),
            fetchall=True
        ) or []
        mapa = {int(r[0]): r for r in rows}
        for t_id in tallas_unicas:
            row = mapa.get(t_id)
            if not row:
                raise HTTPException(status_code=400, detail=f"La talla con ID {t_id} no existe.")
            if not (row[1] and row[2]):
                raise HTTPException(status_code=400, detail=f"La talla '{row[3]}' está inactiva y no puede seleccionarse.")
            if id_empresa and row[4] is not None and row[4] != id_empresa:
                raise HTTPException(status_code=403, detail=f"La talla '{row[3]}' pertenece a otro Tenant.")
    finally:
        db.close_connection()

def _validar_colores_activos(colores_ids: List[int], id_empresa: Optional[int]):
    """Verifica que todos los colores seleccionados existan y estén activos en el Tenant (en 1 sola consulta)."""
    if not colores_ids:
        return
    colores_unicos = list(dict.fromkeys(int(c) for c in colores_ids if c is not None))
    if not colores_unicos:
        return
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        rows = db.execute_query(
            f"SELECT id_color, activo, estado, nombre, id_empresa FROM {schema}.t_color WHERE id_color = ANY(%s);",
            (colores_unicos,),
            fetchall=True
        ) or []
        mapa = {int(r[0]): r for r in rows}
        for c_id in colores_unicos:
            row = mapa.get(c_id)
            if not row:
                raise HTTPException(status_code=400, detail=f"El color con ID {c_id} no existe.")
            if not (row[1] and row[2]):
                raise HTTPException(status_code=400, detail=f"El color '{row[3]}' está inactivo y no puede seleccionarse.")
            if id_empresa and row[4] is not None and row[4] != id_empresa:
                raise HTTPException(status_code=403, detail=f"El color '{row[3]}' pertenece a otro Tenant.")
    finally:
        db.close_connection()

# ==============================================================================
# SERVICIOS PRINCIPALES
# ==============================================================================

from app.core.tenant_guard import (
    es_administrador_global,
    resolver_tenant_operacion,
    validar_acceso_recurso_tenant,
    validar_relaciones_tenant
)

def listar_productos_service(
    token_data: dict,
    id_empresa: Optional[int] = None,
    solo_activos: bool = False,
    id_categoria: Optional[int] = None,
    busqueda: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    activo: Optional[bool] = None,
    temporada: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Lista productos aplicando el filtro multi-tenant según el alcance del usuario.
    """
    empresa_filtro = resolver_tenant_operacion(token_data, id_empresa, permitir_global=True)

    return productos_repos.listar_productos(
        id_empresa=empresa_filtro,
        solo_activos=solo_activos,
        id_categoria=id_categoria,
        busqueda=busqueda,
        limit=limit if limit is not None else 200,
        offset=offset if offset is not None else 0,
        activo=activo,
        temporada=temporada
    )

def obtener_producto_service(id_producto: int, token_data: dict) -> Dict[str, Any]:
    """
    Obtiene el detalle completo de un producto con validación de Tenant.
    """
    producto = productos_repos.obtener_producto_por_id(id_producto)
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado."
        )

    validar_acceso_recurso_tenant(token_data, producto.get("id_empresa"), "producto")
    return producto

@atomic
def crear_producto_service(datos: dict, token_data: dict, ip_cliente: str = "") -> Dict[str, Any]:
    """
    Registra un producto, sus variantes (Talla x Color) y sus imágenes en Cloudinary.
    """
    id_usuario = token_data.get("id_usuario")

    # 1. Determinar Tenant con resolución estricta
    id_empresa_solicitado = datos.get("id_empresa")
    if id_empresa_solicitado in (0, '0', '', None):
        id_empresa_solicitado = None
    else:
        id_empresa_solicitado = int(id_empresa_solicitado)

    id_empresa = resolver_tenant_operacion(token_data, id_empresa_solicitado, permitir_global=False)

    # 2. Validar campos obligatorios
    nombre = datos.get("nombre")
    if not nombre or not nombre.strip():
        raise HTTPException(status_code=400, detail="El nombre del producto es obligatorio.")

    id_categoria = datos.get("id_categoria")
    if not id_categoria:
        raise HTTPException(status_code=400, detail="La categoría del producto es obligatoria.")

    try:
        precio = float(datos.get("precio", 0))
        if precio <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="El precio del producto debe ser un número mayor a 0.")

    # 3. Validar unicidad de nombre en el Tenant
    if productos_repos.verificar_nombre_duplicado(nombre, id_empresa):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un producto registrado con el nombre '{nombre.strip()}' en este Tenant."
        )

    # 4. Validar categoría, tallas y colores activos
    _validar_categoria_activa(id_categoria, id_empresa)

    tallas_ids = datos.get("tallas_ids") or []
    colores_ids = datos.get("colores_ids") or []
    _validar_tallas_activas(tallas_ids, id_empresa)
    _validar_colores_activos(colores_ids, id_empresa)

    # 5. Crear producto base
    id_producto = productos_repos.crear_producto(
        id_empresa=id_empresa,
        id_categoria=id_categoria,
        nombre=nombre,
        precio=precio,
        descripcion=datos.get("descripcion", ""),
        codigo_producto=datos.get("codigo_producto"),
        temporada=datos.get("temporada"),
        coleccion=datos.get("coleccion"),
        marca=datos.get("marca", "Aurora Atelier"),
        genero=datos.get("genero", "Femenino"),
        activo=bool(datos.get("activo", True)),
        tiene_ra=bool(datos.get("tiene_ra", False)),
        tipo_prenda_ra=datos.get("tipo_prenda_ra"),
        modelo_2d_url=datos.get("modelo_2d_url")
    )

    # 6. Generar variantes si se especificaron tallas y colores
    info_variantes = None
    if tallas_ids and colores_ids:
        info_variantes = productos_repos.sincronizar_variantes_producto(
            id_producto=id_producto,
            tallas_ids=tallas_ids,
            colores_ids=colores_ids,
            precio_base=precio,
            precios_por_talla=datos.get("precios_por_talla"),
            precios_variantes=datos.get("precios_variantes")
        )

    # 7. Asociar imágenes iniciales si se proporcionaron
    imagenes_data = datos.get("imagenes") or []
    for idx, img in enumerate(imagenes_data):
        url = img.get("imagen_url")
        pub_id = img.get("public_id")
        es_ppal = bool(img.get("es_principal", idx == 0))
        if url and pub_id:
            productos_repos.agregar_imagen_producto(
                id_producto=id_producto,
                imagen_url=url,
                public_id=pub_id,
                es_principal=es_ppal
            )

    # 8. Auditoría en Bitácora
    try:
        bitacora_services.registrar_accion(
            modulo="PRODUCTOS",
            accion="CREAR_PRODUCTO",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=token_data,
            entidad="Producto",
            id_entidad=str(id_producto),
            descripcion=f"Prenda creada: '{nombre}' (Tenant #{id_empresa}) con precio Bs. {precio}.",
            datos_nuevos={"nombre": nombre, "precio": precio, "id_categoria": id_categoria, "activo": datos.get("activo", True)}
        )
    except Exception as e:
        print(f"Error al registrar bitácora: {e}")

    return {
        "success": True,
        "message": f"Producto '{nombre}' registrado exitosamente.",
        "id_producto": id_producto,
        "variantes_generadas": info_variantes
    }

@atomic
def actualizar_producto_service(
    id_producto: int,
    datos: dict,
    token_data: dict,
    ip_cliente: str = ""
) -> Dict[str, Any]:
    """
    Actualiza la información general, variantes e imágenes de un producto existente.
    """
    # 1. Comprobar que el producto exista y pertenezca al Tenant
    producto_actual = productos_repos.obtener_producto_por_id(id_producto)
    if not producto_actual:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    validar_acceso_recurso_tenant(token_data, producto_actual["id_empresa"], "producto")

    id_empresa = producto_actual["id_empresa"]

    # 2. Validar campos
    nombre = datos.get("nombre")
    if not nombre or not nombre.strip():
        raise HTTPException(status_code=400, detail="El nombre del producto es obligatorio.")

    id_categoria = datos.get("id_categoria")
    if not id_categoria:
        raise HTTPException(status_code=400, detail="La categoría es obligatoria.")

    try:
        precio = float(datos.get("precio", 0))
        if precio <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="El precio debe ser mayor a 0.")

    # 3. Validar duplicado
    if productos_repos.verificar_nombre_duplicado(nombre, id_empresa, id_producto_actual=id_producto):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe otro producto registrado con el nombre '{nombre.strip()}' en este Tenant."
        )

    # 4. Validar categoría y relaciones
    _validar_categoria_activa(id_categoria, id_empresa)
    tallas_ids = datos.get("tallas_ids") or []
    colores_ids = datos.get("colores_ids") or []
    validar_relaciones_tenant(id_empresa=id_empresa, id_categoria=id_categoria, tallas_ids=tallas_ids, colores_ids=colores_ids)

    # 5. Actualizar información general
    activo = bool(datos.get("activo", True))
    productos_repos.actualizar_producto(
        id_producto=id_producto,
        id_categoria=id_categoria,
        nombre=nombre,
        precio=precio,
        descripcion=datos.get("descripcion", ""),
        codigo_producto=datos.get("codigo_producto"),
        temporada=datos.get("temporada"),
        coleccion=datos.get("coleccion"),
        marca=datos.get("marca", "Aurora Atelier"),
        genero=datos.get("genero", "Femenino"),
        activo=activo,
        tiene_ra=bool(datos.get("tiene_ra", False)),
        tipo_prenda_ra=datos.get("tipo_prenda_ra"),
        modelo_2d_url=datos.get("modelo_2d_url")
    )

    # 6. Sincronizar variantes si se enviaron listas
    info_variantes = None
    if "tallas_ids" in datos and "colores_ids" in datos:
        _validar_tallas_activas(tallas_ids, id_empresa)
        _validar_colores_activos(colores_ids, id_empresa)
        info_variantes = productos_repos.sincronizar_variantes_producto(
            id_producto=id_producto,
            tallas_ids=tallas_ids,
            colores_ids=colores_ids,
            precio_base=precio,
            precios_por_talla=datos.get("precios_por_talla"),
            precios_variantes=datos.get("precios_variantes")
        )
    elif "precios_por_talla" in datos or "precios_variantes" in datos:
        productos_repos.actualizar_precios_variantes_producto(
            id_producto=id_producto,
            precios_por_talla=datos.get("precios_por_talla"),
            precios_por_variante=datos.get("precios_variantes")
        )

    # 7. Auditoría
    try:
        bitacora_services.registrar_accion(
            modulo="PRODUCTOS",
            accion="ACTUALIZAR_PRODUCTO",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=token_data,
            entidad="Producto",
            id_entidad=str(id_producto),
            descripcion=f"Prenda actualizada: '{nombre}' (ID: {id_producto}). Nuevo precio: Bs. {precio}.",
            datos_nuevos={"nombre": nombre, "precio": precio, "id_categoria": id_categoria, "activo": activo}
        )
    except Exception as e:
        print(f"Error al registrar bitácora: {e}")

    return {
        "success": True,
        "message": f"Producto '{nombre}' actualizado exitosamente.",
        "id_producto": id_producto,
        "variantes_actualizadas": info_variantes
    }

def cambiar_estado_service(
    id_producto: int,
    activo: bool,
    token_data: dict,
    ip_cliente: str = ""
) -> Dict[str, Any]:
    """
    Alterna el estado Activo / Inactivo del producto.
    """
    prod = productos_repos.obtener_producto_por_id(id_producto)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    validar_acceso_recurso_tenant(token_data, prod.get("id_empresa"), "producto")

    ok = productos_repos.cambiar_estado_producto(id_producto, activo)
    estado_str = "Activo" if activo else "Inactivo"

    try:
        bitacora_services.registrar_accion(
            modulo="PRODUCTOS",
            accion="CAMBIAR_ESTADO_PRODUCTO",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=token_data,
            entidad="Producto",
            id_entidad=str(id_producto),
            descripcion=f"Cambio de estado de la prenda '{prod['nombre']}' a {estado_str}.",
            datos_nuevos={"activo": activo}
        )
    except Exception as e:
        print(f"Error al registrar bitácora: {e}")

    return {
        "success": ok,
        "message": f"El producto ahora se encuentra {estado_str}.",
        "activo": activo
    }

def agregar_imagen_service(
    id_producto: int,
    imagen_url: str,
    public_id: str,
    es_principal: bool,
    token_data: dict
) -> Dict[str, Any]:
    """
    Asocia una nueva imagen subida a Cloudinary a la galería del producto.
    """
    prod = productos_repos.obtener_producto_por_id(id_producto)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    validar_acceso_recurso_tenant(token_data, prod.get("id_empresa"), "producto")

    id_img = productos_repos.agregar_imagen_producto(id_producto, imagen_url, public_id, es_principal)
    return {
        "success": True,
        "message": "Imagen agregada exitosamente a la galería del producto.",
        "id_imagen": id_img,
        "imagen_url": imagen_url,
        "public_id": public_id,
        "es_principal": es_principal
    }

def marcar_portada_service(id_producto: int, id_imagen: int, token_data: dict) -> Dict[str, Any]:
    """
    Establece la imagen como la principal de la prenda.
    """
    prod = productos_repos.obtener_producto_por_id(id_producto)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    validar_acceso_recurso_tenant(token_data, prod.get("id_empresa"), "producto")

    ok = productos_repos.marcar_imagen_principal(id_imagen, id_producto)
    if not ok:
        raise HTTPException(status_code=400, detail="No se pudo marcar la imagen como principal.")

    return {"success": True, "message": "Portada del producto actualizada."}

def eliminar_imagen_service(id_producto: int, id_imagen: int, token_data: dict) -> Dict[str, Any]:
    """
    Elimina la foto del producto y la destruye en Cloudinary.
    """
    prod = productos_repos.obtener_producto_por_id(id_producto)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    validar_acceso_recurso_tenant(token_data, prod.get("id_empresa"), "producto")

    pub_id = productos_repos.eliminar_imagen_producto(id_imagen, id_producto)
    if pub_id:
        try:
            cloudinary_service.eliminar_imagen_cloudinary(pub_id)
        except Exception as e:
            print(f"Error al eliminar de Cloudinary: {e}")

    return {"success": True, "message": "Imagen eliminada de la galería correctamente."}

def eliminar_producto_service(
    id_producto: int,
    token_data: dict,
    ip_cliente: str = ""
) -> Dict[str, Any]:
    """
    Elimina el producto de forma segura o lo desactiva si tiene historial/inventario.
    """
    prod = productos_repos.obtener_producto_por_id(id_producto)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    validar_acceso_recurso_tenant(token_data, prod.get("id_empresa"), "producto")

    accion_resultado, public_ids = productos_repos.eliminar_producto_seguro(id_producto)

    # Si se eliminó físicamente, limpiar sus imágenes en Cloudinary
    if accion_resultado == "ELIMINADO" and public_ids:
        for p_id in public_ids:
            try:
                cloudinary_service.eliminar_imagen_cloudinary(p_id)
            except Exception as e:
                print(f"Error al borrar {p_id} de Cloudinary: {e}")

    # Auditoría
    try:
        bitacora_services.registrar_accion(
            modulo="PRODUCTOS",
            accion="ELIMINAR_PRODUCTO",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=token_data,
            entidad="Producto",
            id_entidad=str(id_producto),
            descripcion=f"Resultado: {accion_resultado}. Prenda '{prod['nombre']}' (ID: {id_producto}).",
            datos_nuevos={"accion_resultado": accion_resultado}
        )
    except Exception as e:
        print(f"Error al registrar bitácora: {e}")

    if accion_resultado == "DESACTIVADO":
        return {
            "success": True,
            "action": "DESACTIVADO",
            "message": f"El producto '{prod['nombre']}' cuenta con movimientos o existencias en inventario. Por reglas de integridad de catálogo no fue eliminado físicamente, sino desactivado."
        }

    return {
        "success": True,
        "action": "ELIMINADO",
        "message": f"Producto '{prod['nombre']}' eliminado permanentemente del catálogo."
    }


def asignar_promocion_producto_service(
    token_data: dict,
    id_promocion: int,
    id_producto: int,
    porcentaje_descuento: float
) -> int:
    try:
        id_empresa = resolver_tenant_operacion(token_data)

        validar_acceso_recurso_tenant(
            token_data=token_data,
            tabla="t_producto",
            campo_id="id_producto",
            id_recurso=id_producto,
            id_empresa=id_empresa
        )

        return productos_repos.asignar_promocion_producto(
            id_promocion=id_promocion,
            id_producto=id_producto,
            porcentaje_descuento=porcentaje_descuento
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


def actualizar_precios_variantes_service(
    id_producto: int,
    datos: dict,
    token_data: dict,
    ip_cliente: str = ""
) -> Dict[str, Any]:
    producto = productos_repos.obtener_producto_por_id(id_producto)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    validar_acceso_recurso_tenant(token_data, producto["id_empresa"], "producto")

    actualizadas = productos_repos.actualizar_precios_variantes_producto(
        id_producto=id_producto,
        precios_por_talla=datos.get("precios_por_talla"),
        precios_por_variante=datos.get("precios_variantes")
    )

    try:
        bitacora_services.registrar_accion(
            modulo="PRODUCTOS",
            accion="ACTUALIZAR_PRECIOS_VARIANTES",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=token_data,
            entidad="Producto",
            id_entidad=str(id_producto),
            descripcion=f"Precios de variantes actualizados para producto ID {id_producto} ({actualizadas} variantes afectadas).",
            ip_origen=ip_cliente
        )
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Precios actualizados para {actualizadas} variante(s).",
        "id_producto": id_producto,
        "variantes_actualizadas": actualizadas
    }


def actualizar_precios_variantes_service(
    id_producto: int,
    datos: dict,
    token_data: dict,
    ip_cliente: str = ""
) -> Dict[str, Any]:
    producto = productos_repos.obtener_producto_por_id(id_producto)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    validar_acceso_recurso_tenant(token_data, producto["id_empresa"], "producto")

    actualizadas = productos_repos.actualizar_precios_variantes_producto(
        id_producto=id_producto,
        precios_por_talla=datos.get("precios_por_talla"),
        precios_por_variante=datos.get("precios_variantes")
    )

    try:
        bitacora_services.registrar_accion(
            modulo="PRODUCTOS",
            accion="ACTUALIZAR_PRECIOS_VARIANTES",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=token_data,
            entidad="Producto",
            id_entidad=str(id_producto),
            descripcion=f"Precios de variantes actualizados para producto ID {id_producto} ({actualizadas} variantes afectadas).",
            ip_origen=ip_cliente
        )
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Precios actualizados para {actualizadas} variante(s).",
        "id_producto": id_producto,
        "variantes_actualizadas": actualizadas
    }


def obtener_promocion_producto_service(
    token_data: dict,
    id_producto: int
) -> Optional[Dict[str, Any]]:
    try:
        id_empresa = resolver_tenant_operacion(token_data)

        validar_acceso_recurso_tenant(
            token_data=token_data,
            tabla="t_producto",
            campo_id="id_producto",
            id_recurso=id_producto,
            id_empresa=id_empresa
        )

        return productos_repos.obtener_promocion_producto(
            id_producto=id_producto
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


def obtener_promocion_producto_service(
    token_data: dict,
    id_producto: int
) -> Optional[Dict[str, Any]]:
    try:
        id_empresa = resolver_tenant_operacion(token_data)

        validar_acceso_recurso_tenant(
            token_data=token_data,
            tabla="t_producto",
            campo_id="id_producto",
            id_recurso=id_producto,
            id_empresa=id_empresa
        )

        return productos_repos.obtener_promocion_producto(
            id_producto=id_producto
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


def listar_promociones_producto_service(
    token_data: dict,
    id_producto: int
) -> List[Dict[str, Any]]:
    try:
        id_empresa = resolver_tenant_operacion(token_data)

        validar_acceso_recurso_tenant(
            token_data=token_data,
            tabla="t_producto",
            campo_id="id_producto",
            id_recurso=id_producto,
            id_empresa=id_empresa
        )

        return productos_repos.listar_promociones_producto(
            id_producto=id_producto
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


def eliminar_promocion_producto_service(
    token_data: dict,
    id_producto: int,
    id_promocion_producto: int
) -> Dict[str, Any]:
    try:
        id_empresa = resolver_tenant_operacion(token_data)

        validar_acceso_recurso_tenant(
            token_data=token_data,
            tabla="t_producto",
            campo_id="id_producto",
            id_recurso=id_producto,
            id_empresa=id_empresa
        )

        eliminado = productos_repos.eliminar_promocion_producto(
            id_promocion_producto=id_promocion_producto,
            id_producto=id_producto
        )

        return {
            "success": eliminado,
            "id_promocion_producto": id_promocion_producto
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


def listar_promociones_service(
    token_data: dict,
    solo_activas: bool = True
) -> List[Dict[str, Any]]:
    try:
        return productos_repos.listar_promociones(
            solo_activas=solo_activas
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


def actualizar_precios_variantes_service(
    id_producto: int,
    datos: dict,
    token_data: dict,
    ip_cliente: str = ""
) -> Dict[str, Any]:
    producto = productos_repos.obtener_producto_por_id(id_producto)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    validar_acceso_recurso_tenant(token_data, producto["id_empresa"], "producto")

    actualizadas = productos_repos.actualizar_precios_variantes_producto(
        id_producto=id_producto,
        precios_por_talla=datos.get("precios_por_talla"),
        precios_por_variante=datos.get("precios_variantes")
    )

    try:
        bitacora_services.registrar_accion(
            modulo="PRODUCTOS",
            accion="ACTUALIZAR_PRECIOS_VARIANTES",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=token_data,
            entidad="Producto",
            id_entidad=str(id_producto),
            descripcion=f"Precios de variantes actualizados para producto ID {id_producto} ({actualizadas} variantes afectadas).",
            ip_origen=ip_cliente
        )
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Precios actualizados para {actualizadas} variante(s).",
        "id_producto": id_producto,
        "variantes_actualizadas": actualizadas
    }