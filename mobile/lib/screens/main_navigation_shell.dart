import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../core/connectivity/connectivity_service.dart';
import '../core/sync/sync_coordinator.dart';
import '../services/carrito_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_floating_assistant.dart';
import 'carrito_screen.dart';
import 'catalogo_screen.dart';
import 'mis_pedidos_screen.dart';
import 'mis_reservas_screen.dart';
import 'perfil_screen.dart';

class MainNavigationShell extends StatefulWidget {
  final int initialIndex;

  const MainNavigationShell({super.key, this.initialIndex = 0});

  @override
  State<MainNavigationShell> createState() => _MainNavigationShellState();
}

class _MainNavigationShellState extends State<MainNavigationShell> {
  late int _currentIndex;

  @override
  void initState() {
    super.initState();
    _currentIndex = widget.initialIndex;
  }

  void _irACatalogo() {
    setState(() {
      _currentIndex = 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    final carritoService = context.watch<CarritoService>();
    final connectivity = context.watch<ConnectivityService>();
    final syncCoordinator = context.watch<SyncCoordinator>();
    final totalItemsCarrito = carritoService.totalItems;

    final screens = [
      const CatalogoScreen(),
      CarritoScreen(onIrAlCatalogo: _irACatalogo),
      MisReservasScreen(onIrAlCatalogo: _irACatalogo),
      MisPedidosScreen(onIrAlCatalogo: _irACatalogo),
      const PerfilScreen(),
    ];

    final bool showOfflineBanner = connectivity.isOffline;
    final bool showSyncingBanner = !showOfflineBanner && syncCoordinator.isSyncing;
    final bool showPendingBanner = !showOfflineBanner && !showSyncingBanner && syncCoordinator.pendingCount > 0;

    return Scaffold(
      body: Column(
        children: [
          if (showOfflineBanner || showSyncingBanner || showPendingBanner)
            SafeArea(
              bottom: false,
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                decoration: BoxDecoration(
                  color: showOfflineBanner
                      ? const Color(0xFF27272A)
                      : showSyncingBanner
                          ? const Color(0xFF0284C7)
                          : const Color(0xFF92400E),
                  border: const Border(bottom: BorderSide(color: Colors.black12, width: 1)),
                ),
                child: Row(
                  children: [
                    Icon(
                      showOfflineBanner
                          ? Icons.wifi_off
                          : showSyncingBanner
                              ? Icons.sync
                              : Icons.cloud_upload_outlined,
                      size: 16,
                      color: Colors.white,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        showOfflineBanner
                            ? 'Modo sin conexión: reservas y bolsa se guardan localmente.'
                            : showSyncingBanner
                                ? 'Sincronizando operaciones con la tienda...'
                                : '${syncCoordinator.pendingCount} operación(es) pendiente(s) de sincronizar.',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    if (showPendingBanner)
                      InkWell(
                        onTap: () => syncCoordinator.sincronizarLote(),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: Colors.white24,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            'Sincronizar',
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 10.5,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          Expanded(
            child: IndexedStack(
              index: _currentIndex,
              children: screens,
            ),
          ),
        ],
      ),
      floatingActionButton: const AuroraFloatingAssistant(),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        items: [
          const BottomNavigationBarItem(
            icon: Icon(Icons.storefront_outlined),
            activeIcon: Icon(Icons.storefront),
            label: 'Catálogo',
          ),
          BottomNavigationBarItem(
            icon: Badge(
              isLabelVisible: totalItemsCarrito > 0,
              label: Text('$totalItemsCarrito'),
              backgroundColor: AppTheme.primaryGold,
              child: const Icon(Icons.shopping_bag_outlined),
            ),
            activeIcon: Badge(
              isLabelVisible: totalItemsCarrito > 0,
              label: Text('$totalItemsCarrito'),
              backgroundColor: AppTheme.primaryGold,
              child: const Icon(Icons.shopping_bag),
            ),
            label: 'Bolsa',
          ),
          const BottomNavigationBarItem(
            icon: Icon(Icons.calendar_today_outlined),
            activeIcon: Icon(Icons.calendar_today),
            label: 'Reservas',
          ),
          const BottomNavigationBarItem(
            icon: Icon(Icons.local_shipping_outlined),
            activeIcon: Icon(Icons.local_shipping),
            label: 'Pedidos',
          ),
          const BottomNavigationBarItem(
            icon: Icon(Icons.person_outline),
            activeIcon: Icon(Icons.person),
            label: 'Perfil',
          ),
        ],
      ),
    );
  }
}
