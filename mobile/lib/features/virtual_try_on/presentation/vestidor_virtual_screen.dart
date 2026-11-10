import 'dart:io';
import 'dart:ui';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../theme/app_theme.dart';
import '../data/virtual_try_on_repository.dart';
import '../domain/garment_transformer.dart';
import '../domain/pose_processor.dart';
import '../models/body_pose_model.dart';
import '../models/garment_model.dart';
import 'camera_view.dart';
import 'garment_overlay.dart';
import 'garment_selector.dart';
import 'garment_size_selector.dart';
import 'pose_skeleton_painter.dart';
import 'visor_3d_widget.dart';

enum VestidorStatus {
  initializing,
  detecting,
  bodyDetected,
  noBody,
  loadingGarments,
  error,
}

enum ModoVestidor {
  enVivoCamara,
  visor3d,
}

/// Pantalla principal del Vestidor Virtual Híbrido: En Vivo con Cámara + Visor 3D y ARCore
class VestidorVirtualScreen extends StatefulWidget {
  final GarmentModel? initialGarment;
  final int? initialProductoId;
  final bool openDirectTo3D;

  const VestidorVirtualScreen({
    super.key,
    this.initialGarment,
    this.initialProductoId,
    this.openDirectTo3D = false,
  });

  @override
  State<VestidorVirtualScreen> createState() => _VestidorVirtualScreenState();
}

class _VestidorVirtualScreenState extends State<VestidorVirtualScreen>
    with WidgetsBindingObserver {
  final VirtualTryOnRepository _repository = VirtualTryOnRepository();
  final PoseProcessor _poseProcessor = PoseProcessor();
  final GarmentTransformer _transformer = GarmentTransformer();

  List<CameraDescription> _availableCameras = [];
  CameraController? _cameraController;
  int _selectedCameraIndex = 0;

  List<GarmentModel> _garments = [];
  GarmentModel? _selectedGarment;

  VestidorStatus _status = VestidorStatus.initializing;
  ModoVestidor _modo = ModoVestidor.enVivoCamara;
  String? _errorMessage;

  BodyPose? _currentBodyPose;
  GarmentTransform _currentTransform = GarmentTransform.hidden;
  String _selectedSize = 'M';
  bool _showSkeleton = false;
  bool _isStreaming = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _selectedGarment = widget.initialGarment;
    if (widget.openDirectTo3D) {
      _modo = ModoVestidor.visor3d;
    }
    _initialize();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final CameraController? controller = _cameraController;
    if (controller == null || !controller.value.isInitialized) return;

    if (state == AppLifecycleState.inactive) {
      _stopStreaming();
      controller.dispose();
    } else if (state == AppLifecycleState.resumed) {
      _initCamera(_availableCameras[_selectedCameraIndex]);
    }
  }

  Future<void> _initialize() async {
    setState(() => _status = VestidorStatus.initializing);
    try {
      // 1. Obtener cámaras disponibles
      _availableCameras = await availableCameras();
      if (_availableCameras.isEmpty) {
        setState(() {
          _status = VestidorStatus.error;
          _errorMessage = 'No se encontraron cámaras disponibles en el dispositivo.';
        });
        return;
      }

      // Priorizar cámara frontal por ser vestidor virtual
      int frontIndex = _availableCameras.indexWhere(
        (c) => c.lensDirection == CameraLensDirection.front,
      );
      _selectedCameraIndex = frontIndex != -1 ? frontIndex : 0;

      // 2. Cargar catálogo de prendas compatibles en paralelo
      _loadGarments();

      // 3. Inicializar la cámara
      await _initCamera(_availableCameras[_selectedCameraIndex]);
    } catch (e) {
      setState(() {
        _status = VestidorStatus.error;
        _errorMessage = 'Error al inicializar vestidor: $e';
      });
    }
  }

  Future<void> _loadGarments() async {
    try {
      final list = await _repository.getPrendasCompatibles();
      if (!mounted) return;

      setState(() {
        _garments = list;
        // Si no se pasó prenda inicial, seleccionar la primera disponible
        if (_selectedGarment == null && _garments.isNotEmpty) {
          _selectedGarment = _garments.first;
        }
      });

      // Si se pasó un idProducto pero no el modelo completo
      if (_selectedGarment == null && widget.initialProductoId != null) {
        final initial = await _repository.getProductoVestidor(widget.initialProductoId!);
        if (mounted && initial != null) {
          setState(() => _selectedGarment = initial);
        }
      }
    } catch (e) {
      debugPrint('[Vestidor] Error al cargar prendas: $e');
    }
  }

  Future<void> _initCamera(CameraDescription camera) async {
    if (_cameraController != null) {
      await _stopStreaming();
      await _cameraController!.dispose();
      _cameraController = null;
    }

    final controller = CameraController(
      camera,
      ResolutionPreset.medium, // 480p / 720p óptimo para ML Kit Pose a 30fps
      enableAudio: false,
      imageFormatGroup: Platform.isAndroid ? ImageFormatGroup.nv21 : ImageFormatGroup.bgra8888,
    );

    _cameraController = controller;

    try {
      await controller.initialize();
      if (!mounted) return;

      setState(() {
        _status = VestidorStatus.detecting;
      });

      await _startStreaming();
    } catch (e) {
      if (mounted) {
        setState(() {
          _status = VestidorStatus.error;
          _errorMessage = 'No se pudo acceder a la cámara: $e';
        });
      }
    }
  }

  Future<void> _startStreaming() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) return;
    if (_isStreaming) return;

    _isStreaming = true;
    _cameraController!.startImageStream((CameraImage image) {
      _processFrame(image);
    });
  }

  Future<void> _stopStreaming() async {
    if (_cameraController != null &&
        _cameraController!.value.isInitialized &&
        _isStreaming) {
      try {
        await _cameraController!.stopImageStream();
      } catch (_) {}
      _isStreaming = false;
    }
  }

  void _processFrame(CameraImage image) async {
    if (!mounted || _selectedGarment == null) return;

    final currentCam = _availableCameras[_selectedCameraIndex];
    final isFront = currentCam.lensDirection == CameraLensDirection.front;

    final bodyPose = await _poseProcessor.processCameraImage(
      image: image,
      camera: currentCam,
    );

    if (bodyPose == null || !mounted) return;

    final screenSize = MediaQuery.of(context).size;
    final cameraAspect = _cameraController?.value.aspectRatio;
    final sizeScale = GarmentSizeSelector.sizeScales[_selectedSize] ?? 1.0;

    final transform = _transformer.computeTransform(
      pose: bodyPose,
      garment: _selectedGarment!,
      screenSize: screenSize,
      cameraAspectRatio: cameraAspect,
      sizeScale: sizeScale,
      isFrontCamera: isFront,
    );

    if (mounted) {
      setState(() {
        _currentBodyPose = bodyPose;
        _currentTransform = transform;
        if (transform.visible) {
          _status = VestidorStatus.bodyDetected;
        } else {
          _status = VestidorStatus.noBody;
        }
      });
    }
  }

  void _switchCamera() async {
    if (_availableCameras.length < 2) return;

    setState(() {
      _status = VestidorStatus.initializing;
      _currentTransform = GarmentTransform.hidden;
      _selectedCameraIndex = (_selectedCameraIndex + 1) % _availableCameras.length;
    });

    _transformer.reset();
    await _initCamera(_availableCameras[_selectedCameraIndex]);
  }

  void _onGarmentSelected(GarmentModel garment) {
    setState(() {
      _selectedGarment = garment;
      if (!garment.tallasDisponibles.contains(_selectedSize)) {
        if (garment.tallasDisponibles.contains('M')) {
          _selectedSize = 'M';
        } else if (garment.tallasDisponibles.isNotEmpty) {
          _selectedSize = garment.tallasDisponibles.first;
        }
      }
      _transformer.reset();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _stopStreaming();
    _cameraController?.dispose();
    _poseProcessor.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final mediaQuery = MediaQuery.of(context);
    final screenSize = mediaQuery.size;
    final cameraAspect = _cameraController?.value.aspectRatio;

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // MODO 1: En Vivo con Cámara y tracking de silueta/brazos en tiempo real
          if (_modo == ModoVestidor.enVivoCamara) ...[
            CameraView(controller: _cameraController),
            CustomPaint(
              painter: PoseSkeletonPainter(
                pose: _currentBodyPose,
                screenSize: screenSize,
                cameraAspectRatio: cameraAspect,
                quadPoints: _currentTransform.quadPoints,
                isVisible: _showSkeleton,
              ),
            ),
            GarmentOverlay(
              garment: _selectedGarment,
              transform: _currentTransform,
            ),
          ] else if (_selectedGarment != null) ...[
            // MODO 2: Visor 3D Interactivo 360° y Proyección ARCore (Google SceneViewer)
            Visor3dWidget(
              garment: _selectedGarment!,
            ),
          ],

          // Barra superior con Selector Híbrido [ En Vivo | Visor 3D & AR ] y Controles
          SafeArea(
            child: Align(
              alignment: Alignment.topCenter,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Botón volver
                    _buildGlassIconButton(
                      icon: Icons.arrow_back_ios_new_rounded,
                      onTap: () => Navigator.of(context).pop(),
                    ),

                    // Selector Híbrido de Modo: En Vivo vs Visor 3D AR
                    _buildModeSelector(),

                    // Controles contextuales según el modo
                    if (_modo == ModoVestidor.enVivoCamara)
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          _buildGlassIconButton(
                            icon: _showSkeleton
                                ? Icons.accessibility_new_rounded
                                : Icons.accessibility_outlined,
                            color: _showSkeleton
                                ? const Color(0xFFF59E0B)
                                : Colors.white,
                            tooltip: 'Alternar esqueleto',
                            onTap: () {
                              setState(() {
                                _showSkeleton = !_showSkeleton;
                              });
                            },
                          ),
                          const SizedBox(width: 8),
                          _buildGlassIconButton(
                            icon: Icons.flip_camera_ios_rounded,
                            onTap: _availableCameras.length > 1 ? _switchCamera : null,
                          ),
                        ],
                      )
                    else
                      _buildStatusBadge(),
                  ],
                ),
              ),
            ),
          ),

          // 5. Selector inferior de Talla (según disponibilidad de la prenda) + Carrusel de Prendas
          SafeArea(
            top: false,
            child: Align(
              alignment: Alignment.bottomCenter,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Selector de Talla con ajuste de proporciones
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: GarmentSizeSelector(
                      selectedSize: _selectedSize,
                      sizes: _selectedGarment?.tallasDisponibles ?? const ['S', 'M', 'L'],
                      onSizeSelected: (newSize) {
                        setState(() {
                          _selectedSize = newSize;
                        });
                      },
                    ),
                  ),

                  // Carrusel de Prendas
                  GarmentSelector(
                    garments: _garments,
                    selectedGarment: _selectedGarment,
                    onGarmentSelected: _onGarmentSelected,
                  ),
                ],
              ),
            ),
          ),

          // 6. Mensaje de error si falla la cámara
          if (_status == VestidorStatus.error)
            Container(
              color: Colors.black87,
              padding: const EdgeInsets.all(24),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.error_outline_rounded,
                      color: Color(0xFFEF4444),
                      size: 48,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      _errorMessage ?? 'Ocurrió un error inesperado.',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontFamily: 'Inter',
                      ),
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: Colors.black,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                      onPressed: _initialize,
                      child: const Text('Reintentar'),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildModeSelector() {
    return ClipRRect(
      borderRadius: BorderRadius.circular(24),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          padding: const EdgeInsets.all(3),
          decoration: BoxDecoration(
            color: Colors.black.withValues(alpha: 0.55),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.18),
              width: 1,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildModeTab(
                label: 'En Vivo',
                icon: Icons.videocam_rounded,
                isSelected: _modo == ModoVestidor.enVivoCamara,
                onTap: () {
                  if (_modo != ModoVestidor.enVivoCamara) {
                    setState(() => _modo = ModoVestidor.enVivoCamara);
                    _startStreaming();
                  }
                },
              ),
              const SizedBox(width: 4),
              _buildModeTab(
                label: '3D & AR',
                icon: Icons.view_in_ar_rounded,
                isSelected: _modo == ModoVestidor.visor3d,
                onTap: () {
                  if (_modo != ModoVestidor.visor3d) {
                    setState(() => _modo = ModoVestidor.visor3d);
                    _stopStreaming();
                  }
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildModeTab({
    required String label,
    required IconData icon,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(20),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primaryGold : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 14,
              color: isSelected ? const Color(0xFF0F1117) : Colors.white70,
            ),
            const SizedBox(width: 5),
            Text(
              label,
              style: GoogleFonts.plusJakartaSans(
                fontSize: 11,
                fontWeight: isSelected ? FontWeight.w700 : FontWeight.w600,
                color: isSelected ? const Color(0xFF0F1117) : Colors.white70,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGlassIconButton({
    required IconData icon,
    required VoidCallback? onTap,
    Color color = Colors.white,
    String? tooltip,
  }) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(30),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.black.withValues(alpha: 0.45),
            shape: BoxShape.circle,
            border: Border.all(
              color: color == Colors.white
                  ? Colors.white.withValues(alpha: 0.2)
                  : color.withValues(alpha: 0.6),
              width: 1,
            ),
          ),
          child: IconButton(
            icon: Icon(icon, color: color, size: 20),
            tooltip: tooltip,
            onPressed: onTap,
          ),
        ),
      ),
    );
  }

  Widget _buildStatusBadge() {
    String text;
    Color dotColor;

    if (_modo == ModoVestidor.visor3d) {
      text = '3D 360° • ${_selectedGarment?.nombre ?? "Prenda"}';
      dotColor = AppTheme.primaryGold;
    } else {
      switch (_status) {
        case VestidorStatus.initializing:
          text = 'Preparando vestidor...';
          dotColor = const Color(0xFFF59E0B);
          break;
        case VestidorStatus.detecting:
          text = 'Detectando cuerpo...';
          dotColor = const Color(0xFF3B82F6);
          break;
        case VestidorStatus.bodyDetected:
          if (_currentBodyPose != null && _currentBodyPose!.hasArms) {
            text = 'Brazos y Torso ✓ (Talla $_selectedSize)';
            dotColor = const Color(0xFF10B981);
          } else if (_selectedGarment != null) {
            text = 'Talla $_selectedSize • ${_selectedGarment!.nombre}';
            dotColor = const Color(0xFF10B981);
          } else {
            text = 'Cuerpo detectado (Talla $_selectedSize)';
            dotColor = const Color(0xFF10B981);
          }
          break;
        case VestidorStatus.noBody:
          text = 'Párate frente a la cámara';
          dotColor = const Color(0xFFF59E0B);
          break;
        case VestidorStatus.loadingGarments:
          text = 'Cargando prendas...';
          dotColor = const Color(0xFF8B5CF6);
          break;
        case VestidorStatus.error:
          text = 'Error en vestidor';
          dotColor = const Color(0xFFEF4444);
          break;
      }
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
          decoration: BoxDecoration(
            color: Colors.black.withValues(alpha: 0.45),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.15),
              width: 1,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 7,
                height: 7,
                decoration: BoxDecoration(
                  color: dotColor,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: dotColor.withValues(alpha: 0.7),
                      blurRadius: 6,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 160),
                child: Text(
                  text,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    fontFamily: 'Inter',
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
