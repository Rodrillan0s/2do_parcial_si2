import math
from datetime import datetime, timedelta, date, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

from app.core.postgres import PostgreSQL
from app.core.config import Config

def _get_schema() -> str:
    return Config.SCHEMA or 'comercio'


def obtener_serie_temporal_ventas(
    id_empresa: int,
    id_sucursal: Optional[int] = None,
    id_producto: Optional[int] = None,
    dias_historia: int = 60
) -> List[Dict[str, Any]]:
    """
    Extrae la serie temporal diaria de unidades vendidas y montos para el tenant.
    Excluye estrictamente ventas ANULADAS, CANCELADAS o PENDIENTES_PAGO.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        fecha_corte = (datetime.now() - timedelta(days=dias_historia)).strftime('%Y-%m-%d')
        
        where_clauses = [
            "v.id_empresa = %s",
            "UPPER(COALESCE(v.estado, '')) NOT IN ('ANULADA', 'CANCELADA', 'PENDIENTE_PAGO')",
            "v.fecha_venta >= %s"
        ]
        params = [id_empresa, fecha_corte]
        
        if id_sucursal:
            where_clauses.append("v.id_sucursal = %s")
            params.append(id_sucursal)
            
        join_producto = ""
        if id_producto:
            where_clauses.append("ptc.id_producto = %s")
            params.append(id_producto)
            join_producto = f"JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = dv.id_variante"

        where_sql = " AND ".join(where_clauses)
        
        q = f"""
            SELECT 
                DATE(v.fecha_venta) AS fecha,
                SUM(dv.cantidad) AS unidades_vendidas,
                SUM(dv.subtotal) AS total_ingresos,
                COUNT(DISTINCT v.id_venta) AS num_transacciones
            FROM {schema}.t_venta v
            JOIN {schema}.t_detalle_venta dv ON dv.id_venta = v.id_venta
            {join_producto}
            WHERE {where_sql}
            GROUP BY DATE(v.fecha_venta)
            ORDER BY DATE(v.fecha_venta) ASC;
        """
        rows = db.execute_query(q, tuple(params), fetchall=True) or []
        
        # Mapear a serie continua rellenando días con 0 ventas si corresponde
        serie_dict = {
            r[0].strftime('%Y-%m-%d') if isinstance(r[0], (date, datetime)) else str(r[0]): {
                "unidades": int(r[1] or 0),
                "ingresos": float(r[2] or 0.0),
                "transacciones": int(r[3] or 0)
            }
            for r in rows
        }
        
        serie_continua: List[Dict[str, Any]] = []
        hoy = date.today()
        fecha_inicio_dt = hoy - timedelta(days=dias_historia)
        
        cur_dt = fecha_inicio_dt
        while cur_dt <= hoy:
            f_str = cur_dt.strftime('%Y-%m-%d')
            entry = serie_dict.get(f_str, {"unidades": 0, "ingresos": 0.0, "transacciones": 0})
            serie_continua.append({
                "fecha": f_str,
                "unidades": entry["unidades"],
                "ingresos": entry["ingresos"],
                "transacciones": entry["transacciones"]
            })
            cur_dt += timedelta(days=1)
            
        return serie_continua
    finally:
        db.close_connection()


def predecir_demanda_serie(
    serie: List[Dict[str, Any]],
    dias_proyeccion: int = 14,
    alfa: float = 0.35,
    beta: float = 0.15
) -> Dict[str, Any]:
    """
    Aplica suavizamiento exponencial doble (Holt Linear Trend) para proyectar
    la demanda futura e intervalos de predicción al 95% de confianza.
    """
    valores = [it["unidades"] for it in serie]
    n = len(valores)
    
    if n < 3:
        # Fallback para series muy cortas
        prom = sum(valores) / max(1, n)
        fechas_futuras = []
        hoy = date.today()
        proyecciones = []
        for i in range(1, dias_proyeccion + 1):
            f_fut = (hoy + timedelta(days=i)).strftime('%Y-%m-%d')
            proyecciones.append({
                "fecha": f_fut,
                "prediccion": round(prom, 2),
                "limite_inferior": max(0.0, round(prom * 0.7, 2)),
                "limite_superior": round(prom * 1.3 + 1, 2)
            })
        return {
            "historico": serie,
            "proyecciones": proyecciones,
            "tendencia": "ESTABLE",
            "tasa_crecimiento_diario": 0.0,
            "sigma": 1.0
        }
        
    # Inicialización de nivel (level) y tendencia (trend)
    level = float(valores[0])
    trend = float(valores[1] - valores[0])
    
    ajustados = [level]
    residuos = []
    
    for t in range(1, n):
        y_t = float(valores[t])
        last_level = level
        level = alfa * y_t + (1 - alfa) * (last_level + trend)
        trend = beta * (level - last_level) + (1 - beta) * trend
        pred_t = last_level + trend
        ajustados.append(pred_t)
        residuos.append(y_t - pred_t)
        
    # Desviación estándar de los errores residuales
    var_res = sum(r ** 2 for r in residuos) / max(1, len(residuos))
    sigma = math.sqrt(var_res) if var_res > 0 else 0.5
    
    # Proyecciones a futuro
    hoy = date.today()
    proyecciones = []
    for h in range(1, dias_proyeccion + 1):
        f_fut = (hoy + timedelta(days=h)).strftime('%Y-%m-%d')
        y_hat = max(0.0, level + h * trend)
        
        # Margen de error acumulado con raíz del horizonte h (intervalo 95% = 1.96 * sigma * sqrt(h))
        margen = 1.96 * sigma * math.sqrt(h)
        lim_inf = max(0.0, round(y_hat - margen, 2))
        lim_sup = round(y_hat + margen, 2)
        
        proyecciones.append({
            "fecha": f_fut,
            "prediccion": round(y_hat, 2),
            "limite_inferior": lim_inf,
            "limite_superior": lim_sup
        })
        
    # Clasificación de tendencia
    if trend > 0.05:
        tipo_tendencia = "ALCISTA"
    elif trend < -0.05:
        tipo_tendencia = "BAJISTA"
    else:
        tipo_tendencia = "ESTABLE"
        
    return {
        "historico": serie,
        "proyecciones": proyecciones,
        "tendencia": tipo_tendencia,
        "tasa_crecimiento_diario": round(trend, 3),
        "sigma": round(sigma, 2)
    }


def evaluar_backtesting_modelo(
    serie: List[Dict[str, Any]],
    dias_test: int = 14
) -> Dict[str, Any]:
    """
    Ejecuta backtesting temporal: divide la serie histórica en Entrenamiento y Prueba,
    evaluando la precisión real contra métricas MAE, RMSE y MAPE.
    """
    if len(serie) < dias_test + 7:
        dias_test = max(3, len(serie) // 3)
        
    train_serie = serie[:-dias_test]
    test_serie = serie[-dias_test:]
    
    valores_train = [it["unidades"] for it in train_serie]
    valores_test = [it["unidades"] for it in test_serie]
    
    if not valores_train or not valores_test:
        return {
            "mae": 0.0,
            "rmse": 0.0,
            "mape": 0.0,
            "precision_pct": 100.0,
            "puntos_evaluados": 0
        }
        
    alfa = 0.35
    beta = 0.15
    level = float(valores_train[0])
    trend = float(valores_train[1] - valores_train[0]) if len(valores_train) > 1 else 0.0
    
    for t in range(1, len(valores_train)):
        y_t = float(valores_train[t])
        last_level = level
        level = alfa * y_t + (1 - alfa) * (last_level + trend)
        trend = beta * (level - last_level) + (1 - beta) * trend
        
    predicciones_test = []
    for h in range(1, len(valores_test) + 1):
        pred_h = max(0.0, level + h * trend)
        predicciones_test.append(pred_h)
        
    # Cálculo de métricas
    n = len(valores_test)
    errores_abs = []
    errores_cuad = []
    errores_pct = []
    
    comparativa = []
    for i in range(n):
        y_real = float(valores_test[i])
        y_pred = predicciones_test[i]
        diff = y_real - y_pred
        errores_abs.append(abs(diff))
        errores_cuad.append(diff ** 2)
        
        # Evitar división por cero en MAPE utilizando denominador suavizado
        denom = max(1.0, y_real)
        errores_pct.append(abs(diff) / denom)
        
        comparativa.append({
            "fecha": test_serie[i]["fecha"],
            "real": y_real,
            "predicho": round(y_pred, 2),
            "error_absoluto": round(abs(diff), 2)
        })
        
    mae = sum(errores_abs) / n
    rmse = math.sqrt(sum(errores_cuad) / n)
    mape = (sum(errores_pct) / n) * 100.0
    precision_pct = max(0.0, min(100.0, 100.0 - mape))
    
    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2),
        "precision_pct": round(precision_pct, 2),
        "puntos_evaluados": n,
        "comparativa": comparativa
    }


def calcular_recomendaciones_reposicion_db(
    id_empresa: int,
    id_sucursal: Optional[int] = None,
    lead_time_dias: int = 7
) -> List[Dict[str, Any]]:
    """
    Calcula recomendaciones automáticas de reposición cruzando la demanda diaria proyectada
    con el inventario físico actual y el stock mínimo por variante y sucursal.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = _get_schema()
        where_clauses = ["p.id_empresa = %s", "p.activo = TRUE"]
        params = [id_empresa]
        
        if id_sucursal:
            where_clauses.append("i.id_sucursal = %s")
            params.append(id_sucursal)
            
        where_sql = " AND ".join(where_clauses)
        
        # 1. Ventas recientes de los últimos 30 días agrupadas por variante y sucursal
        q_ventas_variante = f"""
            SELECT 
                dv.id_variante,
                v.id_sucursal,
                COALESCE(SUM(dv.cantidad), 0) AS total_vendido_30d,
                COUNT(DISTINCT DATE(v.fecha_venta)) AS dias_con_venta
            FROM {schema}.t_venta v
            JOIN {schema}.t_detalle_venta dv ON dv.id_venta = v.id_venta
            WHERE v.id_empresa = %s
              AND UPPER(COALESCE(v.estado, '')) NOT IN ('ANULADA', 'CANCELADA', 'PENDIENTE_PAGO')
              AND v.fecha_venta >= CURRENT_DATE - 30
            GROUP BY dv.id_variante, v.id_sucursal;
        """
        ventas_raw = db.execute_query(q_ventas_variante, (id_empresa,), fetchall=True) or []
        tasas_venta: Dict[Tuple[int, int], float] = {}
        for vr in ventas_raw:
            id_var = vr[0]
            id_suc = vr[1]
            tot_30d = float(vr[2] or 0)
            tasas_venta[(id_var, id_suc)] = max(0.05, tot_30d / 30.0) # Ritmo diario
            
        # 2. Inventario actual por variante y sucursal
        q_inventario = f"""
            SELECT 
                i.id_inventario,
                i.id_sucursal,
                s.nombre AS sucursal_nombre,
                p.id_producto,
                p.nombre AS producto_nombre,
                p.codigo_producto,
                cat.nombre AS categoria_nombre,
                ptc.id_variante,
                ptc.sku,
                t.nombre AS talla,
                col.nombre AS color,
                COALESCE(i.stock_actual, 0) AS stock_actual,
                COALESCE(i.stock_disponible, 0) AS stock_disponible,
                COALESCE(i.stock_minimo, 5) AS stock_minimo,
                p.precio
            FROM {schema}.t_inventario i
            JOIN {schema}.t_sucursal s ON s.id_sucursal = i.id_sucursal
            JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = i.id_variante
            JOIN {schema}.t_producto p ON p.id_producto = ptc.id_producto
            LEFT JOIN {schema}.t_categoria cat ON cat.id_categoria = p.id_categoria
            LEFT JOIN {schema}.t_talla t ON t.id_talla = ptc.id_talla
            LEFT JOIN {schema}.t_color col ON col.id_color = ptc.id_color
            WHERE {where_sql}
            ORDER BY s.nombre ASC, p.nombre ASC, ptc.sku ASC;
        """
        inv_rows = db.execute_query(q_inventario, tuple(params), fetchall=True) or []
        
        recomendaciones = []
        for r in inv_rows:
            id_var = r[7]
            id_suc = r[1]
            disp = int(r[12] or 0)
            s_min = int(r[13] or 5)
            precio = float(r[14] or 0.0)
            
            ritmo_diario = tasas_venta.get((id_var, id_suc), 0.1) # promedio base
            
            # Días de cobertura de inventario actual
            dias_cobertura = round(disp / ritmo_diario, 1) if ritmo_diario > 0 else 999.0
            
            # Nivel de riesgo
            if disp == 0:
                riesgo = "CRITICO"
                prioridad = 1
            elif dias_cobertura <= lead_time_dias:
                riesgo = "ALTO"
                prioridad = 2
            elif dias_cobertura <= lead_time_dias * 2:
                riesgo = "MODERADO"
                prioridad = 3
            else:
                riesgo = "OPTIMO"
                prioridad = 4
                
            # Demanda esperada durante el ciclo de reposición (lead time + margen de seguridad)
            demanda_lead_time = ritmo_diario * (lead_time_dias + 3)
            reposicion_sugerida = max(0, math.ceil(demanda_lead_time + s_min - disp))
            
            if reposicion_sugerida > 0 or riesgo in ("CRITICO", "ALTO"):
                costo_estimado = round(reposicion_sugerida * (precio * 0.55), 2)
                
                # Explicación clara y profesional
                if disp == 0:
                    explicacion = f"Prenda agotada físicamente. Se recomienda reponer {reposicion_sugerida} unidades de inmediato para cubrir {lead_time_dias} días de venta."
                elif dias_cobertura <= lead_time_dias:
                    explicacion = f"Inventario para solo {dias_cobertura} días al ritmo de {ritmo_diario:.1f} u/día. Riesgo inminente de quiebre antes de la llegada del pedido."
                else:
                    explicacion = f"Cobertura de {dias_cobertura} días. Reposición preventiva sugerida para mantener el umbral de seguridad."
                    
                recomendaciones.append({
                    "id_inventario": r[0],
                    "id_sucursal": id_suc,
                    "sucursal": r[2],
                    "id_producto": r[3],
                    "producto": r[4],
                    "codigo_producto": r[5],
                    "categoria": r[6] or "Alta Costura",
                    "id_variante": id_var,
                    "sku": r[8],
                    "talla": r[9] or "Única",
                    "color": r[10] or "Estándar",
                    "stock_disponible": disp,
                    "stock_minimo": s_min,
                    "ritmo_diario_estimado": round(ritmo_diario, 2),
                    "dias_cobertura": dias_cobertura,
                    "riesgo_rotura": riesgo,
                    "prioridad": prioridad,
                    "reposicion_sugerida": reposicion_sugerida,
                    "inversion_estimada_bs": costo_estimado,
                    "explicacion": explicacion
                })
                
        # Ordenar por criticidad (prioridad ascendente)
        recomendaciones.sort(key=lambda x: (x["prioridad"], x["dias_cobertura"]))
        return recomendaciones
    finally:
        db.close_connection()
