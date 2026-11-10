import { Injectable, inject, signal, computed } from '@angular/core';
import {
  CatalogoPublicoService,
  TenantPublico,
  FiltrosCatalogoResponse,
  ConfiguracionStorefront,
  SeccionStorefront
} from './catalogo-publico';

const STORAGE_TENANT_ID_KEY = 'aurora_active_tenant_id';
const STORAGE_TENANT_SLUG_KEY = 'aurora_active_tenant_slug';

const DEFAULT_SECCIONES: SeccionStorefront[] = [
  { codigo: 'banner', visible: true, orden: 1 },
  { codigo: 'publicos', visible: true, orden: 2 },
  { codigo: 'categorias', visible: true, orden: 3 },
  { codigo: 'colecciones', visible: true, orden: 4 },
  { codigo: 'destacados', visible: true, orden: 5 },
  { codigo: 'novedades', visible: true, orden: 6 },
  { codigo: 'recomendaciones', visible: true, orden: 7 }
];

/**
 * Utilidades matemáticas para cálculo de luminancia y contraste accesible (WCAG 2.1)
 */
function parseHexColor(hex: string): { r: number; g: number; b: number } {
  if (!hex) return { r: 24, g: 24, b: 27 };
  let c = hex.replace('#', '').trim();
  if (c.length === 3) {
    c = c.split('').map(x => x + x).join('');
  }
  if (c.length !== 6) return { r: 24, g: 24, b: 27 };
  const num = parseInt(c, 16);
  return {
    r: (num >> 16) & 255,
    g: (num >> 8) & 255,
    b: num & 255
  };
}

function calcularLuminancia(hex: string): number {
  const { r, g, b } = parseHexColor(hex);
  const a = [r, g, b].map(v => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
}

function obtenerColorTextoContraste(hex: string): '#ffffff' | '#09090b' {
  const l = calcularLuminancia(hex);
  // Si la luminancia relativa supera 0.40 el fondo es claro -> texto oscuro charcoal
  return l > 0.40 ? '#09090b' : '#ffffff';
}

function hexToRgba(hex: string, alpha: number): string {
  const { r, g, b } = parseHexColor(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

@Injectable({
  providedIn: 'root'
})
export class TenantContextService {
  private catalogoService = inject(CatalogoPublicoService);

  public readonly tenantsDisponibles = signal<TenantPublico[]>([]);
  public readonly tenantActual = signal<TenantPublico | null>(null);
  public readonly filtrosActuales = signal<FiltrosCatalogoResponse>({
    categorias: [],
    publicos: [],
    sucursales: [],
    tallas: [],
    colores: [],
    temporadas: [],
    colecciones: []
  });
  public readonly cargandoTenant = signal<boolean>(false);
  public readonly tenantNoEncontrado = signal<boolean>(false);

  public readonly idEmpresaActual = computed<number>(() => {
    return this.tenantActual()?.id_empresa || 1;
  });

  public readonly configStorefront = computed<ConfiguracionStorefront>(() => {
    const t = this.tenantActual();
    const cfg = t?.configuracion_storefront;
    const nombre = cfg?.nombre_comercial || t?.nombre_empresa || 'Tienda Oficial';
    return {
      nombre_comercial: nombre,
      eslogan: cfg?.eslogan || 'Moda y estilo para cada ocasión',
      color_primario: cfg?.color_primario || '#18181b',
      color_secundario: cfg?.color_secundario || '#c2410c',
      tipografia: cfg?.tipografia || 'editorial',
      estilo_tarjetas: cfg?.estilo_tarjetas || 'editorial',
      banner_titulo: cfg?.banner_titulo || `Colección Oficial ${nombre}`,
      banner_subtitulo: cfg?.banner_subtitulo || 'Descubre prendas seleccionadas con disponibilidad real por sucursal.',
      banner_imagen_url: cfg?.banner_imagen_url || '',
      banner_cta_texto: cfg?.banner_cta_texto || 'Explorar catálogo',
      publicos_habilitados: cfg?.publicos_habilitados || [],
      colecciones_destacadas: cfg?.colecciones_destacadas || [],
      secciones: cfg?.secciones?.length ? [...cfg.secciones].sort((a, b) => a.orden - b.orden) : DEFAULT_SECCIONES,
      onboarding_completado: Boolean(cfg?.onboarding_completado)
    };
  });

  /**
   * Color de texto con alto contraste accesible sobre el color primario de la tienda.
   * Evita textos opacos, quemados o ilegibles ante cualquier color de paleta.
   */
  public readonly colorTextoSobrePrimario = computed<'#ffffff' | '#09090b'>(() => {
    return obtenerColorTextoContraste(this.configStorefront().color_primario);
  });

  /**
   * Color de texto con alto contraste accesible sobre el color secundario (acentos/botones).
   */
  public readonly colorTextoSobreSecundario = computed<'#ffffff' | '#09090b'>(() => {
    return obtenerColorTextoContraste(this.configStorefront().color_secundario);
  });

  /**
   * Versión translúcida armónica (12% opacidad) del color secundario para chips y badges.
   */
  public readonly colorSecundarioSuave = computed<string>(() => {
    return hexToRgba(this.configStorefront().color_secundario, 0.12);
  });

  /**
   * Versión translúcida armónica (30% opacidad) del color secundario para bordes refinados.
   */
  public readonly colorSecundarioBorde = computed<string>(() => {
    return hexToRgba(this.configStorefront().color_secundario, 0.30);
  });

  /**
   * Indica si el color primario es visualmente claro.
   */
  public readonly esPrimarioClaro = computed<boolean>(() => {
    return calcularLuminancia(this.configStorefront().color_primario) > 0.40;
  });

  /**
   * Indica si el color secundario es visualmente claro.
   */
  public readonly esSecundarioClaro = computed<boolean>(() => {
    return calcularLuminancia(this.configStorefront().color_secundario) > 0.40;
  });

  /**
   * Públicos objetivo efectivamente visibles en el menú y home del tenant:
   * combina los públicos con productos reales en catálogo y los habilitados por el tenant.
   */
  public readonly publicosDisponibles = computed(() => {
    const fPubs = this.filtrosActuales().publicos || [];
    const habs = this.configStorefront().publicos_habilitados || [];
    if (habs.length > 0 && fPubs.length > 0) {
      const filtrados = fPubs.filter(p => habs.includes(p.nombre));
      return filtrados.length > 0 ? filtrados : fPubs;
    }
    return fPubs;
  });

  /**
   * Detecta si el hostname actual incluye un subdominio de tenant (ej. midominio.localhost o tienda.aurorastore.com)
   */
  detectarSubdominioHost(): string | null {
    if (typeof window === 'undefined') return null;
    const host = window.location.hostname.toLowerCase();
    if (host === 'localhost' || host === '127.0.0.1' || host.endsWith('.onrender.com')) {
      return null;
    }
    if (host.endsWith('.localhost')) {
      const sub = host.replace('.localhost', '').trim();
      if (sub && sub !== 'www' && sub !== 'saas' && sub !== 'admin') {
        return sub;
      }
    }
    const parts = host.split('.');
    if (parts.length >= 3) {
      const sub = parts[0];
      if (sub && sub !== 'www' && sub !== 'saas' && sub !== 'admin' && sub !== 'api') {
        return sub;
      }
    }
    return null;
  }

  /**
   * Inicializa la lista de tiendas públicas y resuelve el tenant activo
   */
  inicializarContexto(opciones?: { slug?: string | null; idEmpresa?: number | null }): void {
    const subdominio = this.detectarSubdominioHost();
    const slugObjetivo = opciones?.slug || subdominio || this.obtenerSlugGuardado();
    const idObjetivo = opciones?.idEmpresa || this.obtenerIdEmpresaGuardado();

    this.catalogoService.obtenerTenants().subscribe({
      next: (res) => {
        const lista = res?.data || [];
        this.tenantsDisponibles.set(lista);

        if (slugObjetivo) {
          const matchSlug = lista.find(t => t.slug?.toLowerCase() === slugObjetivo.toLowerCase());
          if (matchSlug) {
            this.cargarTenantPorId(matchSlug.id_empresa);
            return;
          }
          this.cargarTenantPorSlug(slugObjetivo);
          return;
        }

        if (idObjetivo) {
          const matchId = lista.find(t => t.id_empresa === idObjetivo);
          if (matchId) {
            this.cargarTenantPorId(matchId.id_empresa);
            return;
          }
        }

        if (lista.length > 0) {
          this.cargarTenantPorId(lista[0].id_empresa);
        }
      }
    });
  }

  cargarTenantPorSlug(slug: string): void {
    if (!slug) return;
    this.cargandoTenant.set(true);
    this.tenantNoEncontrado.set(false);

    this.catalogoService.resolverTenantPorSlug(slug).subscribe({
      next: (res) => {
        if (res?.success && res.empresa) {
          this.tenantActual.set(res.empresa);
          this.filtrosActuales.set(res.filtros || {
            categorias: [],
            publicos: [],
            sucursales: [],
            tallas: [],
            colores: [],
            temporadas: [],
            colecciones: []
          });
          this.guardarSeleccionLocal(res.empresa.id_empresa, res.empresa.slug);
        }
        this.cargandoTenant.set(false);
      },
      error: () => {
        this.tenantNoEncontrado.set(true);
        this.cargandoTenant.set(false);
      }
    });
  }

  cargarTenantPorId(idEmpresa: number): void {
    if (!idEmpresa) return;
    this.cargandoTenant.set(true);
    this.tenantNoEncontrado.set(false);

    this.catalogoService.obtenerFiltros(idEmpresa).subscribe({
      next: (res) => {
        if (res?.empresa) {
          this.tenantActual.set(res.empresa);
          this.guardarSeleccionLocal(res.empresa.id_empresa, res.empresa.slug);
        } else {
          const fallback = this.tenantsDisponibles().find(t => t.id_empresa === idEmpresa) || null;
          if (fallback) this.tenantActual.set(fallback);
        }
        if (res?.data) {
          this.filtrosActuales.set(res.data);
        }
        this.cargandoTenant.set(false);
      },
      error: () => {
        this.cargandoTenant.set(false);
      }
    });
  }

  seleccionarTenant(tenant: TenantPublico): void {
    if (!tenant?.id_empresa) return;
    this.tenantActual.set(tenant);
    this.guardarSeleccionLocal(tenant.id_empresa, tenant.slug);
    this.cargarTenantPorId(tenant.id_empresa);
  }

  seccionVisible(codigo: SeccionStorefront['codigo']): boolean {
    const sec = this.configStorefront().secciones.find(s => s.codigo === codigo);
    return sec ? sec.visible : true;
  }

  obtenerFamiliaTipografica(): string {
    const tipo = this.configStorefront().tipografia;
    switch (tipo) {
      case 'moderna':
        return "'Plus Jakarta Sans', 'Inter', system-ui, sans-serif";
      case 'clasica':
        return "'Georgia', 'Times New Roman', serif";
      case 'minimal':
        return "'Inter', system-ui, -apple-system, sans-serif";
      case 'editorial':
      default:
        return "'Playfair Display', 'Georgia', serif";
    }
  }

  private guardarSeleccionLocal(idEmpresa: number, slug?: string): void {
    if (typeof localStorage === 'undefined') return;
    try {
      localStorage.setItem(STORAGE_TENANT_ID_KEY, String(idEmpresa));
      if (slug) localStorage.setItem(STORAGE_TENANT_SLUG_KEY, slug);
    } catch (_) {}
  }

  private obtenerIdEmpresaGuardado(): number | null {
    if (typeof localStorage === 'undefined') return null;
    try {
      const val = Number(localStorage.getItem(STORAGE_TENANT_ID_KEY));
      return Number.isFinite(val) && val > 0 ? val : null;
    } catch {
      return null;
    }
  }

  private obtenerSlugGuardado(): string | null {
    if (typeof localStorage === 'undefined') return null;
    try {
      return localStorage.getItem(STORAGE_TENANT_SLUG_KEY) || null;
    } catch {
      return null;
    }
  }
}
