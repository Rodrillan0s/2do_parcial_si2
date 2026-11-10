#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador Maestro del Script de Automatización de Diagramas de Secuencia UML 2.5 para Sparx Enterprise Architect
Proyecto: AuroraStore SaaS
Casos de Uso: CU11W a CU15W
  - CU11W / CU02M: Buscar y filtrar productos
  - CU12W / CU03M: Consultar detalles de producto
  - CU13W / CU04M: Consultar disponibilidad por sucursal
  - CU14W / CU05M: Gestionar reservas
  - CU15W: Gestionar inventario
"""

import os
import sys

def build_javascript_content():
    return r"""/*
 * =================================================================================================
 * SCRIPT MAESTRO DE AUTOMATIZACIÓN DE DIAGRAMAS DE SECUENCIA UML 2.5 PARA SPARX ENTERPRISE ARCHITECT
 * =================================================================================================
 * Proyecto: AuroraStore SaaS
 * Casos de Uso soportados (Exactamente 5 diagramas únicos consolidados):
 *   - sd CU11W - Buscar y filtrar productos (Web y Móvil)
 *   - sd CU12W - Consultar detalles de producto (Web y Móvil)
 *   - sd CU13W - Consultar disponibilidad por sucursal (Web y Móvil)
 *   - sd CU14W - Gestionar reservas (Web y Móvil)
 *   - sd CU15W - Gestionar inventario
 * 
 * Reglas de Modelado UML 2.5 en Enterprise Architect:
 *   1. Líneas de Vida Rectangulares Estándar UML:
 *      - Sin estereotipos «boundary», «control» o «entity» en las lifelines para evitar círculos de robustez.
 *      - Representan cabeceras estándar rectangulares [ Object1 ] con líneas verticales discontinuas.
 *   2. Controladores fieles a la implementación real del backend:
 *      - CU11W: catalogo_routes, catalogo_services
 *      - CU12W: catalogo_routes, catalogo_services
 *      - CU13W: inventario_routes, inventario_services
 *      - CU14W: reserva_routes, reserva_services
 *      - CU15W: inventario_routes, inventario_services, compras_lotes_routes
 *   3. Interfaces limpias y sintetizadas (1 Boundary UI por caso de uso).
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
    // Stereotype vacío para cabecera rectangular estándar UML
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
// 1. CU11W / CU02M: Buscar y filtrar productos
// =================================================================================================
function generarCU11W(pkg) {
    Session.Output(" -> Construyendo: sd CU11W - Buscar y filtrar productos");
    var diag = pkg.Diagrams.AddNew("sd CU11W - Buscar y filtrar productos", "Sequence");
    diag.Update();

    var totalH = 800;
    var w = 125;
    var pitch = 150;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "user : Usuario", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : BusquedaFiltrosUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : catalogo_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : catalogo_services", "Sequence", x, w, totalH); x += pitch;
    var tCat = agregarLifeline(pkg, diag, "t_categoria", "Sequence", x, w, totalH); x += pitch;
    var tPrd = agregarLifeline(pkg, diag, "t_producto", "Sequence", x, w, totalH); x += pitch;
    var tVar = agregarLifeline(pkg, diag, "t_producto_talla_color", "Sequence", x, w, totalH); x += pitch;
    var cLoc = agregarLifeline(pkg, diag, "cache_local", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Filtrar y Listar Catálogo
    agregarMensaje(act, ui, seq++ + ": aplicar_filtros(categoria, talla, color, busqueda)", seq, false, false);

    // Fragmento alt: Detección de Conectividad
    agregarFragmentoCombinado(pkg, diag, "alt_conectividad_busqueda", "alt", "[sin conexion de red: MODO OFFLINE] vs [else: conexion activa: ONLINE]", 40, 1180, 130, 480);

    // Rama Offline (Nodo Rojo)
    agregarMensaje(ui, cLoc, seq++ + ": buscar_productos_cache(query, filtros)", seq, false, true);
    agregarMensaje(cLoc, ui, seq++ + ": return productos_filtrados_cache", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_resultados_offline(\"(Resultados en Caché)\")", seq, true, true);

    // Rama Online
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/catalogo/productos?q=&cat=&tal=&col=", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": listar_productos_catalogo(filtros)", seq, false, false);
    agregarMensaje(srv, tPrd, seq++ + ": SELECT p.*, c.nombre FROM t_producto p JOIN t_categoria c ON c.id_categoria=p.id_categoria WHERE p.activo=true", seq, false, false);
    agregarMensaje(tPrd, srv, seq++ + ": return lista_productos", seq, true, false);
    agregarMensaje(srv, tVar, seq++ + ": JOIN t_producto_talla_color (precios y variantes)", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return productos_filtrados", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (productos_filtrados)", seq, true, false);
    agregarMensaje(ui, cLoc, seq++ + ": sincronizar_cache_local(productos_filtrados)", seq, false, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_productos_encontrados()", seq, true, false);

    // Escenario 2: Seleccionar producto
    agregarMensaje(act, ui, seq++ + ": seleccionar_producto(id_producto)", seq, false, false);
    agregarMensaje(ui, act, seq++ + ": navegar_a_detalle(id_producto)", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 2. CU12W / CU03M: Consultar detalles de producto
// =================================================================================================
function generarCU12W(pkg) {
    Session.Output(" -> Construyendo: sd CU12W - Consultar detalles de producto");
    var diag = pkg.Diagrams.AddNew("sd CU12W - Consultar detalles de producto", "Sequence");
    diag.Update();

    var totalH = 800;
    var w = 125;
    var pitch = 150;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "user : Usuario", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : DetalleProductoUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : catalogo_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : catalogo_services", "Sequence", x, w, totalH); x += pitch;
    var tCat = agregarLifeline(pkg, diag, "t_categoria", "Sequence", x, w, totalH); x += pitch;
    var tPrd = agregarLifeline(pkg, diag, "t_producto", "Sequence", x, w, totalH); x += pitch;
    var tVar = agregarLifeline(pkg, diag, "t_producto_talla_color", "Sequence", x, w, totalH); x += pitch;
    var cLoc = agregarLifeline(pkg, diag, "cache_local", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Consultar Detalle
    agregarMensaje(act, ui, seq++ + ": abrir_detalle_producto(id_producto)", seq, false, false);

    // Fragmento alt: Conectividad
    agregarFragmentoCombinado(pkg, diag, "alt_detalle_conectividad", "alt", "[sin conexion: MODO OFFLINE] vs [else: conexion activa: ONLINE]", 40, 1180, 130, 680);

    // Rama Offline (Nodo Rojo)
    agregarMensaje(ui, cLoc, seq++ + ": obtener_detalle_cache(id_producto)", seq, false, true);
    agregarMensaje(cLoc, ui, seq++ + ": return detalle_cache", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_detalle_producto_offline(\"(Modo Sin Conexión)\")", seq, true, true);

    // Rama Online
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/catalogo/productos/{id}", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": obtener_detalle_producto_catalogo(id_producto)", seq, false, false);
    agregarMensaje(srv, tPrd, seq++ + ": SELECT * FROM t_producto WHERE id_producto=:id AND activo=true", seq, false, false);
    agregarMensaje(tPrd, srv, seq++ + ": return datos_producto", seq, true, false);
    agregarMensaje(srv, tVar, seq++ + ": SELECT ptc.*, col.nombre, tal.talla FROM t_producto_talla_color ptc JOIN t_color col ON col.id_color=ptc.id_color JOIN t_talla tal ON tal.id_talla=ptc.id_talla WHERE ptc.id_producto=:id", seq, false, false);
    agregarMensaje(tVar, srv, seq++ + ": return variantes_completas", seq, true, false);
    agregarMensaje(srv, rtr, seq++ + ": return detalle_response", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (detalle_completo)", seq, true, false);
    agregarMensaje(ui, cLoc, seq++ + ": actualizar_cache_detalle(id_producto, datos)", seq, false, false);
    agregarMensaje(ui, act, seq++ + ": desplegar_vista_detalle_con_variantes()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 3. CU13W / CU04M: Consultar disponibilidad por sucursal
// =================================================================================================
function generarCU13W(pkg) {
    Session.Output(" -> Construyendo: sd CU13W - Consultar disponibilidad por sucursal");
    var diag = pkg.Diagrams.AddNew("sd CU13W - Consultar disponibilidad por sucursal", "Sequence");
    diag.Update();

    var totalH = 800;
    var w = 125;
    var pitch = 150;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "user : Usuario", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : DisponibilidadUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : inventario_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : inventario_services", "Sequence", x, w, totalH); x += pitch;
    var tSuc = agregarLifeline(pkg, diag, "t_sucursal", "Sequence", x, w, totalH); x += pitch;
    var tVar = agregarLifeline(pkg, diag, "t_producto_talla_color", "Sequence", x, w, totalH); x += pitch;
    var tInv = agregarLifeline(pkg, diag, "t_inventario", "Sequence", x, w, totalH); x += pitch;
    var cLoc = agregarLifeline(pkg, diag, "cache_local", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Consultar disponibilidad por sucursal
    agregarMensaje(act, ui, seq++ + ": seleccionar_sucursal_y_prenda(id_sucursal, id_variante)", seq, false, false);

    // Fragmento alt: Detección de Red
    agregarFragmentoCombinado(pkg, diag, "alt_conexion_stock", "alt", "[sin conexion: MODO OFFLINE] vs [else: conexion activa: ONLINE]", 40, 1180, 130, 680);

    // Rama Offline (Nodo Rojo)
    agregarMensaje(ui, cLoc, seq++ + ": consultar_stock_cache(id_sucursal, id_variante)", seq, false, true);
    agregarMensaje(cLoc, ui, seq++ + ": return stock_estimado_cache", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_disponibilidad_offline(\"(Stock Estimado)\")", seq, true, true);

    // Rama Online
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/inventario/disponibilidad?sucursal=:s&variante=:v", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": consultar_disponibilidad_variante(id_sucursal, id_variante)", seq, false, false);
    agregarMensaje(srv, tSuc, seq++ + ": SELECT id_sucursal, nombre FROM t_sucursal WHERE activo=true", seq, false, false);
    agregarMensaje(tSuc, srv, seq++ + ": return datos_sucursal", seq, true, false);
    agregarMensaje(srv, tInv, seq++ + ": SELECT stock_actual, stock_reservado, (stock_actual - stock_reservado) AS disponible FROM t_inventario WHERE id_sucursal=:s AND id_producto_talla_color=:v", seq, false, false);
    agregarMensaje(tInv, srv, seq++ + ": return datos_stock", seq, true, false);
    agregarMensaje(srv, rtr, seq++ + ": return disponibilidad_response", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (stock_disponible)", seq, true, false);
    agregarMensaje(ui, cLoc, seq++ + ": guardar_stock_cache(id_suc, id_var, disponible)", seq, false, false);
    agregarMensaje(ui, act, seq++ + ": actualizar_indicador_disponibilidad()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 4. CU14W / CU05M: Gestionar reservas
// =================================================================================================
function generarCU14W(pkg) {
    Session.Output(" -> Construyendo: sd CU14W - Gestionar reservas");
    var diag = pkg.Diagrams.AddNew("sd CU14W - Gestionar reservas", "Sequence");
    diag.Update();

    var totalH = 1040;
    var w = 125;
    var pitch = 150;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "cliente : Cliente", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : ReservasUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : reserva_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : reserva_services", "Sequence", x, w, totalH); x += pitch;
    var tCli = agregarLifeline(pkg, diag, "t_cliente", "Sequence", x, w, totalH); x += pitch;
    var tInv = agregarLifeline(pkg, diag, "t_inventario", "Sequence", x, w, totalH); x += pitch;
    var tRes = agregarLifeline(pkg, diag, "t_reserva", "Sequence", x, w, totalH); x += pitch;
    var tDet = agregarLifeline(pkg, diag, "t_detalle_reserva", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH); x += pitch;
    var cLoc = agregarLifeline(pkg, diag, "cache_local", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Agendar solicitud de reserva
    agregarMensaje(act, ui, seq++ + ": agendar_reserva(id_sucursal, id_variante, cantidad)", seq, false, false);

    // Fragmento alt: Conectividad
    agregarFragmentoCombinado(pkg, diag, "alt_conexion_reserva", "alt", "[sin conexion de red] vs [else: conexion activa]", 40, 1490, 130, 370);

    // Rama Offline (Nodo Rojo)
    agregarMensaje(ui, cLoc, seq++ + ": encolar_reserva_offline(solicitud)", seq, false, true);
    agregarMensaje(cLoc, ui, seq++ + ": return ticket_local_pendiente", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_reserva_pendiente_sync()", seq, true, true);

    // Rama Online
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/reservas/ (solicitud_reserva)", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": crear_reserva(datos_reserva)", seq, false, false);

    // Escenario 2: Confirmación en Servidor con bloqueo de stock
    agregarMensaje(srv, tInv, seq++ + ": SELECT stock_actual, stock_reservado FROM t_inventario WHERE id_sucursal=:s AND id_producto_talla_color=:v FOR UPDATE", seq, false, false);
    agregarMensaje(tInv, srv, seq++ + ": return datos_stock", seq, true, false);

    // Fragmento alt: Validación de Stock
    agregarFragmentoCombinado(pkg, diag, "alt_validacion_stock_reserva", "alt", "[(stock_actual - stock_reservado) < cantidad] vs [else: stock suficiente]", 480, 1350, 490, 950);

    // Rama Error Stock
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"Stock insuficiente para agendar reserva\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error_stock_insuficiente()", seq, true, true);

    // Rama Normal (else)
    agregarMensaje(srv, tCli, seq++ + ": SELECT id_cliente FROM t_cliente WHERE id_usuario=:usr", seq, false, false);
    agregarMensaje(tCli, srv, seq++ + ": return id_cliente", seq, true, false);

    agregarFragmentoCombinado(pkg, diag, "opt_cliente_nuevo", "opt", "[cliente no registrado]", 480, 780, 680, 735);
    agregarMensaje(srv, tCli, seq++ + ": INSERT INTO t_cliente(...) RETURNING id_cliente", seq, false, false);

    agregarMensaje(srv, tRes, seq++ + ": INSERT INTO t_reserva(id_cliente, id_sucursal, estado='PENDIENTE') RETURNING id_reserva", seq, false, false);
    agregarMensaje(tRes, srv, seq++ + ": return id_reserva", seq, true, false);
    agregarMensaje(srv, tDet, seq++ + ": INSERT INTO t_detalle_reserva(id_reserva, id_producto_talla_color, cantidad)", seq, false, false);
    agregarMensaje(srv, tInv, seq++ + ": UPDATE t_inventario SET stock_reservado = stock_reservado + :cant", seq, false, false);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"RESERVAS\", \"RESERVA_CONFIRMADA\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return reserva_confirmada", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 201 Created (codigo_retiro)", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_comprobante_reserva(codigo_retiro)", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 5. CU15W: Gestionar inventario
// =================================================================================================
function generarCU15W(pkg) {
    Session.Output(" -> Construyendo: sd CU15W - Gestionar inventario");
    var diag = pkg.Diagrams.AddNew("sd CU15W - Gestionar inventario", "Sequence");
    diag.Update();

    var totalH = 1100;
    var w = 120;
    var pitch = 145;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : AdminTienda", "Actor", x, 110, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : InventarioUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : inventario_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : inventario_services", "Sequence", x, w, totalH); x += pitch;
    var cmp  = agregarLifeline(pkg, diag, "compras : compras_lotes_routes", "Sequence", x, w, totalH); x += pitch;
    var tInv = agregarLifeline(pkg, diag, "t_inventario", "Sequence", x, w, totalH); x += pitch;
    var tMov = agregarLifeline(pkg, diag, "t_movimiento_inventario", "Sequence", x, w, totalH); x += pitch;
    var tOrd = agregarLifeline(pkg, diag, "t_orden_compra", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH); x += pitch;
    var cLoc = agregarLifeline(pkg, diag, "cache_local", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Listar inventario (con soporte offline)
    agregarMensaje(act, ui, seq++ + ": solicitar_inventario(filtros)", seq, false, false);

    // Fragmento alt: Conectividad
    agregarFragmentoCombinado(pkg, diag, "alt_inventario_conexion", "alt", "[sin conexion: MODO OFFLINE] vs [else: conexion activa: ONLINE]", 40, 1490, 130, 420);

    // Rama Offline
    agregarMensaje(ui, cLoc, seq++ + ": obtener_inventario_cache()", seq, false, true);
    agregarMensaje(cLoc, ui, seq++ + ": return inventario_cache", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_inventario_offline()", seq, true, true);

    // Rama Online
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/inventario/?sucursal=:s", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": listar_inventario(id_sucursal)", seq, false, false);
    agregarMensaje(srv, tInv, seq++ + ": SELECT inv.*, p.nombre, ptc.sku FROM t_inventario inv JOIN t_producto_talla_color ptc ...", seq, false, false);
    agregarMensaje(tInv, srv, seq++ + ": return stock_lista", seq, true, false);
    agregarMensaje(srv, rtr, seq++ + ": return inventario_response", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, cLoc, seq++ + ": actualizar_cache_inventario(stock_lista)", seq, false, false);
    agregarMensaje(ui, act, seq++ + ": renderizar_tabla_stock()", seq, true, false);

    // Escenario 2: Registrar Movimiento Manual de Inventario (Ajuste / Entrada / Salida)
    agregarMensaje(act, ui, seq++ + ": registrar_movimiento(id_inventario, tipo, cantidad, motivo)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/inventario/movimientos", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": registrar_movimiento(datos_movimiento)", seq, false, false);
    agregarMensaje(srv, tInv, seq++ + ": UPDATE t_inventario SET stock_actual = stock_actual +/- :cant WHERE id_inventario=:id", seq, false, false);
    agregarMensaje(srv, tMov, seq++ + ": INSERT INTO t_movimiento_inventario(id_inventario, tipo, cantidad, motivo)", seq, false, false);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"INVENTARIO\", \"AJUSTE_STOCK\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return movimiento_registrado", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 201 Created", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": actualizar_stock_vista()", seq, true, false);

    // Escenario 3: Agendar y recibir Orden de Compra (Reposición por Lote)
    agregarMensaje(act, ui, seq++ + ": agendar_y_recibir_orden(id_proveedor, items)", seq, false, false);
    agregarMensaje(ui, cmp, seq++ + ": POST /api/v1/inventario/compras-lotes/ordenes", seq, false, false);
    agregarMensaje(cmp, tOrd, seq++ + ": INSERT INTO t_orden_compra(id_proveedor, estado='RECIBIDA')", seq, false, false);
    agregarMensaje(cmp, tInv, seq++ + ": UPDATE t_inventario SET stock_actual = stock_actual + :cant", seq, false, false);
    agregarMensaje(cmp, tMov, seq++ + ": INSERT INTO t_movimiento_inventario(tipo='ENTRADA_COMPRA', cantidad)", seq, false, false);
    agregarMensaje(cmp, tBit, seq++ + ": registrar_bitacora(\"COMPRAS\", \"RECEPCION_ORDEN\")", seq, false, false);
    agregarMensaje(cmp, ui, seq++ + ": 201 Created (orden_recibida)", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": notificar_ingreso_lote_y_actualizar()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// FUNCIÓN PRINCIPAL DE EJECUCIÓN
// =================================================================================================
function Main() {
    Repository.EnsureOutputVisible("Script");
    Session.Output("================================================================================");
    Session.Output("Iniciando generación de Diagramas de Secuencia UML 2.5 (CU11W–CU15W) en EA...");
    Session.Output("================================================================================");

    var pkg = Repository.GetTreeSelectedPackage();
    if (pkg == null) {
        Session.Prompt("ERROR: Por favor seleccione un paquete en el Project Browser antes de ejecutar.", 0);
        return;
    }

    var pkgName = "Diagramas de Secuencia (UML 2.5) - CU11W a CU15W";
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

    generarCU11W(subPkg);
    generarCU12W(subPkg);
    generarCU13W(subPkg);
    generarCU14W(subPkg);
    generarCU15W(subPkg);

    Repository.RefreshModelView(subPkg.PackageID);
    Session.Output("================================================================================");
    Session.Output(" [OK] Se generaron exitosamente los 5 diagramas de secuencia (CU11W a CU15W).");
    Session.Output(" Paquete: " + subPkg.Name);
    Session.Output("================================================================================");
}

Main();
"""

def main():
    js_content = build_javascript_content()
    
    # 1. Write docs/enterprise_architect
    js_path = os.path.join("docs", "enterprise_architect", "AuroraStore_CU11W_CU15W_Sequence_FINAL_EA.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"[OK] Archivo JavaScript generado: {js_path} ({len(js_content)} bytes)")

    # 2. Write root
    root_js_path = "AuroraStore_CU11W_CU15W_Sequence_FINAL_EA.js"
    with open(root_js_path, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"[OK] Copia en raíz generada: {root_js_path}")

if __name__ == "__main__":
    main()

