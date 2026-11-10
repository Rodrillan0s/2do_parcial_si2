-- Reversible rollback for 002_iter1_perf_indexes.
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_color_empresa_activo;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_talla_empresa_activo;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_categoria_padre;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_categoria_empresa_activo;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_inventario_variante_sucursal;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_inventario_sucursal_variante;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_variante_color;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_variante_talla;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_variante_producto_activo;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_producto_imagen_lookup;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_producto_empresa_categoria;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_producto_empresa_activo_id;
DROP INDEX IF EXISTS __SCHEMA__.idx_iter1_sucursal_empresa_activo;

