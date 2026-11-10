import { Injectable, inject, PLATFORM_ID, NgZone } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

// ============================================================
// INTERFACES
// ============================================================

export interface Notificacion {
  id_notificacion?: number;     // Solo existe en notificaciones del historial (BD)
  tipo_alerta: string;          // Para push en tiempo real  (viene como tipo_alerta)
  tipo_referencia?: string;     // Para historial desde BD   (viene como tipo_referencia)
  titulo: string;
  cuerpo: string;
  data?: any;
  leida: boolean;               // Campo normalizado para el frontend
  leido?: boolean;              // Campo original de BD (se mapea a 'leida')
  fecha: Date;
  nro_emergencia?: number;
}

interface RespuestaHistorial {
  success: boolean;
  message: string;
  data: any[];
}

// ============================================================
// SERVICIO
// ============================================================

@Injectable({ providedIn: 'root' })
export class NotificacionesService {

  private http       = inject(HttpClient);
  private authService = inject(AuthService);
  private platformId  = inject(PLATFORM_ID);
  private ngZone      = inject(NgZone);

  private socket: WebSocket | null = null;
  private cargandoHistorial = false;
  private reconnectTimer: any = null;

  // Estado reactivo central: mezcla de historial (BD) + push (WS)
  private notificacionesSource = new BehaviorSubject<Notificacion[]>([]);
  notificaciones$: Observable<Notificacion[]> = this.notificacionesSource.asObservable();

  // ----------------------------------------------------------------
  // CONEXIÓN WEBSOCKET
  // ----------------------------------------------------------------

  conectar() {
    if (!isPlatformBrowser(this.platformId)) return;
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    const token = this.authService.obtenerToken();
    if (!token) return;

    // 1. Cargar historial desde BD antes de abrir el canal en tiempo real
    this.cargarHistorial();

    // 2. Abrir canal WebSocket
    const wsBaseUrl = environment.apiUrl.replace(/^http/, 'ws');
    const wsUrl     = `${wsBaseUrl}/api/ws/notificaciones?token=${token}`;

    this.ngZone.runOutsideAngular(() => {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        console.log('WebSocket Notificaciones Conectado 🟢');
      };

      this.socket.onmessage = (event) => {
        this.ngZone.run(() => {
          try {
            const dataBackend = JSON.parse(event.data);

            // Normalizar campo tipo (push usa tipo_alerta, BD usa tipo_referencia)
            const nuevaNotificacion: Notificacion = {
              tipo_alerta:     dataBackend.tipo_alerta,
              tipo_referencia: dataBackend.tipo_alerta,
              titulo:          dataBackend.titulo,
              cuerpo:          dataBackend.cuerpo,
              data:            dataBackend.data,
              leida:           false,
              fecha:           new Date()
            };

            // Insertar al principio sin duplicar (por si ya llegó del historial)
            const listaActual = this.notificacionesSource.getValue();
            this.notificacionesSource.next([nuevaNotificacion, ...listaActual]);

          } catch (e) {
            console.error('Error al parsear notificación WS:', e);
          }
        });
      };

      this.socket.onclose = () => {
        this.socket = null;
        if (!this.reconnectTimer && this.authService.obtenerToken()) {
          this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.conectar();
          }, 5000);
        }
      };

      this.socket.onerror = (err) => {
        console.error('WebSocket Error:', err);
      };
    });
  }

  desconectar() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }
  }

  // ----------------------------------------------------------------
  // HISTORIAL DESDE BASE DE DATOS
  // ----------------------------------------------------------------

  /**
   * Llama a GET /api/ws/historial y puebla el BehaviorSubject
   * con las notificaciones persistidas en BD.
   */
  cargarHistorial() {
    if (this.cargandoHistorial) return;
    this.cargandoHistorial = true;

    const headers = this.getAuthHeaders();
    if (!headers) return;

    this.http.get<RespuestaHistorial>(
      `${environment.apiUrl}/api/ws/historial`,
      { headers }
    ).subscribe({
      next: (res) => {
        if (res.success && Array.isArray(res.data)) {
          // Mapear el modelo de BD al modelo del frontend
          const notificaciones: Notificacion[] = res.data.map(n => ({
            id_notificacion: n.id_notificacion,
            tipo_alerta:     n.tipo_referencia,   // normalizar nombre del campo
            tipo_referencia: n.tipo_referencia,
            titulo:          n.titulo,
            cuerpo:          n.cuerpo,
            leida:           n.leido,             // normalizar nombre del campo
            leido:           n.leido,
            fecha:           new Date(n.fecha_creacion),
            nro_emergencia:  n.nro_emergencia,
            data:            { nro_emergencia: n.nro_emergencia }
          }));
          this.notificacionesSource.next(notificaciones);
        }
        this.cargandoHistorial = false;
      },
      error: (err) => {
        console.error('Error cargando historial de notificaciones:', err);
        this.cargandoHistorial = false;
      }
    });
  }

  // ----------------------------------------------------------------
  // MARCAR COMO LEÍDAS — sincronizado con el backend
  // ----------------------------------------------------------------

  /**
   * Marca TODAS las notificaciones como leídas.
   * Llama a PUT /api/ws/leer con { marcar_todo: true }
   * y actualiza el estado local optimistamente.
   */
  marcarComoLeidas() {
    const headers = this.getAuthHeaders();
    if (!headers) return;

    // Actualización optimista: no esperar respuesta del servidor para la UI
    const listaActualizada = this.notificacionesSource.getValue()
      .map(n => ({ ...n, leida: true, leido: true }));
    this.notificacionesSource.next(listaActualizada);

    // Persistir en BD
    this.http.put(
      `${environment.apiUrl}/api/ws/leer`,
      { marcar_todo: true },
      { headers }
    ).subscribe({
      error: (err) => console.error('Error al marcar todas como leídas en BD:', err)
    });
  }

  /**
   * Marca UNA notificación específica como leída por su id.
   * Llama a PUT /api/ws/leer con { id_notificacion: N }
   */
  marcarUnaComoLeida(id_notificacion: number) {
    const headers = this.getAuthHeaders();
    if (!headers) return;

    // Actualización optimista
    const listaActualizada = this.notificacionesSource.getValue().map(n =>
      n.id_notificacion === id_notificacion ? { ...n, leida: true, leido: true } : n
    );
    this.notificacionesSource.next(listaActualizada);

    // Persistir en BD
    this.http.put(
      `${environment.apiUrl}/api/ws/leer`,
      { id_notificacion },
      { headers }
    ).subscribe({
      error: (err) => console.error(`Error al marcar notificación ${id_notificacion} como leída:`, err)
    });
  }

  // ----------------------------------------------------------------
  // HELPERS
  // ----------------------------------------------------------------

  private getAuthHeaders(): HttpHeaders | null {
    const token = this.authService.obtenerToken();
    if (!token) return null;
    return new HttpHeaders({ Authorization: `Bearer ${token}` });
  }
}