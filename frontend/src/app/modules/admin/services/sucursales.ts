import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { tap } from 'rxjs/operators';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export interface Sucursal {
  id_sucursal?: number;
  nombre: string;
  direccion: string;
  telefono?: string;
  id_empresa: number;
  empresa_nombre?: string;
  id_ciudad?: number;
  ciudad?: string;
  departamento?: string;
  latitud?: number | null;
  longitud?: number | null;
  activo: boolean;
  estado?: string;
  created_at?: string;
}

export interface RespuestaApiSucursales {
  success: boolean;
  message: string;
  data: Sucursal[];
}

@Injectable({
  providedIn: 'root'
})
export class SucursalService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = `${environment.apiUrl}/api/sucursales`;
  private cache = new Map<string, RespuestaApiSucursales>();

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token
      ? new HttpHeaders({ 'Authorization': `Bearer ${token}` })
      : new HttpHeaders();
  }

  limpiarCache(): void {
    this.cache.clear();
  }

  listarSucursales(id_empresa?: number, forceRefresh: boolean = false): Observable<RespuestaApiSucursales> {
    const key = id_empresa ? `emp_${id_empresa}` : 'all';
    if (!forceRefresh && this.cache.has(key)) {
      return of(this.cache.get(key)!);
    }

    const url = id_empresa
      ? `${this.apiUrl}/?id_empresa=${id_empresa}`
      : `${this.apiUrl}/`;

    return this.http.get<RespuestaApiSucursales>(
      url,
      { headers: this.getHeaders() }
    ).pipe(
      tap(res => {
        if (res && res.success) {
          this.cache.set(key, res);
        }
      })
    );
  }

  crearSucursal(sucursal: Sucursal): Observable<any> {
    return this.http.post(
      `${this.apiUrl}/`,
      sucursal,
      { headers: this.getHeaders() }
    ).pipe(tap(() => this.limpiarCache()));
  }

  actualizarSucursal(id_sucursal: number, sucursal: Sucursal): Observable<any> {
    return this.http.put(
      `${this.apiUrl}/${id_sucursal}`,
      sucursal,
      { headers: this.getHeaders() }
    ).pipe(tap(() => this.limpiarCache()));
  }

  cambiarEstadoSucursal(id_sucursal: number, activo: boolean): Observable<any> {
    return this.http.put(
      `${this.apiUrl}/${id_sucursal}/estado`,
      { activo },
      { headers: this.getHeaders() }
    ).pipe(tap(() => this.limpiarCache()));
  }

  eliminarSucursal(id_sucursal: number): Observable<any> {
    return this.http.delete(
      `${this.apiUrl}/${id_sucursal}`,
      { headers: this.getHeaders() }
    ).pipe(tap(() => this.limpiarCache()));
  }
}