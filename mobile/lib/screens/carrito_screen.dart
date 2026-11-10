import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../services/auth_provider.dart';
import '../services/carrito_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_button.dart';
import '../widgets/aurora_empty_state.dart';
import 'auth_screens.dart';
import 'checkout_screen.dart';

class CarritoScreen extends StatefulWidget {
  final VoidCallback? onIrAlCatalogo;

  const CarritoScreen({super.key, this.onIrAlCatalogo});

  @override
  State<CarritoScreen> createState() => _CarritoScreenState();
}

class _CarritoScreenState extends State<CarritoScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<CarritoService>().cargarCarrito();
    });
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final carritoService = context.watch<CarritoService>();
    final carrito = carritoService.carrito;

    final currencyFormatter = NumberFormat.currency(
      locale: 'es_BO',
      symbol: 'Bs. ',
      decimalDigits: 2,
    );

    if (!authProvider.estaAutenticado) {
      return Scaffold(
        backgroundColor: AppTheme.background,
        appBar: AppBar(title: const Text('Bolsa de Compras')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.shopping_bag_outlined, size: 64, color: AppTheme.primaryGold),
                const SizedBox(height: 16),
                Text(
                  'Inicia sesión para ver tu bolsa',
                  style: GoogleFonts.playfairDisplay(fontSize: 20, fontWeight: FontWeight.w700),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Guarda tus prendas favoritas y sincroniza tus compras en todos tus dispositivos.',
                  style: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textSecondary),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                AuroraButton(
                  text: 'Iniciar sesión',
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const AuthScreen()),
                    );
                  },
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Text(
          'Bolsa de Compras',
          style: GoogleFonts.playfairDisplay(fontSize: 18, fontWeight: FontWeight.w700),
        ),
        actions: [
          if (carrito != null && carrito.items.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.delete_sweep_outlined),
              tooltip: 'Vaciar bolsa',
              onPressed: () async {
                final confirm = await showDialog<bool>(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    title: const Text('Vaciar bolsa'),
                    content: const Text('¿Deseas eliminar todas las prendas de tu bolsa?'),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
                      ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Vaciar')),
                    ],
                  ),
                );
                if (confirm == true) {
                  await carritoService.vaciarCarrito();
                }
              },
            ),
        ],
      ),
      body: carritoService.cargando && carrito == null
          ? const Center(child: CircularProgressIndicator())
          : carrito == null || carrito.items.isEmpty
              ? AuroraEmptyState(
                  icon: Icons.shopping_bag_outlined,
                  title: 'Tu bolsa está vacía',
                  message: 'Explora nuestra colección de alta costura y agrega tus prendas favoritas.',
                  buttonText: 'Explorar catálogo',
                  onButtonPressed: widget.onIrAlCatalogo,
                )
              : Column(
                  children: [
                    // Identificador de Tienda para aislamiento multitenant
                    if (carrito.nombreEmpresa.isNotEmpty)
                      Container(
                        width: double.infinity,
                        margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        decoration: BoxDecoration(
                          color: AppTheme.goldLight,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: AppTheme.primaryGold.withValues(alpha: 0.3)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.storefront, size: 16, color: AppTheme.primaryGold),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                'Bolsa activa en: ${carrito.nombreEmpresa}',
                                style: GoogleFonts.plusJakartaSans(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.primaryGold,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),

                    // Alerta de Stock si alguna prenda tiene advertencia
                    ...carrito.items.where((i) => i.advertenciaStock != null).map(
                          (i) => Container(
                            margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: AppTheme.errorLight,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.warning_amber_rounded, color: AppTheme.error, size: 18),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    i.advertenciaStock!,
                                    style: GoogleFonts.plusJakartaSans(
                                      fontSize: 11,
                                      color: AppTheme.error,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),

                    // Lista de Prendas en el Carrito
                    Expanded(
                      child: ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: carrito.items.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final item = carrito.items[index];
                          return Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AppTheme.surface,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: AppTheme.border),
                            ),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                // Thumbnail de la prenda
                                Container(
                                  width: 70,
                                  height: 85,
                                  decoration: BoxDecoration(
                                    color: AppTheme.surfaceVariant,
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  clipBehavior: Clip.antiAlias,
                                  child: item.imagenUrl != null && item.imagenUrl!.isNotEmpty
                                      ? Image.network(
                                          item.imagenUrl!,
                                          fit: BoxFit.cover,
                                          errorBuilder: (_, __, ___) => const Center(
                                            child: Icon(Icons.checkroom, color: AppTheme.textMuted),
                                          ),
                                        )
                                      : const Center(
                                          child: Icon(Icons.checkroom, color: AppTheme.textMuted),
                                        ),
                                ),
                                const SizedBox(width: 14),

                                // Información y Controles
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Expanded(
                                            child: Text(
                                              item.productoNombre,
                                              style: GoogleFonts.playfairDisplay(
                                                fontSize: 15,
                                                fontWeight: FontWeight.w700,
                                                color: AppTheme.textPrimary,
                                              ),
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ),
                                          IconButton(
                                            padding: EdgeInsets.zero,
                                            constraints: const BoxConstraints(),
                                            icon: const Icon(Icons.close, size: 18, color: AppTheme.textMuted),
                                            onPressed: () {
                                              carritoService.eliminarItem(
                                                idDetalleCarrito: item.idDetalleCarrito,
                                                idEmpresa: carrito.idEmpresa,
                                              );
                                            },
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        'Talla: ${item.tallaNombre}  •  Color: ${item.colorNombre}',
                                        style: GoogleFonts.plusJakartaSans(
                                          fontSize: 12,
                                          color: AppTheme.textSecondary,
                                        ),
                                      ),
                                      const SizedBox(height: 8),
                                      Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Text(
                                            currencyFormatter.format(item.precioUnitario),
                                            style: GoogleFonts.plusJakartaSans(
                                              fontSize: 14,
                                              fontWeight: FontWeight.w700,
                                              color: AppTheme.textPrimary,
                                            ),
                                          ),
                                          // Controles de Cantidad (+ / -)
                                          Container(
                                            decoration: BoxDecoration(
                                              color: AppTheme.surfaceVariant,
                                              borderRadius: BorderRadius.circular(8),
                                              border: Border.all(color: AppTheme.border),
                                            ),
                                            child: Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                InkWell(
                                                  onTap: item.cantidad > 1
                                                      ? () {
                                                          carritoService.actualizarCantidad(
                                                            idDetalleCarrito: item.idDetalleCarrito,
                                                            nuevaCantidad: item.cantidad - 1,
                                                            idEmpresa: carrito.idEmpresa,
                                                          );
                                                        }
                                                      : null,
                                                  child: const Padding(
                                                    padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                                    child: Icon(Icons.remove, size: 14),
                                                  ),
                                                ),
                                                Padding(
                                                  padding: const EdgeInsets.symmetric(horizontal: 6),
                                                  child: Text(
                                                    '${item.cantidad}',
                                                    style: GoogleFonts.plusJakartaSans(
                                                      fontSize: 13,
                                                      fontWeight: FontWeight.w700,
                                                    ),
                                                  ),
                                                ),
                                                InkWell(
                                                  onTap: () {
                                                    carritoService.actualizarCantidad(
                                                      idDetalleCarrito: item.idDetalleCarrito,
                                                      nuevaCantidad: item.cantidad + 1,
                                                      idEmpresa: carrito.idEmpresa,
                                                    );
                                                  },
                                                  child: const Padding(
                                                    padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                                    child: Icon(Icons.add, size: 14),
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                    ),

                    // Resumen Inferior y Botón Checkout
                    Container(
                      padding: const EdgeInsets.all(20),
                      decoration: const BoxDecoration(
                        color: AppTheme.surface,
                        border: Border(top: BorderSide(color: AppTheme.border)),
                        boxShadow: [
                          BoxShadow(
                            color: Color(0x08000000),
                            blurRadius: 8,
                            offset: Offset(0, -2),
                          ),
                        ],
                      ),
                      child: SafeArea(
                        top: false,
                        child: Column(
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  'Subtotal',
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 13,
                                    color: AppTheme.textSecondary,
                                  ),
                                ),
                                Text(
                                  currencyFormatter.format(carrito.subtotal),
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  'Total estimado',
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w700,
                                    color: AppTheme.textPrimary,
                                  ),
                                ),
                                Text(
                                  currencyFormatter.format(carrito.total),
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 18,
                                    fontWeight: FontWeight.w800,
                                    color: AppTheme.primaryGold,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),
                            AuroraButton(
                              text: 'Continuar con la compra',
                              onPressed: () {
                                Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => CheckoutScreen(carrito: carrito),
                                  ),
                                );
                              },
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }
}
