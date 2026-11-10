import { Component, OnInit, inject, ChangeDetectorRef, NgZone, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { AuthService } from '../../../services/auth';
import { Sucursal, SucursalService } from '../../../services/sucursales';
import { Ciudad, CiudadService } from '../../../services/ciudades';
import { Empresa, EmpresaService } from '../../../services/empresa';
import { MapaSucursalComponent } from '../mapa-sucursal/mapa-sucursal';
import { extraerMensajeError } from '../../../utils/error-helper';

@Component({
  selector: 'app-lista-sucursales',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MapaSucursalComponent
  ],
  templateUrl: './lista-sucursales.html'
})
export class ListaSucursalesComponent implements OnInit {

  private sucursalService = inject(SucursalService);
  private ciudadService = inject(CiudadService);
  private empresaService = inject(EmpresaService);
  public authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  private ngZone = inject(NgZone);
  private destroyRef = inject(DestroyRef);
  private busquedaSucursalSubject = new Subject<string>();
  private busquedaCiudadSubject = new Subject<string>();
  ciudadesCargadas: boolean = false;

  // Tab navigation
tabActiva: 'SUCURSALES' | 'CIUDADES' | 'MAPA' = 'SUCURSALES';

  // Branch data
  sucursales: Sucursal[] = [];
  sucursalesFiltradas: Sucursal[] = [];
  empresas: Empresa[] = [];

  // City data
  ciudades: Ciudad[] = [];
  ciudadesFiltradas: Ciudad[] = [];

  // Branch filters
  filtroEstado: string = 'TODOS';
  filtroBusqueda: string = '';
  filtroEmpresaId: number = 0;

  // City filters
  filtroCiudadDepto: string = 'TODOS';
  filtroCiudadBusqueda: string = '';

  // UI state
  cargando: boolean = false;
  guardando: boolean = false;
  mensajeError: string = '';
  mensajeModalError: string = '';
  mensajeExito: string = '';

  // Branch Modal
  mostrarModalSucursal: boolean = false;
  modoEdicionSucursal: boolean = false;
  sucursalForm: Sucursal = this.inicializarSucursal();

  // City Modal
  mostrarModalCiudad: boolean = false;
  modoEdicionCiudad: boolean = false;
  ciudadForm: Ciudad = this.inicializarCiudad();

  // Autocomplete / MenuItem de Ciudades
  inputCiudadTexto: string = '';
  mostrarMenuCiudades: boolean = false;
  sugerenciasCiudades: Ciudad[] = [];

  readonly departamentosBolivia: string[] = [
    'Santa Cruz',
    'La Paz',
    'Cochabamba',
    'Chuquisaca',
    'Oruro',
    'Potosí',
    'Tarija',
    'Beni',
    'Pando'
  ];

  readonly DEPARTAMENTO_COORDS_MAP: Record<string, { lat: number; lng: number }> = {
    'Santa Cruz': { lat: -17.7833, lng: -63.1821 },
    'La Paz': { lat: -16.5000, lng: -68.1500 },
    'Cochabamba': { lat: -17.3895, lng: -66.1568 },
    'Chuquisaca': { lat: -19.0333, lng: -65.2627 },
    'Oruro': { lat: -17.9833, lng: -67.1500 },
    'Potosí': { lat: -19.5836, lng: -65.7531 },
    'Tarija': { lat: -21.5355, lng: -64.7296 },
    'Beni': { lat: -14.8333, lng: -64.9000 },
    'Pando': { lat: -11.0267, lng: -68.7692 },
  };

  // Metrics
  totalSucursales: number = 0;
  sucursalesActivas: number = 0;
  sucursalesInactivas: number = 0;
  totalCiudadesCobertura: number = 0;

  get idEmpresaSesion(): number {
    const user = this.authService.obtenerUsuario();
    return user?.id_empresa || 0;
  }

get isGlobalAdmin(): boolean {
  const u = this.authService.obtenerUsuario();

  if (!u) return false;

  const rol = (u.nombre_rol || '').toUpperCase();
  const roles = (u.roles || []).map(r => r.toUpperCase());

  return (
    u.id_rol === 1 ||
    rol === 'ADMINISTRADOR' ||
    roles.includes('ADMINISTRADOR') ||
    this.authService.getScopeLevel() === 'PLATAFORMA'
  );
}

get sucursalesParaMapa(): Sucursal[] {
  if (this.isGlobalAdmin && this.filtroEmpresaId > 0) {
    return this.sucursales.filter(
      s => s.id_empresa === Number(this.filtroEmpresaId)
    );
  }

  return this.sucursales;
}
  ngOnInit() {
    this.busquedaSucursalSubject
      .pipe(debounceTime(200), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.aplicarFiltrosSucursales());

    this.busquedaCiudadSubject
      .pipe(debounceTime(200), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.aplicarFiltrosCiudades());

    if (this.authService.obtenerToken()) {
      if (this.isGlobalAdmin) {
        this.cargarEmpresas();
        const effId = this.authService.getEffectiveCompanyId();
        if (effId) {
          this.filtroEmpresaId = Number(effId);
        }
      }

      this.cargarSucursales();

      this.authService.companyChanged$
        .pipe(
          distinctUntilChanged((p, c) => p?.id_empresa === c?.id_empresa),
          takeUntilDestroyed(this.destroyRef)
        )
        .subscribe((emp) => {
          if (this.isGlobalAdmin) {
            this.filtroEmpresaId = emp && emp.id_empresa ? Number(emp.id_empresa) : 0;
            this.aplicarFiltrosSucursales();
          }
        });
    } else {
      this.cargando = false;
      this.mensajeError = 'No se pudo iniciar sesión. Por favor recarga la página.';
    }
  }

  onBusquedaSucursalInput() {
    this.busquedaSucursalSubject.next(this.filtroBusqueda);
  }

  onBusquedaCiudadInput() {
    this.busquedaCiudadSubject.next(this.filtroCiudadBusqueda);
  }

  trackBySucursalId(index: number, item: Sucursal): number {
    return item.id_sucursal || index;
  }

  trackByCiudadId(index: number, item: Ciudad): number {
    return item.id_ciudad || index;
  }

  // ============================================================
  // TABS
  // ============================================================
  cambiarTab(tab: 'SUCURSALES' | 'CIUDADES' | 'MAPA') {
    this.tabActiva = tab;
    this.mensajeError = '';
    this.mensajeExito = '';

    if (tab === 'CIUDADES') {
      if (!this.ciudadesCargadas) {
        this.cargarCiudades();
      } else {
        this.aplicarFiltrosCiudades();
      }
    } else {
      this.aplicarFiltrosSucursales();
    }
  }

  // ============================================================
  // CARGA DE DATOS
  // ============================================================

  cargarEmpresas() {
    this.empresaService.listarEmpresas()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            if (res && res.success) {
              this.empresas = res.data || [];
            }
          });
        }
      });
  }

  cargarCiudades() {
    this.ciudadService.listarCiudades(false)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.ciudadesCargadas = true;
            if (res && res.success) {
              this.ciudades = [...res.data];
              this.aplicarFiltrosCiudades();
              this.actualizarMetricas();
            }
          });
        }
      });
  }

  cargarSucursales() {
    this.cargando = true;
    this.mensajeError = '';

    const idEmpresaParam =
      (!this.isGlobalAdmin && this.idEmpresaSesion > 0)
        ? this.idEmpresaSesion
        : undefined;

    this.sucursalService.listarSucursales(idEmpresaParam)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            if (res && res.success) {
              this.sucursales = [...res.data];
              this.aplicarFiltrosSucursales();
            } else {
              this.mensajeError =
                res.message || 'Error al obtener sucursales.';
            }

            this.cargando = false;
            this.cdr.detectChanges();
          });
        },

        error: (err) => {
          this.ngZone.run(() => {
            this.mensajeError = extraerMensajeError(err, 'Error de conexión al cargar sucursales.');
            this.cargando = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  // ============================================================
  // INICIALIZACIÓN DE FORMULARIOS
  // ============================================================

  inicializarSucursal(): Sucursal {
    const empresaSeleccionada = this.authService.selectedCompany()?.id_empresa;
    let idEmpresaDefault = 0;
    if (this.isGlobalAdmin) {
      if (this.filtroEmpresaId > 0) {
        idEmpresaDefault = this.filtroEmpresaId;
      } else if (empresaSeleccionada) {
        idEmpresaDefault = empresaSeleccionada;
      } else if (this.empresas.length > 0 && this.empresas[0].id_empresa) {
        idEmpresaDefault = this.empresas[0].id_empresa;
      }
    } else {
      idEmpresaDefault = this.idEmpresaSesion || 0;
    }

    return {
      nombre: '',
      direccion: '',
      telefono: '',
      id_ciudad: undefined,
      ciudad: '',
      departamento: 'Santa Cruz',
      id_empresa: idEmpresaDefault,
      latitud: -17.7833,
      longitud: -63.1821,
      activo: true
    };
  }

  inicializarCiudad(): Ciudad {
    return {
      nombre: '',
      departamento: 'Santa Cruz',
      estado: true
    };
  }

  // ============================================================
  // FILTROS SUCURSALES
  // ============================================================

  aplicarFiltrosSucursales() {
    let lista = [...this.sucursales];

    if (this.filtroEstado !== 'TODOS') {
      const targetActivo = this.filtroEstado === 'ACTIVO';
      lista = lista.filter(s => s.activo === targetActivo);
    }

    if (this.filtroEmpresaId > 0) {
      lista = lista.filter(
        s => s.id_empresa === Number(this.filtroEmpresaId)
      );
    }

    if (this.filtroBusqueda && this.filtroBusqueda.trim().length > 0) {
      const q = this.filtroBusqueda.trim().toLowerCase();

      lista = lista.filter(s =>
        (s.nombre && s.nombre.toLowerCase().includes(q)) ||
        (s.direccion && s.direccion.toLowerCase().includes(q)) ||
        (s.ciudad && s.ciudad.toLowerCase().includes(q)) ||
        (s.departamento && s.departamento.toLowerCase().includes(q)) ||
        (s.empresa_nombre && s.empresa_nombre.toLowerCase().includes(q)) ||
        (s.telefono && s.telefono.toLowerCase().includes(q))
      );
    }

    this.sucursalesFiltradas = lista;
    this.actualizarMetricas();
  }

  // ============================================================
  // FILTROS CIUDADES
  // ============================================================

  aplicarFiltrosCiudades() {
    let lista = [...this.ciudades];

    if (this.filtroCiudadDepto !== 'TODOS') {
      lista = lista.filter(
        c => c.departamento === this.filtroCiudadDepto
      );
    }

    if (
      this.filtroCiudadBusqueda &&
      this.filtroCiudadBusqueda.trim().length > 0
    ) {
      const q = this.filtroCiudadBusqueda.trim().toLowerCase();

      lista = lista.filter(c =>
        (c.nombre && c.nombre.toLowerCase().includes(q)) ||
        (c.departamento && c.departamento.toLowerCase().includes(q))
      );
    }

    this.ciudadesFiltradas = lista;
  }

  // ============================================================
  // MÉTRICAS
  // ============================================================

  actualizarMetricas() {
    this.totalSucursales = this.sucursales.length;

    this.sucursalesActivas =
      this.sucursales.filter(s => s.activo === true).length;

    this.sucursalesInactivas =
      this.sucursales.filter(s => s.activo === false).length;

    const ciudadesSet = new Set(
      this.sucursales
        .filter(s => s.activo && s.ciudad)
        .map(s => s.ciudad)
    );

    this.totalCiudadesCobertura = ciudadesSet.size;
  }

  obtenerIniciales(nombre: string): string {
    if (!nombre) return 'SU';

    const partes = nombre.trim().split(' ');

    if (partes.length >= 2) {
      return (
        partes[0][0] +
        partes[1][0]
      ).toUpperCase();
    }

    return nombre.substring(0, 2).toUpperCase();
  }

  mostrarNotificacionExito(mensaje: string) {
    this.mensajeExito = mensaje;

    setTimeout(() => {
      this.mensajeExito = '';
      this.cdr.detectChanges();
    }, 4500);
  }

  // ============================================================
  // AUTOCOMPLETE / MENUITEM CIUDADES
  // ============================================================

  onInputCiudad(texto: string) {
    this.inputCiudadTexto = texto;
    this.sucursalForm.ciudad = texto;

    if (!texto || texto.trim().length === 0) {
      this.sugerenciasCiudades = [];
      this.mostrarMenuCiudades = false;
      return;
    }

    const q = texto.trim().toLowerCase();

    this.sugerenciasCiudades = this.ciudades
      .filter(c =>
        c.estado &&
        (
          c.nombre.toLowerCase().includes(q) ||
          c.departamento.toLowerCase().includes(q)
        )
      )
      .slice(0, 8);

    this.mostrarMenuCiudades = true;
    this.cdr.detectChanges();
  }

  seleccionarCiudadSugerida(c: Ciudad) {
    this.sucursalForm.id_ciudad = c.id_ciudad;
    this.sucursalForm.ciudad = c.nombre;
    this.sucursalForm.departamento = c.departamento;

    if (this.DEPARTAMENTO_COORDS_MAP[c.departamento]) {
      const coords = this.DEPARTAMENTO_COORDS_MAP[c.departamento];
      this.sucursalForm.latitud = coords.lat;
      this.sucursalForm.longitud = coords.lng;
    }

    this.inputCiudadTexto = c.nombre;
    this.mostrarMenuCiudades = false;

    this.cdr.detectChanges();
  }

  onDepartamentoChange() {
    const depto = this.sucursalForm.departamento || 'Santa Cruz';
    const coords = this.DEPARTAMENTO_COORDS_MAP[depto] || { lat: -17.7833, lng: -63.1821 };
    this.sucursalForm.latitud = coords.lat;
    this.sucursalForm.longitud = coords.lng;
    this.cdr.detectChanges();
  }

  seleccionarCiudadPersonalizada() {
    const texto = this.inputCiudadTexto.trim();

    if (!texto) return;

    this.sucursalForm.id_ciudad = undefined;
    this.sucursalForm.ciudad = texto;

    this.mostrarMenuCiudades = false;
    this.cdr.detectChanges();
  }

  cerrarMenuCiudadesConRetraso() {
    setTimeout(() => {
      this.mostrarMenuCiudades = false;
      this.cdr.detectChanges();
    }, 250);
  }

  // ============================================================
  // MODAL SUCURSAL
  // ============================================================

  abrirModalNuevaSucursal() {
    if (!this.ciudadesCargadas) {
      this.cargarCiudades();
    }
    this.modoEdicionSucursal = false;
    this.mensajeModalError = '';

    this.sucursalForm = this.inicializarSucursal();

    this.inputCiudadTexto = '';
    this.mostrarMenuCiudades = false;
    this.mostrarModalSucursal = true;

    this.cdr.detectChanges();
  }

  abrirModalEditarSucursal(sucursal: Sucursal) {
    if (!this.ciudadesCargadas) {
      this.cargarCiudades();
    }
    this.modoEdicionSucursal = true;
    this.mensajeModalError = '';

    this.sucursalForm = {
      ...sucursal,
      departamento: sucursal.departamento || 'Santa Cruz',
      telefono: sucursal.telefono || '',
      latitud: sucursal.latitud ?? null,
      longitud: sucursal.longitud ?? null
    };

    this.inputCiudadTexto = sucursal.ciudad || '';
    this.mostrarMenuCiudades = false;
    this.mostrarModalSucursal = true;

    this.cdr.detectChanges();
  }

  cerrarModalSucursal() {
    this.mostrarModalSucursal = false;
    this.mensajeModalError = '';
    this.guardando = false;

    this.cdr.detectChanges();
  }

  seleccionarUbicacionSucursal(evento: {
    latitud: number;
    longitud: number;
  }) {
    this.sucursalForm.latitud = evento.latitud;
    this.sucursalForm.longitud = evento.longitud;

    this.cdr.detectChanges();
  }

  // ============================================================
  // GUARDAR SUCURSAL
  // ============================================================

  guardarSucursal() {
    this.mensajeModalError = '';

    if (
      !this.sucursalForm.nombre ||
      !this.sucursalForm.nombre.trim()
    ) {
      this.mensajeModalError =
        'El nombre de la sucursal es obligatorio.';
      return;
    }

    if (
      !this.sucursalForm.ciudad ||
      !this.sucursalForm.ciudad.trim()
    ) {
      this.mensajeModalError =
        'Debe indicar o seleccionar una ciudad para la sucursal.';
      return;
    }

    if (
      !this.sucursalForm.departamento ||
      !this.sucursalForm.departamento.trim()
    ) {
      this.mensajeModalError =
        'El departamento es obligatorio.';
      return;
    }

    if (
      !this.sucursalForm.direccion ||
      !this.sucursalForm.direccion.trim()
    ) {
      this.mensajeModalError =
        'La dirección física de la sucursal es obligatoria.';
      return;
    }

    if (
      !this.sucursalForm.telefono ||
      !this.sucursalForm.telefono.trim()
    ) {
      this.mensajeModalError =
        'El teléfono de contacto de la sucursal es obligatorio.';
      return;
    }

    if (
      this.isGlobalAdmin &&
      (
        !this.sucursalForm.id_empresa ||
        this.sucursalForm.id_empresa === 0
      )
    ) {
      this.mensajeModalError =
        'Debe seleccionar una empresa (Tenant) para la sucursal.';
      return;
    }

    if (!this.sucursalForm.id_empresa) {
      this.sucursalForm.id_empresa =
        this.idEmpresaSesion;
    }

    if (
      this.sucursalForm.latitud === null ||
      this.sucursalForm.latitud === undefined ||
      this.sucursalForm.longitud === null ||
      this.sucursalForm.longitud === undefined
    ) {
      const depto = this.sucursalForm.departamento || 'Santa Cruz';
      const fallbackCoords = this.DEPARTAMENTO_COORDS_MAP[depto] || { lat: -17.7833, lng: -63.1821 };
      this.sucursalForm.latitud = fallbackCoords.lat;
      this.sucursalForm.longitud = fallbackCoords.lng;
    }

    this.guardando = true;
    this.cdr.detectChanges();

    const payload: Sucursal = {
      ...this.sucursalForm,
      nombre: this.sucursalForm.nombre.trim(),
      direccion: this.sucursalForm.direccion.trim(),
      telefono: this.sucursalForm.telefono.trim(),
      ciudad: this.sucursalForm.ciudad.trim(),
      departamento: this.sucursalForm.departamento.trim(),

      latitud: Number(
        Number(this.sucursalForm.latitud).toFixed(7)
      ),

      longitud: Number(
        Number(this.sucursalForm.longitud).toFixed(7)
      ),

      activo: Boolean(this.sucursalForm.activo)
    };

    if (this.modoEdicionSucursal) {

      if (!this.sucursalForm.id_sucursal) {
        this.mensajeModalError =
          'No se encontró el identificador de la sucursal.';
        this.guardando = false;
        return;
      }

      this.sucursalService
        .actualizarSucursal(
          this.sucursalForm.id_sucursal,
          payload
        )
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({

          next: () => {
            this.ngZone.run(() => {

              this.guardando = false;

              this.cerrarModalSucursal();

              this.cargarSucursales();
              this.cargarCiudades();

              this.mostrarNotificacionExito(
                `¡Sucursal '${payload.nombre}' actualizada exitosamente!`
              );
            });
          },

          error: (err) => {
            this.ngZone.run(() => {
              this.mensajeModalError = extraerMensajeError(err, 'Error al actualizar la sucursal.');
              this.guardando = false;
              this.cdr.detectChanges();
            });
          }
        });

    } else {

      this.sucursalService
        .crearSucursal(payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({

          next: () => {
            this.ngZone.run(() => {

              this.guardando = false;

              this.cerrarModalSucursal();

              this.cargarSucursales();
              this.cargarCiudades();

              this.mostrarNotificacionExito(
                `¡Sucursal '${payload.nombre}' registrada exitosamente!`
              );
            });
          },

          error: (err) => {
            this.ngZone.run(() => {
              this.mensajeModalError = extraerMensajeError(err, 'Error al registrar la sucursal.');
              this.guardando = false;
              this.cdr.detectChanges();
            });
          }
        });
    }
  }

  // ============================================================
  // CAMBIAR ESTADO SUCURSAL
  // ============================================================

  cambiarEstadoSucursal(s: Sucursal) {

    if (!s.id_sucursal) return;

    const nuevoEstado = !s.activo;
    const accion = nuevoEstado
      ? 'activar'
      : 'desactivar';

    const confirmar = confirm(
      `¿Está seguro que desea ${accion} la sucursal '${s.nombre}'?`
    );

    if (!confirmar) return;

    this.cargando = true;

    this.sucursalService
      .cambiarEstadoSucursal(
        s.id_sucursal,
        nuevoEstado
      )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({

        next: () => {
          this.ngZone.run(() => {

            this.cargarSucursales();

            this.mostrarNotificacionExito(
              `Sucursal '${s.nombre}' ${
                nuevoEstado
                  ? 'activada'
                  : 'desactivada'
              } correctamente.`
            );
          });
        },

        error: (err) => {
          this.ngZone.run(() => {
            alert(extraerMensajeError(err, 'Error al cambiar el estado de la sucursal.'));
            this.cargando = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  // ============================================================
  // MODAL CIUDADES
  // ============================================================

  abrirModalNuevaCiudad() {
    this.modoEdicionCiudad = false;
    this.mensajeModalError = '';
    this.ciudadForm = this.inicializarCiudad();
    this.mostrarModalCiudad = true;
    this.cdr.detectChanges();
  }

  abrirModalEditarCiudad(c: Ciudad) {
    this.modoEdicionCiudad = true;
    this.mensajeModalError = '';
    this.ciudadForm = { ...c };
    this.mostrarModalCiudad = true;
    this.cdr.detectChanges();
  }

  cerrarModalCiudad() {
    this.mostrarModalCiudad = false;
    this.mensajeModalError = '';
    this.guardando = false;
    this.cdr.detectChanges();
  }

  guardarCiudad() {
    this.mensajeModalError = '';

    if (
      !this.ciudadForm.nombre ||
      !this.ciudadForm.nombre.trim()
    ) {
      this.mensajeModalError =
        'El nombre de la ciudad es obligatorio.';
      return;
    }

    if (
      !this.ciudadForm.departamento ||
      !this.ciudadForm.departamento.trim()
    ) {
      this.mensajeModalError =
        'El departamento es obligatorio.';
      return;
    }

    this.guardando = true;
    this.cdr.detectChanges();

    const payload: Ciudad = {
      ...this.ciudadForm,
      nombre: this.ciudadForm.nombre.trim(),
      departamento: this.ciudadForm.departamento.trim(),
      estado: Boolean(this.ciudadForm.estado)
    };

    if (this.modoEdicionCiudad) {

      if (!this.ciudadForm.id_ciudad) {
        this.mensajeModalError =
          'Identificador de ciudad no válido.';
        this.guardando = false;
        return;
      }

      this.ciudadService
        .actualizarCiudad(
          this.ciudadForm.id_ciudad,
          payload
        )
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({

          next: () => {
            this.ngZone.run(() => {

              this.guardando = false;

              this.cerrarModalCiudad();
              this.cargarCiudades();

              this.mostrarNotificacionExito(
                `Ciudad '${payload.nombre}' actualizada exitosamente.`
              );
            });
          },

          error: (err) => {
            this.ngZone.run(() => {

              this.mensajeModalError =
                err?.error?.detail ||
                err?.message ||
                'Error al actualizar la ciudad.';

              this.guardando = false;
              this.cdr.detectChanges();
            });
          }
        });

    } else {

      this.ciudadService
        .crearCiudad(payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({

          next: () => {
            this.ngZone.run(() => {

              this.guardando = false;

              this.cerrarModalCiudad();
              this.cargarCiudades();

              this.mostrarNotificacionExito(
                `Ciudad '${payload.nombre}' registrada en ${payload.departamento}.`
              );
            });
          },

          error: (err) => {
            this.ngZone.run(() => {

              this.mensajeModalError =
                err?.error?.detail ||
                err?.message ||
                'Error al registrar la ciudad.';

              this.guardando = false;
              this.cdr.detectChanges();
            });
          }
        });
    }
  }

  cambiarEstadoCiudad(c: Ciudad) {

    if (!c.id_ciudad) return;

    const nuevoEstado = !c.estado;

    const accion = nuevoEstado
      ? 'activar'
      : 'desactivar';

    const confirmar = confirm(
      `¿Está seguro que desea ${accion} la ciudad '${c.nombre}' (${c.departamento})?`
    );

    if (!confirmar) return;

    this.cargando = true;

    this.ciudadService
      .cambiarEstadoCiudad(
        c.id_ciudad,
        nuevoEstado
      )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({

        next: () => {
          this.ngZone.run(() => {

            this.cargarCiudades();

            this.mostrarNotificacionExito(
              `Ciudad '${c.nombre}' ${
                nuevoEstado
                  ? 'activada'
                  : 'desactivada'
              } correctamente.`
            );
          });
        },

        error: (err) => {
          this.ngZone.run(() => {

            alert(
              err?.error?.detail ||
              'Error al cambiar el estado de la ciudad.'
            );

            this.cargando = false;
            this.cdr.detectChanges();
          });
        }
      });
  }
}