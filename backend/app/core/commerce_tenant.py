"""Public store selection is distinct from employee authorization."""
from fastapi import HTTPException
from app.modules.catalogo.repos import catalogo_repos
from app.core.tenant_guard import obtener_alcance_usuario, resolver_tenant_operacion, resolver_sucursal_autorizada


def resolver_empresa_compra(payload, solicitada=None, sucursal_empresa=None, id_sucursal=None):
    alcance = obtener_alcance_usuario(payload)
    if alcance != 'CLIENTE':
        empresa = resolver_tenant_operacion(payload, solicitada or sucursal_empresa)
        if sucursal_empresa is not None and empresa != sucursal_empresa:
            raise HTTPException(403, detail='La sucursal pertenece a otra empresa.')
        if id_sucursal is not None:
            resolver_sucursal_autorizada(payload, id_sucursal)
        return empresa
    # Clients can browse/buy across public stores, but repositories still check ownership.
    if solicitada is not None and sucursal_empresa is not None and solicitada != sucursal_empresa:
        raise HTTPException(403, detail='La sucursal no pertenece a la tienda seleccionada.')
    tiendas = catalogo_repos.obtener_tenants_publicos()
    empresa = sucursal_empresa or solicitada or (tiendas[0]['id_empresa'] if tiendas else None)
    if not any(t['id_empresa'] == empresa for t in tiendas):
        raise HTTPException(400, detail='Seleccione una tienda activa.')
    return empresa
