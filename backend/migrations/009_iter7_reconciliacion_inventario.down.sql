-- Migración 009 (DOWN): Reversión de la conciliación de inventario
-- Restaura los valores exactos a partir de la tabla de respaldo.

UPDATE __SCHEMA__.t_inventario inv
SET stock_disponible = bkp.stock_disponible_antiguo,
    fecha_actualizacion = CURRENT_TIMESTAMP
FROM __SCHEMA__.t_inventario_conciliacion_backup_009 bkp
WHERE inv.id_inventario = bkp.id_inventario;

DROP TABLE IF EXISTS __SCHEMA__.t_inventario_conciliacion_backup_009;
