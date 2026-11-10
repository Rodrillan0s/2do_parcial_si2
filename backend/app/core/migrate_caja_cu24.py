import os
import sys
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env')))

from app.core.postgres import PostgreSQL
from app.core.config import Config

logger = logging.getLogger(__name__)

def migrar_caja_pos():
    """
    Crea y actualiza idempotentemente las tablas, denominaciones y funciones
    necesarias para CU/W24 (Punto de Venta / POS y Gestión de Caja).
    """
    schema = Config.SCHEMA or 'comercio'
    db = PostgreSQL()
    db.create_connection()
    try:
        logger.info(f"[*] Iniciando migración W24 (Caja y POS) en esquema '{schema}'...")

        # 1. Tabla de Denominaciones Monetarias Parametrizadas
        db.execute_query(f"""
            CREATE TABLE IF NOT EXISTS {schema}.t_denominacion (
                id_denominacion SERIAL PRIMARY KEY,
                valor NUMERIC(10, 2) NOT NULL,
                moneda VARCHAR(10) NOT NULL DEFAULT 'BOB',
                tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('BILLETE', 'MONEDA')),
                activo BOOLEAN NOT NULL DEFAULT TRUE,
                orden INT NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """, commit=True)

        # Sembrar denominaciones de Bolivia (Bs)
        denominaciones = [
            (200.00, 'BOB', 'BILLETE', 1),
            (100.00, 'BOB', 'BILLETE', 2),
            (50.00, 'BOB', 'BILLETE', 3),
            (20.00, 'BOB', 'BILLETE', 4),
            (10.00, 'BOB', 'BILLETE', 5),
            (5.00, 'BOB', 'MONEDA', 6),
            (2.00, 'BOB', 'MONEDA', 7),
            (1.00, 'BOB', 'MONEDA', 8),
            (0.50, 'BOB', 'MONEDA', 9),
            (0.20, 'BOB', 'MONEDA', 10),
            (0.10, 'BOB', 'MONEDA', 11),
        ]
        for valor, moneda, tipo, orden in denominaciones:
            db.execute_query(f"""
                INSERT INTO {schema}.t_denominacion (valor, moneda, tipo, orden, activo)
                SELECT %s, %s, %s, %s, TRUE
                WHERE NOT EXISTS (
                    SELECT 1 FROM {schema}.t_denominacion 
                    WHERE valor = %s AND moneda = %s AND tipo = %s
                );
            """, (valor, moneda, tipo, orden, valor, moneda, tipo), commit=True)

        # 2. Tabla de Cajas Físicas / Lógicas por Sucursal
        db.execute_query(f"""
            CREATE TABLE IF NOT EXISTS {schema}.t_caja (
                id_caja SERIAL PRIMARY KEY,
                id_sucursal INT NOT NULL REFERENCES {schema}.t_sucursal(id_sucursal),
                id_empresa INT NOT NULL REFERENCES {schema}.empresa(id_empresa),
                codigo_caja VARCHAR(50) NOT NULL,
                nombre VARCHAR(100) NOT NULL,
                estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVA' CHECK (estado IN ('ACTIVA', 'INACTIVA')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """, commit=True)

        # 3. Tabla de Sesiones de Caja (Turnos de Apertura y Cierre)
        db.execute_query(f"""
            CREATE TABLE IF NOT EXISTS {schema}.t_caja_sesion (
                id_sesion_caja SERIAL PRIMARY KEY,
                id_caja INT NOT NULL REFERENCES {schema}.t_caja(id_caja),
                id_usuario INT NOT NULL REFERENCES {schema}.t_usuario(id_usuario),
                id_sucursal INT NOT NULL REFERENCES {schema}.t_sucursal(id_sucursal),
                id_empresa INT NOT NULL REFERENCES {schema}.empresa(id_empresa),
                fecha_apertura TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                fecha_cierre TIMESTAMP,
                monto_inicial NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                efectivo_esperado NUMERIC(12, 2),
                efectivo_contado NUMERIC(12, 2),
                diferencia NUMERIC(12, 2),
                estado VARCHAR(20) NOT NULL DEFAULT 'ABIERTA' CHECK (estado IN ('ABIERTA', 'CERRADA')),
                observacion_apertura TEXT,
                observacion_cierre TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """, commit=True)

        # 4. Tabla de Detalle Histórico de Denominaciones (Apertura y Cierre)
        db.execute_query(f"""
            CREATE TABLE IF NOT EXISTS {schema}.t_caja_conteo (
                id_conteo SERIAL PRIMARY KEY,
                id_sesion_caja INT NOT NULL REFERENCES {schema}.t_caja_sesion(id_sesion_caja) ON DELETE CASCADE,
                tipo_conteo VARCHAR(20) NOT NULL CHECK (tipo_conteo IN ('APERTURA', 'CIERRE')),
                id_denominacion INT REFERENCES {schema}.t_denominacion(id_denominacion),
                valor_denominacion NUMERIC(10, 2) NOT NULL,
                cantidad INT NOT NULL CHECK (cantidad >= 0),
                subtotal NUMERIC(12, 2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """, commit=True)

        # 5. Asegurar columna id_sesion_caja en t_venta
        db.execute_query(f"""
            ALTER TABLE {schema}.t_venta 
            ADD COLUMN IF NOT EXISTS id_sesion_caja INT REFERENCES {schema}.t_caja_sesion(id_sesion_caja);
        """, commit=True)

        # 6. Crear Cajas por defecto para todas las sucursales existentes si no tienen
        sucursales = db.execute_query(f"SELECT id_sucursal, id_empresa, nombre FROM {schema}.t_sucursal;", fetchall=True) or []
        for suc in sucursales:
            id_suc, id_emp, nom_suc = suc[0], suc[1], suc[2]
            cajas_exist = db.execute_query(f"SELECT id_caja FROM {schema}.t_caja WHERE id_sucursal = %s LIMIT 1;", (id_suc,), fetchone=True)
            if not cajas_exist:
                db.execute_query(f"""
                    INSERT INTO {schema}.t_caja (id_sucursal, id_empresa, codigo_caja, nombre, estado)
                    VALUES (%s, %s, %s, %s, 'ACTIVA');
                """, (id_suc, id_emp, f"CAJA-SUC-{id_suc}-01", f"Caja 01 - {nom_suc}"), commit=True)

        # 7. Permisos RBAC para Caja y POS
        permisos_caja = [
            ('caja.abrir', 'Abrir caja', 'Permiso para realizar apertura de caja registradora con conteo físico', 'CAJA'),
            ('caja.cerrar', 'Cerrar caja', 'Permiso para realizar cierre de caja registradora y arqueo', 'CAJA'),
            ('caja.ver', 'Ver estado de caja', 'Permiso para consultar estado y sesiones de caja', 'CAJA'),
            ('pos.vender', 'Operar POS', 'Permiso para registrar ventas presenciales en el punto de venta', 'POS'),
            ('pos.descuento', 'Aplicar descuentos POS', 'Permiso para aplicar descuentos manuales o promocionales en POS', 'POS'),
        ]
        for cod, nom, desc, mod in permisos_caja:
            db.execute_query(f"""
                INSERT INTO {schema}.t_permiso (codigo, nombre, descripcion, modulo, activo)
                SELECT %s, %s, %s, %s, TRUE
                WHERE NOT EXISTS (SELECT 1 FROM {schema}.t_permiso WHERE codigo = %s);
            """, (cod, nom, desc, mod, cod), commit=True)

        # Asignar permisos a roles: CAJERO (id_rol=5), ADMINISTRADOR (id_rol=1), ADMINISTRADOR_TIENDA (id_rol=3), ENCARGADO_SUCURSAL (id_rol=4)
        roles_con_caja = [1, 3, 4, 5]
        for id_r in roles_con_caja:
            for cod, _, _, _ in permisos_caja:
                db.execute_query(f"""
                    INSERT INTO {schema}.t_rol_permiso (id_rol, id_permiso)
                    SELECT %s, p.id_permiso
                    FROM {schema}.t_permiso p
                    WHERE p.codigo = %s
                    AND NOT EXISTS (
                        SELECT 1 FROM {schema}.t_rol_permiso rp 
                        WHERE rp.id_rol = %s AND rp.id_permiso = p.id_permiso
                    );
                """, (id_r, cod, id_r), commit=True)

        # 8. Función Transaccional PostgreSQL para Registrar Venta POS Atómica
        db.execute_query(f"""
        CREATE OR REPLACE FUNCTION {schema}.fn_registrar_venta_pos(
            p_id_sesion_caja INT,
            p_id_usuario INT,
            p_id_sucursal INT,
            p_id_empresa INT,
            p_id_cliente INT,
            p_items JSON,
            p_descuento NUMERIC,
            p_observacion TEXT
        )
        RETURNS JSON
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_sesion_estado VARCHAR(20);
            v_sesion_sucursal INT;
            v_sesion_empresa INT;
            v_sesion_usuario INT;
            v_item JSON;
            v_id_variante INT;
            v_cantidad INT;
            v_precio_unit NUMERIC(12, 2);
            v_subtotal_item NUMERIC(12, 2);
            v_subtotal_calc NUMERIC(12, 2) := 0.00;
            v_descuento_aplicado NUMERIC(12, 2) := COALESCE(p_descuento, 0.00);
            v_total_calc NUMERIC(12, 2) := 0.00;
            v_id_inv INT;
            v_stk_actual INT;
            v_stk_disp INT;
            v_nuevo_actual INT;
            v_nuevo_disp INT;
            v_id_venta INT;
            v_numero_venta VARCHAR(50);
            v_items_count INT := 0;
            v_codigo_producto VARCHAR(50);
            v_producto_nombre VARCHAR(150);
        BEGIN
            -- 1. Validar que la sesión de caja exista y esté ABIERTA
            SELECT estado, id_sucursal, id_empresa, id_usuario
            INTO v_sesion_estado, v_sesion_sucursal, v_sesion_empresa, v_sesion_usuario
            FROM {schema}.t_caja_sesion
            WHERE id_sesion_caja = p_id_sesion_caja
            FOR UPDATE;

            IF v_sesion_estado IS NULL THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'SESION_NO_ENCONTRADA',
                    'message', 'La sesión de caja especificada no existe.'
                );
            END IF;

            IF v_sesion_estado <> 'ABIERTA' THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'CAJA_CERRADA',
                    'message', 'La caja se encuentra cerrada. Debe abrir una caja para registrar ventas.'
                );
            END IF;

            IF v_sesion_sucursal <> p_id_sucursal THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'SUCURSAL_INVALIDA',
                    'message', 'La sesión de caja no corresponde a la sucursal activa.'
                );
            END IF;

            -- 2. Validar que vengan ítems en la venta
            IF p_items IS NULL OR json_array_length(p_items) = 0 THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'VENTA_SIN_ITEMS',
                    'message', 'No se pueden registrar ventas sin productos.'
                );
            END IF;

            -- 3. Recorrer ítems, validar existencia de variante, precios actuales y stock
            FOR v_item IN SELECT * FROM json_array_elements(p_items)
            LOOP
                v_id_variante := (v_item->>'id_variante')::INT;
                v_cantidad := (v_item->>'cantidad')::INT;

                IF v_cantidad IS NULL OR v_cantidad <= 0 THEN
                    RETURN json_build_object(
                        'success', false,
                        'error', 'CANTIDAD_INVALIDA',
                        'message', 'La cantidad del ítem debe ser un entero positivo.'
                    );
                END IF;

                -- Obtener precio actual y verificar que la variante pertenezca a la empresa
                SELECT COALESCE(v.precio, p.precio), p.nombre, p.codigo_producto
                INTO v_precio_unit, v_producto_nombre, v_codigo_producto
                FROM {schema}.t_producto_talla_color v
                JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
                WHERE v.id_variante = v_id_variante 
                  AND p.id_empresa = p_id_empresa
                  AND v.activo = TRUE 
                  AND p.activo = TRUE;

                IF v_precio_unit IS NULL THEN
                    RETURN json_build_object(
                        'success', false,
                        'error', 'PRODUCTO_NO_ENCONTRADO',
                        'message', 'Variante ID ' || v_id_variante || ' no encontrada o inactiva.'
                    );
                END IF;

                v_subtotal_item := v_precio_unit * v_cantidad;
                v_subtotal_calc := v_subtotal_calc + v_subtotal_item;
                v_items_count := v_items_count + 1;

                -- 4. Bloquear fila de inventario con FOR UPDATE para prevenir sobreventas concurrentes
                SELECT id_inventario, stock_actual, stock_disponible
                INTO v_id_inv, v_stk_actual, v_stk_disp
                FROM {schema}.t_inventario
                WHERE id_sucursal = p_id_sucursal AND id_variante = v_id_variante
                FOR UPDATE;

                IF v_id_inv IS NULL THEN
                    RETURN json_build_object(
                        'success', false,
                        'error', 'INVENTARIO_NO_ENCONTRADO',
                        'message', 'No existe inventario en la sucursal para la variante ID ' || v_id_variante
                    );
                END IF;

                IF v_stk_disp < v_cantidad THEN
                    RETURN json_build_object(
                        'success', false,
                        'error', 'STOCK_INSUFICIENTE',
                        'message', 'Stock insuficiente para ' || v_producto_nombre || '. Disponible: ' || v_stk_disp || ', solicitado: ' || v_cantidad,
                        'id_variante', v_id_variante,
                        'stock_disponible', v_stk_disp,
                        'cantidad_solicitada', v_cantidad
                    );
                END IF;

                v_nuevo_actual := v_stk_actual - v_cantidad;
                v_nuevo_disp := v_stk_disp - v_cantidad;

                -- Descontar inventario
                UPDATE {schema}.t_inventario
                SET stock_actual = v_nuevo_actual,
                    stock_disponible = v_nuevo_disp,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id_inventario = v_id_inv;

                -- Registrar movimiento de salida
                INSERT INTO {schema}.t_movimiento_inventario (
                    id_inventario,
                    id_usuario,
                    tipo_movimiento,
                    cantidad,
                    stock_anterior,
                    stock_nuevo,
                    motivo,
                    fecha_movimiento
                ) VALUES (
                    v_id_inv,
                    p_id_usuario,
                    'SALIDA',
                    v_cantidad,
                    v_stk_actual,
                    v_nuevo_actual,
                    'Venta presencial POS',
                    CURRENT_TIMESTAMP
                );
            END LOOP;

            -- 5. Validar descuento
            IF v_descuento_aplicado < 0 THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'DESCUENTO_NEGATIVO',
                    'message', 'El descuento no puede ser negativo.'
                );
            END IF;

            IF v_descuento_aplicado > v_subtotal_calc THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'DESCUENTO_EXCESIVO',
                    'message', 'El descuento no puede superar el subtotal de la venta.'
                );
            END IF;

            v_total_calc := v_subtotal_calc - v_descuento_aplicado;

            -- 6. Generar número de venta único
            v_numero_venta := 'VTA-' || TO_CHAR(CURRENT_TIMESTAMP, 'YYYYMMDD') || '-' || LPAD(FLOOR(RANDOM() * 90000 + 10000)::TEXT, 5, '0');

            -- 7. Insertar cabecera t_venta en estado PENDIENTE_PAGO (Regla RB09: No crea pago W28)
            INSERT INTO {schema}.t_venta (
                id_cliente,
                id_sucursal,
                id_usuario,
                numero_venta,
                tipo_venta,
                fecha_venta,
                subtotal,
                descuento,
                total,
                estado,
                observacion,
                id_empresa,
                id_sesion_caja,
                tipo_documento
            ) VALUES (
                p_id_cliente,
                p_id_sucursal,
                p_id_usuario,
                v_numero_venta,
                'PRESENCIAL',
                CURRENT_TIMESTAMP,
                v_subtotal_calc,
                v_descuento_aplicado,
                v_total_calc,
                'PENDIENTE_PAGO',
                COALESCE(p_observacion, 'Venta presencial POS'),
                p_id_empresa,
                p_id_sesion_caja,
                'COMPROBANTE'
            ) RETURNING id_venta INTO v_id_venta;

            -- 8. Insertar detalle t_detalle_venta con precios históricos
            FOR v_item IN SELECT * FROM json_array_elements(p_items)
            LOOP
                v_id_variante := (v_item->>'id_variante')::INT;
                v_cantidad := (v_item->>'cantidad')::INT;

                SELECT COALESCE(v.precio, p.precio)
                INTO v_precio_unit
                FROM {schema}.t_producto_talla_color v
                JOIN {schema}.t_producto p ON p.id_producto = v.id_producto
                WHERE v.id_variante = v_id_variante;

                v_subtotal_item := v_precio_unit * v_cantidad;

                INSERT INTO {schema}.t_detalle_venta (
                    id_venta,
                    id_variante,
                    cantidad,
                    precio_unitario,
                    descuento,
                    subtotal
                ) VALUES (
                    v_id_venta,
                    v_id_variante,
                    v_cantidad,
                    v_precio_unit,
                    0.00,
                    v_subtotal_item
                );
            END LOOP;

            -- 9. Retornar confirmación exitosa
            RETURN json_build_object(
                'success', true,
                'message', 'Venta registrada exitosamente. Pendiente de cobro en caja (W28).',
                'id_venta', v_id_venta,
                'numero_venta', v_numero_venta,
                'subtotal', v_subtotal_calc,
                'descuento', v_descuento_aplicado,
                'total', v_total_calc,
                'estado', 'PENDIENTE_PAGO',
                'id_sesion_caja', p_id_sesion_caja
            );
        END;
        $$;
        """, commit=True)

        logger.info("[*] Migración W24 finalizada exitosamente.")
        return True
    except Exception as e:
        logger.error(f"[ERROR MIGRACION W24] {e}")
        db.conn.rollback()
        raise e
    finally:
        db.close_connection()

if __name__ == '__main__':
    migrar_caja_pos()
