import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { PedidoService, PedidoResumen, PedidoData, PedidoFiltros } from '../../../services/pedido';
import { PagoService } from '../../../services/pago';
import { AuthService } from '../../../services/auth';
import { ThemeService } from '../../../services/theme';
import {
  DevolucionesService,
  DevolucionResumen,
  DevolucionDetalleCompleto,
  ElegibilidadVentaResponse,
  SolicitarDevolucionPayload
} from '../../../services/devoluciones';
import { ValoracionModalComponent } from '../../../components/valoracion-modal/valoracion-modal';

@Component({
  selector: 'app-mis-pedidos',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule, ValoracionModalComponent],
  templateUrl: './mis-pedidos.html',
  styleUrls: ['./mis-pedidos.css']
})
export class MisPedidosComponent implements OnInit {
  private pedidoService = inject(PedidoService);
  private pagoService = inject(PagoService);
  private devolucionesService = inject(DevolucionesService);
  public authService = inject(AuthService);
  public themeService = inject(ThemeService);
  public router = inject(Router);
  private cdr = inject(ChangeDetectorRef);

  // Pestañas (CU11 Mis Pedidos / CU25W Mis Devoluciones / Mis Saldos)
  tabActiva: 'PEDIDOS' | 'DEVOLUCIONES' | 'CREDITOS' = 'PEDIDOS';

  // --- Mis Créditos (Saldo a Favor) ---
  misCreditos: any[] = [];
  cargandoCreditos: boolean = false;

  // --- Listado y Paginación de Pedidos ---
  pedidos: PedidoResumen[] = [];
  total: number = 0;
  paginaActual: number = 1;
  limitePorPagina: number = 10;
  totalPaginas: number = 1;
  cargando: boolean = true;
  opcionesLimite: number[] = [5, 10, 20, 50];

  // Filtros Pedidos
  filtroEstado: string = 'TODOS';
  filtroEstadoPago: string = 'TODOS';
  filtroFechaInicio: string = '';
  filtroFechaFin: string = '';
  filtroCodigo: string = '';

  // Modal Detalle Pedido
  pedidoDetalle: PedidoData | null = null;
  mostrarModalDetalle: boolean = false;
  cargandoDetalle: boolean = false;
  descargandoPdfId: number | null = null;

  // Valoración de Pedido y Prendas
  modalValoracionVisible: boolean = false;
  pedidoAValorar: { id_pedido: number; codigo_pedido: string; id_producto?: number | null; nombre_producto?: string; imagen_producto?: string; nombre_sucursal?: string } | null = null;
  pedidosValoradosIds: Set<number> = new Set<number>();

  abrirModalValoracion(p: any, item?: any): void {
    this.pedidoAValorar = {
      id_pedido: p.id_pedido,
      codigo_pedido: p.codigo_pedido,
      id_producto: item?.id_producto || null,
      nombre_producto: item?.producto_nombre || item?.nombre_producto || '',
      imagen_producto: item?.imagen_url || item?.imagen_principal || '',
      nombre_sucursal: p.nombre_sucursal || ''
    };
    this.modalValoracionVisible = true;
  }

  onValoracionRegistrada(datos: any): void {
    if (this.pedidoAValorar) {
      this.pedidosValoradosIds.add(this.pedidoAValorar.id_pedido);
    }
  }

  // Modal Cancelar Pedido (CU11 / CU12)
  mostrarModalCancelar: boolean = false;
  pedidoACancelar: PedidoResumen | null = null;
  motivoCancelacion: string = '';
  cancelandoPedido: boolean = false;

  // --- CU25W: Mis Devoluciones Solicitadas ---
  misDevoluciones: DevolucionResumen[] = [];
  totalDevoluciones: number = 0;
  paginaDevoluciones: number = 1;
  limiteDevoluciones: number = 10;
  totalPaginasDevoluciones: number = 1;
  cargandoDevoluciones: boolean = false;

  // Modal Solicitud Devolución (CU25W)
  mostrarModalSolicitud: boolean = false;
  cargandoElegibilidad: boolean = false;
  datosElegibilidad: ElegibilidadVentaResponse | null = null;
  idVentaDevolucion: number | null = null;
  idEmpresaDevolucion: number | null = null;
  itemsSeleccionados: {
    [id_detalle_venta: number]: {
      seleccionado: boolean;
      cantidad: number;
      talla_deseada?: string;
      id_variante_cambio?: number;
    }
  } = {};
  motivoDevolucion: string = 'DEFECTO_FABRICA';
  tipoResolucionDevolucion: 'CAMBIO_PRENDA' | 'SALDO_A_FAVOR' | 'REEMBOLSO_DINERO' = 'REEMBOLSO_DINERO';
  descripcionDevolucion: string = '';
  evidenciaUrlDevolucion: string = '';
  enviandoSolicitud: boolean = false;

  // Modal Detalle Devolución (CU25W)
  mostrarModalDetalleDevolucion: boolean = false;
  devolucionDetalle: DevolucionDetalleCompleto | null = null;
  cargandoDetalleDevolucion: boolean = false;

  // Toast Feedback
  mensajeToast: { tipo: 'exito' | 'error' | 'info'; texto: string } | null = null;
  copiadoExitoso: boolean = false;

  ngOnInit(): void {
    if (!this.authService.estaAutenticado()) {
      this.router.navigate(['/catalogo']);
      return;
    }
    this.cargarPedidos(1);
  }

  cambiarTab(tab: 'PEDIDOS' | 'DEVOLUCIONES' | 'CREDITOS'): void {
    this.tabActiva = tab;
    if (tab === 'DEVOLUCIONES' && this.misDevoluciones.length === 0) {
      this.cargarDevoluciones(1);
    } else if (tab === 'CREDITOS') {
      this.cargarMisCreditos();
    }
    this.cdr.markForCheck();
  }

  cargarMisCreditos(): void {
    this.cargandoCreditos = true;
    this.cdr.markForCheck();
    this.devolucionesService.obtenerMisCreditos().subscribe({
      next: (res: any) => {
        this.misCreditos = res.data || [];
        this.cargandoCreditos = false;
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.cargandoCreditos = false;
        this.mostrarToast('error', err?.error?.detail || 'No se pudieron consultar los saldos a favor.');
        this.cdr.markForCheck();
      }
    });
  }

  // =========================================================================
  // GESTIÓN DE PEDIDOS (CU11)
  // =========================================================================

  cargarPedidos(pagina: number = 1): void {
    this.paginaActual = pagina;
    this.cargando = true;
    this.cdr.markForCheck();

    const filtros: PedidoFiltros = {
      page: this.paginaActual,
      limit: this.limitePorPagina,
      estado: this.filtroEstado !== 'TODOS' ? this.filtroEstado : undefined,
      estado_pago: this.filtroEstadoPago !== 'TODOS' ? this.filtroEstadoPago : undefined,
      fecha_inicio: this.filtroFechaInicio || undefined,
      fecha_fin: this.filtroFechaFin || undefined,
      codigo: this.filtroCodigo.trim() || undefined
    };

    this.pedidoService.obtenerMisPedidos(filtros).subscribe({
      next: (res) => {
        this.pedidos = res.data || [];
        this.total = res.total || 0;
        this.totalPaginas = res.total_paginas || 1;
        this.cargando = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.cargando = false;
        this.mostrarToast('error', err?.error?.detail || 'No fue posible cargar tu historial de pedidos.');
        this.cdr.markForCheck();
      }
    });
  }

  aplicarFiltros(): void {
    this.cargarPedidos(1);
  }

  limpiarFiltros(): void {
    this.filtroEstado = 'TODOS';
    this.filtroEstadoPago = 'TODOS';
    this.filtroFechaInicio = '';
    this.filtroFechaFin = '';
    this.filtroCodigo = '';
    this.cargarPedidos(1);
  }

  cambiarLimite(nuevoLimite: any): void {
    this.limitePorPagina = Number(nuevoLimite);
    this.cargarPedidos(1);
  }

  abrirDetalle(idPedido: number): void {
    this.cargandoDetalle = true;
    this.mostrarModalDetalle = true;
    this.pedidoDetalle = null;
    this.cdr.markForCheck();

    this.pedidoService.obtenerPedido(idPedido).subscribe({
      next: (res) => {
        this.pedidoDetalle = res.data;
        this.cargandoDetalle = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.cargandoDetalle = false;
        this.mostrarModalDetalle = false;
        this.mostrarToast('error', err?.error?.detail || 'No se pudo cargar el detalle del pedido.');
        this.cdr.markForCheck();
      }
    });
  }

  cerrarDetalle(): void {
    this.mostrarModalDetalle = false;
    this.pedidoDetalle = null;
    this.cdr.markForCheck();
  }

  abrirModalCancelar(pedido: PedidoResumen): void {
    this.pedidoACancelar = pedido;
    this.motivoCancelacion = '';
    this.mostrarModalCancelar = true;
    this.cdr.markForCheck();
  }

  cerrarModalCancelar(): void {
    this.mostrarModalCancelar = false;
    this.pedidoACancelar = null;
    this.motivoCancelacion = '';
    this.cdr.markForCheck();
  }

  confirmarCancelarPedido(): void {
    if (!this.pedidoACancelar) return;
    this.cancelandoPedido = true;
    this.cdr.markForCheck();

    const motivo = this.motivoCancelacion.trim() || 'Cancelado por el cliente desde su perfil';
    this.pedidoService.cancelarPedido(this.pedidoACancelar.id_pedido, motivo, this.pedidoACancelar.id_empresa).subscribe({
      next: () => {
        this.cancelandoPedido = false;
        this.mostrarModalCancelar = false;
        const cod = this.pedidoACancelar?.codigo_pedido;
        this.pedidoACancelar = null;
        this.mostrarToast('exito', `El pedido ${cod} ha sido cancelado y sus prendas han sido liberadas a stock disponible.`);
        this.cargarPedidos(this.paginaActual);
      },
      error: (err) => {
        this.cancelandoPedido = false;
        this.mostrarToast('error', err?.error?.detail || 'No se pudo cancelar el pedido.');
        this.cdr.markForCheck();
      }
    });
  }

  irAPagar(idPedido: number): void {
    this.router.navigate(['/pago', idPedido]);
  }

  descargarComprobante(idPedido: number): void {
    this.descargandoPdfId = idPedido;
    this.cdr.markForCheck();

    this.pagoService.descargarComprobantePedidoBlob(idPedido).subscribe({
      next: (blob) => {
        this.descargandoPdfId = null;
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `comprobante_pedido_${idPedido}.pdf`;
        a.click();
        window.URL.revokeObjectURL(url);
        this.mostrarToast('exito', 'Comprobante descargado correctamente en PDF.');
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.descargandoPdfId = null;
        this.mostrarToast('error', err?.error?.detail || 'No se pudo generar o descargar el comprobante en PDF.');
        this.cdr.markForCheck();
      }
    });
  }

  // =========================================================================
  // CU25W: GESTIÓN DE DEVOLUCIONES CLIENTE
  // =========================================================================

  cargarDevoluciones(pagina: number = 1): void {
    this.paginaDevoluciones = pagina;
    this.cargandoDevoluciones = true;
    this.cdr.markForCheck();

    this.devolucionesService.listarMisDevoluciones(this.paginaDevoluciones, this.limiteDevoluciones).subscribe({
      next: (res: any) => {
        this.misDevoluciones = res.data || [];
        this.totalDevoluciones = res.total || 0;
        this.totalPaginasDevoluciones = res.total_paginas || 1;
        this.cargandoDevoluciones = false;
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.cargandoDevoluciones = false;
        this.mostrarToast('error', err?.error?.detail || 'Error al consultar tus devoluciones.');
        this.cdr.markForCheck();
      }
    });
  }

  iniciarSolicitudDevolucion(idVenta: number, idEmpresa?: number): void {
    this.idVentaDevolucion = idVenta;
    this.idEmpresaDevolucion = idEmpresa || null;
    this.cargandoElegibilidad = true;
    this.mostrarModalSolicitud = true;
    this.datosElegibilidad = null;
    this.itemsSeleccionados = {};
    this.motivoDevolucion = 'DEFECTO_FABRICA';
    this.descripcionDevolucion = '';
    this.evidenciaUrlDevolucion = '';
    this.cdr.markForCheck();

    this.devolucionesService.consultarElegibilidadVenta(idVenta, idEmpresa).subscribe({
      next: (res) => {
        this.cargandoElegibilidad = false;
        this.datosElegibilidad = res;
        if (res.es_elegible && res.items?.length) {
          res.items.forEach(it => {
            if (it.cantidad_elegible > 0) {
              const primeraVar = (it.variantes_disponibles && it.variantes_disponibles.length > 0) 
                ? it.variantes_disponibles.find(v => v.talla !== it.talla) || it.variantes_disponibles[0]
                : null;
              this.itemsSeleccionados[it.id_detalle_venta] = {
                seleccionado: false,
                cantidad: it.cantidad_elegible,
                talla_deseada: primeraVar ? primeraVar.talla : 'M',
                id_variante_cambio: primeraVar ? primeraVar.id_variante : undefined
              };
            }
          });
        }
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.cargandoElegibilidad = false;
        this.mostrarToast('error', err?.error?.detail || 'No se pudo verificar la elegibilidad de la venta.');
        this.mostrarModalSolicitud = false;
        this.cdr.markForCheck();
      }
    });
  }

  cerrarModalSolicitud(): void {
    this.mostrarModalSolicitud = false;
    this.datosElegibilidad = null;
    this.idVentaDevolucion = null;
    this.itemsSeleccionados = {};
    this.cdr.markForCheck();
  }

  toggleSeleccionItem(idDetalleVenta: number): void {
    if (this.itemsSeleccionados[idDetalleVenta]) {
      this.itemsSeleccionados[idDetalleVenta].seleccionado = !this.itemsSeleccionados[idDetalleVenta].seleccionado;
      this.cdr.markForCheck();
    }
  }

  ajustarCantidadItem(idDetalleVenta: number, cant: number, max: number): void {
    if (this.itemsSeleccionados[idDetalleVenta]) {
      const val = Math.max(1, Math.min(cant, max));
      this.itemsSeleccionados[idDetalleVenta].cantidad = val;
      this.cdr.markForCheck();
    }
  }

  onSeleccionarVarianteCambio(idDetalleVenta: number, tallaSeleccionada: string, variantes?: any[]): void {
    if (this.itemsSeleccionados[idDetalleVenta]) {
      this.itemsSeleccionados[idDetalleVenta].talla_deseada = tallaSeleccionada;
      if (variantes && variantes.length > 0) {
        const found = variantes.find(v => v.talla === tallaSeleccionada);
        if (found) {
          this.itemsSeleccionados[idDetalleVenta].id_variante_cambio = found.id_variante;
        }
      }
      this.cdr.markForCheck();
    }
  }

  hayItemsSeleccionados(): boolean {
    return Object.values(this.itemsSeleccionados).some(it => it.seleccionado && it.cantidad > 0);
  }

  calcularMontoEstimadoReembolso(): number {
    if (!this.datosElegibilidad?.items) return 0;
    let total = 0;
    for (const item of this.datosElegibilidad.items) {
      const sel = this.itemsSeleccionados[item.id_detalle_venta];
      if (sel?.seleccionado && sel.cantidad > 0) {
        total += item.precio_neto_unitario * sel.cantidad;
      }
    }
    return Math.round(total * 100) / 100;
  }

  enviarSolicitudDevolucion(): void {
    if (!this.hayItemsSeleccionados()) {
      this.mostrarToast('info', 'Debes seleccionar al menos una prenda para devolver.');
      return;
    }
    if (!this.idVentaDevolucion) return;

    if (this.motivoDevolucion === 'OTRO' && !this.descripcionDevolucion.trim()) {
      this.mostrarToast('info', 'Por favor ingresa una descripción para el motivo seleccionado.');
      return;
    }

    const itemsPayload = Object.entries(this.itemsSeleccionados)
      .filter(([_, val]) => val.seleccionado && val.cantidad > 0)
      .map(([idDet, val]) => ({
        id_detalle_venta: Number(idDet),
        cantidad: val.cantidad,
        talla_deseada: this.tipoResolucionDevolucion === 'CAMBIO_PRENDA' ? (val.talla_deseada || undefined) : undefined,
        id_variante_cambio: this.tipoResolucionDevolucion === 'CAMBIO_PRENDA' ? (val.id_variante_cambio || undefined) : undefined
      }));

    const payload: SolicitarDevolucionPayload = {
      id_venta: this.idVentaDevolucion,
      id_empresa: this.idEmpresaDevolucion || undefined,
      motivo: this.motivoDevolucion,
      tipo_resolucion: this.tipoResolucionDevolucion,
      descripcion: this.descripcionDevolucion.trim() || undefined,
      evidencia_url: this.evidenciaUrlDevolucion.trim() || undefined,
      items: itemsPayload
    };

    this.enviandoSolicitud = true;
    this.cdr.markForCheck();

    this.devolucionesService.solicitarDevolucion(payload).subscribe({
      next: (res) => {
        this.enviandoSolicitud = false;
        this.cerrarModalSolicitud();
        if (this.mostrarModalDetalle) {
          this.cerrarDetalle();
        }
        this.mostrarToast('exito', `Solicitud ${res?.data?.codigo_devolucion || ''} enviada correctamente.`);
        this.cambiarTab('DEVOLUCIONES');
        this.cargarDevoluciones(1);
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.enviandoSolicitud = false;
        this.mostrarToast('error', err?.error?.detail || 'No fue posible registrar la solicitud de devolución. Se conservan tus datos.');
        this.cdr.markForCheck();
      }
    });
  }

  abrirDetalleDevolucion(idDevolucion: number): void {
    this.cargandoDetalleDevolucion = true;
    this.mostrarModalDetalleDevolucion = true;
    this.devolucionDetalle = null;
    this.cdr.markForCheck();

    this.devolucionesService.verMiDevolucion(idDevolucion).subscribe({
      next: (res: any) => {
        this.devolucionDetalle = res.data;
        this.cargandoDetalleDevolucion = false;
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.cargandoDetalleDevolucion = false;
        this.mostrarModalDetalleDevolucion = false;
        this.mostrarToast('error', err?.error?.detail || 'No se pudo obtener el detalle de la devolución.');
        this.cdr.markForCheck();
      }
    });
  }

  cerrarDetalleDevolucion(): void {
    this.mostrarModalDetalleDevolucion = false;
    this.devolucionDetalle = null;
    this.cdr.markForCheck();
  }

  // =========================================================================
  // HELPERS UI Y ESTILOS
  // =========================================================================

  copiarCodigo(codigo: string): void {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(codigo).then(() => {
        this.copiadoExitoso = true;
        this.mostrarToast('exito', `Código ${codigo} copiado al portapapeles.`);
        this.cdr.markForCheck();
        setTimeout(() => {
          this.copiadoExitoso = false;
          this.cdr.markForCheck();
        }, 2500);
      });
    }
  }

  mostrarToast(tipo: 'exito' | 'error' | 'info', texto: string): void {
    this.mensajeToast = { tipo, texto };
    this.cdr.markForCheck();
    setTimeout(() => {
      this.mensajeToast = null;
      this.cdr.markForCheck();
    }, 4500);
  }

  getEstadoClase(estado: string): string {
    switch (estado?.toUpperCase()) {
      case 'PENDIENTE_PAGO':
        return 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30';
      case 'CONFIRMADO':
      case 'APROBADO':
        return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30';
      case 'EN_PREPARACION':
        return 'bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/30';
      case 'ENVIADO':
        return 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border-indigo-500/30';
      case 'ENTREGADO':
        return 'bg-teal-500/15 text-teal-700 dark:text-teal-300 border-teal-500/30';
      case 'CANCELADO':
        return 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30';
      default:
        return 'bg-zinc-500/15 text-zinc-700 dark:text-zinc-300 border-zinc-500/30';
    }
  }

  getEstadoLabel(estado: string): string {
    switch (estado?.toUpperCase()) {
      case 'PENDIENTE_PAGO': return 'Pendiente de Pago';
      case 'CONFIRMADO': return 'Confirmado';
      case 'APROBADO': return 'Aprobado';
      case 'EN_PREPARACION': return 'En Preparación';
      case 'ENVIADO': return 'Enviado';
      case 'ENTREGADO': return 'Entregado';
      case 'CANCELADO': return 'Cancelado';
      default: return estado || 'Registrado';
    }
  }

  getEstadoPagoClase(estadoPago: string): string {
    switch (estadoPago?.toUpperCase()) {
      case 'PAGADO':
        return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30';
      case 'PENDIENTE':
        return 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30';
      case 'RECHAZADO':
      case 'CANCELADO':
        return 'bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/30';
      default:
        return 'bg-zinc-500/15 text-zinc-700 dark:text-zinc-400 border-zinc-500/30';
    }
  }

  getEstadoPagoLabel(estadoPago: string): string {
    switch (estadoPago?.toUpperCase()) {
      case 'PAGADO': return 'Pagado ✓';
      case 'PENDIENTE': return 'Pago Pendiente';
      case 'RECHAZADO': return 'Pago Rechazado';
      case 'CANCELADO': return 'Anulado';
      default: return estadoPago || 'Pendiente';
    }
  }

  getEstadoDevolucionClase(estado: string): string {
    switch (estado?.toUpperCase()) {
      case 'SOLICITADA':
        return 'bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/30';
      case 'EN_REVISION':
        return 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30';
      case 'APROBADA':
        return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30';
      case 'RECHAZADA':
        return 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30';
      case 'RECIBIDA':
        return 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border-indigo-500/30';
      case 'PENDIENTE_REEMBOLSO':
        return 'bg-cyan-500/15 text-cyan-700 dark:text-cyan-300 border-cyan-500/30';
      case 'PENDIENTE_ENTREGA':
        return 'bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/30';
      case 'COMPLETADA':
        return 'bg-teal-500/15 text-teal-700 dark:text-teal-300 border-teal-500/30';
      case 'CANCELADA':
        return 'bg-zinc-500/15 text-zinc-700 dark:text-zinc-300 border-zinc-500/30';
      default:
        return 'bg-zinc-500/15 text-zinc-700 dark:text-zinc-300 border-zinc-500/30';
    }
  }

  getEstadoDevolucionLabel(estado: string): string {
    switch (estado?.toUpperCase()) {
      case 'SOLICITADA': return 'Solicitada (En Espera)';
      case 'EN_REVISION': return 'En Revisión Técnica';
      case 'APROBADA': return 'Aprobada ✓';
      case 'RECHAZADA': return 'Rechazada ✕';
      case 'RECIBIDA': return 'Prendas Recibidas';
      case 'PENDIENTE_REEMBOLSO': return 'Pendiente de Reembolso';
      case 'PENDIENTE_ENTREGA': return 'Prenda Recibida — Listo para Entrega de Cambio';
      case 'COMPLETADA': return 'Devolución Completada';
      case 'CANCELADA': return 'Cancelada';
      default: return estado || 'En Proceso';
    }
  }

  getTipoResolucionLabel(tipo: string | undefined): string {
    switch (tipo?.toUpperCase()) {
      case 'CAMBIO_PRENDA': return 'Cambio de Prenda';
      case 'SALDO_A_FAVOR': return 'Saldo a Favor en Tienda';
      case 'REEMBOLSO_DINERO': return 'Reembolso de Dinero';
      default: return tipo || 'Reembolso';
    }
  }

  getTipoResolucionClase(tipo: string | undefined): string {
    switch (tipo?.toUpperCase()) {
      case 'CAMBIO_PRENDA':
        return 'bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/30';
      case 'SALDO_A_FAVOR':
        return 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30';
      case 'REEMBOLSO_DINERO':
        return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30';
      default:
        return 'bg-zinc-500/15 text-zinc-700 dark:text-zinc-300 border-zinc-500/30';
    }
  }
}
