import 'dart:ui';

/// Filtro de Suavizado Temporal Exponencial (EMA)
/// Reduce la vibración y jitter entre frames de cámara sucesivos.
/// Formula: nuevaPosicion = anterior * (1 - alpha) + detectada * alpha
class SmoothingFilter {
  final double alpha;

  double? _lastX;
  double? _lastY;
  double? _lastScaleX;
  double? _lastScaleY;
  double? _lastRotation;
  List<Offset>? _lastQuad;

  SmoothingFilter({this.alpha = 0.35});

  void reset() {
    _lastX = null;
    _lastY = null;
    _lastScaleX = null;
    _lastScaleY = null;
    _lastRotation = null;
    _lastQuad = null;
  }

  double smoothValue(double? previous, double current, {bool adaptive = false}) {
    if (previous == null) return current;
    if (!adaptive) {
      return previous * (1.0 - alpha) + current * alpha;
    }
    final diff = (current - previous).abs();
    final dynamicAlpha = (alpha + (diff / 30.0) * (0.85 - alpha)).clamp(alpha, 0.88);
    return previous * (1.0 - dynamicAlpha) + current * dynamicAlpha;
  }

  ({double x, double y, double scaleX, double scaleY, double rotation}) smooth({
    required double x,
    required double y,
    required double scaleX,
    required double scaleY,
    required double rotation,
    bool adaptive = false,
  }) {
    _lastX = smoothValue(_lastX, x, adaptive: adaptive);
    _lastY = smoothValue(_lastY, y, adaptive: adaptive);
    _lastScaleX = smoothValue(_lastScaleX, scaleX, adaptive: adaptive);
    _lastScaleY = smoothValue(_lastScaleY, scaleY, adaptive: adaptive);

    // Suavizado circular simple para rotación
    _lastRotation = smoothValue(_lastRotation, rotation, adaptive: false);

    return (
      x: _lastX!,
      y: _lastY!,
      scaleX: _lastScaleX!,
      scaleY: _lastScaleY!,
      rotation: _lastRotation!,
    );
  }

  /// Suaviza los 4 puntos del cuadrilátero de deformación de perspectiva
  /// con respuesta adaptativa a la velocidad del movimiento corporal
  List<Offset> smoothQuad(List<Offset> currentQuad, {bool adaptive = true}) {
    if (_lastQuad == null || _lastQuad!.length != currentQuad.length) {
      _lastQuad = List.from(currentQuad);
      return currentQuad;
    }

    final smoothed = <Offset>[];
    for (int i = 0; i < currentQuad.length; i++) {
      final prev = _lastQuad![i];
      final curr = currentQuad[i];
      final dist = (curr - prev).distance;
      final effectiveAlpha = adaptive
          ? (alpha + (dist / 35.0) * (0.85 - alpha)).clamp(alpha, 0.88)
          : alpha;
      final smX = prev.dx * (1.0 - effectiveAlpha) + curr.dx * effectiveAlpha;
      final smY = prev.dy * (1.0 - effectiveAlpha) + curr.dy * effectiveAlpha;
      smoothed.add(Offset(smX, smY));
    }
    _lastQuad = smoothed;
    return smoothed;
  }
}
