import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { PerfilService, PerfilUsuario } from '../../services/perfil';
import { AuthService } from '../../services/auth';

@Component({
  selector: 'app-perfil',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './perfil.html',
  styleUrls: ['./perfil.css']
})
export class PerfilComponent implements OnInit {
  private perfilService = inject(PerfilService);
  public authService = inject(AuthService);
  private router = inject(Router);

  perfil = signal<PerfilUsuario | null>(null);
  cargando = signal<boolean>(true);
  guardando = signal<boolean>(false);
  modoEdicion = signal<boolean>(false);
  
  mensaje = signal<{ texto: string; tipo: 'exito' | 'error' } | null>(null);

  // Estados de modal de contraseña
  modalPasswordAbierto = signal<boolean>(false);
  cambiandoPassword = signal<boolean>(false);
  mostrarNuevaPassword = signal<boolean>(false);
  mostrarConfirmarPassword = signal<boolean>(false);

  passwordForm = {
    nueva_password: '',
    confirmar_password: ''
  };

  // Formulario reactivo de perfil general
  formulario = {
    nombre: '',
    apellido: '',
    telefono: '',
    correo: '',
    ci: '',
    direccion: '',
    ciudad: ''
  };

  // Validaciones idénticas a recuperación de contraseña
  get newPasswordMinLength(): boolean {
    return (this.passwordForm.nueva_password || '').length >= 8;
  }

  get newPasswordSpecialChar(): boolean {
    return /[!@#$%^&*(),.?":{}|<>]/.test(this.passwordForm.nueva_password || '');
  }

  get isNewPasswordValid(): boolean {
    return this.newPasswordMinLength && this.newPasswordSpecialChar;
  }

  get passwordsMatch(): boolean {
    return !!this.passwordForm.nueva_password && 
           this.passwordForm.nueva_password === this.passwordForm.confirmar_password;
  }

  get canSubmitPassword(): boolean {
    return this.isNewPasswordValid && this.passwordsMatch && !this.cambiandoPassword();
  }

  ngOnInit() {
    this.cargarPerfil();
  }

  cargarPerfil() {
    this.cargando.set(true);
    this.perfilService.obtenerPerfil().subscribe({
      next: (res) => {
        if (res && res.data) {
          this.perfil.set(res.data);
          this.inicializarFormulario(res.data);
        }
        this.cargando.set(false);
      },
      error: (err) => {
        console.error('Error cargando perfil:', err);
        this.mostrarMensaje('No se pudo cargar la información del perfil.', 'error');
        this.cargando.set(false);
      }
    });
  }

  inicializarFormulario(p: PerfilUsuario) {
    this.formulario = {
      nombre: p.nombre || '',
      apellido: p.apellido || '',
      telefono: p.telefono || '',
      correo: p.correo || '',
      ci: p.ci || '',
      direccion: p.direccion || '',
      ciudad: p.ciudad || 'Santa Cruz'
    };
  }

  activarEdicion() {
    const p = this.perfil();
    if (p) {
      this.inicializarFormulario(p);
      this.modoEdicion.set(true);
    }
  }

  cancelarEdicion() {
    this.modoEdicion.set(false);
    const p = this.perfil();
    if (p) {
      this.inicializarFormulario(p);
    }
  }

  // MODAL CAMBIAR CONTRASEÑA
  abrirModalPassword() {
    this.passwordForm = { nueva_password: '', confirmar_password: '' };
    this.mostrarNuevaPassword.set(false);
    this.mostrarConfirmarPassword.set(false);
    this.modalPasswordAbierto.set(true);
  }

  cerrarModalPassword() {
    this.modalPasswordAbierto.set(false);
    this.passwordForm = { nueva_password: '', confirmar_password: '' };
  }

  guardarPassword() {
    if (!this.newPasswordMinLength) {
      this.mostrarMensaje('La contraseña debe tener al menos 8 caracteres.', 'error');
      return;
    }
    if (!this.newPasswordSpecialChar) {
      this.mostrarMensaje('La contraseña debe contener al menos un carácter especial (!@#$%^&*...).', 'error');
      return;
    }
    if (!this.passwordsMatch) {
      this.mostrarMensaje('Las contraseñas ingresadas no coinciden.', 'error');
      return;
    }

    this.cambiandoPassword.set(true);
    this.perfilService.cambiarPassword({ password: this.passwordForm.nueva_password }).subscribe({
      next: (res) => {
        this.cambiandoPassword.set(false);
        this.cerrarModalPassword();
        this.mostrarMensaje('¡Contraseña actualizada exitosamente!', 'exito');
      },
      error: (err) => {
        this.cambiandoPassword.set(false);
        const errorMsg = err?.error?.detail || err?.error?.message || 'Error al cambiar la contraseña.';
        this.mostrarMensaje(errorMsg, 'error');
      }
    });
  }

  // GUARDAR EDICIÓN GENERAL DE PERFIL
  guardarCambios() {
    if (!this.formulario.nombre.trim() || !this.formulario.apellido.trim()) {
      this.mostrarMensaje('El nombre y apellido son obligatorios.', 'error');
      return;
    }

    if (!this.formulario.correo.trim()) {
      this.mostrarMensaje('El correo electrónico es obligatorio.', 'error');
      return;
    }

    this.guardando.set(true);

    const payload: any = {
      nombre: this.formulario.nombre.trim(),
      apellido: this.formulario.apellido.trim(),
      telefono: this.formulario.telefono.trim(),
      correo: this.formulario.correo.trim(),
      ci: this.formulario.ci.trim(),
      direccion: this.formulario.direccion.trim(),
      ciudad: this.formulario.ciudad.trim()
    };

    this.perfilService.actualizarPerfil(payload).subscribe({
      next: (res) => {
        this.guardando.set(false);
        this.modoEdicion.set(false);
        if (res.data) {
          this.perfil.set(res.data);
          this.inicializarFormulario(res.data);
        } else {
          this.cargarPerfil();
        }
        this.mostrarMensaje('¡Tu perfil ha sido actualizado exitosamente!', 'exito');
      },
      error: (err) => {
        this.guardando.set(false);
        const errorMsg = err?.error?.detail || err?.message || 'Error al guardar los cambios.';
        this.mostrarMensaje(errorMsg, 'error');
      }
    });
  }

  mostrarMensaje(texto: string, tipo: 'exito' | 'error') {
    this.mensaje.set({ texto, tipo });
    setTimeout(() => {
      this.mensaje.set(null);
    }, 5000);
  }

  obtenerIniciales(): string {
    const p = this.perfil();
    if (!p) return 'AU';
    const n = p.nombre ? p.nombre.charAt(0).toUpperCase() : '';
    const a = p.apellido ? p.apellido.charAt(0).toUpperCase() : '';
    return (n + a) || (p.username ? p.username.substring(0, 2).toUpperCase() : 'AU');
  }

  cerrarSesion() {
    this.authService.cerrarSesion();
    this.router.navigate(['/']);
  }
}