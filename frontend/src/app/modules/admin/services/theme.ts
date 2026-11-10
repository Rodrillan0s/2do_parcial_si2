import { Injectable, inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { BehaviorSubject, Observable } from 'rxjs';

export type TemaSistema = 'dark' | 'light';

@Injectable({
  providedIn: 'root'
})
export class ThemeService {
  private platformId = inject(PLATFORM_ID);
  private modoOscuroSubject = new BehaviorSubject<boolean>(true);
  public modoOscuro$: Observable<boolean> = this.modoOscuroSubject.asObservable();

  constructor() {
    this.inicializarTema();
  }

  private inicializarTema(): void {
    if (!isPlatformBrowser(this.platformId)) return;

    const temaGuardado = localStorage.getItem('tema_sistema');
    // Por defecto Aurora Atelier es Dark Luxury, a menos que el usuario haya guardado 'light'
    const esOscuro = temaGuardado ? temaGuardado === 'dark' : true;
    this.aplicarTema(esOscuro);
  }

  public esModoOscuro(): boolean {
    return this.modoOscuroSubject.value;
  }

  public alternarTema(): void {
    const nuevoModo = !this.modoOscuroSubject.value;
    this.aplicarTema(nuevoModo);
  }

  public establecerTema(modo: TemaSistema): void {
    this.aplicarTema(modo === 'dark');
  }

  private aplicarTema(esOscuro: boolean): void {
    this.modoOscuroSubject.next(esOscuro);

    if (isPlatformBrowser(this.platformId)) {
      const htmlEl = document.documentElement;
      if (esOscuro) {
        htmlEl.classList.add('dark');
        localStorage.setItem('tema_sistema', 'dark');
      } else {
        htmlEl.classList.remove('dark');
        localStorage.setItem('tema_sistema', 'light');
      }
    }
  }
}
