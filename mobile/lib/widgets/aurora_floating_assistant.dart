import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../screens/asistente_chat_modal.dart';

class AuroraFloatingAssistant extends StatelessWidget {
  const AuroraFloatingAssistant({super.key});

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton(
      heroTag: 'aurora_ai_bubble',
      onPressed: () {
        showModalBottomSheet(
          context: context,
          isScrollControlled: true,
          backgroundColor: Colors.transparent,
          builder: (ctx) => const AsistenteChatModal(),
        );
      },
      backgroundColor: AppTheme.primary,
      elevation: 4,
      shape: const CircleBorder(),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            width: 50,
            height: 50,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: AppTheme.accentGold, width: 1.5),
            ),
          ),
          const Icon(
            Icons.chat_bubble_outline_rounded,
            color: Colors.white,
            size: 24,
          ),
        ],
      ),
    );
  }
}
