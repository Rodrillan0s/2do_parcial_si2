import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';

export interface ItemInventario {
  id_inventario: number;
  id_sucursal: number;
  sucursal_nombre: string;
  codigo_sucursal?: string;
  id_empresa: number;
  id_variante: number;
  id_producto: number;
  producto_nombre: string;
  codigo_producto?: string;
  imagen_url?: string;
  marca?: string;
  sku: string;
  codigo_barras?: string;
  precio: number;
  id_talla?: number;
  talla_nombre: string;
  id_color?: number;
  color_nombre: string;
  color_hex: string;
  stock_actual: number;
  stock_reservado: number;
  stock_disponible: number;
  stock_minimo: number;
  estado: boolean;
  fecha_actualizacion?: string;
  semaforo: 'NORMAL' | 'BAJO_STOCK' | 'SIN_STOCK';
}

export interface ResumenInventario {
  total_posiciones: number;
  total_actual: number;
  total_reservado: number;
  total_disponible: number;
  total_bajo_stock: number;
  total_sin_stock: number;
}

export interface InventarioResponse {
  success: boolean;
  items: ItemInventario[];
  total: number;
  pagina: number;
  limite: number;
  total_paginas: number;
  resumen: ResumenInventario;
  message?: string;
}

export interface MovimientoInventario {
  id_movimiento: number;
  id_inventario: number;
  id_usuario?: number;
  usuario_nombre: string;
  tipo_movimiento: 'ENTRADA' | 'SALIDA' | 'AJUSTE' | 'RESERVA' | string;
  cantidad: number;
  stock_anterior: number;
  stock_nuevo: number;
  motivo: string;
  fecha_movimiento: string;
  id_sucursal: number;
  sucursal_nombre: string;
  id_variante: number;
  producto_nombre: string;
  sku: string;
  talla_nombre: string;
  color_nombre: string;
  imagen_url?: string;
}

export interface MovimientoPayload {
  id_sucursal: number;
  id_variante: number;
  tipo_movimiento: 'ENTRADA' | 'SALIDA' | 'AJUSTE';
  cantidad: number;
  motivo: string;
}

export interface FiltrosInventario {
  id_sucursal?: number | string | null;
  id_producto?: number | string | null;
  id_variante?: number | string | null;
  id_talla?: number | string | null;
  id_color?: number | string | null;
  id_empresa?: number | string | null;
  estado?: string | boolean | null;
  filtro_stock?: 'bajo_stock' | 'sin_stock' | 'disponible' | '' | null;
  busqueda?: string | null;
  pagina?: number;
  limite?: number;
}

export interface FiltrosMovimientos {
  id_inventario?: number | null;
  id_sucursal?: number | null;
  id_variante?: number | null;
  id_empresa?: number | string | null;
  tipo_movimiento?: string | null;
  busqueda?: string | null;
  pagina?: number;
  limite?: number;
}

@Injectable({
  providedIn: 'root'
})
export class InventarioService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/api/inventario`;

  consultarInventario(filtros: FiltrosInventario = {}): Observable<InventarioResponse> {
    let params = new HttpParams();

    if (filtros.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros.id_producto) params = params.set('id_producto', filtros.id_producto.toString());
    if (filtros.id_variante) params = params.set('id_variante', filtros.id_variante.toString());
    if (filtros.id_talla) params = params.set('id_talla', filtros.id_talla.toString());
    if (filtros.id_color) params = params.set('id_color', filtros.id_color.toString());
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());
    if (filtros.estado !== undefined && filtros.estado !== null && filtros.estado !== '') {
      params = params.set('estado', filtros.estado.toString());
    }
    if (filtros.filtro_stock) params = params.set('filtro_stock', filtros.filtro_stock);
    if (filtros.busqueda && filtros.busqueda.trim()) params = params.set('busqueda', filtros.busqueda.trim());
    if (filtros.pagina) params = params.set('pagina', filtros.pagina.toString());
    if (filtros.limite) params = params.set('limite', filtros.limite.toString());

    return this.http.get<InventarioResponse>(this.apiUrl, { params });
  }

  obtenerInventarioPorId(idInventario: number): Observable<{ success: boolean; item: ItemInventario }> {
    return this.http.get<{ success: boolean; item: ItemInventario }>(`${this.apiUrl}/${idInventario}`);
  }

  registrarMovimiento(payload: MovimientoPayload): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/movimiento`, payload);
  }

  consultarMovimientos(filtros: FiltrosMovimientos = {}): Observable<{ success: boolean; items: MovimientoInventario[]; total: number; pagina: number; limite: number; total_paginas: number }> {
    let params = new HttpParams();

    if (filtros.id_inventario) params = params.set('id_inventario', filtros.id_inventario.toString());
    if (filtros.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros.id_variante) params = params.set('id_variante', filtros.id_variante.toString());
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());
    if (filtros.tipo_movimiento) params = params.set('tipo_movimiento', filtros.tipo_movimiento);
    if (filtros.busqueda && filtros.busqueda.trim()) params = params.set('busqueda', filtros.busqueda.trim());
    if (filtros.pagina) params = params.set('pagina', filtros.pagina.toString());
    if (filtros.limite) params = params.set('limite', filtros.limite.toString());

    return this.http.get<any>(`${this.apiUrl}/movimientos`, { params });
  }
}
