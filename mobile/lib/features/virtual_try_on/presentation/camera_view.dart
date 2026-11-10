import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

/// Vista de la cámara ajustada a pantalla completa
class CameraView extends StatelessWidget {
  final CameraController? controller;

  const CameraView({
    super.key,
    required this.controller,
  });

  @override
  Widget build(BuildContext context) {
    if (controller == null || !controller!.value.isInitialized) {
      return Container(
        color: const Color(0xFF09090B),
        child: const Center(
          child: CircularProgressIndicator(
            valueColor: AlwaysStoppedAnimation<Color>(Colors.white70),
          ),
        ),
      );
    }

    final size = MediaQuery.of(context).size;
    final cameraAspectRatio = controller!.value.aspectRatio;
    final isFrontCamera = controller!.description.lensDirection == CameraLensDirection.front;

    // Calcular factor de escala para llenar pantalla sin distorsión
    double scale = size.aspectRatio * cameraAspectRatio;
    if (scale < 1) scale = 1 / scale;

    return ClipRect(
      child: Container(
        width: size.width,
        height: size.height,
        color: Colors.black,
        child: Transform.scale(
          scaleX: isFrontCamera ? -scale : scale,
          scaleY: scale,
          alignment: Alignment.center,
          child: Center(
            child: CameraPreview(controller!),
          ),
        ),
      ),
    );
  }
}
