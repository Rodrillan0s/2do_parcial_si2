import sys
from app.modules.auth.repos import (
    auth_repos, users_repos, roles_repos, rbac_repos, profile_repos, session_repos
)
from app.modules.saas.repos import tenant_repos
from app.modules.catalogo.repos import (
    productos_repos, categorias_repos, tallas_colores_repos, catalogo_repos
)
from app.modules.inventario.repos import (
    sucursales_repos, ciudades_repos, inventario_repos, proveedores_repos
)
from app.modules.ecommerce.repos import carrito_repos, pago_repos
from app.modules.reservas.repos import reserva_repos, atender_reserva_repos
from app.modules.pos.repos import pos_repos, caja_repos, caja_pago_repos
from app.modules.pedidos.repos import pedido_repos, reportes_repos, kpis_repos, devoluciones_repos
from app.modules.admin.repos import bitacora_repos, notificaciones_repos

_REPOS = {
    'auth_repos': auth_repos,
    'users_repos': users_repos,
    'roles_repos': roles_repos,
    'rbac_repos': rbac_repos,
    'profile_repos': profile_repos,
    'session_repos': session_repos,
    'tenant_repos': tenant_repos,
    'productos_repos': productos_repos,
    'categorias_repos': categorias_repos,
    'tallas_colores_repos': tallas_colores_repos,
    'catalogo_repos': catalogo_repos,
    'sucursales_repos': sucursales_repos,
    'ciudades_repos': ciudades_repos,
    'inventario_repos': inventario_repos,
    'proveedores_repos': proveedores_repos,
    'carrito_repos': carrito_repos,
    'pago_repos': pago_repos,
    'reserva_repos': reserva_repos,
    'atender_reserva_repos': atender_reserva_repos,
    'pos_repos': pos_repos,
    'caja_repos': caja_repos,
    'caja_pago_repos': caja_pago_repos,
    'pedido_repos': pedido_repos,
    'devoluciones_repos': devoluciones_repos,
    'reportes_repos': reportes_repos,
    'kpis_repos': kpis_repos,
    'bitacora_repos': bitacora_repos,
    'notificaciones_repos': notificaciones_repos,
}

for name, mod in _REPOS.items():
    sys.modules[f'app.repos.{name}'] = mod
