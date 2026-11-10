import 'package:flutter/material.dart';
import '../domain/garment_transformer.dart';
import '../models/garment_model.dart';

/// Widget de superposición de prenda sobre la vista de cámara
/// Soporta tanto deformación por perspectiva proyectiva (Warping 4 puntos)
/// como transformación rígida estándar (rotación + escala) de respaldo.
class GarmentOverlay extends StatelessWidget {
  final GarmentModel? garment;
  final GarmentTransform transform;

  const GarmentOverlay({
    super.key,
    required this.garment,
    required this.transform,
  });

  @override
  Widget build(BuildContext context) {
    if (garment == null || !transform.visible || garment!.modelo2dUrl.isEmpty) {
      return const SizedBox.shrink();
    }

    // =========================================================================
    // MODO 1: WARPING PROYECTIVO DE 4 PUNTOS (FASE 5)
    // Deforma la prenda adaptando las 4 esquinas a los hombros y caderas
    // =========================================================================
    if (transform.usePerspective && transform.perspectiveTransform != null) {
      return Positioned(
        left: 0,
        top: 0,
        child: Transform(
          transform: transform.perspectiveTransform!,
          alignment: Alignment.topLeft,
          child: SizedBox(
            width: transform.sourceWidth,
            height: transform.sourceHeight,
            child: Image.network(
              garment!.modelo2dUrl,
              fit: BoxFit.fill,
              errorBuilder: (context, error, stackTrace) {
                return const SizedBox.shrink();
              },
              loadingBuilder: (context, child, loadingProgress) {
                if (loadingProgress == null) return child;
                return const Center(
                  child: SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation<Color>(Colors.white70),
                    ),
                  ),
                );
              },
            ),
          ),
        ),
      );
    }

    // =========================================================================
    // MODO 2: TRANSFORMACIÓN RÍGIDA ESTÁNDAR (RESPALDO ANATÓMICO)
    // =========================================================================
    final width = transform.width.clamp(40.0, 1000.0);
    final height = transform.height.clamp(40.0, 1200.0);

    return Positioned(
      left: transform.x - (width / 2),
      top: transform.y - (height / 2),
      width: width,
      height: height,
      child: Transform.rotate(
        angle: transform.rotation,
        alignment: Alignment.center,
        child: Image.network(
          garment!.modelo2dUrl,
          fit: BoxFit.contain,
          errorBuilder: (context, error, stackTrace) {
            return const SizedBox.shrink();
          },
          loadingBuilder: (context, child, loadingProgress) {
            if (loadingProgress == null) return child;
            return const Center(
              child: SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white70),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
