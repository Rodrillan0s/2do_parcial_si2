import { Component, OnInit, inject, ChangeDetectorRef, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AuthService } from '../../../services/auth';
import {
  CajaService,
  VentaParaPago,
  MetodoPagoPos,
  ProcesarPagoCajaPayload,
  ResultadoPagoCaja
} from '../../../services/caja';

@Component({
  selector: 'app-caja-pago',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './caja-pago.html',
  styleUrls: ['./caja-pago.css']
})
export class CajaPagoComponent implements OnInit {
  private route = inject(ActivatedRoute);
  public router = inject(Router);
  private cajaService = inject(CajaService);
  public authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);

  // Parámetros y Venta
  idVenta: number = 0;
  venta: VentaParaPago | null = null;
  metodosPago: MetodoPagoPos[] = [];

  // Estado de pantalla
  cargando: boolean = true;
  procesando: boolean = false;
  errorCarga: string | null = null;
  mensajeError: string | null = null;
  pagoExitoso: ResultadoPagoCaja | null = null;

  // Formulario de Pago
  idMetodoSeleccionado: number = 3; // Default: Efectivo (id 3)
  metodoSeleccionadoTipo: string = 'EFECTIVO';
  montoRecibido: number = 0;
  referenciaExterna: string = '';

  // Denominaciones para Efectivo Recibido y Cambio
  denominacionesDisponibles: Array<{ id_denominacion: number; valor: number; tipo: string; moneda: string }> = [];
  filasDenominacionRecibida: Array<{ id_denominacion: number; valor: number; tipo: string; cantidad: number; subtotal: number }> = [];
  desgloseCambio: Array<{ id_denominacion: number; valor: number; tipo: string; cantidad: number; subtotal: number }> = [];
  modoEntradaDenominaciones: boolean = true;

  // Datos opcionales de facturación
  razonSocial: string = '';
  nitCi: string = '';
  correoFacturacion: string = '';

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const idStr = params.get('id');
      if (idStr) {
        this.idVenta = parseInt(idStr, 10);
        this.cargarDenominaciones();
        this.cargarDatosVenta();
      } else {
        this.errorCarga = 'Identificador de venta no especificado.';
        this.cargando = false;
      }
    });
  }

  cargarDenominaciones(): void {
    this.cajaService.obtenerDenominaciones().subscribe({
      next: (res) => {
        if (res.success && res.denominaciones) {
          this.denominacionesDisponibles = res.denominaciones;
        } else {
          this.denominacionesDisponibles = this.denominacionesFallback();
        }
        this.inicializarFilasDenominacion();
      },
      error: () => {
        this.denominacionesDisponibles = this.denominacionesFallback();
        this.inicializarFilasDenominacion();
      }
    });
  }

  private denominacionesFallback(): Array<{ id_denominacion: number; valor: number; tipo: string; moneda: string }> {
    return [
      { id_denominacion: 1, valor: 200, tipo: 'BILLETE', moneda: 'BOB' },
      { id_denominacion: 2, valor: 100, tipo: 'BILLETE', moneda: 'BOB' },
      { id_denominacion: 3, valor: 50, tipo: 'BILLETE', moneda: 'BOB' },
      { id_denominacion: 4, valor: 20, tipo: 'BILLETE', moneda: 'BOB' },
      { id_denominacion: 5, valor: 10, tipo: 'BILLETE', moneda: 'BOB' },
      { id_denominacion: 6, valor: 5, tipo: 'MONEDA', moneda: 'BOB' },
      { id_denominacion: 7, valor: 2, tipo: 'MONEDA', moneda: 'BOB' },
      { id_denominacion: 8, valor: 1, tipo: 'MONEDA', moneda: 'BOB' },
      { id_denominacion: 9, valor: 0.5, tipo: 'MONEDA', moneda: 'BOB' }
    ];
  }

  inicializarFilasDenominacion(): void {
    this.filasDenominacionRecibida = this.denominacionesDisponibles.map(d => ({
      id_denominacion: d.id_denominacion,
      valor: d.valor,
      tipo: d.tipo,
      cantidad: 0,
      subtotal: 0
    }));
  }

  recalcularDesdeDenominaciones(): void {
    const total = this.filasDenominacionRecibida.reduce((acc, f) => {
      f.subtotal = Math.round((f.cantidad || 0) * f.valor * 100) / 100;
      return acc + f.subtotal;
    }, 0);
    this.montoRecibido = Math.round(total * 100) / 100;
    this.actualizarCalculoCambio();
  }

  onMontoRecibidoManualChange(): void {
    // Si el usuario escribe manualmente el monto total recibido
    this.actualizarCalculoCambio();
  }

  cambiarCantidadBillete(fila: { id_denominacion: number; valor: number; cantidad: number; subtotal: number }, delta: number): void {
    fila.cantidad = Math.max(0, (fila.cantidad || 0) + delta);
    this.recalcularDesdeDenominaciones();
  }

  agregarBillete(valor: number): void {
    const fila = this.filasDenominacionRecibida.find(f => f.valor === valor);
    if (fila) {
      fila.cantidad = (fila.cantidad || 0) + 1;
      this.recalcularDesdeDenominaciones();
    } else {
      this.montoRecibido = +(Number(this.montoRecibido || 0) + valor).toFixed(2);
      this.actualizarCalculoCambio();
    }
  }

  limpiarDenominaciones(): void {
    this.filasDenominacionRecibida.forEach(f => {
      f.cantidad = 0;
      f.subtotal = 0;
    });
    this.montoRecibido = 0;
    this.desgloseCambio = [];
  }

  actualizarCalculoCambio(): void {
    const cambio = this.cambioCalculado;
    if (cambio <= 0) {
      this.desgloseCambio = [];
      return;
    }

    let rem = cambio;
    const desglose: Array<{ id_denominacion: number; valor: number; tipo: string; cantidad: number; subtotal: number }> = [];
    const denomsOrdenadas = [...this.denominacionesDisponibles].sort((a, b) => b.valor - a.valor);

    for (const d of denomsOrdenadas) {
      if (rem >= d.valor) {
        const cant = Math.floor(+(rem / d.valor).toFixed(4));
        if (cant > 0) {
          const subt = +(cant * d.valor).toFixed(2);
          rem = Math.max(0, +(rem - subt).toFixed(2));
          desglose.push({
            id_denominacion: d.id_denominacion,
            valor: d.valor,
            tipo: d.tipo,
            cantidad: cant,
            subtotal: subt
          });
        }
      }
      if (rem <= 0.001) break;
    }

    this.desgloseCambio = desglose;
  }

  establecerMontoExacto(): void {
    this.limpiarDenominaciones();
    this.montoRecibido = this.totalVenta;
    // Opcional: distribuir vorazmente en denominaciones para conveniencia
    let rem = this.totalVenta;
    const denomsOrdenadas = [...this.filasDenominacionRecibida].sort((a, b) => b.valor - a.valor);
    for (const f of denomsOrdenadas) {
      if (rem >= f.valor) {
        const cant = Math.floor(+(rem / f.valor).toFixed(4));
        if (cant > 0) {
          f.cantidad = cant;
          f.subtotal = +(cant * f.valor).toFixed(2);
          rem = Math.max(0, +(rem - f.subtotal).toFixed(2));
        }
      }
      if (rem <= 0.001) break;
    }
    this.actualizarCalculoCambio();
  }

  cargarDatosVenta(): void {
    this.cargando = true;
    this.errorCarga = null;
    this.mensajeError = null;

    // Cargar métodos de pago disponibles
    this.cajaService.obtenerMetodosPagoCaja().subscribe({
      next: (res) => {
        if (res.success && res.metodos) {
          this.metodosPago = res.metodos;
          const efectivo = this.metodosPago.find(m => m.tipo === 'EFECTIVO');
          if (efectivo) {
            this.idMetodoSeleccionado = efectivo.id_metodo_pago;
            this.metodoSeleccionadoTipo = efectivo.tipo;
          } else if (this.metodosPago.length > 0) {
            this.idMetodoSeleccionado = this.metodosPago[0].id_metodo_pago;
            this.metodoSeleccionadoTipo = this.metodosPago[0].tipo;
          }
        }
      },
      error: () => {
        // Fallback default
        this.metodosPago = [
          { id_metodo_pago: 3, nombre: 'Efectivo', tipo: 'EFECTIVO' },
          { id_metodo_pago: 1, nombre: 'Tarjeta de Débito/Crédito', tipo: 'TARJETA' },
          { id_metodo_pago: 4, nombre: 'Pago QR', tipo: 'QR' }
        ];
      }
    });

    // Cargar y validar la venta para cobro
    this.cajaService.obtenerVentaParaPago(this.idVenta).subscribe({
      next: (res) => {
        this.cargando = false;
        if (res.success && res.venta) {
          this.venta = res.venta;
          this.montoRecibido = Number(this.venta.total);
          this.razonSocial = this.venta.razon_social || this.venta.cliente_nombre || 'Sin Nombre';
          this.nitCi = this.venta.nit_ci || '0';
          this.correoFacturacion = this.venta.correo_facturacion || this.venta.cliente_correo || '';
        } else {
          this.errorCarga = 'No se encontró la información de la venta especificada.';
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.cargando = false;
        const msg = err.error?.detail || err.error?.message || err.message || 'Error al validar la venta para cobro.';
        this.errorCarga = msg;
        this.cdr.detectChanges();
      }
    });
  }

  seleccionarMetodo(metodo: MetodoPagoPos): void {
    this.idMetodoSeleccionado = metodo.id_metodo_pago;
    this.metodoSeleccionadoTipo = metodo.tipo;
    if (this.metodoSeleccionadoTipo === 'EFECTIVO' && this.venta) {
      if (!this.montoRecibido || this.montoRecibido < Number(this.venta.total)) {
        this.montoRecibido = Number(this.venta.total);
      }
    }
  }

  // Helpers de cálculo de cambio para efectivo
  get totalVenta(): number {
    return this.venta ? Number(this.venta.total) : 0;
  }

  get cambioCalculado(): number {
    if (this.metodoSeleccionadoTipo !== 'EFECTIVO') return 0;
    const rec = Number(this.montoRecibido) || 0;
    return Math.max(0, +(rec - this.totalVenta).toFixed(2));
  }

  get montoFaltante(): number {
    if (this.metodoSeleccionadoTipo !== 'EFECTIVO') return 0;
    const rec = Number(this.montoRecibido) || 0;
    return Math.max(0, +(this.totalVenta - rec).toFixed(2));
  }

  get puedeCobrar(): boolean {
    if (this.procesando || !this.venta) return false;
    if (this.metodoSeleccionadoTipo === 'EFECTIVO') {
      return (Number(this.montoRecibido) || 0) >= this.totalVenta;
    }
    if (this.metodoSeleccionadoTipo === 'TARJETA' || this.metodoSeleccionadoTipo === 'QR') {
      return this.referenciaExterna.trim().length >= 3;
    }
    return true;
  }

  procesarPago(): void {
    if (!this.puedeCobrar || !this.venta) return;

    this.procesando = true;
    this.mensajeError = null;

    const desgloseRecibidoPayload = this.filasDenominacionRecibida
      .filter(f => (f.cantidad || 0) > 0)
      .map(f => ({
        id_denominacion: f.id_denominacion,
        valor: f.valor,
        cantidad: f.cantidad,
        subtotal: f.subtotal
      }));

    const desgloseCambioPayload = this.desgloseCambio
      .filter(c => (c.cantidad || 0) > 0)
      .map(c => ({
        id_denominacion: c.id_denominacion,
        valor: c.valor,
        cantidad: c.cantidad,
        subtotal: c.subtotal
      }));

    const payload: ProcesarPagoCajaPayload = {
      id_venta: this.idVenta,
      id_metodo_pago: this.idMetodoSeleccionado,
      monto_recibido: this.metodoSeleccionadoTipo === 'EFECTIVO' ? Number(this.montoRecibido) : undefined,
      referencia_externa: this.referenciaExterna.trim() ? this.referenciaExterna.trim() : undefined,
      razon_social: this.razonSocial.trim() || undefined,
      nit_ci: this.nitCi.trim() || undefined,
      correo_facturacion: this.correoFacturacion.trim() || undefined,
      desglose_recibido: this.metodoSeleccionadoTipo === 'EFECTIVO' && desgloseRecibidoPayload.length > 0 ? desgloseRecibidoPayload : undefined,
      desglose_cambio: this.metodoSeleccionadoTipo === 'EFECTIVO' && desgloseCambioPayload.length > 0 ? desgloseCambioPayload : undefined
    };

    this.cajaService.procesarPagoCaja(payload).subscribe({
      next: (res) => {
        this.procesando = false;
        if (res.success) {
          this.pagoExitoso = res;
          if (this.venta) {
            this.venta.estado = 'PAGADO';
          }
        } else {
          this.mensajeError = res.message || 'No se pudo procesar el pago.';
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.procesando = false;
        this.mensajeError = err.error?.detail || err.error?.message || err.message || 'Error inesperado al procesar el pago.';
        this.cdr.detectChanges();
      }
    });
  }

  irAComprobante(): void {
    this.router.navigate(['/admin/caja/comprobante', this.idVenta]);
  }

  irANuevaVenta(): void {
    this.router.navigate(['/admin/caja']);
  }
}
