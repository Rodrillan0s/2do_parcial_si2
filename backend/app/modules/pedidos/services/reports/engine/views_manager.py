from app.core.postgres import PostgreSQL
from app.core.config import Config

_VISTAS_INICIALIZADAS = False

def _crear_vista(db, schema: str, name: str, sql: str):
    try:
        db.execute_query(sql, commit=True)
    except Exception:
        try:
            db.execute_query(f"DROP VIEW IF EXISTS {schema}.{name} CASCADE;", commit=True)
        except Exception:
            pass
        db.execute_query(sql, commit=True)

def asegurar_vistas_sql(force: bool = False):
    """
    Crea o actualiza las vistas SQL en PostgreSQL que sirven como
    fuentes de datos limpias y reutilizables para el Motor de Reportes.
    """
    global _VISTAS_INICIALIZADAS
    if _VISTAS_INICIALIZADAS and not force:
        return
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'

        # 1. Vista de Ventas
        v_ventas = f"""
        CREATE OR REPLACE VIEW {schema}.vw_ventas_reporte AS
        SELECT 
            v.id_venta,
            v.numero_venta,
            v.id_empresa,
            v.id_sucursal,
            s.nombre AS sucursal,
            COALESCE(c.nombre, 'No asignada') AS ciudad,
            v.id_cliente,
            COALESCE(v.razon_social, u_cliente.nombre || ' ' || COALESCE(u_cliente.apellido, ''), u_cajero.nombre || ' (Mostrador)', 'Cliente Mostrador') AS cliente,
            COALESCE(v.nit_ci, '0') AS nit_ci,
            v.fecha_venta,
            DATE(v.fecha_venta) AS fecha,
            COALESCE(v.subtotal, 0) AS subtotal,
            COALESCE(v.descuento, 0) AS descuento,
            COALESCE(v.total, 0) AS total,
            COALESCE(v.estado, 'COMPLETADA') AS estado,
            v.tipo_venta,
            p.id_pago,
            COALESCE(mp.nombre, 'Efectivo / Mostrador') AS metodo_pago,
            p.id_metodo_pago
        FROM {schema}.t_venta v
        JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
        LEFT JOIN {schema}.t_ciudad c ON c.id_ciudad = s.id_ciudad
        LEFT JOIN {schema}.t_cliente cl ON cl.id_cliente = v.id_cliente
        LEFT JOIN {schema}.t_usuario u_cajero ON u_cajero.id_usuario = v.id_usuario
        LEFT JOIN {schema}.t_usuario u_cliente ON u_cliente.id_usuario = cl.id_usuario
        LEFT JOIN {schema}.t_pago p ON p.id_venta = v.id_venta
        LEFT JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p.id_metodo_pago;
        """
        _crear_vista(db, schema, 'vw_ventas_reporte', v_ventas)

        # 2. Vista de Inventario
        v_inv = f"""
        CREATE OR REPLACE VIEW {schema}.vw_inventario_reporte AS
        SELECT 
            i.id_inventario,
            s.id_empresa,
            i.id_sucursal,
            s.nombre AS sucursal,
            p.id_producto,
            p.nombre AS producto,
            p.codigo_producto,
            p.id_categoria,
            COALESCE(cat.nombre, 'Sin Categoría') AS categoria,
            ptc.id_variante,
            ptc.sku,
            COALESCE(t.nombre, '') AS talla,
            COALESCE(col.nombre, '') AS color,
            COALESCE(i.stock_actual, 0) AS stock_actual,
            COALESCE(i.stock_reservado, 0) AS stock_reservado,
            COALESCE(i.stock_disponible, 0) AS stock_disponible,
            COALESCE(i.stock_minimo, 0) AS stock_minimo,
            CASE 
                WHEN i.stock_disponible = 0 THEN 'AGOTADO'
                WHEN i.stock_disponible <= i.stock_minimo THEN 'BAJO_STOCK'
                ELSE 'OPTIMO'
            END AS estado_stock
        FROM {schema}.t_inventario i
        JOIN {schema}.t_sucursal s ON s.id_sucursal = i.id_sucursal
        JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = i.id_variante
        JOIN {schema}.t_producto p ON p.id_producto = ptc.id_producto
        LEFT JOIN {schema}.t_categoria cat ON cat.id_categoria = p.id_categoria
        LEFT JOIN {schema}.t_talla t ON t.id_talla = ptc.id_talla
        LEFT JOIN {schema}.t_color col ON col.id_color = ptc.id_color;
        """
        _crear_vista(db, schema, 'vw_inventario_reporte', v_inv)

        # 3. Vista de Productos Vendidos
        v_prod = f"""
        CREATE OR REPLACE VIEW {schema}.vw_productos_reporte AS
        SELECT 
            dv.id_detalle_venta,
            v.id_empresa,
            v.id_sucursal,
            s.nombre AS sucursal,
            v.id_venta,
            v.numero_venta,
            v.fecha_venta,
            DATE(v.fecha_venta) AS fecha,
            p.id_producto,
            p.nombre AS producto,
            p.codigo_producto,
            p.id_categoria,
            COALESCE(cat.nombre, 'Sin Categoría') AS categoria,
            ptc.id_variante,
            ptc.sku,
            COALESCE(t.nombre, '') AS talla,
            COALESCE(col.nombre, '') AS color,
            COALESCE(dv.cantidad, 0) AS cantidad,
            COALESCE(dv.precio_unitario, 0) AS precio_unitario,
            COALESCE(dv.descuento, 0) AS descuento,
            COALESCE(dv.subtotal, 0) AS subtotal_ingresos
        FROM {schema}.t_detalle_venta dv
        JOIN {schema}.t_venta v ON v.id_venta = dv.id_venta
        JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
        JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = dv.id_variante
        JOIN {schema}.t_producto p ON p.id_producto = ptc.id_producto
        LEFT JOIN {schema}.t_categoria cat ON cat.id_categoria = p.id_categoria
        LEFT JOIN {schema}.t_talla t ON t.id_talla = ptc.id_talla
        LEFT JOIN {schema}.t_color col ON col.id_color = ptc.id_color;
        """
        _crear_vista(db, schema, 'vw_productos_reporte', v_prod)

        # 4. Vista de Pagos
        v_pagos = f"""
        CREATE OR REPLACE VIEW {schema}.vw_pagos_reporte AS
        SELECT 
            p.id_pago,
            v.id_empresa,
            v.id_sucursal,
            s.nombre AS sucursal,
            p.id_venta,
            v.numero_venta,
            p.id_metodo_pago,
            COALESCE(mp.nombre, 'Efectivo / Mostrador') AS metodo_pago,
            p.codigo_transaccion,
            COALESCE(p.monto, 0) AS monto,
            p.fecha_pago,
            DATE(p.fecha_pago) AS fecha,
            COALESCE(p.estado, 'COMPLETADO') AS estado,
            p.referencia_externa
        FROM {schema}.t_pago p
        JOIN {schema}.t_venta v ON v.id_venta = p.id_venta
        JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
        LEFT JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p.id_metodo_pago;
        """
        _crear_vista(db, schema, 'vw_pagos_reporte', v_pagos)

        # 5. Vista de Caja
        v_caja = f"""
        CREATE OR REPLACE VIEW {schema}.vw_caja_reporte AS
        SELECT 
            cs.id_sesion_caja,
            cs.id_caja,
            c.nombre AS caja_nombre,
            c.codigo_caja,
            cs.id_empresa,
            cs.id_sucursal,
            s.nombre AS sucursal,
            cs.id_usuario,
            COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), 'Cajero') AS cajero_nombre,
            cs.fecha_apertura,
            DATE(cs.fecha_apertura) AS fecha,
            cs.fecha_cierre,
            COALESCE(cs.monto_inicial, 0) AS monto_inicial,
            COALESCE(cs.efectivo_esperado, 0) AS efectivo_esperado,
            COALESCE(cs.efectivo_contado, 0) AS efectivo_contado,
            COALESCE(cs.diferencia, 0) AS diferencia,
            COALESCE(cs.estado, 'CERRADA') AS estado
        FROM {schema}.t_caja_sesion cs
        JOIN {schema}.t_caja c ON c.id_caja = cs.id_caja
        JOIN {schema}.t_sucursal s ON s.id_sucursal = cs.id_sucursal
        LEFT JOIN {schema}.t_usuario u ON u.id_usuario = cs.id_usuario;
        """
        _crear_vista(db, schema, 'vw_caja_reporte', v_caja)

        # 6. Vista de Ventas y Pedidos Pendientes de Pago (Prendas por Pagar)
        v_pendientes = f"""
        CREATE OR REPLACE VIEW {schema}.vw_ventas_pendientes_reporte AS
        SELECT 
            'VENTA-' || v.id_venta AS id_registro,
            v.id_venta,
            v.numero_venta AS numero_documento,
            v.id_empresa,
            v.id_sucursal,
            s.nombre AS sucursal,
            COALESCE(c.nombre, 'No asignada') AS ciudad,
            v.id_cliente,
            COALESCE(v.razon_social, u_cliente.nombre || ' ' || COALESCE(u_cliente.apellido, ''), u_cajero.nombre || ' (Mostrador)', 'Cliente Mostrador') AS cliente,
            COALESCE(u_cliente.telefono, u_cajero.telefono, 'S/N') AS telefono,
            v.fecha_venta AS fecha_registro,
            DATE(v.fecha_venta) AS fecha,
            COALESCE(v.total, 0) AS total,
            'PRESENCIAL / POS' AS canal,
            COALESCE(v.estado, 'PENDIENTE_PAGO') AS estado,
            COALESCE(v.estado, 'PENDIENTE_PAGO') AS estado_pago,
            (CURRENT_DATE - DATE(v.fecha_venta)) AS dias_pendiente
        FROM {schema}.t_venta v
        JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
        LEFT JOIN {schema}.t_ciudad c ON c.id_ciudad = s.id_ciudad
        LEFT JOIN {schema}.t_cliente cl ON cl.id_cliente = v.id_cliente
        LEFT JOIN {schema}.t_usuario u_cajero ON u_cajero.id_usuario = v.id_usuario
        LEFT JOIN {schema}.t_usuario u_cliente ON u_cliente.id_usuario = cl.id_usuario
        WHERE v.estado IN ('PENDIENTE_PAGO', 'PENDIENTE')

        UNION ALL

        SELECT 
            'PEDIDO-' || p.id_pedido AS id_registro,
            p.id_pedido AS id_venta,
            p.codigo_pedido AS numero_documento,
            p.id_empresa,
            p.id_sucursal,
            s.nombre AS sucursal,
            COALESCE(p.ciudad_entrega, 'Santa Cruz') AS ciudad,
            p.id_cliente,
            COALESCE(p.nombre_contacto, u.nombre || ' ' || COALESCE(u.apellido, ''), 'Cliente Web') AS cliente,
            COALESCE(p.telefono_contacto, u.telefono, 'S/N') AS telefono,
            p.fecha_pedido AS fecha_registro,
            DATE(p.fecha_pedido) AS fecha,
            COALESCE(p.total, 0) AS total,
            'TIENDA ONLINE' AS canal,
            COALESCE(p.estado, 'PENDIENTE') AS estado,
            COALESCE(p.estado_pago, p.estado, 'PENDIENTE') AS estado_pago,
            (CURRENT_DATE - DATE(p.fecha_pedido)) AS dias_pendiente
        FROM {schema}.t_pedido p
        JOIN {schema}.t_sucursal s ON s.id_sucursal = p.id_sucursal
        LEFT JOIN {schema}.t_cliente cl ON cl.id_cliente = p.id_cliente
        LEFT JOIN {schema}.t_usuario u ON u.id_usuario = cl.id_usuario
        WHERE (p.estado IN ('PENDIENTE', 'PENDIENTE_PAGO') OR p.estado_pago = 'PENDIENTE')
          AND p.id_venta IS NULL;
        """
        _crear_vista(db, schema, 'vw_ventas_pendientes_reporte', v_pendientes)

        # 7. Vista de Reservas de Prendas (Apartados por Recoger/Pagar)
        v_reservas = f"""
        CREATE OR REPLACE VIEW {schema}.vw_reservas_reporte AS
        SELECT 
            r.id_reserva,
            r.codigo_reserva,
            s.id_empresa,
            r.id_sucursal,
            s.nombre AS sucursal,
            COALESCE(c.nombre, 'No asignada') AS ciudad,
            r.id_cliente,
            COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), 'Cliente Aurora') AS cliente,
            COALESCE(u.telefono, 'S/N') AS telefono,
            COALESCE(u.correo, '') AS correo,
            r.fecha_reserva,
            DATE(r.fecha_reserva) AS fecha,
            r.fecha_hora_visita,
            DATE(r.fecha_hora_visita) AS fecha_vencimiento,
            r.estado,
            p.nombre AS prenda,
            ptc.sku,
            COALESCE(t.nombre, '') AS talla,
            COALESCE(col.nombre, '') AS color,
            COALESCE(dr.cantidad, 1) AS cantidad,
            COALESCE(p.precio, 0) AS precio_unitario,
            COALESCE(p.precio * COALESCE(dr.cantidad, 1), 0) AS subtotal_estimado,
            CASE 
                WHEN r.estado = 'PENDIENTE' AND r.fecha_hora_visita < CURRENT_TIMESTAMP THEN 'VENCIDA'
                WHEN r.estado = 'PENDIENTE' AND r.fecha_hora_visita >= CURRENT_TIMESTAMP THEN 'VIGENTE'
                ELSE r.estado
            END AS vigencia
        FROM {schema}.t_reserva r
        JOIN {schema}.t_sucursal s ON s.id_sucursal = r.id_sucursal
        LEFT JOIN {schema}.t_ciudad c ON c.id_ciudad = s.id_ciudad
        LEFT JOIN {schema}.t_cliente cl ON cl.id_cliente = r.id_cliente
        LEFT JOIN {schema}.t_usuario u ON u.id_usuario = cl.id_usuario
        LEFT JOIN {schema}.t_detalle_reserva dr ON dr.id_reserva = r.id_reserva
        LEFT JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = dr.id_variante
        LEFT JOIN {schema}.t_producto p ON p.id_producto = ptc.id_producto
        LEFT JOIN {schema}.t_talla t ON t.id_talla = ptc.id_talla
        LEFT JOIN {schema}.t_color col ON col.id_color = ptc.id_color;
        """
        _crear_vista(db, schema, 'vw_reservas_reporte', v_reservas)

        # 8. Vista de Auditoría y Transacciones POS (Punto de Venta)
        v_pos = f"""
        CREATE OR REPLACE VIEW {schema}.vw_pos_reporte AS
        SELECT 
            v.id_venta,
            v.numero_venta,
            v.id_empresa,
            v.id_sucursal,
            s.nombre AS sucursal,
            COALESCE(ci.nombre, 'Santa Cruz') AS ciudad,
            v.fecha_venta,
            DATE(v.fecha_venta) AS fecha,
            TO_CHAR(v.fecha_venta, 'HH24:MI:SS') AS hora,
            v.id_sesion_caja,
            COALESCE(c.nombre, 'Caja Mostrador') AS caja,
            COALESCE(c.codigo_caja, 'POS-01') AS codigo_caja,
            v.id_usuario,
            COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), 'Cajero Turno') AS cajero,
            COALESCE(v.razon_social, 'Cliente Mostrador') AS cliente,
            COALESCE(v.nit_ci, '0') AS nit_ci,
            COALESCE(v.subtotal, 0) AS subtotal,
            COALESCE(v.descuento, 0) AS descuento,
            COALESCE(v.total, 0) AS total,
            COALESCE(v.estado, 'PAGADO') AS estado,
            COALESCE(v.estado, 'PAGADO') AS estado_venta,
            COALESCE(cs.estado, 'CERRADA') AS estado_sesion,
            p.id_pago,
            COALESCE(mp.nombre, 'Efectivo / Mostrador') AS metodo_pago,
            COALESCE(p.estado, 'COMPLETADO') AS estado_pago,
            CASE
                WHEN v.estado = 'PENDIENTE_PAGO' THEN '⚠️ SIN COBRO REGISTRADO'
                WHEN p.id_pago IS NULL THEN '⚠️ VENTA SIN PAGO ASOCIADO'
                WHEN v.id_sesion_caja IS NULL THEN '⚠️ SIN SESIÓN DE CAJA'
                ELSE '✓ COBRADO Y CUADRADO'
            END AS alerta_auditoria
        FROM {schema}.t_venta v
        JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
        LEFT JOIN {schema}.t_ciudad ci ON ci.id_ciudad = s.id_ciudad
        LEFT JOIN {schema}.t_caja_sesion cs ON cs.id_sesion_caja = v.id_sesion_caja
        LEFT JOIN {schema}.t_caja c ON c.id_caja = cs.id_caja
        LEFT JOIN {schema}.t_usuario u ON u.id_usuario = v.id_usuario
        LEFT JOIN {schema}.t_pago p ON p.id_venta = v.id_venta
        LEFT JOIN {schema}.t_metodo_pago mp ON mp.id_metodo_pago = p.id_metodo_pago
        WHERE v.tipo_venta = 'PRESENCIAL' OR v.id_sesion_caja IS NOT NULL;
        """
        _crear_vista(db, schema, 'vw_pos_reporte', v_pos)

        # 9. Vista de Rendimiento y Comparativa de Sucursales
        v_sucursales = f"""
        CREATE OR REPLACE VIEW {schema}.vw_sucursales_reporte AS
        SELECT 
            s.id_sucursal,
            s.id_empresa,
            s.nombre AS sucursal,
            COALESCE(ci.nombre, 'No asignada') AS ciudad,
            COALESCE(s.telefono, 'S/N') AS telefono,
            s.direccion,
            COALESCE(s.activo, TRUE) AS activo,
            COUNT(v.id_venta) AS cantidad_ventas,
            COALESCE(SUM(v.total), 0) AS total_ingresos,
            COALESCE(SUM(v.subtotal), 0) AS total_subtotal,
            COALESCE(AVG(v.total), 0) AS ticket_promedio
        FROM {schema}.t_sucursal s
        LEFT JOIN {schema}.t_ciudad ci ON ci.id_ciudad = s.id_ciudad
        LEFT JOIN {schema}.t_venta v ON v.id_sucursal = s.id_sucursal
        GROUP BY s.id_sucursal, s.id_empresa, s.nombre, ci.nombre, s.telefono, s.direccion, s.activo;
        """
        _crear_vista(db, schema, 'vw_sucursales_reporte', v_sucursales)

        # 10. Vista de Devoluciones y Reclamos
        v_devoluciones = f"""
        CREATE OR REPLACE VIEW {schema}.vw_devoluciones_reporte AS
        SELECT 
            d.id_devolucion,
            d.codigo_devolucion,
            d.id_empresa,
            d.id_sucursal,
            s.nombre AS sucursal,
            COALESCE(ci.nombre, 'Santa Cruz') AS ciudad,
            d.id_venta,
            v.numero_venta,
            d.id_usuario,
            COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), 'Cliente Aurora') AS cliente,
            COALESCE(u.telefono, 'S/N') AS telefono,
            d.fecha_devolucion AS fecha_solicitud,
            DATE(d.fecha_devolucion) AS fecha,
            COALESCE(d.monto_reembolso, 0) AS monto_total_devolucion,
            d.estado,
            COALESCE(d.motivo, 'OTRO') AS motivo_general,
            COALESCE((SELECT SUM(dd.cantidad) FROM {schema}.t_detalle_devolucion dd WHERE dd.id_devolucion = d.id_devolucion), 1) AS total_articulos,
            COALESCE(d.estado, 'NO_REQUERIDO') AS reembolso_estado,
            COALESCE(d.metodo_reembolso, 'EFECTIVO') AS reembolso_metodo
        FROM {schema}.t_devolucion d
        JOIN {schema}.t_sucursal s ON s.id_sucursal = d.id_sucursal
        LEFT JOIN {schema}.t_ciudad ci ON ci.id_ciudad = s.id_ciudad
        LEFT JOIN {schema}.t_venta v ON v.id_venta = d.id_venta
        LEFT JOIN {schema}.t_usuario u ON u.id_usuario = d.id_usuario;
        """
        _crear_vista(db, schema, 'vw_devoluciones_reporte', v_devoluciones)

        # 11. Vista de Rentabilidad y Margen
        v_rentabilidad = f"""
        CREATE OR REPLACE VIEW {schema}.vw_rentabilidad_reporte AS
        SELECT 
            p.id_producto,
            p.id_empresa,
            p.nombre AS producto,
            COALESCE(cat.nombre, 'Sin Categoría') AS categoria,
            s.id_sucursal,
            s.nombre AS sucursal,
            DATE(v.fecha_venta) AS fecha,
            COUNT(dv.id_detalle_venta) AS transacciones,
            SUM(dv.cantidad) AS unidades_vendidas,
            SUM(dv.subtotal) AS ingresos_totales,
            ROUND(SUM(dv.cantidad * COALESCE(pp.costo_base, 0)), 2) AS costo_estimado,
            ROUND(SUM(dv.subtotal - (dv.cantidad * COALESCE(pp.costo_base, 0))), 2) AS margen_bruto_bs,
            ROUND(
                CASE 
                    WHEN SUM(dv.subtotal) > 0 THEN 
                        ((SUM(dv.subtotal - (dv.cantidad * COALESCE(pp.costo_base, 0)))) / SUM(dv.subtotal)) * 100 
                    ELSE 0 
                END, 
                2
            ) AS margen_porcentaje
        FROM {schema}.t_detalle_venta dv
        JOIN {schema}.t_venta v ON v.id_venta = dv.id_venta
        JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
        JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = dv.id_variante
        JOIN {schema}.t_producto p ON p.id_producto = ptc.id_producto
        LEFT JOIN {schema}.t_categoria cat ON cat.id_categoria = p.id_categoria
        LEFT JOIN (
            SELECT id_producto, AVG(costo_compra) AS costo_base 
            FROM {schema}.t_producto_proveedor 
            GROUP BY id_producto
        ) pp ON pp.id_producto = p.id_producto
        GROUP BY p.id_producto, p.id_empresa, p.nombre, cat.nombre, s.id_sucursal, s.nombre, DATE(v.fecha_venta);
        """
        _crear_vista(db, schema, 'vw_rentabilidad_reporte', v_rentabilidad)

        # 12. Vista de Rendimiento de Cajeros y Personal
        v_personal = f"""
        CREATE OR REPLACE VIEW {schema}.vw_rendimiento_personal_reporte AS
        SELECT 
            u.id_usuario,
            v.id_empresa,
            v.id_sucursal,
            s.nombre AS sucursal,
            u.nombre || ' ' || COALESCE(u.apellido, '') AS empleado_nombre,
            COALESCE(r.nombre, 'PERSONAL') AS rol,
            DATE(v.fecha_venta) AS fecha,
            COUNT(v.id_venta) AS total_ventas,
            SUM(v.total) AS total_recaudado,
            ROUND(AVG(v.total), 2) AS ticket_promedio
        FROM {schema}.t_venta v
        JOIN {schema}.t_sucursal s ON s.id_sucursal = v.id_sucursal
        JOIN {schema}.t_usuario u ON u.id_usuario = v.id_usuario
        LEFT JOIN {schema}.t_rol r ON r.id_rol = u.id_rol
        GROUP BY u.id_usuario, v.id_empresa, v.id_sucursal, s.nombre, u.nombre, u.apellido, r.nombre, DATE(v.fecha_venta);
        """
        _crear_vista(db, schema, 'vw_rendimiento_personal_reporte', v_personal)

        # 13. Vista de Stock Inmovilizado / Baja Rotación
        v_inmovilizado = f"""
        CREATE OR REPLACE VIEW {schema}.vw_stock_inmovilizado_reporte AS
        SELECT 
            i.id_inventario,
            s.id_empresa,
            i.id_sucursal,
            s.nombre AS sucursal,
            p.id_producto,
            p.nombre AS producto,
            p.codigo_producto,
            COALESCE(cat.nombre, 'Sin Categoría') AS categoria,
            COALESCE(t.nombre, '') AS talla,
            COALESCE(col.nombre, '') AS color,
            i.stock_disponible,
            p.precio,
            ROUND(i.stock_disponible * p.precio, 2) AS capital_estancado_bs,
            COALESCE(MAX(DATE(v.fecha_venta)), CURRENT_DATE - 45) AS fecha,
            COALESCE(MAX(DATE(v.fecha_venta)), CURRENT_DATE - 45) AS ultima_venta
        FROM {schema}.t_inventario i
        JOIN {schema}.t_sucursal s ON s.id_sucursal = i.id_sucursal
        JOIN {schema}.t_producto_talla_color ptc ON ptc.id_variante = i.id_variante
        JOIN {schema}.t_producto p ON p.id_producto = ptc.id_producto
        LEFT JOIN {schema}.t_categoria cat ON cat.id_categoria = p.id_categoria
        LEFT JOIN {schema}.t_talla t ON t.id_talla = ptc.id_talla
        LEFT JOIN {schema}.t_color col ON col.id_color = ptc.id_color
        LEFT JOIN {schema}.t_detalle_venta dv ON dv.id_variante = i.id_variante
        LEFT JOIN {schema}.t_venta v ON v.id_venta = dv.id_venta
        WHERE i.stock_disponible > 0
        GROUP BY i.id_inventario, s.id_empresa, i.id_sucursal, s.nombre, p.id_producto, p.nombre, p.codigo_producto, cat.nombre, t.nombre, col.nombre, i.stock_disponible, p.precio;
        """
        _crear_vista(db, schema, 'vw_stock_inmovilizado_reporte', v_inmovilizado)

        # 14. Vista de Valoraciones y Satisfacción del Cliente
        v_valoraciones = f"""
        CREATE OR REPLACE VIEW {schema}.vw_valoraciones_reporte AS
        SELECT 
            val.id_valoracion,
            val.id_empresa,
            val.id_sucursal,
            COALESCE(s.nombre, 'Sin sucursal asignada') AS sucursal,
            val.id_producto,
            COALESCE(p.nombre, 'Servicio General de Tienda') AS producto,
            p.id_categoria,
            COALESCE(cat.nombre, 'Servicio / General') AS categoria,
            val.id_cliente,
            COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), 'Cliente') AS cliente,
            DATE(val.fecha_creacion) AS fecha,
            val.fecha_creacion,
            val.puntuacion,
            CASE 
                WHEN val.id_producto IS NOT NULL THEN 'PRENDA'
                WHEN val.id_reserva IS NOT NULL THEN 'RESERVA_PROBADOR'
                ELSE 'SERVICIO_COMPRA'
            END AS tipo_valoracion,
            val.id_pedido,
            COALESCE(ped.codigo_pedido, v.numero_venta, 'Sin código') AS codigo_referencia,
            val.id_venta,
            val.id_reserva,
            COALESCE(val.motivo_negativo, 'Ninguno') AS motivo_negativo,
            COALESCE(val.comentario, '') AS comentario,
            val.requiere_revision,
            val.atendido,
            CASE 
                WHEN val.puntuacion >= 4 THEN 'POSITIVA'
                WHEN val.puntuacion = 3 THEN 'NEUTRA'
                ELSE 'CRITICA'
            END AS estado_satisfaccion
        FROM {schema}.t_valoracion val
        LEFT JOIN {schema}.t_sucursal s ON s.id_sucursal = val.id_sucursal
        LEFT JOIN {schema}.t_producto p ON p.id_producto = val.id_producto
        LEFT JOIN {schema}.t_categoria cat ON cat.id_categoria = p.id_categoria
        LEFT JOIN {schema}.t_cliente cli ON cli.id_cliente = val.id_cliente
        LEFT JOIN {schema}.t_usuario u ON u.id_usuario = cli.id_usuario
        LEFT JOIN {schema}.t_pedido ped ON ped.id_pedido = val.id_pedido
        LEFT JOIN {schema}.t_venta v ON v.id_venta = val.id_venta;
        """
        _crear_vista(db, schema, 'vw_valoraciones_reporte', v_valoraciones)

        _VISTAS_INICIALIZADAS = True
        return True
    finally:
        db.close_connection()

