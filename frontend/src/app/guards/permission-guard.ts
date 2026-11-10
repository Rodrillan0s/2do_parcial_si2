import { CanActivateFn, Router } from '@angular/router';
import { inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { AuthService } from '../services/auth';
import { NetworkStatusService } from '../core/network/network-status.service';
import { catchError, map, of } from 'rxjs';

/**
 * permissionGuard: Valida que el usuario autenticado cuente con los permisos necesarios.
 * Permite pasar un único código de permiso o un arreglo (donde basta tener al menos uno).
 */
export function permissionGuard(requiredPermissions: string | string[]): CanActivateFn {
  return (route, state) => {
    const platformId = inject(PLATFORM_ID);
    if (!isPlatformBrowser(platformId)) {
      return true;
    }

    const authService = inject(AuthService);
    const router = inject(Router);
    const networkStatus = inject(NetworkStatusService);

    const usuario = authService.obtenerUsuario();
    if (!usuario || authService.tokenExpirado()) {
      authService.cerrarSesion();
      authService.openAuthModal('login');
      router.navigate(['/']);
      return false;
    }

    const permissionsToCheck = Array.isArray(requiredPermissions) ? requiredPermissions : [requiredPermissions];

    // Si no hay conexión a internet o el backend está inalcanzable, validar de inmediato con la sesión local
    // para evitar peticiones HTTP fallidas redundantes en cada pestaña o navegación
    if (!networkStatus.isOnline()) {
      if (authService.hasAnyPermission(permissionsToCheck)) {
        return true;
      }
      const destino = authService.getDefaultRouteForUser(usuario);
      return destino === state.url ? false : router.parseUrl(destino);
    }

    return authService.refrescarPermisos().pipe(
      map(() => {
        if (authService.hasAnyPermission(permissionsToCheck)) return true;
        const destino = authService.getDefaultRouteForUser(authService.obtenerUsuario() || usuario);
        return destino === state.url ? false : router.parseUrl(destino);
      }),
      catchError((err) => {
        console.warn('[PermissionGuard] No se pudieron refrescar permisos en tiempo real, validando con sesión local:', err);
        if (authService.hasAnyPermission(permissionsToCheck)) {
          return of(true);
        }
        const destino = authService.getDefaultRouteForUser(usuario);
        return of(destino === state.url ? false : router.parseUrl(destino));
      })
    );
  };
}
