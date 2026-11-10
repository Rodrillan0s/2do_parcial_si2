import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../services/auth_provider.dart';
import '../services/catalogo_service.dart';
import '../services/reserva_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_badge.dart';
import '../widgets/aurora_button.dart';
import 'auth_screens.dart';

class CrearReservaModal extends StatefulWidget {
  final DetallePrendaModel prenda;
  final VarianteModel varianteSeleccionada;

  const CrearReservaModal({
    super.key,
    required this.prenda,
    required this.varianteSeleccionada,
  });

  @override
  State<CrearReservaModal> createState() => _CrearReservaModalState();
}

class _CrearReservaModalState extends State<CrearReservaModal> {
  final TextEditingController _observacionesController = TextEditingController();
  List<DisponibilidadSucursalModel> _sucursales = [];
  DisponibilidadSucursalModel? _sucursalSeleccionada;
  DateTime _fechaSeleccionada = DateTime.now().add(const Duration(days: 1));
  TimeOfDay _horaSeleccionada = const TimeOfDay(hour: 15, minute: 0);

  bool _cargandoSucursales = true;
  bool _enviando = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _cargarSucursales();
  }

  @override
  void dispose() {
    _observacionesController.dispose();
    super.dispose();
  }

  Future<void> _cargarSucursales() async {
    final catalogo = context.read<CatalogoService>();
    final sucursales = await catalogo.consultarDisponibilidadVariante(
      widget.varianteSeleccionada.idVariante,
    );

    if (mounted) {
      setState(() {
        _sucursales = sucursales;
        final conStock = sucursales.where((s) => s.stockDisponible > 0).toList();
        if (conStock.isNotEmpty) {
          _sucursalSeleccionada = conStock.first;
        } else {
          _sucursalSeleccionada = null;
        }
        _cargandoSucursales = false;
      });
    }
  }

  Future<void> _seleccionarFecha() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _fechaSeleccionada,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 7)),
      builder: (context, child) {
        return Theme(
          data: ThemeData.light().copyWith(
            colorScheme: const ColorScheme.light(
              primary: AppTheme.primary,
              onPrimary: Colors.white,
              surface: Colors.white,
            ),
          ),
          child: child!,
        );
      },
    );

    if (picked != null) {
      setState(() {
        _fechaSeleccionada = picked;
      });
    }
  }

  Future<void> _seleccionarHora() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _horaSeleccionada,
      builder: (context, child) {
        return Theme(
          data: ThemeData.light().copyWith(
            colorScheme: const ColorScheme.light(
              primary: AppTheme.primary,
              onPrimary: Colors.white,
              surface: Colors.white,
            ),
          ),
          child: child!,
        );
      },
    );

    if (picked != null) {
      setState(() {
        _horaSeleccionada = picked;
      });
    }
  }

  Future<void> _confirmarReserva() async {
    final authProvider = context.read<AuthProvider>();
    if (!authProvider.estaAutenticado) {
      Navigator.pop(context);
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => const AuthScreen()),
      );
      return;
    }

    if (_sucursalSeleccionada == null || _sucursalSeleccionada!.stockDisponible <= 0) {
      setState(() => _error = 'Por favor selecciona una sucursal con disponibilidad.');
      return;
    }

    if (_horaSeleccionada.hour < 9 || (_horaSeleccionada.hour >= 21 && _horaSeleccionada.minute > 0)) {
      setState(() => _error = 'El horario comercial de boutique es de 09:00 a 21:00. Selecciona una hora dentro de este rango.');
      return;
    }

    final fechaHora = DateTime(
      _fechaSeleccionada.year,
      _fechaSeleccionada.month,
      _fechaSeleccionada.day,
      _horaSeleccionada.hour,
      _horaSeleccionada.minute,
    );

    if (fechaHora.isBefore(DateTime.now())) {
      setState(() => _error = 'La fecha y hora de la cita debe ser posterior al momento actual.');
      return;
    }

    setState(() {
      _enviando = true;
      _error = null;
    });

    final fechaFormateada = DateFormat("yyyy-MM-dd HH:mm:ss").format(fechaHora);

    final reservaService = context.read<ReservaService>();

    try {
      final reserva = await reservaService.crearReserva(
        idSucursal: _sucursalSeleccionada!.idSucursal,
        fechaHoraVisita: fechaFormateada,
        items: [
          {
            'id_variante': widget.varianteSeleccionada.idVariante,
            'cantidad': 1,
          }
        ],
        observaciones: _observacionesController.text.trim(),
        idEmpresa: widget.prenda.idEmpresa,
        conPago: false,
        montoPagado: 0.0,
      );

      if (mounted) {
        Navigator.pop(context);
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            title: Row(
              children: [
                const Icon(
                  Icons.event_available,
                  color: AppTheme.primaryGold,
                  size: 26,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '¡Cita Confirmada!',
                    style: GoogleFonts.playfairDisplay(fontSize: 19, fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Tu cita en probador ha sido agendada exitosamente (100% gratuita):',
                  style: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textSecondary),
                ),
                const SizedBox(height: 8),
                Center(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      color: AppTheme.goldLight,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppTheme.primaryGold.withValues(alpha: 0.3)),
                    ),
                    child: Text(
                      reserva.codigoReserva,
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.primaryGold,
                        letterSpacing: 1,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'Te esperamos en ${_sucursalSeleccionada!.nombre} el día ${DateFormat("dd/MM/yyyy 'a las' HH:mm").format(fechaHora)}.',
                  style: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textPrimary),
                ),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceVariant,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.info_outline,
                        size: 16,
                        color: AppTheme.primaryGold,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Sin costo previo. Pruébatela en tienda con tranquilidad y abona únicamente si decides comprarla.',
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
    } catch (e) {
      if (mounted) {
        setState(() {
          _enviando = false;
          _error = e.toString().replaceAll('Exception: ', '');
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.88,
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        children: [
          // Barra de Arrastre
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
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Reservar cita en tienda',
                  style: GoogleFonts.playfairDisplay(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
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
            child: _cargandoSucursales
                ? const Center(child: CircularProgressIndicator())
                : ListView(
                    padding: const EdgeInsets.all(20),
                    children: [
                      // Resumen de la prenda a reservar
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceVariant,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: Row(
                          children: [
                            Container(
                              width: 50,
                              height: 60,
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(8),
                                color: Colors.white,
                              ),
                              clipBehavior: Clip.antiAlias,
                              child: widget.prenda.imagenPrincipal != null
                                  ? Image.network(
                                      widget.prenda.imagenPrincipal!,
                                      fit: BoxFit.cover,
                                      errorBuilder: (_, __, ___) => const Icon(Icons.checkroom),
                                    )
                                  : const Icon(Icons.checkroom),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    widget.prenda.nombre,
                                    style: GoogleFonts.playfairDisplay(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w700,
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Talla: ${widget.varianteSeleccionada.tallaNombre} • Color: ${widget.varianteSeleccionada.colorNombre}',
                                    style: GoogleFonts.plusJakartaSans(
                                      fontSize: 12,
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

                      // Selector de Sucursal
                      Text(
                        '1. Selecciona la sucursal para tu cita',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 8),

                      if (_sucursales.isEmpty)
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppTheme.surfaceVariant,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            'No hay sucursales registradas para esta tienda.',
                            style: GoogleFonts.plusJakartaSans(
                                fontSize: 12, color: AppTheme.textSecondary),
                          ),
                        )
                      else ...[
                        if (_sucursales.every((s) => s.stockDisponible <= 0))
                          Container(
                            margin: const EdgeInsets.only(bottom: 12),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AppTheme.goldLight,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                  color: AppTheme.primaryGold
                                      .withValues(alpha: 0.3)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.info_outline,
                                    color: AppTheme.primaryGold, size: 20),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    'Esta prenda se encuentra agotada en todas las sucursales físicas para cita presencial.',
                                    style: GoogleFonts.plusJakartaSans(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w600,
                                        color: AppTheme.textPrimary),
                                  ),
                                ),
                              ],
                            ),
                          ),

                        ..._sucursales.map((s) {
                          final tieneStock = s.stockDisponible > 0;
                          final isSelected =
                              _sucursalSeleccionada?.idSucursal == s.idSucursal;
                          final stockLabel = s.stockDisponible <= 0
                              ? 'Agotado en esta sucursal'
                              : s.stockDisponible <= 3
                                  ? '⚠ Últimas unidades'
                                  : '✓ Disponible';
                          final badgeColor = s.stockDisponible <= 0
                              ? AppTheme.errorLight
                              : s.stockDisponible <= 3
                                  ? AppTheme.goldLight
                                  : AppTheme.successLight;
                          final textColor = s.stockDisponible <= 0
                              ? AppTheme.error
                              : s.stockDisponible <= 3
                                  ? AppTheme.primaryGold
                                  : AppTheme.success;

                          return Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: InkWell(
                              onTap: tieneStock
                                  ? () =>
                                      setState(() => _sucursalSeleccionada = s)
                                  : () {
                                      ScaffoldMessenger.of(context)
                                          .showSnackBar(
                                        SnackBar(
                                          content: Text(
                                            '${s.nombre} no cuenta con existencias para esta talla/color.',
                                          ),
                                          duration:
                                              const Duration(seconds: 2),
                                          backgroundColor: AppTheme.error,
                                        ),
                                      );
                                    },
                              borderRadius: BorderRadius.circular(14),
                              child: AnimatedOpacity(
                                duration: const Duration(milliseconds: 200),
                                opacity: tieneStock ? 1.0 : 0.55,
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 14, vertical: 12),
                                  decoration: BoxDecoration(
                                    color: isSelected
                                        ? AppTheme.goldLight
                                        : tieneStock
                                            ? AppTheme.surface
                                            : AppTheme.surfaceVariant
                                                .withValues(alpha: 0.6),
                                    borderRadius: BorderRadius.circular(14),
                                    border: Border.all(
                                      color: isSelected
                                          ? AppTheme.primaryGold
                                          : tieneStock
                                              ? AppTheme.border
                                              : AppTheme.border
                                                  .withValues(alpha: 0.5),
                                      width: isSelected ? 1.5 : 1,
                                    ),
                                  ),
                                  child: Row(
                                    children: [
                                      Icon(
                                        tieneStock
                                            ? (isSelected
                                                ? Icons.radio_button_checked
                                                : Icons.radio_button_off)
                                            : Icons.block,
                                        color: isSelected
                                            ? AppTheme.primaryGold
                                            : tieneStock
                                                ? AppTheme.textMuted
                                                : AppTheme.error,
                                        size: 20,
                                      ),
                                      const SizedBox(width: 12),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              '${s.nombre}${s.ciudad != null ? ' (${s.ciudad})' : ''}',
                                              style:
                                                  GoogleFonts.plusJakartaSans(
                                                fontSize: 13,
                                                fontWeight: isSelected
                                                    ? FontWeight.w700
                                                    : FontWeight.w600,
                                                color: tieneStock
                                                    ? AppTheme.textPrimary
                                                    : AppTheme.textMuted,
                                              ),
                                            ),
                                            if (s.direccion.isNotEmpty) ...[
                                              const SizedBox(height: 2),
                                              Text(
                                                s.direccion,
                                                style: GoogleFonts
                                                    .plusJakartaSans(
                                                  fontSize: 11,
                                                  color:
                                                      AppTheme.textSecondary,
                                                ),
                                                maxLines: 1,
                                                overflow:
                                                    TextOverflow.ellipsis,
                                              ),
                                            ],
                                          ],
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      AuroraBadge(
                                        text: stockLabel,
                                        backgroundColor: badgeColor,
                                        textColor: textColor,
                                        isSmall: true,
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

                      // Selector de Fecha y Hora
                      Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Fecha de visita',
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                InkWell(
                                  onTap: _seleccionarFecha,
                                  borderRadius: BorderRadius.circular(12),
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                                    decoration: BoxDecoration(
                                      border: Border.all(color: AppTheme.border),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Row(
                                      children: [
                                        const Icon(Icons.calendar_today_outlined, size: 16, color: AppTheme.primaryGold),
                                        const SizedBox(width: 8),
                                        Text(
                                          DateFormat('dd/MM/yyyy').format(_fechaSeleccionada),
                                          style: GoogleFonts.plusJakartaSans(fontSize: 13, fontWeight: FontWeight.w600),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Horario aproximado',
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                InkWell(
                                  onTap: _seleccionarHora,
                                  borderRadius: BorderRadius.circular(12),
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                                    decoration: BoxDecoration(
                                      border: Border.all(color: AppTheme.border),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Row(
                                      children: [
                                        const Icon(Icons.access_time, size: 16, color: AppTheme.primaryGold),
                                        const SizedBox(width: 8),
                                        Text(
                                          _horaSeleccionada.format(context),
                                          style: GoogleFonts.plusJakartaSans(fontSize: 13, fontWeight: FontWeight.w600),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(height: 20),

                      // Modalidad de Reserva: Cita 100% Gratuita en Probador Privado
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: AppTheme.goldLight.withValues(alpha: 0.6),
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(
                            color: AppTheme.primaryGold.withValues(alpha: 0.35),
                          ),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Icon(
                              Icons.room_service_outlined,
                              color: AppTheme.primaryGold,
                              size: 22,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Text(
                                        'Cita Presencial en Probador VIP',
                                        style: GoogleFonts.plusJakartaSans(
                                          fontSize: 13,
                                          fontWeight: FontWeight.w700,
                                          color: AppTheme.textPrimary,
                                        ),
                                      ),
                                      const SizedBox(width: 6),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: AppTheme.success.withValues(alpha: 0.15),
                                          borderRadius: BorderRadius.circular(6),
                                        ),
                                        child: Text(
                                          '100% GRATIS',
                                          style: GoogleFonts.plusJakartaSans(
                                            fontSize: 9,
                                            fontWeight: FontWeight.w800,
                                            color: AppTheme.success,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 3),
                                  Text(
                                    'Apartamos tu prenda en la sucursal seleccionada para que te la pruebes cómodamente sin costo previo ni compromiso de compra.',
                                    style: GoogleFonts.plusJakartaSans(
                                      fontSize: 11,
                                      color: AppTheme.textSecondary,
                                      height: 1.35,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),

                      // Observaciones
                      Text(
                        'Observaciones o solicitudes especiales',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _observacionesController,
                        maxLines: 3,
                        decoration: const InputDecoration(
                          hintText: 'Ej. Deseo probarme también con calzado de tacón...',
                        ),
                      ),
                    ],
                  ),
          ),

          // Botón Confirmar
          Padding(
            padding: const EdgeInsets.all(20),
            child: AuroraButton(
              text: 'Confirmar reserva',
              isLoading: _enviando,
              onPressed: (_sucursalSeleccionada == null ||
                      _sucursalSeleccionada!.stockDisponible <= 0)
                  ? null
                  : _confirmarReserva,
              variant: AuroraButtonVariant.primary,
            ),
          ),
        ],
      ),
    );
  }
}
