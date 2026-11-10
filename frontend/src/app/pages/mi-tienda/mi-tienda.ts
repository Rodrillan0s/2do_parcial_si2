import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { SaasService, MiStorefrontData } from '../../services/saas';
import { AuthService } from '../../services/auth';
import { SeccionStorefront } from '../../services/catalogo-publico';
import { extraerMensajeError } from '../../utils/error-helper';

@Component({
  selector: 'app-mi-tienda',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './mi-tienda.html'
})
export class MiTiendaComponent implements OnInit {
  private saasService = inject(SaasService);
  public authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);

  cargando = false;
  guardando = false;
  mensajeError = '';
  mensajeExito = '';

  datos: MiStorefrontData | null = null;

  // Formulario controlado
  nombreComercial = '';
  slug = '';
  logo = '';
  eslogan = '';
  colorPrimario = '#18181b';
  colorSecundario = '#c2410c';
  tipografia: 'editorial' | 'moderna' | 'clasica' | 'minimal' = 'editorial';
  estiloTarjetas: 'editorial' | 'minimal' | 'borde_suave' = 'editorial';
  bannerTitulo = '';
  bannerSubtitulo = '';
  bannerImagenUrl = '';
  bannerCtaTexto = 'Explorar catálogo';
  publicosHabilitados: string[] = [];
  coleccionesTexto = '';
  secciones: SeccionStorefront[] = [];
  onboardingCompletado = false;

  readonly opcionesPublicos = ['Mujer', 'Hombre', 'Unisex', 'Niños', 'Niñas', 'Bebés'];
  readonly paletasPreset = [
    { nombre: 'Editorial Carbón & Terracota', primario: '#18181b', secundario: '#c2410c' },
    { nombre: 'Sastrería Azul Marino & Oro', primario: '#0f172a', secundario: '#b45309' },
    { nombre: 'Infantil & Juvenil Índigo', primario: '#1e1b4b', secundario: '#4f46e5' },
    { nombre: 'Botánico Esmeralda', primario: '#064e3b', secundario: '#059669' },
    { nombre: 'Minimal Monocromo', primario: '#111827', secundario: '#374151' }
  ];

  readonly nombresSeccion: Record<string, string> = {
    banner: 'Banner Principal (Hero)',
    publicos: 'Navegación por Público Objetivo',
    categorias: 'Categorías de Producto',
    destacados: 'Productos Destacados',
    colecciones: 'Colecciones y Temporadas',
    recomendaciones: 'Recomendaciones Inteligentes (ML)',
    novedades: 'Últimas Novedades'
  };

  get colorTextoSobrePrimario(): '#ffffff' | '#09090b' {
    return this.calcularContraste(this.colorPrimario);
  }

  get colorTextoSobreSecundario(): '#ffffff' | '#09090b' {
    return this.calcularContraste(this.colorSecundario);
  }

  private calcularContraste(hex: string): '#ffffff' | '#09090b' {
    if (!hex) return '#ffffff';
    let c = hex.replace('#', '').trim();
    if (c.length === 3) c = c.split('').map(x => x + x).join('');
    if (c.length !== 6) return '#ffffff';
    const num = parseInt(c, 16);
    const r = (num >> 16) & 255;
    const g = (num >> 8) & 255;
    const b = num & 255;
    const a = [r, g, b].map(v => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    const l = a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
    return l > 0.40 ? '#09090b' : '#ffffff';
  }

  ngOnInit(): void {
    this.cargarConfiguracion();
  }

  cargarConfiguracion(): void {
    this.cargando = true;
    this.mensajeError = '';
    const idEmpresa = this.authService.currentUser()?.id_empresa || 1;

    this.saasService.obtenerMiStorefront(idEmpresa).subscribe({
      next: (res) => {
        this.cargando = false;
        if (res?.data) {
          this.aplicarDatosEnFormulario(res.data);
        }
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.cargando = false;
        this.mensajeError = extraerMensajeError(err, 'No se pudo cargar la configuración de la tienda.');
        this.cdr.markForCheck();
      }
    });
  }

  private aplicarDatosEnFormulario(d: MiStorefrontData): void {
    this.datos = d;
    const cfg = d.configuracion_storefront;
    this.nombreComercial = cfg.nombre_comercial || d.nombre_empresa;
    this.slug = d.slug || '';
    this.logo = d.logo || '';
    this.eslogan = cfg.eslogan || '';
    this.colorPrimario = cfg.color_primario || '#18181b';
    this.colorSecundario = cfg.color_secundario || '#c2410c';
    this.tipografia = cfg.tipografia || 'editorial';
    this.estiloTarjetas = cfg.estilo_tarjetas || 'editorial';
    this.bannerTitulo = cfg.banner_titulo || '';
    this.bannerSubtitulo = cfg.banner_subtitulo || '';
    this.bannerImagenUrl = cfg.banner_imagen_url || '';
    this.bannerCtaTexto = cfg.banner_cta_texto || 'Explorar catálogo';
    this.publicosHabilitados = [...(cfg.publicos_habilitados || [])];
    this.coleccionesTexto = (cfg.colecciones_destacadas || []).join(', ');
    this.secciones = [...(cfg.secciones || [])].sort((a, b) => a.orden - b.orden);
    this.onboardingCompletado = Boolean(cfg.onboarding_completado);
  }

  aplicarPaleta(primario: string, secundario: string): void {
    this.colorPrimario = primario;
    this.colorSecundario = secundario;
  }

  togglePublico(pub: string): void {
    if (this.publicosHabilitados.includes(pub)) {
      this.publicosHabilitados = this.publicosHabilitados.filter(p => p !== pub);
    } else {
      this.publicosHabilitados = [...this.publicosHabilitados, pub];
    }
  }

  moverSeccion(index: number, direccion: -1 | 1): void {
    const target = index + direccion;
    if (target < 0 || target >= this.secciones.length) return;
    const copia = [...this.secciones];
    const temp = copia[index];
    copia[index] = copia[target];
    copia[target] = temp;
    this.secciones = copia.map((s, idx) => ({ ...s, orden: idx + 1 }));
  }

  guardarConfiguracion(marcarOnboardingListo = false): void {
    if (!this.datos) return;
    this.guardando = true;
    this.mensajeError = '';
    this.mensajeExito = '';

    const colecciones = this.coleccionesTexto
      .split(',')
      .map(c => c.trim())
      .filter(Boolean);

    const payload = {
      nombre_comercial: this.nombreComercial.trim(),
      slug: this.slug.trim(),
      logo: this.logo.trim(),
      eslogan: this.eslogan.trim(),
      color_primario: this.colorPrimario,
      color_secundario: this.colorSecundario,
      tipografia: this.tipografia,
      estilo_tarjetas: this.estiloTarjetas,
      banner_titulo: this.bannerTitulo.trim(),
      banner_subtitulo: this.bannerSubtitulo.trim(),
      banner_imagen_url: this.bannerImagenUrl.trim(),
      banner_cta_texto: this.bannerCtaTexto.trim() || 'Explorar catálogo',
      publicos_habilitados: this.publicosHabilitados,
      colecciones_destacadas: colecciones,
      secciones: this.secciones,
      onboarding_completado: marcarOnboardingListo ? true : this.onboardingCompletado
    };

    this.saasService.actualizarMiStorefront(payload, this.datos.id_empresa).subscribe({
      next: (res) => {
        this.guardando = false;
        if (res?.data) {
          this.aplicarDatosEnFormulario(res.data);
        }
        this.mensajeExito = 'Configuración del storefront guardada y publicada correctamente.';
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.guardando = false;
        this.mensajeError = extraerMensajeError(err, 'Error al guardar la configuración del storefront.');
        this.cdr.markForCheck();
      }
    });
  }
}
