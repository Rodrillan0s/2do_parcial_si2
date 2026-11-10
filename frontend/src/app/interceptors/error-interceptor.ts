import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, tap } from 'rxjs/operators';
import { throwError } from 'rxjs';
import { AuthService } from '../services/auth';
import { NetworkStatusService } from '../core/network/network-status.service';

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const networkStatus = inject(NetworkStatusService);

  return next(req).pipe(
    tap(() => {
      if (req.url.includes('/api/')) {
        networkStatus.recordApiSuccess();
      }
    }),
    catchError((error) => {
      // 1. Diagnóstico de conectividad: status === 0 (red caída) o 504 (timeout)
      if ((error.status === 0 || error.status === 504) && req.url.includes('/api/')) {
        networkStatus.recordApiNetworkFailure();
      } else if (error.status > 0 && error.status < 500 && req.url.includes('/api/')) {
        networkStatus.recordApiSuccess();
      }

      // 2. Acceso denegado por permisos (403): NO es sesión caducada; NO cerrar sesión
      if (error.status === 403) {
        console.warn('[RBAC 403] Acceso denegado por permisos insuficientes. La sesión se mantiene activa.');
        return throwError(() => error);
      }

      // 3. Servidor con error interno (5xx): fallo temporal de backend, NO cerrar sesión
      if (error.status >= 500) {
        console.warn(`[HTTP ${error.status}] Error en servidor backend. La sesión se mantiene activa.`);
        return throwError(() => error);
      }

      // 4. SOLO si el error es 401 (No autenticado / token caducado)
      if (error.status === 401) {
        // Ignorar rutas de autenticación pública (login, registro, etc.):
        // Un 401 en login significa "credenciales incorrectas", NO "sesión caducada".
        const esRutaAuth = req.url.includes('/api/auth/login') ||
                           req.url.includes('/api/auth/register') ||
                           req.url.includes('/api/auth/verify-device') ||
                           req.url.includes('/api/auth/forgot-password') ||
                           req.url.includes('/api/auth/reset-password');

        if (esRutaAuth) {
          return throwError(() => error);
        }

        const token = authService.obtenerToken();
        if (!token) {
          console.warn('Petición 401 sin token (posible carga inicial). Ignorando...');
          return throwError(() => error);
        }

        // Si SÍ hay token en una ruta protegida y el backend da 401, entonces sí caducó
        console.warn('El backend rechazó el token. Sesión caducada.');
        authService.cerrarSesion();
        setTimeout(() => router.navigate(['/']), 0);
      }
      return throwError(() => error);
    })
  );
};