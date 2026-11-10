import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from '../../services/auth';
import { AtenderReservaService, ReservaItem, PrendaReserva, CobroReservaPayload } from '../../services/atender-reserva';
import { CajaService } from '../../services/caja';

@Component({
  selector: 'app-atender-reserva',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule
  ],
  templateUrl: './atender-reserva.html',
  styleUrls: ['./atender-reserva.css']
})
export class AtenderReservaComponent implements OnInit {

  private authService = inject(AuthService);
  private atenderReservaService = inject(AtenderReservaService);
  private cajaService = inject(CajaService);
  private router = inject(Router);

  // --- Estado general ---
  reservas: ReservaItem[] = [];
  reservaSeleccionada: ReservaItem | null = null;

  sucursalActiva: any = null;
  empresaActiva: any = null;

  cargando = false;
  procesando = false;
  descargandoPdf = false;

  mensaje = '';
  error = '';

  // --- Filtros y búsqueda rápida ---
  busqueda = '';
  filtroEstado = '';

  // --- Estado de la Caja Registradora ---
  cajaAbierta = false;
  cajaInfo: any = null;
  cargandoCaja = false;

  // --- Modal de Cobro POS Autónomo ---
  mostrarModalCobro = false;
  metodoPagoSeleccionado: number = 3; // 3: Efectivo, 1: Tarjeta, 4: QR
  montoRecibido: number = 0;
  cambio: number = 0;
  referenciaTransaccion = '';
  descuento: number = 0;
  observacionCobro = '';

  datosFacturacion = {
    nit_ci: '',
    razon_social: '',
    correo_facturacion: '',
    tipo_documento: 'COMPROBANTE'
  };

  // --- Modal de Éxito / Comprobante ---
  mostrarModalExito = false;
  resultadoExito: any = null;

  ngOnInit(): void {
    this.sucursalActiva = this.authService.activeBranch();
    this.empresaActiva = this.authService.selectedCompany();

    this.verificarEstadoCaja();

    if (this.sucursalActiva?.id) {
      this.cargarReservas();
    }

    this.authService.branchChanged$.subscribe(sucursal => {
      this.sucursalActiva = sucursal;
      this.reservas = [];
      this.reservaSeleccionada = null;
      this.verificarEstadoCaja();

      if (sucursal?.id) {
        this.cargarReservas();
      }
    });

    this.authService.companyChanged$.subscribe((empresa: any) => {
      this.empresaActiva = empresa;
      this.reservas = [];
      this.reservaSeleccionada = null;
      this.verificarEstadoCaja();
      if (this.sucursalActiva?.id) {
        this.cargarReservas();
      }
    });
  }

  // --- Verificación de Caja Registradora ---
  verificarEstadoCaja(): void {
    this.cargandoCaja = true;
    const idEmpresa = this.empresaActiva?.id_empresa || this.empresaActiva?.id;
    this.cajaService.obtenerEstadoCaja(this.sucursalActiva?.id, idEmpresa).subscribe({
      next: (resp) => {
        this.cargandoCaja = false;
        this.cajaAbierta = !!(resp?.tiene_sesion_activa && resp?.sesion_activa);
        this.cajaInfo = resp?.sesion_activa || null;
      },
      error: () => {
        this.cargandoCaja = false;
        this.cajaAbierta = false;
        this.cajaInfo = null;
      }
    });
  }

  // --- Carga de reservas ---
  cargarReservas(): void {
    if (!this.sucursalActiva?.id) {
      this.error = 'Seleccione una sucursal activa para gestionar reservas.';
      return;
    }

    this.cargando = true;
    this.mensaje = '';
    this.error = '';

    const idEmpresa = this.empresaActiva?.id_empresa || this.empresaActiva?.id;

    this.atenderReservaService
      .listarReservas(this.sucursalActiva.id, idEmpresa, this.busqueda, this.filtroEstado)
      .subscribe({
        next: (respuesta) => {
          this.cargando = false;
          if (!respuesta?.success) {
            this.error = respuesta?.message || 'No se pudieron cargar las reservas.';
            return;
          }
          this.reservas = respuesta.data || [];

          // Si había una reserva seleccionada, actualizarla con los datos frescos
          if (this.reservaSeleccionada) {
            const actualizada = this.reservas.find(r => r.id_reserva === this.reservaSeleccionada!.id_reserva);
            if (actualizada) {
              this.seleccionarReserva(actualizada);
            }
          }
        },
        error: (err) => {
          this.cargando = false;
          this.error = err?.error?.detail || err?.error?.message || 'No se pudieron cargar las reservas.';
        }
      });
  }

  onBuscar(): void {
    this.cargarReservas();
  }

  limpiarBusqueda(): void {
    this.busqueda = '';
    this.cargarReservas();
  }

  filtrarPorEstado(estado: string): void {
    this.filtroEstado = estado;
    this.cargarReservas();
  }

  // --- Selección de Reserva en el Workstation POS ---
  seleccionarReserva(reserva: ReservaItem): void {
    // Clonar para manipulación interactiva de prendas en probador
    this.reservaSeleccionada = JSON.parse(JSON.stringify(reserva));
    this.mensaje = '';
    this.error = '';

    if (this.reservaSeleccionada?.prendas) {
      this.reservaSeleccionada.prendas.forEach(p => {
        // Por defecto, toda prenda reservada se marca como aceptada para llevar
        p.aceptado = (p.estado_prenda !== 'RECHAZADA');
      });
    }

    // Inicializar datos de facturación sugeridos con los del cliente
    const cliente = this.reservaSeleccionada?.cliente;
    this.datosFacturacion = {
      nit_ci: cliente?.ci || '0',
      razon_social: cliente?.nombre_completo || 'CONTROL INTERNO',
      correo_facturacion: cliente?.correo || '',
      tipo_documento: 'COMPROBANTE'
    };

    this.descuento = 0;
    this.observacionCobro = '';
    this.montoRecibido = this.totalCobrar;
    this.calcularCambio();
  }

  limpiarSeleccion(): void {
    this.reservaSeleccionada = null;
    this.mensaje = '';
    this.error = '';
    this.mostrarModalCobro = false;
  }

  // --- Probador y Gestión de Prendas (Aceptar / Devolver) ---
  togglePrendaAceptada(prenda: PrendaReserva): void {
    prenda.aceptado = !prenda.aceptado;
    this.montoRecibido = this.totalCobrar;
    this.calcularCambio();
  }

  marcarTodas(aceptadas: boolean): void {
    if (!this.reservaSeleccionada?.prendas) return;
    this.reservaSeleccionada.prendas.forEach(p => {
      p.aceptado = aceptadas;
    });
    this.montoRecibido = this.totalCobrar;
    this.calcularCambio();
  }

  get prendasAceptadas(): PrendaReserva[] {
    return (this.reservaSeleccionada?.prendas || []).filter(p => p.aceptado);
  }

  get prendasDevueltas(): PrendaReserva[] {
    return (this.reservaSeleccionada?.prendas || []).filter(p => !p.aceptado);
  }

  get subtotalCobrar(): number {
    return this.prendasAceptadas.reduce((sum, it) => sum + (it.precio * it.cantidad), 0);
  }

  get totalCobrar(): number {
    const total = this.subtotalCobrar - (this.descuento || 0);
    return Math.max(0, +total.toFixed(2));
  }

  // --- Flujo de Cobro POS Autónomo ---
  abrirModalCobro(): void {
    if (!this.reservaSeleccionada) return;

    if (!this.cajaAbierta) {
      this.error = 'Debe abrir una sesión de caja antes de realizar cobros en mostrador.';
      return;
    }

    if (this.prendasAceptadas.length === 0) {
      if (confirm('El cliente no adquirió ninguna prenda. ¿Desea devolver todas las prendas al stock y cerrar la atención?')) {
        this.procesarCierreSinCompra();
      }
      return;
    }

    this.metodoPagoSeleccionado = 3; // Efectivo por defecto
    this.montoRecibido = this.totalCobrar;
    this.calcularCambio();
    this.referenciaTransaccion = '';
    this.mostrarModalCobro = true;
    this.error = '';
  }

  cerrarModalCobro(): void {
    this.mostrarModalCobro = false;
  }

  seleccionarMetodoPago(idMetodo: number): void {
    this.metodoPagoSeleccionado = idMetodo;
    if (idMetodo !== 3) {
      this.montoRecibido = this.totalCobrar;
      this.cambio = 0;
    } else {
      this.calcularCambio();
    }
  }

  setMontoExacto(): void {
    this.montoRecibido = this.totalCobrar;
    this.calcularCambio();
  }

  agregarEfectivo(valor: number): void {
    this.montoRecibido = +(Number(this.montoRecibido || 0) + valor).toFixed(2);
    this.calcularCambio();
  }

  calcularCambio(): void {
    if (this.metodoPagoSeleccionado !== 3) {
      this.cambio = 0;
      return;
    }
    const recibido = Number(this.montoRecibido || 0);
    const total = this.totalCobrar;
    this.cambio = Math.max(0, +(recibido - total).toFixed(2));
  }

  // --- Confirmar Venta POS y Entrega ---
  confirmarCobroPos(): void {
    if (!this.reservaSeleccionada || !this.sucursalActiva?.id) return;

    if (this.metodoPagoSeleccionado === 3 && (this.montoRecibido < this.totalCobrar)) {
      this.error = `Efectivo insuficiente. El cliente debe abonar al menos Bs. ${this.totalCobrar.toFixed(2)}.`;
      return;
    }

    this.procesando = true;
    this.error = '';

    const payload: CobroReservaPayload = {
      id_sesion_caja: this.cajaInfo?.id_sesion_caja,
      id_metodo_pago: this.metodoPagoSeleccionado,
      monto_recibido: this.metodoPagoSeleccionado === 3 ? this.montoRecibido : this.totalCobrar,
      monto_cambio: this.metodoPagoSeleccionado === 3 ? this.cambio : 0,
      referencia_transaccion: this.referenciaTransaccion || undefined,
      descuento: this.descuento || 0,
      observacion: this.observacionCobro || `Cobro en mostrador POS - Reserva ${this.reservaSeleccionada.codigo_reserva}`,
      datos_facturacion: this.datosFacturacion,
      items_seleccionados: (this.reservaSeleccionada.prendas || []).map(p => ({
        id_detalle_reserva: p.id_detalle_reserva,
        id_variante: p.id_variante,
        cantidad: p.cantidad,
        aceptado: !!p.aceptado
      }))
    };

    const idEmpresa = this.empresaActiva?.id_empresa;

    this.atenderReservaService.cobrarReservaPos(
      this.reservaSeleccionada.id_reserva,
      payload,
      this.sucursalActiva.id,
      idEmpresa
    ).subscribe({
      next: (resp) => {
        this.procesando = false;
        this.mostrarModalCobro = false;

        if (!resp?.success) {
          this.error = resp?.message || 'Error al procesar el cobro en mostrador.';
          return;
        }

        this.resultadoExito = resp.data || resp;
        this.mostrarModalExito = true;
        this.cargarReservas();
      },
      error: (err) => {
        this.procesando = false;
        this.error = err?.error?.detail || err?.error?.message || 'No se pudo procesar la venta en el POS.';
      }
    });
  }

  // --- Devolución completa de prendas sin compra ---
  procesarCierreSinCompra(): void {
    if (!this.reservaSeleccionada || !this.sucursalActiva?.id) return;
    this.procesando = true;

    const payload: CobroReservaPayload = {
      id_sesion_caja: this.cajaInfo?.id_sesion_caja,
      id_metodo_pago: 3,
      monto_recibido: 0,
      monto_cambio: 0,
      items_seleccionados: (this.reservaSeleccionada.prendas || []).map(p => ({
        id_detalle_reserva: p.id_detalle_reserva,
        id_variante: p.id_variante,
        cantidad: p.cantidad,
        aceptado: false
      }))
    };

    const idEmpresa = this.empresaActiva?.id_empresa || this.empresaActiva?.id;

    this.atenderReservaService.cobrarReservaPos(
      this.reservaSeleccionada.id_reserva,
      payload,
      this.sucursalActiva.id,
      idEmpresa
    ).subscribe({
      next: (resp) => {
        this.procesando = false;
        this.mensaje = resp?.message || 'Prendas devueltas y reserva cerrada.';
        this.limpiarSeleccion();
        this.cargarReservas();
      },
      error: (err) => {
        this.procesando = false;
        this.error = err?.error?.detail || err?.error?.message || 'Error al devolver las prendas al stock.';
      }
    });
  }

  // --- Entrega de Reserva Prepagada Online ---
  confirmarEntregaPrepagada(): void {
    if (!this.reservaSeleccionada || !this.sucursalActiva?.id) return;

    this.procesando = true;
    this.error = '';

    const payload = {
      items_seleccionados: (this.reservaSeleccionada.prendas || []).map(p => ({
        id_detalle_reserva: p.id_detalle_reserva,
        id_variante: p.id_variante,
        cantidad: p.cantidad,
        aceptado: !!p.aceptado
      }))
    };

    const idEmpresa = this.empresaActiva?.id_empresa || this.empresaActiva?.id;

    this.atenderReservaService.entregarReservaPagada(
      this.reservaSeleccionada.id_reserva,
      payload,
      this.sucursalActiva.id,
      idEmpresa
    ).subscribe({
      next: (resp) => {
        this.procesando = false;
        if (!resp?.success) {
          this.error = resp?.message || 'Error al entregar prendas de la reserva.';
          return;
        }

        this.resultadoExito = resp.data || {
          codigo_reserva: this.reservaSeleccionada?.codigo_reserva,
          id_venta: this.reservaSeleccionada?.id_venta,
          items_entregados: this.prendasAceptadas.length,
          items_devueltos: this.prendasDevueltas.length
        };
        this.mostrarModalExito = true;
        this.cargarReservas();
      },
      error: (err) => {
        this.procesando = false;
        this.error = err?.error?.detail || err?.error?.message || 'No se pudo completar la entrega de la reserva.';
      }
    });
  }

  // --- Descarga de Comprobante / Ticket PDF ---
  descargarTicket(idVenta?: number): void {
    const vId = idVenta || this.resultadoExito?.id_venta || this.reservaSeleccionada?.id_venta;
    if (!vId) {
      this.error = 'No se encontró el ID de la venta para emitir el comprobante.';
      return;
    }

    this.descargandoPdf = true;
    this.cajaService.descargarComprobantePdf(vId).subscribe({
      next: (blob) => {
        this.descargandoPdf = false;
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Ticket-Venta-${this.resultadoExito?.numero_venta || vId}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      },
      error: () => {
        this.descargandoPdf = false;
        this.error = 'No se pudo generar el comprobante PDF de la venta.';
      }
    });
  }

  cerrarModalExito(): void {
    this.mostrarModalExito = false;
    this.resultadoExito = null;
    this.limpiarSeleccion();
    this.cargarReservas();
  }

  irACaja(): void {
    this.router.navigate(['/admin/caja']);
  }
}