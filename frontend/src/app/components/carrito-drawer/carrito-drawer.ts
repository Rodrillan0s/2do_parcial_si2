import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { CarritoService, ItemCarrito, CarritoData } from '../../services/carrito';
import { AuthService } from '../../services/auth';

@Component({
  selector: 'app-carrito-drawer',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './carrito-drawer.html'
})
export class CarritoDrawerComponent implements OnInit {
  public carritoService = inject(CarritoService);
  public authService = inject(AuthService);
  private router = inject(Router);

  mostrarConfirmacionVaciar = false;
  detalleEnOperacion: number | null = null;
  mensajeFeedback: string | null = null;
  errorFeedback: string | null = null;

  ngOnInit(): void {
    // Si el usuario está autenticado, cargar el carrito
    if (this.authService.estaAutenticado()) {
      this.carritoService.cargarCarrito().subscribe();
    }
  }

  cerrar(): void {
    this.carritoService.cerrarDrawer();
    this.mostrarConfirmacionVaciar = false;
  }

  irAlCatalogo(): void {
    this.cerrar();
    this.router.navigate(['/catalogo']);
  }

  iniciarSesion(): void {
    this.cerrar();
    this.authService.openAuthModal('login');
  }

  agendarCitaParaPrenda(item: ItemCarrito): void {
    this.cerrar();
    this.router.navigate(['/catalogo'], { queryParams: { producto: item.id_producto, modo: 'cita' } });
  }

  incrementarCantidad(item: ItemCarrito): void {
    if (item.cantidad >= item.stock_disponible) {
      this.mostrarError(`Solo quedan ${item.stock_disponible} unidades disponibles.`);
      return;
    }
    this.detalleEnOperacion = item.id_detalle_carrito;
    this.carritoService.actualizarCantidad(item.id_detalle_carrito, item.cantidad + 1).subscribe({
      next: () => {
        this.detalleEnOperacion = null;
      },
      error: (err) => {
        this.detalleEnOperacion = null;
        this.mostrarError(err?.error?.detail || 'No fue posible actualizar la cantidad.');
      }
    });
  }

  decrementarCantidad(item: ItemCarrito): void {
    if (item.cantidad <= 1) {
      this.eliminarItem(item);
      return;
    }
    this.detalleEnOperacion = item.id_detalle_carrito;
    this.carritoService.actualizarCantidad(item.id_detalle_carrito, item.cantidad - 1).subscribe({
      next: () => {
        this.detalleEnOperacion = null;
      },
      error: (err) => {
        this.detalleEnOperacion = null;
        this.mostrarError(err?.error?.detail || 'No fue posible actualizar la cantidad.');
      }
    });
  }

  eliminarItem(item: ItemCarrito): void {
    this.detalleEnOperacion = item.id_detalle_carrito;
    this.carritoService.eliminarItem(item.id_detalle_carrito).subscribe({
      next: () => {
        this.detalleEnOperacion = null;
        this.mostrarMensaje(`Se quitó "${item.producto_nombre}" de tu bolsa.`);
      },
      error: (err) => {
        this.detalleEnOperacion = null;
        this.mostrarError(err?.error?.detail || 'No fue posible eliminar la prenda.');
      }
    });
  }

  confirmarVaciar(): void {
    this.mostrarConfirmacionVaciar = true;
  }

  cancelarVaciar(): void {
    this.mostrarConfirmacionVaciar = false;
  }

  ejecutarVaciar(): void {
    this.mostrarConfirmacionVaciar = false;
    this.carritoService.vaciarCarrito().subscribe({
      next: () => {
        this.mostrarMensaje('Tu bolsa ha sido vaciada.');
      },
      error: (err) => {
        this.mostrarError(err?.error?.detail || 'No fue posible vaciar la bolsa.');
      }
    });
  }

  continuarCompra(carrito: CarritoData): void {
    if (!carrito.puede_continuar_compra) {
      this.mostrarError('Por favor ajusta las prendas no disponibles antes de continuar con la compra.');
      return;
    }
    this.cerrar();
    this.router.navigate(['/checkout']);
  }

  private mostrarMensaje(msg: string): void {
    this.mensajeFeedback = msg;
    this.errorFeedback = null;
    setTimeout(() => {
      if (this.mensajeFeedback === msg) this.mensajeFeedback = null;
    }, 3500);
  }

  private mostrarError(err: string): void {
    this.errorFeedback = err;
    this.mensajeFeedback = null;
    setTimeout(() => {
      if (this.errorFeedback === err) this.errorFeedback = null;
    }, 4500);
  }
}
