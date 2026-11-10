import { Component, OnInit, inject, ChangeDetectorRef, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AuthService } from '../../../services/auth';
import {
  CajaService,
  DatosComprobanteVenta,
  EmitirComprobantePayload
} from '../../../services/caja';

@Component({
  selector: 'app-caja-comprobante',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './caja-comprobante.html',
  styleUrls: ['./caja-comprobante.css']
})
export class CajaComprobanteComponent implements OnInit {
  private route = inject(ActivatedRoute);
  public router = inject(Router);
  private cajaService = inject(CajaService);
  public authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);

  // Parámetros
  idVenta: number = 0;
  venta: DatosComprobanteVenta | null = null;

  // Estado
  cargando: boolean = true;
  procesando: boolean = false;
  descargandoPdf: boolean = false;
  errorCarga: string | null = null;
  mensajeError: string | null = null;
  mensajeExito: string | null = null;
  comprobanteEmitido: boolean = false;
  pdfUrlDisponible: string | null = null;

  // Formulario de emisión
  tipoDocumento: 'FACTURA' | 'RECIBO' = 'FACTURA';
  razonSocial: string = '';
  nitCi: string = '';
  correoFacturacion: string = '';
  enviarCorreo: boolean = false;

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const idStr = params.get('id');
      if (idStr) {
        this.idVenta = parseInt(idStr, 10);
        this.cargarDatos();
      } else {
        this.errorCarga = 'Identificador de venta no proporcionado.';
        this.cargando = false;
      }
    });
  }

  cargarDatos(): void {
    this.cargando = true;
    this.errorCarga = null;
    this.mensajeError = null;

    this.cajaService.obtenerDatosComprobanteVenta(this.idVenta).subscribe({
      next: (res) => {
        this.cargando = false;
        if (res.success && res.venta) {
          this.venta = res.venta;
          this.inicializarFormulario();
          // Si ya tiene nit/ci o razón social grabada, considerarlo listo para descargar
          if (this.venta.razon_social && this.venta.nit_ci) {
            this.comprobanteEmitido = true;
            this.pdfUrlDisponible = `/api/comprobantes/venta/${this.idVenta}/pdf`;
          }
        } else {
          this.errorCarga = 'No se encontró la venta requerida.';
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.cargando = false;
        this.errorCarga = err.error?.detail || err.error?.message || err.message || 'Error al obtener datos para el comprobante.';
        this.cdr.detectChanges();
      }
    });
  }

  inicializarFormulario(): void {
    if (!this.venta) return;

    this.tipoDocumento = (this.venta.tipo_documento as any) || 'FACTURA';
    this.razonSocial = this.venta.razon_social || this.venta.cliente_nombre || 'Sin Nombre';
    this.nitCi = this.venta.nit_ci || '0';
    this.correoFacturacion = this.venta.correo_facturacion || this.venta.cliente_correo || '';
    if (this.correoFacturacion.trim()) {
      this.enviarCorreo = true;
    }
  }

  get esFormularioValido(): boolean {
    return this.razonSocial.trim().length > 0 && this.nitCi.trim().length > 0;
  }

  emitirComprobante(): void {
    if (!this.esFormularioValido || this.procesando) return;

    this.procesando = true;
    this.mensajeError = null;
    this.mensajeExito = null;

    const payload: EmitirComprobantePayload = {
      razon_social: this.razonSocial.trim(),
      nit_ci: this.nitCi.trim(),
      correo_facturacion: this.correoFacturacion.trim() || undefined,
      tipo_documento: this.tipoDocumento,
      enviar_correo: this.enviarCorreo
    };

    this.cajaService.emitirComprobanteVenta(this.idVenta, payload).subscribe({
      next: (res) => {
        this.procesando = false;
        if (res.success) {
          this.comprobanteEmitido = true;
          this.pdfUrlDisponible = res.pdf_url || `/api/comprobantes/venta/${this.idVenta}/pdf`;
          this.mensajeExito = res.correo_enviado 
            ? '¡Comprobante emitido exitosamente y enviado al correo electrónico!' 
            : '¡Comprobante emitido exitosamente!';
          if (this.venta) {
            this.venta.razon_social = payload.razon_social;
            this.venta.nit_ci = payload.nit_ci;
            this.venta.correo_facturacion = payload.correo_facturacion;
            this.venta.tipo_documento = payload.tipo_documento;
          }
        } else {
          this.mensajeError = res.message || 'No se pudo emitir el comprobante.';
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.procesando = false;
        this.mensajeError = err.error?.detail || err.error?.message || err.message || 'Error al emitir el comprobante.';
        this.cdr.detectChanges();
      }
    });
  }

  descargarPdf(): void {
    this.descargandoPdf = true;
    this.cajaService.descargarComprobantePdf(this.idVenta).subscribe({
      next: (blob) => {
        this.descargandoPdf = false;
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `comprobante_venta_${this.venta?.codigo_venta || this.idVenta}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(blobUrl);
      },
      error: (err) => {
        this.descargandoPdf = false;
        this.mensajeError = 'Error al descargar el comprobante en formato PDF.';
        this.cdr.detectChanges();
      }
    });
  }

  abrirPdfEnNuevaPestana(): void {
    this.cajaService.descargarComprobantePdf(this.idVenta).subscribe({
      next: (blob) => {
        const blobUrl = URL.createObjectURL(blob);
        window.open(blobUrl, '_blank');
      },
      error: () => {
        this.mensajeError = 'No se pudo abrir el PDF en una nueva pestaña.';
      }
    });
  }

  irANuevaVenta(): void {
    this.router.navigate(['/admin/caja']);
  }

  irACobro(): void {
    this.router.navigate(['/admin/caja/pago', this.idVenta]);
  }
}
