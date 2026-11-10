import { Component, OnInit, OnDestroy, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ReservaService, ReservaData } from '../../../services/reserva';
import { AuthService } from '../../../services/auth';
import { ThemeService } from '../../../services/theme';
import { SyncQueueService } from '../../../core/sync/sync-queue.service';

@Component({
  selector: 'app-mis-reservas',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  templateUrl: './mis-reservas.html'
})
export class MisReservasComponent implements OnInit, OnDestroy {
  private reservaService = inject(ReservaService);
  public authService = inject(AuthService);
  public themeService = inject(ThemeService);
  private syncQueue = inject(SyncQueueService);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);
  private syncSub?: Subscription;

  reservas: ReservaData[] = [];
  cargando: boolean = true;
  filtroEstado: string = 'TODOS';

  // Modal de Detalle
  reservaDetalle: ReservaData | null = null;
  mostrarModalDetalle: boolean = false;

  // Modal de Cancelación
  mostrarModalCancelar: boolean = false;
  reservaACancelar: ReservaData | null = null;
  motivoCancelacion: string = '';
  cargandoCancelacion: boolean = false;

  // Feedback Toast
  mensajeToast: { tipo: 'exito' | 'error'; texto: string } | null = null;

  ngOnInit(): void {
    if (!this.authService.estaAutenticado()) {
      this.router.navigate(['/catalogo']);
      return;
    }
    this.cargarReservas();
    this.syncSub = this.syncQueue.syncCompleted$.subscribe((batch) => {
      const syncedReserva = (batch.results || []).find(
        (r) => r.kind === 'RESERVA_SOLICITUD' && r.status === 'synced'
      );
      if (syncedReserva) {
        this.mostrarToast('exito', syncedReserva.message || 'Tu solicitud de reserva offline fue confirmada en línea.');
      }
      this.cargarReservas();
    });
  }

  ngOnDestroy(): void {
    this.syncSub?.unsubscribe();
  }

  cargarReservas(): void {
    this.cargando = true;
    this.cdr.markForCheck();
    this.reservaService.obtenerMisReservas().subscribe({
      next: (res) => {
        this.reservas = res.data || [];
        this.cargando = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.cargando = false;
        this.mostrarToast('error', err?.error?.detail || 'No fue posible cargar tus citas y reservas.');
        this.cdr.markForCheck();
      }
    });
  }

  get reservasFiltradas(): ReservaData[] {
    if (this.filtroEstado === 'TODOS') return this.reservas;
    if (this.filtroEstado === 'PENDIENTE') {
      return this.reservas.filter(
        r =>
          r.estado === 'PENDIENTE' ||
          r.estado === 'SOLICITUD_PENDIENTE_ONLINE' ||
          r.estado === 'EN_CONFLICTO_SYNC'
      );
    }
    return this.reservas.filter(r => r.estado === this.filtroEstado);
  }

  verDetalle(reserva: ReservaData): void {
    this.reservaDetalle = reserva;
    this.mostrarModalDetalle = true;
    this.cdr.markForCheck();
  }

  cerrarDetalle(): void {
    this.mostrarModalDetalle = false;
    this.reservaDetalle = null;
    this.cdr.markForCheck();
  }

  abrirModalCancelar(reserva: ReservaData): void {
    if (reserva.estado !== 'PENDIENTE' && reserva.estado !== 'CONFIRMADA') {
      this.mostrarToast('error', `No se puede cancelar una reserva que ya está ${reserva.estado}.`);
      return;
    }
    this.reservaACancelar = reserva;
    this.motivoCancelacion = '';
    this.mostrarModalCancelar = true;
    this.cdr.markForCheck();
  }

  confirmarCancelacion(): void {
    if (!this.reservaACancelar) return;

    this.cargandoCancelacion = true;
    this.cdr.markForCheck();
    const motivo = this.motivoCancelacion.trim() || 'Cancelación solicitada por el cliente.';

    this.reservaService.cancelarReserva(this.reservaACancelar.id_reserva, motivo).subscribe({
      next: () => {
        this.cargandoCancelacion = false;
        this.mostrarModalCancelar = false;
        this.mostrarToast('exito', `Reserva ${this.reservaACancelar?.codigo_reserva} cancelada. El inventario ha sido restituido.`);
        this.reservaACancelar = null;
        this.cargarReservas();
      },
      error: (err) => {
        this.cargandoCancelacion = false;
        this.mostrarToast('error', err?.error?.detail || 'Error al cancelar la reserva.');
        this.cdr.markForCheck();
      }
    });
  }

  mostrarToast(tipo: 'exito' | 'error', texto: string): void {
    this.mensajeToast = { tipo, texto };
    this.cdr.markForCheck();
    setTimeout(() => {
      this.mensajeToast = null;
      this.cdr.markForCheck();
    }, 4500);
  }

  obtenerClaseEstado(estado: string): string {
    switch (estado) {
      case 'SOLICITUD_PENDIENTE_ONLINE':
        return 'bg-sky-500/15 text-sky-400 border-sky-500/30';
      case 'EN_CONFLICTO_SYNC':
        return 'bg-rose-500/15 text-rose-400 border-rose-500/30';
      case 'PENDIENTE':
        return 'bg-amber-500/15 text-amber-500 border-amber-500/30';
      case 'CONFIRMADA':
        return 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30';
      case 'ATENDIDA':
        return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
      case 'CANCELADA':
        return 'bg-rose-500/15 text-rose-400 border-rose-500/30';
      case 'VENCIDA':
        return 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30';
      default:
        return 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30';
    }
  }

  obtenerIconoEstado(estado: string): string {
    switch (estado) {
      case 'SOLICITUD_PENDIENTE_ONLINE':
        return 'ph-cloud-arrow-up';
      case 'EN_CONFLICTO_SYNC':
        return 'ph-warning-octagon';
      case 'PENDIENTE':
        return 'ph-clock';
      case 'CONFIRMADA':
        return 'ph-check-circle';
      case 'ATENDIDA':
        return 'ph-sparkle';
      case 'CANCELADA':
        return 'ph-x-circle';
      case 'VENCIDA':
        return 'ph-hourglass-low';
      default:
        return 'ph-circle';
    }
  }
}
