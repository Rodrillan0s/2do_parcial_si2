import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../core/tenant/tenant_context_manager.dart';
import '../services/auth_provider.dart';
import '../services/devoluciones_service.dart';
import '../services/pedido_service.dart';
import '../theme/app_theme.dart';
import '../widgets/aurora_badge.dart';
import '../widgets/aurora_button.dart';
import '../widgets/aurora_empty_state.dart';
import '../widgets/valoracion_bottom_sheet.dart';
import 'auth_screens.dart';
import 'pago_screen.dart';
import 'politicas_devolucion_modal.dart';
import 'solicitar_devolucion_modal.dart';

class MisPedidosScreen extends StatefulWidget {
  final VoidCallback? onIrAlCatalogo;

  const MisPedidosScreen({super.key, this.onIrAlCatalogo});

  @override
  State<MisPedidosScreen> createState() => _MisPedidosScreenState();
}

class _MisPedidosScreenState extends State<MisPedidosScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _cargarDatos();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _cargarDatos() {
    final tenantId = context.read<TenantContextManager>().idEmpresaActiva;
    context.read<PedidoService>().cargarMisPedidos(idEmpresa: tenantId);
    context.read<DevolucionesService>().cargarMisDevoluciones(idEmpresa: tenantId);
    context.read<DevolucionesService>().cargarMisCreditos(idEmpresa: tenantId);
  }

  void _mostrarPoliticas() {
    final tenantId = context.read<TenantContextManager>().idEmpresaActiva;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => PoliticasDevolucionModal(idEmpresa: tenantId),
    );
  }

  void _abrirSolicitudDevolucion(PedidoModel pedido) async {
    final result = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => SolicitarDevolucionModal(pedido: pedido),
    );

    if (result == true && mounted) {
      _cargarDatos();
      _tabController.animateTo(1); // Cambiar a la pestaña de Devoluciones
    }
  }

  void _mostrarDetallePedido(PedidoModel pedido) {
    final currencyFormatter = NumberFormat.currency(
      locale: 'es_BO',
      symbol: 'Bs. ',
      decimalDigits: 2,
    );

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        height: MediaQuery.of(context).size.height * 0.85,
        decoration: const BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: Column(
          children: [
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
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Detalle de la Compra',
                    style: GoogleFonts.playfairDisplay(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),

            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Expanded(
                        child: Text(
                          pedido.codigoPedido,
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                            color: AppTheme.primaryGold,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 8),
                      AuroraBadge.status(pedido.estado),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    pedido.fechaPedido,
                    style: GoogleFonts.plusJakartaSans(fontSize: 12, color: AppTheme.textMuted),
                  ),

                  const SizedBox(height: 16),
                  Text(
                    'Prendas Adquiridas',
                    style: GoogleFonts.plusJakartaSans(fontSize: 14, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),

                  ...pedido.items.map((item) {
                    return Container(
                      margin: const EdgeInsets.only(bottom: 8),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppTheme.surfaceVariant,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppTheme.border),
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  item.productoNombre,
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                                Text(
                                  'Talla: ${item.talla} · Color: ${item.color} · Cant: ${item.cantidad}',
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 11,
                                    color: AppTheme.textMuted,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Text(
                            currencyFormatter.format(item.subtotal),
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.primaryGold,
                            ),
                          ),
                        ],
                      ),
                    );
                  }),

                  const Divider(height: 24),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Total Abonado:', style: GoogleFonts.plusJakartaSans(fontSize: 14, fontWeight: FontWeight.w700)),
                      Text(currencyFormatter.format(pedido.total), style: GoogleFonts.plusJakartaSans(fontSize: 18, fontWeight: FontWeight.w800, color: AppTheme.primaryGold)),
                    ],
                  ),

                  // Botón para iniciar devolución si la compra ya fue completada o entregada
                  if (pedido.estado.toUpperCase() == 'ENTREGADO' ||
                      pedido.estado.toUpperCase() == 'COMPLETADO' ||
                      pedido.estadoPago.toUpperCase() == 'PAGADO') ...[
                    const SizedBox(height: 20),
                    OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        side: const BorderSide(color: AppTheme.primaryGold),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      icon: const Icon(Icons.assignment_return_outlined, color: AppTheme.primaryGold, size: 18),
                      label: Text(
                        'Solicitar Devolución o Cambio (Ley 453)',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.primaryGold,
                        ),
                      ),
                      onPressed: () {
                        Navigator.pop(ctx);
                        _abrirSolicitudDevolucion(pedido);
                      },
                    ),
                    const SizedBox(height: 10),
                    ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFF59E0B),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      icon: const Icon(Icons.star_rounded, size: 18),
                      label: Text(
                        'Calificar Compra y Servicio',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      onPressed: () {
                        Navigator.pop(ctx);
                        ValoracionBottomSheet.mostrar(
                          context,
                          idPedido: pedido.idPedido,
                          codigoPedido: pedido.codigoPedido,
                        );
                      },
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final pedidoService = context.watch<PedidoService>();
    final devolucionesService = context.watch<DevolucionesService>();

    final currencyFormatter = NumberFormat.currency(
      locale: 'es_BO',
      symbol: 'Bs. ',
      decimalDigits: 2,
    );

    if (!authProvider.estaAutenticado) {
      return Scaffold(
        backgroundColor: AppTheme.background,
        appBar: AppBar(title: const Text('Mis Pedidos')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.receipt_long_outlined, size: 64, color: AppTheme.primaryGold),
                const SizedBox(height: 16),
                Text(
                  'Inicia sesión para ver tus compras',
                  style: GoogleFonts.playfairDisplay(fontSize: 20, fontWeight: FontWeight.w700),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Consulta el estado de entrega de tus prendas exclusivas, solicita cambios y gestiona tus garantías.',
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
        title: Text(
          'Compras & Devoluciones',
          style: GoogleFonts.playfairDisplay(fontSize: 18, fontWeight: FontWeight.w700),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.policy_outlined),
            tooltip: 'Políticas de Devolución',
            onPressed: _mostrarPoliticas,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppTheme.primaryGold,
          unselectedLabelColor: AppTheme.textMuted,
          indicatorColor: AppTheme.primaryGold,
          indicatorWeight: 2.5,
          labelStyle: GoogleFonts.plusJakartaSans(fontSize: 12, fontWeight: FontWeight.w700),
          tabs: const [
            Tab(text: 'Mis Compras'),
            Tab(text: 'Devoluciones'),
            Tab(text: 'Saldos a Favor'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          // -------------------------------------------------------------
          // PESTAÑA 1: MIS COMPRAS / PEDIDOS
          // -------------------------------------------------------------
          RefreshIndicator(
            onRefresh: () async => _cargarDatos(),
            child: pedidoService.cargando && pedidoService.misPedidos.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : pedidoService.misPedidos.isEmpty
                    ? AuroraEmptyState(
                        icon: Icons.receipt_long_outlined,
                        title: 'Aún no tienes compras',
                        message: 'Cuando realices una compra de alta costura, podrás hacer seguimiento a su entrega aquí.',
                        buttonText: 'Explorar catálogo',
                        onButtonPressed: widget.onIrAlCatalogo,
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: pedidoService.misPedidos.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 14),
                        itemBuilder: (context, index) {
                          final pedido = pedidoService.misPedidos[index];

                          return InkWell(
                            onTap: () => _mostrarDetallePedido(pedido),
                            borderRadius: BorderRadius.circular(16),
                            child: Container(
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: AppTheme.surface,
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(color: AppTheme.border),
                                boxShadow: const [
                                  BoxShadow(
                                    color: Color(0x06000000),
                                    blurRadius: 8,
                                    offset: Offset(0, 3),
                                  ),
                                ],
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Expanded(
                                        child: Text(
                                          pedido.codigoPedido,
                                          style: GoogleFonts.plusJakartaSans(
                                            fontSize: 15,
                                            fontWeight: FontWeight.w700,
                                            color: AppTheme.primaryGold,
                                          ),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                      AuroraBadge.status(pedido.estado),
                                    ],
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    pedido.fechaPedido,
                                    style: GoogleFonts.plusJakartaSans(fontSize: 12, color: AppTheme.textMuted),
                                  ),
                                  const Divider(height: 20),

                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(
                                        '${pedido.totalItems} prenda(s) • ${pedido.modalidadCompra == 'ENTREGA_DOMICILIO' ? 'A Domicilio' : 'Retiro en Tienda'}',
                                        style: GoogleFonts.plusJakartaSans(fontSize: 12, color: AppTheme.textSecondary),
                                      ),
                                      Text(
                                        currencyFormatter.format(pedido.total),
                                        style: GoogleFonts.plusJakartaSans(
                                          fontSize: 16,
                                          fontWeight: FontWeight.w800,
                                          color: AppTheme.textPrimary,
                                        ),
                                      ),
                                    ],
                                  ),

                                  // Botón pagar si está pendiente
                                  if ((pedido.estadoPago == 'PENDIENTE' || pedido.estadoPago == 'PENDIENTE_PAGO') &&
                                      pedido.estado != 'CANCELADO') ...[
                                    const SizedBox(height: 12),
                                    SizedBox(
                                      width: double.infinity,
                                      height: 38,
                                      child: ElevatedButton.icon(
                                        style: ElevatedButton.styleFrom(
                                          backgroundColor: AppTheme.primaryGold,
                                          foregroundColor: Colors.white,
                                          elevation: 0,
                                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                        ),
                                        icon: const Icon(Icons.lock_outline, size: 16),
                                        label: Text(
                                          'Pagar ahora (${currencyFormatter.format(pedido.total)})',
                                          style: GoogleFonts.plusJakartaSans(fontSize: 12, fontWeight: FontWeight.w700),
                                        ),
                                        onPressed: () {
                                          Navigator.push(
                                            context,
                                            MaterialPageRoute(
                                              builder: (_) => PagoScreen(
                                                idPedido: pedido.idPedido,
                                                pedidoInicial: pedido,
                                              ),
                                            ),
                                          );
                                        },
                                      ),
                                    ),
                                  ],
                                  if (pedido.estado.toUpperCase() == 'ENTREGADO' ||
                                      pedido.estado.toUpperCase() == 'COMPLETADO' ||
                                      pedido.estadoPago.toUpperCase() == 'PAGADO') ...[
                                    const SizedBox(height: 10),
                                    SizedBox(
                                      width: double.infinity,
                                      height: 36,
                                      child: OutlinedButton.icon(
                                        style: OutlinedButton.styleFrom(
                                          foregroundColor: const Color(0xFFD97706),
                                          side: const BorderSide(color: Color(0xFFFDE68A)),
                                          backgroundColor: const Color(0xFFFFFBEB),
                                          elevation: 0,
                                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                        ),
                                        icon: const Icon(Icons.star_rounded, size: 16, color: Color(0xFFD97706)),
                                        label: Text(
                                          'Calificar compra',
                                          style: GoogleFonts.plusJakartaSans(fontSize: 12, fontWeight: FontWeight.w600),
                                        ),
                                        onPressed: () {
                                          ValoracionBottomSheet.mostrar(
                                            context,
                                            idPedido: pedido.idPedido,
                                            codigoPedido: pedido.codigoPedido,
                                          );
                                        },
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          );
                        },
                      ),
          ),

          // -------------------------------------------------------------
          // PESTAÑA 2: MIS DEVOLUCIONES (SOLICITUDES & ESTADOS)
          // -------------------------------------------------------------
          RefreshIndicator(
            onRefresh: () async => _cargarDatos(),
            child: devolucionesService.cargando && devolucionesService.misSolicitudes.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : devolucionesService.misSolicitudes.isEmpty
                    ? AuroraEmptyState(
                        icon: Icons.assignment_return_outlined,
                        title: 'Sin devoluciones activas',
                        message: 'Si necesitas cambiar una prenda o solicitar una garantía, puedes gestionarlo desde el detalle de tu compra.',
                        buttonText: 'Explorar catálogo',
                        onButtonPressed: widget.onIrAlCatalogo,
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: devolucionesService.misSolicitudes.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 14),
                        itemBuilder: (context, index) {
                          final sol = devolucionesService.misSolicitudes[index];

                          return Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: AppTheme.surface,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: AppTheme.border),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        sol.codigoSolicitud,
                                        style: GoogleFonts.plusJakartaSans(
                                          fontSize: 14,
                                          fontWeight: FontWeight.w800,
                                          color: AppTheme.primaryGold,
                                        ),
                                      ),
                                    ),
                                    AuroraBadge.status(sol.estado),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'Fecha: ${sol.fechaSolicitud}',
                                  style: GoogleFonts.plusJakartaSans(fontSize: 11, color: AppTheme.textMuted),
                                ),
                                const SizedBox(height: 8),

                                Text(
                                  'Motivo: ${sol.motivoGeneral}',
                                  style: GoogleFonts.plusJakartaSans(fontSize: 12, fontWeight: FontWeight.w600),
                                ),
                                Text(
                                  'Resolución: ${sol.tipoResolucion == 'SALDO_A_FAVOR' || sol.tipoResolucion == 'CREDITO_TIENDA' ? 'Saldo a Favor / Vale Digital' : sol.tipoResolucion == 'CAMBIO_PRENDA' ? 'Cambio de Talla / Prenda' : 'Reembolso Monetario'}',
                                  style: GoogleFonts.plusJakartaSans(fontSize: 12, color: AppTheme.textSecondary),
                                ),

                                if (sol.tipoResolucion == 'CAMBIO_PRENDA') ...[
                                  const SizedBox(height: 6),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                    decoration: BoxDecoration(
                                      color: Colors.cyan.withValues(alpha: 0.1),
                                      borderRadius: BorderRadius.circular(8),
                                      border: Border.all(color: Colors.cyan.withValues(alpha: 0.3)),
                                    ),
                                    child: Text(
                                      sol.estado == 'PENDIENTE_ENTREGA'
                                          ? '🔄 Prenda original recibida en tienda — Tu nueva talla está lista para entrega'
                                          : '🔄 Canje directo por nueva talla (Sin desembolso monetario)',
                                      style: GoogleFonts.plusJakartaSans(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.cyan.shade900),
                                    ),
                                  ),
                                ] else if (sol.montoTotalEstimado > 0) ...[
                                  const SizedBox(height: 6),
                                  Text(
                                    'Monto estimado: ${currencyFormatter.format(sol.montoTotalEstimado)}',
                                    style: GoogleFonts.plusJakartaSans(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.primaryGold),
                                  ),
                                ],

                                if (sol.items.isNotEmpty) ...[
                                  const Divider(height: 18),
                                  ...sol.items.map((it) => Padding(
                                    padding: const EdgeInsets.symmetric(vertical: 3),
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            const Icon(Icons.circle, size: 6, color: AppTheme.primaryGold),
                                            const SizedBox(width: 6),
                                            Expanded(
                                              child: Text(
                                                '${it.productoNombre} (Talla: ${it.talla} / ${it.color}) x${it.cantidad}',
                                                style: GoogleFonts.plusJakartaSans(fontSize: 11, color: AppTheme.textSecondary),
                                              ),
                                            ),
                                          ],
                                        ),
                                        if (it.tallaCambio != null && it.tallaCambio!.isNotEmpty)
                                          Padding(
                                            padding: const EdgeInsets.only(left: 12, top: 2),
                                            child: Text(
                                              '🔄 Nueva talla solicitada: ${it.tallaCambio}',
                                              style: GoogleFonts.plusJakartaSans(fontSize: 11, fontWeight: FontWeight.w700, color: Colors.cyan.shade800),
                                            ),
                                          ),
                                      ],
                                    ),
                                  )),
                                ],
                              ],
                            ),
                          );
                        },
                      ),
          ),

          // -------------------------------------------------------------
          // PESTAÑA 3: SALDOS A FAVOR (VOUCHERS DIGITALES)
          // -------------------------------------------------------------
          RefreshIndicator(
            onRefresh: () async => _cargarDatos(),
            child: devolucionesService.cargando && devolucionesService.misCreditos.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : devolucionesService.misCreditos.isEmpty
                    ? AuroraEmptyState(
                        icon: Icons.credit_card_outlined,
                        title: 'No tienes saldos a favor',
                        message: 'Los créditos y vouchers otorgados por cambios o devoluciones se registrarán aquí.',
                        buttonText: 'Explorar catálogo',
                        onButtonPressed: widget.onIrAlCatalogo,
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: devolucionesService.misCreditos.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 14),
                        itemBuilder: (context, index) {
                          final voucher = devolucionesService.misCreditos[index];

                          return Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: [
                                  AppTheme.surface,
                                  AppTheme.goldLight.withValues(alpha: 0.3),
                                ],
                                begin: Alignment.topLeft,
                                end: Alignment.bottomRight,
                              ),
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: AppTheme.primaryGold.withValues(alpha: 0.4)),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Row(
                                      children: [
                                        const Icon(Icons.confirmation_number_outlined, color: AppTheme.primaryGold, size: 20),
                                        const SizedBox(width: 8),
                                        Text(
                                          voucher.codigoVoucher,
                                          style: GoogleFonts.plusJakartaSans(
                                            fontSize: 15,
                                            fontWeight: FontWeight.w800,
                                            color: AppTheme.primaryGold,
                                            letterSpacing: 1.2,
                                          ),
                                        ),
                                      ],
                                    ),
                                    IconButton(
                                      icon: const Icon(Icons.copy, size: 18, color: AppTheme.primaryGold),
                                      tooltip: 'Copiar código',
                                      onPressed: () {
                                        Clipboard.setData(ClipboardData(text: voucher.codigoVoucher));
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          const SnackBar(
                                            content: Text('Código de cupón copiado.'),
                                            duration: Duration(seconds: 2),
                                          ),
                                        );
                                      },
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  'Saldo disponible:',
                                  style: GoogleFonts.plusJakartaSans(fontSize: 11, color: AppTheme.textMuted),
                                ),
                                Text(
                                  currencyFormatter.format(voucher.saldoDisponible),
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 22,
                                    fontWeight: FontWeight.w900,
                                    color: AppTheme.textPrimary,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  'Emisión: ${voucher.fechaEmision}${voucher.fechaVencimiento != null ? ' · Vence: ${voucher.fechaVencimiento}' : ' · Sin vencimiento'}',
                                  style: GoogleFonts.plusJakartaSans(fontSize: 11, color: AppTheme.textSecondary),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
