import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { BehaviorSubject, Observable, catchError, finalize, from, of, shareReplay, switchMap, tap, throwError } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';
import { CachedRecord, IndexedDbService } from '../../../core/storage/indexed-db.service';
import { NetworkStatusService } from '../../../core/network/network-status.service';
import { SyncQueueService } from '../../../core/sync/sync-queue.service';

export interface ItemCarrito {
  id_detalle_carrito: number;
  id_variante: number;
  id_producto: number;
  producto_nombre: string;
  codigo_producto?: string;
  talla_nombre: string;
  color_nombre: string;
  codigo_hex: string;
  sku?: string;
  imagen_url?: string | null;
  cantidad: number;
  precio_unitario: number;
  subtotal: number;
  stock_disponible: number;
  disponible: boolean;
  advertencia_stock?: string | null;
  pendiente_sincronizacion?: boolean;
}

export interface CarritoData {
  id_carrito: number;
  id_empresa: number;
  nombre_empresa: string;
  items: ItemCarrito[];
  total_items: number;
  subtotal: number;
  descuento: number;
  total: number;
  puede_continuar_compra: boolean;
  _offline_draft?: boolean;
}

export interface AgregarItemMeta {
  id_producto?: number;
  producto_nombre?: string;
  talla_nombre?: string;
  color_nombre?: string;
  codigo_hex?: string;
  precio_unitario?: number;
  imagen_url?: string | null;
  stock_disponible?: number;
}

const CART_TTL_MS = 7 * 24 * 60 * 60 * 1000;

@Injectable({
  providedIn: 'root'
})
export class CarritoService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private indexedDb = inject(IndexedDbService);
  private networkStatus = inject(NetworkStatusService);
  private syncQueue = inject(SyncQueueService);
  private apiUrl = `${environment.apiUrl}/api/carrito`;

  private carritoSubject = new BehaviorSubject<CarritoData | null>(null);
  public carrito$ = this.carritoSubject.asObservable();

  private totalItemsSubject = new BehaviorSubject<number>(0);
  public totalItems$ = this.totalItemsSubject.asObservable();

  private subtotalSubject = new BehaviorSubject<number>(0);
  public subtotal$ = this.subtotalSubject.asObservable();

  private drawerAbiertoSubject = new BehaviorSubject<boolean>(false);
  public drawerAbierto$ = this.drawerAbiertoSubject.asObservable();

  private cargandoSubject = new BehaviorSubject<boolean>(false);
  public cargando$ = this.cargandoSubject.asObservable();

  public isOfflineDraft = signal<boolean>(false);

  // Tenant activo actualmente en el cliente
  private currentEmpresaId: number | null = null;
  private inFlightLoad$: Observable<{ success: boolean; data: CarritoData } | null> | null = null;
  private inFlightEmpresaId: number | undefined = undefined;

  constructor() {
    // Al completarse la sincronización en segundo plano, refrescar el carrito con la respuesta oficial del servidor
    this.syncQueue.syncCompleted$.subscribe((evt) => {
      if (evt.latestCartData) {
        this.isOfflineDraft.set(false);
        this.actualizarEstado(evt.latestCartData);
        this.guardarBorradorLocal(evt.latestCartData, evt.latestCartData.id_empresa);
      } else if (evt.syncedCount > 0 && this.authService.estaAutenticado()) {
        this.cargarCarrito().subscribe();
      }
    });
  }

  public resolverEmpresaId(idEmpresa?: number): number | undefined {
    if (idEmpresa && idEmpresa > 0) return idEmpresa;
    if (this.currentEmpresaId && this.currentEmpresaId > 0) return this.currentEmpresaId;
    const effective = this.authService.getEffectiveCompanyId();
    if (effective && effective > 0) return effective;
    const user = this.authService.obtenerUsuario();
    if (user?.id_empresa && user.id_empresa > 0) return user.id_empresa;
    if (this.authService.getScopeLevel() === 'PLATAFORMA') {
      return 1; // Tienda predeterminada para operaciones retail del administrador global
    }
    return undefined;
  }

  private getCartScopeAndKey(idEmpresa?: number): { scopeKey: string; recordKey: string; tenantId: number } {
    const user = this.authService.obtenerUsuarioActual();
    const uid = user?.id_usuario || 0;
    const tid = this.resolverEmpresaId(idEmpresa) || 1;
    const scopeKey = this.indexedDb.buildPrivateScopeKey(uid, tid);
    return {
      scopeKey,
      recordKey: `cart_draft_${scopeKey}`,
      tenantId: tid
    };
  }

  private async guardarBorradorLocal(data: CarritoData, idEmpresa?: number): Promise<void> {
    if (!this.authService.estaAutenticado()) return;
    const { scopeKey, recordKey, tenantId } = this.getCartScopeAndKey(idEmpresa || data?.id_empresa);
    const now = Date.now();
    await this.indexedDb.put<CachedRecord<CarritoData>>('cart_drafts', {
      key: recordKey,
      scope_key: scopeKey,
      tenant_id: tenantId,
      data,
      fetched_at: new Date(now).toISOString(),
      fetched_at_ms: now,
      expires_at_ms: now + CART_TTL_MS
    });
  }

  private async obtenerBorradorLocal(idEmpresa?: number): Promise<CarritoData | null> {
    if (!this.authService.estaAutenticado()) return null;
    const { recordKey, tenantId } = this.getCartScopeAndKey(idEmpresa);
    const rec = await this.indexedDb.get<CachedRecord<CarritoData>>('cart_drafts', recordKey);
    if (rec?.data) {
      return rec.data;
    }
    return {
      id_carrito: 0,
      id_empresa: tenantId,
      nombre_empresa: 'Tienda Aurora',
      items: [],
      total_items: 0,
      subtotal: 0,
      descuento: 0,
      total: 0,
      puede_continuar_compra: false,
      _offline_draft: true
    };
  }

  private recalcularTotalesBorrador(draft: CarritoData): CarritoData {
    let totalItems = 0;
    let subtotal = 0;
    for (const item of draft.items) {
      item.subtotal = Number((item.cantidad * item.precio_unitario).toFixed(2));
      totalItems += Number(item.cantidad || 0);
      subtotal += item.subtotal;
    }
    draft.total_items = totalItems;
    draft.subtotal = Number(subtotal.toFixed(2));
    draft.total = Number((subtotal - (draft.descuento || 0)).toFixed(2));
    draft.puede_continuar_compra = draft.items.length > 0;
    draft._offline_draft = true;
    return draft;
  }

  setEmpresaId(idEmpresa: number): void {
    if (this.currentEmpresaId !== idEmpresa) {
      this.currentEmpresaId = idEmpresa;
      this.cargarCarrito(idEmpresa).subscribe();
    }
  }

  getEmpresaId(): number | null {
    return this.currentEmpresaId || this.resolverEmpresaId() || null;
  }

  abrirDrawer(): void {
    this.drawerAbiertoSubject.next(true);
  }

  cerrarDrawer(): void {
    this.drawerAbiertoSubject.next(false);
  }

  alternarDrawer(): void {
    this.drawerAbiertoSubject.next(!this.drawerAbiertoSubject.value);
  }

  private actualizarEstado(data: CarritoData | null): void {
    this.carritoSubject.next(data);
    if (data) {
      this.totalItemsSubject.next(data.total_items || 0);
      this.subtotalSubject.next(data.total || 0);
    } else {
      this.totalItemsSubject.next(0);
      this.subtotalSubject.next(0);
    }
  }

  cargarCarrito(idEmpresa?: number): Observable<{ success: boolean; data: CarritoData } | null> {
    const empId = this.resolverEmpresaId(idEmpresa);

    if (this.inFlightLoad$ && this.inFlightEmpresaId === empId) {
      return this.inFlightLoad$;
    }

    let params = new HttpParams();
    if (empId) params = params.set('id_empresa', empId.toString());

    this.cargandoSubject.next(true);
    this.inFlightEmpresaId = empId;

    this.inFlightLoad$ = this.http.get<{ success: boolean; data: CarritoData }>(`${this.apiUrl}`, { params }).pipe(
      tap((res) => {
        if (res && res.success) {
          if (empId && empId > 0) {
            this.currentEmpresaId = empId;
          }
          this.isOfflineDraft.set(false);
          this.actualizarEstado(res.data);
          this.guardarBorradorLocal(res.data, empId);
        }
        this.cargandoSubject.next(false);
      }),
      catchError(() => {
        this.cargandoSubject.next(false);
        return from(this.obtenerBorradorLocal(empId)).pipe(
          switchMap((draft) => {
            if (draft && draft.items.length > 0) {
              this.isOfflineDraft.set(true);
              this.actualizarEstado(draft);
              return of({ success: true, data: draft });
            }
            return of(null);
          })
        );
      }),
      finalize(() => {
        this.inFlightLoad$ = null;
      }),
      shareReplay(1)
    );

    return this.inFlightLoad$;
  }

  agregarItem(
    idVariante: number,
    cantidad: number,
    idEmpresa?: number,
    meta?: AgregarItemMeta
  ): Observable<{ success: boolean; message: string; data: CarritoData; offline_queued?: boolean }> {
    const empId = this.resolverEmpresaId(idEmpresa);
    const body: any = {
      id_variante: idVariante,
      cantidad: cantidad
    };
    if (empId) body.id_empresa = empId;

    if (!this.networkStatus.isOnline()) {
      return from(this.aplicarAgregarItemOffline(idVariante, cantidad, empId, meta));
    }

    this.cargandoSubject.next(true);
    return this.http.post<{ success: boolean; message: string; data: CarritoData }>(`${this.apiUrl}/items`, body).pipe(
      tap((res) => {
        if (res && res.success) {
          if (empId && empId > 0) {
            this.currentEmpresaId = empId;
          }
          this.isOfflineDraft.set(false);
          this.actualizarEstado(res.data);
          this.guardarBorradorLocal(res.data, empId);
        }
        this.cargandoSubject.next(false);
      }),
      catchError((err) => {
        this.cargandoSubject.next(false);
        if (err?.status === 0) {
          return from(this.aplicarAgregarItemOffline(idVariante, cantidad, empId, meta));
        }
        return throwError(() => err);
      })
    );
  }

  private async aplicarAgregarItemOffline(
    idVariante: number,
    cantidad: number,
    empId?: number,
    meta?: AgregarItemMeta
  ): Promise<{ success: boolean; message: string; data: CarritoData; offline_queued: boolean }> {
    const current = this.carritoSubject.value || (await this.obtenerBorradorLocal(empId))!;
    const draft: CarritoData = JSON.parse(JSON.stringify(current));

    let targetItem = draft.items.find((it) => Number(it.id_variante) === Number(idVariante));
    let finalQty = cantidad;

    if (targetItem) {
      targetItem.cantidad += cantidad;
      finalQty = targetItem.cantidad;
      targetItem.pendiente_sincronizacion = true;
    } else {
      const unitPrice = Number(meta?.precio_unitario || 0);
      targetItem = {
        id_detalle_carrito: -Math.floor(Date.now() % 1000000),
        id_variante: idVariante,
        id_producto: meta?.id_producto || 0,
        producto_nombre: meta?.producto_nombre || `Prenda #${idVariante}`,
        talla_nombre: meta?.talla_nombre || '-',
        color_nombre: meta?.color_nombre || '-',
        codigo_hex: meta?.codigo_hex || '#18181b',
        imagen_url: meta?.imagen_url || null,
        cantidad: cantidad,
        precio_unitario: unitPrice,
        subtotal: Number((unitPrice * cantidad).toFixed(2)),
        stock_disponible: meta?.stock_disponible ?? 99,
        disponible: true,
        advertencia_stock: 'Pendiente de confirmar stock en línea',
        pendiente_sincronizacion: true
      };
      draft.items.push(targetItem);
    }

    this.recalcularTotalesBorrador(draft);
    this.isOfflineDraft.set(true);
    this.actualizarEstado(draft);
    await this.guardarBorradorLocal(draft, empId);

    await this.syncQueue.enqueueOperation({
      kind: 'CART_ADD_ITEM',
      tenantId: empId || draft.id_empresa || 1,
      entityId: idVariante,
      summaryLabel: `Agregar al carrito: ${targetItem.producto_nombre} (${targetItem.talla_nombre} / ${targetItem.color_nombre}) x${finalQty}`,
      payload: {
        id_variante: idVariante,
        cantidad: finalQty,
        mode: 'SET',
        expected_unit_price: targetItem.precio_unitario > 0 ? targetItem.precio_unitario : undefined
      }
    });

    return {
      success: true,
      offline_queued: true,
      message: 'Guardado en tu bolsa local (pendiente de sincronizar al recuperar conexión).',
      data: draft
    };
  }

  actualizarCantidad(
    idDetalle: number,
    cantidad: number,
    idEmpresa?: number
  ): Observable<{ success: boolean; message: string; data: CarritoData; offline_queued?: boolean }> {
    const empId = this.resolverEmpresaId(idEmpresa);
    const body: any = { cantidad };
    if (empId) body.id_empresa = empId;

    if (!this.networkStatus.isOnline() || idDetalle < 0) {
      return from(this.aplicarActualizarCantidadOffline(idDetalle, cantidad, empId));
    }

    this.cargandoSubject.next(true);
    return this.http.put<{ success: boolean; message: string; data: CarritoData }>(`${this.apiUrl}/items/${idDetalle}`, body).pipe(
      tap((res) => {
        if (res && res.success) {
          if (empId && empId > 0) {
            this.currentEmpresaId = empId;
          }
          this.isOfflineDraft.set(false);
          this.actualizarEstado(res.data);
          this.guardarBorradorLocal(res.data, empId);
        }
        this.cargandoSubject.next(false);
      }),
      catchError((err) => {
        this.cargandoSubject.next(false);
        if (err?.status === 0) {
          return from(this.aplicarActualizarCantidadOffline(idDetalle, cantidad, empId));
        }
        return throwError(() => err);
      })
    );
  }

  private async aplicarActualizarCantidadOffline(
    idDetalle: number,
    cantidad: number,
    empId?: number
  ): Promise<{ success: boolean; message: string; data: CarritoData; offline_queued: boolean }> {
    const current = this.carritoSubject.value || (await this.obtenerBorradorLocal(empId))!;
    const draft: CarritoData = JSON.parse(JSON.stringify(current));
    const item = draft.items.find((it) => Number(it.id_detalle_carrito) === Number(idDetalle));

    if (item) {
      item.cantidad = cantidad;
      item.pendiente_sincronizacion = true;
    }

    this.recalcularTotalesBorrador(draft);
    this.isOfflineDraft.set(true);
    this.actualizarEstado(draft);
    await this.guardarBorradorLocal(draft, empId);

    await this.syncQueue.enqueueOperation({
      kind: 'CART_UPDATE_QTY',
      tenantId: empId || draft.id_empresa || 1,
      entityId: item?.id_variante || idDetalle,
      summaryLabel: `Actualizar cantidad: ${item?.producto_nombre || 'Prenda'} a ${cantidad} u.`,
      payload: {
        id_detalle_carrito: idDetalle,
        id_variante: item?.id_variante,
        cantidad
      }
    });

    return {
      success: true,
      offline_queued: true,
      message: 'Cantidad actualizada en tu bolsa local (pendiente de sincronizar).',
      data: draft
    };
  }

  eliminarItem(
    idDetalle: number,
    idEmpresa?: number
  ): Observable<{ success: boolean; message: string; data: CarritoData; offline_queued?: boolean }> {
    const empId = this.resolverEmpresaId(idEmpresa);
    let params = new HttpParams();
    if (empId) params = params.set('id_empresa', empId.toString());

    if (!this.networkStatus.isOnline() || idDetalle < 0) {
      return from(this.aplicarEliminarItemOffline(idDetalle, empId));
    }

    this.cargandoSubject.next(true);
    return this.http.delete<{ success: boolean; message: string; data: CarritoData }>(`${this.apiUrl}/items/${idDetalle}`, { params }).pipe(
      tap((res) => {
        if (res && res.success) {
          if (empId && empId > 0) {
            this.currentEmpresaId = empId;
          }
          this.isOfflineDraft.set(false);
          this.actualizarEstado(res.data);
          this.guardarBorradorLocal(res.data, empId);
        }
        this.cargandoSubject.next(false);
      }),
      catchError((err) => {
        this.cargandoSubject.next(false);
        if (err?.status === 0) {
          return from(this.aplicarEliminarItemOffline(idDetalle, empId));
        }
        return throwError(() => err);
      })
    );
  }

  private async aplicarEliminarItemOffline(
    idDetalle: number,
    empId?: number
  ): Promise<{ success: boolean; message: string; data: CarritoData; offline_queued: boolean }> {
    const current = this.carritoSubject.value || (await this.obtenerBorradorLocal(empId))!;
    const draft: CarritoData = JSON.parse(JSON.stringify(current));
    const removed = draft.items.find((it) => Number(it.id_detalle_carrito) === Number(idDetalle));
    draft.items = draft.items.filter((it) => Number(it.id_detalle_carrito) !== Number(idDetalle));

    this.recalcularTotalesBorrador(draft);
    this.isOfflineDraft.set(true);
    this.actualizarEstado(draft);
    await this.guardarBorradorLocal(draft, empId);

    await this.syncQueue.enqueueOperation({
      kind: 'CART_REMOVE_ITEM',
      tenantId: empId || draft.id_empresa || 1,
      entityId: removed?.id_variante || idDetalle,
      summaryLabel: `Quitar de la bolsa: ${removed?.producto_nombre || 'Prenda'}`,
      payload: {
        id_detalle_carrito: idDetalle,
        id_variante: removed?.id_variante
      }
    });

    return {
      success: true,
      offline_queued: true,
      message: 'Prenda removida de tu bolsa local (pendiente de sincronizar).',
      data: draft
    };
  }

  vaciarCarrito(
    idEmpresa?: number
  ): Observable<{ success: boolean; message: string; data: CarritoData; offline_queued?: boolean }> {
    const empId = this.resolverEmpresaId(idEmpresa);
    let params = new HttpParams();
    if (empId) params = params.set('id_empresa', empId.toString());

    if (!this.networkStatus.isOnline()) {
      return from(this.aplicarVaciarCarritoOffline(empId));
    }

    this.cargandoSubject.next(true);
    return this.http.delete<{ success: boolean; message: string; data: CarritoData }>(`${this.apiUrl}/vaciar`, { params }).pipe(
      tap((res) => {
        if (res && res.success) {
          if (empId && empId > 0) {
            this.currentEmpresaId = empId;
          }
          this.isOfflineDraft.set(false);
          this.actualizarEstado(res.data);
          this.guardarBorradorLocal(res.data, empId);
        }
        this.cargandoSubject.next(false);
      }),
      catchError((err) => {
        this.cargandoSubject.next(false);
        if (err?.status === 0) {
          return from(this.aplicarVaciarCarritoOffline(empId));
        }
        return throwError(() => err);
      })
    );
  }

  private async aplicarVaciarCarritoOffline(
    empId?: number
  ): Promise<{ success: boolean; message: string; data: CarritoData; offline_queued: boolean }> {
    const current = this.carritoSubject.value || (await this.obtenerBorradorLocal(empId))!;
    const draft: CarritoData = JSON.parse(JSON.stringify(current));
    draft.items = [];
    this.recalcularTotalesBorrador(draft);

    this.isOfflineDraft.set(true);
    this.actualizarEstado(draft);
    await this.guardarBorradorLocal(draft, empId);

    await this.syncQueue.enqueueOperation({
      kind: 'CART_CLEAR',
      tenantId: empId || draft.id_empresa || 1,
      summaryLabel: 'Vaciar bolsa de compras',
      payload: { id_empresa: empId || draft.id_empresa || 1 }
    });

    return {
      success: true,
      offline_queued: true,
      message: 'Bolsa vaciada localmente (pendiente de sincronizar).',
      data: draft
    };
  }
}
