import { Component, OnInit, inject, ChangeDetectorRef, NgZone, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AuthService } from '../../services/auth';
import { SaasService, PlanSaaS, SolicitudContratacion } from '../../services/saas';
import { extraerMensajeError } from '../../utils/error-helper';

@Component({
  selector: 'app-planes',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './planes.html'
})
export class PlanesComponent implements OnInit {
  private saasService = inject(SaasService);
  public authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  private ngZone = inject(NgZone);
  private destroyRef = inject(DestroyRef);

  planes: PlanSaaS[] = [];
  cargando: boolean = false;
  guardando: boolean = false;
  mensajeError: string = '';
  mensajeModalError: string = '';
  mensajeExito: string = '';

  // Modal para editar plan
  mostrarModal: boolean = false;
  planEnEdicion: PlanSaaS | null = null;
  formNombre: string = '';
  formActivo: boolean = true;
  formPrecioMensual: number = 0;
  formPrecioAnual: number = 0;
  formDescripcion: string = '';

  // Contrataciones autónomas SaaS
  contrataciones: SolicitudContratacion[] = [];
  cargandoContrataciones: boolean = false;
  filtroEstadoContratacion: string = '';
  solicitudEnRevision: SolicitudContratacion | null = null;
  notasRevision: string = '';
  resolviendoSolicitud: boolean = false;

  get puedeGestionar(): boolean {
    return this.authService.isGlobalAdmin() && this.authService.hasPermission('planes.gestionar');
  }

  get puedeGestionarContrataciones(): boolean {
    return this.authService.isGlobalAdmin() && (
      this.authService.hasPermission('contrataciones.gestionar') ||
      this.authService.hasPermission('suscripciones.gestionar')
    );
  }

  get pendientesCount(): number {
    return this.contrataciones.filter(c => c.estado_contratacion === 'PENDIENTE_VERIFICACION_PAGO').length;
  }

  ngOnInit() {
    this.cargarPlanes();
    if (this.puedeGestionarContrataciones) {
      this.cargarContrataciones();
    }
  }

  cargarPlanes() {
    this.cargando = true;
    this.mensajeError = '';

    this.saasService.listarPlanes()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            if (res && res.data) {
              this.planes = res.data;
            }
            this.cargando = false;
            this.cdr.detectChanges();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.mensajeError = extraerMensajeError(err, 'No fue posible cargar el catálogo de planes.');
            this.cargando = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  cargarContrataciones() {
    if (!this.puedeGestionarContrataciones) return;
    this.cargandoContrataciones = true;
    this.saasService.listarContrataciones(this.filtroEstadoContratacion || undefined)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.contrataciones = res?.data || [];
            this.cargandoContrataciones = false;
            this.cdr.detectChanges();
          });
        },
        error: () => {
          this.ngZone.run(() => {
            this.cargandoContrataciones = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  abrirModalEditar(plan: PlanSaaS) {
    if (!this.puedeGestionar) return;
    this.planEnEdicion = plan;
    this.formNombre = plan.nombre;
    this.formActivo = plan.activo;
    this.formPrecioMensual = Number(plan.precio_mensual || 0);
    this.formPrecioAnual = Number(plan.precio_anual || 0);
    this.formDescripcion = plan.descripcion || '';
    this.mensajeModalError = '';
    this.mostrarModal = true;
  }

  cerrarModal() {
    this.mostrarModal = false;
    this.planEnEdicion = null;
    this.mensajeModalError = '';
    this.guardando = false;
  }

  guardarPlan() {
    if (!this.planEnEdicion || !this.puedeGestionar) return;

    if (!this.formNombre || !this.formNombre.trim()) {
      this.mensajeModalError = 'El nombre comercial del plan es requerido.';
      return;
    }

    this.guardando = true;
    this.mensajeModalError = '';

    const codigo = this.planEnEdicion.codigo;
    const payload = {
      nombre: this.formNombre.trim(),
      activo: this.formActivo,
      precio_mensual: Number(this.formPrecioMensual || 0),
      precio_anual: Number(this.formPrecioAnual || 0),
      descripcion: this.formDescripcion.trim()
    };

    this.saasService.actualizarPlan(codigo, payload)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.cerrarModal();
            this.mostrarNotificacionExito(`Plan '${res.data.nombre}' actualizado correctamente.`);
            this.cargarPlanes();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.mensajeModalError = extraerMensajeError(err, 'Error al actualizar el plan.');
            this.cdr.detectChanges();
          });
        }
      });
  }

  abrirRevisionSolicitud(sol: SolicitudContratacion) {
    this.solicitudEnRevision = sol;
    this.notasRevision = sol.observaciones_revision || '';
  }

  cerrarRevisionSolicitud() {
    this.solicitudEnRevision = null;
    this.notasRevision = '';
    this.resolviendoSolicitud = false;
  }

  resolverContratacion(accion: 'APROBAR' | 'RECHAZAR') {
    if (!this.solicitudEnRevision || this.resolviendoSolicitud) return;
    this.resolviendoSolicitud = true;

    this.saasService.resolverContratacion(
      this.solicitudEnRevision.id_solicitud,
      accion,
      this.notasRevision.trim()
    )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.ngZone.run(() => {
            this.resolviendoSolicitud = false;
            this.cerrarRevisionSolicitud();
            this.mostrarNotificacionExito(
              accion === 'APROBAR'
                ? 'Contratación aprobada: empresa y suscripción activadas.'
                : 'Comprobante observado/rechazado.'
            );
            this.cargarContrataciones();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.resolviendoSolicitud = false;
            this.mensajeError = extraerMensajeError(err, 'No se pudo procesar la solicitud.');
            this.cdr.detectChanges();
          });
        }
      });
  }

  mostrarNotificacionExito(msg: string) {
    this.mensajeExito = msg;
    setTimeout(() => {
      this.mensajeExito = '';
      this.cdr.detectChanges();
    }, 4500);
  }
}
