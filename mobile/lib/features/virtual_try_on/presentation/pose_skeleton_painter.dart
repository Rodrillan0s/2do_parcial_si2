import 'package:flutter/material.dart';
import '../domain/garment_transformer.dart';
import '../models/body_pose_model.dart';

/// Pintor personalizado para dibujar en tiempo real el esqueleto anatómico,
/// los puntos clave de seguimiento corporal (brazos, hombros, torso y piernas)
/// y el cuadrilátero de deformación por perspectiva (Warping 4 puntos).
class PoseSkeletonPainter extends CustomPainter {
  final BodyPose? pose;
  final Size screenSize;
  final double? cameraAspectRatio;
  final List<Offset>? quadPoints;
  final bool isVisible;

  PoseSkeletonPainter({
    required this.pose,
    required this.screenSize,
    this.cameraAspectRatio,
    this.quadPoints,
    this.isVisible = true,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (!isVisible || pose == null || !pose!.isBodyDetected) return;

    final p = pose!;

    Offset? toScreen(BodyPoint? pt) {
      if (pt == null || pt.confidence < 0.35) return null;
      return GarmentTransformer.mapPointToScreen(
        point: pt,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
    }

    // Puntos anatómicos mapeados a coordenadas de pantalla
    final pLeftShoulder = toScreen(p.leftShoulder);
    final pRightShoulder = toScreen(p.rightShoulder);
    final pLeftElbow = toScreen(p.leftElbow);
    final pRightElbow = toScreen(p.rightElbow);
    final pLeftWrist = toScreen(p.leftWrist);
    final pRightWrist = toScreen(p.rightWrist);
    final pLeftHip = toScreen(p.leftHip);
    final pRightHip = toScreen(p.rightHip);
    final pLeftKnee = toScreen(p.leftKnee);
    final pRightKnee = toScreen(p.rightKnee);
    final pLeftAnkle = toScreen(p.leftAnkle);
    final pRightAnkle = toScreen(p.rightAnkle);

    // 0. Cuadrilátero de Warping de Perspectiva (Fase 5)
    if (quadPoints != null && quadPoints!.length == 4) {
      final quadPath = Path()
        ..moveTo(quadPoints![0].dx, quadPoints![0].dy)
        ..lineTo(quadPoints![1].dx, quadPoints![1].dy)
        ..lineTo(quadPoints![2].dx, quadPoints![2].dy)
        ..lineTo(quadPoints![3].dx, quadPoints![3].dy)
        ..close();

      final quadFill = Paint()
        ..color = const Color(0xFFF59E0B).withValues(alpha: 0.12)
        ..style = PaintingStyle.fill;
      canvas.drawPath(quadPath, quadFill);

      final quadStroke = Paint()
        ..color = const Color(0xFFF59E0B).withValues(alpha: 0.50)
        ..strokeWidth = 1.5
        ..style = PaintingStyle.stroke;
      canvas.drawPath(quadPath, quadStroke);
    }

    // Pincel para líneas de extremidades superiores (Brazos - Cian Neón)
    final armPaint = Paint()
      ..color = const Color(0xFF06B6D4).withValues(alpha: 0.85)
      ..strokeWidth = 3.5
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    // Pincel para líneas de torso y hombros (Dorado Aurora)
    final torsoPaint = Paint()
      ..color = const Color(0xFFF59E0B).withValues(alpha: 0.85)
      ..strokeWidth = 3.0
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    // Pincel para líneas de piernas (Esmeralda)
    final legPaint = Paint()
      ..color = const Color(0xFF10B981).withValues(alpha: 0.70)
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    void drawLine(Offset? a, Offset? b, Paint paint) {
      if (a != null && b != null) {
        canvas.drawLine(a, b, paint);
      }
    }

    // 1. Conexiones de los Brazos (Seguimiento de extremidades)
    // Brazo izquierdo: Hombro -> Codo -> Muñeca
    drawLine(pLeftShoulder, pLeftElbow, armPaint);
    drawLine(pLeftElbow, pLeftWrist, armPaint);

    // Brazo derecho: Hombro -> Codo -> Muñeca
    drawLine(pRightShoulder, pRightElbow, armPaint);
    drawLine(pRightElbow, pRightWrist, armPaint);

    // 2. Conexiones del Torso
    drawLine(pLeftShoulder, pRightShoulder, torsoPaint);
    drawLine(pLeftShoulder, pLeftHip, torsoPaint);
    drawLine(pRightShoulder, pRightHip, torsoPaint);
    drawLine(pLeftHip, pRightHip, torsoPaint);

    // 3. Conexiones de las Piernas
    drawLine(pLeftHip, pLeftKnee, legPaint);
    drawLine(pLeftKnee, pLeftAnkle, legPaint);
    drawLine(pRightHip, pRightKnee, legPaint);
    drawLine(pRightKnee, pRightAnkle, legPaint);

    // 4. Dibujar articulaciones con efecto de halo radiante
    void drawJoint(Offset? pt, Color color, {double radius = 5.0}) {
      if (pt == null) return;

      // Halo exterior transparente
      final haloPaint = Paint()
        ..color = color.withValues(alpha: 0.25)
        ..style = PaintingStyle.fill;
      canvas.drawCircle(pt, radius * 2.2, haloPaint);

      // Círculo coloreado medio
      final midPaint = Paint()
        ..color = color
        ..style = PaintingStyle.fill;
      canvas.drawCircle(pt, radius, midPaint);

      // Punto central blanco nítido
      final centerPaint = Paint()
        ..color = Colors.white
        ..style = PaintingStyle.fill;
      canvas.drawCircle(pt, radius * 0.45, centerPaint);
    }

    // Dibujar nodos de articulaciones
    // Hombros
    drawJoint(pLeftShoulder, const Color(0xFFF59E0B), radius: 6.0);
    drawJoint(pRightShoulder, const Color(0xFFF59E0B), radius: 6.0);

    // Codos (Brazos)
    drawJoint(pLeftElbow, const Color(0xFF06B6D4), radius: 5.0);
    drawJoint(pRightElbow, const Color(0xFF06B6D4), radius: 5.0);

    // Muñecas (Brazos)
    drawJoint(pLeftWrist, const Color(0xFF38BDF8), radius: 4.5);
    drawJoint(pRightWrist, const Color(0xFF38BDF8), radius: 4.5);

    // Caderas
    drawJoint(pLeftHip, const Color(0xFFF59E0B), radius: 5.5);
    drawJoint(pRightHip, const Color(0xFFF59E0B), radius: 5.5);

    // Rodillas y Tobillos
    drawJoint(pLeftKnee, const Color(0xFF10B981), radius: 4.5);
    drawJoint(pRightKnee, const Color(0xFF10B981), radius: 4.5);
    drawJoint(pLeftAnkle, const Color(0xFF10B981), radius: 4.0);
    drawJoint(pRightAnkle, const Color(0xFF10B981), radius: 4.0);
  }

  @override
  bool shouldRepaint(covariant PoseSkeletonPainter oldDelegate) {
    return oldDelegate.pose != pose ||
        oldDelegate.isVisible != isVisible ||
        oldDelegate.cameraAspectRatio != cameraAspectRatio ||
        oldDelegate.quadPoints != quadPoints ||
        oldDelegate.screenSize != screenSize;
  }
}
