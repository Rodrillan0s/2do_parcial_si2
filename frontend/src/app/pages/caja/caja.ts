import { Component, OnInit, inject, ChangeDetectorRef, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { distinctUntilChanged } from 'rxjs/operators';
import { AuthService } from '../../services/auth';
import { EmpresaService, Empresa } from '../../services/empresa';
import {
  CajaService,
  Denominacion,
  CajaEstadoResponse,
  ProductoPos,
  VariantePos,
  ClientePos,
  VentaPosItem,
  ResumenCajaResponse
} from '../../services/caja';
import { CategoriasService, Categoria } from '../../services/categorias';
import { extraerMensajeError } from '../../utils/error-helper';
import { NetworkStatusService } from '../../core/network/network-status.service';
import { SyncQueueService } from '../../core/sync/sync-queue.service';

export interface CartItem {
  variante: VariantePos;
  productoNombre: string;
  productoCodigo?: string;
  imagenUrl?: string;
  precioUnitario: number;
  cantidad: number;
  subtotal: number;
  stockDisponible: number;
}

export interface ConteoFila {
  id_denominacion: number;
  valor: number;
  tipo: 'BILLETE' | 'MONEDA';
  moneda: string;
  cantidad: number;
  subtotal: number;
  cantidad_esperada?: number;
  subtotal_esperado?: number;
}

@Component({
  selector: 'app-caja',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './caja.html',
  styleUrls: ['./caja.css']
})
export class CajaComponent implements OnInit {
  public authService = inject(AuthService);
  public networkStatus = inject(NetworkStatusService);
  public syncQueue = inject(SyncQueueService);
  private cajaService = inject(CajaService);
  private categoriasService = inject(CategoriasService);
  private empresaService = inject(EmpresaService);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);
  private searchTimer: any = null;

  // --- CONTEXTO MULTI-TENANT & ALCANCE ---
  empresasDisponibles: Empresa[] = [];
  cargandoEmpresas: boolean = false;
  private inicializado: boolean = false;

  get esSuperAdmin(): boolean {
    return this.authService.getScopeLevel() === 'PLATAFORMA';
  }

  get empresaActivaId(): number | null {
    return this.authService.getEffectiveCompanyId();
  }

  get empresaActivaNombre(): string {
    return this.authService.getEffectiveCompanyName();
  }

  get empresaRequerida(): boolean {
    return this.esSuperAdmin && !this.empresaActivaId;
  }

  constructor() { }

  // --- ESTADO GENERAL ---
  cargando: boolean = false;
  procesando: boolean = false;
  mensajeExito: string = '';
  mensajeError: string = '';
  pestanaDerecha: 'CARRITO' | 'POR_COBRAR' = 'CARRITO';

  get sucursalActiva(): { id: number; nombre: string; ciudad?: string } | null {
    return this.authService.activeBranch();
  }

  // --- SESIÓN Y ESTADO DE CAJA ---
  estadoCaja: CajaEstadoResponse | null = null;
  denominaciones: Denominacion[] = [];
  resumenCaja: ResumenCajaResponse['resumen'] | null = null;

  // --- ARQUEO Y CONTEO DE DENOMINACIONES ---
  conteoApertura: ConteoFila[] = [];
  conteoCierre: ConteoFila[] = [];
  observacionApertura: string = '';
  observacionCierre: string = '';

  // --- CATÁLOGO POS ---
  productos: ProductoPos[] = [];
  categorias: Categoria[] = [];
  categoriaSeleccionadaId: number | null = null;
  busquedaProducto: string = '';
  cargandoCatalogo: boolean = false;

  // --- SELECCIÓN DE VARIANTE ---
  modalVariantesAbierto: boolean = false;
  productoSeleccionadoParaVariante: ProductoPos | null = null;
  variantesDelProducto: VariantePos[] = [];
  cargandoVariantes: boolean = false;

  // --- CARRITO / VENTA ACTIVA ---
  carrito: CartItem[] = [];
  descuento: number = 0;
  observacionesVenta: string = '';

  // --- CONTEXTO DE RESERVA ---
  idReservaActual: number | null = null;
  reservaEnAtencion: boolean = false;
  reservaContexto: any = null;


  // --- GESTIÓN DE CLIENTE ---
  tipoCliente: 'SIN_CLIENTE' | 'CON_CLIENTE' = 'SIN_CLIENTE';
  clienteSeleccionado: ClientePos | null = null;
  busquedaCliente: string = '';
  clientesResultados: ClientePos[] = [];
  buscandoClientes: boolean = false;

  // --- HISTORIAL DEL TURNO ---
  ventasTurno: VentaPosItem[] = [];
  modalHistorialAbierto: boolean = false;
  cargandoHistorial: boolean = false;
  ventaDetalleSeleccionada: any = null;
  modalDetalleVentaAbierto: boolean = false;

  // --- MODALES ---
  modalAbrirAbierto: boolean = false;
  modalCerrarAbierto: boolean = false;
  modalResumenAbierto: boolean = false;
  modalConfirmarVentaAbierto: boolean = false;
  modalVentaExitosaAbierto: boolean = false;
  ventaExitosaInfo: {
    id_venta: number;
    codigo_venta: string;
    total: number;
    cant_items: number;
    offline_queued?: boolean;
    monto_recibido?: number;
    cambio?: number;
  } | null = null;

  // --- VENTA DE CONTADO EN EFECTIVO (CU24W ONLINE / OFFLINE) ---
  modalidadCobroConfirmacion: 'PASO_W28_ONLINE' | 'EFECTIVO_INMEDIATO' = 'PASO_W28_ONLINE';
  montoRecibidoEfectivo: number = 0;
  nitCiFacturacionOffline: string = 'S/N';
  razonSocialFacturacionOffline: string = 'SIN NOMBRE';

  get cambioEfectivoCalculado(): number {
    return Math.max(0, Math.round(((Number(this.montoRecibidoEfectivo) || 0) - this.totalCarrito) * 100) / 100);
  }

  get montoEfectivoValido(): boolean {
    return (Number(this.montoRecibidoEfectivo) || 0) >= this.totalCarrito;
  }

  // --- PERMISOS ---
  get puedeAbrirCaja(): boolean {
    return this.authService.hasPermission('caja.abrir');
  }

  get puedeCerrarCaja(): boolean {
    return this.authService.hasPermission('caja.cerrar');
  }

  get puedeVender(): boolean {
    return this.authService.hasPermission('pos.vender');
  }

  get puedeAplicarDescuento(): boolean {
    return this.authService.hasPermission('pos.descuento');
  }

  // --- TOTALES DEL CARRITO ---
  get subtotalCarrito(): number {
    const sum = this.carrito.reduce((acc, item) => acc + item.subtotal, 0);
    return Math.round(sum * 100) / 100;
  }

  get totalCarrito(): number {
    const tot = Math.max(0, this.subtotalCarrito - (this.descuento || 0));
    return Math.round(tot * 100) / 100;
  }

  get totalItemsCarrito(): number {
    return this.carrito.reduce((acc, item) => acc + item.cantidad, 0);
  }

  // --- TOTALES DE CONTEO APERTURA / CIERRE ---
  get totalConteoApertura(): number {
    const sum = this.conteoApertura.reduce((acc, fila) => acc + fila.subtotal, 0);
    return Math.round(sum * 100) / 100;
  }

  get totalConteoCierre(): number {
    const sum = this.conteoCierre.reduce((acc, fila) => acc + fila.subtotal, 0);
    return Math.round(sum * 100) / 100;
  }

  get diferenciaCierre(): number {
    if (!this.resumenCaja) return 0;
    const diff = this.totalConteoCierre - this.resumenCaja.efectivo_esperado;
    return Math.round(diff * 100) / 100;
  }

  get estadoDiferenciaCierre(): 'CUADRA' | 'SOBRANTE' | 'FALTANTE' {
    const diff = this.diferenciaCierre;
    if (Math.abs(diff) < 0.01) return 'CUADRA';
    if (diff > 0) return 'SOBRANTE';
    return 'FALTANTE';
  }

  ngOnInit(): void {
    const navigation = this.router.getCurrentNavigation();
    const state = navigation?.extras?.state || history.state;

    if (state?.reserva) {
      this.reservaContexto = state.reserva;
      this.idReservaActual = Number(state.reserva.id_reserva);
      this.reservaEnAtencion = true;
    }
    if (this.esSuperAdmin) {
      this.cargarEmpresas();
    }

    this.authService.companyChanged$
      .pipe(
        distinctUntilChanged((prev, curr) => prev?.id_empresa === curr?.id_empresa),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(() => {
        if (this.inicializado) {
          this.onContextoCambio();
        }
      });

    this.authService.branchChanged$
      .pipe(
        distinctUntilChanged((prev, curr) => prev?.id === curr?.id),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(() => {
        if (this.inicializado) {
          this.onContextoCambio();
        }
      });

    this.syncQueue.syncCompleted$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((batch) => {
        const ventasSync = (batch.results || []).filter(r => r.kind === 'VENTA_CONTADO' && r.status === 'synced');
        const ventasInc = (batch.results || []).filter(
          r => r.kind === 'VENTA_CONTADO' && (r.status === 'reconciliation_required' || r.reconciliation_required || r.status === 'conflict')
        );
        if (ventasSync.length > 0) {
          this.mostrarExito(`Se sincronizaron ${ventasSync.length} venta(s) en efectivo offline con el servidor.`);
        }
        if (ventasInc.length > 0) {
          this.mostrarError(
            ventasInc[0].message ||
            'Atención: una venta en efectivo offline requiere conciliación de caja.'
          );
        }
        this.cargarCatalogoPOS();
        if (this.estadoCaja?.sesion_activa) {
          this.consultarResumenCaja(this.estadoCaja.sesion_activa.id_sesion_caja);
          this.cargarVentasTurno();
        }
      });

    if (this.empresaRequerida) {
      this.cargando = false;
      this.inicializado = true;
      return;
    }

    this.ultimoContextoCargado = {
      empresaId: this.empresaActivaId || null,
      sucursalId: this.sucursalActiva?.id || null
    };
    this.cargarDatosIniciales();
    this.inicializado = true;
  }

  private ultimoContextoCargado: { empresaId: number | null; sucursalId: number | null } | null = null;

  onContextoCambio(): void {
    const currentEmpresaId = this.empresaActivaId || null;
    const currentSucursalId = this.sucursalActiva?.id || null;

    if (
      this.ultimoContextoCargado &&
      this.ultimoContextoCargado.empresaId === currentEmpresaId &&
      this.ultimoContextoCargado.sucursalId === currentSucursalId
    ) {
      // Contexto idéntico: prevenir bucles de recarga de POS y categorías
      return;
    }

    this.ultimoContextoCargado = {
      empresaId: currentEmpresaId,
      sucursalId: currentSucursalId
    };

    // Vaciar canasta para prevenir mezclas de inventarios entre distintas tiendas o sucursales
    this.vaciarCarrito();
    this.productos = [];
    this.variantesDelProducto = [];
    this.modalVariantesAbierto = false;

    if (this.empresaRequerida) {
      this.estadoCaja = null;
      this.cargando = false;
      this.cdr.detectChanges();
      return;
    }

    this.cargarDatosIniciales();
  }

  cargarEmpresas(): void {
    this.cargandoEmpresas = true;
    this.empresaService.listarEmpresas()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res: any) => {
          this.cargandoEmpresas = false;
          this.empresasDisponibles = (res?.data || []).filter((e: Empresa) => e.estado === 'ACTIVO');
          this.cdr.detectChanges();
        },
        error: () => {
          this.cargandoEmpresas = false;
          this.cdr.detectChanges();
        }
      });
  }

  seleccionarEmpresaDirecta(emp: Empresa): void {
    if (emp && emp.id_empresa) {
      this.authService.setSelectedCompany({
        id_empresa: emp.id_empresa,
        nombre_empresa: emp.nombre_empresa
      });
    }
  }

  cargarDatosIniciales(): void {
    this.cargando = true;
    this.cajaService.obtenerDenominaciones().subscribe({
      next: (res) => {
        if (res.success) {
          this.denominaciones = res.denominaciones;
          this.inicializarConteos();
        }
        this.verificarEstadoCaja();
      },
      error: (err) => {
        this.cargando = false;
        this.mostrarError('Error al cargar denominaciones de moneda: ' + (err.error?.message || err.message));
      }
    });

    this.cargarCategorias();
  }

  inicializarConteos(): void {
    this.conteoApertura = this.denominaciones.map(d => ({
      id_denominacion: d.id_denominacion,
      valor: d.valor,
      tipo: d.tipo,
      moneda: d.moneda,
      cantidad: 0,
      subtotal: 0.00
    }));

    this.conteoCierre = this.denominaciones.map(d => ({
      id_denominacion: d.id_denominacion,
      valor: d.valor,
      tipo: d.tipo,
      moneda: d.moneda,
      cantidad: 0,
      subtotal: 0.00
    }));
  }

  verificarEstadoCaja(callback?: () => void): void {
    if (this.empresaRequerida) {
      this.estadoCaja = null;
      this.cargando = false;
      this.cdr.detectChanges();
      return;
    }

    const idSucursal = this.sucursalActiva?.id;
    const idEmpresa = this.empresaActivaId || undefined;

    this.cajaService.obtenerEstadoCaja(idSucursal, idEmpresa).subscribe({
      next: (res) => {
        this.estadoCaja = res;
        this.cargando = false;
        if (res.tiene_sesion_activa && res.sesion_activa) {
          this.cargarCatalogoPOS();
          this.consultarResumenCaja(res.sesion_activa.id_sesion_caja);
          this.cargarVentasTurno();
          this.cargarCuotasContingencia();
        } else {
          // Pre-cargar catálogo de la sucursal seleccionada para consulta
          this.cargarCatalogoPOS();
        }
        if (callback) callback();
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.cargando = false;
        this.mostrarError('Error al consultar estado de caja: ' + (err.error?.message || err.message));
      }
    });
  }

  cargarCategorias(): void {
    this.categoriasService.listarCategorias({ solo_activas: true }).subscribe({
      next: (res: any) => {
        if (res && res.success && res.data && Array.isArray(res.data)) {
          this.categorias = res.data;
        } else if (res && res.success && res.categorias && Array.isArray(res.categorias)) {
          this.categorias = res.categorias;
        } else if (Array.isArray(res)) {
          this.categorias = res;
        }
      },
      error: (err: any) => {
        console.warn('Error al cargar categorías para filtro POS:', err);
      }
    });
  }

  // -------------------------------------------------------------
  // APERTURA DE CAJA
  // -------------------------------------------------------------
  abrirModalApertura(): void {
    if (!this.puedeAbrirCaja) {
      this.mostrarError('No tiene permisos para abrir caja.');
      return;
    }
    this.inicializarConteos();
    this.observacionApertura = '';
    this.modalAbrirAbierto = true;
  }

  cerrarModalApertura(): void {
    this.modalAbrirAbierto = false;
  }

  cambiarCantidadApertura(fila: ConteoFila, delta: number): void {
    const nuevaCant = Math.max(0, (fila.cantidad || 0) + delta);
    fila.cantidad = nuevaCant;
    fila.subtotal = Math.round(fila.cantidad * fila.valor * 100) / 100;
  }

  actualizarSubtotalApertura(fila: ConteoFila): void {
    if (!fila.cantidad || fila.cantidad < 0) {
      fila.cantidad = 0;
    }
    fila.subtotal = Math.round(fila.cantidad * fila.valor * 100) / 100;
  }

  confirmarAperturaCaja(): void {
    if (!this.estadoCaja?.caja_asignada) {
      this.mostrarError('No tiene una caja física asignada en su sucursal.');
      return;
    }

    const conteoItems = this.conteoApertura.map(f => ({
      id_denominacion: f.id_denominacion,
      cantidad: f.cantidad || 0
    }));

    this.procesando = true;
    this.cajaService.abrirCaja({
      id_caja: this.estadoCaja.caja_asignada.id_caja,
      id_sucursal: this.estadoCaja.caja_asignada.id_sucursal || this.sucursalActiva?.id,
      id_empresa: this.empresaActivaId || undefined,
      conteo: conteoItems,
      conteo_items: conteoItems,
      observacion: this.observacionApertura.trim() || undefined
    }).subscribe({
      next: (res) => {
        this.procesando = false;
        this.modalAbrirAbierto = false;
        this.mostrarExito(`Caja abierta exitosamente con un fondo de Bs. ${res.sesion.monto_inicial.toFixed(2)}.`);
        this.verificarEstadoCaja();
      },
      error: (err) => {
        this.procesando = false;
        this.mostrarError(err.error?.message || err.message || 'Error al abrir caja.');
      }
    });
  }

  // -------------------------------------------------------------
  // RESUMEN Y CIERRE DE CAJA (ARQUEO)
  // -------------------------------------------------------------
  consultarResumenCaja(idSesion: number, callback?: () => void): void {
    this.cajaService.obtenerResumenCaja(idSesion).subscribe({
      next: (res) => {
        if (res.success) {
          this.resumenCaja = res.resumen;
          if (callback) callback();
          this.cdr.detectChanges();
        }
      },
      error: (err) => {
        console.warn('Error al obtener resumen de caja:', err);
      }
    });
  }

  abrirModalResumen(): void {
    if (!this.estadoCaja?.sesion_activa) return;
    this.cargando = true;
    this.consultarResumenCaja(this.estadoCaja.sesion_activa.id_sesion_caja, () => {
      this.cargando = false;
      this.modalResumenAbierto = true;
    });
  }

  cerrarModalResumen(): void {
    this.modalResumenAbierto = false;
  }

  abrirModalCierre(): void {
    if (!this.puedeCerrarCaja) {
      this.mostrarError('No tiene permisos para cerrar caja.');
      return;
    }
    if (!this.estadoCaja?.sesion_activa) return;

    this.cargando = true;
    this.consultarResumenCaja(this.estadoCaja.sesion_activa.id_sesion_caja, () => {
      this.cargando = false;
      const esperadas = this.resumenCaja?.denominaciones_esperadas || [];
      const espMap = new Map<number, any>();
      esperadas.forEach(e => espMap.set(e.id_denominacion, e));

      this.conteoCierre = this.denominaciones.map(d => {
        const itemEsp = espMap.get(d.id_denominacion);
        const cantEsp = itemEsp ? Number(itemEsp.cantidad_esperada || 0) : 0;
        return {
          id_denominacion: d.id_denominacion,
          valor: d.valor,
          tipo: d.tipo,
          moneda: d.moneda,
          cantidad: 0,
          subtotal: 0.00,
          cantidad_esperada: cantEsp,
          subtotal_esperado: Math.round(cantEsp * d.valor * 100) / 100
        };
      });

      this.observacionCierre = '';
      this.modalCerrarAbierto = true;
    });
  }

  copiarEsperadoAContado(): void {
    for (const fila of this.conteoCierre) {
      fila.cantidad = fila.cantidad_esperada || 0;
      fila.subtotal = Math.round(fila.cantidad * fila.valor * 100) / 100;
    }
  }

  cerrarModalCierre(): void {
    this.modalCerrarAbierto = false;
  }

  cambiarCantidadCierre(fila: ConteoFila, delta: number): void {
    const nuevaCant = Math.max(0, (fila.cantidad || 0) + delta);
    fila.cantidad = nuevaCant;
    fila.subtotal = Math.round(fila.cantidad * fila.valor * 100) / 100;
  }

  actualizarSubtotalCierre(fila: ConteoFila): void {
    if (!fila.cantidad || fila.cantidad < 0) {
      fila.cantidad = 0;
    }
    fila.subtotal = Math.round(fila.cantidad * fila.valor * 100) / 100;
  }

  confirmarCierreCaja(): void {
    if (!this.estadoCaja?.sesion_activa) return;

    const conteoItems = this.conteoCierre.map(f => ({
      id_denominacion: f.id_denominacion,
      cantidad: f.cantidad || 0
    }));

    this.procesando = true;
    this.cajaService.cerrarCaja({
      id_sesion_caja: this.estadoCaja.sesion_activa.id_sesion_caja,
      conteo: conteoItems,
      conteo_items: conteoItems,
      observacion: this.observacionCierre.trim() || undefined
    }).subscribe({
      next: (res) => {
        this.procesando = false;
        this.modalCerrarAbierto = false;
        const diffText = res.cierre.diferencia === 0
          ? 'CUADRA EXACTO'
          : `${res.cierre.estado_diferencia}: Bs. ${Math.abs(res.cierre.diferencia).toFixed(2)}`;
        this.mostrarExito(`Caja cerrada correctamente. Efectivo contado: Bs. ${res.cierre.efectivo_contado.toFixed(2)} (${diffText}).`);
        this.vaciarCarrito();
        this.verificarEstadoCaja();
      },
      error: (err) => {
        this.procesando = false;
        this.mostrarError(err.error?.message || err.message || 'Error al cerrar caja.');
      }
    });
  }

  // -------------------------------------------------------------
  // CATÁLOGO POS Y BÚSQUEDA
  // -------------------------------------------------------------
  cargarCatalogoPOS(): void {
    if (this.empresaRequerida) {
      this.productos = [];
      this.cargandoCatalogo = false;
      return;
    }
    if (this.cargandoCatalogo) return;
    this.cargandoCatalogo = true;
    const idSucursal = this.sucursalActiva?.id;
    const idEmpresa = this.empresaActivaId || undefined;
    this.cajaService.buscarProductos(
      this.busquedaProducto,
      this.categoriaSeleccionadaId || undefined,
      idSucursal,
      idEmpresa
    ).subscribe({
      next: (res) => {
        this.cargandoCatalogo = false;
        if (res.success) {
          this.productos = res.productos;
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.cargandoCatalogo = false;
        console.warn('Error al buscar catálogo POS:', err);
      }
    });
  }

  seleccionarCategoria(idCategoria: number | null): void {
    this.categoriaSeleccionadaId = idCategoria;
    this.cargarCatalogoPOS();
  }

  onBuscarProductoChange(): void {
    if (this.searchTimer) {
      clearTimeout(this.searchTimer);
    }
    this.searchTimer = setTimeout(() => {
      this.cargarCatalogoPOS();
    }, 250);
  }

  limpiarBusqueda(): void {
    this.busquedaProducto = '';
    this.categoriaSeleccionadaId = null;
    this.cargarCatalogoPOS();
  }

  // -------------------------------------------------------------
  // GESTIÓN DE PRODUCTO / VARIANTE Y AGREGAR A LA VENTA
  // -------------------------------------------------------------
  seleccionarProducto(producto: ProductoPos): void {
    if (producto.stock_total_sucursal <= 0) {
      this.mostrarError(`El producto ${producto.nombre} no cuenta con stock disponible en esta sucursal.`);
      return;
    }

    this.cargandoVariantes = true;
    this.productoSeleccionadoParaVariante = producto;
    this.modalVariantesAbierto = true;

    const idSucursal = this.sucursalActiva?.id;
    const idEmpresa = this.empresaActivaId || undefined;

    this.cajaService.obtenerVariantesProducto(producto.id_producto, idSucursal, idEmpresa).subscribe({
      next: (res) => {
        this.cargandoVariantes = false;
        if (res.success) {
          this.variantesDelProducto = res.variantes;
          // Si solo hay una variante con stock disponible, se agrega directamente
          const disponibles = this.variantesDelProducto.filter(v => v.stock_disponible > 0);
          if (this.variantesDelProducto.length === 1 && disponibles.length === 1) {
            this.agregarVarianteAlCarrito(this.productoSeleccionadoParaVariante!, disponibles[0]);
            this.modalVariantesAbierto = false;
          }
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.cargandoVariantes = false;
        this.mostrarError('Error al obtener variantes: ' + (err.error?.message || err.message));
      }
    });
  }

  cerrarModalVariantes(): void {
    this.modalVariantesAbierto = false;
    this.productoSeleccionadoParaVariante = null;
    this.variantesDelProducto = [];
  }

  agregarVarianteAlCarrito(producto: ProductoPos, variante: VariantePos): void {
    if (variante.stock_disponible <= 0) {
      this.mostrarError(`La variante ${variante.talla_nombre || ''} / ${variante.color_nombre || ''} no tiene stock disponible.`);
      return;
    }

    const index = this.carrito.findIndex(item => item.variante.id_variante === variante.id_variante);
    if (index !== -1) {
      const item = this.carrito[index];
      if (item.cantidad + 1 > variante.stock_disponible) {
        this.mostrarError(`No es posible agregar más unidades. Stock disponible: ${variante.stock_disponible}.`);
        return;
      }
      item.cantidad += 1;
      item.subtotal = Math.round(item.cantidad * item.precioUnitario * 100) / 100;
    } else {
      this.carrito.push({
        variante: variante,
        productoNombre: producto.nombre,
        productoCodigo: producto.codigo,
        imagenUrl: producto.imagen_url,
        precioUnitario: variante.precio,
        cantidad: 1,
        subtotal: variante.precio,
        stockDisponible: variante.stock_disponible
      });
    }

    this.cerrarModalVariantes();
    this.validarDescuento();
    this.cdr.detectChanges();
  }

  // -------------------------------------------------------------
  // OPERACIONES SOBRE LA CANASTA DE VENTA
  // -------------------------------------------------------------
  incrementarCantidad(item: CartItem): void {
    if (item.cantidad + 1 > item.stockDisponible) {
      this.mostrarError(`Límite de stock alcanzado (${item.stockDisponible} disponibles).`);
      return;
    }
    item.cantidad += 1;
    item.subtotal = Math.round(item.cantidad * item.precioUnitario * 100) / 100;
    this.validarDescuento();
  }

  decrementarCantidad(item: CartItem): void {
    if (item.cantidad > 1) {
      item.cantidad -= 1;
      item.subtotal = Math.round(item.cantidad * item.precioUnitario * 100) / 100;
      this.validarDescuento();
    } else {
      this.eliminarItemCarrito(item);
    }
  }

  eliminarItemCarrito(item: CartItem): void {
    this.carrito = this.carrito.filter(i => i.variante.id_variante !== item.variante.id_variante);
    this.validarDescuento();
  }

  vaciarCarrito(): void {
    this.carrito = [];
    this.descuento = 0;
    this.clienteSeleccionado = null;
    this.tipoCliente = 'SIN_CLIENTE';
    this.observacionesVenta = '';
  }

  validarDescuento(): void {
    if (!this.descuento || this.descuento < 0) {
      this.descuento = 0;
      return;
    }
    if (this.descuento > this.subtotalCarrito) {
      this.descuento = this.subtotalCarrito;
      this.mostrarError('El descuento no puede superar el subtotal de la venta.');
    }
  }

  // -------------------------------------------------------------
  // BÚSQUEDA Y ASIGNACIÓN DE CLIENTE
  // -------------------------------------------------------------
  setTipoCliente(tipo: 'SIN_CLIENTE' | 'CON_CLIENTE'): void {
    this.tipoCliente = tipo;
    if (tipo === 'SIN_CLIENTE') {
      this.clienteSeleccionado = null;
      this.busquedaCliente = '';
      this.clientesResultados = [];
    }
  }

  buscarClientes(): void {
    if (!this.busquedaCliente || this.busquedaCliente.trim().length < 2) {
      this.clientesResultados = [];
      return;
    }

    this.buscandoClientes = true;
    const idEmpresa = this.empresaActivaId || undefined;
    this.cajaService.buscarClientes(this.busquedaCliente, idEmpresa).subscribe({
      next: (res) => {
        this.buscandoClientes = false;
        if (res.success) {
          this.clientesResultados = res.clientes;
        }
      },
      error: (err) => {
        this.buscandoClientes = false;
        console.warn('Error al buscar clientes:', err);
      }
    });
  }

  seleccionarCliente(cliente: ClientePos): void {
    this.clienteSeleccionado = cliente;
    this.busquedaCliente = '';
    this.clientesResultados = [];
  }

  quitarCliente(): void {
    this.clienteSeleccionado = null;
  }

  // -------------------------------------------------------------
  // REGISTRAR VENTA POS (TRANSACCIÓN)
  // -------------------------------------------------------------
  abrirModalConfirmarVenta(): void {
    if (!this.estadoCaja?.tiene_sesion_activa || !this.estadoCaja.sesion_activa) {
      this.mostrarError('No puede registrar ventas sin una caja abierta.');
      return;
    }

    if (this.carrito.length === 0) {
      this.mostrarError('La canasta de venta está vacía. Agregue productos para continuar.');
      return;
    }

    this.validarDescuento();
    this.montoRecibidoEfectivo = this.totalCarrito;
    this.nitCiFacturacionOffline = this.clienteSeleccionado?.nit_ci || 'S/N';
    this.razonSocialFacturacionOffline = this.clienteSeleccionado?.nombre_completo || 'SIN NOMBRE';
    this.modalidadCobroConfirmacion = this.networkStatus.isOnline() ? 'PASO_W28_ONLINE' : 'EFECTIVO_INMEDIATO';
    this.modalConfirmarVentaAbierto = true;
  }

  cargarCuotasContingencia(): void {
    const sesionId = this.estadoCaja?.sesion_activa?.id_sesion_caja;
    if (!sesionId || !this.networkStatus.isOnline()) return;
    this.cajaService.obtenerCuotasContingencia(sesionId).subscribe({
      next: (res) => {
        if (res?.cuotas) {
          console.info(`[POS Contingencia] ${res.cuotas.length} cuotas de contingencia sincronizadas.`);
        }
      },
      error: (err) => console.warn('[POS Contingencia] Aviso al descargar cuotas:', err)
    });
  }

  imprimirTicketProvisional(): void {
    if (typeof window !== 'undefined') {
      window.print();
    }
  }

  fijarMontoRecibidoRapido(monto: number): void {
    this.montoRecibidoEfectivo = Math.round(monto * 100) / 100;
  }

  cerrarModalConfirmarVenta(): void {
    this.modalConfirmarVentaAbierto = false;
  }

  procesarVentaPos(): void {
    if (!this.estadoCaja?.sesion_activa) return;

    // Si estamos sin conexión o el cajero eligió cobro directo en efectivo (CU24W)
    if (!this.networkStatus.isOnline() || this.modalidadCobroConfirmacion === 'EFECTIVO_INMEDIATO') {
      if (!this.montoEfectivoValido) {
        this.mostrarError(
          `El monto recibido en efectivo (Bs. ${(Number(this.montoRecibidoEfectivo) || 0).toFixed(2)}) debe cubrir el total a pagar (Bs. ${this.totalCarrito.toFixed(2)}).`
        );
        return;
      }
      void this.ejecutarVentaEfectivoOffline();
      return;
    }

    const payloadItems = this.carrito.map(item => ({
      id_variante: item.variante.id_variante,
      cantidad: item.cantidad
    }));

    this.procesando = true;
    this.cajaService.registrarVentaPos({
      id_sesion_caja: this.estadoCaja.sesion_activa.id_sesion_caja,
      id_cliente: this.clienteSeleccionado
        ? this.clienteSeleccionado.id_cliente
        : null,
      id_empresa: this.empresaActivaId || undefined,
      id_sucursal: this.sucursalActiva?.id,
      id_reserva: this.idReservaActual,
      items: payloadItems,
      descuento: this.descuento || 0.00,
      observaciones: this.observacionesVenta.trim() || undefined
    }).subscribe({
      next: (res) => {
        this.procesando = false;
        this.modalConfirmarVentaAbierto = false;
        this.ventaExitosaInfo = {
          id_venta: res.venta.id_venta,
          codigo_venta: res.venta.codigo_venta,
          total: res.venta.total,
          cant_items: this.totalItemsCarrito,
          offline_queued: false
        };
        this.modalVentaExitosaAbierto = true;

        // Limpiar canasta y actualizar stock de catálogo
        this.vaciarCarrito();
        this.cargarCatalogoPOS();
        this.consultarResumenCaja(this.estadoCaja!.sesion_activa!.id_sesion_caja);
        this.cargarVentasTurno();
      },
      error: (err) => {
        if (err?.status === 0) {
          this.montoRecibidoEfectivo = Math.max(Number(this.montoRecibidoEfectivo) || 0, this.totalCarrito);
          void this.ejecutarVentaEfectivoOffline();
          return;
        }
        this.procesando = false;
        this.mostrarError(err.error?.message || err.message || 'Error al procesar la venta.');
      }
    });
  }

  private async ejecutarVentaEfectivoOffline(): Promise<void> {
    if (!this.estadoCaja?.sesion_activa) return;
    this.procesando = true;
    this.cdr.detectChanges();

    try {
      // CU38W / Validación de cuota de contingencia offline local (IndexedDB)
      const sesionId = this.estadoCaja.sesion_activa.id_sesion_caja;
      let posibleSobreventa = false;
      const advertenciasCuota: string[] = [];

      for (const item of this.carrito) {
        const cuota = await this.cajaService.obtenerCuotaContingenciaLocal(sesionId, item.variante.id_variante);
        if (cuota !== null && item.cantidad > cuota) {
          posibleSobreventa = true;
          advertenciasCuota.push(
            `• ${item.productoNombre} (${item.variante.talla_nombre || 'Talla única'}/${item.variante.color_nombre || 'Color único'}): Solicitado ${item.cantidad}, Cuota autorizada ${cuota}.`
          );
        }
      }

      if (posibleSobreventa) {
        const confirmar = confirm(
          `⚠️ ALERTA DE CUOTA DE CONTINGENCIA POS:\n\n` +
          `Las siguientes prendas superan la cuota offline autorizada para esta caja:\n\n` +
          advertenciasCuota.join('\n') +
          `\n\n¿Desea registrar la venta provisional de todos modos bajo observación de posible sobreventa?`
        );
        if (!confirmar) {
          this.procesando = false;
          this.cdr.detectChanges();
          return;
        }
      }

      const obsFinal = posibleSobreventa
        ? `[SOBREVENTA_CONTINGENCIA] ${this.observacionesVenta.trim()}`.trim()
        : (this.observacionesVenta.trim() || undefined);

      const payloadItems = this.carrito.map(item => ({
        id_variante: item.variante.id_variante,
        cantidad: item.cantidad,
        expected_unit_price: item.precioUnitario,
        producto_nombre: item.productoNombre,
        talla: item.variante.talla_nombre || 'Única',
        color: item.variante.color_nombre || 'Estándar',
        sku: item.variante.sku
      }));

      const cantTotal = this.totalItemsCarrito;
      const res = await this.cajaService.registrarVentaContadoOffline({
        id_sesion_caja: this.estadoCaja.sesion_activa.id_sesion_caja,
        id_cliente: this.clienteSeleccionado ? this.clienteSeleccionado.id_cliente : null,
        id_empresa: this.empresaActivaId || undefined,
        id_sucursal: this.sucursalActiva?.id,
        items: payloadItems,
        descuento: this.descuento || 0,
        observaciones: obsFinal,
        metodo_tipo: 'EFECTIVO',
        monto_recibido: Number(this.montoRecibidoEfectivo) || this.totalCarrito,
        expected_total: this.totalCarrito,
        nit_ci: (this.nitCiFacturacionOffline || 'S/N').trim(),
        razon_social: (this.razonSocialFacturacionOffline || 'SIN NOMBRE').trim()
      });

      this.procesando = false;
      this.modalConfirmarVentaAbierto = false;
      this.ventaExitosaInfo = {
        id_venta: res.venta.id_venta,
        codigo_venta: res.venta.codigo_venta,
        total: res.venta.total,
        cant_items: cantTotal,
        offline_queued: true,
        monto_recibido: res.venta.monto_recibido,
        cambio: res.venta.cambio
      };
      this.modalVentaExitosaAbierto = true;

      this.vaciarCarrito();
      this.cargarCatalogoPOS();
      this.consultarResumenCaja(this.estadoCaja.sesion_activa.id_sesion_caja);
      this.cargarVentasTurno();
      this.cdr.detectChanges();
    } catch (err: any) {
      this.procesando = false;
      this.mostrarError(err?.message || 'No se pudo registrar la venta en efectivo offline.');
      this.cdr.detectChanges();
    }
  }

  cerrarModalVentaExitosa(): void {
    this.modalVentaExitosaAbierto = false;
    this.ventaExitosaInfo = null;
  }

  irACobrar(idVenta: number): void {
    this.cerrarModalVentaExitosa();
    this.modalHistorialAbierto = false;
    this.modalDetalleVentaAbierto = false;
    this.router.navigate(['/admin/caja/pago', idVenta]);
  }

  irAComprobante(idVenta: number): void {
    this.modalHistorialAbierto = false;
    this.modalDetalleVentaAbierto = false;
    this.router.navigate(['/admin/caja/comprobante', idVenta]);
  }

  // -------------------------------------------------------------
  // HISTORIAL Y VENTAS DEL TURNO (ACCESO DIRECTO A COBROS)
  // -------------------------------------------------------------
  get ventasPendientesTurno(): VentaPosItem[] {
    return (this.ventasTurno || []).filter(v => v.estado === 'PENDIENTE_PAGO');
  }

  cargarVentasTurno(callback?: () => void): void {
    if (!this.estadoCaja?.sesion_activa) return;
    this.cajaService.obtenerHistorialVentas(this.estadoCaja.sesion_activa.id_sesion_caja).subscribe({
      next: (res) => {
        if (res.success && res.ventas) {
          this.ventasTurno = res.ventas;
          if (callback) callback();
          this.cdr.detectChanges();
        }
      },
      error: (err) => {
        console.warn('Error al cargar ventas del turno:', err);
      }
    });
  }

  activarPestanaCobrosPendientes(): void {
    this.pestanaDerecha = 'POR_COBRAR';
    this.cargarVentasTurno();
  }

  abrirModalHistorial(): void {
    if (!this.estadoCaja?.sesion_activa) return;
    this.cargandoHistorial = true;
    this.modalHistorialAbierto = true;
    this.cajaService.obtenerHistorialVentas(this.estadoCaja.sesion_activa.id_sesion_caja).subscribe({
      next: (res) => {
        this.cargandoHistorial = false;
        if (res.success) {
          this.ventasTurno = res.ventas;
        }
      },
      error: (err) => {
        this.cargandoHistorial = false;
        this.mostrarError('Error al obtener historial: ' + (err.error?.message || err.message));
      }
    });
  }

  cerrarModalHistorial(): void {
    this.modalHistorialAbierto = false;
  }

  verDetalleVenta(idVenta: number): void {
    if (idVenta < 0) {
      const localVenta = this.ventasTurno.find(v => v.id_venta === idVenta);
      const localOp = localVenta?.offline_operation_id
        ? this.syncQueue.operations().find(o => o.operation_id === localVenta.offline_operation_id)
        : undefined;
      if (localVenta) {
        const items = Array.isArray(localOp?.payload?.['items']) ? localOp!.payload['items'] : [];
        this.ventaDetalleSeleccionada = {
          id_venta: localVenta.id_venta,
          codigo_venta: localVenta.codigo_venta,
          cliente: localVenta.cliente,
          cajero: localVenta.cajero,
          fecha: localVenta.fecha,
          estado: localVenta.estado,
          total: localVenta.total,
          offline_conflict_message: localVenta.offline_conflict_message,
          detalles: items.map((it: any) => ({
            producto: it.producto_nombre || `Variante #${it.id_variante}`,
            talla: it.talla || '',
            color: it.color || '',
            sku: it.sku || '',
            cantidad: Number(it.cantidad || 1),
            precio_unitario: Number(it.expected_unit_price || 0),
            subtotal: Math.round(Number(it.cantidad || 1) * Number(it.expected_unit_price || 0) * 100) / 100
          }))
        };
        this.modalDetalleVentaAbierto = true;
      }
      return;
    }

    this.cajaService.obtenerDetalleVenta(idVenta).subscribe({
      next: (res) => {
        if (res.success) {
          this.ventaDetalleSeleccionada = res.venta;
          this.modalDetalleVentaAbierto = true;
        }
      },
      error: (err) => {
        this.mostrarError('Error al obtener detalle de venta: ' + (err.error?.message || err.message));
      }
    });
  }

  cerrarModalDetalleVenta(): void {
    this.modalDetalleVentaAbierto = false;
    this.ventaDetalleSeleccionada = null;
  }

  // -------------------------------------------------------------
  // MENSAJES Y NOTIFICACIONES
  // -------------------------------------------------------------
  mostrarExito(msg: string): void {
    this.mensajeExito = msg;
    this.mensajeError = '';
    setTimeout(() => {
      if (this.mensajeExito === msg) this.mensajeExito = '';
      this.cdr.detectChanges();
    }, 6000);
  }

  mostrarError(msg: any): void {
    this.mensajeError = typeof msg === 'string' ? msg : extraerMensajeError(msg);
    this.mensajeExito = '';
    setTimeout(() => {
      this.mensajeError = '';
      this.cdr.detectChanges();
    }, 7000);
  }
}
