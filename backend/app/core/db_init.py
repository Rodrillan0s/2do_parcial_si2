from app.core.postgres import PostgreSQL
from app.core.config import Config

# Inicializa el esquema comercio y las tablas de seguridad sobre las tablas existentes t_usuario y t_rol.
def inicializar_tablas_seguridad():
    db = PostgreSQL()
    try:
        db.create_connection()
        if not db.conn:
            return

        schema = Config.SCHEMA or 'comercio'

        # 1. Asegurar columnas en t_rol y sembrar roles requeridos
        db.execute_query(f"ALTER TABLE {schema}.t_rol ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;", commit=True)
        
        roles_default = [
            (1, 'ADMINISTRADOR', 'Administrador General'),
            (2, 'CLIENTE', 'Cliente Comprador'),
            (3, 'ADMINISTRADOR_TIENDA', 'Administrador de Tienda'),
            (4, 'ENCARGADO_SUCURSAL', 'Encargado de Sucursal'),
            (5, 'CAJERO', 'Cajero'),
            (6, 'PROVEEDOR', 'Proveedor')
        ]
        for r_id, r_nombre, r_desc in roles_default:
            res = db.execute_query(f"SELECT id_rol FROM {schema}.t_rol WHERE id_rol = %s OR LOWER(nombre) = LOWER(%s);", (r_id, r_nombre), fetchone=True)
            if not res:
                db.execute_query(f"INSERT INTO {schema}.t_rol (id_rol, nombre, descripcion) VALUES (%s, %s, %s);", (r_id, r_nombre, r_desc), commit=True)
            else:
                db.execute_query(f"UPDATE {schema}.t_rol SET nombre = %s, descripcion = %s WHERE id_rol = %s;", (r_nombre, r_desc, res[0]), commit=True)

        # 2. Tabla t_seguridad_usuario vinculada a t_usuario(id_usuario)
        query_seguridad = f"""
        CREATE TABLE IF NOT EXISTS {schema}.t_seguridad_usuario (
            id_seguridad SERIAL PRIMARY KEY,
            id_usuario INT UNIQUE NOT NULL REFERENCES {schema}.t_usuario(id_usuario) ON DELETE CASCADE,
            intentos_fallidos INT DEFAULT 0 NOT NULL,
            bloqueado_hasta TIMESTAMP,
            codigo_recuperacion VARCHAR(10),
            codigo_recuperacion_expira TIMESTAMP,
            codigo_verificacion_dispositivo VARCHAR(10),
            codigo_dispositivo_expira TIMESTAMP,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        db.execute_query(query_seguridad, commit=True)

        # 3. Tabla t_dispositivo_usuario vinculada a t_usuario(id_usuario)
        query_dispositivos = f"""
        CREATE TABLE IF NOT EXISTS {schema}.t_dispositivo_usuario (
            id_dispositivo SERIAL PRIMARY KEY,
            id_usuario INT NOT NULL REFERENCES {schema}.t_usuario(id_usuario) ON DELETE CASCADE,
            device_fingerprint VARCHAR(255) NOT NULL,
            nombre_dispositivo VARCHAR(150),
            ip_address VARCHAR(45),
            verificado BOOLEAN DEFAULT TRUE NOT NULL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultima_conexion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_t_usuario_dispositivo UNIQUE (id_usuario, device_fingerprint)
        );
        """
        db.execute_query(query_dispositivos, commit=True)

        # 4. Tabla t_notificacion para notificaciones y alertas
        query_notificacion = f"""
        CREATE TABLE IF NOT EXISTS {schema}.t_notificacion (
            id_notificacion SERIAL PRIMARY KEY,
            titulo VARCHAR(255) NOT NULL,
            cuerpo TEXT NOT NULL,
            tipo_referencia VARCHAR(100) DEFAULT 'SISTEMA',
            nro_usuario INT NOT NULL REFERENCES {schema}.t_usuario(id_usuario) ON DELETE CASCADE,
            leido BOOLEAN DEFAULT FALSE,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            nro_emergencia INT
        );
        """
        db.execute_query(query_notificacion, commit=True)

        # 5. Función PostgreSQL fn_reservar_stock para control de concurrencia en reservas
        query_fn_reserva = f"""
        CREATE OR REPLACE FUNCTION {schema}.fn_reservar_stock(
            p_id_sucursal INT,
            p_id_variante INT,
            p_cantidad INT,
            p_id_usuario INT
        )
        RETURNS JSON AS $$
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
            FROM {schema}.t_inventario
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

            UPDATE {schema}.t_inventario
            SET stock_reservado = v_nuevo_reservado,
                stock_disponible = v_nuevo_disponible,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_inventario = v_id_inventario;

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
        $$ LANGUAGE plpgsql;
        """
        db.execute_query(query_fn_reserva, commit=True)

        # 6. Función PostgreSQL fn_movimiento_inventario para gestión transaccional de inventario (W22 - CU22)
        query_fn_movimiento = f"""
        CREATE OR REPLACE FUNCTION {schema}.fn_movimiento_inventario(
            p_id_sucursal INT,
            p_id_variante INT,
            p_tipo_movimiento VARCHAR,
            p_cantidad INT,
            p_id_usuario INT,
            p_motivo VARCHAR
        )
        RETURNS JSON AS $$
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
            FROM {schema}.t_inventario
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
            UPDATE {schema}.t_inventario
            SET stock_actual = v_nuevo_actual,
                stock_disponible = v_nuevo_disponible,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id_inventario = v_id_inventario;

            -- 7. Registrar t_movimiento_inventario asegurando que id_usuario exista
            IF p_id_usuario IS NOT NULL AND NOT EXISTS (SELECT 1 FROM {schema}.t_usuario WHERE id_usuario = p_id_usuario) THEN
                p_id_usuario := NULL;
            END IF;

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
        $$ LANGUAGE plpgsql;
        """
        db.execute_query(query_fn_movimiento, commit=True)

        # 9. Migración de pago y comprobante W27/W29
        try:
            from app.core.migrate_pago_cu27_cu29 import migrar_pago_comprobante
            migrar_pago_comprobante()
        except Exception as err_pago:
            print(f"Aviso inicializando W27/W29 en db_init: {err_pago}")
    except Exception as e:
        raise e
    finally:
        db.close_connection()


