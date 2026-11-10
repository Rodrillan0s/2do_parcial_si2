"""
Script de Población de Datos Operacionales para ML, Reportes y Dashboards
AuroraStore Multi-Tenant SaaS:
1. Sesiones de Caja (t_caja_sesion) para todas las sucursales de Tenants 1, 2 y 3.
2. Ventas presenciales POS y pedidos ecommerce (t_venta, t_detalle_venta, t_pago, t_pedido, t_detalle_pedido).
3. Reservas de probador (t_reserva, t_detalle_reserva) en estados COMPLETADA, CONFIRMADA y CANCELADA.
4. Devoluciones de prendas (t_devolucion, t_detalle_devolucion) con resoluciones CAMBIO_PRENDA y REEMBOLSO_DINERO (Ley 453).
5. Valoraciones y calificaciones de satisfacción (t_valoracion) con retroalimentación cualitativa y cuantitativa.
6. Ejecución del motor MiniML de preferencias y recomendaciones vectoriales (t_preferencia_cliente, t_recomendacion).
"""

import json
import logging
import random
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from app.core.postgres import PostgreSQL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("poblador_operaciones")

SCHEMA = "comercio"


COMENTARIOS_VALORACIONES = [
    (5, "La calidad de la tela es excepcional, el calce es perfecto y llegó en 24 horas a Santa Cruz. Totalmente recomendada."),
    (5, "Hermosa confección, el tejido de alpaca abriga bastante y los acabados son de primera línea. Muy elegante."),
    (5, "Excelente experiencia de compra. La atención en probadores fue puntual y el vestido luce idéntico a las fotos."),
    (4, "Muy linda prenda y buen corte. El color es un tono más oscuro que en la web pero luce sofisticado."),
    (5, "El traje sastre tiene una caída impecable. Lo usé para un evento corporativo en La Paz y recibí muchos cumplidos."),
    (5, "Algodón pima suave y fresco, ideal para el clima de Santa Cruz. Se nota la dedicación en los detalles."),
    (4, "Buena relación calidad-precio. La talla M me quedó justa de hombros, sugiero consultar la guía de tallas."),
    (5, "El corte de este pantalón estiliza muchísimo. La tela no se arruga y es muy cómoda para la oficina."),
    (3, "La prenda es de buena calidad pero demoró dos días más de lo previsto el envío a Cochabamba."),
    (4, "Me encantó el diseño urbano. Muy cómodo para el día a día y los bolsillos son bastante funcionales."),
    (5, "Súper abrigado y liviano a la vez. El acabado en lana merino justifica totalmente el precio."),
    (5, "Compré el blazer para un grado académico y la confección fue un 10 de 10. Volveré a comprar."),
    (2, "El talle viene algo reducido respecto a la tabla estándar, tuve que solicitar cambio de talla en sucursal."),
    (5, "El vestido sirena es un sueño, la tela satinada tiene mucho peso y elegancia. 100% satisfecha.")
]


def poblar_operaciones():
    db = PostgreSQL()
    db.create_connection()
    try:
        logger.info("=== 1. Creando Cajas y Sesiones de Caja para Tenants 1, 2 y 3 ===")
        # Asegurar cajas activas en sucursales
        sucursales = db.execute_query(f"""
            SELECT s.id_sucursal, s.id_empresa, s.nombre, emp.nombre_empresa
            FROM {SCHEMA}.t_sucursal s
            JOIN {SCHEMA}.empresa emp ON emp.id_empresa = s.id_empresa
            WHERE s.estado = TRUE AND s.activo = TRUE
            ORDER BY s.id_empresa, s.id_sucursal;
        """, fetchall=True)

        cajas_map = {}
        for s in sucursales:
            id_suc = s[0]
            id_emp = s[1]
            nom_suc = s[2]
            row_c = db.execute_query(f"SELECT id_caja FROM {SCHEMA}.t_caja WHERE id_sucursal = %s LIMIT 1;", (id_suc,), fetchone=True)
            if not row_c:
                cod_caja = f"CAJA-S{id_suc:02d}-01"
                ins_c = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_caja (id_sucursal, id_empresa, codigo_caja, nombre, estado)
                    VALUES (%s, %s, %s, %s, 'ACTIVA')
                    RETURNING id_caja;
                """, (id_suc, id_emp, cod_caja, f"Caja Mostrador {nom_suc}"), fetchone=True, commit=True)
                cajas_map[id_suc] = ins_c[0]
            else:
                cajas_map[id_suc] = row_c[0]

        # Cajeros por empresa
        cajeros_por_empresa = {
            1: [13, 22, 23],  # Cajeros Shopping Bolivia
            2: [11, 20],      # Cajeros FashionWorld
            3: [16, 21]       # Cajeros Urban Store
        }
        # Fallback a usuarios existentes de la empresa
        for emp_id in [1, 2, 3]:
            rows_u = db.execute_query(f"SELECT id_usuario FROM {SCHEMA}.t_usuario WHERE id_empresa = %s AND id_rol IN (3, 4, 5);", (emp_id,), fetchall=True)
            if rows_u:
                cajeros_por_empresa[emp_id] = [r[0] for r in rows_u]

        # Crear sesiones de caja cerradas históricas y una abierta para hoy
        sesiones_por_sucursal = {}
        now = datetime.now()

        for id_suc, id_caja in cajas_map.items():
            row_suc_emp = db.execute_query(f"SELECT id_empresa FROM {SCHEMA}.t_sucursal WHERE id_sucursal = %s;", (id_suc,), fetchone=True)
            id_emp = row_suc_emp[0]
            cajeros = cajeros_por_empresa.get(id_emp, [3])
            id_cajero = cajeros[0]

            sesiones_suc = []
            # Crear 3 sesiones cerradas pasadas (hace 40 días, hace 20 días, hace 5 días)
            for dias_atras in [40, 20, 5]:
                f_aper = now - timedelta(days=dias_atras, hours=10)
                f_cier = now - timedelta(days=dias_atras, hours=2)
                row_prev = db.execute_query(f"""
                    SELECT id_sesion_caja FROM {SCHEMA}.t_caja_sesion 
                    WHERE id_caja = %s AND fecha_apertura::date = %s::date LIMIT 1;
                """, (id_caja, f_aper.date()), fetchone=True)

                if not row_prev:
                    ins_s = db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_caja_sesion (
                            id_caja, id_usuario, id_sucursal, id_empresa, fecha_apertura, fecha_cierre,
                            monto_inicial, efectivo_esperado, efectivo_contado, diferencia, estado,
                            observacion_apertura, observacion_cierre
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            500.00, 2850.00, 2850.00, 0.00, 'CERRADA',
                            'Apertura regular de turno mañana', 'Cierre arqueado sin novedades'
                        ) RETURNING id_sesion_caja;
                    """, (id_caja, id_cajero, id_suc, id_emp, f_aper, f_cier), fetchone=True, commit=True)
                    sesiones_suc.append(ins_s[0])
                else:
                    sesiones_suc.append(row_prev[0])

            # Sesión abierta de hoy
            row_act = db.execute_query(f"""
                SELECT id_sesion_caja FROM {SCHEMA}.t_caja_sesion 
                WHERE id_caja = %s AND estado = 'ABIERTA' LIMIT 1;
            """, (id_caja,), fetchone=True)
            if not row_act:
                f_hoy_aper = now - timedelta(hours=3)
                ins_act = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_caja_sesion (
                        id_caja, id_usuario, id_sucursal, id_empresa, fecha_apertura,
                        monto_inicial, estado, observacion_apertura
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        500.00, 'ABIERTA', 'Apertura de turno mostrador'
                    ) RETURNING id_sesion_caja;
                """, (id_caja, id_cajero, id_suc, id_emp, f_hoy_aper), fetchone=True, commit=True)
                sesiones_suc.append(ins_act[0])
            else:
                sesiones_suc.append(row_act[0])

            sesiones_por_sucursal[id_suc] = sesiones_suc

        logger.info(f"Sesiones de caja listas en {len(sesiones_por_sucursal)} sucursales.")

        logger.info("=== 2. Generando Ventas, Pedidos y Pagos Multicanal para Tenants 1, 2 y 3 ===")
        # Traer clientes con sus datos
        clientes = db.execute_query(f"""
            SELECT c.id_cliente, c.id_usuario, u.nombre, u.apellido, c.ci, c.ciudad
            FROM {SCHEMA}.t_cliente c
            JOIN {SCHEMA}.t_usuario u ON u.id_usuario = c.id_usuario
            ORDER BY c.id_cliente;
        """, fetchall=True)

        if not clientes:
            logger.error("No se encontraron clientes registrados.")
            return

        total_ventas_creadas = 0

        # Cantidad de ventas por tenant para tener riqueza analítica
        # Empresa 1: 25 nuevas ventas
        # Empresa 2: 35 nuevas ventas
        # Empresa 3: 35 nuevas ventas
        ventas_config = [
            (1, 25),
            (2, 35),
            (3, 35)
        ]

        metodos_pago_pool = [
            (3, "EFECTIVO", "EF-POS"),
            (4, "QR", "QR-BCB"),
            (1, "TARJETA", "TARJ-VISA"),
            (2, "PAYPAL", "PAYPAL-CAP")
        ]

        # Ponderaciones de métodos: 40% Efectivo, 30% QR, 20% Tarjeta, 10% PayPal
        metodos_weighted = [metodos_pago_pool[0]] * 4 + [metodos_pago_pool[1]] * 3 + [metodos_pago_pool[2]] * 2 + [metodos_pago_pool[3]] * 1

        for id_emp, cant_ventas in ventas_config:
            # Traer sucursales de la empresa
            suc_emp = [s[0] for s in sucursales if s[1] == id_emp]
            if not suc_emp:
                continue

            # Traer variantes de la empresa con precio
            variantes_emp = db.execute_query(f"""
                SELECT v.id_variante, v.precio, p.id_producto, p.nombre
                FROM {SCHEMA}.t_producto_talla_color v
                JOIN {SCHEMA}.t_producto p ON p.id_producto = v.id_producto
                WHERE p.id_empresa = %s AND v.precio > 0 AND v.estado = TRUE
                ORDER BY v.id_variante;
            """, (id_emp,), fetchall=True)

            if not variantes_emp:
                logger.warning(f"No hay variantes con precio para Empresa {id_emp}")
                continue

            cajeros_emp = cajeros_por_empresa.get(id_emp, [3])

            for i in range(cant_ventas):
                # Distribuir fechas en los últimos 55 días
                dias_atras = random.randint(0, 55)
                horas_atras = random.randint(1, 10)
                fecha_vta = now - timedelta(days=dias_atras, hours=horas_atras, minutes=random.randint(5, 50))

                id_suc = random.choice(suc_emp)
                id_caja_suc = cajas_map.get(id_suc, 1)
                sesiones_suc = sesiones_por_sucursal.get(id_suc, [1])
                id_sesion = random.choice(sesiones_suc)

                cliente = random.choice(clientes)
                id_cli = cliente[0]
                nom_cli = f"{cliente[2]} {cliente[3]}".strip()
                ci_cli = cliente[4] or f"{random.randint(3000000, 9999999)}"
                ciudad_cli = cliente[5] or "Santa Cruz"

                id_cajero = random.choice(cajeros_emp)
                es_pos = random.random() < 0.70
                tipo_vta = "POS" if es_pos else "ECOMMERCE"
                sesion_venta_id = id_sesion if es_pos else None

                # Elegir entre 1 y 3 prendas
                num_prendas = random.choices([1, 2, 3], weights=[50, 35, 15])[0]
                prendas_elegidas = random.sample(variantes_emp, min(num_prendas, len(variantes_emp)))

                subtotal = Decimal("0.00")
                items_data = []
                for p_var in prendas_elegidas:
                    id_v = p_var[0]
                    p_unit = p_var[1]
                    cant = 1 if p_unit > 300 else random.choice([1, 2])
                    st_item = p_unit * cant
                    subtotal += st_item
                    items_data.append((id_v, cant, p_unit, st_item))

                descuento = Decimal("0.00")
                if random.random() < 0.25:
                    descuento = round(subtotal * Decimal("0.10"), 2)
                total = subtotal - descuento

                tipo_doc = "FACTURA" if (ci_cli and len(ci_cli) > 4) else "COMPROBANTE"
                num_vta = f"VTA-{id_emp}-{id_suc}-{random.randint(10000, 99999)}"

                # Insertar cabecera t_venta
                ins_vta = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_venta (
                        id_cliente, id_sucursal, id_usuario, numero_venta, tipo_venta,
                        fecha_venta, subtotal, descuento, total, estado, observacion,
                        id_empresa, nit_ci, razon_social, tipo_documento, id_sesion_caja,
                        correo_facturacion
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, 'PAGADO', 'Venta registrada en sistema',
                        %s, %s, %s, %s, %s,
                        %s
                    ) RETURNING id_venta;
                """, (
                    id_cli, id_suc, id_cajero, num_vta, tipo_vta,
                    fecha_vta, subtotal, descuento, total,
                    id_emp, ci_cli, nom_cli, tipo_doc, sesion_venta_id,
                    f"factura.{id_cli}@gmail.com"
                ), fetchone=True, commit=True)

                id_vta_creada = ins_vta[0]
                total_ventas_creadas += 1

                # Insertar ítems en t_detalle_venta
                for id_v, cant, p_unit, st_item in items_data:
                    db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_detalle_venta (
                            id_venta, id_variante, cantidad, precio_unitario, descuento, subtotal
                        ) VALUES (%s, %s, %s, %s, 0.00, %s);
                    """, (id_vta_creada, id_v, cant, p_unit, st_item), commit=True)

                # Insertar pago en t_pago
                metodo_elegido = random.choice(metodos_weighted)
                id_met = metodo_elegido[0]
                cod_pref = metodo_elegido[2]
                cod_tx = f"{cod_pref}-{random.randint(100000, 999999)}"

                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_pago (
                        id_venta, id_metodo_pago, codigo_transaccion, monto, fecha_pago, estado, referencia_externa
                    ) VALUES (
                        %s, %s, %s, %s, %s, 'APROBADO', %s
                    );
                """, (id_vta_creada, id_met, cod_tx, total, fecha_vta, f"REF-VTA-{id_vta_creada}"), commit=True)

                # Si es ecommerce, crear pedido vinculado en t_pedido
                if not es_pos:
                    cod_ped = f"PED-{id_emp}-{random.randint(1000, 9999)}"
                    estado_ped = "ENTREGADO" if dias_atras > 3 else random.choice(["EN_CAMINO", "EN_PREPARACION"])
                    db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_pedido (
                            codigo_pedido, id_cliente, id_empresa, id_sucursal, fecha_pedido,
                            estado, estado_pago, modalidad_compra, nombre_contacto, telefono_contacto,
                            correo_contacto, direccion_entrega, ciudad_entrega, subtotal, costo_envio,
                            descuento, total, id_venta
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, 'PAGADO', 'ENVIO_DOMICILIO', %s, %s,
                            %s, %s, %s, %s, 25.00,
                            %s, %s, %s
                        );
                    """, (
                        cod_ped, id_cli, id_emp, id_suc, fecha_vta,
                        estado_ped, nom_cli, "+591 71234567",
                        f"cliente{id_cli}@gmail.com", f"Av. Principal #{random.randint(100, 900)}", ciudad_cli,
                        subtotal, descuento, total + Decimal("25.00"), id_vta_creada
                    ), commit=True)

        logger.info(f"Ventas y pagos generados: {total_ventas_creadas} registros nuevos.")

        logger.info("=== 3. Generando Reservas de Probador para cada Empresa ===")
        total_reservas = 0
        for id_emp in [1, 2, 3]:
            suc_emp = [s[0] for s in sucursales if s[1] == id_emp]
            if not suc_emp:
                continue

            # Traer variantes
            vars_emp = db.execute_query(f"""
                SELECT v.id_variante, p.nombre
                FROM {SCHEMA}.t_producto_talla_color v
                JOIN {SCHEMA}.t_producto p ON p.id_producto = v.id_producto
                WHERE p.id_empresa = %s LIMIT 20;
            """, (id_emp,), fetchall=True)

            if not vars_emp:
                continue

            for r_idx in range(12):
                id_suc = random.choice(suc_emp)
                cliente = random.choice(clientes)
                id_cli = cliente[0]
                cod_res = f"RES-{id_emp}-{random.randint(1000, 9999)}"

                # Citas pasadas completadas vs citas futuras confirmadas
                es_futura = r_idx < 4
                if es_futura:
                    dias_adelante = random.randint(1, 5)
                    hora_visita = random.randint(10, 19)
                    f_reserva = now - timedelta(days=random.randint(0, 2))
                    f_visita = now + timedelta(days=dias_adelante, hours=hora_visita - now.hour)
                    estado_res = "CONFIRMADA"
                else:
                    dias_pasado = random.randint(3, 40)
                    f_reserva = now - timedelta(days=dias_pasado + 2)
                    f_visita = now - timedelta(days=dias_pasado)
                    estado_res = random.choices(["COMPLETADA", "CANCELADA", "VENCIDA"], weights=[70, 15, 15])[0]

                ins_r = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_reserva (
                        id_cliente, id_sucursal, codigo_reserva, fecha_reserva, fecha_hora_visita,
                        estado, observaciones, con_pago, estado_pago, monto_pagado
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, 'Cita personalizada en probador de boutique', FALSE, 'NO_REQUERIDO', 0.00
                    ) RETURNING id_reserva;
                """, (id_cli, id_suc, cod_res, f_reserva, f_visita, estado_res), fetchone=True, commit=True)

                id_res_creada = ins_r[0]
                total_reservas += 1

                # Asociar 2 a 3 prendas
                prendas_res = random.sample(vars_emp, min(random.randint(2, 3), len(vars_emp)))
                for p_var in prendas_res:
                    st_prenda = "PROBADA" if estado_res == "COMPLETADA" else "PENDIENTE"
                    db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_detalle_reserva (id_reserva, id_variante, cantidad, estado_prenda)
                        VALUES (%s, %s, 1, %s);
                    """, (id_res_creada, p_var[0], st_prenda), commit=True)

        logger.info(f"Reservas de probador creadas: {total_reservas} registros.")

        logger.info("=== 4. Generando Devoluciones y Cambios de Prenda (Ley 453) ===")
        # Traer ventas recientes para cada empresa para asociar devoluciones
        total_devoluciones = 0
        for id_emp in [1, 2, 3]:
            ventas_recientes = db.execute_query(f"""
                SELECT v.id_venta, v.id_sucursal, v.id_usuario, v.total, dv.id_detalle_venta, dv.id_variante, dv.precio_unitario
                FROM {SCHEMA}.t_venta v
                JOIN {SCHEMA}.t_detalle_venta dv ON dv.id_venta = v.id_venta
                WHERE v.id_empresa = %s
                ORDER BY v.id_venta DESC LIMIT 10;
            """, (id_emp,), fetchall=True)

            if not ventas_recientes:
                continue

            # Crear 3 devoluciones (2 CAMBIO_PRENDA y 1 REEMBOLSO_DINERO)
            muestras = random.sample(ventas_recientes, min(3, len(ventas_recientes)))
            for dev_idx, v_row in enumerate(muestras):
                id_vta = v_row[0]
                id_suc = v_row[1]
                id_usr = v_row[2]
                id_dtv = v_row[4]
                id_var = v_row[5]
                precio_u = v_row[6]

                cod_dev = f"DEV-{id_emp}-{random.randint(1000, 9999)}"
                f_dev = now - timedelta(days=random.randint(1, 15))

                if dev_idx in (0, 1):
                    # CAMBIO DE TALLA / PRENDA
                    tipo_resolucion = "CAMBIO_PRENDA"
                    motivo = "TALLA_INCORRECTA"
                    condicion = "NUEVO_CON_ETIQUETA"
                    estado_dev = "COMPLETADA"
                    desc_cli = "La prenda es de excelente calidad pero requiero una talla más holgada."
                    obs_res = "Prenda recibida con empaque y etiqueta original. Cambio físico entregado en tienda."
                    monto_reemb = Decimal("0.00")
                    ley_453 = False
                else:
                    # REEMBOLSO LEY 453 (GARANTIA)
                    tipo_resolucion = "REEMBOLSO_DINERO"
                    motivo = "DEFECTO_FABRICA"
                    condicion = "DEFECTO_FABRICA"
                    estado_dev = "COMPLETADA"
                    desc_cli = "Costura lateral descosida en primer uso conforme a garantía legal."
                    obs_res = "Garantía comercial Ley 453 aprobada. Devolución de fondos efectivizada."
                    monto_reemb = precio_u
                    ley_453 = True

                ins_dev = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_devolucion (
                        id_venta, id_usuario, fecha_devolucion, motivo, monto_reembolso,
                        estado, codigo_devolucion, id_empresa, id_sucursal, tipo_devolucion,
                        descripcion_cliente, id_usuario_revisor, fecha_resolucion, observaciones_resolucion,
                        metodo_reembolso, fecha_reembolso, tipo_resolucion, dias_desde_compra, cumple_politica, excepcion_ley_453
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, 'PARCIAL',
                        %s, %s, %s, %s,
                        'QR_TRANSFERENCIA', %s, %s, 4, TRUE, %s
                    ) RETURNING id_devolucion;
                """, (
                    id_vta, id_usr, f_dev, motivo, monto_reemb,
                    estado_dev, cod_dev, id_emp, id_suc,
                    desc_cli, id_usr, f_dev + timedelta(hours=2), obs_res,
                    f_dev + timedelta(hours=3), tipo_resolucion, ley_453
                ), fetchone=True, commit=True)

                id_dev_creada = ins_dev[0]
                total_devoluciones += 1

                # Detalle de devolución
                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_detalle_devolucion (
                        id_devolucion, id_detalle_venta, cantidad, condicion, precio_unitario,
                        monto_reembolso, estado_item, destino_inventario
                    ) VALUES (
                        %s, %s, 1, %s, %s,
                        %s, 'ACEPTADO', 'RESTITUIDO'
                    );
                """, (id_dev_creada, id_dtv, condicion, precio_u, monto_reemb), commit=True)

        logger.info(f"Devoluciones generadas: {total_devoluciones} registros con resoluciones.")

        logger.info("=== 5. Generando Valoraciones y Reseñas de Clientes (t_valoracion) ===")
        total_valoraciones = 0
        for id_emp in [1, 2, 3]:
            # Traer productos de la empresa
            prods = db.execute_query(f"SELECT id_producto, nombre FROM {SCHEMA}.t_producto WHERE id_empresa = %s;", (id_emp,), fetchall=True)
            suc_emp = [s[0] for s in sucursales if s[1] == id_emp]
            if not prods or not suc_emp:
                continue

            for v_idx in range(16):
                prod = random.choice(prods)
                id_p = prod[0]
                id_suc = random.choice(suc_emp)
                cliente = random.choice(clientes)
                id_cli = cliente[0]

                # Elegir feedback
                score, comment = random.choice(COMENTARIOS_VALORACIONES)
                req_rev = score <= 3
                motivo_neg = "TALLA_INCORRECTA" if score <= 3 else None
                f_crea = now - timedelta(days=random.randint(1, 45), hours=random.randint(1, 12))

                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_valoracion (
                        id_empresa, id_sucursal, id_cliente, id_producto, puntuacion,
                        comentario, motivo_negativo, requiere_revision, atendido, fecha_creacion
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    );
                """, (
                    id_emp, id_suc, id_cli, id_p, score,
                    comment, motivo_neg, req_rev, not req_rev, f_crea
                ), commit=True)
                total_valoraciones += 1

        logger.info(f"Valoraciones generadas: {total_valoraciones} opiniones de clientes.")

        logger.info("=== 6. Entrenando Motor MiniML de Preferencias y Recomendaciones ===")
        try:
            from app.modules.ia.services.ml_preferencias_services import aprender_preferencias_cliente
            clientes_activos = db.execute_query(f"SELECT DISTINCT id_cliente, id_empresa FROM {SCHEMA}.t_venta WHERE id_cliente IS NOT NULL;", fetchall=True)
            count_ml = 0
            for r_cli in clientes_activos:
                c_id = r_cli[0]
                e_id = r_cli[1]
                try:
                    aprender_preferencias_cliente(c_id, e_id)
                    count_ml += 1
                except Exception as ex_ml:
                    pass
            logger.info(f"Motor vectorial de Machine Learning actualizado para {count_ml} clientes.")
        except Exception as e_import:
            logger.warning(f"Aviso no bloqueante al invocar ML engine: {e_import}")

        logger.info("Población operacional completada con total éxito.")

    finally:
        db.close_connection()


if __name__ == "__main__":
    poblar_operaciones()
