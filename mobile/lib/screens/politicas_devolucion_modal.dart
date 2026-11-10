import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../services/devoluciones_service.dart';
import '../theme/app_theme.dart';

class PoliticasDevolucionModal extends StatefulWidget {
  final int? idEmpresa;

  const PoliticasDevolucionModal({super.key, this.idEmpresa});

  @override
  State<PoliticasDevolucionModal> createState() => _PoliticasDevolucionModalState();
}

class _PoliticasDevolucionModalState extends State<PoliticasDevolucionModal> {
  bool _cargando = true;
  PoliticaDevolucionModel? _politica;

  @override
  void initState() {
    super.initState();
    _cargarPoliticas();
  }

  Future<void> _cargarPoliticas() async {
    final service = context.read<DevolucionesService>();
    final pol = await service.consultarPoliticasTienda(idEmpresa: widget.idEmpresa);
    if (mounted) {
      setState(() {
        _politica = pol;
        _cargando = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.75,
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        children: [
          // Drag handle
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
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
            child: Row(
              children: [
                const Icon(Icons.policy_outlined, color: AppTheme.primaryGold, size: 24),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Políticas de Devolución & Garantía',
                    style: GoogleFonts.playfairDisplay(fontSize: 18, fontWeight: FontWeight.w700),
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
            child: _cargando
                ? const Center(child: CircularProgressIndicator())
                : ListView(
                    padding: const EdgeInsets.all(20),
                    children: [
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: AppTheme.goldLight.withValues(alpha: 0.6),
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(color: AppTheme.primaryGold.withValues(alpha: 0.3)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.gavel, color: AppTheme.primaryGold, size: 24),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Ley General de los Derechos de las Usuarias y los Usuarios y de las Consumidoras y los Consumidores (Ley N° 453)',
                                    style: GoogleFonts.plusJakartaSans(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w700,
                                      color: AppTheme.textPrimary,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Aurora Store garantiza el derecho a cambio, saldo a favor o reparación en caso de defectos o vicios ocultos de las prendas.',
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
                      const SizedBox(height: 16),

                      _buildPolicyCard(
                        icon: Icons.calendar_month_outlined,
                        title: 'Plazo Máximo para Devoluciones',
                        description: 'Cuentas con hasta ${_politica?.diasMaximosDevolucion ?? 7} días calendario a partir de la entrega de tu pedido para iniciar tu solicitud.',
                      ),
                      const SizedBox(height: 12),

                      _buildPolicyCard(
                        icon: Icons.checkroom_outlined,
                        title: 'Condición de la Prenda',
                        description: _politica?.requiereEtiquetaOriginal == true
                            ? 'La prenda debe conservarse con sus etiquetas intactas, sin signos de lavado o uso indebido.'
                            : 'La prenda debe estar en buen estado para su revisión en sucursal.',
                      ),
                      const SizedBox(height: 12),

                      _buildPolicyCard(
                        icon: Icons.credit_score_outlined,
                        title: 'Saldos a Favor y Vouchers',
                        description: 'Si eliges saldo a favor, recibirás un cupón digital instantáneo sin fecha de caducidad restrictiva para canjear en la misma tienda.',
                      ),
                      const SizedBox(height: 12),

                      _buildPolicyCard(
                        icon: Icons.sync_alt_outlined,
                        title: 'Cambios Presenciales',
                        description: 'Puedes acercarte a cualquiera de nuestras sucursales con tu código de solicitud aprobada para probarte y retirar la nueva prenda.',
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildPolicyCard({
    required IconData icon,
    required String title,
    required String description,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: AppTheme.primaryGold, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
