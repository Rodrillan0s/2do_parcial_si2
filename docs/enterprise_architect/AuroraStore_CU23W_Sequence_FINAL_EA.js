/*
 * =================================================================================================
 * SCRIPT MAESTRO DE AUTOMATIZACIÓN DE DIAGRAMAS DE SECUENCIA UML 2.5 PARA SPARX ENTERPRISE ARCHITECT
 * =================================================================================================
 * Proyecto: AuroraStore SaaS
 * Caso de Uso:
 *   - sd CU23W - Consultar análisis predictivo y patrones comerciales
 * 
 * Reglas de Modelado UML 2.5 en Enterprise Architect:
 *   1. Líneas de Vida Rectangulares Estándar UML:
 *      - Sin estereotipos «boundary», «control» o «entity» en las lifelines para evitar círculos de robustez.
 *      - Cabecera rectangular clásica [ Object1 ] con líneas verticales discontinuas.
 *   2. Controladores fieles al backend real FastAPI:
 *      - router : predicciones_routes
 *      - service : demanda_forecast_services
 *   3. Interfaces limpias y trazables al caso de uso:
 *      - ui : PrediccionesDemandaUI (pPrediccion y Demanda / /admin/predicciones)
 *   4. Entidades reales de persistencia PostgreSQL:
 *      - t_venta: Serie temporal de transacciones de demanda histórica.
 *      - t_detalle_venta: Unidades vendidas por prenda y variante.
 *      - t_inventario: Niveles actuales de stock físico y stock de seguridad.
 *      - t_producto: Precios de costo y catálogo activo.
 *      - t_recomendacion: Reglas de asociación, co-ocurrencia y afinidad de prendas.
 *   5. Fragmentos combinados (alt) calculados con coordenadas en 4to cuadrante (top > bottom).
 * =================================================================================================
 */

// -------------------------------------------------------------------------------------------------
// UTILIDADES Y HELPERS DE ENTERPRISE ARCHITECT AUTOMATION
// -------------------------------------------------------------------------------------------------

function agregarLifeline(pkg, diag, nombre, eaType, posX, ancho, altoTotal) {
    var tipoFinal = (eaType === "Actor") ? "Actor" : "Sequence";
    var el = pkg.Elements.AddNew(nombre, tipoFinal);
    el.Update();

    var left = posX;
    var right = posX + ancho;
    var top = -30;
    var bottom = -(30 + altoTotal);

    var diagObj = diag.DiagramObjects.AddNew("l=" + left + ";r=" + right + ";t=" + top + ";b=" + bottom + ";", "");
    diagObj.ElementID = el.ElementID;
    diagObj.Update();

    return el;
}

function agregarMensaje(sourceEl, targetEl, textoMensaje, seqNum, esRetorno, esError) {
    if (!sourceEl || !targetEl) return null;

    var conn = sourceEl.Connectors.AddNew(textoMensaje, "Sequence");
    conn.SupplierID = targetEl.ElementID;

    if (esError) {
        conn.Stereotype = "error";
    }
    conn.Update();
    sourceEl.Connectors.Refresh();

    try {
        if (esRetorno) {
            Repository.Execute("UPDATE t_connector SET PDATA4 = '1' WHERE Connector_ID = " + conn.ConnectorID);
        }
        if (seqNum > 0) {
            Repository.Execute("UPDATE t_connector SET SeqNo = " + seqNum + " WHERE Connector_ID = " + conn.ConnectorID);
        }
    } catch (ex) {
        // Fallback transparente
    }

    return conn;
}

function agregarFragmentoCombinado(pkg, diag, nombre, operador, guarda, left, right, topY, bottomY) {
    var frag = pkg.Elements.AddNew(nombre, "InteractionFragment");
    frag.Stereotype = operador; // "alt", "opt", "loop"
    frag.Notes = guarda;
    frag.Update();

    var top = -topY;
    var bottom = -bottomY;

    var diagObj = diag.DiagramObjects.AddNew("l=" + left + ";r=" + right + ";t=" + top + ";b=" + bottom + ";", "");
    diagObj.ElementID = frag.ElementID;
    diagObj.Update();

    return frag;
}

// =================================================================================================
// GENERACIÓN: CU23W - Consultar análisis predictivo y patrones comerciales
// =================================================================================================
function generarCU23W(pkg) {
    Session.Output(" -> Construyendo: sd CU23W - Consultar análisis predictivo y patrones comerciales");
    var diag = pkg.Diagrams.AddNew("sd CU23W - Consultar análisis predictivo y patrones comerciales", "Sequence");
    diag.Update();

    var totalH = 1250;
    var w = 120;
    var pitch = 145;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : Administrador / AdminTienda", "Actor", x, 110, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : PrediccionesDemandaUI", "Sequence", x, 125, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : predicciones_routes", "Sequence", x, 130, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : demanda_forecast_services", "Sequence", x, 135, totalH); x += pitch;
    var tVen = agregarLifeline(pkg, diag, "t_venta", "Sequence", x, w, totalH); x += pitch;
    var tDet = agregarLifeline(pkg, diag, "t_detalle_venta", "Sequence", x, 125, totalH); x += pitch;
    var tInv = agregarLifeline(pkg, diag, "t_inventario", "Sequence", x, w, totalH); x += pitch;
    var tPrd = agregarLifeline(pkg, diag, "t_producto", "Sequence", x, w, totalH); x += pitch;
    var tRec = agregarLifeline(pkg, diag, "t_recomendacion", "Sequence", x, 125, totalH);

    var seq = 1;

    // ---------------------------------------------------------------------------------------------
    // Escenario 1: Proyección de Demanda Temporal (Holt Linear Trend & Intervalos 95%)
    // ---------------------------------------------------------------------------------------------
    agregarMensaje(act, ui, seq++ + ": solicitar_proyeccion_demanda(id_sucursal, dias=14)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/ia/predicciones/demanda?id_sucursal=:s&dias_proyeccion=14", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": obtener_serie_temporal_ventas(empresa_id, sucursal_id, dias_historia=60)", seq, false, false);

    agregarMensaje(srv, tVen, seq++ + ": SELECT DATE(fecha_venta), SUM(subtotal) FROM t_venta WHERE fecha >= corte GROUP BY DATE", seq, false, false);
    agregarMensaje(tVen, srv, seq++ + ": return fechas_transacciones", seq, true, false);

    agregarMensaje(srv, tDet, seq++ + ": SELECT SUM(dv.cantidad) FROM t_detalle_venta dv JOIN t_venta v ...", seq, false, false);
    agregarMensaje(tDet, srv, seq++ + ": return serie_unidades_diarias", seq, true, false);

    agregarMensaje(srv, srv, seq++ + ": predecir_demanda_serie(serie, alfa=0.35, beta=0.15) [Holt trend]", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return {historico, proyecciones_14d, tendencia, sigma, IC_95}", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (forecast_demanda_payload)", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": renderizar_grafico_demanda_e_intervalos()", seq, true, false);

    // ---------------------------------------------------------------------------------------------
    // Escenario 2: Análisis de Reposición Inteligente y Riesgo de Quiebre de Stock
    // ---------------------------------------------------------------------------------------------
    agregarMensaje(act, ui, seq++ + ": consultar_recomendaciones_reposicion(lead_time=7)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/ia/predicciones/reposicion?lead_time_dias=7", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": calcular_recomendaciones_reposicion_db(empresa_id, sucursal_id, lead_time=7)", seq, false, false);

    agregarMensaje(srv, tInv, seq++ + ": SELECT stock_actual, stock_minimo, stock_seguridad FROM t_inventario WHERE id_sucursal=:s", seq, false, false);
    agregarMensaje(tInv, srv, seq++ + ": return saldos_stock_variantes", seq, true, false);

    agregarMensaje(srv, tPrd, seq++ + ": SELECT id_producto, precio_costo, nombre FROM t_producto WHERE id_empresa=:e AND activo=TRUE", seq, false, false);
    agregarMensaje(tPrd, srv, seq++ + ": return datos_prendas_y_costos", seq, true, false);

    agregarMensaje(srv, srv, seq++ + ": evaluar_punto_reorden(stock_actual, demanda_proyectada, lead_time)", seq, false, false);

    // Fragmento alt: Criticidad del Abastecimiento
    agregarFragmentoCombinado(pkg, diag, "alt_criticidad_reposicion", "alt", "[existen prendas con riesgo CRITICO o ALTO] vs [else: stock optimo]", 40, 1370, 685, 915);

    // Rama Crítico
    agregarMensaje(srv, rtr, seq++ + ": return {resumen: {alertas_criticas, inversion_sugerida_bs}, recomendaciones}", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (alertas_quiebre_stock)", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_semaforo_rojo_y_sugerencia_compra()", seq, true, true);

    // Rama Óptimo
    agregarMensaje(srv, rtr, seq++ + ": return {resumen: {alertas_criticas:0, alertas_altas:0}, recomendaciones:[]}", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (sin_alertas_reposicion)", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_indicador_abastecimiento_estable()", seq, true, false);

    // ---------------------------------------------------------------------------------------------
    // Escenario 3: Consulta de Patrones Comerciales y Afinidad de Productos
    // ---------------------------------------------------------------------------------------------
    agregarMensaje(act, ui, seq++ + ": consultar_patrones_comerciales_asociados()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/ia/predicciones/patrones-comerciales", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": obtener_matriz_afinidad_productos(empresa_id)", seq, false, false);

    agregarMensaje(srv, tRec, seq++ + ": SELECT id_producto, id_producto_recomendado, score_afinidad FROM t_recomendacion", seq, false, false);
    agregarMensaje(tRec, srv, seq++ + ": return reglas_asociacion_prendas", seq, true, false);

    agregarMensaje(srv, rtr, seq++ + ": return matriz_patrones_comerciales", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": desplegar_matriz_patrones_y_co_ocurrencia()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// FUNCIÓN PRINCIPAL DE EJECUCIÓN
// =================================================================================================
function Main() {
    Repository.EnsureOutputVisible("Script");
    Session.Output("================================================================================");
    Session.Output("Iniciando generación de Diagrama de Secuencia (CU23W) en EA...");
    Session.Output("================================================================================");

    var pkg = Repository.GetTreeSelectedPackage();
    if (pkg == null) {
        Session.Prompt("ERROR: Por favor seleccione un paquete en el Project Browser antes de ejecutar.", 0);
        return;
    }

    var targetPkg = pkg.Packages.AddNew("Diagramas de Secuencia (UML 2.5) - Analisis Predictivo IA", "");
    targetPkg.Update();
    pkg.Packages.Refresh();

    generarCU23W(targetPkg);

    Session.Output("================================================================================");
    Session.Output("¡Generación completada exitosamente!");
    Session.Output("Paquete creado: Diagramas de Secuencia (UML 2.5) - Analisis Predictivo IA");
    Session.Output("Diagrama generado: sd CU23W - Consultar análisis predictivo y patrones comerciales");
    Session.Output("================================================================================");
}

Main();
