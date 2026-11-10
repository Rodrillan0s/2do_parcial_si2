import sys
from app.modules.auth.routes import auth_routes, users_routes, roles_routes, rbac_routes, profile_routes
from app.modules.saas.routes import saas_routes, tenant_routes
from app.modules.catalogo.routes import productos_routes, categorias_routes, tallas_colores_routes, catalogo_routes, media_routes
from app.modules.inventario.routes import sucursales_routes, ciudades_routes, inventario_routes, proveedores_routes, compras_lotes_routes
from app.modules.ecommerce.routes import carrito_routes, pago_routes
from app.modules.reservas.routes import reserva_routes, atender_reserva_routes
from app.modules.pos.routes import pos_routes, caja_routes, caja_pago_routes, comprobante_routes
from app.modules.pedidos.routes import pedido_routes, reportes_routes, kpis_routes, motor_reportes_routes, devoluciones_routes
from app.modules.ia.routes import asistente_routes
from app.modules.admin.routes import backup_routes, bitacora_routes, main_routes, notificaciones_routes

_ROUTES = {
    'auth_routes': auth_routes,
    'users_routes': users_routes,
    'roles_routes': roles_routes,
    'rbac_routes': rbac_routes,
    'profile_routes': profile_routes,
    'saas_routes': saas_routes,
    'tenant_routes': tenant_routes,
    'productos_routes': productos_routes,
    'categorias_routes': categorias_routes,
    'tallas_colores_routes': tallas_colores_routes,
    'catalogo_routes': catalogo_routes,
    'media_routes': media_routes,
    'sucursales_routes': sucursales_routes,
    'ciudades_routes': ciudades_routes,
    'inventario_routes': inventario_routes,
    'proveedores_routes': proveedores_routes,
    'compras_lotes_routes': compras_lotes_routes,
    'carrito_routes': carrito_routes,
    'pago_routes': pago_routes,
    'reserva_routes': reserva_routes,
    'atender_reserva_routes': atender_reserva_routes,
    'pos_routes': pos_routes,
    'caja_routes': caja_routes,
    'caja_pago_routes': caja_pago_routes,
    'comprobante_routes': comprobante_routes,
    'pedido_routes': pedido_routes,
    'devoluciones_routes': devoluciones_routes,
    'reportes_routes': reportes_routes,
    'kpis_routes': kpis_routes,
    'motor_reportes_routes': motor_reportes_routes,
    'asistente_routes': asistente_routes,
    'backup_routes': backup_routes,
    'bitacora_routes': bitacora_routes,
    'main_routes': main_routes,
    'notificaciones_routes': notificaciones_routes,
}

for name, mod in _ROUTES.items():
    sys.modules[f'app.routes.{name}'] = mod
