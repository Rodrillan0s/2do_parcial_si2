import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../services/carrito_service.dart';
import '../services/pedido_service.dart';
import '../services/profile_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_badge.dart';
import '../widgets/aurora_button.dart';
import '../widgets/aurora_text_field.dart';
import 'pago_screen.dart';

class CheckoutScreen extends StatefulWidget {
  final CarritoModel carrito;

  const CheckoutScreen({super.key, required this.carrito});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final _formKey = GlobalKey<FormState>();

  List<SucursalCheckoutModel> _sucursales = [];
  SucursalCheckoutModel? _sucursalSeleccionada;
  String _modalidad = 'ENTREGA_DOMICILIO'; // 'ENTREGA_DOMICILIO' o 'RETIRO_SUCURSAL'

  String _filtroCiudad = 'TODAS';
  String _busquedaSucursal = '';
  final _busquedaSucursalCtrl = TextEditingController();

  final _nombreCtrl = TextEditingController();
  final _telefonoCtrl = TextEditingController();
  final _correoCtrl = TextEditingController();
  final _direccionCtrl = TextEditingController();
  final _ciudadCtrl = TextEditingController(text: 'La Paz');
  final _notasCtrl = TextEditingController();

  bool _cargandoSucursales = true;
  bool _procesando = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _cargarDatosIniciales();
  }

  @override
  void dispose() {
    _busquedaSucursalCtrl.dispose();
    _nombreCtrl.dispose();
    _telefonoCtrl.dispose();
    _correoCtrl.dispose();
    _direccionCtrl.dispose();
    _ciudadCtrl.dispose();
    _notasCtrl.dispose();
    super.dispose();
  }

  Future<void> _cargarDatosIniciales() async {
    final pedidoService = context.read<PedidoService>();
    final profileService = ProfileService();

    try {
      final sucursales = await pedidoService.obtenerSucursalesCheckout(
        idEmpresa: widget.carrito.idEmpresa,
      );

      final perfil = await profileService.obtenerPerfil();

      if (mounted) {
        setState(() {
          _sucursales = sucursales;
          final conStock = sucursales.where((s) => s.tieneStockCompleto).toList();
          _sucursalSeleccionada = conStock.isNotEmpty
              ? conStock.first
              : (sucursales.isNotEmpty ? sucursales.first : null);
          _nombreCtrl.text = '${perfil.nombre} ${perfil.apellido}'.trim();
          _correoCtrl.text = perfil.correo;
          _telefonoCtrl.text = perfil.telefono ?? '';
          _direccionCtrl.text = perfil.direccion ?? '';
          _ciudadCtrl.text = perfil.ciudad ?? 'La Paz';
          _cargandoSucursales = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _cargandoSucursales = false;
        });
      }
    }
  }

  List<SucursalCheckoutModel> get _sucursalesFiltradas {
    return _sucursales.where((s) {
      final coincideCiudad = _filtroCiudad == 'TODAS' ||
          s.ciudad.toLowerCase() == _filtroCiudad.toLowerCase();
      final query = _busquedaSucursal.toLowerCase().trim();
      final coincideBusqueda = query.isEmpty ||
          s.nombre.toLowerCase().contains(query) ||
          s.direccion.toLowerCase().contains(query) ||
          s.ciudad.toLowerCase().contains(query);
      return coincideCiudad && coincideBusqueda;
    }).toList();
  }

  List<String> get _ciudadesDisponibles {
    final setCiudades =
        _sucursales.map((s) => s.ciudad).where((c) => c.isNotEmpty).toSet().toList();
    setCiudades.sort();
    return ['TODAS', ...setCiudades];
  }

  bool get _haySucursalConStockCompleto {
    return _sucursales.any((s) => s.tieneStockCompleto);
  }

  Future<void> _confirmarPedido() async {
    if (!_formKey.currentState!.validate()) return;

    if (_modalidad == 'RETIRO_SUCURSAL') {
      if (_sucursalSeleccionada == null) {
        setState(() => _error = 'Por favor selecciona una sucursal para el retiro.');
        return;
      }
      if (!_sucursalSeleccionada!.tieneStockCompleto) {
        setState(() => _error =
            'La sucursal seleccionada no cuenta con inventario suficiente para todas tus prendas.');
        return;
      }
    }

    setState(() {
      _procesando = true;
      _error = null;
    });

    final pedidoService = context.read<PedidoService>();
    final carritoService = context.read<CarritoService>();

    try {
      final idSuc = _sucursalSeleccionada?.idSucursal ?? (_sucursales.isNotEmpty ? _sucursales.first.idSucursal : 1);

      final nuevoPedido = await pedidoService.crearPedido(
        idSucursal: idSuc,
        modalidadCompra: _modalidad,
        nombreContacto: _nombreCtrl.text.trim(),
        telefonoContacto: _telefonoCtrl.text.trim(),
        correoContacto: _correoCtrl.text.trim(),
        direccionEntrega: _modalidad == 'ENTREGA_DOMICILIO' ? _direccionCtrl.text.trim() : null,
        ciudadEntrega: _modalidad == 'ENTREGA_DOMICILIO' ? _ciudadCtrl.text.trim() : null,
        notasEntrega: _notasCtrl.text.trim(),
        idEmpresa: widget.carrito.idEmpresa,
      );

      // Recargar bolsa para reflejar que se procesó
      await carritoService.cargarCarrito();

      if (mounted) {
        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (ctx) => AlertDialog(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
            title: Row(
              children: [
                const Icon(Icons.check_circle, color: AppTheme.primaryGold, size: 28),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    '¡Pedido Registrado!',
                    style: GoogleFonts.playfairDisplay(fontSize: 20, fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Tu pedido ha sido registrado con éxito bajo el código:',
                  style: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textSecondary),
                ),
                const SizedBox(height: 10),
                Center(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      color: AppTheme.goldLight,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppTheme.primaryGold.withValues(alpha: 0.3)),
                    ),
                    child: Text(
                      nuevoPedido.codigoPedido,
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.primaryGold,
                        letterSpacing: 1,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                Text(
                  'Para asegurar el despacho de tus prendas de alta costura, completa el pago electrónico ahora.',
                  style: GoogleFonts.plusJakartaSans(fontSize: 12, color: AppTheme.textSecondary),
                ),
              ],
            ),
            actions: [
              AuroraButton(
                text: 'Proceder al Pago Seguro',
                icon: Icons.lock_outline,
                onPressed: () {
                  Navigator.pop(ctx); // Cierra diálogo
                  Navigator.pushReplacement(
                    context,
                    MaterialPageRoute(
                      builder: (_) => PagoScreen(
                        idPedido: nuevoPedido.idPedido,
                        pedidoInicial: nuevoPedido,
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 8),
              AuroraButton(
                text: 'Pagar más tarde',
                variant: AuroraButtonVariant.outline,
                onPressed: () {
                  Navigator.pop(ctx); // Cierra diálogo
                  Navigator.pop(context); // Cierra checkout y vuelve a la tienda
                },
              ),
            ],
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _procesando = false;
          _error = e.toString().replaceAll('Exception: ', '');
        });
      }
    }
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
          'Confirmar Compra',
          style: GoogleFonts.playfairDisplay(fontSize: 18, fontWeight: FontWeight.w700),
        ),
      ),
      body: _cargandoSucursales
          ? const Center(child: CircularProgressIndicator())
          : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  if (_error != null) ...[
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppTheme.errorLight,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        _error!,
                        style: GoogleFonts.plusJakartaSans(color: AppTheme.error, fontSize: 12),
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],

                  // Resumen de la Bolsa
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Resumen de compra',
                              style: GoogleFonts.playfairDisplay(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            Text(
                              '${widget.carrito.totalItems} prendas',
                              style: GoogleFonts.plusJakartaSans(
                                fontSize: 12,
                                color: AppTheme.textMuted,
                              ),
                            ),
                          ],
                        ),
                        const Divider(height: 20),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Subtotal',
                              style: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textSecondary),
                            ),
                            Text(
                              currencyFormatter.format(widget.carrito.subtotal),
                              style: GoogleFonts.plusJakartaSans(fontSize: 13, fontWeight: FontWeight.w600),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Total a pagar',
                              style: GoogleFonts.plusJakartaSans(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                            Text(
                              currencyFormatter.format(widget.carrito.total),
                              style: GoogleFonts.plusJakartaSans(
                                fontSize: 18,
                                fontWeight: FontWeight.w800,
                                color: AppTheme.primaryGold,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 20),

                  // Modalidad de Compra
                  Text(
                    'Modalidad de Entrega',
                    style: GoogleFonts.plusJakartaSans(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: InkWell(
                          onTap: () => setState(() => _modalidad = 'RETIRO_SUCURSAL'),
                          borderRadius: BorderRadius.circular(12),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
                            decoration: BoxDecoration(
                              color: _modalidad == 'RETIRO_SUCURSAL' ? AppTheme.goldLight : AppTheme.surface,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: _modalidad == 'RETIRO_SUCURSAL' ? AppTheme.primaryGold : AppTheme.border,
                                width: _modalidad == 'RETIRO_SUCURSAL' ? 1.5 : 1,
                              ),
                            ),
                            child: Column(
                              children: [
                                Icon(
                                  Icons.storefront,
                                  color: _modalidad == 'RETIRO_SUCURSAL' ? AppTheme.primaryGold : AppTheme.textMuted,
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  'Retiro en Sucursal',
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: _modalidad == 'RETIRO_SUCURSAL' ? AppTheme.primaryGold : AppTheme.textPrimary,
                                  ),
                                  textAlign: TextAlign.center,
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: InkWell(
                          onTap: () => setState(() => _modalidad = 'ENTREGA_DOMICILIO'),
                          borderRadius: BorderRadius.circular(12),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
                            decoration: BoxDecoration(
                              color: _modalidad == 'ENTREGA_DOMICILIO' ? AppTheme.goldLight : AppTheme.surface,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: _modalidad == 'ENTREGA_DOMICILIO' ? AppTheme.primaryGold : AppTheme.border,
                                width: _modalidad == 'ENTREGA_DOMICILIO' ? 1.5 : 1,
                              ),
                            ),
                            child: Column(
                              children: [
                                Icon(
                                  Icons.local_shipping_outlined,
                                  color: _modalidad == 'ENTREGA_DOMICILIO' ? AppTheme.primaryGold : AppTheme.textMuted,
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  'Entrega a Domicilio',
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: _modalidad == 'ENTREGA_DOMICILIO' ? AppTheme.primaryGold : AppTheme.textPrimary,
                                  ),
                                  textAlign: TextAlign.center,
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 20),

                  // Selector de Sucursal con Filtros y Badges de Stock
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _modalidad == 'RETIRO_SUCURSAL'
                            ? 'Sucursal de Retiro'
                            : 'Sucursal de Origen / Despacho',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      if (_modalidad == 'RETIRO_SUCURSAL')
                        Text(
                          'Solo con stock completo',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 11,
                            color: AppTheme.primaryGold,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),

                  // Alerta si ninguna sucursal tiene stock completo para retiro
                  if (_modalidad == 'RETIRO_SUCURSAL' &&
                      !_cargandoSucursales &&
                      !_haySucursalConStockCompleto &&
                      _sucursales.isNotEmpty) ...[
                    Container(
                      padding: const EdgeInsets.all(12),
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: AppTheme.goldLight,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                            color: AppTheme.primaryGold.withValues(alpha: 0.3)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.info_outline,
                              color: AppTheme.primaryGold, size: 20),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              'Ninguna sucursal física cuenta con el stock completo de todas tus prendas. Te recomendamos entrega a domicilio.',
                              style: GoogleFonts.plusJakartaSans(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],

                  // Barra de Búsqueda y Filtros de Ciudad
                  if (_sucursales.length > 1) ...[
                    TextField(
                      controller: _busquedaSucursalCtrl,
                      onChanged: (val) => setState(() => _busquedaSucursal = val),
                      decoration: InputDecoration(
                        hintText: 'Buscar sucursal por nombre o dirección...',
                        hintStyle: GoogleFonts.plusJakartaSans(fontSize: 12),
                        prefixIcon: const Icon(Icons.search, size: 18),
                        suffixIcon: _busquedaSucursal.isNotEmpty
                            ? IconButton(
                                icon: const Icon(Icons.clear, size: 16),
                                onPressed: () {
                                  _busquedaSucursalCtrl.clear();
                                  setState(() => _busquedaSucursal = '');
                                },
                              )
                            : null,
                        contentPadding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 10),
                      ),
                    ),
                    const SizedBox(height: 8),

                    // Chips de Ciudades
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: _ciudadesDisponibles.map((ciudad) {
                          final isSelected = _filtroCiudad == ciudad;
                          return Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: FilterChip(
                              label: Text(
                                ciudad,
                                style: GoogleFonts.plusJakartaSans(
                                  fontSize: 11,
                                  fontWeight: isSelected
                                      ? FontWeight.w700
                                      : FontWeight.w500,
                                  color: isSelected
                                      ? Colors.white
                                      : AppTheme.textPrimary,
                                ),
                              ),
                              selected: isSelected,
                              showCheckmark: false,
                              selectedColor: AppTheme.primaryGold,
                              backgroundColor: AppTheme.surfaceVariant,
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 4, vertical: 2),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10),
                                side: BorderSide(
                                  color: isSelected
                                      ? AppTheme.primaryGold
                                      : AppTheme.border,
                                ),
                              ),
                              onSelected: (_) {
                                setState(() => _filtroCiudad = ciudad);
                              },
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],

                  // Listado de Tarjetas de Sucursal
                  if (_sucursalesFiltradas.isEmpty && !_cargandoSucursales) ...[
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: AppTheme.surfaceVariant,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Center(
                        child: Text(
                          'No se encontraron sucursales con los filtros aplicados.',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 12,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ),
                    ),
                  ] else ...[
                    ..._sucursalesFiltradas.map((s) {
                      final isSelected =
                          _sucursalSeleccionada?.idSucursal == s.idSucursal;
                      final bloqueada = _modalidad == 'RETIRO_SUCURSAL' &&
                          !s.tieneStockCompleto;

                      final badgeColor = s.tieneStockCompleto
                          ? AppTheme.successLight
                          : s.stockEstado == 'PARCIAL'
                              ? AppTheme.goldLight
                              : AppTheme.errorLight;
                      final textColor = s.tieneStockCompleto
                          ? AppTheme.success
                          : s.stockEstado == 'PARCIAL'
                              ? AppTheme.primaryGold
                              : AppTheme.error;

                      return Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: InkWell(
                          onTap: bloqueada
                              ? () {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(
                                      content: Text(
                                        '${s.nombre} no cuenta con todas las prendas de tu bolsa en stock.',
                                      ),
                                      duration: const Duration(seconds: 2),
                                      backgroundColor: AppTheme.error,
                                    ),
                                  );
                                }
                              : () =>
                                  setState(() => _sucursalSeleccionada = s),
                          borderRadius: BorderRadius.circular(14),
                          child: AnimatedOpacity(
                            duration: const Duration(milliseconds: 200),
                            opacity: bloqueada ? 0.55 : 1.0,
                            child: Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: isSelected
                                    ? AppTheme.goldLight
                                    : !bloqueada
                                        ? AppTheme.surface
                                        : AppTheme.surfaceVariant
                                            .withValues(alpha: 0.6),
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(
                                  color: isSelected
                                      ? AppTheme.primaryGold
                                      : !bloqueada
                                          ? AppTheme.border
                                          : AppTheme.border
                                              .withValues(alpha: 0.5),
                                  width: isSelected ? 1.5 : 1,
                                ),
                              ),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Padding(
                                    padding: const EdgeInsets.only(top: 2),
                                    child: Icon(
                                      bloqueada
                                          ? Icons.block
                                          : isSelected
                                              ? Icons.radio_button_checked
                                              : Icons.radio_button_off,
                                      color: isSelected
                                          ? AppTheme.primaryGold
                                          : bloqueada
                                              ? AppTheme.error
                                              : AppTheme.textMuted,
                                      size: 20,
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            Expanded(
                                              child: Text(
                                                s.nombre,
                                                style: GoogleFonts
                                                    .plusJakartaSans(
                                                  fontSize: 13,
                                                  fontWeight: isSelected
                                                      ? FontWeight.w700
                                                      : FontWeight.w600,
                                                  color: !bloqueada
                                                      ? AppTheme.textPrimary
                                                      : AppTheme.textMuted,
                                                ),
                                              ),
                                            ),
                                            Container(
                                              padding:
                                                  const EdgeInsets.symmetric(
                                                      horizontal: 6,
                                                      vertical: 2),
                                              decoration: BoxDecoration(
                                                color: AppTheme.surfaceVariant,
                                                borderRadius:
                                                    BorderRadius.circular(6),
                                              ),
                                              child: Text(
                                                s.ciudad,
                                                style: GoogleFonts
                                                    .plusJakartaSans(
                                                  fontSize: 10,
                                                  fontWeight: FontWeight.w600,
                                                  color:
                                                      AppTheme.textSecondary,
                                                ),
                                              ),
                                            ),
                                          ],
                                        ),
                                        if (s.direccion.isNotEmpty) ...[
                                          const SizedBox(height: 2),
                                          Text(
                                            s.direccion,
                                            style: GoogleFonts.plusJakartaSans(
                                              fontSize: 11,
                                              color: AppTheme.textSecondary,
                                            ),
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        ],
                                        const SizedBox(height: 6),
                                        AuroraBadge(
                                          text: s.stockLabel,
                                          backgroundColor: badgeColor,
                                          textColor: textColor,
                                          isSmall: true,
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      );
                    }),
                  ],

                  const SizedBox(height: 20),

                  // Datos del Cliente
                  Text(
                    'Datos de Contacto',
                    style: GoogleFonts.playfairDisplay(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 12),
                  AuroraTextField(
                    controller: _nombreCtrl,
                    label: 'Nombre completo',
                    validator: (v) => v == null || v.trim().isEmpty ? 'Requerido' : null,
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: AuroraTextField(
                          controller: _telefonoCtrl,
                          label: 'Teléfono de contacto',
                          keyboardType: TextInputType.phone,
                          validator: (v) => v == null || v.trim().isEmpty ? 'Requerido' : null,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: AuroraTextField(
                          controller: _correoCtrl,
                          label: 'Correo electrónico',
                          keyboardType: TextInputType.emailAddress,
                        ),
                      ),
                    ],
                  ),

                  if (_modalidad == 'ENTREGA_DOMICILIO') ...[
                    const SizedBox(height: 16),
                    Text(
                      'Dirección de Envío',
                      style: GoogleFonts.playfairDisplay(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    AuroraTextField(
                      controller: _direccionCtrl,
                      label: 'Dirección completa',
                      hint: 'Calle, número, barrio o edificio',
                      validator: (v) => _modalidad == 'ENTREGA_DOMICILIO' && (v == null || v.trim().isEmpty)
                          ? 'Ingresa tu dirección de entrega'
                          : null,
                    ),
                    const SizedBox(height: 12),
                    AuroraTextField(
                      controller: _ciudadCtrl,
                      label: 'Ciudad',
                      validator: (v) => _modalidad == 'ENTREGA_DOMICILIO' && (v == null || v.trim().isEmpty)
                          ? 'Ingresa tu ciudad'
                          : null,
                    ),
                  ],

                  const SizedBox(height: 12),
                  AuroraTextField(
                    controller: _notasCtrl,
                    label: 'Notas adicionales (opcional)',
                    hint: 'Instrucciones para el paquete o retiro',
                  ),

                  const SizedBox(height: 32),

                  AuroraButton(
                    text: 'Confirmar pedido',
                    isLoading: _procesando,
                    onPressed: _procesando ||
                            (_modalidad == 'RETIRO_SUCURSAL' &&
                                (_sucursalSeleccionada == null ||
                                    !_sucursalSeleccionada!.tieneStockCompleto))
                        ? null
                        : _confirmarPedido,
                    variant: AuroraButtonVariant.primary,
                  ),
                ],
              ),
            ),
    );
  }
}
