import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export interface ProyeccionPunto {
  fecha: string;
  prediccion: number;
  limite_inferior: number;
  limite_superior: number;
}

export interface HistoricoPunto {
  fecha: string;
  unidades: number;
  ingresos: number;
  transacciones: number;
}

export interface RespuestaDemanda {
  success: boolean;
  id_empresa: number;
  id_sucursal?: number | null;
  id_producto?: number | null;
  dias_analizados: number;
  dias_proyectados: number;
  tendencia: 'ALCISTA' | 'BAJISTA' | 'ESTABLE';
  tasa_crecimiento_diario: number;
  sigma: number;
  historico: HistoricoPunto[];
  proyecciones: ProyeccionPunto[];
}

export interface RecomendacionItem {
  id_inventario: number;
  id_sucursal: number;
  sucursal: string;
  id_producto: number;
  producto: string;
  codigo_producto: string;
  categoria: string;
  id_variante: number;
  sku: string;
  talla: string;
  color: string;
  stock_disponible: number;
  stock_minimo: number;
  ritmo_diario_estimado: number;
  dias_cobertura: number;
  riesgo_rotura: 'CRITICO' | 'ALTO' | 'MODERADO' | 'OPTIMO';
  prioridad: number;
  reposicion_sugerida: number;
  inversion_estimada_bs: number;
  explicacion: string;
}

export interface RespuestaReposicion {
  success: boolean;
  id_empresa: number;
  id_sucursal?: number | null;
  lead_time_dias: number;
  total_prendas_analizadas: number;
  resumen: {
    alertas_criticas: number;
    alertas_altas: number;
    inversion_sugerida_bs: number;
  };
  recomendaciones: RecomendacionItem[];
}

export interface EvaluacionBacktesting {
  mae: number;
  rmse: number;
  mape: number;
  precision_pct: number;
  puntos_evaluados: number;
  comparativa: Array<{
    fecha: string;
    real: number;
    predicho: number;
    error_absoluto: number;
  }>;
}

export interface RespuestaEvaluacion {
  success: boolean;
  id_empresa: number;
  id_sucursal?: number | null;
  id_producto?: number | null;
  evaluacion: EvaluacionBacktesting;
}

@Injectable({
  providedIn: 'root'
})
export class PrediccionesService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = environment.apiUrl;

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  obtenerDemanda(params: {
    id_empresa?: number;
    id_sucursal?: number;
    id_producto?: number;
    dias_proyeccion?: number;
    dias_historia?: number;
  }): Observable<RespuestaDemanda> {
    let httpParams = new HttpParams();
    const effectiveCompany = params.id_empresa ?? this.authService.getEffectiveCompanyId();
    if (effectiveCompany) httpParams = httpParams.set('id_empresa', effectiveCompany.toString());
    if (params.id_sucursal) httpParams = httpParams.set('id_sucursal', params.id_sucursal.toString());
    if (params.id_producto) httpParams = httpParams.set('id_producto', params.id_producto.toString());
    if (params.dias_proyeccion) httpParams = httpParams.set('dias_proyeccion', params.dias_proyeccion.toString());
    if (params.dias_historia) httpParams = httpParams.set('dias_historia', params.dias_historia.toString());

    return this.http.get<RespuestaDemanda>(`${this.apiUrl}/api/ia/predicciones/demanda`, {
      headers: this.getHeaders(),
      params: httpParams
    });
  }

  obtenerReposicion(params: {
    id_empresa?: number;
    id_sucursal?: number;
    lead_time_dias?: number;
  }): Observable<RespuestaReposicion> {
    let httpParams = new HttpParams();
    const effectiveCompany = params.id_empresa ?? this.authService.getEffectiveCompanyId();
    if (effectiveCompany) httpParams = httpParams.set('id_empresa', effectiveCompany.toString());
    if (params.id_sucursal) httpParams = httpParams.set('id_sucursal', params.id_sucursal.toString());
    if (params.lead_time_dias) httpParams = httpParams.set('lead_time_dias', params.lead_time_dias.toString());

    return this.http.get<RespuestaReposicion>(`${this.apiUrl}/api/ia/predicciones/reposicion`, {
      headers: this.getHeaders(),
      params: httpParams
    });
  }

  evaluarModelo(body: {
    id_empresa?: number;
    id_sucursal?: number;
    id_producto?: number;
    dias_test?: number;
  }): Observable<RespuestaEvaluacion> {
    const effectiveCompany = body.id_empresa ?? this.authService.getEffectiveCompanyId();
    const payload = effectiveCompany ? { ...body, id_empresa: effectiveCompany } : body;
    return this.http.post<RespuestaEvaluacion>(`${this.apiUrl}/api/ia/predicciones/evaluar`, payload, {
      headers: this.getHeaders()
    });
  }
}
