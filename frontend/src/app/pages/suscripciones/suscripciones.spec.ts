import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SuscripcionesComponent } from './suscripciones';
import { AuthService } from '../../services/auth';
import { EmpresaService } from '../../services/empresa';
import { SaasService, SuscripcionItem } from '../../services/saas';

describe('Suscripciones: contrato e integración', () => {
  let component: SuscripcionesComponent;
  let api: any;
  beforeEach(async () => {
    api = { consultarPlan: vi.fn(() => of({ data: null })), obtenerHistorialSuscripciones: vi.fn(() => of({ data: [] })),
      asignarSuscripcion: vi.fn(() => of({ data: { codigo_plan: 'BASICO' } })) };
    TestBed.configureTestingModule({ providers: [
      { provide: AuthService, useValue: { isGlobalAdmin: () => true, hasPermission: () => true } },
      { provide: SaasService, useValue: api }, { provide: EmpresaService, useValue: {} },
      { provide: ActivatedRoute, useValue: { snapshot: { queryParams: {} } } }
    ] });
    TestBed.overrideComponent(SuscripcionesComponent, { set: { template: '' } });
    const fixture = TestBed.createComponent(SuscripcionesComponent);
    component = fixture.componentInstance;
    component.empresaSeleccionadaId = 1;
  });

  it('permite cancelar ACTIVA y presenta el estado calculado por fechas', () => {
    const item = { estado: 'ACTIVA', inicio: '2000-01-01T00:00:00Z', fin: '2999-01-01T00:00:00Z' } as SuscripcionItem;
    expect(component.puedeCancelar(item)).toBe(true);
    expect(component.estadoPeriodo(item)).toBe('VIGENTE');
    expect(component.puedeCancelar({ ...item, estado: 'CANCELADA' })).toBe(false);
  });

  it('conserva el instante exacto del fin anterior al renovar', () => {
    const fin = '2990-01-01T10:20:35.123Z';
    component.planVigencia = { fin, codigo_plan: 'BASICO', uso: { sucursales_activas: 1 } } as any;
    component.abrirModalAsignar();
    component.guardarSuscripcion();
    expect(api.asignarSuscripcion.mock.calls[0][1].inicio).toBe(fin);
  });

  it('muestra errores del historial en lugar de presentarlos como lista vacía', () => {
    api.obtenerHistorialSuscripciones.mockReturnValue(throwError(() => ({ status: 403, error: { detail: 'Acceso denegado' } })));
    component.cargarHistorial(1);
    expect(component.errorHistorial).toBe('Acceso denegado');
    expect(component.cargandoHistorial).toBe(false);
  });

  it('ignora respuestas de una empresa anterior tras cambiar de selección', () => {
    const anterior = new Subject<any>();
    api.obtenerHistorialSuscripciones.mockReturnValueOnce(anterior).mockReturnValueOnce(of({ data: [{ id_empresa: 2 }] }));
    component.cargarHistorial(1);
    component.cargarHistorial(2);
    anterior.next({ data: [{ id_empresa: 1 }] });
    expect(component.historial[0].id_empresa).toBe(2);
  });
});
