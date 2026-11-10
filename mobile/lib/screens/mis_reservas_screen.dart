import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../services/auth_provider.dart';
import '../services/reserva_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_badge.dart';
import '../widgets/aurora_button.dart';
import '../widgets/aurora_empty_state.dart';
import 'auth_screens.dart';

class MisReservasScreen extends StatefulWidget {
  final VoidCallback? onIrAlCatalogo;

  const MisReservasScreen({super.key, this.onIrAlCatalogo});

  @override
  State<MisReservasScreen> createState() => _MisReservasScreenState();
}

class _MisReservasScreenState extends State<MisReservasScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ReservaService>().cargarMisReservas();
    });
  }

  Future<void> _cancelarReserva(ReservaModel reserva) async {
    final motivoCtrl = TextEditingController();

    final confirmar = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(
          'Cancelar reserva',
          style: GoogleFonts.playfairDisplay(fontSize: 18, fontWeight: FontWeight.w700),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '¿Estás seguro de que deseas cancelar tu reserva ${reserva.codigoReserva}? El stock reservado será liberado.',
              style: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: motivoCtrl,
              decoration: const InputDecoration(
                hintText: 'Motivo de la cancelación (opcional)',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Volver'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Cancelar reserva'),
          ),
        ],
      ),
    );

    if (confirmar == true && mounted) {
      final reservaService = context.read<ReservaService>();
      try {
        await reservaService.cancelarReserva(
          reserva.idReserva,
          motivo: motivoCtrl.text.trim(),
        );
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Reserva cancelada exitosamente.'),
              backgroundColor: AppTheme.success,
            ),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(e.toString().replaceAll('Exception: ', '')),
              backgroundColor: AppTheme.error,
            ),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final reservaService = context.watch<ReservaService>();

    if (!authProvider.estaAutenticado) {
      return Scaffold(
        backgroundColor: AppTheme.background,
        appBar: AppBar(title: const Text('Mis Reservas')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.calendar_month_outlined, size: 64, color: AppTheme.primaryGold),
                const SizedBox(height: 16),
                Text(
                  'Inicia sesión para ver tus reservas',
                  style: GoogleFonts.playfairDisplay(fontSize: 20, fontWeight: FontWeight.w700),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Agenda citas en tienda y mantén el seguimiento de tus prendas reservadas.',
                  style: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textSecondary),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                AuroraButton(
                  text: 'Iniciar sesión',
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const AuthScreen()),
                    );
                  },
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Text(
          'Mis Reservas',
          style: GoogleFonts.playfairDisplay(fontSize: 18, fontWeight: FontWeight.w700),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: () => reservaService.cargarMisReservas(),
        child: reservaService.cargando && reservaService.misReservas.isEmpty
            ? const Center(child: CircularProgressIndicator())
            : reservaService.misReservas.isEmpty
                ? AuroraEmptyState(
                    icon: Icons.calendar_today_outlined,
                    title: 'Aún no tienes reservas',
                    message: 'Elige prendas del catálogo y agenda una cita en tu sucursal favorita para probártelas.',
                    buttonText: 'Explorar catálogo',
                    onButtonPressed: widget.onIrAlCatalogo,
                  )
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: reservaService.misReservas.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 16),
                    itemBuilder: (context, index) {
                      final r = reservaService.misReservas[index];
                      final puedeCancelar = r.estado == 'PENDIENTE' || r.estado == 'CONFIRMADA';

                      DateTime? fechaVisita;
                      try {
                        fechaVisita = DateTime.tryParse(r.fechaHoraVisita);
                      } catch (_) {}

                      return Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AppTheme.surface,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: AppTheme.border),
                          boxShadow: const [
                            BoxShadow(
                              color: Color(0x06000000),
                              blurRadius: 8,
                              offset: Offset(0, 3),
                            ),
                          ],
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Encabezado de la reserva
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.center,
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        r.codigoReserva,
                                        style: GoogleFonts.plusJakartaSans(
                                          fontSize: 15,
                                          fontWeight: FontWeight.w700,
                                          color: AppTheme.primaryGold,
                                        ),
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                      Text(
                                        r.sucursal != null
                                            ? '${r.sucursal!.nombre} • ${r.sucursal!.ciudad}'
                                            : 'Sucursal Central',
                                        style: GoogleFonts.plusJakartaSans(
                                          fontSize: 12,
                                          color: AppTheme.textSecondary,
                                        ),
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    AuroraBadge(
                                      text: r.conPago
                                          ? '✓ Pre-pagada'
                                          : 'Pago en Tienda',
                                      backgroundColor: r.conPago
                                          ? AppTheme.successLight
                                          : AppTheme.goldLight,
                                      textColor: r.conPago
                                          ? AppTheme.success
                                          : AppTheme.primaryGold,
                                      isSmall: true,
                                    ),
                                    const SizedBox(width: 6),
                                    AuroraBadge.status(r.estado),
                                  ],
                                ),
                              ],
                            ),

                            const Divider(height: 20),

                            // Fecha y hora
                            Row(
                              children: [
                                const Icon(Icons.access_time, size: 16, color: AppTheme.primaryGold),
                                const SizedBox(width: 6),
                                Text(
                                  fechaVisita != null
                                      ? DateFormat("dd/MM/yyyy 'a las' HH:mm").format(fechaVisita)
                                      : r.fechaHoraVisita,
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                    color: AppTheme.textPrimary,
                                  ),
                                ),
                              ],
                            ),

                            const SizedBox(height: 12),

                            // Items reservados
                            ...r.items.map((item) {
                              return Padding(
                                padding: const EdgeInsets.symmetric(vertical: 4),
                                child: Row(
                                  children: [
                                    Container(
                                      width: 36,
                                      height: 44,
                                      decoration: BoxDecoration(
                                        color: AppTheme.surfaceVariant,
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      clipBehavior: Clip.antiAlias,
                                      child: item.imagenUrl != null
                                          ? Image.network(
                                              item.imagenUrl!,
                                              fit: BoxFit.cover,
                                              errorBuilder: (_, __, ___) => const Icon(Icons.checkroom, size: 16),
                                            )
                                          : const Icon(Icons.checkroom, size: 16),
                                    ),
                                    const SizedBox(width: 10),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            item.productoNombre,
                                            style: GoogleFonts.playfairDisplay(
                                              fontSize: 13,
                                              fontWeight: FontWeight.w700,
                                            ),
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                          Text(
                                            'Talla: ${item.talla} • Color: ${item.color} • Cant: ${item.cantidad}',
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
                              );
                            }),

                            if (r.observaciones != null && r.observaciones!.isNotEmpty) ...[
                              const SizedBox(height: 8),
                              Text(
                                'Nota: ${r.observaciones}',
                                style: GoogleFonts.plusJakartaSans(
                                  fontSize: 11,
                                  fontStyle: FontStyle.italic,
                                  color: AppTheme.textMuted,
                                ),
                              ),
                            ],

                            // Botón Cancelar si la reserva sigue activa
                            if (puedeCancelar) ...[
                              const SizedBox(height: 12),
                              Align(
                                alignment: Alignment.centerRight,
                                child: OutlinedButton(
                                  style: OutlinedButton.styleFrom(
                                    foregroundColor: AppTheme.error,
                                    side: const BorderSide(color: AppTheme.error),
                                    minimumSize: const Size(120, 36),
                                    padding: const EdgeInsets.symmetric(horizontal: 14),
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                                  ),
                                  onPressed: () => _cancelarReserva(r),
                                  child: const Text('Cancelar reserva', style: TextStyle(fontSize: 12)),
                                ),
                              ),
                            ],
                          ],
                        ),
                      );
                    },
                  ),
      ),
    );
  }
}
