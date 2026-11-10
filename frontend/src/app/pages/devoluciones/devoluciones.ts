import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';

import { AuthService } from '../../services/auth';
import { SucursalService, Sucursal } from '../../services/sucursales';
import {
  DevolucionesService,
  DevolucionResumen,
  DevolucionDetalleCompleto,
  DevolucionesFiltros,
  ElegibilidadVentaResponse,
  DevolucionPresencialPayload,
  ItemPresencialDevolucion,
  VentaCandidataPresencial
} from '../../services/devoluciones';

@Component({
  selector: 'app-devoluciones',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './devoluciones.html',
  styleUrls: ['./devoluciones.css']
})
export class DevolucionesComponent implements OnInit {
  public authService = inject(AuthService);
  private devolucionesService = inject(DevolucionesService);
  private sucursalService = inject(SucursalService);
  private cdr = inject(ChangeDetectorRef);

  // --- DATOS Y LISTADO ---
  devoluciones: DevolucionResumen[] = [];
  total: number = 0;
  paginaActual: number = 1;
  limitePorPagina: number = 15;
  totalPaginas: number = 1;
  cargando: boolean = false;
  sucursales: Sucursal[] = [];

  // --- FILTROS DE BANDEJA ---
  filtroEstado: string = 'TODOS';
  filtroSucursal: number | null = null;
  filtroFechaInicio: string = '';
  filtroFechaFin: string = '';
  filtroBusqueda: string = '';

  // --- MODAL DETALLE / HISTORIAL ---
  mostrarModalDetalle: boolean = false;
  devolucionDetalle: DevolucionDetalleCompleto | null = null;
  cargandoDetalle: boolean = false;

  // --- MODAL REGISTRO PRESENCIAL (CU24W) ---
  mostrarModalPresencial: boolean = false;
  pasoPresencial: 1 | 2 = 1;
  criterioBusquedaPresencial: string = '';
  buscandoVentasPresencial: boolean = false;
  busquedaRealizadaPresencial: boolean = false;
  ventasCandidatas: VentaCandidataPresencial[] = [];
  cargandoVentaPresencial: boolean = false;
  ventaElegiblePresencial: ElegibilidadVentaResponse | null = null;
  itemsPresenciales: {
    [id_detalle_venta: number]: {
      seleccionado: boolean;
      cantidad: number;
      condicion: string;
    }
  } = {};
  motivoPresencial: string = 'DEFECTO_FABRICA';
  tipoResolucionPresencial: 'CAMBIO_PRENDA' | 'SALDO_A_FAVOR' | 'REEMBOLSO_DINERO' = 'REEMBOLSO_DINERO';
  observacionesPresenciales: string = '';
  idSucursalPresencial: number | null = null;
  reembolsoInmediatoPresencial: boolean = true;
  metodoReembolsoPresencial: string = 'EFECTIVO';
  referenciaReembolsoPresencial: string = '';
  guardandoPresencial: boolean = false;

  // Escaneo interactivo de comprobante (QR / Barras)
  mostrarModalEscaner: boolean = false;
  codigoEscaneoInput: string = '';

  // --- MODAL DICTAMEN (APROBAR / RECHAZAR) ---
  mostrarModalDictamen: boolean = false;
  idDevolucionDictamen: number | null = null;
  codigoDevolucionDictamen: string = '';
  accionDictamen: 'APROBAR' | 'RECHAZAR' | 'EN_REVISION' = 'APROBAR';
  tipoResolucionDictamen: 'CAMBIO_PRENDA' | 'SALDO_A_FAVOR' | 'REEMBOLSO_DINERO' = 'REEMBOLSO_DINERO';
  observacionesDictamen: string = '';
  guardandoDictamen: boolean = false;

  // --- MODAL RECEPCIÓN FÍSICA E INSPECCIÓN ---
  mostrarModalRecepcion: boolean = false;
  idDevolucionRecepcion: number | null = null;
  codigoDevolucionRecepcion: string = '';
  idSucursalRecepcion: number | null = null;
  itemsRecepcion: {
    [id_detalle_devolucion: number]: {
      cantidad: number;
      condicion: string;
    }
  } = {};
  observacionesRecepcion: string = '';
  guardandoRecepcion: boolean = false;

  // --- MODAL LIQUIDACIÓN REEMBOLSO O ENTREGA DE CAMBIO ---
  mostrarModalReembolso: boolean = false;
  idDevolucionReembolso: number | null = null;
  codigoDevolucionReembolso: string = '';
  montoReembolsoLiquidacion: number = 0;
  tipoResolucionReembolso: string = 'REEMBOLSO_DINERO';
  metodoReembolso: string = 'EFECTIVO';
  referenciaReembolso: string = '';
  observacionesReembolso: string = '';
  guardandoReembolso: boolean = false;
  esPagoPayPalOriginal: boolean = false;
  idCapturaPayPalOriginal: string = '';

  // --- MODAL CONFIGURACIÓN DE POLÍTICAS ---
  mostrarModalPoliticas: boolean = false;
  cargandoPoliticas: boolean = false;
  guardandoPoliticas: boolean = false;
  politicaConfig: any = {
    dias_devolucion_comercial: 15,
    dias_garantia_defecto: 90,
    requiere_etiqueta_original: true,
    requiere_empaque_original: false,
    permite_cambio_prenda: true,
    permite_saldo_favor: true,
    permite_reembolso_dinero: true,
    dias_vigencia_credito: 180,
    politica_texto_publico: ''
  };

  // --- TOAST NOTIFICATIONS ---
  mensajeToast: { tipo: 'exito' | 'error' | 'info'; texto: string } | null = null;

  ngOnInit(): void {
    this.cargarSucursales();
    this.cargarDevoluciones(1);
  }

  // =========================================================================
  // CARGA DE DATOS & SUCURSALES
  // =========================================================================

  cargarSucursales(): void {
    const idEmpresa = this.authService.getEffectiveCompanyId();
    this.sucursalService.listarSucursales(idEmpresa || undefined).subscribe({
      next: (res: any) => {
        this.sucursales = Array.isArray(res) ? res : (res?.data || []);
        if (this.sucursales.length > 0 && !this.idSucursalPresencial) {
          this.idSucursalPresencial = this.sucursales[0]?.id_sucursal ?? null;
          this.idSucursalRecepcion = this.sucursales[0]?.id_sucursal ?? null;
        }
        this.cdr.markForCheck();
      },
      error: () => {
        // Fallback no bloqueante si falla sucursales
      }
    });
  }

  cargarDevoluciones(pagina: number = 1): void {
    this.paginaActual = pagina;
    this.cargando = true;
    this.cdr.markForCheck();

    const filtros: DevolucionesFiltros = {
      page: this.paginaActual,
      limit: this.limitePorPagina,
      estado: this.filtroEstado !== 'TODOS' ? this.filtroEstado : undefined,
      id_sucursal: this.filtroSucursal || undefined,
      fecha_inicio: this.filtroFechaInicio || undefined,
      fecha_fin: this.filtroFechaFin || undefined,
      busqueda: this.filtroBusqueda.trim() || undefined,
      id_empresa: this.authService.getEffectiveCompanyId() || undefined
    };

    this.devolucionesService.listarDevolucionesPersonal(filtros).subscribe({
      next: (res: any) => {
        this.devoluciones = res.data || [];
        this.total = res.total || 0;
        this.totalPaginas = res.total_paginas || 1;
        this.cargando = false;
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.cargando = false;
        this.mostrarToast('error', err?.error?.detail || 'Error al consultar bandeja de devoluciones.');
        this.cdr.markForCheck();
      }
    });
  }

  aplicarFiltros(): void {
    this.cargarDevoluciones(1);
  }

  limpiarFiltros(): void {
    this.filtroEstado = 'TODOS';
    this.filtroSucursal = null;
    this.filtroFechaInicio = '';
    this.filtroFechaFin = '';
    this.filtroBusqueda = '';
    this.cargarDevoluciones(1);
  }

  // =========================================================================
  // DETALLE COMPLETO DE DEVOLUCIÓN
  // =========================================================================

  abrirDetalle(idDevolucion: number, idEmpresa?: number): void {
    this.cargandoDetalle = true;
    this.mostrarModalDetalle = true;
    this.devolucionDetalle = null;
    this.cdr.markForCheck();

    const empId = idEmpresa || this.authService.getEffectiveCompanyId() || undefined;
    this.devolucionesService.obtenerDetallePersonal(idDevolucion, empId).subscribe({
      next: (res: any) => {
        this.devolucionDetalle = res?.data || res;
        this.cargandoDetalle = false;
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.cargandoDetalle = false;
        this.mostrarToast('error', err?.error?.detail || 'No se pudo obtener el detalle de la devolución.');
        this.cdr.markForCheck();
      }
    });
  }

  cerrarDetalle(): void {
    this.mostrarModalDetalle = false;
    this.devolucionDetalle = null;
    this.cdr.markForCheck();
  }

  // =========================================================================
  // CU24W: DEVOLUCIÓN PRESENCIAL (MOSTRADOR / CAJERO)
  // =========================================================================

  abrirModalPresencial(): void {
    this.mostrarModalPresencial = true;
    this.pasoPresencial = 1;
    this.criterioBusquedaPresencial = '';
    this.ventasCandidatas = [];
    this.busquedaRealizadaPresencial = false;
    this.ventaElegiblePresencial = null;
    this.itemsPresenciales = {};
    this.motivoPresencial = 'DEFECTO_FABRICA';
    this.tipoResolucionPresencial = 'REEMBOLSO_DINERO';
    this.observacionesPresenciales = '';
    this.reembolsoInmediatoPresencial = true;
    this.metodoReembolsoPresencial = 'EFECTIVO';
    this.referenciaReembolsoPresencial = 'REC-PRES-' + Date.now().toString().slice(-6);
    this.idSucursalPresencial = this.sucursales[0]?.id_sucursal || null;
    this.cdr.markForCheck();
  }

  cerrarModalPresencial(): void {
    this.mostrarModalPresencial = false;
    this.pasoPresencial = 1;
    this.criterioBusquedaPresencial = '';
    this.ventasCandidatas = [];
    this.busquedaRealizadaPresencial = false;
    this.ventaElegiblePresencial = null;
    this.itemsPresenciales = {};
    this.cdr.markForCheck();
  }

  ejecutarBusquedaVentasPresencial(): void {
    const query = (this.criterioBusquedaPresencial || '').trim();
    if (!query) {
      this.mostrarToast('info', 'Ingresa el número de venta, código de pedido, cliente o documento.');
      return;
    }

    this.buscandoVentasPresencial = true;
    this.busquedaRealizadaPresencial = true;
    this.ventasCandidatas = [];
    this.ventaElegiblePresencial = null;
    this.cdr.markForCheck();

    this.devolucionesService.buscarVentasPresencial(query, this.authService.getEffectiveCompanyId() || undefined).subscribe({
      next: (candidatas: VentaCandidataPresencial[]) => {
        this.buscandoVentasPresencial = false;
        this.ventasCandidatas = candidatas || [];
        if (this.ventasCandidatas.length === 1) {
          // Si coincide con 1 venta exacta, cargar su ficha de verificación
          this.seleccionarVentaPresencial(this.ventasCandidatas[0].id_venta);
        } else if (this.ventasCandidatas.length === 0) {
          this.mostrarToast('info', 'No se encontraron ventas con los criterios ingresados.');
        }
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.buscandoVentasPresencial = false;
        this.mostrarToast('error', err?.error?.detail || 'Error al buscar ventas.');
        this.cdr.markForCheck();
      }
    });
  }

  seleccionarVentaPresencial(idVenta: number): void {
    this.cargandoVentaPresencial = true;
    this.ventaElegiblePresencial = null;
    this.itemsPresenciales = {};
    this.cdr.markForCheck();

    this.devolucionesService.consultarElegibilidadVenta(idVenta, this.authService.getEffectiveCompanyId() || undefined).subscribe({
      next: (res: ElegibilidadVentaResponse) => {
        this.cargandoVentaPresencial = false;
        this.ventaElegiblePresencial = res;
        if (res.venta?.id_sucursal && !this.idSucursalPresencial) {
          this.idSucursalPresencial = res.venta.id_sucursal;
        }
        if (res.es_elegible && res.items?.length) {
          res.items.forEach((it: any) => {
            if (it.cantidad_elegible > 0) {
              this.itemsPresenciales[it.id_detalle_venta] = {
                seleccionado: false,
                cantidad: it.cantidad_elegible,
                condicion: 'REVENDIBLE'
              };
            }
          });
        }
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.cargandoVentaPresencial = false;
        this.mostrarToast('error', err?.error?.detail || 'No se pudo consultar la venta.');
        this.cdr.markForCheck();
      }
    });
  }

  avanzarASeleccionProductos(): void {
    if (!this.ventaElegiblePresencial?.es_elegible) {
      this.mostrarToast('info', this.ventaElegiblePresencial?.motivo_bloqueo || 'Esta venta no cuenta con artículos elegibles.');
      return;
    }
    // Si ninguna prenda está marcada, pre-seleccionamos la primera disponible
    const haySeleccionados = Object.values(this.itemsPresenciales).some(it => it.seleccionado);
    if (!haySeleccionados && this.ventaElegiblePresencial.items?.length) {
      const primerElegible = this.ventaElegiblePresencial.items.find(it => it.cantidad_elegible > 0);
      if (primerElegible && this.itemsPresenciales[primerElegible.id_detalle_venta]) {
        this.itemsPresenciales[primerElegible.id_detalle_venta].seleccionado = true;
      }
    }
    this.pasoPresencial = 2;
    this.cdr.markForCheck();
  }

  volverABusquedaVenta(): void {
    this.pasoPresencial = 1;
    this.cdr.markForCheck();
  }

  abrirEscanerComprobante(): void {
    this.codigoEscaneoInput = '';
    this.mostrarModalEscaner = true;
    this.cdr.markForCheck();
  }

  cerrarEscanerComprobante(): void {
    this.mostrarModalEscaner = false;
    this.codigoEscaneoInput = '';
    this.cdr.markForCheck();
  }

  procesarCodigoEscaneado(): void {
    const code = (this.codigoEscaneoInput || '').trim();
    if (!code) {
      this.mostrarToast('info', 'Por favor ingresa o escanea un código.');
      return;
    }
    this.criterioBusquedaPresencial = code;
    this.cerrarEscanerComprobante();
    this.ejecutarBusquedaVentasPresencial();
  }

  toggleItemPresencial(idDet: number): void {
    if (this.itemsPresenciales[idDet]) {
      this.itemsPresenciales[idDet].seleccionado = !this.itemsPresenciales[idDet].seleccionado;
      this.cdr.markForCheck();
    }
  }

  ajustarCantidadPresencial(idDet: number, cant: number, max: number): void {
    if (this.itemsPresenciales[idDet]) {
      this.itemsPresenciales[idDet].cantidad = Math.max(1, Math.min(cant, max));
      this.cdr.markForCheck();
    }
  }

  hayItemsPresenciales(): boolean {
    return Object.values(this.itemsPresenciales).some(it => it.seleccionado && it.cantidad > 0);
  }

  calcularReembolsoPresencial(): number {
    if (!this.ventaElegiblePresencial?.items) return 0;
    let tot = 0;
    for (const it of this.ventaElegiblePresencial.items) {
      const sel = this.itemsPresenciales[it.id_detalle_venta];
      if (sel?.seleccionado && sel.cantidad > 0) {
        tot += it.precio_neto_unitario * sel.cantidad;
      }
    }
    return Math.round(tot * 100) / 100;
  }

  confirmarDevolucionPresencial(): void {
    if (!this.hayItemsPresenciales()) {
      this.mostrarToast('info', 'Selecciona al menos una prenda para la devolución presencial.');
      return;
    }
    if (!this.ventaElegiblePresencial?.venta) return;

    const itemsPayload: ItemPresencialDevolucion[] = Object.entries(this.itemsPresenciales)
      .filter(([_, val]) => val.seleccionado && val.cantidad > 0)
      .map(([idDet, val]) => ({
        id_detalle_venta: Number(idDet),
        cantidad: val.cantidad,
        condicion: val.condicion
      }));

    const payload: DevolucionPresencialPayload = {
      id_venta: this.ventaElegiblePresencial.venta.id_venta,
      id_sucursal: this.idSucursalPresencial || this.ventaElegiblePresencial.venta.id_sucursal || undefined,
      id_empresa: this.authService.getEffectiveCompanyId() || undefined,
      motivo: this.motivoPresencial,
      tipo_resolucion: this.tipoResolucionPresencial,
      observaciones: this.observacionesPresenciales.trim() || undefined,
      items: itemsPayload,
      registrar_reembolso_inmediato: this.reembolsoInmediatoPresencial,
      metodo_reembolso: this.reembolsoInmediatoPresencial ? this.metodoReembolsoPresencial : undefined,
      referencia_reembolso: this.reembolsoInmediatoPresencial ? this.referenciaReembolsoPresencial.trim() : undefined
    };

    this.guardandoPresencial = true;
    this.cdr.markForCheck();

    this.devolucionesService.registrarDevolucionPresencial(payload).subscribe({
      next: (res: any) => {
        this.guardandoPresencial = false;
        this.cerrarModalPresencial();
        this.mostrarToast('exito', `Devolución presencial ${res?.data?.codigo_devolucion || ''} registrada y stock actualizado.`);
        this.cargarDevoluciones(1);
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.guardandoPresencial = false;
        this.mostrarToast('error', err?.error?.detail || 'Error al procesar la devolución presencial.');
        this.cdr.markForCheck();
      }
    });
  }

  // =========================================================================
  // CU24W: DICTAMEN (APROBAR / RECHAZAR SOLICITUD)
  // =========================================================================

  abrirModalDictamen(dev: DevolucionResumen | DevolucionDetalleCompleto): void {
    this.idDevolucionDictamen = dev.id_devolucion;
    this.codigoDevolucionDictamen = dev.codigo_devolucion;
    this.accionDictamen = 'APROBAR';
    this.tipoResolucionDictamen = (dev.tipo_resolucion as any) || 'REEMBOLSO_DINERO';
    this.observacionesDictamen = '';
    this.mostrarModalDictamen = true;
    this.cdr.markForCheck();
  }

  cerrarModalDictamen(): void {
    this.mostrarModalDictamen = false;
    this.idDevolucionDictamen = null;
    this.observacionesDictamen = '';
    this.cdr.markForCheck();
  }

  confirmarDictamen(): void {
    if (!this.idDevolucionDictamen) return;
    if (!this.observacionesDictamen.trim()) {
      this.mostrarToast('info', 'Debes ingresar una justificación técnica para el dictamen.');
      return;
    }

    this.guardandoDictamen = true;
    this.cdr.markForCheck();

    this.devolucionesService.dictaminarSolicitud(
      this.idDevolucionDictamen,
      this.accionDictamen,
      this.observacionesDictamen.trim(),
      this.authService.getEffectiveCompanyId() || undefined,
      this.tipoResolucionDictamen
    ).subscribe({
      next: (res: any) => {
        this.guardandoDictamen = false;
        this.cerrarModalDictamen();
        this.mostrarToast('exito', `Dictamen emitido: ${res?.nuevo_estado || this.accionDictamen}.`);
        if (this.mostrarModalDetalle && this.devolucionDetalle?.id_devolucion === this.idDevolucionDictamen) {
          this.abrirDetalle(this.idDevolucionDictamen);
        }
        this.cargarDevoluciones(this.paginaActual);
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.guardandoDictamen = false;
        this.mostrarToast('error', err?.error?.detail || 'Error al emitir el dictamen.');
        this.cdr.markForCheck();
      }
    });
  }

  // =========================================================================
  // CU24W: RECEPCIÓN FÍSICA E INSPECCIÓN DE PRENDAS
  // =========================================================================

  abrirModalRecepcion(dev: DevolucionDetalleCompleto | any): void {
    const rawDev = dev?.data || dev;
    if (!rawDev.items || rawDev.items.length === 0) {
      this.cargando = true;
      this.cdr.markForCheck();
      this.devolucionesService.obtenerDetallePersonal(
        rawDev.id_devolucion, 
        rawDev.id_empresa || this.authService.getEffectiveCompanyId() || undefined
      ).subscribe({
        next: (res: any) => {
          this.cargando = false;
          const detalle = res?.data || res;
          if (detalle) {
            this.devolucionDetalle = detalle;
            this.abrirModalRecepcion(detalle);
          }
          this.cdr.markForCheck();
        },
        error: (err: any) => {
          this.cargando = false;
          this.mostrarToast('error', err?.error?.detail || 'No se pudo cargar el detalle para recepcionar.');
          this.cdr.markForCheck();
        }
      });
      return;
    }

    this.devolucionDetalle = rawDev;
    this.idDevolucionRecepcion = rawDev.id_devolucion;
    this.codigoDevolucionRecepcion = rawDev.codigo_devolucion;
    this.idSucursalRecepcion = rawDev.id_sucursal || (this.sucursales[0]?.id_sucursal ?? null);
    this.observacionesRecepcion = '';
    this.itemsRecepcion = {};

    if (rawDev.items) {
      rawDev.items.forEach((it: any) => {
        this.itemsRecepcion[it.id_detalle_devolucion] = {
          cantidad: it.cantidad,
          condicion: 'REVENDIBLE'
        };
      });
    }

    this.mostrarModalRecepcion = true;
    this.cdr.markForCheck();
  }

  cerrarModalRecepcion(): void {
    this.mostrarModalRecepcion = false;
    this.idDevolucionRecepcion = null;
    this.itemsRecepcion = {};
    this.cdr.markForCheck();
  }

  confirmarRecepcion(): void {
    if (!this.idDevolucionRecepcion) return;

    const itemsPayload = Object.entries(this.itemsRecepcion).map(([idDetDev, val]) => ({
      id_detalle_devolucion: Number(idDetDev),
      cantidad_recibida: val.cantidad,
      condicion: val.condicion
    }));

    if (itemsPayload.length === 0) {
      this.mostrarToast('info', 'No hay ítems para recepcionar.');
      return;
    }

    this.guardandoRecepcion = true;
    this.cdr.markForCheck();

    this.devolucionesService.registrarRecepcionPrendas(
      this.idDevolucionRecepcion,
      itemsPayload,
      this.idSucursalRecepcion || undefined,
      this.observacionesRecepcion.trim() || undefined,
      this.authService.getEffectiveCompanyId() || undefined
    ).subscribe({
      next: (res: any) => {
        this.guardandoRecepcion = false;
        this.cerrarModalRecepcion();
        this.mostrarToast('exito', `Prendas recepcionadas físicamente. Stock vendible actualizado para prendas REVENDIBLES.`);
        if (this.mostrarModalDetalle && this.devolucionDetalle?.id_devolucion === this.idDevolucionRecepcion) {
          this.abrirDetalle(this.idDevolucionRecepcion);
        }
        this.cargarDevoluciones(this.paginaActual);
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.guardandoRecepcion = false;
        this.mostrarToast('error', err?.error?.detail || 'Error al procesar la recepción física.');
        this.cdr.markForCheck();
      }
    });
  }

  // =========================================================================
  // CU24W: LIQUIDACIÓN DE REEMBOLSO FINANCIERO
  // =========================================================================

  abrirModalReembolso(dev: DevolucionResumen | DevolucionDetalleCompleto | any): void {
    const rawDev = dev?.data || dev;
    if (!rawDev.pago_origen && !rawDev.items) {
      this.cargando = true;
      this.cdr.markForCheck();
      this.devolucionesService.obtenerDetallePersonal(
        rawDev.id_devolucion,
        rawDev.id_empresa || this.authService.getEffectiveCompanyId() || undefined
      ).subscribe({
        next: (res: any) => {
          this.cargando = false;
          const detalle = res?.data || res;
          if (detalle) {
            this.devolucionDetalle = detalle;
            this.abrirModalReembolso(detalle);
          }
          this.cdr.markForCheck();
        },
        error: (err: any) => {
          this.cargando = false;
          this.mostrarToast('error', err?.error?.detail || 'No se pudo cargar el detalle para liquidar reembolso.');
          this.cdr.markForCheck();
        }
      });
      return;
    }

    this.idDevolucionReembolso = rawDev.id_devolucion;
    this.codigoDevolucionReembolso = rawDev.codigo_devolucion;
    this.montoReembolsoLiquidacion = rawDev.monto_reembolso;
    this.tipoResolucionReembolso = rawDev.tipo_resolucion || 'REEMBOLSO_DINERO';
    this.observacionesReembolso = '';

    if (rawDev.tipo_resolucion === 'CAMBIO_PRENDA') {
      this.esPagoPayPalOriginal = false;
      this.idCapturaPayPalOriginal = '';
      this.metodoReembolso = 'ENTREGA_PRENDA_CAMBIO';
      this.referenciaReembolso = `CAMBIO-${rawDev.codigo_devolucion}`;
      this.observacionesReembolso = 'Prenda de reemplazo verificada y entregada al cliente a satisfacción.';
    } else {
      const pagoOrig = rawDev.pago_origen;
      if (pagoOrig?.es_paypal || pagoOrig?.metodo_pago === 'PAYPAL' || (pagoOrig?.codigo_transaccion && pagoOrig.codigo_transaccion.length > 10)) {
        this.esPagoPayPalOriginal = true;
        this.idCapturaPayPalOriginal = pagoOrig?.codigo_transaccion || '';
        this.metodoReembolso = 'PAYPAL';
        this.referenciaReembolso = this.idCapturaPayPalOriginal ? `PAYPAL-${this.idCapturaPayPalOriginal}` : 'PAYPAL_REFUND';
      } else if (rawDev.tipo_resolucion === 'SALDO_A_FAVOR') {
        this.esPagoPayPalOriginal = false;
        this.idCapturaPayPalOriginal = '';
        this.metodoReembolso = 'SALDO_A_FAVOR';
        this.referenciaReembolso = 'VALE_DIGITAL';
      } else {
        this.esPagoPayPalOriginal = false;
        this.idCapturaPayPalOriginal = '';
        this.metodoReembolso = 'EFECTIVO';
        this.referenciaReembolso = 'REEMB-' + Date.now().toString().slice(-6);
      }
    }

    this.mostrarModalReembolso = true;
    this.cdr.markForCheck();
  }

  cerrarModalReembolso(): void {
    this.mostrarModalReembolso = false;
    this.idDevolucionReembolso = null;
    this.cdr.markForCheck();
  }

  confirmarReembolso(): void {
    if (!this.idDevolucionReembolso) return;
    if (!this.referenciaReembolso.trim()) {
      this.mostrarToast('info', 'Ingresa la referencia o comprobante.');
      return;
    }

    this.guardandoReembolso = true;
    this.cdr.markForCheck();

    this.devolucionesService.liquidarReembolso(
      this.idDevolucionReembolso,
      this.metodoReembolso,
      this.referenciaReembolso.trim(),
      this.observacionesReembolso.trim() || undefined,
      this.authService.getEffectiveCompanyId() || undefined
    ).subscribe({
      next: (res: any) => {
        this.guardandoReembolso = false;
        this.cerrarModalReembolso();
        const msg = this.tipoResolucionReembolso === 'CAMBIO_PRENDA'
          ? 'Cambio de prenda completado y entregado exitosamente al cliente.'
          : 'Reembolso financiero liquidado exitosamente para la devolución.';
        this.mostrarToast('exito', msg);
        if (this.mostrarModalDetalle && this.devolucionDetalle?.id_devolucion === this.idDevolucionReembolso) {
          this.abrirDetalle(this.idDevolucionReembolso);
        }
        this.cargarDevoluciones(this.paginaActual);
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.guardandoReembolso = false;
        this.mostrarToast('error', err?.error?.detail || 'Error al completar la liquidación.');
        this.cdr.markForCheck();
      }
    });
  }

  // =========================================================================
  // HELPERS UI Y ESTILOS
  // =========================================================================

  mostrarToast(tipo: 'exito' | 'error' | 'info', texto: string): void {
    this.mensajeToast = { tipo, texto };
    this.cdr.markForCheck();
    setTimeout(() => {
      this.mensajeToast = null;
      this.cdr.markForCheck();
    }, 4500);
  }

  copiarCodigo(codigo: string): void {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(codigo).then(() => {
        this.mostrarToast('exito', `Código ${codigo} copiado al portapapeles.`);
      });
    }
  }

  getEstadoClase(estado: string): string {
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

  getEstadoLabel(estado: string): string {
    switch (estado?.toUpperCase()) {
      case 'SOLICITADA': return 'Solicitada (Cliente)';
      case 'EN_REVISION': return 'En Revisión Técnica';
      case 'APROBADA': return 'Aprobada / Pendiente Recepción';
      case 'RECHAZADA': return 'Rechazada ✕';
      case 'RECIBIDA': return 'Prendas Recibidas en Tienda';
      case 'PENDIENTE_REEMBOLSO': return 'Pendiente Liquidar Reembolso';
      case 'PENDIENTE_ENTREGA': return 'Prendas Recibidas / Pendiente Entrega Cambio';
      case 'COMPLETADA': return 'Completada / Reembolsada ✓';
      case 'CANCELADA': return 'Cancelada';
      default: return estado || 'En Proceso';
    }
  }

  // =========================================================================
  // GESTIÓN DE POLÍTICAS DE DEVOLUCIÓN DE LA TIENDA
  // =========================================================================

  abrirModalPoliticas(): void {
    this.mostrarModalPoliticas = true;
    this.cargandoPoliticas = true;
    this.cdr.markForCheck();
    this.devolucionesService.consultarPoliticas(this.authService.getEffectiveCompanyId() || undefined).subscribe({
      next: (res: any) => {
        this.cargandoPoliticas = false;
        if (res.data) {
          this.politicaConfig = { ...this.politicaConfig, ...res.data };
        }
        this.cdr.markForCheck();
      },
      error: () => {
        this.cargandoPoliticas = false;
        this.cdr.markForCheck();
      }
    });
  }

  cerrarModalPoliticas(): void {
    this.mostrarModalPoliticas = false;
    this.cdr.markForCheck();
  }

  guardarPoliticas(): void {
    this.guardandoPoliticas = true;
    this.cdr.markForCheck();
    this.devolucionesService.actualizarPoliticas(this.politicaConfig, this.authService.getEffectiveCompanyId() || undefined).subscribe({
      next: () => {
        this.guardandoPoliticas = false;
        this.cerrarModalPoliticas();
        this.mostrarToast('exito', 'Políticas de devolución actualizadas correctamente.');
        this.cdr.markForCheck();
      },
      error: (err: any) => {
        this.guardandoPoliticas = false;
        this.mostrarToast('error', err?.error?.detail || 'Error al guardar las políticas de devolución.');
        this.cdr.markForCheck();
      }
    });
  }

  getTipoResolucionLabel(tipo: string | undefined): string {
    switch (tipo?.toUpperCase()) {
      case 'CAMBIO_PRENDA': return 'Cambio Prenda';
      case 'SALDO_A_FAVOR': return 'Saldo a Favor';
      case 'REEMBOLSO_DINERO': return 'Reembolso Dinero';
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
