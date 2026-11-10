import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export interface Categoria {
  id_categoria?: number;
  nombre: string;
  descripcion?: string;
  id_padre?: number | null;
  nombre_padre?: string | null;
  id_empresa?: number | null;
  empresa_nombre?: string;
  imagen_url?: string | null;
  imagen_public_id?: string | null;
  activo: boolean;
  estado?: string;
  created_at?: string;
  updated_at?: string;
  total_productos?: number;
  total_subcategorias?: number;
  es_raiz?: boolean;
}

export interface RespuestaApiCategorias {
  success: boolean;
  message: string;
  data: Categoria[];
  total: number;
}

export interface RespuestaApiUploadImagen {
  success: boolean;
  message: string;
  url: string;
  public_id: string;
  data?: any;
}

@Injectable({
  providedIn: 'root'
})
export class CategoriasService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = `${environment.apiUrl}/api/categorias`;

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token ? new HttpHeaders({ 'Authorization': `Bearer ${token}` }) : new HttpHeaders();
  }

  listarCategorias(params?: {
    solo_activas?: boolean;
    busqueda?: string;
    id_empresa?: number;
  }): Observable<RespuestaApiCategorias> {
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

    return this.http.get<RespuestaApiCategorias>(`${this.apiUrl}/`, {
      headers: this.getHeaders(),
      params: httpParams
    });
  }

  obtenerCategoria(id_categoria: number): Observable<{ success: boolean; data: Categoria }> {
    return this.http.get<{ success: boolean; data: Categoria }>(`${this.apiUrl}/${id_categoria}`, {
      headers: this.getHeaders()
    });
  }

  crearCategoria(categoria: Partial<Categoria>): Observable<any> {
    return this.http.post(`${this.apiUrl}/`, categoria, {
      headers: this.getHeaders()
    });
  }

  actualizarCategoria(id_categoria: number, categoria: Partial<Categoria>): Observable<any> {
    return this.http.put(`${this.apiUrl}/${id_categoria}`, categoria, {
      headers: this.getHeaders()
    });
  }

  cambiarEstadoCategoria(id_categoria: number, activo: boolean): Observable<any> {
    return this.http.put(`${this.apiUrl}/${id_categoria}/estado`, { activo }, {
      headers: this.getHeaders()
    });
  }

  eliminarCategoria(id_categoria: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${id_categoria}`, {
      headers: this.getHeaders()
    });
  }

  subirImagen(file: File): Observable<RespuestaApiUploadImagen> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<RespuestaApiUploadImagen>(`${this.apiUrl}/upload-image`, formData, {
      headers: this.getHeaders()
    });
  }
}
