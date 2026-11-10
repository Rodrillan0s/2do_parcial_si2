import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';
import '../features/virtual_try_on/models/garment_model.dart';
import '../features/virtual_try_on/presentation/vestidor_virtual_screen.dart';
import '../services/auth_provider.dart';
import '../services/carrito_service.dart';
import '../services/catalogo_service.dart';
import '../services/valoracion_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_badge.dart';
import '../widgets/aurora_button.dart';
import '../widgets/auth_dialog_helper.dart';
import 'crear_reserva_modal.dart';

class DetalleProductoScreen extends StatefulWidget {
  final int idProducto;

  const DetalleProductoScreen({super.key, required this.idProducto});

  @override
  State<DetalleProductoScreen> createState() => _DetalleProductoScreenState();
}

class _DetalleProductoScreenState extends State<DetalleProductoScreen> {
  DetallePrendaModel? _prenda;
  ResumenValoracionesProductoModel? _resumenValoraciones;
  bool _cargando = true;
  String? _error;

  int _imagenActualIndex = 0;
  final PageController _pageController = PageController();

  int? _tallaSeleccionadaId;
  int? _colorSeleccionadoId;
  VarianteModel? _varianteSeleccionada;

  // Disponibilidad por sucursal
  List<DisponibilidadSucursalModel> _disponibilidadSucursales = [];
  bool _cargandoDisponibilidad = false;

  bool _agregandoAlCarrito = false;

  @override
  void initState() {
    super.initState();
    _cargarDetalle();
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  Future<void> _cargarDetalle() async {
    setState(() {
      _cargando = true;
      _error = null;
    });

    final catalogo = context.read<CatalogoService>();

    try {
      final p = await catalogo.obtenerDetalleProducto(widget.idProducto);
      if (mounted) {
        setState(() {
          _prenda = p;
          _cargando = false;

          // Preseleccionar primera variante disponible
          if (p.variantes.isNotEmpty) {
            _varianteSeleccionada = p.variantes.first;
            _tallaSeleccionadaId = _varianteSeleccionada!.idTalla;
            _colorSeleccionadoId = _varianteSeleccionada!.idColor;
          }
        });

        if (_varianteSeleccionada != null) {
          _consultarDisponibilidad(_varianteSeleccionada!.idVariante);
        }

        ValoracionService().obtenerResumenProducto(widget.idProducto).then((res) {
          if (mounted) setState(() => _resumenValoraciones = res);
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString().replaceAll('Exception: ', '');
          _cargando = false;
        });
      }
    }
  }

  void _actualizarVarianteSeleccionada(int? tallaId, int? colorId) {
    if (_prenda == null) return;

    _tallaSeleccionadaId = tallaId;
    _colorSeleccionadoId = colorId;

    // Buscar variante que coincida
    VarianteModel? match;
    for (final v in _prenda!.variantes) {
      final matchTalla = (tallaId == null || v.idTalla == tallaId);
      final matchColor = (colorId == null || v.idColor == colorId);
      if (matchTalla && matchColor) {
        match = v;
        break;
      }
    }

    // Fallback a primera si no coincide exacta
    match ??= _prenda!.variantes.isNotEmpty ? _prenda!.variantes.first : null;

    setState(() {
      _varianteSeleccionada = match;
    });

    if (match != null) {
      _consultarDisponibilidad(match.idVariante);
    }
  }

  Future<void> _consultarDisponibilidad(int idVariante) async {
    setState(() {
      _cargandoDisponibilidad = true;
    });

    final catalogo = context.read<CatalogoService>();
    final list = await catalogo.consultarDisponibilidadVariante(idVariante);

    if (mounted) {
      setState(() {
        _disponibilidadSucursales = list;
        _cargandoDisponibilidad = false;
      });
      if (catalogo.sucursalSeleccionada == null &&
          catalogo.sucursalPersistidaId != null) {
        for (final sucursal in list) {
          if (sucursal.idSucursal == catalogo.sucursalPersistidaId &&
              sucursal.disponible) {
            await catalogo.seleccionarSucursal(SucursalContextModel(
              idSucursal: sucursal.idSucursal,
              idEmpresa:
                  catalogo.tenantSeleccionado?.idEmpresa ?? _prenda!.idEmpresa,
              nombre: sucursal.nombre,
              direccion: sucursal.direccion,
            ));
            break;
          }
        }
      }
    }
  }

  Future<void> _agregarAlCarrito() async {
    final authProvider = context.read<AuthProvider>();
    if (!authProvider.estaAutenticado) {
      AuthDialogHelper.mostrarModalLoginRequerido(
        context,
        titulo: 'Inicia sesión para comprar',
        mensaje:
            'Para añadir prendas a tu bolsa de compras y sincronizar tus pedidos, ingresa con tu cuenta de Aurora Store.',
      );
      return;
    }

    if (_varianteSeleccionada == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Por favor selecciona una talla y color.')),
      );
      return;
    }

    setState(() {
      _agregandoAlCarrito = true;
    });

    final carrito = context.read<CarritoService>();
    try {
      final ok = await carrito.agregarItem(
        idVariante: _varianteSeleccionada!.idVariante,
        cantidad: 1,
        idEmpresa: _prenda?.idEmpresa,
      );

      if (mounted) {
        setState(() {
          _agregandoAlCarrito = false;
        });

        if (ok) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('${_prenda!.nombre} agregada a la bolsa.'),
              backgroundColor: AppTheme.success,
              action: SnackBarAction(
                label: 'Ver bolsa',
                textColor: Colors.white,
                onPressed: () {
                  Navigator.pop(context); // Regresa al shell
                },
              ),
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(carrito.error ?? 'No se pudo agregar a la bolsa.'),
              backgroundColor: AppTheme.error,
            ),
          );
        }
      }
    } on DifferentStoreCartException catch (e) {
      if (!mounted) return;
      setState(() {
        _agregandoAlCarrito = false;
      });

      final comenzarNueva = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(
            'Bolsa en otra tienda',
            style: GoogleFonts.playfairDisplay(fontSize: 18, fontWeight: FontWeight.w700),
          ),
          content: Text(
            'Tu bolsa actual contiene prendas de ${e.existingTenantName}.\n\n¿Deseas iniciar una nueva bolsa para esta tienda o prefieres conservar tus prendas anteriores?',
            style: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textSecondary),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Conservar anterior'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primary),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Comenzar nueva bolsa'),
            ),
          ],
        ),
      );

      if (comenzarNueva == true && mounted) {
        await carrito.vaciarCarrito(idEmpresa: e.existingTenantId);
        final ok = await carrito.agregarItem(
          idVariante: _varianteSeleccionada!.idVariante,
          cantidad: 1,
          idEmpresa: e.newTenantId,
        );
        if (ok && mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('${_prenda!.nombre} agregada a la nueva bolsa.'),
              backgroundColor: AppTheme.success,
            ),
          );
        }
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _agregandoAlCarrito = false;
        });
      }
    }
  }

  void _abrirModalReserva() {
    final authProvider = context.read<AuthProvider>();
    if (!authProvider.estaAutenticado) {
      AuthDialogHelper.mostrarModalLoginRequerido(
        context,
        titulo: 'Inicia sesión para reservar',
        mensaje:
            'Para agendar una cita privada en nuestras sucursales exclusivas, por favor identifícate con tu cuenta de Aurora Store.',
      );
      return;
    }

    if (_prenda == null || _varianteSeleccionada == null) return;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => CrearReservaModal(
        prenda: _prenda!,
        varianteSeleccionada: _varianteSeleccionada!,
      ),
    );
  }

  Future<void> _abrirVestidorVirtual({bool directTo3D = false}) async {
    if (_prenda == null) return;

    if (!directTo3D) {
      final status = await Permission.camera.request();
      if (!mounted) return;

      if (!status.isGranted && !status.isLimited) {
        // Si la cámara no tiene permiso, abrimos directamente en Visor 3D
        directTo3D = true;
      }
    }

    final garment = GarmentModel(
      idProducto: _prenda!.idProducto,
      nombre: _prenda!.nombre,
      modelo2dUrl: _prenda!.modelo2dUrl ?? _prenda!.imagenPrincipal ?? '',
      modelo3dUrl: _prenda!.modelo3dUrl,
      tipo: GarmentType.fromString(_prenda!.tipoPrendaRa),
      precio: _prenda!.precio,
      imagenPreview: _prenda!.imagenPrincipal,
    );

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => VestidorVirtualScreen(
          initialGarment: garment,
          initialProductoId: _prenda!.idProducto,
          openDirectTo3D: directTo3D,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final currencyFormatter = NumberFormat.currency(
      locale: 'es_BO',
      symbol: 'Bs. ',
      decimalDigits: 2,
    );

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Text(
          _prenda?.nombre ?? 'Detalle de la Prenda',
          style: GoogleFonts.playfairDisplay(
              fontSize: 18, fontWeight: FontWeight.w700),
        ),
      ),
      body: _cargando
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(_error!),
                      const SizedBox(height: 12),
                      AuroraButton(
                        text: 'Reintentar',
                        width: 140,
                        onPressed: _cargarDetalle,
                      ),
                    ],
                  ),
                )
              : Column(
                  children: [
                    Expanded(
                      child: SingleChildScrollView(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Carrusel de Imágenes
                            SizedBox(
                              height: 380,
                              child: Stack(
                                children: [
                                  PageView.builder(
                                    controller: _pageController,
                                    itemCount: _prenda!.imagenes.isNotEmpty
                                        ? _prenda!.imagenes.length
                                        : 1,
                                    onPageChanged: (index) {
                                      setState(() {
                                        _imagenActualIndex = index;
                                      });
                                    },
                                    itemBuilder: (context, index) {
                                      final url = _prenda!.imagenes.isNotEmpty
                                          ? _prenda!.imagenes[index]
                                          : _prenda!.imagenPrincipal;

                                      if (url != null && url.isNotEmpty) {
                                        return Image.network(
                                          url,
                                          fit: BoxFit.cover,
                                          errorBuilder: (_, __, ___) =>
                                              const Center(
                                            child: Icon(Icons.checkroom,
                                                size: 64,
                                                color: AppTheme.textMuted),
                                          ),
                                        );
                                      }
                                      return const Center(
                                        child: Icon(Icons.checkroom,
                                            size: 64,
                                            color: AppTheme.textMuted),
                                      );
                                    },
                                  ),
                                  // Indicador de Puntos
                                  if (_prenda!.imagenes.length > 1)
                                    Positioned(
                                      bottom: 16,
                                      left: 0,
                                      right: 0,
                                      child: Row(
                                        mainAxisAlignment:
                                            MainAxisAlignment.center,
                                        children: List.generate(
                                          _prenda!.imagenes.length,
                                          (index) => Container(
                                            margin: const EdgeInsets.symmetric(
                                                horizontal: 3),
                                            width: _imagenActualIndex == index
                                                ? 18
                                                : 6,
                                            height: 6,
                                            decoration: BoxDecoration(
                                              color: _imagenActualIndex == index
                                                  ? AppTheme.primary
                                                  : Colors.black26,
                                              borderRadius:
                                                  BorderRadius.circular(3),
                                            ),
                                          ),
                                        ),
                                      ),
                                    ),
                                ],
                              ),
                            ),

                            Padding(
                              padding: const EdgeInsets.all(20),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  // Marca y Categoría
                                  Row(
                                    mainAxisAlignment:
                                        MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(
                                        _prenda!.marca.toUpperCase(),
                                        style: GoogleFonts.plusJakartaSans(
                                          fontSize: 11,
                                          fontWeight: FontWeight.w700,
                                          color: AppTheme.primaryGold,
                                          letterSpacing: 1.5,
                                        ),
                                      ),
                                      Row(
                                        children: [
                                          if (_prenda!.tieneRa) ...[
                                            const AuroraBadge(
                                              text: 'AR VESTIDOR',
                                              backgroundColor:
                                                  Color(0xFFFEF3C7),
                                              textColor: Color(0xFFB45309),
                                              isSmall: true,
                                            ),
                                            const SizedBox(width: 6),
                                          ],
                                          AuroraBadge(
                                            text: _prenda!.categoriaNombre,
                                            isSmall: true,
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 6),

                                  // Nombre de la prenda
                                  Text(
                                    _prenda!.nombre,
                                    style: GoogleFonts.playfairDisplay(
                                      fontSize: 22,
                                      fontWeight: FontWeight.w700,
                                      color: AppTheme.textPrimary,
                                      height: 1.2,
                                    ),
                                  ),
                                  if (_resumenValoraciones != null && _resumenValoraciones!.total > 0) ...[
                                    const SizedBox(height: 6),
                                    Row(
                                      children: [
                                        Row(
                                          children: List.generate(5, (i) {
                                            final isFull = (i + 1) <= _resumenValoraciones!.promedio;
                                            return Icon(
                                              isFull ? Icons.star_rounded : Icons.star_outline_rounded,
                                              size: 16,
                                              color: const Color(0xFFF59E0B),
                                            );
                                          }),
                                        ),
                                        const SizedBox(width: 6),
                                        Text(
                                          _resumenValoraciones!.promedio.toStringAsFixed(1),
                                          style: GoogleFonts.plusJakartaSans(
                                            fontSize: 12,
                                            fontWeight: FontWeight.w700,
                                            color: AppTheme.textPrimary,
                                          ),
                                        ),
                                        const SizedBox(width: 4),
                                        Text(
                                          '(${_resumenValoraciones!.total} ${_resumenValoraciones!.total == 1 ? 'opinión' : 'opiniones'})',
                                          style: GoogleFonts.plusJakartaSans(
                                            fontSize: 11,
                                            color: AppTheme.textMuted,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                  const SizedBox(height: 8),

                                  // Precio y Estado de Disponibilidad
                                  Row(
                                    children: [
                                      Text(
                                        currencyFormatter.format(_prenda!.precio),
                                        style: GoogleFonts.plusJakartaSans(
                                          fontSize: 20,
                                          fontWeight: FontWeight.w800,
                                          color: AppTheme.textPrimary,
                                        ),
                                      ),
                                      const SizedBox(width: 12),
                                      AuroraBadge(
                                        text: _prenda!.stockTotalGeneral <= 0
                                            ? 'Agotado'
                                            : _prenda!.stockTotalGeneral <= 3
                                                ? '⚠ Últimas unidades'
                                                : '✓ Disponible',
                                        backgroundColor: _prenda!.stockTotalGeneral <= 0
                                            ? AppTheme.errorLight
                                            : _prenda!.stockTotalGeneral <= 3
                                                ? AppTheme.goldLight
                                                : AppTheme.successLight,
                                        textColor: _prenda!.stockTotalGeneral <= 0
                                            ? AppTheme.error
                                            : _prenda!.stockTotalGeneral <= 3
                                                ? AppTheme.primaryGold
                                                : AppTheme.success,
                                        isSmall: true,
                                      ),
                                    ],
                                  ),

                                  // Botones de Realidad Aumentada Híbrida (En Vivo + 3D ARCore)
                                  if (_prenda!.tieneRa) ...[
                                    const SizedBox(height: 14),
                                    Row(
                                      children: [
                                        // Opción 1: Probar en Cámara En Vivo
                                        Expanded(
                                          child: InkWell(
                                            onTap: () => _abrirVestidorVirtual(directTo3D: false),
                                            borderRadius: BorderRadius.circular(12),
                                            child: Container(
                                              padding: const EdgeInsets.symmetric(vertical: 11, horizontal: 10),
                                              decoration: BoxDecoration(
                                                color: const Color(0xFF09090B),
                                                borderRadius: BorderRadius.circular(12),
                                                border: Border.all(color: const Color(0xFFB45309), width: 1.1),
                                              ),
                                              child: Row(
                                                mainAxisAlignment: MainAxisAlignment.center,
                                                children: [
                                                  const Icon(Icons.videocam_rounded, color: Color(0xFFF59E0B), size: 17),
                                                  const SizedBox(width: 6),
                                                  Flexible(
                                                    child: Text(
                                                      'Probar En Vivo',
                                                      style: GoogleFonts.plusJakartaSans(
                                                        color: Colors.white,
                                                        fontSize: 12,
                                                        fontWeight: FontWeight.w700,
                                                      ),
                                                    ),
                                                  ),
                                                ],
                                              ),
                                            ),
                                          ),
                                        ),
                                        const SizedBox(width: 10),

                                        // Opción 2: Visor 3D 360° & ARCore
                                        Expanded(
                                          child: InkWell(
                                            onTap: () => _abrirVestidorVirtual(directTo3D: true),
                                            borderRadius: BorderRadius.circular(12),
                                            child: Container(
                                              padding: const EdgeInsets.symmetric(vertical: 11, horizontal: 10),
                                              decoration: BoxDecoration(
                                                color: const Color(0xFF131722),
                                                borderRadius: BorderRadius.circular(12),
                                                border: Border.all(color: AppTheme.primaryGold, width: 1.1),
                                              ),
                                              child: Row(
                                                mainAxisAlignment: MainAxisAlignment.center,
                                                children: [
                                                  const Icon(Icons.view_in_ar_rounded, color: AppTheme.primaryGold, size: 17),
                                                  const SizedBox(width: 6),
                                                  Flexible(
                                                    child: Text(
                                                      'Modelo 3D & AR',
                                                      style: GoogleFonts.plusJakartaSans(
                                                        color: AppTheme.primaryGold,
                                                        fontSize: 12,
                                                        fontWeight: FontWeight.w700,
                                                      ),
                                                    ),
                                                  ),
                                                ],
                                              ),
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],

                                  const Divider(height: 28),

                                  // Selector de Tallas
                                  if (_prenda!.tallas.isNotEmpty) ...[
                                    Text(
                                      'Selecciona tu Talla',
                                      style: GoogleFonts.plusJakartaSans(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                    const SizedBox(height: 10),
                                    Wrap(
                                      spacing: 8,
                                      children: _prenda!.tallas.map((t) {
                                        final idTalla = t['id_talla'] as int;
                                        final nombreTalla =
                                            t['nombre'].toString();
                                        final isSelected =
                                            _tallaSeleccionadaId == idTalla;

                                        return ChoiceChip(
                                          label: Text(nombreTalla),
                                          selected: isSelected,
                                          onSelected: (_) =>
                                              _actualizarVarianteSeleccionada(
                                                  idTalla,
                                                  _colorSeleccionadoId),
                                          selectedColor: AppTheme.primary,
                                          backgroundColor: AppTheme.surface,
                                          labelStyle:
                                              GoogleFonts.plusJakartaSans(
                                            fontSize: 13,
                                            fontWeight: FontWeight.w600,
                                            color: isSelected
                                                ? Colors.white
                                                : AppTheme.textPrimary,
                                          ),
                                          side: BorderSide(
                                            color: isSelected
                                                ? AppTheme.primary
                                                : AppTheme.borderStrong,
                                          ),
                                        );
                                      }).toList(),
                                    ),
                                    const SizedBox(height: 20),
                                  ],

                                  // Selector de Colores
                                  if (_prenda!.colores.isNotEmpty) ...[
                                    Text(
                                      'Selecciona el Color',
                                      style: GoogleFonts.plusJakartaSans(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                    const SizedBox(height: 10),
                                    Wrap(
                                      spacing: 12,
                                      children: _prenda!.colores.map((c) {
                                        final idColor = c['id_color'] as int;
                                        final nombreColor =
                                            c['nombre'].toString();
                                        final hex =
                                            (c['codigo_hex'] ?? '#000000')
                                                .toString()
                                                .replaceAll('#', '');
                                        final colorVal =
                                            int.tryParse('FF$hex', radix: 16) ??
                                                0xFF000000;
                                        final isSelected =
                                            _colorSeleccionadoId == idColor;

                                        return InkWell(
                                          onTap: () =>
                                              _actualizarVarianteSeleccionada(
                                                  _tallaSeleccionadaId,
                                                  idColor),
                                          borderRadius:
                                              BorderRadius.circular(24),
                                          child: Container(
                                            padding: const EdgeInsets.symmetric(
                                                horizontal: 12, vertical: 6),
                                            decoration: BoxDecoration(
                                              color: isSelected
                                                  ? AppTheme.goldLight
                                                  : AppTheme.surfaceVariant,
                                              borderRadius:
                                                  BorderRadius.circular(20),
                                              border: Border.all(
                                                color: isSelected
                                                    ? AppTheme.primaryGold
                                                    : AppTheme.border,
                                                width: isSelected ? 1.5 : 1,
                                              ),
                                            ),
                                            child: Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                Container(
                                                  width: 16,
                                                  height: 16,
                                                  decoration: BoxDecoration(
                                                    color: Color(colorVal),
                                                    shape: BoxShape.circle,
                                                    border: Border.all(
                                                        color: Colors.black12),
                                                  ),
                                                ),
                                                const SizedBox(width: 8),
                                                Text(
                                                  nombreColor,
                                                  style: GoogleFonts
                                                      .plusJakartaSans(
                                                    fontSize: 12,
                                                    fontWeight: isSelected
                                                        ? FontWeight.w600
                                                        : FontWeight.w500,
                                                    color: isSelected
                                                        ? AppTheme.primaryGold
                                                        : AppTheme.textPrimary,
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                        );
                                      }).toList(),
                                    ),
                                    const SizedBox(height: 24),
                                  ],

                                  // Disponibilidad por Sucursal Física (M07)
                                  Container(
                                    padding: const EdgeInsets.all(16),
                                    decoration: BoxDecoration(
                                      color: AppTheme.surface,
                                      borderRadius: BorderRadius.circular(16),
                                      border:
                                          Border.all(color: AppTheme.border),
                                    ),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            const Icon(Icons.storefront,
                                                size: 20,
                                                color: AppTheme.primaryGold),
                                            const SizedBox(width: 8),
                                            Text(
                                              'Disponibilidad en Sucursales',
                                              style:
                                                  GoogleFonts.playfairDisplay(
                                                fontSize: 16,
                                                fontWeight: FontWeight.w700,
                                              ),
                                            ),
                                          ],
                                        ),
                                        const SizedBox(height: 12),
                                        if (_cargandoDisponibilidad)
                                          const Center(
                                            child: Padding(
                                              padding: EdgeInsets.all(12),
                                              child: CircularProgressIndicator(
                                                  strokeWidth: 2),
                                            ),
                                          )
                                        else if (_disponibilidadSucursales
                                            .isEmpty)
                                          Text(
                                            'Selecciona una talla y color para verificar tiendas con stock físico.',
                                            style: GoogleFonts.plusJakartaSans(
                                                fontSize: 12,
                                                color: AppTheme.textMuted),
                                          )
                                        else
                                          ..._disponibilidadSucursales
                                              .map((suc) {
                                            final catalogo =
                                                context.read<CatalogoService>();
                                            final seleccionada = catalogo
                                                    .sucursalSeleccionada
                                                    ?.idSucursal ==
                                                suc.idSucursal;
                                            return Padding(
                                              padding:
                                                  const EdgeInsets.symmetric(
                                                      vertical: 6),
                                              child: InkWell(
                                                borderRadius:
                                                    BorderRadius.circular(12),
                                                onTap: suc.disponible
                                                    ? () =>
                                                        catalogo.seleccionarSucursal(
                                                            SucursalContextModel(
                                                          idSucursal:
                                                              suc.idSucursal,
                                                          idEmpresa: catalogo
                                                                  .tenantSeleccionado
                                                                  ?.idEmpresa ??
                                                              _prenda!
                                                                  .idEmpresa,
                                                          nombre: suc.nombre,
                                                          direccion:
                                                              suc.direccion,
                                                        ))
                                                    : null,
                                                child: Padding(
                                                  padding:
                                                      const EdgeInsets.all(8),
                                                  child: Row(
                                                    mainAxisAlignment:
                                                        MainAxisAlignment
                                                            .spaceBetween,
                                                    children: [
                                                      Expanded(
                                                        child: Column(
                                                          crossAxisAlignment:
                                                              CrossAxisAlignment
                                                                  .start,
                                                          children: [
                                                            Row(
                                                              children: [
                                                                if (seleccionada)
                                                                  const Icon(
                                                                      Icons
                                                                          .check_circle,
                                                                      size: 16,
                                                                      color: AppTheme
                                                                          .primaryGold),
                                                                if (seleccionada)
                                                                  const SizedBox(
                                                                      width: 5),
                                                                Flexible(
                                                                  child: Text(
                                                                    suc.nombre,
                                                                    style: GoogleFonts
                                                                        .plusJakartaSans(
                                                                      fontSize:
                                                                          13,
                                                                      fontWeight:
                                                                          FontWeight
                                                                              .w600,
                                                                    ),
                                                                  ),
                                                                ),
                                                              ],
                                                            ),
                                                            Text(
                                                              suc.direccion,
                                                              style: GoogleFonts
                                                                  .plusJakartaSans(
                                                                fontSize: 11,
                                                                color: AppTheme
                                                                    .textMuted,
                                                              ),
                                                            ),
                                                          ],
                                                        ),
                                                      ),
                                                      AuroraBadge(
                                                        text: suc.stockDisponible <= 0
                                                            ? 'Agotado'
                                                            : suc.stockDisponible <= 3
                                                                ? '⚠ Últimas unidades'
                                                                : '✓ Disponible',
                                                        backgroundColor: suc.stockDisponible <= 0
                                                            ? AppTheme.errorLight
                                                            : suc.stockDisponible <= 3
                                                                ? AppTheme.goldLight
                                                                : AppTheme.successLight,
                                                        textColor: suc.stockDisponible <= 0
                                                            ? AppTheme.error
                                                            : suc.stockDisponible <= 3
                                                                ? AppTheme.primaryGold
                                                                : AppTheme.success,
                                                        isSmall: true,
                                                      ),
                                                    ],
                                                  ),
                                                ),
                                              ),
                                            );
                                          }),
                                      ],
                                    ),
                                  ),

                                  const SizedBox(height: 20),

                                  // Descripción de la prenda
                                  if (_prenda!.descripcion.isNotEmpty) ...[
                                    Text(
                                      'Descripción & Detalles',
                                      style: GoogleFonts.playfairDisplay(
                                        fontSize: 16,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                    const SizedBox(height: 8),
                                    Text(
                                      _prenda!.descripcion,
                                      style: GoogleFonts.plusJakartaSans(
                                        fontSize: 13,
                                        color: AppTheme.textSecondary,
                                        height: 1.5,
                                      ),
                                    ),
                                    const SizedBox(height: 20),
                                  ],
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),

                    // Barra Fija Inferior con Acciones
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: const BoxDecoration(
                        color: AppTheme.surface,
                        border: Border(top: BorderSide(color: AppTheme.border)),
                        boxShadow: [
                          BoxShadow(
                            color: Color(0x08000000),
                            blurRadius: 8,
                            offset: Offset(0, -2),
                          ),
                        ],
                      ),
                      child: SafeArea(
                        top: false,
                        child: Row(
                          children: [
                            // Botón Probar en Tienda / Agendar Cita
                            Expanded(
                              flex: 1,
                              child: AuroraButton(
                                text: 'Probar en tienda',
                                fontSize: 12,
                                variant: AuroraButtonVariant.outline,
                                icon: Icons.calendar_month_outlined,
                                onPressed: _abrirModalReserva,
                              ),
                            ),
                            const SizedBox(width: 10),
                            // Botón Agregar a la Bolsa
                            Expanded(
                              flex: 1,
                              child: AuroraButton(
                                text: _prenda!.stockTotalGeneral <= 0
                                    ? 'Agotado'
                                    : 'Añadir a la bolsa',
                                fontSize: 12,
                                variant: AuroraButtonVariant.primary,
                                icon: _prenda!.stockTotalGeneral <= 0
                                    ? Icons.remove_shopping_cart_outlined
                                    : Icons.shopping_bag_outlined,
                                isLoading: _agregandoAlCarrito,
                                onPressed: _prenda!.stockTotalGeneral <= 0
                                    ? null
                                    : _agregarAlCarrito,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }
}
