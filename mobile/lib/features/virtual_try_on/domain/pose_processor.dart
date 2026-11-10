import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';
import '../models/body_pose_model.dart';

/// Procesador de poses corporales utilizando Google ML Kit Pose Detection.
/// Recibe frames de la cámara en streaming y genera modelos BodyPose desacoplados.
class PoseProcessor {
  final PoseDetector _poseDetector;
  bool _isProcessing = false;

  PoseProcessor()
      : _poseDetector = PoseDetector(
          options: PoseDetectorOptions(
            mode: PoseDetectionMode.stream,
            model: PoseDetectionModel.base,
          ),
        );

  bool get isProcessing => _isProcessing;

  /// Procesa un frame de la cámara y retorna un BodyPose normalizado (0.0 a 1.0)
  Future<BodyPose?> processCameraImage({
    required CameraImage image,
    required CameraDescription camera,
  }) async {
    // Throttling: descartar frame si el detector aún está procesando el anterior
    if (_isProcessing) return null;

    _isProcessing = true;
    try {
      final inputImage = _buildInputImage(image, camera);
      if (inputImage == null) return null;

      final List<Pose> poses = await _poseDetector.processImage(inputImage);
      if (poses.isEmpty) {
        return const BodyPose();
      }

      final isFrontCamera = camera.lensDirection == CameraLensDirection.front;
      final rotation = inputImage.metadata?.rotation ?? InputImageRotation.rotation0deg;
      final isRotated = rotation == InputImageRotation.rotation90deg ||
          rotation == InputImageRotation.rotation270deg;

      final effectiveWidth =
          isRotated ? image.height.toDouble() : image.width.toDouble();
      final effectiveHeight =
          isRotated ? image.width.toDouble() : image.height.toDouble();

      return _mapPoseToBodyPose(
        poses.first,
        effectiveWidth: effectiveWidth,
        effectiveHeight: effectiveHeight,
        isFrontCamera: isFrontCamera,
      );
    } catch (e) {
      debugPrint('[PoseProcessor] Error al procesar frame: $e');
      return null;
    } finally {
      _isProcessing = false;
    }
  }

  /// Construye un InputImage a partir de un CameraImage
  InputImage? _buildInputImage(CameraImage image, CameraDescription camera) {
    final sensorOrientation = camera.sensorOrientation;
    final rotation = InputImageRotationValue.fromRawValue(sensorOrientation) ??
        InputImageRotation.rotation0deg;

    final format = (defaultTargetPlatform == TargetPlatform.android)
        ? InputImageFormat.nv21
        : (InputImageFormatValue.fromRawValue(image.format.raw) ??
            InputImageFormat.bgra8888);

    final WriteBuffer allBytes = WriteBuffer();
    for (final Plane plane in image.planes) {
      allBytes.putUint8List(plane.bytes);
    }
    final bytes = allBytes.done().buffer.asUint8List();

    final metadata = InputImageMetadata(
      size: Size(image.width.toDouble(), image.height.toDouble()),
      rotation: rotation,
      format: format,
      bytesPerRow: image.planes[0].bytesPerRow,
    );

    return InputImage.fromBytes(bytes: bytes, metadata: metadata);
  }

  /// Mapea los landmarks nativos de ML Kit al modelo de dominio BodyPose
  BodyPose _mapPoseToBodyPose(
    Pose pose, {
    required double effectiveWidth,
    required double effectiveHeight,
    required bool isFrontCamera,
  }) {
    BodyPoint? mapLandmark(PoseLandmarkType type) {
      final lm = pose.landmarks[type];
      if (lm == null) return null;

      double normX = lm.x / effectiveWidth;
      double normY = lm.y / effectiveHeight;

      // Clamping para seguridad
      normX = normX.clamp(0.0, 1.0);
      normY = normY.clamp(0.0, 1.0);

      return BodyPoint(
        x: normX,
        y: normY,
        z: lm.z,
        confidence: lm.likelihood,
      );
    }

    return BodyPose(
      nose: mapLandmark(PoseLandmarkType.nose),
      leftShoulder: mapLandmark(PoseLandmarkType.leftShoulder),
      rightShoulder: mapLandmark(PoseLandmarkType.rightShoulder),
      leftElbow: mapLandmark(PoseLandmarkType.leftElbow),
      rightElbow: mapLandmark(PoseLandmarkType.rightElbow),
      leftWrist: mapLandmark(PoseLandmarkType.leftWrist),
      rightWrist: mapLandmark(PoseLandmarkType.rightWrist),
      leftHip: mapLandmark(PoseLandmarkType.leftHip),
      rightHip: mapLandmark(PoseLandmarkType.rightHip),
      leftKnee: mapLandmark(PoseLandmarkType.leftKnee),
      rightKnee: mapLandmark(PoseLandmarkType.rightKnee),
      leftAnkle: mapLandmark(PoseLandmarkType.leftAnkle),
      rightAnkle: mapLandmark(PoseLandmarkType.rightAnkle),
    );
  }

  /// Cierra el detector de poses liberando recursos nativos
  Future<void> dispose() async {
    await _poseDetector.close();
  }
}
