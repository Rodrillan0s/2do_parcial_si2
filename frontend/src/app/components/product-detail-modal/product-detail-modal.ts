import { Component, Input, Output, EventEmitter, inject, OnChanges, SimpleChanges, OnDestroy, ChangeDetectorRef, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth';
import { CarritoService } from '../../services/carrito';
import { ReservaService } from '../../services/reserva';
import { DetallePrendaCatalogo, VarianteDetalle, SucursalStockDetalle } from '../../services/catalogo-publico';
import { SyncQueueService } from '../../core/sync/sync-queue.service';
import { ValoracionService, ResumenValoracionesProducto } from '../../services/valoracion';

// Interfaz retrocompatible para páginas estáticas previas
export interface ProductoFashion {
  id: number;
  nombre: string;
  subtitulo?: string;
  precio: number;
  precioAnterior?: number;
  categoria: string;
  imagenPrincipal: string;
  imagenes: string[];
  tallas: string[];
  colores: { nombre: string; hex: string }[];
  descripcion: string;
  especificaciones?: string[];
  sucursalesDisponibles?: string[];
  etiqueta?: string;
  popularidad?: number;
}

@Component({
  selector: 'app-product-detail-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './product-detail-modal.html',
  styles: [`
    :host {
      display: contents;
    }
  `]
})
export class ProductDetailModalComponent implements OnChanges, OnDestroy {
  @Input() producto: DetallePrendaCatalogo | ProductoFashion | null = null;
  @Input() modoInicial: 'PRODUCTO' | 'AGENDAR_CITA' = 'PRODUCTO';
  @Output() close = new EventEmitter<void>();

  public authService = inject(AuthService);
  public carritoService = inject(CarritoService);
  public reservaService = inject(ReservaService);
  public syncQueue = inject(SyncQueueService);
  public router = inject(Router);
  public valoracionService = inject(ValoracionService);
  private cdr = inject(ChangeDetectorRef);

  // Resumen de valoraciones del producto
  resumenValoraciones: ResumenValoracionesProducto | null = null;
  cargandoValoraciones: boolean = false;

  // Estados visuales de selección
  selectedImageIndex: number = 0;
  selectedSizeName: string = '';
  selectedColorHex: string = '';
  quantity: number = 1;

  // Estados de feedback de Bolsa
  cargandoBolsa: boolean = false;
  addedToast: boolean = false;
  toastEsError: boolean = false;
  toastMessage: string = '';

  // Vista actual del modal: 'PRODUCTO' (limpio, compra online) | 'AGENDAR_CITA' (probar en tienda)
  vistaModal: 'PRODUCTO' | 'AGENDAR_CITA' = 'PRODUCTO';

  // Estados del flujo de Reserva en Sucursal
  sucursalReservaSeleccionada: number | null = null;
  fechaReserva: string = '';
  horaReserva: string = '15:00';
  observacionesReserva: string = '';
  cargandoReserva: boolean = false;
  errorReserva: string = '';
  reservaExitosa: boolean = false;
  reservaEnColaOffline: boolean = false;
  codigoReservaGenerado: string = '';
  modalidadReserva: 'SIN_PAGO' | 'CON_PAGO' = 'SIN_PAGO';
  montoReservaPagado: number = 0;

  // Vista RA (Opcional)
  mostrarVistaRA: boolean = false;

  @HostListener('window:keydown.escape')
  onEscapePress(): void {
    if (this.producto) {
      this.closeModal();
    }
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['producto'] && this.producto) {
      this.selectedImageIndex = 0;
      this.quantity = 1;
      this.mostrarVistaRA = false;
      this.reservaExitosa = false;
      this.vistaModal = this.modoInicial || 'PRODUCTO';
      this.errorReserva = '';
      this.codigoReservaGenerado = '';

      // Bloquear scroll de la página de fondo
      this.bloquearBodyScroll();

      // Inicializar con la primera variante real disponible
      if (this.esDetalleReal(this.producto) && this.producto.variantes && this.producto.variantes.length > 0) {
        const v = this.producto.variantes[0];
        this.selectedSizeName = v.talla_nombre;
        this.selectedColorHex = v.codigo_hex;
      } else {
        const tallas = this.getTallas();
        if (tallas.length > 0) {
          this.selectedSizeName = tallas[0].nombre;
        }
        const colores = this.getColores();
        if (colores.length > 0) {
          this.selectedColorHex = colores[0].hex;
        }
      }

      // Inicializar parámetros de la reserva en tienda
      this.inicializarDatosReserva();

      // Cargar valoraciones reales del producto
      const prodId = (this.producto as any).id_producto || (this.producto as any).id;
      if (prodId) {
        this.cargarValoraciones(prodId);
      }

      this.cdr.markForCheck();
    }
  }

  ngOnDestroy(): void {
    this.desbloquearBodyScroll();
  }

  private bloquearBodyScroll(): void {
    try {
      if (typeof document !== 'undefined') {
        document.body.style.overflow = 'hidden';
      }
    } catch (_) { }
  }

  private desbloquearBodyScroll(): void {
    try {
      if (typeof document !== 'undefined') {
        document.body.style.overflow = '';
      }
    } catch (_) { }
  }

  cargarValoraciones(idProducto: number): void {
    this.cargandoValoraciones = true;
    this.valoracionService.obtenerValoracionesProducto(idProducto).subscribe({
      next: (res) => {
        this.cargandoValoraciones = false;
        if (res && res.success && res.data) {
          this.resumenValoraciones = res.data;
        } else {
          this.resumenValoraciones = null;
        }
        this.cdr.markForCheck();
      },
      error: () => {
        this.cargandoValoraciones = false;
        this.resumenValoraciones = null;
        this.cdr.markForCheck();
      }
    });
  }

  inicializarDatosReserva(): void {
    // Fecha sugerida: mañana
    const manana = new Date();
    manana.setDate(manana.getDate() + 1);
    this.fechaReserva = manana.toISOString().split('T')[0];
    this.horaReserva = '15:00';
    this.observacionesReserva = '';
    this.errorReserva = '';
    this.reservaExitosa = false;
    this.cargandoReserva = false;
    this.modalidadReserva = 'SIN_PAGO';
    this.montoReservaPagado = 0;

    // Seleccionar por defecto la primera sucursal con existencias
    const sucs = this.getSucursalesStock();
    const sucConStock = sucs.find(s => this.getStockVarianteEnSucursal(s) > 0);
    this.sucursalReservaSeleccionada = sucConStock ? sucConStock.id_sucursal : null;
  }

  // Detectar si el producto recibido es del catálogo real (DetallePrendaCatalogo)
  esDetalleReal(p: any): p is DetallePrendaCatalogo {
    return p && ('id_producto' in p || 'variantes' in p);
  }

  getImagenes(): string[] {
    if (!this.producto) return [];
    if (this.esDetalleReal(this.producto)) {
      if (this.producto.imagenes && this.producto.imagenes.length > 0) {
        return this.producto.imagenes.map(img => img.imagen_url);
      }
      return this.producto.imagen_principal ? [this.producto.imagen_principal] : ['https://images.unsplash.com/photo-1539109136881-3be0616acf4b?auto=format&fit=crop&w=800&q=80'];
    }
    return this.producto.imagenes || (this.producto.imagenPrincipal ? [this.producto.imagenPrincipal] : []);
  }

  getTallas(): { id?: number; nombre: string }[] {
    if (!this.producto) return [];
    if (this.esDetalleReal(this.producto)) {
      return this.producto.tallas || [];
    }
    return (this.producto.tallas || []).map(t => ({ nombre: t }));
  }

  getColores(): { id?: number; nombre: string; hex: string }[] {
    if (!this.producto) return [];
    if (this.esDetalleReal(this.producto)) {
      return (this.producto.colores || []).map(c => ({
        id: c.id_color,
        nombre: c.nombre,
        hex: c.codigo_hex
      }));
    }
    return this.producto.colores || [];
  }

  getVarianteSeleccionada(): VarianteDetalle | null {
    if (!this.producto || !this.esDetalleReal(this.producto)) return null;
    const variantes = this.producto.variantes || [];
    const match = variantes.find(v =>
      v.talla_nombre === this.selectedSizeName &&
      v.codigo_hex.toLowerCase() === this.selectedColorHex.toLowerCase()
    );
    return match || (variantes.length > 0 ? variantes[0] : null);
  }

  esCombinacionValida(): boolean {
    if (!this.producto || !this.esDetalleReal(this.producto)) return true;
    return this.getVarianteSeleccionada() !== null;
  }

  getPrecioActual(): number {
    const v = this.getVarianteSeleccionada();
    if (v && v.precio) return v.precio;
    if (this.producto) return this.producto.precio;
    return 0;
  }

  getPrecioTalla(tallaNombre: string): number | null {
    if (!this.producto || !this.esDetalleReal(this.producto) || !this.producto.variantes) return null;
    const variante = this.producto.variantes.find(v => v.talla_nombre === tallaNombre);
    return variante && variante.precio ? variante.precio : null;
  }

  getSucursalesStock(): SucursalStockDetalle[] {
    if (!this.producto || !this.esDetalleReal(this.producto)) return [];
    return this.producto.sucursales_stock || [];
  }

  getStockVarianteEnSucursal(suc: SucursalStockDetalle): number {
    const v = this.getVarianteSeleccionada();
    if (!v) return 0;
    const keyStr = v.id_variante.toString();
    const keyNum = v.id_variante;
    const val = suc.stock_por_variante?.[keyStr] ?? suc.stock_por_variante?.[keyNum as any] ?? 0;
    const provisionalDelta = this.syncQueue.getProvisionalDeltaForVariant(v.id_variante, suc.id_sucursal);
    return Math.max(0, val - provisionalDelta);
  }

  getStockTotalVarianteSeleccionada(): number {
    const v = this.getVarianteSeleccionada();
    if (!v) return 0;
    const sucs = this.getSucursalesStock();
    return sucs.reduce((acc, s) => acc + this.getStockVarianteEnSucursal(s), 0);
  }

  getStockSucursalSeleccionada(): number {
    if (!this.sucursalReservaSeleccionada) return 0;
    const suc = this.getSucursalesStock().find(s => s.id_sucursal === Number(this.sucursalReservaSeleccionada));
    if (!suc) return 0;
    return this.getStockVarianteEnSucursal(suc);
  }

  getSucursalSeleccionadaObj(): SucursalStockDetalle | undefined {
    if (!this.sucursalReservaSeleccionada) return undefined;
    return this.getSucursalesStock().find(s => s.id_sucursal === Number(this.sucursalReservaSeleccionada));
  }

  /**
   * REGLAS DE STOCK DE BOUTIQUE (Sin números crudos):
   * stock > 3   → ✓ Disponible
   * stock 1–3   → ⚠ Últimas unidades
   * stock = 0   → Agotado
   */
  getEstadoDisponibilidad(stock: number): {
    texto: string;
    clase: string;
    badgeClase: string;
    icono: string;
    esAgotado: boolean;
    esUltimas: boolean;
  } {
    if (stock > 3) {
      return {
        texto: 'Disponible',
        clase: 'text-emerald-700 dark:text-emerald-400',
        badgeClase: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/25',
        icono: '✓',
        esAgotado: false,
        esUltimas: false
      };
    }
    if (stock >= 1 && stock <= 3) {
      return {
        texto: 'Últimas unidades',
        clase: 'text-amber-800 dark:text-amber-300 font-semibold',
        badgeClase: 'bg-amber-500/15 text-amber-800 dark:text-amber-300 border-amber-500/40 font-bold',
        icono: '⚠',
        esAgotado: false,
        esUltimas: true
      };
    }
    return {
      texto: 'Agotado',
      clase: 'text-zinc-500 dark:text-zinc-400',
      badgeClase: 'bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 border-zinc-300 dark:border-zinc-700',
      icono: '✕',
      esAgotado: true,
      esUltimas: false
    };
  }

  getEstadoVarianteActual() {
    return this.getEstadoDisponibilidad(this.getStockTotalVarianteSeleccionada());
  }

  getEstadoSucursal(suc: SucursalStockDetalle): string {
    const st = this.getStockVarianteEnSucursal(suc);
    if (st > 3) return '✓ Disponible';
    if (st >= 1 && st <= 3) return '⚠ Últimas unidades';
    return '✕ Agotado en esta sucursal';
  }

  getStockTallaEnColorActual(tallaNombre: string): number {
    if (!this.producto || !this.esDetalleReal(this.producto)) return 99;
    const v = (this.producto.variantes || []).find(varItem =>
      varItem.talla_nombre === tallaNombre &&
      varItem.codigo_hex.toLowerCase() === this.selectedColorHex.toLowerCase()
    );
    if (!v) return 0;
    const sucs = this.getSucursalesStock();
    const keyStr = v.id_variante.toString();
    return sucs.reduce((acc, s) => acc + (s.stock_por_variante?.[keyStr] ?? s.stock_por_variante?.[v.id_variante as any] ?? 0), 0);
  }

  isTallaAgotada(tallaNombre: string): boolean {
    return this.getStockTallaEnColorActual(tallaNombre) <= 0;
  }

  isTallaUltimas(tallaNombre: string): boolean {
    const st = this.getStockTallaEnColorActual(tallaNombre);
    return st >= 1 && st <= 3;
  }

  abrirAgendarCita(): void {
    if (!this.authService.estaAutenticado()) {
      this.authService.openAuthModal('login');
      return;
    }
    this.errorReserva = '';
    this.vistaModal = 'AGENDAR_CITA';
    this.cdr.markForCheck();
  }

  volverAProducto(): void {
    this.vistaModal = 'PRODUCTO';
    this.cdr.markForCheck();
  }

  selectImage(idx: number): void {
    this.selectedImageIndex = idx;
  }

  selectSize(sizeName: string): void {
    this.selectedSizeName = sizeName;
    if (this.esDetalleReal(this.producto) && this.producto.variantes) {
      const matchExacto = this.producto.variantes.find(v =>
        v.talla_nombre === sizeName && v.codigo_hex.toLowerCase() === this.selectedColorHex.toLowerCase()
      );
      if (!matchExacto) {
        const primerColorDeTalla = this.producto.variantes.find(v => v.talla_nombre === sizeName);
        if (primerColorDeTalla) {
          this.selectedColorHex = primerColorDeTalla.codigo_hex;
        }
      }
    }
    this.verificarStockSucursalActual();
    this.cdr.markForCheck();
  }

  selectColor(hex: string): void {
    this.selectedColorHex = hex;
    if (this.esDetalleReal(this.producto) && this.producto.variantes) {
      const matchExacto = this.producto.variantes.find(v =>
        v.codigo_hex.toLowerCase() === hex.toLowerCase() && v.talla_nombre === this.selectedSizeName
      );
      if (!matchExacto) {
        const primeraTallaDeColor = this.producto.variantes.find(v => v.codigo_hex.toLowerCase() === hex.toLowerCase());
        if (primeraTallaDeColor) {
          this.selectedSizeName = primeraTallaDeColor.talla_nombre;
        }
      }
    }
    this.verificarStockSucursalActual();
    this.cdr.markForCheck();
  }

  private verificarStockSucursalActual(): void {
    // Si la sucursal actual no tiene stock para la nueva combinación, auto-seleccionar una que sí tenga
    if (this.getStockSucursalSeleccionada() <= 0) {
      const sucs = this.getSucursalesStock();
      const sucConStock = sucs.find(s => this.getStockVarianteEnSucursal(s) > 0);
      this.sucursalReservaSeleccionada = sucConStock ? sucConStock.id_sucursal : null;
    }
  }

  haySucursalConStock(): boolean {
    return this.getSucursalesStock().some(s => this.getStockVarianteEnSucursal(s) > 0);
  }

  onSucursalChange(id: any): void {
    this.sucursalReservaSeleccionada = Number(id);
    this.errorReserva = '';
    this.cdr.markForCheck();
  }

  incrementQuantity(): void {
    const max = this.getStockSucursalSeleccionada() || this.getStockTotalVarianteSeleccionada() || 99;
    if (this.quantity < max) {
      this.quantity++;
      this.cdr.markForCheck();
    }
  }

  decrementQuantity(): void {
    if (this.quantity > 1) {
      this.quantity--;
      this.cdr.markForCheck();
    }
  }

  // ============================================================================
  // FLUJO DE RESERVA DIRECTO (APARTAR EN TIENDA)
  // ============================================================================
  reservarCita(): void {
    this.errorReserva = '';

    // 1. Si no está autenticado, abrir inmediatamente el modal de inicio de sesión / registro
    if (!this.authService.estaAutenticado()) {
      this.errorReserva = '✦ Inicia sesión o regístrate para apartar tu prenda y confirmar tu visita a tu nombre.';
      this.authService.openAuthModal('login');
      this.cdr.markForCheck();
      return;
    }

    // 2. Validar sucursal seleccionada
    if (!this.sucursalReservaSeleccionada || this.getStockSucursalSeleccionada() <= 0) {
      this.errorReserva = 'Por favor selecciona una sucursal con disponibilidad de stock.';
      this.cdr.markForCheck();
      return;
    }

    // 3. Validar fecha de visita
    if (!this.fechaReserva) {
      this.errorReserva = 'Por favor selecciona la fecha programada para tu visita.';
      this.cdr.markForCheck();
      return;
    }

    // 4. Validar variante seleccionada
    let v = this.getVarianteSeleccionada();
    if (!v && this.esDetalleReal(this.producto) && this.producto.variantes?.length) {
      v = this.producto.variantes[0];
      this.selectedSizeName = v.talla_nombre;
      this.selectedColorHex = v.codigo_hex;
    }
    if (!v) {
      this.errorReserva = 'Por favor selecciona una talla y color disponibles antes de reservar.';
      this.cdr.markForCheck();
      return;
    }

    // 5. Validar disponibilidad real en inventario
    const stockDisponible = this.getStockSucursalSeleccionada();
    if (stockDisponible <= 0) {
      this.errorReserva = 'La variante seleccionada no cuenta con existencias en esta tienda. Por favor selecciona otra sucursal.';
      this.cdr.markForCheck();
      return;
    }

    if (this.quantity > stockDisponible) {
      this.errorReserva = `Solo puedes apartar hasta ${stockDisponible} unidad(es) según el stock de esta tienda.`;
      this.cdr.markForCheck();
      return;
    }

    // 6. Preparar payload y ejecutar la reserva en backend
    const fechaHora = `${this.fechaReserva} ${this.horaReserva || '15:00'}`;
    const empresaId = this.esDetalleReal(this.producto) 
      ? (this.producto.id_empresa || (this.producto as any).empresa_id) 
      : ((this.producto as any)?.id_empresa || (this.producto as any)?.empresa_id || undefined);
    const esConPago = false;
    const totalPagar = 0.0;

    this.cargandoReserva = true;
    this.reservaEnColaOffline = false;
    this.cdr.markForCheck();

    const sucObj = this.getSucursalSeleccionadaObj();
    const precioUnitarioActual = this.getPrecioActual();
    const imgPrincipal = this.getImagenes()[this.selectedImageIndex] || this.getImagenes()[0] || null;

    this.reservaService.crearReserva(
      {
        id_sucursal: Number(this.sucursalReservaSeleccionada),
        fecha_hora_visita: fechaHora,
        observaciones: this.observacionesReserva || undefined,
        items: [{
          id_variante: v.id_variante,
          cantidad: this.quantity,
          expected_unit_price: precioUnitarioActual,
          producto_nombre: this.producto?.nombre,
          talla: v.talla_nombre,
          color: v.color_nombre,
          codigo_hex: v.codigo_hex,
          imagen_url: imgPrincipal
        }],
        id_empresa: empresaId,
        con_pago: esConPago,
        monto_pagado: esConPago ? totalPagar : 0.0
      },
      {
        productoNombre: this.producto?.nombre,
        sucursalNombre: sucObj?.nombre,
        sucursalDireccion: sucObj?.direccion,
        sucursalCiudad: sucObj?.ciudad,
        talla: v.talla_nombre,
        color: v.color_nombre,
        codigoHex: v.codigo_hex,
        imagenUrl: imgPrincipal,
        expectedUnitPrice: precioUnitarioActual
      }
    ).subscribe({
      next: (res) => {
        this.cargandoReserva = false;
        this.reservaExitosa = true;
        this.reservaEnColaOffline = Boolean(res.offline_queued);
        this.codigoReservaGenerado = res.data.codigo_reserva;
        this.montoReservaPagado = esConPago && !res.offline_queued ? totalPagar : 0.0;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.cargandoReserva = false;
        this.errorReserva = err?.error?.detail || 'No se pudo completar la reserva. Verifica disponibilidad de stock.';
        this.cdr.markForCheck();
      }
    });
  }

  // ============================================================================
  // FLUJO DE BOLSA DE COMPRAS (CARRITO)
  // ============================================================================
  addToCart(abrirDrawerAlFinalizar: boolean = false): void {
    if (!this.authService.estaAutenticado()) {
      this.toastEsError = true;
      this.toastMessage = 'Inicia sesión para guardar prendas en tu bolsa de compras.';
      this.addedToast = true;
      this.cdr.markForCheck();
      setTimeout(() => {
        this.addedToast = false;
        this.cdr.markForCheck();
      }, 3500);
      this.authService.openAuthModal('login');
      return;
    }

    let v = this.getVarianteSeleccionada();
    if (!v && this.esDetalleReal(this.producto) && this.producto.variantes?.length) {
      v = this.producto.variantes[0];
      this.selectedSizeName = v.talla_nombre;
      this.selectedColorHex = v.codigo_hex;
    }

    if (!v) {
      this.toastEsError = true;
      this.toastMessage = 'Por favor selecciona una talla y color disponibles.';
      this.addedToast = true;
      this.cdr.markForCheck();
      setTimeout(() => {
        this.addedToast = false;
        this.cdr.markForCheck();
      }, 3500);
      return;
    }

    const stockTotal = this.getStockTotalVarianteSeleccionada();
    if (stockTotal <= 0) {
      this.toastEsError = true;
      this.toastMessage = 'Prenda agotada temporalmente en todas las sucursales.';
      this.addedToast = true;
      this.cdr.markForCheck();
      setTimeout(() => {
        this.addedToast = false;
        this.cdr.markForCheck();
      }, 3500);
      return;
    }

    if (this.quantity > stockTotal) {
      this.toastEsError = true;
      this.toastMessage = `Solo quedan ${stockTotal} unidades disponibles.`;
      this.addedToast = true;
      this.cdr.markForCheck();
      setTimeout(() => {
        this.addedToast = false;
        this.cdr.markForCheck();
      }, 3500);
      return;
    }

    const empresaId = this.esDetalleReal(this.producto) 
      ? (this.producto.id_empresa || (this.producto as any).empresa_id) 
      : ((this.producto as any)?.id_empresa || (this.producto as any)?.empresa_id || undefined);
    const imgs = this.getImagenes();
    this.cargandoBolsa = true;
    this.cdr.markForCheck();

    this.carritoService.agregarItem(v.id_variante, this.quantity, empresaId, {
      id_producto: this.esDetalleReal(this.producto) ? this.producto.id_producto : 0,
      producto_nombre: this.producto?.nombre || 'Prenda',
      talla_nombre: v.talla_nombre,
      color_nombre: v.color_nombre,
      codigo_hex: v.codigo_hex,
      precio_unitario: Number(v.promocion?.precio_promocional ?? this.getPrecioActual()),
      imagen_url: imgs[0] || null,
      stock_disponible: stockTotal
    }).subscribe({
      next: (res) => {
        this.cargandoBolsa = false;
        this.toastEsError = false;
        const info = ` (${v.talla_nombre} / ${v.color_nombre})`;
        this.toastMessage = res.offline_queued
          ? `⏳ Guardada en tu Bolsa Local (${this.quantity} u.${info}) — pendiente de sincronizar al reconectar.`
          : `✓ ${this.quantity} unidad(es) añadida(s) a tu Bolsa${info}.`;
        this.addedToast = true;
        this.cdr.markForCheck();
        setTimeout(() => {
          this.addedToast = false;
          this.cdr.markForCheck();
        }, 3500);

        if (abrirDrawerAlFinalizar) {
          this.carritoService.abrirDrawer();
          this.closeModal();
        }
      },
      error: (err) => {
        this.cargandoBolsa = false;
        this.toastEsError = true;
        this.toastMessage = err?.error?.detail || 'No fue posible añadir la prenda a la bolsa.';
        this.addedToast = true;
        this.cdr.markForCheck();
        setTimeout(() => {
          this.addedToast = false;
          this.cdr.markForCheck();
        }, 4500);
      }
    });
  }

  buyNow(): void {
    if (!this.authService.estaAutenticado()) {
      this.authService.openAuthModal('login');
    } else {
      this.addToCart(true);
    }
  }

  irAMisReservas(): void {
    this.closeModal();
    this.router.navigate(['/mis-reservas']);
  }

  toggleVistaRA(): void {
    this.mostrarVistaRA = !this.mostrarVistaRA;
    this.cdr.markForCheck();
  }

  closeModal(): void {
    this.mostrarVistaRA = false;
    this.reservaExitosa = false;
    this.vistaModal = 'PRODUCTO';
    this.errorReserva = '';
    this.desbloquearBodyScroll();
    this.close.emit();
  }
}
