import { Routes } from '@angular/router';
import { authGuard } from './guards/auth-guard';
import { permissionGuard } from './guards/permission-guard';
import { scopeGuard } from './guards/scope-guard';

export const routes: Routes = [
  // =========================================================================
  // 1. SITIO COMERCIAL SAAS DE AURORASTORE (SUPERFICIE INDEPENDIENTE)
  // =========================================================================
  { path: 'saas', loadComponent: () => import('./pages/saas-comercial/saas-comercial').then(m => m.SaasComercialComponent) },
  { path: 'saas/planes', loadComponent: () => import('./pages/saas-comercial/saas-comercial').then(m => m.SaasComercialComponent) },
  { path: 'saas/registro', loadComponent: () => import('./pages/saas-comercial/saas-comercial').then(m => m.SaasComercialComponent) },
  { path: 'saas/contratacion/:codigo', loadComponent: () => import('./pages/saas-comercial/saas-comercial').then(m => m.SaasComercialComponent) },

  // =========================================================================
  // 2. STOREFRONT DEL TENANT (CONSUMIDOR FINAL - MULTITENANT DINÁMICO)
  // =========================================================================
  { path: '', loadComponent: () => import('./pages/explorar/explorar').then(m => m.ExplorarComponent) },
  { path: 'explorar', loadComponent: () => import('./pages/explorar/explorar').then(m => m.ExplorarComponent) },
  { path: 't/:slug', loadComponent: () => import('./pages/explorar/explorar').then(m => m.ExplorarComponent) },
  { path: 't/:slug/catalogo', loadComponent: () => import('./pages/catalogo/catalogo').then(m => m.CatalogoComponent) },
  { path: 'catalogo', loadComponent: () => import('./pages/catalogo/catalogo').then(m => m.CatalogoComponent) },
  { path: 'catalogo/:id', loadComponent: () => import('./pages/catalogo/catalogo').then(m => m.CatalogoComponent) },
  { path: 'login', loadComponent: () => import('./pages/explorar/explorar').then(m => m.ExplorarComponent) },
  { path: 'perfil', loadComponent: () => import('./pages/perfil/perfil').then(m => m.PerfilComponent), canActivate: [authGuard] },
  { path: 'checkout', loadComponent: () => import('./pages/checkout/checkout').then(m => m.CheckoutComponent), canActivate: [authGuard] },
  { path: 'pedido-confirmado/:id', loadComponent: () => import('./pages/pedido-confirmado/pedido-confirmado').then(m => m.PedidoConfirmadoComponent), canActivate: [authGuard] },
  { path: 'pago/:id', loadComponent: () => import('./pages/pago/pago').then(m => m.PagoComponent), canActivate: [authGuard] },
  { path: 'mis-reservas', loadComponent: () => import('./pages/reservas/mis-reservas/mis-reservas').then(m => m.MisReservasComponent), canActivate: [authGuard] },
  { path: 'mis-pedidos', loadComponent: () => import('./pages/pedidos/mis-pedidos/mis-pedidos').then(m => m.MisPedidosComponent), canActivate: [authGuard] },

  // RUTAS DE REDIRECCIÓN A NIVEL RAÍZ A /admin/* PARA EVITAR CAÍDAS A LA TIENDA PÚBLICA
  { path: 'kpis', redirectTo: 'admin/kpis', pathMatch: 'full' },
  { path: 'usuarios', redirectTo: 'admin/usuarios', pathMatch: 'full' },
  { path: 'roles', redirectTo: 'admin/usuarios', pathMatch: 'full' },
  { path: 'empresas', redirectTo: 'admin/empresas', pathMatch: 'full' },
  { path: 'sucursales', redirectTo: 'admin/sucursales', pathMatch: 'full' },
  { path: 'categorias', redirectTo: 'admin/categorias', pathMatch: 'full' },
  { path: 'tallas-colores', redirectTo: 'admin/tallas-colores', pathMatch: 'full' },
  { path: 'productos', redirectTo: 'admin/productos', pathMatch: 'full' },
  { path: 'inventario', redirectTo: 'admin/inventario', pathMatch: 'full' },
  { path: 'caja', redirectTo: 'admin/caja', pathMatch: 'full' },
  { path: 'cajas-monitoreo', redirectTo: 'admin/cajas-monitoreo', pathMatch: 'full' },
  { path: 'cajas', redirectTo: 'admin/cajas-monitoreo', pathMatch: 'full' },
  { path: 'pos', redirectTo: 'admin/caja', pathMatch: 'full' },
  { path: 'caja/pago/:id', redirectTo: 'admin/caja/pago/:id', pathMatch: 'full' },
  { path: 'caja/comprobante/:id', redirectTo: 'admin/caja/comprobante/:id', pathMatch: 'full' },
  { path: 'bitacora', redirectTo: 'admin/bitacora', pathMatch: 'full' },
  { path: 'backup', redirectTo: 'admin/backup', pathMatch: 'full' },
  { path: 'reportes', redirectTo: 'admin/reportes', pathMatch: 'full' },
  { path: 'bi-dashboard', redirectTo: 'admin/bi_dashboard', pathMatch: 'full' },
  { path: 'bi_dashboard', redirectTo: 'admin/bi_dashboard', pathMatch: 'full' },
  { path: 'triaje-chat', redirectTo: 'admin/triaje-chat', pathMatch: 'full' },
  { path: 'proveedores', redirectTo: 'admin/proveedores', pathMatch: 'full' },
  { path: 'planes', redirectTo: 'admin/planes', pathMatch: 'full' },
  { path: 'suscripciones', redirectTo: 'admin/suscripciones', pathMatch: 'full' },
  { path: 'mi-tienda', redirectTo: 'admin/mi-tienda', pathMatch: 'full' },
  { path: 'devoluciones', redirectTo: 'admin/devoluciones', pathMatch: 'full' },

  // =========================================================================
  // 3. PANEL ADMINISTRATIVO INTERNO (DISEÑO NEUTRAL INDEPENDIENTE DEL TENANT)
  // =========================================================================
  {
    path: 'admin',
    loadComponent: () => import('./layouts/admin-layout/admin-layout').then(m => m.AdminLayoutComponent),
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'kpis', pathMatch: 'full' },
      { path: 'kpis', loadComponent: () => import('./pages/dashboard-kpis/dashboard-kpis').then(m => m.DashboardKpisComponent), canActivate: [permissionGuard(['reportes.ver', 'admin.acceder'])] },
      { path: 'reportes', loadComponent: () => import('./pages/reportes/reportes').then(m => m.ReportesComponent), canActivate: [permissionGuard('reportes.ver')] },
      { path: 'planes', loadComponent: () => import('./pages/planes/planes').then(m => m.PlanesComponent), canActivate: [permissionGuard('planes.ver')] },
      { path: 'suscripciones', loadComponent: () => import('./pages/suscripciones/suscripciones').then(m => m.SuscripcionesComponent), canActivate: [permissionGuard('suscripciones.ver')] },
      { path: 'mi-tienda', loadComponent: () => import('./pages/mi-tienda/mi-tienda').then(m => m.MiTiendaComponent), canActivate: [permissionGuard(['storefront.configurar', 'sucursales.ver', 'admin.acceder'])] },
      { path: 'usuarios', loadComponent: () => import('./pages/usuarios/lista-usuarios/lista-usuarios').then(m => m.ListaUsuariosComponent), canActivate: [permissionGuard('usuarios.ver')] },
      { 
        path: 'empresas', 
        loadComponent: () => import('./pages/empresas/lista-empresas/lista-empresas').then(m => m.ListaEmpresasComponent), 
        canActivate: [scopeGuard(['PLATAFORMA']), permissionGuard('empresas.ver')] 
      },
      { path: 'sucursales', loadComponent: () => import('./pages/sucursales/lista-sucursales/lista-sucursales').then(m => m.ListaSucursalesComponent), canActivate: [permissionGuard('sucursales.ver')] },
      { path: 'categorias', loadComponent: () => import('./pages/categorias/lista-categorias/lista-categorias').then(m => m.ListaCategoriasComponent), canActivate: [permissionGuard(['categorias.ver', 'productos.ver'])] },
      { path: 'tallas-colores', loadComponent: () => import('./pages/catalogo/tallas-colores/tallas-colores').then(m => m.TallasColoresComponent), canActivate: [permissionGuard(['tallas.ver', 'productos.ver'])] },
      { path: 'productos', loadComponent: () => import('./pages/catalogo/productos/productos').then(m => m.ProductosComponent), canActivate: [permissionGuard('productos.ver')] },
      { path: 'inventario', loadComponent: () => import('./pages/inventario/lista-inventario/lista-inventario').then(m => m.ListaInventarioComponent), canActivate: [permissionGuard('inventario.ver')] },
      { path: 'caja', loadComponent: () => import('./pages/caja/caja').then(m => m.CajaComponent), canActivate: [permissionGuard(['ventas.crear', 'ventas.ver', 'admin.acceder'])] },
      { path: 'cajas-monitoreo', loadComponent: () => import('./pages/cajas-monitoreo/cajas-monitoreo').then(m => m.CajasMonitoreoComponent), canActivate: [permissionGuard(['ventas.ver', 'reportes.ver', 'caja.ver', 'admin.acceder'])] },
      { path: 'caja/pago/:id', loadComponent: () => import('./pages/caja/pago/caja-pago').then(m => m.CajaPagoComponent), canActivate: [permissionGuard(['ventas.crear', 'admin.acceder'])] },
      { path: 'caja/comprobante/:id', loadComponent: () => import('./pages/caja/comprobante/caja-comprobante').then(m => m.CajaComprobanteComponent), canActivate: [permissionGuard(['ventas.crear', 'ventas.ver', 'admin.acceder'])] },
      { path: 'bitacora', loadComponent: () => import('./pages/bitacora/lista-bitacora/lista-bitacora').then(m => m.ListaBitacoraComponent), canActivate: [permissionGuard('bitacora.ver')] },
      { 
        path: 'backup', 
        loadComponent: () => import('./pages/backup/backup').then(m => m.BackupComponent), 
        canActivate: [scopeGuard(['PLATAFORMA', 'EMPRESA'])] 
      },
      { path: 'bi_dashboard', loadComponent: () => import('./pages/bi-dashboard/bi-dashboard').then(m => m.BiDashboardComponent), canActivate: [permissionGuard('reportes.ver')] },
      { path: 'bi-dashboard', loadComponent: () => import('./pages/bi-dashboard/bi-dashboard').then(m => m.BiDashboardComponent), canActivate: [permissionGuard('reportes.ver')] },
      { path: 'triaje-chat', loadComponent: () => import('./pages/triaje-chat/triaje-chat').then(m => m.TriajeChatComponent), canActivate: [permissionGuard('admin.acceder')] },
      { path: 'catalogo', loadComponent: () => import('./pages/catalogo/catalogo').then(m => m.CatalogoComponent), canActivate: [permissionGuard('productos.ver')] },
      { path: 'proveedores', loadComponent: () => import('./pages/proveedores/proveedores').then(m => m.ProveedoresComponent), canActivate: [permissionGuard('compras.ver')] },
      { path: 'atender-reserva', loadComponent: () => import('./pages/atender-reserva/atender-reserva').then(m => m.AtenderReservaComponent), canActivate: [permissionGuard('ventas.ver')] },
      { path: 'devoluciones', loadComponent: () => import('./pages/devoluciones/devoluciones').then(m => m.DevolucionesComponent), canActivate: [permissionGuard('devoluciones.ver')] },
      { path: 'predicciones', loadComponent: () => import('./pages/predicciones/predicciones').then(m => m.PrediccionesComponent), canActivate: [permissionGuard(['reportes.ver', 'admin.acceder', 'ia.recomendar'])] }   
    ]
  },

  { path: '**', redirectTo: '' }
];
