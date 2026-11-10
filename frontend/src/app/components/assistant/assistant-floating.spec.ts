import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AssistantFloatingComponent } from './assistant-floating';
import { AssistantService, AssistantMessage } from '../../services/assistant.service';
import { ThemeService } from '../../services/theme';

describe('W13 / Iter 2-3: AssistantFloatingComponent & Aurora Advisor UI (Frontend)', () => {
  let component: AssistantFloatingComponent;
  let fixture: ComponentFixture<AssistantFloatingComponent>;
  let mockAssistantService: any;
  let mockThemeService: any;

  beforeEach(async () => {
    const messagesSig = signal<AssistantMessage[]>([
      {
        id: 'msg_welcome_1',
        role: 'assistant',
        content: 'Hola 👋 Soy **Aurora Advisor**.',
        timestamp: new Date(),
        tipo: 'texto'
      }
    ]);
    const isOpenSig = signal<boolean>(true);
    const isLoadingSig = signal<boolean>(false);
    const isListeningSig = signal<boolean>(false);
    const speechErrorSig = signal<string | null>(null);
    const transcripcionPreviaSig = signal<string>('');
    const selectedModelSig = signal<'deepseek-chat' | 'deepseek-reasoner'>('deepseek-chat');

    mockAssistantService = {
      isOpen: isOpenSig,
      isLoading: isLoadingSig,
      isListening: isListeningSig,
      speechError: speechErrorSig,
      transcripcionPrevia: transcripcionPreviaSig,
      selectedModel: selectedModelSig,
      messages: messagesSig,
      esUsuarioAdmin: vi.fn().mockReturnValue(true),
      cambiarModeloDeepSeek: vi.fn((m: 'deepseek-chat' | 'deepseek-reasoner') => selectedModelSig.set(m)),
      alternarModeloDeepSeek: vi.fn(),
      toggleAssistant: vi.fn(() => isOpenSig.set(!isOpenSig())),
      closeAssistant: vi.fn(() => isOpenSig.set(false)),
      limpiarConversacion: vi.fn(),
      detenerRespuesta: vi.fn(() => isLoadingSig.set(false)),
      reintentarUltimoMensaje: vi.fn(),
      enviarMensaje: vi.fn((texto: string) => {
        messagesSig.update(prev => [
          ...prev,
          { id: 'u_1', role: 'user', content: texto, timestamp: new Date(), tipo: 'texto' },
          {
            id: 'a_1',
            role: 'assistant',
            content: 'Se proyectan **148 unidades** en los próximos 14 días.',
            timestamp: new Date(),
            tipo: 'predicciones',
            herramientas_usadas: ['consultar_demanda_proyectada'],
            datos: {
              dias_proyeccion: 14,
              demanda_total_proyectada: 148,
              promedio_diario_proyectado: 10.57,
              tendencia: 'CRECIENTE',
              modelo_seleccionado: 'Holt-Winters / Ensemble'
            }
          }
        ]);
      }),
      alternarVoz: vi.fn((cb: (txt: string, esFinal: boolean) => void) => {
        transcripcionPreviaSig.set('Ventas de esta semana');
        cb('Ventas de esta semana', false);
      })
    };

    mockThemeService = {
      isDark: signal(false)
    };

    await TestBed.configureTestingModule({
      imports: [AssistantFloatingComponent],
      providers: [
        provideRouter([]),
        { provide: AssistantService, useValue: mockAssistantService },
        { provide: ThemeService, useValue: mockThemeService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(AssistantFloatingComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('1. Debe renderizar el panel de Aurora Advisor con modo Copiloto Pro para administradores', () => {
    expect(component).toBeTruthy();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Aurora Advisor');
    expect(compiled.textContent).toContain('Copiloto Pro');
  });

  it('2. Debe enviar consulta en lenguaje natural y renderizar widget de predicciones CU23W e insignias de herramientas', () => {
    component.mensajeTexto = '¿Cuál es la proyección de demanda para las próximas dos semanas?';
    component.enviar();
    fixture.detectChanges();

    expect(mockAssistantService.enviarMensaje).toHaveBeenCalledWith(
      '¿Cuál es la proyección de demanda para las próximas dos semanas?'
    );
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('consultar_demanda_proyectada');
    expect(compiled.textContent).toContain('148 un.');
    expect(compiled.textContent).toContain('CRECIENTE');
  });

  it('3. Debe permitir editar la transcripción previa de voz antes de enviarla', () => {
    component.autoEnviarVoz = false;
    component.alternarMicrofono();
    fixture.detectChanges();

    expect(mockAssistantService.alternarVoz).toHaveBeenCalled();
    expect(component.mensajeTexto).toBe('Ventas de esta semana');
    expect(mockAssistantService.enviarMensaje).not.toHaveBeenCalled();
  });

  it('4. Debe escapar etiquetas HTML maliciosas (<script>) al formatear mensajes del asistente', () => {
    const malicioso = 'Hola <script>alert("xss")</script> **Aurora**';
    const seguro = component.formatearTexto(malicioso);
    expect(seguro).not.toContain('<script>');
    expect(seguro).toContain('&lt;script&gt;');
    expect(seguro).toContain('<strong>Aurora</strong>');
  });

  it('5. Debe permitir detener una consulta en progreso y reintentar ante errores', () => {
    mockAssistantService.isLoading.set(true);
    fixture.detectChanges();
    component.detenerRespuesta();
    expect(mockAssistantService.detenerRespuesta).toHaveBeenCalled();

    component.reintentar();
    expect(mockAssistantService.reintentarUltimoMensaje).toHaveBeenCalled();
  });

  it('6. Debe permitir cambiar entre variantes de DeepSeek (deepseek-chat V3 y deepseek-reasoner R1)', () => {
    expect(component.selectedModel).toBe('deepseek-chat');
    component.seleccionarModelo('deepseek-reasoner');
    fixture.detectChanges();
    expect(mockAssistantService.cambiarModeloDeepSeek).toHaveBeenCalledWith('deepseek-reasoner');
    expect(component.selectedModel).toBe('deepseek-reasoner');
  });
});
