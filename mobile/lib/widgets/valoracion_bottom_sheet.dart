import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../services/valoracion_service.dart';
import 'aurora_button.dart';

class ValoracionBottomSheet extends StatefulWidget {
  final int? idPedido;
  final int? idVenta;
  final int? idReserva;
  final int? idProducto;
  final String? nombreProducto;
  final String? imagenProducto;
  final String? codigoPedido;
  final String? nombreSucursal;

  const ValoracionBottomSheet({
    super.key,
    this.idPedido,
    this.idVenta,
    this.idReserva,
    this.idProducto,
    this.nombreProducto,
    this.imagenProducto,
    this.codigoPedido,
    this.nombreSucursal,
  });

  static Future<bool?> mostrar(
    BuildContext context, {
    int? idPedido,
    int? idVenta,
    int? idReserva,
    int? idProducto,
    String? nombreProducto,
    String? imagenProducto,
    String? codigoPedido,
    String? nombreSucursal,
  }) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => ValoracionBottomSheet(
        idPedido: idPedido,
        idVenta: idVenta,
        idReserva: idReserva,
        idProducto: idProducto,
        nombreProducto: nombreProducto,
        imagenProducto: imagenProducto,
        codigoPedido: codigoPedido,
        nombreSucursal: nombreSucursal,
      ),
    );
  }

  @override
  State<ValoracionBottomSheet> createState() => _ValoracionBottomSheetState();
}

class _ValoracionBottomSheetState extends State<ValoracionBottomSheet> {
  final _valoracionService = ValoracionService();
  final _comentarioController = TextEditingController();
  final _motivoController = TextEditingController();

  int _estrellas = 0;
  String _motivoSeleccionadoRapido = '';
  bool _enviando = false;
  String? _mensajeError;

  final List<String> _motivosPredefinidos = const [
    'Defecto en tela o costura',
    'Talla no coincide con la guía',
    'Demora en la entrega',
    'Atención deficiente',
    'Producto dañado o diferente',
  ];

  @override
  void dispose() {
    _comentarioController.dispose();
    _motivoController.dispose();
    super.dispose();
  }

  void _seleccionarEstrellas(int n) {
    HapticFeedback.lightImpact();
    setState(() {
      _estrellas = n;
      _mensajeError = null;
      if (n != 1) {
        _motivoController.clear();
        _motivoSeleccionadoRapido = '';
      }
    });
  }

  bool get _esUnaEstrella => _estrellas == 1;

  bool get _puedeEnviar {
    if (_enviando) return false;
    if (_estrellas < 1) return false;
    if (_esUnaEstrella) {
      return _motivoController.text.trim().length >= 5 || _motivoSeleccionadoRapido.isNotEmpty;
    }
    return true;
  }

  Future<void> _enviar() async {
    if (!_puedeEnviar) return;

    setState(() {
      _enviando = true;
      _mensajeError = null;
    });

    try {
      String? motivoFinal;
      if (_esUnaEstrella) {
        final texto = _motivoController.text.trim();
        motivoFinal = texto.isNotEmpty ? texto : _motivoSeleccionadoRapido;
        if (_motivoSeleccionadoRapido.isNotEmpty && !motivoFinal.contains(_motivoSeleccionadoRapido)) {
          motivoFinal = '$_motivoSeleccionadoRapido: $motivoFinal';
        }
      }

      await _valoracionService.crearValoracion(
        puntuacion: _estrellas,
        comentario: _comentarioController.text.trim().isNotEmpty
            ? _comentarioController.text.trim()
            : null,
        motivoNegativo: motivoFinal,
        idProducto: widget.idProducto,
        idPedido: widget.idPedido,
        idVenta: widget.idVenta,
        idReserva: widget.idReserva,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('✓ ¡Gracias por tu valoración!'),
            backgroundColor: AppTheme.success,
          ),
        );
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _enviando = false;
          _mensajeError = 'No se pudo registrar la valoración. Verifica tu conexión.';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;

    return Container(
      padding: EdgeInsets.only(
        top: 16,
        left: 20,
        right: 20,
        bottom: 24 + bottomInset,
      ),
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Pill de agarre
            Center(
              child: Container(
                width: 44,
                height: 4,
                decoration: BoxDecoration(
                  color: AppTheme.borderStrong,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Encabezado
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '✦ TU OPINIÓN CUENTA',
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1.2,
                        color: AppTheme.primaryGold,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Valorar Experiencia',
                      style: GoogleFonts.playfairDisplay(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                  ],
                ),
                // Botón Cerrar (Flujo A1: Cierre voluntario sin registrar)
                IconButton(
                  onPressed: () => Navigator.of(context).pop(false),
                  icon: const Icon(Icons.close, size: 20),
                  color: AppTheme.textSecondary,
                  tooltip: 'Cerrar sin calificar',
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Card informativa de la prenda o compra
            if (widget.nombreProducto != null || widget.codigoPedido != null)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceVariant,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Row(
                  children: [
                    if (widget.imagenProducto != null && widget.imagenProducto!.isNotEmpty)
                      ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: Image.network(
                          widget.imagenProducto!,
                          width: 44,
                          height: 44,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => Container(
                            width: 44,
                            height: 44,
                            color: AppTheme.border,
                            child: const Icon(Icons.checkroom, size: 20, color: AppTheme.textMuted),
                          ),
                        ),
                      )
                    else
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          color: AppTheme.goldLight,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.shopping_bag_outlined, color: AppTheme.primaryGold, size: 22),
                      ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (widget.nombreProducto != null)
                            Text(
                              widget.nombreProducto!,
                              style: GoogleFonts.plusJakartaSans(
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.textPrimary,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          Text(
                            [
                              if (widget.codigoPedido != null) 'Orden: ${widget.codigoPedido}',
                              if (widget.nombreSucursal != null) widget.nombreSucursal,
                            ].join(' • '),
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 11,
                              color: AppTheme.textMuted,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

            const SizedBox(height: 18),

            // Selector de Estrellas
            Center(
              child: Text(
                'Toca para seleccionar tu puntuación',
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textSecondary,
                ),
              ),
            ),
            const SizedBox(height: 8),

            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: List.generate(5, (index) {
                final estrellaNum = index + 1;
                final estaMarcada = estrellaNum <= _estrellas;
                return GestureDetector(
                  onTap: () => _seleccionarEstrellas(estrellaNum),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 6),
                    child: Icon(
                      estaMarcada ? Icons.star_rounded : Icons.star_outline_rounded,
                      size: 40,
                      color: estaMarcada ? const Color(0xFFF59E0B) : AppTheme.borderStrong,
                    ),
                  ),
                );
              }),
            ),

            const SizedBox(height: 6),
            Center(
              child: Text(
                _textoEstrellas(_estrellas),
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: _colorEstrellas(_estrellas),
                ),
              ),
            ),

            // Flujo Alternativo A2: Panel Dinámico para 1 Estrella
            AnimatedSize(
              duration: const Duration(milliseconds: 250),
              curve: Curves.easeInOut,
              child: _esUnaEstrella
                  ? Container(
                      margin: const EdgeInsets.only(top: 16),
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AppTheme.errorLight,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Icon(Icons.info_outline, size: 16, color: AppTheme.error),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  'Queremos darte una solución',
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                    color: AppTheme.error,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Por favor indícanos qué problema tuviste para que el equipo lo atienda de inmediato:',
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 11,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                          const SizedBox(height: 8),
                          // Chips rápidos
                          Wrap(
                            spacing: 6,
                            runSpacing: 6,
                            children: _motivosPredefinidos.map((m) {
                              final sel = _motivoSeleccionadoRapido == m;
                              return ChoiceChip(
                                label: Text(
                                  m,
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 11,
                                    color: sel ? Colors.white : AppTheme.textPrimary,
                                    fontWeight: sel ? FontWeight.w600 : FontWeight.w400,
                                  ),
                                ),
                                selected: sel,
                                selectedColor: AppTheme.error,
                                backgroundColor: Colors.white,
                                onSelected: (_) {
                                  setState(() {
                                    _motivoSeleccionadoRapido = m;
                                    if (_motivoController.text.isEmpty) {
                                      _motivoController.text = m;
                                    }
                                  });
                                },
                              );
                            }).toList(),
                          ),
                          const SizedBox(height: 8),
                          TextField(
                            controller: _motivoController,
                            maxLines: 2,
                            decoration: InputDecoration(
                              hintText: 'Detalla qué sucedió (obligatorio)...',
                              hintStyle: GoogleFonts.plusJakartaSans(fontSize: 12, color: AppTheme.textMuted),
                              fillColor: Colors.white,
                              filled: true,
                              contentPadding: const EdgeInsets.all(10),
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: BorderSide(color: AppTheme.error.withValues(alpha: 0.4)),
                              ),
                            ),
                            style: GoogleFonts.plusJakartaSans(fontSize: 12),
                            onChanged: (_) => setState(() {}),
                          ),
                        ],
                      ),
                    )
                  : const SizedBox.shrink(),
            ),

            // Comentario Libre (para 2 a 5 estrellas)
            if (!_esUnaEstrella && _estrellas > 1) ...[
              const SizedBox(height: 14),
              TextField(
                controller: _comentarioController,
                maxLines: 2,
                decoration: InputDecoration(
                  hintText: 'Comentario opcional sobre el calce, calidad o entrega...',
                  hintStyle: GoogleFonts.plusJakartaSans(fontSize: 12, color: AppTheme.textMuted),
                  fillColor: AppTheme.surfaceVariant,
                  filled: true,
                  contentPadding: const EdgeInsets.all(12),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                    borderSide: const BorderSide(color: AppTheme.border),
                  ),
                ),
                style: GoogleFonts.plusJakartaSans(fontSize: 12),
              ),
            ],

            if (_mensajeError != null) ...[
              const SizedBox(height: 10),
              Text(
                _mensajeError!,
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 11,
                  color: AppTheme.error,
                  fontWeight: FontWeight.w500,
                ),
                textAlign: TextAlign.center,
              ),
            ],

            const SizedBox(height: 20),

            // Acciones: Enviar y Omitir
            Row(
              children: [
                // Flujo A1: Omitir
                Expanded(
                  flex: 2,
                  child: TextButton(
                    onPressed: _enviando ? null : () => Navigator.of(context).pop(false),
                    child: Text(
                      'Omitir por ahora',
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  flex: 3,
                  child: AuroraButton(
                    text: 'Enviar Valoración',
                    variant: AuroraButtonVariant.gold,
                    isLoading: _enviando,
                    onPressed: _puedeEnviar ? _enviar : null,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _textoEstrellas(int n) {
    switch (n) {
      case 1:
        return '1 estrella — Muy Insatisfecho';
      case 2:
        return '2 estrellas — Insatisfecho';
      case 3:
        return '3 estrellas — Aceptable';
      case 4:
        return '4 estrellas — Bueno';
      case 5:
        return '5 estrellas — ¡Excelente!';
      default:
        return '';
    }
  }

  Color _colorEstrellas(int n) {
    if (n == 1) return AppTheme.error;
    if (n < 4) return AppTheme.primaryGold;
    return AppTheme.success;
  }
}
