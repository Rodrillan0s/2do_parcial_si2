import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NetworkStatusService } from '../../core/network/network-status.service';
import { PendingOperation, SyncQueueService } from '../../core/sync/sync-queue.service';
import { PwaUpdateService } from '../../core/pwa/pwa-update.service';
import { IndexedDbService } from '../../core/storage/indexed-db.service';

@Component({
  selector: 'app-pwa-status-bar',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <!-- Top Banner para Conectividad / Operaciones Pendientes / Conflictos / Nueva Versión PWA -->
    <div
      *ngIf="shouldShowTopBar()"
      role="status"
      aria-live="polite"
      class="w-full z-50 border-b text-xs font-medium transition-colors duration-200"
      [ngClass]="topBarClasses()">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 py-2 flex flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-2.5">
          <!-- Indicador de estado -->
          <span
            class="inline-block w-2 h-2 rounded-full shrink-0"
            [ngClass]="{
              'bg-amber-400 animate-pulse': networkStatus.connectionState() === 'OFFLINE' || networkStatus.connectionState() === 'CHECKING',
              'bg-sky-400 animate-ping': networkStatus.connectionState() === 'SYNCING' || syncQueue.isSyncing(),
              'bg-rose-400': syncQueue.conflictCount() > 0,
              'bg-emerald-400': networkStatus.isOnline() && syncQueue.conflictCount() === 0
            }">
          </span>

          <!-- Mensaje contextual -->
          <span *ngIf="networkStatus.connectionState() === 'OFFLINE'">
            <strong>Modo sin conexión activo:</strong> Puedes consultar datos descargados, registrar solicitudes de reserva y cobrar ventas en efectivo en caja.
          </span>

          <span *ngIf="networkStatus.connectionState() === 'CHECKING'">
            Comprobando conexión real con el servidor de AuroraStore...
          </span>

          <span *ngIf="networkStatus.connectionState() === 'SYNCING' || syncQueue.isSyncing()">
            Sincronizando tus operaciones pendientes con el servidor...
          </span>

          <span *ngIf="networkStatus.connectionState() === 'ONLINE' && !syncQueue.isSyncing() && syncQueue.conflictCount() > 0">
            <strong>Atención:</strong> Tienes {{ syncQueue.conflictCount() }} operación(es) con conflicto o conciliación de caja pendiente.
          </span>

          <span *ngIf="networkStatus.connectionState() === 'ONLINE' && !syncQueue.isSyncing() && syncQueue.conflictCount() === 0 && syncQueue.pendingCount() > 0">
            Tienes {{ syncQueue.pendingCount() }} operación(es) en cola listas para sincronizar.
          </span>

          <span *ngIf="syncQueue.lastSyncBannerMessage() as msg">
            {{ msg.text }}
          </span>

          <span *ngIf="pwaUpdate.updateAvailable()">
            <span *ngIf="pwaUpdate.staleChunkDetected()">
              <strong>Actualización requerida:</strong> Se detectaron componentes actualizados en el servidor. Actualiza para continuar navegando fluidamente.
            </span>
            <span *ngIf="!pwaUpdate.staleChunkDetected()">
              Hay una nueva versión de AuroraStore lista para aplicar.
            </span>
          </span>

          <span *ngIf="indexedDb.storageStatus() !== 'OK' && indexedDb.storageWarningMessage()">
            {{ indexedDb.storageWarningMessage() }}
          </span>
        </div>

        <div class="flex items-center gap-2 ml-auto">
          <!-- Botón Sincronizar Ahora (CU38W) -->
          <button
            *ngIf="syncQueue.pendingCount() > 0 && networkStatus.isOnline() && !syncQueue.isSyncing()"
            type="button"
            (click)="sincronizarAhora()"
            class="px-2.5 py-1 rounded bg-white/15 hover:bg-white/25 text-white font-semibold transition cursor-pointer">
            Sincronizar ahora ({{ syncQueue.pendingCount() }})
          </button>

          <!-- Botón Ver Cola / Resolver Conflictos (CU37W / CU39W) -->
          <button
            type="button"
            (click)="abrirPanel()"
            class="px-2.5 py-1 rounded border border-white/25 hover:bg-white/15 transition cursor-pointer flex items-center gap-1.5">
            <span>Cola Offline ({{ syncQueue.activeOperations().length }})</span>
            <span *ngIf="syncQueue.conflictCount() > 0" class="px-1.5 py-0.2 rounded-full bg-rose-500 text-white text-[10px] font-bold">
              {{ syncQueue.conflictCount() }} conflicto(s)
            </span>
          </button>

          <!-- Botón Actualizar PWA -->
          <button
            *ngIf="pwaUpdate.updateAvailable()"
            type="button"
            (click)="pwaUpdate.applyUpdateNow()"
            class="px-2.5 py-1 rounded bg-amber-400 text-zinc-950 font-semibold hover:bg-amber-300 transition cursor-pointer">
            Actualizar aplicación
          </button>

          <!-- Cerrar aviso de sincronización -->
          <button
            *ngIf="syncQueue.lastSyncBannerMessage()"
            type="button"
            (click)="syncQueue.dismissBannerMessage()"
            aria-label="Cerrar notificación"
            class="p-1 opacity-75 hover:opacity-100 cursor-pointer">
            ✕
          </button>
        </div>
      </div>
    </div>

    <!-- Píldora flotante discreta (abajo a la izquierda) para consultar Estado Offline / Cola en cualquier momento -->
    <div class="fixed bottom-4 left-4 z-40">
      <button
        type="button"
        (click)="abrirPanel()"
        title="Estado de conexión y operaciones pendientes"
        class="flex items-center gap-2 px-3 py-1.5 rounded-full shadow-lg border text-xs font-medium transition-all cursor-pointer backdrop-blur-md"
        [ngClass]="{
          'bg-zinc-900/90 text-zinc-100 border-zinc-700 hover:border-zinc-500': networkStatus.isOnline() && syncQueue.conflictCount() === 0 && syncQueue.pendingCount() === 0,
          'bg-amber-950/95 text-amber-200 border-amber-700': !networkStatus.isOnline() || syncQueue.pendingCount() > 0,
          'bg-rose-950/95 text-rose-200 border-rose-700 animate-pulse': syncQueue.conflictCount() > 0
        }">
        <span
          class="w-2 h-2 rounded-full"
          [ngClass]="{
            'bg-emerald-400': networkStatus.isOnline() && syncQueue.conflictCount() === 0,
            'bg-amber-400': !networkStatus.isOnline(),
            'bg-rose-400': syncQueue.conflictCount() > 0
          }">
        </span>
        <span>{{ estadoEtiqueta() }}</span>
        <span
          *ngIf="syncQueue.activeOperations().length > 0"
          class="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-white/15">
          {{ syncQueue.activeOperations().length }}
        </span>
      </button>
    </div>

    <!-- Modal / Drawer del Centro de Sincronización Offline -->
    <div
      *ngIf="panelOpen()"
      class="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs"
      (click)="cerrarPanel()">
      <div
        class="relative w-full max-w-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 h-full shadow-2xl border-l border-zinc-200 dark:border-zinc-800 flex flex-col"
        (click)="$event.stopPropagation()">
        <!-- Encabezado -->
        <div class="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
          <div>
            <span class="text-[10px] uppercase tracking-widest text-amber-600 dark:text-amber-400 font-bold">
              PWA Offline-First · Sincronización Inteligente
            </span>
            <h2 class="text-base font-bold mt-0.5">Centro de Conectividad y Sincronización</h2>
          </div>
          <button
            type="button"
            (click)="cerrarPanel()"
            class="p-2 rounded-lg text-zinc-500 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer">
            ✕
          </button>
        </div>

        <!-- Resumen de red y almacenamiento -->
        <div class="px-6 py-3.5 bg-zinc-50 dark:bg-zinc-950/60 border-b border-zinc-200 dark:border-zinc-800 space-y-2 text-xs">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span
                class="w-2.5 h-2.5 rounded-full"
                [ngClass]="{
                  'bg-emerald-500': networkStatus.connectionState() === 'ONLINE',
                  'bg-amber-500': networkStatus.connectionState() === 'OFFLINE' || networkStatus.connectionState() === 'CHECKING',
                  'bg-sky-500 animate-ping': networkStatus.connectionState() === 'SYNCING'
                }">
              </span>
              <span class="font-semibold">Estado actual: {{ estadoEtiqueta() }}</span>
            </div>
            <button
              type="button"
              (click)="comprobarRed()"
              class="px-2.5 py-1 rounded border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-200 dark:hover:bg-zinc-800 transition cursor-pointer">
              Verificar API
            </button>
          </div>

          <div class="flex flex-wrap items-center justify-between text-[11px] text-zinc-500 dark:text-zinc-400 gap-2">
            <span>Almacenamiento IndexedDB: <strong>{{ indexedDb.storageStatus() }}</strong></span>
            <span *ngIf="syncQueue.lastSyncedAt()">
              Última sync: {{ syncQueue.lastSyncedAt() | date:'shortTime' }}
            </span>
          </div>
        </div>

        <!-- Barra de acción CU38W -->
        <div class="px-6 py-3 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between gap-3">
          <div class="text-xs text-zinc-600 dark:text-zinc-400">
            <strong>{{ syncQueue.pendingCount() }}</strong> pendiente(s) ·
            <strong>{{ syncQueue.conflictCount() }}</strong> incidencia(s)/conflicto(s)
          </div>
          <button
            type="button"
            [disabled]="!networkStatus.isOnline() || syncQueue.pendingCount() === 0 || syncQueue.isSyncing()"
            (click)="sincronizarAhora()"
            class="px-3.5 py-1.5 rounded-lg bg-zinc-900 dark:bg-amber-500 text-white dark:text-zinc-950 text-xs font-semibold disabled:opacity-40 hover:opacity-90 transition cursor-pointer">
            {{ syncQueue.isSyncing() ? 'Sincronizando...' : 'Sincronizar pendientes' }}
          </button>
        </div>

        <!-- Lista de operaciones -->
        <div class="flex-1 overflow-y-auto p-6 space-y-3">
          <div
            *ngIf="syncQueue.activeOperations().length === 0"
            class="text-center py-12 px-4 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl">
            <p class="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              No hay operaciones pendientes de sincronización
            </p>
            <p class="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              Las reservas, ventas en efectivo de caja o cambios de bolsa que registres sin conexión aparecerán aquí y se enviarán automáticamente al reconectar.
            </p>
          </div>

          <div
            *ngFor="let op of syncQueue.activeOperations()"
            class="p-4 rounded-xl border transition-all space-y-2.5"
            [ngClass]="{
              'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900': op.status === 'pending' || op.status === 'syncing',
              'border-rose-300 dark:border-rose-800/80 bg-rose-50/40 dark:bg-rose-950/20': op.status === 'conflict' || op.status === 'reconciliation_required' || op.status === 'failed_permanent',
              'border-amber-300 dark:border-amber-800/80 bg-amber-50/40 dark:bg-amber-950/20': op.status === 'failed_retryable'
            }">
            <div class="flex items-start justify-between gap-2">
              <div>
                <span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
                  {{ etiquetaTipo(op.kind) }}
                </span>
                <h3 class="text-xs font-semibold mt-1.5">{{ op.summary_label }}</h3>
              </div>

              <span
                class="text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0"
                [ngClass]="{
                  'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200': op.status === 'pending' || op.status === 'failed_retryable',
                  'bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-200': op.status === 'syncing',
                  'bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-200': op.status === 'conflict' || op.status === 'reconciliation_required' || op.status === 'failed_permanent'
                }">
                {{ etiquetaEstadoOperacion(op.status) }}
              </span>
            </div>

            <div class="flex items-center justify-between text-[11px] text-zinc-500 dark:text-zinc-400">
              <span>Creada: {{ op.created_at | date:'short' }}</span>
              <span>Intentos: {{ op.attempt_count }}</span>
            </div>

            <!-- Detalle de error o conflicto (CU39W) -->
            <div
              *ngIf="op.last_error"
              class="p-2.5 rounded-lg bg-rose-100/70 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800/60 text-xs text-rose-900 dark:text-rose-200">
              <p class="font-semibold">{{ op.last_error }}</p>
              <p *ngIf="op.conflict_code" class="text-[10px] opacity-80 mt-0.5">
                Código: {{ op.conflict_code }}
              </p>
            </div>

            <!-- Formulario inline de Conciliación de Caja para VENTA_CONTADO en conflicto -->
            <div
              *ngIf="reconcilingOpId() === op.operation_id"
              class="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 space-y-2 text-xs">
              <label class="block font-bold text-amber-900 dark:text-amber-200">
                Nota de Conciliación Física de Caja (Obligatoria para auditoría):
              </label>
              <input
                type="text"
                [(ngModel)]="reconciliationNote"
                placeholder="Ej: Efectivo devuelto al cliente / Ajuste en arqueo de turno..."
                class="w-full px-2.5 py-1.5 rounded bg-white dark:bg-zinc-900 border border-amber-300 dark:border-amber-700 text-xs outline-none" />
              <div class="flex items-center justify-end gap-2">
                <button
                  type="button"
                  (click)="cancelarConciliacion()"
                  class="px-2.5 py-1 rounded border border-zinc-300 dark:border-zinc-700 text-xs cursor-pointer">
                  Cancelar
                </button>
                <button
                  type="button"
                  (click)="confirmarConciliacionVenta(op)"
                  class="px-3 py-1 rounded bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs cursor-pointer">
                  Guardar nota de conciliación
                </button>
              </div>
            </div>

            <!-- Botones de resolución de conflictos (CU39W) -->
            <div class="pt-1 flex flex-wrap items-center gap-2">
              <!-- Resolver STOCK_INSUFFICIENT ajustando a stock disponible -->
              <button
                *ngIf="op.conflict_code === 'STOCK_INSUFFICIENT' && getAvailableStock(op) > 0"
                type="button"
                (click)="ajustarStockYReintentar(op)"
                class="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition cursor-pointer">
                Ajustar a {{ getAvailableStock(op) }} disponible(s) y sincronizar
              </button>

              <!-- Resolver PRICE_CHANGED aceptando nuevo precio vigente -->
              <button
                *ngIf="op.conflict_code === 'PRICE_CHANGED' && getCurrentPrice(op) > 0"
                type="button"
                (click)="aceptarNuevoPrecioYReintentar(op)"
                class="px-2.5 py-1 rounded-lg bg-amber-500 hover:bg-amber-400 text-zinc-950 text-xs font-semibold transition cursor-pointer">
                Aceptar precio actual (Bs. {{ getCurrentPrice(op) | number:'1.2-2' }})
              </button>

              <!-- Reintentar operación -->
              <button
                *ngIf="op.status === 'conflict' || op.status === 'reconciliation_required' || op.status === 'failed_retryable'"
                type="button"
                (click)="reintentarOperacion(op)"
                class="px-2.5 py-1 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-xs font-medium transition cursor-pointer">
                Reintentar
              </button>

              <!-- Para VENTA_CONTADO rechazada: NUNCA eliminar silenciosamente; exigir Conciliación -->
              <button
                *ngIf="op.kind === 'VENTA_CONTADO' && (op.status === 'reconciliation_required' || op.reconciliation_required || op.status === 'conflict')"
                type="button"
                (click)="abrirConciliacion(op)"
                class="px-2.5 py-1 rounded-lg bg-amber-600/15 text-amber-700 dark:text-amber-300 border border-amber-500/40 hover:bg-amber-600/25 text-xs font-semibold transition cursor-pointer ml-auto">
                Registrar Conciliación de Caja
              </button>

              <!-- Descartar operación (solo para carrito, reservas o ventas aún no en conflicto) -->
              <button
                *ngIf="!(op.kind === 'VENTA_CONTADO' && (op.status === 'reconciliation_required' || op.reconciliation_required || op.status === 'conflict'))"
                type="button"
                (click)="descartarOperacion(op)"
                class="px-2.5 py-1 rounded-lg text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-xs font-medium transition cursor-pointer ml-auto">
                Conservar para revisión
              </button>
            </div>
          </div>

          <!-- Historial Auditable de Ventas en Efectivo Conciliadas -->
          <div *ngIf="syncQueue.reconciledHistory().length > 0" class="pt-4 border-t border-zinc-200 dark:border-zinc-800 space-y-2">
            <h4 class="text-[11px] font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              Notas de conciliación de caja ({{ syncQueue.reconciledHistory().length }})
            </h4>
            <div
              *ngFor="let rec of syncQueue.reconciledHistory()"
              class="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-950/60 border border-zinc-200 dark:border-zinc-800 text-xs space-y-1">
              <div class="flex items-center justify-between">
                <strong class="font-mono text-[11px]">{{ rec['entity_id'] || rec['summary_label'] }}</strong>
                <span class="text-[10px] px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold">
                  CONCILIADA
                </span>
              </div>
              <p class="text-[11px] text-zinc-500">{{ rec['last_error'] }}</p>
              <p class="text-[11px] font-medium text-amber-700 dark:text-amber-300">
                Nota: "{{ rec['reconciliation_note'] }}" · {{ rec['reconciled_at'] | date:'short' }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `
})
export class PwaStatusBarComponent {
  public networkStatus = inject(NetworkStatusService);
  public syncQueue = inject(SyncQueueService);
  public pwaUpdate = inject(PwaUpdateService);
  public indexedDb = inject(IndexedDbService);

  public panelOpen = signal<boolean>(false);
  public reconcilingOpId = signal<string | null>(null);
  public reconciliationNote: string = '';

  constructor() {
    this.pwaUpdate.initServiceWorker();
  }

  public shouldShowTopBar = computed(() => {
    return (
      this.networkStatus.connectionState() !== 'ONLINE' ||
      this.syncQueue.pendingCount() > 0 ||
      this.syncQueue.conflictCount() > 0 ||
      this.syncQueue.lastSyncBannerMessage() !== null ||
      this.pwaUpdate.updateAvailable() ||
      this.indexedDb.storageStatus() !== 'OK'
    );
  });

  public topBarClasses(): string {
    if (this.syncQueue.conflictCount() > 0) {
      return 'bg-rose-950 text-rose-100 border-rose-800';
    }
    if (!this.networkStatus.isOnline()) {
      return 'bg-zinc-900 text-amber-200 border-amber-800/70';
    }
    if (this.syncQueue.isSyncing()) {
      return 'bg-sky-950 text-sky-100 border-sky-800';
    }
    if (this.syncQueue.lastSyncBannerMessage()?.type === 'success') {
      return 'bg-emerald-950 text-emerald-100 border-emerald-800';
    }
    return 'bg-zinc-900 text-zinc-100 border-zinc-800';
  }

  public estadoEtiqueta(): string {
    const st = this.networkStatus.connectionState();
    if (st === 'OFFLINE') return 'Sin conexión';
    if (st === 'CHECKING') return 'Verificando red...';
    if (st === 'SYNCING' || this.syncQueue.isSyncing()) return 'Sincronizando...';
    return 'En línea';
  }

  public etiquetaTipo(kind: string): string {
    switch (kind) {
      case 'CART_ADD_ITEM':
        return 'Bolsa · Agregar';
      case 'CART_UPDATE_QTY':
        return 'Bolsa · Cantidad';
      case 'CART_REMOVE_ITEM':
        return 'Bolsa · Quitar';
      case 'CART_CLEAR':
        return 'Bolsa · Vaciar';
      case 'RESERVA_SOLICITUD':
        return 'Reserva · Solicitud';
      case 'VENTA_CONTADO':
        return 'Caja POS · Venta Efectivo';
      default:
        return kind;
    }
  }

  public etiquetaEstadoOperacion(status: string): string {
    switch (status) {
      case 'pending':
        return 'Pendiente';
      case 'syncing':
        return 'Sincronizando';
      case 'conflict':
        return 'Conflicto';
      case 'reconciliation_required':
        return 'Conciliación de Caja';
      case 'failed_retryable':
        return 'Reintentable';
      case 'failed_permanent':
        return 'Rechazada';
      default:
        return status;
    }
  }

  public abrirPanel(): void {
    void this.syncQueue.refreshOperations();
    this.panelOpen.set(true);
  }

  public cerrarPanel(): void {
    this.panelOpen.set(false);
    this.reconcilingOpId.set(null);
  }

  public async comprobarRed(): Promise<void> {
    const ok = await this.networkStatus.verifyApiConnectivity(true);
    if (ok && this.syncQueue.pendingCount() > 0) {
      await this.syncQueue.syncNow(true);
    }
  }

  public async sincronizarAhora(): Promise<void> {
    await this.syncQueue.syncNow(true);
  }

  public getAvailableStock(op: PendingOperation): number {
    return Number(op.conflict_detail?.['available_stock'] || 0);
  }

  public getCurrentPrice(op: PendingOperation): number {
    return Number(op.conflict_detail?.['current_unit_price'] || 0);
  }

  public async ajustarStockYReintentar(op: PendingOperation): Promise<void> {
    await this.syncQueue.adjustConflictQuantityToAvailable(op.operation_id);
  }

  public async aceptarNuevoPrecioYReintentar(op: PendingOperation): Promise<void> {
    await this.syncQueue.acceptConflictPriceChange(op.operation_id);
  }

  public async reintentarOperacion(op: PendingOperation): Promise<void> {
    await this.syncQueue.resolveConflictWithPatch(op.operation_id, {});
  }

  public abrirConciliacion(op: PendingOperation): void {
    this.reconcilingOpId.set(op.operation_id);
    this.reconciliationNote = '';
  }

  public cancelarConciliacion(): void {
    this.reconcilingOpId.set(null);
    this.reconciliationNote = '';
  }

  public async confirmarConciliacionVenta(op: PendingOperation): Promise<void> {
    await this.syncQueue.reconcileCashSaleIncidence(op.operation_id, this.reconciliationNote);
    this.reconcilingOpId.set(null);
    this.reconciliationNote = '';
  }

  public async descartarOperacion(op: PendingOperation): Promise<void> {
    await this.syncQueue.discardOperation(op.operation_id);
  }
}
