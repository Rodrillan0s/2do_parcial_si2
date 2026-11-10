import { PLATFORM_ID } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { IDBFactory, IDBObjectStore } from 'fake-indexeddb';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { IndexedDbService } from './indexed-db.service';
import { OperationIdentity, VerifiedSyncResult } from '../sync/sync-confirmation';

const operation = (id = 'operation-one'): OperationIdentity => ({ operation_id: id, kind: 'VENTA_CONTADO',
  user_id: 3, tenant_id: 1, scope_key: 'u:3|e:1|b:1', branch_id: 1,
  created_at: '2026-10-31T12:00:00Z', payload: { items: [{ id_variante: 100, cantidad: 2 }] } });
const receipt = (op: OperationIdentity): VerifiedSyncResult => ({ operation_id: op.operation_id, kind: op.kind,
  status: 'synced', http_status: 200, confirmation_verified: true,
  confirmation: { operation_id: op.operation_id, id_usuario: op.user_id, id_empresa: op.tenant_id, request_hash: 'a'.repeat(64) },
  data: { id_venta: 7, id_pago: 8, estado_venta: 'PAGADO' } });

describe('IndexedDbService: evidencia durable de sincronización', () => {
  let storage: IndexedDbService;
  beforeEach(() => {
    vi.stubGlobal('indexedDB', new IDBFactory());
    TestBed.configureTestingModule({ providers: [{ provide: PLATFORM_ID, useValue: 'browser' }] });
    storage = TestBed.inject(IndexedDbService);
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it('confirma recibo e intento y retira pendiente en una única transacción', async () => {
    const op = operation();
    await storage.put('pending_operations', op);
    await storage.acknowledgeOperation(op, receipt(op));
    expect(await storage.get('pending_operations', op.operation_id)).toBeNull();
    const stored = await storage.get<any>('sync_receipts', op.operation_id);
    expect(stored.request).toEqual(op);
    expect(stored.data.id_venta).toBe(7);
    expect((await storage.getAllByScope('sync_attempts', 'u:3|e:1|')).length).toBe(1);
  });

  it('retiene el pendiente si falla escribir el recibo, sin caer a RAM', async () => {
    const op = operation();
    await storage.put('pending_operations', op);
    const original = IDBObjectStore.prototype.put;
    vi.spyOn(IDBObjectStore.prototype, 'put').mockImplementation(function(this: IDBObjectStore, ...args: Parameters<typeof original>) {
      if (this.name === 'sync_receipts') throw new DOMException('Disk full', 'QuotaExceededError');
      return original.apply(this, args);
    });
    await expect(storage.acknowledgeOperation(op, receipt(op))).rejects.toThrow();
    expect(await storage.get('pending_operations', op.operation_id)).toEqual(op);
    expect(await storage.get('sync_receipts', op.operation_id)).toBeNull();
    expect(await storage.getAllByScope('sync_attempts', '')).toEqual([]);
  });

  it('revierte también el recibo si falla retirar el pendiente', async () => {
    const op = operation();
    await storage.put('pending_operations', op);
    vi.spyOn(IDBObjectStore.prototype, 'delete').mockImplementation(() => { throw new Error('Injected delete failure'); });
    await expect(storage.acknowledgeOperation(op, receipt(op))).rejects.toThrow();
    expect(await storage.get('pending_operations', op.operation_id)).toEqual(op);
    expect(await storage.get('sync_receipts', op.operation_id)).toBeNull();
    expect(await storage.getAllByScope('sync_attempts', '')).toEqual([]);
  });

  for (const field of ['user', 'tenant', 'operation', 'kind', 'confirmation', 'hash', 'http', 'sale', 'payment', 'paid'] as const) {
    it(`no elimina una operación con recibo inválido: ${field}`, async () => {
      const op = operation(), result = receipt(op);
      if (field === 'user') result.confirmation!.id_usuario = 99;
      if (field === 'tenant') result.confirmation!.id_empresa = 2;
      if (field === 'operation') result.confirmation!.operation_id = 'another';
      if (field === 'kind') result.kind = 'RESERVA_SOLICITUD';
      if (field === 'confirmation') result.confirmation_verified = false;
      if (field === 'hash') result.confirmation!.request_hash = 'invalid';
      if (field === 'http') (result as Partial<VerifiedSyncResult>).http_status = undefined;
      if (field === 'sale') delete result.data.id_venta;
      if (field === 'payment') delete result.data.id_pago;
      if (field === 'paid') result.data.estado_venta = 'PENDIENTE_PAGO';
      await storage.put('pending_operations', op);
      await expect(storage.acknowledgeOperation(op, result)).rejects.toThrow();
      expect(await storage.get('pending_operations', op.operation_id)).toEqual(op);
    });
  }

  it('conserva una operación editada durante el envío y rechaza el recibo del contenido anterior', async () => {
    const op = operation(), changed = { ...op, payload: { items: [{ id_variante: 100, cantidad: 3 }] } };
    await storage.put('pending_operations', changed);
    await expect(storage.acknowledgeOperation(op, receipt(op))).rejects.toThrow('cambió');
    expect(await storage.get('pending_operations', op.operation_id)).toEqual(changed);
  });

  it('la purga de logout/401 conserva pendientes y recibos tras crear otra instancia', async () => {
    const done = operation('done'), pending = operation('pending');
    await storage.put('pending_operations', done);
    await storage.acknowledgeOperation(done, receipt(done));
    await storage.put('pending_operations', pending);
    await storage.put('cart_drafts', { key: 'draft', scope_key: done.scope_key });
    await storage.purgePrivateData();
    const reopened = TestBed.runInInjectionContext(() => new IndexedDbService());
    expect(await reopened.get('pending_operations', pending.operation_id)).toEqual(pending);
    expect(await reopened.get('sync_receipts', done.operation_id)).toBeTruthy();
    expect(await reopened.getAllByScope('sync_attempts', done.scope_key)).toHaveLength(1);
    expect(await reopened.get('cart_drafts', 'draft')).toBeNull();
    expect(await reopened.getAllByScope('pending_operations', 'u:33|e:1|')).toEqual([]);
  });

  it('no acepta escrituras críticas ni lecturas aparentes cuando IndexedDB no está disponible', async () => {
    vi.stubGlobal('indexedDB', undefined);
    await expect(storage.put('pending_operations', operation())).rejects.toThrow();
    await expect(storage.getAllByScope('pending_operations', '')).rejects.toThrow();
    await storage.put('catalog_filters', { key: 'cache', scope_key: 'public|e:1' });
    expect(await storage.get('catalog_filters', 'cache')).toBeTruthy();
  });

  it('una cuota agotada no convierte un pendiente nuevo en un éxito guardado en RAM', async () => {
    const original = IDBObjectStore.prototype.put;
    vi.spyOn(IDBObjectStore.prototype, 'put').mockImplementation(function(this: IDBObjectStore, ...args: Parameters<typeof original>) {
      if (this.name === 'pending_operations') throw new DOMException('Full', 'QuotaExceededError');
      return original.apply(this, args);
    });
    await expect(storage.put('pending_operations', operation())).rejects.toThrow();
    expect(storage.storageStatus()).toBe('QUOTA_WARNING');
    const reopened = TestBed.runInInjectionContext(() => new IndexedDbService());
    expect(await reopened.getAllByScope('pending_operations', '')).toEqual([]);
  });

  it('no permite borrar directamente operaciones o evidencia', async () => {
    const op = operation();
    await storage.put('pending_operations', op);
    for (const store of ['pending_operations', 'sync_attempts', 'sync_receipts'] as const) {
      await expect(storage.delete(store, op.operation_id)).rejects.toThrow();
    }
    expect(await storage.get('pending_operations', op.operation_id)).toEqual(op);
  });

  it('una escritura atrasada de otra pestaña no recrea un pendiente ya confirmado', async () => {
    const op = operation();
    await storage.put('pending_operations', op);
    await storage.acknowledgeOperation(op, receipt(op));
    const otherTab = TestBed.runInInjectionContext(() => new IndexedDbService());
    await expect(otherTab.put('pending_operations', { ...op, status: 'failed_retryable' })).rejects.toThrow('recibo durable');
    expect(await storage.get('pending_operations', op.operation_id)).toBeNull();
  });

  for (const version of [3, 7]) it(`abre/migra IndexedDB v${version} sin borrar operaciones`, async () => {
    const op = operation();
    await new Promise<void>((resolve, reject) => {
      const req = indexedDB.open('aurora_store_pwa_db', version);
      req.onupgradeneeded = () => req.result.createObjectStore('pending_operations', { keyPath: 'operation_id' }).put(op);
      req.onsuccess = () => { req.result.close(); resolve(); };
      req.onerror = () => reject(req.error);
    });
    expect(await storage.get('pending_operations', op.operation_id)).toEqual(op);
    await storage.acknowledgeOperation(op, receipt(op));
    expect(await storage.get('sync_receipts', op.operation_id)).toBeTruthy();
  });
});
