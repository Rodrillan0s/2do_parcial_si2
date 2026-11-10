import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, from, of, throwError } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';
import { IndexedDbService } from '../../../core/storage/indexed-db.service';
import { NetworkStatusService } from '../../../core/network/network-status.service';
import { SyncQueueService, PendingOperation } from '../../../core/sync/sync-queue.service';

export interface Denominacion {
  id_denominacion: number;
  valor: number;
  moneda: string;
  tipo: 'BILLETE' | 'MONEDA';
  orden: number;
}

export interface CajaEstadoResponse {
  success: boolean;
  tiene_sesion_activa: boolean;
  offline_cached?: boolean;
  caja_asignada?: {
    id_caja: number;
    codigo_caja: string;
    nombre: string;
    id_sucursal: number;
    sucursal_nombre?: string;
  };
  sesion_activa?: {
    id_sesion_caja: number;
    id_caja: number;
    codigo_caja: string;
    nombre_caja: string;
    id_sucursal: number;
    sucursal_nombre: string;
    monto_inicial: number;
    fecha_apertura: string;
    cajero_nombre: string;
    id_cajero: number;
  } | null;
}

export interface ConteoItemPayload {
  id_denominacion: number;
  cantidad: number;
}

export interface AbrirCajaPayload {
  id_caja: number;
  id_sucursal?: number;
  id_empresa?: number;
  conteo?: ConteoItemPayload[];
  conteo_items?: ConteoItemPayload[];
  monto_inicial?: number;
  observacion?: string;
  observaciones?: string;
}

export interface DenominacionEsperada {
  id_denominacion: number;
  valor: number;
  moneda: string;
  tipo: string;
  orden: number;
  cantidad_apertura: number;
  cantidad_recibida: number;
  cantidad_cambio: number;
  cantidad_esperada: number;
  subtotal_esperado: number;
  cantidad_contada?: number;
  subtotal_contado?: number;
  diferencia_unidades?: number;
}

export interface SesionActivaMonitoreo {
  id_sesion_caja: number;
  id_usuario: number;
  cajero_nombre: string;
  fecha_apertura: string;
  monto_inicial: number;
  observacion?: string;
  total_ventas: number;
  cant_ventas: number;
  ventas_efectivo: number;
  ventas_tarjeta: number;
  ventas_qr: number;
  efectivo_esperado: number;
  resumen?: any;
}

export interface UltimaSesionCerradaMonitoreo {
  id_sesion_caja: number;
  fecha_cierre: string;
  cajero_nombre: string;
  monto_inicial: number;
  efectivo_esperado: number;
  efectivo_contado: number;
  diferencia: number;
}

export interface CajaMonitoreoItem {
  id_caja: number;
  codigo_caja: string;
  nombre: string;
  estado_caja: string;
  id_sucursal: number;
  sucursal_nombre: string;
  sucursal_ciudad: string;
  id_empresa: number;
  empresa_nombre: string;
  estado_turno: 'ABIERTA' | 'CERRADA';
  sesion_activa?: SesionActivaMonitoreo | null;
  ultima_sesion_cerrada?: UltimaSesionCerradaMonitoreo | null;
}

export interface MonitoreoCajasResponse {
  success: boolean;
  cajas: CajaMonitoreoItem[];
  total_cajas: number;
  total_abiertas: number;
  total_cerradas: number;
  efectivo_total_en_cajas: number;
}

export interface SesionCajaHistorialItem {
  id_sesion_caja: number;
  id_caja: number;
  codigo_caja: string;
  nombre_caja: string;
  id_sucursal: number;
  sucursal_nombre: string;
  id_empresa: number;
  empresa_nombre: string;
  id_usuario: number;
  cajero_nombre: string;
  fecha_apertura: string;
  fecha_cierre?: string;
  monto_inicial: number;
  efectivo_esperado?: number;
  efectivo_contado?: number;
  diferencia?: number;
  estado: string;
  observacion_apertura?: string;
  observacion_cierre?: string;
}

export interface ResumenCajaResponse {
  success: boolean;
  resumen: {
    id_sesion_caja: number;
    estado: string;
    fecha_apertura: string;
    fecha_cierre?: string | null;
    monto_inicial: number;
    ventas_efectivo: number;
    ventas_tarjeta: number;
    ventas_electronicas: number;
    desglose_pagos: Record<string, number>;
    efectivo_esperado: number;
    efectivo_contado?: number | null;
    diferencia?: number | null;
    total_ventas: number;
    cant_ventas: number;
    cant_pagadas: number;
    cant_pendientes: number;
    denominaciones_esperadas?: DenominacionEsperada[];
  };
}

export interface CerrarCajaPayload {
  id_sesion_caja: number;
  conteo?: ConteoItemPayload[];
  conteo_items?: ConteoItemPayload[];
  observacion?: string;
  observaciones?: string;
}

export interface ProductoPos {
  id_producto: number;
  nombre: string;
  codigo?: string;
  id_categoria?: number;
  precio_base: number;
  imagen_url?: string;
  categoria_nombre?: string;
  tiene_variantes: boolean;
  stock_total_sucursal: number;
  stock_confirmado_servidor?: number;
  unidades_provisionales_offline?: number;
  variantes?: VariantePos[];
}

export interface VariantePos {
  id_variante: number;
  id_producto: number;
  sku: string;
  codigo_barras?: string;
  precio: number;
  talla_nombre?: string;
  color_nombre?: string;
  color_hex?: string;
  stock_disponible: number;
  stock_confirmado_servidor?: number;
  unidades_provisionales_offline?: number;
}

export interface ClientePos {
  id_cliente: number;
  nombre: string;
  apellido: string;
  nombre_completo: string;
  nit_ci?: string;
  correo?: string;
  telefono?: string;
}

export interface ItemVentaPayload {
  id_variante: number;
  cantidad: number;
  expected_unit_price?: number;
  producto_nombre?: string;
  talla?: string;
  color?: string;
  sku?: string;
}

export interface RegistrarVentaPayload {
  id_sesion_caja: number;
  id_cliente?: number | null;
  id_empresa?: number;
  id_sucursal?: number;
  id_reserva?: number | null;
  items: ItemVentaPayload[];
  descuento: number;
  observaciones?: string;
}

export interface RegistrarVentaContadoOfflinePayload extends RegistrarVentaPayload {
  metodo_tipo: 'EFECTIVO';
  id_metodo_pago?: number;
  monto_recibido: number;
  expected_total: number;
  nit_ci?: string;
  razon_social?: string;
  desglose_recibido?: DesgloseDenominacionPayload[];
  desglose_cambio?: DesgloseDenominacionPayload[];
}

export interface VentaPosItem {
  id_venta: number;
  codigo_venta: string;
  fecha: string;
  cliente: string;
  nit_ci?: string;
  cajero: string;
  total: number;
  subtotal: number;
  descuento: number;
  estado: string;
  cant_items: number;
  offline_operation_id?: string;
  offline_conflict_message?: string | null;
  monto_recibido?: number;
  cambio?: number;
}

export interface MetodoPagoPos {
  id_metodo_pago: number;
  nombre: string;
  tipo: string;
}

export interface VentaParaPago {
  id_venta: number;
  codigo_venta: string;
  fecha: string;
  estado: string;
  total: number;
  subtotal: number;
  descuento: number;
  id_cliente?: number | null;
  cliente_nombre?: string;
  cliente_correo?: string;
  nit_ci?: string;
  razon_social?: string;
  correo_facturacion?: string;
  tipo_documento?: string;
  items: Array<{
    id_detalle_venta: number;
    producto_nombre: string;
    sku: string;
    cantidad: number;
    precio_unitario: number;
    subtotal: number;
    talla?: string;
    color?: string;
  }>;
}

export interface DesgloseDenominacionPayload {
  id_denominacion: number;
  valor: number;
  cantidad: number;
  subtotal: number;
}

export interface ProcesarPagoCajaPayload {
  id_venta: number;
  id_metodo_pago: number;
  monto_recibido?: number;
  referencia_externa?: string;
  razon_social?: string;
  nit_ci?: string;
  correo_facturacion?: string;
  desglose_recibido?: DesgloseDenominacionPayload[];
  desglose_cambio?: DesgloseDenominacionPayload[];
}

export interface ResultadoPagoCaja {
  success: boolean;
  message: string;
  id_pago: number;
  id_venta: number;
  total: number;
  monto_recibido: number;
  cambio: number;
  metodo_pago: string;
  fecha_pago: string;
  estado_venta: string;
  desglose_recibido?: DesgloseDenominacionPayload[];
  desglose_cambio?: DesgloseDenominacionPayload[];
}

export interface DatosComprobanteVenta {
  id_venta: number;
  codigo_venta: string;
  fecha: string;
  estado: string;
  total: number;
  subtotal: number;
  descuento: number;
  nit_ci?: string;
  razon_social?: string;
  correo_facturacion?: string;
  tipo_documento?: string;
  id_cliente?: number | null;
  cliente_nombre?: string;
  cliente_correo?: string;
  items: Array<{
    id_detalle_venta: number;
    producto_nombre: string;
    sku: string;
    cantidad: number;
    precio_unitario: number;
    subtotal: number;
    talla?: string;
    color?: string;
  }>;
  pago?: {
    id_pago: number;
    monto: number;
    metodo: string;
    fecha: string;
    estado: string;
  };
}

export interface EmitirComprobantePayload {
  razon_social: string;
  nit_ci: string;
  correo_facturacion?: string;
  tipo_documento?: string;
  enviar_correo?: boolean;
}

const DEFAULT_DENOMINACIONES: Denominacion[] = [
  { id_denominacion: 1, valor: 200, moneda: 'BOB', tipo: 'BILLETE', orden: 1 },
  { id_denominacion: 2, valor: 100, moneda: 'BOB', tipo: 'BILLETE', orden: 2 },
  { id_denominacion: 3, valor: 50, moneda: 'BOB', tipo: 'BILLETE', orden: 3 },
  { id_denominacion: 4, valor: 20, moneda: 'BOB', tipo: 'BILLETE', orden: 4 },
  { id_denominacion: 5, valor: 10, moneda: 'BOB', tipo: 'BILLETE', orden: 5 },
  { id_denominacion: 6, valor: 5, moneda: 'BOB', tipo: 'MONEDA', orden: 6 },
  { id_denominacion: 7, valor: 2, moneda: 'BOB', tipo: 'MONEDA', orden: 7 },
  { id_denominacion: 8, valor: 1, moneda: 'BOB', tipo: 'MONEDA', orden: 8 },
  { id_denominacion: 9, valor: 0.5, moneda: 'BOB', tipo: 'MONEDA', orden: 9 },
];

@Injectable({
  providedIn: 'root'
})
export class CajaService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private idb = inject(IndexedDbService);
  private network = inject(NetworkStatusService);
  private syncQueue = inject(SyncQueueService);

  private cajaApiUrl = `${environment.apiUrl}/api/caja`;
  private posApiUrl = `${environment.apiUrl}/api/pos`;
  private comprobantesApiUrl = `${environment.apiUrl}/api/comprobantes`;

  private getScope(idSucursal?: number, idEmpresa?: number): {
    userId: number;
    tenantId: number;
    branchId: number;
    scopeKey: string;
  } {
    const user = this.authService.obtenerUsuario();
    const userId = Number(user?.id_usuario ?? user?.nro_usuario ?? 0);
    const tenantId = Number(idEmpresa || this.authService.getEffectiveCompanyId() || user?.id_empresa || 1);
    const branchId = Number(idSucursal || this.authService.activeBranch()?.id || user?.id_sucursal || 1);
    const scopeKey = `u:${userId}|e:${tenantId}|b:${branchId}`;
    return { userId, tenantId, branchId, scopeKey };
  }

  /**
   * Aplica descuentos provisionales de stock local a la lista de productos POS,
   * diferenciando `stock_confirmado_servidor` y `stock_total_sucursal` (disponible efectivo).
   */
  private applyProvisionalStockToProducts(productos: ProductoPos[], idSucursal?: number): ProductoPos[] {
    const provMap = this.syncQueue.getProvisionalStockMap(idSucursal ?? null);
    if (provMap.size === 0) {
      return (productos || []).map((p) => ({
        ...p,
        stock_confirmado_servidor: p.stock_confirmado_servidor ?? p.stock_total_sucursal,
        unidades_provisionales_offline: 0,
      }));
    }

    return (productos || []).map((p) => {
      const confirmed = Number(p.stock_confirmado_servidor ?? p.stock_total_sucursal ?? 0);
      let provProd = 0;
      if (Array.isArray(p.variantes) && p.variantes.length > 0) {
        for (const v of p.variantes) {
          provProd += provMap.get(Number(v.id_variante)) || 0;
        }
      } else {
        // Si las variantes están cacheadas por separado, revisar coincidencias en operaciones activas
        for (const op of this.syncQueue.operations()) {
          if (op.kind !== 'RESERVA_SOLICITUD' && op.kind !== 'VENTA_CONTADO') continue;
          if (op.status === 'synced' || op.status === 'failed_permanent') continue;
          const items = Array.isArray(op.payload?.['items']) ? op.payload['items'] : [];
          for (const it of items) {
            if (
              (it?.id_producto && Number(it.id_producto) === Number(p.id_producto)) ||
              (it?.producto_nombre && it.producto_nombre === p.nombre)
            ) {
              provProd += Number(it.cantidad || 0);
            }
          }
        }
      }

      return {
        ...p,
        stock_confirmado_servidor: confirmed,
        unidades_provisionales_offline: provProd,
        stock_total_sucursal: Math.max(0, confirmed - provProd),
      };
    });
  }

  private applyProvisionalStockToVariants(variantes: VariantePos[], idSucursal?: number): VariantePos[] {
    return (variantes || []).map((v) => {
      const confirmed = Number(v.stock_confirmado_servidor ?? v.stock_disponible ?? 0);
      const prov = this.syncQueue.getProvisionalDeltaForVariant(v.id_variante, idSucursal ?? null);
      return {
        ...v,
        stock_confirmado_servidor: confirmed,
        unidades_provisionales_offline: prov,
        stock_disponible: Math.max(0, confirmed - prov),
      };
    });
  }

  private buildOfflineVentasFromQueue(idSucursal?: number, idEmpresa?: number): VentaPosItem[] {
    const scope = this.getScope(idSucursal, idEmpresa);
    const user = this.authService.obtenerUsuario();
    const cajeroNombre = `${user?.nombre || ''} ${user?.apellido || ''}`.trim() || 'Cajero Actual';

    const ops = this.syncQueue
      .operations()
      .filter(
        (op: PendingOperation) =>
          op.kind === 'VENTA_CONTADO' &&
          op.status !== 'synced' &&
          (!scope.tenantId || !op.tenant_id || Number(op.tenant_id) === scope.tenantId) &&
          (!scope.branchId || !op.branch_id || Number(op.branch_id) === scope.branchId)
      );

    return ops.map((op, idx) => {
      const p = op.payload || {};
      const items = Array.isArray(p['items']) ? p['items'] : [];
      const cantItems = items.reduce((acc: number, it: any) => acc + Number(it?.cantidad || 0), 0);
      const isIncidence =
        op.status === 'reconciliation_required' ||
        Boolean(op.reconciliation_required) ||
        op.status === 'conflict' ||
        op.status === 'failed_permanent';

      const total = Number(p['expected_total'] ?? 0);
      const descuento = Number(p['descuento'] ?? 0);
      const montoRecibido = Number(p['monto_recibido'] ?? total);

      return {
        id_venta: -(idx + 1),
        codigo_venta: String(op.entity_id || p['codigo_venta_provisional'] || `OFFLINE-${op.operation_id.slice(0, 6).toUpperCase()}`),
        fecha: op.created_at,
        cliente: p['datos_facturacion']?.['razon_social'] || p['cliente_nombre'] || 'Cliente Mostrador (Offline)',
        nit_ci: p['datos_facturacion']?.['nit_ci'] || 'S/N',
        cajero: cajeroNombre,
        total,
        subtotal: Math.round((total + descuento) * 100) / 100,
        descuento,
        estado: isIncidence ? 'INCIDENCIA_CONCILIACION' : 'PENDIENTE_SYNC_OFFLINE',
        cant_items: cantItems,
        offline_operation_id: op.operation_id,
        offline_conflict_message: op.last_error || null,
        monto_recibido: montoRecibido,
        cambio: Math.max(0, Math.round((montoRecibido - total) * 100) / 100),
      };
    });
  }

  // --- MÓDULO CAJA ---
  obtenerDenominaciones(): Observable<{ success: boolean; denominaciones: Denominacion[] }> {
    const cacheKey = 'global_denominaciones_bob';
    if (!this.network.isOnline()) {
      return from(this.idb.get<{ key: string; denominaciones: Denominacion[] }>('metadata', cacheKey)).pipe(
        map((cached) => ({
          success: true,
          denominaciones: cached?.denominaciones?.length ? cached.denominaciones : DEFAULT_DENOMINACIONES,
        }))
      );
    }

    return this.http.get<{ success: boolean; denominaciones: Denominacion[] }>(`${this.cajaApiUrl}/denominaciones`).pipe(
      tap((res) => {
        if (res?.success && res.denominaciones?.length) {
          const nowMs = Date.now();
          void this.idb.put('metadata', {
            key: cacheKey,
            scope_key: 'public|e:1',
            tenant_id: 1,
            fetched_at_ms: nowMs,
            denominaciones: res.denominaciones,
          });
        }
      }),
      catchError((err) => {
        if (err?.status === 0) {
          return from(this.idb.get<{ key: string; denominaciones: Denominacion[] }>('metadata', cacheKey)).pipe(
            map((cached) => ({
              success: true,
              denominaciones: cached?.denominaciones?.length ? cached.denominaciones : DEFAULT_DENOMINACIONES,
            }))
          );
        }
        return throwError(() => err);
      })
    );
  }

  obtenerEstadoCaja(idSucursal?: number, idEmpresa?: number): Observable<CajaEstadoResponse> {
    let params = new HttpParams();
    if (idSucursal) params = params.set('id_sucursal', idSucursal.toString());
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());

    const scope = this.getScope(idSucursal, idEmpresa);
    const cacheKey = `${scope.scopeKey}_estado_caja`;

    if (!this.network.isOnline()) {
      return from(this.idb.get<{ key: string; data: CajaEstadoResponse }>('metadata', cacheKey)).pipe(
        map((cached) => {
          if (cached?.data) {
            return { ...cached.data, offline_cached: true };
          }
          return {
            success: true,
            tiene_sesion_activa: false,
            offline_cached: true,
          };
        })
      );
    }

    return this.http.get<CajaEstadoResponse>(`${this.cajaApiUrl}/estado`, { params }).pipe(
      tap((res) => {
        if (res?.success) {
          const nowMs = Date.now();
          void this.idb.put('metadata', {
            key: cacheKey,
            scope_key: scope.scopeKey,
            tenant_id: scope.tenantId,
            fetched_at_ms: nowMs,
            data: res,
          });
        }
      }),
      catchError((err) => {
        if (err?.status === 0) {
          return from(this.idb.get<{ key: string; data: CajaEstadoResponse }>('metadata', cacheKey)).pipe(
            map((cached) => {
              if (cached?.data) {
                return { ...cached.data, offline_cached: true };
              }
              throw err;
            })
          );
        }
        return throwError(() => err);
      })
    );
  }

  abrirCaja(payload: AbrirCajaPayload): Observable<any> {
    return this.http.post<any>(`${this.cajaApiUrl}/abrir`, payload).pipe(
      tap((res) => {
        const sesionId = res?.data?.id_sesion_caja;
        const cuotas = res?.data?.cuotas_contingencia;
        if (sesionId && Array.isArray(cuotas) && cuotas.length > 0) {
          void this.guardarCuotasContingenciaOffline(sesionId, cuotas);
        }
      })
    );
  }

  /**
   * CU38W / Migración 008: Consulta las cuotas de contingencia activas asignadas a la sesión de caja.
   */
  obtenerCuotasContingencia(idSesionCaja: number): Observable<{ success: boolean; total: number; cuotas: any[] }> {
    return this.http.get<{ success: boolean; total: number; cuotas: any[] }>(
      `${this.posApiUrl}/contingencia/cuotas?id_sesion_caja=${idSesionCaja}`
    ).pipe(
      tap((res) => {
        if (res?.success && Array.isArray(res?.cuotas)) {
          void this.guardarCuotasContingenciaOffline(idSesionCaja, res.cuotas);
        }
      })
    );
  }

  /**
   * Guarda o actualiza las cuotas de contingencia descargadas en IndexedDB para disponibilidad offline.
   */
  async guardarCuotasContingenciaOffline(idSesionCaja: number, cuotas: any[]): Promise<void> {
    const nowMs = Date.now();
    for (const c of cuotas || []) {
      const key = `caja:${idSesionCaja}|var:${c.id_variante}`;
      await this.idb.put('pos_contingency_quotas', {
        key,
        id_sesion_caja: idSesionCaja,
        id_variante: c.id_variante,
        sku: c.sku,
        producto_nombre: c.producto_nombre,
        cuota_asignada: c.cuota_asignada,
        cuota_consumida: c.cuota_consumida,
        cuota_disponible: c.cuota_disponible,
        fetched_at_ms: nowMs,
        updated_at: new Date(nowMs).toISOString(),
      });
    }
  }

  /**
   * Obtiene la cuota disponible local para una variante en la sesión activa.
   */
  async obtenerCuotaContingenciaLocal(idSesionCaja: number, idVariante: number): Promise<number | null> {
    try {
      const key = `caja:${idSesionCaja}|var:${idVariante}`;
      const record = await this.idb.get<any>('pos_contingency_quotas', key);
      return record ? Number(record.cuota_disponible ?? record.cuota_asignada ?? 0) : null;
    } catch {
      return null;
    }
  }

  obtenerResumenCaja(idSesionCaja: number): Observable<ResumenCajaResponse> {
    const scope = this.getScope();
    const cacheKey = `${scope.scopeKey}_resumen_caja_${idSesionCaja}`;

    const enrichWithOfflineCash = (res: ResumenCajaResponse): ResumenCajaResponse => {
      const offlineSales = this.buildOfflineVentasFromQueue(scope.branchId, scope.tenantId).filter(
        (v) => v.estado === 'PENDIENTE_SYNC_OFFLINE'
      );
      if (offlineSales.length === 0 || !res?.resumen) return res;
      const extraCash = offlineSales.reduce((acc, v) => acc + Number(v.total || 0), 0);
      return {
        ...res,
        resumen: {
          ...res.resumen,
          ventas_efectivo: Math.round((Number(res.resumen.ventas_efectivo || 0) + extraCash) * 100) / 100,
          efectivo_esperado: Math.round((Number(res.resumen.efectivo_esperado || 0) + extraCash) * 100) / 100,
          total_ventas: Math.round((Number(res.resumen.total_ventas || 0) + extraCash) * 100) / 100,
          cant_ventas: Number(res.resumen.cant_ventas || 0) + offlineSales.length,
        },
      };
    };

    if (!this.network.isOnline()) {
      return from(this.idb.get<{ key: string; data: ResumenCajaResponse }>('metadata', cacheKey)).pipe(
        map((cached) => {
          if (cached?.data) {
            return enrichWithOfflineCash(cached.data);
          }
          return {
            success: true,
            resumen: {
              id_sesion_caja: idSesionCaja,
              estado: 'ABIERTA',
              fecha_apertura: new Date().toISOString(),
              monto_inicial: 0,
              ventas_efectivo: 0,
              ventas_tarjeta: 0,
              ventas_electronicas: 0,
              desglose_pagos: {},
              efectivo_esperado: 0,
              total_ventas: 0,
              cant_ventas: 0,
              cant_pagadas: 0,
              cant_pendientes: 0,
            },
          };
        })
      );
    }

    return this.http.get<ResumenCajaResponse>(`${this.cajaApiUrl}/resumen?id_sesion_caja=${idSesionCaja}`).pipe(
      tap((res) => {
        if (res?.success) {
          const nowMs = Date.now();
          void this.idb.put('metadata', {
            key: cacheKey,
            scope_key: scope.scopeKey,
            tenant_id: scope.tenantId,
            fetched_at_ms: nowMs,
            data: res,
          });
        }
      }),
      map((res) => enrichWithOfflineCash(res)),
      catchError((err) => {
        if (err?.status === 0) {
          return from(this.idb.get<{ key: string; data: ResumenCajaResponse }>('metadata', cacheKey)).pipe(
            map((cached) => {
              if (cached?.data) return enrichWithOfflineCash(cached.data);
              throw err;
            })
          );
        }
        return throwError(() => err);
      })
    );
  }

  cerrarCaja(payload: CerrarCajaPayload): Observable<any> {
    return this.http.post<any>(`${this.cajaApiUrl}/cerrar`, payload);
  }

  // --- MÓDULO POS ---
  buscarProductos(
    query?: string,
    idCategoria?: number,
    idSucursal?: number,
    idEmpresa?: number
  ): Observable<{ success: boolean; productos: ProductoPos[]; total: number; offline?: boolean }> {
    let params = new HttpParams();
    if (query && query.trim()) params = params.set('q', query.trim());
    if (idCategoria) params = params.set('id_categoria', idCategoria.toString());
    if (idSucursal) params = params.set('id_sucursal', idSucursal.toString());
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());

    const scope = this.getScope(idSucursal, idEmpresa);
    const baseCacheKey = `${scope.scopeKey}_pos_productos_all`;

    const filterLocalCatalog = (allProducts: ProductoPos[]): { success: boolean; productos: ProductoPos[]; total: number; offline: boolean } => {
      let list = this.applyProvisionalStockToProducts(allProducts || [], scope.branchId);
      if (idCategoria) {
        list = list.filter((p) => Number(p.id_categoria) === Number(idCategoria));
      }
      if (query && query.trim()) {
        const qNorm = query.trim().toLowerCase();
        list = list.filter(
          (p) =>
            (p.nombre || '').toLowerCase().includes(qNorm) ||
            (p.codigo || '').toLowerCase().includes(qNorm) ||
            (p.categoria_nombre || '').toLowerCase().includes(qNorm)
        );
      }
      return {
        success: true,
        productos: list,
        total: list.length,
        offline: true,
      };
    };

    if (!this.network.isOnline()) {
      return from(this.idb.get<{ key: string; productos: ProductoPos[] }>('metadata', baseCacheKey)).pipe(
        map((cached) => filterLocalCatalog(cached?.productos || []))
      );
    }

    return this.http.get<{ success: boolean; productos: ProductoPos[]; total: number }>(`${this.posApiUrl}/productos`, { params }).pipe(
      tap((res) => {
        if (res?.success && Array.isArray(res.productos)) {
          const nowMs = Date.now();
          if (!query?.trim() && !idCategoria) {
            void this.idb.put('metadata', {
              key: baseCacheKey,
              scope_key: scope.scopeKey,
              tenant_id: scope.tenantId,
              fetched_at_ms: nowMs,
              productos: res.productos,
            });
          }
          // Si cada producto trae variantes embebidas, pre-cachearlas por id_producto para uso offline inmediato
          for (const prod of res.productos) {
            if (Array.isArray(prod.variantes) && prod.variantes.length > 0) {
              const varKey = `${scope.scopeKey}_pos_variantes_${prod.id_producto}`;
              void this.idb.put('metadata', {
                key: varKey,
                scope_key: scope.scopeKey,
                tenant_id: scope.tenantId,
                fetched_at_ms: nowMs,
                variantes: prod.variantes,
              });
            }
          }
        }
      }),
      map((res) => {
        const adjusted = this.applyProvisionalStockToProducts(res.productos || [], scope.branchId);
        return {
          ...res,
          productos: adjusted,
          total: adjusted.length,
        };
      }),
      catchError((err) => {
        if (err?.status === 0) {
          return from(this.idb.get<{ key: string; productos: ProductoPos[] }>('metadata', baseCacheKey)).pipe(
            map((cached) => filterLocalCatalog(cached?.productos || []))
          );
        }
        return throwError(() => err);
      })
    );
  }

  obtenerVariantesProducto(
    idProducto: number,
    idSucursal?: number,
    idEmpresa?: number
  ): Observable<{ success: boolean; variantes: VariantePos[]; offline?: boolean }> {
    let params = new HttpParams();
    if (idSucursal) params = params.set('id_sucursal', idSucursal.toString());
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());

    const scope = this.getScope(idSucursal, idEmpresa);
    const varCacheKey = `${scope.scopeKey}_pos_variantes_${idProducto}`;

    if (!this.network.isOnline()) {
      return from(this.idb.get<{ key: string; variantes: VariantePos[] }>('metadata', varCacheKey)).pipe(
        map((cached) => ({
          success: true,
          variantes: this.applyProvisionalStockToVariants(cached?.variantes || [], scope.branchId),
          offline: true,
        }))
      );
    }

    return this.http.get<{ success: boolean; variantes: VariantePos[] }>(`${this.posApiUrl}/productos/${idProducto}/variantes`, { params }).pipe(
      tap((res) => {
        if (res?.success && Array.isArray(res.variantes)) {
          const nowMs = Date.now();
          void this.idb.put('metadata', {
            key: varCacheKey,
            scope_key: scope.scopeKey,
            tenant_id: scope.tenantId,
            fetched_at_ms: nowMs,
            variantes: res.variantes,
          });
        }
      }),
      map((res) => ({
        ...res,
        variantes: this.applyProvisionalStockToVariants(res.variantes || [], scope.branchId),
      })),
      catchError((err) => {
        if (err?.status === 0) {
          return from(this.idb.get<{ key: string; variantes: VariantePos[] }>('metadata', varCacheKey)).pipe(
            map((cached) => ({
              success: true,
              variantes: this.applyProvisionalStockToVariants(cached?.variantes || [], scope.branchId),
              offline: true,
            }))
          );
        }
        return throwError(() => err);
      })
    );
  }

  buscarClientes(query: string, idEmpresa?: number): Observable<{ success: boolean; clientes: ClientePos[] }> {
    if (!this.network.isOnline()) {
      return of({ success: true, clientes: [] });
    }
    let params = new HttpParams().set('q', query.trim());
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    return this.http.get<{ success: boolean; clientes: ClientePos[] }>(`${this.posApiUrl}/clientes/buscar`, { params });
  }

  registrarVentaPos(payload: RegistrarVentaPayload): Observable<any> {
    return this.http.post<any>(`${this.posApiUrl}/ventas`, payload);
  }

  /**
   * CU24W: Registra una venta de contado en EFECTIVO sin conexión en la cola persistente (`SyncQueueService`),
   * descontando stock provisional local y generando comprobante provisional.
   * Rechaza cualquier método de pago electrónico.
   */
  async registrarVentaContadoOffline(payload: RegistrarVentaContadoOfflinePayload): Promise<{
    success: boolean;
    offline_queued: boolean;
    message: string;
    venta: {
      id_venta: number;
      codigo_venta: string;
      total: number;
      monto_recibido: number;
      cambio: number;
      estado: string;
      operation_id: string;
    };
  }> {
    if (String(payload.metodo_tipo || 'EFECTIVO').toUpperCase() !== 'EFECTIVO') {
      throw new Error('Los pagos electrónicos (Tarjeta, QR, PayPal) están deshabilitados sin conexión. Solo se permite EFECTIVO.');
    }

    const total = Math.round(Number(payload.expected_total || 0) * 100) / 100;
    const montoRecibido = Math.round(Number(payload.monto_recibido ?? total) * 100) / 100;
    if (montoRecibido < total) {
      throw new Error(`El monto recibido en efectivo (Bs. ${montoRecibido.toFixed(2)}) no cubre el total de la venta (Bs. ${total.toFixed(2)}).`);
    }

    const scope = this.getScope(payload.id_sucursal, payload.id_empresa);
    const opId = this.syncQueue.generateOperationId();
    const codigoTemp = `OFFLINE-E${scope.tenantId}-S${scope.branchId}-${opId.slice(0, 6).toUpperCase()}`;
    const cantPrendas = (payload.items || []).reduce((acc, it) => acc + Number(it.cantidad || 0), 0);
    const cambio = Math.max(0, Math.round((montoRecibido - total) * 100) / 100);

    await this.syncQueue.enqueue({
      operationId: opId,
      kind: 'VENTA_CONTADO',
      tenantId: scope.tenantId,
      branchId: scope.branchId,
      entityId: codigoTemp,
      summaryLabel: `Venta Efectivo POS (${codigoTemp}) · ${cantPrendas} u. · Bs. ${total.toFixed(2)}`,
      payload: {
        id_sucursal: scope.branchId,
        id_empresa: scope.tenantId,
        id_sesion_caja: payload.id_sesion_caja,
        id_cliente: payload.id_cliente ?? null,
        metodo_tipo: 'EFECTIVO',
        id_metodo_pago: payload.id_metodo_pago ?? null,
        descuento: Number(payload.descuento || 0),
        monto_recibido: montoRecibido,
        expected_total: total,
        contingencia: true,
        es_contingencia_offline: true,
        comprobante_tipo_provisional: 'PROVISIONAL_CONTINGENCIA',
        codigo_venta_provisional: codigoTemp,
        observaciones: payload.observaciones || null,
        datos_facturacion: {
          nit_ci: payload.nit_ci || 'S/N',
          razon_social: payload.razon_social || 'SIN NOMBRE',
        },
        desglose_recibido: payload.desglose_recibido || [],
        desglose_cambio: payload.desglose_cambio || [],
        items: (payload.items || []).map((it) => ({
          id_variante: it.id_variante,
          cantidad: it.cantidad,
          expected_unit_price: it.expected_unit_price,
          producto_nombre: it.producto_nombre,
          talla: it.talla,
          color: it.color,
          sku: it.sku,
        })),
      },
    });

    return {
      success: true,
      offline_queued: true,
      message: `Venta en efectivo registrada localmente (${codigoTemp}). Se sincronizará automáticamente al recuperar la conexión.`,
      venta: {
        id_venta: -1,
        codigo_venta: codigoTemp,
        total,
        monto_recibido: montoRecibido,
        cambio,
        estado: 'PENDIENTE_SYNC_OFFLINE',
        operation_id: opId,
      },
    };
  }

  obtenerHistorialVentas(idSesionCaja: number): Observable<{ success: boolean; ventas: VentaPosItem[]; total: number }> {
    const scope = this.getScope();
    const cacheKey = `${scope.scopeKey}_pos_ventas_${idSesionCaja}`;

    const mergeWithOfflineSales = (serverSales: VentaPosItem[]): VentaPosItem[] => {
      const offlineSales = this.buildOfflineVentasFromQueue(scope.branchId, scope.tenantId);
      return [...offlineSales, ...(serverSales || [])];
    };

    if (!this.network.isOnline()) {
      return from(this.idb.get<{ key: string; ventas: VentaPosItem[] }>('metadata', cacheKey)).pipe(
        map((cached) => {
          const merged = mergeWithOfflineSales(cached?.ventas || []);
          return {
            success: true,
            ventas: merged,
            total: merged.length,
          };
        })
      );
    }

    return this.http.get<{ success: boolean; ventas: VentaPosItem[]; total: number }>(`${this.posApiUrl}/ventas?id_sesion_caja=${idSesionCaja}`).pipe(
      tap((res) => {
        if (res?.success && Array.isArray(res.ventas)) {
          const nowMs = Date.now();
          void this.idb.put('metadata', {
            key: cacheKey,
            scope_key: scope.scopeKey,
            tenant_id: scope.tenantId,
            fetched_at_ms: nowMs,
            ventas: res.ventas,
          });
        }
      }),
      map((res) => {
        const merged = mergeWithOfflineSales(res.ventas || []);
        return {
          ...res,
          ventas: merged,
          total: merged.length,
        };
      }),
      catchError((err) => {
        if (err?.status === 0) {
          return from(this.idb.get<{ key: string; ventas: VentaPosItem[] }>('metadata', cacheKey)).pipe(
            map((cached) => {
              const merged = mergeWithOfflineSales(cached?.ventas || []);
              return {
                success: true,
                ventas: merged,
                total: merged.length,
              };
            })
          );
        }
        return throwError(() => err);
      })
    );
  }

  obtenerDetalleVenta(idVenta: number): Observable<any> {
    return this.http.get<any>(`${this.posApiUrl}/ventas/${idVenta}`);
  }

  // --- MÓDULO W28: PAGO EN CAJA ---
  obtenerMetodosPagoCaja(): Observable<{ success: boolean; metodos: MetodoPagoPos[] }> {
    return this.http.get<{ success: boolean; metodos: MetodoPagoPos[] }>(`${this.cajaApiUrl}/pagos/metodos`);
  }

  obtenerVentaParaPago(idVenta: number): Observable<{ success: boolean; venta: VentaParaPago }> {
    return this.http.get<{ success: boolean; venta: VentaParaPago }>(`${this.cajaApiUrl}/pagos/venta/${idVenta}`);
  }

  procesarPagoCaja(payload: ProcesarPagoCajaPayload): Observable<ResultadoPagoCaja> {
    return this.http.post<ResultadoPagoCaja>(`${this.cajaApiUrl}/pagos/procesar`, payload);
  }

  // --- MÓDULO W29: EMISIÓN COMPROBANTE ---
  obtenerDatosComprobanteVenta(idVenta: number): Observable<{ success: boolean; venta: DatosComprobanteVenta }> {
    return this.http.get<{ success: boolean; venta: DatosComprobanteVenta }>(`${this.comprobantesApiUrl}/venta/${idVenta}/datos`);
  }

  emitirComprobanteVenta(idVenta: number, payload: EmitirComprobantePayload): Observable<{ success: boolean; message: string; pdf_url: string; correo_enviado: boolean }> {
    return this.http.post<{ success: boolean; message: string; pdf_url: string; correo_enviado: boolean }>(`${this.comprobantesApiUrl}/venta/${idVenta}/emitir`, payload);
  }

  descargarComprobantePdf(idVenta: number): Observable<Blob> {
    return this.http.get(`${this.comprobantesApiUrl}/venta/${idVenta}/pdf`, { responseType: 'blob' });
  }

  // --- MÓDULO SUPERVISIÓN DE CAJAS (TIENDAS Y SUCURSALES) ---
  monitorearCajas(idEmpresa?: number, idSucursal?: number, estado?: string): Observable<MonitoreoCajasResponse> {
    let params = new HttpParams();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    if (idSucursal) params = params.set('id_sucursal', idSucursal.toString());
    if (estado && estado !== 'TODAS') params = params.set('estado', estado);
    return this.http.get<MonitoreoCajasResponse>(`${this.cajaApiUrl}/monitoreo`, { params });
  }

  obtenerHistorialSesiones(idEmpresa?: number, idSucursal?: number, idCaja?: number, limite: number = 50): Observable<{ success: boolean; sesiones: SesionCajaHistorialItem[]; total: number }> {
    let params = new HttpParams().set('limite', limite.toString());
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());
    if (idSucursal) params = params.set('id_sucursal', idSucursal.toString());
    if (idCaja) params = params.set('id_caja', idCaja.toString());
    return this.http.get<{ success: boolean; sesiones: SesionCajaHistorialItem[]; total: number }>(`${this.cajaApiUrl}/sesiones-historial`, { params });
  }

  crearCaja(payload: { id_sucursal: number; id_empresa?: number; nombre: string; codigo_caja?: string }): Observable<any> {
    return this.http.post<any>(`${this.cajaApiUrl}/crear`, payload);
  }
}
