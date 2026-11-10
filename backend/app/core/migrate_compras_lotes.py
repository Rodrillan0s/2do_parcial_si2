from app.core.postgres import PostgreSQL
from app.core.config import Config

def migrar_tablas_compras_lotes():
    """
    Crea las tablas requeridas para el flujo de compras, lotes e importación
    masiva de inventario en el esquema comercio.
    """
    db = PostgreSQL()
    db.create_connection()
    try:
        schema = Config.SCHEMA or 'comercio'

        # 1. Tabla de Órdenes de Compra (Procurement)
        q_orden_compra = f"""
        CREATE TABLE IF NOT EXISTS {schema}.t_orden_compra (
            id_orden_compra SERIAL PRIMARY KEY,
            id_empresa INT NOT NULL REFERENCES {schema}.empresa(id_empresa) ON DELETE CASCADE,
            id_sucursal INT NOT NULL REFERENCES {schema}.t_sucursal(id_sucursal),
            id_proveedor INT REFERENCES {schema}.t_proveedor(id_proveedor),
            numero_orden VARCHAR(50) NOT NULL,
            fecha_emision TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_entrega_esperada DATE,
            estado VARCHAR(30) DEFAULT 'PENDIENTE_APROBACION',
            total_estimado NUMERIC(12,2) DEFAULT 0.0,
            observaciones TEXT,
            id_usuario_creador INT REFERENCES {schema}.t_usuario(id_usuario),
            id_usuario_aprobador INT REFERENCES {schema}.t_usuario(id_usuario),
            fecha_aprobacion TIMESTAMP,
            motivo_rechazo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_orden_compra_tenant ON {schema}.t_orden_compra(id_empresa, id_sucursal);
        CREATE INDEX IF NOT EXISTS idx_orden_compra_estado ON {schema}.t_orden_compra(estado);
        """
        db.execute_query(q_orden_compra, commit=True)

        # 2. Tabla de Detalle de Orden de Compra
        q_detalle_orden = f"""
        CREATE TABLE IF NOT EXISTS {schema}.t_detalle_orden_compra (
            id_detalle_orden SERIAL PRIMARY KEY,
            id_orden_compra INT NOT NULL REFERENCES {schema}.t_orden_compra(id_orden_compra) ON DELETE CASCADE,
            id_producto INT REFERENCES {schema}.t_producto(id_producto),
            id_variante INT REFERENCES {schema}.t_producto_talla_color(id_variante),
            codigo_producto VARCHAR(100),
            nombre_producto VARCHAR(255),
            talla VARCHAR(50),
            color VARCHAR(50),
            sku VARCHAR(100),
            cantidad_solicitada INT NOT NULL DEFAULT 1,
            cantidad_recibida INT DEFAULT 0,
            costo_unitario NUMERIC(10,2) NOT NULL DEFAULT 0.0,
            subtotal NUMERIC(12,2) NOT NULL DEFAULT 0.0
        );
        CREATE INDEX IF NOT EXISTS idx_detalle_orden_compra ON {schema}.t_detalle_orden_compra(id_orden_compra);
        """
        db.execute_query(q_detalle_orden, commit=True)

        # 3. Tabla de Lotes de Ingreso de Mercadería
        q_lote = f"""
        CREATE TABLE IF NOT EXISTS {schema}.t_lote (
            id_lote SERIAL PRIMARY KEY,
            id_empresa INT NOT NULL REFERENCES {schema}.empresa(id_empresa) ON DELETE CASCADE,
            id_sucursal INT NOT NULL REFERENCES {schema}.t_sucursal(id_sucursal),
            id_orden_compra INT REFERENCES {schema}.t_orden_compra(id_orden_compra),
            id_proveedor INT REFERENCES {schema}.t_proveedor(id_proveedor),
            numero_lote VARCHAR(100) NOT NULL,
            fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            guia_remision VARCHAR(100),
            total_prendas INT DEFAULT 0,
            costo_total_lote NUMERIC(12,2) DEFAULT 0.0,
            id_usuario_receptor INT REFERENCES {schema}.t_usuario(id_usuario),
            observaciones TEXT,
            archivo_importado VARCHAR(255)
        );
        CREATE INDEX IF NOT EXISTS idx_lote_tenant ON {schema}.t_lote(id_empresa, id_sucursal);
        CREATE INDEX IF NOT EXISTS idx_lote_numero ON {schema}.t_lote(numero_lote);
        """
        db.execute_query(q_lote, commit=True)

        return True
    finally:
        db.close_connection()

if __name__ == '__main__':
    migrar_tablas_compras_lotes()
    print("Migración de tablas de compras y lotes completada con éxito.")
