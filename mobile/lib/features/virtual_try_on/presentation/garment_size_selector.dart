import 'dart:ui';
import 'package:flutter/material.dart';

class GarmentSizeSelector extends StatelessWidget {
  final String selectedSize;
  final ValueChanged<String> onSizeSelected;
  final List<String> sizes;

  static const Map<String, double> sizeScales = {
    'XXS': 0.85,
    'XS': 0.90,
    'S': 0.95,
    'M': 1.00,
    'L': 1.08,
    'XL': 1.16,
    'XXL': 1.24,
    '3XL': 1.30,
  };

  static const Map<String, String> sizeLabels = {
    'XXS': 'Talla XXS (-15%)',
    'XS': 'Ajuste Slim (-10%)',
    'S': 'Ajuste Fit (-5%)',
    'M': 'Ajuste Estándar (1.0x)',
    'L': 'Corte Holgado (+8%)',
    'XL': 'Corte Oversize (+16%)',
    'XXL': 'Corte Extra Amplio (+24%)',
    '3XL': 'Corte Máximo (+30%)',
  };

  const GarmentSizeSelector({
    super.key,
    required this.selectedSize,
    required this.onSizeSelected,
    this.sizes = const ['S', 'M', 'L'],
  });

  @override
  Widget build(BuildContext context) {
    final activeLabel = sizeLabels[selectedSize] ?? 'Talla $selectedSize';
    final availableSizes = sizes.isNotEmpty ? sizes : const ['S', 'M', 'L'];

    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          constraints: const BoxConstraints(maxWidth: 360),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: const Color(0xFF09090B).withValues(alpha: 0.80),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.15),
              width: 1,
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Fila horizontal scrollable de botones de Tallas (evita overflow)
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                physics: const BouncingScrollPhysics(),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(right: 6),
                      child: Text(
                        'Talla:',
                        style: TextStyle(
                          color: Colors.white70,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          fontFamily: 'Inter',
                        ),
                      ),
                    ),
                    for (final size in availableSizes) ...[
                      GestureDetector(
                        onTap: () => onSizeSelected(size),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 180),
                          curve: Curves.easeInOut,
                          margin: const EdgeInsets.symmetric(horizontal: 3),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 5,
                          ),
                          decoration: BoxDecoration(
                            color: selectedSize == size
                                ? const Color(0xFFF59E0B)
                                : Colors.white.withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(
                              color: selectedSize == size
                                  ? const Color(0xFFFBBF24)
                                  : Colors.white.withValues(alpha: 0.12),
                              width: 1,
                            ),
                            boxShadow: selectedSize == size
                                ? [
                                    BoxShadow(
                                      color: const Color(0xFFF59E0B)
                                          .withValues(alpha: 0.35),
                                      blurRadius: 8,
                                      offset: const Offset(0, 2),
                                    ),
                                  ]
                                : null,
                          ),
                          child: Text(
                            size,
                            style: TextStyle(
                              color: selectedSize == size
                                  ? const Color(0xFF09090B)
                                  : Colors.white,
                              fontSize: 11,
                              fontWeight: selectedSize == size
                                  ? FontWeight.w800
                                  : FontWeight.w500,
                              fontFamily: 'Inter',
                            ),
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 5),
              // Micro-etiqueta con descripción del corte (protegida contra overflow)
              Row(
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 5,
                    height: 5,
                    decoration: const BoxDecoration(
                      color: Color(0xFFF59E0B),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 5),
                  Flexible(
                    child: Text(
                      activeLabel,
                      overflow: TextOverflow.ellipsis,
                      maxLines: 1,
                      style: const TextStyle(
                        color: Color(0xFFE4E4E7),
                        fontSize: 10,
                        fontWeight: FontWeight.w500,
                        fontFamily: 'Inter',
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
