import { CanActivateFn, Router } from '@angular/router';
import { inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { AuthService } from '../services/auth';

export const authGuard: CanActivateFn = (route, state) => {
  const platformId = inject(PLATFORM_ID);
  
  if (!isPlatformBrowser(platformId)) {
    return true; 
  }

  const authService = inject(AuthService);
  const router = inject(Router);

  const usuario = authService.obtenerUsuario();
  const tokenExpirado = authService.tokenExpirado();

  // 1. Validar autenticación básica
  if (!usuario || tokenExpirado) {
    authService.cerrarSesion();
    authService.openAuthModal('login');
    router.navigate(['/']);
    return false; 
  }

  // 2. Si la ruta requiere rol administrativo/empleado (ej. /admin y sus hijas)
  const esRutaAdmin = state.url.startsWith('/admin');
  if (esRutaAdmin) {
    if (!authService.esEmpleadoOAdmin() || authService.getScopeLevel() === 'CLIENTE' || authService.esCliente()) {
      // Un cliente autenticado no tiene acceso al panel administrativo; redirigir a su perfil
      if (authService.esCliente() || authService.getScopeLevel() === 'CLIENTE') {
        router.navigate(['/perfil']);
      } else {
        router.navigate(['/']);
      }
      return false;
    }

    // Restricciones internas: Cadena de Tiendas y Respaldo solo para Administradores de Nivel 1 y 2
    if ((state.url.startsWith('/admin/empresas') || state.url.startsWith('/admin/backup')) && !authService.isGlobalAdmin()) {
      router.navigate(['/admin/kpis']);
      return false;
    }
  }

  return true;
};