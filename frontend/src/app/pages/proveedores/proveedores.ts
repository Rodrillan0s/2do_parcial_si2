import {
  Component,
  OnInit,
  ChangeDetectorRef,
  inject
} from '@angular/core';

import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import {
  ProveedoresService,
  Proveedor,
  DatosProveedor
} from '../../services/proveedores';

@Component({
  selector: 'app-proveedores',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule
  ],
  templateUrl: './proveedores.html',
  styleUrl: './proveedores.css'
})
export class ProveedoresComponent implements OnInit {

  private proveedoresService = inject(ProveedoresService);
  private cdr = inject(ChangeDetectorRef);

  proveedores: Proveedor[] = [];

  cargando = false;
  guardando = false;

  busqueda = '';
  filtroEstado: 'TODOS' | 'ACTIVOS' | 'INACTIVOS' = 'TODOS';

  mostrarModal = false;
  modoEdicion = false;

  proveedorEditandoId: number | null = null;

  mensajeToast = '';
  tipoToast: 'exito' | 'error' | 'info' = 'info';

  private toastTimeout: ReturnType<typeof setTimeout> | null = null;

  formulario: DatosProveedor = {
    razon_social: '',
    nit: '',
    telefono: '',
    correo: '',
    direccion: '',
    contacto: ''
  };

  ngOnInit(): void {
    this.cargarProveedores();
  }

  cargarProveedores(): void {
    this.cargando = true;

    const soloActivos = this.filtroEstado === 'ACTIVOS';

    this.proveedoresService
      .listarProveedores(this.busqueda, soloActivos)
      .subscribe({
        next: (respuesta) => {

          if (respuesta.success && Array.isArray(respuesta.data)) {

            let datos = respuesta.data;

            if (this.filtroEstado === 'INACTIVOS') {
              datos = datos.filter(proveedor => !proveedor.estado);
            }

            this.proveedores = datos;

          } else {
            this.proveedores = [];

            this.mostrarToast(
              respuesta.message || 'No se pudieron obtener los proveedores',
              'error'
            );
          }

          this.cargando = false;
          this.cdr.detectChanges();
        },

        error: (error) => {
          this.cargando = false;

          this.proveedores = [];

          this.mostrarToast(
            this.obtenerMensajeError(
              error,
              'No se pudieron cargar los proveedores'
            ),
            'error'
          );

          this.cdr.detectChanges();
        }
      });
  }

  aplicarFiltros(): void {
    this.cargarProveedores();
  }

  limpiarFiltros(): void {
    this.busqueda = '';
    this.filtroEstado = 'TODOS';

    this.cargarProveedores();
  }

  abrirNuevoProveedor(): void {
    this.modoEdicion = false;
    this.proveedorEditandoId = null;

    this.formulario = {
      razon_social: '',
      nit: '',
      telefono: '',
      correo: '',
      direccion: '',
      contacto: ''
    };

    this.mostrarModal = true;
  }

  editarProveedor(proveedor: Proveedor): void {
    this.modoEdicion = true;
    this.proveedorEditandoId = proveedor.id_proveedor;

    this.formulario = {
      razon_social: proveedor.razon_social || '',
      nit: proveedor.nit || '',
      telefono: proveedor.telefono || '',
      correo: proveedor.correo || '',
      direccion: proveedor.direccion || '',
      contacto: proveedor.contacto || ''
    };

    this.mostrarModal = true;
  }

  cerrarModal(): void {
    if (this.guardando) {
      return;
    }

    this.mostrarModal = false;
    this.proveedorEditandoId = null;
  }

  guardarProveedor(): void {

    if (!this.validarFormulario()) {
      return;
    }

    this.guardando = true;

    const datos: DatosProveedor = {
      razon_social: this.formulario.razon_social.trim(),
      nit: this.formulario.nit.trim(),
      telefono: this.formulario.telefono.trim(),
      correo: this.formulario.correo.trim(),
      direccion: this.formulario.direccion.trim(),
      contacto: this.formulario.contacto.trim()
    };

    if (this.modoEdicion && this.proveedorEditandoId !== null) {

      this.proveedoresService
        .actualizarProveedor(
          this.proveedorEditandoId,
          datos
        )
        .subscribe({
          next: (respuesta) => {

            this.guardando = false;

            if (respuesta.success) {

              this.mostrarToast(
                respuesta.message || 'Proveedor actualizado correctamente',
                'exito'
              );

              this.mostrarModal = false;
              this.proveedorEditandoId = null;

              this.cargarProveedores();

            } else {

              this.mostrarToast(
                respuesta.message || 'No se pudo actualizar el proveedor',
                'error'
              );
            }

            this.cdr.detectChanges();
          },

          error: (error) => {

            this.guardando = false;

            this.mostrarToast(
              this.obtenerMensajeError(
                error,
                'No se pudo actualizar el proveedor'
              ),
              'error'
            );

            this.cdr.detectChanges();
          }
        });

      return;
    }

    this.proveedoresService
      .crearProveedor(datos)
      .subscribe({
        next: (respuesta) => {

          this.guardando = false;

          if (respuesta.success) {

            this.mostrarToast(
              respuesta.message || 'Proveedor registrado correctamente',
              'exito'
            );

            this.mostrarModal = false;

            this.cargarProveedores();

          } else {

            this.mostrarToast(
              respuesta.message || 'No se pudo registrar el proveedor',
              'error'
            );
          }

          this.cdr.detectChanges();
        },

        error: (error) => {

          this.guardando = false;

          this.mostrarToast(
            this.obtenerMensajeError(
              error,
              'No se pudo registrar el proveedor'
            ),
            'error'
          );

          this.cdr.detectChanges();
        }
      });
  }

  cambiarEstado(proveedor: Proveedor): void {

    const nuevoEstado = !proveedor.estado;

    const accion = nuevoEstado
      ? 'activar'
      : 'desactivar';

    const confirmado = window.confirm(
      `¿Deseas ${accion} al proveedor "${proveedor.razon_social}"?`
    );

    if (!confirmado) {
      return;
    }

    this.proveedoresService
      .cambiarEstadoProveedor(
        proveedor.id_proveedor,
        nuevoEstado
      )
      .subscribe({
        next: (respuesta) => {

          if (respuesta.success) {

            this.mostrarToast(
              respuesta.message ||
              (
                nuevoEstado
                  ? 'Proveedor activado correctamente'
                  : 'Proveedor desactivado correctamente'
              ),
              'exito'
            );

            this.cargarProveedores();

          } else {

            this.mostrarToast(
              respuesta.message || 'No se pudo cambiar el estado',
              'error'
            );
          }

          this.cdr.detectChanges();
        },

        error: (error) => {

          this.mostrarToast(
            this.obtenerMensajeError(
              error,
              'No se pudo cambiar el estado del proveedor'
            ),
            'error'
          );

          this.cdr.detectChanges();
        }
      });
  }

  validarFormulario(): boolean {

    if (!this.formulario.razon_social.trim()) {
      this.mostrarToast(
        'La razón social es obligatoria',
        'error'
      );
      return false;
    }

    if (!this.formulario.nit.trim()) {
      this.mostrarToast(
        'El NIT es obligatorio',
        'error'
      );
      return false;
    }

    if (!this.formulario.correo.trim()) {
      this.mostrarToast(
        'El correo es obligatorio',
        'error'
      );
      return false;
    }

    const correoValido =
      /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
        this.formulario.correo.trim()
      );

    if (!correoValido) {
      this.mostrarToast(
        'Ingresa un correo electrónico válido',
        'error'
      );
      return false;
    }

    return true;
  }

  mostrarToast(
    mensaje: string,
    tipo: 'exito' | 'error' | 'info' = 'info'
  ): void {

    this.mensajeToast = mensaje;
    this.tipoToast = tipo;

    if (this.toastTimeout) {
      clearTimeout(this.toastTimeout);
    }

    this.toastTimeout = setTimeout(() => {
      this.mensajeToast = '';
      this.cdr.detectChanges();
    }, 4000);
  }

  obtenerMensajeError(
    error: any,
    mensajePorDefecto: string
  ): string {

    return (
      error?.error?.detail ||
      error?.error?.message ||
      mensajePorDefecto
    );
  }

  trackByProveedor(
    index: number,
    proveedor: Proveedor
  ): number {
    return proveedor.id_proveedor;
  }
}