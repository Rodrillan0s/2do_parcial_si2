import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../services/devoluciones_service.dart';
import '../services/pedido_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_button.dart';

class SolicitarDevolucionModal extends StatefulWidget {
  final PedidoModel pedido;

  const SolicitarDevolucionModal({super.key, required this.pedido});

  @override
  State<SolicitarDevolucionModal> createState() => _SolicitarDevolucionModalState();
}

class _SolicitarDevolucionModalState extends State<SolicitarDevolucionModal> {
  final TextEditingController _motivoDetalleController = TextEditingController();
  final TextEditingController _evidenciaUrlController = TextEditingController();

  bool _cargandoElegibilidad = true;
  String? _errorElegibilidad;
  ElegibilidadVentaModel? _elegibilidad;

  final Map<int, bool> _itemsSeleccionados = {};
  final Map<int, int> _cantidadesDevolver = {};
  final Map<int, String> _tallasDeseadas = {};

  String _motivoSeleccionado = 'TALLA_INCORRECTA';
  String _tipoResolucion = 'CAMBIO_PRENDA';
  bool _enviando = false;
  String? _errorEnvio;

  final List<Map<String, String>> _motivosDisponibles = [
    {'codigo': 'TALLA_INCORRECTA', 'nombre': 'Talla no adecuada o ajuste incorrecto'},
    {'codigo': 'DEFECTO_FABRICA', 'nombre': 'Defecto de confección o costura'},
    {'codigo': 'NO_COINCIDE_DESCRIPCION', 'nombre': 'No coincide con el diseño mostrado'},
    {'codigo': 'CAMBIO_MODELO', 'nombre': 'Preferencia de cambio por otro modelo'},
    {'codigo': 'GARANTIA_LEGAL', 'nombre': 'Garantía legal de calidad (Ley 453)'},
  ];

  @override
  void initState() {
    super.initState();
    _consultarElegibilidad();
  }

  @override
  void dispose() {
    _motivoDetalleController.dispose();
    _evidenciaUrlController.dispose();
    super.dispose();
  }

  Future<void> _consultarElegibilidad() async {
    final service = context.read<DevolucionesService>();
    final idVenta = widget.pedido.idPedido;

    final eleg = await service.consultarElegibilidadVenta(
      idVenta,
      idEmpresa: widget.pedido.idEmpresa,
    );

    if (mounted) {
      setState(() {
        _cargandoElegibilidad = false;
        _elegibilidad = eleg;
        if (!eleg.esElegible) {
          _errorElegibilidad = eleg.motivoNoElegible ?? 'Esta compra no cumple el plazo para devolución.';
        } else {
          // Inicializar checkboxes y tallas deseadas
          for (final item in widget.pedido.items) {
            _itemsSeleccionados[item.idDetallePedido] = true;
            _cantidadesDevolver[item.idDetallePedido] = item.cantidad;

            final elegItem = eleg.items.cast<ItemElegibleDevolucionModel?>().firstWhere(
              (e) => e?.idDetalleVenta == item.idDetallePedido,
              orElse: () => null,
            );
            if (elegItem != null && elegItem.variantesDisponibles.isNotEmpty) {
              final diff = elegItem.variantesDisponibles.firstWhere(
                (v) => v.talla != item.talla,
                orElse: () => elegItem.variantesDisponibles.first,
              );
              _tallasDeseadas[item.idDetallePedido] = diff.talla;
            } else {
              _tallasDeseadas[item.idDetallePedido] = item.talla;
            }
          }
        }
      });
    }
  }

  List<String> _obtenerTallasOpciones(dynamic item) {
    final elegItem = _elegibilidad?.items.cast<ItemElegibleDevolucionModel?>().firstWhere(
      (e) => e?.idDetalleVenta == item.idDetallePedido,
      orElse: () => null,
    );
    if (elegItem != null && elegItem.variantesDisponibles.isNotEmpty) {
      final tallas = elegItem.variantesDisponibles.map((v) => v.talla).toSet().toList();
      if (!tallas.contains(item.talla)) tallas.insert(0, item.talla);
      return tallas;
    }
    return const ['XS', 'S', 'M', 'L', 'XL', 'XXL'];
  }

  Future<void> _enviarSolicitud() async {
    final itemsDevolver = <Map<String, dynamic>>[];
    for (final item in widget.pedido.items) {
      if (_itemsSeleccionados[item.idDetallePedido] == true) {
        final cant = _cantidadesDevolver[item.idDetallePedido] ?? 1;
        if (cant > 0) {
          final tallaDeseada = _tipoResolucion == 'CAMBIO_PRENDA'
              ? (_tallasDeseadas[item.idDetallePedido] ?? item.talla)
              : null;
          itemsDevolver.add({
            'id_detalle_venta': item.idDetallePedido,
            'id_variante': item.idVariante,
            'cantidad': cant,
            'motivo_item': _motivoSeleccionado,
            if (tallaDeseada != null) 'talla_deseada': tallaDeseada,
          });
        }
      }
    }

    if (itemsDevolver.isEmpty) {
      setState(() => _errorEnvio = 'Selecciona al menos una prenda para devolver.');
      return;
    }

    setState(() {
      _enviando = true;
      _errorEnvio = null;
    });

    final service = context.read<DevolucionesService>();
    final idVenta = widget.pedido.idPedido;

    final solicitud = await service.solicitarDevolucion(
      idVenta: idVenta,
      idEmpresa: widget.pedido.idEmpresa,
      motivo: _motivoSeleccionado,
      tipoResolucion: _tipoResolucion,
      descripcion: _motivoDetalleController.text.trim().isNotEmpty
          ? _motivoDetalleController.text.trim()
          : null,
      evidenciaUrl: _evidenciaUrlController.text.trim().isNotEmpty
          ? _evidenciaUrlController.text.trim()
          : null,
      items: itemsDevolver,
    );

    if (mounted) {
      setState(() => _enviando = false);
      Navigator.pop(context, true);
      _mostrarExitoDialog(solicitud);
    }
  }

  void _mostrarExitoDialog(SolicitudDevolucionModel sol) {
    final esCambio = sol.tipoResolucion == 'CAMBIO_PRENDA';
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Icon(
              esCambio ? Icons.swap_horiz : Icons.assignment_turned_in,
              color: esCambio ? Colors.cyan.shade700 : AppTheme.primaryGold,
              size: 26,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                esCambio ? 'Solicitud de Cambio Registrada' : 'Solicitud Registrada',
                style: GoogleFonts.playfairDisplay(fontSize: 18, fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              esCambio
                  ? 'Hemos recibido tu solicitud de cambio de talla correctamente:'
                  : 'Hemos recibido tu solicitud de devolución correctamente:',
              style: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 8),
            Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  color: esCambio ? Colors.cyan.withValues(alpha: 0.1) : AppTheme.goldLight,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: (esCambio ? Colors.cyan : AppTheme.primaryGold).withValues(alpha: 0.3)),
                ),
                child: Text(
                  sol.codigoSolicitud,
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: esCambio ? Colors.cyan.shade800 : AppTheme.primaryGold,
                    letterSpacing: 1,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Text(
              esCambio
                  ? 'Podrás acercarte a la sucursal para entregar tu prenda original y retirar tu nueva talla una vez revisada.'
                  : 'Estado: Solicitada y en revisión por el equipo de calidad.',
              style: GoogleFonts.plusJakartaSans(fontSize: 12, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 4),
            Text(
              'Podrás consultar el avance en la pestaña "Mis Devoluciones".',
              style: GoogleFonts.plusJakartaSans(fontSize: 12, color: AppTheme.textMuted),
            ),
          ],
        ),
        actions: [
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Entendido'),
          ),
        ],
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

    return Container(
      height: MediaQuery.of(context).size.height * 0.90,
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        children: [
          // Barra de arrastre
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppTheme.borderStrong,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),

          // Cabecera
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
            child: Row(
              children: [
                const Icon(Icons.assignment_return_outlined, color: AppTheme.primaryGold, size: 24),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Solicitar Devolución o Cambio',
                        style: GoogleFonts.playfairDisplay(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      Text(
                        'Orden ${widget.pedido.codigoPedido}',
                        style: GoogleFonts.plusJakartaSans(fontSize: 11, color: AppTheme.textMuted),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ),
          const Divider(height: 1),

          Expanded(
            child: _cargandoElegibilidad
                ? const Center(child: CircularProgressIndicator())
                : _errorElegibilidad != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.info_outline, size: 48, color: AppTheme.error),
                              const SizedBox(height: 12),
                              Text(
                                'Devolución No Disponible',
                                style: GoogleFonts.playfairDisplay(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                _errorElegibilidad!,
                                textAlign: TextAlign.center,
                                style: GoogleFonts.plusJakartaSans(
                                  fontSize: 13,
                                  color: AppTheme.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                      )
                    : ListView(
                        padding: const EdgeInsets.all(20),
                        children: [
                          // Banner de Protección Legal Ley 453
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AppTheme.goldLight.withValues(alpha: 0.6),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: AppTheme.primaryGold.withValues(alpha: 0.3)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.shield_outlined, color: AppTheme.primaryGold, size: 20),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    'Compra protegida bajo la Ley 453 de los Derechos del Consumidor. Tienes derecho a devolución, cambio o crédito.',
                                    style: GoogleFonts.plusJakartaSans(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w500,
                                      color: AppTheme.textPrimary,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 16),

                          Text(
                            '1. Selecciona las prendas a devolver',
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 8),

                          ...widget.pedido.items.map((item) {
                            final isSelected = _itemsSeleccionados[item.idDetallePedido] ?? false;
                            final cantActual = _cantidadesDevolver[item.idDetallePedido] ?? 1;

                            return Container(
                              margin: const EdgeInsets.only(bottom: 10),
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: isSelected ? AppTheme.goldLight.withValues(alpha: 0.3) : AppTheme.surface,
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                  color: isSelected ? AppTheme.primaryGold : AppTheme.border,
                                  width: isSelected ? 1.5 : 1,
                                ),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Checkbox(
                                        value: isSelected,
                                        activeColor: AppTheme.primaryGold,
                                        onChanged: (val) {
                                          setState(() {
                                            _itemsSeleccionados[item.idDetallePedido] = val ?? false;
                                          });
                                        },
                                      ),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              item.productoNombre,
                                              style: GoogleFonts.plusJakartaSans(
                                                fontSize: 13,
                                                fontWeight: FontWeight.w700,
                                              ),
                                            ),
                                            Text(
                                              'Talla original: ${item.talla} · Color: ${item.color}',
                                              style: GoogleFonts.plusJakartaSans(
                                                fontSize: 11,
                                                color: AppTheme.textMuted,
                                              ),
                                            ),
                                            Text(
                                              _tipoResolucion == 'CAMBIO_PRENDA'
                                                  ? 'Canje directo por nueva talla'
                                                  : currencyFormatter.format(item.precioUnitario),
                                              style: GoogleFonts.plusJakartaSans(
                                                fontSize: 12,
                                                fontWeight: FontWeight.w600,
                                                color: _tipoResolucion == 'CAMBIO_PRENDA'
                                                    ? Colors.cyan.shade700
                                                    : AppTheme.primaryGold,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                      if (isSelected && item.cantidad > 1) ...[
                                        IconButton(
                                          icon: const Icon(Icons.remove_circle_outline, size: 20),
                                          onPressed: cantActual > 1
                                              ? () => setState(() => _cantidadesDevolver[item.idDetallePedido] = cantActual - 1)
                                              : null,
                                        ),
                                        Text('$cantActual', style: GoogleFonts.plusJakartaSans(fontWeight: FontWeight.w700)),
                                        IconButton(
                                          icon: const Icon(Icons.add_circle_outline, size: 20),
                                          onPressed: cantActual < item.cantidad
                                              ? () => setState(() => _cantidadesDevolver[item.idDetallePedido] = cantActual + 1)
                                              : null,
                                        ),
                                      ],
                                    ],
                                  ),
                                  if (isSelected && _tipoResolucion == 'CAMBIO_PRENDA') ...[
                                    const SizedBox(height: 8),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                      decoration: BoxDecoration(
                                        color: Colors.cyan.withValues(alpha: 0.08),
                                        borderRadius: BorderRadius.circular(8),
                                        border: Border.all(color: Colors.cyan.withValues(alpha: 0.25)),
                                      ),
                                      child: Row(
                                        children: [
                                          const Icon(Icons.swap_horiz, size: 16, color: Colors.cyan),
                                          const SizedBox(width: 8),
                                          Expanded(
                                            child: Text(
                                              'Nueva talla deseada:',
                                              style: GoogleFonts.plusJakartaSans(
                                                fontSize: 11,
                                                fontWeight: FontWeight.w600,
                                                color: Colors.cyan.shade900,
                                              ),
                                            ),
                                          ),
                                          DropdownButton<String>(
                                            value: _tallasDeseadas[item.idDetallePedido] ?? item.talla,
                                            isDense: true,
                                            underline: const SizedBox(),
                                            items: _obtenerTallasOpciones(item).map((t) {
                                              return DropdownMenuItem(
                                                value: t,
                                                child: Text(
                                                  'Talla $t',
                                                  style: GoogleFonts.plusJakartaSans(
                                                    fontSize: 12,
                                                    fontWeight: FontWeight.w700,
                                                    color: t == item.talla ? AppTheme.textMuted : Colors.cyan.shade900,
                                                  ),
                                                ),
                                              );
                                            }).toList(),
                                            onChanged: (val) {
                                              if (val != null) {
                                                setState(() {
                                                  _tallasDeseadas[item.idDetallePedido] = val;
                                                });
                                              }
                                            },
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            );
                          }),

                          const SizedBox(height: 16),
                          Text(
                            '2. Motivo de la Solicitud',
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 8),
                          DropdownButtonFormField<String>(
                            initialValue: _motivoSeleccionado,
                            decoration: InputDecoration(
                              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                            ),
                            items: _motivosDisponibles.map((m) {
                              return DropdownMenuItem(
                                value: m['codigo'],
                                child: Text(m['nombre']!, style: GoogleFonts.plusJakartaSans(fontSize: 12)),
                              );
                            }).toList(),
                            onChanged: (val) {
                              if (val != null) setState(() => _motivoSeleccionado = val);
                            },
                          ),

                          const SizedBox(height: 16),
                          Text(
                            '3. Resolución Preferida',
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 8),
                          RadioGroup<String>(
                            groupValue: _tipoResolucion,
                            onChanged: (val) {
                              if (val != null) setState(() => _tipoResolucion = val);
                            },
                            child: Column(
                              children: [
                                RadioListTile<String>(
                                  title: Text('Cambio de Talla / Prenda', style: GoogleFonts.plusJakartaSans(fontSize: 12, fontWeight: FontWeight.w600)),
                                  subtitle: Text('Canje directo en sucursal por la talla deseada (sin costo ni desembolso monetario).', style: GoogleFonts.plusJakartaSans(fontSize: 10, color: AppTheme.textMuted)),
                                  value: 'CAMBIO_PRENDA',
                                  activeColor: AppTheme.primaryGold,
                                ),
                                RadioListTile<String>(
                                  title: Text('Saldo a Favor / Cupón Digital', style: GoogleFonts.plusJakartaSans(fontSize: 12, fontWeight: FontWeight.w600)),
                                  subtitle: Text('Inmediato para comprar cualquier otra prenda en la tienda.', style: GoogleFonts.plusJakartaSans(fontSize: 10, color: AppTheme.textMuted)),
                                  value: 'SALDO_A_FAVOR',
                                  activeColor: AppTheme.primaryGold,
                                ),
                                RadioListTile<String>(
                                  title: Text('Reembolso Monetario', style: GoogleFonts.plusJakartaSans(fontSize: 12, fontWeight: FontWeight.w600)),
                                  subtitle: Text('Reembolso al método de pago original (requiere revisión administrativa).', style: GoogleFonts.plusJakartaSans(fontSize: 10, color: AppTheme.textMuted)),
                                  value: 'REEMBOLSO_DINERO',
                                  activeColor: AppTheme.primaryGold,
                                ),
                              ],
                            ),
                          ),

                          const SizedBox(height: 16),
                          Text(
                            '4. Detalles adicionales o evidencia (Opcional)',
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 8),
                          TextField(
                            controller: _motivoDetalleController,
                            maxLines: 2,
                            decoration: const InputDecoration(
                              hintText: 'Cuéntanos qué ocurrió con la prenda...',
                            ),
                          ),
                          const SizedBox(height: 10),
                          TextField(
                            controller: _evidenciaUrlController,
                            decoration: const InputDecoration(
                              hintText: 'URL de fotografía de evidencia (opcional)',
                              prefixIcon: Icon(Icons.link, size: 18),
                            ),
                          ),

                          if (_errorEnvio != null) ...[
                            const SizedBox(height: 12),
                            Text(
                              _errorEnvio!,
                              style: GoogleFonts.plusJakartaSans(fontSize: 12, color: AppTheme.error),
                            ),
                          ],
                        ],
                      ),
          ),

          if (_errorElegibilidad == null && !_cargandoElegibilidad)
            Padding(
              padding: const EdgeInsets.all(20),
              child: AuroraButton(
                text: _tipoResolucion == 'CAMBIO_PRENDA'
                    ? 'Confirmar Solicitud de Cambio de Talla'
                    : 'Enviar Solicitud de Devolución',
                isLoading: _enviando,
                onPressed: _enviarSolicitud,
                variant: AuroraButtonVariant.primary,
              ),
            ),
        ],
      ),
    );
  }
}
