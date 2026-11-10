import { Injectable, PLATFORM_ID, inject, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

@Injectable({
  providedIn: 'root'
})
export class PwaUpdateService {
  private platformId = inject(PLATFORM_ID);

  public updateAvailable = signal<boolean>(false);
  public updateVersion = signal<string | null>(null);
  public canInstallPwa = signal<boolean>(false);
  public swRegistered = signal<boolean>(false);
  public staleChunkDetected = signal<boolean>(false);

  private deferredInstallPrompt: any = null;
  private swRegistration: ServiceWorkerRegistration | null = null;

  public initServiceWorker(): void {
    if (!isPlatformBrowser(this.platformId)) return;

    // Capturar errores de carga de chunks dinámicos (típicos de despliegues con nuevos hashes)
    window.addEventListener('error', (event: ErrorEvent) => {
      const msg = event?.message || '';
      if (
        msg.includes('Loading chunk') ||
        msg.includes('Failed to fetch dynamically imported module') ||
        msg.includes('error loading dynamically imported module')
      ) {
        console.warn('[PWA] Chunk obsoleto detectado tras actualización del despliegue:', msg);
        this.staleChunkDetected.set(true);
        this.updateAvailable.set(true);
        this.attemptAutoReloadOnStaleChunk();
      }
    });

    // Capturar promesas rechazadas por importación dinámica fallida (Chrome/Edge/Safari)
    window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
      const reason = event?.reason;
      const msg = reason?.message || String(reason || '');
      if (
        msg.includes('Loading chunk') ||
        msg.includes('Failed to fetch dynamically imported module') ||
        msg.includes('error loading dynamically imported module') ||
        msg.includes('chunk-')
      ) {
        console.warn('[PWA] Unhandled chunk rejection detectada:', msg);
        this.staleChunkDetected.set(true);
        this.updateAvailable.set(true);
        this.attemptAutoReloadOnStaleChunk();
      }
    });

    // Capturar evento de instalación PWA
    window.addEventListener('beforeinstallprompt', (e: Event) => {
      e.preventDefault();
      this.deferredInstallPrompt = e;
      this.canInstallPwa.set(true);
    });

    window.addEventListener('appinstalled', () => {
      this.deferredInstallPrompt = null;
      this.canInstallPwa.set(false);
    });

    if (!('serviceWorker' in navigator)) return;

    // Escuchar mensajes del Service Worker (nueva versión lista sin recarga forzada o chunks obsoletos)
    navigator.serviceWorker.addEventListener('message', (event: MessageEvent) => {
      const data = event.data || {};
      if (data.type === 'SW_UPDATE_AVAILABLE') {
        this.updateVersion.set(data.version || null);
        this.updateAvailable.set(true);
      } else if (data.type === 'STALE_CHUNK_DETECTED') {
        console.warn('[PWA] Service Worker detectó chunk 404 en el servidor:', data.pathname);
        this.staleChunkDetected.set(true);
        this.updateAvailable.set(true);
        this.attemptAutoReloadOnStaleChunk();
      }
    });

    // Registrar Service Worker después de la carga inicial para no competir con recursos críticos
    const registerSw = async () => {
      try {
        const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
        this.swRegistration = reg;
        this.swRegistered.set(true);

        if (reg.waiting) {
          this.updateAvailable.set(true);
        }

        reg.addEventListener('updatefound', () => {
          const installing = reg.installing;
          if (!installing) return;
          installing.addEventListener('statechange', () => {
            if (installing.state === 'installed' && navigator.serviceWorker.controller) {
              this.updateAvailable.set(true);
            }
          });
        });
      } catch (err) {
        console.warn('[PWA] Registro de Service Worker omitido o no disponible en este entorno:', err);
      }
    };

    if (document.readyState === 'complete') {
      registerSw();
    } else {
      window.addEventListener('load', () => registerSw(), { once: true });
    }
  }

  /**
   * Recarga debounced automática ante error crítico de chunk obsoleto para evitar pantalla en blanco.
   */
  public attemptAutoReloadOnStaleChunk(): void {
    if (!isPlatformBrowser(this.platformId) || typeof window === 'undefined') return;
    const lastReload = sessionStorage.getItem('aurora_last_chunk_reload');
    const now = Date.now();
    if (!lastReload || now - Number(lastReload) > 5000) {
      sessionStorage.setItem('aurora_last_chunk_reload', String(now));
      console.warn('[PWA] Purgando caches estáticas y recargando automáticamente para resolver chunk desactualizado...');
      const globalWin = window as any;
      if (globalWin && globalWin.caches) {
        globalWin.caches.keys().then((keys: string[]) => {
          const staleKeys = keys.filter(k => k.includes('static') || k.includes('shell'));
          Promise.all(staleKeys.map(k => globalWin.caches.delete(k))).finally(() => {
            globalWin.location.reload();
          });
        }).catch(() => {
          globalWin.location.reload();
        });
      } else if (globalWin && globalWin.location) {
        globalWin.location.reload();
      }
    }
  }

  /**
   * Aplica la actualización del Service Worker de manera segura únicamente cuando el usuario
   * lo confirma, preservando las operaciones en IndexedDB.
   */
  public applyUpdateSafely(): void {
    if (!isPlatformBrowser(this.platformId) || !('serviceWorker' in navigator)) return;

    const waiting = this.swRegistration?.waiting;
    if (waiting) {
      navigator.serviceWorker.addEventListener(
        'controllerchange',
        () => {
          window.location.reload();
        },
        { once: true }
      );
      waiting.postMessage({ type: 'SKIP_WAITING' });
    } else {
      this.updateAvailable.set(false);
      window.location.reload();
    }
  }

  public applyUpdateNow(): void {
    this.applyUpdateSafely();
  }

  public dismissUpdateBanner(): void {
    this.updateAvailable.set(false);
  }

  public async promptInstallPwa(): Promise<boolean> {
    if (!this.deferredInstallPrompt) return false;
    try {
      this.deferredInstallPrompt.prompt();
      const choice = await this.deferredInstallPrompt.userChoice;
      this.deferredInstallPrompt = null;
      this.canInstallPwa.set(false);
      return choice?.outcome === 'accepted';
    } catch {
      return false;
    }
  }
}
