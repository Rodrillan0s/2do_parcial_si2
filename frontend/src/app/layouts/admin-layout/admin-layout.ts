import {
  Component,
  OnInit,
  inject,
  PLATFORM_ID,
  HostListener,
  ChangeDetectorRef,
  NgZone,
  DestroyRef
} from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { Router, RouterOutlet, RouterModule } from '@angular/router';
import { AuthService } from '../../services/auth';
import { ThemeService } from '../../services/theme';
import { NotificacionesService, Notificacion } from '../../services/notificaciones';
import { KpisService, TenantDashboardItem } from '../../services/kpis';
import { SucursalService } from '../../services/sucursales';
import { SaasService, PlanVigenciaData } from '../../services/saas';
import { NetworkStatusService } from '../../core/network/network-status.service';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { distinctUntilChanged } from 'rxjs';

@Component({
  selector: 'app-admin-layout',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterModule],
  templateUrl: './admin-layout.html'
})
export class AdminLayoutComponent implements OnInit {

  private themeService          = inject(ThemeService);
  public authService            = inject(AuthService);
  private notificacionesService  = inject(NotificacionesService);
  private kpisService           = inject(KpisService);
  private sucursalService       = inject(SucursalService);
  private saasService           = inject(SaasService);
  public networkStatus          = inject(NetworkStatusService);
  private router                = inject(Router);
  private platformId            = inject(PLATFORM_ID);
  private cdr                   = inject(ChangeDetectorRef);
  private ngZone                = inject(NgZone);
  private destroyRef            = inject(DestroyRef);

  // ---- Estado general ----
  usuarioActual: any      = null;
  modoOscuro: boolean     = true;
  sidebarAbierto: boolean   = false;
  sidebarColapsado: boolean = false;

  // ---- Estado notificaciones ----
  mostrarNotificaciones: boolean = false;
  listaNotificaciones: Notificacion[] = [];
  cantidadNoLeidas: number = 0;

  // ---- Estado Multi-Tenant y Sucursales ----
  tenants: TenantDashboardItem[] = [];
  tiendaActiva: TenantDashboardItem | null = null;
  mostrarTenantDropdown: boolean = false;
  mostrarSucursalDropdown: boolean = false;
  cargandoTenants: boolean = false;
  sucursalesDeEmpresa: Array<{ id: number; nombre: string; ciudad?: string }> = [];

  sucursalActiva: { id: number; nombre: string; ciudad?: string } | null = null;
  planVigencia: PlanVigenciaData | null = null;

  // ---- Definición dinámica del menú por Permisos y Alcance ----
  menuFiltrado: any[] = [];

  get scopeContext() {
    return this.authService.getUserScopeContext();
  }

  get sucursalesDisponibles(): Array<{ id: number; nombre: string; ciudad?: string }> {
    const scope = this.authService.getScopeLevel();
    if (scope === 'SUCURSAL') {
      const act = this.authService.activeBranch();
      return act ? [act] : [];
    }
    if (this.sucursalesDeEmpresa.length > 0) {
      return this.sucursalesDeEmpresa;
    }
    if (scope === 'PLATAFORMA') {
      if (this.tiendaActiva && this.tiendaActiva.sucursales && this.tiendaActiva.sucursales.length > 0) {
        return this.tiendaActiva.sucursales;
      }
    } else if (scope === 'EMPRESA') {
      const miEmpresa = this.tenants.find(t => t.id_empresa === this.usuarioActual?.id_empresa);
      if (miEmpresa && miEmpresa.sucursales && miEmpresa.sucursales.length > 0) {
        return miEmpresa.sucursales;
      }
    }
    const act = this.authService.activeBranch();
    return act ? [act] : [];
  }

  cargandoContexto: boolean = false;

  cargarSucursalesHeader(autoSelectFirst: boolean = false) {
    const scope = this.authService.getScopeLevel();
    if (scope === 'SUCURSAL') {
      const br = this.authService.activeBranch();
      this.sucursalesDeEmpresa = br ? [br] : [];
      this.sucursalActiva = br;
      return;
    }

    // 1. Comprobar si la tienda activa ya tiene sus sucursales en memoria
    if (this.tiendaActiva && Array.isArray(this.tiendaActiva.sucursales) && this.tiendaActiva.sucursales.length > 0) {
      this.sucursalesDeEmpresa = this.tiendaActiva.sucursales.map((s: any) => ({
        id: s.id || s.id_sucursal,
        nombre: s.nombre,
        ciudad: s.ciudad || ''
      }));
      const act = this.authService.activeBranch();
      if (autoSelectFirst || !act || !this.sucursalesDeEmpresa.some(s => s.id === act.id)) {
        this.seleccionarSucursal(this.sucursalesDeEmpresa[0], true);
      } else {
        this.sucursalActiva = act;
      }
      this.cdr.detectChanges();
      return;
    }

    const empId = scope === 'EMPRESA' 
      ? (this.usuarioActual?.id_empresa || undefined) 
      : (this.tiendaActiva?.id_empresa || this.authService.selectedCompany()?.id_empresa || undefined);

    this.sucursalService.listarSucursales(empId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          if (res && res.data) {
            this.sucursalesDeEmpresa = res.data
              .filter((s: any) => s.activo !== false)
              .map((s: any) => ({
                id: s.id_sucursal,
                nombre: s.nombre,
                ciudad: s.ciudad || ''
              }));

            const act = this.authService.activeBranch();
            if (autoSelectFirst && this.sucursalesDeEmpresa.length > 0) {
              this.seleccionarSucursal(this.sucursalesDeEmpresa[0], true);
            } else if (this.sucursalesDeEmpresa.length > 0 && act && this.sucursalesDeEmpresa.some(s => s.id === act.id)) {
              this.sucursalActiva = this.sucursalesDeEmpresa.find(s => s.id === act.id) || null;
            } else if (this.sucursalesDeEmpresa.length > 0 && (scope === 'EMPRESA' || this.tiendaActiva)) {
              this.seleccionarSucursal(this.sucursalesDeEmpresa[0], true);
            } else if (this.sucursalesDeEmpresa.length === 0) {
              this.seleccionarSucursal(null, true);
            }
            this.cdr.detectChanges();
          }
        },
        error: (err) => console.warn('Error cargando sucursales para header:', err)
      });
  }

  cargarPlanHeader() {
    if (!this.authService.hasPermission('suscripciones.ver')) {
      this.planVigencia = null;
      return;
    }
    const scope = this.authService.getScopeLevel();
    if (scope === 'CLIENTE') {
      this.planVigencia = null;
      return;
    }

    const empId = scope === 'EMPRESA' 
      ? (this.usuarioActual?.id_empresa || undefined) 
      : (this.tiendaActiva?.id_empresa || this.authService.selectedCompany()?.id_empresa || undefined);

    if (scope === 'PLATAFORMA' && !empId) {
      this.planVigencia = null;
      return;
    }

    // Evitar consultar si ya se tiene cargado el plan de esta misma empresa o si estamos sin conexión
    if (!this.networkStatus.isOnline() || (this.planVigencia && this.planVigencia.id_empresa === empId)) {
      return;
    }

    this.saasService.consultarPlan(empId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          if (res && res.data) {
            this.planVigencia = res.data;
            this.cdr.detectChanges();
          }
        },
        error: () => {
          this.planVigencia = null;
          this.cdr.detectChanges();
        }
      });
  }

  // ------------------------------------------------------------------
  // LIFECYCLE
  // ------------------------------------------------------------------

  ngOnInit() {
    if (!isPlatformBrowser(this.platformId)) return;

    this.usuarioActual = this.authService.obtenerUsuario();

    if (!this.usuarioActual) {
      this.cerrarSesion();
      return;
    }

    // Si el usuario aterriza directamente en '/admin' o '/admin/', redirigir a su panel por defecto
    const currentUrl = this.router.url.split('?')[0];
    if (currentUrl === '/admin' || currentUrl === '/admin/') {
      const target = this.authService.getDefaultRouteForUser(this.usuarioActual);
      if (target !== '/admin') {
        this.router.navigateByUrl(target);
      }
    }

    this.sucursalActiva = this.authService.activeBranch();
    this.cargarSucursalesHeader();
    this.cargarPlanHeader();
    this.construirMenuPorPermisosYAlcance();

    // Sincronizar tema con el servicio global reactivo
    this.themeService.modoOscuro$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((esOscuro) => {
        this.modoOscuro = esOscuro;
        this.cdr.detectChanges();
      });

    this.verificarResolucion();

    // Iniciar WS + cargar historial desde BD solo si hay conexión online
    if (this.networkStatus.isOnline()) {
      this.notificacionesService.conectar();
    }

    // Al reconectar internet, restablecer WebSocket y refrescar estado del header
    this.networkStatus.reconnected$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((timestamp) => {
        if (timestamp > 0 && this.networkStatus.isOnline()) {
          this.notificacionesService.conectar();
          this.cargarTenantsGlobales();
          this.cargarPlanHeader();
        }
      });

    // Suscribirse al stream reactivo (mezcla BD + WS en tiempo real)
    this.notificacionesService.notificaciones$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((notis) => {
        this.ngZone.run(() => {
          this.listaNotificaciones = notis;
          this.cantidadNoLeidas   = notis.filter(n => !n.leida).length;
          this.cdr.detectChanges();
        });
      });

    // Suscribirse al tenant activo global
    this.kpisService.tiendaSeleccionada$
      .pipe(
        distinctUntilChanged((prev, curr) => prev?.id_empresa === curr?.id_empresa),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe((t) => {
        if (this.tiendaActiva?.id_empresa !== t?.id_empresa) {
          this.tiendaActiva = t;
          this.cargarPlanHeader();
          this.cdr.detectChanges();
        }
      });

    // Suscribirse a cambios en sucursal activa para sincronizar header
    this.authService.branchChanged$
      .pipe(
        distinctUntilChanged((prev, curr) => prev?.id === curr?.id),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe((branch) => {
        this.sucursalActiva = branch;
        this.cdr.detectChanges();
      });

    // Suscribirse a cambios de empresa para recargar las sucursales de dicha empresa
    this.authService.companyChanged$
      .pipe(
        distinctUntilChanged((prev, curr) => prev?.id_empresa === curr?.id_empresa),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe((emp) => {
        if (this.scopeContext.canSelectCompany) {
          const actualId = this.tiendaActiva?.id_empresa;
          if (emp) {
            const match = this.tenants.find(t => t.id_empresa === emp.id_empresa);
            if (match && match.id_empresa !== actualId) {
              this.tiendaActiva = match;
              this.cargarSucursalesHeader(true);
              this.cargarPlanHeader();
            }
          } else if (this.tiendaActiva !== null) {
            this.tiendaActiva = null;
            this.cargarSucursalesHeader(true);
            this.cargarPlanHeader();
          }
        }
      });

    this.cargarTenantsGlobales();
  }

  cargarTenantsGlobales() {
    const scope = this.authService.getScopeLevel();

    // Si estamos sin conexión con el backend, usar datos locales sin generar peticiones fallidas
    if (!this.networkStatus.isOnline()) {
      this.cargandoTenants = false;
      const idEmp = this.usuarioActual?.id_empresa;
      const nomEmp = this.authService.getUserCompanyName();
      if (idEmp && !this.tiendaActiva) {
        this.tiendaActiva = {
          id_empresa: idEmp,
          nombre_empresa: nomEmp,
          razon_social: nomEmp,
          nit: '',
          ciudad: '',
          direccion: '',
          telefono: '',
          correo: '',
          logo: '',
          estado: 'ACTIVO',
          total_sucursales: 1,
          total_productos: 0,
          total_stock_disponible: 0,
          total_ventas_cantidad: 0,
          total_ingresos_historico: 0,
          sucursales: [{
            id: this.authService.activeBranch()?.id || 1,
            nombre: this.authService.activeBranch()?.nombre || 'Sucursal Principal',
            ciudad: this.authService.activeBranch()?.ciudad || '',
            direccion: ''
          }]
        };
      }
      this.cdr.detectChanges();
      return;
    }

    // Para Cajeros y usuarios de nivel sucursal/operativo, no consultar /api/kpis/tenants (evita 403)
    if (scope !== 'PLATAFORMA' && !this.authService.isStoreAdmin()) {
      this.cargandoTenants = false;
      const idEmp = this.usuarioActual?.id_empresa;
      const nomEmp = this.authService.getUserCompanyName();
      if (idEmp) {
        this.tiendaActiva = {
          id_empresa: idEmp,
          nombre_empresa: nomEmp,
          razon_social: nomEmp,
          nit: '',
          ciudad: '',
          direccion: '',
          telefono: '',
          correo: '',
          logo: '',
          estado: 'ACTIVO',
          total_sucursales: 1,
          total_productos: 0,
          total_stock_disponible: 0,
          total_ventas_cantidad: 0,
          total_ingresos_historico: 0,
          sucursales: [{
            id: this.authService.activeBranch()?.id || 1,
            nombre: this.authService.activeBranch()?.nombre || 'Sucursal Principal',
            ciudad: this.authService.activeBranch()?.ciudad || '',
            direccion: ''
          }]
        };
      }
      this.cdr.detectChanges();
      return;
    }

    this.cargandoTenants = true;
    this.kpisService.obtenerTenants().subscribe({
      next: (res) => {
        this.cargandoTenants = false;
        if (res.success && res.data) {
          this.tenants = res.data;

          if (scope === 'PLATAFORMA') {
            const actual = this.authService.selectedCompany() || this.kpisService.obtenerTiendaActual();
            if (actual && this.tenants.length > 0) {
              const match = this.tenants.find(t => t.id_empresa === actual.id_empresa);
              if (match) {
                this.tiendaActiva = match;
                // Emitir solo si no coincide para prevenir bucles de eventos reactivos
                if (this.authService.selectedCompany()?.id_empresa !== match.id_empresa) {
                  this.authService.setSelectedCompany({
                    id_empresa: match.id_empresa,
                    nombre_empresa: match.nombre_empresa,
                    sucursales: match.sucursales
                  });
                }
                if (this.kpisService.obtenerTiendaActual()?.id_empresa !== match.id_empresa) {
                  this.kpisService.establecerTiendaSeleccionada(match);
                }
              }
            }
          } else {
            // EMPRESA: fijar su empresa
            const idEmp = this.usuarioActual?.id_empresa;
            if (idEmp) {
              const miTienda = this.tenants.find(t => t.id_empresa === idEmp);
              if (miTienda) {
                this.tiendaActiva = miTienda;
                if (this.kpisService.obtenerTiendaActual()?.id_empresa !== miTienda.id_empresa) {
                  this.kpisService.establecerTiendaSeleccionada(miTienda);
                }
              }
            }
          }
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.cargandoTenants = false;
        console.error('Error cargando tenants:', err);
        this.cdr.detectChanges();
      }
    });
  }

  toggleTenantDropdown() {
    if (!this.scopeContext.canSelectCompany) return;
    this.mostrarTenantDropdown = !this.mostrarTenantDropdown;
    if (this.mostrarTenantDropdown) {
      this.mostrarNotificaciones = false;
      this.mostrarSucursalDropdown = false;
    }
  }

  seleccionarTiendaGlobal(tienda: TenantDashboardItem | null) {
    if (!this.scopeContext.canSelectCompany) return;
    this.cargandoContexto = true;
    this.tiendaActiva = tienda;
    this.mostrarTenantDropdown = false;
    this.sucursalActiva = null;

    this.authService.setSelectedCompany(tienda ? {
      id_empresa: tienda.id_empresa,
      nombre_empresa: tienda.nombre_empresa,
      sucursales: tienda.sucursales
    } : null);
    this.kpisService.establecerTiendaSeleccionada(tienda);

    this.cargarSucursalesHeader(true);
    this.cargarPlanHeader();
    setTimeout(() => {
      this.cargandoContexto = false;
      this.cdr.detectChanges();
    }, 250);
    this.cdr.detectChanges();
  }

  toggleSucursalDropdown() {
    if (!this.scopeContext.canSelectBranch) return;
    this.mostrarSucursalDropdown = !this.mostrarSucursalDropdown;
    if (this.mostrarSucursalDropdown) {
      this.mostrarNotificaciones = false;
      this.mostrarTenantDropdown = false;
    }
  }

  seleccionarSucursal(suc: { id: number; nombre: string; ciudad?: string } | null, force: boolean = false) {
    if (!force && !this.scopeContext.canSelectBranch && this.scopeContext.scope === 'SUCURSAL') return;
    this.sucursalActiva = suc;
    if (suc) {
      this.authService.setBranch({
        id: suc.id,
        nombre: suc.nombre,
        ciudad: suc.ciudad || ''
      });
    } else {
      this.authService.setBranch(null);
    }
    this.mostrarSucursalDropdown = false;
    this.cdr.detectChanges();
  }

  // ------------------------------------------------------------------
  // DEFINICIÓN DECLARATIVA Y FILTRADO DINÁMICO DEL MENÚ (RBAC & ALCANCE)
  // ------------------------------------------------------------------

  construirMenuPorPermisosYAlcance() {
    const scope = this.authService.getScopeLevel();
    const empresaNombre = this.authService.getUserCompanyName();
    const sucursalNombre = this.authService.getUserBranchName();

    // Catálogo maestro de opciones del sistema Aurora Store
    const menuMaster = [
{
  titulo: 'VENTAS & POS',
  icono: 'M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z',
  expandido: true,
  submenus: [
    { nombre: 'Punto de Venta / Caja', ruta: '/admin/caja', permiso: 'ventas.crear' },
    { nombre: 'Cajas de Tienda y Sucursales', ruta: '/admin/cajas-monitoreo', maxAuthorityLevel: 4 },
    { nombre: 'Atender Reservas', ruta: '/admin/atender-reserva', permiso: 'ventas.ver' },
    { nombre: 'Devoluciones & Garantías', ruta: '/admin/devoluciones', permiso: 'devoluciones.ver' }
  ]
},
      {
        titulo: 'CATÁLOGO',
        icono: 'M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z',
        expandido: true,
        submenus: [
          { nombre: 'Categorías', ruta: '/admin/categorias', permiso: 'categorias.ver' },
          { nombre: 'Tallas y Colores', ruta: '/admin/tallas-colores', permiso: 'tallas.ver' },
          { nombre: 'Productos & Prendas', ruta: '/admin/productos', permiso: 'productos.ver' }
        ]
      },
      {
        titulo: 'INVENTARIO',
        icono: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4',
        expandido: true,
        submenus: [
          { nombre: 'Gestión de Inventario', ruta: '/admin/inventario', permiso: 'inventario.ver' }
        ]
      },
      {
        titulo: scope === 'PLATAFORMA' ? 'EMPRESAS' : 'SUCURSALES',
        icono: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
        expandido: true,
        submenus: [
          { 
            nombre: 'Cadena de Tiendas (Tenants)', 
            ruta: '/admin/empresas', 
            permiso: 'empresas.ver', 
            alcances: ['PLATAFORMA'] 
          },
          { 
            nombre: scope === 'PLATAFORMA' ? 'Sucursales y Ciudades' : 'Sucursales de la Empresa', 
            ruta: '/admin/sucursales', 
            permiso: 'sucursales.ver' 
          }
        ]
      },
      {
        titulo: 'SAAS & PLANES',
        icono: 'M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z',
        expandido: true,
        submenus: [
          { nombre: 'Mi Tienda & Storefront', ruta: '/admin/mi-tienda', maxAuthorityLevel: 3 },
          { nombre: 'Planes y Contrataciones', ruta: '/admin/planes', permiso: 'planes.ver' },
          { nombre: 'Suscripciones y Límites', ruta: '/admin/suscripciones', permiso: 'suscripciones.ver' }
        ]
      },
      {
        titulo: scope === 'PLATAFORMA' ? 'SEGURIDAD' : 'EQUIPO',
        icono: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
        expandido: true,
        submenus: [
          { 
            nombre: scope === 'PLATAFORMA' ? 'Usuarios y Permisos' : `Equipo de ${empresaNombre}`, 
            ruta: '/admin/usuarios', 
            permiso: 'usuarios.ver' 
          },
          { 
            nombre: 'Bitácora del Sistema', 
            ruta: '/admin/bitacora', 
            permiso: 'bitacora.ver' 
          },
          { 
            nombre: 'Copias de Respaldo & Nube', 
            ruta: '/admin/backup', 
            permiso: 'admin.acceder', 
            alcances: ['PLATAFORMA', 'EMPRESA'] 
          }
        ]
      },
      {
        titulo: 'ANALÍTICA',
        icono: 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z',
        expandido: true,
        submenus: [
          { 
            nombre: scope === 'PLATAFORMA' ? 'Dashboard de KPIs Globales' : (scope === 'EMPRESA' ? 'Dashboard KPIs Empresa' : 'Métricas de Sucursal'), 
            ruta: '/admin/kpis', 
            permiso: 'reportes.ver' 
          },
          { nombre: 'Generador de Reportes', ruta: '/admin/reportes', permiso: 'reportes.ver' },
          { nombre: 'Predicciones IA & Demanda', ruta: '/admin/predicciones', permiso: 'reportes.ver' },
          { nombre: 'Inteligencia de Ventas (BI)', ruta: '/admin/bi_dashboard', permiso: 'reportes.ver' }
        ]
      }
    ];

    // Filtrar opciones según permisos y alcances del usuario actual
    this.menuFiltrado = menuMaster
      .map(modulo => {
        const submenusAutorizados = modulo.submenus.filter((sub: any) => {
          // Filtro por nivel de autoridad máxima (1: Superadmin, 2: Admin, 3: Admin Tienda, 4: Encargado Sucursal)
          if (sub.maxAuthorityLevel !== undefined && this.authService.getAuthorityLevel() > sub.maxAuthorityLevel) {
            return false;
          }
          // Filtro por alcance permitido si se especificó
          if (sub.alcances && !sub.alcances.includes(scope as any)) {
            return false;
          }
          // Filtro por permiso granular
          if (sub.permiso && !this.authService.hasPermission(sub.permiso)) {
            return false;
          }
          return true;
        });

        return {
          ...modulo,
          submenus: submenusAutorizados
        };
      })
      .filter(modulo => modulo.submenus.length > 0);
    this.cdr.detectChanges();
  }

  // ------------------------------------------------------------------
  // HOST LISTENERS
  // ------------------------------------------------------------------

  @HostListener('window:resize')
  onResize() {
    if (isPlatformBrowser(this.platformId)) {
      this.verificarResolucion();
    }
  }

  /**
   * Cierra el panel de notificaciones si el usuario hace clic
   * fuera del área marcada con [data-notif-panel].
   */
  @HostListener('document:click', ['$event'])
  onClickFuera(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (this.mostrarNotificaciones && !target.closest('[data-notif-panel]')) {
      this.mostrarNotificaciones = false;
      this.cdr.detectChanges();
    }
    if (this.mostrarTenantDropdown && !target.closest('[data-tenant-panel]')) {
      this.mostrarTenantDropdown = false;
      this.cdr.detectChanges();
    }
    if (this.mostrarSucursalDropdown && !target.closest('[data-branch-panel]')) {
      this.mostrarSucursalDropdown = false;
      this.cdr.detectChanges();
    }
  }

  // ------------------------------------------------------------------
  // SIDEBAR
  // ------------------------------------------------------------------

  verificarResolucion() {
    const isDesktop = window.innerWidth >= 768;
    if (isDesktop && this.sidebarAbierto) {
      this.sidebarAbierto = false;
      this.cdr.detectChanges();
    }
  }

  toggleSidebar() {
    if (!isPlatformBrowser(this.platformId)) return;

    if (window.innerWidth < 768) {
      this.sidebarAbierto = !this.sidebarAbierto;
    } else {
      this.sidebarColapsado = !this.sidebarColapsado;
      if (this.sidebarColapsado) {
        this.menuFiltrado.forEach(m => m.expandido = false);
      }
    }
    this.cdr.detectChanges();
  }

  toggleAcordeon(modulo: any) {
    if (this.sidebarColapsado && window.innerWidth >= 768) {
      this.sidebarColapsado = false;
    }
    modulo.expandido = !modulo.expandido;
    this.cdr.detectChanges();
  }

  cerrarSidebarMobile() {
    this.sidebarAbierto = false;
    this.cdr.detectChanges();
  }

  // ------------------------------------------------------------------
  // TEMA
  // ------------------------------------------------------------------

  alternarModoOscuro() {
    this.themeService.alternarTema();
  }

  // ------------------------------------------------------------------
  // NOTIFICACIONES
  // ------------------------------------------------------------------

  /**
   * Abre o cierra el panel.
   * Al abrir: marca todas como leídas en BD (PUT /leer marcar_todo=true)
   * y resetea el contador visual.
   */
  toggleNotificaciones() {
    this.mostrarNotificaciones = !this.mostrarNotificaciones;

    if (this.mostrarNotificaciones && this.cantidadNoLeidas > 0) {
      this.notificacionesService.marcarComoLeidas();
      this.cantidadNoLeidas = 0;
      this.cdr.detectChanges();
    }
  }

  /**
   * Botón "Marcar todas como leídas" dentro del panel.
   * Sincroniza con PUT /api/ws/leer { marcar_todo: true }
   */
  marcarTodasLeidas() {
    this.notificacionesService.marcarComoLeidas();
    this.cantidadNoLeidas = 0;
    this.cdr.detectChanges();
  }

  /**
   * Clic en una notificación individual.
   * Sincroniza con PUT /api/ws/leer { id_notificacion: N }
   * Solo actúa si viene de BD (tiene id_notificacion).
   */
  leerNotificacion(noti: Notificacion) {
    if (!noti.leida && noti.id_notificacion) {
      this.notificacionesService.marcarUnaComoLeida(noti.id_notificacion);
    }
  }

  /** Navega a la pantalla completa y cierra el panel. */
  irANotificaciones() {
    this.mostrarNotificaciones = false;
    this.router.navigate(['/notificaciones']);
  }

  // ------------------------------------------------------------------
  // HELPERS DE ICONOS (dinámicos según tipo_referencia del backend)
  // ------------------------------------------------------------------

  /**
   * Tipos reales del backend:
   *   NUEVA_EMERGENCIA | NUEVA_OFERTA | RESPUESTA_OFERTA
   */
  getIconoClase(tipo: string): string {
    const clases: Record<string, string> = {
      'NUEVA_EMERGENCIA': 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30',
      'NUEVA_OFERTA':     'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border-amber-100 dark:border-amber-800/30',
      'RESPUESTA_OFERTA': 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 border-green-100 dark:border-green-800/30',
      // Genéricos de compatibilidad
      'EMERGENCIA': 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30',
      'ALERTA':     'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border-amber-100 dark:border-amber-800/30',
      'INFO':       'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 border-blue-100 dark:border-blue-800/30',
      'EXITO':      'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 border-green-100 dark:border-green-800/30',
    };
    return clases[tipo] ?? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 border-blue-100 dark:border-blue-800/30';
  }

  getIconoPath(tipo: string): string {
    const iconos: Record<string, string> = {
      'NUEVA_EMERGENCIA': 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
      'NUEVA_OFERTA':     'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
      'RESPUESTA_OFERTA': 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
      // Genéricos de compatibilidad
      'EMERGENCIA': 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
      'ALERTA':     'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
      'INFO':       'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
      'EXITO':      'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
    };
    return iconos[tipo] ?? 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z';
  }

  // ------------------------------------------------------------------
  // SESIÓN
  // ------------------------------------------------------------------

  esModuloSoloOnline(): boolean {
    const url = this.router.url;
    const rutasOnlineOnly = [
      '/admin/usuarios',
      '/admin/empresas',
      '/admin/planes',
      '/admin/backup',
      '/admin/bitacora',
      '/admin/suscripciones',
      '/admin/sucursales',
      '/admin/proveedores',
      '/admin/bi'
    ];
    return rutasOnlineOnly.some(r => url.startsWith(r));
  }

  cerrarSesion() {
    this.notificacionesService.desconectar();
    this.authService.cerrarSesion();
    window.location.href = '/';
  }
}