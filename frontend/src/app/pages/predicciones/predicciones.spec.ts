import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { PLATFORM_ID, signal } from '@angular/core';
import { of, throwError, BehaviorSubject } from 'rxjs';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { PrediccionesComponent } from './predicciones';
import { PrediccionesService, RespuestaDemanda, RespuestaReposicion, RespuestaEvaluacion } from '../../services/predicciones';
import { AuthService } from '../../services/auth';
import { KpisService } from '../../services/kpis';

describe('CU23W: PrediccionesComponent & PrediccionesService (Frontend)', () => {
  let component: PrediccionesComponent;
  let fixture: ComponentFixture<PrediccionesComponent>;
  let mockPrediccionesService: any;
  let mockAuthService: any;
  let mockKpisService: any;

  const mockDemandaRespuesta: RespuestaDemanda = {
    success: true,
    id_empresa: 1,
    id_sucursal: 3,
    dias_analizados: 60,
    dias_proyectados: 14,
    tendencia: 'ALCISTA',
    tasa_crecimiento_diario: 0.05,
    sigma: 1.2,
    historico: [
      { fecha: '2026-10-01', unidades: 10, ingresos: 1200, transacciones: 8 },
      { fecha: '2026-10-02', unidades: 12, ingresos: 1440, transacciones: 9 }
    ],
    proyecciones: [
      { fecha: '2026-11-08', prediccion: 13, limite_inferior: 11, limite_superior: 15 }
    ]
  };

  const mockReposicionRespuesta: RespuestaReposicion = {
    success: true,
    id_empresa: 1,
    id_sucursal: 3,
    lead_time_dias: 7,
    total_prendas_analizadas: 2,
    resumen: {
      alertas_criticas: 1,
      alertas_altas: 1,
      inversion_sugerida_bs: 1500
    },
    recomendaciones: [
      {
        id_inventario: 101,
        id_sucursal: 3,
        sucursal: 'Sucursal Cochabamba',
        id_producto: 12,
        producto: 'Vestido Seda Floral',
        codigo_producto: 'VES-012',
        categoria: 'Vestidos',
        id_variante: 55,
        sku: 'VES-012-S-ROJO',
        talla: 'S',
        color: 'Rojo',
        stock_disponible: 1,
        stock_minimo: 5,
        ritmo_diario_estimado: 0.8,
        dias_cobertura: 1.2,
        riesgo_rotura: 'CRITICO',
        prioridad: 1,
        reposicion_sugerida: 10,
        inversion_estimada_bs: 1000,
        explicacion: 'Stock crítico por debajo de margen de seguridad.'
      },
      {
        id_inventario: 102,
        id_sucursal: 3,
        sucursal: 'Sucursal Cochabamba',
        id_producto: 15,
        producto: 'Pantalón Lino',
        codigo_producto: 'PAN-015',
        categoria: 'Pantalones',
        id_variante: 60,
        sku: 'PAN-015-M-AZUL',
        talla: 'M',
        color: 'Azul',
        stock_disponible: 4,
        stock_minimo: 6,
        ritmo_diario_estimado: 0.5,
        dias_cobertura: 8,
        riesgo_rotura: 'ALTO',
        prioridad: 2,
        reposicion_sugerida: 5,
        inversion_estimada_bs: 500,
        explicacion: 'Stock en zona de reposición estándar.'
      }
    ]
  };

  const mockEvaluacionRespuesta: RespuestaEvaluacion = {
    success: true,
    id_empresa: 1,
    id_sucursal: 3,
    evaluacion: {
      mae: 1.25,
      rmse: 1.62,
      mape: 8.5,
      precision_pct: 91.5,
      puntos_evaluados: 14,
      comparativa: [
        { fecha: '2026-10-25', real: 10, predicho: 11, error_absoluto: 1 }
      ]
    }
  };

  const companyChanged$ = new BehaviorSubject<{ id_empresa: number; nombre_empresa: string } | null>({
    id_empresa: 1,
    nombre_empresa: 'Shopping Bolivia'
  });
  const branchChanged$ = new BehaviorSubject<{ id: number; nombre: string; ciudad: string } | null>({
    id: 3,
    nombre: 'Sucursal Cochabamba Jardin',
    ciudad: 'Cochabamba'
  });

  beforeEach(async () => {
    mockPrediccionesService = {
      obtenerDemanda: vi.fn(() => of(mockDemandaRespuesta)),
      obtenerReposicion: vi.fn(() => of(mockReposicionRespuesta)),
      evaluarModelo: vi.fn(() => of(mockEvaluacionRespuesta))
    };

    mockAuthService = {
      obtenerToken: () => 'fake-jwt-token',
      obtenerUsuario: () => ({ id_usuario: 1, id_empresa: 1, nombre_rol: 'ADMINISTRADOR' }),
      getEffectiveCompanyId: vi.fn(() => 1),
      getEffectiveCompanyName: vi.fn(() => 'Shopping Bolivia'),
      isGlobalAdmin: vi.fn(() => true),
      selectedCompany: signal({ id_empresa: 1, nombre_empresa: 'Shopping Bolivia' }),
      activeBranch: signal({ id: 3, nombre: 'Sucursal Cochabamba Jardin', ciudad: 'Cochabamba' }),
      companyChanged$: companyChanged$.asObservable(),
      branchChanged$: branchChanged$.asObservable(),
      setSelectedCompany: vi.fn(),
      branchList: [
        { id: 1, nombre: 'Sucursal Central Equipetrol', ciudad: 'Santa Cruz' },
        { id: 2, nombre: 'Sucursal Calacoto Luxury', ciudad: 'La Paz' },
        { id: 3, nombre: 'Sucursal Cochabamba Jardin', ciudad: 'Cochabamba' }
      ]
    };

    mockKpisService = {
      obtenerTenants: vi.fn(() => of({
        success: true,
        data: [
          { id_empresa: 1, nombre_empresa: 'Shopping Bolivia', ciudad: 'Santa Cruz' },
          { id_empresa: 2, nombre_empresa: 'Fashion World', ciudad: 'La Paz' }
        ]
      })),
      obtenerTiendaActual: vi.fn(() => ({ id_empresa: 1, nombre_empresa: 'Shopping Bolivia' })),
      tiendaSeleccionada$: of({ id_empresa: 1, nombre_empresa: 'Shopping Bolivia' })
    };

    await TestBed.configureTestingModule({
      imports: [PrediccionesComponent],
      providers: [
        provideRouter([]),
        { provide: PLATFORM_ID, useValue: 'browser' },
        { provide: PrediccionesService, useValue: mockPrediccionesService },
        { provide: AuthService, useValue: mockAuthService },
        { provide: KpisService, useValue: mockKpisService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(PrediccionesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('1. Carga inicial: inicializa con empresa efectiva y consulta proyecciones de demanda', () => {
    expect(component.empresaSeleccionada).toBe(1);
    expect(component.sucursalSeleccionada).toBe(3);
    expect(mockPrediccionesService.obtenerDemanda).toHaveBeenCalledWith({
      id_empresa: 1,
      id_sucursal: 3,
      dias_proyeccion: 14,
      dias_historia: 60
    });
    expect(component.datosDemanda).toEqual(mockDemandaRespuesta);
    expect(component.cargando).toBe(false);
    expect(component.mensajeError).toBe('');
  });

  it('2. Pestaña Reposición: cambia de pestaña, solicita recomendaciones de inventario y filtra por riesgo', () => {
    component.cambiarPestana('reposicion');
    expect(component.pestanaActiva).toBe('reposicion');
    expect(mockPrediccionesService.obtenerReposicion).toHaveBeenCalledWith({
      id_empresa: 1,
      id_sucursal: 3,
      lead_time_dias: 7
    });
    expect(component.datosReposicion).toEqual(mockReposicionRespuesta);
    expect(component.recomendacionesFiltradas.length).toBe(2);

    // Filtrar por riesgo CRITICO
    component.filtroRiesgo = 'CRITICO';
    expect(component.recomendacionesFiltradas.length).toBe(1);
    expect(component.recomendacionesFiltradas[0].sku).toBe('VES-012-S-ROJO');
  });

  it('3. Pestaña Backtesting & Evaluación: ejecuta evaluación de precisión del modelo temporal', () => {
    component.cambiarPestana('evaluacion');
    expect(component.pestanaActiva).toBe('evaluacion');
    expect(mockPrediccionesService.evaluarModelo).toHaveBeenCalledWith({
      id_empresa: 1,
      id_sucursal: 3,
      dias_test: 14
    });
    expect(component.datosEvaluacion).toEqual(mockEvaluacionRespuesta);
    expect(component.datosEvaluacion?.evaluacion.precision_pct).toBe(91.5);
  });

  it('4. Multi-Tenant: cambiar de empresa actualiza el contexto de auth y recarga los datos', () => {
    component.empresaSeleccionada = 2;
    component.onCambiarEmpresa();

    expect(mockAuthService.setSelectedCompany).toHaveBeenCalledWith({
      id_empresa: 2,
      nombre_empresa: 'Fashion World'
    });
    expect(mockPrediccionesService.obtenerDemanda).toHaveBeenCalledWith({
      id_empresa: 2,
      id_sucursal: 3,
      dias_proyeccion: 14,
      dias_historia: 60
    });
  });

  it('5. Manejo de error: muestra el mensaje amigable si el backend responde con error', () => {
    mockPrediccionesService.obtenerDemanda.mockReturnValue(throwError(() => ({
      status: 400,
      error: { detail: 'Debe seleccionar un tenant válido' }
    })));

    component.cargarDatos();

    expect(component.cargando).toBe(false);
    expect(component.mensajeError).toContain('Debe seleccionar un tenant válido');
  });
});
