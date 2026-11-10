import { PLATFORM_ID, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { IDBFactory } from 'fake-indexeddb';
import { Subject, of, throwError } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthService } from '../../services/auth';
import { IndexedDbService } from '../storage/indexed-db.service';
import { NetworkStatusService } from '../network/network-status.service';
import { PendingOperation, SyncBatchItemResult, SyncBatchResponse, SyncOperationKind, SyncQueueService } from './sync-queue.service';

describe('SyncQueueService: conservación de operaciones', () => {
  let queue: SyncQueueService, storage: IndexedDbService;
  let user: ReturnType<typeof signal<{ id_usuario: number; id_empresa: number } | null>>;
  let token: ReturnType<typeof signal<string | null>>;
  let tenant: ReturnType<typeof signal<number>>;
  let companyChanged: Subject<unknown>;
  let http: { post: ReturnType<typeof vi.fn> };
  let network: { isOnline: ReturnType<typeof vi.fn>; verifyApiConnectivity: ReturnType<typeof vi.fn>; setSyncingState: ReturnType<typeof vi.fn>; reconnected$: Subject<number> };

  beforeEach(async () => {
    vi.stubGlobal('indexedDB', new IDBFactory());
    user = signal({ id_usuario: 3, id_empresa: 1 }); token = signal('token-A'); tenant = signal(1);
    companyChanged = new Subject();
    http = { post: vi.fn() };
    network = { isOnline: vi.fn(() => false), verifyApiConnectivity: vi.fn(async () => true), setSyncingState: vi.fn(), reconnected$: new Subject() };
    TestBed.configureTestingModule({ providers: [
      { provide: PLATFORM_ID, useValue: 'browser' }, { provide: HttpClient, useValue: http },
      { provide: AuthService, useValue: { obtenerUsuario: () => user(), estaAutenticado: () => !!user() && !!token(),
        obtenerToken: () => token(), getEffectiveCompanyId: () => tenant(), activeBranch: signal({ id: 1 }),
        companyChanged$: companyChanged, branchChanged$: new Subject() } },
      { provide: NetworkStatusService, useValue: network },
    ] });
    storage = TestBed.inject(IndexedDbService); queue = TestBed.inject(SyncQueueService);
    await queue.refreshOperations();
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  const valid = (op: PendingOperation): SyncBatchItemResult => ({ operation_id: op.operation_id, kind: op.kind,
    status: 'synced', http_status: 200, confirmation_verified: true,
    confirmation: { operation_id: op.operation_id, id_usuario: op.user_id, id_empresa: op.tenant_id, request_hash: 'b'.repeat(64) },
    data: op.kind === 'RESERVA_SOLICITUD' ? { id_reserva: 10, codigo_reserva: 'RES-10' } :
      op.kind === 'VENTA_CONTADO' ? { id_venta: 10, id_pago: 11, estado_venta: 'PAGADO' } : { items: [] } });
  const batch = (results: SyncBatchItemResult[]): SyncBatchResponse => ({ success: true, results, total: results.length,
    synced_count: results.filter(r => r.status === 'synced').length, failed_count: 0, conflict_count: 0 });
  const make = (kind: SyncOperationKind = 'VENTA_CONTADO', entityId?: string) => queue.enqueue({ kind, entityId,
    summaryLabel: 'Test local', payload: { id_sucursal: 1, items: [{ id_variante: 100, cantidad: 2 }] } });

  it('retira únicamente una operación con recibo válido y conserva su evidencia', async () => {
    const op = await make(); http.post.mockReturnValue(of(batch([valid(op)])));
    expect((await queue.syncNow())?.synced_count).toBe(1);
    expect(await storage.get('pending_operations', op.operation_id)).toBeNull();
    expect((await storage.get<any>('sync_receipts', op.operation_id)).data.id_venta).toBe(10);
  });

  it('HTTP 200 y synced sin confirmación conservan el sobre original para reenviar', async () => {
    const op = await make(), result = valid(op); delete result.confirmation;
    http.post.mockReturnValue(of(batch([result])));
    expect((await queue.syncNow())?.synced_count).toBe(0);
    const stored = await storage.get<PendingOperation>('pending_operations', op.operation_id);
    expect(stored?.status).toBe('failed_retryable');
    expect(stored?.payload).toEqual(op.payload); expect(stored?.created_at).toBe(op.created_at);
    expect(await storage.get('sync_receipts', op.operation_id)).toBeNull();
  });

  it('respuesta parcial confirma la primera y conserva la segunda como reintentable', async () => {
    const first = await make(), second = await make('RESERVA_SOLICITUD');
    http.post.mockReturnValue(of(batch([valid(first)])));
    const result = await queue.syncNow();
    expect(result?.synced_count).toBe(1); expect(result?.failed_count).toBe(1);
    expect(await storage.get('pending_operations', first.operation_id)).toBeNull();
    expect((await storage.get<PendingOperation>('pending_operations', second.operation_id))?.status).toBe('failed_retryable');
  });

  it('no vuelve a crear la operación ya confirmada si falla guardar un recibo posterior', async () => {
    const first = await make(), second = await make('RESERVA_SOLICITUD');
    // Establish ordering explicitly; an emulator can persist both within 1 ms.
    await storage.put('pending_operations', { ...second, created_at_ms: first.created_at_ms + 1 });
    const acknowledge = storage.acknowledgeOperation.bind(storage);
    vi.spyOn(storage, 'acknowledgeOperation').mockImplementation((op, result) => op.operation_id === second.operation_id
      ? Promise.reject(new Error('Injected disk failure')) : acknowledge(op, result));
    http.post.mockReturnValue(of(batch([valid(first), valid(second)])));
    expect(await queue.syncNow()).toBeNull();
    expect(await storage.get('pending_operations', first.operation_id)).toBeNull();
    expect(await storage.get('sync_receipts', first.operation_id)).toBeTruthy();
    expect((await storage.get<PendingOperation>('pending_operations', second.operation_id))?.payload).toEqual(second.payload);
  });

  it('tras una respuesta HTTP perdida conserva UUID, usuario, tenant, fecha y payload', async () => {
    const op = await make(); http.post.mockReturnValue(throwError(() => new Error('Lost HTTP response')));
    await queue.syncNow();
    const reopened = TestBed.runInInjectionContext(() => new IndexedDbService());
    const stored = await reopened.get<PendingOperation>('pending_operations', op.operation_id);
    for (const field of ['operation_id', 'user_id', 'tenant_id', 'created_at', 'payload'] as const) expect(stored?.[field]).toEqual(op[field]);
    http.post.mockReturnValue(of(batch([{ ...valid(op), idempotent_replay: true }])));
    expect((await queue.syncNow(true))?.synced_count).toBe(1);
  });

  it('dos reconexiones simultáneas solo envían un lote', async () => {
    const op = await make(); http.post.mockReturnValue(of(batch([valid(op)])));
    await Promise.all([queue.syncNow(), queue.syncNow()]);
    expect(http.post).toHaveBeenCalledOnce();
  });

  it('no envía operaciones si cambia la cuenta durante la comprobación de conectividad', async () => {
    await make();
    network.verifyApiConnectivity.mockImplementation(async () => { user.set({ id_usuario: 4, id_empresa: 2 }); token.set('token-B'); tenant.set(2); return true; });
    expect(await queue.syncNow()).toBeNull();
    expect(http.post).not.toHaveBeenCalled(); expect(queue.operations()).toEqual([]);
    expect(await storage.getAllByScope('pending_operations', 'u:3|e:1|')).toHaveLength(1);
  });

  it('ignora una respuesta de otra sesión y recupera el pendiente al reautenticar su propietario', async () => {
    const op = await make(); const reply = new Subject<SyncBatchResponse>();
    let sent!: () => void; const started = new Promise<void>(resolve => { sent = resolve; });
    http.post.mockImplementation(() => { sent(); return reply; });
    const inFlight = queue.syncNow(); await started;
    user.set({ id_usuario: 4, id_empresa: 2 }); token.set('token-B'); tenant.set(2); companyChanged.next(null);
    expect(queue.operations()).toEqual([]);
    reply.next(batch([valid(op)])); reply.complete();
    expect(await inFlight).toBeNull();
    expect(await storage.get('pending_operations', op.operation_id)).toBeTruthy();
    expect(await storage.get('sync_receipts', op.operation_id)).toBeNull();
    user.set({ id_usuario: 3, id_empresa: 1 }); token.set('token-A'); tenant.set(1);
    await queue.refreshOperations();
    http.post.mockReturnValue(of(batch([{ ...valid(op), idempotent_replay: true }])));
    expect((await queue.syncNow())?.synced_count).toBe(1);
  });

  it('logout/401 ocultan los pendientes y la purga los conserva para su propietario', async () => {
    const op = await make();
    user.set(null); token.set(null); companyChanged.next(null);
    await storage.purgePrivateData();
    expect(queue.operations()).toEqual([]); expect(await queue.syncNow()).toBeNull();
    expect(http.post).not.toHaveBeenCalled();
    user.set({ id_usuario: 3, id_empresa: 1 }); token.set('token-A');
    await queue.refreshOperations();
    expect(queue.operations().map(item => item.operation_id)).toContain(op.operation_id);
  });

  it('anotar conciliación conserva venta y evidencia sin truncar el historial a 50', async () => {
    const op = await make();
    await storage.put('metadata', { key: 'u:3|e:1|reconciled_sales', scope_key: op.scope_key,
      items: Array.from({ length: 60 }, (_, i) => ({ operation_id: `old-${i}`, user_id: 3, tenant_id: 1, scope_key: op.scope_key })) });
    await queue.reconcileCashSaleIncidence(op.operation_id, 'Nota de revisión');
    const stored = await storage.get<PendingOperation>('pending_operations', op.operation_id);
    expect(stored?.reconciliation_note).toBe('Nota de revisión');
    expect(stored?.status).toBe('reconciliation_required');
    expect(queue.reconciledHistory()).toHaveLength(61);
    expect(await storage.get('sync_receipts', op.operation_id)).toBeNull();
    expect(http.post).not.toHaveBeenCalled();
  });

  it('descartar reserva o venta sin recibo conserva la operación para revisión', async () => {
    for (const kind of ['RESERVA_SOLICITUD', 'VENTA_CONTADO'] as const) {
      const op = await make(kind); await queue.discardOperation(op.operation_id);
      expect(await storage.get('pending_operations', op.operation_id)).toBeTruthy();
    }
  });

  it('otra cuenta no puede anotar, descartar ni resolver una operación por su UUID', async () => {
    const op = await make(); user.set({ id_usuario: 4, id_empresa: 1 }); token.set('token-B');
    await expect(queue.discardOperation(op.operation_id)).rejects.toThrow('otro usuario');
    await expect(queue.reconcileCashSaleIncidence(op.operation_id, 'Wrong owner')).rejects.toThrow();
    await expect(queue.resolveConflictWithPatch(op.operation_id, {})).rejects.toThrow();
    expect((await storage.get<PendingOperation>('pending_operations', op.operation_id))?.payload).toEqual(op.payload);
  });

  it('no modifica el contenido de una operación cuyo resultado es incierto', async () => {
    const op = await make();
    await expect(queue.resolveConflictWithPatch(op.operation_id, { monto_recibido: 999 })).rejects.toThrow('incierto');
    expect((await storage.get<PendingOperation>('pending_operations', op.operation_id))?.payload).toEqual(op.payload);
  });

  it('rechaza sobrescribir una clave pendiente con otro contenido', async () => {
    const op = await make();
    await expect(queue.enqueue({ operationId: op.operation_id, kind: op.kind,
      payload: { changed: true }, summaryLabel: 'Overwrite' })).rejects.toThrow('clave local');
    expect((await storage.get<PendingOperation>('pending_operations', op.operation_id))?.payload).toEqual(op.payload);
  });

  it('no compacta un carrito que ya pudo haber llegado al servidor', async () => {
    const op = await make('CART_ADD_ITEM', '100');
    await storage.put('pending_operations', { ...op, status: 'pending', attempt_count: 1 });
    const next = await make('CART_ADD_ITEM', '100');
    expect(next.operation_id).not.toBe(op.operation_id);
    expect(await storage.getAllByScope('pending_operations', 'u:3|e:1|')).toHaveLength(2);
  });

  it('cancelar un agregado de carrito antes del primer envío conserva su evidencia', async () => {
    const op = await make('CART_ADD_ITEM', '100');
    await queue.enqueue({ kind: 'CART_REMOVE_ITEM', entityId: '100', summaryLabel: 'Cancel',
      payload: { id_detalle_carrito: -1 } });
    const stored = await storage.get<PendingOperation>('pending_operations', op.operation_id);
    expect(stored?.conflict_code).toBe('LOCAL_CANCELLED_BEFORE_SEND');
    expect(stored?.status).toBe('failed_permanent');
    expect(stored?.payload).toEqual(op.payload);
    expect(http.post).not.toHaveBeenCalled();
  });

  it('un estado local synced de una versión previa no sustituye un recibo verificable', async () => {
    const op = await make();
    await storage.put('pending_operations', { ...op, status: 'synced' });
    await queue.refreshOperations();
    expect(queue.operations()[0].status).toBe('failed_retryable');
    expect(await storage.get('pending_operations', op.operation_id)).toBeTruthy();
  });

  it('recupera syncing de un proceso anterior al iniciar directamente un reenvío', async () => {
    const op = await make();
    await storage.put('pending_operations', { ...op, status: 'syncing' });
    http.post.mockReturnValue(of(batch([{ ...valid(op), idempotent_replay: true }])));
    expect((await queue.syncNow())?.synced_count).toBe(1);
    expect(await storage.get('pending_operations', op.operation_id)).toBeNull();
  });

  it('no inventa una nota de conciliación cuando el usuario no la ingresó', async () => {
    const op = await make();
    await expect(queue.reconcileCashSaleIncidence(op.operation_id, '')).rejects.toThrow('nota');
    expect((await storage.get<PendingOperation>('pending_operations', op.operation_id))?.status).toBe('pending');
  });
});
