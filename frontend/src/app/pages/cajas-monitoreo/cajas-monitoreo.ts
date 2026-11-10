import { Component, OnInit, inject, ChangeDetectorRef, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { AuthService } from '../../services/auth';
import { EmpresaService, Empresa } from '../../services/empresa';
import { SucursalService, Sucursal } from '../../services/sucursales';
import {
  CajaService,
  CajaMonitoreoItem,
  SesionActivaMonitoreo,
  SesionCajaHistorialItem
} from '../../services/caja';

@Component({
  selector: 'app-cajas-monitoreo',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './cajas-monitoreo.html',
  styleUrls: ['./cajas-monitoreo.css']
})
export class CajasMonitoreoComponent implements OnInit {
  public authService = inject(AuthService);
  private cajaService = inject(CajaService);
  private empresaService = inject(EmpresaService);
  private sucursalService = inject(SucursalService);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);

  // --- CONTROL DE PESTAÑAS ---
  pestanaActiva: 'cajas' | 'historial' = 'cajas';

  // --- DATOS PRINCIPALES ---
  cajas: CajaMonitoreoItem[] = [];
  cajasFiltradas: CajaMonitoreoItem[] = [];
  historialSesiones: SesionCajaHistorialItem[] = [];

  // --- KPIS GLOBALES ---
  totalCajas: number = 0;
  totalAbiertas: number = 0;
  totalCerradas: number = 0;
  efectivoTotalEnCajas: number = 0;

  // --- FILTROS Y BÚSQUEDA ---
  empresas: Empresa[] = [];
  sucursales: Sucursal[] = [];

  idEmpresaFiltro: number | null = null;
  idSucursalFiltro: number | null = null;
  estadoFiltro: string = 'TODAS';
  busquedaTexto: string = '';

  // --- ESTADOS DE CARGA Y NOTIFICACIONES ---
  cargando: boolean = false;
  cargandoHistorial: boolean = false;
  mensajeExito: string = '';
  mensajeError: string = '';

  // --- MODAL DE DETALLE / ARQUEO EN VIVO ---
  mostrarModalArqueo: boolean = false;
  cajaSeleccionada: CajaMonitoreoItem | null = null;
  sesionDetalle: any = null;
  cargandoDetalle: boolean = false;

  // --- MODAL NUEVA CAJA ---
  mostrarModalCrear: boolean = false;
  creandoCaja: boolean = false;
  nuevaCajaNombre: string = '';
  nuevaCajaSucursalId: number | null = null;
  nuevaCajaCodigo: string = '';

  // --- PERMISOS Y ALCANCES ---
  esSuperadmin: boolean = false;
  esAdminTienda: boolean = false;
  esEncargado: boolean = false;

  ngOnInit(): void {
    this.determinarRolYAlcance();
    this.cargarEmpresasYSucursales();
    this.cargarMonitoreoCajas();
  }

  determinarRolYAlcance(): void {
    const lvl = this.authService.getAuthorityLevel();
    const scope = this.authService.getScopeLevel();
    this.esSuperadmin = (lvl === 1 || scope === 'PLATAFORMA');
    this.esAdminTienda = (lvl === 3 || scope === 'EMPRESA');
    this.esEncargado = (lvl === 4 || scope === 'SUCURSAL');

    // Inicializar filtros según contexto
    const user = this.authService.obtenerUsuario();
    if (!this.esSuperadmin && user?.id_empresa) {
      this.idEmpresaFiltro = user.id_empresa;
    }
    if (this.esEncargado && user?.sucursales && user.sucursales.length > 0) {
      this.idSucursalFiltro = user.sucursales[0];
    }
  }

  cargarEmpresasYSucursales(): void {
    if (this.esSuperadmin) {
      this.empresaService.listarEmpresas()
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res: any) => {
            this.empresas = res?.data || (Array.isArray(res) ? res : []);
            this.cdr.detectChanges();
          },
          error: (err: any) => console.error('Error cargando empresas:', err)
        });
    }

    const empId = this.idEmpresaFiltro || undefined;
    this.sucursalService.listarSucursales(empId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.sucursales = res?.data || [];
          this.cdr.detectChanges();
        },
        error: (err) => console.error('Error cargando sucursales:', err)
      });
  }

  onEmpresaChange(): void {
    this.idSucursalFiltro = null;
    const empId = this.idEmpresaFiltro || undefined;
    this.sucursalService.listarSucursales(empId, true)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.sucursales = res?.data || [];
          this.cargarMonitoreoCajas();
        }
      });
  }

  onFiltroChange(): void {
    this.cargarMonitoreoCajas();
    if (this.pestanaActiva === 'historial') {
      this.cargarHistorial();
    }
  }

  cargarMonitoreoCajas(): void {
    this.cargando = true;
    this.mensajeError = '';

    const empId = this.idEmpresaFiltro || undefined;
    const sucId = this.idSucursalFiltro || undefined;

    this.cajaService.monitorearCajas(empId, sucId, this.estadoFiltro)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.cargando = false;
          if (res?.success) {
            this.cajas = res.cajas || [];
            this.totalCajas = res.total_cajas || this.cajas.length;
            this.totalAbiertas = res.total_abiertas || 0;
            this.totalCerradas = res.total_cerradas || 0;
            this.efectivoTotalEnCajas = res.efectivo_total_en_cajas || 0;
            this.aplicarFiltroBusqueda();
          } else {
            this.mensajeError = 'No se pudo obtener el estado de las cajas.';
          }
          this.cdr.detectChanges();
        },
        error: (err) => {
          this.cargando = false;
          this.mensajeError = err?.error?.detail || err?.message || 'Error al comunicarse con el servidor.';
          this.cdr.detectChanges();
        }
      });
  }

  aplicarFiltroBusqueda(): void {
    const q = (this.busquedaTexto || '').toLowerCase().trim();
    if (!q) {
      this.cajasFiltradas = [...this.cajas];
      return;
    }
    this.cajasFiltradas = this.cajas.filter(c => 
      c.nombre.toLowerCase().includes(q) ||
      c.codigo_caja.toLowerCase().includes(q) ||
      c.sucursal_nombre.toLowerCase().includes(q) ||
      c.empresa_nombre.toLowerCase().includes(q) ||
      (c.sesion_activa?.cajero_nombre && c.sesion_activa.cajero_nombre.toLowerCase().includes(q))
    );
  }

  cargarHistorial(): void {
    this.cargandoHistorial = true;
    const empId = this.idEmpresaFiltro || undefined;
    const sucId = this.idSucursalFiltro || undefined;

    this.cajaService.obtenerHistorialSesiones(empId, sucId, undefined, 50)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.cargandoHistorial = false;
          if (res?.success) {
            this.historialSesiones = res.sesiones || [];
          }
          this.cdr.detectChanges();
        },
        error: (err) => {
          this.cargandoHistorial = false;
          console.error('Error cargando historial de sesiones:', err);
          this.cdr.detectChanges();
        }
      });
  }

  cambiarPestana(p: 'cajas' | 'historial'): void {
    this.pestanaActiva = p;
    if (p === 'historial' && this.historialSesiones.length === 0) {
      this.cargarHistorial();
    }
  }

  // --- MODAL DE DETALLE / ARQUEO EN VIVO ---
  abrirModalArqueo(caja: CajaMonitoreoItem): void {
    this.cajaSeleccionada = caja;
    this.mostrarModalArqueo = true;
    this.sesionDetalle = null;

    if (caja.sesion_activa?.id_sesion_caja) {
      this.cargandoDetalle = true;
      this.cajaService.obtenerResumenCaja(caja.sesion_activa.id_sesion_caja)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (res) => {
            this.cargandoDetalle = false;
            this.sesionDetalle = res?.resumen || res;
            this.cdr.detectChanges();
          },
          error: (err) => {
            this.cargandoDetalle = false;
            console.error('Error obteniendo resumen en vivo:', err);
            this.cdr.detectChanges();
          }
        });
    }
  }

  cerrarModalArqueo(): void {
    this.mostrarModalArqueo = false;
    this.cajaSeleccionada = null;
    this.sesionDetalle = null;
  }

  // --- CREAR NUEVA CAJA ---
  abrirModalCrear(): void {
    this.mostrarModalCrear = true;
    this.nuevaCajaNombre = '';
    this.nuevaCajaCodigo = '';
    this.nuevaCajaSucursalId = this.idSucursalFiltro || (this.sucursales.length > 0 ? this.sucursales[0].id_sucursal || null : null);
  }

  cerrarModalCrear(): void {
    this.mostrarModalCrear = false;
  }

  guardarNuevaCaja(): void {
    if (!this.nuevaCajaNombre.trim()) {
      this.mensajeError = 'Debe ingresar un nombre para la caja registradora.';
      return;
    }
    if (!this.nuevaCajaSucursalId) {
      this.mensajeError = 'Debe seleccionar una sucursal.';
      return;
    }

    const suc = this.sucursales.find(s => s.id_sucursal === this.nuevaCajaSucursalId);
    const empId = suc?.id_empresa || this.idEmpresaFiltro || undefined;

    this.creandoCaja = true;
    this.cajaService.crearCaja({
      id_sucursal: this.nuevaCajaSucursalId,
      id_empresa: empId,
      nombre: this.nuevaCajaNombre.trim(),
      codigo_caja: this.nuevaCajaCodigo ? this.nuevaCajaCodigo.trim() : undefined
    }).pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.creandoCaja = false;
          this.mostrarModalCrear = false;
          this.mensajeExito = res?.message || 'Caja creada exitosamente.';
          this.cargarMonitoreoCajas();
          setTimeout(() => this.mensajeExito = '', 5000);
        },
        error: (err) => {
          this.creandoCaja = false;
          this.mensajeError = err?.error?.detail || err?.message || 'Error al crear la caja.';
          this.cdr.detectChanges();
        }
      });
  }

  // --- NAVEGACIÓN RÁPIDA ---
  irAlTerminalPos(caja: CajaMonitoreoItem): void {
    this.router.navigate(['/admin/caja']);
  }

  formatearDiferencia(dif: number | null | undefined): string {
    if (dif === null || dif === undefined) return '—';
    if (dif === 0) return '✓ Cuadrada';
    if (dif > 0) return `+Bs. ${dif.toFixed(2)}`;
    return `-Bs. ${(-dif).toFixed(2)}`;
  }

  obtenerClaseDiferencia(dif: number | null | undefined): string {
    if (dif === null || dif === undefined) return 'text-zinc-400';
    if (dif === 0) return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300';
    if (dif > 0) return 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300';
    return 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300';
  }
}
