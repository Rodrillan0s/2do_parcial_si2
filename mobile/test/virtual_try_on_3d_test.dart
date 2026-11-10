import 'package:flutter_test/flutter_test.dart';
import 'package:aurora_store_mobile/features/virtual_try_on/models/body_pose_model.dart';
import 'package:aurora_store_mobile/features/virtual_try_on/models/garment_model.dart';

void main() {
  group('Realidad Aumentada Híbrida 3D & ARCore Tests', () {
    test('1. GarmentModel asigna modelos 3D volumétricos (.glb) por categoría', () {
      final topGarment = GarmentModel.fromJson({
        'id_producto': 101,
        'nombre': 'Camisa Seda Minimalist',
        'tipo_prenda_ra': 'TOP',
        'precio': 189.0,
      });

      expect(topGarment.modelo3dUrl, isNotNull);
      expect(topGarment.modelo3dUrl!.endsWith('.glb'), isTrue);
      expect(topGarment.modelo3dUrl!.contains('shirt_baked.glb'), isTrue);

      final dressGarment = GarmentModel.fromJson({
        'id_producto': 102,
        'nombre': 'Vestido Corset Gala',
        'tipo_prenda_ra': 'DRESS',
        'precio': 450.0,
      });
      expect(dressGarment.modelo3dUrl!.contains('Corset.glb'), isTrue);

      final shoeGarment = GarmentModel.fromJson({
        'id_producto': 103,
        'nombre': 'Sneakers Luxury Gold',
        'tipo_prenda_ra': 'PANT',
        'precio': 299.0,
      });
      expect(shoeGarment.modelo3dUrl!.contains('MaterialsVariantsShoe.glb'), isTrue);
    });

    test('2. GarmentModel respeta modelo_3d_url personalizado si viene de la base de datos', () {
      final customGarment = GarmentModel.fromJson({
        'id_producto': 200,
        'nombre': 'Chaqueta Cuero Edición Limitada',
        'tipo_prenda_ra': 'TOP',
        'modelo_3d_url': 'https://cdn.aurorastore.com/models3d/chaqueta_custom.glb',
        'precio': 520.0,
      });

      expect(customGarment.modelo3dUrl, 'https://cdn.aurorastore.com/models3d/chaqueta_custom.glb');
    });

    test('3. BodyPoint calcula distancias euclidianas tridimensionales con profundidad Z', () {
      const p1 = BodyPoint(x: 0.0, y: 0.0, z: 0.0, confidence: 0.9);
      const p2 = BodyPoint(x: 3.0, y: 4.0, z: 12.0, confidence: 0.9);

      // sqrt(3^2 + 4^2 + 12^2) = sqrt(9 + 16 + 144) = sqrt(169) = 13.0
      expect(p1.distanceTo(p2), closeTo(13.0, 0.001));

      final mid = BodyPoint.midpoint(p1, p2);
      expect(mid.x, 1.5);
      expect(mid.y, 2.0);
      expect(mid.z, 6.0);
    });

    test('4. BodyPose calcula orientación espacial 3D del torso (Yaw, Pitch y Profundidad Z)', () {
      // Hombros perpendiculares a la cámara (persona de frente)
      const poseFrente = BodyPose(
        leftShoulder: BodyPoint(x: 0.3, y: 0.2, z: 1.0, confidence: 0.8),
        rightShoulder: BodyPoint(x: 0.7, y: 0.2, z: 1.0, confidence: 0.8),
        leftHip: BodyPoint(x: 0.35, y: 0.6, z: 1.0, confidence: 0.8),
        rightHip: BodyPoint(x: 0.65, y: 0.6, z: 1.0, confidence: 0.8),
      );

      expect(poseFrente.hasTorso, isTrue);
      // Yaw debe ser cercano a 0 (dz = 0)
      expect(poseFrente.torsoYawAngle, closeTo(0.0, 0.01));
      expect(poseFrente.torsoPitchAngle, closeTo(0.0, 0.01));
      expect(poseFrente.torsoDepthZ, closeTo(1.0, 0.01));

      // Persona girando el torso hacia la derecha (hombro derecho retrocede en Z)
      const posePerfil = BodyPose(
        leftShoulder: BodyPoint(x: 0.3, y: 0.2, z: 0.8, confidence: 0.8),
        rightShoulder: BodyPoint(x: 0.6, y: 0.2, z: 1.3, confidence: 0.8),
        leftHip: BodyPoint(x: 0.35, y: 0.6, z: 0.85, confidence: 0.8),
        rightHip: BodyPoint(x: 0.55, y: 0.6, z: 1.25, confidence: 0.8),
      );

      expect(posePerfil.torsoYawAngle, greaterThan(0.5)); // Ángulo positivo de rotación Y
      expect(posePerfil.torsoDepthZ, greaterThan(1.0));
    });
  });
}
