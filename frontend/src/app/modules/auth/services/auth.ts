import { Injectable, inject, PLATFORM_ID, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { isPlatformBrowser } from '@angular/common';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, map, shareReplay, catchError } from 'rxjs';
import { environment } from '../../../../environments/environment';

export interface EmpresaSeleccionada {
  id_empresa: number;
  nombre_empresa: string;
  sucursales?: any[];
}

export interface Usuario {
  id_usuario?: number;
  nro_usuario?: number;
  correo: string;
  nombre_usuario: string;
  nombre: string;
  apellido: string;
  telefono?: string;
  id_rol?: number;
  nombre_rol?: string;
  id_empresa?: number | null;
  nombre_empresa?: string;
  id_sucursal?: number | null;
  nombre_sucursal?: string;
  sucursal_nombre?: string;
  sucursales_detalle?: any[];
  alcance?: 'PLATAFORMA' | 'EMPRESA' | 'SUCURSAL' | 'CLIENTE';
  roles?: string[];
  permisos?: string[];
  sucursales?: number[];
}

export type AuthTab = 'login' | 'register' | 'forgot' | 'verify';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private http = inject(HttpClient);
  private apiUrl = environment.apiUrl || 'http://127.0.0.1:5000';
  private platformId = inject(PLATFORM_ID);
  private router = inject(Router);

  // Signals para reactividad en Angular 17/18
  currentUser = signal<Usuario | null>(this.obtenerUsuarioInicial());
  permissions = signal<string[]>(this.obtenerPermisosIniciales());
  roles = signal<string[]>(this.obtenerRolesIniciales());
  branches = signal<number[]>(this.obtenerSucursalesIniciales());
  
  isAuthModalOpen = signal<boolean>(false);
  authModalTab = signal<AuthTab>('login');
  
  // Estado de verificación de dispositivo pendiente
  pendingDeviceVerification = signal<{
    nro_usuario: number;
    codigo_simulado?: string;
    device_fingerprint?: string;
    nombre_dispositivo?: string;
  } | null>(null);

  // Empresa seleccionada (Multi-tenant)
  selectedCompany = signal<EmpresaSeleccionada | null>(this.obtenerEmpresaInicial());
  private companyChangedSubject = new BehaviorSubject<EmpresaSeleccionada | null>(this.obtenerEmpresaInicial());
  public companyChanged$: Observable<EmpresaSeleccionada | null> = this.companyChangedSubject.asObservable();

  public branchList = [
    { id: 1, nombre: 'Sucursal Central Equipetrol', ciudad: 'Santa Cruz' },
    { id: 2, nombre: 'Sucursal Calacoto Luxury', ciudad: 'La Paz' },
    { id: 3, nombre: 'Sucursal Cochabamba Jardin', ciudad: 'Cochabamba' }
  ];

  private obtenerSucursalActivaInicial(): { id: number; nombre: string; ciudad: string } | null {
    const u = this.obtenerUsuarioInicial();
    if (u) {
      const sucursalesDetalle = (u as any).sucursales_detalle;
      if (Array.isArray(sucursalesDetalle) && sucursalesDetalle.length > 0) {
        const s = sucursalesDetalle[0];
        return {
          id: s.id || s.id_sucursal,
          nombre: s.nombre,
          ciudad: s.ciudad || ''
        };
      }
      if (Array.isArray(u.sucursales) && u.sucursales.length > 0) {
        const branchId = u.sucursales[0];
        const found = this.branchList.find(b => b.id === branchId);
        if (found) return found;
        return {
          id: branchId,
          nombre: u.nombre_sucursal || `Sucursal ${branchId}`,
          ciudad: ''
        };
      }
      if (u.id_sucursal) {
        return {
          id: u.id_sucursal,
          nombre: u.sucursal_nombre || u.nombre_sucursal || `Sucursal ${u.id_sucursal}`,
          ciudad: ''
        };
      }
    }
    if (isPlatformBrowser(this.platformId)) {
      const stored = localStorage.getItem('aurora_selected_branch');
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch {
          // ignore
        }
      }
    }
    return null;
  }

  // Sucursal seleccionada (Multi-tenant)
  activeBranch = signal<{ id: number; nombre: string; ciudad: string } | null>(this.obtenerSucursalActivaInicial());
  private branchChangedSubject = new BehaviorSubject<{ id: number; nombre: string; ciudad: string } | null>(this.obtenerSucursalActivaInicial());
  public branchChanged$: Observable<{ id: number; nombre: string; ciudad: string } | null> = this.branchChangedSubject.asObservable();

  private obtenerUsuarioInicial(): Usuario | null {
    if (isPlatformBrowser(this.platformId)) {
      const u = localStorage.getItem('usuario');
      return u ? JSON.parse(u) : null;
    }
    return null;
  }

  private obtenerEmpresaInicial(): EmpresaSeleccionada | null {
    const u = this.obtenerUsuarioInicial();
    if (u && u.id_empresa && u.id_empresa > 0) {
      return {
        id_empresa: u.id_empresa,
        nombre_empresa: u.nombre_empresa || 'Mi Empresa'
      };
    }
    if (isPlatformBrowser(this.platformId)) {
      const stored = localStorage.getItem('aurora_selected_company');
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch {
          return null;
        }
      }
    }
    return null;
  }

  private obtenerPermisosIniciales(): string[] {
    const u = this.obtenerUsuarioInicial();
    if (u && Array.isArray(u.permisos)) return u.permisos;
    return this.extraerPermisosDeToken();
  }

  private obtenerRolesIniciales(): string[] {
    const u = this.obtenerUsuarioInicial();
    if (u && Array.isArray(u.roles)) return u.roles;
    return [];
  }

  private obtenerSucursalesIniciales(): number[] {
    const u = this.obtenerUsuarioInicial();
    if (u && Array.isArray(u.sucursales)) return u.sucursales;
    return [1];
  }

  private extraerPermisosDeToken(): string[] {
    const token = this.obtenerToken();
    if (!token) return [];
    try {
      const payloadBase64 = token.split('.')[1];
      const payloadDecodificado = JSON.parse(atob(payloadBase64));
      return payloadDecodificado.permisos || [];
    } catch {
      return [];
    }
  }

  // --- MÉTODOS DE AUTORIZACIÓN BASADOS EN PERMISOS ---

  getAuthorityLevel(): number {
    const u = this.obtenerUsuario();
    if (!u) return 7;
    const rol = (u.nombre_rol || '').toUpperCase();
    const roles = (u.roles || []).map(r => r.toUpperCase());
    if ((u.id_rol === 1 || rol === 'ADMINISTRADOR' || roles.includes('ADMINISTRADOR')) && (!u.id_empresa || u.id_empresa === 0)) {
      return 1; // SUPERADMIN
    }
    if (u.id_rol === 1 || rol === 'ADMINISTRADOR' || roles.includes('ADMINISTRADOR')) {
      return 2; // ADMINISTRADOR
    }
    if (u.id_rol === 3 || rol === 'ADMINISTRADOR_TIENDA' || roles.includes('ADMINISTRADOR_TIENDA')) {
      return 3; // ADMINISTRADOR_TIENDA
    }
    if (u.id_rol === 4 || rol === 'ENCARGADO' || rol === 'ENCARGADO_SUCURSAL' || roles.includes('ENCARGADO') || roles.includes('ENCARGADO_SUCURSAL')) {
      return 4; // ENCARGADO
    }
    if (u.id_rol === 5 || rol === 'EMPLEADO' || rol === 'CAJERO' || roles.includes('EMPLEADO') || roles.includes('CAJERO')) {
      return 5; // EMPLEADO
    }
    if (u.id_rol === 2 || rol === 'CLIENTE' || roles.includes('CLIENTE')) {
      return 6; // CLIENTE
    }
    return 7; // PROVEEDOR
  }

  hasPermission(codigo: string): boolean {
    if (!codigo) return true;
    const perms = this.permissions();
    return perms.includes(codigo);
  }

  private permisosCache$: Observable<string[]> | null = null;
  private permisosCacheTimestamp = 0;
  private readonly PERMISOS_CACHE_TTL = 15000; // 15 segundos

  refrescarPermisos(forzar: boolean = false): Observable<string[]> {
    const token = this.obtenerToken();
    const ahora = Date.now();

    if (!forzar && this.permisosCache$ && (ahora - this.permisosCacheTimestamp < this.PERMISOS_CACHE_TTL)) {
      return this.permisosCache$;
    }

    this.permisosCacheTimestamp = ahora;
    this.permisosCache$ = this.http.get<{ permisos: string[] }>(`${this.apiUrl}/api/rbac/mis-permisos`).pipe(
      map(res => {
        if (token !== this.obtenerToken() || !this.currentUser()) {
          throw new Error('La sesión cambió durante la consulta de permisos.');
        }
        const permisos = Array.isArray(res.permisos) ? res.permisos : [];
        this.permissions.set(permisos);
        const usuario = { ...this.currentUser()!, permisos };
        this.currentUser.set(usuario);
        if (isPlatformBrowser(this.platformId)) {
          localStorage.setItem('usuario', JSON.stringify(usuario));
        }
        return permisos;
      }),
      shareReplay({ bufferSize: 1, refCount: false }),
      catchError(err => {
        this.permisosCache$ = null;
        this.permisosCacheTimestamp = 0;
        throw err;
      })
    );

    return this.permisosCache$;
  }

  hasAnyPermission(codigos: string[]): boolean {
    if (!codigos || codigos.length === 0) return true;
    const perms = this.permissions();
    return codigos.some(c => perms.includes(c));
  }

  hasAllPermissions(codigos: string[]): boolean {
    if (!codigos || codigos.length === 0) return true;
    const perms = this.permissions();
    return codigos.every(c => perms.includes(c));
  }

  // --- MÉTODOS DE AUTENTICACIÓN QUE LLAMAN AL BACKEND ---

  registrarCliente(datos: any) {
    return this.http.post<any>(`${this.apiUrl}/api/auth/register`, datos);
  }

  iniciarSesion(credenciales: any) {
    return this.http.post<any>(`${this.apiUrl}/api/auth/login`, credenciales);
  }

  verificarDispositivo(datos: any) {
    return this.http.post<any>(`${this.apiUrl}/api/auth/verify-device`, datos);
  }

  solicitarRecuperacionClave(correo: string) {
    return this.http.post<any>(`${this.apiUrl}/api/auth/forgot-password`, { correo });
  }

  verificarCodigoRecuperacion(correo: string, codigo_recuperacion: string) {
    return this.http.post<any>(`${this.apiUrl}/api/auth/verify-recovery-code`, { correo, codigo_recuperacion });
  }

  restablecerClave(datos: any) {
    return this.http.post<any>(`${this.apiUrl}/api/auth/reset-password`, datos);
  }

  // --- MANEJO DE SESIÓN LOCAL ---

  guardarSesion(token: string, usuario: Usuario) {
    if (isPlatformBrowser(this.platformId)) {
      localStorage.setItem('token', token);
      localStorage.setItem('usuario', JSON.stringify(usuario));
    }
    this.currentUser.set(usuario);
    this.permissions.set(usuario.permisos || []);
    this.roles.set(usuario.roles || []);
    this.branches.set(usuario.sucursales || []);

    if (usuario.id_empresa && usuario.id_empresa > 0) {
      this.setSelectedCompany({
        id_empresa: usuario.id_empresa,
        nombre_empresa: usuario.nombre_empresa || 'Mi Empresa'
      });
    }

    if (usuario.sucursales && usuario.sucursales.length > 0) {
      const branchId = usuario.sucursales[0];
      const detalle = (usuario as any).sucursales_detalle?.find((d: any) => d.id === branchId || d.id_sucursal === branchId);
      if (detalle) {
        this.setBranch({
          id: detalle.id || detalle.id_sucursal,
          nombre: detalle.nombre,
          ciudad: detalle.ciudad || ''
        });
      } else {
        const found = this.branchList.find(b => b.id === branchId);
        if (found) {
          this.setBranch(found);
        } else {
          this.setBranch({
            id: branchId,
            nombre: usuario.nombre_sucursal || `Sucursal ${branchId}`,
            ciudad: ''
          });
        }
      }
    }

    this.closeAuthModal();
  }

  cerrarSesion() {
    if (isPlatformBrowser(this.platformId)) {
      localStorage.removeItem('token');
      localStorage.removeItem('usuario');
      localStorage.removeItem('aurora_selected_company');
      localStorage.removeItem('aurora_selected_branch');
    }
    this.currentUser.set(null);
    this.permissions.set([]);
    this.roles.set([]);
    this.branches.set([]);
    this.selectedCompany.set(null);
    this.companyChangedSubject.next(null);
    this.activeBranch.set(null);
    this.branchChangedSubject.next(null);
    this.permisosCache$ = null;
    this.permisosCacheTimestamp = 0;
    
    // Navegación limpia de SPA a la página pública sin recargar destructivamente el navegador
    this.router.navigate(['/']).then(() => {
      if (isPlatformBrowser(this.platformId)) {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  }

  obtenerToken(): string | null {
    if (isPlatformBrowser(this.platformId)) {
      return localStorage.getItem('token');
    }
    return null;
  }

  obtenerUsuario(): Usuario | null {
    if (this.currentUser()) {
      return this.currentUser();
    }
    if (isPlatformBrowser(this.platformId)) {
      const u = localStorage.getItem('usuario');
      return u ? JSON.parse(u) : null;
    }
    return null;
  }

  obtenerUsuarioActual(): Usuario | null {
    return this.obtenerUsuario();
  }

  estaAutenticado(): boolean {
    return !!this.currentUser() && !this.tokenExpirado();
  }

  tokenExpirado(): boolean {
    const token = this.obtenerToken();
    if (!token) return true;
    try {
      const payloadBase64 = token.split('.')[1];
      const payloadDecodificado = JSON.parse(atob(payloadBase64));
      return Date.now() >= payloadDecodificado.exp * 1000;
    } catch {
      return true;
    }
  }

  esCliente(): boolean {
    const user = this.obtenerUsuario();
    if (!user) return false;
    const rol = (user.nombre_rol || '').toUpperCase();
    const roles = (user.roles || []).map(r => r.toUpperCase());
    if (rol === 'ADMINISTRADOR' || user.id_rol === 1 || roles.includes('ADMINISTRADOR')) return false;
    if (rol === 'ADMINISTRADOR_TIENDA' || user.id_rol === 3 || roles.includes('ADMINISTRADOR_TIENDA')) return false;
    if (rol === 'ENCARGADO' || rol === 'ENCARGADO_SUCURSAL' || user.id_rol === 4 || roles.includes('ENCARGADO') || roles.includes('ENCARGADO_SUCURSAL')) return false;
    if (rol === 'EMPLEADO' || rol === 'CAJERO' || user.id_rol === 5 || roles.includes('CAJERO') || roles.includes('EMPLEADO')) return false;
    return rol === 'CLIENTE' || user.id_rol === 2 || roles.includes('CLIENTE');
  }

  esEmpleadoOAdmin(): boolean {
    const user = this.obtenerUsuario();
    if (!user) return false;
    if (this.esCliente()) return false;
    const rol = (user.nombre_rol || '').toUpperCase();
    const roles = (user.roles || []).map(r => r.toUpperCase());
    if (rol === 'ADMINISTRADOR' || user.id_rol === 1 || roles.includes('ADMINISTRADOR')) return true;
    if (rol === 'ADMINISTRADOR_TIENDA' || user.id_rol === 3 || roles.includes('ADMINISTRADOR_TIENDA')) return true;
    if (rol === 'ENCARGADO' || rol === 'ENCARGADO_SUCURSAL' || user.id_rol === 4 || roles.includes('ENCARGADO')) return true;
    if (rol === 'EMPLEADO' || rol === 'CAJERO' || user.id_rol === 5 || roles.includes('EMPLEADO') || roles.includes('CAJERO')) return true;
    if (this.hasPermission('admin.acceder') || this.hasPermission('ventas.crear')) return true;
    return false;
  }

  obtenerNombreRol(): string {
    const user = this.obtenerUsuario();
    if (!user) return 'INVITADO';
    if (user.nombre_rol) return user.nombre_rol;
    if (user.roles && user.roles.length > 0) return user.roles[0];
    return user.id_rol === 2 ? 'CLIENTE' : (user.id_rol === 5 ? 'CAJERO' : 'PERSONAL');
  }

  // --- MÉTODOS DE DETECCIÓN DE NIVEL DE ACCESO Y ALCANCE (SCOPE) ---

  getScopeLevel(): 'PLATAFORMA' | 'EMPRESA' | 'SUCURSAL' | 'CLIENTE' {
    const user = this.obtenerUsuario();
    if (!user) return 'CLIENTE';

    // 0. Clientes sin rol administrativo o con alcance explícito CLIENTE
    if (user.alcance === 'CLIENTE' || this.esCliente() || user.id_rol === 2) {
      return 'CLIENTE';
    }
    
    const rol = (user.nombre_rol || '').toUpperCase();
    const rolesList = (user.roles || []).map(r => r.toUpperCase());
    const idRol = user.id_rol;

    // 1. Cajero / Empleado operativo SIEMPRE es SUCURSAL
    if (idRol === 5 || rol === 'CAJERO' || rol === 'EMPLEADO' || rolesList.includes('CAJERO') || rolesList.includes('EMPLEADO')) {
      return 'SUCURSAL';
    }

    // 2. Encargado de sucursal SIEMPRE es SUCURSAL
    if (idRol === 4 || rol === 'ENCARGADO' || rol === 'ENCARGADO_SUCURSAL' || rolesList.includes('ENCARGADO') || rolesList.includes('ENCARGADO_SUCURSAL')) {
      return 'SUCURSAL';
    }

    // 3. Superadministrador de plataforma (sin empresa fija asignada)
    if ((idRol === 1 || rol === 'ADMINISTRADOR' || rolesList.includes('ADMINISTRADOR') || rolesList.includes('SUPERADMIN')) && (!user.id_empresa || user.id_empresa === 0)) {
      return 'PLATAFORMA';
    }

    // 4. Si el backend provee claim de alcance explícito:
    if (user.alcance === 'SUCURSAL') {
      return 'SUCURSAL';
    }
    if (user.alcance === 'EMPRESA') {
      return 'EMPRESA';
    }
    if (user.alcance === 'PLATAFORMA' && (!user.id_empresa || user.id_empresa === 0)) {
      return 'PLATAFORMA';
    }

    // 5. Administrador de tienda con empresa asignada
    if (idRol === 3 || rol === 'ADMINISTRADOR_TIENDA' || rolesList.includes('ADMINISTRADOR_TIENDA') || (user.id_empresa && user.id_empresa > 0)) {
      return 'EMPRESA';
    }

    return 'PLATAFORMA';
  }

  isGlobalAdmin(): boolean {
    if (this.esCliente() || this.getScopeLevel() === 'CLIENTE') return false;
    return this.getScopeLevel() === 'PLATAFORMA';
  }

  isStoreAdmin(): boolean {
    const user = this.obtenerUsuario();
    if (!user) return false;
    if (this.isCashier() || this.isBranchManager()) return false;
    const rol = (user.nombre_rol || '').toUpperCase();
    const rolesList = (user.roles || []).map(r => r.toUpperCase());
    return user.id_rol === 3 || rol === 'ADMINISTRADOR_TIENDA' || rolesList.includes('ADMINISTRADOR_TIENDA') ||
           ((user.id_rol === 1 || rol === 'ADMINISTRADOR' || rolesList.includes('ADMINISTRADOR')) && !!user.id_empresa);
  }

  isBranchManager(): boolean {
    const user = this.obtenerUsuario();
    if (!user) return false;
    const rol = (user.nombre_rol || '').toUpperCase();
    const rolesList = (user.roles || []).map(r => r.toUpperCase());
    return user.id_rol === 4 || rol === 'ENCARGADO_SUCURSAL' || rol === 'ENCARGADO' || rolesList.includes('ENCARGADO_SUCURSAL') || rolesList.includes('ENCARGADO');
  }

  isCashier(): boolean {
    const user = this.obtenerUsuario();
    if (!user) return false;
    const rol = (user.nombre_rol || '').toUpperCase();
    const rolesList = (user.roles || []).map(r => r.toUpperCase());
    return user.id_rol === 5 || rol === 'CAJERO' || rol === 'EMPLEADO' || rolesList.includes('CAJERO') || rolesList.includes('EMPLEADO');
  }

  getDefaultRouteForUser(usuario?: Usuario | null): string {
    const u = usuario || this.obtenerUsuario();
    if (!u) return '/';

    const rol = (u.nombre_rol || '').toUpperCase();
    const rolesList = (u.roles || []).map(r => r.toUpperCase());

    // Cliente retail
    if (u.id_rol === 2 || rol === 'CLIENTE' || rolesList.includes('CLIENTE')) {
      return '/';
    }

    // Cajero y operador POS
    if (u.id_rol === 5 || rol === 'CAJERO' || rol === 'EMPLEADO' || rolesList.includes('CAJERO') || rolesList.includes('EMPLEADO')) {
      return '/admin/caja';
    }

    // Encargado de sucursal
    if (u.id_rol === 4 || rol === 'ENCARGADO' || rol === 'ENCARGADO_SUCURSAL' || rolesList.includes('ENCARGADO') || rolesList.includes('ENCARGADO_SUCURSAL')) {
      return '/admin/caja';
    }

    // Administrador (Global o de Tienda)
    if (this.hasPermission('reportes.ver') || u.id_rol === 1 || u.id_rol === 3 || rol === 'ADMINISTRADOR' || rol === 'ADMINISTRADOR_TIENDA') {
      return '/admin/kpis';
    }

    // Operador con permiso de ventas
    if (this.hasPermission('ventas.crear')) {
      return '/admin/caja';
    }

    return '/admin/caja';
  }

  getUserCompanyName(): string {
    const user = this.obtenerUsuario();
    if (user && user.nombre_empresa && user.nombre_empresa.trim().length > 0) {
      return user.nombre_empresa;
    }
    const sel = this.selectedCompany();
    if (sel && sel.nombre_empresa) {
      return sel.nombre_empresa;
    }
    return 'Aurora Store';
  }

  getUserBranchName(): string {
    const user = this.obtenerUsuario();
    if (user && user.nombre_sucursal && user.nombre_sucursal.trim().length > 0) {
      return user.nombre_sucursal;
    }
    if (user && user.sucursal_nombre && user.sucursal_nombre.trim().length > 0) {
      return user.sucursal_nombre;
    }
    const sucursalesDetalle = (user as any)?.sucursales_detalle;
    if (Array.isArray(sucursalesDetalle) && sucursalesDetalle.length > 0 && sucursalesDetalle[0].nombre) {
      return sucursalesDetalle[0].nombre;
    }
    const active = this.activeBranch();
    if (active && active.nombre) return active.nombre;
    return 'Sucursal Principal';
  }

  getUserScopeContext() {
    const scope = this.getScopeLevel();
    const empresa = this.getUserCompanyName();
    const sucursal = this.getUserBranchName();
    const user = this.obtenerUsuario();
    const rol = (user?.nombre_rol || 'Personal').toUpperCase();

    if (scope === 'PLATAFORMA') {
      return {
        scope,
        headerTitle: 'Aurora Store',
        headerSubtitle: 'Plataforma Global',
        sidebarTitle: 'Aurora Store',
        sidebarSubtitle: 'Administración Global',
        badgeText: 'PLATAFORMA',
        badgeClass: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
        canSelectCompany: true,
        canSelectBranch: true,
        isGlobalAdmin: true,
        isStoreAdmin: false,
        isBranchLevel: false
      };
    } else if (scope === 'EMPRESA') {
      return {
        scope,
        headerTitle: 'Aurora Store',
        headerSubtitle: `Empresa: ${empresa}`,
        sidebarTitle: empresa,
        sidebarSubtitle: 'Gestión de Tienda',
        badgeText: 'EMPRESA',
        badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
        canSelectCompany: false, // NO dropdown para cambiar de empresa
        canSelectBranch: true,   // Solo sucursales autorizadas de su empresa
        isGlobalAdmin: false,
        isStoreAdmin: true,
        isBranchLevel: false
      };
    } else if (scope === 'CLIENTE') {
      return {
        scope,
        headerTitle: 'Aurora Store',
        headerSubtitle: 'Tienda Online',
        sidebarTitle: 'Aurora Store',
        sidebarSubtitle: 'Cliente Retail',
        badgeText: 'CLIENTE',
        badgeClass: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
        canSelectCompany: false,
        canSelectBranch: false,
        isGlobalAdmin: false,
        isStoreAdmin: false,
        isBranchLevel: false
      };
    } else {
      // SUCURSAL (Encargado de Sucursal o Cajero)
      const sub = this.isCashier() ? `Caja · ${sucursal}` : `Sucursal: ${sucursal}`;
      return {
        scope,
        headerTitle: 'Aurora Store',
        headerSubtitle: `${empresa} · ${sucursal}`,
        sidebarTitle: sucursal,
        sidebarSubtitle: `${empresa} (${rol})`,
        badgeText: this.isCashier() ? 'CAJA / POS' : 'SUCURSAL',
        badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
        canSelectCompany: false, // NO cambiar empresa
        canSelectBranch: false,  // Fija a su sucursal autorizada
        isGlobalAdmin: false,
        isStoreAdmin: false,
        isBranchLevel: true
      };
    }
  }


  // --- CONTROL DEL MODAL DE AUTENTICACIÓN INTEGRAD0 ---

  openAuthModal(tab: AuthTab = 'login') {
    this.authModalTab.set(tab);
    this.isAuthModalOpen.set(true);
  }

  closeAuthModal() {
    this.isAuthModalOpen.set(false);
  }

  setBranch(branch: { id: number; nombre: string; ciudad?: string } | null) {
    const scope = this.getScopeLevel();
    if (scope === 'SUCURSAL') {
      const fixed = this.obtenerSucursalActivaInicial();
      this.activeBranch.set(fixed);
      this.branchChangedSubject.next(fixed);
      return;
    }

    const payload = branch ? {
      id: branch.id,
      nombre: branch.nombre,
      ciudad: branch.ciudad || ''
    } : null;

    this.activeBranch.set(payload);
    this.branchChangedSubject.next(payload);

    if (isPlatformBrowser(this.platformId)) {
      if (payload) {
        localStorage.setItem('aurora_selected_branch', JSON.stringify(payload));
      } else {
        localStorage.removeItem('aurora_selected_branch');
      }
    }
  }

  setSelectedCompany(empresa: EmpresaSeleccionada | null) {
    const user = this.obtenerUsuario();
    // Roles de tienda quedan anclados a su propia empresa
    if (user && user.id_empresa && user.id_empresa > 0) {
      const fixed: EmpresaSeleccionada = {
        id_empresa: user.id_empresa,
        nombre_empresa: user.nombre_empresa || 'Mi Empresa'
      };
      this.selectedCompany.set(fixed);
      this.companyChangedSubject.next(fixed);
      return;
    }

    this.selectedCompany.set(empresa);
    this.companyChangedSubject.next(empresa);

    if (isPlatformBrowser(this.platformId)) {
      if (empresa) {
        localStorage.setItem('aurora_selected_company', JSON.stringify(empresa));
      } else {
        localStorage.removeItem('aurora_selected_company');
      }
    }

    // Si la empresa provee sucursales, actualizamos la lista y fijamos la primera sucursal
    if (empresa && Array.isArray(empresa.sucursales) && empresa.sucursales.length > 0) {
      this.branchList = empresa.sucursales.map(s => ({
        id: s.id || s.id_sucursal,
        nombre: s.nombre,
        ciudad: s.ciudad || ''
      }));
      this.setBranch(this.branchList[0]);
    } else if (!empresa) {
      this.setBranch(null);
    }
  }

  getEffectiveCompanyId(): number | null {
    const u = this.obtenerUsuario();
    if (u && u.id_empresa && u.id_empresa > 0) {
      return u.id_empresa;
    }
    const sel = this.selectedCompany();
    if (sel && sel.id_empresa) return sel.id_empresa;
    if (typeof localStorage !== 'undefined') {
      try {
        const stored = localStorage.getItem('aurora_selected_company');
        if (stored) {
          const parsed = JSON.parse(stored);
          if (parsed && parsed.id_empresa) return Number(parsed.id_empresa);
        }
      } catch {}
      try {
        const stored = localStorage.getItem('tenant_seleccionado');
        if (stored) {
          const parsed = JSON.parse(stored);
          if (parsed && parsed.id_empresa) return Number(parsed.id_empresa);
        }
      } catch {}
      try {
        const stored = localStorage.getItem('aurora_active_tenant_id');
        if (stored) {
          const id = Number(stored);
          if (id > 0) return id;
        }
      } catch {}
    }
    return null;
  }

  getEffectiveCompanyName(): string {
    const effId = this.getEffectiveCompanyId();
    if (!effId) return 'Todas las Empresas (Global)';
    return this.selectedCompany()?.nombre_empresa || this.getUserCompanyName();
  }
}
