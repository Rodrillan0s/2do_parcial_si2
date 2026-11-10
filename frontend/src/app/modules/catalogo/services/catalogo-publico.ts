import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, from, of, throwError } from 'rxjs';
import { catchError, switchMap, tap, take } from 'rxjs/operators';
import { environment } from '../../../../environments/environment';
import { CachedRecord, IndexedDbService } from '../../../core/storage/indexed-db.service';
import { NetworkStatusService } from '../../../core/network/network-status.service';

export interface SeccionStorefront {
  codigo: 'banner' | 'publicos' | 'categorias' | 'colecciones' | 'destacados' | 'novedades' | 'recomendaciones';
  visible: boolean;
  orden: number;
}

export interface ConfiguracionStorefront {
  nombre_comercial: string;
  eslogan: string;
  color_primario: string;
  color_secundario: string;
  tipografia: 'editorial' | 'moderna' | 'clasica' | 'minimal';
  estilo_tarjetas: 'editorial' | 'minimal' | 'borde_suave';
  banner_titulo: string;
  banner_subtitulo: string;
  banner_imagen_url: string;
  banner_cta_texto: string;
  publicos_habilitados: string[];
  colecciones_destacadas: string[];
  secciones: SeccionStorefront[];
  onboarding_completado: boolean;
}

export interface TenantPublico {
  id_empresa: number;
  nombre_empresa: string;
  razon_social?: string;
  logo?: string | null;
  ciudad?: string;
  correo?: string;
  telefono?: string;
  direccion_fiscal?: string;
  slug?: string;
  configuracion_storefront?: ConfiguracionStorefront;
}

export interface PublicoFiltro {
  nombre: string;
  total_prendas: number;
}

export interface SucursalFiltro {
  id_sucursal: number;
  nombre: string;
  direccion: string;
  ciudad: string;
  telefono?: string;
  horario?: string;
}

export interface CategoriaFiltro {
  id_categoria: number;
  nombre: string;
  imagen_url?: string | null;
  total_prendas: number;
}

export interface TallaFiltro {
  id_talla: number;
  nombre: string;
}

export interface ColorFiltro {
  id_color: number;
  nombre: string;
  codigo_hex: string;
}
export interface PromocionProducto {
  id_promocion: number;
  nombre: string;
  descripcion: string;
  porcentaje_descuento: number;
  fecha_inicio: string;
  fecha_fin: string;
  precio_promocional: number;
}
export interface FiltrosCatalogoResponse {
  categorias: CategoriaFiltro[];
  publicos?: PublicoFiltro[];
  sucursales?: SucursalFiltro[];
  tallas: TallaFiltro[];
  colores: ColorFiltro[];
  temporadas: string[];
  colecciones: string[];
  precio_min?: number;
  precio_max?: number;
}

export interface PrendaCatalogo {
  id_producto: number;
  id_empresa: number;
  id_categoria: number;
  categoria_nombre: string;
  codigo_producto?: string;
  nombre: string;
  descripcion: string;
  marca: string;
  genero: string;
  precio: number;
  precio_min?: number;
  precio_max?: number;
  temporada: string;
  coleccion: string;
  fecha_registro?: string;
  imagen_principal?: string | null;
  total_imagenes: number;
  total_variantes: number;
  tallas_disponibles: { id_talla: number; nombre: string; precio?: number }[];
  colores_disponibles: { id_color: number; nombre: string; codigo_hex: string }[];
  promocion?: PromocionProducto | null;
}

export interface VarianteDetalle {
  id_variante: number;
  id_talla: number;
  talla_nombre: string;
  id_color: number;
  color_nombre: string;
  codigo_hex: string;
  sku?: string;
  precio: number;
  promocion?: PromocionProducto | null;  
  modelo_ra_url?: string | null;
}

export interface ImagenDetalle {
  id_imagen: number;
  imagen_url: string;
  public_id: string;
  es_principal: boolean;
  orden: number;
}

export interface SucursalStockDetalle {
  id_sucursal: number;
  nombre: string;
  codigo_sucursal?: string;
  direccion: string;
  telefono?: string;
  horario: string;
  ciudad?: string;
  stock_total_sucursal: number;
  disponible: boolean;
  stock_por_variante: Record<string, number>; // id_variante -> stock
}

export interface DetallePrendaCatalogo {
  id_producto: number;
  id_empresa: number;
  empresa_nombre: string;
  id_categoria: number;
  categoria_nombre: string;
  codigo_producto?: string;
  nombre: string;
  descripcion: string;
  marca: string;
  genero: string;
  precio: number;
  temporada: string;
  coleccion: string;
  fecha_registro?: string;
  imagenes: ImagenDetalle[];
  imagen_principal?: string | null;
  variantes: VarianteDetalle[];
  tallas: { id_talla: number; nombre: string }[];
  colores: { id_color: number; nombre: string; codigo_hex: string }[];
  sucursales_stock: SucursalStockDetalle[];
  stock_total_general: number;
  hay_stock_disponible: boolean;
  permite_reserva: boolean;
  permite_compra: boolean;
  permite_vestidor_ra: boolean;
  promocion?: PromocionProducto | null;
  recursos_ra?: {
    modelo_3d_url?: string | null;
    modelo_ar_url?: string | null;
  };
  _offline_metadata?: {
    fromCache: boolean;
    fetchedAt: string | null;
    isSummaryFallback?: boolean;
  };
}

export interface RespuestaCatalogoProductos {
  success: boolean;
  empresa: TenantPublico | null;
  total: number;
  limit: number;
  offset: number;
  data: PrendaCatalogo[];
  _offline_metadata?: {
    fromCache: boolean;
    fetchedAt: string | null;
    isPartial: boolean;
  };
}

export interface DisponibilidadVarianteSucursal {
  id_sucursal: number;
  nombre: string;
  codigo_sucursal?: string;
  direccion: string;
  telefono?: string;
  correo?: string;
  horario: string;
  ciudad?: string;
  stock_disponible: number;
  disponible: boolean;
  permite_reserva: boolean;
  permite_compra: boolean;
}

export interface DisponibilidadVarianteResponse {
  variante: {
    id_variante: number;
    id_producto: number;
    producto_nombre: string;
    id_empresa: number;
    empresa_nombre: string;
    id_talla: number;
    talla_nombre: string;
    id_color: number;
    color_nombre: string;
    codigo_hex: string;
    sku?: string;
    precio: number;
    promocion?: PromocionProducto | null;
  };
  stock_total: number;
  hay_disponibilidad: boolean;
  sucursales: DisponibilidadVarianteSucursal[];
}

export interface OfflineDataIndicator {
  fromCache: boolean;
  fetchedAt: string | null;
  isPartial: boolean;
}

const CATALOG_TTL_MS = 24 * 60 * 60 * 1000; // 24h en IndexedDB para lectura offline

@Injectable({
  providedIn: 'root'
})
export class CatalogoPublicoService {
  private http = inject(HttpClient);
  private indexedDb = inject(IndexedDbService);
  private networkStatus = inject(NetworkStatusService);
  private apiUrl = `${environment.apiUrl}/api/catalogo`;

  public lastCatalogMeta = signal<OfflineDataIndicator>({
    fromCache: false,
    fetchedAt: null,
    isPartial: false
  });

  public lastDetailMeta = signal<OfflineDataIndicator>({
    fromCache: false,
    fetchedAt: null,
    isPartial: false
  });

  /**
   * Fase F4: Precarga selectiva de lectura no bloqueante.
   * Descarga la primera página (limit=24) y los filtros dinámicos del tenant predeterminado
   * durante tiempo ocioso (requestIdleCallback o setTimeout) para que la PWA cuente con datos
   * consultables offline sin requerir visita manual previa ni congelar la pantalla.
   */
  public precargarCatalogoInicial(tenantId: number = 1): void {
    if (typeof window === 'undefined') return;

    const scheduleTask = (cb: () => void) => {
      if ('requestIdleCallback' in window) {
        (window as any).requestIdleCallback(() => cb(), { timeout: 3500 });
      } else {
        setTimeout(cb, 1500);
      }
    };

    scheduleTask(async () => {
      if (!this.networkStatus.isOnline()) {
        return;
      }

      const scopeKey = this.indexedDb.buildPublicScopeKey(tenantId);
      const filtersKey = `filters_e:${tenantId}`;
      const cachedFilters = await this.indexedDb.get<CachedRecord>('catalog_filters', filtersKey);
      const now = Date.now();

      // 1. Descargar filtros si no están o expiraron
      if (!cachedFilters || (cachedFilters.expires_at_ms || 0) < now) {
        this.obtenerFiltros(tenantId).pipe(take(1)).subscribe({
          next: () => {},
          error: (e) => console.debug('[PWA Precarga] Filtros omitidos:', e)
        });
      }

      // 2. Descargar lista de tenants si no está o expiró
      const cachedTenants = await this.indexedDb.get<CachedRecord>('catalog_filters', 'public_tenants_list');
      if (!cachedTenants || (cachedTenants.expires_at_ms || 0) < now) {
        this.obtenerTenants().pipe(take(1)).subscribe({
          next: () => {},
          error: (e) => console.debug('[PWA Precarga] Tenants omitidos:', e)
        });
      }

      // 3. Precargar página inicial (limit=24) para lectura offline del catálogo
      const allPages = await this.indexedDb.getAllByScope<CachedRecord>('products', scopeKey);
      const needsCatalog = !allPages || allPages.length === 0 || allPages.every(p => (p.expires_at_ms || 0) < now);

      if (needsCatalog) {
        this.consultarProductos({
          id_empresa: tenantId,
          limit: 24,
          offset: 0
        }).pipe(take(1)).subscribe({
          next: () => console.info('[PWA Precarga] Catálogo inicial precargado exitosamente en IndexedDB'),
          error: (e) => console.debug('[PWA Precarga] Error en precarga inicial de productos:', e)
        });
      }
    });
  }

  obtenerTenants(): Observable<{ success: boolean; total: number; data: TenantPublico[] }> {
    const cacheKey = 'public_tenants_list';
    return this.http.get<{ success: boolean; total: number; data: TenantPublico[] }>(`${this.apiUrl}/tenants`).pipe(
      tap((res) => {
        if (res?.success) {
          const now = Date.now();
          if (typeof localStorage !== 'undefined' && res.data) {
            try {
              localStorage.setItem('aurora_last_tenants', JSON.stringify(res));
            } catch (_) {}
          }
          this.indexedDb.put<CachedRecord>('catalog_filters', {
            key: cacheKey,
            scope_key: 'public|global',
            tenant_id: 0,
            data: res,
            fetched_at: new Date(now).toISOString(),
            fetched_at_ms: now,
            expires_at_ms: now + CATALOG_TTL_MS
          });
        }
      }),
      catchError((err) => {
        return from(this.indexedDb.get<CachedRecord>('catalog_filters', cacheKey)).pipe(
          switchMap((cached) => {
            if (cached?.data) {
              return of(cached.data);
            }
            if (typeof localStorage !== 'undefined') {
              try {
                const raw = localStorage.getItem('aurora_last_tenants');
                if (raw) {
                  const parsed = JSON.parse(raw);
                  if (parsed?.data && parsed.data.length > 0) {
                    return of(parsed);
                  }
                }
              } catch (_) {}
            }
            return of({
              success: true,
              total: 1,
              data: [{ id_empresa: 1, nombre_empresa: 'Tienda Aurora', ciudad: 'Bolivia' }]
            });
          })
        );
      })
    );
  }

  resolverTenantPorSlug(slug: string): Observable<{ success: boolean; empresa: TenantPublico; filtros: FiltrosCatalogoResponse }> {
    return this.http.get<{ success: boolean; empresa: TenantPublico; filtros: FiltrosCatalogoResponse }>(
      `${this.apiUrl}/tenant-by-slug/${encodeURIComponent(slug.trim().toLowerCase())}`
    );
  }

  obtenerFiltros(id_empresa?: number, slug?: string): Observable<{ success: boolean; empresa: TenantPublico | null; data: FiltrosCatalogoResponse }> {
    const tenantId = id_empresa || 1;
    const scopeKey = this.indexedDb.buildPublicScopeKey(tenantId);
    const cacheKey = slug ? `filters_slug:${slug}` : `filters_e:${tenantId}`;

    let params = new HttpParams();
    if (id_empresa) params = params.set('id_empresa', id_empresa.toString());
    if (slug && slug.trim()) params = params.set('slug', slug.trim().toLowerCase());

    return this.http
      .get<{ success: boolean; empresa: TenantPublico | null; data: FiltrosCatalogoResponse }>(
        `${this.apiUrl}/filtros`,
        { params }
      )
      .pipe(
        tap((res) => {
          if (res?.success) {
            const now = Date.now();
            if (typeof localStorage !== 'undefined' && res.data) {
              try {
                localStorage.setItem(`aurora_last_filters_e_${tenantId}`, JSON.stringify(res));
                localStorage.setItem('aurora_last_filters_global', JSON.stringify(res));
              } catch (_) {}
            }
            this.indexedDb.put<CachedRecord>('catalog_filters', {
              key: cacheKey,
              scope_key: scopeKey,
              tenant_id: tenantId,
              data: res,
              fetched_at: new Date(now).toISOString(),
              fetched_at_ms: now,
              expires_at_ms: now + CATALOG_TTL_MS
            });
          }
        }),
        catchError((err) => {
          return from(this.indexedDb.get<CachedRecord>('catalog_filters', cacheKey)).pipe(
            switchMap((cached) => {
              if (cached?.data) {
                return of(cached.data);
              }
              if (typeof localStorage !== 'undefined') {
                try {
                  const raw =
                    localStorage.getItem(`aurora_last_filters_e_${tenantId}`) ||
                    localStorage.getItem('aurora_last_filters_global');
                  if (raw) {
                    const parsed = JSON.parse(raw);
                    if (parsed?.data) {
                      return of(parsed);
                    }
                  }
                } catch (_) {}
              }
              const fallbackFiltros = this.sintetizarFiltrosDesdeProductosLocales(tenantId);
              if (fallbackFiltros) {
                return of(fallbackFiltros);
              }
              return of({
                success: true,
                empresa: null,
                data: {
                  categorias: [],
                  tallas: [],
                  colores: [],
                  temporadas: [],
                  colecciones: []
                }
              });
            })
          );
        })
      );
  }

  private sintetizarFiltrosDesdeProductosLocales(tenantId: number): { success: boolean; empresa: TenantPublico | null; data: FiltrosCatalogoResponse } | null {
    if (typeof localStorage === 'undefined') return null;
    try {
      const keys = [`aurora_last_catalog_e_${tenantId}`, 'aurora_last_catalog_global', 'aurora_cached_products_list'];
      let rawList: PrendaCatalogo[] = [];
      let empresa: TenantPublico | null = null;
      for (const k of keys) {
        const raw = localStorage.getItem(k);
        if (raw) {
          const parsed = JSON.parse(raw);
          rawList = Array.isArray(parsed) ? parsed : (parsed?.data || parsed?.productos || []);
          empresa = parsed?.empresa || empresa;
          if (rawList.length > 0) break;
        }
      }
      if (!rawList.length) return null;

      const catMap = new Map<number, { id_categoria: number; nombre: string; total_prendas: number }>();
      const tallasMap = new Map<number, { id_talla: number; nombre: string }>();
      const coloresMap = new Map<number, { id_color: number; nombre: string; codigo_hex: string }>();
      const temporadasSet = new Set<string>();
      const coleccionesSet = new Set<string>();

      for (const p of rawList) {
        if (p.id_categoria && p.categoria_nombre) {
          const existing = catMap.get(p.id_categoria);
          if (existing) {
            existing.total_prendas++;
          } else {
            catMap.set(p.id_categoria, {
              id_categoria: p.id_categoria,
              nombre: p.categoria_nombre,
              total_prendas: 1
            });
          }
        }
        for (const t of p.tallas_disponibles || []) {
          if (t.id_talla) tallasMap.set(t.id_talla, t);
        }
        for (const c of p.colores_disponibles || []) {
          if (c.id_color) coloresMap.set(c.id_color, c);
        }
        if (p.temporada && p.temporada !== 'Todas') temporadasSet.add(p.temporada);
        if (p.coleccion && p.coleccion !== 'Todas') coleccionesSet.add(p.coleccion);
      }

      return {
        success: true,
        empresa: empresa || { id_empresa: tenantId, nombre_empresa: 'Tienda Aurora', ciudad: 'Bolivia' },
        data: {
          categorias: Array.from(catMap.values()),
          tallas: Array.from(tallasMap.values()),
          colores: Array.from(coloresMap.values()),
          temporadas: Array.from(temporadasSet.values()),
          colecciones: Array.from(coleccionesSet.values())
        }
      };
    } catch {
      return null;
    }
  }

  consultarProductos(filtros?: {
    id_empresa?: number;
    slug?: string;
    busqueda?: string;
    id_categoria?: number;
    publico?: string;
    id_sucursal?: number;
    id_talla?: number;
    id_color?: number;
    temporada?: string;
    coleccion?: string;
    precio_min?: number;
    precio_max?: number;
    orden?: string;
    limit?: number;
    offset?: number;
  }): Observable<RespuestaCatalogoProductos> {
    const tenantId = filtros?.id_empresa || 1;
    const scopeKey = this.indexedDb.buildPublicScopeKey(tenantId);

    let params = new HttpParams();
    if (filtros?.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());
    if (filtros?.slug && filtros.slug.trim()) params = params.set('slug', filtros.slug.trim().toLowerCase());
    if (filtros?.busqueda) params = params.set('busqueda', filtros.busqueda.trim());
    if (filtros?.id_categoria) params = params.set('id_categoria', filtros.id_categoria.toString());
    if (filtros?.publico && filtros.publico !== 'Todos') params = params.set('publico', filtros.publico);
    if (filtros?.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros?.id_talla) params = params.set('id_talla', filtros.id_talla.toString());
    if (filtros?.id_color) params = params.set('id_color', filtros.id_color.toString());
    if (filtros?.temporada && filtros.temporada !== 'Todas') params = params.set('temporada', filtros.temporada);
    if (filtros?.coleccion && filtros.coleccion !== 'Todas') params = params.set('coleccion', filtros.coleccion);
    if (filtros?.precio_min !== undefined && filtros?.precio_min !== null) params = params.set('precio_min', filtros.precio_min.toString());
    if (filtros?.precio_max !== undefined && filtros?.precio_max !== null) params = params.set('precio_max', filtros.precio_max.toString());
    if (filtros?.orden) params = params.set('orden', filtros.orden);
    if (filtros?.limit) params = params.set('limit', filtros.limit.toString());
    if (filtros?.offset) params = params.set('offset', filtros.offset.toString());

    const queryKey = `page_e:${tenantId}_${params.toString()}`;

    return this.http.get<RespuestaCatalogoProductos>(`${this.apiUrl}/productos`, { params }).pipe(
      tap((res) => {
        if (res?.success) {
          const now = Date.now();
          const nowIso = new Date(now).toISOString();
          this.lastCatalogMeta.set({
            fromCache: false,
            fetchedAt: nowIso,
            isPartial: false
          });
          if (typeof localStorage !== 'undefined' && Array.isArray(res.data)) {
            try {
              // Mantener un maestro acumulativo para que navegar entre páginas o pestañas no borre productos previos
              const masterKey = `aurora_catalog_master_e_${tenantId}`;
              let existingMaster: PrendaCatalogo[] = [];
              const rawMaster = localStorage.getItem(masterKey);
              if (rawMaster) {
                try {
                  const parsed = JSON.parse(rawMaster);
                  if (Array.isArray(parsed)) existingMaster = parsed;
                } catch (_) {}
              }
              const masterMap = new Map<number, PrendaCatalogo>();
              for (const item of existingMaster) {
                if (item?.id_producto) masterMap.set(item.id_producto, item);
              }
              for (const item of res.data) {
                if (item?.id_producto) masterMap.set(item.id_producto, item);
              }
              const mergedMaster = Array.from(masterMap.values());
              if (mergedMaster.length > 0) {
                localStorage.setItem(masterKey, JSON.stringify(mergedMaster));
                localStorage.setItem('aurora_cached_products_list', JSON.stringify(mergedMaster));
              }

              const offset = filtros?.offset || 0;
              if (offset === 0 && res.data.length > 0) {
                localStorage.setItem(`aurora_last_catalog_e_${tenantId}`, JSON.stringify(res));
                localStorage.setItem('aurora_last_catalog_global', JSON.stringify(res));
              }
            } catch (_) {}
          }
          if (Array.isArray(res.data)) {
            for (const prod of res.data) {
              if (prod?.id_producto) {
                this.indexedDb.put('product_details', {
                  key: `prod_e:${tenantId}_${prod.id_producto}`,
                  scope_key: scopeKey,
                  tenant_id: tenantId,
                  data: prod,
                  fetched_at: nowIso,
                  fetched_at_ms: now,
                  expires_at_ms: now + CATALOG_TTL_MS
                });
              }
            }
          }
          this.indexedDb.put<CachedRecord<RespuestaCatalogoProductos>>('products', {
            key: queryKey,
            scope_key: scopeKey,
            tenant_id: tenantId,
            data: res,
            fetched_at: nowIso,
            fetched_at_ms: now,
            expires_at_ms: now + CATALOG_TTL_MS
          });
        }
      }),
      catchError((err) => {
        return from(this.resolverCatalogoOffline(scopeKey, queryKey, tenantId, filtros)).pipe(
          switchMap((fallback) => {
            if (fallback) {
              return of(fallback);
            }
            return throwError(() => err);
          })
        );
      })
    );
  }

  /**
   * CU04W y CU05W: Resuelve listado y filtrado offline sobre páginas previamente descargadas
   * del tenant activo, indicando con transparencia si el resultado es un subconjunto local.
   */
  private async resolverCatalogoOffline(
    scopeKey: string,
    exactQueryKey: string,
    tenantId: number,
    filtros?: {
      id_empresa?: number;
      busqueda?: string;
      id_categoria?: number;
      id_talla?: number;
      id_color?: number;
      temporada?: string;
      coleccion?: string;
      precio_min?: number;
      precio_max?: number;
      orden?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<RespuestaCatalogoProductos | null> {
    const exact = await this.indexedDb.get<CachedRecord<RespuestaCatalogoProductos>>('products', exactQueryKey);
    const hasActiveFilter = Boolean(
      filtros?.busqueda?.trim() ||
        filtros?.id_categoria ||
        filtros?.id_talla ||
        filtros?.id_color ||
        (filtros?.temporada && filtros.temporada !== 'Todas') ||
        (filtros?.coleccion && filtros.coleccion !== 'Todas') ||
        filtros?.precio_min !== undefined ||
        filtros?.precio_max !== undefined
    );

    const exactItems = Array.isArray(exact?.data?.data) ? exact.data.data : [];
    if (exact?.data && !hasActiveFilter && exactItems.length > 0) {
      this.lastCatalogMeta.set({
        fromCache: true,
        fetchedAt: exact.fetched_at,
        isPartial: false
      });
      return {
        ...exact.data,
        _offline_metadata: {
          fromCache: true,
          fetchedAt: exact.fetched_at,
          isPartial: false
        }
      };
    }

    // CU05W: Consolidar productos únicos descargados en páginas de este tenant y aplicar filtros localmente
    let allPages = await this.indexedDb.getAllByScope<CachedRecord<RespuestaCatalogoProductos>>('products', scopeKey);
    if (!allPages.length) {
      allPages = await this.indexedDb.getAllByScope<CachedRecord<RespuestaCatalogoProductos>>('products', '');
    }

    const uniqueMap = new Map<number, PrendaCatalogo>();
    let latestFetchedAt: string | null = null;
    let latestMs = 0;
    let empresaInfo: TenantPublico | null = null;

    for (const page of allPages) {
      if ((page.fetched_at_ms || 0) > latestMs) {
        latestMs = page.fetched_at_ms;
        latestFetchedAt = page.fetched_at;
      }
      if (!empresaInfo && page.data?.empresa) {
        empresaInfo = page.data.empresa;
      }
      const rawList = Array.isArray(page.data)
        ? (page.data as any[])
        : (page.data?.data || (page.data as any)?.productos || []);
      for (const item of rawList) {
        const pId = item?.id_producto || item?.id;
        if (pId) {
          uniqueMap.set(pId, item);
        }
      }
    }

    let items = Array.from(uniqueMap.values());

    if (!items.length) {
      let details = await this.indexedDb.getAllByScope<CachedRecord>('product_details', scopeKey);
      if (!details.length) {
        details = await this.indexedDb.getAllByScope<CachedRecord>('product_details', '');
      }
      for (const d of details) {
        const prod = d.data;
        const pId = prod?.id_producto || prod?.id;
        if (pId) {
          uniqueMap.set(pId, prod);
        }
      }
      items = Array.from(uniqueMap.values());
    }

    // Respaldo de contingencia sincrónico si IndexedDB aún no tenía datos o estaba frío
    if (!items.length && typeof localStorage !== 'undefined') {
      try {
        const keys = [
          `aurora_catalog_master_e_${tenantId}`,
          `aurora_last_catalog_e_${tenantId}`,
          'aurora_last_catalog_global',
          'aurora_cached_products_list'
        ];
        for (const k of keys) {
          const raw = localStorage.getItem(k);
          if (raw) {
            const parsed = JSON.parse(raw);
            const rawList = Array.isArray(parsed)
              ? parsed
              : (parsed?.data || parsed?.productos || []);
            if (Array.isArray(rawList) && rawList.length > 0) {
              items = rawList;
              empresaInfo = parsed.empresa || empresaInfo;
              latestFetchedAt = latestFetchedAt || new Date().toISOString();
              break;
            }
          }
        }
      } catch (_) {}
    }

    if (!items.length) {
      return null;
    }

    if (filtros?.busqueda?.trim()) {
      const q = filtros.busqueda.trim().toLowerCase();
      items = items.filter(
        (p) =>
          (p.nombre || '').toLowerCase().includes(q) ||
          (p.marca || '').toLowerCase().includes(q) ||
          (p.categoria_nombre || '').toLowerCase().includes(q) ||
          (p.descripcion || '').toLowerCase().includes(q) ||
          (p.codigo_producto || '').toLowerCase().includes(q)
      );
    }

    if (filtros?.id_categoria) {
      items = items.filter((p) => Number(p.id_categoria) === Number(filtros.id_categoria));
    }

    if (filtros?.id_talla) {
      items = items.filter((p) =>
        (p.tallas_disponibles || []).some((t) => Number(t.id_talla) === Number(filtros.id_talla))
      );
    }

    if (filtros?.id_color) {
      items = items.filter((p) =>
        (p.colores_disponibles || []).some((c) => Number(c.id_color) === Number(filtros.id_color))
      );
    }

    if (filtros?.temporada && filtros.temporada !== 'Todas') {
      items = items.filter((p) => (p.temporada || '').toLowerCase() === filtros.temporada!.toLowerCase());
    }

    if (filtros?.coleccion && filtros.coleccion !== 'Todas') {
      items = items.filter((p) => (p.coleccion || '').toLowerCase() === filtros.coleccion!.toLowerCase());
    }

    if (filtros?.precio_min !== undefined && filtros?.precio_min !== null) {
      items = items.filter((p) => Number(p.promocion?.precio_promocional ?? p.precio) >= Number(filtros.precio_min));
    }

    if (filtros?.precio_max !== undefined && filtros?.precio_max !== null) {
      items = items.filter((p) => Number(p.promocion?.precio_promocional ?? p.precio) <= Number(filtros.precio_max));
    }

    const orden = filtros?.orden || 'recientes';
    if (orden === 'precio_asc') {
      items.sort((a, b) => Number(a.promocion?.precio_promocional ?? a.precio) - Number(b.promocion?.precio_promocional ?? b.precio));
    } else if (orden === 'precio_desc') {
      items.sort((a, b) => Number(b.promocion?.precio_promocional ?? b.precio) - Number(a.promocion?.precio_promocional ?? a.precio));
    } else if (orden === 'nombre_asc') {
      items.sort((a, b) => (a.nombre || '').localeCompare(b.nombre || ''));
    } else {
      items.sort((a, b) => Number(b.id_producto) - Number(a.id_producto));
    }

    const limit = filtros?.limit || 24;
    let offset = filtros?.offset || 0;
    if (offset >= items.length && items.length > 0) {
      offset = 0;
    }
    const paged = items.slice(offset, offset + limit);

    this.lastCatalogMeta.set({
      fromCache: true,
      fetchedAt: latestFetchedAt,
      isPartial: true
    });

    return {
      success: true,
      empresa: empresaInfo,
      total: items.length,
      limit,
      offset,
      data: paged,
      _offline_metadata: {
        fromCache: true,
        fetchedAt: latestFetchedAt,
        isPartial: true
      }
    };
  }

  obtenerDetalleProducto(
    id_producto: number,
    id_empresa?: number
  ): Observable<{ success: boolean; data: DetallePrendaCatalogo }> {
    const tenantId = id_empresa || 1;
    const scopeKey = this.indexedDb.buildPublicScopeKey(tenantId);
    const detailKey = `detail_e:${tenantId}_p:${id_producto}`;

    let params = new HttpParams();
    if (id_empresa) {
      params = params.set('id_empresa', id_empresa.toString());
    }

    return this.http
      .get<{ success: boolean; data: DetallePrendaCatalogo }>(`${this.apiUrl}/productos/${id_producto}`, { params })
      .pipe(
        tap((res) => {
          if (res?.success && res.data) {
            const now = Date.now();
            const nowIso = new Date(now).toISOString();
            this.lastDetailMeta.set({
              fromCache: false,
              fetchedAt: nowIso,
              isPartial: false
            });
            this.indexedDb.put<CachedRecord<DetallePrendaCatalogo>>('product_details', {
              key: detailKey,
              scope_key: scopeKey,
              tenant_id: res.data.id_empresa || tenantId,
              data: res.data,
              fetched_at: nowIso,
              fetched_at_ms: now,
              expires_at_ms: now + CATALOG_TTL_MS
            });
          }
        }),
        catchError((err) => {
          return from(this.resolverDetalleOffline(scopeKey, detailKey, id_producto, tenantId)).pipe(
            switchMap((cachedDetail) => {
              if (cachedDetail) {
                return of({ success: true, data: cachedDetail });
              }
              return throwError(() => err);
            })
          );
        })
      );
  }

  /**
   * CU06W y CU07W: Recupera el detalle de prenda desde IndexedDB si fue visitado antes,
   * o construye una vista honesta de resumen si solo se descargó la tarjeta en el listado.
   */
  private async resolverDetalleOffline(
    scopeKey: string,
    detailKey: string,
    idProducto: number,
    tenantId: number
  ): Promise<DetallePrendaCatalogo | null> {
    const cached = await this.indexedDb.get<CachedRecord<DetallePrendaCatalogo>>('product_details', detailKey);
    if (cached?.data) {
      this.lastDetailMeta.set({
        fromCache: true,
        fetchedAt: cached.fetched_at,
        isPartial: false
      });
      return {
        ...cached.data,
        _offline_metadata: {
          fromCache: true,
          fetchedAt: cached.fetched_at,
          isSummaryFallback: false
        }
      };
    }

    // Buscar si la prenda está en alguna página descargada de products
    const allPages = await this.indexedDb.getAllByScope<CachedRecord<RespuestaCatalogoProductos>>('products', scopeKey);
    for (const page of allPages) {
      const found = (page.data?.data || []).find((p) => Number(p.id_producto) === Number(idProducto));
      if (found) {
        this.lastDetailMeta.set({
          fromCache: true,
          fetchedAt: page.fetched_at,
          isPartial: true
        });
        return {
          id_producto: found.id_producto,
          id_empresa: found.id_empresa || tenantId,
          empresa_nombre: page.data?.empresa?.nombre_empresa || 'Tienda Aurora',
          id_categoria: found.id_categoria,
          categoria_nombre: found.categoria_nombre,
          codigo_producto: found.codigo_producto,
          nombre: found.nombre,
          descripcion: found.descripcion,
          marca: found.marca,
          genero: found.genero,
          precio: found.precio,
          temporada: found.temporada,
          coleccion: found.coleccion,
          fecha_registro: found.fecha_registro,
          imagenes: found.imagen_principal
            ? [
                {
                  id_imagen: 0,
                  imagen_url: found.imagen_principal,
                  public_id: '',
                  es_principal: true,
                  orden: 1
                }
              ]
            : [],
          imagen_principal: found.imagen_principal || null,
          variantes: [],
          tallas: found.tallas_disponibles || [],
          colores: found.colores_disponibles || [],
          sucursales_stock: [],
          stock_total_general: 0,
          hay_stock_disponible: false,
          permite_reserva: false,
          permite_compra: false,
          permite_vestidor_ra: false,
          promocion: found.promocion || null,
          _offline_metadata: {
            fromCache: true,
            fetchedAt: page.fetched_at,
            isSummaryFallback: true
          }
        };
      }
    }

    return null;
  }

  consultarDisponibilidadVariante(
    id_variante: number,
    id_empresa?: number
  ): Observable<{
    success: boolean;
    data: DisponibilidadVarianteResponse;
    _offline_metadata?: { fromCache: boolean; fetchedAt: string | null };
  }> {
    const tenantId = id_empresa || 1;
    const scopeKey = this.indexedDb.buildPublicScopeKey(tenantId);
    const snapKey = `var_stock_e:${tenantId}_v:${id_variante}`;

    let params = new HttpParams();
    if (id_empresa) {
      params = params.set('id_empresa', id_empresa.toString());
    }

    return this.http
      .get<{
        success: boolean;
        data: DisponibilidadVarianteResponse;
      }>(`${this.apiUrl}/variantes/${id_variante}/disponibilidad`, { params })
      .pipe(
        tap((res) => {
          if (res?.success && res.data) {
            const now = Date.now();
            this.indexedDb.put<CachedRecord<DisponibilidadVarianteResponse>>('stock_snapshots', {
              key: snapKey,
              scope_key: scopeKey,
              tenant_id: res.data.variante?.id_empresa || tenantId,
              data: res.data,
              fetched_at: new Date(now).toISOString(),
              fetched_at_ms: now,
              expires_at_ms: now + CATALOG_TTL_MS
            });
          }
        }),
        catchError((err) => {
          return from(this.indexedDb.get<CachedRecord<DisponibilidadVarianteResponse>>('stock_snapshots', snapKey)).pipe(
            switchMap((cached) => {
              if (cached?.data) {
                return of({
                  success: true,
                  data: cached.data,
                  _offline_metadata: {
                    fromCache: true,
                    fetchedAt: cached.fetched_at
                  }
                });
              }
              return throwError(() => err);
            })
          );
        })
      );
  }
}
