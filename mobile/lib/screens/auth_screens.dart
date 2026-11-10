import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../services/auth_provider.dart';
import '../services/auth_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_button.dart';
import '../widgets/aurora_text_field.dart';

class AuthScreen extends StatefulWidget {
  final bool initialIsRegister;

  const AuthScreen({super.key, this.initialIsRegister = false});

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  // Controladores Login
  final _loginIdController = TextEditingController();
  final _loginPasswordController = TextEditingController();
  final _loginFormKey = GlobalKey<FormState>();

  // Controladores Registro
  final _regNombreController = TextEditingController();
  final _regApellidoController = TextEditingController();
  final _regCorreoController = TextEditingController();
  final _regPasswordController = TextEditingController();
  final _regConfirmPasswordController = TextEditingController();
  final _regTelefonoController = TextEditingController();
  final _regFormKey = GlobalKey<FormState>();

  bool _cargando = false;
  String? _errorMensaje;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(
      length: 2,
      vsync: this,
      initialIndex: widget.initialIsRegister ? 1 : 0,
    );
  }

  @override
  void dispose() {
    _tabController.dispose();
    _loginIdController.dispose();
    _loginPasswordController.dispose();
    _regNombreController.dispose();
    _regApellidoController.dispose();
    _regCorreoController.dispose();
    _regPasswordController.dispose();
    _regConfirmPasswordController.dispose();
    _regTelefonoController.dispose();
    super.dispose();
  }

  Future<void> _ejecutarLogin() async {
    if (!_loginFormKey.currentState!.validate()) return;

    setState(() {
      _cargando = true;
      _errorMensaje = null;
    });

    final authProvider = context.read<AuthProvider>();
    final res = await authProvider.login(
      _loginIdController.text.trim(),
      _loginPasswordController.text,
    );

    if (!mounted) return;

    setState(() {
      _cargando = false;
    });

    if (res['success'] == true) {
      if (res['requires_verification'] == true) {
        _mostrarDialogoVerificacion(res['nro_usuario'], res['codigo_simulado']);
      } else {
        // Login exitoso, el RootRouter o Navigator retornará a la tienda
        if (Navigator.canPop(context)) {
          Navigator.pop(context);
        }
      }
    } else {
      setState(() {
        _errorMensaje = res['message'] ?? 'Credenciales inválidas.';
      });
    }
  }

  Future<void> _ejecutarRegistro() async {
    if (!_regFormKey.currentState!.validate()) return;

    setState(() {
      _cargando = true;
      _errorMensaje = null;
    });

    final authProvider = context.read<AuthProvider>();
    final res = await authProvider.register(
      correo: _regCorreoController.text.trim(),
      password: _regPasswordController.text,
      confirmPassword: _regConfirmPasswordController.text,
      nombre: _regNombreController.text.trim(),
      apellido: _regApellidoController.text.trim(),
      telefono: _regTelefonoController.text.trim(),
    );

    if (!mounted) return;

    setState(() {
      _cargando = false;
    });

    if (res['success'] == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cuenta creada exitosamente. Bienvenido a Aurora Store.'),
          backgroundColor: AppTheme.success,
        ),
      );
      if (Navigator.canPop(context)) {
        Navigator.pop(context);
      }
    } else {
      setState(() {
        _errorMensaje = res['message'] ?? 'Error al registrar la cuenta.';
      });
    }
  }

  void _mostrarDialogoVerificacion(int nroUsuario, String? codigoSimulado) {
    final codeController = TextEditingController(text: codigoSimulado ?? '');
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(
          'Verificación de dispositivo',
          style: GoogleFonts.playfairDisplay(fontSize: 18, fontWeight: FontWeight.w700),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Dispositivo no reconocido. Ingresa el código de seguridad enviado:',
              style: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: codeController,
              decoration: const InputDecoration(
                hintText: 'Código de 6 dígitos',
                prefixIcon: Icon(Icons.security_outlined),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () async {
              final messenger = ScaffoldMessenger.of(context);
              final authService = AuthService();
              final verifRes = await authService.verifyDevice(
                nroUsuario: nroUsuario,
                codigo: codeController.text.trim(),
              );
              if (!mounted || !ctx.mounted) return;
              Navigator.of(ctx).pop();
              if (verifRes['success'] == true) {
                // Reintentar login para iniciar sesión de inmediato
                _ejecutarLogin();
              } else {
                messenger.showSnackBar(
                  SnackBar(
                    content: Text(verifRes['message'] ?? 'Código inválido.'),
                    backgroundColor: AppTheme.error,
                  ),
                );
              }
            },
            child: const Text('Verificar'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Text(
          'Aurora Store',
          style: GoogleFonts.playfairDisplay(
            fontSize: 22,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Encabezado de bienvenida
              Center(
                child: Column(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: const BoxDecoration(
                        color: AppTheme.goldLight,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(
                        Icons.diamond_outlined,
                        size: 32,
                        color: AppTheme.primaryGold,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'ALTA COSTURA & MODA',
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 2,
                        color: AppTheme.primaryGold,
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 24),

              // Selector de pestaña (Iniciar sesión / Registrarse)
              Container(
                decoration: BoxDecoration(
                  color: AppTheme.surfaceVariant,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.border),
                ),
                child: TabBar(
                  controller: _tabController,
                  indicator: BoxDecoration(
                    color: AppTheme.primary,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  labelColor: Colors.white,
                  unselectedLabelColor: AppTheme.textSecondary,
                  labelStyle: GoogleFonts.plusJakartaSans(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                  dividerColor: Colors.transparent,
                  indicatorSize: TabBarIndicatorSize.tab,
                  tabs: const [
                    Tab(text: 'Iniciar sesión'),
                    Tab(text: 'Registrarse'),
                  ],
                ),
              ),

              const SizedBox(height: 20),

              // Mensaje de error general si aplica
              if (_errorMensaje != null) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.errorLight,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline, size: 18, color: AppTheme.error),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _errorMensaje!,
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 12,
                            color: AppTheme.error,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],

              // Contenido de la pestaña activa
              AnimatedBuilder(
                animation: _tabController,
                builder: (context, _) {
                  return _tabController.index == 0
                      ? _buildLoginForm()
                      : _buildRegisterForm();
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLoginForm() {
    return Form(
      key: _loginFormKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AuroraTextField(
            controller: _loginIdController,
            label: 'Correo electrónico o usuario',
            hint: 'ejemplo@aurorastore.com',
            prefixIcon: Icons.person_outline,
            keyboardType: TextInputType.emailAddress,
            validator: (val) {
              if (val == null || val.trim().isEmpty) {
                return 'Por favor ingresa tu correo o usuario';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),
          AuroraTextField(
            controller: _loginPasswordController,
            label: 'Contraseña',
            hint: '••••••••',
            prefixIcon: Icons.lock_outline,
            isPassword: true,
            validator: (val) {
              if (val == null || val.isEmpty) {
                return 'Por favor ingresa tu contraseña';
              }
              return null;
            },
          ),
          const SizedBox(height: 24),
          AuroraButton(
            text: 'Iniciar sesión',
            isLoading: _cargando,
            onPressed: _ejecutarLogin,
            variant: AuroraButtonVariant.primary,
          ),
        ],
      ),
    );
  }

  Widget _buildRegisterForm() {
    return Form(
      key: _regFormKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: AuroraTextField(
                  controller: _regNombreController,
                  label: 'Nombre',
                  hint: 'Juan',
                  validator: (val) {
                    if (val == null || val.trim().isEmpty) return 'Requerido';
                    return null;
                  },
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: AuroraTextField(
                  controller: _regApellidoController,
                  label: 'Apellido',
                  hint: 'Pérez',
                  validator: (val) {
                    if (val == null || val.trim().isEmpty) return 'Requerido';
                    return null;
                  },
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          AuroraTextField(
            controller: _regCorreoController,
            label: 'Correo electrónico',
            hint: 'tu@correo.com',
            prefixIcon: Icons.email_outlined,
            keyboardType: TextInputType.emailAddress,
            validator: (val) {
              if (val == null || val.trim().isEmpty) return 'Ingresa tu correo';
              if (!val.contains('@') || !val.contains('.')) return 'Correo inválido';
              return null;
            },
          ),
          const SizedBox(height: 14),
          AuroraTextField(
            controller: _regTelefonoController,
            label: 'Teléfono (opcional)',
            hint: '+591 70000000',
            prefixIcon: Icons.phone_outlined,
            keyboardType: TextInputType.phone,
          ),
          const SizedBox(height: 14),
          AuroraTextField(
            controller: _regPasswordController,
            label: 'Contraseña',
            hint: 'Mínimo 8 caracteres y 1 símbolo',
            prefixIcon: Icons.lock_outline,
            isPassword: true,
            validator: (val) {
              if (val == null || val.isEmpty) return 'Ingresa tu contraseña';
              if (val.length < 8) return 'Debe tener al menos 8 caracteres';
              final specialCharRegExp = RegExp(r'[!@#$%^&*(),.?":{}|<>]');
              if (!specialCharRegExp.hasMatch(val)) {
                return 'Debe incluir al menos un símbolo especial';
              }
              return null;
            },
          ),
          const SizedBox(height: 14),
          AuroraTextField(
            controller: _regConfirmPasswordController,
            label: 'Confirmar contraseña',
            hint: 'Repite tu contraseña',
            prefixIcon: Icons.lock_outline,
            isPassword: true,
            validator: (val) {
              if (val != _regPasswordController.text) {
                return 'Las contraseñas no coinciden';
              }
              return null;
            },
          ),
          const SizedBox(height: 20),
          Text(
            'Al registrarte, aceptas los términos de servicio y políticas de privacidad de Aurora Store.',
            style: GoogleFonts.plusJakartaSans(
              fontSize: 11,
              color: AppTheme.textMuted,
            ),
          ),
          const SizedBox(height: 20),
          AuroraButton(
            text: 'Registrarse',
            isLoading: _cargando,
            onPressed: _ejecutarRegistro,
            variant: AuroraButtonVariant.primary,
          ),
        ],
      ),
    );
  }
}