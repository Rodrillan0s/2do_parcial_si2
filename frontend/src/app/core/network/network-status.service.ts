import { Injectable, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { BehaviorSubject } from 'rxjs';
import { environment } from '../../../environments/environment';

export type ConnectionState = 'ONLINE' | 'OFFLINE' | 'CHECKING' | 'SYNCING';

@Injectable({
  providedIn: 'root'
})
export class NetworkStatusService {
  private platformId = inject(PLATFORM_ID);
  private apiUrl = environment.apiUrl || 'http://127.0.0.1:5000';

  public connectionState = signal<ConnectionState>('ONLINE');
  public isBrowserOnline = signal<boolean>(true);
  public isApiReachable = signal<boolean>(true);
  public lastVerifiedAt = signal<string | null>(null);

  public isOnline = computed(() => {
    const st = this.connectionState();
    return st === 'ONLINE' || st === 'SYNCING';
  });

  public isOffline = computed(() => !this.isOnline());

  private stateSubject = new BehaviorSubject<ConnectionState>('ONLINE');
  public state$ = this.stateSubject.asObservable();

  private reconnectedSubject = new BehaviorSubject<number>(0);
  public reconnected$ = this.reconnectedSubject.asObservable();

  private verifyingInFlight: Promise<boolean> | null = null;
  private lastProbeMs = 0;

  constructor() {
    if (isPlatformBrowser(this.platformId)) {
      const initialNavigatorOnline = typeof navigator !== 'undefined' ? navigator.onLine !== false : true;
      this.isBrowserOnline.set(initialNavigatorOnline);
      this.setState(initialNavigatorOnline ? 'ONLINE' : 'OFFLINE');

      window.addEventListener('online', () => {
        this.isBrowserOnline.set(true);
        this.verifyApiConnectivity(true);
      });

      window.addEventListener('offline', () => {
        this.isBrowserOnline.set(false);
        this.isApiReachable.set(false);
        this.setState('OFFLINE');
      });
    }
  }

  private setState(next: ConnectionState): void {
    const prev = this.connectionState();
    if (prev === next) return;
    this.connectionState.set(next);
    this.stateSubject.next(next);
    if (prev === 'OFFLINE' && next === 'ONLINE') {
      this.reconnectedSubject.next(Date.now());
    }
  }

  public setSyncingState(syncing: boolean): void {
    if (syncing) {
      if (this.connectionState() !== 'OFFLINE') {
        this.setState('SYNCING');
      }
    } else if (this.connectionState() === 'SYNCING') {
      this.setState(this.isBrowserOnline() && this.isApiReachable() ? 'ONLINE' : 'OFFLINE');
    }
  }

  /**
   * Llamado pasivamente cuando una petición HTTP hacia la API responde (incluso 4xx de validación),
   * demostrando conectividad real con el servidor FastAPI sin necesidad de sondeos extra.
   */
  public recordApiSuccess(): void {
    this.isBrowserOnline.set(true);
    this.isApiReachable.set(true);
    this.lastVerifiedAt.set(new Date().toISOString());
    if (this.connectionState() !== 'SYNCING') {
      this.setState('ONLINE');
    }
  }

  /**
   * Llamado cuando ocurre un error de red (status === 0 / ProgressEvent / Failed to fetch).
   * No confía ciegamente en navigator.onLine: marca la API como inalcanzable y programa
   * verificación real.
   */
  public recordApiNetworkFailure(): void {
    this.isApiReachable.set(false);
    this.setState('OFFLINE');
  }

  /**
   * Comprueba disponibilidad real de la API combinando señal del navegador con petición ligera.
   */
  public async verifyApiConnectivity(force: boolean = false): Promise<boolean> {
    if (!isPlatformBrowser(this.platformId)) return true;

    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      this.isBrowserOnline.set(false);
      this.isApiReachable.set(false);
      this.setState('OFFLINE');
      return false;
    }

    const now = Date.now();
    if (!force && this.verifyingInFlight) {
      return this.verifyingInFlight;
    }
    if (!force && now - this.lastProbeMs < 5000 && this.isApiReachable()) {
      return true;
    }

    this.lastProbeMs = now;
    if (this.connectionState() === 'OFFLINE') {
      this.setState('CHECKING');
    }

    this.verifyingInFlight = (async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 3500);
      try {
        const res = await fetch(`${this.apiUrl}/api/sync/ping?_t=${now}`, {
          method: 'GET',
          cache: 'no-store',
          signal: controller.signal
        });
        clearTimeout(timer);
        if (res.ok || res.status < 500) {
          this.recordApiSuccess();
          return true;
        }
        this.recordApiNetworkFailure();
        return false;
      } catch {
        clearTimeout(timer);
        this.recordApiNetworkFailure();
        return false;
      } finally {
        this.verifyingInFlight = null;
      }
    })();

    return this.verifyingInFlight;
  }
}

