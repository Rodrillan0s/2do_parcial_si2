-- Explicit and reversible performance index migration for Iteration 1 SaaS.
-- __SCHEMA__ is validated and quoted by backend/migrate.py.
-- Evaluates write/lock impact: uses btree composite indexes aligned with real tenant/catalog/inventory queries.

CREATE INDEX IF NOT EXISTS idx_iter1_sucursal_empresa_activo
    ON __SCHEMA__.t_sucursal (id_empresa, activo, estado);

DO $$
BEGIN
    IF to_regclass('__SCHEMA__.t_producto') IS NOT NULL THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_producto_empresa_activo_id ON __SCHEMA__.t_producto (id_empresa, activo, id_producto DESC)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_producto_empresa_categoria ON __SCHEMA__.t_producto (id_empresa, id_categoria)';
    END IF;

    IF to_regclass('__SCHEMA__.t_producto_imagen') IS NOT NULL THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_producto_imagen_lookup ON __SCHEMA__.t_producto_imagen (id_producto, es_principal DESC, id_imagen ASC)';
    END IF;

    IF to_regclass('__SCHEMA__.t_producto_talla_color') IS NOT NULL THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_variante_producto_activo ON __SCHEMA__.t_producto_talla_color (id_producto, activo, id_variante)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_variante_talla ON __SCHEMA__.t_producto_talla_color (id_talla)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_variante_color ON __SCHEMA__.t_producto_talla_color (id_color)';
    END IF;

    IF to_regclass('__SCHEMA__.t_inventario') IS NOT NULL THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_inventario_sucursal_variante ON __SCHEMA__.t_inventario (id_sucursal, id_variante)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_inventario_variante_sucursal ON __SCHEMA__.t_inventario (id_variante, id_sucursal)';
    END IF;

    IF to_regclass('__SCHEMA__.t_categoria') IS NOT NULL THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_categoria_empresa_activo ON __SCHEMA__.t_categoria (id_empresa, activo)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_categoria_padre ON __SCHEMA__.t_categoria (id_padre)';
    END IF;

    IF to_regclass('__SCHEMA__.t_talla') IS NOT NULL THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_talla_empresa_activo ON __SCHEMA__.t_talla (id_empresa, activo)';
    END IF;

    IF to_regclass('__SCHEMA__.t_color') IS NOT NULL THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_iter1_color_empresa_activo ON __SCHEMA__.t_color (id_empresa, activo)';
    END IF;
END $$;

