import { Component, OnInit, OnDestroy, inject, ChangeDetectorRef, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { firstValueFrom, combineLatest } from 'rxjs';

import { PagoService, ResumenPedidoPago, ResultadoPago, ProcesarTarjetaPayload } from '../../services/pago';
import { AuthService } from '../../services/auth';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-pago',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './pago.html',
  styleUrls: ['./pago.css']
})
export class PagoComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private pagoService = inject(PagoService);
  public authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);

  // Estado del pedido
  idPedido: number = 0;
  pedido: ResumenPedidoPago | null = null;
  cargando: boolean = true;
  errorCarga: string | null = null;

  // Estado del flujo de pago: SELECCIONANDO | PROCESANDO | APROBADO | RECHAZADO | CANCELADO
  estadoPago: 'SELECCIONANDO' | 'PROCESANDO' | 'APROBADO' | 'RECHAZADO' | 'CANCELADO' = 'SELECCIONANDO';
  mensajeError: string | null = null;
  mensajeExito: string | null = null;
  procesando: boolean = false;

  // Método de pago: Solo 'TARJETA' o 'PAYPAL' (sin sandbox visible)
  metodoSeleccionado: 'TARJETA' | 'PAYPAL' = 'TARJETA';

  // Datos del formulario de Tarjeta
  titularTarjeta: string = '';
  numeroTarjeta: string = '';
  mesExpiracion: string = '';
  anioExpiracion: string = '';
  cvvTarjeta: string = '';

  // Facturación opcional
  deseaFactura: boolean = false;
  nitCi: string = '';
  razonSocial: string = '';

  // Datos de resultado tras pago exitoso (W29)
  resultadoPago: ResultadoPago | null = null;
  descargandoPdf: boolean = false;
  reenviandoCorreo: boolean = false;
  correoReenvioMensaje: string | null = null;

  // Datos de flujo PayPal (W27)
  paypalOrderId: string | null = null;
  cargandoSdkPayPal: boolean = false;
  paypalSdkCargado: boolean = false;
  paypalBotonRenderizado: boolean = false;

  // Listener para mensajes provenientes de popups de PayPal
  private mensajeHandler = (event: MessageEvent) => {
    if (!event.data) return;
    if (event.data.type === 'PAYPAL_ORDER_APPROVED') {
      const orderId = event.data.orderId;
      if (orderId && !this.procesando && this.estadoPago !== 'APROBADO') {
        this.capturarOrdenPayPalDirecta(this.idPedido, orderId);
      }
    } else if (event.data.type === 'PAYPAL_ORDER_COMPLETED' && event.data.data) {
      this.procesando = false;
      this.resultadoPago = event.data.data;
      this.estadoPago = 'APROBADO';
      this.mensajeExito = '¡Pago con PayPal verificado y venta confirmada exitosamente!';
      this.cdr.detectChanges();
    }
  };

  // Listener para sincronización entre pestañas/ventanas con localStorage
  private storageHandler = (event: StorageEvent) => {
    if (event.key === `aura_pago_exitoso_${this.idPedido}` && event.newValue) {
      try {
        const data = JSON.parse(event.newValue);
        this.procesando = false;
        this.resultadoPago = data;
        this.estadoPago = 'APROBADO';
        this.mensajeExito = '¡Pago con PayPal verificado y venta confirmada exitosamente!';
        this.cdr.detectChanges();
      } catch (e) {
        console.error('Error procesando sync de pago:', e);
      }
    }
  };

  ngOnInit(): void {
    if (!this.authService.estaAutenticado()) {
      this.router.navigate(['/login']);
      return;
    }

    // Escuchar eventos entre ventanas y pestañas
    window.addEventListener('message', this.mensajeHandler);
    window.addEventListener('storage', this.storageHandler);

    combineLatest([this.route.params, this.route.queryParams])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(([params, queryParams]) => {
        const id = parseInt(params['id'], 10);
        if (isNaN(id) || id <= 0) {
          this.errorCarga = 'Identificador de pedido inválido.';
          this.cargando = false;
          return;
        }
        this.idPedido = id;

        // Verificar si existe confirmación previa en localStorage para este pedido
        try {
          const stored = localStorage.getItem(`aura_pago_exitoso_${this.idPedido}`);
          if (stored) {
            const data = JSON.parse(stored);
            this.resultadoPago = data;
            this.estadoPago = 'APROBADO';
            this.cargando = false;
            this.cdr.detectChanges();
            return;
          }
        } catch (_) {}

        // VERIFICAR SI VENIMOS DE UN RETORNO DE PAYPAL (?token=...&PayerID=...)
        const token = queryParams['token'];
        const payerId = queryParams['PayerID'];

        if (token) {
          // Si esta ventana tiene opener, notificar inmediatamente
          if (window.opener && !window.opener.closed) {
            try {
              window.opener.postMessage({ type: 'PAYPAL_ORDER_APPROVED', orderId: token, payerId: payerId }, '*');
            } catch (_) {}
          }

          // Proceder con la captura de la orden sin quedar bloqueado
          this.cargando = true;
          this.pagoService.obtenerResumenPago(this.idPedido)
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
              next: (res) => {
                this.cargando = false;
                if (res && res.success && res.data) {
                  this.pedido = res.data;
                  if (this.pedido.estado_pago === 'PAGADO') {
                    this.errorCarga = `El pedido ${this.pedido.codigo_pedido} ya ha sido pagado previamente.`;
                    this.cdr.detectChanges();
                    return;
                  }
                  // Capturar inmediatamente la orden de PayPal
                  this.capturarOrdenPayPalDirecta(this.idPedido, token);
                }
              },
              error: (err) => {
                this.cargando = false;
                this.errorCarga = err.error?.detail || 'Error al conectar con el servidor para consultar el pedido.';
                this.cdr.detectChanges();
              }
            });
          return;
        }

        // Carga normal sin retorno previo
        if (!this.pedido || this.pedido.id_pedido !== this.idPedido) {
          this.cargarResumenPedido();
        }
      });
  }

  ngOnDestroy(): void {
    window.removeEventListener('message', this.mensajeHandler);
    window.removeEventListener('storage', this.storageHandler);
  }

  cargarResumenPedido(): void {
    this.cargando = true;
    this.errorCarga = null;

    this.pagoService.obtenerResumenPago(this.idPedido)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.cargando = false;
          if (res && res.success && res.data) {
            this.pedido = res.data;
            if (this.pedido.nombre_contacto && !this.titularTarjeta) {
              this.titularTarjeta = this.pedido.nombre_contacto.toUpperCase();
            }
            if (this.pedido.estado_pago === 'PAGADO') {
              this.errorCarga = `El pedido ${this.pedido.codigo_pedido} ya ha sido pagado previamente.`;
            }
          } else {
            this.errorCarga = 'No se pudo recuperar los datos del pedido.';
          }
          this.cdr.detectChanges();
        },
        error: (err) => {
          this.cargando = false;
          this.errorCarga = err.error?.detail || 'Error al conectar con el servidor para consultar el pedido.';
          this.cdr.detectChanges();
        }
      });
  }

  seleccionarMetodo(metodo: 'TARJETA' | 'PAYPAL'): void {
    if (this.procesando) return;
    this.metodoSeleccionado = metodo;
    this.mensajeError = null;
    if (metodo === 'PAYPAL') {
      this.cdr.detectChanges();
      this.renderizarBotonPayPal();
    }
  }

  formatearNumeroTarjeta(event: any): void {
    let input = event.target.value.replace(/\D/g, '');
    if (input.length > 16) input = input.substring(0, 16);
    const parts = input.match(/.{1,4}/g);
    this.numeroTarjeta = parts ? parts.join(' ') : input;
  }

  formularioTarjetaValido(): boolean {
    const rawNumber = this.numeroTarjeta.replace(/\s+/g, '');
    if (!this.titularTarjeta.trim()) return false;
    if (rawNumber.length < 13 || rawNumber.length > 19) return false;
    if (!this.mesExpiracion || this.mesExpiracion.length !== 2) return false;
    if (!this.anioExpiracion || (this.anioExpiracion.length !== 2 && this.anioExpiracion.length !== 4)) return false;
    if (!this.cvvTarjeta || this.cvvTarjeta.length < 3) return false;
    if (this.deseaFactura && (!this.nitCi.trim() || !this.razonSocial.trim())) return false;
    return true;
  }

  // --- PROCESAR PAGO CON TARJETA (W27) ---
  pagarConTarjeta(): void {
    if (this.procesando || !this.pedido) return;
    this.mensajeError = null;

    if (!this.formularioTarjetaValido()) {
      this.mensajeError = 'Por favor complete todos los datos de la tarjeta correctamente.';
      return;
    }

    const cleanNumber = this.numeroTarjeta.replace(/\s+/g, '');
    this.procesando = true;
    this.estadoPago = 'PROCESANDO';
    this.cdr.detectChanges();

    const payload: ProcesarTarjetaPayload = {
      id_pedido: this.pedido.id_pedido,
      titular: this.titularTarjeta.trim(),
      numero_tarjeta: cleanNumber,
      mes_exp: this.mesExpiracion.trim(),
      anio_exp: this.anioExpiracion.trim(),
      cvv: this.cvvTarjeta.trim(),
      nit_ci: this.deseaFactura ? this.nitCi.trim() : undefined,
      razon_social: this.deseaFactura ? this.razonSocial.trim() : undefined,
      id_empresa: this.pedido.id_empresa
    };

    this.pagoService.procesarTarjeta(payload)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.procesando = false;
          if (res && res.success && res.data) {
            this.resultadoPago = res.data;
            this.estadoPago = 'APROBADO';
            this.mensajeExito = res.message || 'Pago procesado exitosamente.';
          } else {
            this.estadoPago = 'RECHAZADO';
            this.mensajeError = res?.message || 'La tarjeta fue rechazada por la pasarela de pagos.';
          }
          this.cdr.detectChanges();
        },
        error: (err) => {
          this.procesando = false;
          this.estadoPago = 'RECHAZADO';
          this.mensajeError = err.error?.detail || 'Ocurrió un error al procesar la tarjeta. Por favor verifica tus datos e intenta nuevamente.';
          this.cdr.detectChanges();
        }
      });
  }

  // --- INTEGRACIÓN OFICIAL PAYPAL JS SDK (W27) ---
  private cargarScriptPayPal(clientId: string): Promise<any> {
    if ((window as any).paypal) {
      this.paypalSdkCargado = true;
      return Promise.resolve((window as any).paypal);
    }
    this.cargandoSdkPayPal = true;
    this.cdr.detectChanges();

    return new Promise((resolve, reject) => {
      const existingScript = document.getElementById('paypal-js-sdk');
      if (existingScript) {
        existingScript.remove();
      }

      const script = document.createElement('script');
      script.id = 'paypal-js-sdk';
      script.src = `https://www.paypal.com/sdk/js?client-id=${clientId}&currency=USD&intent=capture&components=buttons`;
      script.async = true;
      script.onload = () => {
        this.cargandoSdkPayPal = false;
        this.paypalSdkCargado = true;
        this.cdr.detectChanges();
        resolve((window as any).paypal);
      };
      script.onerror = (err) => {
        this.cargandoSdkPayPal = false;
        this.mensajeError = 'No fue posible cargar el componente de PayPal. Por favor verifica tu conexión a internet.';
        this.cdr.detectChanges();
        reject(err);
      };
      document.body.appendChild(script);
    });
  }

  renderizarBotonPayPal(): void {
    if (!this.pedido) return;

    const clientId = this.pedido.paypal_client_id || environment.paypalClientId;
    this.cargarScriptPayPal(clientId).then((paypal) => {
      if (!paypal || !paypal.Buttons) return;

      setTimeout(() => {
        const container = document.getElementById('paypal-button-container');
        if (!container) return;
        container.innerHTML = '';

        paypal.Buttons({
          style: {
            layout: 'vertical',
            color: 'gold',
            shape: 'rect',
            label: 'paypal',
            height: 48
          },
          createOrder: async () => {
            if (this.procesando || !this.pedido) {
              throw new Error('Operación en curso');
            }
            this.mensajeError = null;
            this.cdr.detectChanges();

            try {
              const res = await firstValueFrom(
                this.pagoService.crearOrdenPayPal(this.pedido.id_pedido, this.pedido.id_empresa)
              );
              if (!res || !res.success || !res.data?.order_id) {
                throw new Error(res?.message || 'No se pudo crear la orden en PayPal');
              }
              this.paypalOrderId = res.data.order_id;
              return res.data.order_id;
            } catch (err: any) {
              this.mensajeError = err?.error?.detail || err?.message || 'Error al iniciar la orden con PayPal';
              this.cdr.detectChanges();
              throw err;
            }
          },
          onApprove: async (data: any) => {
            // 1. PayPal cierra el popup automáticamente
            // 2. La ventana principal recibe onApprove()
            // 3. Envía paypal_order_id al backend para verificación y captura
            const orderId = data.orderID || this.paypalOrderId;
            this.capturarOrdenPayPalDirecta(this.pedido!.id_pedido, orderId);
          },
          onCancel: (data: any) => {
            // Regla W27: El cierre del Popup NO significa pago exitoso. Mantener pedido PENDIENTE_PAGO.
            this.procesando = false;
            this.estadoPago = 'SELECCIONANDO';
            this.mensajeError = 'Transacción cancelada en PayPal. El pedido permanece PENDIENTE_PAGO.';
            this.cdr.detectChanges();
          },
          onError: (err: any) => {
            this.procesando = false;
            this.estadoPago = 'RECHAZADO';
            this.mensajeError = 'Ocurrió un error en la pasarela de PayPal. Intente nuevamente.';
            this.cdr.detectChanges();
          }
        }).render('#paypal-button-container');

        this.paypalBotonRenderizado = true;
      }, 60);
    }).catch(err => {
      console.error('Error cargando o renderizando botón de PayPal:', err);
    });
  }

  capturarOrdenPayPalDirecta(idPedido: number, orderId: string): void {
    if (this.procesando || this.estadoPago === 'APROBADO') return;
    this.procesando = true;
    this.estadoPago = 'PROCESANDO';
    this.mensajeError = null;
    this.cdr.detectChanges();

    this.pagoService.capturarPayPal({
      id_pedido: idPedido,
      order_id: orderId,
      nit_ci: this.deseaFactura ? this.nitCi.trim() : undefined,
      razon_social: this.deseaFactura ? this.razonSocial.trim() : undefined
    })
    .pipe(takeUntilDestroyed(this.destroyRef))
    .subscribe({
      next: (res) => {
        this.procesando = false;
        if (res && res.success && res.data) {
          this.resultadoPago = res.data;
          this.estadoPago = 'APROBADO';
          this.mensajeExito = res.message || '¡Pago con PayPal verificado y venta confirmada exitosamente!';

          // Guardar en localStorage para sincronizar con otras ventanas abiertas del cliente
          try {
            localStorage.setItem(`aura_pago_exitoso_${idPedido}`, JSON.stringify(res.data));
          } catch (_) {}

          // Notificar a ventana padre si es un popup
          if (window.opener && !window.opener.closed) {
            try {
              window.opener.postMessage({ type: 'PAYPAL_ORDER_COMPLETED', data: res.data }, '*');
              setTimeout(() => {
                try { window.close(); } catch (_) {}
              }, 1200);
            } catch (_) {}
          }

          // Limpiar parámetros de la URL para evitar bucle de re-captura si el usuario recarga
          this.router.navigate([], {
            relativeTo: this.route,
            queryParams: {},
            replaceUrl: true
          });
        } else {
          this.estadoPago = 'RECHAZADO';
          this.mensajeError = res?.message || 'PayPal no confirmó la finalización del pago.';
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.procesando = false;
        this.estadoPago = 'RECHAZADO';
        this.mensajeError = err.error?.detail || err?.message || 'Error al capturar y verificar la orden con PayPal.';
        this.cdr.detectChanges();
      }
    });
  }

  cancelarPago(): void {
    if (!this.pedido) return;
    this.pagoService.cancelarPago(this.pedido.id_pedido)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.estadoPago = 'CANCELADO';
          this.cdr.detectChanges();
        },
        error: () => {
          this.estadoPago = 'CANCELADO';
          this.cdr.detectChanges();
        }
      });
  }

  reintentar(): void {
    this.estadoPago = 'SELECCIONANDO';
    this.procesando = false;
    this.mensajeError = null;
    this.paypalOrderId = null;
    if (this.metodoSeleccionado === 'PAYPAL') {
      this.cdr.detectChanges();
      this.renderizarBotonPayPal();
    }
  }

  // --- EMISIÓN Y DESCARGA DE COMPROBANTE (W29) ---
  descargarComprobante(): void {
    if (!this.resultadoPago) return;
    this.descargandoPdf = true;

    this.pagoService.descargarComprobanteVentaBlob(this.resultadoPago.id_venta)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          this.descargandoPdf = false;
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `${this.resultadoPago!.tipo_documento}_${this.resultadoPago!.numero_venta}.pdf`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          window.URL.revokeObjectURL(url);
          this.cdr.detectChanges();
        },
        error: () => {
          this.descargandoPdf = false;
          alert('No fue posible descargar el archivo PDF. Puedes reintentar más tarde en Mis Pedidos.');
          this.cdr.detectChanges();
        }
      });
  }

  reenviarCorreo(): void {
    if (!this.resultadoPago) return;
    this.reenviandoCorreo = true;
    this.correoReenvioMensaje = null;

    this.pagoService.reenviarCorreoComprobante(this.resultadoPago.id_venta)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.reenviandoCorreo = false;
          this.correoReenvioMensaje = res.message || 'Comprobante reenviado con éxito.';
          this.cdr.detectChanges();
        },
        error: (err) => {
          this.reenviandoCorreo = false;
          this.correoReenvioMensaje = err.error?.detail || 'Error al intentar enviar el correo.';
          this.cdr.detectChanges();
        }
      });
  }

  irAMisPedidos(): void {
    this.router.navigate(['/mis-pedidos']);
  }

  irAlCatalogo(): void {
    this.router.navigate(['/catalogo']);
  }
}
