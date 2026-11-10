import { Injectable, signal, computed } from '@angular/core';

export interface ProductoFavorito {
  id_producto: number;
  nombre: string;
  categoria_nombre?: string;
  precio: number;
  imagen_principal?: string;
  subtitulo?: string;
  fecha_agregado?: string;
}

export type PrendaFavorita = ProductoFavorito;

const STORAGE_KEY = 'aurora_favoritos_v1';

@Injectable({
  providedIn: 'root'
})
export class FavoritosService {
  // Estado reactivo de favoritos con Signals de Angular
  public favoritos = signal<ProductoFavorito[]>(this.cargarDeStorage());
  public totalFavoritos = computed(() => this.favoritos().length);
  public mostrarModalFavoritos = signal<boolean>(false);

  private cargarDeStorage(): ProductoFavorito[] {
    if (typeof window === 'undefined' || !window.localStorage) return [];
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      console.warn('[FavoritosService] Error al leer favoritos de localStorage:', e);
      return [];
    }
  }

  private guardarEnStorage(lista: ProductoFavorito[]): void {
    if (typeof window === 'undefined' || !window.localStorage) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(lista));
    } catch (e) {
      console.warn('[FavoritosService] Error al guardar favoritos:', e);
    }
  }

  public esFavorito(id_producto: number): boolean {
    if (!id_producto) return false;
    return this.favoritos().some(p => p.id_producto === id_producto);
  }

  public toggleFavorito(prenda: any): boolean {
    if (!prenda || !prenda.id_producto) return false;
    const actual = this.favoritos();
    const existe = actual.some(p => p.id_producto === prenda.id_producto);

    let nuevaLista: ProductoFavorito[];
    if (existe) {
      nuevaLista = actual.filter(p => p.id_producto !== prenda.id_producto);
    } else {
      const item: ProductoFavorito = {
        id_producto: prenda.id_producto,
        nombre: prenda.nombre || 'Prenda Exclusiva',
        categoria_nombre: prenda.categoria_nombre || prenda.categoria || 'Colección Aurora',
        precio: Number(prenda.precio_base || prenda.precio || 0),
        imagen_principal: prenda.imagen_principal || prenda.imagenPrincipal || '',
        subtitulo: prenda.subtitulo || prenda.corte || '',
        fecha_agregado: new Date().toISOString()
      };
      nuevaLista = [item, ...actual];
    }

    this.favoritos.set(nuevaLista);
    this.guardarEnStorage(nuevaLista);
    return !existe;
  }

  public eliminarFavorito(id_producto: number): void {
    const nuevaLista = this.favoritos().filter(p => p.id_producto !== id_producto);
    this.favoritos.set(nuevaLista);
    this.guardarEnStorage(nuevaLista);
  }

  public limpiarTodos(): void {
    this.favoritos.set([]);
    this.guardarEnStorage([]);
  }

  public abrirModal(): void {
    this.mostrarModalFavoritos.set(true);
  }

  public cerrarModal(): void {
    this.mostrarModalFavoritos.set(false);
  }
}
