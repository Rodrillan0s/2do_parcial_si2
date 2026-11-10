import sys
from app.modules.auth.services import (
    auth_services, users_services, roles_services, rbac_services,
    profile_services, asignaciones_services
)
from app.modules.saas.services import saas_services, tenant_services
from app.modules.catalogo.services import (
    productos_services, categorias_services, tallas_colores_services
)
from app.modules.inventario.services import (
    sucursales_services, ciudades_services, proveedores_services, compras_lotes_services
)
from app.modules.ecommerce.services import paypal_service
from app.modules.reservas.services import atender_reserva_services
from app.modules.pos.services import comprobante_service
from app.modules.pedidos.services import reportes_services, kpis_services, devoluciones_services
from app.modules.ia.services import asistente_services
from app.modules.admin.services import backup_services, bitacora_services, notificaciones_services

_SERVICES = {
    'auth_services': auth_services,
    'users_services': users_services,
    'roles_services': roles_services,
    'rbac_services': rbac_services,
    'profile_services': profile_services,
    'asignaciones_services': asignaciones_services,
    'saas_services': saas_services,
    'tenant_services': tenant_services,
    'productos_services': productos_services,
    'categorias_services': categorias_services,
    'tallas_colores_services': tallas_colores_services,
    'sucursales_services': sucursales_services,
    'ciudades_services': ciudades_services,
    'proveedores_services': proveedores_services,
    'compras_lotes_services': compras_lotes_services,
    'paypal_service': paypal_service,
    'atender_reserva_services': atender_reserva_services,
    'comprobante_service': comprobante_service,
    'reportes_services': reportes_services,
    'devoluciones_services': devoluciones_services,
    'kpis_services': kpis_services,
    'asistente_services': asistente_services,
    'backup_services': backup_services,
    'bitacora_services': bitacora_services,
    'notificaciones_services': notificaciones_services,
}

for name, mod in _SERVICES.items():
    sys.modules[f'app.services.{name}'] = mod
