import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Subject, firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../../services/auth';
import { IndexedDbService, CachedRecord } from '../storage/indexed-db.service';
import { NetworkStatusService } from '../network/network-status.service';
import { hasVerifiedConfirmation, sameOperationRequest, VerifiedSyncResult } from './sync-confirmation';

export type SyncOperationKind =
  | 'CART_ADD_ITEM'
  | 'CART_UPDATE_QTY'
  | 'CART_REMOVE_ITEM'
  | 'CART_CLEAR'
  | 'RESERVA_SOLICITUD'
  | 'VENTA_CONTADO';

export type SyncOperationStatus =
  | 'pending'
  | 'syncing'
  | 'synced'
  | 'conflict'
  | 'reconciliation_required'
  | 'failed_retryable'
  | 'failed_permanent';

export interface PendingOperation {
  operation_id: string;
  scope_key: string;
  user_id: number;
  tenant_id: number;
  branch_id: number | null;
  kind: SyncOperationKind;
  entity_id?: string | number | null;
  summary_label: string;
  payload: Record<string, any>;
  created_at: string;
  created_at_ms: number;
  fetched_at_ms: number;
  attempt_count: number;
  next_retry_at_ms?: number | null;
  status: SyncOperationStatus;
  reconciliation_required?: boolean;
  reconciliation_note?: string | null;
  last_error?: string | null;
  conflict_code?: string | null;
  conflict_detail?: Record<string, any> | null;
  client_version?: string | number | null;
  outcome_known_rejected?: boolean;
}

export interface SyncBatchItemResult extends VerifiedSyncResult {
  operation_id: string;
  kind: SyncOperationKind;
  status: SyncOperationStatus;
  reconciliation_required?: boolean;
  http_status: number;
  conflict_code?: string | null;
  message?: string;
  data?: any;
  conflict_detail?: Record<string, any> | null;
  synced_at?: string;
  idempotent_replay?: boolean;
}

export interface SyncBatchResponse {
  success: boolean;
  total: number;
  synced_count: number;
  conflict_count: number;
  reconciliation_count?: number;
  failed_count: number;
  results: SyncBatchItemResult[];
}

export interface SyncCompletedEvent extends SyncBatchResponse {
  syncedCount: number;
  conflictCount: number;
  latestCartData?: any;
}

@Injectable({
  providedIn: 'root',
})
export class SyncQueueService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly idb = inject(IndexedDbService);
  private readonly network = inject(NetworkStatusService);
  private readonly syncLoteUrl = `${environment.apiUrl}/api/sync/lote`;

  private readonly loadedOperations = signal<PendingOperation[]>([]);
  readonly operations = computed(() => this.loadedOperations().filter(op => this.belongsToCurrentScope(op)));
  readonly activeOperations = computed(() => this.operations());
  readonly isSyncing = signal<boolean>(false);
  readonly lastSyncedAt = signal<string | null>(null);
  readonly lastSyncSummary = signal<string | null>(null);
  readonly lastSyncBannerMessage = signal<{ type: 'success' | 'warning' | 'error'; text: string } | null>(null);
  private readonly loadedHistory = signal<Array<Record<string, any>>>([]);
  readonly reconciledHistory = computed(() => this.loadedHistory().filter(op => this.belongsToCurrentScope(op)));

  /** Emitido cada vez que un lote termina de sincronizar operaciones */
  private readonly syncCompletedSubject = new Subject<SyncCompletedEvent>();
  readonly syncCompleted$ = this.syncCompletedSubject.asObservable();

  readonly pendingCount = computed(() =>
    this.operations().filter(
      (op) => op.status === 'pending' || op.status === 'syncing' || op.status === 'failed_retryable'
    ).length
  );

  readonly conflictCount = computed(() =>
    this.operations().filter(
      (op) => op.status === 'conflict' || op.status === 'reconciliation_required'
    ).length
  );

  readonly reconciliationCount = computed(() =>
    this.operations().filter(
      (op) => op.status === 'reconciliation_required' || Boolean(op.reconciliation_required)
    ).length
  );

  readonly totalActiveCount = computed(() => this.operations().length);

  private syncLock = false;
  private readonly inFlightOperations = new Set<string>();
  private refreshVersion = 0;

  constructor() {
    void this.refreshOperationsSafely();

    this.network.reconnected$.subscribe((ts) => {
      if (ts > 0) {
        void this.syncNow(false);
      }
    });

    this.authService.companyChanged$.subscribe(() => {
      this.loadedOperations.set([]);
      this.loadedHistory.set([]);
      void this.refreshOperationsSafely();
    });

    this.authService.branchChanged$.subscribe(() => {
      void this.refreshOperationsSafely();
    });
  }

  public dismissBannerMessage(): void {
    this.lastSyncBannerMessage.set(null);
  }

  private getCurrentScope(overrideTenantId?: number | null, overrideBranchId?: number | null): {
    userId: number;
    tenantId: number;
    branchId: number | null;
  } {
    const user = this.authService.obtenerUsuario();
    const userId = this.authService.estaAutenticado() ? Number(user?.id_usuario ?? user?.nro_usuario ?? 0) : 0;
    const tenantId = Number(
      overrideTenantId ??
        this.authService.getEffectiveCompanyId() ??
        user?.id_empresa ??
        1
    );
    const branchId =
      overrideBranchId !== undefined
        ? overrideBranchId
        : (this.authService.activeBranch()?.id ?? null);
    return { userId, tenantId, branchId };
  }

  private belongsToCurrentScope(op: { user_id?: number; tenant_id?: number; scope_key?: string }): boolean {
    const scope = this.getCurrentScope();
    return scope.userId > 0 && op.user_id === scope.userId && op.tenant_id === scope.tenantId &&
      String(op.scope_key).startsWith(`u:${scope.userId}|e:${scope.tenantId}|`);
  }

  private async refreshOperationsSafely(): Promise<void> {
    try { await this.refreshCountFromDb(); }
    catch (error) {
      this.loadedOperations.set([]);
      this.loadedHistory.set([]);
      this.lastSyncBannerMessage.set({ type: 'error', text: (error as Error).message });
    }
  }

  private async getActiveOperation(operationId: string): Promise<PendingOperation | null> {
    if (!this.getCurrentScope().userId) throw new Error('Reautentique la cuenta propietaria de la operación.');
    const op = await this.idb.get<PendingOperation>('pending_operations', operationId);
    if (op && !this.belongsToCurrentScope(op)) throw new Error('La operación pertenece a otro usuario o empresa.');
    return op;
  }

  /**
   * Genera un UUID v4 criptográficamente seguro para idempotencia (CU38W).
   */
  generateOperationId(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  async refreshOperations(): Promise<void> {
    await this.refreshCountFromDb();
  }

  /**
   * Carga las operaciones pendientes del usuario y tenant activo desde IndexedDB.
   * Si alguna operación quedó en estado 'syncing' por cierre abrupto de la PWA,
   * la restaura automáticamente a 'pending'.
   */
  async refreshCountFromDb(): Promise<void> {
    const version = ++this.refreshVersion;
    const scope = this.getCurrentScope();
    if (!scope.userId) {
      this.loadedOperations.set([]);
      this.loadedHistory.set([]);
      return;
    }

    const prefix = `u:${scope.userId}|e:${scope.tenantId}|`;
    const allUserOps = await this.idb.getAllByScope<PendingOperation>('pending_operations', prefix);
    const filteredOps = allUserOps.filter(
      (op) => op.user_id === scope.userId && op.tenant_id === scope.tenantId
    );

    const normalizedOps: PendingOperation[] = [];
    for (const op of filteredOps) {
      if (op.status === 'synced') {
        const unverified: PendingOperation = { ...op, status: 'failed_retryable',
          conflict_code: 'LOCAL_CONFIRMATION_MISSING', outcome_known_rejected: false };
        await this.idb.put('pending_operations', unverified);
        normalizedOps.push(unverified);
      } else if (op.status === 'syncing' && !this.inFlightOperations.has(op.operation_id)) {
        const recovered: PendingOperation = { ...op, status: 'pending' };
        await this.idb.put('pending_operations', recovered);
        normalizedOps.push(recovered);
      } else {
        normalizedOps.push(op);
      }
    }

    normalizedOps.sort((a, b) => a.created_at_ms - b.created_at_ms);
    if (version !== this.refreshVersion || this.getCurrentScope().userId !== scope.userId ||
        this.getCurrentScope().tenantId !== scope.tenantId) return;
    this.loadedOperations.set(normalizedOps);

    await this.syncProvisionalStockSnapshots(normalizedOps, scope.userId, scope.tenantId || 1);

    const historyKey = `u:${scope.userId}|e:${scope.tenantId || 1}|reconciled_sales`;
    const [historyEntry, attempts] = await Promise.all([
      this.idb.get<{ key: string; items: Array<Record<string, any>> }>('metadata', historyKey),
      this.idb.getAllByScope<Record<string, any>>('sync_attempts', prefix),
    ]);
    if (version === this.refreshVersion) this.loadedHistory.set([
      ...attempts.filter(item => item['status'] === 'reconciliation_note').reverse(),
      ...(historyEntry?.items || []),
    ].map(item => ({ ...item, user_id: item['user_id'] ?? scope.userId, scope_key: item['scope_key'] ?? prefix })));
  }

  /**
   * Calcula y persiste en `stock_snapshots` las unidades comprometidas localmente
   * por reservas y ventas en efectivo pendientes de confirmación del servidor.
   */
  private async syncProvisionalStockSnapshots(
    ops: PendingOperation[],
    userId: number,
    tenantId: number
  ): Promise<void> {
    const scopePrefix = `u:${userId}|e:${tenantId}`;
    const existingSnaps = await this.idb.getAllByScope<{ key: string }>('stock_snapshots', scopePrefix);
    for (const snap of existingSnaps) {
      if (snap?.key) {
        await this.idb.delete('stock_snapshots', snap.key);
      }
    }

    const nowMs = Date.now();
    const mapByBranchVariant = new Map<string, {
      key: string;
      scope_key: string;
      tenant_id: number;
      branch_id: number | null;
      id_variante: number;
      provisional_delta: number;
      fetched_at_ms: number;
      updated_at: string;
    }>();

    for (const op of ops) {
      if (op.kind !== 'RESERVA_SOLICITUD' && op.kind !== 'VENTA_CONTADO') continue;
      if (op.status === 'synced' || op.status === 'failed_permanent') continue;

      const branchId = op.branch_id ?? op.payload?.['id_sucursal'] ?? null;
      const scopeKey = `u:${userId}|e:${tenantId}|b:${branchId ?? 'all'}`;
      const items = Array.isArray(op.payload?.['items']) ? op.payload['items'] : [];

      for (const it of items) {
        const idVar = Number(it?.id_variante || 0);
        const cant = Number(it?.cantidad || 0);
        if (idVar <= 0 || cant <= 0) continue;

        const snapKey = `${scopeKey}_var_${idVar}`;
        const prev = mapByBranchVariant.get(snapKey);
        if (prev) {
          prev.provisional_delta += cant;
        } else {
          mapByBranchVariant.set(snapKey, {
            key: snapKey,
            scope_key: scopeKey,
            tenant_id: tenantId,
            branch_id: branchId !== null ? Number(branchId) : null,
            id_variante: idVar,
            provisional_delta: cant,
            fetched_at_ms: nowMs,
            updated_at: new Date(nowMs).toISOString(),
          });
        }
      }
    }

    for (const snap of mapByBranchVariant.values()) {
      await this.idb.put('stock_snapshots', snap);
    }
  }

  /**
   * Devuelve la cantidad provisionalmente comprometida en la cola offline para una variante
   * (en una sucursal específica o en todas las sucursales de la tienda activa).
   */
  getProvisionalDeltaForVariant(idVariante: number, branchId?: number | null): number {
    const targetVar = Number(idVariante || 0);
    if (targetVar <= 0) return 0;

    let delta = 0;
    for (const op of this.operations()) {
      if (op.kind !== 'RESERVA_SOLICITUD' && op.kind !== 'VENTA_CONTADO') continue;
      if (op.status === 'synced' || op.status === 'failed_permanent') continue;

      const opBranch = op.branch_id ?? op.payload?.['id_sucursal'] ?? null;
      if (branchId !== undefined && branchId !== null && opBranch !== null && Number(opBranch) !== Number(branchId)) {
        continue;
      }

      const items = Array.isArray(op.payload?.['items']) ? op.payload['items'] : [];
      for (const it of items) {
        if (Number(it?.id_variante) === targetVar) {
          delta += Math.max(0, Number(it?.cantidad || 0));
        }
      }
    }
    return delta;
  }

  /**
   * Devuelve un mapa `id_variante -> unidades comprometidas offline` para uso en catálogo y POS.
   */
  getProvisionalStockMap(branchId?: number | null): Map<number, number> {
    const map = new Map<number, number>();
    for (const op of this.operations()) {
      if (op.kind !== 'RESERVA_SOLICITUD' && op.kind !== 'VENTA_CONTADO') continue;
      if (op.status === 'synced' || op.status === 'failed_permanent') continue;

      const opBranch = op.branch_id ?? op.payload?.['id_sucursal'] ?? null;
      if (branchId !== undefined && branchId !== null && opBranch !== null && Number(opBranch) !== Number(branchId)) {
        continue;
      }

      const items = Array.isArray(op.payload?.['items']) ? op.payload['items'] : [];
      for (const it of items) {
        const idVar = Number(it?.id_variante || 0);
        const cant = Math.max(0, Number(it?.cantidad || 0));
        if (idVar > 0 && cant > 0) {
          map.set(idVar, (map.get(idVar) || 0) + cant);
        }
      }
    }
    return map;
  }

  async enqueueOperation(params: {
    kind: SyncOperationKind;
    summaryLabel: string;
    payload: Record<string, any>;
    entityId?: string | number | null;
    clientVersion?: string | number | null;
    tenantId?: number | null;
    branchId?: number | null;
    operationId?: string;
  }): Promise<PendingOperation> {
    return this.enqueue(params);
  }

  /**
   * Encola una operación autorizada localmente en IndexedDB.
   * Compacta operaciones redundantes sobre la misma variante del carrito si aún están en 'pending'.
   */
  async enqueue(params: {
    kind: SyncOperationKind;
    summaryLabel: string;
    payload: Record<string, any>;
    entityId?: string | number | null;
    clientVersion?: string | number | null;
    tenantId?: number | null;
    branchId?: number | null;
    operationId?: string;
  }): Promise<PendingOperation> {
    const scope = this.getCurrentScope(params.tenantId, params.branchId);
    const userId = scope.userId || 0;
    if (!userId || scope.tenantId !== this.getCurrentScope().tenantId) {
      throw new Error('Debe autenticar y seleccionar la cuenta y empresa de esta operación.');
    }
    const tenantId = scope.tenantId || 1;
    const branchId = scope.branchId ?? null;
    const scopeKey = `u:${userId}|e:${tenantId}|b:${branchId ?? 'all'}`;

    if (params.operationId) {
      const prior = await this.getActiveOperation(params.operationId);
      if (prior) {
        if (!sameOperationRequest(prior, { ...prior, kind: params.kind, scope_key: scopeKey,
          branch_id: branchId, entity_id: params.entityId ?? null, payload: params.payload })) {
          throw new Error('La clave local ya pertenece a otra operación; se conserva su contenido original.');
        }
        return prior;
      }
      if (await this.idb.get('sync_receipts', params.operationId)) {
        throw new Error('La operación ya tiene una confirmación guardada en este dispositivo.');
      }
    }

    await this.refreshCountFromDb();
    const currentOps = this.operations();

    // Compactación segura para carrito: si ya hay un CART_ADD_ITEM o CART_UPDATE_QTY 'pending' para la misma variante
    if (
      (params.kind === 'CART_ADD_ITEM' || params.kind === 'CART_UPDATE_QTY') &&
      params.entityId !== undefined &&
      params.entityId !== null
    ) {
      const existingPending = currentOps.find(
        (op) =>
          op.scope_key === scopeKey &&
          op.status === 'pending' &&
          op.attempt_count === 0 &&
          (op.kind === 'CART_ADD_ITEM' || op.kind === 'CART_UPDATE_QTY') &&
          String(op.entity_id) === String(params.entityId)
      );

      if (existingPending) {
        const updatedOp: PendingOperation = {
          ...existingPending,
          summary_label: params.summaryLabel,
          payload: {
            ...existingPending.payload,
            ...params.payload,
            mode: 'SET',
          },
          client_version: params.clientVersion ?? existingPending.client_version,
        };
        await this.idb.put('pending_operations', updatedOp);
        await this.refreshCountFromDb();
        return updatedOp;
      }
    }

    // Si se elimina un item del carrito que fue agregado offline y aún no se sincronizó, cancelar ambos
    if (params.kind === 'CART_REMOVE_ITEM' && params.entityId !== undefined && params.entityId !== null) {
      const pendingAdd = currentOps.find(
        (op) =>
          op.scope_key === scopeKey &&
          op.status === 'pending' &&
          op.attempt_count === 0 &&
          op.kind === 'CART_ADD_ITEM' &&
          String(op.entity_id) === String(params.entityId)
      );

      if (pendingAdd && Number(params.payload['id_detalle_carrito'] || 0) < 0) {
        const cancelled: PendingOperation = { ...pendingAdd, status: 'failed_permanent',
          conflict_code: 'LOCAL_CANCELLED_BEFORE_SEND', last_error: 'Cancelada antes del primer envío; se conserva la evidencia local.' };
        await this.idb.put('pending_operations', cancelled);
        await this.refreshCountFromDb();
        return cancelled;
      }
    }

    const nowMs = Date.now();
    const nowIso = new Date(nowMs).toISOString();
    const op: PendingOperation = {
      operation_id: params.operationId || this.generateOperationId(),
      scope_key: scopeKey,
      user_id: userId,
      tenant_id: tenantId,
      branch_id: branchId,
      kind: params.kind,
      entity_id: params.entityId ?? null,
      summary_label: params.summaryLabel,
      payload: params.payload,
      created_at: nowIso,
      created_at_ms: nowMs,
      fetched_at_ms: nowMs,
      attempt_count: 0,
      next_retry_at_ms: null,
      status: 'pending',
      reconciliation_required: false,
      reconciliation_note: null,
      last_error: null,
      conflict_code: null,
      conflict_detail: null,
      client_version: params.clientVersion ?? nowIso,
    };

    if (!this.belongsToCurrentScope(op)) throw new Error('La cuenta o empresa cambió antes de guardar la operación.');
    await this.idb.put('pending_operations', op);
    await this.refreshCountFromDb();

    if (this.network.isOnline()) {
      void this.syncNow();
    }

    return op;
  }

  /**
   * Sincroniza en lote las operaciones pendientes o reintentables del usuario/tenant activo (CU38W).
   */
  async syncNow(force: boolean = false): Promise<SyncBatchResponse | null> {
    if (this.syncLock) return null;
    // Acquire before the first await: two reconnect callbacks cannot both send.
    this.syncLock = true;
    let eligible: PendingOperation[] = [];
    const unresolved = new Set<string>();
    const scope = this.getCurrentScope();
    const token = this.authService.obtenerToken();
    const sameContext = () => this.getCurrentScope().userId === scope.userId &&
      this.getCurrentScope().tenantId === scope.tenantId && this.authService.obtenerToken() === token;
    try {
      if (!scope.userId || !token) return null;
      await this.refreshCountFromDb();
      if (!sameContext()) return null;
      const now = Date.now();
      eligible = structuredClone(this.operations().filter(op => op.status === 'pending' ||
        (op.status === 'failed_retryable' && (force || !op.next_retry_at_ms || now >= op.next_retry_at_ms))))
        .sort((a, b) => {
          // Prioridad P0: Ventas presenciales en efectivo POS antes de carritos o reservas online
          if (a.kind === 'VENTA_CONTADO' && b.kind !== 'VENTA_CONTADO') return -1;
          if (b.kind === 'VENTA_CONTADO' && a.kind !== 'VENTA_CONTADO') return 1;
          return 0;
        })
        .slice(0, 50);
      if (!eligible.length || !await this.network.verifyApiConnectivity(force) || !sameContext()) return null;
      this.isSyncing.set(true);
      this.network.setSyncingState(true);
      for (const op of eligible) {
        if (!sameContext()) return null;
        unresolved.add(op.operation_id);
        this.inFlightOperations.add(op.operation_id);
        op.status = 'syncing';
        op.attempt_count = Number.isSafeInteger(op.attempt_count) ? op.attempt_count + 1 : 1;
        await this.idb.put('pending_operations', op);
      }
      if (!sameContext()) return null;
      const response = await firstValueFrom(this.http.post<SyncBatchResponse>(this.syncLoteUrl, {
        operations: eligible.map(op => ({ operation_id: op.operation_id, kind: op.kind, tenant_id: op.tenant_id,
          branch_id: op.branch_id, entity_id: op.entity_id, client_version: op.client_version,
          created_at: op.created_at, payload: op.payload })),
      }));
      if (!sameContext()) return null;
      const results: SyncBatchItemResult[] = [];
      let latestCartData: any;
      for (const localOp of eligible) {
        if (!sameContext()) return null;
        const matches = (Array.isArray(response?.results) ? response.results : [])
          .filter(res => res.operation_id === localOp.operation_id);
        let result = matches.length === 1 ? matches[0] : undefined;
        if (!result || result.kind !== localOp.kind ||
            (result.status === 'synced' && !hasVerifiedConfirmation(localOp, result))) {
          result = { operation_id: localOp.operation_id, kind: localOp.kind, status: 'failed_retryable',
            http_status: 503, confirmation_verified: false, conflict_code: 'SYNC_CONFIRMATION_MISSING',
            message: 'Respuesta incompleta o sin recibo verificable. Se conserva la operación para reenviar.' };
        }
        if (hasVerifiedConfirmation(localOp, result)) {
          await this.idb.acknowledgeOperation(localOp, result);
          unresolved.delete(localOp.operation_id);
          if (localOp.kind.startsWith('CART_')) latestCartData = result.data;
        } else {
          const at = Date.now();
          await this.idb.put('sync_attempts', {
            attempt_id: `${localOp.operation_id}_${this.generateOperationId()}`, scope_key: localOp.scope_key,
            user_id: localOp.user_id, tenant_id: localOp.tenant_id, operation_id: localOp.operation_id,
            kind: localOp.kind, status: result.status, http_status: result.http_status,
            conflict_code: result.conflict_code, message: result.message, fetched_at_ms: at,
            attempted_at: new Date(at).toISOString(),
          });
          const retryable = result.status === 'failed_retryable';
          const reconciliation = !retryable && (result.status === 'reconciliation_required' ||
            result.reconciliation_required || (localOp.kind === 'VENTA_CONTADO' && result.status === 'conflict'));
          const status: SyncOperationStatus = retryable ? 'failed_retryable' : reconciliation ? 'reconciliation_required' :
            result.status === 'conflict' ? 'conflict' : result.status === 'failed_permanent' ? 'failed_permanent' : 'failed_retryable';
          await this.idb.put('pending_operations', { ...localOp, status,
            reconciliation_required: Boolean(reconciliation), conflict_code: result.conflict_code ?? null,
            conflict_detail: result.conflict_detail ?? null, last_error: result.message ?? 'Operación sin confirmar.',
            outcome_known_rejected: result.confirmation_verified === false &&
              ['conflict', 'reconciliation_required'].includes(result.status) &&
              ['STOCK_INSUFFICIENT', 'PRICE_CHANGED', 'PRODUCT_INACTIVE', 'BRANCH_INACTIVE',
                'CAJA_CERRADA', 'DISCOUNT_FORBIDDEN', 'PAYMENT_REQUIRES_ONLINE', 'PAYMENT_REGISTRATION_ERROR'].includes(result.conflict_code ?? ''),
            next_retry_at_ms: status === 'failed_retryable' ? at + Math.min(60_000, 2_000 * 2 ** (localOp.attempt_count - 1)) : null,
          });
          unresolved.delete(localOp.operation_id);
          result = { ...result, status };
        }
        results.push(result);
      }
      if (!sameContext()) return null;
      const verified: SyncBatchResponse = { success: true, total: results.length, results,
        synced_count: results.filter(res => res.status === 'synced').length,
        conflict_count: results.filter(res => ['conflict', 'reconciliation_required'].includes(res.status)).length,
        reconciliation_count: results.filter(res => res.status === 'reconciliation_required').length,
        failed_count: results.filter(res => res.status.startsWith('failed_')).length };
      this.lastSyncedAt.set(new Date().toISOString());
      const message = `${verified.synced_count} operación(es) confirmada(s); ${verified.total - verified.synced_count} pendiente(s) o en revisión.`;
      this.lastSyncSummary.set(message);
      this.lastSyncBannerMessage.set({ type: verified.synced_count === verified.total ? 'success' : 'warning', text: message });
      await this.refreshCountFromDb();
      if (sameContext()) this.syncCompletedSubject.next({ ...verified, syncedCount: verified.synced_count,
        conflictCount: verified.conflict_count, latestCartData });
      return sameContext() ? verified : null;
    } catch (error) {
      // A previous operation may already have been acknowledged in this batch.
      // Never recreate it when a later HTTP/storage operation fails.
      for (const op of eligible.filter(item => unresolved.has(item.operation_id))) {
        try {
          const current = await this.idb.get<PendingOperation>('pending_operations', op.operation_id);
          if (current) await this.idb.put('pending_operations', { ...current, status: 'failed_retryable',
            outcome_known_rejected: false, last_error: (error as Error).message,
            next_retry_at_ms: Date.now() + 2_000 });
        } catch { /* Keep the last durable envelope; recover syncing after reload. */ }
      }
      if (sameContext()) {
        this.lastSyncBannerMessage.set({ type: 'error', text: (error as Error).message });
        await this.refreshOperationsSafely();
      }
      return null;
    } finally {
      this.inFlightOperations.clear();
      this.syncLock = false;
      this.isSyncing.set(false);
      this.network.setSyncingState(false);
    }
  }

  /**
   * CU39W: Permite resolver un conflicto actualizando el payload y reintentando con el mismo operation_id.
   */
  async resolveConflictWithPatch(
    operationId: string,
    updatedPayloadPatch: Record<string, any>,
    updatedSummaryLabel?: string
  ): Promise<SyncBatchResponse | null> {
    const existing = await this.getActiveOperation(operationId);
    if (!existing) return null;

    if (Object.keys(updatedPayloadPatch).length && !existing.outcome_known_rejected) {
      throw new Error('El resultado anterior es incierto. Reenvíe el contenido original antes de modificarlo.');
    }
    const updated: PendingOperation = {
      ...existing,
      summary_label: updatedSummaryLabel || existing.summary_label,
      payload: {
        ...existing.payload,
        ...updatedPayloadPatch,
      },
      status: 'pending',
      reconciliation_required: false,
      conflict_code: null,
      conflict_detail: null,
      last_error: null,
      next_retry_at_ms: null,
    };

    await this.idb.put('pending_operations', updated);
    await this.refreshCountFromDb();
    return this.syncNow(true);
  }

  async resolveConflictWithPayload(
    operationId: string,
    updatedPayloadPatch: Record<string, any>
  ): Promise<SyncBatchResponse | null> {
    return this.resolveConflictWithPatch(operationId, updatedPayloadPatch);
  }

  /**
   * CU39W: Acepta el cambio de precio informado por el servidor tanto para operaciones de carrito
   * como para reservas (`RESERVA_SOLICITUD`) o ventas en efectivo (`VENTA_CONTADO`).
   */
  async acceptConflictPriceChange(operationId: string): Promise<SyncBatchResponse | null> {
    const existing = await this.getActiveOperation(operationId);
    if (!existing) return null;

    const detail = existing.conflict_detail || {};
    const targetVar = Number(detail['id_variante'] || 0);
    const currentPrice = Number(detail['current_unit_price'] || 0);

    const nextPayload: Record<string, any> = {
      ...existing.payload,
      accept_price_change: true,
    };

    if (currentPrice > 0 && nextPayload['expected_unit_price'] !== undefined) {
      nextPayload['expected_unit_price'] = currentPrice;
    }

    if (Array.isArray(nextPayload['items'])) {
      nextPayload['items'] = nextPayload['items'].map((it: any) => {
        if (targetVar > 0 && Number(it?.id_variante) === targetVar && currentPrice > 0) {
          return {
            ...it,
            expected_unit_price: currentPrice,
            precio_unitario: currentPrice,
            accept_price_change: true,
          };
        }
        return { ...it, accept_price_change: true };
      });

      if (existing.kind === 'VENTA_CONTADO') {
        const nuevoSubtotal = nextPayload['items'].reduce(
          (acc: number, it: any) =>
            acc + Number(it.expected_unit_price ?? it.precio_unitario ?? 0) * Number(it.cantidad || 1),
          0
        );
        const desc = Number(nextPayload['descuento'] || 0);
        const nuevoTotal = Math.max(0, Math.round((nuevoSubtotal - desc) * 100) / 100);
        nextPayload['expected_total'] = nuevoTotal;
        if (Number(nextPayload['monto_recibido'] || 0) < nuevoTotal) {
          nextPayload['monto_recibido'] = nuevoTotal;
        }
      }
    }

    return this.resolveConflictWithPatch(operationId, nextPayload);
  }

  /**
   * CU39W: Ajusta la cantidad solicitada al stock disponible real del servidor y reintenta la sincronización.
   */
  async adjustConflictQuantityToAvailable(operationId: string): Promise<SyncBatchResponse | null> {
    const existing = await this.getActiveOperation(operationId);
    if (!existing) return null;

    const detail = existing.conflict_detail || {};
    const avail = Math.max(0, Number(detail['available_stock'] || 0));
    const targetVar = Number(detail['id_variante'] || 0);
    if (avail <= 0) return null;

    const nextPayload: Record<string, any> = { ...existing.payload };

    if (Array.isArray(nextPayload['items']) && targetVar > 0) {
      nextPayload['items'] = nextPayload['items'].map((it: any) =>
        Number(it?.id_variante) === targetVar ? { ...it, cantidad: avail } : it
      );
      if (existing.kind === 'VENTA_CONTADO') {
        const nuevoSubtotal = nextPayload['items'].reduce(
          (acc: number, it: any) =>
            acc + Number(it.expected_unit_price ?? it.precio_unitario ?? 0) * Number(it.cantidad || 1),
          0
        );
        const desc = Number(nextPayload['descuento'] || 0);
        nextPayload['expected_total'] = Math.max(0, Math.round((nuevoSubtotal - desc) * 100) / 100);
      }
    } else {
      nextPayload['cantidad'] = avail;
      nextPayload['mode'] = 'SET';
    }

    return this.resolveConflictWithPatch(
      operationId,
      nextPayload,
      `${existing.summary_label} (ajustado a ${avail} u.)`
    );
  }

  /**
   * CU39W / CU24W: Registra una incidencia de conciliación para una venta en efectivo rechazada
   * sin eliminar silenciosamente su trazabilidad. Conserva el historial auditable en IndexedDB (`metadata` y `sync_attempts`).
   */
  async reconcileCashSaleIncidence(operationId: string, resolutionNote: string): Promise<void> {
    const existing = await this.getActiveOperation(operationId);
    if (!existing) return;

    const nowMs = Date.now();
    const noteClean = (resolutionNote || '').trim();
    if (!noteClean) throw new Error('Ingrese una nota para guardar la incidencia.');
    const reconciledRecord = {
      operation_id: existing.operation_id,
      entity_id: existing.entity_id,
      summary_label: existing.summary_label,
      user_id: existing.user_id,
      scope_key: existing.scope_key,
      tenant_id: existing.tenant_id,
      branch_id: existing.branch_id,
      conflict_code: existing.conflict_code,
      last_error: existing.last_error,
      payload: existing.payload,
      reconciliation_note: noteClean,
      reconciled_at: new Date(nowMs).toISOString(),
    };

    // Append a durable note without rewriting/truncating the legacy history.
    // A note never substitutes for a server receipt or removes a pending sale.
    await this.idb.put('sync_attempts', { ...reconciledRecord,
      attempt_id: `${existing.operation_id}_note_${this.generateOperationId()}`,
      kind: existing.kind, status: 'reconciliation_note', http_status: 409,
      fetched_at_ms: nowMs, attempted_at: new Date(nowMs).toISOString(),
    });
    await this.idb.put('pending_operations', { ...existing, status: 'reconciliation_required',
      reconciliation_required: true, reconciliation_note: noteClean, next_retry_at_ms: null,
      last_error: 'Nota guardada; la operaci\u00f3n sigue pendiente de confirmaci\u00f3n verificable.' });
    await this.refreshCountFromDb();
  }

  /**
   * CU39W: Permite descartar una operación en conflicto (carrito o reserva).
   * Para ventas en efectivo rechazadas (`VENTA_CONTADO` en `reconciliation_required`),
   * redirige a `reconcileCashSaleIncidence` para garantizar que jamás se eliminen silenciosamente.
   */
  async discardOperation(operationId: string, reconciliationNote?: string): Promise<void> {
    const existing = await this.getActiveOperation(operationId);
    if (!existing) return;

    if (
      existing.kind === 'VENTA_CONTADO'
    ) {
      await this.reconcileCashSaleIncidence(
        operationId,
        reconciliationNote || 'Venta en efectivo offline registrada como incidencia para arqueo/conciliación física.'
      );
      return;
    }

    await this.idb.put('pending_operations', { ...existing, status: 'conflict',
      conflict_code: existing.conflict_code || 'LOCAL_REVIEW_REQUIRED',
      last_error: 'Se conserva la operación: descartarla no verifica su resultado en el servidor.', next_retry_at_ms: null });
    await this.refreshCountFromDb();
  }
}
