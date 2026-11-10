import { Component, Input, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ValoracionService, CrearValoracionPayload } from '../../services/valoracion';

@Component({
  selector: 'app-valoracion-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './valoracion-modal.html',
  styles: [`
    :host {
      display: contents;
    }
  `]
})
export class ValoracionModalComponent {
  private valoracionService = inject(ValoracionService);

  @Input() visible: boolean = false;
  @Input() idPedido?: number | null = null;
  @Input() idVenta?: number | null = null;
  @Input() idReserva?: number | null = null;
  @Input() idProducto?: number | null = null;
  @Input() nombreProducto: string = '';
  @Input() imagenProducto: string = '';
  @Input() codigoPedido: string = '';
  @Input() nombreSucursal: string = '';

  @Output() cerrar = new EventEmitter<void>();
  @Output() valoracionEnviada = new EventEmitter<any>();

  estrellas: number = 0;
  hoverEstrellas: number = 0;
  comentario: string = '';
  motivoNegativo: string = '';
  motivoSeleccionadoRapido: string = '';

  guardando: boolean = false;
  mensajeError: string | null = null;
  exito: boolean = false;

  motivosPredefinidos: string[] = [
    'Defecto en tela o costura',
    'La talla no coincide con la guía',
    'Demora excesiva en entrega',
    'Atención deficiente del personal',
    'Producto dañado o diferente al catálogo'
  ];

  seleccionarEstrellas(n: number): void {
    this.estrellas = n;
    this.mensajeError = null;
    if (n !== 1) {
      this.motivoNegativo = '';
      this.motivoSeleccionadoRapido = '';
    }
  }

  setHover(n: number): void {
    this.hoverEstrellas = n;
  }

  clearHover(): void {
    this.hoverEstrellas = 0;
  }

  seleccionarMotivoRapido(motivo: string): void {
    this.motivoSeleccionadoRapido = motivo;
    if (!this.motivoNegativo || this.motivosPredefinidos.includes(this.motivoNegativo)) {
      this.motivoNegativo = motivo;
    } else if (!this.motivoNegativo.includes(motivo)) {
      this.motivoNegativo = `${motivo}: ${this.motivoNegativo}`;
    }
  }

  get esUnaEstrella(): boolean {
    return this.estrellas === 1;
  }

  get puedeEnviar(): boolean {
    if (this.guardando) return false;
    if (this.estrellas < 1) return false;
    if (this.estrellas === 1) {
      return (this.motivoNegativo.trim().length >= 5) || (this.motivoSeleccionadoRapido.length > 0);
    }
    return true;
  }

  // Flujo A1: Cierre voluntario sin registrar valoración
  onCerrar(): void {
    if (this.guardando) return;
    this.resetForm();
    this.cerrar.emit();
  }

  enviar(): void {
    if (!this.puedeEnviar) return;

    this.guardando = true;
    this.mensajeError = null;

    let motivoFinal: string | null = null;
    if (this.esUnaEstrella) {
      motivoFinal = this.motivoNegativo.trim() || this.motivoSeleccionadoRapido;
    }

    const payload: CrearValoracionPayload = {
      puntuacion: this.estrellas,
      comentario: this.comentario.trim() || null,
      motivo_negativo: motivoFinal,
      id_producto: this.idProducto || null,
      id_pedido: this.idPedido || null,
      id_venta: this.idVenta || null,
      id_reserva: this.idReserva || null
    };

    this.valoracionService.crearValoracion(payload).subscribe({
      next: (res) => {
        this.guardando = false;
        this.exito = true;
        setTimeout(() => {
          this.valoracionEnviada.emit(res.data);
          this.onCerrar();
        }, 1200);
      },
      error: (err) => {
        this.guardando = false;
        this.mensajeError = err?.error?.detail || 'No se pudo guardar tu valoración. Intenta de nuevo.';
      }
    });
  }

  private resetForm(): void {
    this.estrellas = 0;
    this.hoverEstrellas = 0;
    this.comentario = '';
    this.motivoNegativo = '';
    this.motivoSeleccionadoRapido = '';
    this.mensajeError = null;
    this.exito = false;
    this.guardando = false;
  }
}
