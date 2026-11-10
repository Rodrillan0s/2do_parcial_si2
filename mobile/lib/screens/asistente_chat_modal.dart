import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../services/asistente_service.dart';
import '../theme/app_theme.dart';
import 'detalle_producto_screen.dart';

class AsistenteChatModal extends StatefulWidget {
  const AsistenteChatModal({super.key});

  @override
  State<AsistenteChatModal> createState() => _AsistenteChatModalState();
}

class _AsistenteChatModalState extends State<AsistenteChatModal> {
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _enviarMensaje() {
    final text = _inputController.text.trim();
    if (text.isEmpty) return;

    _inputController.clear();
    final asistente = context.read<AsistenteService>();
    asistente.enviarMensaje(text);
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final asistente = context.watch<AsistenteService>();

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

          // Cabecera del Asistente
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: const BoxDecoration(
                    color: AppTheme.goldLight,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.auto_awesome, size: 20, color: AppTheme.primaryGold),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Aurora Advisor',
                        style: GoogleFonts.playfairDisplay(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      Text(
                        'Asesor Inteligente de Moda',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 11,
                          color: AppTheme.textMuted,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.refresh_outlined, size: 20),
                  tooltip: 'Reiniciar conversación',
                  onPressed: () => asistente.limpiarConversacion(),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ),

          // Selector de Modelo DeepSeek (V3 Chat vs R1 Reasoner)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 2, 20, 8),
            child: Row(
              children: [
                Text(
                  'Modelo IA:',
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textMuted,
                  ),
                ),
                const SizedBox(width: 8),
                InkWell(
                  onTap: () => asistente.setModelo('deepseek-chat'),
                  borderRadius: BorderRadius.circular(16),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: asistente.modeloSeleccionado == 'deepseek-chat'
                          ? AppTheme.primary
                          : AppTheme.surfaceVariant,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.flash_on,
                          size: 13,
                          color: asistente.modeloSeleccionado == 'deepseek-chat'
                              ? AppTheme.primaryGold
                              : AppTheme.textSecondary,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          '⚡ V3 Chat',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: asistente.modeloSeleccionado == 'deepseek-chat'
                                ? Colors.white
                                : AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                InkWell(
                  onTap: () => asistente.setModelo('deepseek-reasoner'),
                  borderRadius: BorderRadius.circular(16),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: asistente.modeloSeleccionado == 'deepseek-reasoner'
                          ? AppTheme.primary
                          : AppTheme.surfaceVariant,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.psychology,
                          size: 13,
                          color: asistente.modeloSeleccionado == 'deepseek-reasoner'
                              ? AppTheme.primaryGold
                              : AppTheme.textSecondary,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          '🧠 R1 Reasoner',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: asistente.modeloSeleccionado == 'deepseek-reasoner'
                                ? Colors.white
                                : AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1),

          // Mensajes de la conversación
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: asistente.mensajes.length,
              itemBuilder: (context, index) {
                final msg = asistente.mensajes[index];
                final isUser = msg.role == 'user';

                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (!isUser) ...[
                        const CircleAvatar(
                          radius: 14,
                          backgroundColor: AppTheme.primary,
                          child: Icon(Icons.diamond_outlined, size: 14, color: AppTheme.accentGold),
                        ),
                        const SizedBox(width: 8),
                      ],
                      Flexible(
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          decoration: BoxDecoration(
                            color: isUser ? AppTheme.primary : AppTheme.surfaceVariant,
                            borderRadius: BorderRadius.only(
                              topLeft: const Radius.circular(16),
                              topRight: const Radius.circular(16),
                              bottomLeft: Radius.circular(isUser ? 16 : 4),
                              bottomRight: Radius.circular(isUser ? 4 : 16),
                            ),
                            border: isUser ? null : Border.all(color: AppTheme.border),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                msg.content,
                                style: GoogleFonts.plusJakartaSans(
                                  fontSize: 13,
                                  color: isUser ? Colors.white : AppTheme.textPrimary,
                                  height: 1.4,
                                ),
                              ),
                              // Renderizar prendas estructuradas si el asistente devolvió productos
                              if (!isUser && msg.tipo == 'productos' && msg.datos is List) ...[
                                const SizedBox(height: 10),
                                ...((msg.datos as List).take(3)).map((prodMap) {
                                  final pId = prodMap['id_producto'];
                                  final pNom = prodMap['nombre'] ?? 'Prenda';
                                  final pPre = prodMap['precio']?.toString() ?? '';
                                  return InkWell(
                                    onTap: () {
                                      if (pId != null) {
                                        Navigator.pop(context);
                                        Navigator.push(
                                          context,
                                          MaterialPageRoute(
                                            builder: (_) => DetalleProductoScreen(idProducto: pId),
                                          ),
                                        );
                                      }
                                    },
                                    child: Container(
                                      margin: const EdgeInsets.only(top: 6),
                                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                                      decoration: BoxDecoration(
                                        color: Colors.white,
                                        borderRadius: BorderRadius.circular(8),
                                        border: Border.all(color: AppTheme.border),
                                      ),
                                      child: Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Expanded(
                                            child: Text(
                                              pNom,
                                              style: GoogleFonts.playfairDisplay(fontSize: 12, fontWeight: FontWeight.w700),
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ),
                                          Text(
                                            'Bs. $pPre',
                                            style: GoogleFonts.plusJakartaSans(fontSize: 12, fontWeight: FontWeight.w700, color: AppTheme.primaryGold),
                                          ),
                                          const Icon(Icons.chevron_right, size: 16),
                                        ],
                                      ),
                                    ),
                                  );
                                }),
                              ],
                            ],
                          ),
                        ),
                      ),
                      if (isUser) const SizedBox(width: 8),
                    ],
                  ),
                );
              },
            ),
          ),

          // Indicador de escritura del asistente
          if (asistente.cargando)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
              child: Row(
                children: [
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Aurora está pensando...',
                    style: GoogleFonts.plusJakartaSans(fontSize: 11, color: AppTheme.textMuted),
                  ),
                ],
              ),
            ),

          // Barra de entrada inferior
          Container(
            padding: EdgeInsets.only(
              left: 16,
              right: 16,
              top: 10,
              bottom: MediaQuery.of(context).viewInsets.bottom + 12,
            ),
            decoration: const BoxDecoration(
              color: AppTheme.surface,
              border: Border(top: BorderSide(color: AppTheme.border)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Container(
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceVariant,
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: TextField(
                      controller: _inputController,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _enviarMensaje(),
                      style: GoogleFonts.plusJakartaSans(fontSize: 13),
                      decoration: InputDecoration(
                        hintText: 'Escribe tu consulta aquí...',
                        hintStyle: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textMuted),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                        border: InputBorder.none,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.send_rounded, color: AppTheme.primary),
                  onPressed: _enviarMensaje,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
