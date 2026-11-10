import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import { NavbarComponent } from './components/navbar/navbar';
import { FooterComponent } from './components/footer/footer';
import { AuthModalComponent } from './components/auth-modal/auth-modal';
import { CarritoDrawerComponent } from './components/carrito-drawer/carrito-drawer';
import { AssistantFloatingComponent } from './components/assistant/assistant-floating';
import { PwaStatusBarComponent } from './components/pwa-status-bar/pwa-status-bar';
import { PwaUpdateService } from './core/pwa/pwa-update.service';
import { CatalogoPublicoService } from './services/catalogo-publico';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule, 
    RouterOutlet, 
    NavbarComponent, 
    FooterComponent, 
    AuthModalComponent, 
    CarritoDrawerComponent,
    AssistantFloatingComponent,
    PwaStatusBarComponent
  ],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  private router = inject(Router);
  private pwaUpdate = inject(PwaUpdateService);
  private catalogoService = inject(CatalogoPublicoService);

  esRutaAdmin: boolean = false;

  constructor() {
    this.router.events
      .pipe(filter(event => event instanceof NavigationEnd))
      .subscribe((event: any) => {
        const url = event.urlAfterRedirects || event.url || '';
        this.esRutaAdmin = url.startsWith('/admin') || url.startsWith('/saas');
      });
  }

  ngOnInit(): void {
    // Inicializar Service Worker (registro seguro e inspección de updates)
    this.pwaUpdate.initServiceWorker();

    // Precarga selectiva de lectura no bloqueante en IndexedDB durante tiempo ocioso
    this.catalogoService.precargarCatalogoInicial();
  }
}
