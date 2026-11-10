import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export interface FilaPreview {
  fila_excel: number;
  codigo_producto: string;
  nombre_producto: string;
  categoria: string;
  categoria_nueva: boolean;
  genero: string;
  talla: string;
  talla_nueva: boolean;
  color: string;
  color_nuevo: boolean;
  sku: string;
  cantidad: number;
  costo_unitario: number;
  precio_venta: number;
  subtotal_costo: number;
  stock_minimo: number;
  proveedor: string;
  numero_lote: string;
  estado: 'NUEVO_PRODUCTO' | 'PRODUCTO_EXISTENTE' | 'ERROR';
  errores: string[];
}

export interface PreviewResultadoData {
  valido: boolean;
  total_filas: number;
  filas_validas: number;
  filas_con_error: number;
  total_prendas: number;
  costo_total: number;
  valor_venta_total: number;
  margen_bruto_estimado: number;
  productos_nuevos: number;
  productos_existentes: number;
  filas: FilaPreview[];
}

export interface DetalleOrdenCompraItem {
  id_detalle_orden: number;
  id_producto?: number;
  id_variante?: number;
  codigo_producto: string;
  nombre_producto: string;
  talla: string;
  color: string;
  sku: string;
  cantidad_solicitada: number;
  cantidad_recibida: number;
  costo_unitario: number;
  subtotal: number;
}

export interface OrdenCompraItem {
  id_orden_compra: number;
  numero_orden: string;
  id_sucursal: number;
  sucursal: string;
  id_proveedor?: number;
  proveedor: string;
  fecha_emision: string;
  fecha_entrega_esperada?: string;
  estado: 'BORRADOR' | 'PENDIENTE_APROBACION' | 'APROBADA' | 'RECIBIDA_TOTAL' | 'RECIBIDA_PARCIAL' | 'RECHAZADA' | 'CANCELADA';
  total_estimado: number;
  observaciones?: string;
  creador: string;
  aprobador?: string;
  fecha_aprobacion?: string;
  motivo_rechazo?: string;
  total_items?: number;
  total_prendas?: number;
  items?: DetalleOrdenCompraItem[];
}

export interface LoteIngresoItem {
  id_lote: number;
  numero_lote: string;
  id_sucursal: number;
  sucursal: string;
  id_orden_compra?: number;
  orden_compra: string;
  proveedor: string;
  fecha_ingreso: string;
  guia_remision?: string;
  total_prendas: number;
  costo_total_lote: number;
  receptor: string;
  observaciones?: string;
}

export interface CrearItemOrdenPayload {
  id_producto?: number;
  id_variante?: number;
  codigo_producto: string;
  nombre_producto: string;
  talla?: string;
  color?: string;
  sku?: string;
  cantidad_solicitada: number;
  costo_unitario: number;
}

export interface CrearOrdenCompraPayload {
  id_sucursal: number;
  id_empresa?: number;
  id_proveedor?: number | null;
  fecha_entrega_esperada?: string;
  observaciones?: string;
  items: CrearItemOrdenPayload[];
}

@Injectable({
  providedIn: 'root'
})
export class ComprasLotesService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = environment.apiUrl;

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  // ============================================================================
  // 1. PLANTILLA EXCEL E IMPORTACIÓN MASIVA
  // ============================================================================

  descargarPlantillaExcel(): Observable<Blob> {
    let params = new HttpParams();
    const idEmpresa = this.authService.getEffectiveCompanyId();
    if (idEmpresa) params = params.set('id_empresa', idEmpresa.toString());

    return this.http.get(
      `${this.apiUrl}/api/inventario/importacion/plantilla`,
      { headers: this.getHeaders(), params, responseType: 'blob' }
    );
  }

  previsualizarArchivoExcel(archivo: File, idSucursal?: number): Observable<{ success: boolean; data: PreviewResultadoData }> {
    const formData = new FormData();
    formData.append('archivo', archivo, archivo.name);
    const idEmpresa = this.authService.getEffectiveCompanyId();
    if (idSucursal) {
      formData.append('id_sucursal', idSucursal.toString());
    }
    if (idEmpresa) {
      formData.append('id_empresa', idEmpresa.toString());
    }

    return this.http.post<{ success: boolean; data: PreviewResultadoData }>(
      `${this.apiUrl}/api/inventario/importacion/preview`,
      formData,
      { headers: this.getHeaders() }
    );
  }

  confirmarImportacion(payload: {
    id_sucursal: number;
    id_empresa?: number | null;
    filas: FilaPreview[];
    generar_orden_compra: boolean;
    id_proveedor?: number | null;
    numero_lote?: string;
    guia_remision?: string;
    observaciones?: string;
  }): Observable<any> {
    const effectiveCompany = payload.id_empresa ?? this.authService.getEffectiveCompanyId();
    const body = {
      ...payload,
      id_empresa: effectiveCompany
    };
    return this.http.post(
      `${this.apiUrl}/api/inventario/importacion/confirmar`,
      body,
      { headers: this.getHeaders() }
    );
  }

  // ============================================================================
  // 2. ÓRDENES DE COMPRA & LOTES (POR SUCURSAL Y TENANT)
  // ============================================================================

  listarOrdenesCompra(filtros?: { id_sucursal?: number; estado?: string; id_empresa?: number }): Observable<{ success: boolean; ordenes: OrdenCompraItem[]; total: number }> {
    let params = new HttpParams();
    const effectiveCompany = filtros?.id_empresa ?? this.authService.getEffectiveCompanyId();
    if (effectiveCompany) params = params.set('id_empresa', effectiveCompany.toString());
    if (filtros?.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros?.estado && filtros.estado !== 'TODOS') params = params.set('estado', filtros.estado);

    return this.http.get<{ success: boolean; ordenes: OrdenCompraItem[]; total: number }>(
      `${this.apiUrl}/api/compras/ordenes`,
      { headers: this.getHeaders(), params }
    );
  }

  crearOrdenCompra(payload: CrearOrdenCompraPayload): Observable<{ success: boolean; mensaje: string; orden: OrdenCompraItem }> {
    const effectiveCompany = payload.id_empresa ?? this.authService.getEffectiveCompanyId();
    const body = {
      ...payload,
      id_empresa: effectiveCompany
    };
    return this.http.post<{ success: boolean; mensaje: string; orden: OrdenCompraItem }>(
      `${this.apiUrl}/api/compras/ordenes`,
      body,
      { headers: this.getHeaders() }
    );
  }

  obtenerDetalleOrden(idOrden: number, idEmpresa?: number): Observable<{ success: boolean; orden: OrdenCompraItem }> {
    let params = new HttpParams();
    const effectiveCompany = idEmpresa ?? this.authService.getEffectiveCompanyId();
    if (effectiveCompany) params = params.set('id_empresa', effectiveCompany.toString());

    return this.http.get<{ success: boolean; orden: OrdenCompraItem }>(
      `${this.apiUrl}/api/compras/ordenes/${idOrden}`,
      { headers: this.getHeaders(), params }
    );
  }

  aprobarOrdenCompra(idOrden: number): Observable<any> {
    return this.http.put(
      `${this.apiUrl}/api/compras/ordenes/${idOrden}/aprobar`,
      {},
      { headers: this.getHeaders() }
    );
  }

  rechazarOrdenCompra(idOrden: number, motivo: string): Observable<any> {
    return this.http.put(
      `${this.apiUrl}/api/compras/ordenes/${idOrden}/rechazar`,
      { motivo },
      { headers: this.getHeaders() }
    );
  }

  recibirMercaderiaOrden(idOrden: number, payload: { numero_lote?: string; guia_remision?: string; observaciones?: string }): Observable<any> {
    return this.http.post(
      `${this.apiUrl}/api/compras/ordenes/${idOrden}/recibir`,
      payload,
      { headers: this.getHeaders() }
    );
  }

  listarLotes(filtros?: { id_sucursal?: number; id_empresa?: number } | number): Observable<{ success: boolean; lotes: LoteIngresoItem[]; total: number }> {
    let params = new HttpParams();
    const effectiveCompany = typeof filtros === 'object' && filtros?.id_empresa 
      ? filtros.id_empresa 
      : this.authService.getEffectiveCompanyId();
    if (effectiveCompany) params = params.set('id_empresa', effectiveCompany.toString());

    const idSucursal = typeof filtros === 'number' ? filtros : filtros?.id_sucursal;
    if (idSucursal) params = params.set('id_sucursal', idSucursal.toString());

    return this.http.get<{ success: boolean; lotes: LoteIngresoItem[]; total: number }>(
      `${this.apiUrl}/api/compras/lotes`,
      { headers: this.getHeaders(), params }
    );
  }
}
