import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  SaasService,
  PlanSaaS,
  CodigoPlan,
  PeriodicidadPlan,
  SolicitudContratacion
} from '../../services/saas';
import { AuthService } from '../../services/auth';
import { TenantContextService } from '../../services/tenant-context';
import { extraerMensajeError } from '../../utils/error-helper';

@Component({
  selector: 'app-saas-comercial',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './saas-comercial.html'
})
export class SaasComercialComponent implements OnInit {
  public saasService = inject(SaasService);
  public authService = inject(AuthService);
  public tenantContext = inject(TenantContextService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);

  // Vista activa dentro del Sitio Comercial de AuroraStore:
  // 'inicio' | 'planes' | 'registro' | 'contratacion'
  vistaActual: 'inicio' | 'planes' | 'registro' | 'contratacion' = 'inicio';

  // Catálogo de planes activos desde backend
  planes: PlanSaaS[] = [];
  cargandoPlanes = false;
  periodicidadSeleccionada: PeriodicidadPlan = 'MENSUAL';
  planSeleccionado: CodigoPlan = 'PROFESIONAL';

  // Consulta rápida de seguimiento
  codigoConsultaInput = '';

  // Formulario progresivo de registro autónomo (Paso 1: Propietario, Paso 2: Tienda)
  pasoRegistro: 1 | 2 = 1;
  regNombre = '';
  regApellido = '';
  regCorreo = '';
  regTelefono = '';
  regPassword = '';
  regConfirmPassword = '';
  regNombreComercial = '';
  regRazonSocial = '';
  regNit = '';
  regCiudad = 'Santa Cruz';
  regDireccionFiscal = '';
  regSlug = '';
  regPublicos: string[] = ['Mujer', 'Hombre', 'Unisex'];

  readonly publicosOpciones = ['Mujer', 'Hombre', 'Unisex', 'Niños', 'Niñas', 'Bebés'];
  readonly ciudadesBolivia = ['Santa Cruz', 'La Paz', 'Cochabamba', 'Sucre', 'Tarija', 'Oruro', 'Potosí', 'Beni', 'Pando'];

  // Estado de validación de slug en tiempo real
  slugVerificando = false;
  slugDisponible: boolean | null = null;
  slugMensaje = '';
  slugSugerencia = '';
  private slugTimer: any = null;

  // Estado de solicitud de contratación activa
  contratacionActual: SolicitudContratacion | null = null;
  tokenVerificacionInput = '';
  metodoPagoElegido: 'PAYPAL' | 'QR_TRANSFERENCIA' = 'QR_TRANSFERENCIA';
  paypalOrderIdCreado = '';
  paypalApproveUrl = '';
  archivoComprobante: File | null = null;
  referenciaPagoInput = '';

  // Mensajes y spinners
  procesando = false;
  mensajeError = '';
  mensajeExito = '';

  ngOnInit(): void {
    this.cargarPlanesPublicos();
    if (!this.tenantContext.tenantsDisponibles().length) {
      this.tenantContext.inicializarContexto();
    }

    this.route.paramMap.subscribe(params => {
      const codigo = params.get('codigo');
      if (codigo) {
        this.vistaActual = 'contratacion';
        this.cargarEstadoContratacion(codigo);
      }
    });

    this.route.queryParamMap.subscribe(qParams => {
      const vista = qParams.get('vista');
      const plan = qParams.get('plan') as CodigoPlan | null;
      const tokenUrl = qParams.get('token');
      const codigoUrl = this.route.snapshot.paramMap.get('codigo') || qParams.get('codigo');

      if (plan === 'BASICO' || plan === 'PROFESIONAL') {
        this.planSeleccionado = plan;
      }
      if (vista === 'planes' || vista === 'registro') {
        this.vistaActual = vista;
      }
      if (codigoUrl && tokenUrl) {
        this.tokenVerificacionInput = tokenUrl;
        this.verificarCorreoConToken(codigoUrl, tokenUrl);
      }
      this.cdr.markForCheck();
    });
  }

  cargarPlanesPublicos(): void {
    this.cargandoPlanes = true;
    this.saasService.listarPlanesPublicos().subscribe({
      next: (res) => {
        this.planes = res?.data || [];
        if (this.planes.length > 0 && !this.planes.some(p => p.codigo === this.planSeleccionado)) {
          this.planSeleccionado = this.planes[0].codigo;
        }
        this.cargandoPlanes = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.mensajeError = extraerMensajeError(err, 'No se pudieron cargar los planes disponibles.');
        this.cargandoPlanes = false;
        this.cdr.markForCheck();
      }
    });
  }

  get planObjetoSeleccionado(): PlanSaaS | undefined {
    return this.planes.find(p => p.codigo === this.planSeleccionado);
  }

  obtenerPrecioPlan(plan: PlanSaaS): number {
    return this.periodicidadSeleccionada === 'ANUAL'
      ? (plan.precio_anual || 1990)
      : (plan.precio_mensual || 199);
  }

  irAVista(vista: 'inicio' | 'planes' | 'registro' | 'contratacion', codigoPlan?: CodigoPlan): void {
    this.mensajeError = '';
    this.mensajeExito = '';
    if (codigoPlan) {
      this.planSeleccionado = codigoPlan;
    }
    this.vistaActual = vista;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  onNombreComercialChange(valor: string): void {
    this.regNombreComercial = valor;
    const autoSlug = valor
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 50);
    this.regSlug = autoSlug;
    this.onSlugInput(autoSlug);
  }

  onSlugInput(valor: string): void {
    this.regSlug = valor.toLowerCase().replace(/[^a-z0-9-]/g, '');
    this.slugDisponible = null;
    this.slugMensaje = '';
    this.slugSugerencia = '';

    if (this.slugTimer) clearTimeout(this.slugTimer);
    if (this.regSlug.length < 3) {
      this.slugMensaje = 'Mínimo 3 caracteres alfanuméricos.';
      return;
    }

    this.slugVerificando = true;
    this.slugTimer = setTimeout(() => {
      this.saasService.verificarSlug(this.regSlug).subscribe({
        next: (res) => {
          this.slugVerificando = false;
          this.slugDisponible = res.data.disponible;
          this.slugMensaje = res.data.motivo;
          this.slugSugerencia = res.data.sugerencia || '';
          this.cdr.markForCheck();
        },
        error: () => {
          this.slugVerificando = false;
          this.cdr.markForCheck();
        }
      });
    }, 300);
  }

  usarSlugSugerido(): void {
    if (this.slugSugerencia) {
      this.regSlug = this.slugSugerencia;
      this.onSlugInput(this.regSlug);
    }
  }

  togglePublicoRegistro(pub: string): void {
    if (this.regPublicos.includes(pub)) {
      if (this.regPublicos.length > 1) {
        this.regPublicos = this.regPublicos.filter(p => p !== pub);
      }
    } else {
      this.regPublicos = [...this.regPublicos, pub];
    }
  }

  avanzarAPaso2(): void {
    this.mensajeError = '';
    if (!this.regNombre.trim() || !this.regApellido.trim() || !this.regCorreo.trim()) {
      this.mensajeError = 'Completa tu nombre, apellido y correo electrónico.';
      return;
    }
    if (this.regPassword.length < 8 || !/[^a-zA-Z0-9]/.test(this.regPassword)) {
      this.mensajeError = 'La contraseña debe tener al menos 8 caracteres y al menos 1 carácter especial.';
      return;
    }
    if (this.regPassword !== this.regConfirmPassword) {
      this.mensajeError = 'Las contraseñas no coinciden.';
      return;
    }
    this.pasoRegistro = 2;
  }

  enviarRegistroContratacion(): void {
    this.mensajeError = '';
    this.mensajeExito = '';

    if (!this.regNombreComercial.trim() || this.regSlug.trim().length < 3) {
      this.mensajeError = 'Indica el nombre comercial de tu tienda y un identificador (slug) válido.';
      return;
    }
    if (this.slugDisponible === false) {
      this.mensajeError = 'El identificador (slug) elegido no está disponible.';
      return;
    }

    this.procesando = true;
    this.saasService.registrarContratacion({
      nombre: this.regNombre.trim(),
      apellido: this.regApellido.trim(),
      correo: this.regCorreo.trim(),
      telefono: this.regTelefono.trim(),
      password: this.regPassword,
      confirm_password: this.regConfirmPassword,
      nombre_comercial: this.regNombreComercial.trim(),
      razon_social: this.regRazonSocial.trim() || this.regNombreComercial.trim(),
      nit: this.regNit.trim(),
      ciudad: this.regCiudad,
      direccion_fiscal: this.regDireccionFiscal.trim(),
      slug: this.regSlug.trim(),
      codigo_plan: this.planSeleccionado,
      periodicidad: this.periodicidadSeleccionada,
      publicos_objetivo: this.regPublicos
    }).subscribe({
      next: (res) => {
        this.procesando = false;
        this.contratacionActual = res.data;
        if (res.data.token_verificacion_dev) {
          this.tokenVerificacionInput = res.data.token_verificacion_dev;
        }
        this.vistaActual = 'contratacion';
        this.mensajeExito = 'Cuenta y solicitud creadas. Verifica tu correo electrónico para habilitar el pago.';
        this.router.navigate(['/saas/contratacion', res.data.codigo_seguimiento]);
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.procesando = false;
        this.mensajeError = extraerMensajeError(err, 'No fue posible registrar la contratación.');
        this.cdr.markForCheck();
      }
    });
  }

  consultarPorCodigo(): void {
    const cod = this.codigoConsultaInput.trim();
    if (!cod) return;
    this.router.navigate(['/saas/contratacion', cod]);
  }

  cargarEstadoContratacion(codigo: string): void {
    this.procesando = true;
    this.mensajeError = '';
    this.saasService.obtenerEstadoContratacion(codigo).subscribe({
      next: (res) => {
        this.procesando = false;
        this.contratacionActual = res.data;
        this.vistaActual = 'contratacion';
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.procesando = false;
        this.mensajeError = extraerMensajeError(err, 'No se encontró una contratación con ese código.');
        this.cdr.markForCheck();
      }
    });
  }

  verificarCorreoConToken(codigo?: string, token?: string): void {
    const cod = codigo || this.contratacionActual?.codigo_seguimiento || '';
    const tok = (token || this.tokenVerificacionInput || '').trim();
    if (!cod || !tok) {
      this.mensajeError = 'Ingresa el token de verificación enviado a tu correo.';
      return;
    }
    this.procesando = true;
    this.mensajeError = '';
    this.saasService.verificarCorreoContratacion(cod, tok).subscribe({
      next: (res) => {
        this.procesando = false;
        this.contratacionActual = res.data;
        this.mensajeExito = 'Correo verificado correctamente. Ya puedes completar el pago de tu suscripción.';
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.procesando = false;
        this.mensajeError = extraerMensajeError(err, 'El token de verificación es inválido o ha expirado.');
        this.cdr.markForCheck();
      }
    });
  }

  reenviarCorreoVerificacion(): void {
    if (!this.contratacionActual?.codigo_seguimiento) return;
    this.procesando = true;
    this.mensajeError = '';
    this.saasService.reenviarVerificacionCorreo(this.contratacionActual.codigo_seguimiento).subscribe({
      next: (res) => {
        this.procesando = false;
        if (res.data?.token_verificacion_dev) {
          this.tokenVerificacionInput = res.data.token_verificacion_dev;
        }
        this.mensajeExito = 'Se generó y envió un nuevo enlace de verificación a tu correo.';
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.procesando = false;
        this.mensajeError = extraerMensajeError(err, 'No se pudo reenviar el correo de verificación.');
        this.cdr.markForCheck();
      }
    });
  }

  iniciarPagoPayPal(): void {
    if (!this.contratacionActual?.codigo_seguimiento) return;
    this.procesando = true;
    this.mensajeError = '';
    this.saasService.crearOrdenPayPalContratacion(this.contratacionActual.codigo_seguimiento).subscribe({
      next: (res) => {
        this.procesando = false;
        this.paypalOrderIdCreado = res.data.paypal_order_id;
        this.paypalApproveUrl = res.data.approve_url || '';
        if (this.paypalApproveUrl && typeof window !== 'undefined') {
          window.open(this.paypalApproveUrl, '_blank', 'noopener,noreferrer');
        }
        this.mensajeExito = 'Orden PayPal generada. Aprueba el pago en la ventana de PayPal y luego pulsa "Confirmar Pago en Servidor".';
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.procesando = false;
        this.mensajeError = extraerMensajeError(err, 'No se pudo inicializar la orden en PayPal.');
        this.cdr.markForCheck();
      }
    });
  }

  confirmarCapturaPayPal(): void {
    if (!this.contratacionActual?.codigo_seguimiento) return;
    const orderId = this.paypalOrderIdCreado || this.contratacionActual.paypal_order_id || '';
    if (!orderId) {
      this.mensajeError = 'Primero genera la orden de PayPal.';
      return;
    }
    this.procesando = true;
    this.mensajeError = '';
    this.saasService.capturarOrdenPayPalContratacion(this.contratacionActual.codigo_seguimiento, orderId).subscribe({
      next: (res) => {
        this.procesando = false;
        this.contratacionActual = res.data;
        this.mensajeExito = '¡Pago confirmado por PayPal! Tu tienda y suscripción han sido activadas.';
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.procesando = false;
        this.mensajeError = extraerMensajeError(err, 'PayPal aún no reporta la orden como aprobada/completada.');
        this.cdr.markForCheck();
      }
    });
  }

  onArchivoSeleccionado(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.archivoComprobante = input.files[0];
    }
  }

  enviarComprobanteTransferencia(): void {
    if (!this.contratacionActual?.codigo_seguimiento) return;
    if (!this.archivoComprobante) {
      this.mensajeError = 'Selecciona el archivo de imagen de tu comprobante de pago QR o transferencia.';
      return;
    }
    this.procesando = true;
    this.mensajeError = '';
    this.saasService.subirComprobanteContratacion(
      this.contratacionActual.codigo_seguimiento,
      this.archivoComprobante,
      this.referenciaPagoInput.trim() || 'QR-TRANSFERENCIA'
    ).subscribe({
      next: (res) => {
        this.procesando = false;
        this.contratacionActual = res.data;
        this.mensajeExito = 'Comprobante recibido correctamente. Tu contratación está en revisión por el equipo autorizado.';
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.procesando = false;
        this.mensajeError = extraerMensajeError(err, 'No se pudo subir el comprobante.');
        this.cdr.markForCheck();
      }
    });
  }

  abrirLoginPropietario(): void {
    this.authService.openAuthModal('login');
  }
}
