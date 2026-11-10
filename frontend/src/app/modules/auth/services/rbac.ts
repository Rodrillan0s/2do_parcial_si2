import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from './auth';

export interface Permiso {
  id_permiso: number;
  codigo: string;
  nombre: string;
  descripcion?: string;
  modulo: string;
  activo?: boolean;
}

export interface Rol {
  id_rol: number;
  nombre: string;
  descripcion?: string;
  activo?: boolean;
  nivel_jerarquia?: number;
}

export interface PermisosUsuarioResponse {
  success: boolean;
  id_usuario: number;
  usuario: string;
  permisos_directos: Permiso[];
  permisos_heredados: Permiso[];
  permisos_efectivos: string[];
}

@Injectable({
  providedIn: 'root'
})
export class RbacService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = `${environment.apiUrl}/api/rbac`;

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token ? new HttpHeaders({ 'Authorization': `Bearer ${token}` }) : new HttpHeaders();
  }

  listarPermisos(): Observable<{ success: boolean; permisos: Permiso[] }> {
    return this.http.get<{ success: boolean; permisos: Permiso[] }>(`${this.apiUrl}/permisos`, { headers: this.getHeaders() });
  }

  listarPermisosDelegables(): Observable<{ success: boolean; permisos: Permiso[] }> {
    return this.http.get<{ success: boolean; permisos: Permiso[] }>(`${this.apiUrl}/permisos-delegables`, { headers: this.getHeaders() });
  }

  listarRolesDelegables(): Observable<{ success: boolean; roles: Rol[] }> {
    return this.http.get<{ success: boolean; roles: Rol[] }>(`${this.apiUrl}/roles-delegables`, { headers: this.getHeaders() });
  }

  obtenerPermisosUsuario(id_usuario: number): Observable<PermisosUsuarioResponse> {
    return this.http.get<PermisosUsuarioResponse>(`${this.apiUrl}/usuarios/${id_usuario}/permisos`, { headers: this.getHeaders() });
  }

  asignarPermisosDirectosUsuario(id_usuario: number, ids_permisos: number[]): Observable<any> {
    return this.http.post(`${this.apiUrl}/usuarios/${id_usuario}/permisos`, { ids_permisos }, { headers: this.getHeaders() });
  }

  obtenerSucursalesUsuario(id_usuario: number): Observable<{ success: boolean; id_usuario: number; sucursales: number[] }> {
    return this.http.get<{ success: boolean; id_usuario: number; sucursales: number[] }>(
      `${this.apiUrl}/usuarios/${id_usuario}/sucursales`,
      { headers: this.getHeaders() }
    );
  }

  asignarSucursalesUsuario(id_usuario: number, ids_sucursales: number[]): Observable<{ success: boolean; message: string; id_usuario: number; sucursales: number[] }> {
    return this.http.post<{ success: boolean; message: string; id_usuario: number; sucursales: number[] }>(
      `${this.apiUrl}/usuarios/${id_usuario}/sucursales`,
      { ids_sucursales },
      { headers: this.getHeaders() }
    );
  }
}

