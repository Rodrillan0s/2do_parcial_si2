import { Component, OnInit, inject, ChangeDetectorRef, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth';
import { FavoritosService } from '../../services/favoritos';
import { CatalogoPublicoService, DetallePrendaCatalogo, PrendaCatalogo } from '../../services/catalogo-publico';
import { ProductDetailModalComponent, ProductoFashion } from '../../components/product-detail-modal/product-detail-modal';
import { RecomendacionesService, RecomendacionML } from '../../services/recomendaciones.service';
import { TenantContextService } from '../../services/tenant-context';

export interface ProductoDestacadoItem extends ProductoFashion {
  genero?: string;
  coleccion?: string;
  rating?: number;
  reviews?: number;
}

@Component({
  selector: 'app-explorar',
  standalone: true,
  imports: [CommonModule, RouterLink, ProductDetailModalComponent],
  templateUrl: './explorar.html'
})
export class ExplorarComponent implements OnInit {
  public authService = inject(AuthService);
  public tenantContext = inject(TenantContextService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private catalogoService = inject(CatalogoPublicoService);
  private cdr = inject(ChangeDetectorRef);
  public favoritosService = inject(FavoritosService);
  private recomendacionesService = inject(RecomendacionesService);

  selectedProductForModal: DetallePrendaCatalogo | ProductoFashion | null = null;
  public recomendacionesML: RecomendacionML[] = [];
  public productosDestacados: ProductoDestacadoItem[] = [];
  public productosNovedades: ProductoDestacadoItem[] = [];
  public cargandoProductos: boolean = false;
  private ultimoTenantCargado: number = 0;

  readonly defaultBannerImg = 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=1600&q=85';

  constructor() {
    effect(() => {
      const tenant = this.tenantContext.tenantActual();
      if (tenant && tenant.id_empresa !== this.ultimoTenantCargado) {
        this.ultimoTenantCargado = tenant.id_empresa;
        this.cargarProductosDelTenant(tenant.id_empresa);
      }
    });
  }

  ngOnInit(): void {
    this.route.paramMap.subscribe(params => {
      const slug = params.get('slug');
      if (slug) {
        this.tenantContext.cargarTenantPorSlug(slug);
      }
    });

    this.route.queryParamMap.subscribe(qParams => {
      const empId = Number(qParams.get('empresa'));
      const slug = qParams.get('tienda');
      if (slug) {
        this.tenantContext.cargarTenantPorSlug(slug);
      } else if (empId && empId > 0) {
        this.tenantContext.cargarTenantPorId(empId);
      } else if (!this.tenantContext.tenantActual()) {
        this.tenantContext.inicializarContexto();
      }
    });

    const actual = this.tenantContext.tenantActual();
    if (actual) {
      this.ultimoTenantCargado = actual.id_empresa;
      this.cargarProductosDelTenant(actual.id_empresa);
    }

    this.recomendacionesService.obtenerMisRecomendaciones(4).subscribe({
      next: (res) => {
        if (res && res.recomendaciones && res.recomendaciones.length > 0) {
          this.recomendacionesML = res.recomendaciones;
          this.cdr.markForCheck();
        }
      },
      error: () => {}
    });
  }

  private mapearPrenda(p: PrendaCatalogo, idx: number): ProductoDestacadoItem {
    return {
      id: p.id_producto,
      nombre: p.nombre,
      subtitulo: `${p.marca || this.tenantContext.configStorefront().nombre_comercial} • ${p.coleccion || p.temporada || 'Catálogo'}`,
      precio: p.precio,
      categoria: p.categoria_nombre,
      genero: p.genero || 'Unisex',
      coleccion: p.coleccion || '',
      imagenPrincipal: p.imagen_principal || 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=800&q=80',
      imagenes: p.imagen_principal ? [p.imagen_principal] : [],
      tallas: p.tallas_disponibles?.map(t => t.nombre) || [],
      colores: p.colores_disponibles?.map(c => ({ nombre: c.nombre, hex: c.codigo_hex })) || [],
      descripcion: p.descripcion,
      popularidad: 95,
      etiqueta: p.temporada,
      rating: 4.8,
      reviews: 12 + idx * 5
    };
  }

  cargarProductosDelTenant(idEmpresa: number): void {
    this.cargandoProductos = true;
    this.catalogoService.consultarProductos({ id_empresa: idEmpresa, orden: 'destacados', limit: 12 }).subscribe({
      next: (res) => {
        const lista = (res.data || []).map((p, idx) => this.mapearPrenda(p, idx));
        this.productosDestacados = lista.slice(0, 6);
        this.productosNovedades = lista.slice(6, 12).length > 0 ? lista.slice(6, 12) : lista.slice(0, 4);
        this.cargandoProductos = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.productosDestacados = [];
        this.productosNovedades = [];
        this.cargandoProductos = false;
        this.cdr.markForCheck();
      }
    });
  }

  get coleccionesParaMostrar(): string[] {
    const dest = this.tenantContext.configStorefront().colecciones_destacadas || [];
    const disp = this.tenantContext.filtrosActuales().colecciones || [];
    if (dest.length > 0) {
      return dest;
    }
    return disp.slice(0, 6);
  }

  iconoPublico(publico: string): string {
    const p = publico.toLowerCase();
    if (p.includes('mujer')) return 'ph-dress';
    if (p.includes('hombre')) return 'ph-coat-hanger';
    if (p.includes('niñ')) return 'ph-smiley';
    if (p.includes('beb')) return 'ph-baby';
    return 'ph-users-three';
  }

  iconoCategoria(nombre: string): string {
    const n = (nombre || '').toLowerCase();
    if (n.includes('vestid')) return 'ph-dress';
    if (n.includes('blus') || n.includes('camis') || n.includes('poler') || n.includes('top')) return 'ph-t-shirt';
    if (n.includes('pantal') || n.includes('jean') || n.includes('short')) return 'ph-scissors';
    if (n.includes('chaquet') || n.includes('abrig') || n.includes('blazer') || n.includes('saco')) return 'ph-coat-hanger';
    if (n.includes('calzad') || n.includes('zapat') || n.includes('bot')) return 'ph-sneaker';
    if (n.includes('bols') || n.includes('carter') || n.includes('mochil') || n.includes('accesori')) return 'ph-handbag';
    if (n.includes('joy') || n.includes('reloj') || n.includes('anill') || n.includes('collar')) return 'ph-sparkle';
    if (n.includes('fald')) return 'ph-sketch-logo';
    if (n.includes('deport') || n.includes('active') || n.includes('sport')) return 'ph-lightning';
    return 'ph-tag';
  }

  openQuickView(prod: any): void {
    if (prod?.id) {
      this.catalogoService.obtenerDetalleProducto(prod.id).subscribe({
        next: (res) => {
          if (res.data) {
            this.selectedProductForModal = res.data;
          } else {
            this.selectedProductForModal = prod;
          }
          this.cdr.markForCheck();
        },
        error: () => {
          this.router.navigate(['/catalogo'], { queryParams: { empresa: this.tenantContext.idEmpresaActual() } });
        }
      });
    } else {
      this.router.navigate(['/catalogo'], { queryParams: { empresa: this.tenantContext.idEmpresaActual() } });
    }
  }

  closeQuickView(): void {
    this.selectedProductForModal = null;
    this.cdr.markForCheck();
  }

  openAuth(tab: 'login' | 'register' = 'login'): void {
    this.authService.openAuthModal(tab);
  }

  toggleFavorito(prod: ProductoFashion, event: Event): void {
    event.stopPropagation();
    this.favoritosService?.toggleFavorito({
      id_producto: prod.id,
      nombre: prod.nombre,
      categoria_nombre: prod.categoria,
      precio: prod.precio,
      imagen_principal: prod.imagenPrincipal,
      subtitulo: prod.subtitulo
    });
    this.cdr.markForCheck();
  }

  esFavorito(id: number): boolean {
    return this.favoritosService?.esFavorito(id) ?? false;
  }
}
