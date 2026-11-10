import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import '../services/catalogo_service.dart';
import '../theme/app_theme.dart';

class AuroraProductCard extends StatelessWidget {
  final PrendaModel prenda;
  final VoidCallback onTap;

  const AuroraProductCard({
    super.key,
    required this.prenda,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final currencyFormatter = NumberFormat.currency(
      locale: 'es_BO',
      symbol: 'Bs. ',
      decimalDigits: 2,
    );
    final promotionPrice = prenda.promocion?['precio_promocional'];
    final hasPromotion = promotionPrice != null;
    final promotionValue =
        hasPromotion ? double.tryParse(promotionPrice.toString()) : null;
    final stockLabel = switch (prenda.stockDisponibleCatalogo) {
      <= 0 => 'Agotado',
      <= 3 => '⚠ Últimas unidades',
      _ => '✓ Disponible',
    };
    final stockColor = prenda.stockDisponibleCatalogo <= 0
        ? AppTheme.error
        : prenda.stockDisponibleCatalogo <= 3
            ? AppTheme.primaryGold
            : AppTheme.success;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.border, width: 1),
          boxShadow: const [
            BoxShadow(
              color: Color(0x0A000000),
              blurRadius: 12,
              offset: Offset(0, 4),
            ),
          ],
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Contenedor de la Imagen
            Expanded(
              child: Stack(
                children: [
                  Positioned.fill(
                    child: Container(
                      color: AppTheme.surfaceVariant,
                      child: prenda.imagenPrincipal != null &&
                              prenda.imagenPrincipal!.isNotEmpty
                          ? Image.network(
                              prenda.imagenPrincipal!,
                              fit: BoxFit.cover,
                              errorBuilder: (context, error, stackTrace) {
                                return const Center(
                                  child: Icon(
                                    Icons.checkroom_outlined,
                                    size: 40,
                                    color: AppTheme.textMuted,
                                  ),
                                );
                              },
                              loadingBuilder:
                                  (context, child, loadingProgress) {
                                if (loadingProgress == null) return child;
                                return Center(
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    value: loadingProgress.expectedTotalBytes !=
                                            null
                                        ? loadingProgress
                                                .cumulativeBytesLoaded /
                                            loadingProgress.expectedTotalBytes!
                                        : null,
                                  ),
                                );
                              },
                            )
                          : const Center(
                              child: Icon(
                                Icons.checkroom_outlined,
                                size: 40,
                                color: AppTheme.textMuted,
                              ),
                            ),
                    ),
                  ),
                  // Badge de Categoría
                  if (prenda.categoriaNombre.isNotEmpty)
                    Positioned(
                      top: 8,
                      left: 8,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.9),
                          borderRadius: BorderRadius.circular(20),
                          boxShadow: const [
                            BoxShadow(
                              color: Color(0x10000000),
                              blurRadius: 4,
                            ),
                          ],
                        ),
                        child: Text(
                          prenda.categoriaNombre,
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),

            // Información de la prenda
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    prenda.marca.isNotEmpty
                        ? prenda.marca
                        : 'Aurora Collection',
                    style: GoogleFonts.plusJakartaSans(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.primaryGold,
                      letterSpacing: 0.5,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    prenda.nombre,
                    style: GoogleFonts.playfairDisplay(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                      height: 1.2,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  if (hasPromotion && promotionValue != null) ...[
                    Text(
                      currencyFormatter.format(prenda.precio),
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 11,
                        decoration: TextDecoration.lineThrough,
                        color: AppTheme.textMuted,
                      ),
                    ),
                    Text(
                      currencyFormatter.format(promotionValue),
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.error,
                      ),
                    ),
                  ] else
                    Text(
                      currencyFormatter.format(prenda.precio),
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                  const SizedBox(height: 4),
                  Text(
                    stockLabel,
                    style: GoogleFonts.plusJakartaSans(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: stockColor,
                    ),
                  ),
                  const SizedBox(height: 4),
                  // Puntos de colores disponibles
                  if (prenda.coloresDisponibles.isNotEmpty)
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          ...prenda.coloresDisponibles.take(4).map((c) {
                            final hex = (c['codigo_hex'] ?? '#000000')
                                .toString()
                                .replaceAll('#', '');
                            final colorVal =
                                int.tryParse('FF$hex', radix: 16) ?? 0xFF000000;
                            return Container(
                              margin: const EdgeInsets.only(right: 4),
                              width: 10,
                              height: 10,
                              decoration: BoxDecoration(
                                color: Color(colorVal),
                                shape: BoxShape.circle,
                                border:
                                    Border.all(color: Colors.white, width: 1.5),
                                boxShadow: const [
                                  BoxShadow(
                                    color: Color(0x15000000),
                                    blurRadius: 2,
                                  ),
                                ],
                              ),
                            );
                          }),
                          if (prenda.coloresDisponibles.length > 4)
                            Text(
                              '+${prenda.coloresDisponibles.length - 4}',
                              style: GoogleFonts.plusJakartaSans(
                                fontSize: 9,
                                color: AppTheme.textMuted,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
