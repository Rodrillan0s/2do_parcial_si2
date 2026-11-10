import { Component, OnInit, inject, ChangeDetectorRef, NgZone, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { AuthService } from '../../../services/auth';
import { Talla, ColorPrenda, TallasColoresService } from '../../../services/tallas-colores';
import { Empresa, EmpresaService } from '../../../services/empresa';

@Component({
  selector: 'app-tallas-colores',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './tallas-colores.html'
})
export class TallasColoresComponent implements OnInit {
  private tallasColoresService = inject(TallasColoresService);
  private empresaService = inject(EmpresaService);
  public authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  private ngZone = inject(NgZone);
  private destroyRef = inject(DestroyRef);
  private busquedaTallasSubject = new Subject<string>();
  private busquedaColoresSubject = new Subject<string>();

  // Tab activo: 'TALLAS' | 'COLORES'
  tabActivo: 'TALLAS' | 'COLORES' = 'TALLAS';

  // Datos
  tallas: Talla[] = [];
  tallasFiltradas: Talla[] = [];
  colores: ColorPrenda[] = [];
  coloresFiltrados: ColorPrenda[] = [];
  empresas: Empresa[] = [];
  tallasCargadas: boolean = false;
  coloresCargados: boolean = false;

  // Métricas precomputadas
  totalTallas: number = 0;
  tallasActivas: number = 0;
  totalColores: number = 0;
  coloresActivos: number = 0;

  // Filtros
  filtroEstadoTallas: string = 'TODOS';
  filtroBusquedaTallas: string = '';
  filtroEstadoColores: string = 'TODOS';
  filtroBusquedaColores: string = '';
  filtroEmpresaId: number = 0;

  // Estado UI
  cargando: boolean = false;
  guardando: boolean = false;
  mensajeError: string = '';
  mensajeExito: string = '';
  mensajeModalError: string = '';

  // Modal Talla
  mostrarModalTalla: boolean = false;
  modoEdicionTalla: boolean = false;
  tallaForm: Talla = this.inicializarTalla();

  // Modal Color
  mostrarModalColor: boolean = false;
  modoEdicionColor: boolean = false;
  colorForm: ColorPrenda = this.inicializarColor();

  // Modal Confirmación Eliminación
  mostrarModalConfirmacion: boolean = false;
  elementoAeliminar: { tipo: 'TALLA' | 'COLOR', id: number, nombre: string, variantes: number } | null = null;

  ngOnInit(): void {
    this.busquedaTallasSubject
      .pipe(debounceTime(200), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.aplicarFiltrosTallas());

    this.busquedaColoresSubject
      .pipe(debounceTime(200), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.aplicarFiltrosColores());

    if (this.esSuperAdmin) {
      this.cargarEmpresasSiEsAdmin();
      this.filtroEmpresaId = this.authService.getEffectiveCompanyId() || 0;
    }
    this.cargarDatos();

    this.authService.companyChanged$
      .pipe(
        distinctUntilChanged((p, c) => p?.id_empresa === c?.id_empresa),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(empresa => {
        if (this.esSuperAdmin) {
          const nueva = empresa ? empresa.id_empresa : 0;
          if (this.filtroEmpresaId !== nueva) {
            this.filtroEmpresaId = nueva;
            this.tallasCargadas = false;
            this.coloresCargados = false;
            this.cargarDatos();
            this.cdr.detectChanges();
          }
        }
      });
  }

  onBusquedaTallasInput(): void {
    this.busquedaTallasSubject.next(this.filtroBusquedaTallas);
  }

  onBusquedaColoresInput(): void {
    this.busquedaColoresSubject.next(this.filtroBusquedaColores);
  }

  trackByTallaId(index: number, item: Talla): number {
    return item.id_talla || index;
  }

  trackByColorId(index: number, item: ColorPrenda): number {
    return item.id_color || index;
  }

  onFiltroEmpresaChange(): void {
    if (this.esSuperAdmin) {
      if (this.filtroEmpresaId > 0) {
        const emp = this.empresas.find(e => e.id_empresa === this.filtroEmpresaId);
        if (emp && emp.id_empresa) {
          this.authService.setSelectedCompany({ id_empresa: emp.id_empresa, nombre_empresa: emp.nombre_empresa });
        }
      } else {
        this.authService.setSelectedCompany(null);
      }
    }
    this.cargarDatos();
  }

  get esSuperAdmin(): boolean {
    const u = this.authService.obtenerUsuario();
    if (!u) return false;
    const rol = (u.nombre_rol || '').toUpperCase();
    const roles = (u.roles || []).map(r => r.toUpperCase());
    return u.id_rol === 1 || rol === 'ADMINISTRADOR' || roles.includes('ADMINISTRADOR') || this.authService.getScopeLevel() === 'PLATAFORMA';
  }

  get tenantActualId(): number {
    const user = this.authService.obtenerUsuario();
    return user?.id_empresa || 1;
  }

  inicializarTalla(): Talla {
    return {
      nombre: '',
      descripcion: '',
      id_empresa: this.esSuperAdmin ? (this.filtroEmpresaId || this.tenantActualId) : this.tenantActualId,
      activo: true,
      estado: 'ACTIVO'
    };
  }

  inicializarColor(): ColorPrenda {
    return {
      nombre: '',
      codigo_hex: '#E8C5C8', // Rosa empolvado por defecto
      id_empresa: this.esSuperAdmin ? (this.filtroEmpresaId || this.tenantActualId) : this.tenantActualId,
      activo: true,
      estado: 'ACTIVO'
    };
  }

  cambiarTab(tab: 'TALLAS' | 'COLORES'): void {
    this.tabActivo = tab;
    this.mensajeError = '';
    this.mensajeExito = '';
    if (tab === 'COLORES' && !this.coloresCargados) {
      this.cargarColores();
    } else if (tab === 'TALLAS' && !this.tallasCargadas) {
      this.cargarTallas();
    }
    this.cdr.detectChanges();
  }

  cargarEmpresasSiEsAdmin(): void {
    if (this.esSuperAdmin) {
      this.empresaService.listarEmpresas()
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res: any) => {
            if (res?.success && res?.data) {
              this.empresas = res.data;
            }
          },
          error: (err: any) => console.warn('No se pudieron cargar empresas:', err)
        });
    }
  }

  private construirParams(): any {
    const params: any = {};
    if (this.filtroEmpresaId > 0) {
      params.id_empresa = this.filtroEmpresaId;
    }
    return params;
  }

  cargarDatos(): void {
    this.mensajeError = '';
    if (this.tabActivo === 'TALLAS') {
      this.cargarTallas();
      if (this.coloresCargados) {
        this.cargarColores(true);
      }
    } else {
      this.cargarColores();
      if (this.tallasCargadas) {
        this.cargarTallas(true);
      }
    }
  }

  cargarTallas(silencioso: boolean = false): void {
    if (!silencioso) {
      this.cargando = true;
    }
    const params = this.construirParams();
    this.tallasColoresService.listarTallas(params)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            if (!silencioso) {
              this.cargando = false;
            }
            this.tallasCargadas = true;
            if (res?.success) {
              this.tallas = res.data || [];
              this.aplicarFiltrosTallas();
            }
            this.cdr.detectChanges();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            if (!silencioso) {
              this.cargando = false;
            }
            this.mensajeError = err.error?.detail || 'Error al cargar tallas.';
            this.cdr.detectChanges();
          });
        }
      });
  }

  cargarColores(silencioso: boolean = false): void {
    if (!silencioso) {
      this.cargando = true;
    }
    const params = this.construirParams();
    this.tallasColoresService.listarColores(params)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            if (!silencioso) {
              this.cargando = false;
            }
            this.coloresCargados = true;
            if (res?.success) {
              this.colores = res.data || [];
              this.aplicarFiltrosColores();
            }
            this.cdr.detectChanges();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            if (!silencioso) {
              this.cargando = false;
            }
            this.mensajeError = err.error?.detail || 'Error al cargar colores.';
            this.cdr.detectChanges();
          });
        }
      });
  }

  // --- FILTROS TALLAS ---
  aplicarFiltrosTallas(): void {
    let list = [...this.tallas];
    if (this.filtroEstadoTallas === 'ACTIVOS') {
      list = list.filter(t => t.activo === true);
    } else if (this.filtroEstadoTallas === 'INACTIVOS') {
      list = list.filter(t => t.activo === false);
    }

    if (this.filtroBusquedaTallas.trim()) {
      const q = this.filtroBusquedaTallas.toLowerCase().trim();
      list = list.filter(t => 
        t.nombre.toLowerCase().includes(q) || 
        (t.descripcion && t.descripcion.toLowerCase().includes(q))
      );
    }
    this.tallasFiltradas = list;
    this.totalTallas = this.tallas.length;
    this.tallasActivas = this.tallas.filter(t => t.activo).length;
    this.cdr.detectChanges();
  }

  // --- FILTROS COLORES ---
  aplicarFiltrosColores(): void {
    let list = [...this.colores];
    if (this.filtroEstadoColores === 'ACTIVOS') {
      list = list.filter(c => c.activo === true);
    } else if (this.filtroEstadoColores === 'INACTIVOS') {
      list = list.filter(c => c.activo === false);
    }

    if (this.filtroBusquedaColores.trim()) {
      const q = this.filtroBusquedaColores.toLowerCase().trim();
      list = list.filter(c => 
        c.nombre.toLowerCase().includes(q) || 
        c.codigo_hex.toLowerCase().includes(q)
      );
    }
    this.coloresFiltrados = list;
    this.totalColores = this.colores.length;
    this.coloresActivos = this.colores.filter(c => c.activo).length;
    this.cdr.detectChanges();
  }

  // --- ACCIONES TALLA ---
  abrirModalCrearTalla(): void {
    this.modoEdicionTalla = false;
    this.tallaForm = this.inicializarTalla();
    this.mensajeModalError = '';
    this.mostrarModalTalla = true;
    this.cdr.detectChanges();
  }

  abrirModalEditarTalla(talla: Talla): void {
    this.modoEdicionTalla = true;
    this.tallaForm = { ...talla };
    this.mensajeModalError = '';
    this.mostrarModalTalla = true;
    this.cdr.detectChanges();
  }

  cerrarModalTalla(): void {
    this.mostrarModalTalla = false;
    this.modoEdicionTalla = false;
    this.mensajeModalError = '';
    this.cdr.detectChanges();
  }

  guardarTalla(): void {
    if (!this.tallaForm.nombre || !this.tallaForm.nombre.trim()) {
      this.mensajeModalError = 'El nombre de la talla es obligatorio (ej. XS, M, 38).';
      return;
    }

    this.guardando = true;
    this.mensajeModalError = '';

    const payload = {
      nombre: this.tallaForm.nombre.trim(),
      descripcion: (this.tallaForm.descripcion || '').trim(),
      id_empresa: this.tallaForm.id_empresa ? Number(this.tallaForm.id_empresa) : this.tenantActualId,
      activo: Boolean(this.tallaForm.activo)
    };

    if (this.modoEdicionTalla && this.tallaForm.id_talla) {
      this.tallasColoresService.actualizarTalla(this.tallaForm.id_talla, payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mostrarExito(res?.message || 'Talla actualizada exitosamente.');
              this.cerrarModalTalla();
              this.cargarDatos();
            });
          },
          error: (err) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mensajeModalError = err.error?.detail || err.error?.message || 'Error al actualizar la talla.';
              this.cdr.detectChanges();
            });
          }
        });
    } else {
      this.tallasColoresService.crearTalla(payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mostrarExito(res?.message || 'Talla registrada exitosamente.');
              this.cerrarModalTalla();
              this.cargarDatos();
            });
          },
          error: (err) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mensajeModalError = err.error?.detail || err.error?.message || 'Error al registrar la talla.';
              this.cdr.detectChanges();
            });
          }
        });
    }
  }

  toggleEstadoTalla(talla: Talla, event: Event): void {
    event.stopPropagation();
    const nuevoEstado = !talla.activo;
    this.tallasColoresService.cambiarEstadoTalla(talla.id_talla!, nuevoEstado)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            talla.activo = nuevoEstado;
            talla.estado = nuevoEstado ? 'ACTIVO' : 'INACTIVO';
            this.mostrarExito(res?.message || `Talla ${nuevoEstado ? 'activada' : 'desactivada'}`);
            this.aplicarFiltrosTallas();
          });
        },
        error: (err) => {
          this.mensajeError = err.error?.detail || 'No se pudo cambiar el estado de la talla.';
          this.cdr.detectChanges();
        }
      });
  }

  // --- ACCIONES COLOR ---
  abrirModalCrearColor(): void {
    this.modoEdicionColor = false;
    this.colorForm = this.inicializarColor();
    this.mensajeModalError = '';
    this.mostrarModalColor = true;
    this.cdr.detectChanges();
  }

  abrirModalEditarColor(color: ColorPrenda): void {
    this.modoEdicionColor = true;
    this.colorForm = { ...color };
    this.mensajeModalError = '';
    this.mostrarModalColor = true;
    this.cdr.detectChanges();
  }

  cerrarModalColor(): void {
    this.mostrarModalColor = false;
    this.modoEdicionColor = false;
    this.mensajeModalError = '';
    this.cdr.detectChanges();
  }

  guardarColor(): void {
    if (!this.colorForm.nombre || !this.colorForm.nombre.trim()) {
      this.mensajeModalError = 'El nombre del color es obligatorio (ej. Rosa Empolvado).';
      return;
    }
    if (!this.colorForm.codigo_hex || !this.colorForm.codigo_hex.trim()) {
      this.mensajeModalError = 'El código HEX del color es obligatorio (ej. #E8C5C8).';
      return;
    }

    this.guardando = true;
    this.mensajeModalError = '';

    const payload = {
      nombre: this.colorForm.nombre.trim(),
      codigo_hex: this.colorForm.codigo_hex.trim().toUpperCase(),
      id_empresa: this.colorForm.id_empresa ? Number(this.colorForm.id_empresa) : this.tenantActualId,
      activo: Boolean(this.colorForm.activo)
    };

    if (this.modoEdicionColor && this.colorForm.id_color) {
      this.tallasColoresService.actualizarColor(this.colorForm.id_color, payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mostrarExito(res?.message || 'Color actualizado exitosamente.');
              this.cerrarModalColor();
              this.cargarDatos();
            });
          },
          error: (err) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mensajeModalError = err.error?.detail || err.error?.message || 'Error al actualizar el color.';
              this.cdr.detectChanges();
            });
          }
        });
    } else {
      this.tallasColoresService.crearColor(payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mostrarExito(res?.message || 'Color registrado exitosamente.');
              this.cerrarModalColor();
              this.cargarDatos();
            });
          },
          error: (err) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mensajeModalError = err.error?.detail || err.error?.message || 'Error al registrar el color.';
              this.cdr.detectChanges();
            });
          }
        });
    }
  }

  toggleEstadoColor(color: ColorPrenda, event: Event): void {
    event.stopPropagation();
    const nuevoEstado = !color.activo;
    this.tallasColoresService.cambiarEstadoColor(color.id_color!, nuevoEstado)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            color.activo = nuevoEstado;
            color.estado = nuevoEstado ? 'ACTIVO' : 'INACTIVO';
            this.mostrarExito(res?.message || `Color ${nuevoEstado ? 'activado' : 'desactivado'}`);
            this.aplicarFiltrosColores();
          });
        },
        error: (err) => {
          this.mensajeError = err.error?.detail || 'No se pudo cambiar el estado del color.';
          this.cdr.detectChanges();
        }
      });
  }

  // --- ELIMINACIÓN CON REGLA DE INTEGRIDAD ---
  confirmarEliminacion(tipo: 'TALLA' | 'COLOR', item: any): void {
    this.elementoAeliminar = {
      tipo,
      id: tipo === 'TALLA' ? item.id_talla : item.id_color,
      nombre: item.nombre,
      variantes: item.total_variantes || 0
    };
    this.mostrarModalConfirmacion = true;
    this.cdr.detectChanges();
  }

  cerrarConfirmacion(): void {
    this.mostrarModalConfirmacion = false;
    this.elementoAeliminar = null;
    this.cdr.detectChanges();
  }

  ejecutarEliminacion(): void {
    if (!this.elementoAeliminar) return;

    this.guardando = true;
    const { tipo, id } = this.elementoAeliminar;

    const req$ = tipo === 'TALLA' 
      ? this.tallasColoresService.eliminarTalla(id)
      : this.tallasColoresService.eliminarColor(id);

    req$.pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.cerrarConfirmacion();
            this.mostrarExito(res?.message || 'Operación completada.');
            this.cargarDatos();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.mensajeError = err.error?.detail || 'Error al eliminar el elemento.';
            this.cerrarConfirmacion();
            this.cdr.detectChanges();
          });
        }
      });
  }

  mostrarExito(mensaje: string): void {
    this.mensajeExito = mensaje;
    setTimeout(() => {
      this.mensajeExito = '';
      this.cdr.detectChanges();
    }, 4500);
  }
}
