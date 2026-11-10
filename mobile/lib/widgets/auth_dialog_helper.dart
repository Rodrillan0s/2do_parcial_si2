import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../screens/auth_screens.dart';
import '../theme/app_theme.dart';
import 'aurora_button.dart';

class AuthDialogHelper {
  static Future<bool?> mostrarModalLoginRequerido(
    BuildContext context, {
    String titulo = 'Inicia sesión para continuar',
    String mensaje =
        'Para añadir prendas a tu bolsa o gestionar compras y citas exclusivas, por favor ingresa con tu cuenta de Aurora Store.',
    String? accionRequerida,
  }) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
        decoration: const BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
          boxShadow: [
            BoxShadow(
              color: Color(0x20000000),
              blurRadius: 20,
              offset: Offset(0, -4),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            // Asa superior
            Container(
              width: 44,
              height: 4,
              decoration: BoxDecoration(
                color: AppTheme.borderStrong,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 24),

            // Ícono editorial
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: AppTheme.goldLight,
                shape: BoxShape.circle,
                border: Border.all(
                  color: AppTheme.primaryGold.withValues(alpha: 0.3),
                  width: 2,
                ),
              ),
              child: const Icon(
                Icons.lock_person_outlined,
                size: 32,
                color: AppTheme.primaryGold,
              ),
            ),
            const SizedBox(height: 16),

            // Título
            Text(
              titulo,
              textAlign: TextAlign.center,
              style: GoogleFonts.playfairDisplay(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 8),

            // Mensaje
            Text(
              mensaje,
              textAlign: TextAlign.center,
              style: GoogleFonts.plusJakartaSans(
                fontSize: 13,
                height: 1.5,
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: 24),

            // Botón Iniciar Sesión
            AuroraButton(
              text: 'Iniciar sesión',
              icon: Icons.login_outlined,
              onPressed: () {
                Navigator.pop(ctx, true);
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const AuthScreen()),
                );
              },
            ),
            const SizedBox(height: 10),

            // Botón Registrarse
            AuroraButton(
              text: 'Crear cuenta nueva',
              variant: AuroraButtonVariant.outline,
              icon: Icons.person_add_outlined,
              onPressed: () {
                Navigator.pop(ctx, true);
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const AuthScreen(initialIsRegister: true),
                  ),
                );
              },
            ),
            const SizedBox(height: 12),

            // Cerrar
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: Text(
                'Continuar explorando el catálogo',
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textMuted,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
