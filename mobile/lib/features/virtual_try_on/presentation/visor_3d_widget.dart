import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';
import '../../../theme/app_theme.dart';
import '../models/garment_model.dart';

class Visor3dWidget extends StatefulWidget {
  final GarmentModel garment;
  final VoidCallback? onAddToCart;
  final VoidCallback? onReserve;

  const Visor3dWidget({
    super.key,
    required this.garment,
    this.onAddToCart,
    this.onReserve,
  });

  @override
  State<Visor3dWidget> createState() => _Visor3dWidgetState();
}

class _Visor3dWidgetState extends State<Visor3dWidget> {
  bool _autoRotate = true;
  final NumberFormat _currencyFormat = NumberFormat.currency(
    locale: 'es_BO',
    symbol: 'Bs. ',
    decimalDigits: 2,
  );

  @override
  Widget build(BuildContext context) {
    final modelUrl = widget.garment.modelo3dUrl ??
        GarmentModel.default3dModelForType(widget.garment.tipo);

    return Stack(
      children: [
        // 1. Fondo de estudio de moda con degradado oscuro Obsidian
        Positioned.fill(
          child: Container(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(0, -0.2),
                radius: 1.2,
                colors: [
                  Color(0xFF1E2230),
                  Color(0xFF0F1117),
                  Color(0xFF08090C),
                ],
              ),
            ),
          ),
        ),

        // 2. Componente 3D ModelViewer con ARCore (Google SceneViewer nativo)
        Positioned.fill(
          child: Padding(
            padding: const EdgeInsets.only(bottom: 120),
            child: ModelViewer(
              key: ValueKey(modelUrl),
              src: modelUrl,
              alt: widget.garment.nombre,
              ar: true,
              arModes: const ['scene-viewer', 'webxr', 'quick-look'],
              autoRotate: _autoRotate,
              autoRotateDelay: 1000,
              rotationPerSecond: '25deg',
              cameraControls: true,
              shadowIntensity: 1.2,
              shadowSoftness: 0.8,
              exposure: 1.05,
              backgroundColor: Colors.transparent,
              loading: Loading.eager,
            ),
          ),
        ),

        // 3. Controles superiores flotantes (Badge 3D + Toggle Auto-rotar)
        Positioned(
          top: 16,
          left: 16,
          right: 16,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: Colors.black54,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: AppTheme.primaryGold.withValues(alpha: 0.5),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.view_in_ar_rounded,
                        color: AppTheme.primaryGold, size: 15),
                    const SizedBox(width: 6),
                    Text(
                      '3D VOLUMÉTRICO • ARCORE',
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.primaryGold,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
              ),

              // Botón de alternar auto-rotación
              InkWell(
                onTap: () {
                  setState(() {
                    _autoRotate = !_autoRotate;
                  });
                },
                borderRadius: BorderRadius.circular(20),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: _autoRotate
                        ? AppTheme.primaryGold.withValues(alpha: 0.25)
                        : Colors.black54,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: _autoRotate
                          ? AppTheme.primaryGold
                          : Colors.white24,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.rotate_right_rounded,
                        color: _autoRotate
                            ? AppTheme.primaryGold
                            : Colors.white70,
                        size: 16,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        _autoRotate ? 'Giro 360° Activo' : 'Giro Pausado',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: _autoRotate
                              ? AppTheme.primaryGold
                              : Colors.white70,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),

        // 4. Panel de información de la prenda e instrucciones de interacción
        Positioned(
          bottom: 16,
          left: 16,
          right: 16,
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xEB131722),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: Colors.white.withValues(alpha: 0.12),
              ),
              boxShadow: const [
                BoxShadow(
                  color: Colors.black54,
                  blurRadius: 16,
                  offset: Offset(0, 6),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            widget.garment.nombre,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            _currencyFormat.format(widget.garment.precio),
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 14,
                              fontWeight: FontWeight.w800,
                              color: AppTheme.primaryGold,
                            ),
                          ),
                        ],
                      ),
                    ),

                    // Badge de interacción táctil
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.08),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.touch_app_outlined,
                              size: 13, color: Colors.white70),
                          const SizedBox(width: 4),
                          Text(
                            'Gira • Pellizca zoom',
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 10,
                              color: Colors.white70,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // Hint de proyección en el espacio
                Row(
                  children: [
                    const Icon(Icons.info_outline,
                        size: 13, color: Colors.white54),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        'Pulsa el botón flotante AR en la esquina del modelo para proyectarlo en tu habitación a escala real.',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 11,
                          color: Colors.white60,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
