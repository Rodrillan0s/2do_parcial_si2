#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador del Script de Automatización de Diagrama de Secuencia UML 2.5 para Sparx Enterprise Architect
Proyecto: AuroraStore SaaS
Caso de Uso: CU26W / CU08M - Registrar valoración de producto
"""

import os
import sys

def build_javascript_content():
    return r"""/*
 * =================================================================================================
 * SCRIPT MAESTRO DE AUTOMATIZACIÓN DE DIAGRAMAS DE SECUENCIA UML 2.5 PARA SPARX ENTERPRISE ARCHITECT
 * =================================================================================================
 * Proyecto: AuroraStore SaaS
 * Caso de Uso:
 *   - sd CU26W/CU08M - Registrar valoración de producto
 * 
 * Reglas de Modelado UML 2.5 en Enterprise Architect:
 *   1. Líneas de Vida Rectangulares Estándar UML:
 *      - Sin estereotipos «boundary», «control» o «entity» en las lifelines para evitar círculos de robustez.
 *      - Cabecera rectangular clásica [ Object1 ] con líneas verticales discontinuas.
 *   2. Controladores fieles al backend real FastAPI:
 *      - router : valoracion_routes
 *      - service : valoracion_services
 *   3. Interfaces limpias y trazables al diagrama de robustez:
 *      - ui_vta : VentaConfirmadaUI (pVenta)
 *      - ui_val : ModalValoracionUI (vValoración)
 *   4. Entidades reales de persistencia PostgreSQL:
 *      - t_producto, t_producto_talla_color, t_valoracion, t_bitacora.
 *   5. Fragmentos combinados (alt, opt) calculados con coordenadas en 4to cuadrante (top > bottom).
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
// GENERACIÓN: CU26W / CU08M - Registrar valoración de producto
// =================================================================================================
function generarCU26W_CU08M(pkg) {
    Session.Output(" -> Construyendo: sd CU26W/CU08M - Registrar valoración de producto");
    var diag = pkg.Diagrams.AddNew("sd CU26W/CU08M - Registrar valoración de producto", "Sequence");
    diag.Update();

    var totalH = 1220;
    var w = 125;
    var pitch = 145;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "cliente : Cliente", "Actor", x, 110, totalH); x += pitch;
    var uVta = agregarLifeline(pkg, diag, "ui_vta : VentaConfirmadaUI", "Sequence", x, w, totalH); x += pitch;
    var uVal = agregarLifeline(pkg, diag, "ui_val : ModalValoracionUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : valoracion_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : valoracion_services", "Sequence", x, w, totalH); x += pitch;
    var tPrd = agregarLifeline(pkg, diag, "t_producto", "Sequence", x, w, totalH); x += pitch;
    var tPtc = agregarLifeline(pkg, diag, "t_producto_talla_color", "Sequence", x, w, totalH); x += pitch;
    var tVal = agregarLifeline(pkg, diag, "t_valoracion", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Conclusión de compra y despliegue del modal de valoración (pop up)
    agregarMensaje(act, uVta, seq++ + ": confirmar_compra_o_servicio(id_pedido, items)", seq, false, false);
    agregarMensaje(uVta, uVal, seq++ + ": abrir_modal_valoracion(id_pedido, id_producto)", seq, false, false);
    agregarMensaje(uVal, act, seq++ + ": desplegar_selector_estrellas_y_comentario()", seq, true, false);

    // Fragmento opt: Flujo Alternativo A1 - Cierre voluntario sin registrar valoración
    agregarFragmentoCombinado(pkg, diag, "opt_cierre_voluntario", "opt", "[Flujo A1: Cliente decide no valorar y cierra]", 40, 480, 160, 260);
    agregarMensaje(act, uVal, seq++ + ": click_cerrar_modal()", seq, false, false);
    agregarMensaje(uVal, act, seq++ + ": cerrar_modal_sin_persistencia()", seq, true, false);

    // Fragmento alt: Flujo A2 (1 Estrella) vs Flujo Normal (2 a 5 Estrellas)
    agregarFragmentoCombinado(pkg, diag, "alt_puntuacion", "alt", "[Flujo A2: calificacion == 1 estrella (requiere motivo)] vs [Flujo Normal: calificacion >= 2 estrellas]", 40, 1370, 280, 1180);

    // Rama Flujo A2: 1 Estrella (Añade campos adicionales en rojo)
    agregarMensaje(act, uVal, seq++ + ": seleccionar_puntuacion(1_estrella)", seq, false, true);
    agregarMensaje(uVal, act, seq++ + ": desplegar_panel_motivos_criticos()", seq, true, true);
    agregarMensaje(act, uVal, seq++ + ": completar_motivo_negativo(motivo_predefinido, detalle_adicional)", seq, false, true);

    agregarMensaje(uVal, rtr, seq++ + ": POST /api/valoraciones (body: {puntuacion:1, motivo_negativo, comentario, ...})", seq, false, true);
    agregarMensaje(rtr, srv, seq++ + ": registrar_valoracion_cliente(dto, token_data)", seq, false, true);

    agregarMensaje(srv, tPrd, seq++ + ": SELECT nombre FROM t_producto WHERE id_producto=:id", seq, false, true);
    agregarMensaje(tPrd, srv, seq++ + ": return datos_producto", seq, true, true);

    agregarMensaje(srv, tPtc, seq++ + ": SELECT 1 FROM t_detalle_pedido dp JOIN t_producto_talla_color ptc ...", seq, false, true);
    agregarMensaje(tPtc, srv, seq++ + ": return compra_verificada", seq, true, true);

    agregarMensaje(srv, tVal, seq++ + ": INSERT INTO t_valoracion(..., puntuacion=1, motivo_negativo, requiere_revision=TRUE)", seq, false, true);
    agregarMensaje(tVal, srv, seq++ + ": return id_valoracion, requiere_revision=TRUE", seq, true, true);

    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"VALORACION\", \"ALERTA_CALIDAD_1_ESTRELLA\", id_valoracion)", seq, false, true);
    agregarMensaje(srv, rtr, seq++ + ": return {success:true, message:\"Valoración registrada con alerta de revisión\"}", seq, true, true);
    agregarMensaje(rtr, uVal, seq++ + ": 201 Created", seq, true, true);
    agregarMensaje(uVal, act, seq++ + ": mostrar_agradecimiento_y_aviso_seguimiento()", seq, true, true);

    // Rama Flujo Normal: 2 a 5 Estrellas
    agregarMensaje(act, uVal, seq++ + ": seleccionar_puntuacion(2_a_5_estrellas, comentario_opcional)", seq, false, false);
    agregarMensaje(uVal, rtr, seq++ + ": POST /api/valoraciones (body: {puntuacion:n, comentario, ...})", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": registrar_valoracion_cliente(dto, token_data)", seq, false, false);

    agregarMensaje(srv, tPtc, seq++ + ": validar_elegibilidad_compra(id_cliente, id_producto)", seq, false, false);
    agregarMensaje(tPtc, srv, seq++ + ": return compra_verificada", seq, true, false);

    agregarMensaje(srv, tVal, seq++ + ": INSERT INTO t_valoracion(..., puntuacion=n, requiere_revision=FALSE)", seq, false, false);
    agregarMensaje(tVal, srv, seq++ + ": return id_valoracion, requiere_revision=FALSE", seq, true, false);

    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"VALORACION\", \"VALORACION_REGISTRADA\", id_valoracion)", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return {success:true, message:\"Valoración registrada exitosamente\"}", seq, true, false);
    agregarMensaje(rtr, uVal, seq++ + ": 201 Created", seq, true, false);
    agregarMensaje(uVal, act, seq++ + ": mostrar_confirmacion_y_cerrar_modal()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// FUNCIÓN PRINCIPAL DE EJECUCIÓN
// =================================================================================================
function Main() {
    Repository.EnsureOutputVisible("Script");
    Session.Output("================================================================================");
    Session.Output("Iniciando generación de Diagrama de Secuencia (CU26W/CU08M) en EA...");
    Session.Output("================================================================================");

    var pkg = Repository.GetTreeSelectedPackage();
    if (pkg == null) {
        Session.Prompt("ERROR: Por favor seleccione un paquete en el Project Browser antes de ejecutar.", 0);
        return;
    }

    var targetPkg = pkg.Packages.AddNew("Diagramas de Secuencia (UML 2.5) - Valoracion de Productos y Servicios", "");
    targetPkg.Update();
    pkg.Packages.Refresh();

    generarCU26W_CU08M(targetPkg);

    Session.Output("================================================================================");
    Session.Output("¡Generación completada exitosamente!");
    Session.Output("Paquete creado: Diagramas de Secuencia (UML 2.5) - Valoracion de Productos y Servicios");
    Session.Output("Diagrama generado: sd CU26W/CU08M - Registrar valoración de producto");
    Session.Output("================================================================================");
}

Main();
"""

def main():
    ea_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.abspath(os.path.join(ea_dir, "..", ".."))

    js_code = build_javascript_content()

    out_file_ea = os.path.join(ea_dir, "AuroraStore_CU26W_CU08M_Sequence_FINAL_EA.js")
    with open(out_file_ea, "w", encoding="utf-8") as f:
        f.write(js_code)
    print(f"[OK] Archivo JavaScript generado: {out_file_ea} ({len(js_code)} bytes)")

    out_file_root = os.path.join(workspace_dir, "AuroraStore_CU26W_CU08M_Sequence_FINAL_EA.js")
    with open(out_file_root, "w", encoding="utf-8") as f:
        f.write(js_code)
    print(f"[OK] Copia en raíz generada: {out_file_root}")

if __name__ == "__main__":
    main()
