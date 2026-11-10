#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador Maestro del Script de Automatización de Diagramas de Secuencia UML 2.5 para Sparx Enterprise Architect
Proyecto: AuroraStore SaaS
Casos de Uso: CU18W a CU22W
  - CU18W: Sincronizar operaciones pendientes
  - CU19W: Resolver conflictos de sincronización
  - CU20W: Consultar ventas, reservas e inventario
  - CU21W: Visualizar indicadores empresariales
  - CU22W: Generar reportes bajo demanda
"""

import os
import sys

def build_javascript_content():
    return r"""/*
 * =================================================================================================
 * SCRIPT MAESTRO DE AUTOMATIZACIÓN DE DIAGRAMAS DE SECUENCIA UML 2.5 PARA SPARX ENTERPRISE ARCHITECT
 * =================================================================================================
 * Proyecto: AuroraStore SaaS
 * Casos de Uso soportados:
 *   - sd CU18W - Sincronizar operaciones pendientes
 *   - sd CU19W - Resolver conflictos de sincronización
 *   - sd CU20W - Consultar ventas, reservas e inventario
 *   - sd CU21W - Visualizar indicadores empresariales
 *   - sd CU22W - Generar reportes bajo demanda
 * 
 * Reglas de Modelado UML 2.5 en Enterprise Architect:
 *   1. Líneas de Vida Rectangulares Estándar UML:
 *      - Sin estereotipos «boundary», «control» o «entity» en las lifelines para evitar círculos de robustez.
 *      - Cabecera rectangular clásica [ Object1 ] con líneas verticales discontinuas.
 *   2. Controladores fieles al backend real:
 *      - CU18W: sync_routes, sync_services
 *      - CU19W: sync_routes, sync_services
 *      - CU20W: kpis_routes, kpis_services
 *      - CU21W: kpis_routes, kpis_services
 *      - CU22W: motor_reportes_routes, reportes_services
 *   3. Interfaces limpias y sintetizadas (1 Boundary UI por diagrama).
 *   4. Entidades reales de persistencia PostgreSQL y cache_local (IndexedDB/SQLite).
 *   5. Fragmentos combinados (alt, opt, loop) calculados con coordenadas negativas en 4to cuadrante (top > bottom).
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

    var fragObj = diag.DiagramObjects.AddNew("l=" + left + ";r=" + right + ";t=" + top + ";b=" + bottom + ";", "");
    fragObj.ElementID = frag.ElementID;
    fragObj.Update();

    return frag;
}

// =================================================================================================
// 1. CU18W: Sincronizar operaciones pendientes
// =================================================================================================
function generarCU18W(pkg) {
    Session.Output(" -> Construyendo: sd CU18W - Sincronizar operaciones pendientes");
    var diag = pkg.Diagrams.AddNew("sd CU18W - Sincronizar operaciones pendientes", "Sequence");
    diag.Update();

    var totalH = 1040;
    var w = 120;
    var pitch = 145;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : Administrador / Cajero", "Actor", x, 110, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : CentroSyncUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : sync_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : sync_services", "Sequence", x, w, totalH); x += pitch;
    var cLoc = agregarLifeline(pkg, diag, "cache_local", "Sequence", x, w, totalH); x += pitch;
    var tSyn = agregarLifeline(pkg, diag, "t_sync_operacion", "Sequence", x, w, totalH); x += pitch;
    var tInv = agregarLifeline(pkg, diag, "t_inventario", "Sequence", x, w, totalH); x += pitch;
    var tVen = agregarLifeline(pkg, diag, "t_venta", "Sequence", x, w, totalH); x += pitch;
    var tPag = agregarLifeline(pkg, diag, "t_pago", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Iniciar Sincronización Manual o por Reconexión
    agregarMensaje(act, ui, seq++ + ": solicitar_sincronizacion()", seq, false, false);
    agregarMensaje(ui, cLoc, seq++ + ": obtener_cola_pendientes()", seq, false, false);
    agregarMensaje(cLoc, ui, seq++ + ": return lote_operaciones[UUIDs, payloads]", seq, true, false);

    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/sync/lote (body: lote)", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": _ejecutar_lote_sync(lote, token_data)", seq, false, false);

    agregarMensaje(srv, tSyn, seq++ + ": SELECT operation_id, status FROM t_sync_operacion WHERE operation_id=ANY(:ids)", seq, false, false);
    agregarMensaje(tSyn, srv, seq++ + ": return operaciones_registradas", seq, true, false);

    // Fragmento loop: Procesar cada operación
    agregarFragmentoCombinado(pkg, diag, "loop_procesar_operaciones", "loop", "[para cada operacion no confirmada]", 480, 1350, 275, 595);
    agregarMensaje(srv, tInv, seq++ + ": verificar_y_descontar_stock(id_sucursal, items)", seq, false, false);
    agregarMensaje(srv, tVen, seq++ + ": INSERT INTO t_venta(...) RETURNING id_venta", seq, false, false);
    agregarMensaje(srv, tPag, seq++ + ": INSERT INTO t_pago(id_venta, total, metodo_pago)", seq, false, false);
    agregarMensaje(srv, tSyn, seq++ + ": INSERT INTO t_sync_operacion(op_id, status='CONFIRMED', fingerprint)", seq, false, false);

    // Fragmento alt: Resultado del Lote (Conflictos vs Éxito Total)
    agregarFragmentoCombinado(pkg, diag, "alt_resultado_sync", "alt", "[existen operaciones con conflicto de stock/caja] vs [else: todas confirmadas]", 40, 1350, 650, 990);

    // Rama Conflictos
    agregarMensaje(srv, tSyn, seq++ + ": UPDATE t_sync_operacion SET status='CONFLICT', conflict_code='STOCK_INSUFFICIENT'", seq, false, true);
    agregarMensaje(srv, rtr, seq++ + ": return lote_resultado(confirmadas, conflictos)", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 207 Multi-Status (conflictos detectados)", seq, true, true);
    agregarMensaje(ui, cLoc, seq++ + ": retener_conflictos_en_cola(reconciliation_required)", seq, false, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_alerta_conflictos_pendientes()", seq, true, true);

    // Rama Normal: Todas confirmadas
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"SYNC\", \"LOTE_SINCRONIZADO_EXITO\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return lote_completado_recibo(confirmadas)", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (lote_confirmado)", seq, true, false);
    agregarMensaje(ui, cLoc, seq++ + ": purgar_cola_confirmadas(recibos)", seq, false, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_sincronizacion_exitosa()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 2. CU19W: Resolver conflictos de sincronización
// =================================================================================================
function generarCU19W(pkg) {
    Session.Output(" -> Construyendo: sd CU19W - Resolver conflictos de sincronización");
    var diag = pkg.Diagrams.AddNew("sd CU19W - Resolver conflictos de sincronización", "Sequence");
    diag.Update();

    var totalH = 920;
    var w = 125;
    var pitch = 150;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : Administrador", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : ResolucionConflictosUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : sync_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : sync_services", "Sequence", x, w, totalH); x += pitch;
    var cLoc = agregarLifeline(pkg, diag, "cache_local", "Sequence", x, w, totalH); x += pitch;
    var tSyn = agregarLifeline(pkg, diag, "t_sync_operacion", "Sequence", x, w, totalH); x += pitch;
    var tInv = agregarLifeline(pkg, diag, "t_inventario", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Consultar incidencias y conflictos pendientes
    agregarMensaje(act, ui, seq++ + ": solicitar_bandeja_conflictos()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/sync/pendientes-conciliacion", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": listar_conflictos_sync()", seq, false, false);
    agregarMensaje(srv, tSyn, seq++ + ": SELECT * FROM t_sync_operacion WHERE status='CONFLICT'", seq, false, false);
    agregarMensaje(tSyn, srv, seq++ + ": return lista_conflictos", seq, true, false);
    agregarMensaje(srv, rtr, seq++ + ": return conflictos_response", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_lista_incidencias()", seq, true, false);

    // Escenario 2: Aplicar resolución sobre el conflicto
    agregarMensaje(act, ui, seq++ + ": aplicar_resolucion(operation_id, accion='FORZAR'|'DESCARTAR')", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/sync/conciliar/{id} (resolucion)", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": procesar_conciliacion(id, resolucion)", seq, false, false);

    agregarMensaje(srv, tSyn, seq++ + ": SELECT status FROM t_sync_operacion WHERE operation_id=:id", seq, false, false);
    agregarMensaje(tSyn, srv, seq++ + ": return estado_actual", seq, true, false);

    // Fragmento alt: Verificación de estado de conflicto
    agregarFragmentoCombinado(pkg, diag, "alt_estado_resolucion", "alt", "[operacion ya resuelta previamente] vs [else: pendiente de conciliar]", 40, 1050, 430, 850);

    // Rama Error: Ya resuelta
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"Conflicto ya resuelto con anterioridad\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error_operacion_resuelta()", seq, true, true);

    // Rama Normal: Aplicar Conciliación
    agregarMensaje(srv, tSyn, seq++ + ": UPDATE t_sync_operacion SET status='RECONCILED', conflict_code=NULL", seq, false, false);
    agregarMensaje(srv, tInv, seq++ + ": UPDATE t_inventario (ajuste auditado de saldo)", seq, false, false);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"SYNC\", \"CONFLICTO_CONCILIADO\", op_id)", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return conciliacion_exitosa", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, cLoc, seq++ + ": actualizar_item_local_resuelto(operation_id)", seq, false, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_conflicto_corregido()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 3. CU20W: Consultar ventas, reservas e inventario (Gestión de Tienda)
// =================================================================================================
function generarCU20W(pkg) {
    Session.Output(" -> Construyendo: sd CU20W - Consultar ventas, reservas e inventario");
    var diag = pkg.Diagrams.AddNew("sd CU20W - Consultar ventas, reservas e inventario", "Sequence");
    diag.Update();

    var totalH = 800;
    var w = 120;
    var pitch = 145;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : AdminTienda / Encargado", "Actor", x, 110, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : GestionTiendaUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : kpis_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : kpis_services", "Sequence", x, w, totalH); x += pitch;
    var tSuc = agregarLifeline(pkg, diag, "t_sucursal", "Sequence", x, w, totalH); x += pitch;
    var tSes = agregarLifeline(pkg, diag, "t_caja_sesion", "Sequence", x, w, totalH); x += pitch;
    var tVen = agregarLifeline(pkg, diag, "t_venta", "Sequence", x, w, totalH); x += pitch;
    var tRes = agregarLifeline(pkg, diag, "t_reserva", "Sequence", x, w, totalH); x += pitch;
    var tInv = agregarLifeline(pkg, diag, "t_inventario", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Consultar consolidado operativo de tienda
    agregarMensaje(act, ui, seq++ + ": acceder_gestion_tienda(id_sucursal)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/kpis/operacionales?sucursal=:s", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": generar_dashboard_operacional(id_sucursal)", seq, false, false);

    agregarMensaje(srv, tSuc, seq++ + ": SELECT nombre, direccion FROM t_sucursal WHERE id_sucursal=:s", seq, false, false);
    agregarMensaje(tSuc, srv, seq++ + ": return datos_sucursal", seq, true, false);

    agregarMensaje(srv, tSes, seq++ + ": SELECT id_sesion, estado, monto_apertura FROM t_caja_sesion WHERE id_sucursal=:s AND estado='ABIERTA'", seq, false, false);
    agregarMensaje(tSes, srv, seq++ + ": return estado_caja_turno", seq, true, false);

    agregarMensaje(srv, tVen, seq++ + ": SELECT COUNT(*), SUM(total) FROM t_venta WHERE id_sucursal=:s AND fecha::date=CURRENT_DATE", seq, false, false);
    agregarMensaje(tVen, srv, seq++ + ": return metricas_ventas_dia", seq, true, false);

    agregarMensaje(srv, tRes, seq++ + ": SELECT COUNT(*), estado FROM t_reserva WHERE id_sucursal=:s GROUP BY estado", seq, false, false);
    agregarMensaje(tRes, srv, seq++ + ": return metricas_reservas", seq, true, false);

    agregarMensaje(srv, tInv, seq++ + ": SELECT SUM(stock_actual), SUM(stock_reservado), COUNT(*) FILTER (WHERE stock_actual <= 5) AS bajo_stock FROM t_inventario WHERE id_sucursal=:s", seq, false, false);
    agregarMensaje(tInv, srv, seq++ + ": return metricas_inventario", seq, true, false);

    agregarMensaje(srv, rtr, seq++ + ": return resumen_operacional_tienda(ventas, reservas, stock, caja)", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (datos_consolidados)", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_detalles_ventas_reservas_inventario()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 4. CU21W: Visualizar indicadores empresariales (Dashboard Estratégico)
// =================================================================================================
function generarCU21W(pkg) {
    Session.Output(" -> Construyendo: sd CU21W - Visualizar indicadores empresariales");
    var diag = pkg.Diagrams.AddNew("sd CU21W - Visualizar indicadores empresariales", "Sequence");
    diag.Update();

    var totalH = 800;
    var w = 120;
    var pitch = 145;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : Administrador", "Actor", x, 110, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : DashboardKpisUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : kpis_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : kpis_services", "Sequence", x, w, totalH); x += pitch;
    var emp  = agregarLifeline(pkg, diag, "empresa", "Sequence", x, w, totalH); x += pitch;
    var tSuc = agregarLifeline(pkg, diag, "t_sucursal", "Sequence", x, w, totalH); x += pitch;
    var tVen = agregarLifeline(pkg, diag, "t_venta", "Sequence", x, w, totalH); x += pitch;
    var tRes = agregarLifeline(pkg, diag, "t_reserva", "Sequence", x, w, totalH); x += pitch;
    var tInv = agregarLifeline(pkg, diag, "t_inventario", "Sequence", x, w, totalH); x += pitch;
    var tVal = agregarLifeline(pkg, diag, "t_valoracion", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Cargar Dashboard Estratégico de KPIs
    agregarMensaje(act, ui, seq++ + ": cargar_dashboard_kpis()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/kpis/resumen", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": generar_kpis_resumen(token_data)", seq, false, false);

    agregarMensaje(srv, emp, seq++ + ": SELECT id_empresa, nombre_empresa FROM empresa WHERE id_empresa=:id", seq, false, false);
    agregarMensaje(emp, srv, seq++ + ": return datos_empresa", seq, true, false);

    agregarMensaje(srv, tVen, seq++ + ": SELECT SUM(total) AS ingresos, COUNT(*) AS transacciones, AVG(total) AS ticket_promedio FROM t_venta WHERE fecha >= NOW()-interval '30 days'", seq, false, false);
    agregarMensaje(tVen, srv, seq++ + ": return kpi_ventas_mensual", seq, true, false);

    agregarMensaje(srv, tSuc, seq++ + ": SELECT s.nombre, SUM(v.total) FROM t_sucursal s JOIN t_venta v ON v.id_sucursal=s.id_sucursal GROUP BY s.nombre", seq, false, false);
    agregarMensaje(tSuc, srv, seq++ + ": return ventas_por_sucursal", seq, true, false);

    agregarMensaje(srv, tRes, seq++ + ": SELECT COUNT(*) FROM t_reserva WHERE estado='PENDIENTE'", seq, false, false);
    agregarMensaje(tRes, srv, seq++ + ": return total_reservas_activas", seq, true, false);

    agregarMensaje(srv, tInv, seq++ + ": SELECT SUM(stock_actual * precio_unitario) AS valuacion_stock FROM t_inventario", seq, false, false);
    agregarMensaje(tInv, srv, seq++ + ": return capital_en_stock", seq, true, false);

    agregarMensaje(srv, tVal, seq++ + ": SELECT AVG(calificacion) AS rating, COUNT(*) AS reviews FROM t_valoracion", seq, false, false);
    agregarMensaje(tVal, srv, seq++ + ": return satisfaccion_cliente", seq, true, false);

    agregarMensaje(srv, rtr, seq++ + ": return kpis_dashboard_payload", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_graficos_e_indicadores_kpi()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 5. CU22W: Generar reportes bajo demanda (Motor Dinámico & Vistas Analíticas)
// =================================================================================================
function generarCU22W(pkg) {
    Session.Output(" -> Construyendo: sd CU22W - Generar reportes bajo demanda");
    var diag = pkg.Diagrams.AddNew("sd CU22W - Generar reportes bajo demanda", "Sequence");
    diag.Update();

    var totalH = 1040;
    var w = 120;
    var pitch = 145;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : Administrador", "Actor", x, 110, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : ReportesUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : motor_reportes_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : reportes_services", "Sequence", x, w, totalH); x += pitch;
    var vVen = agregarLifeline(pkg, diag, "vw_ventas_reporte", "Sequence", x, w, totalH); x += pitch;
    var vInv = agregarLifeline(pkg, diag, "vw_inventario_reporte", "Sequence", x, w, totalH); x += pitch;
    var vRen = agregarLifeline(pkg, diag, "vw_rentabilidad_reporte", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Consultar catálogo de reportes y parsear comando
    agregarMensaje(act, ui, seq++ + ": ingresar_comando_reporte(\"ventas por sucursal en Q3\")", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/motor-reportes/parse-command", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": parsear_comando_reporte(texto_comando)", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return query_definicion(dimensiones, metricas, filtros)", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (query_definicion)", seq, true, false);

    // Escenario 2: Ejecutar Reporte sobre Vistas Analíticas
    agregarMensaje(act, ui, seq++ + ": confirmar_ejecucion_reporte(query_definicion)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/motor-reportes/ejecutar", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": ejecutar_reporte(query_definicion)", seq, false, false);

    // Fragmento alt: Vista Analítica Consultada según Tipo de Reporte
    agregarFragmentoCombinado(pkg, diag, "alt_vistas_analiticas", "alt", "[tipo == 'VENTAS'] vs [tipo == 'INVENTARIO'] vs [tipo == 'RENTABILIDAD']", 480, 1050, 390, 710);

    // Rama Ventas
    agregarMensaje(srv, vVen, seq++ + ": SELECT sucursal, SUM(total) FROM vw_ventas_reporte GROUP BY sucursal", seq, false, false);
    agregarMensaje(vVen, srv, seq++ + ": return filas_ventas", seq, true, false);

    // Rama Inventario
    agregarMensaje(srv, vInv, seq++ + ": SELECT prenda, stock_actual FROM vw_inventario_reporte", seq, false, false);
    agregarMensaje(vInv, srv, seq++ + ": return filas_inventario", seq, true, false);

    // Rama Rentabilidad
    agregarMensaje(srv, vRen, seq++ + ": SELECT categoria, margen_bruto FROM vw_rentabilidad_reporte", seq, false, false);
    agregarMensaje(vRen, srv, seq++ + ": return filas_rentabilidad", seq, true, false);

    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"REPORTES\", \"EJECUCION_REPORTE\", tipo)", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return reporte_resultado(filas, totales, graficos)", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (reporte_resultado)", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": desplegar_tabla_y_graficos()", seq, true, false);

    // Fragmento opt: Exportación de Reporte a PDF / Excel
    agregarFragmentoCombinado(pkg, diag, "opt_exportar_documento", "opt", "[usuario solicita exportacion PDF]", 40, 590, 830, 990);
    agregarMensaje(act, ui, seq++ + ": click_exportar_pdf()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/motor-reportes/exportar/pdf", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": generar_pdf_reporte(query_definicion)", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return pdf_bytes", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (application/pdf)", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": descargar_archivo_pdf()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// FUNCIÓN PRINCIPAL DE EJECUCIÓN
// =================================================================================================
function Main() {
    Repository.EnsureOutputVisible("Script");
    Session.Output("================================================================================");
    Session.Output("Iniciando generación de Diagramas de Secuencia (CU18W a CU22W) en EA...");
    Session.Output("================================================================================");

    var pkg = Repository.GetTreeSelectedPackage();
    if (pkg == null) {
        Session.Prompt("ERROR: Por favor seleccione un paquete en el Project Browser antes de ejecutar.", 0);
        return;
    }

    var pkgName = "Diagramas de Secuencia (UML 2.5) - Sincronizacion y Analitica";
    var subPkg = null;
    for (var i = 0; i < pkg.Packages.Count; i++) {
        var p = pkg.Packages.GetAt(i);
        if (p.Name == pkgName) {
            subPkg = p;
            break;
        }
    }
    if (subPkg == null) {
        subPkg = pkg.Packages.AddNew(pkgName, "");
        subPkg.Update();
        pkg.Packages.Refresh();
    }

    Session.Output("Paquete destino: " + subPkg.Name);

    generarCU18W(subPkg);
    generarCU19W(subPkg);
    generarCU20W(subPkg);
    generarCU21W(subPkg);
    generarCU22W(subPkg);

    Repository.RefreshModelView(subPkg.PackageID);
    Session.Output("================================================================================");
    Session.Output(" [OK] Se generaron exitosamente los 5 diagramas de secuencia (CU18W a CU22W).");
    Session.Output(" Paquete: " + subPkg.Name);
    Session.Output("================================================================================");
}

Main();
"""

def main():
    js_content = build_javascript_content()
    
    # 1. Write docs/enterprise_architect
    js_path = os.path.join("docs", "enterprise_architect", "AuroraStore_CU18W_CU22W_Sequence_FINAL_EA.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"[OK] Archivo JavaScript generado: {js_path} ({len(js_content)} bytes)")

    # 2. Write root
    root_js_path = "AuroraStore_CU18W_CU22W_Sequence_FINAL_EA.js"
    with open(root_js_path, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"[OK] Copia en raíz generada: {root_js_path}")

if __name__ == "__main__":
    main()
