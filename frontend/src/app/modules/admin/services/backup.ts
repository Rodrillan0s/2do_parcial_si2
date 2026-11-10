import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpResponse } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export interface GestorCloudInfo {
  gestor: string;
  proveedor: string;
  region: string;
  servicio: string;
  bucket_principal: string;
  tipo_volcado: string;
  sla_disponibilidad: string;
  estado_servicio: string;
  seguridad: string;
}

export interface EmpresaBackupOption {
  id_empresa: number;
  nombre_empresa: string;
  razon_social: string;
  nit: string;
  estado: string;
  ciudad: string;
}

export interface ItemHistorialBackup {
  id_backup: string;
  id_empresa: number | null;
  nombre_empresa: string;
  tipo: 'MANUAL' | 'AUTOMATICO';
  frecuencia: string;
  fecha: string;
  tamano_mb: number;
  gestor: string;
  archivo_dump: string;
  checksum_sha256: string;
  estado: string;
  tablas_incluidas?: number;
}

export interface ConfigAutomaticaBackup {
  habilitado: boolean;
  frecuencia: 'hora' | 'dia' | 'semana' | 'mes';
  intervalo_horas: number;
  hora_ejecucion: string;
  dia_semana: string;
  dia_mes: number;
  id_empresa: number | null;
  nombre_empresa?: string;
  retencion_dias: number;
  gestor: string;
  destino_oci?: string;
  notificar_email?: boolean;
  compresion_oci?: string;
}

@Injectable({ providedIn: 'root' })
export class BackupService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  
  private apiUrl = `${environment.apiUrl}/api/backup`;

  private getAuthHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token ? new HttpHeaders({ 'Authorization': `Bearer ${token}` }) : new HttpHeaders();
  }

  obtenerInfoGestor(): Observable<{ success: boolean; data: GestorCloudInfo }> {
    return this.http.get<{ success: boolean; data: GestorCloudInfo }>(
      `${this.apiUrl}/gestor`,
      { headers: this.getAuthHeaders() }
    );
  }

  obtenerEmpresas(): Observable<{ success: boolean; total: number; data: EmpresaBackupOption[] }> {
    return this.http.get<{ success: boolean; total: number; data: EmpresaBackupOption[] }>(
      `${this.apiUrl}/empresas`,
      { headers: this.getAuthHeaders() }
    );
  }

  obtenerHistorial(): Observable<{ success: boolean; total: number; data: ItemHistorialBackup[] }> {
    return this.http.get<{ success: boolean; total: number; data: ItemHistorialBackup[] }>(
      `${this.apiUrl}/historial`,
      { headers: this.getAuthHeaders() }
    );
  }

  generarBackupManual(idEmpresa?: number | null, nombreEmpresa?: string): Observable<HttpResponse<Blob>> {
    return this.http.post(
      `${this.apiUrl}/manual`,
      { id_empresa: idEmpresa, nombre_empresa: nombreEmpresa },
      {
        headers: this.getAuthHeaders(),
        observe: 'response',
        responseType: 'blob'
      }
    );
  }

  descargarBackupExistente(idBackup: string): Observable<HttpResponse<Blob>> {
    return this.http.get(
      `${this.apiUrl}/download/${encodeURIComponent(idBackup)}`,
      {
        headers: this.getAuthHeaders(),
        observe: 'response',
        responseType: 'blob'
      }
    );
  }

  eliminarBackupHistorial(idBackup: string): Observable<{ success: boolean; message: string }> {
    return this.http.delete<{ success: boolean; message: string }>(
      `${this.apiUrl}/historial/${encodeURIComponent(idBackup)}`,
      { headers: this.getAuthHeaders() }
    );
  }

  obtenerConfiguracionAutomatica(): Observable<{ success: boolean; data: ConfigAutomaticaBackup }> {
    return this.http.get<{ success: boolean; data: ConfigAutomaticaBackup }>(
      `${this.apiUrl}/automatico`,
      { headers: this.getAuthHeaders() }
    );
  }

  guardarConfiguracionAutomatica(config: Partial<ConfigAutomaticaBackup>): Observable<{ success: boolean; message: string; data: ConfigAutomaticaBackup }> {
    return this.http.post<{ success: boolean; message: string; data: ConfigAutomaticaBackup }>(
      `${this.apiUrl}/automatico`,
      config,
      { headers: this.getAuthHeaders() }
    );
  }

  simularRestauracion(archivoDump: string, idEmpresa?: number | null): Observable<{ success: boolean; data: any }> {
    return this.http.post<{ success: boolean; data: any }>(
      `${this.apiUrl}/restaurar/simular`,
      { archivo_dump: archivoDump, id_empresa: idEmpresa },
      { headers: this.getAuthHeaders() }
    );
  }
}
