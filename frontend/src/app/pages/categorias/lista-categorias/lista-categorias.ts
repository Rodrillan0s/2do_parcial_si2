import { Component, OnInit, inject, ChangeDetectorRef, NgZone, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { AuthService } from '../../../services/auth';
import { Categoria, CategoriasService } from '../../../services/categorias';
import { Empresa, EmpresaService } from '../../../services/empresa';

@Component({
  selector: 'app-lista-categorias',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './lista-categorias.html'
})
export class ListaCategoriasComponent implements OnInit {
  private categoriasService = inject(CategoriasService);
  private empresaService = inject(EmpresaService);
  public authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  private ngZone = inject(NgZone);
  private destroyRef = inject(DestroyRef);
  private busquedaSubject = new Subject<string>();

  // Data
  categorias: Categoria[] = [];
  categoriasFiltradas: Categoria[] = [];
  empresas: Empresa[] = [];

  // Métricas precomputadas (evita recalcular .filter() en cada ciclo de Change Detection)
  totalCategorias: number = 0;
  totalRaiz: number = 0;
  totalSubcategorias: number = 0;
  totalActivas: number = 0;

  // Filters
  filtroEstado: string = 'TODOS'; // 'TODOS' | 'ACTIVOS' | 'INACTIVOS'
  filtroJerarquia: string = 'TODOS'; // 'TODOS' | 'RAIZ' | 'SUBCATEGORIAS'
  filtroBusqueda: string = '';
  filtroEmpresaId: number = 0;

  // UI State
  cargando: boolean = false;
  guardando: boolean = false;
  subiendoImagen: boolean = false;
  mensajeError: string = '';
  mensajeModalError: string = '';
  mensajeExito: string = '';

  // Modal Crear / Editar
  mostrarModal: boolean = false;
  modoEdicion: boolean = false;
  categoriaForm: Categoria = this.inicializarCategoria();
  previewImagenLocal: string | null = null;
  archivoSeleccionado: File | null = null;

  // Modal Detalle
  mostrarModalDetalle: boolean = false;
  categoriaSeleccionada: Categoria | null = null;

  // Modal Confirmación Desactivación / Eliminación
  mostrarModalConfirmacion: boolean = false;
  categoriaAeliminar: Categoria | null = null;

  ngOnInit(): void {
    this.busquedaSubject
      .pipe(
        debounceTime(200),
        distinctUntilChanged(),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(() => {
        this.aplicarFiltros();
      });

    if (this.esSuperAdmin) {
      this.filtroEmpresaId = this.authService.getEffectiveCompanyId() || 0;
      this.cargarEmpresasSiEsAdmin();
    }
    this.cargarCategorias();

    this.authService.companyChanged$
      .pipe(
        distinctUntilChanged((p, c) => p?.id_empresa === c?.id_empresa),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe((emp) => {
        if (this.esSuperAdmin) {
          const newId = emp ? emp.id_empresa : 0;
          if (this.filtroEmpresaId !== newId) {
            this.filtroEmpresaId = newId;
            this.cargarCategorias();
          }
        }
      });
  }

  onBusquedaInput(): void {
    this.busquedaSubject.next(this.filtroBusqueda);
  }

  trackByCategoriaId(index: number, item: Categoria): number {
    return item.id_categoria || index;
  }

  trackByEmpresaId(index: number, item: Empresa): number {
    return item.id_empresa || index;
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

  inicializarCategoria(): Categoria {
    return {
      nombre: '',
      descripcion: '',
      id_padre: null,
      id_empresa: this.esSuperAdmin ? (this.filtroEmpresaId || this.tenantActualId) : this.tenantActualId,
      imagen_url: null,
      imagen_public_id: null,
      activo: true,
      estado: 'ACTIVO'
    };
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

  cargarCategorias(): void {
    this.cargando = true;
    this.mensajeError = '';

    const params: any = {};
    if (this.filtroEmpresaId > 0) {
      params.id_empresa = this.filtroEmpresaId;
    }

    this.categoriasService.listarCategorias(params)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.cargando = false;
            if (res?.success) {
              this.categorias = res.data || [];
              this.aplicarFiltros();
            } else {
              this.mensajeError = res?.message || 'Error al obtener categorías';
            }
            this.cdr.detectChanges();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.cargando = false;
            this.mensajeError = err.error?.detail || err.error?.message || 'Error de conexión con el servidor.';
            this.cdr.detectChanges();
          });
        }
      });
  }

  aplicarFiltros(): void {
    let list = [...this.categorias];

    // Filtro por Estado
    if (this.filtroEstado === 'ACTIVOS') {
      list = list.filter(c => c.activo === true);
    } else if (this.filtroEstado === 'INACTIVOS') {
      list = list.filter(c => c.activo === false);
    }

    // Filtro por Jerarquía
    if (this.filtroJerarquia === 'RAIZ') {
      list = list.filter(c => c.es_raiz === true || !c.id_padre);
    } else if (this.filtroJerarquia === 'SUBCATEGORIAS') {
      list = list.filter(c => c.id_padre !== null && c.id_padre !== undefined);
    }

    // Filtro de Búsqueda
    if (this.filtroBusqueda.trim()) {
      const q = this.filtroBusqueda.toLowerCase().trim();
      list = list.filter(c => 
        c.nombre.toLowerCase().includes(q) || 
        (c.descripcion && c.descripcion.toLowerCase().includes(q)) ||
        (c.nombre_padre && c.nombre_padre.toLowerCase().includes(q))
      );
    }

    this.categoriasFiltradas = list;
    this.actualizarMetricas();
    this.cdr.detectChanges();
  }

  private actualizarMetricas(): void {
    this.totalCategorias = this.categorias.length;
    let raiz = 0;
    let sub = 0;
    let activas = 0;
    for (const c of this.categorias) {
      if (c.es_raiz || !c.id_padre) {
        raiz++;
      } else {
        sub++;
      }
      if (c.activo) {
        activas++;
      }
    }
    this.totalRaiz = raiz;
    this.totalSubcategorias = sub;
    this.totalActivas = activas;
  }

  // Opciones para el combo de categoría padre (evitar la misma y ciclos)
  getCategoriasPadreDisponibles(): Categoria[] {
    return this.categorias.filter(c => {
      // Si estamos editando, no puede ser ella misma
      if (this.modoEdicion && this.categoriaForm.id_categoria) {
        if (c.id_categoria === this.categoriaForm.id_categoria) return false;
      }
      return true;
    });
  }

  // Modal Actions
  abrirModalCrear(): void {
    this.modoEdicion = false;
    this.categoriaForm = this.inicializarCategoria();
    this.previewImagenLocal = null;
    this.archivoSeleccionado = null;
    this.mensajeModalError = '';
    this.mostrarModal = true;
    this.cdr.detectChanges();
  }

  abrirModalEditar(cat: Categoria): void {
    this.modoEdicion = true;
    this.categoriaForm = { ...cat };
    this.previewImagenLocal = cat.imagen_url || null;
    this.archivoSeleccionado = null;
    this.mensajeModalError = '';
    this.mostrarModal = true;
    this.cdr.detectChanges();
  }

  cerrarModal(): void {
    this.mostrarModal = false;
    this.modoEdicion = false;
    this.mensajeModalError = '';
    this.previewImagenLocal = null;
    this.archivoSeleccionado = null;
    this.cdr.detectChanges();
  }

  abrirDetalle(cat: Categoria): void {
    this.categoriaSeleccionada = cat;
    this.mostrarModalDetalle = true;
    this.cdr.detectChanges();
  }

  cerrarDetalle(): void {
    this.mostrarModalDetalle = false;
    this.categoriaSeleccionada = null;
    this.cdr.detectChanges();
  }

  // Manejo de Imagen Cloudinary
  onFileSelected(event: any): void {
    const file = event.target.files?.[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        this.mensajeModalError = 'Por favor seleccione un archivo de imagen válido (JPG, PNG, WEBP).';
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        this.mensajeModalError = 'El tamaño de la imagen no debe superar los 10 MB.';
        return;
      }

      this.archivoSeleccionado = file;
      this.mensajeModalError = '';

      // Preview local instantáneo
      const reader = new FileReader();
      reader.onload = () => {
        this.previewImagenLocal = reader.result as string;
        this.cdr.detectChanges();
      };
      reader.readAsDataURL(file);
    }
  }

  eliminarImagenSeleccionada(): void {
    this.archivoSeleccionado = null;
    this.previewImagenLocal = null;
    this.categoriaForm.imagen_url = null;
    this.categoriaForm.imagen_public_id = null;
    this.cdr.detectChanges();
  }

  guardarCategoria(): void {
    if (!this.categoriaForm.nombre || !this.categoriaForm.nombre.trim()) {
      this.mensajeModalError = 'El nombre de la categoría es obligatorio.';
      return;
    }

    if (this.modoEdicion && this.categoriaForm.id_padre && this.categoriaForm.id_padre === this.categoriaForm.id_categoria) {
      this.mensajeModalError = 'Una categoría no puede ser su propia categoría padre.';
      return;
    }

    this.guardando = true;
    this.mensajeModalError = '';

    // Si hay archivo pendiente de subida a Cloudinary, subirlo primero
    if (this.archivoSeleccionado) {
      this.subiendoImagen = true;
      this.categoriasService.subirImagen(this.archivoSeleccionado)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (cloudRes) => {
            this.subiendoImagen = false;
            this.categoriaForm.imagen_url = cloudRes.url;
            this.categoriaForm.imagen_public_id = cloudRes.public_id;
            this.ejecutarGuardadoBackend();
          },
          error: (cloudErr) => {
            this.subiendoImagen = false;
            this.guardando = false;
            this.mensajeModalError = 'Error al subir la imagen a Cloudinary: ' + (cloudErr.error?.detail || cloudErr.message || 'Error de red');
            this.cdr.detectChanges();
          }
        });
    } else {
      this.ejecutarGuardadoBackend();
    }
  }

  private ejecutarGuardadoBackend(): void {
    const payload: any = {
      nombre: this.categoriaForm.nombre.trim(),
      descripcion: (this.categoriaForm.descripcion || '').trim(),
      id_padre: this.categoriaForm.id_padre ? Number(this.categoriaForm.id_padre) : null,
      id_empresa: this.categoriaForm.id_empresa ? Number(this.categoriaForm.id_empresa) : this.tenantActualId,
      activo: Boolean(this.categoriaForm.activo),
      imagen_url: this.categoriaForm.imagen_url || null,
      imagen_public_id: this.categoriaForm.imagen_public_id || null
    };

    if (this.modoEdicion && this.categoriaForm.id_categoria) {
      this.categoriasService.actualizarCategoria(this.categoriaForm.id_categoria, payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mostrarExito(res?.message || 'Categoría actualizada correctamente');
              this.cerrarModal();
              this.cargarCategorias();
            });
          },
          error: (err) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mensajeModalError = err.error?.detail || err.error?.message || 'Error al actualizar la categoría';
              this.cdr.detectChanges();
            });
          }
        });
    } else {
      this.categoriasService.crearCategoria(payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mostrarExito(res?.message || 'Categoría creada exitosamente');
              this.cerrarModal();
              this.cargarCategorias();
            });
          },
          error: (err) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.mensajeModalError = err.error?.detail || err.error?.message || 'Error al registrar la categoría';
              this.cdr.detectChanges();
            });
          }
        });
    }
  }

  // Cambio de estado directo
  toggleEstado(cat: Categoria, event: Event): void {
    event.stopPropagation();
    const nuevoEstado = !cat.activo;
    
    this.categoriasService.cambiarEstadoCategoria(cat.id_categoria!, nuevoEstado)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            cat.activo = nuevoEstado;
            cat.estado = nuevoEstado ? 'ACTIVO' : 'INACTIVO';
            this.mostrarExito(res?.message || `Categoría ${nuevoEstado ? 'activada' : 'desactivada'}`);
            this.aplicarFiltros();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.mensajeError = err.error?.detail || 'No se pudo cambiar el estado de la categoría';
            this.cdr.detectChanges();
          });
        }
      });
  }

  // Eliminación con regla de integridad
  confirmarEliminacion(cat: Categoria): void {
    this.categoriaAeliminar = cat;
    this.mostrarModalConfirmacion = true;
    this.cdr.detectChanges();
  }

  cerrarConfirmacion(): void {
    this.mostrarModalConfirmacion = false;
    this.categoriaAeliminar = null;
    this.cdr.detectChanges();
  }

  ejecutarEliminacion(): void {
    if (!this.categoriaAeliminar || !this.categoriaAeliminar.id_categoria) return;

    this.guardando = true;
    this.categoriasService.eliminarCategoria(this.categoriaAeliminar.id_categoria)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.cerrarConfirmacion();
            this.mostrarExito(res?.message || 'Operación completada.');
            this.cargarCategorias();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.guardando = false;
            this.mensajeError = err.error?.detail || 'Error al eliminar/desactivar la categoría.';
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
