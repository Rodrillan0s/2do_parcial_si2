import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../services/auth_provider.dart';
import '../services/profile_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_button.dart';
import '../widgets/aurora_text_field.dart';
import 'auth_screens.dart';

class PerfilScreen extends StatefulWidget {
  const PerfilScreen({super.key});

  @override
  State<PerfilScreen> createState() => _PerfilScreenState();
}

class _PerfilScreenState extends State<PerfilScreen> {
  final ProfileService _profileService = ProfileService();
  PerfilModel? _perfil;
  bool _cargando = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _cargarPerfil();
  }

  Future<void> _cargarPerfil() async {
    setState(() {
      _cargando = true;
      _error = null;
    });

    try {
      final p = await _profileService.obtenerPerfil();
      if (mounted) {
        setState(() {
          _perfil = p;
          _cargando = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString().replaceAll('Exception: ', '');
          _cargando = false;
        });
      }
    }
  }

  void _abrirModalEditarPerfil() {
    if (_perfil == null) return;

    final nombreCtrl = TextEditingController(text: _perfil!.nombre);
    final apellidoCtrl = TextEditingController(text: _perfil!.apellido);
    final telCtrl = TextEditingController(text: _perfil!.telefono ?? '');
    final ciCtrl = TextEditingController(text: _perfil!.ci ?? '');
    final dirCtrl = TextEditingController(text: _perfil!.direccion ?? '');
    final ciudadCtrl = TextEditingController(text: _perfil!.ciudad ?? '');
    bool guardando = false;
    String? modalError;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) {
          return Container(
            decoration: const BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            ),
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: MediaQuery.of(context).viewInsets.bottom + 24,
            ),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: AppTheme.borderStrong,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Editar datos personales',
                    style: GoogleFonts.playfairDisplay(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (modalError != null) ...[
                    Text(
                      modalError!,
                      style: GoogleFonts.plusJakartaSans(color: AppTheme.error, fontSize: 12),
                    ),
                    const SizedBox(height: 12),
                  ],
                  Row(
                    children: [
                      Expanded(
                        child: AuroraTextField(
                          controller: nombreCtrl,
                          label: 'Nombre',
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: AuroraTextField(
                          controller: apellidoCtrl,
                          label: 'Apellido',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: AuroraTextField(
                          controller: telCtrl,
                          label: 'Teléfono',
                          keyboardType: TextInputType.phone,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: AuroraTextField(
                          controller: ciCtrl,
                          label: 'Documento / CI',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  AuroraTextField(
                    controller: dirCtrl,
                    label: 'Dirección',
                    hint: 'Av. San Martín #123',
                  ),
                  const SizedBox(height: 12),
                  AuroraTextField(
                    controller: ciudadCtrl,
                    label: 'Ciudad',
                    hint: 'Santa Cruz',
                  ),
                  const SizedBox(height: 24),
                  AuroraButton(
                    text: 'Guardar cambios',
                    isLoading: guardando,
                    onPressed: () async {
                      setModalState(() {
                        guardando = true;
                        modalError = null;
                      });

                      final messenger = ScaffoldMessenger.of(context);
                      try {
                        final updated = await _profileService.actualizarPerfil(
                          nombre: nombreCtrl.text,
                          apellido: apellidoCtrl.text,
                          telefono: telCtrl.text,
                          ci: ciCtrl.text,
                          direccion: dirCtrl.text,
                          ciudad: ciudadCtrl.text,
                        );

                        if (mounted && ctx.mounted) {
                          setState(() {
                            _perfil = updated;
                          });
                          Navigator.of(ctx).pop();
                          messenger.showSnackBar(
                            const SnackBar(
                              content: Text('Perfil actualizado correctamente.'),
                              backgroundColor: AppTheme.success,
                            ),
                          );
                        }
                      } catch (e) {
                        setModalState(() {
                          guardando = false;
                          modalError = e.toString().replaceAll('Exception: ', '');
                        });
                      }
                    },
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  void _abrirModalCambiarPassword() {
    final passwordCtrl = TextEditingController();
    final confirmCtrl = TextEditingController();
    bool guardando = false;
    String? modalError;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) {
          return Container(
            decoration: const BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            ),
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: MediaQuery.of(context).viewInsets.bottom + 24,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: AppTheme.borderStrong,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  'Cambiar contraseña',
                  style: GoogleFonts.playfairDisplay(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'La contraseña debe contener al menos 8 caracteres y 1 carácter especial.',
                  style: GoogleFonts.plusJakartaSans(fontSize: 12, color: AppTheme.textMuted),
                ),
                const SizedBox(height: 16),
                if (modalError != null) ...[
                  Text(
                    modalError!,
                    style: GoogleFonts.plusJakartaSans(color: AppTheme.error, fontSize: 12),
                  ),
                  const SizedBox(height: 12),
                ],
                AuroraTextField(
                  controller: passwordCtrl,
                  label: 'Nueva contraseña',
                  isPassword: true,
                ),
                const SizedBox(height: 12),
                AuroraTextField(
                  controller: confirmCtrl,
                  label: 'Confirmar nueva contraseña',
                  isPassword: true,
                ),
                const SizedBox(height: 24),
                AuroraButton(
                  text: 'Actualizar contraseña',
                  isLoading: guardando,
                  onPressed: () async {
                    if (passwordCtrl.text != confirmCtrl.text) {
                      setModalState(() {
                        modalError = 'Las contraseñas no coinciden.';
                      });
                      return;
                    }

                    setModalState(() {
                      guardando = true;
                      modalError = null;
                    });

                    final messenger = ScaffoldMessenger.of(context);
                    try {
                      await _profileService.cambiarPassword(passwordCtrl.text);
                      if (mounted && ctx.mounted) {
                        Navigator.of(ctx).pop();
                        messenger.showSnackBar(
                          const SnackBar(
                            content: Text('Contraseña actualizada con éxito.'),
                            backgroundColor: AppTheme.success,
                          ),
                        );
                      }
                    } catch (e) {
                      setModalState(() {
                        guardando = false;
                        modalError = e.toString().replaceAll('Exception: ', '');
                      });
                    }
                  },
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();

    if (!authProvider.estaAutenticado) {
      return Scaffold(
        backgroundColor: AppTheme.background,
        appBar: AppBar(title: const Text('Mi Perfil')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.person_outline, size: 64, color: AppTheme.primaryGold),
                const SizedBox(height: 16),
                Text(
                  'Inicia sesión',
                  style: GoogleFonts.playfairDisplay(fontSize: 22, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                Text(
                  'Accede a tu cuenta para gestionar tu perfil, consultar tus pedidos y reservas.',
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
        title: const Text('Mi Perfil'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _cargarPerfil,
          ),
        ],
      ),
      body: _cargando
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(_error!),
                      const SizedBox(height: 12),
                      AuroraButton(
                        text: 'Reintentar',
                        width: 150,
                        onPressed: _cargarPerfil,
                      ),
                    ],
                  ),
                )
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Tarjeta de Identidad
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          color: AppTheme.surface,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: AppTheme.border),
                          boxShadow: const [
                            BoxShadow(
                              color: Color(0x08000000),
                              blurRadius: 10,
                              offset: Offset(0, 4),
                            ),
                          ],
                        ),
                        child: Row(
                          children: [
                            CircleAvatar(
                              radius: 30,
                              backgroundColor: AppTheme.primaryGold.withValues(alpha: 0.15),
                              child: Text(
                                _perfil?.nombre.isNotEmpty == true
                                    ? _perfil!.nombre[0].toUpperCase()
                                    : 'A',
                                style: GoogleFonts.playfairDisplay(
                                  fontSize: 24,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.primaryGold,
                                ),
                              ),
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    _perfil?.nombreCompleto ?? 'Usuario',
                                    style: GoogleFonts.playfairDisplay(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w700,
                                      color: AppTheme.textPrimary,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    _perfil?.correo ?? '',
                                    style: GoogleFonts.plusJakartaSans(
                                      fontSize: 12,
                                      color: AppTheme.textSecondary,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: AppTheme.goldLight,
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      _perfil?.nombreRol ?? 'Cliente',
                                      style: GoogleFonts.plusJakartaSans(
                                        fontSize: 10,
                                        fontWeight: FontWeight.w600,
                                        color: AppTheme.primaryGold,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 20),

                      // Detalles de Contacto y Dirección
                      Container(
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          color: AppTheme.surface,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  'Datos de la cuenta',
                                  style: GoogleFonts.playfairDisplay(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                                TextButton.icon(
                                  onPressed: _abrirModalEditarPerfil,
                                  icon: const Icon(Icons.edit_outlined, size: 16),
                                  label: const Text('Editar'),
                                ),
                              ],
                            ),
                            const Divider(height: 20),
                            _buildInfoRow(Icons.phone_outlined, 'Teléfono', _perfil?.telefono ?? 'No especificado'),
                            _buildInfoRow(Icons.badge_outlined, 'Documento / CI', _perfil?.ci ?? 'No especificado'),
                            _buildInfoRow(Icons.location_on_outlined, 'Dirección', _perfil?.direccion ?? 'No especificada'),
                            _buildInfoRow(Icons.location_city_outlined, 'Ciudad', _perfil?.ciudad ?? 'Santa Cruz'),
                            if (_perfil?.nombreEmpresa != null)
                              _buildInfoRow(Icons.business_outlined, 'Empresa', _perfil!.nombreEmpresa!),
                          ],
                        ),
                      ),

                      const SizedBox(height: 20),

                      // Acciones de Seguridad
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AppTheme.surface,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: AppTheme.border),
                        ),
                        child: Column(
                          children: [
                            ListTile(
                              leading: const Icon(Icons.lock_reset_outlined, color: AppTheme.textPrimary),
                              title: Text(
                                'Cambiar contraseña',
                                style: GoogleFonts.plusJakartaSans(fontSize: 14, fontWeight: FontWeight.w600),
                              ),
                              trailing: const Icon(Icons.chevron_right),
                              onTap: _abrirModalCambiarPassword,
                            ),
                            const Divider(),
                            ListTile(
                              leading: const Icon(Icons.logout, color: AppTheme.error),
                              title: Text(
                                'Cerrar sesión',
                                style: GoogleFonts.plusJakartaSans(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.error,
                                ),
                              ),
                              onTap: () async {
                                final confirmar = await showDialog<bool>(
                                  context: context,
                                  builder: (ctx) => AlertDialog(
                                    title: const Text('Cerrar sesión'),
                                    content: const Text('¿Estás seguro de que deseas cerrar sesión?'),
                                    actions: [
                                      TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
                                      ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Cerrar sesión')),
                                    ],
                                  ),
                                );
                                if (confirmar == true) {
                                  await authProvider.logout();
                                }
                              },
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
    );
  }

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(icon, size: 18, color: AppTheme.primaryGold),
          const SizedBox(width: 12),
          Text(
            label,
            style: GoogleFonts.plusJakartaSans(fontSize: 13, color: AppTheme.textSecondary),
          ),
          const Spacer(),
          Text(
            value,
            style: GoogleFonts.plusJakartaSans(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textPrimary),
          ),
        ],
      ),
    );
  }
}