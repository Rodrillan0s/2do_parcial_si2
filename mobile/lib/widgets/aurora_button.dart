import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';

enum AuroraButtonVariant { primary, gold, outline, text }

class AuroraButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final bool isLoading;
  final IconData? icon;
  final AuroraButtonVariant variant;
  final double? width;
  final double height;
  final double? fontSize;

  const AuroraButton({
    super.key,
    required this.text,
    required this.onPressed,
    this.isLoading = false,
    this.icon,
    this.variant = AuroraButtonVariant.primary,
    this.width,
    this.height = 48,
    this.fontSize,
  });

  @override
  Widget build(BuildContext context) {
    Widget content;
    if (isLoading) {
      content = const SizedBox(
        width: 18,
        height: 18,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
        ),
      );
    } else {
      content = Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 16),
            const SizedBox(width: 6),
          ],
          Flexible(
            child: Text(
              text,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: GoogleFonts.plusJakartaSans(
                fontSize: fontSize ?? 13,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.2,
              ),
            ),
          ),
        ],
      );
    }

    Color bgColor;
    Color fgColor;
    BorderSide borderSide = BorderSide.none;

    switch (variant) {
      case AuroraButtonVariant.primary:
        bgColor = AppTheme.primary;
        fgColor = Colors.white;
        break;
      case AuroraButtonVariant.gold:
        bgColor = AppTheme.primaryGold;
        fgColor = Colors.white;
        break;
      case AuroraButtonVariant.outline:
        bgColor = Colors.transparent;
        fgColor = AppTheme.textPrimary;
        borderSide = const BorderSide(color: AppTheme.borderStrong, width: 1.2);
        break;
      case AuroraButtonVariant.text:
        bgColor = Colors.transparent;
        fgColor = AppTheme.primaryGold;
        break;
    }

    final buttonStyle = ElevatedButton.styleFrom(
      backgroundColor: bgColor,
      foregroundColor: fgColor,
      elevation: 0,
      side: borderSide,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
    );

    return SizedBox(
      width: width ?? double.infinity,
      height: height,
      child: ElevatedButton(
        style: buttonStyle,
        onPressed: isLoading ? null : onPressed,
        child: content,
      ),
    );
  }
}
