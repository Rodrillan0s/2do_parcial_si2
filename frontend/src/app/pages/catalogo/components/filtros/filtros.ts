import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { FiltrosCatalogoResponse, TenantPublico } from '../../../../services/catalogo-publico';

@Component({
  selector: 'app-catalogo-filtros',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './filtros.html'
})
export class CatalogoFiltrosComponent {
  @Input() filtrosDisponibles: FiltrosCatalogoResponse = {
    categorias: [],
    publicos: [],
    sucursales: [],
    tallas: [],
    colores: [],
    temporadas: [],
    colecciones: []
  };
  @Input() totalProductos: number = 0;
  @Input() searchQuery: string = '';
  @Input() selectedCategory: number | null = null;
  @Input() selectedPublico: string = 'Todos';
  @Input() selectedSucursal: number | null = null;
  @Input() selectedTalla: number | null = null;
  @Input() selectedColor: number | null = null;
  @Input() selectedTemporada: string = 'Todas';
  @Input() selectedColeccion: string = 'Todas';
  @Input() selectedSort: string = 'destacados';
  @Input() precioMin: number | null = null;
  @Input() precioMax: number | null = null;
  @Input() tenants: TenantPublico[] = [];
  @Input() selectedTenantId: number | null = null;

  @Output() busquedaChange = new EventEmitter<string>();
  @Output() categoriaChange = new EventEmitter<number | null>();
  @Output() publicoChange = new EventEmitter<string>();
  @Output() sucursalChange = new EventEmitter<number | null>();
  @Output() tallaChange = new EventEmitter<number | null>();
  @Output() colorChange = new EventEmitter<number | null>();
  @Output() temporadaChange = new EventEmitter<string>();
  @Output() coleccionChange = new EventEmitter<string>();
  @Output() ordenChange = new EventEmitter<string>();
  @Output() precioMinChange = new EventEmitter<number | null>();
  @Output() precioMaxChange = new EventEmitter<number | null>();
  @Output() tenantChange = new EventEmitter<number>();
  @Output() limpiar = new EventEmitter<void>();

  mostrarDrawerMovil: boolean = false;
  private searchTimer: any = null;
  private priceTimer: any = null;

  colapsados = {
    publico: false,
    categoria: false,
    color: false,
    talla: false,
    temporada: false,
    precio: false,
    sucursal: false
  };

  toggleColapso(sec: 'publico' | 'categoria' | 'color' | 'talla' | 'temporada' | 'precio' | 'sucursal'): void {
    this.colapsados[sec] = !this.colapsados[sec];
  }

  get listaPublicos(): any[] {
    return this.filtrosDisponibles?.publicos || [];
  }

  get listaCategorias(): any[] {
    return this.filtrosDisponibles?.categorias || [];
  }

  get listaColores(): any[] {
    return this.filtrosDisponibles?.colores || [];
  }

  get listaTallas(): any[] {
    return this.filtrosDisponibles?.tallas || [];
  }

  get listaSucursales(): any[] {
    return this.filtrosDisponibles?.sucursales || [];
  }

  onTenantSelect(event: Event): void {
    const val = Number((event.target as HTMLSelectElement).value);
    if (!isNaN(val) && val > 0) {
      this.tenantChange.emit(val);
    }
  }

  onSucursalSelect(val: any): void {
    const parsed = val !== null && val !== '' && val !== 'null' && !isNaN(Number(val)) ? Number(val) : null;
    this.sucursalChange.emit(parsed);
  }

  togglePublico(pub: string): void {
    const nuevo = (this.selectedPublico === pub) ? 'Todos' : pub;
    this.publicoChange.emit(nuevo);
  }

  onSearchInput(val: string): void {
    this.searchQuery = val;
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => {
      this.busquedaChange.emit(this.searchQuery);
    }, 350);
  }

  limpiarBusqueda(): void {
    this.searchQuery = '';
    this.busquedaChange.emit('');
  }

  onPrecioMinChange(val: any): void {
    const parsed = val !== null && val !== '' && !isNaN(Number(val)) ? Number(val) : null;
    this.precioMin = parsed;
    if (this.priceTimer) clearTimeout(this.priceTimer);
    this.priceTimer = setTimeout(() => {
      this.precioMinChange.emit(this.precioMin);
    }, 400);
  }

  onPrecioMaxChange(val: any): void {
    const parsed = val !== null && val !== '' && !isNaN(Number(val)) ? Number(val) : null;
    this.precioMax = parsed;
    if (this.priceTimer) clearTimeout(this.priceTimer);
    this.priceTimer = setTimeout(() => {
      this.precioMaxChange.emit(this.precioMax);
    }, 400);
  }

  toggleCategoria(id: number | null): void {
    const nuevo = (this.selectedCategory === id) ? null : id;
    this.categoriaChange.emit(nuevo);
  }

  toggleTalla(id: number | null): void {
    const nuevo = (this.selectedTalla === id) ? null : id;
    this.tallaChange.emit(nuevo);
  }

  toggleColor(id: number | null): void {
    const nuevo = (this.selectedColor === id) ? null : id;
    this.colorChange.emit(nuevo);
  }

  onTemporadaSelect(val: string): void {
    this.temporadaChange.emit(val);
  }

  onColeccionSelect(val: string): void {
    this.coleccionChange.emit(val);
  }

  onOrdenSelect(val: string): void {
    this.ordenChange.emit(val);
  }

  onLimpiar(): void {
    this.precioMin = null;
    this.precioMax = null;
    this.limpiar.emit();
    this.mostrarDrawerMovil = false;
  }

  contarFiltrosActivos(): number {
    let count = 0;
    if (this.searchQuery.trim().length > 0) count++;
    if (this.selectedCategory !== null) count++;
    if (this.selectedPublico && this.selectedPublico !== 'Todos') count++;
    if (this.selectedSucursal !== null) count++;
    if (this.selectedTalla !== null) count++;
    if (this.selectedColor !== null) count++;
    if (this.selectedTemporada !== 'Todas') count++;
    if (this.selectedColeccion !== 'Todas') count++;
    if (this.selectedSort !== 'destacados') count++;
    if (this.precioMin !== null && this.precioMin > 0) count++;
    if (this.precioMax !== null && this.precioMax > 0) count++;
    return count;
  }

  toggleDrawer(): void {
    this.mostrarDrawerMovil = !this.mostrarDrawerMovil;
  }
}
