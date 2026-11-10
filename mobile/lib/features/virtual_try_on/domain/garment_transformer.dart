import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../models/body_pose_model.dart';
import '../models/garment_model.dart';
import 'smoothing_filter.dart';

class GarmentTransform {
  final double x;
  final double y;
  final double width;
  final double height;
  final double rotation;
  final bool visible;

  // Campos para Warping de Perspectiva 4 Puntos (Fase 5)
  final Matrix4? perspectiveTransform;
  final List<Offset>? quadPoints;
  final double sourceWidth;
  final double sourceHeight;
  final bool usePerspective;

  const GarmentTransform({
    required this.x,
    required this.y,
    required this.width,
    required this.height,
    required this.rotation,
    required this.visible,
    this.perspectiveTransform,
    this.quadPoints,
    this.sourceWidth = 300.0,
    this.sourceHeight = 360.0,
    this.usePerspective = false,
  });

  static const GarmentTransform hidden = GarmentTransform(
    x: 0,
    y: 0,
    width: 0,
    height: 0,
    rotation: 0,
    visible: false,
    usePerspective: false,
  );
}

class GarmentTransformer {
  final SmoothingFilter _filter = SmoothingFilter(alpha: 0.35);
  int _framesWithoutPose = 0;
  GarmentTransform _lastValidTransform = GarmentTransform.hidden;

  void reset() {
    _filter.reset();
    _framesWithoutPose = 0;
    _lastValidTransform = GarmentTransform.hidden;
  }

  /// Mapea un punto normalizado (0..1) al espacio de píxeles de la pantalla,
  /// corrigiendo el escalado y recorte (BoxFit.cover) de la cámara en vivo.
  static Offset mapPointToScreen({
    required BodyPoint point,
    required Size screenSize,
    double? cameraAspectRatio,
  }) {
    if (cameraAspectRatio == null || cameraAspectRatio <= 0) {
      return Offset(point.x * screenSize.width, point.y * screenSize.height);
    }

    final double camAspect = 1.0 / cameraAspectRatio;
    final double screenAspect = screenSize.width / screenSize.height;

    double renderedWidth;
    double renderedHeight;
    double offsetX;
    double offsetY;

    if (screenAspect < camAspect) {
      // Pantalla más alargada que la cámara: llena altura, se recorta a los lados
      renderedHeight = screenSize.height;
      renderedWidth = screenSize.height * camAspect;
      offsetX = (screenSize.width - renderedWidth) / 2.0;
      offsetY = 0.0;
    } else {
      // Pantalla más ancha que la cámara: llena ancho, se recorta arriba/abajo
      renderedWidth = screenSize.width;
      renderedHeight = screenSize.width / camAspect;
      offsetX = 0.0;
      offsetY = (screenSize.height - renderedHeight) / 2.0;
    }

    return Offset(
      offsetX + point.x * renderedWidth,
      offsetY + point.y * renderedHeight,
    );
  }

  /// Verifica si un cuadrilátero [P0, P1, P2, P3] es convexo y no auto-intersecante
  static bool isQuadConvex(List<Offset> quad) {
    if (quad.length != 4) return false;

    double crossProduct(Offset a, Offset b, Offset c) {
      final abX = b.dx - a.dx;
      final abY = b.dy - a.dy;
      final bcX = c.dx - b.dx;
      final bcY = c.dy - b.dy;
      return abX * bcY - abY * bcX;
    }

    final c0 = crossProduct(quad[3], quad[0], quad[1]);
    final c1 = crossProduct(quad[0], quad[1], quad[2]);
    final c2 = crossProduct(quad[1], quad[2], quad[3]);
    final c3 = crossProduct(quad[2], quad[3], quad[0]);

    final allPositive = c0 > 1e-3 && c1 > 1e-3 && c2 > 1e-3 && c3 > 1e-3;
    final allNegative = c0 < -1e-3 && c1 < -1e-3 && c2 < -1e-3 && c3 < -1e-3;
    return allPositive || allNegative;
  }

  /// Calcula la matriz de transformación proyectiva (Homografía de 4 puntos)
  /// que deforma el rectángulo fuente [0, 0, width, height] hacia el cuadrilátero destino [P0, P1, P2, P3].
  /// Basado en el algoritmo de mapeo proyectivo de 8 parámetros de Heckbert.
  static Matrix4? computePerspectiveMatrix(
    double width,
    double height,
    List<Offset> quad,
  ) {
    if (quad.length != 4 || width <= 0 || height <= 0) return null;
    if (!isQuadConvex(quad)) return null;

    final p0 = quad[0]; // Top-Left
    final p1 = quad[1]; // Top-Right
    final p2 = quad[2]; // Bottom-Right
    final p3 = quad[3]; // Bottom-Left

    final double dx1 = p1.dx - p2.dx;
    final double dx2 = p3.dx - p2.dx;
    final double sx = p0.dx - p1.dx + p2.dx - p3.dx;

    final double dy1 = p1.dy - p2.dy;
    final double dy2 = p3.dy - p2.dy;
    final double sy = p0.dy - p1.dy + p2.dy - p3.dy;

    double a11, a12, a13, a21, a22, a23;
    double g = 0.0;
    double h = 0.0;

    if (sx.abs() < 1e-5 && sy.abs() < 1e-5) {
      // Paralelogramo / Afín
      a11 = p1.dx - p0.dx;
      a12 = p3.dx - p0.dx;
      a13 = p0.dx;
      a21 = p1.dy - p0.dy;
      a22 = p3.dy - p0.dy;
      a23 = p0.dy;
    } else {
      final double det = dx1 * dy2 - dx2 * dy1;
      if (det.abs() < 1e-5) return null;

      g = (sx * dy2 - sy * dx2) / det;
      h = (dx1 * sy - dy1 * sx) / det;

      a11 = p1.dx - p0.dx + g * p1.dx;
      a12 = p3.dx - p0.dx + h * p3.dx;
      a13 = p0.dx;
      a21 = p1.dy - p0.dy + g * p1.dy;
      a22 = p3.dy - p0.dy + h * p3.dy;
      a23 = p0.dy;
    }

    // Normalizar respecto a las dimensiones de la imagen fuente
    final double h00 = a11 / width;
    final double h01 = a12 / height;
    final double h02 = a13;

    final double h10 = a21 / width;
    final double h11 = a22 / height;
    final double h12 = a23;

    final double h20 = g / width;
    final double h21 = h / height;
    const double h22 = 1.0;

    // Flutter Matrix4 utiliza almacenamiento column-major
    final matrix = Matrix4.identity();
    matrix.storage[0] = h00;
    matrix.storage[1] = h10;
    matrix.storage[3] = h20;

    matrix.storage[4] = h01;
    matrix.storage[5] = h11;
    matrix.storage[7] = h21;

    matrix.storage[10] = 1.0;

    matrix.storage[12] = h02;
    matrix.storage[13] = h12;
    matrix.storage[15] = h22;

    return matrix;
  }

  GarmentTransform computeTransform({
    required BodyPose pose,
    required GarmentModel garment,
    required Size screenSize,
    double? cameraAspectRatio,
    double sizeScale = 1.0,
    bool isFrontCamera = true,
  }) {
    // Si no hay hombros ni cadera detectados
    if (!pose.isBodyDetected) {
      _framesWithoutPose++;
      if (_framesWithoutPose <= 5 && _lastValidTransform.visible) {
        // Estabilidad mínima: conservar última pose hasta 5 frames
        return _lastValidTransform;
      }
      return GarmentTransform.hidden;
    }

    _framesWithoutPose = 0;

    GarmentTransform raw;
    switch (garment.tipo) {
      case GarmentType.top:
        raw = _transformTop(pose, screenSize, cameraAspectRatio, sizeScale);
        break;
      case GarmentType.pant:
        raw = _transformPant(pose, screenSize, cameraAspectRatio, sizeScale);
        break;
      case GarmentType.dress:
        raw = _transformDress(pose, screenSize, cameraAspectRatio, sizeScale);
        break;
    }

    if (!raw.visible) return GarmentTransform.hidden;

    // Aplicar filtro de suavizado temporal EMA adaptativo en posición, escala y rotación
    final smoothed = _filter.smooth(
      x: raw.x,
      y: raw.y,
      scaleX: raw.width,
      scaleY: raw.height,
      rotation: raw.rotation,
      adaptive: true,
    );

    // Aplicar suavizado a los 4 puntos de perspectiva (Warping)
    List<Offset>? smoothedQuad;
    Matrix4? smoothedPerspectiveMatrix;
    bool usePerspective = false;

    if (raw.quadPoints != null && raw.quadPoints!.length == 4) {
      smoothedQuad = _filter.smoothQuad(raw.quadPoints!, adaptive: true);
      smoothedPerspectiveMatrix = computePerspectiveMatrix(
        raw.sourceWidth,
        raw.sourceHeight,
        smoothedQuad,
      );
      usePerspective = smoothedPerspectiveMatrix != null;
    }

    _lastValidTransform = GarmentTransform(
      x: smoothed.x,
      y: smoothed.y,
      width: smoothed.scaleX,
      height: smoothed.scaleY,
      rotation: smoothed.rotation,
      visible: true,
      perspectiveTransform: smoothedPerspectiveMatrix,
      quadPoints: smoothedQuad,
      sourceWidth: raw.sourceWidth,
      sourceHeight: raw.sourceHeight,
      usePerspective: usePerspective,
    );

    return _lastValidTransform;
  }

  GarmentTransform _transformTop(
    BodyPose pose,
    Size screenSize,
    double? cameraAspectRatio,
    double sizeScale,
  ) {
    if (!pose.hasShoulders) return GarmentTransform.hidden;

    final pShoulder1 = mapPointToScreen(
      point: pose.leftShoulder!,
      screenSize: screenSize,
      cameraAspectRatio: cameraAspectRatio,
    );
    final pShoulder2 = mapPointToScreen(
      point: pose.rightShoulder!,
      screenSize: screenSize,
      cameraAspectRatio: cameraAspectRatio,
    );

    // Ordenar hombros de izquierda a derecha en la pantalla
    final pLeft = pShoulder1.dx <= pShoulder2.dx ? pShoulder1 : pShoulder2;
    final pRight = pShoulder1.dx <= pShoulder2.dx ? pShoulder2 : pShoulder1;

    // Distancia y centro de hombros en pantalla
    final shoulderVec = Offset(pRight.dx - pLeft.dx, pRight.dy - pLeft.dy);
    final shoulderWidth = shoulderVec.distance;
    final shoulderCenter = Offset(
      (pLeft.dx + pRight.dx) / 2.0,
      (pLeft.dy + pRight.dy) / 2.0,
    );

    // Ángulo de inclinación de los hombros
    final angle = math.atan2(shoulderVec.dy, shoulderVec.dx);

    // Vector unitario perpendicular apuntando hacia arriba (hacia el cuello/cabeza)
    final upVecRaw = Offset(shoulderVec.dy, -shoulderVec.dx);
    final upVecLen = upVecRaw.distance;
    final upVec = upVecLen > 1e-4
        ? Offset(upVecRaw.dx / upVecLen, upVecRaw.dy / upVecLen)
        : const Offset(0, -1);

    final rightDir = shoulderWidth > 1e-4
        ? Offset(shoulderVec.dx / shoulderWidth, shoulderVec.dy / shoulderWidth)
        : const Offset(1, 0);
    final leftDir = -rightDir;

    // Centro del torso para clasificar codos/brazos por lado de pantalla
    final centerTorsoX = shoulderCenter.dx;

    Offset? pElbowLeft;
    Offset? pElbowRight;

    if (pose.leftElbow != null && pose.leftElbow!.confidence >= 0.35) {
      final e = mapPointToScreen(
        point: pose.leftElbow!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      if (e.dx <= centerTorsoX) {
        pElbowLeft = e;
      } else {
        pElbowRight = e;
      }
    }

    if (pose.rightElbow != null && pose.rightElbow!.confidence >= 0.35) {
      final e = mapPointToScreen(
        point: pose.rightElbow!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      if (e.dx > centerTorsoX) {
        pElbowRight = e;
      } else {
        pElbowLeft ??= e;
      }
    }

    // Detección de caderas y altura del torso
    double torsoHeight;
    Offset pHipLeft;
    Offset pHipRight;

    if (pose.hasHips) {
      final h1 = mapPointToScreen(
        point: pose.leftHip!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      final h2 = mapPointToScreen(
        point: pose.rightHip!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      pHipLeft = h1.dx <= h2.dx ? h1 : h2;
      pHipRight = h1.dx <= h2.dx ? h2 : h1;
      final hipCenter = Offset(
        (pHipLeft.dx + pHipRight.dx) / 2.0,
        (pHipLeft.dy + pHipRight.dy) / 2.0,
      );
      torsoHeight = (hipCenter - shoulderCenter).distance;
    } else {
      torsoHeight = shoulderWidth * 1.30;
      final downVector = Offset(-upVec.dx * torsoHeight, -upVec.dy * torsoHeight);
      pHipLeft = pLeft + downVector;
      pHipRight = pRight + downVector;
    }

    // Ancho dinámico del pecho adaptado a la apertura de brazos
    double armSpanWidth = shoulderWidth;
    if (pElbowLeft != null && pElbowRight != null) {
      final elbowDist = (pElbowRight.dx - pElbowLeft.dx).abs();
      if (elbowDist > shoulderWidth && elbowDist < shoulderWidth * 3.0) {
        armSpanWidth = math.max(shoulderWidth, elbowDist * 0.75);
      }
    }

    final garmentWidth = math.max(110.0, armSpanWidth * 1.42 * sizeScale);
    final garmentHeight = math.max(
      135.0,
      math.max(garmentWidth * 1.10, torsoHeight * 1.25) * sizeScale,
    );

    // Anclaje del cuello en las clavículas (ajustado para que la prenda no caiga en la panza)
    final posX = shoulderCenter.dx;
    final posY = shoulderCenter.dy + (garmentHeight * 0.32);

    // =========================================================================
    // CÁLCULO DE CUADRILÁTERO DE PERSPECTIVA (FASE 5) CON CUELLO ANCLADO
    // P0: Hombro/Manga Izquierda | P1: Hombro/Manga Derecha
    // P2: Cadera/Faldón Derecho | P3: Cadera/Faldón Izquierdo
    // =========================================================================
    final collarLift = upVec * (shoulderWidth * 0.16 * sizeScale);
    final hemDown = -upVec * (torsoHeight * 0.14 * sizeScale);
    final baseSleeveDist = shoulderWidth * 0.32 * sizeScale;

    // P0: Manga izquierda anclada a la línea del hombro y adaptable al brazo
    Offset armShiftL = Offset.zero;
    if (pElbowLeft != null) {
      final armVec = pElbowLeft - pLeft;
      // Si el brazo se levanta hacia arriba
      if (pElbowLeft.dy < pLeft.dy) {
        armShiftL = Offset(armVec.dx * 0.35, armVec.dy * 0.50) * sizeScale;
      } else if (armVec.dx < -shoulderWidth * 0.20) {
        // Brazo abierto hacia un lado
        armShiftL = Offset(armVec.dx * 0.28, 0) * sizeScale;
      }
    }
    final p0 = pLeft + leftDir * baseSleeveDist + collarLift + armShiftL;

    // P1: Manga derecha anclada a la línea del hombro y adaptable al brazo
    Offset armShiftR = Offset.zero;
    if (pElbowRight != null) {
      final armVec = pElbowRight - pRight;
      if (pElbowRight.dy < pRight.dy) {
        armShiftR = Offset(armVec.dx * 0.35, armVec.dy * 0.50) * sizeScale;
      } else if (armVec.dx > shoulderWidth * 0.20) {
        armShiftR = Offset(armVec.dx * 0.28, 0) * sizeScale;
      }
    }
    final p1 = pRight + rightDir * baseSleeveDist + collarLift + armShiftR;

    // Faldón inferior / cintura (P2 y P3) ceñido a las caderas
    final hipVec = Offset(pHipRight.dx - pHipLeft.dx, pHipRight.dy - pHipLeft.dy);
    final hipWidth = hipVec.distance;
    final hipDir = hipWidth > 1e-4 ? Offset(hipVec.dx / hipWidth, hipVec.dy / hipWidth) : rightDir;

    final waistExt = math.max(shoulderWidth, hipWidth) * 0.22 * sizeScale;
    final p2 = pHipRight + hipDir * waistExt + hemDown;
    final p3 = pHipLeft - hipDir * waistExt + hemDown;

    final quadPoints = [p0, p1, p2, p3];

    return GarmentTransform(
      x: posX,
      y: posY,
      width: garmentWidth,
      height: garmentHeight,
      rotation: angle,
      visible: true,
      quadPoints: quadPoints,
      sourceWidth: 320.0,
      sourceHeight: 380.0,
    );
  }

  GarmentTransform _transformPant(
    BodyPose pose,
    Size screenSize,
    double? cameraAspectRatio,
    double sizeScale,
  ) {
    Offset pHipLeft;
    Offset pHipRight;
    double hipWidth;
    Offset centerHips;
    double angle = 0.0;

    if (pose.hasHips) {
      final h1 = mapPointToScreen(
        point: pose.leftHip!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      final h2 = mapPointToScreen(
        point: pose.rightHip!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      pHipLeft = h1.dx <= h2.dx ? h1 : h2;
      pHipRight = h1.dx <= h2.dx ? h2 : h1;
      centerHips = Offset((pHipLeft.dx + pHipRight.dx) / 2.0, (pHipLeft.dy + pHipRight.dy) / 2.0);
      hipWidth = (pHipRight - pHipLeft).distance;
      angle = math.atan2(pHipRight.dy - pHipLeft.dy, pHipRight.dx - pHipLeft.dx);
    } else if (pose.hasShoulders) {
      final s1 = mapPointToScreen(
        point: pose.leftShoulder!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      final s2 = mapPointToScreen(
        point: pose.rightShoulder!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      final sL = s1.dx <= s2.dx ? s1 : s2;
      final sR = s1.dx <= s2.dx ? s2 : s1;
      final sWidth = (sR - sL).distance;
      hipWidth = sWidth * 0.85;
      final sCenter = Offset((sL.dx + sR.dx) / 2.0, (sL.dy + sR.dy) / 2.0);
      centerHips = Offset(sCenter.dx, sCenter.dy + hipWidth * 1.3);
      angle = math.atan2(sR.dy - sL.dy, sR.dx - sL.dx);
      pHipLeft = Offset(centerHips.dx - hipWidth / 2.0, centerHips.dy);
      pHipRight = Offset(centerHips.dx + hipWidth / 2.0, centerHips.dy);
    } else {
      return GarmentTransform.hidden;
    }

    final centerTorsoX = centerHips.dx;

    // Detectar rodillas separadas por lado de pantalla
    Offset? pKneeLeft;
    Offset? pKneeRight;
    if (pose.leftKnee != null && pose.leftKnee!.confidence >= 0.35) {
      final k = mapPointToScreen(
        point: pose.leftKnee!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      if (k.dx <= centerTorsoX) {
        pKneeLeft = k;
      } else {
        pKneeRight = k;
      }
    }
    if (pose.rightKnee != null && pose.rightKnee!.confidence >= 0.35) {
      final k = mapPointToScreen(
        point: pose.rightKnee!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      if (k.dx > centerTorsoX) {
        pKneeRight = k;
      } else {
        pKneeLeft ??= k;
      }
    }

    // Detectar tobillos separados por lado de pantalla
    Offset? pAnkleLeft;
    Offset? pAnkleRight;
    if (pose.leftAnkle != null && pose.leftAnkle!.confidence >= 0.35) {
      final a = mapPointToScreen(
        point: pose.leftAnkle!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      if (a.dx <= centerTorsoX) {
        pAnkleLeft = a;
      } else {
        pAnkleRight = a;
      }
    }
    if (pose.rightAnkle != null && pose.rightAnkle!.confidence >= 0.35) {
      final a = mapPointToScreen(
        point: pose.rightAnkle!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      if (a.dx > centerTorsoX) {
        pAnkleRight = a;
      } else {
        pAnkleLeft ??= a;
      }
    }

    // Cálculo de posición de los pies/bajos siguiendo las piernas activas
    final defaultLegLen = hipWidth * 2.8;
    final downVec = Offset(-math.sin(angle), math.cos(angle));

    Offset legFootLeft;
    if (pAnkleLeft != null) {
      legFootLeft = pAnkleLeft;
    } else if (pKneeLeft != null) {
      final kneeVec = pKneeLeft - pHipLeft;
      legFootLeft = pHipLeft + kneeVec * 1.85;
    } else {
      legFootLeft = pHipLeft + downVec * defaultLegLen;
    }

    Offset legFootRight;
    if (pAnkleRight != null) {
      legFootRight = pAnkleRight;
    } else if (pKneeRight != null) {
      final kneeVec = pKneeRight - pHipRight;
      legFootRight = pHipRight + kneeVec * 1.85;
    } else {
      legFootRight = pHipRight + downVec * defaultLegLen;
    }

    final hipVec = Offset(pHipRight.dx - pHipLeft.dx, pHipRight.dy - pHipLeft.dy);
    final hipDir = hipWidth > 1e-4 ? Offset(hipVec.dx / hipWidth, hipVec.dy / hipWidth) : const Offset(1, 0);
    final upVec = Offset(-hipDir.dy, hipDir.dx);

    final p0 = pHipLeft - hipDir * (hipWidth * 0.15 * sizeScale) + upVec * (hipWidth * 0.08);
    final p1 = pHipRight + hipDir * (hipWidth * 0.15 * sizeScale) + upVec * (hipWidth * 0.08);

    final cuffWidth = hipWidth * 0.20 * sizeScale;
    final p2 = legFootRight + hipDir * cuffWidth;
    final p3 = legFootLeft - hipDir * cuffWidth;

    final quadPoints = [p0, p1, p2, p3];

    final legSpan = (legFootRight.dx - legFootLeft.dx).abs();
    final legHeight = ((legFootLeft.dy + legFootRight.dy) / 2.0 - centerHips.dy).abs();

    final garmentWidth = math.max(100.0, math.max(hipWidth * 1.45, legSpan + cuffWidth * 1.8) * sizeScale);
    final garmentHeight = math.max(150.0, legHeight * 1.05 * sizeScale);

    final posX = centerHips.dx;
    final posY = centerHips.dy + (garmentHeight * 0.45);

    return GarmentTransform(
      x: posX,
      y: posY,
      width: garmentWidth,
      height: garmentHeight,
      rotation: angle,
      visible: true,
      quadPoints: quadPoints,
      sourceWidth: 280.0,
      sourceHeight: 450.0,
    );
  }

  GarmentTransform _transformDress(
    BodyPose pose,
    Size screenSize,
    double? cameraAspectRatio,
    double sizeScale,
  ) {
    if (!pose.hasShoulders) return GarmentTransform.hidden;

    final s1 = mapPointToScreen(
      point: pose.leftShoulder!,
      screenSize: screenSize,
      cameraAspectRatio: cameraAspectRatio,
    );
    final s2 = mapPointToScreen(
      point: pose.rightShoulder!,
      screenSize: screenSize,
      cameraAspectRatio: cameraAspectRatio,
    );
    final pLeft = s1.dx <= s2.dx ? s1 : s2;
    final pRight = s1.dx <= s2.dx ? s2 : s1;

    final shoulderCenter = Offset((pLeft.dx + pRight.dx) / 2.0, (pLeft.dy + pRight.dy) / 2.0);
    final shoulderVec = Offset(pRight.dx - pLeft.dx, pRight.dy - pLeft.dy);
    final shoulderWidth = shoulderVec.distance;
    final angle = math.atan2(shoulderVec.dy, shoulderVec.dx);

    final upVecRaw = Offset(shoulderVec.dy, -shoulderVec.dx);
    final upVecLen = upVecRaw.distance;
    final upVec = upVecLen > 1e-4
        ? Offset(upVecRaw.dx / upVecLen, upVecRaw.dy / upVecLen)
        : const Offset(0, -1);
    final rightDir = shoulderWidth > 1e-4
        ? Offset(shoulderVec.dx / shoulderWidth, shoulderVec.dy / shoulderWidth)
        : const Offset(1, 0);
    final leftDir = -rightDir;

    // Detectar codos
    final centerTorsoX = shoulderCenter.dx;
    Offset? pElbowLeft;
    Offset? pElbowRight;
    if (pose.leftElbow != null && pose.leftElbow!.confidence >= 0.35) {
      final e = mapPointToScreen(
        point: pose.leftElbow!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      if (e.dx <= centerTorsoX) {
        pElbowLeft = e;
      } else {
        pElbowRight = e;
      }
    }
    if (pose.rightElbow != null && pose.rightElbow!.confidence >= 0.35) {
      final e = mapPointToScreen(
        point: pose.rightElbow!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      if (e.dx > centerTorsoX) {
        pElbowRight = e;
      } else {
        pElbowLeft ??= e;
      }
    }

    final baseSleeveDist = shoulderWidth * 0.28 * sizeScale;
    final collarLift = upVec * (shoulderWidth * 0.16 * sizeScale);

    // P0 manga izquierda
    Offset armShiftL = Offset.zero;
    if (pElbowLeft != null) {
      final armVec = pElbowLeft - pLeft;
      if (pElbowLeft.dy < pLeft.dy) {
        armShiftL = Offset(armVec.dx * 0.35, armVec.dy * 0.50) * sizeScale;
      } else if (armVec.dx < -shoulderWidth * 0.20) {
        armShiftL = Offset(armVec.dx * 0.28, 0) * sizeScale;
      }
    }
    final p0 = pLeft + leftDir * baseSleeveDist + collarLift + armShiftL;

    // P1 manga derecha
    Offset armShiftR = Offset.zero;
    if (pElbowRight != null) {
      final armVec = pElbowRight - pRight;
      if (pElbowRight.dy < pRight.dy) {
        armShiftR = Offset(armVec.dx * 0.35, armVec.dy * 0.50) * sizeScale;
      } else if (armVec.dx > shoulderWidth * 0.20) {
        armShiftR = Offset(armVec.dx * 0.28, 0) * sizeScale;
      }
    }
    final p1 = pRight + rightDir * baseSleeveDist + collarLift + armShiftR;

    // Detectar rodillas y caderas para la falda
    Offset? pKneeLeft;
    Offset? pKneeRight;
    if (pose.leftKnee != null && pose.leftKnee!.confidence >= 0.35) {
      final k = mapPointToScreen(
        point: pose.leftKnee!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      if (k.dx <= centerTorsoX) {
        pKneeLeft = k;
      } else {
        pKneeRight = k;
      }
    }
    if (pose.rightKnee != null && pose.rightKnee!.confidence >= 0.35) {
      final k = mapPointToScreen(
        point: pose.rightKnee!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      if (k.dx > centerTorsoX) {
        pKneeRight = k;
      } else {
        pKneeLeft ??= k;
      }
    }

    double dressLength;
    Offset bottomL;
    Offset bottomR;

    if (pKneeLeft != null && pKneeRight != null) {
      final centerKnees = Offset((pKneeLeft.dx + pKneeRight.dx) / 2.0, (pKneeLeft.dy + pKneeRight.dy) / 2.0);
      dressLength = (centerKnees - shoulderCenter).distance * 1.25;
      bottomL = pKneeLeft;
      bottomR = pKneeRight;
    } else if (pose.hasHips) {
      final h1 = mapPointToScreen(
        point: pose.leftHip!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      final h2 = mapPointToScreen(
        point: pose.rightHip!,
        screenSize: screenSize,
        cameraAspectRatio: cameraAspectRatio,
      );
      final hL = h1.dx <= h2.dx ? h1 : h2;
      final hR = h1.dx <= h2.dx ? h2 : h1;
      final hipCenter = Offset((hL.dx + hR.dx) / 2.0, (hL.dy + hR.dy) / 2.0);
      dressLength = (hipCenter - shoulderCenter).distance * 2.0;
      final downVector = Offset(-upVec.dx * dressLength * 0.55, -upVec.dy * dressLength * 0.55);
      bottomL = hL + downVector;
      bottomR = hR + downVector;
    } else {
      dressLength = shoulderWidth * 2.8;
      final downVector = Offset(-upVec.dx * dressLength, -upVec.dy * dressLength);
      bottomL = pLeft + downVector;
      bottomR = pRight + downVector;
    }

    final garmentWidth = math.max(120.0, shoulderWidth * 1.65 * sizeScale);
    final garmentHeight = math.max(170.0, dressLength * sizeScale);
    final posX = shoulderCenter.dx;
    final posY = shoulderCenter.dy + (garmentHeight * 0.38);

    // Cuadrilátero para Vestido: P2 y P3 acampanados en la falda
    final bottomVec = Offset(bottomR.dx - bottomL.dx, bottomR.dy - bottomL.dy);
    final bottomDir = bottomVec.distance > 1e-4
        ? Offset(bottomVec.dx / bottomVec.distance, bottomVec.dy / bottomVec.distance)
        : rightDir;
    final flare = shoulderWidth * 0.38 * sizeScale;

    final p2 = bottomR + bottomDir * flare;
    final p3 = bottomL - bottomDir * flare;

    final quadPoints = [p0, p1, p2, p3];

    return GarmentTransform(
      x: posX,
      y: posY,
      width: garmentWidth,
      height: garmentHeight,
      rotation: angle,
      visible: true,
      quadPoints: quadPoints,
      sourceWidth: 320.0,
      sourceHeight: 520.0,
    );
  }
}
