import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule], // Necesario para ngIf y ngModel
  templateUrl: './login.html'
})
export class LoginComponent {
  
  // Inyección de dependencias
  private authService = inject(AuthService);
  private router = inject(Router);

  // Variables de estado
  credenciales = {
    ci: '',
    password: ''
  };
  mensajeError = '';
  cargando = false;

  // Función principal
  hacerLogin() {
    // 1. Validar que no haya campos vacíos
    if (!this.credenciales.ci || !this.credenciales.password) {
      this.mensajeError = 'Por favor complete todos los campos.';
      return;
    }

    this.cargando = true;
    this.mensajeError = '';

    // 2. Llamar al servicio
    this.authService.iniciarSesion(this.credenciales).subscribe({
      next: (respuesta) => {
        if (respuesta.success) {
          // 3. Guardar sesión y redirigir
          this.authService.guardarSesion(respuesta.token, respuesta.usuario);
          this.cargando = false;
          const destino = this.authService.getDefaultRouteForUser(respuesta.usuario);
          this.router.navigateByUrl(destino); 
        }
      },
      error: (errorHttp) => {
        // 4. Capturar errores del backend (ej: 401 Unauthorized)
        this.cargando = false;
        this.mensajeError = errorHttp.error?.detail || 'Error de conexión con el servidor.';
      }
    });
  }
}