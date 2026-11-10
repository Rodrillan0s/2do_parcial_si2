import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable, shareReplay, catchError, tap } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';
import { ConfiguracionStorefront, SeccionStorefront } from '../../catalogo/services/catalogo-publico';

export type CodigoPlan = 'BASICO' | 'PROFESIONAL';
export type PeriodicidadPlan = 'MENSUAL' | 'ANUAL';

export interface OpcionesCancelacionSuscripcion {
  tiene_suscripcion_activa: boolean;
  id_suscripcion?: number;
  codigo_plan?: CodigoPlan;
  nombre_plan?: string;
  inicio?: string;
  fin?: string;
  dias_totales?: number;
  dias_transcurridos?: number;
  porcentaje_consumido?: number;
  elegible_reembolso?: boolean;
  limite_porcentaje_reembolso?: number;
  opcion_cancelar_fin_ciclo?: {
    disponible: boolean;
    titulo: string;
    descripcion: string;
  };
  opcion_reembolso_inmediato?: {
    disponible: boolean;
    titulo: string;
    descripcion: string;
  };
}

export interface PlanSaaS {
  codigo: CodigoPlan;
  nombre: string;
  max_sucursales: number;
  reportes_generativos: boolean;
  activo: boolean;
  precio_mensual?: number;
  precio_anual?: number;
  moneda?: string;
  descripcion?: string;
  beneficios?: string[];
}

export type EstadoSuscripcion =
  | 'VIGENTE'
  | 'SIN_SUSCRIPCION'
  | 'PROGRAMADA'
  | 'VENCIDA'
  | 'CANCELADA'
  | 'EMPRESA_INACTIVA'
  | 'PENDIENTE_ACTIVACION';

export type EstadoContratacionSaaS =
  | 'PENDIENTE_VERIFICACION_CORREO'
  | 'PENDIENTE_PAGO'
  | 'PENDIENTE_VERIFICACION_PAGO'
  | 'ACTIVA'
  | 'RECHAZADO'
  | 'CANCELADA';

export interface SolicitudContratacion {
  id_solicitud: number;
  codigo_seguimiento: string;
  id_empresa: number;
  nombre_empresa: string;
  slug: string;
  estado_empresa: string;
  id_usuario_propietario: number;
  nombre_propietario: string;
  correo_propietario: string;
  codigo_plan: CodigoPlan;
  nombre_plan: string;
  max_sucursales?: number;
  reportes_generativos?: boolean;
  periodicidad: PeriodicidadPlan;
  monto: number;
  moneda: string;
  estado_contratacion: EstadoContratacionSaaS;
  correo_verificado: boolean;
  metodo_pago?: 'PAYPAL' | 'QR_TRANSFERENCIA' | null;
  referencia_pago?: string | null;
  paypal_order_id?: string | null;
  comprobante_url?: string | null;
  id_suscripcion_generada?: number | null;
  observaciones_revision?: string | null;
  creado_en?: string;
  actualizado_en?: string;
  email_enviado?: boolean;
  token_verificacion_dev?: string;
}

export interface RegistroContratacionPayload {
  nombre: string;
  apellido: string;
  correo: string;
  telefono?: string;
  password: string;
  confirm_password: string;
  nombre_comercial: string;
  razon_social?: string;
  nit?: string;
  ciudad?: string;
  direccion_fiscal?: string;
  slug: string;
  codigo_plan: CodigoPlan;
  periodicidad: PeriodicidadPlan;
  publicos_objetivo?: string[];
}

export interface MiStorefrontData {
  id_empresa: number;
  nombre_empresa: string;
  razon_social: string;
  nit: string;
  correo: string;
  telefono: string;
  direccion_fiscal: string;
  ciudad: string;
  logo: string;
  estado: string;
  slug: string;
  configuracion_storefront: ConfiguracionStorefront;
  progreso_onboarding: {
    identidad_configurada: boolean;
    publicos_definidos: boolean;
    tiene_sucursal_activa: boolean;
    tiene_productos_activos: boolean;
    sucursales_activas: number;
    productos_activos: number;
    onboarding_completado: boolean;
  };
}

export interface SuscripcionItem {
  id_suscripcion: number;
  id_empresa: number;
  codigo_plan: CodigoPlan;
  inicio: string;
  fin: string;
  estado: 'ACTIVA' | 'CANCELADA';
  motivo: string;
  creado_por?: string | number;
  creado_en?: string;
}

export interface PlanVigenciaData {
  id_empresa: number;
  estado: EstadoSuscripcion;
  vigente: boolean;
  id_suscripcion: number | null;
  codigo_plan: CodigoPlan | null;
  inicio: string | null;
  fin: string | null;
  limites: { sucursales_activas: number | null };
  uso: { sucursales_activas: number } | null;
  disponibles: number;
  capacidades: { reportes_generativos: boolean };
  solicitud_contratacion?: SolicitudContratacion | null;
}

export interface AsignarSuscripcionPayload {
  codigo_plan: CodigoPlan;
  inicio: string;
  fin: string;
  motivo: string;
}

export interface CancelarSuscripcionPayload {
  motivo: string;
  confirmar: true;
}

@Injectable({
  providedIn: 'root'
})
export class SaasService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = environment.apiUrl;

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token ? new HttpHeaders({ 'Authorization': `Bearer ${token}` }) : new HttpHeaders();
  }

  /**
   * Catálogo público de planes activos y contratables (sin requerir JWT)
   */
  listarPlanesPublicos(): Observable<{ success: boolean; data: PlanSaaS[] }> {
    return this.http.get<{ success: boolean; data: PlanSaaS[] }>(
      `${this.apiUrl}/api/public/planes`
    );
  }

  /**
   * Verifica en tiempo real si un slug de tienda está disponible
   */
  verificarSlug(slug: string, excludeIdEmpresa?: number): Observable<{
    success: boolean;
    data: { disponible: boolean; slug_normalizado: string; sugerencia?: string; motivo: string };
  }> {
    let params = new HttpParams().set('slug', slug);
    if (excludeIdEmpresa) {
      params = params.set('exclude_id_empresa', excludeIdEmpresa.toString());
    }
    return this.http.get<{
      success: boolean;
      data: { disponible: boolean; slug_normalizado: string; sugerencia?: string; motivo: string };
    }>(`${this.apiUrl}/api/public/tenant/check-slug`, { params });
  }

  /**
   * Registro autónomo de empresa y propietario (ADMINISTRADOR_TIENDA)
   */
  registrarContratacion(payload: RegistroContratacionPayload): Observable<{ success: boolean; data: SolicitudContratacion }> {
    return this.http.post<{ success: boolean; data: SolicitudContratacion }>(
      `${this.apiUrl}/api/public/contratacion/registro`,
      payload
    );
  }

  /**
   * Verificar titularidad de correo electrónico con token de un solo uso
   */
  verificarCorreoContratacion(codigo_seguimiento: string, token: string): Observable<{ success: boolean; data: SolicitudContratacion }> {
    return this.http.post<{ success: boolean; data: SolicitudContratacion }>(
      `${this.apiUrl}/api/public/contratacion/verificar-correo`,
      { codigo_seguimiento, token }
    );
  }

  /**
   * Reenviar correo de verificación
   */
  reenviarVerificacionCorreo(codigo_seguimiento: string): Observable<{
    success: boolean;
    data: { codigo_seguimiento: string; email_enviado: boolean; token_verificacion_dev?: string };
  }> {
    return this.http.post<{
      success: boolean;
      data: { codigo_seguimiento: string; email_enviado: boolean; token_verificacion_dev?: string };
    }>(`${this.apiUrl}/api/public/contratacion/${encodeURIComponent(codigo_seguimiento)}/reenviar-verificacion`, {});
  }

  /**
   * Consultar estado y resumen de contratación por código de seguimiento
   */
  obtenerEstadoContratacion(codigo_seguimiento: string): Observable<{ success: boolean; data: SolicitudContratacion }> {
    return this.http.get<{ success: boolean; data: SolicitudContratacion }>(
      `${this.apiUrl}/api/public/contratacion/${encodeURIComponent(codigo_seguimiento)}`
    );
  }

  /**
   * Crear orden PayPal Sandbox para contratación SaaS
   */
  crearOrdenPayPalContratacion(
    codigo_seguimiento: string,
    origen?: string,
    retornoUrl?: string
  ): Observable<{
    success: boolean;
    data: {
      codigo_seguimiento: string;
      paypal_order_id: string;
      approve_url?: string;
      monto_bs: number;
      monto_usd: number;
      client_id: string;
    };
  }> {
    return this.http.post<any>(
      `${this.apiUrl}/api/public/contratacion/${encodeURIComponent(codigo_seguimiento)}/paypal/crear-orden`,
      { origen: origen || 'comercial', retorno_url: retornoUrl }
    );
  }

  /**
   * Capturar y confirmar server-to-server orden PayPal para contratación SaaS
   */
  capturarOrdenPayPalContratacion(codigo_seguimiento: string, order_id: string): Observable<{ success: boolean; data: SolicitudContratacion }> {
    return this.http.post<{ success: boolean; data: SolicitudContratacion }>(
      `${this.apiUrl}/api/public/contratacion/${encodeURIComponent(codigo_seguimiento)}/paypal/capturar`,
      { order_id }
    );
  }

  /**
   * Subir archivo de comprobante de pago por QR / Transferencia
   */
  subirComprobanteContratacion(
    codigo_seguimiento: string,
    archivo: File,
    referencia_pago: string = 'QR-TRANSFERENCIA'
  ): Observable<{ success: boolean; data: SolicitudContratacion }> {
    const formData = new FormData();
    formData.append('archivo', archivo);
    formData.append('referencia_pago', referencia_pago);
    return this.http.post<{ success: boolean; data: SolicitudContratacion }>(
      `${this.apiUrl}/api/public/contratacion/${encodeURIComponent(codigo_seguimiento)}/subir-comprobante`,
      formData
    );
  }

  /**
   * Listar solicitudes de contratación autónoma (SuperAdmin)
   */
  listarContrataciones(estado?: string): Observable<{ success: boolean; data: SolicitudContratacion[] }> {
    let params = new HttpParams();
    if (estado) params = params.set('estado', estado);
    return this.http.get<{ success: boolean; data: SolicitudContratacion[] }>(
      `${this.apiUrl}/api/contrataciones`,
      { headers: this.getHeaders(), params }
    );
  }

  /**
   * Aprobar o rechazar solicitud de contratación pendiente (SuperAdmin)
   */
  resolverContratacion(
    id_solicitud: number,
    accion: 'APROBAR' | 'RECHAZAR',
    observaciones: string
  ): Observable<{ success: boolean; data: SolicitudContratacion }> {
    return this.http.post<{ success: boolean; data: SolicitudContratacion }>(
      `${this.apiUrl}/api/contrataciones/${id_solicitud}/resolver`,
      { accion, observaciones },
      { headers: this.getHeaders() }
    );
  }

  /**
   * Obtener configuración de storefront y onboarding de la empresa
   */
  obtenerMiStorefront(idEmpresa?: number): Observable<{ success: boolean; data: MiStorefrontData }> {
    let params = new HttpParams();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    return this.http.get<{ success: boolean; data: MiStorefrontData }>(
      `${this.apiUrl}/api/mi-empresa/storefront`,
      { headers: this.getHeaders(), params }
    );
  }

  /**
   * Actualizar configuración de storefront y onboarding de la empresa
   */
  actualizarMiStorefront(
    payload: Partial<ConfiguracionStorefront> & { slug?: string; logo?: string; secciones?: SeccionStorefront[] },
    idEmpresa?: number
  ): Observable<{ success: boolean; data: MiStorefrontData }> {
    let params = new HttpParams();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    return this.http.put<{ success: boolean; data: MiStorefrontData }>(
      `${this.apiUrl}/api/mi-empresa/storefront`,
      payload,
      { headers: this.getHeaders(), params }
    );
  }

  /**
   * Catálogo de planes disponibles (planes.ver)
   */
  listarPlanes(): Observable<{ success: boolean; data: PlanSaaS[] }> {
    return this.http.get<{ success: boolean; data: PlanSaaS[] }>(
      `${this.apiUrl}/api/planes`,
      { headers: this.getHeaders() }
    );
  }

  /**
   * Actualizar nombre, precios y disponibilidad de un plan (planes.gestionar + plataforma)
   */
  actualizarPlan(
    codigo: CodigoPlan,
    data: { nombre: string; activo: boolean; precio_mensual?: number; precio_anual?: number; descripcion?: string }
  ): Observable<{ success: boolean; data: PlanSaaS }> {
    return this.http.put<{ success: boolean; data: PlanSaaS }>(
      `${this.apiUrl}/api/planes/${codigo}`,
      data,
      { headers: this.getHeaders() }
    );
  }

  private planCache = new Map<string, { obs$: Observable<{ success: boolean; data: PlanVigenciaData }>; timestamp: number }>();
  private readonly PLAN_CACHE_TTL = 20000; // 20s en memoria

  /**
   * Consulta de plan actual, vigencia, capacidades y límites de sucursales activas (suscripciones.ver)
   */
  consultarPlan(idEmpresa?: number, forzar: boolean = false): Observable<{ success: boolean; data: PlanVigenciaData }> {
    const cacheKey = idEmpresa ? String(idEmpresa) : 'default';
    const ahora = Date.now();
    const entry = this.planCache.get(cacheKey);

    if (!forzar && entry && (ahora - entry.timestamp < this.PLAN_CACHE_TTL)) {
      return entry.obs$;
    }

    let params = new HttpParams();
    if (idEmpresa) {
      params = params.set('id_empresa', idEmpresa.toString());
    }

    const obs$ = this.http.get<{ success: boolean; data: PlanVigenciaData }>(
      `${this.apiUrl}/api/mi-empresa/plan`,
      { headers: this.getHeaders(), params }
    ).pipe(
      shareReplay({ bufferSize: 1, refCount: false }),
      catchError((err) => {
        this.planCache.delete(cacheKey);
        throw err;
      })
    );

    this.planCache.set(cacheKey, { obs$, timestamp: ahora });
    return obs$;
  }

  invalidarCachePlan(idEmpresa?: number): void {
    if (idEmpresa) {
      this.planCache.delete(String(idEmpresa));
    } else {
      this.planCache.clear();
    }
  }

  /**
   * Historial de suscripciones de una empresa (suscripciones.ver)
   */
  obtenerHistorialSuscripciones(idEmpresa: number): Observable<{ success: boolean; data: SuscripcionItem[] }> {
    return this.http.get<{ success: boolean; data: SuscripcionItem[] }>(
      `${this.apiUrl}/api/empresas/${idEmpresa}/suscripciones`,
      { headers: this.getHeaders() }
    );
  }

  /**
   * Asignar o renovar una suscripción administrativa (suscripciones.gestionar + plataforma)
   */
  asignarSuscripcion(idEmpresa: number, payload: AsignarSuscripcionPayload): Observable<{ success: boolean; data: SuscripcionItem }> {
    return this.http.post<{ success: boolean; data: SuscripcionItem }>(
      `${this.apiUrl}/api/empresas/${idEmpresa}/suscripciones`,
      payload,
      { headers: this.getHeaders() }
    ).pipe(
      tap(() => this.invalidarCachePlan(idEmpresa))
    );
  }

  /**
   * Cancelar una suscripción administrativa activa (suscripciones.gestionar + plataforma)
   */
  cancelarSuscripcion(idEmpresa: number, idSuscripcion: number, payload: CancelarSuscripcionPayload): Observable<{ success: boolean; data: { id_suscripcion: number; estado: string } }> {
    return this.http.post<{ success: boolean; data: { id_suscripcion: number; estado: string } }>(
      `${this.apiUrl}/api/empresas/${idEmpresa}/suscripciones/${idSuscripcion}/cancelar`,
      payload,
      { headers: this.getHeaders() }
    ).pipe(
      tap(() => this.invalidarCachePlan(idEmpresa))
    );
  }

  /**
   * Obtiene la solicitud de contratación activa o pendiente de pago de la empresa en sesión.
   */
  obtenerContratacionActiva(idEmpresa?: number): Observable<{ success: boolean; data: SolicitudContratacion | null }> {
    let params = new HttpParams();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    return this.http.get<{ success: boolean; data: SolicitudContratacion | null }>(
      `${this.apiUrl}/api/mi-empresa/contratacion-activa`,
      { headers: this.getHeaders(), params }
    );
  }

  /**
   * Solicita una renovación o cambio de plan (Upgrade/Downgrade) para la tienda desde el panel admin.
   */
  solicitarRenovacionOCambioPlan(
    payload: {
      codigo_plan: CodigoPlan;
      periodicidad?: 'MENSUAL' | 'ANUAL';
      momento_cambio?: 'SIGUIENTE_CICLO' | 'INMEDIATO';
      motivo?: string;
    },
    idEmpresa?: number
  ): Observable<{ success: boolean; data: SolicitudContratacion }> {
    let params = new HttpParams();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    return this.http.post<{ success: boolean; data: SolicitudContratacion }>(
      `${this.apiUrl}/api/mi-empresa/suscripcion/solicitar`,
      payload,
      { headers: this.getHeaders(), params }
    ).pipe(
      tap(() => this.invalidarCachePlan(idEmpresa))
    );
  }

  /**
   * Consulta las opciones comerciales de cancelación y elegibilidad de reembolso según el tiempo transcurrido.
   */
  obtenerOpcionesCancelacion(idEmpresa?: number): Observable<{ success: boolean; data: OpcionesCancelacionSuscripcion }> {
    let params = new HttpParams();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    return this.http.get<{ success: boolean; data: OpcionesCancelacionSuscripcion }>(
      `${this.apiUrl}/api/mi-empresa/suscripcion/opciones-cancelacion`,
      { headers: this.getHeaders(), params }
    );
  }

  /**
   * Procesa la cancelación comercial: conservar servicio hasta fin de ciclo o reembolso inmediato si <= 10% consumido.
   */
  cancelarSuscripcionComercial(
    payload: { tipo_cancelacion: 'FIN_DE_CICLO' | 'REEMBOLSO_INMEDIATO'; motivo?: string },
    idEmpresa?: number
  ): Observable<{ success: boolean; data: { exito: boolean; tipo_cancelacion: string; mensaje: string; fecha_fin_servicio?: string } }> {
    let params = new HttpParams();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    return this.http.post<{ success: boolean; data: { exito: boolean; tipo_cancelacion: string; mensaje: string; fecha_fin_servicio?: string } }>(
      `${this.apiUrl}/api/mi-empresa/suscripcion/cancelar`,
      payload,
      { headers: this.getHeaders(), params }
    ).pipe(
      tap(() => this.invalidarCachePlan(idEmpresa))
    );
  }
}
