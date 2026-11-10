enum GarmentType {
  top,
  pant,
  dress;

  static GarmentType fromString(String? val) {
    switch (val?.toUpperCase()) {
      case 'PANT':
      case 'PANTS':
      case 'PANTALON':
        return GarmentType.pant;
      case 'DRESS':
      case 'VESTIDO':
        return GarmentType.dress;
      case 'TOP':
      case 'SHIRT':
      case 'CAMISETA':
      case 'BLUSA':
      default:
        return GarmentType.top;
    }
  }

  String get displayName {
    switch (this) {
      case GarmentType.top:
        return 'Superior';
      case GarmentType.pant:
        return 'Pantalón';
      case GarmentType.dress:
        return 'Vestido';
    }
  }
}

class GarmentModel {
  final int idProducto;
  final String nombre;
  final String modelo2dUrl;
  final String? modelo3dUrl;
  final GarmentType tipo;
  final double precio;
  final String? imagenPreview;
  final List<String> tallasDisponibles;

  const GarmentModel({
    required this.idProducto,
    required this.nombre,
    required this.modelo2dUrl,
    this.modelo3dUrl,
    required this.tipo,
    required this.precio,
    this.imagenPreview,
    this.tallasDisponibles = const ['S', 'M', 'L'],
  });

  /// Modelos 3D GLB públicos de alta costura y moda (Khronos / Three.js CC0)
  static String default3dModelForType(GarmentType tipo) {
    switch (tipo) {
      case GarmentType.top:
        return 'https://raw.githubusercontent.com/adrianhajdin/project_threejs_ai/main/client/public/shirt_baked.glb';
      case GarmentType.dress:
        return 'https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/Corset/glTF-Binary/Corset.glb';
      case GarmentType.pant:
        return 'https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/MaterialsVariantsShoe/glTF-Binary/MaterialsVariantsShoe.glb';
    }
  }

  factory GarmentModel.fromJson(Map<String, dynamic> json) {
    final rawTallas = json['tallas_disponibles'];
    List<String> tallas = const ['S', 'M', 'L'];
    if (rawTallas is List && rawTallas.isNotEmpty) {
      tallas = rawTallas
          .map((e) => e.toString().trim())
          .where((e) => e.isNotEmpty)
          .toList();
    }

    final tipo = GarmentType.fromString(json['tipo_prenda_ra']);
    final custom3d = json['modelo_3d_url'] ?? json['modelo_ar_url'];
    final url3d = (custom3d != null && custom3d.toString().isNotEmpty)
        ? custom3d.toString()
        : default3dModelForType(tipo);

    return GarmentModel(
      idProducto: json['id_producto'] ?? 0,
      nombre: json['nombre'] ?? '',
      modelo2dUrl: json['modelo_2d_url'] ?? json['imagen_preview'] ?? '',
      modelo3dUrl: url3d,
      tipo: tipo,
      precio: (json['precio'] != null)
          ? double.tryParse(json['precio'].toString()) ?? 0.0
          : 0.0,
      imagenPreview: json['imagen_preview'] ?? json['modelo_2d_url'],
      tallasDisponibles: tallas,
    );
  }
}
