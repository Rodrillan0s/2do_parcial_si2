import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';

export interface PrendaReserva {
  id_detalle_reserva: number;
  id_variante: number;
  cantidad: number;
  estado_prenda: string;
  id_producto: number;
  codigo_producto: string;
  nombre: string;
  precio: number;
  subtotal: number;
  sku?: string;
  talla?: string;
  color?: string;
  codigo_hex?: string;
  imagen_url?: string;
  aceptado?: boolean; // POS Fitting room switch state
}

export interface ReservaItem {
  id_reserva: number;
  codigo_reserva: string;
  id_cliente: number;
  id_sucursal: number;
  fecha_reserva: string;
  fecha_hora_visita: string;
  estado: string;
  observaciones?: string;
  id_venta?: number;
  sucursal?: string;
  cliente?: {
    id_cliente: number;
    nombre: string;
    apellido: string;
    nombre_completo: string;
    ci?: string;
    telefono?: string;
    correo?: string;
  };
  venta?: {
    id_venta?: number;
    numero_venta?: string;
    estado?: string;
    total: number;
    pagada: boolean;
  };
  venta_pagada: boolean;
  total_estimado: number;
  cantidad_prendas: number;
  puede_atender: boolean;
  prendas: PrendaReserva[];
}

export interface CobroReservaPayload {
  id_sesion_caja?: number;
  id_metodo_pago: number;
  monto_recibido?: number;
  monto_cambio?: number;
  referencia_transaccion?: string;
  descuento?: number;
  observacion?: string;
  datos_facturacion?: {
    nit_ci?: string;
    razon_social?: string;
    correo_facturacion?: string;
    tipo_documento?: string;
  };
  items_seleccionados?: Array<{
    id_detalle_reserva: number;
    id_variante?: number;
    cantidad?: number;
    aceptado: boolean;
  }>;
}

@Injectable({
  providedIn: 'root'
})
export class AtenderReservaService {

  private apiUrl = `${environment.apiUrl}/api/atender-reserva`;

  constructor(private http: HttpClient) {}

  listarReservas(
    idSucursal: number,
    idEmpresa?: number,
    busqueda?: string,
    estado?: string
  ): Observable<{ success: boolean; data: ReservaItem[]; total?: number; message?: string }> {
    let params = new HttpParams().set('id_sucursal', idSucursal.toString());
    if (idEmpresa) {
      params = params.set('id_empresa', idEmpresa.toString());
    }
    if (busqueda && busqueda.trim()) {
      params = params.set('q', busqueda.trim());
    }
    if (estado && estado.trim()) {
      params = params.set('estado', estado.trim());
    }

    return this.http.get<{ success: boolean; data: ReservaItem[]; total?: number; message?: string }>(
      this.apiUrl,
      { params }
    );
  }

  obtenerReserva(
    idReserva: number,
    idSucursal: number,
    idEmpresa?: number
  ): Observable<{ success: boolean; data: any; message?: string }> {
    let params = new HttpParams().set('id_sucursal', idSucursal.toString());
    if (idEmpresa) {
      params = params.set('id_empresa', idEmpresa.toString());
    }

    return this.http.get<{ success: boolean; data: any; message?: string }>(
      `${this.apiUrl}/${idReserva}`,
      { params }
    );
  }

  cobrarReservaPos(
    idReserva: number,
    payload: CobroReservaPayload,
    idSucursal: number,
    idEmpresa?: number
  ): Observable<any> {
    let params = new HttpParams().set('id_sucursal', idSucursal.toString());
    if (idEmpresa) {
      params = params.set('id_empresa', idEmpresa.toString());
    }

    return this.http.post<any>(
      `${this.apiUrl}/${idReserva}/cobrar-pos`,
      payload,
      { params }
    );
  }

  entregarReservaPagada(
    idReserva: number,
    payload: { items_seleccionados?: any[] },
    idSucursal: number,
    idEmpresa?: number
  ): Observable<any> {
    let params = new HttpParams().set('id_sucursal', idSucursal.toString());
    if (idEmpresa) {
      params = params.set('id_empresa', idEmpresa.toString());
    }

    return this.http.post<any>(
      `${this.apiUrl}/${idReserva}/entregar`,
      payload,
      { params }
    );
  }

  atenderReserva(
    idReserva: number,
    idSucursal: number,
    idEmpresa?: number
  ): Observable<any> {
    let params = new HttpParams().set('id_sucursal', idSucursal.toString());
    if (idEmpresa) {
      params = params.set('id_empresa', idEmpresa.toString());
    }

    return this.http.post<any>(
      `${this.apiUrl}/${idReserva}`,
      {},
      { params }
    );
  }
}