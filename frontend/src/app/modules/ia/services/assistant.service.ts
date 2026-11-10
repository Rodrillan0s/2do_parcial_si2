import { Injectable, inject, PLATFORM_ID, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { isPlatformBrowser } from '@angular/common';
import { Subscription } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth';

export type AssistantResponseType =
  | 'texto'
  | 'productos'
  | 'tabla'
  | 'indicadores'
  | 'reporte'
  | 'comparacion'
  | 'grafico'
  | 'outfit'
  | 'alertas'
  | 'predicciones'
  | 'recomendaciones'
  | 'seguimiento_pedido'
  | 'error';

export interface AssistantProduct {
  id_producto: number;
  nombre: string;
  codigo_producto?: string;
  precio: number;
  categoria?: string;
  genero?: string;
  imagen?: string;
  imagen_url?: string;
  descripcion?: string;
  stock_disponible?: number;
  stock_total?: number;
  tallas?: string[];
  tallas_disponibles?: string;
  colores?: string[];
  colores_disponibles?: string;
  motivo_recomendacion?: string;
  afinidad_porcentaje?: number | null;
}

export interface AssistantMetadata {
  provider?: string;
  model?: string;
  alcance?: string;
  id_empresa?: number;
  id_sucursal?: number | null;
  latency_ms?: number;
  used_fallback?: boolean;
  intenciones_detectadas?: string[];
  es_inicio_frio?: boolean | null;
  referencia_contextual?: string | null;
}

export interface AssistantMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  tipo?: AssistantResponseType;
  datos?: any;
  herramientas_usadas?: string[];
  metadata?: AssistantMetadata;
  isError?: boolean;
}

export interface ChatApiResponse {
  success: boolean;
  conversation_id?: string;
  mensaje?: string;
  respuesta: string;
  tipo: AssistantResponseType;
  datos?: any;
  herramientas_usadas?: string[];
  metadata?: AssistantMetadata;
  error?: string;
}

@Injectable({
  providedIn: 'root'
})
export class AssistantService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private platformId = inject(PLATFORM_ID);
  private apiUrl = environment.apiUrl || 'http://127.0.0.1:5000';

  public isOpen = signal<boolean>(false);
  public isLoading = signal<boolean>(false);
  public isListening = signal<boolean>(false);
  public speechSupported = signal<boolean>(false);
  public speechError = signal<string | null>(null);
  public transcripcionPrevia = signal<string>('');
  public conversationId = signal<string | null>(null);
  public ultimoMensajeUsuario = signal<string>('');
  public selectedModel = signal<'deepseek-chat' | 'deepseek-reasoner'>('deepseek-chat');
  public messages = signal<AssistantMessage[]>([]);

  private recognition: any = null;
  private activeSubscription: Subscription | null = null;

  constructor() {
    this.inicializarSpeechRecognition();
  }

  public toggleAssistant(): void {
    const nuevoEstado = !this.isOpen();
    this.isOpen.set(nuevoEstado);
    if (nuevoEstado && this.messages().length === 0) {
      this.agregarMensajeInicial();
    }
  }

  public openAssistant(): void {
    this.isOpen.set(true);
    if (this.messages().length === 0) {
      this.agregarMensajeInicial();
    }
  }

  public closeAssistant(): void {
    this.isOpen.set(false);
    this.detenerVoz();
  }

  public limpiarConversacion(): void {
    this.detenerRespuesta();
    this.conversationId.set(null);
    this.ultimoMensajeUsuario.set('');
    this.transcripcionPrevia.set('');
    this.messages.set([]);
    this.agregarMensajeInicial();
  }

  public detenerRespuesta(): void {
    if (this.activeSubscription) {
      this.activeSubscription.unsubscribe();
      this.activeSubscription = null;
    }
    if (this.isLoading()) {
      this.isLoading.set(false);
      const cancelMsg: AssistantMessage = {
        id: 'msg_cancel_' + Date.now(),
        role: 'assistant',
        content: '⏹️ Consulta detenida por el usuario. Puedes escribir o dictar una nueva pregunta cuando gustes.',
        timestamp: new Date(),
        tipo: 'texto'
      };
      this.messages.update(prev => [...prev, cancelMsg]);
    }
  }

  public reintentarUltimoMensaje(): void {
    const ultimo = this.ultimoMensajeUsuario();
    if (!ultimo || this.isLoading()) return;
    this.enviarMensaje(ultimo);
  }

  public cambiarModeloDeepSeek(modelo: 'deepseek-chat' | 'deepseek-reasoner'): void {
    this.selectedModel.set(modelo);
  }

  public alternarModeloDeepSeek(): void {
    this.selectedModel.update(actual =>
      actual === 'deepseek-chat' ? 'deepseek-reasoner' : 'deepseek-chat'
    );
  }

  public esUsuarioAdmin(): boolean {
    const roles = this.authService.roles().map(r => r.toUpperCase());
    return (
      roles.includes('ADMINISTRADOR') ||
      roles.includes('SUPERADMIN') ||
      roles.includes('ADMINISTRADOR_TIENDA') ||
      roles.includes('ENCARGADO')
    );
  }

  public agregarMensajeInicial(): void {
    const esAdmin = this.esUsuarioAdmin();

    let saludo = 'Hola 👋\n\nSoy **Aurora Advisor**, tu copiloto e inteligencia conversacional de **Aurora Store**.\n';
    if (esAdmin) {
      saludo +=
        'Puedo analizar **ventas por periodo**, **productos más vendidos**, **capital sin rotación**, **alertas de stock**, **sugerencias de reposición** y **proyecciones de demanda predictiva**.\n\n¿Qué indicador o análisis deseas consultar hoy?';
    } else {
      saludo +=
        'Puedo ayudarte a buscar prendas por **ocasión, talla, color o presupuesto**, **armar outfits**, **comparar productos**, revisar **disponibilidad por sucursal** o consultar el **estado de tus pedidos y reservas**.\n\n¿Qué te gustaría descubrir hoy?';
    }

    this.messages.set([
      {
        id: 'msg_welcome_' + Date.now(),
        role: 'assistant',
        content: saludo,
        timestamp: new Date(),
        tipo: 'texto'
      }
    ]);
  }

  private detectarSlugTiendaActual(): string | null {
    if (!isPlatformBrowser(this.platformId)) return null;
    try {
      const path = window.location.pathname || '';
      const match = path.match(/\/tienda\/([^/?#]+)/i);
      return match ? decodeURIComponent(match[1]) : null;
    } catch {
      return null;
    }
  }

  public enviarMensaje(texto: string): void {
    const mensajeLimpio = (texto || '').trim();
    if (!mensajeLimpio || this.isLoading()) return;

    this.ultimoMensajeUsuario.set(mensajeLimpio);
    this.transcripcionPrevia.set('');

    const userMsg: AssistantMessage = {
      id: 'msg_u_' + Date.now(),
      role: 'user',
      content: mensajeLimpio,
      timestamp: new Date(),
      tipo: 'texto'
    };

    this.messages.update(prev => [...prev, userMsg]);
    this.isLoading.set(true);
    this.speechError.set(null);

    const historial = this.messages()
      .filter(m => !m.isError)
      .slice(-8)
      .map(m => ({ role: m.role, content: m.content }));

    const token = this.authService.obtenerToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const payload: Record<string, any> = {
      mensaje: mensajeLimpio,
      historial: historial,
      modelo: this.selectedModel()
    };
    if (this.conversationId()) {
      payload['conversation_id'] = this.conversationId();
    }
    const slugTienda = this.detectarSlugTiendaActual();
    if (slugTienda) {
      payload['slug_tienda'] = slugTienda;
    }
    const user = this.authService.currentUser();
    const selectedComp = this.authService.selectedCompany();
    if (user?.alcance === 'PLATAFORMA' && selectedComp?.id_empresa) {
      payload['id_empresa'] = selectedComp.id_empresa;
    }

    this.activeSubscription = this.http
      .post<ChatApiResponse>(`${this.apiUrl}/api/asistente/chat`, payload, { headers })
      .subscribe({
        next: (resp) => {
          this.isLoading.set(false);
          this.activeSubscription = null;
          if (resp.conversation_id) {
            this.conversationId.set(resp.conversation_id);
          }
          const contenido = resp.mensaje || resp.respuesta || 'He procesado tu consulta.';
          const botMsg: AssistantMessage = {
            id: 'msg_a_' + Date.now(),
            role: 'assistant',
            content: contenido,
            timestamp: new Date(),
            tipo: resp.tipo || 'texto',
            datos: resp.datos,
            herramientas_usadas: resp.herramientas_usadas || [],
            metadata: resp.metadata,
            isError: resp.success === false || resp.tipo === 'error'
          };
          this.messages.update(prev => [...prev, botMsg]);
        },
        error: (err) => {
          this.isLoading.set(false);
          this.activeSubscription = null;
          const backendDetail = err?.error?.detail;
          const textoError =
            (typeof backendDetail === 'object' && (backendDetail?.mensaje || backendDetail?.respuesta)) ||
            (typeof backendDetail === 'string' ? backendDetail : null) ||
            err?.error?.respuesta ||
            'No pude procesar la solicitud en este momento. Puedes reintentar o continuar usando Aurora Store con normalidad.';

          const errorMsg: AssistantMessage = {
            id: 'msg_err_' + Date.now(),
            role: 'assistant',
            content: textoError,
            timestamp: new Date(),
            tipo: 'error',
            isError: true
          };
          this.messages.update(prev => [...prev, errorMsg]);
        }
      });
  }

  // =====================================================================
  // RECONOCIMIENTO DE VOZ MEDIANTE NATIVE WEB SPEECH API (es-BO / es-ES)
  // =====================================================================

  private inicializarSpeechRecognition(): void {
    if (!isPlatformBrowser(this.platformId)) return;

    const windowAny = window as any;
    const SpeechRecognition = windowAny.SpeechRecognition || windowAny.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      this.speechSupported.set(false);
      return;
    }

    this.speechSupported.set(true);
    try {
      this.recognition = new SpeechRecognition();
      this.recognition.lang = 'es-BO';
      this.recognition.continuous = false;
      this.recognition.interimResults = true;

      this.recognition.onstart = () => {
        this.isListening.set(true);
        this.speechError.set(null);
      };

      this.recognition.onend = () => {
        this.isListening.set(false);
      };

      this.recognition.onerror = (event: any) => {
        this.isListening.set(false);
        if (event.error === 'language-not-supported' && this.recognition.lang !== 'es-ES') {
          this.recognition.lang = 'es-ES';
          return;
        }
        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
          this.speechError.set('Permiso de micrófono denegado. Habilita el micrófono en tu navegador.');
        } else if (event.error !== 'no-speech' && event.error !== 'aborted') {
          this.speechError.set('No se pudo capturar el audio del micrófono.');
        }
      };
    } catch {
      this.speechSupported.set(false);
    }
  }

  public alternarVoz(onTextoDetectado: (texto: string, esFinal: boolean) => void): void {
    if (this.isListening()) {
      this.detenerVoz();
    } else {
      this.iniciarVoz(onTextoDetectado);
    }
  }

  public iniciarVoz(onTextoDetectado: (texto: string, esFinal: boolean) => void): void {
    if (!isPlatformBrowser(this.platformId)) return;

    if (!this.recognition) {
      this.inicializarSpeechRecognition();
    }

    if (!this.recognition) {
      this.speechError.set('Reconocimiento por voz no disponible en este navegador.');
      return;
    }

    try {
      this.recognition.onresult = (event: any) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex || 0; i < event.results.length; i++) {
          const res = event.results[i];
          const text = res[0]?.transcript || '';
          if (res.isFinal) {
            finalTranscript += text;
          } else {
            interimTranscript += text;
          }
        }

        const currentText = (finalTranscript || interimTranscript).trim();
        this.transcripcionPrevia.set(currentText);
        if (currentText) {
          onTextoDetectado(currentText, Boolean(finalTranscript));
        }
      };
      this.recognition.start();
    } catch {
      this.isListening.set(false);
    }
  }

  public detenerVoz(): void {
    if (this.recognition && this.isListening()) {
      try {
        this.recognition.stop();
      } catch {
        // Ignore stop errors
      }
      this.isListening.set(false);
    }
  }
}
