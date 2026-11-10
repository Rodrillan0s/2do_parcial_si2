import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';

export interface ItemResumenPago {
  id_variante: number;
  cantidad: number;
  precio_unitario: number;
  subtotal: number;
  producto_nombre: string;
  sku: string;
  talla: string;
  color: string;
}

export interface ResumenPedidoPago {
  id_pedido: number;
  codigo_pedido: string;
  id_cliente: number;
  id_empresa: number;
  id_sucursal: number;
  estado: string;
  estado_pago: string;
  subtotal: number;
  costo_envio: number;
  descuento: number;
  total: number;
  correo_contacto: string;
  nombre_contacto: string;
  id_venta?: number | null;
  sucursal_nombre: string;
  nombre_empresa: string;
  items: ItemResumenPago[];
  paypal_client_id?: string;
}

export interface ProcesarTarjetaPayload {
  id_pedido: number;
  titular: string;
  numero_tarjeta: string;
  mes_exp: string;
  anio_exp: string;
  cvv: string;
  nit_ci?: string;
  razon_social?: string;
  id_empresa?: number;
}

export interface ResultadoPago {
  id_pedido: number;
  codigo_pedido: string;
  id_venta: number;
  numero_venta: string;
  tipo_documento: string;
  total: number;
  metodo_pago: string;
  codigo_transaccion: string;
  url_descarga_pdf: string;
}

@Injectable({
  providedIn: 'root'
})
export class PagoService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/api/pagos`;
  private comprobanteUrl = `${environment.apiUrl}/api/comprobantes`;

  obtenerResumenPago(idPedido: number): Observable<{ success: boolean; data: ResumenPedidoPago }> {
    return this.http.get<{ success: boolean; data: ResumenPedidoPago }>(`${this.baseUrl}/resumen/${idPedido}`);
  }

  crearOrdenPayPal(idPedido: number, idEmpresa?: number): Observable<{ success: boolean; data: any; message: string }> {
    return this.http.post<{ success: boolean; data: any; message: string }>(`${this.baseUrl}/paypal/crear-orden`, {
      id_pedido: idPedido,
      id_empresa: idEmpresa
    });
  }

  capturarPayPal(payload: { id_pedido: number; order_id: string; nit_ci?: string; razon_social?: string }): Observable<{ success: boolean; data: ResultadoPago; message: string }> {
    return this.http.post<{ success: boolean; data: ResultadoPago; message: string }>(`${this.baseUrl}/paypal/capturar`, payload);
  }

  procesarTarjeta(payload: ProcesarTarjetaPayload): Observable<{ success: boolean; data: ResultadoPago; message: string }> {
    return this.http.post<{ success: boolean; data: ResultadoPago; message: string }>(`${this.baseUrl}/tarjeta/procesar`, payload);
  }

  cancelarPago(idPedido: number, motivo?: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/cancelar`, {
      id_pedido: idPedido,
      motivo: motivo || 'Cancelado por el usuario'
    });
  }

  descargarComprobanteVentaBlob(idVenta: number): Observable<Blob> {
    return this.http.get(`${this.comprobanteUrl}/venta/${idVenta}/pdf`, {
      responseType: 'blob'
    });
  }

  descargarComprobantePedidoBlob(idPedido: number): Observable<Blob> {
    return this.http.get(`${this.comprobanteUrl}/pedido/${idPedido}/pdf`, {
      responseType: 'blob'
    });
  }

  reenviarCorreoComprobante(idVenta: number, correoDestino?: string): Observable<{ success: boolean; message: string; correo: string }> {
    return this.http.post<{ success: boolean; message: string; correo: string }>(`${this.comprobanteUrl}/venta/${idVenta}/reenviar-correo`, {
      correo_destino: correoDestino
    });
  }

  iniciarPagoDelegado(payload: {
    intent_id: string;
    id_empresa: number;
    id_sucursal?: number;
    monto_total: number;
    items?: any[];
    cliente_nombre?: string;
    nit_ci?: string;
    razon_social?: string;
    id_pedido?: number;
    codigo_referencia?: string;
  }): Observable<{ success: boolean; message: string; data: any }> {
    return this.http.post<{ success: boolean; message: string; data: any }>(
      `${this.baseUrl}/paypal/delegado/iniciar`,
      payload
    );
  }

  capturarPagoDelegado(payload: {
    intent_id: string;
    order_id: string;
    nit_ci?: string;
    razon_social?: string;
  }): Observable<{ success: boolean; message: string; data: any }> {
    return this.http.post<{ success: boolean; message: string; data: any }>(
      `${this.baseUrl}/paypal/delegado/capturar`,
      payload
    );
  }

  consultarEstadoPagoDelegado(intentId: string): Observable<{
    success: boolean;
    status: string;
    capturado: boolean;
    message: string;
    data?: any;
    conflict_code?: string;
  }> {
    return this.http.get<{
      success: boolean;
      status: string;
      capturado: boolean;
      message: string;
      data?: any;
      conflict_code?: string;
    }>(`${this.baseUrl}/paypal/delegado/estado/${intentId}`);
  }
}
