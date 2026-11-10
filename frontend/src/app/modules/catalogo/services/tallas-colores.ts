import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export interface Talla {
  id_talla?: number;
  nombre: string;
  descripcion?: string;
  id_empresa?: number | null;
  empresa_nombre?: string;
  activo: boolean;
  estado?: string;
  created_at?: string;
  updated_at?: string;
  total_variantes?: number;
}

export interface ColorPrenda {
  id_color?: number;
  nombre: string;
  codigo_hex: string;
  id_empresa?: number | null;
  empresa_nombre?: string;
  activo: boolean;
  estado?: string;
  created_at?: string;
  updated_at?: string;
  total_variantes?: number;
}

export interface RespuestaApiTallas {
  success: boolean;
  message: string;
  data: Talla[];
  total: number;
}

export interface RespuestaApiColores {
  success: boolean;
  message: string;
  data: ColorPrenda[];
  total: number;
}

@Injectable({
  providedIn: 'root'
})
export class TallasColoresService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrlTallas = `${environment.apiUrl}/api/tallas`;
  private apiUrlColores = `${environment.apiUrl}/api/colores`;

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token ? new HttpHeaders({ 'Authorization': `Bearer ${token}` }) : new HttpHeaders();
  }

  // --- TALLAS ---
  listarTallas(params?: {
    solo_activas?: boolean;
    busqueda?: string;
    id_empresa?: number;
  }): Observable<RespuestaApiTallas> {
    let httpParams = new HttpParams();
    if (params?.solo_activas !== undefined) {
      httpParams = httpParams.set('solo_activas', params.solo_activas.toString());
    }
    if (params?.busqueda) {
      httpParams = httpParams.set('busqueda', params.busqueda);
    }
    if (params?.id_empresa) {
      httpParams = httpParams.set('id_empresa', params.id_empresa.toString());
    }

    return this.http.get<RespuestaApiTallas>(`${this.apiUrlTallas}/`, {
      headers: this.getHeaders(),
      params: httpParams
    });
  }

  obtenerTalla(id_talla: number): Observable<{ success: boolean; data: Talla }> {
    return this.http.get<{ success: boolean; data: Talla }>(`${this.apiUrlTallas}/${id_talla}`, {
      headers: this.getHeaders()
    });
  }

  crearTalla(talla: Partial<Talla>): Observable<any> {
    return this.http.post(`${this.apiUrlTallas}/`, talla, {
      headers: this.getHeaders()
    });
  }

  actualizarTalla(id_talla: number, talla: Partial<Talla>): Observable<any> {
    return this.http.put(`${this.apiUrlTallas}/${id_talla}`, talla, {
      headers: this.getHeaders()
    });
  }

  cambiarEstadoTalla(id_talla: number, activo: boolean): Observable<any> {
    return this.http.put(`${this.apiUrlTallas}/${id_talla}/estado`, { activo }, {
      headers: this.getHeaders()
    });
  }

  eliminarTalla(id_talla: number): Observable<any> {
    return this.http.delete(`${this.apiUrlTallas}/${id_talla}`, {
      headers: this.getHeaders()
    });
  }

  // --- COLORES ---
  listarColores(params?: {
    solo_activos?: boolean;
    busqueda?: string;
    id_empresa?: number;
  }): Observable<RespuestaApiColores> {
    let httpParams = new HttpParams();
    if (params?.solo_activos !== undefined) {
      httpParams = httpParams.set('solo_activos', params.solo_activos.toString());
    }
    if (params?.busqueda) {
      httpParams = httpParams.set('busqueda', params.busqueda);
    }
    if (params?.id_empresa) {
      httpParams = httpParams.set('id_empresa', params.id_empresa.toString());
    }

    return this.http.get<RespuestaApiColores>(`${this.apiUrlColores}/`, {
      headers: this.getHeaders(),
      params: httpParams
    });
  }

  obtenerColor(id_color: number): Observable<{ success: boolean; data: ColorPrenda }> {
    return this.http.get<{ success: boolean; data: ColorPrenda }>(`${this.apiUrlColores}/${id_color}`, {
      headers: this.getHeaders()
    });
  }

  crearColor(color: Partial<ColorPrenda>): Observable<any> {
    return this.http.post(`${this.apiUrlColores}/`, color, {
      headers: this.getHeaders()
    });
  }

  actualizarColor(id_color: number, color: Partial<ColorPrenda>): Observable<any> {
    return this.http.put(`${this.apiUrlColores}/${id_color}`, color, {
      headers: this.getHeaders()
    });
  }

  cambiarEstadoColor(id_color: number, activo: boolean): Observable<any> {
    return this.http.put(`${this.apiUrlColores}/${id_color}/estado`, { activo }, {
      headers: this.getHeaders()
    });
  }

  eliminarColor(id_color: number): Observable<any> {
    return this.http.delete(`${this.apiUrlColores}/${id_color}`, {
      headers: this.getHeaders()
    });
  }
}
