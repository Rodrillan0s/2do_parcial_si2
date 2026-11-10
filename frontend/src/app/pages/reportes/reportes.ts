import { Component, OnInit, OnDestroy, inject, PLATFORM_ID, ChangeDetectorRef, DestroyRef } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, ActivatedRoute } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged, takeUntil } from 'rxjs/operators';
import { 
  ReportesService, 
  ReporteVentaItem, 
  ReporteInventarioItem, 
  ReporteProductoItem, 
  ReporteSucursalItem,
  ReporteValoracionItem
} from '../../services/reportes';
import { 
  MotorReportesService, 
  ReportRequest, 
  ReporteEjecutadoData, 
  AmbiguedadDetectada, 
  OpcionAmbiguedad, 
  CatalogoReporteItem,
  ColumnaMeta
} from '../../services/motor-reportes';
import { AuthService } from '../../services/auth';
import { KpisService } from '../../services/kpis';
import { extraerMensajeError } from '../../utils/error-helper';

export type TipoReporte = 'ventas' | 'inventario' | 'productos' | 'sucursales' | 'valoraciones';

@Component({
  selector: 'app-reportes',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './reportes.html',
  styleUrls: ['./reportes.css']
})
export class ReportesComponent implements OnInit, OnDestroy {

  private reportesService = inject(ReportesService);
  public motorService = inject(MotorReportesService);
  public authService = inject(AuthService);
  private kpisService = inject(KpisService);
  private route = inject(ActivatedRoute);
  private platformId = inject(PLATFORM_ID);
  private cdr = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);

  // Control de peticiones reactivas y cancelación de consultas anteriores
  private recargarReporte$ = new Subject<void>();
  private cancelReportePrevio$ = new Subject<void>();

  // ---- MULTI-TENANT: SELECCIÓN DE TIENDA / TENANT ----
  tenants: any[] = [];
  empresaSeleccionada: number | null = null;
  tiendaNombre: string = '';

  // Modo de visualización: estándar (pestañas fijas) o dinámico (generado por motor)
  vistaActiva: 'estandar' | 'dinamico' = 'estandar';
  tipoReporteActivo: TipoReporte = 'ventas';

  // ---- Filtros estándar ----
  fechaInicio: string = '';
  fechaFin: string = '';
  sucursalSeleccionada: number | null = null;
  estadoVenta: string = 'TODOS';
  estadoStock: string = 'todos';
  categoriaSeleccionada: number | null = null;
  filtroPuntuacion: number | null = null;
  filtroCriticas: boolean = false;

  // ---- Estados de Carga ----
  cargando: boolean = false;
  descargandoPdf: boolean = false;
  descargandoPdfDinamico: boolean = false;
  mensajeError: string = '';
  mensajeExito: string = '';

  // ---- Datos del reporte estándar ----
  datosVentas: { items: ReporteVentaItem[]; resumen: any } | null = null;
  datosInventario: { items: ReporteInventarioItem[]; resumen: any } | null = null;
  datosProductos: { items: ReporteProductoItem[]; resumen: any } | null = null;
  datosSucursales: { items: ReporteSucursalItem[]; resumen: any } | null = null;
  datosValoraciones: { items: ReporteValoracionItem[]; resumen: any } | null = null;

  // ---- MOTOR DE REPORTES DINÁMICO & VOZ ----
  comandoTexto: string = '';
  escuchandoVoz: boolean = false;
  soportaVoz: boolean = false;
  reconocedorVoz: any = null;
  interpretandoComando: boolean = false;
  comandoInterpretadoResumen: string = '';
  ultimoReportRequest: ReportRequest | null = null;
  resultadoDinamico: ReporteEjecutadoData | null = null;
  catalogoMotor: CatalogoReporteItem[] = [];

  // Desambiguación
  ambiguedadesPendientes: AmbiguedadDetectada[] = [];
  mostrarModalAmbiguedad: boolean = false;

  // Comandos sugeridos rápidos
  comandosSugeridos: string[] = [
    'Ventas de hoy',
    'Ventas pendientes de pago',
    'Valoraciones y satisfacción de clientes',
    'Quejas de calidad de prendas (1★)',
    'Opiniones de clientes por sucursal',
    'Reservas de prendas apartadas',
    'Auditoría y ventas POS',
    'Ventas de esta semana por sucursal',
    'Inventario de prendas agotadas',
    'Prendas con stock bajo',
    'Reporte de pagos de este mes',
    'Sesiones de caja',
    'Devoluciones de este mes',
    'Rentabilidad por producto',
    'Rendimiento de cajeros',
    'Stock inmovilizado'
  ];

  // Paginación en tabla
  paginaActual: number = 1;
  itemsPorPagina: number = 15;

  get sucursalesDisponibles() {
    return this.authService.branchList || [
      { id: 1, nombre: 'Sucursal Central Equipetrol', ciudad: 'Santa Cruz' },
      { id: 2, nombre: 'Sucursal Calacoto Luxury', ciudad: 'La Paz' },
      { id: 3, nombre: 'Sucursal Cochabamba Jardin', ciudad: 'Cochabamba' }
    ];
  }

  ngOnInit(): void {
    if (isPlatformBrowser(this.platformId)) {
      this.soportaVoz = this.motorService.isSpeechRecognitionSupported();
      this.cargarCatalogoMotor();
      this.establecerRangoMesActual();

      // Unificar consultas en pipeline debounced para evitar peticiones repetidas en la carga inicial
      this.recargarReporte$
        .pipe(
          debounceTime(80),
          takeUntilDestroyed(this.destroyRef)
        )
        .subscribe(() => {
          this.ejecutarConsultaReporte();
        });

      // Inicializar con la empresa y sucursal activas del Header
      this.empresaSeleccionada = this.authService.getEffectiveCompanyId();
      this.sucursalSeleccionada = this.authService.activeBranch()?.id || null;

      this.cargarTenants();

      // Suscribirse reactivamente al cambio de Empresa en el Header
      this.authService.companyChanged$
        .pipe(
          distinctUntilChanged((p, c) => p?.id_empresa === c?.id_empresa),
          takeUntilDestroyed(this.destroyRef)
        )
        .subscribe(empresa => {
          const newId = empresa ? empresa.id_empresa : this.authService.getEffectiveCompanyId();
          if (this.empresaSeleccionada !== newId) {
            this.empresaSeleccionada = newId;
            const t = this.tenants.find(x => x.id_empresa === this.empresaSeleccionada);
            this.tiendaNombre = t?.nombre_empresa || empresa?.nombre_empresa || '';
            this.consultarReporte();
          }
        });

      // Suscribirse reactivamente al cambio de Sucursal en el Header
      this.authService.branchChanged$
        .pipe(
          distinctUntilChanged((p, c) => p?.id === c?.id),
          takeUntilDestroyed(this.destroyRef)
        )
        .subscribe(branch => {
          const newBranchId = branch ? branch.id : null;
          if (this.sucursalSeleccionada !== newBranchId) {
            this.sucursalSeleccionada = newBranchId;
            this.consultarReporte();
          }
        });

      // Leer queryParams opcionales enviados desde el Dashboard de KPIs
      this.route.queryParams
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe(params => {
          if (params['empresa']) {
            this.empresaSeleccionada = Number(params['empresa']);
          }
          if (params['tienda_nombre']) {
            this.tiendaNombre = params['tienda_nombre'];
          }
          if (params['tipo']) {
            const t = String(params['tipo']).toLowerCase();
            if (t === 'ventas' || t === 'inventario' || t === 'productos' || t === 'sucursales' || t === 'valoraciones') {
              this.tipoReporteActivo = t as TipoReporte;
              this.vistaActiva = 'estandar';
              this.consultarReporte();
            } else {
              // Reporte especial dinámico (caja, pagos, reservas, etc.)
              this.vistaActiva = 'dinamico';
              this.ejecutarReporteDinamico({ 
                tipo_reporte: t, 
                filtros: this.empresaSeleccionada ? { id_empresa: this.empresaSeleccionada } : {} 
              });
            }
          } else {
            this.consultarReporte();
          }
        });
    }
  }

  cargarTenants() {
    this.kpisService.obtenerTenants().subscribe({
      next: (res) => {
        if (res.success && res.data) {
          this.tenants = res.data;
          const currentEffective = this.authService.getEffectiveCompanyId() || this.kpisService.obtenerTiendaActual()?.id_empresa;
          if (currentEffective && this.tenants.some(x => Number(x.id_empresa) === Number(currentEffective))) {
            this.empresaSeleccionada = Number(currentEffective);
          } else if (!this.empresaSeleccionada && this.tenants.length > 0) {
            this.empresaSeleccionada = Number(this.tenants[0].id_empresa);
          }
          const t = this.tenants.find(x => Number(x.id_empresa) === Number(this.empresaSeleccionada));
          if (t) {
            this.tiendaNombre = t.nombre_empresa;
            if (this.authService.getEffectiveCompanyId() !== t.id_empresa) {
              this.authService.setSelectedCompany({
                id_empresa: t.id_empresa,
                nombre_empresa: t.nombre_empresa
              });
            }
          }
          this.cdr.detectChanges();
        }
      },
      error: () => {}
    });
  }

  onCambiarEmpresa() {
    this.empresaSeleccionada = this.empresaSeleccionada ? Number(this.empresaSeleccionada) : null;
    if (this.empresaSeleccionada) {
      const t = this.tenants.find(x => Number(x.id_empresa) === Number(this.empresaSeleccionada));
      if (t) {
        this.tiendaNombre = t.nombre_empresa;
        this.authService.setSelectedCompany({
          id_empresa: t.id_empresa,
          nombre_empresa: t.nombre_empresa
        });
      }
    }
    if (this.vistaActiva === 'estandar') {
      this.consultarReporte();
    } else if (this.ultimoReportRequest) {
      if (!this.ultimoReportRequest.filtros) this.ultimoReportRequest.filtros = {};
      this.ultimoReportRequest.id_empresa = this.empresaSeleccionada || undefined;
      this.ultimoReportRequest.filtros['id_empresa'] = this.empresaSeleccionada;
      this.ejecutarReporteDinamico(this.ultimoReportRequest);
    }
  }

  cargarCatalogoMotor() {
    this.motorService.obtenerCatalogo().subscribe({
      next: (res) => {
        if (res.success) {
          this.catalogoMotor = res.catalogo;
        }
      },
      error: () => {}
    });
  }

  // ============================================================================
  // BARRA DE COMANDOS INTELIGENTE (VOZ Y TEXTO - SIN IA / DETERMINÍSTICO)
  // ============================================================================

  toggleReconocimientoVoz() {
    if (this.escuchandoVoz) {
      this.detenerReconocimientoVoz();
    } else {
      this.iniciarReconocimientoVoz();
    }
  }

  iniciarReconocimientoVoz() {
    if (!this.soportaVoz) {
      this.mensajeError = 'Tu navegador no soporta la Web Speech API nativa. Puedes escribir el comando en el campo de texto.';
      return;
    }

    this.mensajeError = '';
    this.escuchandoVoz = true;
    this.comandoTexto = '';

    this.reconocedorVoz = this.motorService.crearReconocedorVoz(
      (texto, isFinal) => {
        this.comandoTexto = texto;
        this.cdr.detectChanges();
        if (isFinal) {
          this.detenerReconocimientoVoz();
          this.ejecutarComandoTexto(texto);
        }
      },
      (error) => {
        this.escuchandoVoz = false;
        if (error !== 'no-speech') {
          this.mensajeError = `Error en captura de voz: ${error}`;
        }
        this.cdr.detectChanges();
      },
      () => {
        this.escuchandoVoz = false;
        this.cdr.detectChanges();
      }
    );

    try {
      this.reconocedorVoz.start();
    } catch (e) {
      this.escuchandoVoz = false;
    }
  }

  detenerReconocimientoVoz() {
    this.escuchandoVoz = false;
    if (this.reconocedorVoz) {
      try {
        this.reconocedorVoz.stop();
      } catch (e) {}
    }
  }

  ejecutarComandoSugerido(cmd: string) {
    this.comandoTexto = cmd;
    this.ejecutarComandoTexto(cmd);
  }

  ejecutarComandoTexto(textoManual?: string) {
    const query = (textoManual || this.comandoTexto || '').trim();
    if (!query) {
      this.mensajeError = 'Por favor ingresa o dicta un comando para el motor de reportes.';
      return;
    }

    this.interpretandoComando = true;
    this.mensajeError = '';
    this.mensajeExito = '';

    const idEmpresa = this.empresaSeleccionada ? Number(this.empresaSeleccionada) : this.authService.getEffectiveCompanyId();
    const contexto: any = idEmpresa ? { id_empresa: idEmpresa } : {};

    this.motorService.parsearComando(query, contexto).subscribe({
      next: (res) => {
        this.interpretandoComando = false;
        if (!res.valido) {
          this.mensajeError = 'No se pudo interpretar el comando. Intenta con frases como: "Ventas de hoy" o "Inventario agotado".';
          this.cdr.detectChanges();
          return;
        }

        this.comandoInterpretadoResumen = res.resumen_interpretacion;
        this.ultimoReportRequest = res.report_request;
        if (idEmpresa && this.ultimoReportRequest) {
          this.ultimoReportRequest.id_empresa = idEmpresa;
          if (!this.ultimoReportRequest.filtros) this.ultimoReportRequest.filtros = {};
          this.ultimoReportRequest.filtros['id_empresa'] = idEmpresa;
        }

        // Si existen ambigüedades (ej. "vestido" coincide con producto y categoría)
        if (res.ambiguities && res.ambiguities.length > 0) {
          this.ambiguedadesPendientes = res.ambiguities;
          this.mostrarModalAmbiguedad = true;
          this.cdr.detectChanges();
          return;
        }

        // Ejecutar directamente en el motor dinámico
        this.ejecutarReporteDinamico(this.ultimoReportRequest);
      },
      error: (err) => {
        this.interpretandoComando = false;
        this.manejarError(err);
      }
    });
  }

  resolverAmbiguedad(opcion: OpcionAmbiguedad, ambiguedad: AmbiguedadDetectada) {
    if (!this.ultimoReportRequest) return;

    if (!this.ultimoReportRequest.filtros) {
      this.ultimoReportRequest.filtros = {};
    }

    if (opcion.tipo === 'categoria') {
      this.ultimoReportRequest.filtros['categoriaId'] = opcion.id;
    } else if (opcion.tipo === 'producto') {
      this.ultimoReportRequest.filtros['productoId'] = opcion.id;
    } else if (opcion.tipo === 'sucursal') {
      this.ultimoReportRequest.filtros['sucursalId'] = opcion.id;
    } else if (opcion.tipo === 'metodo_pago') {
      this.ultimoReportRequest.filtros['metodoPagoId'] = opcion.id;
    }

    // Remover ambigüedad resuelta
    this.ambiguedadesPendientes = this.ambiguedadesPendientes.filter(a => a.termino !== ambiguedad.termino);
    if (this.ambiguedadesPendientes.length === 0) {
      this.mostrarModalAmbiguedad = false;
      this.ejecutarReporteDinamico(this.ultimoReportRequest);
    }
  }

  cancelarAmbiguedad() {
    this.mostrarModalAmbiguedad = false;
    this.ambiguedadesPendientes = [];
    if (this.ultimoReportRequest) {
      this.ejecutarReporteDinamico(this.ultimoReportRequest);
    }
  }

  ejecutarReporteDinamico(req: ReportRequest) {
    this.cargando = true;
    this.vistaActiva = 'dinamico';
    this.paginaActual = 1;
    this.mensajeError = '';

    const idEmpresa = this.empresaSeleccionada ? Number(this.empresaSeleccionada) : this.authService.getEffectiveCompanyId();
    if (idEmpresa) {
      req.id_empresa = idEmpresa;
      if (!req.filtros) req.filtros = {};
      req.filtros['id_empresa'] = idEmpresa;
    }

    this.motorService.ejecutarReporte(req).subscribe({
      next: (res) => {
        this.resultadoDinamico = res.data;
        this.cargando = false;
        this.mensajeExito = `Reporte generado: ${res.data.nombre} (${res.data.resumen.total_registros} registros)`;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.cargando = false;
        this.manejarError(err);
      }
    });
  }

  descargarPdfDinamico() {
    if (!this.ultimoReportRequest) return;
    this.descargandoPdfDinamico = true;
    this.mensajeError = '';

    const idEmpresa = this.empresaSeleccionada ? Number(this.empresaSeleccionada) : this.authService.getEffectiveCompanyId();
    if (idEmpresa) {
      this.ultimoReportRequest.id_empresa = idEmpresa;
      if (!this.ultimoReportRequest.filtros) this.ultimoReportRequest.filtros = {};
      this.ultimoReportRequest.filtros['id_empresa'] = idEmpresa;
    }

    this.motorService.exportarPdf(this.ultimoReportRequest).subscribe({
      next: (blob) => {
        const timestamp = new Date().toISOString().replace(/\D/g, '').substring(0, 14);
        const tipo = this.ultimoReportRequest?.tipo_reporte || 'dinamico';
        const nombreArchivo = `Reporte_${tipo.toUpperCase()}_${timestamp}.pdf`;

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = nombreArchivo;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        this.descargandoPdfDinamico = false;
        this.mensajeExito = `PDF oficial generado y descargado: ${nombreArchivo}`;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.descargandoPdfDinamico = false;
        this.mensajeError = 'Error al generar el PDF del reporte en el servidor.';
        this.cdr.detectChanges();
      }
    });
  }

  exportarExcelDinamico() {
    if (!this.resultadoDinamico || !this.resultadoDinamico.items.length) {
      alert('No hay registros para exportar.');
      return;
    }
    const timestamp = new Date().toISOString().replace(/\D/g, '').substring(0, 14);
    const nombre = `Reporte_${this.resultadoDinamico.codigo}_${timestamp}`;
    this.motorService.exportarExcel(
      this.resultadoDinamico.items,
      nombre,
      this.resultadoDinamico.columnas,
      this.resultadoDinamico.nombre
    );
  }

  exportarCsvDinamico() {
    if (!this.resultadoDinamico || !this.resultadoDinamico.items.length) {
      alert('No hay registros para exportar.');
      return;
    }
    const timestamp = new Date().toISOString().replace(/\D/g, '').substring(0, 14);
    const nombre = `Reporte_${this.resultadoDinamico.codigo}_${timestamp}`;
    this.motorService.exportarCsv(
      this.resultadoDinamico.items,
      nombre,
      this.resultadoDinamico.columnas
    );
  }

  volverAVistaEstandar() {
    this.vistaActiva = 'estandar';
    this.cdr.detectChanges();
  }

  // ============================================================================
  // REPORTES ESTÁNDAR (PESTAÑAS CLÁSICAS)
  // ============================================================================

  cambiarTipoReporte(tipo: TipoReporte) {
    this.tipoReporteActivo = tipo;
    this.vistaActiva = 'estandar';
    this.paginaActual = 1;
    this.mensajeError = '';
    this.mensajeExito = '';
    this.consultarReporte();
  }

  establecerRangoMesActual() {
    const ahora = new Date();
    const primerDia = new Date(ahora.getFullYear(), ahora.getMonth(), 1);
    this.fechaInicio = primerDia.toISOString().substring(0, 10);
    this.fechaFin = ahora.toISOString().substring(0, 10);
  }

  limpiarFiltros() {
    this.fechaInicio = '';
    this.fechaFin = '';
    this.sucursalSeleccionada = null;
    this.estadoVenta = 'TODOS';
    this.estadoStock = 'todos';
    this.categoriaSeleccionada = null;
    this.filtroPuntuacion = null;
    this.filtroCriticas = false;
    this.comandoTexto = '';
    this.comandoInterpretadoResumen = '';
    this.vistaActiva = 'estandar';
    this.consultarReporte();
  }

  consultarReporte(inmediato: boolean = false) {
    if (inmediato) {
      this.ejecutarConsultaReporte();
    } else {
      this.recargarReporte$.next();
    }
  }

  ejecutarConsultaReporte() {
    // Cancelar cualquier petición de reporte previa aún en tránsito
    this.cancelReportePrevio$.next();

    this.cargando = true;
    this.mensajeError = '';
    this.mensajeExito = '';
    this.paginaActual = 1;

    const fIni = this.fechaInicio || undefined;
    const fFin = this.fechaFin || undefined;
    const suc = this.sucursalSeleccionada || undefined;
    const emp = this.empresaSeleccionada || undefined;

    if (this.tipoReporteActivo === 'ventas') {
      const est = this.estadoVenta !== 'TODOS' ? this.estadoVenta : undefined;
      this.reportesService.obtenerReporteVentas({
        fecha_inicio: fIni,
        fecha_fin: fFin,
        id_sucursal: suc,
        estado: est,
        id_empresa: emp
      })
      .pipe(takeUntil(this.cancelReportePrevio$))
      .subscribe({
        next: (res) => {
          this.datosVentas = res.data;
          this.cargando = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') this.manejarError(err);
        }
      });
    } else if (this.tipoReporteActivo === 'inventario') {
      const estStock = this.estadoStock !== 'todos' ? this.estadoStock : undefined;
      const cat = this.categoriaSeleccionada || undefined;
      this.reportesService.obtenerReporteInventario({
        id_sucursal: suc,
        id_categoria: cat,
        estado_stock: estStock,
        id_empresa: emp
      })
      .pipe(takeUntil(this.cancelReportePrevio$))
      .subscribe({
        next: (res) => {
          this.datosInventario = res.data;
          this.cargando = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') this.manejarError(err);
        }
      });
    } else if (this.tipoReporteActivo === 'productos') {
      const cat = this.categoriaSeleccionada || undefined;
      this.reportesService.obtenerReporteProductos({
        fecha_inicio: fIni,
        fecha_fin: fFin,
        id_sucursal: suc,
        id_categoria: cat,
        id_empresa: emp
      })
      .pipe(takeUntil(this.cancelReportePrevio$))
      .subscribe({
        next: (res) => {
          this.datosProductos = res.data;
          this.cargando = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') this.manejarError(err);
        }
      });
    } else if (this.tipoReporteActivo === 'sucursales') {
      this.reportesService.obtenerReporteSucursales({
        fecha_inicio: fIni,
        fecha_fin: fFin,
        id_empresa: emp
      })
      .pipe(takeUntil(this.cancelReportePrevio$))
      .subscribe({
        next: (res) => {
          this.datosSucursales = res.data;
          this.cargando = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') this.manejarError(err);
        }
      });
    } else if (this.tipoReporteActivo === 'valoraciones') {
      this.reportesService.obtenerReporteValoraciones({
        fecha_inicio: fIni,
        fecha_fin: fFin,
        id_sucursal: suc,
        puntuacion: this.filtroPuntuacion || undefined,
        requiere_revision: this.filtroCriticas ? true : undefined,
        id_empresa: emp
      })
      .pipe(takeUntil(this.cancelReportePrevio$))
      .subscribe({
        next: (res) => {
          this.datosValoraciones = res.data;
          this.cargando = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') this.manejarError(err);
        }
      });
    }
  }

  ngOnDestroy(): void {
    this.cancelReportePrevio$.next();
    this.cancelReportePrevio$.complete();
    this.recargarReporte$.complete();
  }

  descargarPdf() {
    this.descargandoPdf = true;
    this.mensajeError = '';

    const fIni = this.fechaInicio || undefined;
    const fFin = this.fechaFin || undefined;
    const suc = this.sucursalSeleccionada || undefined;
    const emp = this.empresaSeleccionada || undefined;
    const timestamp = new Date().toISOString().replace(/\D/g, '').substring(0, 14);

    let obs;
    let nombreArchivo = '';

    if (this.tipoReporteActivo === 'ventas') {
      nombreArchivo = `Reporte_Ventas_${timestamp}.pdf`;
      obs = this.reportesService.descargarPdfVentas({
        fecha_inicio: fIni,
        fecha_fin: fFin,
        id_sucursal: suc,
        estado: this.estadoVenta !== 'TODOS' ? this.estadoVenta : undefined,
        id_empresa: emp
      });
    } else if (this.tipoReporteActivo === 'inventario') {
      nombreArchivo = `Reporte_Inventario_${timestamp}.pdf`;
      obs = this.reportesService.descargarPdfInventario({
        id_sucursal: suc,
        id_categoria: this.categoriaSeleccionada || undefined,
        estado_stock: this.estadoStock !== 'todos' ? this.estadoStock : undefined,
        id_empresa: emp
      });
    } else if (this.tipoReporteActivo === 'productos') {
      nombreArchivo = `Reporte_Productos_Vendidos_${timestamp}.pdf`;
      obs = this.reportesService.descargarPdfProductos({
        fecha_inicio: fIni,
        fecha_fin: fFin,
        id_sucursal: suc,
        id_categoria: this.categoriaSeleccionada || undefined,
        id_empresa: emp
      });
    } else if (this.tipoReporteActivo === 'valoraciones') {
      nombreArchivo = `Reporte_Valoraciones_${timestamp}.pdf`;
      obs = this.reportesService.descargarPdfValoraciones({
        fecha_inicio: fIni,
        fecha_fin: fFin,
        id_sucursal: suc,
        puntuacion: this.filtroPuntuacion || undefined,
        requiere_revision: this.filtroCriticas ? true : undefined,
        id_empresa: emp
      });
    } else {
      nombreArchivo = `Reporte_Sucursales_${timestamp}.pdf`;
      obs = this.reportesService.descargarPdfSucursales({
        fecha_inicio: fIni,
        fecha_fin: fFin,
        id_empresa: emp
      });
    }

    obs.subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = nombreArchivo;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        this.descargandoPdf = false;
        this.mensajeExito = `PDF generado y descargado: ${nombreArchivo}`;
        this.cdr.detectChanges();
      },
      error: () => {
        this.descargandoPdf = false;
        this.mensajeError = 'Error al descargar el PDF generado por el backend.';
        this.cdr.detectChanges();
      }
    });
  }

  exportarExcel() {
    const timestamp = new Date().toISOString().replace(/\D/g, '').substring(0, 14);

    if (this.tipoReporteActivo === 'ventas') {
      const filas = (this.datosVentas?.items || []).map(v => ({
        'N° Venta': v.numero_venta,
        'Fecha': v.fecha,
        'Sucursal': v.sucursal,
        'Cliente': v.cliente,
        'NIT/CI': v.nit_ci,
        'Método Pago': v.metodo_pago,
        'Subtotal (Bs.)': v.subtotal,
        'Descuento (Bs.)': v.descuento,
        'Total (Bs.)': v.total,
        'Estado': v.estado
      }));
      this.reportesService.exportarAExcel(filas, `Reporte_Ventas_${timestamp}`, 'Ventas');
    } else if (this.tipoReporteActivo === 'inventario') {
      const filas = (this.datosInventario?.items || []).map(i => ({
        'Prenda': i.producto,
        'SKU': i.sku,
        'Código': i.codigo_producto,
        'Categoría': i.categoria,
        'Talla': i.talla,
        'Color': i.color,
        'Sucursal': i.sucursal,
        'Stock Actual': i.stock_actual,
        'Stock Reservado': i.stock_reservado,
        'Stock Disponible': i.stock_disponible,
        'Stock Mínimo': i.stock_minimo,
        'Estado': i.estado_alerta
      }));
      this.reportesService.exportarAExcel(filas, `Reporte_Inventario_${timestamp}`, 'Inventario');
    } else if (this.tipoReporteActivo === 'productos') {
      const filas = (this.datosProductos?.items || []).map(p => ({
        'Prenda / Modelo': p.producto,
        'SKU': p.sku,
        'Categoría': p.categoria,
        'Talla': p.talla,
        'Color': p.color,
        'Unidades Vendidas': p.unidades_vendidas,
        'Precio Promedio (Bs.)': p.precio_promedio,
        'Total Ingresos (Bs.)': p.total_ingresos,
        'Participación %': p.participacion_pct
      }));
      this.reportesService.exportarAExcel(filas, `Reporte_Productos_Vendidos_${timestamp}`, 'Productos');
    } else if (this.tipoReporteActivo === 'valoraciones') {
      const filas = (this.datosValoraciones?.items || []).map(v => ({
        'Fecha': v.fecha,
        'Cliente': v.cliente,
        'Prenda / Producto': v.producto,
        'Categoría': v.categoria,
        'Sucursal': v.sucursal,
        'Puntuación (★)': v.puntuacion,
        'N° Referencia': v.codigo_referencia,
        'Motivo Queja': v.motivo_negativo || 'N/A',
        'Comentario': v.comentario || '',
        'Satisfacción': v.estado_satisfaccion,
        'Requiere Revisión': v.requiere_revision ? 'SÍ' : 'NO'
      }));
      this.reportesService.exportarAExcel(filas, `Reporte_Valoraciones_${timestamp}`, 'Valoraciones');
    } else {
      const filas = (this.datosSucursales?.items || []).map(s => ({
        'Sucursal': s.sucursal,
        'Ciudad': s.ciudad,
        'Teléfono': s.telefono,
        'Cantidad Ventas': s.cantidad_ventas,
        'Prendas Vendidas': s.unidades_vendidas,
        'Ticket Promedio (Bs.)': s.ticket_promedio,
        'Total Ingresos (Bs.)': s.total_ingresos,
        'Participación Ingresos %': s.participacion_ingresos_pct
      }));
      this.reportesService.exportarAExcel(filas, `Reporte_Sucursales_${timestamp}`, 'Sucursales');
    }
  }

  exportarCsv() {
    const timestamp = new Date().toISOString().replace(/\D/g, '').substring(0, 14);

    if (this.tipoReporteActivo === 'ventas') {
      const filas = (this.datosVentas?.items || []).map(v => ({
        'N° Venta': v.numero_venta,
        'Fecha': v.fecha,
        'Sucursal': v.sucursal,
        'Cliente': v.cliente,
        'NIT/CI': v.nit_ci,
        'Método Pago': v.metodo_pago,
        'Subtotal (Bs.)': v.subtotal,
        'Descuento (Bs.)': v.descuento,
        'Total (Bs.)': v.total,
        'Estado': v.estado
      }));
      this.reportesService.exportarACSV(filas, `Reporte_Ventas_${timestamp}`);
    } else if (this.tipoReporteActivo === 'inventario') {
      const filas = (this.datosInventario?.items || []).map(i => ({
        'Prenda': i.producto,
        'SKU': i.sku,
        'Código': i.codigo_producto,
        'Categoría': i.categoria,
        'Talla': i.talla,
        'Color': i.color,
        'Sucursal': i.sucursal,
        'Stock Actual': i.stock_actual,
        'Stock Reservado': i.stock_reservado,
        'Stock Disponible': i.stock_disponible,
        'Stock Mínimo': i.stock_minimo,
        'Estado': i.estado_alerta
      }));
      this.reportesService.exportarACSV(filas, `Reporte_Inventario_${timestamp}`);
    } else if (this.tipoReporteActivo === 'productos') {
      const filas = (this.datosProductos?.items || []).map(p => ({
        'Prenda / Modelo': p.producto,
        'SKU': p.sku,
        'Categoría': p.categoria,
        'Talla': p.talla,
        'Color': p.color,
        'Unidades Vendidas': p.unidades_vendidas,
        'Precio Promedio (Bs.)': p.precio_promedio,
        'Total Ingresos (Bs.)': p.total_ingresos,
        'Participación %': p.participacion_pct
      }));
      this.reportesService.exportarACSV(filas, `Reporte_Productos_Vendidos_${timestamp}`);
    } else if (this.tipoReporteActivo === 'valoraciones') {
      const filas = (this.datosValoraciones?.items || []).map(v => ({
        'Fecha': v.fecha,
        'Cliente': v.cliente,
        'Prenda / Producto': v.producto,
        'Categoría': v.categoria,
        'Sucursal': v.sucursal,
        'Puntuación (★)': v.puntuacion,
        'N° Referencia': v.codigo_referencia,
        'Motivo Queja': v.motivo_negativo || 'N/A',
        'Comentario': v.comentario || '',
        'Satisfacción': v.estado_satisfaccion,
        'Requiere Revisión': v.requiere_revision ? 'SÍ' : 'NO'
      }));
      this.reportesService.exportarACSV(filas, `Reporte_Valoraciones_${timestamp}`);
    } else {
      const filas = (this.datosSucursales?.items || []).map(s => ({
        'Sucursal': s.sucursal,
        'Ciudad': s.ciudad,
        'Teléfono': s.telefono,
        'Cantidad Ventas': s.cantidad_ventas,
        'Prendas Vendidas': s.unidades_vendidas,
        'Ticket Promedio (Bs.)': s.ticket_promedio,
        'Total Ingresos (Bs.)': s.total_ingresos,
        'Participación Ingresos %': s.participacion_ingresos_pct
      }));
      this.reportesService.exportarACSV(filas, `Reporte_Sucursales_${timestamp}`);
    }
  }

  // ---- Helpers de Paginación Dinámica y Estándar ----
  get totalItems(): number {
    if (this.vistaActiva === 'dinamico') {
      return this.resultadoDinamico?.items.length || 0;
    }
    if (this.tipoReporteActivo === 'ventas') return this.datosVentas?.items.length || 0;
    if (this.tipoReporteActivo === 'inventario') return this.datosInventario?.items.length || 0;
    if (this.tipoReporteActivo === 'productos') return this.datosProductos?.items.length || 0;
    if (this.tipoReporteActivo === 'valoraciones') return this.datosValoraciones?.items.length || 0;
    return this.datosSucursales?.items.length || 0;
  }

  get totalPaginas(): number {
    return Math.ceil(this.totalItems / this.itemsPorPagina) || 1;
  }

  get itemsPaginados(): any[] {
    const inicio = (this.paginaActual - 1) * this.itemsPorPagina;
    const fin = inicio + this.itemsPorPagina;
    if (this.vistaActiva === 'dinamico') {
      return (this.resultadoDinamico?.items || []).slice(inicio, fin);
    }
    if (this.tipoReporteActivo === 'ventas') return (this.datosVentas?.items || []).slice(inicio, fin);
    if (this.tipoReporteActivo === 'inventario') return (this.datosInventario?.items || []).slice(inicio, fin);
    if (this.tipoReporteActivo === 'productos') return (this.datosProductos?.items || []).slice(inicio, fin);
    if (this.tipoReporteActivo === 'valoraciones') return (this.datosValoraciones?.items || []).slice(inicio, fin);
    return (this.datosSucursales?.items || []).slice(inicio, fin);
  }

  irAPagina(p: number) {
    if (p >= 1 && p <= this.totalPaginas) {
      this.paginaActual = p;
    }
  }

  private manejarError(err: any) {
    this.cargando = false;
    this.mensajeError = extraerMensajeError(err, 'Error al procesar la solicitud de reporte.');
    this.cdr.detectChanges();
  }

  obtenerBadgeClass(valor: any): string {
    const val = String(valor || '').toUpperCase();
    if (val.includes('⚠️') || val.includes('VENCIDA') || val.includes('AGOTADO') || val.includes('ANULADA') || val.includes('CANCELAD') || val.includes('SIN COBRO') || val.includes('SIN PAGO') || val.includes('CRITIC') || val.includes('NEGATIV')) {
      return 'bg-rose-100 text-rose-700 dark:bg-rose-950/70 dark:text-rose-300 border border-rose-200 dark:border-rose-900';
    }
    if (val.includes('PENDIENTE') || val.includes('BAJO') || val.includes('ESPERA') || val.includes('NEUTR')) {
      return 'bg-amber-100 text-amber-700 dark:bg-amber-950/70 dark:text-amber-300 border border-amber-200 dark:border-amber-900';
    }
    if (val.includes('COMPLETAD') || val.includes('OPTIMO') || val.includes('VIGENTE') || val.includes('PAGADO') || val.includes('✓') || val.includes('CUADRADO') || val.includes('POSITIV')) {
      return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900';
    }
    return 'bg-stone-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300';
  }
}
