import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';
import * as XLSX from 'xlsx';

export interface ReporteVentaItem {
  id_venta: number;
  numero_venta: string;
  fecha: string;
  sucursal: string;
  cliente: string;
  nit_ci: string;
  metodo_pago: string;
  subtotal: number;
  descuento: number;
  total: number;
  estado: string;
}

export interface ReporteVentasData {
  items: ReporteVentaItem[];
  resumen: {
    cantidad_ventas: number;
    total_recaudado: number;
    total_subtotal: number;
    total_descuento: number;
    ticket_promedio: number;
  };
}

export interface ReporteInventarioItem {
  id_producto: number;
  producto: string;
  sku: string;
  codigo_producto: string;
  categoria: string;
  talla: string;
  color: string;
  sucursal: string;
  stock_actual: number;
  stock_reservado: number;
  stock_disponible: number;
  stock_minimo: number;
  estado_alerta: string;
}

export interface ReporteInventarioData {
  items: ReporteInventarioItem[];
  resumen: {
    total_items_registrados: number;
    stock_total_unidades: number;
    stock_reservado_unidades: number;
    stock_disponible_unidades: number;
    items_agotados: number;
    items_bajo_stock: number;
  };
}

export interface ReporteProductoItem {
  id_producto: number;
  producto: string;
  sku: string;
  categoria: string;
  talla: string;
  color: string;
  unidades_vendidas: number;
  precio_promedio: number;
  total_ingresos: number;
  participacion_pct: number;
}

export interface ReporteProductosData {
  items: ReporteProductoItem[];
  resumen: {
    total_productos_distintos: number;
    total_unidades_vendidas: number;
    total_ingresos: number;
    precio_promedio_general: number;
  };
}

export interface ReporteSucursalItem {
  id_sucursal: number;
  sucursal: string;
  ciudad: string;
  telefono: string;
  cantidad_ventas: number;
  total_ingresos: number;
  unidades_vendidas: number;
  ticket_promedio: number;
  participacion_ingresos_pct: number;
}

export interface ReporteSucursalesData {
  items: ReporteSucursalItem[];
  resumen: {
    total_sucursales: number;
    total_ventas: number;
    total_ingresos: number;
    total_unidades_vendidas: number;
    ticket_promedio_general: number;
  };
}

export interface ReporteValoracionItem {
  id_valoracion: number;
  fecha: string;
  cliente: string;
  producto: string;
  categoria: string;
  sucursal: string;
  puntuacion: number;
  codigo_referencia: string;
  motivo_negativo: string;
  comentario: string;
  estado_satisfaccion: string;
  requiere_revision: boolean;
}

export interface ReporteValoracionesData {
  items: ReporteValoracionItem[];
  resumen: {
    total_valoraciones: number;
    calificacion_promedio: number;
    tasa_satisfaccion_pct: number;
    valoraciones_positivas: number;
    alertas_criticas: number;
  };
}

export interface RespuestaApiReporte<T> {
  success: boolean;
  message: string;
  data: T;
}

@Injectable({
  providedIn: 'root'
})
export class ReportesService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = environment.apiUrl;

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  // --- REPORTE 1: VENTAS ---
  obtenerReporteVentas(filtros: { fecha_inicio?: string; fecha_fin?: string; id_sucursal?: number; estado?: string; id_metodo_pago?: number; id_empresa?: number }): Observable<RespuestaApiReporte<ReporteVentasData>> {
    let params = new HttpParams().set('formato', 'json');
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    if (filtros.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros.estado) params = params.set('estado', filtros.estado);
    if (filtros.id_metodo_pago) params = params.set('id_metodo_pago', filtros.id_metodo_pago.toString());
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());

    return this.http.get<RespuestaApiReporte<ReporteVentasData>>(
      `${this.apiUrl}/api/reportes/ventas`,
      { headers: this.getHeaders(), params }
    );
  }

  descargarPdfVentas(filtros: { fecha_inicio?: string; fecha_fin?: string; id_sucursal?: number; estado?: string; id_metodo_pago?: number; id_empresa?: number }): Observable<Blob> {
    let params = new HttpParams().set('formato', 'pdf');
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    if (filtros.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros.estado) params = params.set('estado', filtros.estado);
    if (filtros.id_metodo_pago) params = params.set('id_metodo_pago', filtros.id_metodo_pago.toString());
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());

    return this.http.get(
      `${this.apiUrl}/api/reportes/ventas`,
      { headers: this.getHeaders(), params, responseType: 'blob' }
    );
  }

  // --- REPORTE 2: INVENTARIO ---
  obtenerReporteInventario(filtros: { id_sucursal?: number; id_categoria?: number; estado_stock?: string; id_empresa?: number }): Observable<RespuestaApiReporte<ReporteInventarioData>> {
    let params = new HttpParams().set('formato', 'json');
    if (filtros.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros.id_categoria) params = params.set('id_categoria', filtros.id_categoria.toString());
    if (filtros.estado_stock) params = params.set('estado_stock', filtros.estado_stock);
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());

    return this.http.get<RespuestaApiReporte<ReporteInventarioData>>(
      `${this.apiUrl}/api/reportes/inventario`,
      { headers: this.getHeaders(), params }
    );
  }

  descargarPdfInventario(filtros: { id_sucursal?: number; id_categoria?: number; estado_stock?: string; id_empresa?: number }): Observable<Blob> {
    let params = new HttpParams().set('formato', 'pdf');
    if (filtros.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros.id_categoria) params = params.set('id_categoria', filtros.id_categoria.toString());
    if (filtros.estado_stock) params = params.set('estado_stock', filtros.estado_stock);
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());

    return this.http.get(
      `${this.apiUrl}/api/reportes/inventario`,
      { headers: this.getHeaders(), params, responseType: 'blob' }
    );
  }

  // --- REPORTE 3: PRODUCTOS VENDIDOS ---
  obtenerReporteProductos(filtros: { fecha_inicio?: string; fecha_fin?: string; id_sucursal?: number; id_categoria?: number; id_empresa?: number }): Observable<RespuestaApiReporte<ReporteProductosData>> {
    let params = new HttpParams().set('formato', 'json');
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    if (filtros.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros.id_categoria) params = params.set('id_categoria', filtros.id_categoria.toString());
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());

    return this.http.get<RespuestaApiReporte<ReporteProductosData>>(
      `${this.apiUrl}/api/reportes/productos-vendidos`,
      { headers: this.getHeaders(), params }
    );
  }

  descargarPdfProductos(filtros: { fecha_inicio?: string; fecha_fin?: string; id_sucursal?: number; id_categoria?: number; id_empresa?: number }): Observable<Blob> {
    let params = new HttpParams().set('formato', 'pdf');
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    if (filtros.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros.id_categoria) params = params.set('id_categoria', filtros.id_categoria.toString());
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());

    return this.http.get(
      `${this.apiUrl}/api/reportes/productos-vendidos`,
      { headers: this.getHeaders(), params, responseType: 'blob' }
    );
  }

  // --- REPORTE 4: SUCURSALES ---
  obtenerReporteSucursales(filtros: { fecha_inicio?: string; fecha_fin?: string; id_empresa?: number }): Observable<RespuestaApiReporte<ReporteSucursalesData>> {
    let params = new HttpParams().set('formato', 'json');
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());

    return this.http.get<RespuestaApiReporte<ReporteSucursalesData>>(
      `${this.apiUrl}/api/reportes/sucursales`,
      { headers: this.getHeaders(), params }
    );
  }

  descargarPdfSucursales(filtros: { fecha_inicio?: string; fecha_fin?: string; id_empresa?: number }): Observable<Blob> {
    let params = new HttpParams().set('formato', 'pdf');
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());

    return this.http.get(
      `${this.apiUrl}/api/reportes/sucursales`,
      { headers: this.getHeaders(), params, responseType: 'blob' }
    );
  }

  // --- REPORTE 5: VALORACIONES Y SATISFACCIÓN (CSAT / CALIDAD) ---
  obtenerReporteValoraciones(filtros: {
    fecha_inicio?: string;
    fecha_fin?: string;
    id_sucursal?: number;
    puntuacion?: number;
    requiere_revision?: boolean;
    id_empresa?: number;
  }): Observable<RespuestaApiReporte<ReporteValoracionesData>> {
    let params = new HttpParams().set('formato', 'json');
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    if (filtros.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros.puntuacion) params = params.set('puntuacion', filtros.puntuacion.toString());
    if (filtros.requiere_revision !== undefined) params = params.set('requiere_revision', String(filtros.requiere_revision));
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());

    return this.http.get<RespuestaApiReporte<ReporteValoracionesData>>(
      `${this.apiUrl}/api/reportes/valoraciones`,
      { headers: this.getHeaders(), params }
    );
  }

  descargarPdfValoraciones(filtros: {
    fecha_inicio?: string;
    fecha_fin?: string;
    id_sucursal?: number;
    puntuacion?: number;
    requiere_revision?: boolean;
    id_empresa?: number;
  }): Observable<Blob> {
    let params = new HttpParams().set('formato', 'pdf');
    if (filtros.fecha_inicio) params = params.set('fecha_inicio', filtros.fecha_inicio);
    if (filtros.fecha_fin) params = params.set('fecha_fin', filtros.fecha_fin);
    if (filtros.id_sucursal) params = params.set('id_sucursal', filtros.id_sucursal.toString());
    if (filtros.puntuacion) params = params.set('puntuacion', filtros.puntuacion.toString());
    if (filtros.requiere_revision !== undefined) params = params.set('requiere_revision', String(filtros.requiere_revision));
    if (filtros.id_empresa) params = params.set('id_empresa', filtros.id_empresa.toString());

    return this.http.get(
      `${this.apiUrl}/api/reportes/valoraciones`,
      { headers: this.getHeaders(), params, responseType: 'blob' }
    );
  }

  // ============================================================================
  // EXPORTACIÓN A EXCEL (.XLSX) Y CSV (CU21W)
  // ============================================================================
  exportarACSV(filas: any[], nombreArchivo: string) {
    if (!filas || !filas.length) {
      alert('No hay datos para exportar a CSV.');
      return;
    }
    const headers = Object.keys(filas[0]);
    const csvRows = [
      headers.join(','),
      ...filas.map(row => headers.map(h => {
        let val = row[h] ?? '';
        val = String(val).replace(/"/g, '""');
        return `"${val}"`;
      }).join(','))
    ];
    const blob = new Blob(['\uFEFF' + csvRows.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${nombreArchivo}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  exportarAExcel(filas: any[], nombreArchivo: string, nombreHoja: string = 'Reporte') {
    if (!filas || !filas.length) {
      alert('No hay datos para exportar a Excel.');
      return;
    }

    const worksheet: XLSX.WorkSheet = XLSX.utils.json_to_sheet(filas);
    
    // Auto-ajustar ancho de columnas
    const colWidths = Object.keys(filas[0]).map(key => {
      const maxLen = Math.max(
        key.length,
        ...filas.map(row => (row[key] ? row[key].toString().length : 0))
      );
      return { wch: Math.min(Math.max(maxLen + 3, 10), 40) };
    });
    worksheet['!cols'] = colWidths;

    const workbook: XLSX.WorkBook = {
      Sheets: { [nombreHoja]: worksheet },
      SheetNames: [nombreHoja]
    };

    XLSX.writeFile(workbook, `${nombreArchivo}.xlsx`);
  }
}
