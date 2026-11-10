import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';

export interface BitacoraEvent {
  id_bitacora: number;
  fecha_hora: string;
  fecha_evento?: string;
  id_usuario: number;
  usuario_nombre: string;
  id_empresa: number;
  id_sucursal: number;
  modulo: string;
  accion: string;
  entidad: string;
  id_entidad: string;
  descripcion: string;
  resultado: string;
  nivel: string;
  ip: string;
  user_agent: string;
  datos_anteriores: any;
  datos_nuevos: any;
  metadatos: any;
  request_id: string;
}

export interface BitacoraResponse {
  success: boolean;
  data: BitacoraEvent[];
  page: number;
  limit: number;
  total: number;
  pages: number;
}

export interface BitacoraDetalleResponse {
  success: boolean;
  data: BitacoraEvent;
}

@Injectable({
  providedIn: 'root'
})
export class BitacoraService {
  private apiUrl = `${environment.apiUrl}/api/bitacora/`;

  constructor(private http: HttpClient) {}

  obtenerEventos(filtros: any = {}, page: number = 1, limit: number = 25): Observable<BitacoraResponse> {
    let params = new HttpParams()
      .set('page', page.toString())
      .set('limit', limit.toString());

    Object.keys(filtros).forEach(key => {
      if (filtros[key] !== null && filtros[key] !== undefined && filtros[key] !== '') {
        params = params.set(key, filtros[key]);
      }
    });

    return this.http.get<BitacoraResponse>(this.apiUrl, { params });
  }

  obtenerDetalleEvento(id_bitacora: number): Observable<BitacoraDetalleResponse> {
    return this.http.get<BitacoraDetalleResponse>(`${this.apiUrl}${id_bitacora}`);
  }
}
