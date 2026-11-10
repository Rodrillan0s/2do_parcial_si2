import { Component, OnInit, OnDestroy, inject, ChangeDetectorRef, NgZone, PLATFORM_ID, DestroyRef } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged, takeUntil } from 'rxjs/operators';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { 
  KpisService, 
  KpisResumen, 
  VentaTimelineItem, 
  ProductoMasVendidoItem, 
  InventarioAlertaItem, 
  VentaSucursalItem,
  DashboardMetricas,
  TenantDashboardItem,
  PrendaRankingSatisfaccionItem,
  AlertaCalidadCriticaItem
} from '../../services/kpis';
import { AuthService } from '../../services/auth';

@Component({
  selector: 'app-dashboard-kpis',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  templateUrl: './dashboard-kpis.html'
})
export class DashboardKpisComponent implements OnInit, OnDestroy {

  private kpisService = inject(KpisService);
  public authService = inject(AuthService);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);
  private ngZone = inject(NgZone);
  private platformId = inject(PLATFORM_ID);
  private destroyRef = inject(DestroyRef);

  // Control reactivo de peticiones y cancelación de vuelos obsoletos
  private recargarTrigger$ = new Subject<void>();
  private cancelPeticionesPrevias$ = new Subject<void>();

  // ---- MULTI-TENANT: SELECCIÓN DE TIENDA / TENANT ----
  tenants: TenantDashboardItem[] = [];
  tiendaSeleccionada: TenantDashboardItem | null = null;
  cargandoTenants: boolean = false;
  filtroBusquedaTienda: string = '';
  pestanaActiva: 'indicadores' | 'inventario' | 'satisfaccion' | 'reportes' | 'sucursales' = 'indicadores';

  // ---- Filtros W32 ----
  fechaInicio: string = '';
  fechaFin: string = '';
  sucursalSeleccionada: number | null = null;
  presetSeleccionado: 'hoy' | '7dias' | 'mes' | 'historico' = 'historico';

  // ---- Datos W32 ----
  kpisResumen: KpisResumen | null = null;
  ventasTimeline: VentaTimelineItem[] = [];
  productosTop: ProductoMasVendidoItem[] = [];
  alertasInventario: InventarioAlertaItem[] = [];
  ventasPorSucursal: VentaSucursalItem[] = [];
  rankingSatisfaccion: PrendaRankingSatisfaccionItem[] = [];
  alertasCalidad: AlertaCalidadCriticaItem[] = [];
  
  // Hover en gráfico interactivo
  puntoHover: VentaTimelineItem | null = null;
  posicionHoverX: number = 0;
  posicionHoverY: number = 0;

  // Datos de Plataforma / Empresa
  metricasPlataforma: DashboardMetricas | null = null;
  vistaActiva: 'indicadores' | 'sistema' = 'indicadores';

  cargando: boolean = false;
  mensajeError: string = '';
  usuarioActual: any = null;

  get sucursalesDisponibles() {
    if (this.tiendaSeleccionada && this.tiendaSeleccionada.sucursales && this.tiendaSeleccionada.sucursales.length > 0) {
      return this.tiendaSeleccionada.sucursales;
    }
    return this.authService.branchList || [
      { id: 1, nombre: 'Sucursal Central Equipetrol', ciudad: 'Santa Cruz' },
      { id: 2, nombre: 'Sucursal Calacoto Luxury', ciudad: 'La Paz' }
    ];
  }

  get alcance(): 'PLATAFORMA' | 'EMPRESA' | 'SUCURSAL' | 'OPERATIVO' {
    return (this.authService.getScopeLevel() as any) || 'EMPRESA';
  }

  get tenantsFiltrados(): TenantDashboardItem[] {
    if (!this.filtroBusquedaTienda || !this.filtroBusquedaTienda.trim()) {
      return this.tenants;
    }
    const q = this.filtroBusquedaTienda.toLowerCase().trim();
    return this.tenants.filter(t => 
      t.nombre_empresa.toLowerCase().includes(q) ||
      t.razon_social.toLowerCase().includes(q) ||
      t.ciudad.toLowerCase().includes(q) ||
      t.nit.toLowerCase().includes(q)
    );
  }

  ngOnInit(): void {
    if (isPlatformBrowser(this.platformId)) {
      this.usuarioActual = this.authService.obtenerUsuario();

      if (!this.usuarioActual || this.authService.tokenExpirado()) {
        this.cerrarSesion();
        return;
      }

      if (this.authService.esCliente()) {
        this.router.navigate(['/perfil']);
        return;
      }

      // Si es cajero o rol sin permiso de analítica, desviar al Terminal POS
      if (this.authService.isCashier() || (!this.authService.hasPermission('reportes.ver') && !this.authService.isGlobalAdmin() && !this.authService.isStoreAdmin())) {
        this.router.navigate(['/admin/caja']);
        return;
      }

      const scope = this.authService.getScopeLevel();
      const idEmpresaUsuario = this.usuarioActual?.id_empresa;

      // Unificar todas las recargas en un flujo debounced para evitar avalanchas
      this.recargarTrigger$
        .pipe(
          debounceTime(100),
          takeUntilDestroyed(this.destroyRef)
        )
        .subscribe(() => {
          this.ejecutarCargaIndicadores();
        });

      this.kpisService.tiendaSeleccionada$
        .pipe(
          distinctUntilChanged((prev, curr) => prev?.id_empresa === curr?.id_empresa),
          takeUntilDestroyed(this.destroyRef)
        )
        .subscribe((tienda) => {
          if (scope === 'PLATAFORMA') {
            if (tienda?.id_empresa !== this.tiendaSeleccionada?.id_empresa) {
              this.tiendaSeleccionada = tienda;
              this.cargarTodosLosIndicadores();
            }
          } else if (tienda && tienda.id_empresa === idEmpresaUsuario) {
            if (this.tiendaSeleccionada?.id_empresa !== tienda.id_empresa) {
              this.tiendaSeleccionada = tienda;
              this.cargarTodosLosIndicadores();
            }
          }
        });

      this.authService.companyChanged$
        .pipe(
          distinctUntilChanged((prev, curr) => prev?.id_empresa === curr?.id_empresa),
          takeUntilDestroyed(this.destroyRef)
        )
        .subscribe((empresa) => {
          if (scope === 'PLATAFORMA') {
            const match = empresa ? this.tenants.find(t => t.id_empresa === empresa.id_empresa) : null;
            if (match?.id_empresa !== this.tiendaSeleccionada?.id_empresa) {
              this.tiendaSeleccionada = match || null;
              this.cargarTodosLosIndicadores();
            }
          }
        });

      this.authService.branchChanged$
        .pipe(
          distinctUntilChanged((prev, curr) => prev?.id === curr?.id),
          takeUntilDestroyed(this.destroyRef)
        )
        .subscribe((branch) => {
          const newSuc = branch ? branch.id : null;
          if (this.sucursalSeleccionada !== newSuc) {
            this.sucursalSeleccionada = newSuc;
            if (this.tiendaSeleccionada || scope === 'PLATAFORMA' || idEmpresaUsuario) {
              this.cargarTodosLosIndicadores();
            }
          }
        });

      this.cargarTenants();
    }
  }

  cargarTenants(): void {
    this.cargandoTenants = true;
    this.cdr.detectChanges();

    this.kpisService.obtenerTenants().subscribe({
      next: (res) => {
        this.cargandoTenants = false;
        if (res.success && res.data) {
          this.tenants = res.data;
          const scope = this.authService.getScopeLevel();
          const idEmpresaUsuario = this.usuarioActual?.id_empresa;

          if (scope !== 'PLATAFORMA' && idEmpresaUsuario) {
            // Usuario de tienda: SIEMPRE fijar su empresa
            const miTienda = this.tenants.find(t => t.id_empresa === idEmpresaUsuario);
            if (miTienda && this.tiendaSeleccionada?.id_empresa !== miTienda.id_empresa) {
              this.seleccionarTienda(miTienda, false);
            }
          } else if (scope === 'PLATAFORMA') {
            const effId = this.authService.getEffectiveCompanyId();
            if (effId) {
              const match = this.tenants.find(t => t.id_empresa === effId);
              if (match?.id_empresa !== this.tiendaSeleccionada?.id_empresa) {
                this.tiendaSeleccionada = match || null;
                this.cargarTodosLosIndicadores();
              }
            } else {
              const activaGlobal = this.kpisService.obtenerTiendaActual();
              if (activaGlobal) {
                const match = this.tenants.find(t => t.id_empresa === activaGlobal.id_empresa);
                if (match?.id_empresa !== this.tiendaSeleccionada?.id_empresa) {
                  this.tiendaSeleccionada = match || null;
                  this.cargarTodosLosIndicadores();
                }
              } else if (this.tiendaSeleccionada !== null) {
                this.tiendaSeleccionada = null; // Vista global consolidada
                this.cargarTodosLosIndicadores();
              }
            }
          }
          // Disparar carga inicial única consolidada
          this.cargarTodosLosIndicadores();
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.cargandoTenants = false;
        console.error('Error al cargar listado de tiendas:', err);
        this.cdr.detectChanges();
      }
    });
  }

  seleccionarTienda(tienda: TenantDashboardItem, emit: boolean = true): void {
    this.tiendaSeleccionada = tienda;
    if (emit) {
      this.kpisService.establecerTiendaSeleccionada(tienda);
    }
    this.sucursalSeleccionada = null;
    this.pestanaActiva = 'indicadores';
    this.aplicarPreset(this.presetSeleccionado || 'historico', false);
    this.cargarTodosLosIndicadores();
  }

  deseleccionarTienda(): void {
    if (this.alcance !== 'PLATAFORMA') return;
    this.tiendaSeleccionada = null;
    this.kpisService.establecerTiendaSeleccionada(null);
    this.sucursalSeleccionada = null;
    this.cargarTodosLosIndicadores();
    this.cdr.detectChanges();
  }

  cambiarPestana(pestana: 'indicadores' | 'inventario' | 'satisfaccion' | 'reportes' | 'sucursales'): void {
    this.pestanaActiva = pestana;
    this.cdr.detectChanges();
  }
  cambiarPestaña(p: 'indicadores' | 'inventario' | 'satisfaccion' | 'reportes' | 'sucursales'): void {
    this.cambiarPestana(p);
  }

  onSeleccionarTiendaDesdeSelect(event: Event): void {
    if (this.alcance !== 'PLATAFORMA') return;
    const select = event.target as HTMLSelectElement;
    const id = Number(select.value);
    if (id === 0 || isNaN(id)) {
      this.deseleccionarTienda();
    } else {
      const encontrada = this.tenants.find(t => t.id_empresa === id);
      if (encontrada) {
        this.seleccionarTienda(encontrada);
      }
    }
  }

  aplicarPreset(preset: 'hoy' | '7dias' | 'mes' | 'historico', dispararCarga: boolean = true) {
    this.presetSeleccionado = preset;
    const ahora = new Date();
    const hoyStr = ahora.toISOString().substring(0, 10);

    if (preset === 'hoy') {
      this.fechaInicio = hoyStr;
      this.fechaFin = hoyStr;
    } else if (preset === '7dias') {
      const hace7 = new Date();
      hace7.setDate(ahora.getDate() - 7);
      this.fechaInicio = hace7.toISOString().substring(0, 10);
      this.fechaFin = hoyStr;
    } else if (preset === 'mes') {
      const primerDia = new Date(ahora.getFullYear(), ahora.getMonth(), 1);
      this.fechaInicio = primerDia.toISOString().substring(0, 10);
      this.fechaFin = hoyStr;
    } else {
      this.fechaInicio = '';
      this.fechaFin = '';
    }

    if (dispararCarga) {
      this.cargarTodosLosIndicadores();
    }
  }

  cargarTodosLosIndicadores(inmediato: boolean = false): void {
    if (inmediato) {
      this.ejecutarCargaIndicadores();
    } else {
      this.recargarTrigger$.next();
    }
  }

  ejecutarCargaIndicadores(): void {
    if (!this.tiendaSeleccionada && this.alcance !== 'PLATAFORMA') {
      return;
    }

    // Cancelar cualquier lote de peticiones KPI anterior que siga en vuelo
    this.cancelPeticionesPrevias$.next();

    this.cargando = true;
    this.mensajeError = '';
    this.cdr.detectChanges();

    const fIni = this.fechaInicio || undefined;
    const fFin = this.fechaFin || undefined;
    const suc = this.sucursalSeleccionada || undefined;
    const idEmpresa = this.tiendaSeleccionada ? this.tiendaSeleccionada.id_empresa : (this.alcance === 'PLATAFORMA' ? undefined : this.usuarioActual?.id_empresa);

    // 1. Resumen de KPIs
    this.kpisService.obtenerResumen(fIni, fFin, suc, idEmpresa)
      .pipe(takeUntil(this.cancelPeticionesPrevias$))
      .subscribe({
        next: (res) => {
          if (res.success) {
            this.kpisResumen = res.data;
          }
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') console.error('Error al cargar resumen KPIs:', err);
        }
      });

    // 2. Línea temporal de ventas (para SVG)
    this.kpisService.obtenerVentasTimeline(fIni, fFin, suc, idEmpresa)
      .pipe(takeUntil(this.cancelPeticionesPrevias$))
      .subscribe({
        next: (res) => {
          if (res.success) {
            this.ventasTimeline = res.data || [];
          }
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') console.error('Error timeline:', err);
        }
      });

    // 3. Ranking de productos más vendidos
    this.kpisService.obtenerProductosMasVendidos(fIni, fFin, suc, 6, idEmpresa)
      .pipe(takeUntil(this.cancelPeticionesPrevias$))
      .subscribe({
        next: (res) => {
          if (res.success) {
            this.productosTop = res.data || [];
          }
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') console.error('Error top productos:', err);
        }
      });

    // 4. Inventario crítico
    this.kpisService.obtenerInventarioAlertas(suc, idEmpresa)
      .pipe(takeUntil(this.cancelPeticionesPrevias$))
      .subscribe({
        next: (res) => {
          if (res.success && res.data) {
            this.alertasInventario = res.data.alertas_stock || [];
          }
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') console.error('Error alertas inventario:', err);
        }
      });

    // 5. Ventas por sucursal
    this.kpisService.obtenerVentasPorSucursal(fIni, fFin, idEmpresa)
      .pipe(takeUntil(this.cancelPeticionesPrevias$))
      .subscribe({
        next: (res) => {
          if (res.success) {
            this.ventasPorSucursal = res.data || [];
          }
          this.finalizarCarga();
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') console.error('Error ventas por sucursal:', err);
          this.finalizarCarga();
        }
      });

    // 6. Ranking de satisfacción por prendas (W32 + CSAT)
    this.kpisService.obtenerRankingSatisfaccion(suc, 5, idEmpresa)
      .pipe(takeUntil(this.cancelPeticionesPrevias$))
      .subscribe({
        next: (res) => {
          if (res.success) {
            this.rankingSatisfaccion = res.data || [];
          }
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') console.error('Error ranking satisfacción:', err);
        }
      });

    // 7. Alertas críticas de calidad (1 estrella o a revisar)
    this.kpisService.obtenerAlertasCalidad(suc, 10, idEmpresa)
      .pipe(takeUntil(this.cancelPeticionesPrevias$))
      .subscribe({
        next: (res) => {
          if (res.success) {
            this.alertasCalidad = res.data || [];
          }
        },
        error: (err) => {
          if (err?.name !== 'EmptyError') console.error('Error alertas calidad:', err);
        }
      });

    // 8. Cargar también resumen de empresa si es nivel alto
    if (this.authService.getAuthorityLevel() <= 3) {
      this.kpisService.obtenerMetricasDashboard(idEmpresa)
        .pipe(takeUntil(this.cancelPeticionesPrevias$))
        .subscribe({
          next: (res) => {
            if (res.success) this.metricasPlataforma = res.data;
          },
          error: (err) => {
            if (err?.name !== 'EmptyError') console.error('Error métricas plataforma:', err);
          }
        });
    }
  }

  private finalizarCarga() {
    this.cargando = false;
    this.cdr.detectChanges();
  }

  // Redirigir al motor de reportes con la tienda ya preseleccionada
  abrirReporteEnMotor(tipoReporte: string): void {
    this.router.navigate(['/admin/reportes'], {
      queryParams: {
        tipo: tipoReporte,
        empresa: this.tiendaSeleccionada?.id_empresa,
        tienda_nombre: this.tiendaSeleccionada?.nombre_empresa
      }
    });
  }

  // ---- CÁLCULOS PARA GRÁFICO SVG RESPONSIVO ----
  get svgPuntosLinea(): string {
    if (!this.ventasTimeline || this.ventasTimeline.length < 2) {
      if (this.ventasTimeline.length === 1) {
        return '40,110 760,110';
      }
      return '';
    }

    const maxVal = Math.max(...this.ventasTimeline.map(v => v.total), 1);
    const ancho = 720;
    const alto = 160;
    const paddingX = 40;
    const paddingY = 30;

    const puntos = this.ventasTimeline.map((item, idx) => {
      const x = paddingX + (idx / (this.ventasTimeline.length - 1)) * ancho;
      const y = paddingY + alto - (item.total / maxVal) * alto;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    return puntos.join(' ');
  }

  get svgAreaPoligono(): string {
    const linea = this.svgPuntosLinea;
    if (!linea) return '';
    return `${linea} 760,200 40,200`;
  }

  getPuntoCoordenadas(item: VentaTimelineItem, idx: number): { x: number; y: number } {
    const count = this.ventasTimeline.length;
    if (count <= 1) return { x: 400, y: 110 };
    const maxVal = Math.max(...this.ventasTimeline.map(v => v.total), 1);
    const ancho = 720;
    const alto = 160;
    const x = 40 + (idx / (count - 1)) * ancho;
    const y = 30 + alto - (item.total / maxVal) * alto;
    return { x, y };
  }

  onHoverPunto(item: VentaTimelineItem, idx: number) {
    const coords = this.getPuntoCoordenadas(item, idx);
    this.puntoHover = item;
    this.posicionHoverX = coords.x;
    this.posicionHoverY = coords.y;
  }

  onLeavePunto() {
    this.puntoHover = null;
  }

  // ---- COMPARATIVAS DE SUCURSAL BARRAS ----
  getMaxIngresoSucursal(): number {
    if (!this.ventasPorSucursal.length) return 1;
    return Math.max(...this.ventasPorSucursal.map(s => s.total_ingresos), 1);
  }

  getAnchoBarraSucursal(ingreso: number): number {
    const max = this.getMaxIngresoSucursal();
    if (max === 0) return 0;
    return Number(((ingreso / max) * 100).toFixed(1));
  }

  cerrarSesion(): void {
    this.authService.cerrarSesion();
  }

  ngOnDestroy(): void {
    this.cancelPeticionesPrevias$.next();
    this.cancelPeticionesPrevias$.complete();
    this.recargarTrigger$.complete();
  }
}