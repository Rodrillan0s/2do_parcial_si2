import 'dart:ui';
import 'package:flutter/material.dart';
import '../models/garment_model.dart';

/// Selector horizontal de prendas para el vestidor virtual con filtros por categoría
class GarmentSelector extends StatefulWidget {
  final List<GarmentModel> garments;
  final GarmentModel? selectedGarment;
  final ValueChanged<GarmentModel> onGarmentSelected;

  const GarmentSelector({
    super.key,
    required this.garments,
    required this.selectedGarment,
    required this.onGarmentSelected,
  });

  @override
  State<GarmentSelector> createState() => _GarmentSelectorState();
}

class _GarmentSelectorState extends State<GarmentSelector> {
  GarmentType? _selectedCategory; // null = Todas

  @override
  Widget build(BuildContext context) {
    final filteredGarments = _selectedCategory == null
        ? widget.garments
        : widget.garments.where((g) => g.tipo == _selectedCategory).toList();

    return ClipRRect(
      borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            color: const Color(0xCC09090B), // Obsidian semitransparente
            border: Border(
              top: BorderSide(
                color: Colors.white.withValues(alpha: 0.12),
                width: 1,
              ),
            ),
          ),
          child: SafeArea(
            top: false,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Chips de filtro por tipo de prenda
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        _buildFilterChip(
                          label: 'Todas',
                          isSelected: _selectedCategory == null,
                          onTap: () => setState(() => _selectedCategory = null),
                        ),
                        const SizedBox(width: 8),
                        _buildFilterChip(
                          label: 'Tops',
                          isSelected: _selectedCategory == GarmentType.top,
                          onTap: () => setState(() => _selectedCategory = GarmentType.top),
                        ),
                        const SizedBox(width: 8),
                        _buildFilterChip(
                          label: 'Pantalones',
                          isSelected: _selectedCategory == GarmentType.pant,
                          onTap: () => setState(() => _selectedCategory = GarmentType.pant),
                        ),
                        const SizedBox(width: 8),
                        _buildFilterChip(
                          label: 'Vestidos',
                          isSelected: _selectedCategory == GarmentType.dress,
                          onTap: () => setState(() => _selectedCategory = GarmentType.dress),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),

                // Carrusel horizontal de prendas
                SizedBox(
                  height: 104,
                  child: filteredGarments.isEmpty
                      ? const Center(
                          child: Text(
                            'No hay prendas en esta categoría',
                            style: TextStyle(
                              color: Colors.white54,
                              fontSize: 13,
                              fontFamily: 'Inter',
                            ),
                          ),
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          scrollDirection: Axis.horizontal,
                          itemCount: filteredGarments.length,
                          separatorBuilder: (_, __) => const SizedBox(width: 12),
                          itemBuilder: (context, index) {
                            final garment = filteredGarments[index];
                            final isSelected =
                                widget.selectedGarment?.idProducto == garment.idProducto;

                            return _buildGarmentCard(garment, isSelected);
                          },
                        ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildFilterChip({
    required String label,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? Colors.white : Colors.white.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? Colors.white : Colors.white.withValues(alpha: 0.15),
            width: 1,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? const Color(0xFF09090B) : Colors.white70,
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
            fontFamily: 'Inter',
            letterSpacing: 0.2,
          ),
        ),
      ),
    );
  }

  Widget _buildGarmentCard(GarmentModel garment, bool isSelected) {
    return GestureDetector(
      onTap: () => widget.onGarmentSelected(garment),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        width: 80,
        decoration: BoxDecoration(
          color: isSelected
              ? Colors.white.withValues(alpha: 0.14)
              : Colors.white.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? const Color(0xFFB45309) : Colors.white.withValues(alpha: 0.1),
            width: isSelected ? 2 : 1,
          ),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: const Color(0xFFB45309).withValues(alpha: 0.3),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ]
              : null,
        ),
        padding: const EdgeInsets.all(6),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Thumbnail de la prenda
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: Image.network(
                  garment.imagenPreview ?? garment.modelo2dUrl,
                  fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) => const Icon(
                    Icons.checkroom,
                    color: Colors.white54,
                    size: 28,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 4),
            // Nombre corto
            Text(
              garment.nombre,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: isSelected ? Colors.white : Colors.white70,
                fontSize: 10,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                fontFamily: 'Inter',
              ),
            ),
            // Precio
            Text(
              'Bs. ${garment.precio.toStringAsFixed(0)}',
              maxLines: 1,
              style: const TextStyle(
                color: Color(0xFFD97706),
                fontSize: 9,
                fontWeight: FontWeight.w600,
                fontFamily: 'Inter',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
