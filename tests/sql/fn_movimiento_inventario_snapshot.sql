-- Read-only production definition captured 2026-11-01; isolated test fixture only.
CREATE OR REPLACE FUNCTION __SCHEMA__.fn_movimiento_inventario(p_id_sucursal integer, p_id_variante integer, p_tipo_movimiento character varying, p_cantidad integer, p_id_usuario integer, p_motivo character varying)
 RETURNS json
 LANGUAGE plpgsql
AS $function$
        DECLARE
            v_id_inventario INT;
            v_stock_actual INT;
            v_stock_reservado INT;
            v_stock_disponible INT;
            v_stock_minimo INT;
            v_estado BOOLEAN;
            v_stock_anterior INT;
            v_nuevo_actual INT;
            v_nuevo_disponible INT;
            v_delta INT;
            v_id_movimiento INT;
            v_tipo_upper VARCHAR;
        BEGIN
            v_tipo_upper := UPPER(TRIM(p_tipo_movimiento));

            -- 1. Validar tipo de movimiento
            IF v_tipo_upper NOT IN ('ENTRADA', 'SALIDA', 'AJUSTE') THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'TIPO_MOVIMIENTO_INVALIDO',
                    'message', 'El tipo de movimiento debe ser ENTRADA, SALIDA o AJUSTE.'
                );
            END IF;

            -- 2. Validar cantidad según el tipo
            IF v_tipo_upper IN ('ENTRADA', 'SALIDA') AND (p_cantidad IS NULL OR p_cantidad <= 0) THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'CANTIDAD_INVALIDA',
                    'message', 'La cantidad para entrada o salida debe ser mayor a 0.'
                );
            END IF;

            IF v_tipo_upper = 'AJUSTE' AND (p_cantidad IS NULL OR p_cantidad < 0) THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'STOCK_NEGATIVO_NO_PERMITIDO',
                    'message', 'El stock para ajuste no puede ser negativo.'
                );
            END IF;

            -- 3. Bloqueo FOR UPDATE atómico sobre la fila de inventario
            SELECT id_inventario, stock_actual, stock_reservado, stock_disponible, stock_minimo, estado
            INTO v_id_inventario, v_stock_actual, v_stock_reservado, v_stock_disponible, v_stock_minimo, v_estado
            FROM __SCHEMA__.t_inventario
            WHERE id_sucursal = p_id_sucursal AND id_variante = p_id_variante
            FOR UPDATE;

            -- 4. Validar existencia de inventario
            IF v_id_inventario IS NULL THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'INVENTARIO_NO_ENCONTRADO',
                    'message', 'No existe inventario para la variante en la sucursal especificada.'
                );
            END IF;

            v_stock_actual := COALESCE(v_stock_actual, 0);
            v_stock_reservado := COALESCE(v_stock_reservado, 0);
            v_stock_disponible := COALESCE(v_stock_disponible, v_stock_actual - v_stock_reservado);
            v_stock_anterior := v_stock_actual;

            -- 5. Aplicar lógica según el tipo de movimiento
            IF v_tipo_upper = 'ENTRADA' THEN
                v_nuevo_actual := v_stock_actual + p_cantidad;
                v_nuevo_disponible := v_nuevo_actual - v_stock_reservado;
                v_delta := p_cantidad;

            ELSIF v_tipo_upper = 'SALIDA' THEN
                -- Regla de stock: salida nunca puede consumir unidades reservadas
                -- stock_disponible = stock_actual - stock_reservado
                IF p_cantidad > v_stock_disponible THEN
                    RETURN json_build_object(
                        'success', false,
                        'error', 'STOCK_INSUFICIENTE',
                        'message', 'Stock disponible insuficiente para realizar la salida. Las unidades reservadas no pueden consumirse.',
                        'stock_actual', v_stock_actual,
                        'stock_reservado', v_stock_reservado,
                        'stock_disponible', v_stock_disponible,
                        'cantidad_solicitada', p_cantidad
                    );
                END IF;

                v_nuevo_actual := v_stock_actual - p_cantidad;
                IF v_nuevo_actual < 0 THEN
                    RETURN json_build_object(
                        'success', false,
                        'error', 'STOCK_NEGATIVO_NO_PERMITIDO',
                        'message', 'La salida provocaría un stock negativo.',
                        'stock_actual', v_stock_actual,
                        'cantidad_solicitada', p_cantidad
                    );
                END IF;

                v_nuevo_disponible := v_nuevo_actual - v_stock_reservado;
                v_delta := p_cantidad;

            ELSIF v_tipo_upper = 'AJUSTE' THEN
                v_nuevo_actual := p_cantidad;

                IF v_nuevo_actual < 0 THEN
                    RETURN json_build_object(
                        'success', false,
                        'error', 'STOCK_NEGATIVO_NO_PERMITIDO',
                        'message', 'El stock ajustado no puede ser negativo.'
                    );
                END IF;

                IF v_nuevo_actual < v_stock_reservado THEN
                    RETURN json_build_object(
                        'success', false,
                        'error', 'STOCK_MENOR_A_RESERVADO',
                        'message', 'El nuevo stock no puede ser inferior a las unidades reservadas vigentes (' || v_stock_reservado || ').',
                        'stock_reservado', v_stock_reservado,
                        'stock_solicitado', v_nuevo_actual
                    );
                END IF;

                v_nuevo_disponible := v_nuevo_actual - v_stock_reservado;
                v_delta := ABS(v_nuevo_actual - v_stock_actual);
            END IF;

            -- 6. Actualizar t_inventario
            UPDATE __SCHEMA__.t_inventario
            SET stock_actual = v_nuevo_actual,
                stock_disponible = v_nuevo_disponible,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_inventario = v_id_inventario;

            -- 7. Registrar t_movimiento_inventario asegurando que id_usuario exista
            IF p_id_usuario IS NOT NULL AND NOT EXISTS (SELECT 1 FROM __SCHEMA__.t_usuario WHERE id_usuario = p_id_usuario) THEN
                p_id_usuario := NULL;
            END IF;

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
                v_tipo_upper,
                v_delta,
                v_stock_anterior,
                v_nuevo_actual,
                COALESCE(p_motivo, 'Movimiento ' || v_tipo_upper),
                CURRENT_TIMESTAMP
            ) RETURNING id_movimiento INTO v_id_movimiento;

            -- 8. Devolver stock anterior, nuevo y resultado
            RETURN json_build_object(
                'success', true,
                'message', 'Movimiento registrado exitosamente',
                'id_inventario', v_id_inventario,
                'id_movimiento', v_id_movimiento,
                'id_sucursal', p_id_sucursal,
                'id_variante', p_id_variante,
                'tipo_movimiento', v_tipo_upper,
                'cantidad', v_delta,
                'stock_anterior', v_stock_anterior,
                'stock_nuevo', v_nuevo_actual,
                'stock_actual', v_nuevo_actual,
                'stock_reservado', v_stock_reservado,
                'stock_disponible', v_nuevo_disponible
            );
        END;
        $function$
;

