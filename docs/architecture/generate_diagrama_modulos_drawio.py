#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador Maestro del Diagrama de Módulos de Sistema en formato Draw.io (.drawio / XML)
Proyecto: AuroraStore SaaS
Arquitectura: 3 Capas (Presentación, Negocio, Datos) integrando fielmente los 10 Módulos de Dominio.
Diseño Refinado: Espaciado generoso, flujo ortogonal sin cruces de flechas, legibilidad óptima.
"""

import os
import html
import xml.etree.ElementTree as ET
import xml.dom.minidom
import resvg_py
from PIL import Image

def build_drawio_xml():
    # Estilos optimizados para Draw.io / UML 2.5
    style_layer = (
        "shape=folder;fontStyle=1;tabWidth=140;tabHeight=28;tabPosition=left;html=1;boundedLbl=1;"
        "backgroundOutline=0;fillColor=#fafbfc;strokeColor=#1e293b;strokeWidth=2;fontFamily=Segoe UI,Arial;"
        "fontSize=13;fontColor=#0f172a;align=left;spacingLeft=15;verticalAlign=top;spacingTop=6;"
    )

    style_subsystem = (
        "shape=folder;fontStyle=1;tabWidth=130;tabHeight=22;tabPosition=left;html=1;boundedLbl=1;"
        "backgroundOutline=0;fillColor=#f8fafc;strokeColor=#64748b;strokeWidth=1.5;fontFamily=Segoe UI,Arial;"
        "fontSize=11;fontColor=#1e293b;align=left;spacingLeft=10;verticalAlign=top;spacingTop=4;"
    )

    style_subsystem_backend = (
        "shape=folder;fontStyle=1;tabWidth=160;tabHeight=24;tabPosition=left;html=1;boundedLbl=1;"
        "backgroundOutline=0;fillColor=#f8fafc;strokeColor=#334155;strokeWidth=1.8;fontFamily=Segoe UI,Arial;"
        "fontSize=11;fontColor=#0f172a;align=left;spacingLeft=12;verticalAlign=top;spacingTop=4;"
    )

    style_subsystem_ia = (
        "shape=folder;fontStyle=1;tabWidth=170;tabHeight=24;tabPosition=left;html=1;boundedLbl=1;"
        "backgroundOutline=0;fillColor=#faf5ff;strokeColor=#7c3aed;strokeWidth=1.8;fontFamily=Segoe UI,Arial;"
        "fontSize=11;fontColor=#4c1d95;align=left;spacingLeft=12;verticalAlign=top;spacingTop=4;"
    )

    style_subsystem_db = (
        "shape=folder;fontStyle=1;tabWidth=200;tabHeight=24;tabPosition=left;html=1;boundedLbl=1;"
        "backgroundOutline=0;fillColor=#f0fdf4;strokeColor=#059669;strokeWidth=1.8;fontFamily=Segoe UI,Arial;"
        "fontSize=11;fontColor=#064e3b;align=left;spacingLeft=12;verticalAlign=top;spacingTop=4;"
    )

    # Estilos de Componentes (Módulos)
    style_mod_coral = (
        "shape=component;align=center;valign=middle;html=1;whiteSpace=wrap;"
        "fillColor=#ffebee;gradientColor=#ffcdd2;strokeColor=#e53935;strokeWidth=1.4;"
        "fontFamily=Segoe UI,Arial;fontSize=11;fontStyle=1;fontColor=#1e293b;"
    )

    style_mod_ia = (
        "shape=component;align=center;valign=middle;html=1;whiteSpace=wrap;"
        "fillColor=#f3e8ff;gradientColor=#e9d5ff;strokeColor=#9333ea;strokeWidth=1.4;"
        "fontFamily=Segoe UI,Arial;fontSize=11;fontStyle=1;fontColor=#3b0764;"
    )

    style_mod_db = (
        "shape=component;align=center;valign=middle;html=1;whiteSpace=wrap;"
        "fillColor=#ecfdf5;gradientColor=#d1fae5;strokeColor=#059669;strokeWidth=1.4;"
        "fontFamily=Segoe UI,Arial;fontSize=11;fontStyle=1;fontColor=#064e3b;"
    )

    # Conectores ortogonales limpios
    style_edge_internal = (
        "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
        "dashed=1;endArrow=open;endSize=8;strokeColor=#64748b;strokeWidth=1.5;fontFamily=Segoe UI,Arial;"
        "fontSize=9;fontColor=#475569;labelBackgroundColor=#ffffff;labelBorderColor=#cbd5e1;"
    )

    style_edge_cross = (
        "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
        "dashed=1;endArrow=open;endSize=8;strokeColor=#dc2626;strokeWidth=1.8;fontFamily=Segoe UI,Arial;"
        "fontSize=9;fontColor=#991b1b;labelBackgroundColor=#ffffff;labelBorderColor=#fca5a5;"
    )

    nodes = []
    edges = []

    # ---------------------------------------------------------------------------------------------
    # 0. HEADER DEL DIAGRAMA
    # ---------------------------------------------------------------------------------------------
    nodes.append({
        "id": "header",
        "value": (
            "<b>pkg Diagrama de modulos de sistema — AuroraStore SaaS</b><br/>"
            "<span style='font-size:11px;font-weight:normal;color:#475569;'>"
            "Arquitectura en 3 Capas (Presentación, Negocio, Datos) integrando los 10 Módulos de Dominio</span>"
        ),
        "style": "text;html=1;align=left;verticalAlign=middle;fontSize=14;fontFamily=Segoe UI,Arial;fontStyle=1;fontColor=#0f172a;",
        "x": 30, "y": 10, "w": 800, "h": 30
    })

    # =============================================================================================
    # 1. CAPA PRESENTACIÓN
    # =============================================================================================
    nodes.append({
        "id": "capa_presentacion",
        "value": "&laquo;Capa&raquo;<br/><b>Presentación</b>",
        "style": style_layer,
        "x": 30, "y": 45, "w": 1380, "h": 275
    })

    # SubSistema Web (Angular PWA)
    nodes.append({
        "id": "sub_web",
        "value": "&laquo;SubSistema&raquo;<br/><b>Web (Angular 19 PWA)</b>",
        "style": style_subsystem,
        "x": 50, "y": 85, "w": 620, "h": 220
    })
    nodes.append({
        "id": "mod_web_views",
        "value": "&laquo;modulo&raquo;<br/><b>views</b><br/><span style='font-size:9px;font-weight:normal;'>Storefront &amp; Admin</span>",
        "style": style_mod_coral,
        "x": 75, "y": 125, "w": 230, "h": 60
    })
    nodes.append({
        "id": "mod_web_services",
        "value": "&laquo;modulo&raquo;<br/><b>Services</b><br/><span style='font-size:9px;font-weight:normal;'>HTTP Clients &amp; State</span>",
        "style": style_mod_coral,
        "x": 415, "y": 125, "w": 230, "h": 60
    })
    nodes.append({
        "id": "mod_web_offline",
        "value": "&laquo;modulo&raquo;<br/><b>offline</b><br/><span style='font-size:9px;font-weight:normal;'>IndexedDB &amp; Service Worker</span>",
        "style": style_mod_coral,
        "x": 75, "y": 215, "w": 230, "h": 60
    })

    # SubSistema Móvil (Flutter)
    nodes.append({
        "id": "sub_movil",
        "value": "&laquo;SubSistema&raquo;<br/><b>Movil (Flutter 3.x)</b>",
        "style": style_subsystem,
        "x": 710, "y": 85, "w": 680, "h": 220
    })
    nodes.append({
        "id": "mod_movil_views",
        "value": "&laquo;modulo&raquo;<br/><b>Views</b><br/><span style='font-size:9px;font-weight:normal;'>Flutter Client Screens</span>",
        "style": style_mod_coral,
        "x": 735, "y": 125, "w": 200, "h": 60
    })
    nodes.append({
        "id": "mod_movil_services",
        "value": "&laquo;modulo&raquo;<br/><b>Services</b><br/><span style='font-size:9px;font-weight:normal;'>ApiClient &amp; TokenStorage</span>",
        "style": style_mod_coral,
        "x": 1045, "y": 125, "w": 200, "h": 60
    })
    nodes.append({
        "id": "mod_movil_vestidor",
        "value": "&laquo;modulo&raquo;<br/><b>Vestidor RA</b><br/><span style='font-size:9px;font-weight:normal;'>ARCore &amp; Visor 3D GLB</span>",
        "style": style_mod_coral,
        "x": 735, "y": 215, "w": 200, "h": 60
    })
    nodes.append({
        "id": "mod_movil_offline",
        "value": "&laquo;modulo&raquo;<br/><b>offline</b><br/><span style='font-size:9px;font-weight:normal;'>SQLite DatabaseHelper</span>",
        "style": style_mod_coral,
        "x": 1045, "y": 215, "w": 200, "h": 60
    })

    # Conectores internos Presentación
    edges.append({"id": "e_wv_ws", "source": "mod_web_views", "target": "mod_web_services", "value": "&laquo;use&raquo;", "style": style_edge_internal})
    edges.append({"id": "e_wv_wo", "source": "mod_web_views", "target": "mod_web_offline", "value": "&laquo;use&raquo;", "style": style_edge_internal})
    edges.append({"id": "e_mv_ms", "source": "mod_movil_views", "target": "mod_movil_services", "value": "&laquo;use&raquo;", "style": style_edge_internal})
    edges.append({"id": "e_mv_mr", "source": "mod_movil_views", "target": "mod_movil_vestidor", "value": "&laquo;use&raquo;", "style": style_edge_internal})
    edges.append({"id": "e_mv_mo", "source": "mod_movil_views", "target": "mod_movil_offline", "value": "&laquo;use&raquo;", "style": style_edge_internal})

    # =============================================================================================
    # 2. CAPA NEGOCIO
    # =============================================================================================
    nodes.append({
        "id": "capa_negocio",
        "value": "&laquo;Capa&raquo;<br/><b>Negocio</b>",
        "style": style_layer,
        "x": 30, "y": 345, "w": 1380, "h": 890
    })

    # SubSistema Backend
    nodes.append({
        "id": "sub_backend",
        "value": "&laquo;SubSistema&raquo;<br/><b>Backend (FastAPI)</b>",
        "style": style_subsystem_backend,
        "x": 50, "y": 385, "w": 960, "h": 835
    })

    # SubSistema Seguridad (Módulo 10 core)
    nodes.append({
        "id": "sub_seguridad",
        "value": "&laquo;SubSistema&raquo;<br/><b>Seguridad</b>",
        "style": style_subsystem,
        "x": 75, "y": 425, "w": 420, "h": 95
    })
    nodes.append({
        "id": "mod_middleware",
        "value": "&laquo;modulo&raquo;<br/><b>middleware</b><br/><span style='font-size:9px;font-weight:normal;'>JWT Auth &amp; Permisos RBAC</span>",
        "style": style_mod_coral,
        "x": 95, "y": 455, "w": 370, "h": 52
    })

    # SubSistema Saas (Módulo 9)
    nodes.append({
        "id": "sub_saas",
        "value": "&laquo;SubSistema&raquo;<br/><b>Saas (Multi-tenant)</b>",
        "style": style_subsystem,
        "x": 535, "y": 425, "w": 450, "h": 95
    })
    nodes.append({
        "id": "mod_scopes",
        "value": "&laquo;modulo&raquo;<br/><b>Scopes</b><br/><span style='font-size:9px;font-weight:normal;'>Aislamiento Tenant &amp; Sucursales</span>",
        "style": style_mod_coral,
        "x": 555, "y": 455, "w": 400, "h": 52
    })

    edges.append({"id": "e_mid_sc", "source": "mod_middleware", "target": "mod_scopes", "value": "&laquo;use&raquo;", "style": style_edge_internal})

    # Los 8 Módulos de Dominio del Backend (2 columnas x 4 filas)
    dominios = [
        ("Autenticacion y Usuarios", 75, 535, 420, "m1"),
        ("Catalogo", 535, 535, 450, "m2"),
        ("Gestion de E-Commerce", 75, 650, 420, "m4"),
        ("Sucursales e Inventario", 535, 650, 450, "m3"),
        ("Reservas", 75, 765, 420, "m5"),
        ("Punto de Venta (POS)", 535, 765, 450, "m6"),
        ("Pedidos y Reportes", 75, 880, 420, "m7"),
        ("Administracion y Respaldos", 535, 880, 450, "m10")
    ]

    for title, sx, sy, sw, prefix in dominios:
        nodes.append({
            "id": f"sub_{prefix}",
            "value": f"&laquo;SubSistema&raquo;<br/><b>{title}</b>",
            "style": style_subsystem,
            "x": sx, "y": sy, "w": sw, "h": 100
        })
        w_mod = (sw - 60) // 2
        nodes.append({
            "id": f"mod_{prefix}_srv",
            "value": "&laquo;modulo&raquo;<br/><b>service</b>",
            "style": style_mod_coral,
            "x": sx + 15, "y": sy + 32, "w": w_mod, "h": 55
        })
        nodes.append({
            "id": f"mod_{prefix}_ctrl",
            "value": "&laquo;modulo&raquo;<br/><b>controller</b>",
            "style": style_mod_coral,
            "x": sx + 35 + w_mod, "y": sy + 32, "w": w_mod, "h": 55
        })
        # Flecha interna: controller usa service
        edges.append({
            "id": f"e_{prefix}_ctrl_srv",
            "source": f"mod_{prefix}_ctrl",
            "target": f"mod_{prefix}_srv",
            "value": "&laquo;use&raquo;",
            "style": style_edge_internal
        })

    # SubSistema 8: Inteligencia Artificial (Módulo 8 - Panel Derecho)
    nodes.append({
        "id": "sub_ia",
        "value": "&laquo;SubSistema&raquo;<br/><b>Inteligencia Artificial</b>",
        "style": style_subsystem_ia,
        "x": 1040, "y": 385, "w": 350, "h": 835
    })
    nodes.append({
        "id": "mod_ia_service",
        "value": "&laquo;modulo&raquo;<br/><b>Service (Orquestador IA)</b><br/><span style='font-size:9px;font-weight:normal;'>Aurora Advisor W13 / 26 Tools</span>",
        "style": style_mod_ia,
        "x": 1065, "y": 440, "w": 300, "h": 75
    })
    nodes.append({
        "id": "mod_ia_modelo",
        "value": "&laquo;modulo&raquo;<br/><b>Modelo de ia (LLMs)</b><br/><span style='font-size:9px;font-weight:normal;'>DeepSeek V3/R1, Gemini, OpenAI</span>",
        "style": style_mod_ia,
        "x": 1065, "y": 580, "w": 300, "h": 75
    })
    nodes.append({
        "id": "mod_ia_forecast",
        "value": "&laquo;modulo&raquo;<br/><b>Pronostico de Demanda</b><br/><span style='font-size:9px;font-weight:normal;'>demanda_forecast (Holt 95%)</span>",
        "style": style_mod_ia,
        "x": 1065, "y": 720, "w": 300, "h": 75
    })
    nodes.append({
        "id": "mod_ia_afinidad",
        "value": "&laquo;modulo&raquo;<br/><b>Mini-ML Afinidad</b><br/><span style='font-size:9px;font-weight:normal;'>ml_preferencias (Cosine Model)</span>",
        "style": style_mod_ia,
        "x": 1065, "y": 860, "w": 300, "h": 75
    })

    # IA dependencias internas
    edges.append({"id": "e_ia_srv_mod", "source": "mod_ia_service", "target": "mod_ia_modelo", "value": "&laquo;use&raquo;", "style": style_edge_internal})
    edges.append({"id": "e_ia_srv_fc", "source": "mod_ia_service", "target": "mod_ia_forecast", "value": "&laquo;use&raquo;", "style": style_edge_internal})
    edges.append({"id": "e_ia_srv_af", "source": "mod_ia_service", "target": "mod_ia_afinidad", "value": "&laquo;use&raquo;", "style": style_edge_internal})

    # =============================================================================================
    # 3. CAPA DATOS
    # =============================================================================================
    nodes.append({
        "id": "capa_datos",
        "value": "&laquo;Capa&raquo;<br/><b>Datos</b>",
        "style": style_layer,
        "x": 30, "y": 1255, "w": 1380, "h": 435
    })

    # SubSistema Persistencia de Datos
    nodes.append({
        "id": "sub_persistencia",
        "value": "&laquo;SubSistema&raquo;<br/><b>Persistencia de Datos</b>",
        "style": style_subsystem,
        "x": 50, "y": 1295, "w": 620, "h": 375
    })
    nodes.append({
        "id": "mod_repos",
        "value": "&laquo;modulo&raquo;<br/><b>repositories</b><br/><span style='font-size:9px;font-weight:normal;'>Capa de Repositorios SQL</span>",
        "style": style_mod_coral,
        "x": 75, "y": 1345, "w": 250, "h": 70
    })
    nodes.append({
        "id": "mod_entities",
        "value": "&laquo;modulo&raquo;<br/><b>entities</b><br/><span style='font-size:9px;font-weight:normal;'>Modelos de Dominio &amp; DTOs</span>",
        "style": style_mod_coral,
        "x": 385, "y": 1345, "w": 250, "h": 70
    })
    nodes.append({
        "id": "mod_almacen_local",
        "value": "&laquo;modulo&raquo;<br/><b>Almacenamiento Local Offline</b><br/><span style='font-size:9px;font-weight:normal;'>IndexedDB (Web PWA) &amp; SQLite (Flutter Movil)</span>",
        "style": style_mod_coral,
        "x": 75, "y": 1460, "w": 560, "h": 70
    })
    nodes.append({
        "id": "mod_pool_postgres",
        "value": "&laquo;modulo&raquo;<br/><b>Conector PostgreSQL (Pool)</b><br/><span style='font-size:9px;font-weight:normal;'>app.core.postgres / Zero RTT / ContextVar</span>",
        "style": style_mod_coral,
        "x": 75, "y": 1570, "w": 560, "h": 70
    })

    # Persistencia dependencias internas
    edges.append({"id": "e_rep_ent", "source": "mod_repos", "target": "mod_entities", "value": "&laquo;use&raquo;", "style": style_edge_internal})
    edges.append({"id": "e_rep_local", "source": "mod_repos", "target": "mod_almacen_local", "value": "&laquo;use&raquo;", "style": style_edge_internal})
    edges.append({"id": "e_loc_pool", "source": "mod_almacen_local", "target": "mod_pool_postgres", "value": "&laquo;use&raquo;", "style": style_edge_internal})

    # SubSistema Base de Datos (PostgreSQL)
    nodes.append({
        "id": "sub_database",
        "value": "&laquo;SubSistema&raquo;<br/><b>Base de datos (PostgreSQL 15+)</b>",
        "style": style_subsystem_db,
        "x": 710, "y": 1295, "w": 680, "h": 375
    })
    nodes.append({
        "id": "mod_db_usuarios",
        "value": "&laquo;modulo&raquo;<br/><b>usuarios</b><br/><span style='font-size:9px;font-weight:normal;'>t_usuario, t_rol, t_permiso</span>",
        "style": style_mod_db,
        "x": 735, "y": 1345, "w": 270, "h": 70
    })
    nodes.append({
        "id": "mod_db_tienda",
        "value": "&laquo;modulo&raquo;<br/><b>tienda.sql (comercio)</b><br/><span style='font-size:9px;font-weight:normal;'>empresa, t_producto, t_venta, etc.</span>",
        "style": style_mod_db,
        "x": 1045, "y": 1345, "w": 310, "h": 70
    })
    nodes.append({
        "id": "mod_db_vistas",
        "value": "&laquo;modulo&raquo;<br/><b>Vistas Analiticas SQL</b><br/><span style='font-size:9px;font-weight:normal;'>vw_ventas_reporte, vw_inventario_reporte, etc. (14 vistas)</span>",
        "style": style_mod_db,
        "x": 735, "y": 1460, "w": 620, "h": 70
    })
    nodes.append({
        "id": "mod_db_bitacora",
        "value": "&laquo;modulo&raquo;<br/><b>Auditoria &amp; Bitacora Central</b><br/><span style='font-size:9px;font-weight:normal;'>t_bitacora inmutable &amp; t_sync_operacion</span>",
        "style": style_mod_db,
        "x": 735, "y": 1570, "w": 620, "h": 70
    })

    # Base de datos dependencias internas
    edges.append({"id": "e_db_usr_tienda", "source": "mod_db_usuarios", "target": "mod_db_tienda", "value": "&laquo;use&raquo;", "style": style_edge_internal})

    # =============================================================================================
    # 4. DEPENDENCIAS ENTRE CAPAS (CROSS-LAYER CON RUTAS ORTOGONALES LIMPIAS)
    # =============================================================================================
    # Presentación Web -> Backend middleware (Línea directa vertical limpia)
    edges.append({
        "id": "e_cross_web_mid",
        "source": "mod_web_services",
        "target": "mod_middleware",
        "value": "&laquo;use&raquo;",
        "style": style_edge_cross
    })

    # Presentación Móvil -> Backend middleware (Línea diagonal/ortogonal por el canal central)
    edges.append({
        "id": "e_cross_movil_mid",
        "source": "mod_movil_services",
        "target": "mod_middleware",
        "value": "&laquo;use&raquo;",
        "style": style_edge_cross
    })

    # middleware -> controllers de dominio (descenso vertical hacia el primer bloque)
    edges.append({
        "id": "e_cross_mid_ctrl",
        "source": "mod_middleware",
        "target": "mod_m1_ctrl",
        "value": "&laquo;use&raquo;",
        "style": style_edge_cross
    })

    # Backend -> Inteligencia Artificial (conexión limpia por el pasillo lateral derecho)
    edges.append({
        "id": "e_cross_back_ia",
        "source": "mod_m2_srv",
        "target": "mod_ia_service",
        "value": "&laquo;use&raquo;",
        "style": style_edge_cross
    })

    # Backend -> Persistencia de Datos (repositories) (descenso vertical limpio desde la base del backend)
    edges.append({
        "id": "e_cross_back_repos",
        "source": "mod_m7_srv",
        "target": "mod_repos",
        "value": "&laquo;use&raquo;",
        "style": style_edge_cross
    })

    # Persistencia (entities) -> Base de datos (usuarios / tienda.sql) (conexión horizontal limpia)
    edges.append({
        "id": "e_cross_pers_db",
        "source": "mod_entities",
        "target": "mod_db_usuarios",
        "value": "&laquo;use&raquo;",
        "style": style_edge_cross
    })

    # Construir documento XML Draw.io
    mxfile = ET.Element("mxfile", {
        "host": "Electron",
        "modified": "2026-11-08T21:00:00.000Z",
        "agent": "Antigravity Architect",
        "version": "21.6.8",
        "type": "device"
    })
    diagram = ET.SubElement(mxfile, "diagram", {
        "id": "diag_modulos_aurorastore_v2",
        "name": "pkg Diagrama de modulos de sistema"
    })
    graph_model = ET.SubElement(diagram, "mxGraphModel", {
        "dx": "1440",
        "dy": "1200",
        "grid": "1",
        "gridSize": "10",
        "guides": "1",
        "tooltips": "1",
        "connect": "1",
        "arrows": "1",
        "fold": "1",
        "page": "1",
        "pageScale": "1",
        "pageWidth": "1460",
        "pageHeight": "1740",
        "math": "0",
        "shadow": "0"
    })
    root = ET.SubElement(graph_model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    for node in nodes:
        cell = ET.SubElement(root, "mxCell", {
            "id": node["id"],
            "value": node["value"],
            "style": node["style"],
            "vertex": "1",
            "parent": "1"
        })
        ET.SubElement(cell, "mxGeometry", {
            "x": str(node["x"]),
            "y": str(node["y"]),
            "width": str(node["w"]),
            "height": str(node["h"]),
            "as": "geometry"
        })

    for edge in edges:
        cell = ET.SubElement(root, "mxCell", {
            "id": edge["id"],
            "value": edge["value"],
            "style": edge["style"],
            "edge": "1",
            "parent": "1",
            "source": edge["source"],
            "target": edge["target"]
        })
        geo = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})

    xml_str = ET.tostring(mxfile, encoding="utf-8")
    dom = xml.dom.minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")

def main():
    arch_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.abspath(os.path.join(arch_dir, "..", ".."))

    drawio_content = build_drawio_xml()

    out_arch = os.path.join(arch_dir, "diagrama_modulos_sistema.drawio")
    with open(out_arch, "w", encoding="utf-8") as f:
        f.write(drawio_content)
    print(f"[OK] Archivo Draw.io generado en docs/architecture: {out_arch} ({len(drawio_content)} bytes)")

    out_root = os.path.join(workspace_dir, "diagrama_modulos_sistema.drawio")
    with open(out_root, "w", encoding="utf-8") as f:
        f.write(drawio_content)
    print(f"[OK] Archivo Draw.io copiado en la raíz: {out_root}")

    out_xml = os.path.join(arch_dir, "diagrama_modulos_sistema.xml")
    with open(out_xml, "w", encoding="utf-8") as f:
        f.write(drawio_content)
    print(f"[OK] Archivo XML generado en docs/architecture: {out_xml}")

if __name__ == "__main__":
    main()
