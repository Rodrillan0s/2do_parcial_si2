import { Component, inject, OnInit, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService, AuthTab } from '../../services/auth';
import { ThemeService } from '../../services/theme';
import { CarritoService } from '../../services/carrito';
import { FavoritosService, PrendaFavorita } from '../../services/favoritos';
import { TenantContextService } from '../../services/tenant-context';
import { TenantPublico, SucursalFiltro } from '../../services/catalogo-publico';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, RouterLinkActive],
  templateUrl: './navbar.html'
})
export class NavbarComponent implements OnInit {
  public authService      = inject(AuthService);
  public themeService     = inject(ThemeService);
  public carritoService   = inject(CarritoService);
  public favoritosService = inject(FavoritosService);
  public tenantContext    = inject(TenantContextService);
  private router          = inject(Router);

  isMobileMenuOpen = false;
  isBranchDropdownOpen = false;
  isTenantDropdownOpen = false;
  isUserMenuOpen = false;
  busquedaTexto: string = '';

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (this.isUserMenuOpen && !target.closest('[data-user-menu]')) {
      this.isUserMenuOpen = false;
    }
    if (this.isBranchDropdownOpen && !target.closest('[data-branch-menu]')) {
      this.isBranchDropdownOpen = false;
    }
    if (this.isTenantDropdownOpen && !target.closest('[data-tenant-menu]')) {
      this.isTenantDropdownOpen = false;
    }
  }

  ngOnInit(): void {
    if (!this.tenantContext.tenantActual()) {
      this.tenantContext.inicializarContexto();
    }
    if (this.authService.estaAutenticado()) {
      this.carritoService.cargarCarrito().subscribe();
    }
  }

  get sucursalesTenant(): { id: number; nombre: string; ciudad: string }[] {
    const sucs: SucursalFiltro[] = this.tenantContext.filtrosActuales().sucursales || [];
    if (sucs.length > 0) {
      return sucs.map(s => ({
        id: s.id_sucursal,
        nombre: s.nombre,
        ciudad: s.ciudad || 'Bolivia'
      }));
    }
    return this.authService.branchList;
  }

  get totalFavoritos(): number {
    return this.favoritosService ? this.favoritosService.totalFavoritos() : 0;
  }

  get mostrarModalFavoritos(): boolean {
    return this.favoritosService ? this.favoritosService.mostrarModalFavoritos() : false;
  }

  get listaFavoritos(): PrendaFavorita[] {
    return this.favoritosService ? this.favoritosService.favoritos() : [];
  }

  vaciarFavoritos(): void {
    this.favoritosService?.limpiarTodos();
  }

  abrirCarrito(): void {
    this.carritoService.abrirDrawer();
  }

  abrirFavoritos(): void {
    this.favoritosService?.abrirModal();
  }

  cerrarFavoritos(): void {
    this.favoritosService?.cerrarModal();
  }

  verPrendaFavorita(fav: PrendaFavorita): void {
    this.favoritosService?.cerrarModal();
    this.router.navigate(['/catalogo'], { queryParams: { producto: fav.id_producto } });
  }

  quitarFavorito(id: number, event: Event): void {
    event.stopPropagation();
    this.favoritosService?.eliminarFavorito(id);
  }

  toggleMobileMenu() {
    this.isMobileMenuOpen = !this.isMobileMenuOpen;
  }

  toggleUserMenu() {
    this.isUserMenuOpen = !this.isUserMenuOpen;
    this.isBranchDropdownOpen = false;
    this.isTenantDropdownOpen = false;
  }

  toggleBranchDropdown() {
    this.isBranchDropdownOpen = !this.isBranchDropdownOpen;
    this.isTenantDropdownOpen = false;
    this.isUserMenuOpen = false;
  }

  toggleTenantDropdown() {
    this.isTenantDropdownOpen = !this.isTenantDropdownOpen;
    this.isBranchDropdownOpen = false;
    this.isUserMenuOpen = false;
  }

  cambiarTienda(tenant: TenantPublico) {
    this.tenantContext.seleccionarTenant(tenant);
    this.isTenantDropdownOpen = false;
    this.router.navigate(['/explorar'], { queryParams: { empresa: tenant.id_empresa } });
  }

  selectBranch(branch: { id: number; nombre: string; ciudad: string }) {
    this.authService.setBranch(branch);
    this.isBranchDropdownOpen = false;
  }

  filtrarPorPublico(publico: string): void {
    this.isMobileMenuOpen = false;
    this.router.navigate(['/catalogo'], {
      queryParams: {
        empresa: this.tenantContext.idEmpresaActual(),
        publico
      }
    });
  }

  filtrarPorCategoria(idCategoria: number): void {
    this.isMobileMenuOpen = false;
    this.router.navigate(['/catalogo'], {
      queryParams: {
        empresa: this.tenantContext.idEmpresaActual(),
        categoria: idCategoria
      }
    });
  }

  openAuth(tab: AuthTab = 'login') {
    this.authService.openAuthModal(tab);
    this.isMobileMenuOpen = false;
  }

  cerrarSesion() {
    this.authService.cerrarSesion();
  }

  buscarEnCatalogo(): void {
    const q = this.busquedaTexto.trim();
    const empresa = this.tenantContext.idEmpresaActual();
    if (q) {
      this.router.navigate(['/catalogo'], { queryParams: { empresa, q } });
    } else {
      this.router.navigate(['/catalogo'], { queryParams: { empresa } });
    }
  }
}
