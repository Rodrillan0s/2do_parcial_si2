import { Component, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService, AuthTab } from '../../services/auth';

@Component({
  selector: 'app-auth-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './auth-modal.html'
})
export class AuthModalComponent {
  public authService = inject(AuthService);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);

  // Formularios
  loginData = {
    login_identifier: '',
    password: '',
    device_fingerprint: 'device_web_browser_alpha_1',
    nombre_dispositivo: 'Navegador Web Chrome'
  };

  registerData = {
    correo: '',
    nombre_usuario: '',
    password: '',
    confirm_password: '',
    nombre: '',
    apellido: '',
    telefono: '',
    aceptar_terminos: false,
    device_fingerprint: 'device_web_browser_alpha_1',
    nombre_dispositivo: 'Navegador Web Chrome'
  };

  forgotData = {
    correo: ''
  };

  resetData = {
    correo: '',
    codigo_recuperacion: '',
    new_password: '',
    confirm_password: ''
  };

  verifyData = {
    nro_usuario: 0,
    codigo_verificacion: '',
    device_fingerprint: 'device_web_browser_alpha_1',
    nombre_dispositivo: 'Navegador Web Chrome'
  };

  // Estados UI
  showPassword = false;
  showConfirmPassword = false;
  isLoading = false;
  errorMessage = '';
  successMessage = '';
  forgotStep: 'request' | 'verify_code' | 'new_password' = 'request';

  get hasMinLength(): boolean {
    return (this.registerData.password || '').length >= 8;
  }

  get hasSpecialChar(): boolean {
    return /[!@#$%^&*(),.?":{}|<>]/.test(this.registerData.password || '');
  }

  get isPasswordValid(): boolean {
    return this.hasMinLength && this.hasSpecialChar;
  }

  // Validaciones para la nueva contraseña en recuperación
  get newPasswordMinLength(): boolean {
    return (this.resetData.new_password || '').length >= 8;
  }

  get newPasswordSpecialChar(): boolean {
    return /[!@#$%^&*(),.?":{}|<>]/.test(this.resetData.new_password || '');
  }

  get isNewPasswordValid(): boolean {
    return this.newPasswordMinLength && this.newPasswordSpecialChar;
  }

  switchTab(tab: AuthTab) {
    this.authService.authModalTab.set(tab);
    if (tab === 'forgot') {
      this.forgotStep = 'request';
      if (this.loginData.login_identifier && this.loginData.login_identifier.includes('@')) {
        this.forgotData.correo = this.loginData.login_identifier;
      }
    }
    this.clearMessages();
  }


  closeModal() {
    this.authService.closeAuthModal();
    this.clearMessages();
  }

  clearMessages() {
    this.errorMessage = '';
    this.successMessage = '';
    this.isLoading = false;
    this.cdr.detectChanges();
  }

  // 1. INICIAR SESIÓN
  onLogin() {
    this.clearMessages();
    if (!this.loginData.login_identifier || !this.loginData.password) {
      this.errorMessage = 'Por favor ingresa tu correo/usuario y contraseña.';
      this.cdr.detectChanges();
      return;
    }

    this.isLoading = true;
    this.cdr.detectChanges();

    this.authService.iniciarSesion(this.loginData).subscribe({
      next: (res) => {
        this.isLoading = false;
        if (res.requires_verification) {
          this.authService.pendingDeviceVerification.set({
            nro_usuario: res.nro_usuario,
            codigo_simulado: res.codigo_simulado,
            device_fingerprint: this.loginData.device_fingerprint,
            nombre_dispositivo: this.loginData.nombre_dispositivo
          });
          this.verifyData.nro_usuario = res.nro_usuario;
          if (res.codigo_simulado) {
            this.verifyData.codigo_verificacion = res.codigo_simulado;
          }
          this.successMessage = res.message;
          this.authService.authModalTab.set('verify');
        } else if (res.success) {
          this.authService.guardarSesion(res.token, res.usuario);
          const target = this.authService.getDefaultRouteForUser(res.usuario);
          if (!this.authService.esCliente()) {
            this.router.navigateByUrl(target);
          }
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || err.error?.message || 'Error al iniciar sesión. Verifica tus credenciales.';
        this.cdr.detectChanges();
      }
    });
  }

  // 2. CREAR CUENTA
  onRegister() {
    this.clearMessages();
    if (!this.registerData.correo || !this.registerData.nombre_usuario || !this.registerData.password || !this.registerData.nombre || !this.registerData.apellido) {
      this.errorMessage = 'Por favor completa todos los campos requeridos.';
      this.cdr.detectChanges();
      return;
    }

    if (!this.registerData.aceptar_terminos) {
      this.errorMessage = 'Debes aceptar los Términos de Servicio y Condiciones.';
      this.cdr.detectChanges();
      return;
    }

    if (!this.isPasswordValid) {
      this.errorMessage = 'La contraseña debe tener al menos 8 caracteres y 1 símbolo especial.';
      this.cdr.detectChanges();
      return;
    }

    if (this.registerData.password !== this.registerData.confirm_password) {
      this.errorMessage = 'Las contraseñas no coinciden.';
      this.cdr.detectChanges();
      return;
    }

    this.isLoading = true;
    this.cdr.detectChanges();

    this.authService.registrarCliente(this.registerData).subscribe({
      next: (res) => {
        this.isLoading = false;
        if (res.success) {
          this.authService.guardarSesion(res.token, res.usuario);
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || err.error?.message || 'Error en el registro de usuario.';
        this.cdr.detectChanges();
      }
    });
  }

  // 3. SOLICITAR CÓDIGO DE RECUPERACIÓN (PASO 1)
  onRequestForgot(event?: Event) {
    if (event) event.preventDefault();
    if (this.isLoading) return;

    this.clearMessages();
    const input = (this.forgotData.correo || '').trim();
    if (!input) {
      this.errorMessage = 'Ingresa el correo electrónico o usuario asociado a tu cuenta.';
      return;
    }

    this.isLoading = true;
    this.cdr.detectChanges();

    const safetyTimer = setTimeout(() => {
      if (this.isLoading) {
        this.isLoading = false;
        this.errorMessage = 'La conexión tardó más de lo esperado. Por favor reintenta.';
        this.cdr.detectChanges();
      }
    }, 6000);

    this.authService.solicitarRecuperacionClave(input).subscribe({
      next: (res) => {
        clearTimeout(safetyTimer);
        this.isLoading = false;
        if (res.success) {
          this.successMessage = 'Código enviado a tu correo. Ingrésalo a continuación.';
          this.resetData.correo = input;
          this.resetData.codigo_recuperacion = '';
          this.forgotStep = 'verify_code';
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        clearTimeout(safetyTimer);
        this.isLoading = false;
        this.errorMessage = err.error?.detail || err.error?.message || 'No se pudo enviar el código de recuperación.';
        this.cdr.detectChanges();
      }
    });
  }

  // 4. VALIDAR CÓDIGO DE RECUPERACIÓN EN BASE DE DATOS (PASO 2)
  onVerifyCode(event?: Event) {
    if (event) event.preventDefault();
    if (this.isLoading) return;
    this.clearMessages();

    const code = (this.resetData.codigo_recuperacion || '').trim();
    if (!code) {
      this.errorMessage = 'Ingresa el código de recuperación';
      return;
    }

    if (code.length !== 6) {
      this.errorMessage = 'El código debe contener 6 dígitos';
      return;
    }

    this.isLoading = true;
    this.cdr.detectChanges();

    this.authService.verificarCodigoRecuperacion(this.resetData.correo, code).subscribe({
      next: (res) => {
        this.isLoading = false;
        if (res.success) {
          this.successMessage = 'Código verificado. Ahora crea tu nueva contraseña.';
          this.forgotStep = 'new_password';
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || err.error?.message || 'El código ingresado es incorrecto o ha expirado.';
        this.cdr.detectChanges();
      }
    });
  }

  // 5. CAMBIAR CONTRASEÑA (PASO 3)
  onResetPassword(event?: Event) {
    if (event) event.preventDefault();
    if (this.isLoading) return;

    this.clearMessages();
    if (!this.resetData.new_password || !this.resetData.confirm_password) {
      this.errorMessage = 'Completa los campos de la nueva contraseña.';
      return;
    }

    if (!this.isNewPasswordValid) {
      this.errorMessage = 'La contraseña debe cumplir con los requisitos mínimos.';
      return;
    }

    if (this.resetData.new_password !== this.resetData.confirm_password) {
      this.errorMessage = 'Las contraseñas no coinciden.';
      return;
    }

    this.isLoading = true;
    this.cdr.detectChanges();

    this.authService.restablecerClave(this.resetData).subscribe({
      next: (res) => {
        this.isLoading = false;
        if (res.success) {
          this.successMessage = 'Contraseña restablecida exitosamente. Redirigiendo al inicio de sesión...';
          setTimeout(() => {
            this.switchTab('login');
            this.forgotStep = 'request';
            this.cdr.detectChanges();
          }, 1500);
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || err.error?.message || 'Código incorrecto o expirado.';
        this.cdr.detectChanges();
      }
    });
  }

  // 5. VERIFICAR DISPOSITIVO
  onVerifyDevice() {
    this.clearMessages();
    if (!this.verifyData.codigo_verificacion) {
      this.errorMessage = 'Ingresa el código de 6 dígitos enviado a tu correo.';
      return;
    }

    this.isLoading = true;
    this.authService.verificarDispositivo(this.verifyData).subscribe({
      next: (res) => {
        this.isLoading = false;
        if (res.success) {
          this.successMessage = 'Dispositivo verificado exitosamente. Iniciando sesión...';
          this.authService.iniciarSesion(this.loginData).subscribe({
            next: (loginRes) => {
              if (loginRes.token) {
                this.authService.guardarSesion(loginRes.token, loginRes.usuario);
                const target = this.authService.getDefaultRouteForUser(loginRes.usuario);
                if (!this.authService.esCliente()) {
                  this.router.navigateByUrl(target);
                }
              }
            }
          });
        }
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || err.error?.message || 'Código de verificación incorrecto o expirado.';
      }
    });
  }
}
