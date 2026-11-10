import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { PLATFORM_ID } from '@angular/core';
import { firstValueFrom, of, throwError } from 'rxjs';
import { describe, it, expect, vi } from 'vitest';
import { AuthService } from '../services/auth';
import { permissionGuard } from './permission-guard';

describe('permissionGuard: permisos vigentes', () => {
  it('cancela la navegación si el servidor falla sin entrar en un bucle de redirecciones', async () => {
    const auth = { obtenerUsuario: () => ({}), tokenExpirado: () => false,
      refrescarPermisos: () => throwError(() => new Error('Sin conexión')),
      hasAnyPermission: () => false,
      getDefaultRouteForUser: () => '/admin/suscripciones' };
    TestBed.configureTestingModule({ providers: [provideRouter([]), { provide: PLATFORM_ID, useValue: 'browser' }, { provide: AuthService, useValue: auth }] });
    const result = TestBed.runInInjectionContext(() => permissionGuard('suscripciones.ver')({} as any, { url: '/admin/suscripciones' } as any));
    expect(await firstValueFrom(result as any)).toBe(false);
  });
  for (const permitido of [true, false]) {
    it(permitido ? 'admite un permiso concedido después del login' : 'rechaza un permiso revocado aunque la sesión sea válida', async () => {
      const auth = { obtenerUsuario: () => ({}), tokenExpirado: () => false,
        refrescarPermisos: vi.fn(() => of([])), hasAnyPermission: () => permitido,
        getDefaultRouteForUser: () => '/admin/kpis' };
      TestBed.configureTestingModule({ providers: [provideRouter([]), { provide: PLATFORM_ID, useValue: 'browser' }, { provide: AuthService, useValue: auth }] });
      const result = TestBed.runInInjectionContext(() => permissionGuard('suscripciones.ver')({} as any, { url: '/admin/suscripciones' } as any));
      const value = await firstValueFrom(result as any);
      expect(auth.refrescarPermisos).toHaveBeenCalledOnce();
      if (permitido) expect(value).toBe(true);
      else expect(TestBed.inject(Router).serializeUrl(value as any)).toBe('/admin/kpis');
    });
  }
});
