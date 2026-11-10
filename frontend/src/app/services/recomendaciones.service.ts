import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface RecomendacionML {
  id_producto: number;
  nombre: string;
  categoria: string;
  precio: number;
  imagen_url: string;
  puntuacion: number;
  afinidad_porcentaje: number;
  motivo: string;
  descripcion: string;
  tallas: string[];
  colores: string[];
}

export interface RecomendacionesResponse {
  success: boolean;
  total: number;
  personalizado: boolean;
  recomendaciones: RecomendacionML[];
}

@Injectable({
  providedIn: 'root'
})
export class RecomendacionesService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/api/recomendaciones`;

  obtenerMisRecomendaciones(limite: number = 6): Observable<RecomendacionesResponse> {
    return this.http.get<RecomendacionesResponse>(`${this.apiUrl}/mis-recomendaciones`, {
      params: { limite: limite.toString() }
    });
  }

  obtenerPorCliente(idCliente: number): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/cliente/${idCliente}`);
  }

  reentrenarModelo(): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/entrenar`, {});
  }
}

