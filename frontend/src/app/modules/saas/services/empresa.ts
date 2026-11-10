import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export interface Empresa {
  id_empresa?: number;
  nombre_empresa: string;        // Nombre comercial
  razon_social?: string;        // Razón social
  nit: string;                  // NIT único
  correo?: string;              // Correo empresarial
  telefono?: string;            // Teléfono de contacto
  direccion_fiscal?: string;    // Dirección fiscal
  ciudad?: string;              // Ciudad de operación
  logo?: string;                // URL del logotipo (opcional)
  estado: string;               // ACTIVO / INACTIVO
  created_at?: string;
  updated_at?: string;
}

export interface RespuestaApiEmpresas {
  success: boolean;
  message: string;
  data: Empresa[];
}

export interface RespuestaApiEmpresaAccion {
  success: boolean;
  message: string;
  id_empresa?: number;
  data?: Empresa;
}

@Injectable({
  providedIn: 'root'
})
export class EmpresaService {

  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = environment.apiUrl;

  private getHeaders() {
    const token = this.authService.obtenerToken();
    return {
      Authorization: `Bearer ${token}`
    };
  }

  listarEmpresas(): Observable<RespuestaApiEmpresas> {
    return this.http.get<RespuestaApiEmpresas>(
      `${this.apiUrl}/api/empresas/`,
      { headers: this.getHeaders() }
    );
  }

  obtenerEmpresa(idEmpresa: number): Observable<RespuestaApiEmpresaAccion> {
    return this.http.get<RespuestaApiEmpresaAccion>(
      `${this.apiUrl}/api/empresas/${idEmpresa}`,
      { headers: this.getHeaders() }
    );
  }

  crearEmpresa(empresa: Empresa): Observable<RespuestaApiEmpresaAccion> {
    return this.http.post<RespuestaApiEmpresaAccion>(
      `${this.apiUrl}/api/empresas/`,
      empresa,
      { headers: this.getHeaders() }
    );
  }

  actualizarEmpresa(idEmpresa: number, empresa: Empresa): Observable<RespuestaApiEmpresaAccion> {
    return this.http.put<RespuestaApiEmpresaAccion>(
      `${this.apiUrl}/api/empresas/${idEmpresa}`,
      empresa,
      { headers: this.getHeaders() }
    );
  }

  eliminarEmpresa(idEmpresa: number): Observable<RespuestaApiEmpresaAccion> {
    return this.http.delete<RespuestaApiEmpresaAccion>(
      `${this.apiUrl}/api/empresas/${idEmpresa}`,
      { headers: this.getHeaders() }
    );
  }
}