import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, from, throwError } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';
import { IndexedDbService } from '../../../core/storage/indexed-db.service';
import { NetworkStatusService } from '../../../core/network/network-status.service';
import { SyncQueueService, PendingOperation } from '../../../core/sync/sync-queue.service';

export interface ItemReservaInput {
  id_variante: number;
  cantidad: number;
  expected_unit_price?: number;
  producto_nombre?: string;
  talla?: string;
  color?: string;
  codigo_hex?: string;
  imagen_url?: string | null;
}

export interface CrearReservaRequest {
  id_sucursal: number;
  fecha_hora_visita: string;
  observaciones?: string;
  items: ItemReservaInput[];
  id_empresa?: number;
  con_pago?: boolean;
  monto_pagado?: number;
}

export interface CrearReservaResponse {
  success: boolean;
  message: string;
  offline_queued?: boolean;
  data: {
    id_reserva: number;
    codigo_reserva: string;
    estado: string;
    fecha_hora_visita: string;
    id_sucursal: number;
    total_prendas: number;
    con_pago?: boolean;
    estado_pago?: string;
    monto_pagado?: number;
    items: Array<{
      id_variante: number;
      sku: string;
      producto_nombre: string;
      cantidad: number;
    }>;
  };
}

export interface ReservaResumen {
  id_reserva: number;
  codigo_reserva: string;
  fecha_reserva: string | null;
  fecha_hora_visita: string | null;
  estado: 'PENDIENTE' | 'CONFIRMADA' | 'ATENDIDA' | 'CANCELADA' | 'VENCIDA' | string;
  observaciones: string | null;
  motivo_cancelacion: string | null;
  con_pago?: boolean;
  estado_pago?: 'SIN_PAGO' | 'PAGADO' | 'REEMBOLSADO' | string;
  monto_pagado?: number;
  sucursal: {
    id_sucursal: number;
    nombre: string;
    direccion: string;
    telefono: string;
    ciudad: string;
    departamento: string;
  };
  total_prendas: number;
  items: Array<{
    id_detalle_reserva: number;
    id_variante: number;
    cantidad: number;
    estado_item: string;
    sku: string;
    precio: number;
    id_producto: number;
    producto_nombre: string;
    codigo_producto: string;
    talla: string;
    color: string;
    codigo_hex: string;
    imagen_url: string | null;
  }>;
  offline_operation_id?: string;
  offline_conflict_message?: string | null;
}

export type ReservaData = ReservaResumen;

@Injectable({
  providedIn: 'root',
})
export class ReservaService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly idb = inject(IndexedDbService);
  private readonly network = inject(NetworkStatusService);
  private readonly syncQueue = inject(SyncQueueService);
  private readonly apiUrl = `${environment.apiUrl}/api/reservas`;

  private getCurrentScope(empresaId?: number): { userId: number; tenantId: number; branchId: number | null; scopeKey: string } {
    const user = this.authService.obtenerUsuario();
    const userId = Number(user?.id_usuario ?? user?.nro_usuario ?? 0);
    const tenantId = Number(empresaId || this.authService.getEffectiveCompanyId() || user?.id_empresa || 1);
    const branchId = this.authService.activeBranch()?.id ?? null;
    const scopeKey = `u:${userId}|e:${tenantId}|b:${branchId ?? 'all'}`;
    return { userId, tenantId, branchId, scopeKey };
  }

  /**
   * Transforma las operaciones `RESERVA_SOLICITUD` pendientes o en conflicto en objetos `ReservaResumen`
   * para que el usuario las consulte en `/mis-reservas` incluso tras reiniciar la PWA sin conexión (CU10W / CU37W).
   */
  private buildOfflineReservasFromQueue(empresaId?: number): ReservaResumen[] {
    const scope = this.getCurrentScope(empresaId);
    const tid = scope.tenantId;

    const ops = this.syncQueue
      .operations()
      .filter(
        (op: PendingOperation) =>
          op.kind === 'RESERVA_SOLICITUD' &&
          op.status !== 'synced' &&
          (!tid || !op.tenant_id || Number(op.tenant_id) === tid)
      );

    return ops.map((op, idx) => {
      const p = op.payload || {};
      const rawItems = Array.isArray(p['items']) ? p['items'] : [];
      const totalPrendas = rawItems.reduce((acc: number, it: any) => acc + Number(it?.cantidad || 0), 0);
      const isConflict = op.status === 'conflict' || op.status === 'failed_permanent';

      return {
        id_reserva: -(idx + 1),
        codigo_reserva: p['codigo_reserva_provisional'] || `SOL-OFFLINE-${op.operation_id.slice(0, 6).toUpperCase()}`,
        fecha_reserva: op.created_at,
        fecha_hora_visita: p['fecha_hora_visita'] || op.created_at,
        estado: isConflict ? 'EN_CONFLICTO_SYNC' : 'SOLICITUD_PENDIENTE_ONLINE',
        observaciones: p['observaciones'] || 'Solicitud registrada sin conexión; se confirmará automáticamente al reconectar.',
        motivo_cancelacion: isConflict ? (op.last_error || 'Conflicto detectado al sincronizar con la sucursal.') : null,
        con_pago: false,
        estado_pago: 'SIN_PAGO',
        monto_pagado: 0,
        sucursal: {
          id_sucursal: Number(p['id_sucursal'] || op.branch_id || 0),
          nombre: p['sucursal_nombre'] || `Sucursal #${p['id_sucursal'] || op.branch_id || 1}`,
          direccion: p['sucursal_direccion'] || 'Pendiente de confirmación en servidor',
          telefono: '',
          ciudad: p['sucursal_ciudad'] || 'Bolivia',
          departamento: '',
        },
        total_prendas: totalPrendas,
        items: rawItems.map((it: any, itemIdx: number) => ({
          id_detalle_reserva: -(itemIdx + 1),
          id_variante: Number(it?.id_variante || 0),
          cantidad: Number(it?.cantidad || 1),
          estado_item: isConflict ? 'CONFLICTO' : 'PENDIENTE_SYNC',
          sku: it?.sku || `VAR-${it?.id_variante || 0}`,
          precio: Number(it?.expected_unit_price || 0),
          id_producto: Number(it?.id_producto || 0),
          producto_nombre: it?.producto_nombre || p['producto_nombre'] || 'Prenda Aurora',
          codigo_producto: it?.codigo_producto || '',
          talla: it?.talla || p['talla'] || '-',
          color: it?.color || p['color'] || '-',
          codigo_hex: it?.codigo_hex || '#18181b',
          imagen_url: it?.imagen_url || null,
        })),
        offline_operation_id: op.operation_id,
        offline_conflict_message: op.last_error || null,
      };
    });
  }

  /**
   * CU10W: Crea una nueva reserva.
   * - Si incluye pago anticipado (`con_pago: true`) y no hay red, bloquea explícitamente (Regla #6).
   * - Si es reserva en tienda sin pago y no hay conexión, la registra como
   *   `SOLICITUD_PENDIENTE_ONLINE` en la cola persistente `SyncQueueService` y descuenta stock provisional.
   */
  crearReserva(
    payload: CrearReservaRequest,
    meta?: {
      productoNombre?: string;
      sucursalNombre?: string;
      sucursalDireccion?: string;
      sucursalCiudad?: string;
      talla?: string;
      color?: string;
      codigoHex?: string;
      imagenUrl?: string | null;
      expectedUnitPrice?: number;
    }
  ): Observable<CrearReservaResponse> {
    if (!this.network.isOnline()) {
      if (payload.con_pago) {
        return throwError(() => ({
          status: 409,
          error: {
            detail:
              'Las reservas con pago anticipado electrónico requieren conexión en tiempo real. Puedes cambiar a "Pagar en Tienda" para registrar tu solicitud offline.',
          },
        }));
      }
      return from(this.enqueueReservaOffline(payload, meta));
    }

    return this.http.post<CrearReservaResponse>(this.apiUrl, payload).pipe(
      catchError((err) => {
        if (err?.status === 0 && !payload.con_pago) {
          return from(this.enqueueReservaOffline(payload, meta));
        }
        return throwError(() => err);
      })
    );
  }

  private async enqueueReservaOffline(
    payload: CrearReservaRequest,
    meta?: {
      productoNombre?: string;
      sucursalNombre?: string;
      sucursalDireccion?: string;
      sucursalCiudad?: string;
      talla?: string;
      color?: string;
      codigoHex?: string;
      imagenUrl?: string | null;
      expectedUnitPrice?: number;
    }
  ): Promise<CrearReservaResponse> {
    const scope = this.getCurrentScope(payload.id_empresa);
    const tenantId = scope.tenantId;
    const totalPrendas = (payload.items || []).reduce((acc, it) => acc + Number(it.cantidad || 0), 0);
    const labelProducto = meta?.productoNombre ? `${meta.productoNombre}` : `${totalPrendas} prenda(s)`;
    const labelSucursal = meta?.sucursalNombre ? ` en ${meta.sucursalNombre}` : '';
    const opId = this.syncQueue.generateOperationId();
    const codigoTemp = `SOL-OFFLINE-${opId.slice(0, 6).toUpperCase()}`;

    const enrichedItems = (payload.items || []).map((it) => ({
      id_variante: it.id_variante,
      cantidad: it.cantidad,
      expected_unit_price: it.expected_unit_price ?? meta?.expectedUnitPrice,
      producto_nombre: it.producto_nombre || meta?.productoNombre || 'Prenda reservada (offline)',
      talla: it.talla || meta?.talla || '-',
      color: it.color || meta?.color || '-',
      codigo_hex: it.codigo_hex || meta?.codigoHex || '#18181b',
      imagen_url: it.imagen_url ?? meta?.imagenUrl ?? null,
    }));

    const op = await this.syncQueue.enqueue({
      operationId: opId,
      kind: 'RESERVA_SOLICITUD',
      tenantId,
      branchId: payload.id_sucursal,
      entityId: codigoTemp,
      summaryLabel: `Solicitud de reserva: ${labelProducto}${labelSucursal} (${payload.fecha_hora_visita})`,
      payload: {
        ...payload,
        items: enrichedItems,
        con_pago: false,
        monto_pagado: 0,
        codigo_reserva_provisional: codigoTemp,
        producto_nombre: meta?.productoNombre,
        sucursal_nombre: meta?.sucursalNombre,
        sucursal_direccion: meta?.sucursalDireccion,
        sucursal_ciudad: meta?.sucursalCiudad,
        talla: meta?.talla,
        color: meta?.color,
      },
    });

    return {
      success: true,
      offline_queued: true,
      message:
        'Solicitud de reserva guardada en este dispositivo (SOLICITUD_PENDIENTE_ONLINE). Se confirmará automáticamente al recuperar la conexión.',
      data: {
        id_reserva: -1,
        codigo_reserva: codigoTemp,
        estado: 'SOLICITUD_PENDIENTE_ONLINE',
        fecha_hora_visita: payload.fecha_hora_visita,
        id_sucursal: payload.id_sucursal,
        total_prendas: totalPrendas,
        con_pago: false,
        estado_pago: 'SIN_PAGO',
        monto_pagado: 0,
        items: enrichedItems.map((it) => ({
          id_variante: it.id_variante,
          sku: `OFFLINE-${op.operation_id.slice(0, 4)}`,
          producto_nombre: it.producto_nombre,
          cantidad: it.cantidad,
        })),
      },
    };
  }

  /**
   * Obtiene el listado de reservas del cliente autenticado (con respaldo offline en IndexedDB
   * y fusión en vivo con las solicitudes de reserva pendientes en `SyncQueueService`).
   */
  obtenerMisReservas(
    estado?: string,
    idEmpresa?: number
  ): Observable<{ success: boolean; total: number; data: ReservaResumen[]; offline?: boolean }> {
    let params = new HttpParams();
    if (estado && estado !== 'TODOS') {
      params = params.set('estado', estado);
    }
    if (idEmpresa) {
      params = params.set('id_empresa', idEmpresa.toString());
    }

    const scope = this.getCurrentScope(idEmpresa);
    const cacheKey = `${scope.scopeKey}_mis_reservas_${estado || 'TODOS'}`;

    const mergeWithOfflineQueue = (serverList: ReservaResumen[]): ReservaResumen[] => {
      const offlinePending = this.buildOfflineReservasFromQueue(idEmpresa);
      const filteredOffline =
        !estado || estado === 'TODOS' || estado === 'PENDIENTE'
          ? offlinePending
          : offlinePending.filter((r) => r.estado === estado);
      return [...filteredOffline, ...(serverList || [])];
    };

    if (!this.network.isOnline()) {
      return from(this.idb.get<{ key: string; data: ReservaResumen[] }>('metadata', cacheKey)).pipe(
        map((cached) => {
          const merged = mergeWithOfflineQueue(cached?.data || []);
          return {
            success: true,
            total: merged.length,
            data: merged,
            offline: true,
          };
        })
      );
    }

    return this.http
      .get<{ success: boolean; total: number; data: ReservaResumen[] }>(`${this.apiUrl}/mis-reservas`, { params })
      .pipe(
        tap((res) => {
          if (res?.data) {
            const nowMs = Date.now();
            void this.idb.put('metadata', {
              key: cacheKey,
              scope_key: scope.scopeKey,
              tenant_id: scope.tenantId,
              fetched_at_ms: nowMs,
              data: res.data,
              updated_at: new Date(nowMs).toISOString(),
            });
          }
        }),
        map((res) => {
          const merged = mergeWithOfflineQueue(res?.data || []);
          return {
            ...res,
            total: merged.length,
            data: merged,
          };
        }),
        catchError((err) => {
          if (err?.status === 0) {
            return from(this.idb.get<{ key: string; data: ReservaResumen[] }>('metadata', cacheKey)).pipe(
              map((cached) => {
                const merged = mergeWithOfflineQueue(cached?.data || []);
                return {
                  success: true,
                  total: merged.length,
                  data: merged,
                  offline: true,
                };
              })
            );
          }
          return throwError(() => err);
        })
      );
  }

  /**
   * Obtiene el detalle completo de una reserva específica.
   */
  obtenerDetalleReserva(idReserva: number): Observable<{ success: boolean; data: ReservaResumen }> {
    return this.http.get<{ success: boolean; data: ReservaResumen }>(`${this.apiUrl}/${idReserva}`);
  }

  /**
   * Cancela una reserva activa devolviendo el stock en el servidor (requiere red).
   */
  cancelarReserva(idReserva: number, motivo?: string): Observable<{ success: boolean; message: string; data: any }> {
    return this.http.patch<{ success: boolean; message: string; data: any }>(`${this.apiUrl}/${idReserva}/cancelar`, {
      motivo: motivo || null,
    });
  }
}
