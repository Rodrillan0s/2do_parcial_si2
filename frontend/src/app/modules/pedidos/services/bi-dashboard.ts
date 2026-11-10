import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export interface MetricasBI {
  incidentes_por_tipo_historico: any[];
  casos_cancelados_actuales: number;
  total_casos_registrados: number;
  tiempos_y_finanzas: {
    promedio_respuesta_minutos: number;
    ingresos_totales_historicos: number;
  };
  mapa_calor: any[];
}

export interface RespuestaApiMetricas {
  success: boolean;
  message: string;
  data: MetricasBI;
}

@Injectable({
  providedIn: 'root'
})
export class BiDashboardService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = environment.apiUrl;

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token ? new HttpHeaders({ 'Authorization': `Bearer ${token}` }) : new HttpHeaders();
  }

  obtenerMetricas(): Observable<RespuestaApiMetricas> {
    return this.http.get<RespuestaApiMetricas>(`${this.apiUrl}/api/dashboard/metricas`, { headers: this.getHeaders() });
  }

  // Este es el botón "mágico" para disparar el ETL de madrugada manualmente en tu defensa
  ejecutarProcesoETL(): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/api/dashboard/etl/ejecutar`, {}, { headers: this.getHeaders() });
  }
}