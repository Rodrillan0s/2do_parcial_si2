import logging
from app.core.postgres import PostgreSQL
from app.core.config import Config

logger = logging.getLogger(__name__)

def migrar_pago_comprobante():
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'
        print(f"[*] Iniciando migración W27/W29 en esquema '{schema}'...")

        # 1. Vincular t_pedido -> t_venta con id_venta nullable
        db.execute_query(f"""
            ALTER TABLE {schema}.t_pedido 
            ADD COLUMN IF NOT EXISTS id_venta INTEGER REFERENCES {schema}.t_venta(id_venta);
        """, commit=True)
        print("[+] Columna id_venta asegurada en t_pedido.")

        # 2. Agregar columnas de facturación y tenant en t_venta
        db.execute_query(f"""
            ALTER TABLE {schema}.t_venta 
            ADD COLUMN IF NOT EXISTS id_empresa INTEGER REFERENCES {schema}.empresa(id_empresa);
        """, commit=True)

        db.execute_query(f"""
            ALTER TABLE {schema}.t_venta 
            ADD COLUMN IF NOT EXISTS nit_ci VARCHAR(50);
        """, commit=True)

        db.execute_query(f"""
            ALTER TABLE {schema}.t_venta 
            ADD COLUMN IF NOT EXISTS razon_social VARCHAR(150);
        """, commit=True)

        db.execute_query(f"""
            ALTER TABLE {schema}.t_venta 
            ADD COLUMN IF NOT EXISTS tipo_documento VARCHAR(50) DEFAULT 'COMPROBANTE';
        """, commit=True)
        print("[+] Columnas de facturación y multi-tenant aseguradas en t_venta.")

        # 3. Poblar t_metodo_pago con métodos oficiales
        metodos = [
            (1, 'Tarjeta de Débito/Crédito', 'TARJETA'),
            (2, 'PayPal', 'PAYPAL'),
            (3, 'Efectivo en Caja', 'EFECTIVO')
        ]
        for m_id, m_nombre, m_tipo in metodos:
            existe = db.execute_query(f"""
                SELECT id_metodo_pago FROM {schema}.t_metodo_pago 
                WHERE id_metodo_pago = %s OR UPPER(tipo) = UPPER(%s);
            """, (m_id, m_tipo), fetchone=True)
            if not existe:
                db.execute_query(f"""
                    INSERT INTO {schema}.t_metodo_pago (id_metodo_pago, nombre, tipo, estado)
                    VALUES (%s, %s, %s, TRUE);
                """, (m_id, m_nombre, m_tipo), commit=True)
            else:
                db.execute_query(f"""
                    UPDATE {schema}.t_metodo_pago
                    SET nombre = %s, tipo = %s, estado = TRUE
                    WHERE id_metodo_pago = %s;
                """, (m_nombre, m_tipo, existe[0]), commit=True)
        print("[+] Métodos de pago registrados en t_metodo_pago.")

        # 4. Crear o actualizar función atómica PostgreSQL: fn_confirmar_pago_pedido
        query_fn_pago = f"""
        CREATE OR REPLACE FUNCTION {schema}.fn_confirmar_pago_pedido(
            p_id_pedido INT,
            p_id_metodo_pago INT,
            p_codigo_transaccion VARCHAR,
            p_monto NUMERIC,
            p_id_usuario INT,
            p_nit_ci VARCHAR DEFAULT NULL,
            p_razon_social VARCHAR DEFAULT NULL,
            p_tipo_documento VARCHAR DEFAULT NULL
        )
        RETURNS JSON AS $$
        DECLARE
            v_id_pedido INT;
            v_id_cliente INT;
            v_id_empresa INT;
            v_id_sucursal INT;
            v_estado VARCHAR;
            v_estado_pago VARCHAR;
            v_codigo_pedido VARCHAR;
            v_subtotal NUMERIC;
            v_descuento NUMERIC;
            v_total NUMERIC;
            v_id_venta_existente INT;

            v_item RECORD;
            v_id_inv INT;
            v_stk_actual INT;
            v_stk_res INT;
            v_stk_disp INT;
            v_nuevo_actual INT;
            v_nuevo_disp INT;
            v_nuevo_res INT;

            v_id_venta INT;
            v_id_pago INT;
            v_numero_venta VARCHAR;
            v_tipo_doc VARCHAR;
            v_items_count INT := 0;
        BEGIN
            -- 1. Bloquear y validar el pedido
            SELECT id_pedido, id_cliente, id_empresa, id_sucursal, estado, estado_pago,
                   codigo_pedido, subtotal, descuento, total, id_venta
            INTO v_id_pedido, v_id_cliente, v_id_empresa, v_id_sucursal, v_estado, v_estado_pago,
                 v_codigo_pedido, v_subtotal, v_descuento, v_total, v_id_venta_existente
            FROM {schema}.t_pedido
            WHERE id_pedido = p_id_pedido
            FOR UPDATE;

            IF v_id_pedido IS NULL THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'PEDIDO_NO_ENCONTRADO',
                    'message', 'El pedido con ID ' || p_id_pedido || ' no fue encontrado.'
                );
            END IF;

            IF v_estado_pago = 'PAGADO' OR v_id_venta_existente IS NOT NULL THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'PEDIDO_YA_PAGADO',
                    'message', 'El pedido ' || v_codigo_pedido || ' ya ha sido pagado y procesado previamente.',
                    'id_venta', v_id_venta_existente
                );
            END IF;

            IF v_estado IN ('CANCELADO', 'ANULADO') THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'PEDIDO_CANCELADO',
                    'message', 'El pedido se encuentra cancelado y no admite pagos.'
                );
            END IF;

            -- 2. Validar método de pago existente
            IF NOT EXISTS (SELECT 1 FROM {schema}.t_metodo_pago WHERE id_metodo_pago = p_id_metodo_pago AND estado = TRUE) THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'METODO_PAGO_INVALIDO',
                    'message', 'El método de pago especificado no existe o se encuentra inactivo.'
                );
            END IF;

            -- 3. Recorrer ítems de t_detalle_pedido, bloquear inventario y descontar existencias
            FOR v_item IN
                SELECT id_detalle_pedido, id_variante, cantidad, precio_unitario, subtotal
                FROM {schema}.t_detalle_pedido
                WHERE id_pedido = p_id_pedido
            LOOP
                v_items_count := v_items_count + 1;

                SELECT id_inventario, stock_actual, stock_reservado, stock_disponible
                INTO v_id_inv, v_stk_actual, v_stk_res, v_stk_disp
                FROM {schema}.t_inventario
                WHERE id_sucursal = v_id_sucursal AND id_variante = v_item.id_variante
                FOR UPDATE;

                IF v_id_inv IS NULL THEN
                    RETURN json_build_object(
                        'success', false,
                        'error', 'INVENTARIO_NO_ENCONTRADO',
                        'message', 'No existe inventario en la sucursal para la variante ID ' || v_item.id_variante || '.'
                    );
                END IF;

                -- Comprobar si el inventario cubre la venta (priorizando las reservas del pedido)
                IF v_stk_res >= v_item.cantidad THEN
                    v_nuevo_res := v_stk_res - v_item.cantidad;
                    v_nuevo_disp := v_stk_disp;
                    v_nuevo_actual := v_stk_actual - v_item.cantidad;
                ELSIF (v_stk_disp + v_stk_res) >= v_item.cantidad AND v_stk_actual >= v_item.cantidad THEN
                    -- Se consumen las reservas existentes del cliente y el resto de disponible
                    v_nuevo_disp := v_stk_disp - (v_item.cantidad - v_stk_res);
                    v_nuevo_res := 0;
                    v_nuevo_actual := v_stk_actual - v_item.cantidad;
                ELSE
                    RETURN json_build_object(
                        'success', false,
                        'error', 'STOCK_INSUFICIENTE',
                        'message', 'Stock insuficiente para la variante ID ' || v_item.id_variante || '. Disponible: ' || v_stk_disp || ', solicitado: ' || v_item.cantidad,
                        'id_variante', v_item.id_variante,
                        'stock_disponible', v_stk_disp,
                        'cantidad_solicitada', v_item.cantidad
                    );
                END IF;

                IF v_nuevo_actual < 0 THEN
                    RETURN json_build_object(
                        'success', false,
                        'error', 'STOCK_NEGATIVO',
                        'message', 'La operación resultaría en stock negativo para la variante ' || v_item.id_variante
                    );
                END IF;

                -- Actualizar inventario
                UPDATE {schema}.t_inventario
                SET stock_actual = v_nuevo_actual,
                    stock_reservado = v_nuevo_res,
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
                    v_item.cantidad,
                    v_stk_actual,
                    v_nuevo_actual,
                    'Venta confirmada pedido ' || v_codigo_pedido,
                    CURRENT_TIMESTAMP
                );
            END LOOP;

            IF v_items_count = 0 THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'PEDIDO_SIN_ITEMS',
                    'message', 'El pedido no contiene ítems para procesar la venta.'
                );
            END IF;

            -- 4. Determinar tipo de documento
            IF p_tipo_documento IS NOT NULL AND p_tipo_documento <> '' THEN
                v_tipo_doc := UPPER(p_tipo_documento);
            ELSIF p_nit_ci IS NOT NULL AND TRIM(p_nit_ci) <> '' THEN
                v_tipo_doc := 'FACTURA';
            ELSE
                v_tipo_doc := 'COMPROBANTE';
            END IF;

            -- 5. Generar número de venta único
            v_numero_venta := 'VTA-' || TO_CHAR(CURRENT_TIMESTAMP, 'YYYYMMDD') || '-' || LPAD(FLOOR(RANDOM() * 90000 + 10000)::TEXT, 5, '0');

            -- 6. Crear cabecera de venta en t_venta
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
                nit_ci,
                razon_social,
                tipo_documento,
                id_empresa
            ) VALUES (
                v_id_cliente,
                v_id_sucursal,
                p_id_usuario,
                v_numero_venta,
                'ONLINE',
                CURRENT_TIMESTAMP,
                v_subtotal,
                v_descuento,
                v_total,
                'COMPLETADA',
                'Venta procesada mediante pago electrónico - Pedido ' || v_codigo_pedido,
                p_nit_ci,
                p_razon_social,
                v_tipo_doc,
                v_id_empresa
            ) RETURNING id_venta INTO v_id_venta;

            -- 7. Crear detalle de la venta en t_detalle_venta
            INSERT INTO {schema}.t_detalle_venta (
                id_venta,
                id_variante,
                cantidad,
                precio_unitario,
                descuento,
                subtotal
            )
            SELECT
                v_id_venta,
                id_variante,
                cantidad,
                precio_unitario,
                0,
                subtotal
            FROM {schema}.t_detalle_pedido
            WHERE id_pedido = p_id_pedido;

            -- 8. Registrar el pago en t_pago
            INSERT INTO {schema}.t_pago (
                id_venta,
                id_metodo_pago,
                codigo_transaccion,
                monto,
                fecha_pago,
                estado
            ) VALUES (
                v_id_venta,
                p_id_metodo_pago,
                COALESCE(p_codigo_transaccion, 'TXN-' || TO_CHAR(CURRENT_TIMESTAMP, 'YYYYMMDDHH24MISS')),
                p_monto,
                CURRENT_TIMESTAMP,
                'APROBADO'
            ) RETURNING id_pago INTO v_id_pago;

            -- 9. Actualizar estado y vincular t_pedido con t_venta
            UPDATE {schema}.t_pedido
            SET id_venta = v_id_venta,
                estado = 'PAGADO',
                estado_pago = 'PAGADO',
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_pedido = p_id_pedido;

            -- 10. Confirmación exitosa
            RETURN json_build_object(
                'success', true,
                'message', 'Pago y venta confirmados exitosamente.',
                'id_pedido', p_id_pedido,
                'codigo_pedido', v_codigo_pedido,
                'id_venta', v_id_venta,
                'numero_venta', v_numero_venta,
                'id_pago', v_id_pago,
                'codigo_transaccion', p_codigo_transaccion,
                'tipo_documento', v_tipo_doc,
                'monto', p_monto,
                'total', v_total
            );
        END;
        $$ LANGUAGE plpgsql;
        """
        db.execute_query(query_fn_pago, commit=True)
        print("[+] Función PostgreSQL fn_confirmar_pago_pedido creada/actualizada exitosamente.")

        print("[*] Migración W27/W29 finalizada al 100%.")
    except Exception as e:
        print(f"[!] Error en migración: {e}")
        raise e
    finally:
        db.close_connection()

if __name__ == '__main__':
    migrar_pago_comprobante()
