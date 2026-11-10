import { Component, OnInit, inject, ChangeDetectorRef, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NotificacionesService, Notificacion } from '../../services/notificaciones';

// ─────────────────────────────────────────────
// MODELO INTERNO: grupo de notificaciones por fecha
// ─────────────────────────────────────────────
interface GrupoFecha {
  etiqueta: string;            // "Hoy", "Ayer", "Lun 3 Jun", etc.
  fechaClave: string;          // YYYY-MM-DD para comparar
  notificaciones: Notificacion[];
}

@Component({
  selector: 'app-notificaciones',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './notificaciones.html'
})
export class NotificacionesComponent implements OnInit {

  private notificacionesService = inject(NotificacionesService);
  private cdr                   = inject(ChangeDetectorRef);
  private destroyRef            = inject(DestroyRef);

  // ── Estado de la vista ──
  cargando: boolean      = true;
  marcandoTodas: boolean = false;

  // ── Datos ──
  grupos: GrupoFecha[]   = [];
  totalNoLeidas: number  = 0;

  // ─────────────────────────────────────────────
  // LIFECYCLE
  // ─────────────────────────────────────────────

  ngOnInit() {
    // Recargar historial fresco desde la BD al entrar a la pantalla
    this.notificacionesService.cargarHistorial();

    // Suscribirse al stream central (mismo BehaviorSubject que el layout)
    this.notificacionesService.notificaciones$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((notis) => {
        this.cargando      = false;
        this.totalNoLeidas = notis.filter(n => !n.leida).length;
        this.grupos        = this.agruparPorFecha(notis);
        this.cdr.detectChanges();
      });
  }

  // ─────────────────────────────────────────────
  // ACCIONES
  // ─────────────────────────────────────────────

  /**
   * Clic en un ítem: marca como leída si aún no lo está.
   * Llama a PUT /api/ws/leer { id_notificacion: N }
   */
  leerNotificacion(noti: Notificacion) {
    if (noti.leida) return;
    if (noti.id_notificacion) {
      this.notificacionesService.marcarUnaComoLeida(noti.id_notificacion);
    }
  }

  /**
   * Botón masivo: marca todas en BD.
   * Llama a PUT /api/ws/leer { marcar_todo: true }
   */
  marcarTodas() {
    if (this.marcandoTodas) return;
    this.marcandoTodas = true;
    this.notificacionesService.marcarComoLeidas();
    // El BehaviorSubject emitirá el nuevo estado, resetear el spinner
    setTimeout(() => {
      this.marcandoTodas = false;
      this.cdr.detectChanges();
    }, 600);
  }

  // ─────────────────────────────────────────────
  // AGRUPACIÓN POR FECHA
  // ─────────────────────────────────────────────

  private agruparPorFecha(notis: Notificacion[]): GrupoFecha[] {
    const mapa = new Map<string, Notificacion[]>();

    for (const noti of notis) {
      const clave = this.fechaClave(noti.fecha);
      if (!mapa.has(clave)) mapa.set(clave, []);
      mapa.get(clave)!.push(noti);
    }

    return Array.from(mapa.entries()).map(([clave, lista]) => ({
      etiqueta:        this.etiquetaFecha(new Date(clave + 'T00:00:00')),
      fechaClave:      clave,
      notificaciones:  lista
    }));
  }

  /** Devuelve YYYY-MM-DD de una fecha para usarla como clave del mapa. */
  private fechaClave(fecha: Date): string {
    const d = new Date(fecha);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  /** Etiqueta legible: "Hoy", "Ayer", o "Lun 3 Jun" para el resto. */
  private etiquetaFecha(fecha: Date): string {
    const hoy   = new Date(); hoy.setHours(0, 0, 0, 0);
    const ayer  = new Date(hoy); ayer.setDate(hoy.getDate() - 1);
    const semana = new Date(hoy); semana.setDate(hoy.getDate() - 6);

    const f = new Date(fecha); f.setHours(0, 0, 0, 0);

    if (f.getTime() === hoy.getTime())  return 'Hoy';
    if (f.getTime() === ayer.getTime()) return 'Ayer';
    if (f >= semana) {
      return fecha.toLocaleDateString('es-BO', { weekday: 'short', day: 'numeric', month: 'short' });
    }
    return fecha.toLocaleDateString('es-BO', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  // ─────────────────────────────────────────────
  // HELPERS DE ESTILO (igual que en el layout)
  // ─────────────────────────────────────────────

  getIconoClase(tipo: string): string {
    const clases: Record<string, string> = {
      'NUEVA_EMERGENCIA': 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30',
      'NUEVA_OFERTA':     'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border-amber-100 dark:border-amber-800/30',
      'RESPUESTA_OFERTA': 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 border-green-100 dark:border-green-800/30',
      'EMERGENCIA':       'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30',
      'ALERTA':           'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border-amber-100 dark:border-amber-800/30',
      'INFO':             'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 border-blue-100 dark:border-blue-800/30',
      'EXITO':            'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 border-green-100 dark:border-green-800/30',
    };
    return clases[tipo] ?? clases['INFO'];
  }

  getIconoPath(tipo: string): string {
    const iconos: Record<string, string> = {
      'NUEVA_EMERGENCIA': 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
      'NUEVA_OFERTA':     'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
      'RESPUESTA_OFERTA': 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
      'EMERGENCIA':       'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
      'ALERTA':           'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
      'INFO':             'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
      'EXITO':            'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
    };
    return iconos[tipo] ?? iconos['INFO'];
  }

  /** Barra lateral izquierda de color para ítems no leídos. */
  getBarraClase(tipo: string): string {
    const barras: Record<string, string> = {
      'NUEVA_EMERGENCIA': 'bg-red-500',
      'NUEVA_OFERTA':     'bg-amber-500',
      'RESPUESTA_OFERTA': 'bg-green-500',
      'EMERGENCIA':       'bg-red-500',
      'ALERTA':           'bg-amber-500',
      'INFO':             'bg-blue-500',
      'EXITO':            'bg-green-500',
    };
    return barras[tipo] ?? 'bg-blue-500';
  }

  /** Badge con etiqueta corta del tipo. */
  getBadgeClase(tipo: string): string {
    const badges: Record<string, string> = {
      'NUEVA_EMERGENCIA': 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
      'NUEVA_OFERTA':     'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
      'RESPUESTA_OFERTA': 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
      'EMERGENCIA':       'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
      'ALERTA':           'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
      'INFO':             'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
      'EXITO':            'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
    };
    return badges[tipo] ?? badges['INFO'];
  }

  /** Texto corto del tipo para el badge. */
  getTipoLabel(tipo: string): string {
    const labels: Record<string, string> = {
      'NUEVA_EMERGENCIA': 'Emergencia',
      'NUEVA_OFERTA':     'Oferta',
      'RESPUESTA_OFERTA': 'Respuesta',
      'EMERGENCIA':       'Emergencia',
      'ALERTA':           'Alerta',
      'INFO':             'Info',
      'EXITO':            'Éxito',
    };
    return labels[tipo] ?? tipo;
  }
}