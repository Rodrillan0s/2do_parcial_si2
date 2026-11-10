import logging
from app.core.postgres import PostgreSQL
from app.core.config import Config

logger = logging.getLogger(__name__)

def migrar_pago_caja_cu28_cu29():
    """
    Migración para CU28 (Pago en Caja) y CU29 (Emisión de Comprobantes POS).
    - Agrega columna correo_facturacion a t_venta.
    - Asegura métodos de pago activos (Efectivo, Tarjeta, QR).
    - Agrega permisos RBAC para pago en caja.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'

        # 1. Columna correo_facturacion en t_venta y referencia_externa en t_pago
        db.execute_query(f"""
            ALTER TABLE {schema}.t_venta 
            ADD COLUMN IF NOT EXISTS correo_facturacion VARCHAR(255);
            ALTER TABLE {schema}.t_pago
            ADD COLUMN IF NOT EXISTS referencia_externa VARCHAR(150);
        """, commit=True)
        logger.info(f"✅ Columnas correo_facturacion y referencia_externa verificadas.")

        # 2. Asegurar métodos de pago en t_metodo_pago
        db.execute_query(f"""
            INSERT INTO {schema}.t_metodo_pago (id_metodo_pago, nombre, tipo, estado)
            VALUES 
                (1, 'Tarjeta de Débito/Crédito', 'TARJETA', TRUE),
                (2, 'PayPal', 'PAYPAL', TRUE),
                (3, 'Efectivo en Caja', 'EFECTIVO', TRUE),
                (4, 'Código QR', 'QR', TRUE)
            ON CONFLICT (id_metodo_pago) DO UPDATE 
            SET nombre = EXCLUDED.nombre, tipo = EXCLUDED.tipo, estado = EXCLUDED.estado;
        """, commit=True)
        logger.info(f"✅ Métodos de pago configurados en {schema}.t_metodo_pago.")

        # 3. Permisos RBAC para pago y comprobantes en caja
        permisos = [
            ("pos.cobrar", "Cobrar Venta POS", "Permite procesar el cobro de ventas presenciales en caja", "CAJA"),
            ("comprobante.emitir", "Emitir Comprobante", "Permite emitir y enviar comprobantes de venta", "VENTAS")
        ]
        for codigo, nombre, desc, modulo in permisos:
            db.execute_query(f"""
                INSERT INTO {schema}.t_permiso (codigo, nombre, descripcion, modulo, activo)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (codigo) DO NOTHING;
            """, (codigo, nombre, desc, modulo), commit=True)

            # Asignar a roles administrativos y cajeros
            db.execute_query(f"""
                INSERT INTO {schema}.t_rol_permiso (id_rol, id_permiso)
                SELECT r.id_rol, p.id_permiso
                FROM {schema}.t_rol r
                CROSS JOIN {schema}.t_permiso p
                WHERE r.id_rol IN (1, 3, 4, 5) AND p.codigo = %s
                ON CONFLICT DO NOTHING;
            """, (codigo,), commit=True)

        logger.info("✅ Permisos RBAC pos.cobrar y comprobante.emitir registrados.")
        print("Migración CU28 y CU29 completada exitosamente.")
    except Exception as e:
        logger.error(f"Error en migración CU28/CU29: {e}")
        raise
    finally:
        db.close_connection()

if __name__ == "__main__":
    migrar_pago_caja_cu28_cu29()
