import { Component, OnInit, inject, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common'; // <-- Para el pipe date, *ngIf, *ngFor y ngClass
import { FormsModule } from '@angular/forms';   // <-- Para el [(ngModel)]
import { TriajeService } from '../../services/triaje';

interface MensajeChat {
  emisor: 'IA' | 'CLIENTE';
  texto: string;
  fecha: Date;
}

@Component({
  selector: 'app-triaje-chat',
  templateUrl: './triaje-chat.html',
  standalone: true, // Asegúrate de tener esto si usas componentes standalone
  imports: [CommonModule, FormsModule] // <-- ¡Aquí se inyectan las dependencias para el HTML!
})
export class TriajeChatComponent implements OnInit, AfterViewChecked {
  private triajeService = inject(TriajeService);
  
  @ViewChild('scrollContainer') private scrollContainer!: ElementRef;

  idConversacion: number | null = null;
  mensajes: MensajeChat[] = [];
  nuevoMensaje: string = '';
  cargandoRespuesta: boolean = false;
  chatFinalizado: boolean = false;

  ngOnInit() {
    this.iniciarTriaje();
  }

  ngAfterViewChecked() {
    this.scrollToBottom();
  }

  private scrollToBottom(): void {
    try {
      this.scrollContainer.nativeElement.scrollTop = this.scrollContainer.nativeElement.scrollHeight;
    } catch(err) { }
  }

  iniciarTriaje() {
    this.cargandoRespuesta = true;
    this.triajeService.iniciarChat().subscribe({
      next: (res) => {
        this.idConversacion = res.id_conversacion;
        this.mensajes.push({
          emisor: 'IA',
          texto: res.mensaje_ia,
          fecha: new Date()
        });
        this.cargandoRespuesta = false;
      },
      error: (err) => {
        console.error('Error al iniciar triaje', err);
        this.cargandoRespuesta = false;
      }
    });
  }

  onEnterPress(event: Event) {
    const keyboardEvent = event as KeyboardEvent;
    // Si presiona Enter SIN la tecla Shift, enviamos el mensaje
    if (!keyboardEvent.shiftKey) {
      keyboardEvent.preventDefault(); // Evita el salto de línea en el textarea
      this.enviarMensaje();
    }
  }

  enviarMensaje() {
    if (!this.nuevoMensaje.trim() || !this.idConversacion || this.cargandoRespuesta) return;

    const textoUsuario = this.nuevoMensaje;
    this.mensajes.push({ emisor: 'CLIENTE', texto: textoUsuario, fecha: new Date() });
    this.nuevoMensaje = '';
    this.cargandoRespuesta = true;

    this.triajeService.enviarMensaje(this.idConversacion, textoUsuario).subscribe({
      next: (res) => {
        const datosIA = res.data;
        
        this.mensajes.push({
          emisor: 'IA',
          texto: datosIA.respuesta_al_cliente,
          fecha: new Date()
        });

        // Si la IA detecta gravedad, bloqueamos el chat
        if (datosIA.escalar_a_humano) {
          this.chatFinalizado = true;
        }
        
        this.cargandoRespuesta = false;
      },
      error: (err) => {
        this.mensajes.push({
          emisor: 'IA',
          texto: 'Ocurrió un error de conexión. Por favor, intenta de nuevo.',
          fecha: new Date()
        });
        this.cargandoRespuesta = false;
      }
    });
  }
}