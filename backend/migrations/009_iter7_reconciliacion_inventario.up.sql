-- Migración 009 (UP): Conciliación histórica de saldos de inventario en t_inventario
-- Crea tabla de respaldo para total reversibilidad antes de ajustar la consistencia matemática.

DO $$
DECLARE
    v_has_contingencia BOOLEAN;
    v_schema TEXT;
BEGIN
    v_schema := REPLACE('__SCHEMA__', '"', '');

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = v_schema AND table_name = 't_inventario' AND column_name = 'stock_contingencia'
    ) INTO v_has_contingencia;

    -- 1. Crear tabla de respaldo con snapshot de los saldos anteriores
    CREATE TABLE IF NOT EXISTS __SCHEMA__.t_inventario_conciliacion_backup_009 (
        id_backup SERIAL PRIMARY KEY,
        id_inventario INT NOT NULL,
        stock_actual_antiguo INT NOT NULL,
        stock_reservado_antiguo INT NOT NULL,
        stock_disponible_antiguo INT NOT NULL,
        fecha_respaldo TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    IF v_has_contingencia THEN
        EXECUTE '
            INSERT INTO __SCHEMA__.t_inventario_conciliacion_backup_009 (
                id_inventario, stock_actual_antiguo, stock_reservado_antiguo, stock_disponible_antiguo
            )
            SELECT id_inventario, stock_actual, stock_reservado, stock_disponible
            FROM __SCHEMA__.t_inventario
            WHERE stock_disponible != GREATEST(0, stock_actual - stock_reservado - COALESCE(stock_contingencia, 0));

            UPDATE __SCHEMA__.t_inventario
            SET stock_disponible = GREATEST(0, stock_actual - stock_reservado - COALESCE(stock_contingencia, 0)),
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE stock_disponible != GREATEST(0, stock_actual - stock_reservado - COALESCE(stock_contingencia, 0));
        ';
    ELSE
        EXECUTE '
            INSERT INTO __SCHEMA__.t_inventario_conciliacion_backup_009 (
                id_inventario, stock_actual_antiguo, stock_reservado_antiguo, stock_disponible_antiguo
            )
            SELECT id_inventario, stock_actual, stock_reservado, stock_disponible
            FROM __SCHEMA__.t_inventario
            WHERE stock_disponible != GREATEST(0, stock_actual - stock_reservado);

            UPDATE __SCHEMA__.t_inventario
            SET stock_disponible = GREATEST(0, stock_actual - stock_reservado),
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE stock_disponible != GREATEST(0, stock_actual - stock_reservado);
        ';
    END IF;
END $$;
