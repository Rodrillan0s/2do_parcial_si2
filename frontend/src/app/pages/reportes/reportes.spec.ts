import { TestBed, ComponentFixture, fakeAsync, tick } from '@angular/core/testing';
import { provideRouter, ActivatedRoute } from '@angular/router';
import { PLATFORM_ID, signal } from '@angular/core';
import { of, throwError, BehaviorSubject } from 'rxjs';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { ReportesComponent } from './reportes';
import { ReportesService } from '../../services/reportes';
import { 
  MotorReportesService, 
  ParseCommandResponse, 
  ReporteEjecutadoData, 
  CatalogoReporteItem 
} from '../../services/motor-reportes';
import { AuthService } from '../../services/auth';
import { KpisService } from '../../services/kpis';

describe('CU21W / CU22W: ReportesComponent & Motor de Reportes Dinámico (Frontend)', () => {
  let component: ReportesComponent;
  let fixture: ComponentFixture<ReportesComponent>;
  let mockReportesService: any;
  let mockMotorService: any;
  let mockAuthService: any;
  let mockKpisService: any;

  const mockCatalogo: CatalogoReporteItem[] = [
    {
      codigo: 'ventas_pendientes',
      nombre: 'Ventas Pendientes de Pago',
      descripcion: 'Ventas registradas que no completaron confirmación de pago',
      vista: 'comercio.vw_ventas_pendientes_reporte',
      filtros_permitidos: ['sucursalId', 'fechaDesde', 'fechaHasta', 'metodoPagoId'],
      agrupaciones_permitidas: ['sucursal', 'metodo_pago', 'dia'],
      columnas: [
        { campo: 'numero_venta', titulo: 'N° Venta', tipo: 'string' },
        { campo: 'fecha', titulo: 'Fecha', tipo: 'date' },
        { campo: 'sucursal', titulo: 'Sucursal', tipo: 'string' },
        { campo: 'cliente', titulo: 'Cliente', tipo: 'string' },
        { campo: 'total', titulo: 'Total Bs.', tipo: 'currency' },
        { campo: 'estado', titulo: 'Estado', tipo: 'badge' }
      ],
      campo_monto: 'total'
    },
    {
      codigo: 'reservas_apartadas',
      nombre: 'Prendas Apartadas y Reservas',
      descripcion: 'Prendas separadas con anticipo en boutique',
      vista: 'comercio.vw_reservas_reporte',
      filtros_permitidos: ['sucursalId', 'estadoReserva'],
      agrupaciones_permitidas: ['sucursal', 'estado'],
      columnas: [
        { campo: 'codigo_reserva', titulo: 'Código', tipo: 'string' },
        { campo: 'cliente', titulo: 'Cliente', tipo: 'string' },
        { campo: 'total', titulo: 'Total Bs.', tipo: 'currency' }
      ],
      campo_monto: 'total'
    }
  ];

  const mockParseResponseVentasPendientes: ParseCommandResponse = {
    success: true,
    valido: true,
    comando_original: 'Ventas pendientes de pago',
    resumen_interpretacion: 'Reporte de **VENTAS PENDIENTES**',
    report_request: {
      tipo_reporte: 'ventas_pendientes',
      reporte: 'ventas_pendientes',
      filtros: {},
      groupBy: null,
      orderBy: 'fecha',
      orderDirection: 'DESC'
    },
    ambiguities: []
  };

  const mockEjecucionVentasPendientes: { success: boolean; data: ReporteEjecutadoData } = {
    success: true,
    data: {
      tipo_reporte: 'ventas_pendientes',
      codigo: 'ventas_pendientes',
      nombre: 'Ventas Pendientes de Pago',
      descripcion: 'Ventas registradas que no completaron confirmación de pago',
      columnas: [
        { campo: 'numero_venta', titulo: 'N° Venta', tipo: 'string' },
        { campo: 'fecha', titulo: 'Fecha', tipo: 'date' },
        { campo: 'sucursal', titulo: 'Sucursal', tipo: 'string' },
        { campo: 'cliente', titulo: 'Cliente', tipo: 'string' },
        { campo: 'total', titulo: 'Total Bs.', tipo: 'currency' },
        { campo: 'estado', titulo: 'Estado', tipo: 'badge' }
      ],
      items: [
        {
          id_venta: 101,
          numero_venta: 'VTA-20261107-001',
          fecha: '2026-11-07 10:30',
          sucursal: 'Sucursal Central Equipetrol',
          cliente: 'Juan Perez',
          total: 250.00,
          estado: 'PENDIENTE_PAGO'
        }
      ],
      resumen: {
        total_registros: 1,
        total_monto: 250.00,
        promedio_monto: 250.00,
        campo_monto_usado: 'total'
      },
      filtros_aplicados: { id_empresa: 1 },
      groupBy: null,
      orderBy: 'fecha',
      orderDirection: 'DESC'
    }
  };

  const companyChanged$ = new BehaviorSubject<{ id_empresa: number; nombre_empresa: string } | null>({
    id_empresa: 1,
    nombre_empresa: 'Shopping Bolivia'
  });
  const branchChanged$ = new BehaviorSubject<{ id: number; nombre: string; ciudad: string } | null>({
    id: 1,
    nombre: 'Sucursal Central Equipetrol',
    ciudad: 'Santa Cruz'
  });

  beforeEach(async () => {
    mockReportesService = {
      obtenerReporteVentas: vi.fn(() => of({
        success: true,
        message: 'OK',
        data: {
          items: [],
          resumen: { cantidad_ventas: 0, total_recaudado: 0, total_subtotal: 0, total_descuento: 0, ticket_promedio: 0 }
        }
      })),
      obtenerReporteInventario: vi.fn(() => of({
        success: true,
        message: 'OK',
        data: {
          items: [],
          resumen: { total_items_registrados: 0, stock_total_unidades: 0, stock_reservado_unidades: 0, stock_disponible_unidades: 0, items_agotados: 0, items_bajo_stock: 0 }
        }
      })),
      obtenerReporteProductos: vi.fn(() => of({
        success: true,
        message: 'OK',
        data: {
          items: [],
          resumen: { total_productos_distintos: 0, total_unidades_vendidas: 0, total_ingresos: 0, precio_promedio_general: 0 }
        }
      })),
      obtenerReporteSucursales: vi.fn(() => of({
        success: true,
        message: 'OK',
        data: {
          items: [],
          resumen: { total_sucursales: 0, total_ventas: 0, total_ingresos: 0, total_unidades_vendidas: 0, ticket_promedio_general: 0 }
        }
      }))
    };

    mockMotorService = {
      obtenerCatalogo: vi.fn(() => of({ success: true, catalogo: mockCatalogo, total: mockCatalogo.length })),
      parsearComando: vi.fn(() => of(mockParseResponseVentasPendientes)),
      ejecutarReporte: vi.fn(() => of(mockEjecucionVentasPendientes)),
      exportarPdf: vi.fn(() => of(new Blob(['fake-pdf'], { type: 'application/pdf' }))),
      exportarExcel: vi.fn(),
      exportarCsv: vi.fn(),
      isSpeechRecognitionSupported: vi.fn(() => false),
      crearReconocedorVoz: vi.fn()
    };

    mockAuthService = {
      obtenerToken: () => 'fake-jwt-token',
      obtenerUsuario: () => ({ id_usuario: 1, id_empresa: 1, nombre_rol: 'ADMINISTRADOR' }),
      getEffectiveCompanyId: vi.fn(() => 1),
      isGlobalAdmin: vi.fn(() => true),
      activeBranch: signal({ id: 1, nombre: 'Sucursal Central Equipetrol', ciudad: 'Santa Cruz' }),
      companyChanged$: companyChanged$.asObservable(),
      branchChanged$: branchChanged$.asObservable(),
      setSelectedCompany: vi.fn(),
      branchList: [
        { id: 1, nombre: 'Sucursal Central Equipetrol', ciudad: 'Santa Cruz' },
        { id: 2, nombre: 'Sucursal Calacoto Luxury', ciudad: 'La Paz' }
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
      obtenerTiendaActual: vi.fn(() => ({ id_empresa: 1, nombre_empresa: 'Shopping Bolivia' }))
    };

    await TestBed.configureTestingModule({
      imports: [ReportesComponent],
      providers: [
        provideRouter([]),
        { provide: PLATFORM_ID, useValue: 'browser' },
        { provide: ReportesService, useValue: mockReportesService },
        { provide: MotorReportesService, useValue: mockMotorService },
        { provide: AuthService, useValue: mockAuthService },
        { provide: KpisService, useValue: mockKpisService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(ReportesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('debe inicializar correctamente con catálogo y chips de comandos sugeridos', () => {
    expect(component).toBeTruthy();
    expect(mockMotorService.obtenerCatalogo).toHaveBeenCalled();
    expect(component.catalogoMotor.length).toBe(2);

    // Debe contener los chips de comandos sugeridos para voz y búsqueda rápida
    expect(component.comandosSugeridos).toContain('Ventas de hoy');
    expect(component.comandosSugeridos).toContain('Ventas pendientes de pago');
    expect(component.comandosSugeridos).toContain('Reservas de prendas apartadas');
    expect(component.comandosSugeridos).toContain('Auditoría y ventas POS');
    expect(component.comandosSugeridos).toContain('Prendas con stock bajo');
    expect(component.comandosSugeridos).toContain('Devoluciones de este mes');
    expect(component.comandosSugeridos.length).toBeGreaterThanOrEqual(13);
  });

  it('debe ejecutar reporte dinámico al seleccionar el comando "Ventas pendientes de pago"', () => {
    // Simular clic en el chip sugerido
    component.ejecutarComandoSugerido('Ventas pendientes de pago');

    expect(mockMotorService.parsearComando).toHaveBeenCalledWith(
      'Ventas pendientes de pago',
      expect.objectContaining({ id_empresa: 1 })
    );

    expect(mockMotorService.ejecutarReporte).toHaveBeenCalledWith(
      expect.objectContaining({
        tipo_reporte: 'ventas_pendientes',
        id_empresa: 1
      })
    );

    expect(component.vistaActiva).toBe('dinamico');
    expect(component.resultadoDinamico).toBeTruthy();
    expect(component.resultadoDinamico?.codigo).toBe('ventas_pendientes');
    expect(component.resultadoDinamico?.items.length).toBe(1);
    expect(component.mensajeExito).toContain('Reporte generado: Ventas Pendientes de Pago (1 registros)');
    expect(component.mensajeError).toBe('');
  });

  it('debe gestionar ambigüedades en comandos y resolverlas adecuadamente', () => {
    // Simular que el parser detecta ambigüedad (ej. 'vestido' coincide con categoría y producto)
    mockMotorService.parsearComando.mockReturnValueOnce(of({
      success: true,
      valido: true,
      comando_original: 'ventas de vestido',
      resumen_interpretacion: 'Reporte de ventas de vestido',
      report_request: {
        tipo_reporte: 'ventas',
        filtros: {}
      },
      ambiguities: [
        {
          termino: 'vestido',
          opciones: [
            { tipo: 'categoria', id: 5, nombre: 'Vestidos de Gala', detalle: 'Categoría' },
            { tipo: 'producto', id: 22, nombre: 'Vestido Seda Floral', detalle: 'Prenda' }
          ]
        }
      ]
    }));

    component.ejecutarComandoTexto('ventas de vestido');

    expect(component.mostrarModalAmbiguedad).toBe(true);
    expect(component.ambiguedadesPendientes.length).toBe(1);

    // Resolver seleccionando la opción de categoría
    component.resolverAmbiguedad(
      { tipo: 'categoria', id: 5, nombre: 'Vestidos de Gala', detalle: 'Categoría' },
      component.ambiguedadesPendientes[0]
    );

    expect(component.mostrarModalAmbiguedad).toBe(false);
    expect(component.ambiguedadesPendientes.length).toBe(0);
    expect(mockMotorService.ejecutarReporte).toHaveBeenCalledWith(
      expect.objectContaining({
        filtros: expect.objectContaining({ categoriaId: 5 })
      })
    );
  });

  it('debe mostrar mensaje de error amigable cuando el motor o endpoint falla', () => {
    mockMotorService.parsearComando.mockReturnValueOnce(of(mockParseResponseVentasPendientes));
    mockMotorService.ejecutarReporte.mockReturnValueOnce(throwError(() => ({
      status: 409,
      error: { detail: 'column "estado" does not exist LINE 4: WHERE id_empresa = 1' }
    })));

    component.ejecutarComandoTexto('Ventas pendientes de pago');

    expect(component.cargando).toBe(false);
    expect(component.mensajeError).toContain('column "estado" does not exist');
  });

  it('debe alternar correctamente entre la vista dinámica y la vista estándar', () => {
    // Pasar a dinámico
    component.ejecutarComandoSugerido('Ventas pendientes de pago');
    expect(component.vistaActiva).toBe('dinamico');

    // Volver a estándar
    component.volverAVistaEstandar();
    expect(component.vistaActiva).toBe('estandar');

    // Cambiar tipo de reporte estándar
    component.cambiarTipoReporte('inventario');
    expect(component.tipoReporteActivo).toBe('inventario');
    expect(component.vistaActiva).toBe('estandar');
  });

  it('debe actualizar el tenant seleccionado y reenviar el reporte con aislamiento multitenant', () => {
    component.tenants = [
      { id_empresa: 1, nombre_empresa: 'Shopping Bolivia', ciudad: 'Santa Cruz' },
      { id_empresa: 2, nombre_empresa: 'Fashion World', ciudad: 'La Paz' }
    ];
    component.empresaSeleccionada = 2;
    component.vistaActiva = 'dinamico';
    component.ultimoReportRequest = {
      tipo_reporte: 'ventas_pendientes',
      filtros: { id_empresa: 1 }
    };

    component.onCambiarEmpresa();

    expect(mockAuthService.setSelectedCompany).toHaveBeenCalledWith({
      id_empresa: 2,
      nombre_empresa: 'Fashion World'
    });
    expect(mockMotorService.ejecutarReporte).toHaveBeenCalledWith(
      expect.objectContaining({
        id_empresa: 2,
        filtros: expect.objectContaining({ id_empresa: 2 })
      })
    );
  });

  it('debe exportar Excel y CSV del reporte dinámico si hay registros disponibles', () => {
    component.resultadoDinamico = mockEjecucionVentasPendientes.data;

    component.exportarExcelDinamico();
    expect(mockMotorService.exportarExcel).toHaveBeenCalledWith(
      mockEjecucionVentasPendientes.data.items,
      expect.stringContaining('Reporte_ventas_pendientes_'),
      mockEjecucionVentasPendientes.data.columnas,
      mockEjecucionVentasPendientes.data.nombre
    );

    component.exportarCsvDinamico();
    expect(mockMotorService.exportarCsv).toHaveBeenCalledWith(
      mockEjecucionVentasPendientes.data.items,
      expect.stringContaining('Reporte_ventas_pendientes_'),
      mockEjecucionVentasPendientes.data.columnas
    );
  });
});
