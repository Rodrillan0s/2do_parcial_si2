from fastapi import APIRouter, HTTPException, Depends, Query, Body, Request
from typing import Optional, Dict, Any
from app.core.security import require_permission
from app.core.tenant_guard import resolver_sucursal_autorizada
from app.modules.inventario.repos import inventario_repos
from app.modules.admin.repos.bitacora_repos import registrar_evento_db

router = APIRouter(prefix="/api/inventario", tags=["Inventario"])

@router.get("")
@router.get("/")
def listar_inventario(
    id_sucursal: Optional[int] = Query(None, description="Filtrar por ID de sucursal"),
    id_producto: Optional[int] = Query(None, description="Filtrar por ID de producto"),
    id_variante: Optional[int] = Query(None, description="Filtrar por ID de variante"),
    id_talla: Optional[int] = Query(None, description="Filtrar por ID de talla"),
    id_color: Optional[int] = Query(None, description="Filtrar por ID de color"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por Tenant (solo SuperAdmin o global)"),
    estado: Optional[str] = Query(None, description="Filtrar por estado activo/inactivo"),
    filtro_stock: Optional[str] = Query(None, description="Filtro rápido: bajo_stock, sin_stock, disponible"),
    busqueda: Optional[str] = Query(None, description="Búsqueda por producto, SKU, código de barras"),
    pagina: int = Query(1, ge=1, description="Número de página"),
    limite: int = Query(20, ge=1, le=100, description="Elementos por página"),
    payload: dict = Depends(require_permission("inventario.ver"))
):
    """
    Consulta el inventario agrupado por sucursal y variante de producto.
    Aplica aislamiento multi-tenant: los usuarios de empresa solo pueden ver el stock de su empresa.
    """
    try:
        # Multi-tenant: usuarios de tienda usan estrictamente el id_empresa del JWT. SuperAdmin puede filtrar o ver global.
        alcance = payload.get("alcance")
        id_empresa_efectivo = payload.get("id_empresa") if alcance != "PLATAFORMA" else id_empresa

        id_sucursal = resolver_sucursal_autorizada(payload, id_sucursal if isinstance(id_sucursal, int) else None)

        filtros = {
            "id_sucursal": id_sucursal,
            "id_producto": id_producto if isinstance(id_producto, int) else None,
            "id_variante": id_variante if isinstance(id_variante, int) else None,
            "id_talla": id_talla if isinstance(id_talla, int) else None,
            "id_color": id_color if isinstance(id_color, int) else None,
            "estado": estado if isinstance(estado, str) else None,
            "filtro_stock": filtro_stock if isinstance(filtro_stock, str) else None,
            "busqueda": busqueda if isinstance(busqueda, str) else None,
            "pagina": pagina if isinstance(pagina, int) else 1,
            "limite": limite if isinstance(limite, int) else 20
        }

        resultado = inventario_repos.listar_inventario(id_empresa_efectivo, filtros)
        return resultado
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar inventario: {str(e)}")

@router.get("/movimientos")
def listar_movimientos(
    id_inventario: Optional[int] = Query(None, description="Filtrar por ID de inventario"),
    id_sucursal: Optional[int] = Query(None, description="Filtrar por ID de sucursal"),
    id_variante: Optional[int] = Query(None, description="Filtrar por ID de variante"),
    id_empresa: Optional[int] = Query(None, description="Filtrar por Tenant (solo SuperAdmin o global)"),
    tipo_movimiento: Optional[str] = Query(None, description="ENTRADA, SALIDA, AJUSTE, RESERVA"),
    busqueda: Optional[str] = Query(None, description="Búsqueda libre"),
    pagina: int = Query(1, ge=1, description="Número de página"),
    limite: int = Query(20, ge=1, le=100, description="Elementos por página"),
    payload: dict = Depends(require_permission("inventario.ver"))
):
    """
    Consulta el historial detallado de movimientos de inventario en t_movimiento_inventario.
    """
    try:
        alcance = payload.get("alcance")
        id_empresa_efectivo = payload.get("id_empresa") if alcance != "PLATAFORMA" else id_empresa

        id_sucursal = resolver_sucursal_autorizada(payload, id_sucursal if isinstance(id_sucursal, int) else None)

        filtros = {
            "id_inventario": id_inventario if isinstance(id_inventario, int) else None,
            "id_sucursal": id_sucursal,
            "id_variante": id_variante if isinstance(id_variante, int) else None,
            "tipo_movimiento": tipo_movimiento if isinstance(tipo_movimiento, str) else None,
            "busqueda": busqueda if isinstance(busqueda, str) else None,
            "pagina": pagina if isinstance(pagina, int) else 1,
            "limite": limite if isinstance(limite, int) else 20
        }

        resultado = inventario_repos.listar_movimientos_inventario(id_empresa_efectivo, filtros)
        return resultado
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar historial de movimientos: {str(e)}")

@router.get("/{id_inventario}")
def obtener_inventario(
    id_inventario: int,
    payload: dict = Depends(require_permission("inventario.ver"))
):
    """
    Consulta el detalle de una posición de inventario específica.
    """
    try:
        alcance = payload.get("alcance")
        id_empresa = payload.get("id_empresa") if alcance != "PLATAFORMA" else None

        item = inventario_repos.obtener_inventario_por_id(id_inventario, id_empresa)
        if not item:
            raise HTTPException(status_code=404, detail="Posición de inventario no encontrada o no pertenece a su empresa.")
        return {"success": True, "item": item}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener detalle de inventario: {str(e)}")

@router.post("/movimiento")
def registrar_movimiento(
    request: Request,
    datos: Dict[str, Any] = Body(...),
    payload: dict = Depends(require_permission("inventario.gestionar"))
):
    """
    Registra una entrada, salida o ajuste en el inventario mediante la función
    transaccional atómica fn_movimiento_inventario con bloqueo FOR UPDATE.
    Regla de negocio: stock_disponible = stock_actual - stock_reservado.
    Una salida nunca puede consumir unidades reservadas.
    """
    # 1. Validar campos obligatorios en el body
    id_sucursal = datos.get("id_sucursal")
    id_variante = datos.get("id_variante")
    tipo_movimiento = datos.get("tipo_movimiento")
    cantidad = datos.get("cantidad")
    motivo = datos.get("motivo") or "Movimiento de inventario"

    if not id_sucursal or not id_variante or not tipo_movimiento or cantidad is None:
        raise HTTPException(
            status_code=400,
            detail="Los campos id_sucursal, id_variante, tipo_movimiento y cantidad son obligatorios."
        )

    tipo_upper = str(tipo_movimiento).strip().upper()
    if tipo_upper not in ("ENTRADA", "SALIDA", "AJUSTE"):
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de movimiento '{tipo_movimiento}' no válido. Debe ser ENTRADA, SALIDA o AJUSTE."
        )

    try:
        cantidad = int(cantidad)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="El campo cantidad debe ser un número entero.")

    if tipo_upper in ("ENTRADA", "SALIDA") and cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad para entrada o salida debe ser mayor a 0.")

    if tipo_upper == "AJUSTE" and cantidad < 0:
        raise HTTPException(status_code=400, detail="El stock ajustado no puede ser negativo.")

    # 2. Multi-tenant: id_empresa viene exclusivamente del JWT autenticado
    alcance = payload.get("alcance")
    id_empresa = payload.get("id_empresa") if alcance != "PLATAFORMA" else None
    id_usuario = payload.get("nro_usuario") or payload.get("id_usuario")
    if not id_usuario:
        raise HTTPException(status_code=401, detail="La sesión no contiene un usuario válido.")

    resolver_sucursal_autorizada(payload, int(id_sucursal))

    # 3. Invocar registro atómico
    resultado = inventario_repos.registrar_movimiento_inventario(
        id_sucursal=int(id_sucursal),
        id_variante=int(id_variante),
        tipo_movimiento=tipo_upper,
        cantidad=cantidad,
        id_usuario=id_usuario,
        motivo=motivo,
        id_empresa=id_empresa
    )

    if not resultado.get("success"):
        err_code = resultado.get("error")
        msg = resultado.get("message") or resultado.get("mensaje") or "Error al procesar movimiento."

        if err_code in ("SUCURSAL_AJENA_TENANT", "VARIANTE_AJENA_TENANT", "TENANT_MISMATCH", "ACCESO_DENEGADO"):
            raise HTTPException(status_code=403, detail=msg)
        elif err_code == "INVENTARIO_NO_ENCONTRADO":
            raise HTTPException(status_code=404, detail=msg)
        elif err_code in ("STOCK_INSUFICIENTE", "STOCK_NEGATIVO_NO_PERMITIDO", "STOCK_MENOR_A_RESERVADO", "CANTIDAD_INVALIDA"):
            raise HTTPException(status_code=400, detail=msg)
        else:
            raise HTTPException(status_code=400, detail=msg)

    # 4. Registrar evento en bitácora de auditoría
    try:
        registrar_evento_db(
            id_usuario=id_usuario,
            modulo="INVENTARIO",
            accion=f"MOVIMIENTO_{tipo_upper}",
            entidad="t_inventario",
            id_entidad=str(resultado.get("id_inventario")),
            descripcion=f"{tipo_upper} de {resultado.get('cantidad')} unidades. Stock: {resultado.get('stock_anterior')} -> {resultado.get('stock_nuevo')}. Motivo: {motivo}",
            resultado="EXITO",
            nivel="INFO",
            id_empresa=id_empresa,
            id_sucursal=int(id_sucursal),
            datos_anteriores={"stock_actual": resultado.get("stock_anterior")},
            datos_nuevos={"stock_actual": resultado.get("stock_nuevo"), "stock_disponible": resultado.get("stock_disponible")},
            metadatos={"id_movimiento": resultado.get("id_movimiento"), "tipo_movimiento": tipo_upper}
        )
    except Exception as audit_err:
        print(f"[AUDITORIA] Advertencia al registrar bitácora de inventario: {audit_err}")

    return resultado
