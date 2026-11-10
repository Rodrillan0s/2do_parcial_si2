import { Component, Input, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PrendaCatalogo } from '../../../../services/catalogo-publico';
import { FavoritosService } from '../../../../services/favoritos';

@Component({
  selector: 'app-producto-card',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './producto-card.html'
})
export class ProductoCardComponent {
  @Input({ required: true }) prenda!: PrendaCatalogo;
  @Output() clickPrenda = new EventEmitter<number>();

  public favoritosService = inject(FavoritosService);

  fallbackImg = 'https://images.unsplash.com/photo-1539109136881-3be0616acf4b?auto=format&fit=crop&w=800&q=80';

  onErrorImagen(event: Event): void {
    const target = event.target as HTMLImageElement;
    if (target && target.src !== this.fallbackImg) {
      target.src = this.fallbackImg;
    }
  }

  onCardClick(): void {
    if (this.prenda?.id_producto) {
      this.clickPrenda.emit(this.prenda.id_producto);
    }
  }

  onToggleFavorito(event: Event): void {
    event.stopPropagation();
    this.favoritosService?.toggleFavorito(this.prenda);
  }

  esFavorito(): boolean {
    return this.favoritosService?.esFavorito(this.prenda?.id_producto) ?? false;
  }

  get rating(): string {
    const base = 4.5 + ((this.prenda?.id_producto * 7) % 5) * 0.1;
    return base.toFixed(1);
  }

  get reviewCount(): number {
    return 15 + ((this.prenda?.id_producto * 13) % 35);
  }
}
