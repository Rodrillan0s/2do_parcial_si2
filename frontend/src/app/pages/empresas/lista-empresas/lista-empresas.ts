import { Component, OnInit, inject, ChangeDetectorRef, NgZone, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AuthService } from '../../../services/auth';
import { Empresa, EmpresaService } from '../../../services/empresa';
import { extraerMensajeError } from '../../../utils/error-helper';

@Component({
  selector: 'app-lista-empresas',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './lista-empresas.html'
})
export class ListaEmpresasComponent implements OnInit {

  private empresaService = inject(EmpresaService);
  public authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  private ngZone = inject(NgZone);
  private destroyRef = inject(DestroyRef);

  empresas: Empresa[] = [];
  empresasFiltradas: Empresa[] = [];

  filtroEstado: string = '';
  filtroBusqueda: string = '';

  cargando: boolean = false;
  guardando: boolean = false;
  mensajeError: string = '';
  mensajeModalError: string = '';
  mensajeExito: string = '';

  mostrarModal: boolean = false;
  modoEdicion: boolean = false;

  empresaForm: Empresa = this.inicializarEmpresa();

  totalEmpresas: number = 0;
  empresasActivas: number = 0;
  empresasInactivas: number = 0;

  get esSuperAdmin(): boolean {
    const u = this.authService.obtenerUsuario();
    if (!u) return false;
    const rol = (u.nombre_rol || '').toUpperCase();
    const roles = (u.roles || []).map(r => r.toUpperCase());
    return u.id_rol === 1 || rol === 'ADMINISTRADOR' || roles.includes('ADMINISTRADOR');
  }

  async ngOnInit() {
    this.cargando = true;
    let intentos = 0;

    while (!this.authService.obtenerToken() && intentos < 10) {
      await new Promise(resolve => setTimeout(resolve, 50));
      intentos++;
    }

    if (this.authService.obtenerToken()) {
      this.cargarEmpresas();
    } else {
      this.cargando = false;
      this.mensajeError = 'No se pudo iniciar sesión. Por favor recarga la página.';
    }
  }

  inicializarEmpresa(): Empresa {
    return {
      nombre_empresa: '',
      razon_social: '',
      nit: '',
      correo: '',
      telefono: '',
      direccion_fiscal: '',
      ciudad: 'Santa Cruz',
      logo: '',
      estado: 'ACTIVO'
    };
  }

  cargarEmpresas() {
    this.cargando = true;
    this.mensajeError = '';

    this.empresaService.listarEmpresas()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            if (res && res.success) {
              this.empresas = [...(res.data || [])];
              this.aplicarFiltros();
            } else {
              this.mensajeError = res.message || 'Error al obtener empresas.';
            }
            this.cargando = false;
            this.cdr.detectChanges();
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            this.mensajeError = extraerMensajeError(err, 'Error de conexión al cargar las empresas.');
            this.cargando = false;
            this.cdr.detectChanges();
          });
        }
      });
  }

  aplicarFiltros() {
    let lista = [...this.empresas];

    if (this.filtroEstado !== '') {
      lista = lista.filter(e => e.estado === this.filtroEstado);
    }

    if (this.filtroBusqueda && this.filtroBusqueda.trim().length > 0) {
      const q = this.filtroBusqueda.trim().toLowerCase();
      lista = lista.filter(e => 
        (e.nombre_empresa && e.nombre_empresa.toLowerCase().includes(q)) ||
        (e.razon_social && e.razon_social.toLowerCase().includes(q)) ||
        (e.nit && e.nit.toLowerCase().includes(q)) ||
        (e.ciudad && e.ciudad.toLowerCase().includes(q))
      );
    }

    this.empresasFiltradas = lista;
    this.actualizarMetricas();
  }

  actualizarMetricas() {
    this.totalEmpresas = this.empresas.length;
    this.empresasActivas = this.empresas.filter(e => e.estado === 'ACTIVO').length;
    this.empresasInactivas = this.empresas.filter(e => e.estado === 'INACTIVO').length;
  }

  obtenerIniciales(nombre: string): string {
    if (!nombre) return 'AU';
    const partes = nombre.trim().split(' ');
    if (partes.length >= 2) {
      return (partes[0][0] + partes[1][0]).toUpperCase();
    }
    return nombre.substring(0, 2).toUpperCase();
  }

  abrirModalNuevo() {
    this.modoEdicion = false;
    this.mensajeModalError = '';
    this.empresaForm = this.inicializarEmpresa();
    this.mostrarModal = true;
    this.cdr.detectChanges();
  }

  abrirModalEditar(empresa: Empresa) {
    this.modoEdicion = true;
    this.mensajeModalError = '';
    this.empresaForm = { 
      ...empresa,
      razon_social: empresa.razon_social || empresa.nombre_empresa,
      direccion_fiscal: empresa.direccion_fiscal || '',
      ciudad: empresa.ciudad || 'Santa Cruz'
    };
    this.mostrarModal = true;
    this.cdr.detectChanges();
  }

  cerrarModal() {
    this.mostrarModal = false;
    this.mensajeModalError = '';
    this.guardando = false;
    this.cdr.detectChanges();
  }

  mostrarNotificacionExito(mensaje: string) {
    this.mensajeExito = mensaje;
    setTimeout(() => {
      this.mensajeExito = '';
      this.cdr.detectChanges();
    }, 4500);
  }

  guardarEmpresa() {
    this.mensajeModalError = '';

    // Validaciones de campos obligatorios
    if (!this.empresaForm.nombre_empresa || !this.empresaForm.nombre_empresa.trim()) {
      this.mensajeModalError = 'El Nombre comercial es obligatorio.';
      return;
    }

    if (!this.empresaForm.razon_social || !this.empresaForm.razon_social.trim()) {
      this.empresaForm.razon_social = this.empresaForm.nombre_empresa;
    }

    if (!this.empresaForm.nit || !String(this.empresaForm.nit).trim()) {
      this.mensajeModalError = 'El NIT / Identificación fiscal es obligatorio.';
      return;
    }

    if (!this.empresaForm.correo || !this.empresaForm.correo.trim()) {
      this.mensajeModalError = 'El correo empresarial es obligatorio.';
      return;
    }

    const emailRegex = /^[\w\.-]+@[\w\.-]+\.\w+$/;
    if (!emailRegex.test(this.empresaForm.correo.trim())) {
      this.mensajeModalError = 'El formato del correo electrónico empresarial no es válido.';
      return;
    }

    if (!this.empresaForm.telefono || !this.empresaForm.telefono.trim()) {
      this.mensajeModalError = 'El teléfono de contacto es obligatorio.';
      return;
    }

    if (!this.empresaForm.direccion_fiscal || !this.empresaForm.direccion_fiscal.trim()) {
      this.mensajeModalError = 'La dirección fiscal es obligatoria.';
      return;
    }

    if (!this.empresaForm.ciudad || !this.empresaForm.ciudad.trim()) {
      this.mensajeModalError = 'La ciudad de operación es obligatoria.';
      return;
    }

    this.guardando = true;
    this.cdr.detectChanges();

    const payload: Empresa = {
      ...this.empresaForm,
      nombre_empresa: this.empresaForm.nombre_empresa.trim().toUpperCase(),
      razon_social: this.empresaForm.razon_social.trim().toUpperCase(),
      nit: String(this.empresaForm.nit).trim(),
      correo: this.empresaForm.correo.trim().toLowerCase(),
      telefono: this.empresaForm.telefono.trim(),
      direccion_fiscal: this.empresaForm.direccion_fiscal.trim(),
      ciudad: this.empresaForm.ciudad.trim(),
      logo: this.empresaForm.logo ? this.empresaForm.logo.trim() : '',
      estado: this.empresaForm.estado || 'ACTIVO'
    };

    if (this.modoEdicion) {
      if (!this.empresaForm.id_empresa) {
        this.mensajeModalError = 'No se encontró el ID de la empresa a actualizar.';
        this.guardando = false;
        return;
      }

      this.empresaService.actualizarEmpresa(this.empresaForm.id_empresa, payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.cerrarModal();
              this.cargarEmpresas();
              this.mostrarNotificacionExito(`¡Tenant '${payload.nombre_empresa}' actualizado con éxito!`);
            });
          },
          error: (err) => {
            this.ngZone.run(() => {
              this.mensajeModalError = extraerMensajeError(err, 'Error al actualizar la empresa.');
              this.guardando = false;
              this.cdr.detectChanges();
            });
          }
        });
    } else {
      this.empresaService.crearEmpresa(payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res) => {
            this.ngZone.run(() => {
              this.guardando = false;
              this.cerrarModal();
              this.cargarEmpresas();
              this.mostrarNotificacionExito(`¡Tenant '${payload.nombre_empresa}' registrado exitosamente en estado ACTIVO!`);
            });
          },
          error: (err) => {
            this.ngZone.run(() => {
              this.mensajeModalError = extraerMensajeError(err, 'Error al registrar la empresa. Verifique los datos.');
              this.guardando = false;
              this.cdr.detectChanges();
            });
          }
        });
    }
  }

  eliminarEmpresa(idEmpresa?: number, nombreEmpresa?: string) {
    if (!idEmpresa) return;

    const nombre = nombreEmpresa || 'esta empresa';
    const confirmar = confirm(`¿Está seguro que desea desactivar ${nombre}? Sus sucursales y operaciones comerciales quedarán suspendidas sin eliminar sus registros históricos.`);
    if (!confirmar) return;

    this.cargando = true;

    this.empresaService.eliminarEmpresa(idEmpresa)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.ngZone.run(() => {
            this.cargarEmpresas();
            const msg = res?.message || 'Empresa desactivada exitosamente.';
            this.mostrarNotificacionExito(msg);
          });
        },
        error: (err) => {
          this.ngZone.run(() => {
            const errorMsg = extraerMensajeError(err, 'Error al desactivar la empresa.');
            alert(errorMsg);
            this.cargando = false;
            this.cdr.detectChanges();
          });
        }
      });
  }
}