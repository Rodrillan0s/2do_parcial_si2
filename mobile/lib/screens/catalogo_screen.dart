import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../config/app_config.dart';
import '../core/tenant/tenant_context_manager.dart';
import '../services/catalogo_service.dart';
import '../services/carrito_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_empty_state.dart';
import '../widgets/aurora_product_card.dart';
import 'detalle_producto_screen.dart';

class CatalogoScreen extends StatefulWidget {
  const CatalogoScreen({super.key});

  @override
  State<CatalogoScreen> createState() => _CatalogoScreenState();
}

class _CatalogoScreenState extends State<CatalogoScreen> {
  final TextEditingController _searchController = TextEditingController();
  bool _selectorMostrado = false;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_selectorMostrado) {
      WidgetsBinding.instance
          .addPostFrameCallback((_) => _mostrarSelectorInicial());
    }
  }

  void _mostrarSelectorInicial() {
    if (!mounted || _selectorMostrado) return;
    final catalogo = context.read<CatalogoService>();
    if (catalogo.cargando ||
        catalogo.tenants.isEmpty ||
        catalogo.tenantSeleccionado != null) {
      if (catalogo.tenants.isEmpty) {
        Future.delayed(
            const Duration(milliseconds: 300), _mostrarSelectorInicial);
      }
      return;
    }
    _selectorMostrado = true;
    _mostrarSelectorTienda(context, catalogo, inicial: true);
  }

  Future<void> _cambiarTienda(TenantModel tenant) async {
    final catalogo = context.read<CatalogoService>();
    final carrito = context.read<CarritoService>();
    final tenantManager = context.read<TenantContextManager>();

    await tenantManager.seleccionarTenant(tenant);
    await catalogo.seleccionarTenant(tenant);
    // Preservar borradores: cargar bolsa de la nueva tienda sin vaciar la anterior
    await carrito.cargarCarrito(idEmpresa: tenant.idEmpresa);
  }

  void _mostrarSelectorTienda(BuildContext context, CatalogoService catalogo,
      {bool inicial = false}) {
    showDialog(
      context: context,
      barrierDismissible: !inicial,
      builder: (ctx) => AlertDialog(
        title: Text(
          '¿Dónde quieres comprar?',
          style: GoogleFonts.playfairDisplay(
              fontSize: 21, fontWeight: FontWeight.w700),
        ),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView.separated(
            shrinkWrap: true,
            itemCount: catalogo.tenants.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (_, index) {
              final tenant = catalogo.tenants[index];
              return ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const CircleAvatar(
                  backgroundColor: AppTheme.goldLight,
                  child: Icon(Icons.storefront_outlined,
                      color: AppTheme.primaryGold),
                ),
                title: Text(tenant.nombreEmpresa),
                subtitle: Text(tenant.ciudad ?? 'Tienda Aurora Store'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () async {
                  await _cambiarTienda(tenant);
                  if (ctx.mounted) Navigator.pop(ctx);
                },
              );
            },
          ),
        ),
      ),
    );
  }

  void _mostrarDialogoConexion(BuildContext context) {
    final controller = TextEditingController(text: AppConfig.apiBaseUrl);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(
          'Configurar Servidor',
          style: GoogleFonts.playfairDisplay(
              fontSize: 18, fontWeight: FontWeight.w700),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Dirección IP / URL del Backend FastAPI:',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 12, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: controller,
              decoration: const InputDecoration(
                hintText: 'http://127.0.0.1:5000',
                prefixIcon: Icon(Icons.link),
              ),
            ),
            const SizedBox(height: 14),
            Text(
              'Accesos directos:',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 12, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              children: [
                ActionChip(
                  label: const Text('Backend desplegado'),
                  onPressed: () =>
                      controller.text = AppConfig.defaultDeployedUrl,
                ),
                ActionChip(
                  label: const Text('127.0.0.1 (USB adb)'),
                  onPressed: () => controller.text = AppConfig.defaultLocalUrl,
                ),
                ActionChip(
                  label: const Text('192.168.0.9 (Wi-Fi)'),
                  onPressed: () => controller.text = AppConfig.defaultLanUrl,
                ),
                ActionChip(
                  label: const Text('10.0.2.2 (Emulador)'),
                  onPressed: () =>
                      controller.text = AppConfig.defaultEmulatorUrl,
                ),
              ],
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () async {
              final url = controller.text.trim();
              if (url.isNotEmpty) {
                await AppConfig.setBaseUrl(url);
                if (ctx.mounted) Navigator.pop(ctx);
                if (context.mounted) {
                  context.read<CatalogoService>().inicializar();
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('Servidor configurado: $url'),
                      backgroundColor: AppTheme.success,
                    ),
                  );
                }
              }
            },
            child: const Text('Guardar y Reconectar'),
          ),
        ],
      ),
    );
  }

  void _abrirModalFiltros(BuildContext context, CatalogoService catalogo) {
    final filtros = catalogo.filtros;
    if (filtros == null) return;

    int? tempCategoriaId = catalogo.categoriaId;
    int? tempTallaId = catalogo.tallaId;
    int? tempColorId = catalogo.colorId;
    double? tempPrecioMin = catalogo.precioMin;
    double? tempPrecioMax = catalogo.precioMax;
    String? tempOrden = catalogo.orden;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) {
          return Container(
            height: MediaQuery.of(context).size.height * 0.85,
            decoration: const BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            ),
            child: Column(
              children: [
                // Cabecera del BottomSheet
                Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Filtros de catálogo',
                        style: GoogleFonts.playfairDisplay(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      TextButton(
                        onPressed: () {
                          setModalState(() {
                            tempCategoriaId = null;
                            tempTallaId = null;
                            tempColorId = null;
                            tempPrecioMin = null;
                            tempPrecioMax = null;
                            tempOrden = null;
                          });
                        },
                        child: const Text('Limpiar todo'),
                      ),
                    ],
                  ),
                ),
                const Divider(height: 1),

                // Lista de Filtros
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.all(20),
                    children: [
                      // Ordenar por
                      Text(
                        'Ordenar por',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        children: [
                          _buildChoiceChip(
                            'Predeterminado',
                            tempOrden == null,
                            () => setModalState(() => tempOrden = null),
                          ),
                          _buildChoiceChip(
                            'Menor precio',
                            tempOrden == 'precio_asc',
                            () => setModalState(() => tempOrden = 'precio_asc'),
                          ),
                          _buildChoiceChip(
                            'Mayor precio',
                            tempOrden == 'precio_desc',
                            () =>
                                setModalState(() => tempOrden = 'precio_desc'),
                          ),
                          _buildChoiceChip(
                            'Más recientes',
                            tempOrden == 'recientes',
                            () => setModalState(() => tempOrden = 'recientes'),
                          ),
                        ],
                      ),

                      const SizedBox(height: 24),

                      // Tallas
                      if (filtros.tallas.isNotEmpty) ...[
                        Text(
                          'Tallas disponibles',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            _buildChoiceChip(
                              'Todas',
                              tempTallaId == null,
                              () => setModalState(() => tempTallaId = null),
                            ),
                            ...filtros.tallas.map(
                              (t) => _buildChoiceChip(
                                t.nombre,
                                tempTallaId == t.idTalla,
                                () => setModalState(
                                    () => tempTallaId = t.idTalla),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 24),
                      ],

                      // Colores
                      if (filtros.colores.isNotEmpty) ...[
                        Text(
                          'Colores',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 10,
                          runSpacing: 10,
                          children: [
                            _buildChoiceChip(
                              'Todos',
                              tempColorId == null,
                              () => setModalState(() => tempColorId = null),
                            ),
                            ...filtros.colores.map((c) {
                              final hex = c.codigoHex.replaceAll('#', '');
                              final colorInt =
                                  int.tryParse('FF$hex', radix: 16) ??
                                      0xFF000000;
                              final isSelected = tempColorId == c.idColor;

                              return InkWell(
                                onTap: () => setModalState(
                                    () => tempColorId = c.idColor),
                                borderRadius: BorderRadius.circular(20),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 10, vertical: 6),
                                  decoration: BoxDecoration(
                                    color: isSelected
                                        ? AppTheme.goldLight
                                        : AppTheme.surfaceVariant,
                                    borderRadius: BorderRadius.circular(20),
                                    border: Border.all(
                                      color: isSelected
                                          ? AppTheme.primaryGold
                                          : AppTheme.border,
                                    ),
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Container(
                                        width: 14,
                                        height: 14,
                                        decoration: BoxDecoration(
                                          color: Color(colorInt),
                                          shape: BoxShape.circle,
                                          border:
                                              Border.all(color: Colors.black12),
                                        ),
                                      ),
                                      const SizedBox(width: 6),
                                      Text(
                                        c.nombre,
                                        style: GoogleFonts.plusJakartaSans(
                                          fontSize: 12,
                                          fontWeight: isSelected
                                              ? FontWeight.w600
                                              : FontWeight.w400,
                                          color: isSelected
                                              ? AppTheme.primaryGold
                                              : AppTheme.textPrimary,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              );
                            }),
                          ],
                        ),
                      ],
                    ],
                  ),
                ),

                // Botón aplicar
                Padding(
                  padding: const EdgeInsets.all(20),
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primary,
                      foregroundColor: Colors.white,
                      minimumSize: const Size(double.infinity, 48),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                    onPressed: () {
                      catalogo.aplicarFiltros(
                        categoriaId: tempCategoriaId,
                        tallaId: tempTallaId,
                        colorId: tempColorId,
                        precioMin: tempPrecioMin,
                        precioMax: tempPrecioMax,
                        orden: tempOrden,
                      );
                      Navigator.pop(ctx);
                    },
                    child: Text(
                      'Aplicar filtros',
                      style: GoogleFonts.plusJakartaSans(
                          fontWeight: FontWeight.w600),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildChoiceChip(String label, bool isSelected, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primary : AppTheme.surfaceVariant,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? AppTheme.primary : AppTheme.border,
          ),
        ),
        child: Text(
          label,
          style: GoogleFonts.plusJakartaSans(
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
            color: isSelected ? Colors.white : AppTheme.textPrimary,
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final catalogo = context.watch<CatalogoService>();

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Column(
          children: [
            Text(
              'Aurora Store',
              style: GoogleFonts.playfairDisplay(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
            if (catalogo.tenantSeleccionado != null)
              Text(
                catalogo.tenantSeleccionado!.nombreEmpresa.toUpperCase(),
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 1.5,
                  color: AppTheme.primaryGold,
                ),
              ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.wifi_tethering),
            tooltip: 'Configurar conexión',
            onPressed: () => _mostrarDialogoConexion(context),
          ),
          // Selector de tenant / tienda
          if (catalogo.tenants.isNotEmpty)
            PopupMenuButton<TenantModel>(
              icon: const Icon(Icons.storefront_outlined),
              tooltip: 'Cambiar tienda',
              onSelected: _cambiarTienda,
              itemBuilder: (ctx) => catalogo.tenants.map((t) {
                final isSelected =
                    t.idEmpresa == catalogo.tenantSeleccionado?.idEmpresa;
                return PopupMenuItem(
                  value: t,
                  child: Row(
                    children: [
                      Icon(
                        isSelected ? Icons.check_circle : Icons.circle_outlined,
                        size: 16,
                        color: isSelected
                            ? AppTheme.primaryGold
                            : AppTheme.textMuted,
                      ),
                      const SizedBox(width: 8),
                      Text(t.nombreEmpresa),
                    ],
                  ),
                );
              }).toList(),
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => catalogo.cargarProductos(),
        child: CustomScrollView(
          slivers: [
            // Barra de Búsqueda y Botón de Filtros
            if (catalogo.tenantSeleccionado == null)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
                  child: OutlinedButton.icon(
                    onPressed: () => _mostrarSelectorTienda(context, catalogo),
                    icon: const Icon(Icons.storefront_outlined),
                    label: const Text(
                        'Selecciona una tienda para ver su catálogo'),
                  ),
                ),
              ),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
                child: Row(
                  children: [
                    Expanded(
                      child: Container(
                        height: 44,
                        decoration: BoxDecoration(
                          color: AppTheme.surface,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: TextField(
                          controller: _searchController,
                          textInputAction: TextInputAction.search,
                          onSubmitted: (val) {
                            catalogo.aplicarFiltros(busqueda: val);
                          },
                          decoration: InputDecoration(
                            hintText: 'Buscar prendas, marcas...',
                            hintStyle: GoogleFonts.plusJakartaSans(
                                fontSize: 13, color: AppTheme.textMuted),
                            prefixIcon: const Icon(Icons.search,
                                size: 20, color: AppTheme.textMuted),
                            suffixIcon: _searchController.text.isNotEmpty
                                ? IconButton(
                                    icon: const Icon(Icons.clear, size: 18),
                                    onPressed: () {
                                      _searchController.clear();
                                      catalogo.aplicarFiltros(busqueda: '');
                                    },
                                  )
                                : null,
                            border: InputBorder.none,
                            contentPadding:
                                const EdgeInsets.symmetric(vertical: 10),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    InkWell(
                      onTap: () => _abrirModalFiltros(context, catalogo),
                      borderRadius: BorderRadius.circular(12),
                      child: Container(
                        height: 44,
                        width: 44,
                        decoration: BoxDecoration(
                          color: catalogo.categoriaId != null ||
                                  catalogo.tallaId != null ||
                                  catalogo.colorId != null
                              ? AppTheme.primaryGold
                              : AppTheme.surface,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: catalogo.categoriaId != null ||
                                    catalogo.tallaId != null ||
                                    catalogo.colorId != null
                                ? AppTheme.primaryGold
                                : AppTheme.border,
                          ),
                        ),
                        child: Icon(
                          Icons.tune,
                          size: 20,
                          color: catalogo.categoriaId != null ||
                                  catalogo.tallaId != null ||
                                  catalogo.colorId != null
                              ? Colors.white
                              : AppTheme.textPrimary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Chips Horizontales de Categorías
            if (catalogo.filtros?.categorias.isNotEmpty == true)
              SliverToBoxAdapter(
                child: SizedBox(
                  height: 44,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                    children: [
                      _buildCategoryChip(
                        'Todas',
                        catalogo.categoriaId == null,
                        () => catalogo.aplicarFiltros(categoriaId: null),
                      ),
                      ...catalogo.filtros!.categorias.map(
                        (cat) => _buildCategoryChip(
                          cat.nombre,
                          catalogo.categoriaId == cat.idCategoria,
                          () => catalogo.aplicarFiltros(
                              categoriaId: cat.idCategoria),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            // Grid de Productos
            if (catalogo.tenantSeleccionado == null)
              const SliverFillRemaining(
                hasScrollBody: false,
                child: AuroraEmptyState(
                  icon: Icons.storefront_outlined,
                  title: 'Selecciona una tienda',
                  message:
                      'El catálogo, las promociones y la bolsa pertenecen a una sola empresa.',
                ),
              )
            else if (catalogo.cargando)
              const SliverFillRemaining(
                child: Center(child: CircularProgressIndicator()),
              )
            else if (catalogo.error != null && catalogo.productos.isEmpty)
              SliverFillRemaining(
                child: AuroraEmptyState(
                  icon: Icons.wifi_off_outlined,
                  title: 'Error de conexión',
                  message:
                      '${catalogo.error}\n\nConexión actual: ${AppConfig.apiBaseUrl}\nPuedes cambiar la dirección IP o reconectar pulsando aquí.',
                  buttonText: 'Configurar servidor',
                  onButtonPressed: () => _mostrarDialogoConexion(context),
                ),
              )
            else if (catalogo.productos.isEmpty)
              SliverFillRemaining(
                child: AuroraEmptyState(
                  icon: Icons.search_off_outlined,
                  title: 'No encontramos resultados',
                  message:
                      'Prueba ajustando los términos de búsqueda o limpiando los filtros.',
                  buttonText: 'Ver todas las prendas',
                  onButtonPressed: () {
                    _searchController.clear();
                    catalogo.limpiarFiltros();
                  },
                ),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.all(16),
                sliver: SliverGrid(
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    mainAxisSpacing: 16,
                    crossAxisSpacing: 14,
                    childAspectRatio: 0.58,
                  ),
                  delegate: SliverChildBuilderDelegate(
                    (context, index) {
                      final prenda = catalogo.productos[index];
                      return AuroraProductCard(
                        prenda: prenda,
                        onTap: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => DetalleProductoScreen(
                                  idProducto: prenda.idProducto),
                            ),
                          );
                        },
                      );
                    },
                    childCount: catalogo.productos.length,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildCategoryChip(String title, bool isSelected, VoidCallback onTap) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ChoiceChip(
        label: Text(title),
        selected: isSelected,
        onSelected: (_) => onTap(),
        selectedColor: AppTheme.primary,
        backgroundColor: AppTheme.surface,
        labelStyle: GoogleFonts.plusJakartaSans(
          fontSize: 12,
          fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
          color: isSelected ? Colors.white : AppTheme.textPrimary,
        ),
        side: BorderSide(
          color: isSelected ? AppTheme.primary : AppTheme.border,
        ),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      ),
    );
  }
}
