import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'core/connectivity/connectivity_service.dart';
import 'core/sync/sync_coordinator.dart';
import 'core/tenant/tenant_context_manager.dart';
import 'services/asistente_service.dart';
import 'services/auth_provider.dart';
import 'services/carrito_service.dart';
import 'services/catalogo_service.dart';
import 'services/devoluciones_service.dart';
import 'services/pago_service.dart';
import 'services/pedido_service.dart';
import 'services/reserva_service.dart';
import 'config/app_config.dart';
import 'screens/main_navigation_shell.dart';
import 'theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await AppConfig.init();

  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
    ),
  );

  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
  ]);

  final authProvider = AuthProvider();
  await authProvider.verificarSesion();

  // Inicializar subsistemas de red, multitenant y sincronización
  final tenantManager = TenantContextManager();
  final connectivity = ConnectivityService();
  final syncCoordinator = SyncCoordinator();

  await tenantManager.inicializar();
  await syncCoordinator.inicializar();
  await connectivity.inicializar(onRegainedConnection: () {
    syncCoordinator.sincronizarLote();
  });

  runApp(AuroraStoreApp(
    authProvider: authProvider,
    tenantManager: tenantManager,
    connectivity: connectivity,
    syncCoordinator: syncCoordinator,
  ));
}

class AuroraStoreApp extends StatelessWidget {
  final AuthProvider? authProvider;
  final TenantContextManager? tenantManager;
  final ConnectivityService? connectivity;
  final SyncCoordinator? syncCoordinator;

  const AuroraStoreApp({
    super.key,
    this.authProvider,
    this.tenantManager,
    this.connectivity,
    this.syncCoordinator,
  });

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: authProvider ?? AuthProvider()),
        ChangeNotifierProvider.value(value: tenantManager ?? TenantContextManager()),
        ChangeNotifierProvider.value(value: connectivity ?? ConnectivityService()),
        ChangeNotifierProvider.value(value: syncCoordinator ?? SyncCoordinator()),
        ChangeNotifierProvider(create: (_) => CatalogoService()),
        ChangeNotifierProvider(create: (_) => CarritoService()),
        ChangeNotifierProvider(create: (_) => PedidoService()),
        ChangeNotifierProvider(create: (_) => ReservaService()),
        ChangeNotifierProvider(create: (_) => PagoService()),
        ChangeNotifierProvider(create: (_) => AsistenteService()),
        ChangeNotifierProvider(create: (_) => DevolucionesService()),
      ],
      child: MaterialApp(
        title: 'Aurora Store',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        home: const MainNavigationShell(),
      ),
    );
  }
}
