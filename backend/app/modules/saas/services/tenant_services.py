import re
from app.modules.saas.repos import tenant_repos
from fastapi import Request
from app.modules.admin.services import bitacora_services
from app.core.tenant_guard import (
    es_administrador_global,
    validar_acceso_recurso_tenant,
    obtener_alcance_usuario
)

def listar_empresas(payload: dict = None):
    empresas = tenant_repos.obtener_todas_las_empresas()
    
    # Si el usuario no es de alcance global (Plataforma), solo puede ver su propia empresa
    if payload and not es_administrador_global(payload):
        id_empresa_usuario = payload.get('id_empresa')
        empresas = [e for e in empresas if e.get('id_empresa') == id_empresa_usuario]
        
    return {
        "success": True,
        "message": "Empresas (Tenants) recuperadas exitosamente",
        "data": empresas
    }

def obtener_empresa(id_empresa: int, payload: dict = None):
    if payload:
        validar_acceso_recurso_tenant(payload, id_empresa, "Empresa (Tenant)")
        
    empresa = tenant_repos.obtener_empresa_por_id_db(id_empresa)
    if not empresa:
        raise ValueError("La empresa solicitada no existe.")
    return {
        "success": True,
        "data": empresa
    }

def registrar_empresa(data: dict, payload: dict, request: Request = None):
    nombre_comercial = data.get('nombre_empresa') or data.get('nombre_comercial')
    razon_social = data.get('razon_social')
    nit = data.get('nit')
    correo = data.get('correo')
    telefono = data.get('telefono')
    direccion_fiscal = data.get('direccion_fiscal') or data.get('direccion')
    ciudad = data.get('ciudad')
    logo = data.get('logo')

    # Validaciones de obligatoriedad
    if not nombre_comercial or not str(nombre_comercial).strip():
        raise ValueError("El Nombre Comercial de la tienda/empresa es obligatorio.")
    if not razon_social or not str(razon_social).strip():
        razon_social = nombre_comercial
    if not nit or not str(nit).strip():
        raise ValueError("El NIT / Identificación Fiscal es obligatorio.")
    if not correo or not str(correo).strip():
        raise ValueError("El correo electrónico empresarial es obligatorio.")
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', str(correo).strip()):
        raise ValueError("El formato del correo electrónico empresarial no es válido.")
    if not telefono or not str(telefono).strip():
        raise ValueError("El teléfono de contacto es obligatorio.")
    if not direccion_fiscal or not str(direccion_fiscal).strip():
        raise ValueError("La dirección fiscal es obligatoria.")
    if not ciudad or not str(ciudad).strip():
        raise ValueError("La ciudad de la empresa es obligatoria.")

    # Validación de unicidad de NIT
    nit_limpio = str(nit).strip()
    if tenant_repos.existe_nit_db(nit_limpio):
        raise ValueError(f"Ya existe un Tenant registrado con el NIT '{nit_limpio}'. No se permiten duplicados.")

    datos_tenant = {
        "nombre_empresa": str(nombre_comercial).strip().upper(),
        "razon_social": str(razon_social).strip().upper(),
        "nit": nit_limpio,
        "correo": str(correo).strip().lower(),
        "telefono": str(telefono).strip(),
        "direccion_fiscal": str(direccion_fiscal).strip(),
        "ciudad": str(ciudad).strip(),
        "logo": str(logo).strip() if logo else None,
        "estado": "ACTIVO"
    }

    nuevo_id = tenant_repos.crear_empresa_db(datos_tenant)
    if not nuevo_id:
        raise ValueError("No se pudo crear el registro del nuevo Tenant en la base de datos.")

    # Registro en Bitácora de Auditoría
    try:
        bitacora_services.registrar_accion(
            modulo="EMPRESAS",
            accion="REGISTRAR_TENANT",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="empresa",
            id_entidad=str(nuevo_id),
            descripcion=f"Nuevo Tenant registrado por SuperAdmin: {datos_tenant['nombre_empresa']} (NIT: {nit_limpio})",
            datos_nuevos=datos_tenant,
            request=request
        )
    except Exception as e:
        print(f"Advertencia: No se pudo auditar registro de empresa en bitácora: {e}")

    empresa_creada = tenant_repos.obtener_empresa_por_id_db(nuevo_id)
    return {
        "success": True,
        "message": f"¡Tenant '{datos_tenant['nombre_empresa']}' registrado exitosamente en estado ACTIVO!",
        "id_empresa": nuevo_id,
        "data": empresa_creada
    }

def actualizar_empresa(id_empresa: int, data: dict, payload: dict, request: Request = None):
    if id_empresa <= 0:
        raise ValueError("ID de empresa no válido.")

    empresa_anterior = tenant_repos.obtener_empresa_por_id_db(id_empresa)
    if not empresa_anterior:
        raise ValueError("La empresa especificada no existe.")

    nombre_comercial = data.get('nombre_empresa') or data.get('nombre_comercial')
    razon_social = data.get('razon_social')
    nit = data.get('nit')
    correo = data.get('correo')
    telefono = data.get('telefono')
    direccion_fiscal = data.get('direccion_fiscal') or data.get('direccion')
    ciudad = data.get('ciudad')
    logo = data.get('logo')
    estado = data.get('estado') or empresa_anterior.get('estado', 'ACTIVO')

    if not nombre_comercial or not str(nombre_comercial).strip():
        raise ValueError("El Nombre Comercial es obligatorio.")
    if not nit or not str(nit).strip():
        raise ValueError("El NIT es obligatorio.")

    nit_limpio = str(nit).strip()
    if tenant_repos.existe_nit_db(nit_limpio, exclude_id_empresa=id_empresa):
        raise ValueError(f"Ya existe otra empresa registrada con el NIT '{nit_limpio}'.")

    if correo and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', str(correo).strip()):
        raise ValueError("El formato del correo electrónico empresarial no es válido.")

    if str(estado).strip().upper() not in ('ACTIVO', 'INACTIVO'):
        raise ValueError('Estado de empresa invalido.')

    datos_actualizados = {
        "nombre_empresa": str(nombre_comercial).strip().upper(),
        "razon_social": str(razon_social or nombre_comercial).strip().upper(),
        "nit": nit_limpio,
        "correo": str(correo).strip().lower() if correo else empresa_anterior.get('correo', ''),
        "telefono": str(telefono).strip() if telefono else empresa_anterior.get('telefono', ''),
        "direccion_fiscal": str(direccion_fiscal).strip() if direccion_fiscal else empresa_anterior.get('direccion_fiscal', ''),
        "ciudad": str(ciudad).strip() if ciudad else empresa_anterior.get('ciudad', 'Santa Cruz'),
        "logo": str(logo).strip() if logo else empresa_anterior.get('logo'),
        "estado": str(estado).strip().upper()
    }

    exito = tenant_repos.actualizar_empresa_db(id_empresa, datos_actualizados)
    if not exito:
        raise ValueError("No se pudo actualizar la información de la empresa.")

    try:
        bitacora_services.registrar_accion(
            modulo="EMPRESAS",
            accion="ACTUALIZAR_TENANT",
            nivel="INFO",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="empresa",
            id_entidad=str(id_empresa),
            descripcion=f"Tenant actualizado: {datos_actualizados['nombre_empresa']} (ID: {id_empresa})",
            datos_anteriores=empresa_anterior,
            datos_nuevos=datos_actualizados,
            request=request
        )
    except Exception as e:
        print(f"Advertencia: No se pudo auditar en bitácora: {e}")

    empresa_nueva = tenant_repos.obtener_empresa_por_id_db(id_empresa)
    return {
        "success": True,
        "message": "Empresa actualizada exitosamente",
        "data": empresa_nueva
    }

def borrar_empresa(id_empresa: int, payload: dict, request: Request = None):
    if id_empresa <= 0:
        raise ValueError("ID de empresa no válido.")

    empresa_anterior = tenant_repos.obtener_empresa_por_id_db(id_empresa)
    if not empresa_anterior:
        raise ValueError("La empresa especificada no existe.")

    exito = tenant_repos.eliminar_empresa_db(id_empresa)
    if not exito:
        raise ValueError("No se pudo eliminar la empresa seleccionada.")

    try:
        bitacora_services.registrar_accion(
            modulo="EMPRESAS",
            accion="ELIMINAR_TENANT",
            nivel="WARNING",
            resultado="EXITO",
            payload_jwt=payload,
            entidad="empresa",
            id_entidad=str(id_empresa),
            descripcion=f"Tenant desactivado: {empresa_anterior.get('nombre_empresa')} (ID: {id_empresa})",
            datos_anteriores=empresa_anterior,
            request=request
        )
    except Exception as e:
        print(f"Advertencia: No se pudo auditar en bitácora: {e}")

    return {
        "success": True,
        "message": "Empresa desactivada exitosamente"
    }