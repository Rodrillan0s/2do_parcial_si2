import { Component, OnInit, inject, ChangeDetectorRef, NgZone, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AuthService } from '../../services/auth';
import { Empresa, EmpresaService } from '../../services/empresa';
import {
  SaasService,
  PlanVigenciaData,
  SuscripcionItem,
  CodigoPlan,
  SolicitudContratacion,
  OpcionesCancelacionSuscripcion,
  AsignarSuscripcionPayload,
  CancelarSuscripcionPayload
} from '../../services/saas';
import { extraerMensajeError } from '../../utils/error-helper';

@Component({
  selector: 'app-suscripciones',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './suscripciones.html'
})
export class SuscripcionesComponent implements OnInit {
  private saasService = inject(SaasService);
  private empresaService = inject(EmpresaService);
  public authService = inject(AuthService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);
  private ngZone = inject(NgZone);
  private destroyRef = inject(DestroyRef);

  // Estado de empresa
  empresas: Empresa[] = [];
  empresaSeleccionadaId: number | null = null;
  empresaActual: Empresa | null = null;

  // Datos de vigencia y plan actual
  planVigencia: PlanVigenciaData | null = null;
  historial: SuscripcionItem[] = [];

  // Estados UI
  cargandoPlan: boolean = false;
  cargandoHistorial: boolean = false;
  guardando: boolean = false;
  mensajeError: string = '';
  mensajeExito: string = '';
  errorHistorial: string = '';
  private solicitudPlan = 0;
  private solicitudHistorial = 0;
  private inicioRenovacionExacto: string | null = null;
  private inicioRenovacionInput = '';

  // Modal Asignar / Renovar Suscripción (SuperAdmin)
  mostrarModalAsignar: boolean = false;
  modalError: string = '';
  formPlan: CodigoPlan = 'BASICO';
  formInicio: string = '';
  formFin: string = '';
  formMotivo: string = '';

  // Modal Cancelar Suscripción (SuperAdmin)
  mostrarModalCancelar: boolean = false;
  suscripcionACancelar: SuscripcionItem | null = null;
  formCancelarMotivo: string = '';
  formCancelarConfirmar: boolean = false;

  // Modal Autoservicio: Renovación / Cambio de Plan / Pago Pendiente
  mostrarModalCambiarPlan: boolean = false;
  modalCambioPaso: 'PLAN' | 'PAGO' = 'PLAN';
  planElegido: CodigoPlan = 'PROFESIONAL';
  periodicidadElegida: 'MENSUAL' | 'ANUAL' = 'MENSUAL';
  momentoCambioElegido: 'SIGUIENTE_CICLO' | 'INMEDIATO' = 'SIGUIENTE_CICLO';
  metodoPagoElegido: 'PAYPAL' | 'QR_TRANSFERENCIA' = 'PAYPAL';
  solicitudCreada: SolicitudContratacion | null = null;
  procesandoSolicitud: boolean = false;
  errorModalCambio: string = '';
  exitoModalCambio: string = '';
  paypalOrderIdCreado: string = '';
  paypalApproveUrl: string = '';
  paypalEsperandoAprobacion: boolean = false;
  verificandoPagoPayPalAuto: boolean = false;
  subiendoComprobante: boolean = false;
  comprobanteUrl: string = '';
  referenciaPagoQr: string = '';

  // Modal Cancelación Comercial (Propietario Tienda)
  mostrarModalCancelarComercial: boolean = false;
  opcionesCancelacion: OpcionesCancelacionSuscripcion | null = null;
  cargandoOpcionesCancelacion: boolean = false;
  tipoCancelacionElegida: 'FIN_DE_CICLO' | 'REEMBOLSO_INMEDIATO' = 'FIN_DE_CICLO';
  motivoCancelacionComercial: string = '';
  confirmarCancelacionComercial: boolean = false;
  procesandoCancelacionComercial: boolean = false;
  errorModalCancelarComercial: string = '';

  get isGlobalAdmin(): boolean {
    return this.authService.isGlobalAdmin();
  }

  get puedeGestionar(): boolean {
    return this.isGlobalAdmin && this.authService.hasPermission('suscripciones.gestionar');
  }

  get porcentajeUsoSucursales(): number {
    const limite = this.planVigencia?.limites?.sucursales_activas;
    if (!limite || limite <= 0) return 0;
    const uso = this.planVigencia?.uso?.sucursales_activas || 0;
    return Math.min(100, Math.round((uso / limite) * 100));
  }

  ngOnInit() {
    // Si es admin global, cargar listado de empresas en paralelo con la empresa activa si ya se conoce
    if (this.isGlobalAdmin) {
      const paramEmpresa = Number(this.route.snapshot.queryParams['empresa'] || 0);
      const effEmpresa = this.authService.getEffectiveCompanyId() || 1;
      this.empresaSeleccionadaId = paramEmpresa > 0 ? paramEmpresa : effEmpresa;
      this.cargarDatosEmpresa();
      this.cargarEmpresas();
    } else {
      // Empresa directa desde sesión
      const user = this.authService.obtenerUsuario();
      this.empresaSeleccionadaId = user?.id_empresa || null;
      this.cargarDatosEmpresa();
    }

    // Detección automática de retorno desde PayPal
    const qp = this.route.snapshot.queryParams;
    const paypalEstado = qp['paypal'];
    const codigoContratacion = qp['codigo'];
    const tokenPayPal = qp['token'] || qp['order_id'];

    if (paypalEstado === 'success' && codigoContratacion) {
      this.verificarCapturaAutomaticaAlRegresar(codigoContratacion, tokenPayPal);
    } else if (paypalEstado === 'cancel') {
      this.mensajeError = 'La operación de pago en PayPal fue cancelada. Puedes intentar nuevamente cuando lo desees.';
      this.router.navigate([], { replaceUrl: true, queryParams: {} });
    }
  }

  trackBySuscripcionId(index: number, item: SuscripcionItem): number {
    return item.id_suscripcion || index;
  }

  cargarEmpresas() {
    const empresaPrevia = this.empresaSeleccionadaId;
    this.empresaService.listarEmpresas()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            if (res && res.data) {
              this.empresas = res.data;

              // Revisar si viene ?empresa=ID en queryParams
              const paramEmpresa = this.route.snapshot.queryParams['empresa'];
              if (paramEmpresa) {
                const id = Number(paramEmpresa);
                if (this.empresas.some(e => e.id_empresa === id)) {
                  this.empresaSeleccionadaId = id;
                }
              }

              // Si la empresa seleccionada no existe en el listado, tomar la del usuario o la primera
              if (!this.empresaSeleccionadaId || !this.empresas.some(e => e.id_empresa === this.empresaSeleccionadaId)) {
                const user = this.authService.obtenerUsuario();
                if (user?.id_empresa && this.empresas.some(e => e.id_empresa === user.id_empresa)) {
                  this.empresaSeleccionadaId = user.id_empresa;
                } else if (this.empresas.length > 0) {
                  this.empresaSeleccionadaId = this.empresas[0].id_empresa || null;
                }
              }

              this.actualizarEmpresaActual();
              if (this.empresaSeleccionadaId !== empresaPrevia) {
                this.cargarDatosEmpresa();
              } else {
                this.cdr.detectChanges();
              }
            }
          });
        },
        error: (err) => {
          this.mensajeError = extraerMensajeError(err, 'No fue posible cargar el listado de empresas.');
          this.cdr.markForCheck();
        }
      });
  }

  onSeleccionarEmpresa() {
    this.actualizarEmpresaActual();
    this.cargarDatosEmpresa();
  }

  private actualizarEmpresaActual() {
    if (this.empresaSeleccionadaId && this.empresas.length > 0) {
      this.empresaActual = this.empresas.find(e => e.id_empresa === this.empresaSeleccionadaId) || null;
    } else {
      this.empresaActual = null;
    }
  }

  cargarDatosEmpresa() {
    this.mensajeError = '';
    this.errorHistorial = '';
    this.planVigencia = null;
    this.historial = [];
    this.solicitudPlan++;
    this.solicitudHistorial++;
    this.cargandoPlan = false;
    this.cargandoHistorial = false;
    if (this.isGlobalAdmin && !this.empresaSeleccionadaId) return;
    this.cargarVigenciaPlan();
    if (this.empresaSeleccionadaId) {
      this.cargarHistorial(this.empresaSeleccionadaId);
    }
  }

  cargarVigenciaPlan() {
    const solicitud = ++this.solicitudPlan;
    this.cargandoPlan = true;
    const targetEmpresa = this.isGlobalAdmin ? (this.empresaSeleccionadaId || undefined) : undefined;

    this.saasService.consultarPlan(targetEmpresa)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          if (solicitud !== this.solicitudPlan) return;
          this.ngZone.run(() => {
            if (res && res.data) {
              this.planVigencia = res.data;
              if (!this.empresaSeleccionadaId && res.data.id_empresa) {
                this.empresaSeleccionadaId = res.data.id_empresa;
              }

              const qp = this.route.snapshot.queryParams;
              if (qp['pagoPendiente'] && this.planVigencia?.solicitud_contratacion?.estado_contratacion === 'PENDIENTE_PAGO') {
                this.abrirPagoPendiente();
              } else if (qp['cambiarPlan']) {
                this.abrirModalCambiarPlan(qp['cambiarPlan'] as CodigoPlan);
              }
            }
            this.cargandoPlan = false;
            this.cdr.detectChanges();
          });
        },
        error: (err) => {
          if (solicitud !== this.solicitudPlan) return;
          this.ngZone.run(() => {
            this.mensajeError = extraerMensajeError(err, 'No se pudo obtener el estado de suscripción de la empresa.');
            this.planVigencia = null;
            this.cargandoPlan = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  cargarHistorial(idEmpresa: number) {
    const solicitud = ++this.solicitudHistorial;
    this.cargandoHistorial = true;

    this.saasService.obtenerHistorialSuscripciones(idEmpresa)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          if (solicitud !== this.solicitudHistorial) return;
          this.ngZone.run(() => {
            if (res && res.data) {
              this.historial = res.data;
            } else {
              this.historial = [];
            }
            this.cargandoHistorial = false;
            this.cdr.detectChanges();
          });
        },
        error: (err) => {
          if (solicitud !== this.solicitudHistorial) return;
          this.ngZone.run(() => {
            // Un 503 por MIGRACION_PENDIENTE o error de consulta
            const msg = extraerMensajeError(err, 'Error al obtener el historial de suscripciones.');
            this.errorHistorial = msg;
            this.historial = [];
            this.cargandoHistorial = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  // --- MODAL ASIGNAR / RENOVAR ---

  abrirModalAsignar() {
    if (!this.puedeGestionar || !this.empresaSeleccionadaId) return;

    this.modalError = '';
    this.formPlan = 'BASICO';
    this.inicioRenovacionExacto = null;
    this.inicioRenovacionInput = '';

    // Establecer fechas predeterminadas
    const ahora = new Date();
    // Si la empresa ya tiene fin vigente, sugerir renovación contigua
    if (this.planVigencia && this.planVigencia.fin) {
      const fechaFinActual = new Date(this.planVigencia.fin);
      if (fechaFinActual > ahora) {
        this.formInicio = this.formatearFechaLocalInput(fechaFinActual);
        this.inicioRenovacionExacto = this.planVigencia.fin;
        this.inicioRenovacionInput = this.formInicio;
        const unMesDespues = new Date(fechaFinActual);
        unMesDespues.setMonth(unMesDespues.getMonth() + 1);
        this.formFin = this.formatearFechaLocalInput(unMesDespues);
        this.formMotivo = 'Renovación administrativa contigua';
        this.formPlan = this.planVigencia.codigo_plan || 'BASICO';
        this.mostrarModalAsignar = true;
        return;
      }
    }

    this.formInicio = this.formatearFechaLocalInput(ahora);
    const unMesDespues = new Date(ahora);
    unMesDespues.setMonth(unMesDespues.getMonth() + 1);
    this.formFin = this.formatearFechaLocalInput(unMesDespues);
    this.formMotivo = 'Asignación de periodo administrativo';
    this.mostrarModalAsignar = true;
  }

  cerrarModalAsignar() {
    this.mostrarModalAsignar = false;
    this.modalError = '';
    this.guardando = false;
  }

  guardarSuscripcion() {
    if (!this.empresaSeleccionadaId || !this.puedeGestionar) return;

    if (!this.formPlan) {
      this.modalError = 'Debe seleccionar un plan.';
      return;
    }

    if (!this.formInicio || !this.formFin) {
      this.modalError = 'Las fechas de inicio y fin son obligatorias.';
      return;
    }

    const dInicio = new Date(this.formInicio);
    const dFin = new Date(this.formFin);

    if (isNaN(dInicio.getTime()) || isNaN(dFin.getTime())) {
      this.modalError = 'Formato de fechas inválido.';
      return;
    }

    if (dFin <= dInicio) {
      this.modalError = 'La fecha de fin debe ser posterior a la fecha de inicio.';
      return;
    }

    if (!this.formMotivo || this.formMotivo.trim().length < 3) {
      this.modalError = 'Debe especificar un motivo válido de al menos 3 caracteres.';
      return;
    }

    // Advertencia informativa de capacidad de sucursales
    if (this.formPlan === 'BASICO' && this.planVigencia?.uso?.sucursales_activas && this.planVigencia.uso.sucursales_activas > 2) {
      this.modalError = `La empresa cuenta actualmente con ${this.planVigencia.uso.sucursales_activas} sucursales activas. El plan BASICO admite un máximo de 2. Asigne PROFESIONAL o resuelva las sucursales antes de continuar.`;
      return;
    }

    this.guardando = true;
    this.modalError = '';

    const payload: AsignarSuscripcionPayload = {
      codigo_plan: this.formPlan,
      inicio: this.inicioRenovacionExacto && this.formInicio === this.inicioRenovacionInput
        ? this.inicioRenovacionExacto : dInicio.toISOString(),
      fin: dFin.toISOString(),
      motivo: this.formMotivo.trim()
    };

    this.saasService.asignarSuscripcion(this.empresaSeleccionadaId, payload)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.cerrarModalAsignar();
            this.mostrarNotificacionExito(`¡Suscripción al plan '${res.data.codigo_plan}' registrada exitosamente!`);
            this.cargarDatosEmpresa();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.modalError = extraerMensajeError(err, 'Error al registrar la suscripción.');
            this.cdr.detectChanges();
          });
        }
      });
  }

  // --- MODAL CANCELAR ---

  abrirModalCancelar(item: SuscripcionItem) {
    if (!this.puedeGestionar) return;
    this.suscripcionACancelar = item;
    this.formCancelarMotivo = '';
    this.formCancelarConfirmar = false;
    this.modalError = '';
    this.mostrarModalCancelar = true;
  }

  cerrarModalCancelar() {
    this.mostrarModalCancelar = false;
    this.suscripcionACancelar = null;
    this.modalError = '';
    this.guardando = false;
  }

  confirmarCancelacion() {
    if (!this.suscripcionACancelar || !this.empresaSeleccionadaId || !this.puedeGestionar) return;

    if (!this.formCancelarMotivo || this.formCancelarMotivo.trim().length < 3) {
      this.modalError = 'Debe indicar un motivo de cancelación de al menos 3 caracteres.';
      return;
    }

    if (!this.formCancelarConfirmar) {
      this.modalError = 'Debe marcar la casilla de confirmación explícita para proceder.';
      return;
    }

    this.guardando = true;
    this.modalError = '';

    const payload: CancelarSuscripcionPayload = {
      motivo: this.formCancelarMotivo.trim(),
      confirmar: true
    };

    this.saasService.cancelarSuscripcion(
      this.empresaSeleccionadaId,
      this.suscripcionACancelar.id_suscripcion,
      payload
    )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.cerrarModalCancelar();
            this.mostrarNotificacionExito('Suscripción cancelada correctamente en el historial.');
            this.cargarDatosEmpresa();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.modalError = extraerMensajeError(err, 'Error al cancelar la suscripción.');
            this.cdr.detectChanges();
          });
        }
      });
  }

  // --- HELPERS DE FORMATEO Y ESTÉTICA ---

  estadoPeriodo(item: SuscripcionItem): string {
    if (item.estado === 'CANCELADA') return 'CANCELADA';
    const ahora = Date.now();
    if (new Date(item.inicio).getTime() > ahora) return 'PROGRAMADA';
    return new Date(item.fin).getTime() > ahora ? 'VIGENTE' : 'VENCIDA';
  }

  puedeCancelar(item: SuscripcionItem): boolean {
    return this.puedeGestionar && item.estado === 'ACTIVA';
  }

  private formatearFechaLocalInput(d: Date): string {
    const pad = (n: number) => n < 10 ? '0' + n : n;
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  formatearFechaDisplay(fechaStr: string | null | undefined): string {
    if (!fechaStr) return '—';
    try {
      const d = new Date(fechaStr);
      return d.toLocaleString('es-BO', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return fechaStr;
    }
  }

  obtenerBadgeEstadoClass(estado: string | undefined): string {
    const est = (estado || '').toUpperCase();
    if (est === 'VIGENTE') {
      return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800';
    }
    if (est === 'PROGRAMADA' || est === 'PENDIENTE_ACTIVACION') {
      return 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400 border border-amber-200 dark:border-amber-800';
    }
    if (est === 'VENCIDA' || est === 'EMPRESA_INACTIVA') {
      return 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-400 border border-rose-200 dark:border-rose-800';
    }
    if (est === 'CANCELADA') {
      return 'bg-stone-100 text-zinc-600 dark:bg-slate-900 dark:text-slate-400 border border-stone-200 dark:border-slate-800';
    }
    return 'bg-zinc-100 text-zinc-700 dark:bg-slate-900 dark:text-slate-300 border border-zinc-200 dark:border-slate-800';
  }

  mostrarNotificacionExito(msg: string) {
    this.mensajeExito = msg;
    setTimeout(() => {
      this.mensajeExito = '';
      this.cdr.detectChanges();
    }, 4500);
  }

  // --- MÉTODOS DE AUTOSERVICIO SAAS (RENOVAR, CAMBIAR PLAN, TERMINAR PAGO) ---

  abrirModalRenovar(): void {
    this.planElegido = this.planVigencia?.codigo_plan || 'BASICO';
    this.periodicidadElegida = 'MENSUAL';
    this.modalCambioPaso = 'PLAN';
    this.errorModalCambio = '';
    this.exitoModalCambio = '';
    this.solicitudCreada = null;
    this.mostrarModalCambiarPlan = true;
  }

  abrirModalCambiarPlan(planObjetivo?: CodigoPlan): void {
    if (planObjetivo && (planObjetivo === 'BASICO' || planObjetivo === 'PROFESIONAL')) {
      this.planElegido = planObjetivo;
    } else {
      this.planElegido = this.planVigencia?.codigo_plan === 'BASICO' ? 'PROFESIONAL' : 'BASICO';
    }
    this.periodicidadElegida = 'MENSUAL';
    this.modalCambioPaso = 'PLAN';
    this.errorModalCambio = '';
    this.exitoModalCambio = '';
    this.solicitudCreada = null;
    this.mostrarModalCambiarPlan = true;
  }

  abrirPagoPendiente(): void {
    const sol = this.planVigencia?.solicitud_contratacion;
    if (sol) {
      this.solicitudCreada = sol;
      this.planElegido = sol.codigo_plan;
      this.periodicidadElegida = sol.periodicidad;
      this.modalCambioPaso = 'PAGO';
      this.errorModalCambio = '';
      this.exitoModalCambio = '';
      this.paypalOrderIdCreado = sol.paypal_order_id || '';
      this.mostrarModalCambiarPlan = true;
    }
  }

  cerrarModalCambiarPlan(): void {
    this.mostrarModalCambiarPlan = false;
    this.solicitudCreada = null;
    this.errorModalCambio = '';
    this.exitoModalCambio = '';
    this.procesandoSolicitud = false;
  }

  calcularMonto(codigo: CodigoPlan, periodicidad: 'MENSUAL' | 'ANUAL'): number {
    if (codigo === 'BASICO') {
      return periodicidad === 'ANUAL' ? 1990 : 199;
    }
    return periodicidad === 'ANUAL' ? 3990 : 399;
  }

  excedeSucursalesParaBasico(): boolean {
    const uso = this.planVigencia?.uso?.sucursales_activas || 0;
    return this.planElegido === 'BASICO' && uso > 2;
  }

  verificarCapturaAutomaticaAlRegresar(codigo: string, token?: string): void {
    this.verificandoPagoPayPalAuto = true;
    this.mensajeError = '';
    this.mensajeExito = '';
    const orderId = token || '';
    this.saasService.capturarOrdenPayPalContratacion(codigo, orderId).subscribe({
      next: () => {
        this.verificandoPagoPayPalAuto = false;
        this.mensajeExito = '¡Pago verificado y aprobado por PayPal! Tu suscripción y límites han sido activados exitosamente.';
        this.saasService.invalidarCachePlan(this.empresaSeleccionadaId || undefined);
        this.cargarDatosEmpresa();
        this.router.navigate([], { replaceUrl: true, queryParams: {} });
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.verificandoPagoPayPalAuto = false;
        this.mensajeError = extraerMensajeError(err, 'PayPal aún no reporta la orden como completada o se encuentra en proceso.');
        this.cdr.detectChanges();
      }
    });
  }

  continuarAlPago(): void {
    this.errorModalCambio = '';
    if (this.excedeSucursalesParaBasico()) {
      this.errorModalCambio = `Tu empresa tiene ${this.planVigencia?.uso?.sucursales_activas} sucursales activas. El plan Básico admite un máximo de 2. Desactiva sucursales antes de solicitar este cambio.`;
      return;
    }

    this.procesandoSolicitud = true;
    const esMismoPlan = this.planVigencia?.codigo_plan === this.planElegido;
    const motivo = esMismoPlan
      ? `Renovación de suscripción al plan ${this.planElegido}`
      : `Cambio de plan a ${this.planElegido} (${this.momentoCambioElegido})`;

    this.saasService.solicitarRenovacionOCambioPlan({
      codigo_plan: this.planElegido,
      periodicidad: this.periodicidadElegida,
      momento_cambio: this.momentoCambioElegido,
      motivo
    }, this.empresaSeleccionadaId || undefined).subscribe({
      next: (res) => {
        this.procesandoSolicitud = false;
        this.solicitudCreada = res.data;
        this.modalCambioPaso = 'PAGO';
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.procesandoSolicitud = false;
        this.errorModalCambio = extraerMensajeError(err, 'No fue posible registrar la solicitud de contratación.');
        this.cdr.detectChanges();
      }
    });
  }

  iniciarPagoPayPalModal(): void {
    if (!this.solicitudCreada) return;
    this.procesandoSolicitud = true;
    this.errorModalCambio = '';
    this.exitoModalCambio = '';
    const retorno = typeof window !== 'undefined'
      ? `${window.location.origin}/admin/suscripciones`
      : undefined;

    this.saasService.crearOrdenPayPalContratacion(
      this.solicitudCreada.codigo_seguimiento,
      'admin',
      retorno
    ).subscribe({
      next: (res) => {
        this.procesandoSolicitud = false;
        this.paypalOrderIdCreado = res.data.paypal_order_id;
        this.paypalApproveUrl = res.data.approve_url || '';
        this.paypalEsperandoAprobacion = true;
        this.errorModalCambio = '';
        if (this.paypalApproveUrl && typeof window !== 'undefined') {
          window.open(this.paypalApproveUrl, '_blank', 'noopener,noreferrer');
        }
        this.exitoModalCambio = 'Orden generada en PayPal. Completa la autorización y luego pulsa "Verificar y Confirmar Pago".';
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.procesandoSolicitud = false;
        this.exitoModalCambio = '';
        this.errorModalCambio = extraerMensajeError(err, 'No se pudo generar la orden de PayPal.');
        this.cdr.detectChanges();
      }
    });
  }

  confirmarCapturaPayPalModal(): void {
    if (!this.solicitudCreada) return;
    const orderId = this.paypalOrderIdCreado || this.solicitudCreada.paypal_order_id || '';
    this.procesandoSolicitud = true;
    this.errorModalCambio = '';
    this.exitoModalCambio = '';
    this.saasService.capturarOrdenPayPalContratacion(this.solicitudCreada.codigo_seguimiento, orderId).subscribe({
      next: () => {
        this.procesandoSolicitud = false;
        this.paypalEsperandoAprobacion = false;
        this.errorModalCambio = '';
        this.exitoModalCambio = '¡Pago confirmado exitosamente! Tu plan ha sido activado.';
        this.saasService.invalidarCachePlan(this.empresaSeleccionadaId || undefined);
        this.cargarDatosEmpresa();
        this.cdr.detectChanges();
        setTimeout(() => this.cerrarModalCambiarPlan(), 2000);
      },
      error: (err) => {
        this.procesandoSolicitud = false;
        this.exitoModalCambio = '';
        this.errorModalCambio = extraerMensajeError(err, 'PayPal aún no reporta la orden como aprobada. Asegúrate de autorizar la transacción en PayPal y reintenta.');
        this.cdr.detectChanges();
      }
    });
  }

  onSubirComprobanteModal(event: any): void {
    const file = event?.target?.files?.[0];
    if (!file || !this.solicitudCreada) return;
    this.subiendoComprobante = true;
    this.errorModalCambio = '';
    this.exitoModalCambio = '';
    const ref = this.referenciaPagoQr || 'TRANSFERENCIA-BANCARIA';
    this.saasService.subirComprobanteContratacion(this.solicitudCreada.codigo_seguimiento, file, ref).subscribe({
      next: (res: { success: boolean; data: any }) => {
        this.subiendoComprobante = false;
        this.comprobanteUrl = res.data?.comprobante_url || '';
        this.errorModalCambio = '';
        this.exitoModalCambio = 'Comprobante recibido. Tu pago será verificado por el personal de AuroraStore a la brevedad.';
        this.saasService.invalidarCachePlan(this.empresaSeleccionadaId || undefined);
        this.cargarDatosEmpresa();
        this.cdr.detectChanges();
        setTimeout(() => this.cerrarModalCambiarPlan(), 2500);
      },
      error: (errSubir: any) => {
        this.subiendoComprobante = false;
        this.exitoModalCambio = '';
        this.errorModalCambio = extraerMensajeError(errSubir, 'Error al subir la imagen del comprobante.');
        this.cdr.detectChanges();
      }
    });
  }

  // Métodos de Cancelación Comercial (Propietario de Tienda)
  abrirModalCancelarComercial(): void {
    this.errorModalCancelarComercial = '';
    this.confirmarCancelacionComercial = false;
    this.motivoCancelacionComercial = '';
    this.tipoCancelacionElegida = 'FIN_DE_CICLO';
    this.cargandoOpcionesCancelacion = true;
    this.mostrarModalCancelarComercial = true;

    this.saasService.obtenerOpcionesCancelacion(this.empresaSeleccionadaId || undefined).subscribe({
      next: (res) => {
        this.cargandoOpcionesCancelacion = false;
        this.opcionesCancelacion = res.data;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.cargandoOpcionesCancelacion = false;
        this.errorModalCancelarComercial = extraerMensajeError(err, 'No fue posible consultar las opciones de cancelación.');
        this.cdr.detectChanges();
      }
    });
  }

  cerrarModalCancelarComercial(): void {
    this.mostrarModalCancelarComercial = false;
    this.opcionesCancelacion = null;
    this.errorModalCancelarComercial = '';
    this.procesandoCancelacionComercial = false;
  }

  confirmarCancelarComercial(): void {
    if (!this.confirmarCancelacionComercial) {
      this.errorModalCancelarComercial = 'Debes confirmar que comprendes los términos de la cancelación.';
      return;
    }
    this.procesandoCancelacionComercial = true;
    this.errorModalCancelarComercial = '';

    this.saasService.cancelarSuscripcionComercial({
      tipo_cancelacion: this.tipoCancelacionElegida,
      motivo: this.motivoCancelacionComercial || 'Cancelación gestionada por el propietario'
    }, this.empresaSeleccionadaId || undefined).subscribe({
      next: (res) => {
        this.procesandoCancelacionComercial = false;
        this.mensajeExito = res.data.mensaje;
        this.cerrarModalCancelarComercial();
        this.saasService.invalidarCachePlan(this.empresaSeleccionadaId || undefined);
        this.cargarDatosEmpresa();
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.procesandoCancelacionComercial = false;
        this.errorModalCancelarComercial = extraerMensajeError(err, 'No fue posible procesar la cancelación.');
        this.cdr.detectChanges();
      }
    });
  }
}
