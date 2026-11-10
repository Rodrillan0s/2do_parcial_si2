import { CanActivateFn, Router } from '@angular/router';
import { inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { AuthService } from '../services/auth';

/**
 * scopeGuard: Valida que el usuario pertenezca a uno de los alcances permitidos
 * ('PLATAFORMA', 'EMPRESA', 'SUCURSAL').
 * Ejemplo: /admin/empresas solo permite ['PLATAFORMA'].
 */
export function scopeGuard(allowedScopes: Array<'PLATAFORMA' | 'EMPRESA' | 'SUCURSAL' | 'CLIENTE'>): CanActivateFn {
  return (route, state) => {
    const platformId = inject(PLATFORM_ID);
    if (!isPlatformBrowser(platformId)) {
      return true;
    }

    const authService = inject(AuthService);
    const router = inject(Router);

    const usuario = authService.obtenerUsuario();
    if (!usuario || authService.tokenExpirado()) {
      authService.cerrarSesion();
      authService.openAuthModal('login');
      router.navigate(['/']);
      return false;
    }

    const currentScope = authService.getScopeLevel();
    if (currentScope === 'CLIENTE') {
      router.navigate(['/perfil']);
      return false;
    }

    const esPermitido = allowedScopes.includes(currentScope);

    if (!esPermitido) {
      console.warn(`[ScopeGuard] Acceso denegado a '${state.url}'. Alcance actual: '${currentScope}', Alcances permitidos:`, allowedScopes);
      router.navigate(['/admin/kpis']);
      return false;
    }

    return true;
  };
}
