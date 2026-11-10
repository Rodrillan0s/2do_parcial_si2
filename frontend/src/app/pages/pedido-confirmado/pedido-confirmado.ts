import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { PedidoService, PedidoData } from '../../services/pedido';
import { PagoService } from '../../services/pago';
import { AuthService } from '../../services/auth';
import { ValoracionModalComponent } from '../../components/valoracion-modal/valoracion-modal';

@Component({
  selector: 'app-pedido-confirmado',
  standalone: true,
  imports: [CommonModule, RouterModule, ValoracionModalComponent],
  templateUrl: './pedido-confirmado.html'
})
export class PedidoConfirmadoComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private pedidoService = inject(PedidoService);
  private pagoService = inject(PagoService);
  public authService = inject(AuthService);

  pedido: PedidoData | null = null;
  cargando: boolean = true;
  errorMensaje: string | null = null;
  modalValoracionVisible: boolean = false;
  valoracionRegistrada: boolean = false;

  abrirModalValoracion(): void {
    this.modalValoracionVisible = true;
  }

  onValoracionRegistrada(datos: any): void {
    this.valoracionRegistrada = true;
  }

  ngOnInit(): void {
    if (!this.authService.estaAutenticado()) {
      this.router.navigate(['/catalogo']);
      return;
    }

    this.route.params.subscribe(params => {
      const id = parseInt(params['id'], 10);
      if (isNaN(id) || id <= 0) {
        this.errorMensaje = 'Identificador de pedido inválido.';
        this.cargando = false;
        return;
      }
      this.cargarPedido(id);
    });
  }

  cargarPedido(idPedido: number): void {
    this.cargando = true;
    this.errorMensaje = null;

    this.pedidoService.obtenerPedido(idPedido).subscribe({
      next: (res) => {
        this.cargando = false;
        if (res && res.success && res.data) {
          this.pedido = res.data;
        } else {
          this.errorMensaje = 'No se encontró la información del pedido solicitado.';
        }
      },
      error: (err) => {
        this.cargando = false;
        this.errorMensaje = err?.error?.detail || 'Error al recuperar los detalles de tu pedido.';
      }
    });
  }

  descargandoPdf: boolean = false;

  irAlCatalogo(): void {
    this.router.navigate(['/catalogo']);
  }

  irAlPerfil(): void {
    this.router.navigate(['/perfil']);
  }

  descargarComprobante(): void {
    if (!this.pedido) return;
    this.descargandoPdf = true;
    this.pagoService.descargarComprobantePedidoBlob(this.pedido.id_pedido).subscribe({
      next: (blob: Blob) => {
        this.descargandoPdf = false;
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Comprobante_${this.pedido!.codigo_pedido}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      },
      error: () => {
        this.descargandoPdf = false;
        alert('No se pudo descargar el comprobante en este momento.');
      }
    });
  }
}
