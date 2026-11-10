import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/pago_service.dart';
import '../services/pedido_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_button.dart';

class PagoScreen extends StatefulWidget {
  final int idPedido;
  final PedidoModel? pedidoInicial;

  const PagoScreen({
    super.key,
    required this.idPedido,
    this.pedidoInicial,
  });

  @override
  State<PagoScreen> createState() => _PagoScreenState();
}

class _PagoScreenState extends State<PagoScreen> {
  String _metodoSeleccionado = 'TARJETA'; // 'TARJETA' o 'PAYPAL'

  // Formulario Tarjeta
  final _titularController = TextEditingController();
  final _numeroTarjetaController = TextEditingController();
  final _mesController = TextEditingController();
  final _anioController = TextEditingController();
  final _cvvController = TextEditingController();

  // Facturación opcional
  bool _deseaFactura = false;
  final _nitCiController = TextEditingController();
  final _razonSocialController = TextEditingController();

  bool _procesando = false;
  String? _errorMensaje;
  ResultadoPagoModel? _resultadoPago;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<PagoService>().obtenerResumen(widget.idPedido);
    });
  }

  @override
  void dispose() {
    _titularController.dispose();
    _numeroTarjetaController.dispose();
    _mesController.dispose();
    _anioController.dispose();
    _cvvController.dispose();
    _nitCiController.dispose();
    _razonSocialController.dispose();
    super.dispose();
  }

  bool _formularioTarjetaValido() {
    final titular = _titularController.text.trim();
    final numero = _numeroTarjetaController.text.replaceAll(' ', '').trim();
    final mes = _mesController.text.trim();
    final anio = _anioController.text.trim();
    final cvv = _cvvController.text.trim();

    if (titular.length < 3) return false;
    if (numero.length < 13 || numero.length > 19) return false;
    if (mes.length != 2 ||
        (int.tryParse(mes) ?? 0) < 1 ||
        (int.tryParse(mes) ?? 0) > 12) {
      return false;
    }
    if (anio.length < 2 || anio.length > 4) return false;
    if (cvv.length < 3 || cvv.length > 4) return false;

    if (_deseaFactura) {
      if (_nitCiController.text.trim().isEmpty) return false;
      if (_razonSocialController.text.trim().isEmpty) return false;
    }

    return true;
  }

  Future<void> _pagarConTarjeta(ResumenPedidoPagoModel resumen) async {
    if (!_formularioTarjetaValido()) {
      setState(() =>
          _errorMensaje = 'Por favor completa todos los campos de la tarjeta.');
      return;
    }

    setState(() {
      _procesando = true;
      _errorMensaje = null;
    });

    final pagoService = context.read<PagoService>();
    final pedidoService = context.read<PedidoService>();

    final res = await pagoService.procesarTarjeta(
      idPedido: resumen.idPedido,
      titular: _titularController.text.trim(),
      numeroTarjeta: _numeroTarjetaController.text.trim(),
      mesExp: _mesController.text.trim(),
      anioExp: _anioController.text.trim(),
      cvv: _cvvController.text.trim(),
      nitCi: _deseaFactura ? _nitCiController.text.trim() : null,
      razonSocial: _deseaFactura ? _razonSocialController.text.trim() : null,
      idEmpresa: resumen.idEmpresa,
    );

    if (mounted) {
      setState(() {
        _procesando = false;
        if (res != null) {
          _resultadoPago = res;
        } else {
          _errorMensaje =
              pagoService.error ?? 'No fue posible autorizar el pago.';
        }
      });

      if (res != null) {
        // Refrescar lista de pedidos para que cambie a PAGADO
        pedidoService.cargarMisPedidos();
      }
    }
  }


  Future<void> _iniciarPagoPayPal(ResumenPedidoPagoModel resumen) async {
    if (_deseaFactura) {
      if (_nitCiController.text.trim().isEmpty ||
          _razonSocialController.text.trim().isEmpty) {
        setState(() => _errorMensaje =
            'Por favor ingresa NIT/CI y Razón Social para la factura.');
        return;
      }
    }

    setState(() {
      _procesando = true;
      _errorMensaje = null;
    });

    final pagoService = context.read<PagoService>();
    final pedidoService = context.read<PedidoService>();

    final ordenData = await pagoService.crearOrdenPayPal(
      resumen.idPedido,
      idEmpresa: resumen.idEmpresa,
    );

    if (!mounted) return;

    if (ordenData == null || ordenData['order_id'] == null) {
      setState(() {
        _procesando = false;
        _errorMensaje =
            pagoService.error ?? 'No fue posible iniciar la orden de PayPal.';
      });
      return;
    }

    final orderId = ordenData['order_id'] as String;
    final totalUsd = ordenData['total_usd'] ?? '0.00';
    final approveUrl = ordenData['approve_url']?.toString();

    if (approveUrl == null || approveUrl.isEmpty) {
      setState(() {
        _procesando = false;
        _errorMensaje = 'PayPal no devolvió la URL de aprobación.';
      });
      return;
    }

    final opened = await launchUrl(
      Uri.parse(approveUrl),
      mode: LaunchMode.externalApplication,
    );
    if (!opened || !mounted) {
      if (mounted) {
        setState(() {
          _procesando = false;
          _errorMensaje = 'No se pudo abrir PayPal en el dispositivo.';
        });
      }
      return;
    }

    // Diálogo de autorización PayPal para confirmar el cobro
    final confirmar = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: const Color(0xFF0070BA).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.payment, color: Color(0xFF0070BA)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'Autorizar con PayPal',
                style: GoogleFonts.playfairDisplay(
                    fontSize: 18, fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'PayPal se abrió en el navegador. Aprueba allí la orden y vuelve a esta pantalla para confirmar:',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 13, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 14),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppTheme.surfaceVariant,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('ID de Orden PayPal:',
                      style: GoogleFonts.plusJakartaSans(
                          fontSize: 11, color: AppTheme.textMuted)),
                  Text(orderId,
                      style: GoogleFonts.plusJakartaSans(
                          fontSize: 12, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  Text('Monto a cobrar:',
                      style: GoogleFonts.plusJakartaSans(
                          fontSize: 11, color: AppTheme.textMuted)),
                  Text(
                    'USD \$$totalUsd (Equiv. Bs. ${resumen.total.toStringAsFixed(2)})',
                    style: GoogleFonts.plusJakartaSans(
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        color: const Color(0xFF0070BA)),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'La captura solo se realizará después de que PayPal confirme la aprobación.',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 11, color: AppTheme.textMuted),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF0070BA),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12)),
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Ya aprobé en PayPal'),
          ),
        ],
      ),
    );

    if (confirmar != true) {
      setState(() {
        _procesando = false;
        _errorMensaje = 'Transacción cancelada por el usuario.';
      });
      return;
    }

    // Capturar la orden de PayPal
    final res = await pagoService.capturarPayPal(
      idPedido: resumen.idPedido,
      orderId: orderId,
      nitCi: _deseaFactura ? _nitCiController.text.trim() : null,
      razonSocial: _deseaFactura ? _razonSocialController.text.trim() : null,
      idEmpresa: resumen.idEmpresa,
    );

    if (mounted) {
      setState(() {
        _procesando = false;
        if (res != null) {
          _resultadoPago = res;
        } else {
          _errorMensaje = pagoService.error ??
              'No fue posible capturar la orden en PayPal.';
        }
      });

      if (res != null) {
        pedidoService.cargarMisPedidos();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final pagoService = context.watch<PagoService>();
    final resumen = pagoService.resumen;

    final currencyFormatter = NumberFormat.currency(
      locale: 'es_BO',
      symbol: 'Bs. ',
      decimalDigits: 2,
    );

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Text(
          'Pago Electrónico Seguro',
          style: GoogleFonts.playfairDisplay(
              fontSize: 18, fontWeight: FontWeight.w700),
        ),
      ),
      body: pagoService.cargando && resumen == null
          ? const Center(child: CircularProgressIndicator())
          : _resultadoPago != null
              ? _buildPantallaExito(context, _resultadoPago!, currencyFormatter)
              : resumen == null
                  ? _buildErrorCarga(context, pagoService.error)
                  : _buildContenidoPago(context, resumen, currencyFormatter),
    );
  }

  Widget _buildErrorCarga(BuildContext context, String? error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 60, color: AppTheme.error),
            const SizedBox(height: 16),
            Text(
              'No se pudo cargar el pedido',
              style: GoogleFonts.playfairDisplay(
                  fontSize: 20, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Text(
              error ??
                  'El pedido no se encuentra disponible para pago o ya ha sido pagado.',
              textAlign: TextAlign.center,
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 13, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 24),
            AuroraButton(
              text: 'Volver a Mis Pedidos',
              width: 200,
              onPressed: () => Navigator.pop(context),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContenidoPago(
    BuildContext context,
    ResumenPedidoPagoModel resumen,
    NumberFormat currencyFormatter,
  ) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Banner de seguridad
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.goldLight,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                  color: AppTheme.primaryGold.withValues(alpha: 0.3)),
            ),
            child: Row(
              children: [
                const Icon(Icons.lock_outline,
                    color: AppTheme.primaryGold, size: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Pasarela Encriptada de Extremo a Extremo',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.primaryGold,
                        ),
                      ),
                      Text(
                        'Cumplimiento PCI DSS. Sin almacenamiento de claves de seguridad.',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 11,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Resumen del pedido
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppTheme.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      resumen.codigoPedido,
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.primaryGold,
                      ),
                    ),
                    Text(
                      '${resumen.items.length} ${resumen.items.length == 1 ? 'prenda' : 'prendas'}',
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 12,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
                const Divider(height: 20),
                ...resumen.items.map((item) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              '${item.cantidad}x ${item.productoNombre} (${item.talla} / ${item.color})',
                              style: GoogleFonts.plusJakartaSans(fontSize: 12),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            currencyFormatter.format(item.subtotal),
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    )),
                const Divider(height: 20),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Total a Pagar',
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      currencyFormatter.format(resumen.total),
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
          const SizedBox(height: 24),

          // Selector de Método de Pago
          Text(
            'Selecciona el Método de Pago',
            style: GoogleFonts.playfairDisplay(
                fontSize: 16, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 12),

          Row(
            children: [
              // Opción 1: Tarjeta (Débito / Crédito)
              Expanded(
                child: InkWell(
                  onTap: () => setState(() => _metodoSeleccionado = 'TARJETA'),
                  borderRadius: BorderRadius.circular(16),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                    decoration: BoxDecoration(
                      color: _metodoSeleccionado == 'TARJETA'
                          ? AppTheme.goldLight
                          : AppTheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: _metodoSeleccionado == 'TARJETA'
                            ? AppTheme.primaryGold
                            : AppTheme.border,
                        width: _metodoSeleccionado == 'TARJETA' ? 2 : 1,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Icon(Icons.credit_card,
                                color: AppTheme.primaryGold, size: 24),
                            if (_metodoSeleccionado == 'TARJETA')
                              const Icon(Icons.check_circle,
                                  color: AppTheme.primaryGold, size: 16),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Tarjeta',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        Text(
                          'Débito / Crédito',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 11,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),

              // Opción 2: PayPal (Internacional)
              Expanded(
                child: InkWell(
                  onTap: () => setState(() => _metodoSeleccionado = 'PAYPAL'),
                  borderRadius: BorderRadius.circular(16),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                    decoration: BoxDecoration(
                      color: _metodoSeleccionado == 'PAYPAL'
                          ? const Color(0xFF0070BA).withValues(alpha: 0.08)
                          : AppTheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: _metodoSeleccionado == 'PAYPAL'
                            ? const Color(0xFF0070BA)
                            : AppTheme.border,
                        width: _metodoSeleccionado == 'PAYPAL' ? 2 : 1,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Icon(Icons.account_balance_wallet,
                                color: Color(0xFF0070BA), size: 24),
                            if (_metodoSeleccionado == 'PAYPAL')
                              const Icon(Icons.check_circle,
                                  color: Color(0xFF0070BA), size: 16),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'PayPal',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        Text(
                          'Internacional',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 11,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // FORMULARIO SEGÚN MÉTODO SELECCIONADO
          if (_metodoSeleccionado == 'TARJETA')
            _buildFormularioTarjeta(context, resumen, currencyFormatter)
          else
            _buildSeccionPayPal(context, resumen, currencyFormatter),

          if (_errorMensaje != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.errorLight,
                borderRadius: BorderRadius.circular(12),
                border:
                    Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline,
                      color: AppTheme.error, size: 20),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      _errorMensaje!,
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 12,
                        color: AppTheme.error,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildFormularioTarjeta(
    BuildContext context,
    ResumenPedidoPagoModel resumen,
    NumberFormat currencyFormatter,
  ) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Titular
          Text('Nombre del Titular',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 12, fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          TextField(
            controller: _titularController,
            textCapitalization: TextCapitalization.characters,
            decoration: InputDecoration(
              hintText: 'Como figura en la tarjeta',
              filled: true,
              fillColor: AppTheme.surfaceVariant,
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none),
            ),
          ),
          const SizedBox(height: 14),

          // Número de tarjeta
          Text('Número de Tarjeta',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 12, fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          TextField(
            controller: _numeroTarjetaController,
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(16),
              _CardNumberFormatter(),
            ],
            decoration: InputDecoration(
              hintText: '4000 1234 5678 9010',
              prefixIcon: const Icon(Icons.credit_card_outlined),
              filled: true,
              fillColor: AppTheme.surfaceVariant,
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none),
            ),
          ),
          const SizedBox(height: 14),

          // Mes, Año y CVV
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Mes',
                        style: GoogleFonts.plusJakartaSans(
                            fontSize: 12, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _mesController,
                      keyboardType: TextInputType.number,
                      textAlign: TextAlign.center,
                      inputFormatters: [
                        FilteringTextInputFormatter.digitsOnly,
                        LengthLimitingTextInputFormatter(2),
                      ],
                      decoration: InputDecoration(
                        hintText: 'MM',
                        filled: true,
                        fillColor: AppTheme.surfaceVariant,
                        contentPadding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 12),
                        border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide.none),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Año',
                        style: GoogleFonts.plusJakartaSans(
                            fontSize: 12, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _anioController,
                      keyboardType: TextInputType.number,
                      textAlign: TextAlign.center,
                      inputFormatters: [
                        FilteringTextInputFormatter.digitsOnly,
                        LengthLimitingTextInputFormatter(4),
                      ],
                      decoration: InputDecoration(
                        hintText: 'AA / AAAA',
                        filled: true,
                        fillColor: AppTheme.surfaceVariant,
                        contentPadding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 12),
                        border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide.none),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('CVV',
                        style: GoogleFonts.plusJakartaSans(
                            fontSize: 12, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _cvvController,
                      keyboardType: TextInputType.number,
                      textAlign: TextAlign.center,
                      obscureText: true,
                      inputFormatters: [
                        FilteringTextInputFormatter.digitsOnly,
                        LengthLimitingTextInputFormatter(4),
                      ],
                      decoration: InputDecoration(
                        hintText: '•••',
                        filled: true,
                        fillColor: AppTheme.surfaceVariant,
                        contentPadding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 12),
                        border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide.none),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),

          // Facturación opcional
          _buildOpcionFactura(),
          const SizedBox(height: 20),

          // Botón Confirmar Pago
          AuroraButton(
            text:
                'Confirmar Pago de ${currencyFormatter.format(resumen.total)}',
            isLoading: _procesando,
            icon: Icons.lock_outline,
            onPressed: _procesando ? null : () => _pagarConTarjeta(resumen),
          ),
        ],
      ),
    );
  }

  Widget _buildSeccionPayPal(
    BuildContext context,
    ResumenPedidoPagoModel resumen,
    NumberFormat currencyFormatter,
  ) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFF0070BA).withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                  color: const Color(0xFF0070BA).withValues(alpha: 0.2)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.language,
                        color: Color(0xFF0070BA), size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'Pago Internacional con PayPal',
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: const Color(0xFF0070BA),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  'El cobro se procesará de manera segura al cambio oficial por un total de ${currencyFormatter.format(resumen.total)}. Puedes asociar tu cuenta de PayPal o pagar con tu saldo internacional.',
                  style: GoogleFonts.plusJakartaSans(
                      fontSize: 12, height: 1.4, color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),

          // Facturación opcional
          _buildOpcionFactura(),
          const SizedBox(height: 20),

          // Botón PayPal
          SizedBox(
            width: double.infinity,
            height: 50,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFFFC439),
                foregroundColor: const Color(0xFF003087),
                elevation: 0,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14)),
              ),
              icon: _procesando
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Color(0xFF003087)),
                    )
                  : const Icon(Icons.payment, size: 20),
              label: Text(
                _procesando ? 'Conectando con PayPal...' : 'Pagar con PayPal',
                style: GoogleFonts.plusJakartaSans(
                    fontSize: 14, fontWeight: FontWeight.w800),
              ),
              onPressed: _procesando ? null : () => _iniciarPagoPayPal(resumen),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildOpcionFactura() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: () => setState(() => _deseaFactura = !_deseaFactura),
          child: Row(
            children: [
              Checkbox(
                value: _deseaFactura,
                activeColor: AppTheme.primaryGold,
                onChanged: (val) =>
                    setState(() => _deseaFactura = val ?? false),
              ),
              Expanded(
                child: Text(
                  'Deseo Factura Electrónica con datos fiscales',
                  style: GoogleFonts.plusJakartaSans(
                      fontSize: 12, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
        ),
        if (_deseaFactura) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.surfaceVariant,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppTheme.border),
            ),
            child: Column(
              children: [
                TextField(
                  controller: _nitCiController,
                  decoration: InputDecoration(
                    labelText: 'NIT / CI *',
                    hintText: 'Ej: 8492019',
                    filled: true,
                    fillColor: AppTheme.surface,
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 10),
                    border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide.none),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _razonSocialController,
                  decoration: InputDecoration(
                    labelText: 'Razón Social *',
                    hintText: 'Nombre o Empresa',
                    filled: true,
                    fillColor: AppTheme.surface,
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 10),
                    border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide.none),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildPantallaExito(
    BuildContext context,
    ResultadoPagoModel resultado,
    NumberFormat currencyFormatter,
  ) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const SizedBox(height: 20),
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppTheme.successLight,
              shape: BoxShape.circle,
              border: Border.all(
                  color: AppTheme.success.withValues(alpha: 0.3), width: 2),
            ),
            child: const Icon(Icons.check_circle_outline,
                size: 44, color: AppTheme.success),
          ),
          const SizedBox(height: 18),
          Text(
            '¡Pago Procesado con Éxito!',
            style: GoogleFonts.playfairDisplay(
                fontSize: 22, fontWeight: FontWeight.w700),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 6),
          Text(
            'La venta ha sido registrada formalmente y el inventario ha sido actualizado.',
            style: GoogleFonts.plusJakartaSans(
                fontSize: 13, color: AppTheme.textSecondary),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 28),

          // Ficha de Venta / Factura
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppTheme.border),
              boxShadow: const [
                BoxShadow(
                    color: Color(0x08000000),
                    blurRadius: 10,
                    offset: Offset(0, 4)),
              ],
            ),
            child: Column(
              children: [
                _buildFilaFicha(
                  'Documento Emitido',
                  resultado.tipoDocumento == 'FACTURA'
                      ? 'Factura Electrónica'
                      : 'Comprobante de Venta',
                  esDestacado: true,
                ),
                const Divider(height: 20),
                _buildFilaFicha('N° de Venta', resultado.numeroVenta),
                const Divider(height: 20),
                _buildFilaFicha('Código de Pedido', resultado.codigoPedido),
                const Divider(height: 20),
                _buildFilaFicha('Método de Pago', resultado.metodoPago),
                const Divider(height: 20),
                _buildFilaFicha(
                    'Transacción Bancaria', resultado.codigoTransaccion),
                const Divider(height: 20),
                _buildFilaFicha(
                  'Total Pagado',
                  currencyFormatter.format(resultado.total),
                  colorValor: AppTheme.success,
                  esGrande: true,
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Aviso de envío por correo
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.surfaceVariant,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppTheme.border),
            ),
            child: Row(
              children: [
                const Icon(Icons.email_outlined,
                    color: AppTheme.primaryGold, size: 20),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Se ha enviado una copia digital a tu correo electrónico.',
                    style: GoogleFonts.plusJakartaSans(
                        fontSize: 12, color: AppTheme.textSecondary),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 28),

          AuroraButton(
            text: 'Ver Mis Pedidos',
            onPressed: () {
              Navigator.pop(context); // Cierra pantalla de pago
            },
          ),
          const SizedBox(height: 10),
          AuroraButton(
            text: 'Continuar Comprando',
            variant: AuroraButtonVariant.outline,
            onPressed: () {
              Navigator.popUntil(context, (route) => route.isFirst);
            },
          ),
        ],
      ),
    );
  }

  Widget _buildFilaFicha(
    String etiqueta,
    String valor, {
    bool esDestacado = false,
    bool esGrande = false,
    Color? colorValor,
  }) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          etiqueta,
          style: GoogleFonts.plusJakartaSans(
            fontSize: 12,
            color: AppTheme.textSecondary,
          ),
        ),
        const SizedBox(width: 10),
        Flexible(
          child: Text(
            valor,
            style: GoogleFonts.plusJakartaSans(
              fontSize: esGrande ? 16 : 13,
              fontWeight:
                  esDestacado || esGrande ? FontWeight.w800 : FontWeight.w600,
              color: colorValor ?? AppTheme.textPrimary,
            ),
            textAlign: TextAlign.end,
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}

class _CardNumberFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    var text = newValue.text.replaceAll(' ', '');
    var buffer = StringBuffer();
    for (int i = 0; i < text.length; i++) {
      buffer.write(text[i]);
      var nonZeroIndex = i + 1;
      if (nonZeroIndex % 4 == 0 && nonZeroIndex != text.length) {
        buffer.write(' ');
      }
    }
    var string = buffer.toString();
    return newValue.copyWith(
      text: string,
      selection: TextSelection.collapsed(offset: string.length),
    );
  }
}
