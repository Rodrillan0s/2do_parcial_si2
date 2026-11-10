import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, from, of, throwError } from 'rxjs';
import { catchError, switchMap, tap } from 'rxjs/operators';
import { environment } from '../../../../environments/environment';
import { CachedRecord, IndexedDbService } from '../../../core/storage/indexed-db.service';
import { AuthService } from '../../auth/services/auth';

export interface ImagenProducto {
  id_imagen?: number;
  imagen_url: string;
  public_id: string;
  es_principal?: boolean;
  orden?: number;
  created_at?: string;
  file?: File;
  subiendo?: boolean;
}

export interface VarianteProducto {
  id_variante?: number;
  id_talla: number;
  talla_nombre?: string;
  id_color: number;
  color_nombre?: string;
  codigo_hex?: string;
  sku?: string;
  precio?: number;
  activo?: boolean;
  estado?: boolean;
  tiene_stock?: boolean;
  total_movimientos?: number;
}

export interface PromocionProducto {
  id_promocion_producto?: number;
  id_promocion: number;
  nombre: string;
  descripcion?: string;
  fecha_inicio: string;
  fecha_fin: string;
  estado: boolean;
  porcentaje_descuento: number;
  vigente: boolean;
  precio_promocional?: number;
}
export interface Promocion {
  id_promocion: number;
  nombre: string;
  descripcion?: string;
  fecha_inicio: string;
  fecha_fin: string;
  estado: boolean;
  vigente: boolean;
}
export interface Producto {
  id_producto?: number;
  id_empresa?: number;
  empresa_nombre?: string;
  id_categoria: number;
  categoria_nombre?: string;
  codigo_producto?: string;
  nombre: string;
  descripcion?: string;
  marca?: string;
  genero?: string;
  precio: number;

  temporada?: string;
  temporada_actual?: string;
  es_temporada_actual?: boolean;

  coleccion?: string;
  activo: boolean;
  estado?: boolean;
  fecha_registro?: string;
  updated_at?: string;
  imagen_principal?: string;
  imagen_thumbnail?: string;
  total_imagenes?: number;
  total_variantes?: number;
  imagenes?: ImagenProducto[];
  variantes?: VarianteProducto[];

  tiene_ra?: boolean;
  tipo_prenda_ra?: 'TOP' | 'PANT' | 'DRESS' | string;
  modelo_2d_url?: string;

  tiene_promocion_vigente?: boolean;
  visible_para_clientes?: boolean;
  promocion?: PromocionProducto | null;
}

const ADMIN_PRODUCTS_TTL_MS = 12 * 60 * 60 * 1000;

@Injectable({
  providedIn: 'root'
})
export class ProductosService {
  private http = inject(HttpClient);
  private indexedDb = inject(IndexedDbService);
  private authService = inject(AuthService);
  private apiUrl = `${environment.apiUrl}/api/productos`;

  public offlineMeta = signal<{ fromCache: boolean; fetchedAt: string | null }>({
    fromCache: false,
    fetchedAt: null
  });

  private getPrivateScope(explicitEmpresaId?: number): { scopeKey: string; tenantId: number } {
    const user = this.authService.obtenerUsuarioActual();
    const uid = user?.id_usuario || 0;
    const tid = explicitEmpresaId || this.authService.getEffectiveCompanyId() || user?.id_empresa || 1;
    return {
      scopeKey: this.indexedDb.buildPrivateScopeKey(uid, tid),
      tenantId: tid
    };
  }

  listarProductos(filtros?: {
    id_empresa?: number;
    solo_activos?: boolean;
    id_categoria?: number;
    busqueda?: string;
    limit?: number;
    offset?: number;
  }): Observable<{ success: boolean; total: number; data: Producto[] }> {
    let params = new HttpParams();

    if (filtros?.id_empresa) {
      params = params.set('id_empresa', filtros.id_empresa.toString());
    }

    if (filtros?.solo_activos) {
      params = params.set('solo_activos', 'true');
    }

    if (filtros?.id_categoria) {
      params = params.set('id_categoria', filtros.id_categoria.toString());
    }

    if (filtros?.busqueda) {
      params = params.set('busqueda', filtros.busqueda);
    }

    if (filtros?.limit !== undefined) {
      params = params.set('limit', filtros.limit.toString());
    }

    if (filtros?.offset !== undefined) {
      params = params.set('offset', filtros.offset.toString());
    }

    const { scopeKey, tenantId } = this.getPrivateScope(filtros?.id_empresa);
    const cacheKey = `admin_prod_${scopeKey}_${params.toString()}`;

    return this.http
      .get<{
        success: boolean;
        total: number;
        data: Producto[];
      }>(this.apiUrl, { params })
      .pipe(
        tap((res) => {
          if (res?.success) {
            const now = Date.now();
            const nowIso = new Date(now).toISOString();
            this.offlineMeta.set({ fromCache: false, fetchedAt: nowIso });
            this.indexedDb.put<CachedRecord>('products', {
              key: cacheKey,
              scope_key: scopeKey,
              tenant_id: tenantId,
              data: res,
              fetched_at: nowIso,
              fetched_at_ms: now,
              expires_at_ms: now + ADMIN_PRODUCTS_TTL_MS
            });
          }
        }),
        catchError((err) => {
          return from(this.indexedDb.get<CachedRecord>('products', cacheKey)).pipe(
            switchMap((cached) => {
              if (cached?.data) {
                this.offlineMeta.set({ fromCache: true, fetchedAt: cached.fetched_at });
                return of(cached.data);
              }
              return throwError(() => err);
            })
          );
        })
      );
  }

  obtenerProducto(
    id_producto: number
  ): Observable<{ success: boolean; data: Producto }> {
    const { scopeKey, tenantId } = this.getPrivateScope();
    const detailKey = `admin_detail_${scopeKey}_${id_producto}`;

    return this.http
      .get<{
        success: boolean;
        data: Producto;
      }>(`${this.apiUrl}/${id_producto}`)
      .pipe(
        tap((res) => {
          if (res?.success && res.data) {
            const now = Date.now();
            this.indexedDb.put<CachedRecord>('product_details', {
              key: detailKey,
              scope_key: scopeKey,
              tenant_id: tenantId,
              data: res,
              fetched_at: new Date(now).toISOString(),
              fetched_at_ms: now,
              expires_at_ms: now + ADMIN_PRODUCTS_TTL_MS
            });
          }
        }),
        catchError((err) => {
          return from(this.indexedDb.get<CachedRecord>('product_details', detailKey)).pipe(
            switchMap((cached) => {
              if (cached?.data) {
                return of(cached.data);
              }
              return throwError(() => err);
            })
          );
        })
      );
  }

  crearProducto(datos: {
    id_empresa?: number;
    id_categoria: number;
    nombre: string;
    precio: number;
    descripcion?: string;
    codigo_producto?: string;
    temporada?: string;
    coleccion?: string;
    marca?: string;
    genero?: string;
    activo?: boolean;
    tallas_ids?: number[];
    colores_ids?: number[];
    imagenes?: {
      imagen_url: string;
      public_id: string;
      es_principal?: boolean;
    }[];
    tiene_ra?: boolean;
    tipo_prenda_ra?: string;
    modelo_2d_url?: string;
  }): Observable<any> {
    return this.http.post(this.apiUrl, datos);
  }

  actualizarProducto(id_producto: number, datos: {
    id_categoria: number;
    nombre: string;
    precio: number;
    descripcion?: string;
    codigo_producto?: string;
    temporada?: string;
    coleccion?: string;
    marca?: string;
    genero?: string;
    activo?: boolean;
    tallas_ids?: number[];
    colores_ids?: number[];
    tiene_ra?: boolean;
    tipo_prenda_ra?: string;
    modelo_2d_url?: string;
  }): Observable<any> {
    return this.http.put(`${this.apiUrl}/${id_producto}`, datos);
  }

  cambiarEstado(
    id_producto: number,
    activo: boolean
  ): Observable<any> {
    return this.http.put(
      `${this.apiUrl}/${id_producto}/estado`,
      { activo }
    );
  }
  listarPromociones(
    solo_activas: boolean = true
  ): Observable<{
    success: boolean;
    total: number;
    data: Promocion[];
  }> {
    let params = new HttpParams()
      .set('solo_activas', solo_activas.toString());

    return this.http.get<{
      success: boolean;
      total: number;
      data: Promocion[];
    }>(
      `${this.apiUrl}/promociones`,
      { params }
    );
  }

  eliminarProducto(
    id_producto: number
  ): Observable<{
    success: boolean;
    action: string;
    message: string;
  }> {
    return this.http.delete<{
      success: boolean;
      action: string;
      message: string;
    }>(`${this.apiUrl}/${id_producto}`);
  }

  subirImagenCloudinary(
    archivo: File
  ): Observable<{
    success: boolean;
    message: string;
    data: {
      imagen_url: string;
      public_id: string;
    };
  }> {
    const formData = new FormData();
    formData.append('file', archivo);

    return this.http.post<{
      success: boolean;
      message: string;
      data: {
        imagen_url: string;
        public_id: string;
      };
    }>(
      `${this.apiUrl}/upload-image`,
      formData
    );
  }

  agregarImagenAProducto(
    id_producto: number,
    imagen_url: string,
    public_id: string,
    es_principal: boolean = false
  ): Observable<any> {
    return this.http.post(
      `${this.apiUrl}/${id_producto}/imagenes`,
      {
        imagen_url,
        public_id,
        es_principal
      }
    );
  }

  marcarPortada(
    id_producto: number,
    id_imagen: number
  ): Observable<any> {
    return this.http.put(
      `${this.apiUrl}/${id_producto}/imagenes/${id_imagen}/principal`,
      {}
    );
  }

  eliminarImagen(
    id_producto: number,
    id_imagen: number
  ): Observable<any> {
    return this.http.delete(
      `${this.apiUrl}/${id_producto}/imagenes/${id_imagen}`
    );
  }

  // ==========================================================================
  // PROMOCIONES
  // ==========================================================================

  asignarPromocion(
    id_producto: number,
    id_promocion: number,
    porcentaje_descuento: number
  ): Observable<{
    success: boolean;
    message: string;
    id_promocion_producto: number;
  }> {
    let params = new HttpParams()
      .set('id_promocion', id_promocion.toString())
      .set('porcentaje_descuento', porcentaje_descuento.toString());

    return this.http.post<{
      success: boolean;
      message: string;
      id_promocion_producto: number;
    }>(
      `${this.apiUrl}/${id_producto}/promocion`,
      {},
      { params }
    );
  }

  listarPromocionesProducto(
    id_producto: number
  ): Observable<{
    success: boolean;
    total: number;
    data: PromocionProducto[];
  }> {
    return this.http.get<{
      success: boolean;
      total: number;
      data: PromocionProducto[];
    }>(
      `${this.apiUrl}/${id_producto}/promociones`
    );
  }

  obtenerPromocionVigente(
    id_producto: number
  ): Observable<{
    success: boolean;
    data: PromocionProducto | null;
  }> {
    return this.http.get<{
      success: boolean;
      data: PromocionProducto | null;
    }>(
      `${this.apiUrl}/${id_producto}/promocion-vigente`
    );
  }

  eliminarPromocion(
    id_producto: number,
    id_promocion_producto: number
  ): Observable<{
    success: boolean;
    message: string;
    data: any;
  }> {
    return this.http.delete<{
      success: boolean;
      message: string;
      data: any;
    }>(
      `${this.apiUrl}/${id_producto}/promociones/${id_promocion_producto}`
    );
  }
}
