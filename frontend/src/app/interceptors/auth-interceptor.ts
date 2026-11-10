import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const token = authService.obtenerToken();

  // No enviar Authorization header a endpoints públicos de autenticación
  const esRutaAuth = req.url.includes('/api/auth/login') ||
                     req.url.includes('/api/auth/register') ||
                     req.url.includes('/api/auth/forgot-password') ||
                     req.url.includes('/api/auth/reset-password');

  if (token && !esRutaAuth) {
    const reqClonada = req.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`
      }
    });
    return next(reqClonada);
  }

  return next(req);
};