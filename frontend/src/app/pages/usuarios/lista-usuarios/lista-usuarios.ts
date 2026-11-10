import { Component, OnInit, inject, ChangeDetectorRef, NgZone, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../../services/auth';
import { RbacService, Permiso, Rol } from '../../../services/rbac';
import { SucursalService, Sucursal } from '../../../services/sucursales';
import { EmpresaService } from '../../../services/empresa';
import { extraerMensajeError } from '../../../utils/error-helper';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

export interface Empresa {
  id_empresa: number;
  nombre_empresa: string;
  nit?: string | null;
  estado: string;
}

export interface Usuario {
  nro_usuario?: number;
  id_usuario?: number;
  ci?: string;
  nombre_usuario: string;
  username?: string;
  estado: string;
  id_empresa?: number | null;
  nombre_empresa?: string; 
  nombre_completo: string;
  nombre?: string;
  apellido?: string;
  correo: string;
  telefono: string;
  direccion?: string;
  ciudad?: string;
  fecha_registro?: string;
  nombre_rol?: string; 
  nro_rol: number;
  id_rol?: number;
  password?: string;
  permisos_directos_count?: number;
  ids_sucursales?: number[];
  id_sucursal?: number | null;
  sucursal_nombre?: string;
  sucursales_nombres?: string;
}

export interface ModuloPermisos {
  modulo: string;
  permisos: Permiso[];
}

@Component({
  selector: 'app-lista-usuarios',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './lista-usuarios.html'
})
export class ListaUsuariosComponent implements OnInit {
  
  private http = inject(HttpClient);
  private cdr = inject(ChangeDetectorRef);
  public authService = inject(AuthService);
  private rbacService = inject(RbacService);
  private sucursalService = inject(SucursalService);
  private empresaService = inject(EmpresaService);
  private ngZone = inject(NgZone);
  private apiUrl = environment.apiUrl;
  private destroyRef = inject(DestroyRef);
  private busquedaSubject = new Subject<string>();

  // --- VARIABLES DE DATOS ---
  usuarios: Usuario[] = [];
  usuariosFiltrados: Usuario[] = [];
  empresas: Empresa[] = []; 
  rolesDisponibles: Rol[] = [];
  sucursalesDisponibles: Sucursal[] = [];
  cargandoSucursales: boolean = false;
  
  // --- FILTROS ---
  filtroEmpresa: string = 'TODOS';
  filtroEstado: string = 'TODOS';
  filtroRol: string = 'TODOS';
  filtroTexto: string = '';

  cargando: boolean = false;
  guardando: boolean = false;
  mensajeError: string = '';
  mensajeModalError: string = '';
  mensajeExito: string = '';

  // --- MODAL USUARIO (CREAR / EDITAR) ---
  mostrarModal: boolean = false;
  modoEdicion: boolean = false;
  usuarioForm: Usuario = this.inicializarUsuario();

  // --- MODAL DETALLE DE USUARIO ---
  mostrarModalDetalle: boolean = false;
  cargandoDetallePermisos: boolean = false;
  usuarioSeleccionadoDetalle: Usuario | null = null;
  permisosDirectosDetalle: Permiso[] = [];
  permisosHeredadosDetalle: Permiso[] = [];
  permisosEfectivosDetalle: string[] = [];

  // --- MODAL ASIGNACIÓN DE PERMISOS DIRECTOS ---
  mostrarModalPermisos: boolean = false;
  cargandoPermisos: boolean = false;
  usuarioSeleccionadoPermisos: Usuario | null = null;
  modulosPermisos: ModuloPermisos[] = [];
  idsPermisosDirectosSeleccionados = new Set<number>();
  codigosPermisosHeredados = new Set<string>();
  codigosPermisosDelegables = new Set<string>();

  // --- MODAL ASIGNACIÓN DE SUCURSALES AUTORIZADAS ---
  mostrarModalSucursales: boolean = false;
  cargandoSucursalesModal: boolean = false;
  usuarioSeleccionadoSucursales: Usuario | null = null;
  idsSucursalesSeleccionadas = new Set<number>();
  sucursalesModalDisponibles: Sucursal[] = [];
  mensajeModalSucursalesError: string = '';

  // --- MÉTRICAS ---
  totalUsuarios: number = 0;
  usuariosActivos: number = 0;
  usuariosInactivos: number = 0;

  get isGlobalAdmin(): boolean {
    return this.authService.getAuthorityLevel() <= 2;
  }

  get isStoreAdmin(): boolean {
    return this.authService.getAuthorityLevel() === 3;
  }

  get idEmpresaSesion(): number | null {
    const u = this.authService.obtenerUsuario();
    return u?.id_empresa || null;
  }

  inicializarUsuario(): Usuario {
    const defaultEmpresaId = (!this.isGlobalAdmin && this.idEmpresaSesion) ? this.idEmpresaSesion : null;
    return {
      nombre_usuario: '',
      nombre_completo: '',
      correo: '',
      telefono: '',
      direccion: '',
      estado: 'ACTIVO',
      nro_rol: this.isStoreAdmin ? 4 : 3,
      id_empresa: defaultEmpresaId,
      id_sucursal: null,
      ids_sucursales: []
    };
  }

  cargarSucursalesParaUsuario(idEmpresa?: number) {
    this.cargandoSucursales = true;
    const targetEmpresa = idEmpresa || (!this.isGlobalAdmin ? (this.idEmpresaSesion || undefined) : undefined);
    this.sucursalService.listarSucursales(targetEmpresa)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.cargandoSucursales = false;
            if (res && res.data) {
              this.sucursalesDisponibles = res.data.filter(s => s.activo !== false);
            } else {
              this.sucursalesDisponibles = [];
            }
            this.cdr.detectChanges();
          });
        },
        error: () => {
          this.ngZone.run(() => {
            this.cargandoSucursales = false;
            this.sucursalesDisponibles = [];
            this.cdr.detectChanges();
          });
        }
      });
  }

  requiereSucursal(): boolean {
    const rolId = Number(this.usuarioForm.nro_rol || this.usuarioForm.id_rol);
    if (rolId === 4 || rolId === 5) return true;
    const rolObj = this.rolesDisponibles.find(r => r.id_rol === rolId);
    if (rolObj) {
      const name = (rolObj.nombre || '').toUpperCase();
      if (name.includes('CAJER') || name.includes('ENCARGAD') || name.includes('SUCURSAL') || name.includes('EMPLEAD')) {
        return true;
      }
    }
    return false;
  }

  puedeTenerSucursal(): boolean {
    return this.requiereSucursal() || !!this.usuarioForm.id_empresa;
  }

  onEmpresaFormChange() {
    this.usuarioForm.id_sucursal = null;
    const empId = this.usuarioForm.id_empresa ? Number(this.usuarioForm.id_empresa) : undefined;
    this.cargarSucursalesParaUsuario(empId);
  }

  onRolFormChange() {
    if (!this.puedeTenerSucursal()) {
      this.usuarioForm.id_sucursal = null;
    }
  }

  obtenerNombresSucursales(u: Usuario): string {
    if (u.sucursal_nombre) return u.sucursal_nombre;
    if (u.sucursales_nombres) return u.sucursales_nombres;
    if (u.ids_sucursales && u.ids_sucursales.length > 0) {
      return `Sucursal #${u.ids_sucursales.join(', #')}`;
    }
    return '';
  }

  ngOnInit() {
    this.busquedaSubject
      .pipe(debounceTime(200), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        this.aplicarFiltros();
        this.cdr.detectChanges();
      });

    if (this.authService.obtenerToken()) {
      const currentUser = this.authService.obtenerUsuario();
      if (!this.isGlobalAdmin && currentUser?.id_empresa) {
        this.filtroEmpresa = String(currentUser.id_empresa);
      } else if (this.isGlobalAdmin) {
        const eff = this.authService.getEffectiveCompanyId();
        this.filtroEmpresa = eff ? String(eff) : 'TODOS';
        this.cargarEmpresas();
      }
      this.cargarUsuarios();
      this.cargarRolesDelegables();

      this.authService.companyChanged$
        .pipe(
          distinctUntilChanged((p, c) => p?.id_empresa === c?.id_empresa),
          takeUntilDestroyed(this.destroyRef)
        )
        .subscribe(empresa => {
          if (this.isGlobalAdmin) {
            const nueva = empresa ? String(empresa.id_empresa) : 'TODOS';
            if (this.filtroEmpresa !== nueva) {
              this.filtroEmpresa = nueva;
              this.aplicarFiltros();
              this.cdr.detectChanges();
            }
          }
        });
    } else {
      this.cargando = false;
      this.mensajeError = "No se pudo iniciar sesión. Por favor recarga la página.";
    }
  }

  onBusquedaInput() {
    this.busquedaSubject.next(this.filtroTexto);
  }

  trackByUsuarioId(index: number, item: Usuario): number {
    return item.id_usuario || item.nro_usuario || index;
  }

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token ? new HttpHeaders({ 'Authorization': `Bearer ${token}` }) : new HttpHeaders();
  }


  mostrarNotificacionExito(msg: string) {
    this.mensajeExito = msg;
    setTimeout(() => {
      this.mensajeExito = '';
      this.cdr.detectChanges();
    }, 4500);
  }

  // --- MÉTODOS DE CARGA ---

  cargarRolesDelegables() {
    this.rbacService.listarRolesDelegables()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            if (res && res.success) {
              this.rolesDisponibles = res.roles || [];
            }
          });
        },
        error: () => {
          // Fallback a roles estándar
          this.rolesDisponibles = [
            { id_rol: 3, nombre: 'ADMINISTRADOR_TIENDA' },
            { id_rol: 4, nombre: 'ENCARGADO' },
            { id_rol: 5, nombre: 'EMPLEADO' },
            { id_rol: 2, nombre: 'CLIENTE' },
            { id_rol: 6, nombre: 'PROVEEDOR' }
          ];
        }
      });
  }

  cargarEmpresas() {
    this.empresaService.listarEmpresas()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res: any) => {
          this.ngZone.run(() => {
            if (res && res.success) {
              this.empresas = (res.data || []).filter((e: any) => e.estado === 'ACTIVO');
            }
          });
        }
      });
  }

  cargarUsuarios() {
    this.cargando = true;
    this.mensajeError = '';

    this.http.get<any>(`${this.apiUrl}/api/usuarios/`, { headers: this.getHeaders() })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            if (res && res.success) {
              this.usuarios = [...(res.data || [])];
              this.aplicarFiltros();
            } else {
              this.mensajeError = res.message || 'Error al obtener usuarios.';
            }
            this.cargando = false;
            this.cdr.detectChanges();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.mensajeError = err?.error?.detail || 'Error de conexión al cargar usuarios.';
            this.cargando = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  // --- FILTRADO Y MÉTRICAS ---

  onFiltroEmpresaChange() {
    if (this.isGlobalAdmin) {
      if (this.filtroEmpresa !== 'TODOS' && this.filtroEmpresa !== '') {
        const emp = this.empresas.find(e => e.id_empresa === Number(this.filtroEmpresa));
        if (emp) {
          this.authService.setSelectedCompany({ id_empresa: emp.id_empresa, nombre_empresa: emp.nombre_empresa });
        }
      } else {
        this.authService.setSelectedCompany(null);
      }
    }
    this.aplicarFiltros();
  }

  aplicarFiltros() {
    let resultado = [...this.usuarios];

    const currentUser = this.authService.obtenerUsuario();

    // Aislamiento Multi-Tenant para administradores de tienda
    if (!this.isGlobalAdmin && currentUser?.id_empresa) {
      resultado = resultado.filter(u => u.id_empresa === currentUser.id_empresa);
    } else if (this.filtroEmpresa !== '' && this.filtroEmpresa !== 'TODOS') {
      const idBuscado = Number(this.filtroEmpresa);
      resultado = resultado.filter(u => u.id_empresa === idBuscado);
    }

    // Filtro por Estado
    if (this.filtroEstado !== '' && this.filtroEstado !== 'TODOS') {
      resultado = resultado.filter(u => u.estado === this.filtroEstado);
    }

    // Filtro por Rol
    if (this.filtroRol !== '' && this.filtroRol !== 'TODOS') {
      const idRolBuscado = Number(this.filtroRol);
      resultado = resultado.filter(u => (u.id_rol || u.nro_rol) === idRolBuscado);
    }

    // Filtro por Texto
    if (this.filtroTexto && this.filtroTexto.trim().length > 0) {
      const q = this.filtroTexto.toLowerCase().trim();
      resultado = resultado.filter(u =>
        (u.nombre_completo && u.nombre_completo.toLowerCase().includes(q)) ||
        (u.correo && u.correo.toLowerCase().includes(q)) ||
        (u.nombre_usuario && u.nombre_usuario.toLowerCase().includes(q)) ||
        (u.nombre_rol && u.nombre_rol.toLowerCase().includes(q)) ||
        (u.nombre_empresa && u.nombre_empresa.toLowerCase().includes(q))
      );
    }

    this.usuariosFiltrados = resultado;
    this.actualizarMetricas();
  }

  actualizarMetricas() {
    this.totalUsuarios = this.usuariosFiltrados.length;
    this.usuariosActivos = this.usuariosFiltrados.filter(u => u.estado === 'ACTIVO').length;
    this.usuariosInactivos = this.usuariosFiltrados.filter(u => u.estado === 'INACTIVO').length;
  }

  obtenerIniciales(nombre: string): string {
    if (!nombre) return 'AU';
    const partes = nombre.trim().split(' ');
    if (partes.length >= 2) {
      return (partes[0][0] + partes[1][0]).toUpperCase();
    }
    return nombre.substring(0, 2).toUpperCase();
  }

  // --- GESTIÓN DE USUARIO (CREAR / EDITAR) ---

  abrirModalNuevo() {
    this.modoEdicion = false;
    this.mensajeModalError = '';
    this.usuarioForm = this.inicializarUsuario();
    this.cargarSucursalesParaUsuario(this.usuarioForm.id_empresa || undefined);
    this.mostrarModal = true;
  }

  abrirModalEditar(usuario: Usuario) {
    this.modoEdicion = true;
    this.mensajeModalError = '';
    const rolEncontrado = usuario.id_rol || usuario.nro_rol || 2;
    const sucId = usuario.id_sucursal || (usuario.ids_sucursales && usuario.ids_sucursales.length > 0 ? usuario.ids_sucursales[0] : null);
    this.usuarioForm = { 
      ...usuario, 
      nro_rol: Number(rolEncontrado),
      id_rol: Number(rolEncontrado),
      id_empresa: usuario.id_empresa ? Number(usuario.id_empresa) : null,
      id_sucursal: sucId ? Number(sucId) : null,
      password: '' 
    }; 
    this.cargarSucursalesParaUsuario(this.usuarioForm.id_empresa || undefined);
    this.mostrarModal = true;
  }

  cerrarModal() {
    this.mostrarModal = false;
    this.guardando = false;
    this.mensajeModalError = '';
  }

  guardarUsuario() {
    this.mensajeModalError = '';

    if (!this.usuarioForm.nombre_completo || !this.usuarioForm.nombre_completo.trim()) {
      this.mensajeModalError = 'El Nombre Completo es obligatorio.';
      return;
    }

    if (!this.usuarioForm.nombre_usuario || !this.usuarioForm.nombre_usuario.trim()) {
      this.mensajeModalError = 'El Nombre de Usuario es obligatorio.';
      return;
    }

    if (!this.usuarioForm.nro_rol) {
      this.mensajeModalError = 'Debe seleccionar un Rol para el usuario.';
      return;
    }

    if (!this.isGlobalAdmin && !this.usuarioForm.id_empresa) {
      this.usuarioForm.id_empresa = this.idEmpresaSesion;
    }

    if (this.requiereSucursal() && !this.usuarioForm.id_sucursal) {
      this.mensajeModalError = 'Debe seleccionar la Sucursal asignada para este rol operativo/encargado.';
      return;
    }

    this.guardando = true;

    const payload: any = {
      ...this.usuarioForm,
      nombre_completo: this.usuarioForm.nombre_completo.trim(),
      nombre_usuario: this.usuarioForm.nombre_usuario.trim().toLowerCase(),
      id_rol: Number(this.usuarioForm.nro_rol),
      nro_rol: Number(this.usuarioForm.nro_rol),
      id_empresa: this.usuarioForm.id_empresa ? Number(this.usuarioForm.id_empresa) : null,
      id_sucursal: this.usuarioForm.id_sucursal ? Number(this.usuarioForm.id_sucursal) : null,
      ids_sucursales: this.usuarioForm.id_sucursal ? [Number(this.usuarioForm.id_sucursal)] : []
    };

    const targetId = this.usuarioForm.id_usuario || this.usuarioForm.nro_usuario;

    if (this.modoEdicion && targetId) {
      this.http.put<any>(`${this.apiUrl}/api/usuarios/${targetId}`, payload, { headers: this.getHeaders() })
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: () => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.cerrarModal();
              this.cargarUsuarios();
              this.mostrarNotificacionExito(`Usuario '${payload.nombre_completo}' actualizado exitosamente.`);
            });
          },
          error: (err) => {
            this.ngZone.run(() => {
              this.mensajeModalError = extraerMensajeError(err, 'Error al actualizar el usuario.');
              this.guardando = false;
              this.cdr.detectChanges();
            });
          }
        });
    } else {
      if (!this.usuarioForm.password || !this.usuarioForm.password.trim()) {
        this.mensajeModalError = 'La contraseña es obligatoria para nuevos usuarios.';
        this.guardando = false;
        return;
      }

      this.http.post<any>(`${this.apiUrl}/api/usuarios/`, payload, { headers: this.getHeaders() })
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: () => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.cerrarModal();
              this.cargarUsuarios();
              this.mostrarNotificacionExito(`Usuario '${payload.nombre_completo}' registrado exitosamente.`);
            });
          },
          error: (err) => {
            this.ngZone.run(() => {
              this.mensajeModalError = extraerMensajeError(err, 'Error al registrar el usuario. Verifique los datos.');
              this.guardando = false;
              this.cdr.detectChanges();
            });
          }
        });
    }
  }

  cambiarEstadoUsuario(usuario: Usuario) {
    const id = usuario.id_usuario || usuario.nro_usuario;
    if (!id) return;

    const nuevoActivo = usuario.estado !== 'ACTIVO';
    const accion = nuevoActivo ? 'activar' : 'desactivar';
    const confirmar = confirm(`¿Está seguro que desea ${accion} al usuario '${usuario.nombre_completo || usuario.nombre_usuario}'?`);
    if (!confirmar) return;

    this.cargando = true;
    this.http.put<any>(`${this.apiUrl}/api/usuarios/${id}/estado`, { activo: nuevoActivo }, { headers: this.getHeaders() })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.ngZone.run(() => {
            this.cargarUsuarios();
            this.mostrarNotificacionExito(`Usuario ${nuevoActivo ? 'activado' : 'desactivado'} correctamente.`);
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            alert(extraerMensajeError(err, 'Error al cambiar estado del usuario.'));
            this.cargando = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  // --- GESTIÓN DE PERMISOS DIRECTOS ---

  abrirModalPermisos(usuario: Usuario) {
    const id = usuario.id_usuario || usuario.nro_usuario;
    if (!id) return;

    this.usuarioSeleccionadoPermisos = usuario;
    this.mostrarModalPermisos = true;
    this.cargandoPermisos = true;
    this.mensajeModalError = '';
    this.idsPermisosDirectosSeleccionados.clear();
    this.codigosPermisosHeredados.clear();
    this.codigosPermisosDelegables.clear();

    // 1. Cargar permisos delegables por el admin actual
    this.rbacService.listarPermisosDelegables()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          if (res && res.success) {
            this.codigosPermisosDelegables = new Set(res.permisos.map(p => p.codigo));
          }
        }
      });

    // 2. Cargar todos los permisos del sistema agrupados por módulo
    this.rbacService.listarPermisos()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          if (res && res.success) {
            const agrupados: { [key: string]: Permiso[] } = {};
            for (const p of res.permisos) {
              const mod = (p.modulo || 'GENERAL').toUpperCase();
              if (!agrupados[mod]) agrupados[mod] = [];
              agrupados[mod].push(p);
            }
            this.modulosPermisos = Object.keys(agrupados).map(mod => ({
              modulo: mod,
              permisos: agrupados[mod]
            }));
          }
        }
      });

    // 3. Cargar estado actual de permisos del usuario destino
    this.rbacService.obtenerPermisosUsuario(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            if (res && res.success) {
              for (const p of (res.permisos_directos || [])) {
                this.idsPermisosDirectosSeleccionados.add(p.id_permiso);
              }
              for (const p of (res.permisos_heredados || [])) {
                this.codigosPermisosHeredados.add(p.codigo);
              }
            }
            this.cargandoPermisos = false;
            this.cdr.detectChanges();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.mensajeModalError = err?.error?.detail || 'Error al obtener permisos del usuario.';
            this.cargandoPermisos = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  cerrarModalPermisos() {
    this.mostrarModalPermisos = false;
    this.usuarioSeleccionadoPermisos = null;
    this.guardando = false;
    this.mensajeModalError = '';
  }

  togglePermisoDirecto(p: Permiso) {
    if (this.idsPermisosDirectosSeleccionados.has(p.id_permiso)) {
      this.idsPermisosDirectosSeleccionados.delete(p.id_permiso);
    } else {
      this.idsPermisosDirectosSeleccionados.add(p.id_permiso);
    }
    this.cdr.detectChanges();
  }

  esPermisoDelegable(p: Permiso): boolean {
    if (this.isGlobalAdmin) return true;
    return this.codigosPermisosDelegables.has(p.codigo);
  }

  guardarPermisosDirectos() {
    if (!this.usuarioSeleccionadoPermisos) return;
    const id = this.usuarioSeleccionadoPermisos.id_usuario || this.usuarioSeleccionadoPermisos.nro_usuario;
    if (!id) return;

    this.guardando = true;
    this.mensajeModalError = '';

    const ids = Array.from(this.idsPermisosDirectosSeleccionados);

    this.rbacService.asignarPermisosDirectosUsuario(id, ids)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.cerrarModalPermisos();
            this.cargarUsuarios();
            this.mostrarNotificacionExito(`Permisos directos asignados con éxito a '${this.usuarioSeleccionadoPermisos?.nombre_completo}'.`);
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.mensajeModalError = extraerMensajeError(err, 'Error al guardar los permisos directos.');
            this.guardando = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  // --- ASIGNACIÓN DE SUCURSALES AUTORIZADAS ---

  abrirModalSucursales(usuario: Usuario) {
    const id = usuario.id_usuario || usuario.nro_usuario;
    if (!id) return;

    this.usuarioSeleccionadoSucursales = usuario;
    this.mostrarModalSucursales = true;
    this.cargandoSucursalesModal = true;
    this.mensajeModalSucursalesError = '';
    this.idsSucursalesSeleccionadas.clear();

    const empId = usuario.id_empresa ? Number(usuario.id_empresa) : (this.idEmpresaSesion || undefined);

    // 1. Cargar sucursales de la empresa
    this.sucursalService.listarSucursales(empId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.sucursalesModalDisponibles = (res?.data || []).filter((s: Sucursal) => s.activo !== false);
            this.cdr.detectChanges();
          });
        },
        error: () => {
          this.sucursalesModalDisponibles = [];
        }
      });

    // 2. Cargar sucursales actualmente asignadas
    this.rbacService.obtenerSucursalesUsuario(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.cargandoSucursalesModal = false;
            if (res && res.sucursales) {
              for (const sId of res.sucursales) {
                this.idsSucursalesSeleccionadas.add(sId);
              }
            }
            this.cdr.detectChanges();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.cargandoSucursalesModal = false;
            this.mensajeModalSucursalesError = extraerMensajeError(err, 'Error al consultar las sucursales asignadas.');
            this.cdr.detectChanges();
          });
        }
      });
  }

  toggleSucursalModal(idSucursal: number) {
    if (this.idsSucursalesSeleccionadas.has(idSucursal)) {
      this.idsSucursalesSeleccionadas.delete(idSucursal);
    } else {
      this.idsSucursalesSeleccionadas.add(idSucursal);
    }
    this.cdr.detectChanges();
  }

  cerrarModalSucursales() {
    this.mostrarModalSucursales = false;
    this.usuarioSeleccionadoSucursales = null;
    this.mensajeModalSucursalesError = '';
    this.guardando = false;
  }

  guardarAsignacionSucursales() {
    if (!this.usuarioSeleccionadoSucursales) return;
    const id = this.usuarioSeleccionadoSucursales.id_usuario || this.usuarioSeleccionadoSucursales.nro_usuario;
    if (!id) return;

    this.guardando = true;
    this.mensajeModalSucursalesError = '';

    const ids = Array.from(this.idsSucursalesSeleccionadas);

    this.rbacService.asignarSucursalesUsuario(id, ids)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.cerrarModalSucursales();
            this.cargarUsuarios();
            this.mostrarNotificacionExito(`Sucursales asignadas exitosamente a '${this.usuarioSeleccionadoSucursales?.nombre_completo}'.`);
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.mensajeModalSucursalesError = extraerMensajeError(err, 'Error al guardar las sucursales asignadas.');
            this.cdr.detectChanges();
          });
        }
      });
  }

  // ==============================================================
  // MODAL DETALLE DE USUARIO (FICHA DE PERFIL)
  // ==============================================================

  abrirModalDetalle(usuario: Usuario) {
    this.usuarioSeleccionadoDetalle = usuario;
    this.mostrarModalDetalle = true;
    this.cargandoDetallePermisos = true;
    this.permisosDirectosDetalle = [];
    this.permisosHeredadosDetalle = [];
    this.permisosEfectivosDetalle = [];

    const id = usuario.id_usuario || usuario.nro_usuario;
    if (!id) {
      this.cargandoDetallePermisos = false;
      return;
    }

    this.rbacService.obtenerPermisosUsuario(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            if (res.success) {
              this.permisosDirectosDetalle = res.permisos_directos || [];
              this.permisosHeredadosDetalle = res.permisos_heredados || [];
              this.permisosEfectivosDetalle = res.permisos_efectivos || [];
            }
            this.cargandoDetallePermisos = false;
            this.cdr.detectChanges();
          });
        },
        error: () => {
          this.ngZone.run(() => {
            this.cargandoDetallePermisos = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  cerrarModalDetalle() {
    this.mostrarModalDetalle = false;
    this.usuarioSeleccionadoDetalle = null;
    this.permisosDirectosDetalle = [];
    this.permisosHeredadosDetalle = [];
    this.permisosEfectivosDetalle = [];
  }

  abrirEdicionDesdeDetalle() {
    if (!this.usuarioSeleccionadoDetalle) return;
    const u = { ...this.usuarioSeleccionadoDetalle };
    this.cerrarModalDetalle();
    this.abrirModalEditar(u);
  }

  abrirPermisosDesdeDetalle() {
    if (!this.usuarioSeleccionadoDetalle) return;
    const u = { ...this.usuarioSeleccionadoDetalle };
    this.cerrarModalDetalle();
    this.abrirModalPermisos(u);
  }

  getNivelJerarquia(rol: string | undefined): number {
    const r = (rol || '').toUpperCase();
    if (r === 'ADMINISTRADOR') return 1;
    if (r === 'ADMINISTRADOR_TIENDA') return 3;
    if (r === 'ENCARGADO' || r === 'ENCARGADO_SUCURSAL') return 4;
    if (r === 'EMPLEADO' || r === 'CAJERO') return 5;
    if (r === 'CLIENTE') return 6;
    if (r === 'PROVEEDOR') return 7;
    return 6;
  }
}