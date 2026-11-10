-- Read-only snapshot, 2026-10-31. Source SHA-256: cc21fefffcd58ac9cd04355d1dbceb144ff74f14a203f034e90e670b9240371f
-- Only schema qualifiers are substituted for isolated integration tests.
CREATE OR REPLACE FUNCTION __SCHEMA__.fn_reservar_stock(p_id_sucursal integer, p_id_variante integer, p_cantidad integer, p_id_usuario integer)
 RETURNS json
 LANGUAGE plpgsql
AS $function$
        DECLARE
            v_id_inventario INT;
            v_stock_actual INT;
            v_stock_reservado INT;
            v_stock_disponible INT;
            v_nuevo_reservado INT;
            v_nuevo_disponible INT;
        BEGIN
            IF p_cantidad <= 0 THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'CANTIDAD_INVALIDA',
                    'message', 'La cantidad a reservar debe ser mayor a 0.'
                );
            END IF;

            SELECT id_inventario, stock_actual, stock_reservado, stock_disponible
            INTO v_id_inventario, v_stock_actual, v_stock_reservado, v_stock_disponible
            FROM __SCHEMA__.t_inventario
            WHERE id_sucursal = p_id_sucursal AND id_variante = p_id_variante
            FOR UPDATE;

            IF v_id_inventario IS NULL THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'INVENTARIO_NO_ENCONTRADO',
                    'message', 'No existe inventario para la variante en la sucursal seleccionada.'
                );
            END IF;

            IF v_stock_disponible < p_cantidad THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'STOCK_INSUFICIENTE',
                    'message', 'Stock disponible insuficiente para cubrir la reserva.',
                    'stock_disponible', v_stock_disponible,
                    'cantidad_solicitada', p_cantidad
                );
            END IF;

            v_nuevo_reservado := v_stock_reservado + p_cantidad;
            v_nuevo_disponible := v_stock_disponible - p_cantidad;

            UPDATE __SCHEMA__.t_inventario
            SET stock_reservado = v_nuevo_reservado,
                stock_disponible = v_nuevo_disponible,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_inventario = v_id_inventario;

            INSERT INTO __SCHEMA__.t_movimiento_inventario (
                id_inventario,
                id_usuario,
                tipo_movimiento,
                cantidad,
                stock_anterior,
                stock_nuevo,
                motivo,
                fecha_movimiento
            ) VALUES (
                v_id_inventario,
                p_id_usuario,
                'RESERVA',
                p_cantidad,
                v_stock_disponible,
                v_nuevo_disponible,
                'Reserva de prenda en sucursal',
                CURRENT_TIMESTAMP
            );

            RETURN json_build_object(
                'success', true,
                'id_inventario', v_id_inventario,
                'stock_anterior', v_stock_disponible,
                'stock_disponible', v_nuevo_disponible,
                'stock_reservado', v_nuevo_reservado
            );
        END;
        $function$

