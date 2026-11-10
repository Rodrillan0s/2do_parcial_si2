import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';

export interface SucursalCheckout {
  id_sucursal: number;
  id_empresa: number;
  nombre: string;
  codigo_sucursal?: string | null;
  direccion: string;
  telefono?: string;
  correo?: string;
  horario?: string;
  ciudad: string;
  activo: boolean;
  tiene_stock_completo?: boolean;
  stock_estado?: string;
  stock_label?: string;
}

export interface CrearPedidoPayload {
  id_sucursal: number;
  modalidad_compra: 'RETIRO_SUCURSAL' | 'ENTREGA_DOMICILIO';
  nombre_contacto: string;
  telefono_contacto: string;
  correo_contacto?: string;
  direccion_entrega?: string;
  ciudad_entrega?: string;
  notas_entrega?: string;
  id_empresa?: number;
}

export interface DetallePedidoData {
  id_detalle_pedido: number;
  id_variante: number;
  cantidad: number;
  precio_unitario: number;
  subtotal: number;
  id_producto: number;
  producto_nombre: string;
  talla_nombre: string;
  color_nombre: string;
  codigo_hex: string;
  sku?: string;
  imagen_url?: string;
}

export interface PedidoData {
  id_pedido: number;
  codigo_pedido: string;
  id_cliente: number;
  id_empresa: number;
  nombre_empresa: string;
  id_sucursal: number;
  sucursal_nombre: string;
  sucursal_direccion?: string;
  sucursal_telefono?: string;
  fecha_pedido: string;
  estado: string;
  estado_pago: string;
  modalidad_compra: 'RETIRO_SUCURSAL' | 'ENTREGA_DOMICILIO';
  nombre_contacto: string;
  telefono_contacto: string;
  correo_contacto?: string;
  direccion_entrega?: string;
  ciudad_entrega?: string;
  notas_entrega?: string;
  subtotal: number;
  costo_envio: number;
  descuento: number;
  total: number;
  id_venta?: number;
  total_items: number;
  items: DetallePedidoData[];
}

export interface PedidoItemResumen {
  id_detalle_pedido: number;
  id_variante: number;
  cantidad: number;
  precio_unitario: number;
  subtotal: number;
  producto_nombre: string;
  talla_nombre: string;
  color_nombre: string;
  codigo_hex: string;
  imagen_url?: string;
}

export interface PedidoResumen {
  id_pedido: number;
  codigo_pedido: string;
  id_cliente: number;
  id_empresa: number;
  nombre_empresa: string;
  id_sucursal: number;
  sucursal_nombre: string;
  sucursal_ciudad: string;
  fecha_pedido: string;
  estado: string;
  estado_pago: string;
  modalidad_compra: string;
  subtotal: number;
  costo_envio: number;
  descuento: number;
  total: number;
  id_venta?: number;
  total_items: number;
  items_resumen: PedidoItemResumen[];
}

export interface PedidoFiltros {
  estado?: string;
  estado_pago?: string;
  fecha_inicio?: string;
  fecha_fin?: string;
  codigo?: string;
  page?: number;
  limit?: number;
  id_empresa?: number;
}

export interface RespuestaPaginadaPedidos {
  success: boolean;
  total: number;
  page: number;
  limit: number;
  total_paginas: number;
  data: PedidoResumen[];
}

@Injectable({
  providedIn: 'root'
})
export class PedidoService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/api/pedidos`;

  obtenerSucursales(idEmpresa?: number): Observable<{ success: boolean; data: SucursalCheckout[] }> {
    let params = new HttpParams();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    return this.http.get<{ success: boolean; data: SucursalCheckout[] }>(`${this.apiUrl}/sucursales`, { params });
  }

  crearPedido(datos: CrearPedidoPayload): Observable<{ success: boolean; message: string; data: PedidoData }> {
    return this.http.post<{ success: boolean; message: string; data: PedidoData }>(`${this.apiUrl}`, datos);
  }

  obtenerPedido(idPedido: number, idEmpresa?: number): Observable<{ success: boolean; data: PedidoData }> {
    let params = new HttpParams();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    return this.http.get<{ success: boolean; data: PedidoData }>(`${this.apiUrl}/${idPedido}`, { params });
  }

  obtenerMisPedidos(filtros?: PedidoFiltros): Observable<RespuestaPaginadaPedidos> {
    let params = new HttpParams();
    if (filtros) {
      if (filtros.estado && filtros.estado !== 'TODOS') params = params.set('estado', filtros.estado);
      if (filtros.estado_pago && filtros.estado_pago !== 'TODOS') params = params.set('estado_pago', filtros.estado_pago);
      if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
      if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
      if (filtros.codigo) params = params.set('codigo', filtros.codigo);
      if (filtros.page) params = params.set('page', filtros.page.toString());
      if (filtros.limit) params = params.set('limit', filtros.limit.toString());
      if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());
    }
    return this.http.get<RespuestaPaginadaPedidos>(`${this.apiUrl}`, { params });
  }

  cancelarPedido(idPedido: number, motivo?: string, idEmpresa?: number): Observable<{ success: boolean; message: string; data: any }> {
    let params = new HttpParams();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    return this.http.post<{ success: boolean; message: string; data: any }>(
      `${this.apiUrl}/${idPedido}/cancelar`,
      { motivo: motivo || 'Cancelado por el cliente' },
      { params }
    );
  }
}

