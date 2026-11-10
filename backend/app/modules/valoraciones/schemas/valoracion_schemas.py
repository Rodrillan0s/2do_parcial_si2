"""
Esquemas Pydantic para el Sistema de Valoración de Prendas y Servicios.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class CrearValoracionDTO(BaseModel):
    id_producto: Optional[int] = Field(None, description="ID del producto valorado (opcional si es solo servicio)")
    id_pedido: Optional[int] = Field(None, description="ID del pedido online asociado")
    id_venta: Optional[int] = Field(None, description="ID de la venta asociada")
    id_reserva: Optional[int] = Field(None, description="ID de la cita de vestidor/reserva asociada")
    puntuacion: int = Field(..., ge=1, le=5, description="Puntuación de 1 a 5 estrellas")
    comentario: Optional[str] = Field(None, max_length=1000, description="Comentario u opinión del cliente")
    motivo_negativo: Optional[str] = Field(None, max_length=150, description="Razón de la baja valoración (obligatorio si puntuación es 1)")
    id_empresa: Optional[int] = Field(None, description="ID del Tenant")


class AtenderValoracionDTO(BaseModel):
    notas_admin: str = Field(..., min_length=3, max_length=1000, description="Detalles del seguimiento o resolución dada al cliente")
    atendido: bool = Field(True, description="Marca la valoración como resuelta")


class ValoracionItemDTO(BaseModel):
    id_valoracion: int
    id_empresa: int
    id_sucursal: Optional[int]
    id_cliente: int
    nombre_cliente: Optional[str]
    id_producto: Optional[int]
    nombre_producto: Optional[str]
    id_pedido: Optional[int]
    codigo_pedido: Optional[str]
    id_venta: Optional[int]
    id_reserva: Optional[int]
    puntuacion: int
    comentario: Optional[str]
    motivo_negativo: Optional[str]
    requiere_revision: bool
    atendido: bool
    notas_admin: Optional[str]
    fecha_creacion: datetime


class ResumenValoracionesProductoDTO(BaseModel):
    id_producto: int
    promedio: float
    total: int
    distribucion: Dict[int, int]
    ultimas_opiniones: List[Dict[str, Any]]
