import { Component, OnInit, inject, PLATFORM_ID, DestroyRef } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import {
  ProductosService,
  Producto,
  ImagenProducto,
  VarianteProducto,
  PromocionProducto,
Promocion
} from '../../../services/productos';
import { CategoriasService, Categoria } from '../../../services/categorias';
import { TallasColoresService, Talla, ColorPrenda } from '../../../services/tallas-colores';
import { AuthService } from '../../../services/auth';
import { EmpresaService, Empresa } from '../../../services/empresa';

@Component({
  selector: 'app-productos',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './productos.html'
})
export class ProductosComponent implements OnInit {
  private productosService = inject(ProductosService);
  private categoriasService = inject(CategoriasService);
  private tallasColoresService = inject(TallasColoresService);
  private empresaService = inject(EmpresaService);
  private authService = inject(AuthService);
  private platformId = inject(PLATFORM_ID);
  private destroyRef = inject(DestroyRef);
  private busquedaSubject$ = new Subject<string>();

  // Estados de lista
  productos: Producto[] = [];
  empresas: Empresa[] = [];
  cargando: boolean = false;
  mensajeAlerta: string = '';
  tipoAlerta: 'exito' | 'error' | 'info' = 'info';

  // Filtros y Paginación
  busqueda: string = '';
  filtroCategoria: number | null = null;
  filtroEstado: string = 'TODOS'; // 'TODOS' | 'ACTIVOS' | 'INACTIVOS'
  filtroEmpresa: number | null = null;
  paginaActual: number = 1;
  itemsPorPagina: number = 20;
  readonly temporadaActual: string = this.calcularTemporadaActual();

  // Catálogos activos para selección
  categoriasDisponibles: Categoria[] = [];
  tallasDisponibles: Talla[] = [];
  coloresDisponibles: ColorPrenda[] = [];
  private productosRequestVersion = 0;
  private catalogosRequestVersion = 0;

  // Modal Principal (Crear / Editar)
  mostrarModal: boolean = false;
  modoEdicion: boolean = false;
  tabModalActiva: 'general' | 'variantes' | 'galeria' | 'ar' = 'general';
  guardando: boolean = false;

  // Formulario de Producto
  productoForm: {
    id_producto?: number;
    id_empresa?: number;
    id_categoria: number | null;
    nombre: string;
    descripcion: string;
    codigo_producto: string;
    precio: number | null;
    temporada: string;
    coleccion: string;
    marca: string;
    genero: string;
    activo: boolean;
    tallas_seleccionadas: number[];
    colores_seleccionados: number[];
    precios_por_talla: { [id_talla: number]: number };
    imagenes: ImagenProducto[];
    tiene_ra: boolean;
    tipo_prenda_ra: string;
    modelo_2d_url: string;
  } = this.getFormVacio();

  // Subida de imagen
  subiendoImagen: boolean = false;
  subiendoFoto2D: boolean = false;

  // Modal Rápido de Galería
  mostrarModalGaleria: boolean = false;
  productoGaleriaSeleccionado: Producto | null = null;

  // Modal de Eliminación / Desactivación
  mostrarModalEliminar: boolean = false;
  productoAeliminar: Producto | null = null;
  eliminando: boolean = false;

  // Modal de Zoom de Imagen
  zoomImagenUrl: string | null = null;
  // Modal de Promociones
mostrarModalPromocion: boolean = false;
productoPromocionSeleccionado: Producto | null = null;
promocionesDisponibles: Promocion[] = [];
promocionesProducto: PromocionProducto[] = [];
promocionSeleccionada: number | null = null;
porcentajeDescuento: number | null = null;
cargandoPromociones: boolean = false;
guardandoPromocion: boolean = false;
  // Permisos y Scope
  get esSuperAdmin(): boolean {
    return this.authService.getScopeLevel() === 'PLATAFORMA';
  }

  get userCompanyId(): number | undefined {
    return this.authService.obtenerUsuario()?.id_empresa ?? undefined;
  }

  get puedeCrear(): boolean {
    return this.authService.hasPermission('productos.crear');
  }

  get puedeEditar(): boolean {
    return this.authService.hasPermission('productos.editar');
  }

  get puedeEliminar(): boolean {
    return this.authService.hasPermission('productos.eliminar');
  }

  // Métricas computadas
  get totalProductos(): number {
    return this.productos.length;
  }

  get totalActivos(): number {
    return this.productos.filter(p => p.activo).length;
  }

  get totalInactivos(): number {
    return this.productos.filter(p => !p.activo).length;
  }

  get totalVariantes(): number {
    return this.productos.reduce((sum, p) => sum + (p.total_variantes || 0), 0);
  }

  // Combinaciones generadas en vivo (N tallas x M colores)
  get combinacionesGeneradas(): { talla: Talla; color: ColorPrenda }[] {
    const res: { talla: Talla; color: ColorPrenda }[] = [];
    const tallas = this.tallasDisponibles.filter(t => t.id_talla !== undefined && this.productoForm.tallas_seleccionadas.includes(t.id_talla));
    const colores = this.coloresDisponibles.filter(c => c.id_color !== undefined && this.productoForm.colores_seleccionados.includes(c.id_color));

    for (const t of tallas) {
      for (const c of colores) {
        res.push({ talla: t, color: c });
      }
    }
    return res;
  }
  private calcularTemporadaActual(): string {
    const mes = new Date().getMonth() + 1;
    if ([12, 1, 2].includes(mes)) return 'VERANO';
    if ([3, 4, 5].includes(mes)) return 'OTOÑO';
    if ([6, 7, 8].includes(mes)) return 'INVIERNO';
    return 'PRIMAVERA';
  }

  esTemporadaActual(prod: Producto): boolean {
    const temporada = (prod.temporada || 'PERMANENTE')
      .trim()
      .toUpperCase();

    return temporada === 'PERMANENTE'
      || temporada === this.temporadaActual;
  }

  // Lista filtrada en cliente
  get productosFiltrados(): Producto[] {
    return this.productos.filter(p => {
      // Filtro de estado
      if (this.filtroEstado === 'ACTIVOS' && !p.activo) return false;
      if (this.filtroEstado === 'INACTIVOS' && p.activo) return false;

      // Filtro de categoría
      if (this.filtroCategoria && p.id_categoria !== this.filtroCategoria) return false;

      // Filtro de búsqueda
      if (this.busqueda.trim()) {
        const q = this.busqueda.toLowerCase();
        const coincideNombre = p.nombre.toLowerCase().includes(q);
        const coincideCodigo = (p.codigo_producto || '').toLowerCase().includes(q);
        const coincideCat = (p.categoria_nombre || '').toLowerCase().includes(q);
        const coincideDesc = (p.descripcion || '').toLowerCase().includes(q);
        if (!coincideNombre && !coincideCodigo && !coincideCat && !coincideDesc) return false;
      }

      return true;
    });
  }

  get totalPaginas(): number {
    return Math.max(1, Math.ceil(this.productosFiltrados.length / this.itemsPorPagina));
  }

  get productosPaginados(): Producto[] {
    const filtrados = this.productosFiltrados;
    const maxPag = Math.max(1, Math.ceil(filtrados.length / this.itemsPorPagina));
    const pag = Math.min(this.paginaActual, maxPag);
    const inicio = (pag - 1) * this.itemsPorPagina;
    return filtrados.slice(inicio, inicio + this.itemsPorPagina);
  }

  cambiarPagina(nuevaPagina: number): void {
    if (nuevaPagina >= 1 && nuevaPagina <= this.totalPaginas) {
      this.paginaActual = nuevaPagina;
    }
  }

  ngOnInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.cargarDatosIniciales();

    this.busquedaSubject$
      .pipe(
        debounceTime(250),
        distinctUntilChanged(),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(val => {
        this.busqueda = val;
        this.paginaActual = 1;
      });

    this.authService.companyChanged$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(empresa => {
        if (this.esSuperAdmin) {
          const nuevoFiltro = empresa ? empresa.id_empresa : null;
          if (this.filtroEmpresa !== nuevoFiltro) {
            this.filtroEmpresa = nuevoFiltro;
            this.productos = [];
            this.paginaActual = 1;
            this.mostrarModal = false;
            this.cargarProductos();
            this.cargarCategoriasActivas(this.filtroEmpresa || undefined);
          }
        }
      });
  }

  trackByProductoId(index: number, prod: Producto): number {
    return prod.id_producto || index;
  }

  onBusquedaInput(event: Event): void {
    const val = (event.target as HTMLInputElement)?.value || '';
    this.busquedaSubject$.next(val);
  }

  cargarDatosIniciales(): void {
    if (this.esSuperAdmin) {
      this.cargarEmpresas();
      this.filtroEmpresa = this.authService.getEffectiveCompanyId();
    } else {
      this.filtroEmpresa = this.userCompanyId || null;
    }
    this.cargarProductos();
    // Solo cargar categorías al entrar; tallas y colores se difieren hasta abrir el modal Crear/Editar
    this.cargarCategoriasActivas(this.filtroEmpresa || undefined);
  }

  cargarEmpresas(): void {
    this.empresaService.listarEmpresas().subscribe({
      next: (res) => {
        this.empresas = (res.data || []).filter(e => e.estado === 'ACTIVO');
      },
      error: (err) => console.error('Error al cargar empresas:', err)
    });
  }

  onFiltroEmpresaChange(): void {
    if (this.esSuperAdmin) {
      if (this.filtroEmpresa) {
        const emp = this.empresas.find(e => e.id_empresa === Number(this.filtroEmpresa));
        if (emp && emp.id_empresa) {
          this.authService.setSelectedCompany({ id_empresa: emp.id_empresa, nombre_empresa: emp.nombre_empresa });
        }
      } else {
        this.authService.setSelectedCompany(null);
      }
    }
    this.paginaActual = 1;
    this.cargarProductos();
    this.cargarCategoriasActivas(this.filtroEmpresa || undefined);
  }

  onModalEmpresaChange(): void {
    if (this.productoForm.id_empresa) {
      this.cargarCatalogosActivos(this.productoForm.id_empresa);
      // Reset selected category and variants to avoid cross-tenant pollution
      this.productoForm.id_categoria = null;
      this.productoForm.tallas_seleccionadas = [];
      this.productoForm.colores_seleccionados = [];
    }
  }

  cargarProductos(): void {
    this.cargando = true;
    const requestVersion = ++this.productosRequestVersion;
    const empresaSolicitada = this.filtroEmpresa;
    const params: any = {};
    if (empresaSolicitada) params.id_empresa = empresaSolicitada;

    this.productosService.listarProductos(params).subscribe({
      next: (res) => {
        if (requestVersion !== this.productosRequestVersion || empresaSolicitada !== this.filtroEmpresa) return;
        this.productos = res.data || [];
        this.cargando = false;
      },
      error: (err) => {
        if (requestVersion !== this.productosRequestVersion || empresaSolicitada !== this.filtroEmpresa) return;
        this.mostrarAlerta(err.error?.detail || 'Error al cargar los productos.', 'error');
        this.cargando = false;
      }
    });
  }

  cargarCategoriasActivas(idEmpresa?: number): void {
    const paramsCat: any = { solo_activas: true };
    if (idEmpresa) {
      paramsCat.id_empresa = idEmpresa;
    }
    this.categoriasService.listarCategorias(paramsCat).subscribe({
      next: (res) => {
        this.categoriasDisponibles = res.data || [];
      },
      error: (err) => console.error('Error al cargar categorías activas:', err)
    });
  }

  cargarCatalogosActivos(idEmpresa?: number): void {
    const requestVersion = ++this.catalogosRequestVersion;
    const paramsCat: any = { solo_activas: true };
    const paramsTallas: any = { solo_activas: true };
    const paramsColores: any = { solo_activos: true };

    if (idEmpresa) {
      paramsCat.id_empresa = idEmpresa;
      paramsTallas.id_empresa = idEmpresa;
      paramsColores.id_empresa = idEmpresa;
    }

    // 1. Categorías activas
    this.categoriasService.listarCategorias(paramsCat).subscribe({
      next: (res) => {
        if (requestVersion !== this.catalogosRequestVersion) return;
        this.categoriasDisponibles = res.data || [];
      },
      error: (err) => console.error('Error al cargar categorías activas:', err)
    });

    // 2. Tallas activas (diferidas a apertura de modal, cacheadas por servicio)
    this.tallasColoresService.listarTallas(paramsTallas).subscribe({
      next: (res) => {
        if (requestVersion !== this.catalogosRequestVersion) return;
        this.tallasDisponibles = res.data || [];
      },
      error: (err) => console.error('Error al cargar tallas activas:', err)
    });

    // 3. Colores activos (diferidos a apertura de modal, cacheados por servicio)
    this.tallasColoresService.listarColores(paramsColores).subscribe({
      next: (res) => {
        if (requestVersion !== this.catalogosRequestVersion) return;
        this.coloresDisponibles = res.data || [];
      },
      error: (err) => console.error('Error al cargar colores activos:', err)
    });
  }

  // ==============================================================================
  // MODAL CREAR / EDITAR
  // ==============================================================================

  abrirModalCrear(): void {
    this.modoEdicion = false;
    this.tabModalActiva = 'general';
    this.productoForm = this.getFormVacio();
    this.subiendoImagen = false;

    if (this.esSuperAdmin) {
      this.productoForm.id_empresa = this.filtroEmpresa || (this.empresas[0]?.id_empresa);
    } else {
      this.productoForm.id_empresa = this.userCompanyId;
    }

    if (this.productoForm.id_empresa) {
      this.cargarCatalogosActivos(this.productoForm.id_empresa);
    }

    this.mostrarModal = true;
  }

  abrirModalEditar(prod: Producto): void {
    if (this.filtroEmpresa && prod.id_empresa !== this.filtroEmpresa) {
      this.mostrarAlerta('El producto seleccionado no pertenece al Tenant activo.', 'error');
      return;
    }
    this.cargando = true;
    this.productosService.obtenerProducto(prod.id_producto!).subscribe({
      next: (res) => {
        const p = res.data;
        this.modoEdicion = true;
        this.tabModalActiva = 'general';

        if (p.id_empresa) {
          this.cargarCatalogosActivos(p.id_empresa);
        }

        // Extraer IDs únicos de tallas y colores de sus variantes
        const tallasIds = Array.from(new Set((p.variantes || []).filter(v => v.activo).map(v => v.id_talla)));
        const coloresIds = Array.from(new Set((p.variantes || []).filter(v => v.activo).map(v => v.id_color)));

        const preciosPorTalla: { [id_talla: number]: number } = {};
        (p.variantes || []).forEach(v => {
          if (v.activo && v.id_talla && v.precio) {
            preciosPorTalla[v.id_talla] = v.precio;
          }
        });

        this.productoForm = {
          id_producto: p.id_producto,
          id_empresa: p.id_empresa,
          id_categoria: p.id_categoria,
          nombre: p.nombre,
          descripcion: p.descripcion || '',
          codigo_producto: p.codigo_producto || '',
          precio: p.precio,
          temporada: p.temporada || '',
          coleccion: p.coleccion || '',
          marca: p.marca || '',
          genero: p.genero || 'Unisex',
          activo: p.activo,
          tallas_seleccionadas: tallasIds,
          colores_seleccionados: coloresIds,
          precios_por_talla: preciosPorTalla,
          imagenes: p.imagenes || [],
          tiene_ra: !!p.tiene_ra,
          tipo_prenda_ra: p.tipo_prenda_ra || 'TOP',
          modelo_2d_url: p.modelo_2d_url || ''
        };

        this.mostrarModal = true;
        this.cargando = false;
      },
      error: (err) => {
        this.mostrarAlerta(err.error?.detail || 'Error al obtener el producto.', 'error');
        this.cargando = false;
      }
    });
  }

  cerrarModal(): void {
    this.mostrarModal = false;
    this.subiendoImagen = false;
    this.subiendoFoto2D = false;
    this.productoForm = this.getFormVacio();
  }

  guardarProducto(): void {
    // Validaciones previas
    if (!this.productoForm.nombre.trim()) {
      this.mostrarAlerta('El nombre de la prenda es obligatorio.', 'error');
      this.tabModalActiva = 'general';
      return;
    }
    if (!this.productoForm.id_categoria) {
      this.mostrarAlerta('Debe seleccionar una categoría.', 'error');
      this.tabModalActiva = 'general';
      return;
    }
    if (!this.productoForm.precio || this.productoForm.precio <= 0) {
      this.mostrarAlerta('El precio de la prenda debe ser mayor a 0.', 'error');
      this.tabModalActiva = 'general';
      return;
    }

    const targetEmpresa = this.productoForm.id_empresa || this.userCompanyId;
    if (!targetEmpresa) {
      this.mostrarAlerta('Debe seleccionar el Tenant / Tienda correspondiente.', 'error');
      this.tabModalActiva = 'general';
      return;
    }

    this.guardando = true;

    const tallasPermitidas = new Set(
      this.tallasDisponibles
        .map(t => t.id_talla)
        .filter((id): id is number => id !== undefined)
    );
    const coloresPermitidos = new Set(
      this.coloresDisponibles
        .map(c => c.id_color)
        .filter((id): id is number => id !== undefined)
    );
    const tallasSeleccionadas = this.productoForm.tallas_seleccionadas.filter(id => tallasPermitidas.has(id));
    const coloresSeleccionados = this.productoForm.colores_seleccionados.filter(id => coloresPermitidos.has(id));

    if (this.modoEdicion && this.productoForm.id_producto) {
      // Actualizar
      const payload = {
        id_categoria: this.productoForm.id_categoria,
        nombre: this.productoForm.nombre.trim(),
        precio: this.productoForm.precio,
        descripcion: this.productoForm.descripcion.trim(),
        codigo_producto: this.productoForm.codigo_producto.trim(),
        temporada: this.productoForm.temporada.trim(),
        coleccion: this.productoForm.coleccion.trim(),
        marca: this.productoForm.marca,
        genero: this.productoForm.genero,
        activo: this.productoForm.activo,
        tallas_ids: tallasSeleccionadas,
        colores_ids: coloresSeleccionados,
        precios_por_talla: this.productoForm.precios_por_talla,
        tiene_ra: !!this.productoForm.tiene_ra,
        tipo_prenda_ra: this.productoForm.tiene_ra ? this.productoForm.tipo_prenda_ra : undefined,
        modelo_2d_url: this.productoForm.tiene_ra ? (this.productoForm.modelo_2d_url || undefined) : undefined
      };

      this.productosService.actualizarProducto(this.productoForm.id_producto, payload).subscribe({
        next: (res) => {
          this.mostrarAlerta(res.message || 'Producto actualizado con éxito.', 'exito');
          this.guardando = false;
          this.cerrarModal();
          this.cargarProductos();
        },
        error: (err) => {
          this.mostrarAlerta(err.error?.detail || 'Error al actualizar el producto.', 'error');
          this.guardando = false;
        }
      });
    } else {
      // Crear
      const payload = {
        id_empresa: this.productoForm.id_empresa || this.userCompanyId,
        id_categoria: this.productoForm.id_categoria,
        nombre: this.productoForm.nombre.trim(),
        precio: this.productoForm.precio,
        descripcion: this.productoForm.descripcion.trim(),
        codigo_producto: this.productoForm.codigo_producto.trim() || undefined,
        temporada: this.productoForm.temporada.trim() || undefined,
        coleccion: this.productoForm.coleccion.trim() || undefined,
        marca: this.productoForm.marca,
        genero: this.productoForm.genero,
        activo: this.productoForm.activo,
        tallas_ids: this.productoForm.tallas_seleccionadas,
        colores_ids: this.productoForm.colores_seleccionados,
        precios_por_talla: this.productoForm.precios_por_talla,
        imagenes: this.productoForm.imagenes.map(img => ({
          imagen_url: img.imagen_url,
          public_id: img.public_id,
          es_principal: img.es_principal
        })),
        tiene_ra: !!this.productoForm.tiene_ra,
        tipo_prenda_ra: this.productoForm.tiene_ra ? this.productoForm.tipo_prenda_ra : undefined,
        modelo_2d_url: this.productoForm.tiene_ra ? (this.productoForm.modelo_2d_url || undefined) : undefined
      };

      this.productosService.crearProducto(payload).subscribe({
        next: (res) => {
          this.mostrarAlerta(res.message || 'Producto registrado exitosamente con sus variantes.', 'exito');
          this.guardando = false;
          this.cerrarModal();
          this.cargarProductos();
        },
        error: (err) => {
          this.mostrarAlerta(err.error?.detail || 'Error al registrar el producto.', 'error');
          this.guardando = false;
        }
      });
    }
  }

  // ==============================================================================
  // GESTIÓN DE VARIANTES (TALLAS & COLORES & PRECIOS DIFERENCIADOS)
  // ==============================================================================

  toggleTalla(tallaId?: number): void {
    if (tallaId === undefined) return;
    const idx = this.productoForm.tallas_seleccionadas.indexOf(tallaId);
    if (idx > -1) {
      this.productoForm.tallas_seleccionadas.splice(idx, 1);
      delete this.productoForm.precios_por_talla[tallaId];
    } else {
      this.productoForm.tallas_seleccionadas.push(tallaId);
      if (this.productoForm.precios_por_talla[tallaId] === undefined) {
        this.productoForm.precios_por_talla[tallaId] = this.productoForm.precio || 0;
      }
    }
  }

  obtenerPrecioTalla(tallaId?: number): number {
    if (tallaId === undefined) return this.productoForm.precio || 0;
    if (this.productoForm.precios_por_talla && this.productoForm.precios_por_talla[tallaId] !== undefined) {
      return this.productoForm.precios_por_talla[tallaId];
    }
    return this.productoForm.precio || 0;
  }

  asignarPrecioTalla(tallaId: number, precio: any): void {
    const num = Number(precio);
    if (!isNaN(num) && num > 0) {
      this.productoForm.precios_por_talla[tallaId] = num;
    } else {
      delete this.productoForm.precios_por_talla[tallaId];
    }
  }

  aplicarPrecioBaseATodasTallas(): void {
    const base = this.productoForm.precio || 0;
    for (const tid of this.productoForm.tallas_seleccionadas) {
      this.productoForm.precios_por_talla[tid] = base;
    }
    this.mostrarAlerta(`Precio base (Bs. ${base.toFixed(2)}) aplicado a todas las tallas seleccionadas.`, 'info');
  }

  get tallasSeleccionadasObjetos(): Talla[] {
    return this.tallasDisponibles.filter(t => t.id_talla !== undefined && this.productoForm.tallas_seleccionadas.includes(t.id_talla));
  }

  toggleColor(colorId?: number): void {
    if (colorId === undefined) return;
    const idx = this.productoForm.colores_seleccionados.indexOf(colorId);
    if (idx > -1) {
      this.productoForm.colores_seleccionados.splice(idx, 1);
    } else {
      this.productoForm.colores_seleccionados.push(colorId);
    }
  }

  seleccionarTodasTallas(): void {
    this.productoForm.tallas_seleccionadas = this.tallasDisponibles
      .map(t => t.id_talla)
      .filter((id): id is number => id !== undefined);
  }

  deseleccionarTodasTallas(): void {
    this.productoForm.tallas_seleccionadas = [];
  }

  seleccionarTodosColores(): void {
    this.productoForm.colores_seleccionados = this.coloresDisponibles
      .map(c => c.id_color)
      .filter((id): id is number => id !== undefined);
  }

  deseleccionarTodosColores(): void {
    this.productoForm.colores_seleccionados = [];
  }

  // ==============================================================================
  // GESTIÓN DE IMÁGENES (CLOUDINARY)
  // ==============================================================================

  onFileSelected(event: any): void {
    const file = event.target.files[0];
    if (!file) return;

    // Validación de formato
    const tiposPermitidos = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg'];
    if (!tiposPermitidos.includes(file.type)) {
      this.mostrarAlerta('Formato inválido. Solo se admiten archivos JPG, PNG y WEBP.', 'error');
      event.target.value = '';
      return;
    }

    // Validación de tamaño (máx 10 MB con optimización automática)
    if (file.size > 10 * 1024 * 1024) {
      this.mostrarAlerta('La imagen supera el límite permitido de 10 MB.', 'error');
      event.target.value = '';
      return;
    }

    this.subiendoImagen = true;
    this.productosService.subirImagenCloudinary(file).subscribe({
      next: (res) => {
        const nuevaImg: ImagenProducto = {
          imagen_url: res.data.imagen_url,
          public_id: res.data.public_id,
          es_principal: this.productoForm.imagenes.length === 0
        };

        // Si ya estamos editando un producto existente en BD, vincular de inmediato
        if (this.modoEdicion && this.productoForm.id_producto) {
          this.productosService.agregarImagenAProducto(
            this.productoForm.id_producto,
            nuevaImg.imagen_url,
            nuevaImg.public_id,
            nuevaImg.es_principal
          ).subscribe({
            next: (vincRes) => {
              nuevaImg.id_imagen = vincRes.id_imagen;
              this.productoForm.imagenes.push(nuevaImg);
              this.subiendoImagen = false;
              this.mostrarAlerta('Foto subida y vinculada a la prenda.', 'exito');
            },
            error: (err) => {
              this.mostrarAlerta(err.error?.detail || 'Error al vincular imagen.', 'error');
              this.subiendoImagen = false;
            }
          });
        } else {
          // En modo creación se almacena en el estado local hasta guardar el producto
          this.productoForm.imagenes.push(nuevaImg);
          this.subiendoImagen = false;
          this.mostrarAlerta('Foto cargada exitosamente.', 'exito');
        }
        event.target.value = '';
      },
      error: (err) => {
        this.mostrarAlerta(err.error?.detail || 'Error al subir la imagen a Cloudinary.', 'error');
        this.subiendoImagen = false;
        event.target.value = '';
      }
    });
  }

  establecerPortada(index: number): void {
    const img = this.productoForm.imagenes[index];
    if (!img) return;

    if (this.modoEdicion && this.productoForm.id_producto && img.id_imagen) {
      this.productosService.marcarPortada(this.productoForm.id_producto, img.id_imagen).subscribe({
        next: () => {
          this.productoForm.imagenes.forEach((im, i) => im.es_principal = (i === index));
          this.mostrarAlerta('Portada actualizada.', 'exito');
        },
        error: (err) => this.mostrarAlerta(err.error?.detail || 'Error al cambiar portada.', 'error')
      });
    } else {
      this.productoForm.imagenes.forEach((im, i) => im.es_principal = (i === index));
    }
  }

  eliminarImagen(index: number): void {
    const img = this.productoForm.imagenes[index];
    if (!img) return;

    if (this.modoEdicion && this.productoForm.id_producto && img.id_imagen) {
      this.productosService.eliminarImagen(this.productoForm.id_producto, img.id_imagen).subscribe({
        next: () => {
          this.productoForm.imagenes.splice(index, 1);
          // Si eliminamos la principal y quedan más fotos, la primera pasa a ser principal
          if (img.es_principal && this.productoForm.imagenes.length > 0) {
            this.productoForm.imagenes[0].es_principal = true;
          }
          this.mostrarAlerta('Imagen eliminada de la galería.', 'exito');
        },
        error: (err) => this.mostrarAlerta(err.error?.detail || 'Error al eliminar imagen.', 'error')
      });
    } else {
      this.productoForm.imagenes.splice(index, 1);
      if (img.es_principal && this.productoForm.imagenes.length > 0) {
        this.productoForm.imagenes[0].es_principal = true;
      }
    }
  }

  // ==============================================================================
  // MODAL RÁPIDO DE GALERÍA
  // ==============================================================================

  abrirModalGaleria(prod: Producto): void {
    this.cargando = true;
    this.productosService.obtenerProducto(prod.id_producto!).subscribe({
      next: (res) => {
        this.productoGaleriaSeleccionado = res.data;
        this.mostrarModalGaleria = true;
        this.cargando = false;
      },
      error: (err) => {
        this.mostrarAlerta(err.error?.detail || 'Error al cargar fotos de la prenda.', 'error');
        this.cargando = false;
      }
    });
  }

  cerrarModalGaleria(): void {
    this.mostrarModalGaleria = false;
    this.subiendoImagen = false;
    this.productoGaleriaSeleccionado = null;
    this.cargarProductos();
  }

  subirFotoGaleriaRapida(event: any): void {
    const file = event.target.files[0];
    if (!file || !this.productoGaleriaSeleccionado) return;

    const tiposPermitidos = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg'];
    if (!tiposPermitidos.includes(file.type)) {
      this.mostrarAlerta('Formato inválido. Solo se admiten archivos JPG, PNG y WEBP.', 'error');
      event.target.value = '';
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      this.mostrarAlerta('La imagen supera el límite permitido de 10 MB.', 'error');
      event.target.value = '';
      return;
    }

    this.subiendoImagen = true;
    this.productosService.subirImagenCloudinary(file).subscribe({
      next: (res) => {
        const esPpal = (this.productoGaleriaSeleccionado!.imagenes || []).length === 0;
        this.productosService.agregarImagenAProducto(
          this.productoGaleriaSeleccionado!.id_producto!,
          res.data.imagen_url,
          res.data.public_id,
          esPpal
        ).subscribe({
          next: (vincRes) => {
            if (!this.productoGaleriaSeleccionado!.imagenes) {
              this.productoGaleriaSeleccionado!.imagenes = [];
            }
            this.productoGaleriaSeleccionado!.imagenes.push({
              id_imagen: vincRes.id_imagen,
              imagen_url: res.data.imagen_url,
              public_id: res.data.public_id,
              es_principal: esPpal
            });
            this.subiendoImagen = false;
            this.mostrarAlerta('Imagen agregada a la galería.', 'exito');
          },
          error: (err) => {
            this.mostrarAlerta(err.error?.detail || 'Error al vincular foto.', 'error');
            this.subiendoImagen = false;
          }
        });
        event.target.value = '';
      },
      error: (err) => {
        this.mostrarAlerta(err.error?.detail || 'Error al subir foto.', 'error');
        this.subiendoImagen = false;
        event.target.value = '';
      }
    });
  }

  establecerPortadaRapida(img: ImagenProducto): void {
    if (!this.productoGaleriaSeleccionado || !img.id_imagen) return;
    this.productosService.marcarPortada(this.productoGaleriaSeleccionado.id_producto!, img.id_imagen).subscribe({
      next: () => {
        this.productoGaleriaSeleccionado!.imagenes?.forEach(i => i.es_principal = (i.id_imagen === img.id_imagen));
        this.mostrarAlerta('Portada actualizada.', 'exito');
      },
      error: (err) => this.mostrarAlerta(err.error?.detail || 'Error al cambiar portada.', 'error')
    });
  }

  eliminarFotoRapida(img: ImagenProducto, idx: number): void {
    if (!this.productoGaleriaSeleccionado || !img.id_imagen) return;
    this.productosService.eliminarImagen(this.productoGaleriaSeleccionado.id_producto!, img.id_imagen).subscribe({
      next: () => {
        this.productoGaleriaSeleccionado!.imagenes?.splice(idx, 1);
        this.mostrarAlerta('Foto eliminada.', 'exito');
      },
      error: (err) => this.mostrarAlerta(err.error?.detail || 'Error al borrar foto.', 'error')
    });
  }



// ==============================================================================
// GESTIÓN DE PROMOCIONES
// ==============================================================================

abrirModalPromocion(prod: Producto): void {
  this.productoPromocionSeleccionado = prod;
  this.promocionSeleccionada = null;
  this.porcentajeDescuento = null;
  this.promocionesProducto = [];
  this.promocionesDisponibles = [];
  this.mostrarModalPromocion = true;
  this.cargandoPromociones = true;

  this.productosService.listarPromociones(true).subscribe({
    next: (res) => {
      this.promocionesDisponibles = res.data || [];
      this.cargarPromocionesProducto(prod.id_producto!);
    },
    error: (err) => {
      this.mostrarAlerta(
        err.error?.detail || 'Error al cargar las promociones.',
        'error'
      );
      this.cargandoPromociones = false;
    }
  });
}

cargarPromocionesProducto(id_producto: number): void {
  this.productosService.listarPromocionesProducto(id_producto).subscribe({
    next: (res) => {
      this.promocionesProducto = res.data || [];
      this.cargandoPromociones = false;
    },
    error: (err) => {
      this.mostrarAlerta(
        err.error?.detail || 'Error al cargar las promociones del producto.',
        'error'
      );
      this.cargandoPromociones = false;
    }
  });
}

cerrarModalPromocion(): void {
  this.mostrarModalPromocion = false;
  this.productoPromocionSeleccionado = null;
  this.promocionesDisponibles = [];
  this.promocionesProducto = [];
  this.promocionSeleccionada = null;
  this.porcentajeDescuento = null;
}

asignarPromocion(): void {
  if (!this.productoPromocionSeleccionado?.id_producto) {
    return;
  }

  if (!this.promocionSeleccionada) {
    this.mostrarAlerta(
      'Debe seleccionar una promoción.',
      'error'
    );
    return;
  }

  if (
    this.porcentajeDescuento === null ||
    this.porcentajeDescuento <= 0 ||
    this.porcentajeDescuento > 100
  ) {
    this.mostrarAlerta(
      'El porcentaje de descuento debe estar entre 0.01 y 100.',
      'error'
    );
    return;
  }

  this.guardandoPromocion = true;

  this.productosService.asignarPromocion(
    this.productoPromocionSeleccionado.id_producto,
    this.promocionSeleccionada,
    this.porcentajeDescuento
  ).subscribe({
    next: (res) => {
      this.mostrarAlerta(
        res.message || 'Promoción asignada correctamente.',
        'exito'
      );

      this.guardandoPromocion = false;

      this.cargarPromocionesProducto(
        this.productoPromocionSeleccionado!.id_producto!
      );

      this.cargarProductos();

      this.promocionSeleccionada = null;
      this.porcentajeDescuento = null;
    },
    error: (err) => {
      this.mostrarAlerta(
        err.error?.detail || 'Error al asignar la promoción.',
        'error'
      );
      this.guardandoPromocion = false;
    }
  });
}

eliminarPromocionProducto(promocion: PromocionProducto): void {
  if (
    !this.productoPromocionSeleccionado?.id_producto ||
    !promocion.id_promocion_producto
  ) {
    return;
  }

  this.productosService.eliminarPromocion(
    this.productoPromocionSeleccionado.id_producto,
    promocion.id_promocion_producto
  ).subscribe({
    next: (res) => {
      this.mostrarAlerta(
        res.message || 'Promoción quitada del producto.',
        'exito'
      );

      this.cargarPromocionesProducto(
        this.productoPromocionSeleccionado!.id_producto!
      );

      this.cargarProductos();
    },
    error: (err) => {
      this.mostrarAlerta(
        err.error?.detail || 'Error al quitar la promoción.',
        'error'
      );
    }
  });
}



  // ==============================================================================
  // CAMBIAR ESTADO Y ELIMINAR
  // ==============================================================================

  alternarEstado(prod: Producto): void {
    const nuevoEstado = !prod.activo;
    this.productosService.cambiarEstado(prod.id_producto!, nuevoEstado).subscribe({
      next: () => {
        prod.activo = nuevoEstado;
        this.mostrarAlerta(`Prenda '${prod.nombre}' ${nuevoEstado ? 'activada' : 'desactivada'}.`, 'exito');
      },
      error: (err) => {
        this.mostrarAlerta(err.error?.detail || 'Error al cambiar estado.', 'error');
      }
    });
  }

  confirmarEliminar(prod: Producto): void {
    this.productoAeliminar = prod;
    this.mostrarModalEliminar = true;
  }

  cerrarModalEliminar(): void {
    this.mostrarModalEliminar = false;
    this.productoAeliminar = null;
  }

  ejecutarEliminacion(): void {
    if (!this.productoAeliminar) return;
    this.eliminando = true;

    this.productosService.eliminarProducto(this.productoAeliminar.id_producto!).subscribe({
      next: (res) => {
        this.mostrarAlerta(res.message, res.action === 'DESACTIVADO' ? 'info' : 'exito');
        this.eliminando = false;
        this.cerrarModalEliminar();
        this.cargarProductos();
      },
      error: (err) => {
        this.mostrarAlerta(err.error?.detail || 'Error al eliminar el producto.', 'error');
        this.eliminando = false;
      }
    });
  }

  // ==============================================================================
  // GESTIÓN VESTIDOR VIRTUAL RA (M14)
  // ==============================================================================

  subirFoto2D(event: any): void {
    const file = event.target.files[0];
    if (!file) return;

    const tiposPermitidos = ['image/png', 'image/webp', 'image/jpeg', 'image/jpg'];
    if (!tiposPermitidos.includes(file.type)) {
      this.mostrarAlerta('Se recomienda subir una imagen PNG o WEBP con fondo transparente para el vestidor.', 'info');
    }

    if (file.size > 10 * 1024 * 1024) {
      this.mostrarAlerta('La imagen supera el límite permitido de 10 MB.', 'error');
      event.target.value = '';
      return;
    }

    this.subiendoFoto2D = true;
    this.productosService.subirImagenCloudinary(file).subscribe({
      next: (res) => {
        this.productoForm.modelo_2d_url = res.data.imagen_url;
        this.productoForm.tiene_ra = true;
        this.subiendoFoto2D = false;
        this.mostrarAlerta('Foto 2D transparente subida exitosamente a Cloudinary.', 'exito');
        event.target.value = '';
      },
      error: (err) => {
        this.mostrarAlerta(err.error?.detail || 'Error al subir foto 2D a Cloudinary.', 'error');
        this.subiendoFoto2D = false;
        event.target.value = '';
      }
    });
  }

  eliminarFoto2D(): void {
    this.productoForm.modelo_2d_url = '';
  }

  // ==============================================================================
  // HELPERS
  // ==============================================================================

  abrirZoom(url: string): void {
    this.zoomImagenUrl = url;
  }

  cerrarZoom(): void {
    this.zoomImagenUrl = null;
  }

  mostrarAlerta(mensaje: string, tipo: 'exito' | 'error' | 'info'): void {
    this.mensajeAlerta = mensaje;
    this.tipoAlerta = tipo;
    setTimeout(() => {
      if (this.mensajeAlerta === mensaje) {
        this.mensajeAlerta = '';
      }
    }, 4500);
  }

  private getFormVacio() {
    return {
      id_producto: undefined,
      id_empresa: undefined,
      id_categoria: null,
      nombre: '',
      descripcion: '',
      codigo_producto: '',
      precio: null,
      temporada: '',
      coleccion: '',
      marca: '',
      genero: 'Unisex',
      activo: true,
      tallas_seleccionadas: [] as number[],
      colores_seleccionados: [] as number[],
      precios_por_talla: {} as { [id_talla: number]: number },
      imagenes: [] as ImagenProducto[],
      tiene_ra: false,
      tipo_prenda_ra: 'TOP',
      modelo_2d_url: ''
    };
  }
}
