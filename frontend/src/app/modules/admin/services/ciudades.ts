import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export interface Ciudad {
  id_ciudad?: number;
  nombre: string;
  departamento: string;
  estado: boolean;
  created_at?: string;
}

export interface RespuestaApiCiudades {
  success: boolean;
  message: string;
  data: Ciudad[];
}

@Injectable({
  providedIn: 'root'
})
export class CiudadService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = `${environment.apiUrl}/api/ciudades`;

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token ? new HttpHeaders({ 'Authorization': `Bearer ${token}` }) : new HttpHeaders();
  }

  listarCiudades(soloActivas: boolean = false, busqueda?: string): Observable<RespuestaApiCiudades> {
    let url = `${this.apiUrl}/?solo_activas=${soloActivas}`;
    if (busqueda && busqueda.trim()) {
      url += `&busqueda=${encodeURIComponent(busqueda.trim())}`;
    }
    return this.http.get<RespuestaApiCiudades>(url, { headers: this.getHeaders() });
  }

  crearCiudad(ciudad: Ciudad): Observable<any> {
    return this.http.post(`${this.apiUrl}/`, ciudad, { headers: this.getHeaders() });
  }

  actualizarCiudad(idCiudad: number, ciudad: Ciudad): Observable<any> {
    return this.http.put(`${this.apiUrl}/${idCiudad}`, ciudad, { headers: this.getHeaders() });
  }

  cambiarEstadoCiudad(idCiudad: number, estado: boolean): Observable<any> {
    return this.http.put(`${this.apiUrl}/${idCiudad}/estado`, { estado }, { headers: this.getHeaders() });
  }

  eliminarCiudad(idCiudad: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${idCiudad}`, { headers: this.getHeaders() });
  }
}
