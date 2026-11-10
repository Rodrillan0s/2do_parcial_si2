#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador Maestro del Script de Automatización de Diagramas de Secuencia UML 2.5 para Sparx Enterprise Architect
Proyecto: AuroraStore SaaS
Casos de Uso: CU16W, CU17W, CU24W, CU25W
  - CU16W: Registrar venta presencial (POS / Caja)
  - CU17W / CU06M: Registrar venta online (E-commerce / Checkout)
  - CU24W / CU12M: Solicitar devolución (Área Cliente)
  - CU25W: Gestionar devoluciones (Bandeja Administrativa)
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
 *   - sd CU16W - Registrar venta presencial (POS / Caja)
 *   - sd CU17W - Registrar venta online (E-commerce / Checkout)
 *   - sd CU24W - Solicitar devolución (Cliente)
 *   - sd CU25W - Gestionar devoluciones (Administración)
 * 
 * Reglas de Modelado UML 2.5 en Enterprise Architect:
 *   1. Líneas de Vida Rectangulares Estándar UML:
 *      - Sin estereotipos «boundary», «control» o «entity» en las lifelines para evitar círculos de robustez.
 *      - Cabecera rectangular clásica [ Object1 ] con líneas verticales discontinuas.
 *   2. Controladores fieles al backend real:
 *      - CU16W: pos_routes, pos_services, caja_services
 *      - CU17W: pago_routes, pago_services
 *      - CU24W: devoluciones_routes, devoluciones_services
 *      - CU25W: devoluciones_routes, devoluciones_services
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
// 1. CU16W: Registrar venta presencial (POS / Caja)
// =================================================================================================
function generarCU16W(pkg) {
    Session.Output(" -> Construyendo: sd CU16W - Registrar venta presencial");
    var diag = pkg.Diagrams.AddNew("sd CU16W - Registrar venta presencial", "Sequence");
    diag.Update();

    var totalH = 1040;
    var w = 120;
    var pitch = 145;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "cajero : Cajero", "Actor", x, 110, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : CajaPosUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : pos_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : pos_services", "Sequence", x, w, totalH); x += pitch;
    var tSes = agregarLifeline(pkg, diag, "t_caja_sesion", "Sequence", x, w, totalH); x += pitch;
    var tInv = agregarLifeline(pkg, diag, "t_inventario", "Sequence", x, w, totalH); x += pitch;
    var tVen = agregarLifeline(pkg, diag, "t_venta", "Sequence", x, w, totalH); x += pitch;
    var tDet = agregarLifeline(pkg, diag, "t_detalle_venta", "Sequence", x, w, totalH); x += pitch;
    var tPag = agregarLifeline(pkg, diag, "t_pago", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Verificar estado de caja
    agregarMensaje(act, ui, seq++ + ": iniciar_turno_venta()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/caja/sesion-activa", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": verificar_estado_caja(id_sucursal, id_cajero)", seq, false, false);
    agregarMensaje(srv, tSes, seq++ + ": SELECT id_sesion, estado FROM t_caja_sesion WHERE id_usuario=:u AND estado='ABIERTA'", seq, false, false);
    agregarMensaje(tSes, srv, seq++ + ": return estado_sesion", seq, true, false);

    // Fragmento alt: Caja Abierta
    agregarFragmentoCombinado(pkg, diag, "alt_estado_caja", "alt", "[caja cerrada || inactiva] vs [else: caja abierta]", 40, 750, 260, 480);

    // Rama Error Caja
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"Caja no abierta. Debe aperturar turno\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error_caja_cerrada()", seq, true, true);

    // Rama Normal (else)
    agregarMensaje(srv, rtr, seq++ + ": return sesion_valida(id_sesion)", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);

    // Escenario 2: Procesar Venta y Cobro
    agregarMensaje(act, ui, seq++ + ": registrar_venta(items, metodo_pago, monto_recibido)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/pos/ventas", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": registrar_venta_presencial(datos_venta)", seq, false, false);

    agregarMensaje(srv, tInv, seq++ + ": SELECT stock_actual, stock_reservado FROM t_inventario WHERE id_sucursal=:s FOR UPDATE", seq, false, false);
    agregarMensaje(tInv, srv, seq++ + ": return datos_stock", seq, true, false);

    // Fragmento alt: Stock Disponible
    agregarFragmentoCombinado(pkg, diag, "alt_stock_pos", "alt", "[stock_disponible < cantidad] vs [else: stock suficiente]", 480, 1350, 650, 990);

    // Rama Error Stock
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"Stock insuficiente para venta\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error_sin_stock()", seq, true, true);

    // Rama Normal: Registrar Venta
    agregarMensaje(srv, tVen, seq++ + ": INSERT INTO t_venta(...) RETURNING id_venta", seq, false, false);
    agregarMensaje(tVen, srv, seq++ + ": return id_venta", seq, true, false);
    agregarMensaje(srv, tDet, seq++ + ": INSERT INTO t_detalle_venta(id_venta, id_producto_talla_color, cantidad, precio)", seq, false, false);
    agregarMensaje(srv, tInv, seq++ + ": UPDATE t_inventario SET stock_actual = stock_actual - :cant", seq, false, false);
    agregarMensaje(srv, tPag, seq++ + ": INSERT INTO t_pago(id_venta, total, metodo_pago) RETURNING id_pago", seq, false, false);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"POS\", \"VENTA_PRESENCIAL_EXITOSA\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return comprobante_venta", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 201 Created (recibo)", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": imprimir_ticket_comprobante()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 2. CU17W / CU06M: Registrar venta online (E-commerce Checkout)
// =================================================================================================
function generarCU17W(pkg) {
    Session.Output(" -> Construyendo: sd CU17W - Registrar venta online");
    var diag = pkg.Diagrams.AddNew("sd CU17W - Registrar venta online", "Sequence");
    diag.Update();

    var totalH = 1040;
    var w = 120;
    var pitch = 145;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "cliente : Cliente", "Actor", x, 110, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : CheckoutUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : pago_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : pago_services", "Sequence", x, w, totalH); x += pitch;
    var tCar = agregarLifeline(pkg, diag, "t_carrito", "Sequence", x, w, totalH); x += pitch;
    var tInv = agregarLifeline(pkg, diag, "t_inventario", "Sequence", x, w, totalH); x += pitch;
    var tPag = agregarLifeline(pkg, diag, "t_pago", "Sequence", x, w, totalH); x += pitch;
    var tVen = agregarLifeline(pkg, diag, "t_venta", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH); x += pitch;
    var cLoc = agregarLifeline(pkg, diag, "cache_local", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Verificar Carrito y Disponibilidad
    agregarMensaje(act, ui, seq++ + ": iniciar_proceso_checkout()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/ecommerce/carrito", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": obtener_resumen_carrito(id_cliente)", seq, false, false);
    agregarMensaje(srv, tCar, seq++ + ": SELECT * FROM t_detalle_carrito WHERE id_carrito=:id", seq, false, false);
    agregarMensaje(tCar, srv, seq++ + ": return items_carrito", seq, true, false);

    agregarMensaje(srv, tInv, seq++ + ": SELECT stock_actual, stock_reservado FROM t_inventario WHERE id_producto_talla_color=ANY(:ids)", seq, false, false);
    agregarMensaje(tInv, srv, seq++ + ": return disponibilidad", seq, true, false);

    // Fragmento alt: Stock disponible
    agregarFragmentoCombinado(pkg, diag, "alt_stock_carrito", "alt", "[stock insuficiente] vs [else: stock suficiente]", 40, 1050, 275, 490);

    // Rama Error Stock
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"Uno o mas productos agotados\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error_stock_insuficiente()", seq, true, true);

    // Rama Normal (else)
    agregarMensaje(srv, rtr, seq++ + ": return resumen_pago(total, items)", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);

    // Escenario 2: Procesar Pago y Confirmar Venta
    agregarMensaje(act, ui, seq++ + ": confirmar_pago(metodo, datos_tarjeta_o_qr)", seq, false, false);

    // Fragmento alt: Conectividad
    agregarFragmentoCombinado(pkg, diag, "alt_conexion_pago", "alt", "[sin conexion: MODO OFFLINE] vs [else: conexion activa: ONLINE]", 40, 1490, 560, 990);

    // Rama Offline
    agregarMensaje(ui, cLoc, seq++ + ": encolar_operacion_offline(PAYMENT_PENDING)", seq, false, true);
    agregarMensaje(cLoc, ui, seq++ + ": return recibo_local_pendiente", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": esperar_reconexion_y_notificar()", seq, true, true);

    // Rama Online
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/ecommerce/pago/confirmar", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": procesar_pago_online(datos_pago)", seq, false, false);
    agregarMensaje(srv, tPag, seq++ + ": INSERT INTO t_pago(monto, metodo_pago, estado='COMPLETADO') RETURNING id_pago", seq, false, false);
    agregarMensaje(tPag, srv, seq++ + ": return id_pago", seq, true, false);
    agregarMensaje(srv, tVen, seq++ + ": INSERT INTO t_venta(id_cliente, id_pago, estado='PAGADO') RETURNING id_venta", seq, false, false);
    agregarMensaje(srv, tInv, seq++ + ": UPDATE t_inventario SET stock_actual = stock_actual - :cant", seq, false, false);
    agregarMensaje(srv, tCar, seq++ + ": DELETE FROM t_detalle_carrito WHERE id_carrito=:id (vaciar)", seq, false, false);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"ECOMMERCE\", \"VENTA_ONLINE_CONFIRMADA\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return orden_confirmada(codigo_pedido)", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 201 Created", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_comprobante_y_orden(codigo_pedido)", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 3. CU24W / CU12M: Solicitar devolución (Cliente)
// =================================================================================================
function generarCU24W(pkg) {
    Session.Output(" -> Construyendo: sd CU24W - Solicitar devolución");
    var diag = pkg.Diagrams.AddNew("sd CU24W - Solicitar devolución", "Sequence");
    diag.Update();

    var totalH = 800;
    var w = 125;
    var pitch = 150;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "cliente : Cliente", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : MisDevolucionesUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : devoluciones_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : devoluciones_services", "Sequence", x, w, totalH); x += pitch;
    var tCli = agregarLifeline(pkg, diag, "t_cliente", "Sequence", x, w, totalH); x += pitch;
    var tVen = agregarLifeline(pkg, diag, "t_venta", "Sequence", x, w, totalH); x += pitch;
    var tDev = agregarLifeline(pkg, diag, "t_devolucion", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Listar compras elegibles para devolución
    agregarMensaje(act, ui, seq++ + ": consultar_compras_elegibles()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/pedidos/devoluciones/elegibles", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": consultar_elegibilidad_venta(id_cliente)", seq, false, false);
    agregarMensaje(srv, tVen, seq++ + ": SELECT v.*, dv.* FROM t_venta v JOIN t_detalle_venta dv ON dv.id_venta=v.id_venta WHERE v.id_cliente=:id AND v.fecha >= NOW()-interval '15 days'", seq, false, false);
    agregarMensaje(tVen, srv, seq++ + ": return compras_elegibles", seq, true, false);
    agregarMensaje(srv, rtr, seq++ + ": return lista_elegibles", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_compras_para_devolucion()", seq, true, false);

    // Escenario 2: Enviar Solicitud de Devolución
    agregarMensaje(act, ui, seq++ + ": enviar_solicitud(id_venta, id_detalle_venta, motivo, id_sucursal)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/pedidos/devoluciones/solicitar", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": solicitar_devolucion(datos_solicitud)", seq, false, false);

    agregarMensaje(srv, tDev, seq++ + ": INSERT INTO t_devolucion(id_venta, id_cliente, id_sucursal, estado='PENDIENTE', motivo) RETURNING id_devolucion", seq, false, false);
    agregarMensaje(tDev, srv, seq++ + ": return id_devolucion", seq, true, false);
    agregarMensaje(srv, tDev, seq++ + ": INSERT INTO t_detalle_devolucion(id_devolucion, id_detalle_venta, cantidad)", seq, false, false);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"DEVOLUCIONES\", \"SOLICITUD_CREADA\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return solicitud_registrada(codigo_ticket)", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 201 Created", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_ticket_solicitud(codigo_ticket)", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 4. CU25W: Gestionar devoluciones (Bandeja Administrativa)
// =================================================================================================
function generarCU25W(pkg) {
    Session.Output(" -> Construyendo: sd CU25W - Gestionar devoluciones");
    var diag = pkg.Diagrams.AddNew("sd CU25W - Gestionar devoluciones", "Sequence");
    diag.Update();

    var totalH = 880;
    var w = 125;
    var pitch = 150;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : AdminTienda", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : GestionDevolucionesUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : devoluciones_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : devoluciones_services", "Sequence", x, w, totalH); x += pitch;
    var tDev = agregarLifeline(pkg, diag, "t_devolucion", "Sequence", x, w, totalH); x += pitch;
    var tInv = agregarLifeline(pkg, diag, "t_inventario", "Sequence", x, w, totalH); x += pitch;
    var tMov = agregarLifeline(pkg, diag, "t_movimiento_inventario", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Listar solicitudes pendientes
    agregarMensaje(act, ui, seq++ + ": solicitar_bandeja_devoluciones()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/pedidos/devoluciones/bandeja?sucursal=:s", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": listar_devoluciones_personal(id_sucursal)", seq, false, false);
    agregarMensaje(srv, tDev, seq++ + ": SELECT d.*, c.nombre FROM t_devolucion d JOIN t_cliente c ON c.id_cliente=d.id_cliente WHERE d.estado='PENDIENTE'", seq, false, false);
    agregarMensaje(tDev, srv, seq++ + ": return lista_pendientes", seq, true, false);
    agregarMensaje(srv, rtr, seq++ + ": return bandeja_response", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_lista_solicitudes()", seq, true, false);

    // Escenario 2: Evaluar y Dictaminar Devolución
    agregarMensaje(act, ui, seq++ + ": evaluar_solicitud(id_devolucion, dictamen, estado_prenda)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/pedidos/devoluciones/{id}/evaluar", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": resolver_solicitud(id_devolucion, dictamen)", seq, false, false);

    // Fragmento alt: Dictamen Aprobada vs Rechazada
    agregarFragmentoCombinado(pkg, diag, "alt_dictamen_devolucion", "alt", "[prendas danadas o plazo vencido: RECHAZADA] vs [else: APROBADA]", 40, 1180, 420, 830);

    // Rama Rechazada (Nodo Rojo)
    agregarMensaje(srv, tDev, seq++ + ": UPDATE t_devolucion SET estado='RECHAZADA', observacion=:obs", seq, false, true);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"DEVOLUCIONES\", \"SOLICITUD_RECHAZADA\")", seq, false, true);
    agregarMensaje(srv, rtr, seq++ + ": return dictamen_rechazado", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (rechazada)", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": notificar_rechazo_y_actualizar()", seq, true, true);

    // Rama Aprobada
    agregarMensaje(srv, tDev, seq++ + ": UPDATE t_devolucion SET estado='APROBADA'", seq, false, false);

    agregarFragmentoCombinado(pkg, diag, "opt_reingreso_stock", "opt", "[estado_prenda == 'REVENDIBLE']", 480, 1020, 640, 695);
    agregarMensaje(srv, tInv, seq++ + ": UPDATE t_inventario SET stock_actual = stock_actual + :cant", seq, false, false);
    agregarMensaje(srv, tMov, seq++ + ": INSERT INTO t_movimiento_inventario(tipo='ENTRADA_DEVOLUCION')", seq, false, false);

    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"DEVOLUCIONES\", \"DEVOLUCION_APROBADA_REEMBOLSO\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return devolucion_completada(monto_reembolso)", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_comprobante_reembolso()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// FUNCIÓN PRINCIPAL DE EJECUCIÓN
// =================================================================================================
function Main() {
    Repository.EnsureOutputVisible("Script");
    Session.Output("================================================================================");
    Session.Output("Iniciando generación de Diagramas de Secuencia (CU16W, CU17W, CU24W, CU25W) en EA...");
    Session.Output("================================================================================");

    var pkg = Repository.GetTreeSelectedPackage();
    if (pkg == null) {
        Session.Prompt("ERROR: Por favor seleccione un paquete en el Project Browser antes de ejecutar.", 0);
        return;
    }

    var pkgName = "Diagramas de Secuencia (UML 2.5) - Ventas y Devoluciones";
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

    generarCU16W(subPkg);
    generarCU17W(subPkg);
    generarCU24W(subPkg);
    generarCU25W(subPkg);

    Repository.RefreshModelView(subPkg.PackageID);
    Session.Output("================================================================================");
    Session.Output(" [OK] Se generaron exitosamente los 4 diagramas de secuencia en Enterprise Architect.");
    Session.Output(" Paquete: " + subPkg.Name);
    Session.Output("================================================================================");
}

Main();
"""

def main():
    js_content = build_javascript_content()
    
    # 1. Write docs/enterprise_architect
    js_path = os.path.join("docs", "enterprise_architect", "AuroraStore_CU16W_CU17W_CU24W_CU25W_Sequence_FINAL_EA.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"[OK] Archivo JavaScript generado: {js_path} ({len(js_content)} bytes)")

    # 2. Write root
    root_js_path = "AuroraStore_CU16W_CU17W_CU24W_CU25W_Sequence_FINAL_EA.js"
    with open(root_js_path, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"[OK] Copia en raíz generada: {root_js_path}")

if __name__ == "__main__":
    main()

