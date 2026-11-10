import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { CarritoService, CarritoData, ItemCarrito } from '../../services/carrito';
import { AuthService } from '../../services/auth';
import { PerfilService } from '../../services/perfil';
import { PedidoService, SucursalCheckout, CrearPedidoPayload } from '../../services/pedido';
import { extraerMensajeError } from '../../utils/error-helper';
import { NetworkStatusService } from '../../core/network/network-status.service';

@Component({
  selector: 'app-checkout',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './checkout.html'
})
export class CheckoutComponent implements OnInit {
  public carritoService = inject(CarritoService);
  public authService = inject(AuthService);
  public networkStatus = inject(NetworkStatusService);
  private perfilService = inject(PerfilService);
  private pedidoService = inject(PedidoService);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);

  // Datos del carrito
  carrito: CarritoData | null = null;
  cargandoCarrito: boolean = true;

  // Filtros de búsqueda de sucursales
  filtroCiudad: string = 'TODAS';
  busquedaSucursal: string = '';

  // Sucursales del Tenant
  sucursales: SucursalCheckout[] = [];
  sucursalSeleccionadaId: number | null = null;
  cargandoSucursales: boolean = false;

  // Modalidad de compra
  modalidadCompra: 'RETIRO_SUCURSAL' | 'ENTREGA_DOMICILIO' = 'RETIRO_SUCURSAL';

  // Datos de contacto del cliente
  nombreContacto: string = '';
  telefonoContacto: string = '';
  correoContacto: string = '';
  direccionEntrega: string = '';
  ciudadEntrega: string = 'Santa Cruz';
  notasEntrega: string = '';

  // Estados de proceso y feedback
  procesando: boolean = false;
  errorMensaje: string | null = null;

  ngOnInit(): void {
    if (!this.authService.estaAutenticado()) {
      this.router.navigate(['/catalogo']);
      this.authService.openAuthModal('login');
      return;
    }

    this.cargarDatosIniciales();
  }

  cargarDatosIniciales(): void {
    this.cargandoCarrito = true;
    this.cargandoSucursales = true;

    // 1. Cargar carrito activo
    this.carritoService.cargarCarrito().subscribe({
      next: (res) => {
        this.cargandoCarrito = false;
        if (res && res.success && res.data) {
          this.carrito = res.data;
          // Cargar sucursales del Tenant del carrito
          this.cargarSucursales(res.data.id_empresa);
        } else {
          this.carrito = null;
          this.cargandoSucursales = false;
        }
        this.cdr.detectChanges();
      },
      error: () => {
        this.cargandoCarrito = false;
        this.cargandoSucursales = false;
        this.cdr.detectChanges();
      }
    });

    // 2. Pre-cargar datos del cliente desde PerfilService
    this.perfilService.obtenerPerfil().subscribe({
      next: (res) => {
        if (res && res.success && res.data) {
          const p = res.data;
          this.nombreContacto = p.nombre_completo || `${p.nombre || ''} ${p.apellido || ''}`.trim();
          this.telefonoContacto = p.telefono || '';
          this.correoContacto = p.correo || '';
          if (p.direccion) this.direccionEntrega = p.direccion;
          if (p.ciudad) this.ciudadEntrega = p.ciudad;
        }
        this.cdr.detectChanges();
      },
      error: () => {
        // Fallback al usuario en AuthService
        const u = this.authService.currentUser();
        if (u) {
          this.nombreContacto = `${u.nombre || ''} ${u.apellido || ''}`.trim();
          this.correoContacto = u.correo || '';
        }
        this.cdr.detectChanges();
      }
    });
  }

  cargarSucursales(idEmpresa: number): void {
    this.pedidoService.obtenerSucursales(idEmpresa).subscribe({
      next: (res) => {
        this.sucursales = res.data || [];
        this.cargandoSucursales = false;
        const conStock = this.sucursales.find(s => s.tiene_stock_completo !== false);
        this.sucursalSeleccionadaId = conStock ? conStock.id_sucursal : (this.sucursales.length > 0 ? this.sucursales[0].id_sucursal : null);
        this.cdr.detectChanges();
      },
      error: () => {
        this.cargandoSucursales = false;
        this.cdr.detectChanges();
      }
    });
  }

  get ciudadesDisponibles(): string[] {
    const set = new Set(this.sucursales.map(s => s.ciudad).filter(c => !!c));
    return ['TODAS', ...Array.from(set).sort()];
  }

  get sucursalesFiltradas(): SucursalCheckout[] {
    return this.sucursales.filter(s => {
      const coincideCiudad = this.filtroCiudad === 'TODAS' || 
        s.ciudad.toLowerCase() === this.filtroCiudad.toLowerCase();
      const query = this.busquedaSucursal.toLowerCase().trim();
      const coincideBusqueda = !query || 
        s.nombre.toLowerCase().includes(query) || 
        s.direccion.toLowerCase().includes(query) || 
        s.ciudad.toLowerCase().includes(query);
      return coincideCiudad && coincideBusqueda;
    });
  }

  get haySucursalConStockCompleto(): boolean {
    return this.sucursales.some(s => s.tiene_stock_completo !== false);
  }

  seleccionarSucursal(s: SucursalCheckout): void {
    if (this.modalidadCompra === 'RETIRO_SUCURSAL' && s.tiene_stock_completo === false) {
      this.errorMensaje = `La sucursal ${s.nombre} no cuenta con todas las prendas de tu bolsa en stock. Elige otra sucursal para el retiro.`;
      return;
    }
    this.sucursalSeleccionadaId = s.id_sucursal;
    this.errorMensaje = null;
  }

  seleccionarModalidad(m: 'RETIRO_SUCURSAL' | 'ENTREGA_DOMICILIO'): void {
    this.modalidadCompra = m;
    this.errorMensaje = null;
    if (m === 'RETIRO_SUCURSAL' && this.sucursalSeleccionada?.tiene_stock_completo === false) {
      const conStock = this.sucursales.find(s => s.tiene_stock_completo !== false);
      if (conStock) {
        this.sucursalSeleccionadaId = conStock.id_sucursal;
      }
    }
  }

  get sucursalSeleccionada(): SucursalCheckout | null {
    return this.sucursales.find(s => s.id_sucursal === this.sucursalSeleccionadaId) || null;
  }

  formularioValido(): boolean {
    if (!this.carrito || this.carrito.items.length === 0) return false;
    if (!this.sucursalSeleccionadaId) return false;
    if (this.modalidadCompra === 'RETIRO_SUCURSAL') {
      const suc = this.sucursalSeleccionada;
      if (!suc || suc.tiene_stock_completo === false) return false;
    }
    if (!this.nombreContacto.trim()) return false;
    if (!this.telefonoContacto.trim()) return false;

    if (this.modalidadCompra === 'ENTREGA_DOMICILIO') {
      if (!this.direccionEntrega.trim() || !this.ciudadEntrega.trim()) return false;
    }

    return true;
  }

  confirmarPedido(): void {
    if (this.procesando) return;
    this.errorMensaje = null;

    if (!this.networkStatus.isOnline()) {
      this.errorMensaje =
        'La confirmación definitiva de compra y pago requiere conexión en línea activa. Tu bolsa y datos siguen resguardados localmente.';
      return;
    }

    if (!this.formularioValido()) {
      this.errorMensaje = 'Por favor completa todos los campos requeridos antes de confirmar.';
      return;
    }

    if (!this.carrito || this.carrito.items.length === 0) {
      this.errorMensaje = 'Tu bolsa de compras está vacía.';
      return;
    }

    this.procesando = true;

    const payload: CrearPedidoPayload = {
      id_sucursal: this.sucursalSeleccionadaId!,
      modalidad_compra: this.modalidadCompra,
      nombre_contacto: this.nombreContacto.trim(),
      telefono_contacto: this.telefonoContacto.trim(),
      correo_contacto: this.correoContacto.trim() || undefined,
      direccion_entrega: this.modalidadCompra === 'ENTREGA_DOMICILIO' ? this.direccionEntrega.trim() : undefined,
      ciudad_entrega: this.modalidadCompra === 'ENTREGA_DOMICILIO' ? this.ciudadEntrega.trim() : undefined,
      notas_entrega: this.notasEntrega.trim() || undefined,
      id_empresa: this.carrito.id_empresa
    };

    this.pedidoService.crearPedido(payload).subscribe({
      next: (res) => {
        this.procesando = false;
        if (res && res.success && res.data) {
          // Recargar el carrito para reflejar que quedó procesado
          this.carritoService.cargarCarrito().subscribe();
          // Navegar a la pantalla de pedido confirmado
          this.router.navigate(['/pedido-confirmado', res.data.id_pedido]);
        }
      },
      error: (err) => {
        this.procesando = false;
        this.errorMensaje = extraerMensajeError(err, 'Ocurrió un error al procesar tu pedido. Por favor intenta nuevamente.');
        // Si fue un problema de stock, recargar el carrito para sincronizar alertas
        this.carritoService.cargarCarrito().subscribe();
      }
    });
  }

  irAlCatalogo(): void {
    this.router.navigate(['/catalogo']);
  }
}
