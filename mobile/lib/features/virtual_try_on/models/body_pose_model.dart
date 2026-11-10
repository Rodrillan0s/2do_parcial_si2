import 'dart:math' as math;

class BodyPoint {
  final double x;
  final double y;
  final double z; // Coordenada de profundidad 3D relativa (en metros) de ML Kit
  final double confidence;

  const BodyPoint({
    required this.x,
    required this.y,
    this.z = 0.0,
    required this.confidence,
  });

  double distanceTo(BodyPoint other) {
    final dx = x - other.x;
    final dy = y - other.y;
    final dz = z - other.z;
    return math.sqrt(dx * dx + dy * dy + dz * dz);
  }

  static BodyPoint midpoint(BodyPoint a, BodyPoint b) {
    return BodyPoint(
      x: (a.x + b.x) / 2,
      y: (a.y + b.y) / 2,
      z: (a.z + b.z) / 2,
      confidence: math.min(a.confidence, b.confidence),
    );
  }
}

class BodyPose {
  final BodyPoint? nose;
  final BodyPoint? leftShoulder;
  final BodyPoint? rightShoulder;
  final BodyPoint? leftElbow;
  final BodyPoint? rightElbow;
  final BodyPoint? leftWrist;
  final BodyPoint? rightWrist;
  final BodyPoint? leftHip;
  final BodyPoint? rightHip;
  final BodyPoint? leftKnee;
  final BodyPoint? rightKnee;
  final BodyPoint? leftAnkle;
  final BodyPoint? rightAnkle;

  const BodyPose({
    this.nose,
    this.leftShoulder,
    this.rightShoulder,
    this.leftElbow,
    this.rightElbow,
    this.leftWrist,
    this.rightWrist,
    this.leftHip,
    this.rightHip,
    this.leftKnee,
    this.rightKnee,
    this.leftAnkle,
    this.rightAnkle,
  });

  bool get hasShoulders =>
      leftShoulder != null &&
      rightShoulder != null &&
      leftShoulder!.confidence > 0.4 &&
      rightShoulder!.confidence > 0.4;

  bool get hasTorso =>
      hasShoulders &&
      leftHip != null &&
      rightHip != null &&
      leftHip!.confidence > 0.3 &&
      rightHip!.confidence > 0.3;

  /// Ángulo de rotación del torso sobre el eje Y (giro lateral / perfil en radianes)
  double get torsoYawAngle {
    if (!hasShoulders) return 0.0;
    final dz = rightShoulder!.z - leftShoulder!.z;
    final dx = rightShoulder!.x - leftShoulder!.x;
    if (dx.abs() < 0.0001) return 0.0;
    return math.atan2(dz, dx);
  }

  /// Ángulo de inclinación hacia adelante o atrás (Pitch en radianes)
  double get torsoPitchAngle {
    if (!hasTorso) return 0.0;
    final shoulderCenterZ = (leftShoulder!.z + rightShoulder!.z) / 2.0;
    final hipCenterZ = (leftHip!.z + rightHip!.z) / 2.0;
    final shoulderCenterY = (leftShoulder!.y + rightShoulder!.y) / 2.0;
    final hipCenterY = (leftHip!.y + rightHip!.y) / 2.0;
    final dz = hipCenterZ - shoulderCenterZ;
    final dy = hipCenterY - shoulderCenterY;
    if (dy.abs() < 0.0001) return 0.0;
    return math.atan2(dz, dy);
  }

  /// Profundidad Z promedio del torso para estimar distancia relativa a la cámara
  double get torsoDepthZ {
    if (hasTorso) {
      return (leftShoulder!.z + rightShoulder!.z + leftHip!.z + rightHip!.z) / 4.0;
    }
    if (hasShoulders) {
      return (leftShoulder!.z + rightShoulder!.z) / 2.0;
    }
    return 0.0;
  }

  bool get hasHips =>
      leftHip != null &&
      rightHip != null &&
      leftHip!.confidence >= 0.45 &&
      rightHip!.confidence >= 0.45;

  bool get hasKnees =>
      leftKnee != null &&
      rightKnee != null &&
      leftKnee!.confidence >= 0.45 &&
      rightKnee!.confidence >= 0.45;

  bool get hasLeftArm =>
      leftShoulder != null &&
      leftElbow != null &&
      leftShoulder!.confidence >= 0.35 &&
      leftElbow!.confidence >= 0.35;

  bool get hasRightArm =>
      rightShoulder != null &&
      rightElbow != null &&
      rightShoulder!.confidence >= 0.35 &&
      rightElbow!.confidence >= 0.35;

  bool get hasArms => hasLeftArm || hasRightArm;

  bool get hasFullArms => hasLeftArm && hasRightArm;

  bool get hasForearms =>
      (leftElbow != null && leftWrist != null && leftElbow!.confidence >= 0.35 && leftWrist!.confidence >= 0.35) ||
      (rightElbow != null && rightWrist != null && rightElbow!.confidence >= 0.35 && rightWrist!.confidence >= 0.35);

  bool get isBodyDetected => hasShoulders || hasHips;
}

