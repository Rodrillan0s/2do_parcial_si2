import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';

class AuroraBadge extends StatelessWidget {
  final String text;
  final Color? backgroundColor;
  final Color? textColor;
  final bool isSmall;

  const AuroraBadge({
    super.key,
    required this.text,
    this.backgroundColor,
    this.textColor,
    this.isSmall = false,
  });

  factory AuroraBadge.status(String status) {
    Color bg;
    Color fg;

    switch (status.toUpperCase()) {
      case 'CONFIRMADA':
      case 'COMPLETADO':
      case 'ENTREGADO':
      case 'PAGADO':
      case 'DISPONIBLE':
      case 'ACTIVO':
        bg = AppTheme.successLight;
        fg = AppTheme.success;
        break;
      case 'PENDIENTE':
      case 'EN_PROCESO':
      case 'RESERVADO':
        bg = AppTheme.goldLight;
        fg = AppTheme.primaryGold;
        break;
      case 'PENDIENTE_ENTREGA':
        bg = const Color(0xFFE0F7FA);
        fg = const Color(0xFF00838F);
        break;
      case 'CANCELADO':
      case 'CANCELADA':
      case 'VENCIDA':
      case 'AGOTADO':
      case 'INACTIVO':
        bg = AppTheme.errorLight;
        fg = AppTheme.error;
        break;
      default:
        bg = AppTheme.infoLight;
        fg = AppTheme.info;
        break;
    }

    return AuroraBadge(
      text: status.replaceAll('_', ' '),
      backgroundColor: bg,
      textColor: fg,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: isSmall ? 8 : 10,
        vertical: isSmall ? 2 : 4,
      ),
      decoration: BoxDecoration(
        color: backgroundColor ?? AppTheme.goldLight,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        text,
        style: GoogleFonts.plusJakartaSans(
          fontSize: isSmall ? 10 : 11,
          fontWeight: FontWeight.w600,
          color: textColor ?? AppTheme.primaryGold,
          letterSpacing: 0.2,
        ),
      ),
    );
  }
}
