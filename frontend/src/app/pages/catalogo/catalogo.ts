import { Component, OnInit, OnDestroy, inject, ChangeDetectorRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { AuthService } from '../../services/auth';
import { ThemeService } from '../../services/theme';
import { CarritoService } from '../../services/carrito';
import { NetworkStatusService } from '../../core/network/network-status.service';
import { TenantContextService } from '../../services/tenant-context';
import { 
  CatalogoPublicoService, 
  TenantPublico, 
  FiltrosCatalogoResponse, 
  PrendaCatalogo, 
  DetallePrendaCatalogo 
} from '../../services/catalogo-publico';
import { CatalogoFiltrosComponent } from './components/filtros/filtros';
import { ProductoCardComponent } from './components/producto-card/producto-card';
import { ProductDetailModalComponent } from '../../components/product-detail-modal/product-detail-modal';

@Component({
  selector: 'app-catalogo',
  standalone: true,
  imports: [
    CommonModule, 
    FormsModule, 
    RouterModule,
    CatalogoFiltrosComponent, 
    ProductoCardComponent, 
    ProductDetailModalComponent
  ],
  templateUrl: './catalogo.html'
})
export class CatalogoComponent implements OnInit, OnDestroy {
  public catalogoService = inject(CatalogoPublicoService);
  public authService     = inject(AuthService);
  public themeService    = inject(ThemeService);
  public carritoService  = inject(CarritoService);
  public networkStatus   = inject(NetworkStatusService);
  public tenantContext   = inject(TenantContextService);
  private route          = inject(ActivatedRoute);
  private cdr            = inject(ChangeDetectorRef);
  private searchTimer: any = null;

  @ViewChild(CatalogoFiltrosComponent) filtrosComponentRef?: CatalogoFiltrosComponent;

  // Tenants / Tiendas
  tenants: TenantPublico[] = [];
  selectedTenantId: number | null = null;
  selectedTenant: TenantPublico | null = null;

  // Productos & Paginación
  productos: PrendaCatalogo[] = [];
  totalProductos: number = 0;
  cargando: boolean = false;
  cargandoFiltros: boolean = false;

  // Filtros dinámicos
  filtrosDisponibles: FiltrosCatalogoResponse = {
    categorias: [],
    tallas: [],
    colores: [],
    temporadas: [],
    colecciones: []
  };

  // Valores de filtros activos
  searchQuery: string = '';
  selectedCategory: number | null = null;
  categoriaNombreFiltro: string = '';
  selectedPublico: string = 'Todos';
  selectedSucursal: number | null = null;
  selectedTalla: number | null = null;
  selectedColor: number | null = null;
  selectedTemporada: string = 'Todas';
  selectedColeccion: string = 'Todas';
  selectedSort: string = 'destacados';
  precioMin: number | null = null;
  precioMax: number | null = null;

  // Paginación
  paginaActual: number = 1;
  limitePorPagina: number = 12;
  totalPaginas: number = 1;
  opcionesLimite: number[] = [12, 24, 48];

  // Detalle de Prenda (Modal)
  selectedProductForModal: DetallePrendaCatalogo | null = null;
  modoModalInicial: 'PRODUCTO' | 'AGENDAR_CITA' = 'PRODUCTO';
  cargandoDetalle: boolean = false;
  private pendingProductId: number | null = null;

  ngOnInit(): void {
    // 1. Escuchar parámetros de ruta directa /catalogo/:id
    this.route.params.subscribe(params => {
      if (params['id']) {
        const id = parseInt(params['id'], 10);
        if (!isNaN(id)) {
          this.pendingProductId = id;
          this.abrirDetalle(id);
        }
      }
    });

    // 2. Escuchar queryParams (tenant / empresa / producto / búsqueda / categoría)
    this.route.queryParams.subscribe(params => {
      const urlTenant = params['empresa'] || params['tenant'];
      const initialTenantId = urlTenant ? parseInt(urlTenant, 10) : null;
      if (params['q'] || params['busqueda']) {
        this.searchQuery = params['q'] || params['busqueda'];
      }
      if (params['categoria']) {
        const catId = parseInt(params['categoria'], 10);
        if (!isNaN(catId)) {
          this.selectedCategory = catId;
        }
      }
      if (params['categoria_nombre']) {
        this.categoriaNombreFiltro = params['categoria_nombre'];
      }
      if (params['publico']) {
        this.selectedPublico = params['publico'];
      }
      if (params['coleccion']) {
        this.selectedColeccion = params['coleccion'];
      }
      if (params['sucursal']) {
        const sucId = parseInt(params['sucursal'], 10);
        if (!isNaN(sucId)) {
          this.selectedSucursal = sucId;
        }
      }
      if (params['producto'] || params['id_producto']) {
        const prodId = parseInt(params['producto'] || params['id_producto'], 10);
        if (!isNaN(prodId)) {
          this.pendingProductId = prodId;
        }
      }
      if (params['modo'] === 'cita' || params['accion'] === 'probar') {
        this.modoModalInicial = 'AGENDAR_CITA';
      } else {
        this.modoModalInicial = 'PRODUCTO';
      }
      this.cargarTenants(initialTenantId);
    });
  }

  ngOnDestroy(): void {
    if (this.searchTimer) {
      clearTimeout(this.searchTimer);
    }
  }

  cargarTenants(initialTenantId: number | null = null): void {
    const tenantCtxId = this.tenantContext.idEmpresaActual();
    const targetTenantId = initialTenantId || (tenantCtxId > 0 ? tenantCtxId : null);

    this.catalogoService.obtenerTenants().subscribe({
      next: (res) => {
        this.tenants = res.data || [];
        if (this.tenants.length > 0) {
          if (targetTenantId && this.tenants.some(t => t.id_empresa === targetTenantId)) {
            this.selectedTenantId = targetTenantId;
          } else {
            this.selectedTenantId = this.tenants[0].id_empresa;
          }
          this.selectedTenant = this.tenants.find(t => t.id_empresa === this.selectedTenantId) || this.tenants[0];
          if (this.selectedTenantId) {
            this.carritoService.setEmpresaId(this.selectedTenantId);
            this.tenantContext.cargarTenantPorId(this.selectedTenantId);
          }
          this.cargarFiltrosYProductos();

          if (this.pendingProductId) {
            this.abrirDetalle(this.pendingProductId);
          }
        } else {
          this.usarFallbackTenant(targetTenantId);
        }
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.warn('Error al cargar tiendas activas, activando modo offline:', err);
        this.usarFallbackTenant(targetTenantId);
        this.cdr.markForCheck();
      }
    });
  }

  private usarFallbackTenant(initialTenantId: number | null): void {
    if (typeof localStorage !== 'undefined') {
      try {
        const raw = localStorage.getItem('aurora_last_tenants');
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed?.data && parsed.data.length > 0) {
            this.tenants = parsed.data;
            this.selectedTenantId = (initialTenantId && this.tenants.some(t => t.id_empresa === initialTenantId))
              ? initialTenantId
              : this.tenants[0].id_empresa;
            this.selectedTenant = this.tenants.find(t => t.id_empresa === this.selectedTenantId) || this.tenants[0];
            this.carritoService.setEmpresaId(this.selectedTenant.id_empresa);
            this.tenantContext.cargarTenantPorId(this.selectedTenant.id_empresa);
            this.cargarFiltrosYProductos();
            return;
          }
        }
      } catch (_) {}
    }
    const fallbackTenantId = initialTenantId || 1;
    const fallbackTenant: TenantPublico = { id_empresa: fallbackTenantId, nombre_empresa: 'Tienda Aurora', ciudad: 'Bolivia' };
    this.selectedTenantId = fallbackTenantId;
    this.selectedTenant = fallbackTenant;
    this.tenants = [fallbackTenant];
    this.carritoService.setEmpresaId(fallbackTenantId);
    this.tenantContext.cargarTenantPorId(fallbackTenantId);
    this.cargarFiltrosYProductos();
  }

  cambiarTenant(idEmpresa: number): void {
    if (this.selectedTenantId === idEmpresa) return;
    this.selectedTenantId = idEmpresa;
    this.selectedTenant = this.tenants.find(t => t.id_empresa === idEmpresa) || null;
    this.carritoService.setEmpresaId(idEmpresa);
    this.tenantContext.cargarTenantPorId(idEmpresa);
    this.limpiarFiltros(false);
    this.cargarFiltrosYProductos();
    this.cdr.markForCheck();
  }

  cargarFiltrosYProductos(): void {
    if (!this.selectedTenantId) return;

    this.cargandoFiltros = true;
    this.cdr.markForCheck();

    // Ejecutar carga de filtros y primera página de productos en paralelo para eliminar cascada secuencial
    this.aplicarFiltros();

    this.catalogoService.obtenerFiltros(this.selectedTenantId).subscribe({
      next: (res) => {
        this.filtrosDisponibles = res.data;
        if (res.empresa) {
          this.selectedTenant = res.empresa;
        }
        if (this.categoriaNombreFiltro && this.filtrosDisponibles.categorias) {
          const match = this.filtrosDisponibles.categorias.find(
            c => c.nombre.toLowerCase().includes(this.categoriaNombreFiltro.toLowerCase())
          );
          if (match) {
            this.selectedCategory = match.id_categoria;
            this.categoriaNombreFiltro = '';
            this.aplicarFiltros();
          }
        }
        this.cargandoFiltros = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error al cargar filtros dinámicos:', err);
        this.cargandoFiltros = false;
        this.cdr.markForCheck();
      }
    });
  }

  aplicarFiltros(): void {
    if (!this.selectedTenantId) {
      this.selectedTenantId = 1;
    }
    this.cargando = true;
    this.cdr.markForCheck();

    const offset = (this.paginaActual - 1) * this.limitePorPagina;

    this.catalogoService.consultarProductos({
      id_empresa: this.selectedTenantId,
      busqueda: this.searchQuery,
      id_categoria: this.selectedCategory || undefined,
      publico: this.selectedPublico !== 'Todos' ? this.selectedPublico : undefined,
      id_sucursal: this.selectedSucursal || undefined,
      id_talla: this.selectedTalla || undefined,
      id_color: this.selectedColor || undefined,
      temporada: this.selectedTemporada,
      coleccion: this.selectedColeccion,
      precio_min: this.precioMin !== null ? this.precioMin : undefined,
      precio_max: this.precioMax !== null ? this.precioMax : undefined,
      orden: this.selectedSort,
      limit: this.limitePorPagina,
      offset: offset
    }).subscribe({
      next: (res) => {
        let items = res.data || [];
        if (!items.length && !this.networkStatus.isOnline() && typeof localStorage !== 'undefined') {
          try {
            const raw =
              localStorage.getItem(`aurora_catalog_master_e_${this.selectedTenantId}`) ||
              localStorage.getItem(`aurora_last_catalog_e_${this.selectedTenantId}`) ||
              localStorage.getItem('aurora_last_catalog_global') ||
              localStorage.getItem('aurora_cached_products_list');
            if (raw) {
              const parsed = JSON.parse(raw);
              const rawItems = Array.isArray(parsed) ? parsed : (parsed.data || parsed.productos || []);
              if (Array.isArray(rawItems) && rawItems.length > 0) {
                items = rawItems;
                this.paginaActual = 1;
              }
            }
          } catch (_) {}
        }
        this.productos = items;
        this.totalProductos = res.total || items.length;
        this.totalPaginas = Math.ceil(this.totalProductos / this.limitePorPagina) || 1;
        if (this.paginaActual > this.totalPaginas && this.totalPaginas > 0) {
          this.paginaActual = this.totalPaginas;
        }
        this.cargando = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.warn('Error al consultar productos, intentando respaldo offline:', err);
        if (!this.networkStatus.isOnline() && typeof localStorage !== 'undefined') {
          try {
            const raw =
              localStorage.getItem(`aurora_catalog_master_e_${this.selectedTenantId}`) ||
              localStorage.getItem(`aurora_last_catalog_e_${this.selectedTenantId}`) ||
              localStorage.getItem('aurora_last_catalog_global') ||
              localStorage.getItem('aurora_cached_products_list');
            if (raw) {
              const parsed = JSON.parse(raw);
              const items = Array.isArray(parsed) ? parsed : (parsed.data || parsed.productos || []);
              if (Array.isArray(items) && items.length > 0) {
                this.productos = items;
                this.totalProductos = items.length;
                this.paginaActual = 1;
                this.totalPaginas = Math.ceil(this.totalProductos / this.limitePorPagina) || 1;
                this.cargando = false;
                this.cdr.markForCheck();
                return;
              }
            }
          } catch (_) {}
        }
        this.productos = [];
        this.totalProductos = 0;
        this.totalPaginas = 1;
        this.cargando = false;
        this.cdr.markForCheck();
      }
    });
  }

  // --- Handlers de Filtros Component ---
  onBusquedaChange(q: string): void {
    this.searchQuery = q;
    this.paginaActual = 1;
    if (this.searchTimer) {
      clearTimeout(this.searchTimer);
    }
    this.searchTimer = setTimeout(() => {
      this.aplicarFiltros();
    }, 200);
  }

  onCategoriaChange(idCat: number | null): void {
    this.selectedCategory = idCat;
    this.paginaActual = 1;
    this.aplicarFiltros();
  }

  onPublicoChange(pub: string): void {
    this.selectedPublico = pub || 'Todos';
    this.paginaActual = 1;
    this.aplicarFiltros();
  }

  onSucursalChange(idSuc: number | null): void {
    this.selectedSucursal = idSuc;
    this.paginaActual = 1;
    this.aplicarFiltros();
  }

  onTallaChange(idTalla: number | null): void {
    this.selectedTalla = idTalla;
    this.paginaActual = 1;
    this.aplicarFiltros();
  }

  onColorChange(idColor: number | null): void {
    this.selectedColor = idColor;
    this.paginaActual = 1;
    this.aplicarFiltros();
  }

  onTemporadaChange(t: string): void {
    this.selectedTemporada = t;
    this.paginaActual = 1;
    this.aplicarFiltros();
  }

  onColeccionChange(c: string): void {
    this.selectedColeccion = c;
    this.paginaActual = 1;
    this.aplicarFiltros();
  }

  onOrdenChange(o: string): void {
    this.selectedSort = o;
    this.paginaActual = 1;
    this.aplicarFiltros();
  }

  onPrecioMinChange(min: number | null): void {
    this.precioMin = min;
    this.paginaActual = 1;
    this.aplicarFiltros();
  }

  onPrecioMaxChange(max: number | null): void {
    this.precioMax = max;
    this.paginaActual = 1;
    this.aplicarFiltros();
  }

  getCategoriaNombre(): string {
    if (!this.selectedCategory) return '';
    const cat = this.filtrosDisponibles?.categorias?.find(c => c.id_categoria === this.selectedCategory);
    return cat ? cat.nombre : '';
  }

  getSucursalNombre(): string {
    if (!this.selectedSucursal) return '';
    const suc = this.filtrosDisponibles?.sucursales?.find(s => s.id_sucursal === this.selectedSucursal);
    return suc ? `${suc.nombre}${suc.ciudad ? ' (' + suc.ciudad + ')' : ''}` : '';
  }

  limpiarFiltros(recargar: boolean = true): void {
    this.searchQuery = '';
    this.selectedCategory = null;
    this.selectedPublico = 'Todos';
    this.selectedSucursal = null;
    this.selectedTalla = null;
    this.selectedColor = null;
    this.selectedTemporada = 'Todas';
    this.selectedColeccion = 'Todas';
    this.selectedSort = 'destacados';
    this.precioMin = null;
    this.precioMax = null;
    this.paginaActual = 1;

    if (recargar) {
      this.aplicarFiltros();
    }
  }

  // --- Handlers de Paginación ---
  cambiarPagina(nuevaPagina: number): void {
    if (nuevaPagina < 1 || nuevaPagina > this.totalPaginas || nuevaPagina === this.paginaActual) return;
    this.paginaActual = nuevaPagina;
    this.aplicarFiltros();
    window.scrollTo({ top: 180, behavior: 'smooth' });
  }

  cambiarLimite(nuevoLimite: any): void {
    const lim = parseInt(nuevoLimite, 10);
    if (!isNaN(lim) && lim > 0 && lim !== this.limitePorPagina) {
      this.limitePorPagina = lim;
      this.paginaActual = 1;
      this.aplicarFiltros();
    }
  }

  getPaginasVisibles(): number[] {
    const paginas: number[] = [];
    const maxBtns = 5;
    let start = Math.max(1, this.paginaActual - Math.floor(maxBtns / 2));
    let end = Math.min(this.totalPaginas, start + maxBtns - 1);
    if (end - start + 1 < maxBtns) {
      start = Math.max(1, end - maxBtns + 1);
    }
    for (let i = start; i <= end; i++) {
      paginas.push(i);
    }
    return paginas;
  }

  // --- Detalle de Prenda ---
  abrirDetalle(idProducto: number): void {
    this.cargandoDetalle = true;
    this.cdr.markForCheck();
    // Consultar detalle sin forzar id_empresa para permitir resolver prendas de cualquier tienda
    this.catalogoService.obtenerDetalleProducto(idProducto).subscribe({
      next: (res) => {
        const prod = res.data;
        if (prod && prod.id_empresa && prod.id_empresa !== this.selectedTenantId) {
          this.selectedTenantId = prod.id_empresa;
          this.selectedTenant = this.tenants.find(t => t.id_empresa === prod.id_empresa) || {
            id_empresa: prod.id_empresa,
            nombre_empresa: prod.empresa_nombre || 'Tienda'
          };
          this.carritoService.setEmpresaId(prod.id_empresa);
          this.tenantContext.cargarTenantPorId(prod.id_empresa);
          this.limpiarFiltros(false);
          this.cargarFiltrosYProductos();
        }
        this.selectedProductForModal = prod;
        this.cargandoDetalle = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error al abrir detalle:', err);
        this.cargandoDetalle = false;
        this.cdr.markForCheck();
      }
    });
  }

  cerrarModalDetalle(): void {
    this.selectedProductForModal = null;
    this.modoModalInicial = 'PRODUCTO';
    this.cdr.markForCheck();
  }
}
