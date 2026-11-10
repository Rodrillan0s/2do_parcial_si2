import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface CrearValoracionPayload {
  id_producto?: number | null;
  id_pedido?: number | null;
  id_venta?: number | null;
  id_reserva?: number | null;
  puntuacion: number;
  comentario?: string | null;
  motivo_negativo?: string | null;
  id_empresa?: number | null;
}

export interface OpinionCliente {
  id_valoracion: number;
  puntuacion: number;
  comentario?: string | null;
  fecha_creacion: string;
  nombre_cliente: string;
  compra_verificada: boolean;
}

export interface ResumenValoracionesProducto {
  id_producto: number;
  promedio: number;
  total: number;
  distribucion: { [key: number]: number };
  ultimas_opiniones: OpinionCliente[];
}

export interface CompraPendienteValoracion {
  id_pedido: number;
  codigo_pedido: string;
  fecha_pedido: string;
  estado: string;
  modalidad_compra: string;
  nombre_sucursal: string;
  id_variante: number;
  id_producto: number;
  nombre_producto: string;
  imagen_producto?: string;
}

export interface ValoracionAdminItem {
  id_valoracion: number;
  id_empresa: number;
  id_sucursal?: number | null;
  nombre_sucursal?: string | null;
  id_cliente: number;
  nombre_cliente: string;
  id_producto?: number | null;
  nombre_producto?: string | null;
  id_pedido?: number | null;
  codigo_pedido?: string | null;
  id_venta?: number | null;
  id_reserva?: number | null;
  puntuacion: number;
  comentario?: string | null;
  motivo_negativo?: string | null;
  requiere_revision: boolean;
  atendido: boolean;
  notas_admin?: string | null;
  fecha_creacion: string;
}

@Injectable({
  providedIn: 'root'
})
export class ValoracionService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/api/valoraciones`;

  crearValoracion(payload: CrearValoracionPayload): Observable<{ success: boolean; message: string; data: any }> {
    return this.http.post<{ success: boolean; message: string; data: any }>(this.apiUrl, payload);
  }

  obtenerPendientes(): Observable<{ success: boolean; data: CompraPendienteValoracion[] }> {
    return this.http.get<{ success: boolean; data: CompraPendienteValoracion[] }>(`${this.apiUrl}/pendientes`);
  }

  obtenerValoracionesProducto(idProducto: number): Observable<{ success: boolean; data: ResumenValoracionesProducto }> {
    return this.http.get<{ success: boolean; data: ResumenValoracionesProducto }>(`${this.apiUrl}/producto/${idProducto}`);
  }

  listarValoracionesAdmin(filtros?: {
    id_empresa?: number;
    id_sucursal?: number;
    solo_criticas?: boolean;
    atendido?: boolean;
    limite?: number;
    offset?: number;
  }): Observable<{ success: boolean; data: ValoracionAdminItem[] }> {
    let params = new HttpParams();
    if (filtros) {
      if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());
      if (filtros.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
      if (filtros.solo_criticas) params = params.set('solo_criticas', 'true');
      if (filtros.atendido !== undefined) params = params.set('atendido', filtros.atendido.toString());
      if (filtros.limite) params = params.set('limite', filtros.limite.toString());
      if (filtros.offset) params = params.set('offset', filtros.offset.toString());
    }
    return this.http.get<{ success: boolean; data: ValoracionAdminItem[] }>(`${this.apiUrl}/admin`, { params });
  }

  atenderValoracionAdmin(
    idValoracion: number,
    notasAdmin: string,
    atendido: boolean = true,
    idEmpresa?: number
  ): Observable<{ success: boolean; message: string }> {
    let params = new HttpParams();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    return this.http.patch<{ success: boolean; message: string }>(
      `${this.apiUrl}/admin/${idValoracion}/atender`,
      { notas_admin: notasAdmin, atendido },
      { params }
    );
  }
}
