-- Read-only snapshot, 2026-10-31. Source SHA-256: bcc907172bfce97f9d6827941f91f7fd0071112a995d588ed758a027792c7fa5
-- Only schema qualifiers are substituted for isolated integration tests.
CREATE OR REPLACE FUNCTION __SCHEMA__.fn_registrar_venta_pos(p_id_sesion_caja integer, p_id_usuario integer, p_id_sucursal integer, p_id_empresa integer, p_id_cliente integer, p_items json, p_descuento numeric, p_observacion text, p_id_reserva integer DEFAULT NULL::integer)
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
    FROM __SCHEMA__.t_caja_sesion
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
        FROM __SCHEMA__.t_reserva
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
        FROM __SCHEMA__.t_producto_talla_color v
        JOIN __SCHEMA__.t_producto p
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
            FROM __SCHEMA__.t_detalle_reserva dr
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
        FROM __SCHEMA__.t_inventario
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
                FROM __SCHEMA__.t_producto_talla_color v
                JOIN __SCHEMA__.t_producto p
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

    INSERT INTO __SCHEMA__.t_venta (
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
        FROM __SCHEMA__.t_producto_talla_color v
        JOIN __SCHEMA__.t_producto p
            ON p.id_producto = v.id_producto
        WHERE v.id_variante = v_id_variante
          AND p.id_empresa = p_id_empresa
          AND v.activo = TRUE
          AND p.activo = TRUE;

        v_subtotal_item :=
            v_precio_unit * v_cantidad;

        INSERT INTO __SCHEMA__.t_detalle_venta (
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
        FROM __SCHEMA__.t_inventario
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

            UPDATE __SCHEMA__.t_inventario
            SET stock_actual = v_nuevo_actual,
                stock_reservado = v_nuevo_reservado,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_inventario = v_id_inv;


            INSERT INTO __SCHEMA__.t_movimiento_inventario (
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

            UPDATE __SCHEMA__.t_inventario
            SET stock_actual = v_nuevo_actual,
                stock_disponible = v_nuevo_disp,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_inventario = v_id_inv;


            INSERT INTO __SCHEMA__.t_movimiento_inventario (
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

        UPDATE __SCHEMA__.t_reserva
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

