CREATE OR REPLACE FUNCTION comercio.fn_confirmar_pago_pedido(p_id_pedido integer, p_id_metodo_pago integer, p_codigo_transaccion character varying, p_monto numeric, p_id_usuario integer, p_nit_ci character varying DEFAULT NULL::character varying, p_razon_social character varying DEFAULT NULL::character varying, p_tipo_documento character varying DEFAULT NULL::character varying)
 RETURNS json
 LANGUAGE plpgsql
AS $function$
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
            FROM comercio.t_pedido
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
            IF NOT EXISTS (SELECT 1 FROM comercio.t_metodo_pago WHERE id_metodo_pago = p_id_metodo_pago AND estado = TRUE) THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'METODO_PAGO_INVALIDO',
                    'message', 'El método de pago especificado no existe o se encuentra inactivo.'
                );
            END IF;

            -- 3. Recorrer ítems de t_detalle_pedido, bloquear inventario y descontar existencias
            FOR v_item IN
                SELECT id_detalle_pedido, id_variante, cantidad, precio_unitario, subtotal
                FROM comercio.t_detalle_pedido
                WHERE id_pedido = p_id_pedido
            LOOP
                v_items_count := v_items_count + 1;

                SELECT id_inventario, stock_actual, stock_reservado, stock_disponible
                INTO v_id_inv, v_stk_actual, v_stk_res, v_stk_disp
                FROM comercio.t_inventario
                WHERE id_sucursal = v_id_sucursal AND id_variante = v_item.id_variante
                FOR UPDATE;

                IF v_id_inv IS NULL THEN
                    RETURN json_build_object(
                        'success', false,
                        'error', 'INVENTARIO_NO_ENCONTRADO',
                        'message', 'No existe inventario en la sucursal para la variante ID ' || v_item.id_variante || '.'
                    );
                END IF;

                -- Comprobar si el inventario cubre la venta (disponible normal o reservado)
                IF v_stk_disp >= v_item.cantidad THEN
                    v_nuevo_disp := v_stk_disp - v_item.cantidad;
                    v_nuevo_res := v_stk_res;
                    v_nuevo_actual := v_stk_actual - v_item.cantidad;
                ELSIF (v_stk_disp + v_stk_res) >= v_item.cantidad AND v_stk_actual >= v_item.cantidad THEN
                    -- Se consumen las reservas existentes del cliente
                    v_nuevo_res := GREATEST(0, v_stk_res - (v_item.cantidad - v_stk_disp));
                    v_nuevo_disp := 0;
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
                UPDATE comercio.t_inventario
                SET stock_actual = v_nuevo_actual,
                    stock_reservado = v_nuevo_res,
                    stock_disponible = v_nuevo_disp,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id_inventario = v_id_inv;

                -- Registrar movimiento de salida
                INSERT INTO comercio.t_movimiento_inventario (
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
            INSERT INTO comercio.t_venta (
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
            INSERT INTO comercio.t_detalle_venta (
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
            FROM comercio.t_detalle_pedido
            WHERE id_pedido = p_id_pedido;

            -- 8. Registrar el pago en t_pago
            INSERT INTO comercio.t_pago (
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
            UPDATE comercio.t_pedido
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
        $function$
;

CREATE OR REPLACE FUNCTION comercio.fn_movimiento_inventario(p_id_sucursal integer, p_id_variante integer, p_tipo_movimiento character varying, p_cantidad integer, p_id_usuario integer, p_motivo character varying)
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
            FROM comercio.t_inventario
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
            UPDATE comercio.t_inventario
            SET stock_actual = v_nuevo_actual,
                stock_disponible = v_nuevo_disponible,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_inventario = v_id_inventario;

            -- 7. Registrar t_movimiento_inventario asegurando que id_usuario exista
            IF p_id_usuario IS NOT NULL AND NOT EXISTS (SELECT 1 FROM comercio.t_usuario WHERE id_usuario = p_id_usuario) THEN
                p_id_usuario := NULL;
            END IF;

            INSERT INTO comercio.t_movimiento_inventario (
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

CREATE OR REPLACE FUNCTION comercio.fn_registrar_venta_pos(p_id_sesion_caja integer, p_id_usuario integer, p_id_sucursal integer, p_id_empresa integer, p_id_cliente integer, p_items json, p_descuento numeric, p_observacion text, p_id_reserva integer DEFAULT NULL::integer)
 RETURNS json
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_sesion_estado VARCHAR(20);
    v_sesion_sucursal INT;
    v_sesion_empresa INT;
    v_sesion_usuario INT;

    v_reserva_estado VARCHAR(50);
    v_reserva_cliente INT;
    v_reserva_sucursal INT;
    v_reserva_venta INT;

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
    v_stk_reservado INT;
    v_stk_disp INT;

    v_nuevo_actual INT;
    v_nuevo_reservado INT;
    v_nuevo_disp INT;

    v_id_venta INT;
    v_numero_venta VARCHAR(50);

    v_items_count INT := 0;
    v_codigo_producto VARCHAR(50);
    v_producto_nombre VARCHAR(150);

    v_cantidad_reservada INT;
BEGIN

    ------------------------------------------------------------------
    -- 1. VALIDAR SESIÓN DE CAJA
    ------------------------------------------------------------------

    SELECT
        estado,
        id_sucursal,
        id_empresa,
        id_usuario
    INTO
        v_sesion_estado,
        v_sesion_sucursal,
        v_sesion_empresa,
        v_sesion_usuario
    FROM comercio.t_caja_sesion
    WHERE id_sesion_caja = p_id_sesion_caja
    FOR UPDATE;

    IF v_sesion_estado IS NULL THEN
        RETURN json_build_object(
            'success', false,
            'error', 'SESION_NO_ENCONTRADA',
            'message', 'La sesión de caja no existe.'
        );
    END IF;

    IF v_sesion_estado <> 'ABIERTA' THEN
        RETURN json_build_object(
            'success', false,
            'error', 'SESION_CERRADA',
            'message', 'La sesión de caja no está abierta.'
        );
    END IF;

    IF v_sesion_sucursal <> p_id_sucursal THEN
        RETURN json_build_object(
            'success', false,
            'error', 'SUCURSAL_INVALIDA',
            'message', 'La sesión de caja no pertenece a la sucursal seleccionada.'
        );
    END IF;

    IF v_sesion_empresa <> p_id_empresa THEN
        RETURN json_build_object(
            'success', false,
            'error', 'EMPRESA_INVALIDA',
            'message', 'La sesión de caja no pertenece a la empresa seleccionada.'
        );
    END IF;


    ------------------------------------------------------------------
    -- 2. VALIDAR RESERVA SI LA VENTA PROVIENE DE UNA
    ------------------------------------------------------------------

    IF p_id_reserva IS NOT NULL THEN

        SELECT
            estado,
            id_cliente,
            id_sucursal,
            id_venta
        INTO
            v_reserva_estado,
            v_reserva_cliente,
            v_reserva_sucursal,
            v_reserva_venta
        FROM comercio.t_reserva
        WHERE id_reserva = p_id_reserva
        FOR UPDATE;

        IF v_reserva_estado IS NULL THEN
            RETURN json_build_object(
                'success', false,
                'error', 'RESERVA_NO_ENCONTRADA',
                'message', 'La reserva indicada no existe.'
            );
        END IF;

        IF v_reserva_estado <> 'PENDIENTE' THEN
            RETURN json_build_object(
                'success', false,
                'error', 'RESERVA_NO_DISPONIBLE',
                'message',
                    'La reserva no puede ser procesada porque su estado actual es '
                    || v_reserva_estado || '.'
            );
        END IF;

        IF v_reserva_sucursal <> p_id_sucursal THEN
            RETURN json_build_object(
                'success', false,
                'error', 'SUCURSAL_RESERVA_INVALIDA',
                'message',
                'La reserva pertenece a una sucursal diferente a la sesión de caja.'
            );
        END IF;

        IF v_reserva_venta IS NOT NULL THEN
            RETURN json_build_object(
                'success', false,
                'error', 'RESERVA_YA_VINCULADA',
                'message',
                'La reserva ya tiene una venta asociada.'
            );
        END IF;

        IF v_reserva_cliente IS NOT NULL
           AND p_id_cliente IS NOT NULL
           AND v_reserva_cliente <> p_id_cliente THEN

            RETURN json_build_object(
                'success', false,
                'error', 'CLIENTE_RESERVA_INVALIDO',
                'message',
                'El cliente seleccionado no corresponde al cliente de la reserva.'
            );
        END IF;

        IF v_reserva_cliente IS NOT NULL
           AND p_id_cliente IS NULL THEN

            p_id_cliente := v_reserva_cliente;

        END IF;

    END IF;


    ------------------------------------------------------------------
    -- 3. VALIDAR ITEMS
    ------------------------------------------------------------------

    IF p_items IS NULL
       OR json_array_length(p_items) = 0 THEN

        RETURN json_build_object(
            'success', false,
            'error', 'ITEMS_VACIOS',
            'message', 'Debe existir al menos un producto en la venta.'
        );

    END IF;


    ------------------------------------------------------------------
    -- 4. VALIDAR PRODUCTOS Y CALCULAR SUBTOTAL
    --
    -- Esta primera pasada NO modifica inventario.
    -- Así evitamos descontar stock y después descubrir un error.
    ------------------------------------------------------------------

    FOR v_item IN
        SELECT value
        FROM json_array_elements(p_items)
    LOOP

        v_id_variante :=
            (v_item ->> 'id_variante')::INT;

        v_cantidad :=
            (v_item ->> 'cantidad')::INT;

        IF v_id_variante IS NULL THEN
            RETURN json_build_object(
                'success', false,
                'error', 'VARIANTE_INVALIDA',
                'message', 'Uno de los productos no tiene una variante válida.'
            );
        END IF;

        IF v_cantidad IS NULL OR v_cantidad <= 0 THEN
            RETURN json_build_object(
                'success', false,
                'error', 'CANTIDAD_INVALIDA',
                'message',
                'La cantidad de cada producto debe ser mayor a 0.'
            );
        END IF;

        SELECT
            COALESCE(v.precio, p.precio),
            p.nombre,
            p.codigo_producto
        INTO
            v_precio_unit,
            v_producto_nombre,
            v_codigo_producto
        FROM comercio.t_producto_talla_color v
        JOIN comercio.t_producto p
            ON p.id_producto = v.id_producto
        WHERE v.id_variante = v_id_variante
          AND p.id_empresa = p_id_empresa
          AND v.activo = TRUE
          AND p.activo = TRUE;

        IF v_precio_unit IS NULL THEN
            RETURN json_build_object(
                'success', false,
                'error', 'PRODUCTO_NO_VALIDO',
                'message',
                'La variante ' || v_id_variante ||
                ' no existe, está inactiva o no pertenece a la empresa.'
            );
        END IF;


        ------------------------------------------------------------------
        -- SI ES UNA VENTA DE RESERVA:
        -- VALIDAR QUE LA VARIANTE PERTENEZCA A LA RESERVA
        ------------------------------------------------------------------

        IF p_id_reserva IS NOT NULL THEN

            SELECT COALESCE(SUM(dr.cantidad), 0)
            INTO v_cantidad_reservada
            FROM comercio.t_detalle_reserva dr
            WHERE dr.id_reserva = p_id_reserva
              AND dr.id_variante = v_id_variante
              AND dr.estado_prenda = 'RESERVADA';

            IF v_cantidad_reservada < v_cantidad THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'CANTIDAD_RESERVA_INVALIDA',
                    'message',
                    'La cantidad solicitada para la variante '
                    || v_id_variante
                    || ' supera la cantidad reservada.',
                    'cantidad_reservada', v_cantidad_reservada,
                    'cantidad_solicitada', v_cantidad
                );
            END IF;

        END IF;


        v_subtotal_item :=
            v_precio_unit * v_cantidad;

        v_subtotal_calc :=
            v_subtotal_calc + v_subtotal_item;

        v_items_count :=
            v_items_count + v_cantidad;

    END LOOP;


    ------------------------------------------------------------------
    -- 5. VALIDAR DESCUENTO
    ------------------------------------------------------------------

    IF v_descuento_aplicado < 0 THEN
        RETURN json_build_object(
            'success', false,
            'error', 'DESCUENTO_INVALIDO',
            'message', 'El descuento no puede ser negativo.'
        );
    END IF;

    IF v_descuento_aplicado > v_subtotal_calc THEN
        RETURN json_build_object(
            'success', false,
            'error', 'DESCUENTO_INVALIDO',
            'message',
            'El descuento no puede ser mayor al subtotal.'
        );
    END IF;

    v_total_calc :=
        v_subtotal_calc - v_descuento_aplicado;


    ------------------------------------------------------------------
    -- 6. VALIDAR INVENTARIO
    --
    -- Venta normal:
    --   stock_actual     - cantidad
    --   stock_disponible - cantidad
    --
    -- Venta de reserva:
    --   stock_actual     - cantidad
    --   stock_reservado  - cantidad
    --   stock_disponible NO cambia
    ------------------------------------------------------------------

    FOR v_item IN
        SELECT value
        FROM json_array_elements(p_items)
    LOOP

        v_id_variante :=
            (v_item ->> 'id_variante')::INT;

        v_cantidad :=
            (v_item ->> 'cantidad')::INT;

        SELECT
            id_inventario,
            stock_actual,
            stock_reservado,
            stock_disponible
        INTO
            v_id_inv,
            v_stk_actual,
            v_stk_reservado,
            v_stk_disp
        FROM comercio.t_inventario
        WHERE id_sucursal = p_id_sucursal
          AND id_variante = v_id_variante
        FOR UPDATE;

        IF v_id_inv IS NULL THEN
            RETURN json_build_object(
                'success', false,
                'error', 'INVENTARIO_NO_ENCONTRADO',
                'message',
                'No existe inventario para la variante '
                || v_id_variante
                || ' en la sucursal seleccionada.'
            );
        END IF;


        ------------------------------------------------------------------
        -- VENTA DE RESERVA
        ------------------------------------------------------------------

        IF p_id_reserva IS NOT NULL THEN

            IF v_stk_reservado < v_cantidad THEN
                RETURN json_build_object(
                    'success', false,
                    'error', 'STOCK_RESERVADO_INSUFICIENTE',
                    'message',
                    'El stock reservado es insuficiente para completar la venta.',
                    'id_variante', v_id_variante,
                    'stock_reservado', v_stk_reservado,
                    'cantidad_solicitada', v_cantidad
                );
            END IF;

        ELSE

            ------------------------------------------------------------------
            -- VENTA POS NORMAL
            ------------------------------------------------------------------

            IF v_stk_disp < v_cantidad THEN

                SELECT p.nombre
                INTO v_producto_nombre
                FROM comercio.t_producto_talla_color v
                JOIN comercio.t_producto p
                    ON p.id_producto = v.id_producto
                WHERE v.id_variante = v_id_variante;

                RETURN json_build_object(
                    'success', false,
                    'error', 'STOCK_INSUFICIENTE',
                    'message',
                    'Stock insuficiente para '
                    || COALESCE(v_producto_nombre, 'el producto')
                    || '. Disponible: '
                    || v_stk_disp
                    || ', solicitado: '
                    || v_cantidad,
                    'id_variante', v_id_variante,
                    'stock_disponible', v_stk_disp,
                    'cantidad_solicitada', v_cantidad
                );

            END IF;

        END IF;

    END LOOP;


    ------------------------------------------------------------------
    -- 7. GENERAR NÚMERO DE VENTA
    ------------------------------------------------------------------

    v_numero_venta :=
        'VTA-'
        || TO_CHAR(CURRENT_TIMESTAMP, 'YYYYMMDDHH24MISS')
        || '-'
        || LPAD(
            FLOOR(RANDOM() * 10000)::INT::TEXT,
            4,
            '0'
        );


    ------------------------------------------------------------------
    -- 8. CREAR VENTA
    ------------------------------------------------------------------

    INSERT INTO comercio.t_venta (
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
    )
    VALUES (
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
        COALESCE(
            p_observacion,
            CASE
                WHEN p_id_reserva IS NOT NULL
                THEN 'Venta presencial proveniente de reserva'
                ELSE 'Venta presencial POS'
            END
        ),
        p_id_empresa,
        p_id_sesion_caja,
        'COMPROBANTE'
    )
    RETURNING id_venta
    INTO v_id_venta;


    ------------------------------------------------------------------
    -- 9. CREAR DETALLES DE VENTA
    ------------------------------------------------------------------

    FOR v_item IN
        SELECT value
        FROM json_array_elements(p_items)
    LOOP

        v_id_variante :=
            (v_item ->> 'id_variante')::INT;

        v_cantidad :=
            (v_item ->> 'cantidad')::INT;

        SELECT
            COALESCE(v.precio, p.precio)
        INTO
            v_precio_unit
        FROM comercio.t_producto_talla_color v
        JOIN comercio.t_producto p
            ON p.id_producto = v.id_producto
        WHERE v.id_variante = v_id_variante
          AND p.id_empresa = p_id_empresa
          AND v.activo = TRUE
          AND p.activo = TRUE;

        v_subtotal_item :=
            v_precio_unit * v_cantidad;

        INSERT INTO comercio.t_detalle_venta (
            id_venta,
            id_variante,
            cantidad,
            precio_unitario,
            descuento,
            subtotal
        )
        VALUES (
            v_id_venta,
            v_id_variante,
            v_cantidad,
            v_precio_unit,
            0.00,
            v_subtotal_item
        );

    END LOOP;


    ------------------------------------------------------------------
    -- 10. DESCONTAR INVENTARIO
    ------------------------------------------------------------------

    FOR v_item IN
        SELECT value
        FROM json_array_elements(p_items)
    LOOP

        v_id_variante :=
            (v_item ->> 'id_variante')::INT;

        v_cantidad :=
            (v_item ->> 'cantidad')::INT;


        SELECT
            id_inventario,
            stock_actual,
            stock_reservado,
            stock_disponible
        INTO
            v_id_inv,
            v_stk_actual,
            v_stk_reservado,
            v_stk_disp
        FROM comercio.t_inventario
        WHERE id_sucursal = p_id_sucursal
          AND id_variante = v_id_variante
        FOR UPDATE;


        ------------------------------------------------------------------
        -- VENTA DE RESERVA
        ------------------------------------------------------------------

        IF p_id_reserva IS NOT NULL THEN

            v_nuevo_actual :=
                v_stk_actual - v_cantidad;

            v_nuevo_reservado :=
                v_stk_reservado - v_cantidad;

            UPDATE comercio.t_inventario
            SET stock_actual = v_nuevo_actual,
                stock_reservado = v_nuevo_reservado,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_inventario = v_id_inv;


            INSERT INTO comercio.t_movimiento_inventario (
                id_inventario,
                id_usuario,
                tipo_movimiento,
                cantidad,
                stock_anterior,
                stock_nuevo,
                motivo,
                fecha_movimiento
            )
            VALUES (
                v_id_inv,
                p_id_usuario,
                'SALIDA',
                v_cantidad,
                v_stk_actual,
                v_nuevo_actual,
                'Venta presencial POS - Reserva ' || p_id_reserva,
                CURRENT_TIMESTAMP
            );


        ELSE

            ------------------------------------------------------------------
            -- VENTA POS NORMAL
            ------------------------------------------------------------------

            v_nuevo_actual :=
                v_stk_actual - v_cantidad;

            v_nuevo_disp :=
                v_stk_disp - v_cantidad;

            UPDATE comercio.t_inventario
            SET stock_actual = v_nuevo_actual,
                stock_disponible = v_nuevo_disp,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_inventario = v_id_inv;


            INSERT INTO comercio.t_movimiento_inventario (
                id_inventario,
                id_usuario,
                tipo_movimiento,
                cantidad,
                stock_anterior,
                stock_nuevo,
                motivo,
                fecha_movimiento
            )
            VALUES (
                v_id_inv,
                p_id_usuario,
                'SALIDA',
                v_cantidad,
                v_stk_actual,
                v_nuevo_actual,
                'Venta presencial POS',
                CURRENT_TIMESTAMP
            );

        END IF;

    END LOOP;


    ------------------------------------------------------------------
    -- 11. VINCULAR LA VENTA CON LA RESERVA
    ------------------------------------------------------------------

    IF p_id_reserva IS NOT NULL THEN

        UPDATE comercio.t_reserva
        SET id_venta = v_id_venta
        WHERE id_reserva = p_id_reserva;

    END IF;


    ------------------------------------------------------------------
    -- 12. RETORNAR RESULTADO
    ------------------------------------------------------------------

    RETURN json_build_object(
        'success', true,
        'message',
        CASE
            WHEN p_id_reserva IS NOT NULL
            THEN 'Venta de reserva registrada exitosamente. Pendiente de cobro en caja (W28).'
            ELSE 'Venta registrada exitosamente. Pendiente de cobro en caja (W28).'
        END,
        'id_venta', v_id_venta,
        'numero_venta', v_numero_venta,
        'id_cliente', p_id_cliente,
        'id_sucursal', p_id_sucursal,
        'id_empresa', p_id_empresa,
        'id_reserva', p_id_reserva,
        'items_count', v_items_count,
        'subtotal', v_subtotal_calc,
        'descuento', v_descuento_aplicado,
        'total', v_total_calc,
        'estado', 'PENDIENTE_PAGO',
        'id_sesion_caja', p_id_sesion_caja
    );


EXCEPTION
    WHEN OTHERS THEN

        RETURN json_build_object(
            'success', false,
            'error', 'ERROR_REGISTRANDO_VENTA',
            'message', SQLERRM
        );

END;
$function$
;

CREATE OR REPLACE FUNCTION comercio.fn_reservar_stock(p_id_sucursal integer, p_id_variante integer, p_cantidad integer, p_id_usuario integer)
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
            FROM comercio.t_inventario
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

            UPDATE comercio.t_inventario
            SET stock_reservado = v_nuevo_reservado,
                stock_disponible = v_nuevo_disponible,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_inventario = v_id_inventario;

            INSERT INTO comercio.t_movimiento_inventario (
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
;