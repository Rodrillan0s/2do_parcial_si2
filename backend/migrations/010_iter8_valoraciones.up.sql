-- Migración 010 (UP): Sistema de Valoración de Calidad y Servicio (Prendas y Servicios)
-- Soporta Flujo Normal (1 a 5 estrellas), Flujo A1 (sin registros basura) y Flujo A2 (1 estrella crítica con revisión administrativa)

CREATE TABLE IF NOT EXISTS __SCHEMA__.t_valoracion (
    id_valoracion          SERIAL PRIMARY KEY,
    id_empresa             INT NOT NULL REFERENCES __SCHEMA__.empresa(id_empresa),
    id_sucursal            INT REFERENCES __SCHEMA__.t_sucursal(id_sucursal),
    id_cliente             INT NOT NULL REFERENCES __SCHEMA__.t_cliente(id_cliente),
    id_producto            INT REFERENCES __SCHEMA__.t_producto(id_producto),
    id_venta               INT REFERENCES __SCHEMA__.t_venta(id_venta),
    id_pedido              INT REFERENCES __SCHEMA__.t_pedido(id_pedido),
    id_reserva             INT REFERENCES __SCHEMA__.t_reserva(id_reserva),
    puntuacion             INT NOT NULL CHECK (puntuacion BETWEEN 1 AND 5),
    comentario             TEXT,
    motivo_negativo        VARCHAR(150),
    requiere_revision      BOOLEAN NOT NULL DEFAULT FALSE,
    atendido               BOOLEAN NOT NULL DEFAULT FALSE,
    notas_admin            TEXT,
    fecha_creacion         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_valoracion_empresa ON __SCHEMA__.t_valoracion(id_empresa);
CREATE INDEX IF NOT EXISTS idx_valoracion_producto ON __SCHEMA__.t_valoracion(id_producto) WHERE id_producto IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_valoracion_cliente ON __SCHEMA__.t_valoracion(id_cliente);
CREATE INDEX IF NOT EXISTS idx_valoracion_revision ON __SCHEMA__.t_valoracion(id_empresa, requiere_revision) WHERE requiere_revision = TRUE;

-- Prevenir valoraciones duplicadas por la misma venta/pedido y producto
CREATE UNIQUE INDEX IF NOT EXISTS uq_val_cli_venta_prod 
ON __SCHEMA__.t_valoracion(id_cliente, id_venta, id_producto) 
WHERE id_venta IS NOT NULL AND id_producto IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_val_cli_pedido_prod 
ON __SCHEMA__.t_valoracion(id_cliente, id_pedido, id_producto) 
WHERE id_pedido IS NOT NULL AND id_producto IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_val_cli_reserva 
ON __SCHEMA__.t_valoracion(id_cliente, id_reserva) 
WHERE id_reserva IS NOT NULL;
