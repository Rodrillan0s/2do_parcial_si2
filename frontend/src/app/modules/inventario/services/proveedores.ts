import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export interface Proveedor {
  id_proveedor: number;
  razon_social: string;
  nit: string;
  telefono: string;
  correo: string;
  direccion: string;
  contacto: string;
  estado: boolean;
}

export interface RespuestaProveedores {
  success: boolean;
  message: string;
  data: Proveedor[];
}

export interface RespuestaProveedor {
  success: boolean;
  message: string;
  data: Proveedor;
}

export interface DatosProveedor {
  razon_social: string;
  nit: string;
  telefono: string;
  correo: string;
  direccion: string;
  contacto: string;
}

@Injectable({
  providedIn: 'root'
})
export class ProveedoresService {

  private http = inject(HttpClient);
  private authService = inject(AuthService);

  private readonly apiUrl = `${environment.apiUrl}/api/proveedores`;

  private getAuthHeaders(): HttpHeaders | null {
    const token = this.authService.obtenerToken();

    if (!token) {
      return null;
    }

    return new HttpHeaders({
      Authorization: `Bearer ${token}`
    });
  }

  listarProveedores(
    busqueda: string = '',
    soloActivos: boolean = false
  ): Observable<RespuestaProveedores> {

    const headers = this.getAuthHeaders();

    let params = new HttpParams()
      .set('solo_activos', soloActivos.toString());

    if (busqueda.trim()) {
      params = params.set('busqueda', busqueda.trim());
    }

    return this.http.get<RespuestaProveedores>(
      this.apiUrl,
      {
        headers: headers || undefined,
        params
      }
    );
  }

  obtenerProveedor(
    idProveedor: number
  ): Observable<RespuestaProveedor> {

    const headers = this.getAuthHeaders();

    return this.http.get<RespuestaProveedor>(
      `${this.apiUrl}/${idProveedor}`,
      {
        headers: headers || undefined
      }
    );
  }

  crearProveedor(
    datos: DatosProveedor
  ): Observable<RespuestaProveedor> {

    const headers = this.getAuthHeaders();

    return this.http.post<RespuestaProveedor>(
      this.apiUrl,
      datos,
      {
        headers: headers || undefined
      }
    );
  }

  actualizarProveedor(
    idProveedor: number,
    datos: DatosProveedor
  ): Observable<RespuestaProveedor> {

    const headers = this.getAuthHeaders();

    return this.http.put<RespuestaProveedor>(
      `${this.apiUrl}/${idProveedor}`,
      datos,
      {
        headers: headers || undefined
      }
    );
  }

  cambiarEstadoProveedor(
    idProveedor: number,
    estado: boolean
  ): Observable<RespuestaProveedor> {

    const headers = this.getAuthHeaders();

    return this.http.put<RespuestaProveedor>(
      `${this.apiUrl}/${idProveedor}/estado`,
      { estado },
      {
        headers: headers || undefined
      }
    );
  }
}