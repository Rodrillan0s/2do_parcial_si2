from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, UploadFile, File, Form
from typing import Optional, List, Dict, Any
from app.core.security import require_permission
from app.modules.catalogo.services import productos_services
from app.shared import cloudinary_service

router = APIRouter(prefix='/api/productos', tags=["Gestión de Productos"])

@router.get('', summary="Listar productos del Tenant actual")
def listar_productos(
    id_empresa: Optional[int] = Query(None, description="Filtrar por Tenant (solo SuperAdmin)"),
    solo_activos: bool = Query(False, description="Filtrar solo prendas activas"),
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo explícito (true/false)"),
    id_categoria: Optional[int] = Query(None, description="Filtrar por categoría"),
    temporada: Optional[str] = Query(None, description="Filtrar por temporada"),
    busqueda: Optional[str] = Query(None, description="Buscar por nombre, código o descripción"),
    limit: Optional[int] = Query(None, description="Cantidad máxima de registros (paginación)"),
    offset: Optional[int] = Query(None, description="Desplazamiento para paginación"),
    token_data: dict = Depends(require_permission('productos.ver'))
):
    productos = productos_services.listar_productos_service(
        token_data=token_data,
        id_empresa=id_empresa,
        solo_activos=solo_activos,
        id_categoria=id_categoria,
        busqueda=busqueda,
        limit=limit,
        offset=offset,
        activo=activo,
        temporada=temporada
    )
    total_real = len(productos)
    if productos:
        first_total = productos[0].get("_total_registros")
        if isinstance(first_total, int) and first_total >= len(productos):
            total_real = first_total
        for item in productos:
            item.pop("_total_registros", None)
    return {
        "success": True,
        "total": total_real,
        "data": productos,
        "limit": limit,
        "offset": offset
    }
@router.get(
    "/promociones",
    summary="Listar promociones"
)
def listar_promociones(
    solo_activas: bool = True,
    token_data: dict = Depends(require_permission('productos.ver'))
):
    promociones = productos_services.listar_promociones_service(
        token_data=token_data,
        solo_activas=solo_activas
    )

    return {
        "success": True,
        "total": len(promociones),
        "data": promociones
    }
@router.get('/{id_producto}', summary="Consultar detalle de producto, galería y variantes")
def obtener_producto(
    id_producto: int,
    token_data: dict = Depends(require_permission('productos.ver'))
):
    producto = productos_services.obtener_producto_service(
        id_producto=id_producto,
        token_data=token_data
    )
    return {
        "success": True,
        "data": producto
    }

@router.post('', status_code=status.HTTP_201_CREATED, summary="Registrar nuevo producto con variantes y fotos")
def crear_producto(
    datos: dict,
    request: Request,
    token_data: dict = Depends(require_permission('productos.crear'))
):
    ip_cliente = request.client.host if request.client else "127.0.0.1"
    resultado = productos_services.crear_producto_service(
        datos=datos,
        token_data=token_data,
        ip_cliente=ip_cliente
    )
    return resultado

@router.put('/{id_producto}', summary="Actualizar información, variantes y fotos de un producto")
def actualizar_producto(
    id_producto: int,
    datos: dict,
    request: Request,
    token_data: dict = Depends(require_permission('productos.editar'))
):
    ip_cliente = request.client.host if request.client else "127.0.0.1"
    resultado = productos_services.actualizar_producto_service(
        id_producto=id_producto,
        datos=datos,
        token_data=token_data,
        ip_cliente=ip_cliente
    )
    return resultado

@router.put('/{id_producto}/precios-variantes', summary="Actualizar precios de variantes por talla o variante")
def actualizar_precios_variantes(
    id_producto: int,
    datos: dict,
    request: Request,
    token_data: dict = Depends(require_permission('productos.editar'))
):
    ip_cliente = request.client.host if request.client else "127.0.0.1"
    return productos_services.actualizar_precios_variantes_service(
        id_producto=id_producto,
        datos=datos,
        token_data=token_data,
        ip_cliente=ip_cliente
    )

@router.put('/{id_producto}/estado', summary="Activar o desactivar producto")
def cambiar_estado(
    id_producto: int,
    datos: dict,
    request: Request,
    token_data: dict = Depends(require_permission('productos.eliminar'))
):
    activo = bool(datos.get("activo", True))
    ip_cliente = request.client.host if request.client else "127.0.0.1"
    resultado = productos_services.cambiar_estado_service(
        id_producto=id_producto,
        activo=activo,
        token_data=token_data,
        ip_cliente=ip_cliente
    )
    return resultado

@router.post('/upload-image', summary="Subir imagen de prenda a Cloudinary")
async def subir_imagen_producto(
    file: UploadFile = File(...),
    token_data: dict = Depends(require_permission('productos.crear'))
):
    """
    Sube un archivo de imagen (JPG, PNG, WEBP, máx 5MB) a Cloudinary en la carpeta aurora_store/productos.
    """
    # Validar extensión
    extensiones_permitidas = {'image/jpeg', 'image/png', 'image/webp', 'image/jpg'}
    if file.content_type not in extensiones_permitidas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no permitido. Solo se admiten archivos JPG, PNG y WEBP."
        )

    # Validar tamaño (máximo 10 MB)
    contenido = await file.read()
    if len(contenido) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen excede el límite permitido de 10 MB."
        )

    try:
        resultado = cloudinary_service.subir_imagen_cloudinary(
            archivo=contenido,
            folder="aurora_store/productos"
        )
        return {
            "success": True,
            "message": "Imagen subida a Cloudinary exitosamente.",
            "data": {
                "imagen_url": resultado.get("secure_url") or resultado.get("url"),
                "public_id": resultado.get("public_id"),
                "bytes": resultado.get("bytes"),
                "format": resultado.get("format")
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir imagen a Cloudinary: {str(e)}"
        )

@router.post('/{id_producto}/imagenes', summary="Vincular imagen a la galería del producto")
def agregar_imagen_a_producto(
    id_producto: int,
    datos: dict,
    token_data: dict = Depends(require_permission('productos.editar'))
):
    imagen_url = datos.get("imagen_url")
    public_id = datos.get("public_id")
    es_principal = bool(datos.get("es_principal", False))

    if not imagen_url or not public_id:
        raise HTTPException(status_code=400, detail="imagen_url y public_id son obligatorios.")

    return productos_services.agregar_imagen_service(
        id_producto=id_producto,
        imagen_url=imagen_url,
        public_id=public_id,
        es_principal=es_principal,
        token_data=token_data
    )

@router.put('/{id_producto}/imagenes/{id_imagen}/principal', summary="Establecer imagen como portada")
def marcar_portada(
    id_producto: int,
    id_imagen: int,
    token_data: dict = Depends(require_permission('productos.editar'))
):
    return productos_services.marcar_portada_service(
        id_producto=id_producto,
        id_imagen=id_imagen,
        token_data=token_data
    )

@router.delete('/{id_producto}/imagenes/{id_imagen}', summary="Eliminar imagen de la prenda y de Cloudinary")
def eliminar_imagen(
    id_producto: int,
    id_imagen: int,
    token_data: dict = Depends(require_permission('productos.editar'))
):
    return productos_services.eliminar_imagen_service(
        id_producto=id_producto,
        id_imagen=id_imagen,
        token_data=token_data
    )

@router.delete('/{id_producto}', summary="Eliminar producto o desactivar si tiene inventario")
def eliminar_producto(
    id_producto: int,
    request: Request,
    token_data: dict = Depends(require_permission('productos.editar'))
):
    ip_cliente = request.client.host if request.client else "127.0.0.1"
    return productos_services.eliminar_producto_service(
        id_producto=id_producto,
        token_data=token_data,
        ip_cliente=ip_cliente
    )

@router.post(
    "/{id_producto}/promocion",
    summary="Asignar promoción a un producto"
)
def asignar_promocion_producto(
    id_producto: int,
    id_promocion: int,
    porcentaje_descuento: float,
    token_data: dict = Depends(require_permission('productos.editar'))
):
    id_promocion_producto = productos_services.asignar_promocion_producto_service(
        token_data=token_data,
        id_promocion=id_promocion,
        id_producto=id_producto,
        porcentaje_descuento=porcentaje_descuento
    )

    return {
        "success": True,
        "message": "Promoción asignada correctamente.",
        "id_promocion_producto": id_promocion_producto
    }

@router.get(
    "/{id_producto}/promociones",
    summary="Listar promociones de un producto"
)
def listar_promociones_producto(
    id_producto: int,
    token_data: dict = Depends(require_permission('productos.ver'))
):
    promociones = productos_services.listar_promociones_producto_service(
        token_data=token_data,
        id_producto=id_producto
    )

    return {
        "success": True,
        "total": len(promociones),
        "data": promociones
    }

@router.get(
    "/{id_producto}/promocion-vigente",
    summary="Obtener promoción vigente de un producto"
)
def obtener_promocion_producto(
    id_producto: int,
    token_data: dict = Depends(require_permission('productos.ver'))
):
    promocion = productos_services.obtener_promocion_producto_service(
        token_data=token_data,
        id_producto=id_producto
    )

    return {
        "success": True,
        "data": promocion
    }

@router.delete(
    "/{id_producto}/promociones/{id_promocion_producto}",
    summary="Quitar promoción de un producto"
)
def eliminar_promocion_producto(
    id_producto: int,
    id_promocion_producto: int,
    token_data: dict = Depends(require_permission('productos.editar'))
):
    resultado = productos_services.eliminar_promocion_producto_service(
        token_data=token_data,
        id_producto=id_producto,
        id_promocion_producto=id_promocion_producto
    )

    return {
        "success": True,
        "message": "Promoción quitada del producto correctamente.",
        "data": resultado
    }

