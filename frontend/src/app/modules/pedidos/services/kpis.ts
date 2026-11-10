import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable, BehaviorSubject, shareReplay, catchError } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export interface RolDistribucion {
  rol: string;
  cantidad: number;
}

export interface DeptoSucursal {
  departamento: string;
  cantidad: number;
}

export interface EventoActividad {
  id: number;
  modulo: string;
  accion: string;
  fecha: string;
  usuario: string;
  descripcion?: string;
}

export interface SucursalDetalle {
  id: number;
  nombre: string;
  ciudad: string;
  departamento: string;
  activo: boolean;
}

export interface DashboardMetricas {
  alcance: 'PLATAFORMA' | 'EMPRESA' | 'SUCURSAL' | 'OPERATIVO';
  titulo: string;
  nombre_empresa?: string;
  nombre_sucursal?: string;
  ciudad?: string;
  
  // Plataforma / Global
  total_empresas?: number;
  total_sucursales?: number;
  total_usuarios?: number;
  total_ciudades?: number;
  total_productos?: number;
  total_eventos_bitacora?: number;
  roles_distribucion?: RolDistribucion[];
  sucursales_por_depto?: DeptoSucursal[];
  actividad_reciente?: EventoActividad[];
  
  // Empresa / Tenant
  sucursales_detalle?: SucursalDetalle[];
  eficiencia_tienda?: string;

  // Sucursal
  personal_sucursal?: number;
  prendas_stock?: number;
  pedidos_retiro_pendientes?: number;
  ventas_hoy?: number;
  estado_operativo?: string;

  // Operativo
  ventas_turno?: number;
  prendas_consultadas?: number;
  clientes_atendidos?: number;
  estado_turno?: string;

  nivel_cumplimiento_sla?: string;
  disponibilidad_red?: string;
}

export interface RespuestaDashboardMetricas {
  success: boolean;
  message: string;
  data: DashboardMetricas;
}

// ==============================================================================
// MODELOS W32: INDICADORES EMPRESARIALES AGREGADOS
// ==============================================================================

export interface KpisResumen {
  ventas: {
    cantidad_ventas: number;
    ventas_totales: number;
    ingresos_totales: number;
    ticket_promedio: number;
    ticket_minimo: number;
    ticket_maximo: number;
    clientes_unicos?: number;
  };
  inventario: {
    total_productos_catalogo: number;
    total_variantes: number;
    stock_total: number;
    stock_disponible: number;
    stock_reservado: number;
    productos_stock_bajo: number;
    productos_agotados: number;
    valoracion_inventario_disponible?: number;
    tasa_disponibilidad_stock?: number;
  };
  satisfaccion?: {
    total_valoraciones: number;
    calificacion_promedio: number;
    tasa_satisfaccion_pct: number;
    valoraciones_positivas: number;
    valoraciones_neutras: number;
    valoraciones_negativas: number;
    alertas_criticas_pendientes: number;
    estrellas_distribucion: { [key: number]: number };
    valoraciones_prendas: number;
    promedio_prendas: number;
    valoraciones_servicio: number;
    promedio_servicio: number;
  };
  canales?: {
    ventas_online_cantidad: number;
    ventas_online_total: number;
    porcentaje_online: number;
    ventas_pos_cantidad: number;
    ventas_pos_total: number;
    porcentaje_pos: number;
    total_pedidos: number;
    pedidos_delivery_cantidad: number;
    pedidos_delivery_total: number;
    pedidos_retiro_cantidad: number;
    pedidos_retiro_total: number;
    pedidos_entregados: number;
    pedidos_en_proceso: number;
  };
  reservas_probador?: {
    total_reservas: number;
    reservas_atendidas: number;
    reservas_canceladas: number;
    reservas_vencidas: number;
    reservas_activas: number;
    tasa_asistencia_pct: number;
  };
  devoluciones?: {
    total_solicitudes: number;
    devoluciones_completadas: number;
    devoluciones_rechazadas: number;
    devoluciones_en_tramite: number;
    monto_total_reembolsado: number;
    casos_ley_453: number;
  };
  comparacion: {
    ventas_crecimiento_pct: number;
    transacciones_crecimiento_pct: number;
    ingresos_crecimiento_pct: number;
    periodo_anterior_disponible: boolean;
  };
}

export interface PrendaRankingSatisfaccionItem {
  id_producto: number;
  nombre: string;
  categoria: string;
  imagen_url: string;
  calificacion_promedio: number;
  total_opiniones: number;
  quejas_1_estrella: number;
}

export interface AlertaCalidadCriticaItem {
  id_valoracion: number;
  fecha_creacion: string;
  nombre_cliente: string;
  nombre_producto: string;
  codigo_pedido: string | null;
  motivo_negativo: string;
  comentario: string;
  atendido: boolean;
  puntuacion: number;
}

export interface VentaTimelineItem {
  fecha: string;
  cantidad: number;
  total: number;
  ticket_promedio: number;
}

export interface ProductoMasVendidoItem {
  id_producto: number;
  nombre: string;
  categoria: string;
  unidades_vendidas: number;
  total_ingresos: number;
  precio_promedio: number;
  imagen_url: string;
}

export interface InventarioAlertaItem {
  id_producto: number;
  producto_nombre: string;
  sku: string;
  talla: string;
  color: string;
  sucursal_nombre: string;
  stock_actual: number;
  stock_disponible: number;
  stock_minimo: number;
  estado_alerta: 'AGOTADO' | 'BAJO_STOCK' | 'OPTIMO';
}

export interface VentaSucursalItem {
  id_sucursal: number;
  nombre_sucursal: string;
  ciudad: string;
  cantidad_ventas: number;
  total_ingresos: number;
  total_unidades: number;
  ticket_promedio: number;
}

export interface TenantSucursalItem {
  id: number;
  nombre: string;
  ciudad: string;
  direccion: string;
}

export interface TenantDashboardItem {
  id_empresa: number;
  nombre_empresa: string;
  razon_social: string;
  nit: string;
  ciudad: string;
  direccion: string;
  telefono: string;
  correo: string;
  logo: string;
  estado: string;
  total_sucursales: number;
  total_productos: number;
  total_stock_disponible: number;
  total_ventas_cantidad: number;
  total_ingresos_historico: number;
  sucursales: TenantSucursalItem[];
}

export interface RespuestaApi<T> {
  success: boolean;
  message: string;
  data: T;
}

@Injectable({
  providedIn: 'root'
})
export class KpisService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = environment.apiUrl;

  // Estado reactivo global de tenant/tienda seleccionada
  private tiendaSeleccionadaSubject = new BehaviorSubject<TenantDashboardItem | null>(this.obtenerTiendaInicial());
  public tiendaSeleccionada$ = this.tiendaSeleccionadaSubject.asObservable();

  obtenerTiendaActual(): TenantDashboardItem | null {
    return this.tiendaSeleccionadaSubject.value;
  }

  establecerTiendaSeleccionada(tienda: TenantDashboardItem | null): void {
    this.tiendaSeleccionadaSubject.next(tienda);
    if (typeof localStorage !== 'undefined') {
      if (tienda) {
        localStorage.setItem('tenant_seleccionado', JSON.stringify(tienda));
      } else {
        localStorage.removeItem('tenant_seleccionado');
      }
    }
  }

  private obtenerTiendaInicial(): TenantDashboardItem | null {
    if (typeof localStorage !== 'undefined') {
      try {
        const stored = localStorage.getItem('tenant_seleccionado');
        return stored ? JSON.parse(stored) : null;
      } catch {
        return null;
      }
    }
    return null;
  }

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  private tenantsCache$: Observable<RespuestaApi<TenantDashboardItem[]>> | null = null;
  private tenantsCacheTimestamp = 0;
  private readonly TENANTS_CACHE_TTL = 30000; // 30 segundos

  // Obtener listado de tiendas / tenants con métricas agregadas (con caché en memoria)
  obtenerTenants(forzarRefresco: boolean = false): Observable<RespuestaApi<TenantDashboardItem[]>> {
    const ahora = Date.now();
    if (!forzarRefresco && this.tenantsCache$ && (ahora - this.tenantsCacheTimestamp < this.TENANTS_CACHE_TTL)) {
      return this.tenantsCache$;
    }

    this.tenantsCacheTimestamp = ahora;
    this.tenantsCache$ = this.http.get<RespuestaApi<TenantDashboardItem[]>>(
      `${this.apiUrl}/api/kpis/tenants`,
      { headers: this.getHeaders() }
    ).pipe(
      shareReplay({ bufferSize: 1, refCount: false }),
      catchError((err) => {
        this.tenantsCache$ = null;
        this.tenantsCacheTimestamp = 0;
        throw err;
      })
    );

    return this.tenantsCache$;
  }

  invalidarCacheTenants(): void {
    this.tenantsCache$ = null;
    this.tenantsCacheTimestamp = 0;
  }

  // Compatibilidad anterior
  obtenerMetricasDashboard(id_empresa?: number): Observable<RespuestaDashboardMetricas> {
    let params = new HttpParams();
    if (id_empresa) params = params.set('id_empresa', id_empresa.toString());

    return this.http.get<RespuestaDashboardMetricas>(
      `${this.apiUrl}/api/dashboard/metricas`,
      { headers: this.getHeaders(), params }
    );
  }

  // W32: Resumen ejecutivo con variación temporal
  obtenerResumen(fecha_inicio?: string, fecha_fin?: string, id_sucursal?: number, id_empresa?: number): Observable<RespuestaApi<KpisResumen>> {
    let params = new HttpParams();
    if (fecha_inicio) params = params.set('fecha_inicio', fecha_inicio);
    if (fecha_fin) params = params.set('fecha_fin', fecha_fin);
    if (id_sucursal) params = params.set('id_sucursal', id_sucursal.toString());
    if (id_empresa) params = params.set('id_empresa', id_empresa.toString());

    return this.http.get<RespuestaApi<KpisResumen>>(
      `${this.apiUrl}/api/kpis/resumen`,
      { headers: this.getHeaders(), params }
    );
  }

  // W32: Serie temporal de ventas para gráfico de línea
  obtenerVentasTimeline(fecha_inicio?: string, fecha_fin?: string, id_sucursal?: number, id_empresa?: number): Observable<RespuestaApi<VentaTimelineItem[]>> {
    let params = new HttpParams();
    if (fecha_inicio) params = params.set('fecha_inicio', fecha_inicio);
    if (fecha_fin) params = params.set('fecha_fin', fecha_fin);
    if (id_sucursal) params = params.set('id_sucursal', id_sucursal.toString());
    if (id_empresa) params = params.set('id_empresa', id_empresa.toString());

    return this.http.get<RespuestaApi<VentaTimelineItem[]>>(
      `${this.apiUrl}/api/kpis/ventas`,
      { headers: this.getHeaders(), params }
    );
  }

  // W32: Ranking de productos con mayor recaudación
  obtenerProductosMasVendidos(fecha_inicio?: string, fecha_fin?: string, id_sucursal?: number, limit: number = 8, id_empresa?: number): Observable<RespuestaApi<ProductoMasVendidoItem[]>> {
    let params = new HttpParams().set('limit', limit.toString());
    if (fecha_inicio) params = params.set('fecha_inicio', fecha_inicio);
    if (fecha_fin) params = params.set('fecha_fin', fecha_fin);
    if (id_sucursal) params = params.set('id_sucursal', id_sucursal.toString());
    if (id_empresa) params = params.set('id_empresa', id_empresa.toString());

    return this.http.get<RespuestaApi<ProductoMasVendidoItem[]>>(
      `${this.apiUrl}/api/kpis/productos-mas-vendidos`,
      { headers: this.getHeaders(), params }
    );
  }

  // W32: Alertas de inventario crítico
  obtenerInventarioAlertas(id_sucursal?: number, id_empresa?: number): Observable<RespuestaApi<{ alertas_stock: InventarioAlertaItem[]; total_alertas: number }>> {
    let params = new HttpParams();
    if (id_sucursal) params = params.set('id_sucursal', id_sucursal.toString());
    if (id_empresa) params = params.set('id_empresa', id_empresa.toString());

    return this.http.get<RespuestaApi<{ alertas_stock: InventarioAlertaItem[]; total_alertas: number }>>(
      `${this.apiUrl}/api/kpis/inventario`,
      { headers: this.getHeaders(), params }
    );
  }

  // W32: Comparativa de ventas por sucursal
  obtenerVentasPorSucursal(fecha_inicio?: string, fecha_fin?: string, id_empresa?: number): Observable<RespuestaApi<VentaSucursalItem[]>> {
    let params = new HttpParams();
    if (fecha_inicio) params = params.set('fecha_inicio', fecha_inicio);
    if (fecha_fin) params = params.set('fecha_fin', fecha_fin);
    if (id_empresa) params = params.set('id_empresa', id_empresa.toString());

    return this.http.get<RespuestaApi<VentaSucursalItem[]>>(
      `${this.apiUrl}/api/kpis/ventas-sucursal`,
      { headers: this.getHeaders(), params }
    );
  }

  // W32: Ranking de satisfacción de prendas por valoración
  obtenerRankingSatisfaccion(id_sucursal?: number, limit: number = 5, id_empresa?: number): Observable<RespuestaApi<PrendaRankingSatisfaccionItem[]>> {
    let params = new HttpParams().set('limit', limit.toString());
    if (id_sucursal) params = params.set('id_sucursal', id_sucursal.toString());
    if (id_empresa) params = params.set('id_empresa', id_empresa.toString());

    return this.http.get<RespuestaApi<PrendaRankingSatisfaccionItem[]>>(
      `${this.apiUrl}/api/kpis/ranking-satisfaccion`,
      { headers: this.getHeaders(), params }
    );
  }

  // W32: Alertas de calidad y valoraciones críticas (1 estrella o a revisar)
  obtenerAlertasCalidad(id_sucursal?: number, limit: number = 10, id_empresa?: number): Observable<RespuestaApi<AlertaCalidadCriticaItem[]>> {
    let params = new HttpParams().set('limit', limit.toString());
    if (id_sucursal) params = params.set('id_sucursal', id_sucursal.toString());
    if (id_empresa) params = params.set('id_empresa', id_empresa.toString());

    return this.http.get<RespuestaApi<AlertaCalidadCriticaItem[]>>(
      `${this.apiUrl}/api/kpis/alertas-calidad`,
      { headers: this.getHeaders(), params }
    );
  }
}