import 'package:flutter_test/flutter_test.dart';
import 'package:aurora_store_mobile/services/asistente_service.dart';

void main() {
  group('Aurora Advisor AsistenteService Unit Tests', () {
    late AsistenteService service;

    setUp(() {
      service = AsistenteService();
    });

    test('1. Inicializa con mensaje de bienvenida y modelo DeepSeek-chat (V3) por defecto', () {
      expect(service.modeloSeleccionado, equals('deepseek-chat'));
      expect(service.conversationId, isNotEmpty);
      expect(service.mensajes.length, equals(1));
      expect(service.mensajes.first.role, equals('assistant'));
      expect(service.mensajes.first.content, contains('Aurora Advisor'));
    });

    test('2. Permite alternar entre DeepSeek-chat (V3) y DeepSeek-reasoner (R1)', () {
      expect(service.modeloSeleccionado, equals('deepseek-chat'));

      service.setModelo('deepseek-reasoner');
      expect(service.modeloSeleccionado, equals('deepseek-reasoner'));

      service.setModelo('deepseek-chat');
      expect(service.modeloSeleccionado, equals('deepseek-chat'));
    });

    test('3. Limpiar conversación regenera UUID de sesión y restaura mensaje de bienvenida', () {
      final oldId = service.conversationId;
      service.limpiarConversacion();

      expect(service.conversationId, isNot(equals(oldId)));
      expect(service.mensajes.length, equals(1));
      expect(service.mensajes.first.id, equals('msg_welcome'));
    });
  });
}
