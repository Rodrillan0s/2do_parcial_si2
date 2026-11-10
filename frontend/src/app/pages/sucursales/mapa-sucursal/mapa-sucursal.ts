import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild
} from '@angular/core';
import { CommonModule } from '@angular/common';
import * as L from 'leaflet';
import { Sucursal } from '../../../services/sucursales';

@Component({
  selector: 'app-mapa-sucursal',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './mapa-sucursal.html',
  styleUrl: './mapa-sucursal.css'
})
export class MapaSucursalComponent implements AfterViewInit, OnChanges, OnDestroy {

  @ViewChild('mapa', { static: true })
  mapaElemento!: ElementRef<HTMLDivElement>;

  @Input() latitud: number | null | undefined = null;
  @Input() longitud: number | null | undefined = null;

  @Input() sucursales: Sucursal[] = [];
  @Input() modoVisualizacion: boolean = false;

  @Output() ubicacionSeleccionada = new EventEmitter<{
    latitud: number;
    longitud: number;
  }>();

  private mapa: L.Map | null = null;
  private marcador: L.Marker | null = null;
  private marcadoresSucursales: L.Marker[] = [];

  private readonly LATITUD_INICIAL = -17.7833;
  private readonly LONGITUD_INICIAL = -63.1821;
  private readonly ZOOM_INICIAL = 13;

  ngAfterViewInit(): void {
    this.inicializarMapa();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!this.mapa) {
      return;
    }

    if (this.modoVisualizacion) {
      if (changes['sucursales']) {
        this.mostrarSucursales();
      }

      setTimeout(() => {
        this.mapa?.invalidateSize();
      }, 100);

      return;
    }

    if (
      changes['latitud'] ||
      changes['longitud']
    ) {
      this.actualizarUbicacion();
    }
  }

  private inicializarMapa(): void {
    const latitudInicial =
      this.latitud !== null &&
      this.latitud !== undefined
        ? this.latitud
        : this.LATITUD_INICIAL;

    const longitudInicial =
      this.longitud !== null &&
      this.longitud !== undefined
        ? this.longitud
        : this.LONGITUD_INICIAL;

    this.mapa = L.map(
      this.mapaElemento.nativeElement
    ).setView(
      [latitudInicial, longitudInicial],
      this.ZOOM_INICIAL
    );

    L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        attribution: '&copy; OpenStreetMap contributors'
      }
    ).addTo(this.mapa);

    if (!this.modoVisualizacion) {
      this.mapa.on(
        'click',
        (evento: L.LeafletMouseEvent) => {
          this.seleccionarUbicacion(
            evento.latlng.lat,
            evento.latlng.lng
          );
        }
      );

      if (
        this.latitud !== null &&
        this.latitud !== undefined &&
        this.longitud !== null &&
        this.longitud !== undefined
      ) {
        this.crearMarcador(
          this.latitud,
          this.longitud
        );
      }

    } else {
      this.mostrarSucursales();
    }

    setTimeout(() => {
      this.mapa?.invalidateSize();
    }, 100);
  }

  private seleccionarUbicacion(
    latitud: number,
    longitud: number
  ): void {
    if (this.modoVisualizacion) {
      return;
    }

    this.crearMarcador(
      latitud,
      longitud
    );

    this.ubicacionSeleccionada.emit({
      latitud: Number(
        latitud.toFixed(7)
      ),
      longitud: Number(
        longitud.toFixed(7)
      )
    });
  }

  private crearMarcador(
    latitud: number,
    longitud: number
  ): void {
    if (!this.mapa) {
      return;
    }

    if (this.marcador) {
      this.marcador.remove();
    }

    this.marcador = L
      .marker([
        latitud,
        longitud
      ])
      .addTo(this.mapa);

    this.marcador.bindPopup(
      `
        <div style="font-size: 13px;">
          <strong>Ubicación de la sucursal</strong><br>
          Latitud: ${latitud.toFixed(7)}<br>
          Longitud: ${longitud.toFixed(7)}
        </div>
      `
    );
  }

  private mostrarSucursales(): void {
    if (!this.mapa) {
      return;
    }

    this.limpiarMarcadoresSucursales();

    const sucursalesConUbicacion =
      this.sucursales.filter(s =>
        s.latitud !== null &&
        s.latitud !== undefined &&
        s.longitud !== null &&
        s.longitud !== undefined
      );

    if (
      sucursalesConUbicacion.length === 0
    ) {
      this.mapa.setView(
        [
          this.LATITUD_INICIAL,
          this.LONGITUD_INICIAL
        ],
        this.ZOOM_INICIAL
      );

      setTimeout(() => {
        this.mapa?.invalidateSize();
      }, 100);

      return;
    }

    const bounds =
      L.latLngBounds([]);

    sucursalesConUbicacion.forEach(
      sucursal => {

        const latitud =
          Number(sucursal.latitud);

        const longitud =
          Number(sucursal.longitud);

        if (
          Number.isNaN(latitud) ||
          Number.isNaN(longitud)
        ) {
          return;
        }

        const marcador =
          L.marker([
            latitud,
            longitud
          ]).addTo(this.mapa!);

        marcador.bindPopup(
          `
            <div style="font-size: 13px; min-width: 190px;">
              <div style="font-weight: 700; font-size: 15px; margin-bottom: 6px;">
                ${this.escapeHtml(sucursal.nombre || 'Sucursal')}
              </div>

              ${
                sucursal.empresa_nombre
                  ? `
                    <div style="margin-bottom: 3px;">
                      <strong>Tenant:</strong>
                      ${this.escapeHtml(sucursal.empresa_nombre)}
                    </div>
                  `
                  : ''
              }

              ${
                sucursal.ciudad
                  ? `
                    <div style="margin-bottom: 3px;">
                      <strong>Ciudad:</strong>
                      ${this.escapeHtml(sucursal.ciudad)}
                    </div>
                  `
                  : ''
              }

              ${
                sucursal.departamento
                  ? `
                    <div style="margin-bottom: 3px;">
                      <strong>Departamento:</strong>
                      ${this.escapeHtml(sucursal.departamento)}
                    </div>
                  `
                  : ''
              }

              ${
                sucursal.direccion
                  ? `
                    <div style="margin-bottom: 3px;">
                      <strong>Dirección:</strong>
                      ${this.escapeHtml(sucursal.direccion)}
                    </div>
                  `
                  : ''
              }

              ${
                sucursal.telefono
                  ? `
                    <div style="margin-bottom: 3px;">
                      <strong>Teléfono:</strong>
                      ${this.escapeHtml(sucursal.telefono)}
                    </div>
                  `
                  : ''
              }

              <div style="margin-top: 6px; font-size: 11px; color: #71717a;">
                ${latitud.toFixed(7)}, ${longitud.toFixed(7)}
              </div>
            </div>
          `
        );

        this.marcadoresSucursales.push(
          marcador
        );

        bounds.extend([
          latitud,
          longitud
        ]);
      }
    );

    if (
      this.marcadoresSucursales.length > 0 &&
      bounds.isValid()
    ) {
      this.mapa.fitBounds(
        bounds,
        {
          padding: [
            40,
            40
          ],
          maxZoom: 16
        }
      );
    }

    setTimeout(() => {
      this.mapa?.invalidateSize();
    }, 100);
  }

  private limpiarMarcadoresSucursales(): void {
    this.marcadoresSucursales.forEach(
      marcador => marcador.remove()
    );

    this.marcadoresSucursales = [];
  }

  private escapeHtml(valor: string): string {
    return valor
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  private actualizarUbicacion(): void {
    if (
      !this.mapa ||
      this.latitud === null ||
      this.latitud === undefined ||
      this.longitud === null ||
      this.longitud === undefined
    ) {
      return;
    }

    this.mapa.setView(
      [
        this.latitud,
        this.longitud
      ],
      this.mapa.getZoom()
    );

    this.crearMarcador(
      this.latitud,
      this.longitud
    );
  }

  ngOnDestroy(): void {
    if (this.mapa) {
      this.mapa.remove();
      this.mapa = null;
    }

    this.marcador = null;
    this.marcadoresSucursales = [];
  }
}