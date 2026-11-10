import { Component, OnInit, ChangeDetectorRef, inject, DestroyRef } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { BitacoraService, BitacoraEvent } from '../../../services/bitacora';
import { AuthService } from '../../../services/auth';
import { EmpresaService, Empresa } from '../../../services/empresa';

@Component({
  selector: 'app-lista-bitacora',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './lista-bitacora.html',
  styleUrls: ['./lista-bitacora.css'],
  providers: [DatePipe]
})
export class ListaBitacoraComponent implements OnInit {
  private bitacoraService = inject(BitacoraService);
  public authService = inject(AuthService);
  private empresaService = inject(EmpresaService);
  private cdr = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);

  eventos: BitacoraEvent[] = [];
  cargando: boolean = false;
  cargandoMas: boolean = false;
  
  // Contexto Multi-Tenant & Alcance
  empresasDisponibles: Empresa[] = [];
  cargandoEmpresas: boolean = false;

  get esSuperAdmin(): boolean {
    return this.authService.getScopeLevel() === 'PLATAFORMA';
  }

  get empresaActivaId(): number | null {
    return this.authService.getEffectiveCompanyId();
  }

  get empresaActivaNombre(): string {
    return this.authService.getEffectiveCompanyName();
  }

  // Paginación rápida (por defecto 10 registros para máxima velocidad de respuesta)
  page: number = 1;
  limit: number = 10;
  total: number = 0;
  pages: number = 0;
  Math = Math;

  // Filtros
  filtros: {
    modulo: string;
    accion: string;
    nivel: string;
    resultado: string;
    fecha_desde: string;
    fecha_hasta: string;
    search: string;
    id_empresa: string;
  } = {
    modulo: '',
    accion: '',
    nivel: '',
    resultado: '',
    fecha_desde: '',
    fecha_hasta: '',
    search: '',
    id_empresa: ''
  };

  // Modal Detalles
  eventoSeleccionado: BitacoraEvent | null = null;
  cargandoDetalle: boolean = false;
  copiadoExitoso: boolean = false;

  ngOnInit(): void {
    if (this.esSuperAdmin) {
      this.cargarEmpresas();
      const eff = this.authService.getEffectiveCompanyId();
      this.filtros.id_empresa = eff ? String(eff) : '';
    } else {
      const eff = this.authService.getEffectiveCompanyId();
      this.filtros.id_empresa = eff ? String(eff) : '';
    }

    this.cargarEventos();

    this.authService.companyChanged$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(emp => {
        if (this.esSuperAdmin) {
          const nueva = emp ? String(emp.id_empresa) : '';
          if (this.filtros.id_empresa !== nueva) {
            this.filtros.id_empresa = nueva;
            this.page = 1;
            this.cargarEventos(false);
            this.cdr.detectChanges();
          }
        }
      });
  }

  cargarEmpresas(): void {
    this.cargandoEmpresas = true;
    this.empresaService.listarEmpresas()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res: any) => {
          this.cargandoEmpresas = false;
          this.empresasDisponibles = (res?.data || []).filter((e: Empresa) => e.estado === 'ACTIVO');
          this.cdr.detectChanges();
        },
        error: () => {
          this.cargandoEmpresas = false;
          this.cdr.detectChanges();
        }
      });
  }

  seleccionarEmpresaDirecta(emp: Empresa): void {
    if (emp && emp.id_empresa) {
      this.authService.setSelectedCompany({
        id_empresa: emp.id_empresa,
        nombre_empresa: emp.nombre_empresa
      });
    }
  }

  cargarEventos(acumular: boolean = false): void {
    if (acumular) {
      this.cargandoMas = true;
    } else {
      this.cargando = true;
    }
    this.cdr.detectChanges();

    this.bitacoraService.obtenerEventos(this.filtros, this.page, this.limit).subscribe({
      next: (res) => {
        if (res && res.success) {
          if (acumular) {
            this.eventos = [...this.eventos, ...(res.data || [])];
          } else {
            this.eventos = res.data || [];
          }
          this.total = res.total || 0;
          this.pages = res.pages || 1;
        }
        this.cargando = false;
        this.cargandoMas = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error cargando bitácora:', err);
        this.cargando = false;
        this.cargandoMas = false;
        this.cdr.detectChanges();
      }
    });
  }

  aplicarFiltros(): void {
    this.page = 1;
    this.cargarEventos(false);
  }

  limpiarFiltros(): void {
    this.filtros = {
      modulo: '',
      accion: '',
      nivel: '',
      resultado: '',
      fecha_desde: '',
      fecha_hasta: '',
      search: '',
      id_empresa: this.esSuperAdmin ? (this.empresaActivaId ? String(this.empresaActivaId) : '') : (this.authService.getEffectiveCompanyId() ? String(this.authService.getEffectiveCompanyId()) : '')
    };
    this.page = 1;
    this.cargarEventos(false);
  }

  cambiarPagina(nuevaPagina: number): void {
    if (nuevaPagina >= 1 && nuevaPagina <= this.pages && nuevaPagina !== this.page) {
      this.page = nuevaPagina;
      this.cargarEventos(false);
    }
  }

  paginaSiguiente(): void {
    if (this.page < this.pages) {
      this.page++;
      this.cargarEventos(false);
    }
  }

  paginaAnterior(): void {
    if (this.page > 1) {
      this.page--;
      this.cargarEventos(false);
    }
  }

  cargarMasRegistros(): void {
    if (this.page < this.pages) {
      this.page++;
      this.cargarEventos(true);
    }
  }

  cambiarLimite(nuevoLimite: number): void {
    this.limit = nuevoLimite;
    this.page = 1;
    this.cargarEventos(false);
  }

  verDetalles(evento: BitacoraEvent): void {
    this.eventoSeleccionado = evento;
    this.cargandoDetalle = true;
    this.copiadoExitoso = false;
    this.cdr.detectChanges();
    
    this.bitacoraService.obtenerDetalleEvento(evento.id_bitacora).subscribe({
      next: (res) => {
        if (res && res.success) {
          this.eventoSeleccionado = res.data;
        }
        this.cargandoDetalle = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error al cargar los detalles del evento:', err);
        this.cargandoDetalle = false;
        this.cdr.detectChanges();
      }
    });
  }

  cerrarModal(): void {
    this.eventoSeleccionado = null;
    this.cargandoDetalle = false;
    this.copiadoExitoso = false;
  }

  copiarJSON(objeto: any): void {
    if (!objeto) return;
    const texto = JSON.stringify(objeto, null, 2);
    navigator.clipboard.writeText(texto).then(() => {
      this.copiadoExitoso = true;
      this.cdr.detectChanges();
      setTimeout(() => {
        this.copiadoExitoso = false;
        this.cdr.detectChanges();
      }, 2500);
    });
  }

  getNivelBadgeClass(nivel: string): string {
    switch ((nivel || '').toUpperCase()) {
      case 'INFO':
        return 'bg-sky-500/10 text-sky-400 border-sky-500/30';
      case 'WARNING':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'CRITICAL':
      case 'ERROR':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      default:
        return 'bg-zinc-800 text-zinc-400 border-zinc-700';
    }
  }

  getNivelDotClass(nivel: string): string {
    switch ((nivel || '').toUpperCase()) {
      case 'INFO': return 'bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.6)]';
      case 'WARNING': return 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]';
      case 'CRITICAL':
      case 'ERROR': return 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]';
      default: return 'bg-zinc-400';
    }
  }

  getModuloIcon(modulo: string): string {
    switch ((modulo || '').toUpperCase()) {
      case 'AUTENTICACION': return 'ph ph-shield-key';
      case 'PERFIL': return 'ph ph-user-circle-gear';
      case 'USUARIOS': return 'ph ph-users-three';
      case 'ROLES': return 'ph ph-key';
      case 'PRODUCTOS': return 'ph ph-t-shirt';
      case 'COMPRAS': return 'ph ph-receipt';
      case 'INVENTARIO': return 'ph ph-package';
      case 'SUCURSALES': return 'ph ph-storefront';
      case 'EMPRESAS': return 'ph ph-buildings';
      default: return 'ph ph-terminal-window';
    }
  }

  getNombreEmpresa(idEmpresa?: number): string {
    if (!idEmpresa) return 'Global / Plataforma';
    const emp = this.empresasDisponibles.find(e => e.id_empresa === idEmpresa);
    return emp ? emp.nombre_empresa : `Empresa #${idEmpresa}`;
  }

  formatearJSON(obj: any): string {
    if (!obj || (typeof obj === 'object' && Object.keys(obj).length === 0)) {
      return 'Sin registros o sin cambios';
    }
    return JSON.stringify(obj, null, 2);
  }
}
