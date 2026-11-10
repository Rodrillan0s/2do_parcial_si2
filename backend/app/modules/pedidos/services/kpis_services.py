from app.modules.pedidos.repos import kpis_repos
from app.modules.auth.services.rbac_services import obtener_nivel_actor

def procesar_etl_diario(token_data: dict):
    nivel = obtener_nivel_actor(token_data)
    if nivel != 1:
        raise ValueError("Operación crítica restringida. Solo el SuperAdministrador puede disparar el recálculo analítico.")
    
    filas = kpis_repos.ejecutar_extraccion_y_carga_etl_db()
    return {
        "success": True, 
        "message": f"Consolidación analítica de Aurora Store completada. Tablas actualizadas: {filas}"
    }

def generar_dashboard(token_data: dict, id_empresa: int = None):
    from app.core.tenant_guard import resolver_tenant_operacion, resolver_sucursal_autorizada, obtener_alcance_usuario
    alcance = obtener_alcance_usuario(token_data)
    if alcance == 'CLIENTE':
        raise ValueError('Panel reservado al personal autorizado.')
    empresa = resolver_tenant_operacion(token_data, id_empresa, permitir_global=True)
    if alcance == 'SUCURSAL':
        sucursal = resolver_sucursal_autorizada(token_data)
        metricas = kpis_repos.obtener_metricas_sucursal_db(sucursal, empresa)
    elif empresa is not None:
        metricas = kpis_repos.obtener_metricas_empresa_db(empresa)
    else:
        metricas = kpis_repos.obtener_metricas_globales_db()
    mensaje = 'Indicadores del contexto autorizado calculados exitosamente.'

    return {
        "success": True,
        "message": mensaje,
        "data": metricas
    }


# ==============================================================================
# W32 — SERVICIOS DE INDICADORES EMPRESARIALES MULTI-TENANT
# ==============================================================================

from datetime import datetime, timedelta

def _resolver_contexto_tenant(token_data: dict, id_sucursal_param: int = None, id_empresa_param: int = None):
    """
    Determina de forma inviolable el id_empresa e id_sucursal permitidos según el JWT.
    Si el usuario tiene permisos administrativos (nivel <= 3), se permite filtrar por id_empresa_param.
    """
    from app.core.tenant_guard import resolver_tenant_operacion, resolver_sucursal_autorizada, obtener_alcance_usuario
    from app.modules.inventario.repos.sucursales_repos import obtener_sucursal_por_id
    if obtener_alcance_usuario(token_data) == 'CLIENTE':
        raise ValueError('Indicadores reservados al personal autorizado.')
    empresa = resolver_tenant_operacion(token_data, id_empresa_param, permitir_global=True)
    sucursal = resolver_sucursal_autorizada(token_data, id_sucursal_param)
    if sucursal is not None:
        branch = obtener_sucursal_por_id(sucursal)
        if not branch or (empresa is not None and branch['id_empresa'] != empresa):
            from fastapi import HTTPException
            raise HTTPException(403, detail='Sucursal ajena al contexto autorizado.')
    return empresa, sucursal


def _normalizar_fechas(fecha_inicio: str = None, fecha_fin: str = None):
    """
    Normaliza los rangos de fecha asegurando que cubran desde 00:00:00 hasta 23:59:59.
    """
    f_ini_str = None
    f_fin_str = None
    d_ini = None
    d_fin = None
    
    if fecha_inicio:
        try:
            d_ini = datetime.strptime(fecha_inicio.strip()[:10], '%Y-%m-%d')
            f_ini_str = d_ini.strftime('%Y-%m-%d 00:00:00')
        except Exception:
            f_ini_str = None
            
    if fecha_fin:
        try:
            d_fin = datetime.strptime(fecha_fin.strip()[:10], '%Y-%m-%d')
            f_fin_str = d_fin.strftime('%Y-%m-%d 23:59:59')
        except Exception:
            f_fin_str = None
            
    return f_ini_str, f_fin_str, d_ini, d_fin


def obtener_resumen_indicadores(token_data: dict, fecha_inicio: str = None, fecha_fin: str = None, id_sucursal: int = None, id_empresa: int = None):
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, d_ini, d_fin = _normalizar_fechas(fecha_inicio, fecha_fin)
    
    # 1. Período actual
    resumen_actual = kpis_repos.obtener_resumen_kpis_db(id_empresa_final, id_sucursal_final, f_ini, f_fin)
    
    # 2. Período anterior (para calcular variación porcentual si se indicaron fechas)
    comparacion = {
        "ventas_crecimiento_pct": 0.0,
        "transacciones_crecimiento_pct": 0.0,
        "ingresos_crecimiento_pct": 0.0,
        "periodo_anterior_disponible": False
    }
    
    if d_ini and d_fin:
        delta_dias = max((d_fin - d_ini).days + 1, 1)
        prev_fin = d_ini - timedelta(seconds=1)
        prev_ini = d_ini - timedelta(days=delta_dias)
        
        prev_res = kpis_repos.obtener_resumen_kpis_db(
            id_empresa_final, id_sucursal_final,
            prev_ini.strftime('%Y-%m-%d 00:00:00'),
            prev_fin.strftime('%Y-%m-%d 23:59:59')
        )
        
        prev_ventas = prev_res['ventas']['ventas_totales']
        curr_ventas = resumen_actual['ventas']['ventas_totales']
        prev_tx = prev_res['ventas']['cantidad_ventas']
        curr_tx = resumen_actual['ventas']['cantidad_ventas']
        
        if prev_ventas > 0:
            crec_v = ((curr_ventas - prev_ventas) / prev_ventas) * 100
            comparacion["ventas_crecimiento_pct"] = round(crec_v, 1)
            comparacion["ingresos_crecimiento_pct"] = round(crec_v, 1)
            comparacion["periodo_anterior_disponible"] = True
        elif curr_ventas > 0:
            comparacion["ventas_crecimiento_pct"] = 100.0
            comparacion["ingresos_crecimiento_pct"] = 100.0
            comparacion["periodo_anterior_disponible"] = True
            
        if prev_tx > 0:
            crec_tx = ((curr_tx - prev_tx) / prev_tx) * 100
            comparacion["transacciones_crecimiento_pct"] = round(crec_tx, 1)
        elif curr_tx > 0:
            comparacion["transacciones_crecimiento_pct"] = 100.0

    resumen_actual["comparacion"] = comparacion
    return {
        "success": True,
        "message": "Resumen ejecutivo de KPIs calculado exitosamente.",
        "data": resumen_actual
    }


def obtener_ventas_periodo(token_data: dict, fecha_inicio: str = None, fecha_fin: str = None, id_sucursal: int = None, id_empresa: int = None):
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    
    datos = kpis_repos.obtener_ventas_timeline_db(id_empresa_final, id_sucursal_final, f_ini, f_fin)
    return {
        "success": True,
        "message": "Serie temporal de ventas calculada.",
        "data": datos
    }


def obtener_productos_mas_vendidos(token_data: dict, fecha_inicio: str = None, fecha_fin: str = None, id_sucursal: int = None, limit: int = 8, id_empresa: int = None):
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    
    datos = kpis_repos.obtener_productos_mas_vendidos_db(id_empresa_final, id_sucursal_final, f_ini, f_fin, limit)
    return {
        "success": True,
        "message": "Top productos más vendidos obtenido.",
        "data": datos
    }


def obtener_inventario_kpis(token_data: dict, id_sucursal: int = None, id_empresa: int = None):
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    alertas = kpis_repos.obtener_inventario_alertas_db(id_empresa_final, id_sucursal_final)
    
    return {
        "success": True,
        "message": "Alertas de inventario obtenidas.",
        "data": {
            "alertas_stock": alertas,
            "total_alertas": len(alertas)
        }
    }


def obtener_ventas_sucursal(token_data: dict, fecha_inicio: str = None, fecha_fin: str = None, id_empresa: int = None):
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, None, id_empresa)
    f_ini, f_fin, _, _ = _normalizar_fechas(fecha_inicio, fecha_fin)
    
    datos = kpis_repos.obtener_ventas_por_sucursal_db(id_empresa_final, f_ini, f_fin, id_sucursal=id_sucursal_final)
    return {
        "success": True,
        "message": "Comparativa de ventas por sucursal calculada.",
        "data": datos
    }


def obtener_tenants_dashboard(token_data: dict):
    nivel = obtener_nivel_actor(token_data)
    if nivel >= 6:
        raise ValueError("Acceso denegado: El panel de tiendas es exclusivo para personal administrativo.")
    
    tenants = kpis_repos.obtener_tenants_dashboard_db()
    token_empresa = token_data.get('id_empresa')
    
    # Si el usuario es de nivel tienda (nivel 3) y tiene id_empresa asignada, filtrar solo su tienda
    if nivel >= 3 and token_empresa:
        tenants = [t for t in tenants if t['id_empresa'] == token_empresa]
        
    return {
        "success": True,
        "message": "Listado de tiendas y tenants obtenido exitosamente.",
        "data": tenants
    }


def obtener_ranking_satisfaccion_prendas(token_data: dict, id_sucursal: int = None, limit: int = 5, id_empresa: int = None):
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    datos = kpis_repos.obtener_ranking_satisfaccion_prendas_db(id_empresa_final, id_sucursal_final, limit)
    return {
        "success": True,
        "message": "Ranking de satisfacción de prendas obtenido.",
        "data": datos
    }


def obtener_alertas_calidad_criticas(token_data: dict, id_sucursal: int = None, limit: int = 10, id_empresa: int = None):
    id_empresa_final, id_sucursal_final = _resolver_contexto_tenant(token_data, id_sucursal, id_empresa)
    datos = kpis_repos.obtener_alertas_calidad_criticas_db(id_empresa_final, id_sucursal_final, limit)
    return {
        "success": True,
        "message": "Alertas críticas de calidad y servicio obtenidas.",
        "data": datos
    }
