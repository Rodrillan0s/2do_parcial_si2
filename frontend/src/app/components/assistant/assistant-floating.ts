import { Component, inject, ElementRef, ViewChild, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AssistantService, AssistantMessage, AssistantProduct } from '../../services/assistant.service';
import { ThemeService } from '../../services/theme';

@Component({
  selector: 'app-assistant-floating',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './assistant-floating.html',
  styleUrls: ['./assistant-floating.css']
})
export class AssistantFloatingComponent implements AfterViewChecked {
  public assistantService = inject(AssistantService);
  public themeService = inject(ThemeService);
  private router = inject(Router);

  @ViewChild('scrollContainer') private scrollContainer?: ElementRef;
  @ViewChild('inputMensaje') private inputMensajeRef?: ElementRef;

  public mensajeTexto: string = '';
  public autoEnviarVoz: boolean = false;
  private debeHacerScroll: boolean = false;

  get isOpen(): boolean {
    return this.assistantService.isOpen();
  }

  get isLoading(): boolean {
    return this.assistantService.isLoading();
  }

  get isListening(): boolean {
    return this.assistantService.isListening();
  }

  get speechError(): string | null {
    return this.assistantService.speechError();
  }

  get transcripcionPrevia(): string {
    return this.assistantService.transcripcionPrevia();
  }

  get messages(): AssistantMessage[] {
    return this.assistantService.messages();
  }

  get esAdmin(): boolean {
    return this.assistantService.esUsuarioAdmin();
  }

  get selectedModel(): 'deepseek-chat' | 'deepseek-reasoner' {
    return this.assistantService.selectedModel();
  }

  public seleccionarModelo(modelo: 'deepseek-chat' | 'deepseek-reasoner'): void {
    this.assistantService.cambiarModeloDeepSeek(modelo);
  }

  public alternarModelo(): void {
    this.assistantService.alternarModeloDeepSeek();
  }

  public alternarPanel(): void {
    this.assistantService.toggleAssistant();
    if (this.assistantService.isOpen()) {
      this.debeHacerScroll = true;
      setTimeout(() => {
        this.inputMensajeRef?.nativeElement?.focus();
      }, 200);
    }
  }

  public cerrarPanel(): void {
    this.assistantService.closeAssistant();
  }

  public reiniciarConversacion(): void {
    this.assistantService.limpiarConversacion();
    this.debeHacerScroll = true;
  }

  public detenerRespuesta(): void {
    this.assistantService.detenerRespuesta();
    this.debeHacerScroll = true;
  }

  public reintentar(): void {
    this.assistantService.reintentarUltimoMensaje();
    this.debeHacerScroll = true;
  }

  public enviar(): void {
    if (!this.mensajeTexto.trim() || this.isLoading) return;
    const texto = this.mensajeTexto;
    this.mensajeTexto = '';
    this.assistantService.enviarMensaje(texto);
    this.debeHacerScroll = true;
  }

  public onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.enviar();
    }
  }

  public alternarMicrofono(): void {
    this.assistantService.alternarVoz((transcripcion: string, esFinal?: boolean) => {
      this.mensajeTexto = transcripcion;
      if (esFinal && this.autoEnviarVoz) {
        this.enviar();
      }
    });
  }

  public verProducto(producto: AssistantProduct | any): void {
    if (!producto) return;
    const id = producto.id_producto || producto.id;
    if (id) {
      this.router.navigate(['/catalogo', id]);
    } else {
      this.router.navigate(['/catalogo']);
    }
  }

  public irARuta(ruta: string): void {
    if (!ruta) return;
    this.router.navigate([ruta]);
  }

  public getProductos(datos: any): AssistantProduct[] {
    if (!datos) return [];
    if (Array.isArray(datos)) return datos;
    if (Array.isArray(datos.recomendaciones)) return datos.recomendaciones;
    if (Array.isArray(datos.productos)) return datos.productos;
    if (Array.isArray(datos.prendas)) return datos.prendas;
    return [];
  }

  public getItemsTabla(datos: any): any[] {
    if (!datos) return [];
    if (Array.isArray(datos)) return datos;
    if (Array.isArray(datos.datos)) return datos.datos;
    if (Array.isArray(datos.recomendaciones)) return datos.recomendaciones;
    if (Array.isArray(datos.items)) return datos.items;
    return [];
  }

  public getAlertas(datos: any): any[] {
    if (!datos) return [];
    if (Array.isArray(datos)) return datos;
    if (Array.isArray(datos.alertas)) return datos.alertas;
    return [];
  }

  public asAny(val: any): any {
    return val || {};
  }

  public sugerirConsulta(texto: string): void {
    this.mensajeTexto = texto;
    this.enviar();
  }

  public formatearTexto(texto: string): string {
    if (!texto) return '';
    // Escapar HTML crudo primero para prevenir XSS
    const escaped = String(texto)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');

    return escaped
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^- (.*$)/gim, '<li class="ml-4 list-disc">$1</li>')
      .replace(/\n/g, '<br>');
  }

  public ngAfterViewChecked(): void {
    if (this.debeHacerScroll) {
      this.scrollAlFondo();
      this.debeHacerScroll = false;
    }
  }

  private scrollAlFondo(): void {
    try {
      if (this.scrollContainer) {
        this.scrollContainer.nativeElement.scrollTop = this.scrollContainer.nativeElement.scrollHeight;
      }
    } catch {
      // Ignore scroll error
    }
  }
}
